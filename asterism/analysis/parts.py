"""Parts of whole: fraction of total (Prism's function, our wording).

Each value divided by its column total (or row total, or the grand total), as fractions or
percentages; when the values are counts, a confidence interval for each fraction by the
hybrid Wilson/Brown method (as Prism does for proportions).
"""

from __future__ import annotations

import numpy as np

from .contingency import wilson_brown
from .results import AnalysisResult, ResultPage, fmt


def fraction_of_total(an) -> AnalysisResult:
    t, cols, p = an.table, list(an.columns), an.params
    rows = [r for r in range(t.nrows_used()) if any(t._ok(r, t.flat(c)) is not None for c in cols)]
    if not rows:
        raise ValueError("No values to divide.")
    m = np.array([[t._ok(r, t.flat(c)) or 0.0 for c in cols] for r in rows], float)
    if np.any(m < 0):
        raise ValueError("Fractions of a total need values that are zero or positive.")
    of = p.get("of", "column")                 # column | row | grand
    pct = p.get("percent", True)
    conf = p.get("conf", 0.95)
    if of == "row":
        tot = m.sum(1, keepdims=True)
    elif of == "grand":
        tot = np.full_like(m, m.sum())
    else:
        tot = m.sum(0, keepdims=True)
    frac = np.divide(m, tot, out=np.full_like(m, np.nan), where=tot > 0)
    scale = 100.0 if pct else 1.0
    want_ci = p.get("ci", False)
    are_counts = bool(np.all(np.abs(m - np.round(m)) < 1e-9))
    heads = []
    for c in cols:
        heads.append(t.label(c))
        if want_ci and are_counts:
            heads.append(f"{t.label(c)}: {conf:.0%} CI")
    out_rows = []
    for i, r in enumerate(rows):
        vals = []
        for j, c in enumerate(cols):
            vals.append(fmt(frac[i, j] * scale))
            if want_ci and are_counts:
                n = int(round(np.broadcast_to(tot, m.shape)[i, j]))
                lo, hi = wilson_brown(int(round(m[i, j])), n, conf) if n else (np.nan, np.nan)
                vals.append(f"{fmt(lo * scale)} to {fmt(hi * scale)}")
        out_rows.append((t.row_label(r), vals, "row"))
    out_rows.append(("Total", [fmt(float(np.nansum(frac[:, j])) * scale) if of == "column" else "" for j in
                               range(len(cols)) for _ in ([0, 1] if want_ci and are_counts else [0])], "row"))
    page = ResultPage("Fractions", heads, out_rows)
    page.first_column = "Row"
    info = [("Divided by", [{"column": "Each column's total", "row": "Each row's total",
                             "grand": "The grand total"}[of]], "row"),
            ("Shown as", ["Percentages" if pct else "Fractions"], "row")]
    if want_ci and not are_counts:
        info.append(("Confidence intervals", ["Not computed: the values are not counts"], "row"))
    res = AnalysisResult(pages=[page, ResultPage("Settings", ["Fraction of total"], info)])
    res.table = {"fractions": frac.tolist(), "rows": [t.row_label(r) for r in rows]}
    return res
