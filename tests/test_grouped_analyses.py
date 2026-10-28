"""M4 analyses: two-way ANOVA, multiple t tests, nested t test / one-way ANOVA.

Golden values come from Prism 11 projects (tests/golden/prism_golden.json, harvested by
tests/golden/harvest.py); the rest are checked against statsmodels / pingouin / scipy.
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from asterism.analysis import anova2, engine, multiple_t
from asterism.doc.model import Analysis, Project

from golden_data import Missing, golden  # noqa: E402

GOLDEN = golden("prism_golden.json")


def _cells(case):
    d = case["data"]
    R, K = len(d["rows"]), len(d["sets"])
    return [[d["sets"][k][r] for k in range(K)] for r in range(R)]


# ---------------------------------------------------------------------------
# Golden: Prism two-way repeated-measures ANOVA (matched rows, unequal groups)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("case", GOLDEN.get("two_way", []), ids=lambda c: c["method"])
def test_two_way_rm_matches_prism(case):
    assert case["design"] == "REPEATED_MEASURES_BY_ROWS"
    C = _cells(case)
    fit = anova2.mixed(anova2._subjects_by_group(C, "rows"), gg=False)
    tb, pr = fit["table"], case["anova"]
    for ours, theirs in (("within", "rowFactor"), ("between", "colFactor"),
                         ("inter", "rowFactorVsColFactor")):
        assert tb[ours]["ss"] == pytest.approx(pr[theirs]["ss"], rel=1e-9)
        assert tb[ours]["F"] == pytest.approx(pr[theirs]["fTest"]["f"], rel=1e-9)
        assert tb[ours]["p"] == pytest.approx(pr[theirs]["fTest"]["p"], rel=1e-7)
    assert fit["residual"][0] == pytest.approx(pr["residual"]["ss"], rel=1e-9)
    assert fit["residual"][1] == pr["residual"]["df"]

    method = {"Bonferroni-Dunn": "bonferroni", "Tukey": "tukey"}[case["method"]]
    R, K = len(C), len(C[0])
    fams = anova2.comparisons("rm_rows", fit, "both", method, 0.95,
                              [f"r{i}" for i in range(R)], [f"c{i}" for i in range(K)])
    ours = {frozenset(pair): r for _, res, pairs in fams for r, pair in zip(res, pairs)}
    assert len(ours) == len(case["comparisons"])
    for cp in case["comparisons"]:
        a = (cp["a"]["row"], cp["a"]["col"])
        b = (cp["b"]["row"], cp["b"]["col"])
        o = ours[frozenset((a, b))]
        assert abs(o["diff"]) == pytest.approx(abs(cp["diff"]), rel=1e-9)
        assert o["se"] == pytest.approx(cp["se"], rel=1e-9)
        assert o["df"] == cp["df"]
        assert o["p"] == pytest.approx(cp["p_adj"], rel=1e-6, abs=1e-12)
        width = o["ci"][1] - o["ci"][0]
        assert width == pytest.approx(cp["ci"][1] - cp["ci"][0], rel=1e-6)


# ---------------------------------------------------------------------------
# Golden: Prism multiple t tests / Mann-Whitney tests with Holm-Šídák
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("case", GOLDEN.get("multiple_tests", []), ids=lambda c: c["test"][:22])
def test_multiple_tests_match_prism(case):
    test = {"MULTIPLE_UNPAIRED_TWO_SAMPLE_UNEQUAL_SD_TESTS": "welch",
            "MULTIPLE_MANN_WHITNEY_TESTS": "mw"}[case["test"]]
    d = case["data"]
    raw = []
    for row in case["rows"]:
        r = row["row"]
        a = np.array([v for v in d["sets"][0][r] if v is not None])
        b = np.array([v for v in d["sets"][1][r] if v is not None])
        o = multiple_t.row_test(a, b, test)
        assert o["stat"] == pytest.approx(row["stat"], rel=1e-9)
        assert o["p"] == pytest.approx(row["p"], rel=1e-9)
        raw.append(o["p"])
    if case["correction"] == "HOLM_SIDAK":
        for o, row in zip(multiple_t.adjust(raw, "holm_sidak"), case["rows"]):
            assert o == pytest.approx(row["p_adj"], rel=1e-9)


def test_mann_whitney_exact_with_ties():
    """Prism's exact P with ties comes from the permutation distribution of mid-ranks."""
    from asterism.core.stats import _mann_whitney
    a, b = [1, 2, 2, 3, 5], [4, 5, 5, 6, 7, 7]
    ranks = stats.rankdata(a + b)
    # brute force over all splits
    import itertools
    obs = ranks[:5].sum()
    mu = 5 * 12 / 2
    sums = [ranks[list(ix)].sum() for ix in itertools.combinations(range(11), 5)]
    p = np.mean([abs(s - mu) >= abs(obs - mu) - 1e-9 for s in sums])
    assert _mann_whitney(a, b).p == pytest.approx(p, rel=1e-12)


# ---------------------------------------------------------------------------
# References
# ---------------------------------------------------------------------------

def test_ordinary_two_way_is_type_iii():
    import statsmodels.api as sm
    import statsmodels.formula.api as smf
    rng = np.random.default_rng(1)
    R, K = 3, 2
    cells_ = [[list(rng.normal(10 + r + 2 * c, 2, size=3 + (r + c) % 3)) for c in range(K)] for r in range(R)]
    fit = anova2.ordinary(cells_)
    df = pd.DataFrame([(r, c, v) for r in range(R) for c in range(K) for v in cells_[r][c]],
                      columns=["ra", "ca", "y"])
    ref = sm.stats.anova_lm(smf.ols("y ~ C(ra, Sum) * C(ca, Sum)", df).fit(), typ=3)
    assert fit["table"]["rows"]["ss"] == pytest.approx(ref.loc["C(ra, Sum)", "sum_sq"])
    assert fit["table"]["cols"]["ss"] == pytest.approx(ref.loc["C(ca, Sum)", "sum_sq"])
    assert fit["table"]["inter"]["ss"] == pytest.approx(ref.loc["C(ra, Sum):C(ca, Sum)", "sum_sq"])
    assert fit["table"]["inter"]["p"] == pytest.approx(ref.loc["C(ra, Sum):C(ca, Sum)", "PR(>F)"])


def test_fully_matched_two_way_matches_pingouin():
    import pingouin as pg
    rng = np.random.default_rng(2)
    n, R, K = 6, 3, 2
    Y = rng.normal(0, 1, (n, R, K)) + rng.normal(0, 1, (n, 1, 1)) + np.arange(R)[None, :, None] * 0.5
    fit = anova2.both_within([[[Y[s, r, c] for s in range(n)] for c in range(K)] for r in range(R)])
    long = pd.DataFrame([(s, r, c, Y[s, r, c]) for s in range(n) for r in range(R) for c in range(K)],
                        columns=["s", "r", "c", "y"])
    ref = pg.rm_anova(long, dv="y", within=["r", "c"], subject="s").set_index("Source")
    for ours, theirs in (("rows", "r"), ("cols", "c"), ("inter", "r * c")):
        assert fit["table"][ours]["F"] == pytest.approx(ref.loc[theirs, "F"])
        assert fit["table"][ours]["p"] == pytest.approx(ref.loc[theirs, "p_unc"])


def test_fdr_methods_match_statsmodels():
    from statsmodels.stats.multitest import multipletests
    p = np.array([0.001, 0.008, 0.039, 0.041, 0.042, 0.06, 0.074, 0.205, 0.212, 0.216])
    assert np.allclose(multiple_t.adjust(list(p), "fdr_bh"), multipletests(p, method="fdr_bh")[1])
    assert np.allclose(multiple_t.adjust(list(p), "fdr_by"), multipletests(p, method="fdr_by")[1])
    for Q in (0.01, 0.05, 0.1, 0.2):
        assert (multiple_t._bky_discoveries(p, Q) == multipletests(p, alpha=Q, method="fdr_tsbky")[0]).all()
        # q values are consistent with the decisions
        assert ((np.array(multiple_t.adjust(list(p), "fdr_bky")) <= Q) ==
                multiple_t._bky_discoveries(p, Q)).all()


# ---------------------------------------------------------------------------
# Through the document model
# ---------------------------------------------------------------------------

def _grouped_project(reps=4, rows=3, sets=2, seed=0):
    p = Project(engine)
    t = p.add_table(table_type="grouped", y_format="replicates", replicates=reps, ncols=sets,
                    example=False)
    rng = np.random.default_rng(seed)
    for ds in range(sets):
        for r in range(rows):
            for s in range(reps):
                t.set(r, t.flat(ds, s), float(10 + 3 * ds + r + rng.normal(0, 1)), emit=False)
    t.changed.emit()
    return p, t


@pytest.mark.parametrize("design", ["ordinary", "rm_rows", "rm_cols", "rm_both"])
@pytest.mark.parametrize("compare", ["both", "cells", "main_cols", "main_rows", "none"])
def test_two_way_runs_every_design(design, compare):
    p, t = _grouped_project()
    a = p.add_analysis(Analysis("anova2", t, [0, 1], {"design": design, "compare": compare}))
    assert a.result.error is None, a.result.error
    titles = [pg.title for pg in a.result.pages]
    assert titles[:2] == ["Results", "ANOVA table"]
    assert ("Comparisons" in titles) == (compare != "none")
    assert a.name.startswith("Two-way")


def test_two_way_live_updates_and_cell_comparisons():
    p, t = _grouped_project()
    a = p.add_analysis(Analysis("anova2", t, [0, 1], {"design": "ordinary", "compare": "rows"}))
    before = a.result.p
    assert len(a.result.cell_comparisons) == 3          # one per row
    t.set(0, t.flat(1, 0), 99.0)
    assert a.result.p != before


def test_two_way_errors_are_friendly():
    p = Project(engine)
    t = p.add_table(table_type="column", example=True)
    a = p.add_analysis(Analysis("anova2", t, t.used_columns(), {}))
    assert "Grouped" in a.result.error


def test_multiple_t_through_model():
    p, t = _grouped_project(rows=5)
    a = p.add_analysis(Analysis("multiple_t", t, [0, 1], {"test": "student", "correction": "fdr_bky"}))
    assert a.result.error is None
    assert len(a.result.rows) == 5
    r0 = a.result.rows[0]
    ref = stats.ttest_ind(t.row_values(0, 0), t.row_values(0, 1))
    assert r0[1] == pytest.approx(ref.pvalue)
    assert a.result.pages[0].columns[0] == "Discovery?"
    a2 = p.add_analysis(Analysis("multiple_t", t, [0, 1, 0], {}))
    assert a2.result.error


def _nested_project(groups=2, subjects=4, reps=5, unequal=False, seed=5):
    p = Project(engine)
    t = p.add_table(table_type="nested", replicates=subjects, ncols=groups, example=False)
    rng = np.random.default_rng(seed)
    for ds in range(groups):
        for sub in range(subjects):
            mu = 50 - 5 * ds + rng.normal(0, 5)
            n = reps - (sub % 2 if unequal else 0)
            for r in range(n):
                t.set(r, t.flat(ds, sub), float(mu + rng.normal(0, 3)), emit=False)
    t.changed.emit()
    return p, t


def test_nested_t_equals_t_test_on_subject_means():
    p, t = _nested_project()
    a = p.add_analysis(Analysis("nested", t, [0, 1], {}))
    assert a.result.error is None
    assert a.name.startswith("Nested t test")
    means = [[np.mean([t.get(r, t.flat(ds, s)) for r in range(5)]) for s in range(4)] for ds in range(2)]
    assert a.result.p == pytest.approx(stats.ttest_ind(means[0], means[1]).pvalue, rel=1e-3)


def test_nested_anova_equals_anova_on_subject_means():
    p, t = _nested_project(groups=3)
    a = p.add_analysis(Analysis("nested", t, [0, 1, 2], {}))
    assert a.result.error is None
    assert a.name.startswith("Nested one-way ANOVA")
    means = [[np.mean([t.get(r, t.flat(ds, s)) for r in range(5)]) for s in range(4)] for ds in range(3)]
    assert a.result.p == pytest.approx(stats.f_oneway(*means).pvalue, rel=1e-3)
    assert len(a.result.comparisons) == 3
    assert [pg.title for pg in a.result.pages] == ["Results", "Comparisons"]


def test_nested_handles_unequal_replicates():
    p, t = _nested_project(unequal=True)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        a = p.add_analysis(Analysis("nested", t, [0, 1], {}))
    assert a.result.error is None
    assert 0 < a.result.p < 1
