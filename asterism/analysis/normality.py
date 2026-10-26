"""Normality and lognormality tests (Prism's four tests, our presentation).

D'Agostino-Pearson omnibus K², Anderson-Darling A² (P from Stephens'
small-sample corrected A²*), Shapiro-Wilk W (Royston), Kolmogorov-Smirnov distance with the
Dallal-Wilkinson approximation to the Lilliefors P value (reported as P > 0.10 when
larger, as Prism does). Minimum sample sizes follow Prism: 8 for D'Agostino-Pearson and
Anderson-Darling, 3 for Shapiro-Wilk, 5 for Kolmogorov-Smirnov.
"""

from __future__ import annotations

import math

import numpy as np
from scipy import stats as sps

from .results import AnalysisResult, ResultPage, fmt, fmt_p

MIN_N = {"dagostino": 8, "anderson": 8, "shapiro": 3, "ks": 5}
TEST_NAMES = {"dagostino": "D'Agostino-Pearson omnibus test",
              "anderson": "Anderson-Darling test", "shapiro": "Shapiro-Wilk test",
              "ks": "Kolmogorov-Smirnov test"}


def dagostino_pearson(x: np.ndarray) -> tuple[float, float]:
    k2, p = sps.normaltest(x)
    return float(k2), float(p)


def anderson_darling(x: np.ndarray) -> tuple[float, float]:
    """Returns (A², P). P comes from the small-sample corrected A²* = A²(1 + 0.75/n + 2.25/n²)
    (D'Agostino & Stephens 1986, normal with estimated mean and SD); the reported statistic
    is the uncorrected A², which is what Prism reports (verified by golden test)."""
    x = np.sort(np.asarray(x, float))
    n = len(x)
    z = (x - x.mean()) / x.std(ddof=1)
    cdf = sps.norm.cdf(z)
    cdf = np.clip(cdf, 1e-300, 1 - 1e-16)
    i = np.arange(1, n + 1)
    a2 = -n - np.sum((2 * i - 1) * (np.log(cdf) + np.log(1 - cdf[::-1]))) / n
    a2s = a2 * (1 + 0.75 / n + 2.25 / n ** 2)
    if a2s < 0.2:
        p = 1 - math.exp(-13.436 + 101.14 * a2s - 223.73 * a2s ** 2)
    elif a2s < 0.34:
        p = 1 - math.exp(-8.318 + 42.796 * a2s - 59.938 * a2s ** 2)
    elif a2s < 0.6:
        p = math.exp(0.9177 - 4.279 * a2s - 1.38 * a2s ** 2)
    else:
        p = math.exp(1.2937 - 5.709 * a2s + 0.0186 * a2s ** 2)
    return float(a2), float(min(max(p, 0.0), 1.0))


def shapiro_wilk(x: np.ndarray) -> tuple[float, float]:
    w, p = sps.shapiro(x)
    return float(w), float(p)


def ks_lilliefors(x: np.ndarray) -> tuple[float, float, bool]:
    """KS distance vs a normal with estimated mean/SD; P by Dallal-Wilkinson. Returns
    (D, P, capped) where capped means P > 0.10 (the approximation's range)."""
    x = np.sort(np.asarray(x, float))
    n = len(x)
    cdf = sps.norm.cdf((x - x.mean()) / x.std(ddof=1))
    i = np.arange(1, n + 1)
    d = float(max(np.max(i / n - cdf), np.max(cdf - (i - 1) / n)))
    if n > 100:
        dd = d * (n / 100) ** 0.49
        nn = 100
    else:
        dd, nn = d, n
    p = math.exp(-7.01256 * dd ** 2 * (nn + 2.78019) + 2.99587 * dd * math.sqrt(nn + 2.78019)
                 - 0.122119 + 0.974598 / math.sqrt(nn) + 1.67997 / nn)
    if p > 0.1:
        return d, 0.1, True
    return d, float(p), False


def run_tests(x: np.ndarray, tests: list[str]) -> dict:
    out = {}
    n = len(x)
    for t in tests:
        if n < MIN_N[t]:
            out[t] = None
            continue
        if t == "dagostino":
            s, p = dagostino_pearson(x)
            out[t] = (s, p, False)
        elif t == "anderson":
            s, p = anderson_darling(x)
            out[t] = (s, p, False)
        elif t == "shapiro":
            s, p = shapiro_wilk(x)
            out[t] = (s, p, False)
        elif t == "ks":
            out[t] = ks_lilliefors(x)
    return out


STAT_LABEL = {"dagostino": "K²", "anderson": "A²", "shapiro": "W", "ks": "Distance (D)"}


def normality(an) -> AnalysisResult:
    t, cols = an.table, an.columns
    p = an.params
    tests = [k for k in ("dagostino", "anderson", "shapiro", "ks") if p.get(k, True)]
    alpha = p.get("alpha", 0.05)
    data = [t.values(c) for c in cols]
    pages = []
    for log_scale in ([False, True] if p.get("lognormal", False) else [False]):
        title = "Lognormality" if log_scale else "Normality"
        rows: list[tuple[str, list[str], str]] = []
        sets = []
        for x in data:
            if log_scale:
                sets.append(np.log10(x[x > 0]) if np.all(x > 0) else None)
            else:
                sets.append(x)
        for test in tests:
            rows.append((TEST_NAMES[test] + (" (on logarithms)" if log_scale else ""), [], "section"))
            res = [run_tests(x, [test])[test] if x is not None else None for x in sets]
            rows.append((STAT_LABEL[test],
                         [fmt(r[0]) if r else _why(x, test) for r, x in zip(res, sets)], "row"))
            rows.append(("P value", [("> 0.10" if r[2] else fmt_p(r[1])) if r else "" for r in res], "row"))
            rows.append((f"Consistent with a {'lognormal' if log_scale else 'normal'} distribution "
                         f"(α = {alpha:g})?",
                         [("Yes" if r[1] >= alpha else "No") if r else "" for r in res], "row"))
            rows.append(("", [], "blank"))
        rows.append(("Number of values", [str(len(x)) if x is not None else "" for x in sets], "row"))
        pages.append(ResultPage(title, [t.label(c) for c in cols], rows))
    res = AnalysisResult(pages=pages)
    if p.get("qq", False):
        from .xy import residual_table
        series = [(c, t.label(c), *qq_points(x)) for c, x in zip(cols, data) if len(x) >= 3]
        if series:
            res.out_table = residual_table(f"QQ plot of {t.name}", series)
    return res


def qq_points(x) -> tuple[np.ndarray, np.ndarray]:
    """Actual values (sorted) and the values predicted for them from a Gaussian with the
    data's mean and SD, at Blom's plotting positions (i − 3/8)/(n + 1/4)."""
    from scipy import stats
    x = np.sort(np.asarray(x, float))
    n = len(x)
    q = (np.arange(1, n + 1) - 0.375) / (n + 0.25)
    return x, x.mean() + x.std(ddof=1) * stats.norm.ppf(q)


def _why(x, test: str) -> str:
    if x is None:
        return "Needs positive values"
    return f"Needs ≥ {MIN_N[test]} values"
