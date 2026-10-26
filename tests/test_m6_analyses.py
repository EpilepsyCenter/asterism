"""M6 analyses: contingency tables, fraction of total, survival.

Golden: Prism 11's Fisher's exact test on the lab's Seizure_data project. References: R
(fisher.test, prop.trend.test, chisq.test; DescTools BinomCI "modified wilson" and
BinomDiffCI "score"/"scorecc"; PropCIs riskscoreci; survival survfit(conf.type =
"log-log") and survdiff) and SAS's published Gehan-Breslow (Wilcoxon) value for the
Freireich leukaemia data. Values below were produced by those packages.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest
from scipy import stats

from asterism.analysis import contingency as ct
from asterism.analysis import engine
from asterism.analysis import survival as sv
from asterism.doc.model import Analysis, Project

GOLDEN = json.loads((Path(__file__).parent / "golden" / "prism_golden.json").read_text())


# ---------------------------------------------------------------------------
# Contingency
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("case", GOLDEN.get("contingency", []), ids=lambda c: c["method"])
def test_fisher_matches_prism(case):
    m = np.array(case["table"], int)
    assert ct.fisher_2x2(m) == pytest.approx(case["prism"]["fisherExactTest"], rel=1e-12)


def test_fisher_larger_tables_match_r():
    assert ct.fisher_rxc(np.array([[3, 1, 4], [2, 5, 1], [0, 4, 6]])) == pytest.approx(0.0516775230113, rel=1e-9)


def test_chi_square_yates_and_trend_match_r():
    assert ct.chi_square(np.array([[5, 2], [2, 11]]), yates=True)["chi2"] == pytest.approx(4.05989614781, rel=1e-10)
    tr = ct.trend(np.array([[15, 15], [10, 20], [8, 22], [3, 27]]))
    assert tr["chi2"] == pytest.approx(11.46031746, rel=1e-9)
    assert tr["p"] == pytest.approx(0.000710981532, rel=1e-8)
    m = np.array([[12, 5, 7], [6, 12, 9]])
    ref = stats.chi2_contingency(m, correction=False)
    assert ct.chi_square(m)["chi2"] == pytest.approx(ref.statistic)


@pytest.mark.parametrize("x,n,lo,hi", [
    (0, 50, 0.0, 0.0713475991334), (1, 50, 0.00102586588775, 0.1049544358964),
    (2, 50, 0.00710723021397, 0.1346009068751), (3, 50, 0.02061497034897, 0.1621709168884),
    (7, 50, 0.06950833427016, 0.2618619371059), (48, 50, 0.86539909312493, 0.9928927697860),
    (49, 50, 0.89504556410362, 0.9989741341122), (50, 50, 0.92865240086664, 1.0),
    (3, 60, 0.0136281907861, 0.137005164763)])
def test_wilson_brown_matches_desctools_modified_wilson(x, n, lo, hi):
    assert ct.wilson_brown(x, n) == pytest.approx((lo, hi), rel=1e-9, abs=1e-12)


def test_newcombe_and_koopman_match_r():
    assert ct.newcombe_diff(56, 70, 48, 80, cc=True) == pytest.approx((0.0427678720029, 0.342186278438), rel=1e-9)
    assert ct.newcombe_diff(56, 70, 48, 80, cc=False) == pytest.approx((0.0524314724024, 0.333872654037), rel=1e-9)
    assert ct.newcombe_diff(5, 7, 2, 13) == pytest.approx((0.0453409703523, 0.827076492435), rel=1e-9)
    assert ct.koopman_rr(5, 7, 2, 13) == pytest.approx((1.35656143103, 17.41379236563), rel=1e-8)
    assert ct.koopman_rr(56, 70, 48, 80) == pytest.approx((1.07982150636, 1.67080557802), rel=1e-8)


def test_baptista_pike_interval_is_on_the_rejection_boundary():
    for tab in ((5, 2, 2, 11), (12, 5, 6, 12), (20, 10, 8, 25)):
        lo, hi = ct.baptista_pike_or(*tab)
        a, b, c, d = tab
        est = a * d / (b * c)
        assert lo < est < hi

        def pv(psi):
            xs, pr = ct._nchg_pmf(psi, a + c, a + b, c + d)
            po = pr[xs == a][0]
            return pr[pr <= po * (1 + 1e-7)].sum()
        assert pv(lo * 1.001) > 0.05 >= pv(lo * 0.999)
        assert pv(hi * 0.999) > 0.05 >= pv(hi * 1.001)
        # narrower than the conservative central exact (Cornfield) interval
        assert lo >= ct.woolf_or(*tab)[0] * 0.5


def test_cramers_v():
    m = np.array([[20, 10, 5], [5, 15, 20]])
    chi = ct.chi_square(m)["chi2"]
    v = ct.cramers_v(m, chi)
    assert v["v"] == pytest.approx(math.sqrt(chi / (m.sum() * 1)))
    assert v["ci"][0] < v["v"] < v["ci"][1]


def test_contingency_analysis_through_the_model():
    p = Project(engine)
    t = p.add_table(table_type="contingency", example=True)
    for prm, page in (({}, "Effect size"), ({"effect": "or"}, "Effect size"), ({"effect": "diagnostic"}, "Effect size"),
                      ({"test": "chi2", "yates": True}, "Results")):
        a = p.add_analysis(Analysis("contingency", t, t.used_columns(), prm))
        assert a.result.error is None
        assert page in [pg.title for pg in a.result.pages]
    labels = [r[0] for r in p.analyses[0].result.pages[1].rows]
    assert "Relative risk" in labels and "Number needed to treat (or harm)" in labels
    t.set(0, t.flat(0), 3.5)
    assert "whole numbers" in p.analyses[0].result.error


def test_fraction_of_total():
    p = Project(engine)
    t = p.add_table(table_type="parts", example=True)
    a = p.add_analysis(Analysis("fraction", t, t.used_columns(), {"ci": True}))
    assert a.result.error is None
    first = a.result.pages[0].rows[0]
    assert first[0] == "Neurons" and float(first[1][0]) == pytest.approx(46.0)
    lo, hi = ct.wilson_brown(46, 100)
    assert first[1][1] == f"{lo * 100:.2f} to {hi * 100:.2f}"


# ---------------------------------------------------------------------------
# Survival
# ---------------------------------------------------------------------------

T = np.array([3, 7, 9, 12, 15, 8, 14, 18, 24, 30, 5, 5, 11, 20, 22, 6, 16, 16, 28, 31.])
E = np.array([1, 1, 0, 1, 1, 1, 0, 1, 0, 1, 1, 1, 1, 0, 1, 1, 1, 1, 0, 0])
G = np.array([1] * 5 + [2] * 5 + [1] * 5 + [2] * 5)
# survfit(Surv(t, e) ~ g, conf.type = "log-log"): time, surv, std.err, lower, upper (group 1)
R_G1 = [(3, 0.9, 0.0948683298051, 0.4730092713621, 0.985281393367),
        (5, 0.7, 0.1449137674619, 0.3287165932797, 0.891949041225),
        (7, 0.6, 0.1549193338483, 0.2526688970039, 0.827220967029),
        (11, 0.48, 0.1639512122554, 0.1608546691176, 0.744665726758),
        (12, 0.36, 0.1609968943800, 0.0898715051082, 0.648422637271),
        (15, 0.24, 0.1453272169967, 0.0376984682906, 0.537252888188)]


def test_kaplan_meier_matches_r():
    cv = sv.km(T[G == 1], E[G == 1])
    rows = {r["time"]: r for r in cv["rows"]}
    for time, s, se, lo, hi in R_G1:
        r = rows[time]
        assert (r["S"], r["se"], r["lo"], r["hi"]) == pytest.approx((s, se, lo, hi), rel=1e-9)
    assert sv.median_survival(cv) == 11.0
    assert sv.median_ci(cv) == (3.0, None)                       # R: 11 (3, NA)
    cv2 = sv.km(T[G == 2], E[G == 2])
    assert sv.median_survival(cv2) == 18.0 and sv.median_ci(cv2) == (6.0, None)


def test_symmetric_intervals_are_clipped():
    cv = sv.km(T[G == 1], E[G == 1], ci="symmetric")
    for r in cv["rows"]:
        if math.isfinite(r["lo"]):
            assert 0.0 <= r["lo"] <= r["S"] <= r["hi"] <= 1.0


def test_logrank_matches_r_survdiff():
    groups = [(T[G == 1], E[G == 1]), (T[G == 2], E[G == 2])]
    lr = sv.weighted_logrank(groups)
    assert lr["chi2"] == pytest.approx(4.04274766442, rel=1e-10)
    assert lr["O"].tolist() == [8, 6]
    assert lr["E"] == pytest.approx([4.64474057504, 9.35525942496], rel=1e-10)
    assert lr["V"][0, 0] == pytest.approx(2.78468179151, rel=1e-10)
    g3 = G.copy()
    g3[[3, 4, 13, 14]] = 3
    assert sv.weighted_logrank([(T[g3 == k], E[g3 == k]) for k in (1, 2, 3)])["chi2"] == \
        pytest.approx(12.5117762624, rel=1e-9)


def test_gehan_breslow_wilcoxon_matches_sas_on_the_freireich_data():
    # MASS::gehan (Freireich et al. 1963): SAS LIFETEST Log-Rank 16.7929, Wilcoxon 13.4579
    mp = ([6, 6, 6, 6, 7, 9, 10, 10, 11, 13, 16, 17, 19, 20, 22, 23, 25, 32, 32, 34, 35],
          [1, 1, 1, 0, 1, 0, 1, 0, 0, 1, 1, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0])
    ctl = ([1, 1, 2, 2, 3, 4, 4, 5, 5, 8, 8, 8, 8, 11, 11, 12, 12, 15, 17, 22, 23], [1] * 21)
    groups = [(np.array(mp[0], float), np.array(mp[1])), (np.array(ctl[0], float), np.array(ctl[1]))]
    assert sv.weighted_logrank(groups)["chi2"] == pytest.approx(16.7929, abs=5e-5)
    assert sv.weighted_logrank(groups, "gehan")["chi2"] == pytest.approx(13.4579, abs=5e-5)


def test_hazard_ratios():
    lr = sv.weighted_logrank([(T[G == 1], E[G == 1]), (T[G == 2], E[G == 2])])
    hr = sv.hazard_ratios(lr)
    O, Ex, V = lr["O"], lr["E"], lr["V"][0, 0]
    assert hr["logrank"][0] == pytest.approx((O[0] / Ex[0]) / (O[1] / Ex[1]))
    assert hr["mh"][0] == pytest.approx(math.exp((O[0] - Ex[0]) / V))
    assert hr["mh"][1] < hr["mh"][0] < hr["mh"][2]


def test_survival_analysis_through_the_model():
    p = Project(engine)
    t = p.add_table(table_type="survival", ncols=3, example=False)
    for r, (time, e, g) in enumerate(zip(T, E, G)):
        t.set(r, "x", float(time), emit=False)
        t.set(r, t.flat(int(g) - 1), float(e), emit=False)
    t.set(len(T), "x", 40.0, emit=False)
    t.set(len(T), t.flat(2), 1.0, emit=False)
    t.set(len(T) + 1, "x", 45.0, emit=False)
    t.set(len(T) + 1, t.flat(2), 0.0, emit=False)
    t.changed.emit()
    a = p.add_analysis(Analysis("survival", t, [0, 1], {}))
    assert a.result.error is None
    labels = [r[0] for r in a.result.pages[0].rows]
    assert "Mantel-Haenszel: ratio" in labels and "Log-rank (Mantel-Cox): chi-square, df" in labels
    assert a.result.p == pytest.approx(stats.chi2.sf(4.04274766442, 1), rel=1e-8)
    b = p.add_analysis(Analysis("survival", t, [0, 1, 2], {"ci": "symmetric", "percent": False}))
    assert "Log-rank test for trend" in [r[0] for r in b.result.pages[0].rows]
    assert b.result.pages[1].columns[0] == "Fraction surviving"
