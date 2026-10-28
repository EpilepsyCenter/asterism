"""Column analyses (M3): golden tests vs Prism, cross-checks vs scipy/statsmodels/pingouin."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pingouin as pg
import pytest
from scipy import stats
from statsmodels.stats.multitest import multipletests

from asterism.analysis import anova, engine, frequency, normality
from asterism.doc.model import Analysis, Project

from golden_data import Missing, golden  # noqa: E402

GOLDEN = golden("prism_golden.json")

A = [24.0, 26.0, 31.0, 27.0, 29.0, 25.0]
B = [31.0, 35.0, 30.0, 36.0, 33.0, 34.0, 32.0]
C = [29.0, 27.0, 33.0, 28.0, 30.0, 31.0]
D = [40.0, 38.0, 36.0, 41.0, 39.0, 35.0]


def _run(kind, groups, **params):
    p = Project(engine)
    t = p.add_table(table_type="column")
    for c, vals in enumerate(groups):
        for r, v in enumerate(vals):
            t.set(r, c, v, emit=False)
    a = p.add_analysis(Analysis(kind, t, list(range(len(groups))), params))
    assert a.result.error is None, a.result.error
    return a.result


def _rows(page) -> dict:
    return {lab: vals for lab, vals, _ in page.rows}


# --- golden: Prism's own numbers ------------------------------------------------------

KEYS = {"dAgostinoPearsonTest": "dagostino", "andersonDarlingTest": "anderson",
        "shapiroWilkTest": "shapiro", "kolmogorovSmirnovTest": "ks"}


@pytest.mark.parametrize("case", GOLDEN.get("normality", []), ids=lambda c: f"n{len(c['values'])}")
def test_normality_matches_prism(case):
    x = np.array(case["values"])
    ours = normality.run_tests(x, list(KEYS.values()))
    for pk, k in KEYS.items():
        pr = case["prism"][pk]
        if pr["status"] != "VALID":
            assert ours[k] is None                      # same minimum sample size
            continue
        stat, p, capped = ours[k]
        assert stat == pytest.approx(pr["stat"], rel=1e-6)
        if pr["p_state"] == "P_VALUE_GREATER":
            assert capped and p == pytest.approx(pr["p"])
        else:
            assert p == pytest.approx(pr["p"], rel=1e-5)


@pytest.mark.parametrize("case", GOLDEN.get("frequency", []), ids=lambda c: f"bins{c['calc']['binWidth']['value']}")
def test_frequency_distribution_matches_prism(case):
    calc, table = case["calc"], case["output_table"]
    nb = len([v for v in table[1] if v is not None])
    params = {"bin_width": calc["binWidth"]["value"], "first_center": calc["binCenterFirst"]["value"],
              "cumulative": calc["distributionType"] == "CUMULATIVE_FREQUENCY",
              "tabulate": "fractions" if calc["tabulate"] == "RELATIVE_FRACTIONS" else "counts"}
    data = [np.array(x) for x in case["inputs"]]
    c0, w, n_ours = frequency.bins_for(data, params)
    assert n_ours == nb                                  # automatic last bin = Prism's
    assert np.allclose(c0 + np.arange(nb) * w, [v for v in table[1][:nb]])
    for k, x in enumerate(data):
        vals, _ = frequency.tabulate(x, c0, w, nb, params["tabulate"], params["cumulative"])
        assert np.allclose(vals, np.array(table[2 + k][:nb], float), atol=1e-12)
    # automatic choices Prism would have made
    assert frequency.nice_width(float(np.concatenate(data).max() - np.concatenate(data).min())) \
        == pytest.approx(calc["binWidth"]["autoValue"])


# --- one-way ANOVA family -------------------------------------------------------------

def test_ordinary_anova_and_tukey_match_scipy():
    res = _run("anova1", [A, B, C], compare="all", method="tukey")
    f, p = stats.f_oneway(A, B, C)
    assert res.p == pytest.approx(p, rel=1e-9)
    tk = stats.tukey_hsd(A, B, C)
    for i, j, padj in res.comparisons:
        assert padj == pytest.approx(tk.pvalue[i, j], rel=1e-4)
    rows = _rows(res.pages[0])
    assert rows["F"] == [f"{f:.4g}"]


def test_dunnett_is_exact_and_agrees_with_scipy():
    # Published critical value (Dunnett's table): 3 treatments + control, df = 20 → 2.54
    lam = np.full(3, np.sqrt(0.5))
    from scipy.optimize import brentq
    assert brentq(lambda c: anova.dunnett_cdf(c, lam, 20) - 0.95, 1, 5) == pytest.approx(2.540, abs=5e-3)
    res = _run("anova1", [A, B, C, D], compare="control", control=0, method="dunnett")
    d = stats.dunnett(B, C, D, control=A, rng=np.random.default_rng(1))   # Monte Carlo
    for ours, theirs in zip([p for _, _, p in res.comparisons], d.pvalue):
        if theirs > 1e-3:
            assert ours == pytest.approx(theirs, rel=2e-2)
    res2 = _run("anova1", [A, B, C, D], compare="control", control=0, method="dunnett")
    assert res2.comparisons == res.comparisons                          # deterministic


@pytest.mark.parametrize("method,sm", [("bonferroni", "bonferroni"), ("sidak", "sidak"),
                                       ("holm_sidak", "holm-sidak")])
def test_corrections_match_statsmodels(method, sm):
    groups = [A, B, C, D]
    res = _run("anova1", groups, compare="all", method=method)
    o = anova.ordinary([np.array(g) for g in groups])
    raw = []
    for i, j, _ in res.comparisons:
        gi, gj = np.array(groups[i]), np.array(groups[j])
        se = np.sqrt(o["msw"] * (1 / len(gi) + 1 / len(gj)))
        raw.append(2 * stats.t.sf(abs(gi.mean() - gj.mean()) / se, o["dfw"]))
    expected = multipletests(raw, method=sm)[1]
    assert [p for *_, p in res.comparisons] == pytest.approx(list(expected), rel=1e-9)


def test_welch_anova_and_games_howell_match_pingouin():
    groups = [A, B, D]
    res = _run("anova1", groups, welch=True, compare="all", method="games_howell")
    df = pd.DataFrame({"v": [*A, *B, *D], "g": ["A"] * len(A) + ["B"] * len(B) + ["D"] * len(D)})
    w = pg.welch_anova(df, dv="v", between="g")
    assert res.p == pytest.approx(float(w["p_unc"].iloc[0]), rel=1e-6)
    gh = pg.pairwise_gameshowell(df, dv="v", between="g")
    assert sorted(p for *_, p in res.comparisons) == pytest.approx(sorted(gh["pval"]), rel=1e-4)


def test_repeated_measures_with_geisser_greenhouse_matches_pingouin():
    rng = np.random.default_rng(0)
    subj = rng.normal(0, 3, 8)
    Y = np.column_stack([10 + subj + rng.normal(0, s, 8) for s in (1, 2, 4)]) + [0, 1.5, 3]
    res = _run("anova1", [Y[:, 0], Y[:, 1], Y[:, 2]], design="rm", gg=True, compare="none")
    long = pd.DataFrame({"s": np.repeat(range(8), 3), "c": np.tile(["a", "b", "c"], 8),
                         "v": Y.ravel()})
    ref = pg.rm_anova(long, dv="v", within="c", subject="s", correction=True)
    assert res.p == pytest.approx(float(ref["p_GG_corr"].iloc[0]), rel=1e-6)
    rows = _rows(res.pages[0])
    assert float(rows["Geisser-Greenhouse ε"][0]) == pytest.approx(float(ref["eps"].iloc[0]), abs=1e-4)


def _kw_brute(groups):
    """Exact Kruskal-Wallis P by listing every split of the values into groups of these sizes."""
    import itertools
    allv = np.concatenate(groups)
    sizes = [len(g) for g in groups]
    h_obs = stats.kruskal(*groups).statistic
    idx = range(len(allv))
    hits = total = 0
    for g1 in itertools.combinations(idx, sizes[0]):
        rest = [i for i in idx if i not in g1]
        for g2 in itertools.combinations(rest, sizes[1]):
            g3 = [i for i in rest if i not in g2]
            h = stats.kruskal(allv[list(g1)], allv[list(g2)], allv[g3]).statistic
            hits += h >= h_obs - 1e-9
            total += 1
    return hits / total


def test_kruskal_wallis_exact_p():
    """Exact P for small and moderate samples (also with ties), as Prism; matches listing
    every arrangement. Large samples fall back to the χ² approximation."""
    from asterism.analysis.anova import kw_exact_p
    no_ties = [np.array([1.2, 3.4, 2.2, 5.1]), np.array([4.4, 6.0, 7.3]), np.array([8.1, 2.9, 9.5, 6.6])]
    ties = [np.array([1.0, 2, 2, 5]), np.array([2.0, 3, 5]), np.array([5.0, 6, 6, 1])]
    for g in (no_ties, ties):
        assert kw_exact_p(g) == pytest.approx(_kw_brute(g), rel=1e-9)
    res = _run("anova1", [A, B, C], distribution="nonparametric", compare="all")
    assert res.p == pytest.approx(kw_exact_p([np.array(A), np.array(B), np.array(C)]), rel=1e-12)
    big = [np.arange(30.0) + k for k in range(3)]
    assert kw_exact_p(big) is None
    res = _run("anova1", [list(g) for g in big], distribution="nonparametric", compare="all")
    assert res.p == pytest.approx(stats.kruskal(*big).pvalue, rel=1e-9)


def test_kruskal_wallis_and_friedman_match_scipy():
    six = [A, C, D]
    res = _run("anova1", six, design="rm", distribution="nonparametric", compare="all")
    assert res.p == pytest.approx(stats.friedmanchisquare(*six).pvalue, rel=1e-9)


def test_anova_needs_three_groups():
    p = Project(engine)
    t = p.add_table(table_type="column", example=True)
    a = p.add_analysis(Analysis("anova1", t, [0, 1], {}))
    assert a.result.error and "three or more" in a.result.error


# --- one-sample, outliers, summary t test ------------------------------------------

def test_one_sample_t_and_wilcoxon():
    res = _run("onesample", [A], mu=25.0)
    r = stats.ttest_1samp(A, 25.0)
    assert _rows(res.pages[0])["P value"] == [f"{r.pvalue:.4f}"]
    res = _run("onesample", [A], mu=25.0, test="wilcoxon")
    assert "P value" in _rows(res.pages[0])


def test_grubbs_finds_the_planted_outlier():
    res = _run("outliers", [A + [60.0]], alpha=0.05)
    rows = _rows(res.pages[0])
    assert rows["Outliers found"] == ["1"] and float(rows["Outlier values"][0]) == 60.0
    res = _run("outliers", [A], alpha=0.05)
    assert _rows(res.pages[0])["Outliers found"] == ["0"]


def test_t_test_from_mean_sd_n_matches_raw_data():
    p = Project(engine)
    t = p.add_table(table_type="column", y_format="mean_sd_n")
    for c, g in enumerate((A, B)):
        x = np.array(g)
        for s, v in enumerate((x.mean(), x.std(ddof=1), len(x))):
            t.set(0, t.flat(c, s), float(v))
    a = p.add_analysis(Analysis("ttest", t, [0, 1], {"test": "welch"}))
    assert a.result.p == pytest.approx(stats.ttest_ind(B, A, equal_var=False).pvalue, rel=1e-9)
