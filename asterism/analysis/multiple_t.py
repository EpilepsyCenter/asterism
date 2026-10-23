"""Multiple t tests (and rank tests): one comparison of two data sets per row, with a
correction for multiple comparisons or false-discovery-rate control.

Tests: Student's t (each row's own pooled SD), Welch's t, Mann-Whitney, paired t, Wilcoxon.
Corrections: Holm-Šídák (default), Bonferroni, Šídák, none; FDR: two-stage step-up
(Benjamini, Krieger & Yekutieli), Benjamini-Hochberg, Benjamini-Yekutieli, reported as q
values with a discovery decision at the chosen Q.
"""

from __future__ import annotations

import math

import numpy as np
from scipy import stats as sps

from asterism.core.stats import _mann_whitney, _wilcoxon

from .anova import _holm_sidak
from .anova2 import fmt_df
from .results import AnalysisResult, ResultPage, fmt, fmt_p, p_summary

TESTS = {"student": "Unpaired t test", "welch": "Welch's t test", "mw": "Mann-Whitney test",
         "paired": "Paired t test", "wilcoxon": "Wilcoxon signed-rank test"}
CORRECTIONS = {"holm_sidak": "Holm-Šídák", "bonferroni": "Bonferroni", "sidak": "Šídák",
               "none": "None", "fdr_bky": "Two-stage step-up (Benjamini, Krieger, Yekutieli)",
               "fdr_bh": "Benjamini-Hochberg", "fdr_by": "Benjamini-Yekutieli"}


def title(params: dict) -> str:
    test = params.get("test", "welch")
    return {"mw": "Multiple Mann-Whitney tests", "wilcoxon": "Multiple Wilcoxon tests"}.get(
        test, "Multiple t tests")


def row_test(a: np.ndarray, b: np.ndarray, test: str) -> dict:
    if test in ("student", "welch"):
        n1, n2 = len(a), len(b)
        if n1 < 2 or n2 < 2:
            raise ValueError("needs 2+ values in each group")
        m1, m2, v1, v2 = a.mean(), b.mean(), a.var(ddof=1), b.var(ddof=1)
        if test == "welch":
            se = math.sqrt(v1 / n1 + v2 / n2)
            df = (v1 / n1 + v2 / n2) ** 2 / ((v1 / n1) ** 2 / (n1 - 1) + (v2 / n2) ** 2 / (n2 - 1))
        else:
            se = math.sqrt(((n1 - 1) * v1 + (n2 - 1) * v2) / (n1 + n2 - 2) * (1 / n1 + 1 / n2))
            df = n1 + n2 - 2
        t = (m2 - m1) / se
        return {"p": float(2 * sps.t.sf(abs(t), df)), "stat": abs(t), "df": df, "m1": m1, "m2": m2,
                "diff": m2 - m1, "se": se}
    if test == "mw":
        r = _mann_whitney(a, b)
        return {"p": float(r.p), "stat": float(r.statistic), "df": None, "m1": float(np.median(a)),
                "m2": float(np.median(b)), "diff": float(np.median(b) - np.median(a)), "se": None}
    n = min(len(a), len(b))
    a, b = a[:n], b[:n]
    if test == "paired":
        d = b - a
        if n < 2:
            raise ValueError("needs 2+ pairs")
        se = d.std(ddof=1) / math.sqrt(n)
        t = d.mean() / se
        return {"p": float(2 * sps.t.sf(abs(t), n - 1)), "stat": abs(t), "df": n - 1, "m1": a.mean(),
                "m2": b.mean(), "diff": d.mean(), "se": se}
    r = _wilcoxon(a, b)
    return {"p": float(r.p), "stat": None, "df": None, "m1": float(np.median(a)),
            "m2": float(np.median(b)), "diff": float(np.median(b - a)), "se": None}


def _bh(p: np.ndarray) -> np.ndarray:
    m = len(p)
    order = np.argsort(p)
    q = np.empty(m)
    prev = 1.0
    for rank in range(m, 0, -1):
        i = order[rank - 1]
        prev = min(prev, p[i] * m / rank)
        q[i] = prev
    return q


def _bky_discoveries(p: np.ndarray, Q: float) -> np.ndarray:
    m = len(p)
    q1 = Q / (1 + Q)
    r1 = int(np.sum(_bh(p) <= q1))
    if r1 == 0:
        return np.zeros(m, bool)
    if r1 == m:
        return np.ones(m, bool)
    m0 = m - r1
    return _bh(p) <= q1 * m / m0


def bky_q(p: np.ndarray) -> np.ndarray:
    """Smallest Q at which each hypothesis is discovered by the two-stage procedure."""
    out = np.empty(len(p))
    for i in range(len(p)):
        lo, hi = 0.0, 1.0
        if not _bky_discoveries(p, hi)[i]:
            out[i] = 1.0
            continue
        for _ in range(60):
            mid = (lo + hi) / 2
            if _bky_discoveries(p, mid)[i]:
                hi = mid
            else:
                lo = mid
        out[i] = hi
    return out


def adjust(p: list[float], method: str) -> list[float]:
    arr = np.array(p, float)
    m = len(arr)
    if method == "holm_sidak":
        return _holm_sidak(list(arr))
    if method == "bonferroni":
        return list(np.minimum(1.0, arr * m))
    if method == "sidak":
        return list(1 - (1 - arr) ** m)
    if method == "fdr_bh":
        return list(_bh(arr))
    if method == "fdr_by":
        c = np.sum(1.0 / np.arange(1, m + 1))
        return list(np.minimum(1.0, _bh(arr) * c))
    if method == "fdr_bky":
        return list(bky_q(arr))
    return list(arr)


def multiple_t(an) -> AnalysisResult:
    t, cols, p = an.table, list(an.columns), an.params
    if t.table_type not in ("grouped", "xy"):
        raise ValueError("Multiple t tests compare two data sets row by row in a Grouped table.")
    if len(cols) != 2:
        raise ValueError("Choose exactly two data sets to compare in each row.")
    if t.is_summary():
        raise ValueError("Multiple t tests need the raw replicate values.")
    test = p.get("test", "welch")
    method = p.get("correction", "holm_sidak")
    Q = p.get("q", 0.01)
    alpha = p.get("alpha", 0.05)
    ca, cb = cols
    rows, results, errors = [], [], []
    for r in range(t.nrows_used()):
        a, b = t.row_values(r, ca), t.row_values(r, cb)
        if not len(a) and not len(b):
            continue
        try:
            results.append(row_test(a, b, test))
            rows.append(r)
        except ValueError as e:
            errors.append((r, str(e)))
    if not results:
        raise ValueError("No row has enough values in both data sets.")
    raw = [x["p"] for x in results]
    adj = adjust(raw, method)
    fdr = method.startswith("fdr")
    label = [t.row_label(r) for r in rows]
    is_rank = test in ("mw", "wilcoxon")
    heads = ["Discovery?" if fdr else "Significant?", "P value", "q value" if fdr else "Adjusted P",
             "Median, A" if is_rank else "Mean, A", "Median, B" if is_rank else "Mean, B", "Difference"]
    if test in ("student", "welch", "paired"):
        heads += ["SE of difference", "t", "df"]
    elif test == "mw":
        heads += ["U"]
    table_rows = []
    res = AnalysisResult()
    for lab, x, padj in zip(label, results, adj):
        found = padj <= Q if fdr else padj < alpha
        vals = ["Yes" if found else "No", fmt_p(x["p"]), fmt_p(padj), fmt(x["m1"]), fmt(x["m2"]), fmt(x["diff"])]
        if test in ("student", "welch", "paired"):
            vals += [fmt(x["se"]), f"{x['stat']:.4g}", fmt_df(x["df"])]
        elif test == "mw":
            vals += [fmt(x["stat"])]
        table_rows.append((lab, vals, "row"))
    for r, err in errors:
        table_rows.append((f"Row {r + 1}", ["", "", "", "", "", err], "row"))
    page = ResultPage("Results", heads, table_rows)
    page.first_column = "Row"
    summary = [("Test", [TESTS[test]], "row"),
               ("Multiple comparisons", [CORRECTIONS[method]], "row"),
               ("Threshold", [f"Q = {Q:g}" if fdr else f"α = {alpha:g}"], "row"),
               ("Rows analysed", [str(len(results))], "row"),
               ("Discoveries" if fdr else "Significant rows", [str(sum((q <= Q) if fdr else (q < alpha) for q in adj))], "row")]
    res.pages = [page, ResultPage("Summary", [title(p)], summary)]
    res.rows = [(r, pr, pa) for r, pr, pa in zip(rows, raw, adj)]
    return res
