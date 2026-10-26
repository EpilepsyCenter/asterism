"""Frequency distribution: counts, relative frequencies or cumulative distributions.

Binning matches Prism exactly (verified on six golden cases): bin i has centre
c0 + i·w and holds values x with  (c0 − w/2) + i·w ≤ x  <  next lower edge, computed as
floor((x − (c0 − w/2)) / w). Automatic choices: bin width = range / 20 rounded to a
1-2-5 number; first and last bin centres = the centres of the bins holding the smallest
and largest values. Values outside the first and last bins are left out (and counted).
"""

from __future__ import annotations

import math

import numpy as np

from .results import AnalysisResult, ResultPage, fmt


def nice_width(span: float) -> float:
    if span <= 0 or not math.isfinite(span):
        return 1.0
    raw = span / 20.0
    e = 10.0 ** math.floor(math.log10(raw))
    m = raw / e
    q = min((1.0, 2.0, 5.0, 10.0), key=lambda v: abs(math.log(m / v)))
    return q * e


def bin_index(x: np.ndarray, c0: float, w: float) -> np.ndarray:
    return np.floor((x - (c0 - w / 2)) / w).astype(int)


def bins_for(data: list[np.ndarray], params: dict) -> tuple[float, float, int]:
    """(first centre, width, number of bins)."""
    allx = np.concatenate([d for d in data if len(d)]) if any(len(d) for d in data) else np.array([0.0])
    w = params.get("bin_width") or nice_width(float(allx.max() - allx.min()))
    if params.get("first_center") is not None:
        c0 = float(params["first_center"])
    else:
        c0 = math.floor(allx.min() / w + 0.5) * w        # centre of the bin holding the minimum
    if params.get("last_center") is not None:
        last = float(params["last_center"])
    else:
        last = c0 + int(bin_index(np.array([allx.max()]), c0, w)[0]) * w
    nb = max(1, int(round((last - c0) / w)) + 1)
    return c0, w, nb


def tabulate(x: np.ndarray, c0: float, w: float, nb: int, mode: str, cumulative: bool) -> tuple[np.ndarray, int]:
    idx = bin_index(x, c0, w)
    inside = (idx >= 0) & (idx < nb)
    counts = np.bincount(idx[inside], minlength=nb)[:nb].astype(float)
    if cumulative:
        counts = np.cumsum(counts)
    n = len(x)
    if mode == "fractions" and n:
        counts = counts / n
    elif mode == "percentages" and n:
        counts = counts / n * 100.0
    return counts, int((~inside).sum())


def frequency(an) -> AnalysisResult:
    t, cols, p = an.table, an.columns, an.params
    data = [t.values(c) for c in cols]
    c0, w, nb = bins_for(data, p)
    mode = p.get("tabulate", "counts")              # counts | fractions | percentages
    cumulative = p.get("cumulative", False)
    tables, left_out = [], []
    for x in data:
        vals, out = tabulate(x, c0, w, nb, mode, cumulative)
        tables.append(vals)
        left_out.append(out)
    centers = c0 + np.arange(nb) * w
    what = {"counts": "Number of values", "fractions": "Fraction of values",
            "percentages": "Percentage of values"}[mode]
    if cumulative:
        what = "Cumulative " + what[0].lower() + what[1:]
    rows = [(fmt(float(c)), [_num(v[i], mode) for v in tables], "row") for i, c in enumerate(centers)]
    page = ResultPage("Distribution", [t.label(c) for c in cols], rows)
    page.first_column = "Bin centre"
    info = [("Bin width", [fmt(w)] * len(cols), "row"),
            ("First bin centre", [fmt(c0)] * len(cols), "row"),
            ("Number of bins", [str(nb)] * len(cols), "row"),
            ("Tabulated", [what] * len(cols), "row"),
            ("Values binned", [str(len(x) - o) for x, o in zip(data, left_out)], "row"),
            ("Values outside the bins", [str(o) for o in left_out], "row")]
    result = AnalysisResult(pages=[page, ResultPage("Bins", [t.label(c) for c in cols], info)])
    result.table = {"centers": centers.tolist(), "values": [v.tolist() for v in tables], "width": float(w),
                    "what": what}
    from asterism.doc.model import Table
    out = Table(an.name, "xy", "single", ncols=max(1, len(cols)))
    for r, cx in enumerate(centers):
        out.set(r, "x", float(cx), emit=False)
    for j, vals in enumerate(tables):
        for r, v in enumerate(vals):
            out.set(r, out.flat(j), float(v), emit=False)
    for j, c in enumerate(cols):
        out.titles[j] = t.label(c)
    out.bin_width = float(w)
    out.cumulative = bool(cumulative)
    result.out_table = out
    return result


def _num(v: float, mode: str) -> str:
    if mode == "counts":
        return str(int(round(v)))
    return f"{v:.4g}" if mode == "fractions" else f"{v:.2f}"
