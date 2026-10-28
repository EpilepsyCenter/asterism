"""M5 analyses: linear regression, correlation, area under the curve, nonlinear regression,
ROUT. Golden values from Prism 11 (the lab's Seizure_data project) where Prism ran them;
R (nls, profile-t intervals) and brute force for the rest."""

from __future__ import annotations

import itertools
import json
import math
from pathlib import Path

import numpy as np
import pytest
from scipy import stats

from asterism.analysis import engine, models, nonlin, xy
from asterism.doc.model import Analysis, Project

from golden_data import Missing, golden  # noqa: E402

GOLDEN = golden("prism_golden.json")


def _xy(case, mean=False):
    if mean:
        pts = [(x, np.mean([v for v in row if v is not None])) for x, row in zip(case["x"], case["y"])
               if x is not None and any(v is not None for v in row)]
    else:
        pts = [(x, v) for x, row in zip(case["x"], case["y"]) for v in row if x is not None and v is not None]
    return np.array(pts, float).T


# ---------------------------------------------------------------------------
# Golden: Prism linear regression and Spearman correlation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("case", GOLDEN.get("linear_regression", []), ids=lambda c: str(c["prism"]["summary"]["pointsAnalyzed"]))
def test_linear_regression_matches_prism(case):
    x, y = _xy(case)
    f = xy.linfit(x, y)
    P, fit = case["prism"]["parameters"], case["prism"]["fit"]
    assert f["n"] == case["prism"]["summary"]["pointsAnalyzed"]
    assert f["slope"] == pytest.approx(P["Slope"]["estimate"], rel=1e-12)
    assert f["intercept"] == pytest.approx(P["Y-intercept"]["estimate"], rel=1e-12)
    assert f["se_slope"] == pytest.approx(P["Slope"]["se"], rel=1e-12)
    assert f["se_intercept"] == pytest.approx(P["Y-intercept"]["se"], rel=1e-12)
    assert f["ci_slope"] == pytest.approx(P["Slope"]["ci"], rel=1e-12)
    assert f["ci_intercept"] == pytest.approx(P["Y-intercept"]["ci"], rel=1e-12)
    assert f["F"] == pytest.approx(P["Slope"]["f"], rel=1e-12)
    assert f["df"] == P["Slope"]["dfd"]
    assert f["p"] == pytest.approx(P["Slope"]["p"], rel=1e-10)
    assert f["r2"] == pytest.approx(fit["r2"], rel=1e-10)
    assert f["syx"] == pytest.approx(fit["syx"], rel=1e-12)
    assert f["ss"] == pytest.approx(fit["lfv"], rel=1e-12)
    assert f["x_intercept"] == pytest.approx(P["X-intercept"]["estimate"], rel=1e-12)
    lo, hi = P["X-intercept"]["ci"]
    if lo == "-inf":
        assert f["ci_x_intercept"] == (-math.inf, math.inf)


@pytest.mark.parametrize("case", GOLDEN.get("correlation", []), ids=lambda c: str(c["prism"]["n"]))
def test_spearman_matches_prism(case):
    x, y = _xy(case, mean=True)
    d = xy.spearman(x, y)
    pr = case["prism"]
    assert d["n"] == pr["n"]
    assert d["r"] == pytest.approx(pr["r"], rel=1e-12)
    assert d["p"] == pytest.approx(pr["p"], rel=1e-12)          # exact, ties included
    assert d["exact"]
    assert d["p_approx"] == pytest.approx(pr["p_approx"], rel=1e-10)
    if pr["ci"][0] == "undefined":
        assert d["ci"] is None                                    # Prism: only for n > 10
    else:
        assert d["ci"] == pytest.approx(pr["ci"], rel=1e-8)


def test_exact_spearman_equals_brute_force_with_ties():
    x = np.array([1, 2, 3, 4, 5, 6, 7.0])
    y = np.array([2, 1, 4, 4, 6, 5, 9.0])
    rx, ry = stats.rankdata(x), stats.rankdata(y)
    obs = float(np.corrcoef(rx, ry)[0, 1])
    rs = [np.corrcoef(rx, ry[list(pm)])[0, 1] for pm in itertools.permutations(range(7))]
    p = np.mean([abs(r) >= abs(obs) - 1e-12 for r in rs])
    assert xy.spearman_exact_p(x, y) == pytest.approx(p, rel=1e-12)
    assert xy.spearman_exact_p(np.arange(20.0), np.arange(20.0)) is None      # too large: t approximation


def test_pearson_matches_scipy():
    rng = np.random.default_rng(0)
    x = rng.normal(size=25)
    y = x + rng.normal(size=25)
    d = xy.pearson(x, y)
    ref = stats.pearsonr(x, y)
    assert d["r"] == pytest.approx(ref.statistic)
    assert d["p"] == pytest.approx(ref.pvalue)
    ci = ref.confidence_interval(0.95)
    assert d["ci"] == pytest.approx((ci.low, ci.high), rel=1e-6)


# ---------------------------------------------------------------------------
# Linear regression details
# ---------------------------------------------------------------------------

def test_line_through_a_point_and_bands():
    import statsmodels.api as sm
    rng = np.random.default_rng(1)
    x = np.linspace(1, 10, 12)
    y = 2.5 * x + rng.normal(0, 1, 12)
    f = xy.linfit(x, y, through=(0.0, 0.0))
    ref = sm.OLS(y, x[:, None]).fit()
    assert f["slope"] == pytest.approx(ref.params[0])
    assert f["se_slope"] == pytest.approx(ref.bse[0])
    assert f["df"] == 11
    f2 = xy.linfit(x, y)
    ols = sm.OLS(y, sm.add_constant(x)).fit()
    pr = ols.get_prediction(sm.add_constant(np.array([3.0, 7.0]))).summary_frame(0.05)
    lo, hi = xy.band(f2, np.array([3.0, 7.0]))
    assert lo == pytest.approx(pr["mean_ci_lower"].to_numpy())
    lo, hi = xy.band(f2, np.array([3.0, 7.0]), prediction=True)
    assert hi == pytest.approx(pr["obs_ci_upper"].to_numpy())


def test_x_intercept_interval_is_where_the_band_crosses_zero():
    x = np.array([1, 2, 3, 4, 5, 6.0])
    y = np.array([-3.1, -1.8, -1.2, 0.3, 1.1, 2.2])
    f = xy.linfit(x, y)
    lo, hi = f["ci_x_intercept"]
    blo, bhi = xy.band(f, np.array([lo, hi]))
    assert bhi[0] == pytest.approx(0.0, abs=1e-9) or blo[0] == pytest.approx(0.0, abs=1e-9)
    assert lo < f["x_intercept"] < hi


def test_compare_slopes_and_intercepts_match_ancova():
    import pandas as pd
    import statsmodels.formula.api as smf
    from statsmodels.stats.anova import anova_lm
    rng = np.random.default_rng(2)
    x = np.tile(np.arange(10.0), 2)
    g = np.repeat([0, 1], 10)
    y = 1 + 0.5 * x + 2 * g + rng.normal(0, 0.5, 20)
    d1, d2 = (x[g == 0], y[g == 0]), (x[g == 1], y[g == 1])
    out = xy.compare_lines([xy.linfit(*d1), xy.linfit(*d2)], [d1, d2])
    df = pd.DataFrame({"x": x, "y": y, "g": g})
    full = smf.ols("y ~ x * C(g)", df).fit()
    par = smf.ols("y ~ x + C(g)", df).fit()
    one = smf.ols("y ~ x", df).fit()
    assert out["slopes"][3] == pytest.approx(anova_lm(par, full)["Pr(>F)"][1])
    assert out["intercepts"][3] == pytest.approx(anova_lm(one, par)["Pr(>F)"][1])


def test_runs_test_exact():
    res = np.array([1, 1, 1, -1, -1, -1, 1, 1.0])      # 3 runs, 5 positive, 3 negative
    runs, p = xy.runs_test(res)
    assert runs == 3
    seqs = set(itertools.permutations([1] * 5 + [-1] * 3))
    count = sum(1 for s in seqs if 1 + sum(a != b for a, b in zip(s, s[1:])) <= 3)
    assert p == pytest.approx(count / len(seqs))


def test_area_under_curve():
    rows = [{"x": x, "mean": y, "sem": 0.5, "n": 3} for x, y in ((0, 0), (1, 2), (2, 4), (3, 1), (4, 0))]
    a = xy.auc_one(rows)
    assert a["total"] == pytest.approx(np.trapezoid([0, 2, 4, 1, 0], [0, 1, 2, 3, 4]))
    assert len(a["peaks"]) == 1 and a["peaks"][0]["peak_x"] == 2
    w = np.array([0.5, 1, 1, 1, 0.5])
    assert a["se"] == pytest.approx(math.sqrt(np.sum((w * 0.5) ** 2)))
    assert a["df"] == 15 - 5


# ---------------------------------------------------------------------------
# Nonlinear regression (reference: R nls; profile-t intervals from MASS::confint)
# ---------------------------------------------------------------------------

DOSE = (np.array([-9, -8.5, -8, -7.5, -7, -6.5, -6, -5.5, -5.]),
        np.array([2.1, 5.3, 12.8, 30.2, 55.1, 77.3, 90.2, 96.4, 98.1]))
R_DOSE = {"est": [0.216893570452, 99.389610713179, -7.098825913254, 0.912649222520],
          "se": [0.29492495908371, 0.26151487873923, 0.00566350726131, 0.01074837676503],
          "ci": [(-0.549629271903, 0.961227764237), (98.724733617468, 100.071488174330),
                 (-7.113398229564, -7.084288128786), (0.885422103867, 0.940540390640)], "ss": 0.4230543048}
MM = (np.array([0.5, 1, 2, 4, 8, 16, 32.]), np.array([1.8, 3.1, 4.9, 6.6, 8.0, 8.9, 9.4]))
R_MM = {"est": [10.10885030394, 2.17559201516], "se": [0.0676996912863, 0.0534446347039],
        "ci": [(9.93749745251, 10.28340517170), (2.04350644323, 2.31554098346)], "ss": 0.0280196987511}
DECAY = (np.array([0, 1, 2, 3, 4, 6, 8, 10, 15, 20.]),
         np.array([100.2, 74.9, 57.1, 43.8, 34.2, 22.1, 15.9, 12.8, 10.3, 10.1]))
R_DECAY = {"est": [100.281572823430, 9.552909546772, 0.326331624915],
           "se": [0.24773731853403, 0.17116126602661, 0.00231875033014],
           "ci": [(99.697326414851, 100.866702322840), (9.148025540363, 9.955073977584),
                  (0.320918751204, 0.331816865419)], "ss": 0.540868090849}


@pytest.mark.parametrize("key,data,ref", [("agonist_4", DOSE, R_DOSE), ("michaelis_menten", MM, R_MM),
                                          ("one_phase_decay", DECAY, R_DECAY)])
def test_nonlinear_fit_matches_r(key, data, ref):
    m = models.BY_KEY[key]
    f = nonlin.fit(m, [nonlin.Data(*data)])
    assert f.ss == pytest.approx(ref["ss"], rel=1e-8)
    assert [f.values[0][p] for p in m.params] == pytest.approx(ref["est"], rel=2e-5, abs=2e-6)
    assert [f.se[0][p] for p in m.params] == pytest.approx(ref["se"], rel=1e-4)
    for p, (lo, hi) in zip(m.params, ref["ci"]):
        a, b = f.ci[0][p]
        # R interpolates its profile with a spline; ours finds the exact root
        assert a == pytest.approx(lo, rel=5e-4, abs=2e-4) and b == pytest.approx(hi, rel=5e-4, abs=2e-4)


def test_profile_limits_meet_the_f_threshold():
    m = models.BY_KEY["michaelis_menten"]
    d = nonlin.Data(*MM)
    f = nonlin.fit(m, [d])
    target = f.ss * (1 + stats.f.ppf(0.95, 1, f.df) / f.df)
    for p in m.params:
        for limit in f.ci[0][p]:
            g = nonlin.fit(m, [d], constraints={p: {"mode": "constant", "value": limit}}, ci_method="asymptotic")
            assert g.ss == pytest.approx(target, rel=1e-6)


def test_asymptotic_intervals_and_constants():
    m = models.BY_KEY["agonist_4"]
    f = nonlin.fit(m, [nonlin.Data(*DOSE)], ci_method="asymptotic")
    tc = stats.t.ppf(0.975, f.df)
    for p in m.params:
        assert f.ci[0][p] == pytest.approx((f.values[0][p] - tc * f.se[0][p], f.values[0][p] + tc * f.se[0][p]))
    g = nonlin.fit(m, [nonlin.Data(*DOSE)], constraints={"Bottom": {"mode": "constant", "value": 0.0}})
    assert g.values[0]["Bottom"] == 0.0 and g.k == 3 and g.df == 6


def test_bounds_are_respected():
    m = models.BY_KEY["agonist_4"]
    f = nonlin.fit(m, [nonlin.Data(*DOSE)], constraints={"HillSlope": {"mode": "fit", "lo": 1.0}})
    assert f.values[0]["HillSlope"] >= 1.0 - 1e-12


def test_global_fit_and_data_set_comparison():
    rng = np.random.default_rng(5)
    x = DOSE[0]
    f4 = models.BY_KEY["agonist_4"].f
    d1 = nonlin.Data(x, f4(x, 0, 100, -7.0, 1.0) + rng.normal(0, 2, len(x)))
    d2 = nonlin.Data(x, f4(x, 0, 100, -6.0, 1.0) + rng.normal(0, 2, len(x)))
    m = models.BY_KEY["agonist_4"]
    sep = nonlin.fit(m, [d1, d2], ci_method="asymptotic")
    shared = nonlin.fit(m, [d1, d2], {"HillSlope": {"mode": "shared"}, "Top": {"mode": "shared"},
                                      "Bottom": {"mode": "shared"}}, ci_method="asymptotic")
    assert sep.k == 8 and shared.k == 5
    assert shared.values[0]["Top"] == shared.values[1]["Top"]
    one = nonlin.fit(m, [d1, d2], {p: {"mode": "shared"} for p in m.params}, ci_method="asymptotic")
    F, dfn, dfd, p = nonlin.extra_ss(one, sep)
    assert dfn == 4 and dfd == sep.df and p < 1e-6           # the EC50s clearly differ


def test_aicc():
    assert nonlin.aicc(10.0, 20, 3) == pytest.approx(20 * math.log(0.5) + 8 + 40 / 15)


def test_relative_weighting_uses_the_curve():
    m = models.BY_KEY["michaelis_menten"]
    d = nonlin.Data(*MM)
    f = nonlin.fit(m, [d], weighting="y2", ci_method="asymptotic")
    yf = f.predict(0, d.x)
    assert f.ss == pytest.approx(float((((d.y - yf) / yf) ** 2).sum()), rel=1e-10)


def test_user_defined_equation_equals_the_library_model():
    u = models.user_model("Y = Vmax*X/(Km + X)", {"Vmax": 10, "Km": 2})
    assert u.params == ["Vmax", "Km"]
    a = nonlin.fit(u, [nonlin.Data(*MM)], ci_method="asymptotic")
    b = nonlin.fit(models.BY_KEY["michaelis_menten"], [nonlin.Data(*MM)], ci_method="asymptotic")
    assert a.values[0]["Vmax"] == pytest.approx(b.values[0]["Vmax"], rel=1e-8)
    with pytest.raises(ValueError):
        models.user_model("Y = __import__('os')")


def test_rout_finds_planted_outliers_and_nothing_in_clean_data():
    from asterism.analysis.onesample import rout_values
    rng = np.random.default_rng(2)
    clean = rng.normal(50, 5, 25)
    assert rout_values(clean, 0.01) == []
    dirty = np.r_[clean, 110.0, -10.0]
    assert sorted(rout_values(dirty, 0.01)) == [-10.0, 110.0]
    assert sorted(rout_values(dirty * 1000, 0.01)) == [-10000.0, 110000.0]     # units don't matter
    m = models.BY_KEY["michaelis_menten"]
    y = MM[1].copy()
    y[3] = 15.0
    mask = nonlin.rout(m, nonlin.Data(MM[0], y), 0.01)
    assert mask.tolist() == [False, False, False, True, False, False, False]


# ---------------------------------------------------------------------------
# Through the document model
# ---------------------------------------------------------------------------

def _dose_project():
    p = Project(engine)
    t = p.add_table(table_type="xy", y_format="replicates", replicates=2, example=False)
    rng = np.random.default_rng(3)
    f4 = models.BY_KEY["agonist_4"].f
    for r, x in enumerate(DOSE[0]):
        t.set(r, "x", float(x), emit=False)
        for k in range(2):
            t.set(r, t.flat(0, k), float(f4(x, 0, 100, -7, 1) + rng.normal(0, 3)), emit=False)
            t.set(r, t.flat(1, k), float(f4(x, 0, 100, -6.3, 1) + rng.normal(0, 3)), emit=False)
    t.set(len(DOSE[0]), t.flat(0, 0), 50.0, emit=False)         # an unknown to interpolate
    t.changed.emit()
    return p, t


def test_nonlinear_analysis_pages_and_options():
    p, t = _dose_project()
    a = p.add_analysis(Analysis("nonlin", t, [0, 1], {
        "model": "agonist_4", "interpolate": True, "residuals": True, "runs_test": True,
        "compare": "param", "compare_param": "LogEC50", "report_se": True}))
    assert a.result.error is None, a.result.error
    titles = [pg.title for pg in a.result.pages]
    assert titles == ["Results", "Compare data sets", "Interpolated", "Residuals"]
    labels = [r[0] for r in a.result.pages[0].rows]
    assert "EC50" in labels and "Sy.x" in labels and "Runs" in labels
    interp = a.result.pages[2].rows[0]
    assert interp[1][0] == "Y → X" and abs(float(interp[1][2]) + 7) < 0.3
    assert a.name.startswith("Nonlinear fit: log(agonist)")
    cmp_ = [r for r in a.result.pages[1].rows if r[0] == "P value"][0]
    assert cmp_[1][0].startswith("<") or float(cmp_[1][0]) < 0.05


def test_nonlinear_compare_models_and_outliers():
    p, t = _dose_project()
    a = p.add_analysis(Analysis("nonlin", t, [0], {"model": "agonist_3", "compare": "models",
                                                   "model_b": "agonist_4", "outliers": "exclude"}))
    assert a.result.error is None
    assert [pg.title for pg in a.result.pages] == ["Results", "Compare models"]
    aic = p.add_analysis(Analysis("nonlin", t, [0], {"model": "agonist_3", "compare": "models",
                                                     "model_b": "agonist_4", "compare_method": "aicc"}))
    assert aic.result.pages[1].columns[1] == "Difference in AICc"


def test_linear_regression_analysis_and_excluded_x():
    p = Project(engine)
    t = p.add_table(table_type="xy", example=True)
    a = p.add_analysis(Analysis("linreg", t, [0, 1], {"compare": True, "interpolate": True,
                                                      "runs_test": True, "linearity_test": True}))
    assert a.result.error is None
    n_before = a.result.fit["fits"][0]["n"]
    t.set_excluded([(0, "x")], True)
    assert a.result.fit["fits"][0]["n"] == n_before - 1
    from asterism.doc.fileformat import project_from_dict, project_to_dict
    q = project_from_dict(project_to_dict(p), engine)
    assert (0, "x") in q.tables[0].excluded


def test_correlation_on_column_and_xy_tables():
    p = Project(engine)
    t = p.add_table(table_type="column", example=False)
    for r in range(8):
        t.set(r, 0, float(r), emit=False)
        t.set(r, 1, float(r * 2 + (r % 3)), emit=False)
        t.set(r, 2, float(-r), emit=False)
    t.changed.emit()
    a = p.add_analysis(Analysis("correlation", t, [0, 1, 2], {"method": "spearman"}))
    assert a.result.error is None and len(a.result.pages[0].columns) == 3
    x = p.add_table(table_type="xy", example=True)
    b = p.add_analysis(Analysis("correlation", x, x.used_columns(), {}))
    assert b.result.error is None and b.name.startswith("Pearson")


def test_auc_analysis():
    p = Project(engine)
    t = p.add_table(table_type="xy", y_format="replicates", replicates=3, example=True)
    a = p.add_analysis(Analysis("auc", t, t.used_columns(), {}))
    assert a.result.error is None
    assert a.result.pages[0].rows[3][0] == "Area"


def test_frequency_distribution_gets_a_graph_of_its_results():
    p = Project(engine)
    t = p.add_table(table_type="column", example=True)
    a = p.add_analysis(Analysis("frequency", t, t.used_columns(), {}))
    g = p.new_result_graph(a)
    p.add_sheets([g], "graph")
    rt = g.table
    assert rt.table_type == "xy" and rt.bin_width == pytest.approx(a.result.table["width"])
    assert g.home is t and g in p.family(t)
    before = rt.state()
    t.set(0, 0, 500.0)                                 # live: the same table, refreshed in place
    assert g.table is rt and rt.state() != before
    from asterism.doc.fileformat import project_from_dict, project_to_dict
    q = project_from_dict(project_to_dict(p), engine)
    assert q.graphs[-1].source is q.analyses[-1]
    p.delete(a)
    assert g not in p.graphs                            # deleting the analysis takes its graph
