"""One-sample t test and Wilcoxon signed-rank test against a hypothetical value, and
outlier detection (Grubbs). Each data set is tested separately, one result column each."""

from __future__ import annotations

import math

import numpy as np
from scipy import stats as sps

from asterism.core.stats import _wilcoxon

from .results import AnalysisResult, ResultPage, fmt, fmt_p, p_summary


def one_sample(an) -> AnalysisResult:
    ALPHA = float(an.params.get("alpha", 0.05))      # significance level (Settings)
    t, cols, p = an.table, an.columns, an.params
    mu = float(p.get("mu", 0.0))
    test = p.get("test", "t")                       # t | wilcoxon
    tails, conf = p.get("tails", 2), p.get("conf", 0.95)
    data = [t.values(c) for c in cols]
    rows: list[tuple[str, list[str], str]] = []
    if test == "t":
        name = "One-sample t test"
        res_rows = []
        for x in data:
            n = len(x)
            if n < 2:
                res_rows.append(None)
                continue
            m, sd = x.mean(), x.std(ddof=1)
            se = sd / math.sqrt(n)
            tv = (m - mu) / se if se > 0 else math.inf
            pv = float(sps.t.sf(abs(tv), n - 1) * (2 if tails == 2 else 1))
            tc = sps.t.ppf(1 - (1 - conf) / 2, n - 1)
            res_rows.append({"m": m, "t": tv, "df": n - 1, "p": pv, "d": m - mu,
                             "ci": (m - mu - tc * se, m - mu + tc * se), "n": n,
                             "r2": tv * tv / (tv * tv + n - 1) if n > 1 else float("nan")})
        rows += [("Hypothetical mean", [fmt(mu)] * len(cols), "row"),
                 ("Actual mean", [fmt(r["m"]) if r else "" for r in res_rows], "row"),
                 ("Number of values", [str(len(x)) for x in data], "row"), ("", [], "blank"),
                 (name, [], "section"),
                 ("t", [f"{abs(r['t']):.3f}" if r else "" for r in res_rows], "row"),
                 ("Degrees of freedom", [str(r["df"]) if r else "" for r in res_rows], "row"),
                 ("P value", [fmt_p(r["p"]) if r else "" for r in res_rows], "row"),
                 ("Significance", [p_summary(r["p"]) if r else "" for r in res_rows], "row"),
                 (f"Significant at α = {ALPHA:g}", [("Yes" if r["p"] < ALPHA else "No") if r else "" for r in res_rows], "row"),
                 ("Tails", ["Two-sided" if tails == 2 else "One-sided"] * len(cols), "row"),
                 ("", [], "blank"), ("Size of the discrepancy", [], "section"),
                 ("Discrepancy (actual − hypothetical)", [fmt(r["d"]) if r else "" for r in res_rows], "row"),
                 (f"{conf:.0%} CI of the discrepancy",
                  [f"{fmt(r['ci'][0])} to {fmt(r['ci'][1])}" if r else "" for r in res_rows], "row"),
                 ("η² (R²)", [f"{r['r2']:.4f}" if r else "" for r in res_rows], "row")]
    else:
        name = "Wilcoxon signed-rank test"
        res_rows = []
        for x in data:
            if len(x) < 2:
                res_rows.append(None)
                continue
            r = _wilcoxon(np.full(len(x), mu), x)
            pv = r.p / 2 if tails == 1 else r.p
            d = x - mu
            nz = d[d != 0]
            rk = sps.rankdata(np.abs(nz))
            pos, neg = float(rk[nz > 0].sum()), float(-rk[nz < 0].sum())
            res_rows.append({"p": pv, "pos": pos, "neg": neg, "W": pos + neg, "med": float(np.median(x)),
                             "method": "Exact" if r.settings.get("wilcoxon_method") == "exact" else "Normal approximation"})
        rows += [("Hypothetical median", [fmt(mu)] * len(cols), "row"),
                 ("Actual median", [fmt(r["med"]) if r else "" for r in res_rows], "row"),
                 ("Number of values", [str(len(x)) for x in data], "row"), ("", [], "blank"),
                 (name, [], "section"),
                 ("W (sum of signed ranks)", [fmt(r["W"]) if r else "" for r in res_rows], "row"),
                 ("Sum of positive ranks", [fmt(r["pos"]) if r else "" for r in res_rows], "row"),
                 ("Sum of negative ranks", [fmt(r["neg"]) if r else "" for r in res_rows], "row"),
                 ("P value", [fmt_p(r["p"]) if r else "" for r in res_rows], "row"),
                 ("P value method", [r["method"] if r else "" for r in res_rows], "row"),
                 ("Significance", [p_summary(r["p"]) if r else "" for r in res_rows], "row"),
                 (f"Significant at α = {ALPHA:g}", [("Yes" if r["p"] < ALPHA else "No") if r else "" for r in res_rows], "row"),
                 ("Tails", ["Two-sided" if tails == 2 else "One-sided"] * len(cols), "row")]
    return AnalysisResult(pages=[ResultPage("Results", [t.label(c) for c in cols], rows)])


# ---------------------------------------------------------------------------
# Outliers (Grubbs)
# ---------------------------------------------------------------------------

def grubbs_critical(n: int, alpha: float) -> float:
    tc = sps.t.ppf(1 - alpha / (2 * n), n - 2)
    return (n - 1) / math.sqrt(n) * math.sqrt(tc ** 2 / (n - 2 + tc ** 2))


def grubbs(x: np.ndarray, alpha: float, iterative: bool) -> list[float]:
    """Values flagged as outliers by Grubbs' test (two-sided), once or repeated."""
    x = list(map(float, x))
    flagged = []
    while len(x) >= 3:
        a = np.array(x)
        sd = a.std(ddof=1)
        if sd == 0:
            break
        i = int(np.argmax(np.abs(a - a.mean())))
        G = abs(a[i] - a.mean()) / sd
        if G > grubbs_critical(len(a), alpha):
            flagged.append(x.pop(i))
            if not iterative:
                break
        else:
            break
    return flagged


def outliers(an) -> AnalysisResult:
    t, cols, p = an.table, an.columns, an.params
    alpha = float(p.get("alpha", 0.05))
    method_key = p.get("method", "grubbs")
    iterative = method_key == "grubbs_iterative"
    data = [t.values(c) for c in cols]
    if method_key == "rout":
        q = float(p.get("q", 0.01))
        found = [rout_values(x, q) for x in data]
        method = "ROUT"
        level = ("Q (maximum false discovery rate)", [f"{q * 100:g}%"] * len(cols), "row")
    else:
        found = [grubbs(x, alpha, iterative) for x in data]
        method = "Grubbs' test, repeated" if iterative else "Grubbs' test (one outlier at most)"
        level = ("α", [f"{alpha:g}"] * len(cols), "row")
    rows = [("Method", [method] * len(cols), "row"), level, ("", [], "blank"),
            ("Values analysed", [str(len(x)) for x in data], "row"),
            ("Outliers found", [str(len(f)) for f in found], "row"),
            ("Outlier values", [", ".join(fmt(v) for v in f) or "None" for f in found], "row"),
            ("Values kept", [str(len(x) - len(f)) for x, f in zip(data, found)], "row")]
    kept_rows = []
    cleaned = []
    for x, f in zip(data, found):
        left = list(x)
        for v in f:
            left.remove(v)
        cleaned.append(left)
    for r in range(max((len(c) for c in cleaned), default=0)):
        kept_rows.append((str(r + 1), [fmt(c[r]) if r < len(c) else "" for c in cleaned], "row"))
    page2 = ResultPage("Cleaned data", [t.label(c) for c in cols], kept_rows)
    page2.first_column = "Row"
    return AnalysisResult(pages=[ResultPage("Outliers", [t.label(c) for c in cols], rows), page2])


def rout_values(x: np.ndarray, q: float = 0.01) -> list[float]:
    """ROUT on one group of values: a robust fit of a horizontal line, then the
    false-discovery-rate outlier test (nonlin.rout)."""
    from .models import Model
    from .nonlin import Data, rout
    if len(x) < 3:
        return []
    m = Model("mean", "", "Mean", "Y = Mean", ["Mean"], lambda xx, mu: mu + 0 * xx,
              lambda xx, yy: (float(np.median(yy)),))
    mask = rout(m, Data(np.arange(len(x), dtype=float), np.asarray(x, float)), q)
    return [float(v) for v in np.asarray(x)[mask]]
