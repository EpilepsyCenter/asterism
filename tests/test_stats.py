"""Tests for the stats core (SPEC §8, §10, §11).

Where possible, cross-checked against a second implementation (scipy) so the numbers
are trustworthy independent of pingouin's internals — the same spirit as the
golden-dataset tests (§13 step 4).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from asterism.core.contract import Dataset
from asterism.core.design import detect_design
from asterism.core.stats import run_analysis, subject_frame


def _ds_two_groups(a, b, *, shared=False):
    """Build a one-factor Dataset from two arrays of subject-level values."""
    rows = []
    if shared:
        for i, (x, y) in enumerate(zip(a, b)):
            rows.append({"value": x, "subject": f"s{i}", "cond": "A"})
            rows.append({"value": y, "subject": f"s{i}", "cond": "B"})
    else:
        sid = 0
        for x in a:
            rows.append({"value": x, "subject": f"s{sid}", "cond": "A"}); sid += 1
        for y in b:
            rows.append({"value": y, "subject": f"s{sid}", "cond": "B"}); sid += 1
    return Dataset(pd.DataFrame(rows), factors=("cond",))


def _ds_k_groups(groups: dict, *, shared=False):
    rows = []
    if shared:
        n = len(next(iter(groups.values())))
        for i in range(n):
            for name, vals in groups.items():
                rows.append({"value": vals[i], "subject": f"s{i}", "cond": name})
    else:
        sid = 0
        for name, vals in groups.items():
            for v in vals:
                rows.append({"value": v, "subject": f"s{sid}", "cond": name}); sid += 1
    return Dataset(pd.DataFrame(rows), factors=("cond",))


# --- Welch t-test, cross-checked against scipy ------------------------------

def test_welch_ttest_matches_scipy():
    from scipy import stats
    a = np.array([10.0, 11.0, 12.0, 9.0, 10.5, 11.5])
    b = np.array([16.0, 15.0, 17.0, 16.5, 15.5, 16.2])
    ds = _ds_two_groups(a, b)
    res = run_analysis(ds)
    t_scipy, p_scipy = stats.ttest_ind(a, b, equal_var=False)
    assert res.test == "Welch's t-test"
    assert np.isclose(res.statistic, t_scipy, rtol=1e-4)
    assert np.isclose(res.p, p_scipy, rtol=1e-4)
    # the trust-critical caveat travels into the result (SPEC §8)
    assert any("Welch" in n for n in res.notes)
    s = res.results_string()
    assert "Welch's t-test" in s and "Cohen's d" in s
    assert ("p = " in s or "p < " in s)


def test_paired_ttest_matches_scipy():
    from scipy import stats
    pre = np.array([5.0, 6.0, 5.5, 7.0, 6.5, 5.8])
    post = np.array([7.0, 8.5, 7.2, 9.0, 8.0, 7.6])
    ds = _ds_two_groups(pre, post, shared=True)
    res = run_analysis(ds)
    t_scipy, p_scipy = stats.ttest_rel(pre, post)
    assert res.test == "paired t-test"
    assert np.isclose(res.statistic, t_scipy, rtol=1e-4)
    assert np.isclose(res.p, p_scipy, rtol=1e-4)


# --- one-way ANOVA, cross-checked against scipy -----------------------------

def test_one_way_anova_matches_scipy_and_has_tukey():
    from scipy import stats
    g = {"A": [10, 11, 12, 9, 10.5, 11.2],
         "B": [13, 14, 12.5, 13.5, 14.2, 13.1],
         "C": [16, 15, 17, 16.5, 15.5, 16.2]}
    ds = _ds_k_groups(g)
    res = run_analysis(ds)
    f_scipy, p_scipy = stats.f_oneway(*[np.array(v) for v in g.values()])
    assert res.test == "one-way ANOVA"
    assert np.isclose(res.statistic, f_scipy, rtol=1e-4)
    assert np.isclose(res.p, p_scipy, rtol=1e-4)
    assert res.df == (2.0, 15.0)             # 3 groups, 18 subjects
    assert len(res.posthoc) == 3             # A-B, A-C, B-C
    assert "F(2, 15)" in res.results_string()


def test_rm_anova_has_geisser_greenhouse():
    g = {"d1": [10, 11, 9, 10.5, 11.2, 9.8],
         "d2": [12, 13, 11.5, 12.5, 13.1, 11.9],
         "d3": [15, 16, 14.5, 15.5, 16.2, 14.9]}
    ds = _ds_k_groups(g, shared=True)
    res = run_analysis(ds)
    assert "repeated-measures" in res.test
    assert "Geisser–Greenhouse" in res.corrections
    assert res.p is not None and res.p < 0.05


# --- two-way ANOVA ----------------------------------------------------------

def test_two_way_anova_runs():
    rows = []
    sid = 0
    rng = np.random.default_rng(0)
    for g in ("WT", "KO"):
        for t in ("veh", "cno"):
            base = {"WT": 10, "KO": 14}[g] + {"veh": 0, "cno": 3}[t]
            for _ in range(5):
                rows.append({"value": base + rng.normal(0, 1),
                             "subject": f"s{sid}", "genotype": g, "treatment": t})
                sid += 1
    ds = Dataset(pd.DataFrame(rows), factors=("genotype", "treatment"))
    res = run_analysis(ds)
    assert res.test == "two-way ANOVA"
    assert res.p is not None
    assert "anova_table" in res.settings


# --- regression / correlation ----------------------------------------------

def test_regression_reports_r2_and_pearson():
    rng = np.random.default_rng(1)
    x = np.linspace(0, 10, 30)
    y = 2.0 * x + 1.0 + rng.normal(0, 0.5, 30)
    df = pd.DataFrame({"value": y, "subject": [f"s{i}" for i in range(30)], "dose": x})
    ds = Dataset(df, factors=(), x="dose")
    res = run_analysis(ds)
    assert res.test == "linear regression"
    assert res.statistic_name == "R²" and res.statistic > 0.95
    assert "Pearson r" in res.results_string()


# --- KS ---------------------------------------------------------------------

def test_ks_matches_scipy():
    from scipy import stats
    rng = np.random.default_rng(2)
    a = rng.normal(0, 1, 200)
    b = rng.normal(0.6, 1, 200)
    df = pd.DataFrame({"value": np.concatenate([a, b]),
                       "subject": [f"s{i}" for i in range(400)]})
    ds = Dataset(df, factors=())
    res = run_analysis(ds, ks_samples=(a, b))
    d_scipy, p_scipy = stats.ks_2samp(a, b)
    assert np.isclose(res.statistic, d_scipy, rtol=1e-6)
    assert np.isclose(res.p, p_scipy, rtol=1e-6)
    assert "Kolmogorov" in res.test


# --- non-parametric override (advisory normality flip, SPEC §8) -------------

def test_parametric_override_gives_mann_whitney():
    a = np.array([10.0, 11.0, 12.0, 9.0, 10.5])
    b = np.array([16.0, 15.0, 17.0, 16.5, 15.5])
    ds = _ds_two_groups(a, b)
    res = run_analysis(ds, parametric=False)
    assert res.test == "Mann–Whitney U"
    assert not res.parametric


# --- subject-mean aggregation is the default unit (SPEC §3) ------------------

def test_stats_run_on_subject_means_not_replicates():
    # 2 subjects per group, 50 replicates each — n must be 2, not 100
    rows = []
    for grp, base in (("A", 10.0), ("B", 16.0)):
        for s in range(2):
            for _ in range(50):
                rows.append({"value": base, "subject": f"{grp}{s}",
                             "replicate": "r", "cond": grp})
    ds = Dataset(pd.DataFrame(rows), factors=("cond",))
    sf = subject_frame(ds)
    assert len(sf) == 4  # 4 subjects, not 200 rows
    res = run_analysis(ds)
    assert res.n_by_level == {"A": 2, "B": 2}


# --- result object shape ----------------------------------------------------

def test_result_serialises_and_info_block():
    ds = _ds_two_groups([10, 11, 12, 9], [16, 15, 17, 16])
    res = run_analysis(ds)
    info = res.info_block()
    assert info["unit_of_analysis"] == "subject means"
    assert "results_string" in info
    d = res.to_dict()
    assert d["statistic_name"] == "t"
    assert isinstance(d["p"], float)


def test_multiple_metrics_requires_selection():
    rows = [
        {"value": 1.0, "subject": "s1", "cond": "A", "metric": "amp"},
        {"value": 2.0, "subject": "s2", "cond": "B", "metric": "amp"},
        {"value": 3.0, "subject": "s1", "cond": "A", "metric": "freq"},
    ]
    ds = Dataset(pd.DataFrame(rows), factors=("cond",))
    res = run_analysis(ds)  # ambiguous → graceful error
    assert res.error is not None and "metric" in res.error
