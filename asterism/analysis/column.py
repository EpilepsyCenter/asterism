"""Column analyses: t tests (and nonparametric tests), descriptive statistics.

Nonparametric tests reuse the golden-tested executors in `asterism.core.stats`
(exact Mann-Whitney / Wilcoxon when Prism would use exact, minimum-U convention).
Defaults follow Prism itself: Student's unpaired t unless Welch is chosen.
"""

from __future__ import annotations

import numpy as np
from scipy import stats as sps

from asterism.core.stats import _mann_whitney, _wilcoxon
from asterism.doc.model import column_letter

from .results import AnalysisResult, ResultPage, fmt, fmt_p, p_summary

TEST_NAMES = {
    ("unpaired", "normal", "student"): "Student's t test",
    ("unpaired", "normal", "welch"): "Welch's t test",
    ("unpaired", "lognormal", "student"): "t test on logarithms",
    ("unpaired", "nonparametric", "mw"): "Mann-Whitney U test",
    ("unpaired", "nonparametric", "ks"): "Kolmogorov-Smirnov test",
    ("paired", "normal", "student"): "Paired t test",
    ("paired", "lognormal", "student"): "Ratio paired t test",
    ("paired", "nonparametric", "wilcoxon"): "Wilcoxon signed-rank test",
}


def _test_key(params: dict) -> tuple[str, str, str]:
    return (params.get("design", "unpaired"), params.get("distribution", "normal"),
            params.get("test", "student"))



def ttest_title(params: dict) -> str:
    return TEST_NAMES.get(_test_key(params), "t test")


# ---------------------------------------------------------------------------
# t tests (and nonparametric tests)
# ---------------------------------------------------------------------------

def _ttest(an) -> AnalysisResult:
    ALPHA = float(an.params.get("alpha", 0.05))      # significance level (Settings)
    if an.table.is_summary():
        return _ttest_summary(an)
    t, (ca, cb) = an.table, an.columns[:2]
    p = an.params
    design, dist, test = _test_key(p)
    tails = p.get("tails", 2)
    conf = p.get("conf", 0.95)
    la, lb = t.label(ca), t.label(cb)
    A, B = column_letter(ca), column_letter(cb)
    rows: list[tuple[str, list[str], str]] = [
        ("Data table", [t.name], "row"),
        (f"Data set {A}", [la], "row"),
        (f"Data set {B}", [lb], "row"),
        ("", [], "blank"),
    ]

    if design == "paired":
        n = min(len(t.cols[ca]), len(t.cols[cb]))
        pairs = [(t._ok(r, t.flat(ca)), t._ok(r, t.flat(cb))) for r in range(n)]   # excluded values left out
        pairs = [(a, b) for a, b in pairs if a is not None and b is not None]
        a = np.array([x for x, _ in pairs], float)
        b = np.array([y for _, y in pairs], float)
    else:
        a, b = t.values(ca), t.values(cb)
    if len(a) < 2 or len(b) < 2:
        raise ValueError("Each data set needs at least two values.")

    name = TEST_NAMES[(design, dist, test)]
    rows.append((name, [], "section"))
    res = AnalysisResult(pair=(ca, cb))

    def p_rows(pv: float, exact: str | None = None) -> None:
        res.p = pv
        rows.append(("P value", [fmt_p(pv)], "row"))
        if exact:
            rows.append(("P value method", [exact], "row"))
        rows.append(("Significance", [p_summary(pv)], "row"))
        rows.append((f"Significant at α = {ALPHA:g}", ["Yes" if pv < ALPHA else "No"], "row"))
        rows.append(("Tails", ["Two-sided" if tails == 2 else "One-sided"], "row"))

    if dist in ("normal", "lognormal") and design == "unpaired":
        xa, xb = (np.log10(a), np.log10(b)) if dist == "lognormal" else (a, b)
        n1, n2 = len(xa), len(xb)
        m1, m2 = xa.mean(), xb.mean()
        v1, v2 = xa.var(ddof=1), xb.var(ddof=1)
        if test == "welch":
            se = np.sqrt(v1 / n1 + v2 / n2)
            df = (v1 / n1 + v2 / n2) ** 2 / ((v1 / n1) ** 2 / (n1 - 1) + (v2 / n2) ** 2 / (n2 - 1))
        else:
            sp2 = ((n1 - 1) * v1 + (n2 - 1) * v2) / (n1 + n2 - 2)
            se = np.sqrt(sp2 * (1 / n1 + 1 / n2))
            df = n1 + n2 - 2
        tv = (m2 - m1) / se
        pv = sps.t.sf(abs(tv), df) * (2 if tails == 2 else 1)
        p_rows(pv)
        dfs = fmt(df) if test == "welch" else str(int(df))
        rows.append(("t", [f"{abs(tv):.3f}"], "row"))
        rows.append(("Degrees of freedom" + (" (Welch)" if test == "welch" else ""), [dfs], "row"))
        rows.append(("", [], "blank"))
        rows.append(("Size of the difference", [], "section"))
        tc = sps.t.ppf(1 - (1 - conf) / 2, df)
        if dist == "lognormal":
            rows += [
                (f"Geometric mean, {A}", [fmt(10 ** m1)], "row"),
                (f"Geometric mean, {B}", [fmt(10 ** m2)], "row"),
                (f"Ratio of geometric means ({B}/{A})", [fmt(10 ** (m2 - m1))], "row"),
                (f"{conf:.0%} CI of the ratio", [f"{fmt(10 ** (m2 - m1 - tc * se))} to {fmt(10 ** (m2 - m1 + tc * se))}"], "row"),
            ]
        else:
            d = m2 - m1
            rows += [
                (f"Mean, {A}", [fmt(m1)], "row"),
                (f"Mean, {B}", [fmt(m2)], "row"),
                (f"Difference of means ({B} − {A})", [fmt(d)], "row"),
                ("Standard error of the difference", [fmt(se)], "row"),
                (f"{conf:.0%} CI of the difference", [f"{fmt(d - tc * se)} to {fmt(d + tc * se)}"], "row"),
                ("η² (R²)", [f"{tv * tv / (tv * tv + df):.4f}"], "row"),
            ]
        # F test to compare variances (Prism prints it under every unpaired t test)
        if v1 >= v2:
            F, dfn, dfd = v1 / v2, n1 - 1, n2 - 1
        else:
            F, dfn, dfd = v2 / v1, n2 - 1, n1 - 1
        pf = min(1.0, 2 * sps.f.sf(F, dfn, dfd))
        rows += [
            ("", [], "blank"),
            ("Equal variances (F test)", [], "section"),
            ("F", [f"{F:.3f}"], "row"),
            ("Degrees of freedom (numerator, denominator)", [f"{dfn}, {dfd}"], "row"),
            ("P value", [fmt_p(pf)], "row"),
            ("Significance", [p_summary(pf)], "row"),
            (f"Variances differ at α = {ALPHA:g}", ["Yes" if pf < ALPHA else "No"], "row"),
        ]
        rows += _data_analyzed(A, B, n1, n2)

    elif dist in ("normal", "lognormal") and design == "paired":
        d = (np.log10(b) - np.log10(a)) if dist == "lognormal" else (b - a)
        n = len(d)
        md, sd = d.mean(), d.std(ddof=1)
        se = sd / np.sqrt(n)
        df = n - 1
        tv = md / se
        pv = sps.t.sf(abs(tv), df) * (2 if tails == 2 else 1)
        p_rows(pv)
        rows.append(("t", [f"{abs(tv):.3f}"], "row"))
        rows.append(("Degrees of freedom", [str(df)], "row"))
        rows.append(("Pairs", [str(n)], "row"))
        rows.append(("", [], "blank"))
        rows.append(("Size of the difference", [], "section"))
        tc = sps.t.ppf(1 - (1 - conf) / 2, df)
        if dist == "lognormal":
            rows.append((f"Geometric mean of the ratios ({B}/{A})", [fmt(10 ** md)], "row"))
            rows.append((f"{conf:.0%} CI of the ratio", [f"{fmt(10 ** (md - tc * se))} to {fmt(10 ** (md + tc * se))}"], "row"))
        else:
            rows += [
                (f"Mean difference ({B} − {A})", [fmt(md)], "row"),
                ("SD of the differences", [fmt(sd)], "row"),
                ("Standard error of the mean difference", [fmt(se)], "row"),
                (f"{conf:.0%} CI of the mean difference", [f"{fmt(md - tc * se)} to {fmt(md + tc * se)}"], "row"),
                ("Partial η²", [f"{tv * tv / (tv * tv + df):.4f}"], "row"),
            ]
        r, pr = sps.pearsonr(a, b) if n > 2 else (np.nan, np.nan)
        rows += [
            ("", [], "blank"),
            ("Pairing", [], "section"),
            ("Correlation between pairs (r)", [fmt(r)], "row"),
            ("P value (one-sided, r > 0)", [fmt_p(pr / 2 if r > 0 else 1 - pr / 2)], "row"),
            ("Significance", [p_summary(pr / 2 if r > 0 else 1)], "row"),
            (f"Pairing effective at α = {ALPHA:g}", ["Yes" if r > 0 and pr / 2 < ALPHA else "No"], "row"),
        ]

    elif test == "mw":
        r = _mann_whitney(a, b)
        pv = r.p / 2 if tails == 1 else r.p
        p_rows(pv, "Exact" if r.settings.get("mwu_method") == "exact" else "Normal approximation")
        ranks = sps.rankdata(np.concatenate([a, b]))
        rows += [
            ("U", [fmt(r.statistic)], "row"),
            (f"Rank sum, {A}", [fmt(ranks[:len(a)].sum())], "row"),
            (f"Rank sum, {B}", [fmt(ranks[len(a):].sum())], "row"),
            ("", [], "blank"),
            ("Medians", [], "section"),
            (f"Median, {A} (n = {len(a)})", [fmt(np.median(a))], "row"),
            (f"Median, {B} (n = {len(b)})", [fmt(np.median(b))], "row"),
            (f"Difference of medians ({B} − {A})", [fmt(np.median(b) - np.median(a))], "row"),
            ("Hodges-Lehmann estimate of the difference", [fmt(np.median(np.subtract.outer(b, a)))], "row"),
        ]

    elif test == "ks":
        r = sps.ks_2samp(a, b, method="exact")
        tails = 2                          # no direction to predict: always two-sided
        p_rows(float(r.pvalue), "Exact (two-sided; the one-sided option doesn't apply to this test)")
        rows.append(("D", [f"{r.statistic:.4f}"], "row"))
        rows += _data_analyzed(A, B, len(a), len(b))

    elif test == "wilcoxon":
        r = _wilcoxon(a, b)
        pv = r.p / 2 if tails == 1 else r.p
        p_rows(pv, "Exact" if r.settings.get("wilcoxon_method") == "exact" else "Normal approximation")
        d = b - a
        nz = d[d != 0]
        rk = sps.rankdata(np.abs(nz))
        pos, neg = rk[nz > 0].sum(), -rk[nz < 0].sum()
        rows += [
            ("W (sum of signed ranks)", [fmt(pos + neg)], "row"),
            ("Sum of positive ranks", [fmt(pos)], "row"),
            ("Sum of negative ranks", [fmt(neg)], "row"),
            ("Pairs", [str(len(d))], "row"),
            ("", [], "blank"),
            ("Differences", [], "section"),
            (f"Median difference ({B} − {A})", [fmt(np.median(d))], "row"),
        ]

    res.pages.append(ResultPage("Results", [name], rows))
    if p.get("descriptive", False):
        res.pages.append(_descriptive_page(t, [ca, cb]))
    if res.p is not None:
        res.comparisons = [(ca, cb, res.p)]
    return res


def _ttest_summary(an) -> AnalysisResult:
    """Unpaired t test from entered mean, SD (or SEM, %CV) and N."""
    ALPHA = float(an.params.get("alpha", 0.05))      # significance level (Settings)
    t, (ca, cb) = an.table, an.columns[:2]
    p = an.params
    design, dist, test = _test_key(p)
    if design != "unpaired" or dist != "normal":
        raise ValueError("From entered means and errors, only the unpaired t test (Student's or "
                         "Welch's) can be run; paired and rank tests need the raw values.")
    sa, sb = t.summary(0, ca), t.summary(0, cb)
    if not sa or not sb or sa["sd"] is None or sb["sd"] is None or not sa["n"] or not sb["n"]:
        raise ValueError("Each data set needs a mean, an SD (or SEM or %CV) and N in its first row.")
    m1, s1, n1 = sa["mean"], sa["sd"], int(sa["n"])
    m2, s2, n2 = sb["mean"], sb["sd"], int(sb["n"])
    tails, conf = p.get("tails", 2), p.get("conf", 0.95)
    A, B = column_letter(ca), column_letter(cb)
    v1, v2 = s1 ** 2, s2 ** 2
    if test == "welch":
        se = np.sqrt(v1 / n1 + v2 / n2)
        df = (v1 / n1 + v2 / n2) ** 2 / ((v1 / n1) ** 2 / (n1 - 1) + (v2 / n2) ** 2 / (n2 - 1))
    else:
        se = np.sqrt(((n1 - 1) * v1 + (n2 - 1) * v2) / (n1 + n2 - 2) * (1 / n1 + 1 / n2))
        df = n1 + n2 - 2
    d = m2 - m1
    tv = d / se
    pv = float(sps.t.sf(abs(tv), df) * (2 if tails == 2 else 1))
    tc = sps.t.ppf(1 - (1 - conf) / 2, df)
    name = TEST_NAMES[(design, dist, test)] + " (from summary data)"
    rows = [("Data table", [t.name], "row"), (f"Data set {A}", [t.label(ca)], "row"),
            (f"Data set {B}", [t.label(cb)], "row"), ("", [], "blank"), (name, [], "section"),
            ("P value", [fmt_p(pv)], "row"), ("Significance", [p_summary(pv)], "row"),
            (f"Significant at α = {ALPHA:g}", ["Yes" if pv < ALPHA else "No"], "row"),
            ("Tails", ["Two-sided" if tails == 2 else "One-sided"], "row"),
            ("t", [f"{abs(tv):.3f}"], "row"),
            ("Degrees of freedom" + (" (Welch)" if test == "welch" else ""),
             [fmt(df) if test == "welch" else str(int(df))], "row"),
            ("", [], "blank"), ("Size of the difference", [], "section"),
            (f"Difference of means ({B} − {A})", [fmt(d)], "row"),
            ("Standard error of the difference", [fmt(se)], "row"),
            (f"{conf:.0%} CI of the difference", [f"{fmt(d - tc * se)} to {fmt(d + tc * se)}"], "row")]
    res = AnalysisResult(pages=[ResultPage("Results", [name], rows)], p=pv, pair=(ca, cb))
    res.comparisons = [(ca, cb, pv)]
    return res


def _data_analyzed(A: str, B: str, n1: int, n2: int) -> list:
    return [
        ("", [], "blank"),
        ("Sample sizes", [], "section"),
        (f"n, {A}", [str(n1)], "row"),
        (f"n, {B}", [str(n2)], "row"),
    ]


# ---------------------------------------------------------------------------
# Descriptive statistics
# ---------------------------------------------------------------------------

def _descriptive(an) -> AnalysisResult:
    return AnalysisResult(pages=[_descriptive_page(an.table, an.columns)])


def _descriptive_page(t, cols: list[int]) -> ResultPage:
    data = [t.values(c) for c in cols]

    def each(f):
        return [fmt(float(f(x))) if len(x) else "" for x in data]

    def pct(q):
        # Prism computes percentiles with the (n+1)p rule — numpy's "weibull".
        return lambda x: np.percentile(x, q, method="weibull") if len(x) > 1 else x[0]

    def ci(sign):
        def f(x):
            if len(x) < 2:
                return np.nan
            se = x.std(ddof=1) / np.sqrt(len(x))
            return x.mean() + sign * sps.t.ppf(0.975, len(x) - 1) * se
        return f

    rows = [
        ("N", [str(len(x)) for x in data], "row"),
        ("", [], "blank"),
        ("Minimum", each(np.min), "row"),
        ("25th percentile", each(pct(25)), "row"),
        ("Median", each(np.median), "row"),
        ("75th percentile", each(pct(75)), "row"),
        ("Maximum", each(np.max), "row"),
        ("Range", each(lambda x: x.max() - x.min()), "row"),
        ("", [], "blank"),
        ("Mean", each(np.mean), "row"),
        ("SD", each(lambda x: x.std(ddof=1) if len(x) > 1 else np.nan), "row"),
        ("SEM", each(lambda x: x.std(ddof=1) / np.sqrt(len(x)) if len(x) > 1 else np.nan), "row"),
        ("", [], "blank"),
        ("95% CI of the mean, lower", each(ci(-1)), "row"),
        ("95% CI of the mean, upper", each(ci(+1)), "row"),
        ("", [], "blank"),
        ("Coefficient of variation (CV)", [f"{x.std(ddof=1) / x.mean() * 100:.2f}%" if len(x) > 1 and x.mean() else "" for x in data], "row"),
        ("", [], "blank"),
        ("Sum", each(np.sum), "row"),
    ]
    return ResultPage("Descriptive statistics", [t.label(c) for c in cols], rows)
