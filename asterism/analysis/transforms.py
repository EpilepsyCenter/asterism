"""Transforms and data manipulation that produce a result table (Prism's functions, our
wording). Each result table is live: it follows its data table, and it can be graphed and
analysed further like any data table.

  transform   apply a function to every Y (and/or X) value
  normalize   each data set from 0% to 100% (smallest/first/value → largest/last/sum/mean/value)
  baseline    subtract or divide by a baseline data set or baseline rows ("column math")
  prune       keep a range of rows, every nth row, or average every k rows
  transpose   rows become data sets
  smooth      smooth (Savitzky-Golay), differentiate or integrate an XY curve (Prism's
              documented procedures: midpoint finite differences; cumulative trapezoids)
  observed_expected   chi-square (or exact binomial) test of observed counts against expected
"""

from __future__ import annotations

import math

import numpy as np
from scipy import stats as sps

from asterism.doc.model import Table

from .results import AnalysisResult, ResultPage, fmt, fmt_p, p_summary

Y_FUNCS = {
    "k_times": "Y × K", "k_plus": "Y + K", "k_minus": "Y − K", "k_div": "Y ÷ K", "square": "Y²",
    "power": "Y to the power K", "log10": "log₁₀(Y)", "neglog10": "−log₁₀(Y)", "ln": "ln(Y)",
    "pow10": "10 to the power Y", "exp": "e to the power Y", "recip": "1 / Y", "sqrt": "√Y",
    "logit": "ln(Y / (1 − Y))", "arcsin": "arcsine √Y (proportions)", "abs": "|Y|",
    "zscore": "Z score within each data set: (Y − mean) / SD", "user": "Your own equation",
}
X_FUNCS = {"none": "Leave X alone", "k_times": "X × K", "k_plus": "X + K", "log10": "log₁₀(X)",
           "ln": "ln(X)", "recip": "1 / X", "square": "X²", "sqrt": "√X", "pow10": "10 to the power X",
           "exp": "e to the power X"}


def _f(key: str, v: float, k: float) -> float | None:
    try:
        r = {"k_times": lambda: v * k, "k_plus": lambda: v + k, "k_minus": lambda: v - k,
             "k_div": lambda: v / k, "square": lambda: v * v, "power": lambda: v ** k,
             "log10": lambda: math.log10(v), "neglog10": lambda: -math.log10(v), "ln": lambda: math.log(v),
             "pow10": lambda: 10 ** v, "exp": lambda: math.exp(v), "recip": lambda: 1 / v,
             "sqrt": lambda: math.sqrt(v), "logit": lambda: math.log(v / (1 - v)),
             "arcsin": lambda: math.asin(math.sqrt(v)), "abs": lambda: abs(v)}[key]()
    except (ValueError, ZeroDivisionError, OverflowError):
        return None
    if isinstance(r, complex) or not math.isfinite(r):      # e.g. a negative number to the power 0.5
        return None
    return float(r)


def _frame(t, cols: list[int], name: str, y_format: str | None = None, replicates: int | None = None,
           table_type: str | None = None) -> Table:
    """An empty table with t's format (or the given one), its X / row titles and the
    chosen data sets' titles."""
    out = Table(name, table_type or t.table_type, y_format or t.y_format,
                replicates=replicates if replicates is not None else t.replicates,
                x_format=t.x_format if (table_type or t.table_type) == "xy" else None,
                row_titles=t.has_row_titles, ncols=max(1, len(cols)))
    for j, c in enumerate(cols):
        out.titles[j] = t.label(c)
    return out


def _copy_rows(t, out: Table) -> None:
    for r in range(t.nrows_used()):
        if out.has_x() and t.has_x():
            v = t.get(r, "x")
            if v is not None:
                out.set(r, "x", v, emit=False)
                if (r, "x") in t.excluded:
                    out.excluded.add((r, "x"))
        if out.has_row_titles and t.has_row_titles and t.get(r, "row") is not None:
            out.set(r, "row", t.get(r, "row"), emit=False)


def _table_page(out: Table) -> ResultPage:
    heads = []
    for ds in range(out.ncols):
        for sub in range(out.width()):
            heads.append(out.label(ds) + (f" · {out.sub_label(ds, sub)}" if out.width() > 1 else ""))
    rows = []
    for r in range(out.nrows_used()):
        lab = out.row_label(r)
        vals = [fmt(out.get(r, out.flat(ds, sub))) if isinstance(out.get(r, out.flat(ds, sub)), float) else ""
                for ds in range(out.ncols) for sub in range(out.width())]
        rows.append((lab, vals, "row"))
    pg = ResultPage("Result table", heads, rows)
    pg.first_column = "X" if out.has_x() else "Row"
    return pg


def _result(out: Table, info: list) -> AnalysisResult:
    res = AnalysisResult(pages=[_table_page(out), ResultPage("Settings", ["What was done"], info)])
    res.out_table = out
    return res


# ---------------------------------------------------------------------------

def transform(an) -> AnalysisResult:
    t, cols, p = an.table, list(an.columns), an.params
    if t.is_summary():
        raise ValueError("Transforms need raw values (this table holds means and errors).")
    yk, xk = p.get("y", "log10"), p.get("x", "none")
    k, kx = float(p.get("k", 1.0)), float(p.get("kx", 1.0))
    out = _frame(t, cols, an.name)
    _copy_rows(t, out)
    if t.has_x() and xk != "none":
        for r in range(t.nrows_used()):
            v = t.get(r, "x")
            out.set(r, "x", _f(xk, v, kx) if isinstance(v, float) else None, emit=False)
    user = None
    if yk == "user":
        from .models import _FUNCS, compile_expression
        expr = p.get("equation", "Y = Y")
        try:
            user = compile_expression(expr.split("=", 1)[1] if "=" in expr else expr, {"X", "Y", "K"})
        except Exception as e:
            raise ValueError(f"The equation can't be used: {e}")
    for j, c in enumerate(cols):
        vals = t.values(c)
        mu, sd = (float(vals.mean()), float(vals.std(ddof=1))) if len(vals) > 1 else (math.nan, math.nan)
        for sub in range(t.width()):
            f_in, f_out = t.flat(c, sub), out.flat(j, sub)
            for r in range(len(t.y[f_in])):
                v = t._ok(r, f_in)
                if v is None:
                    continue
                if yk == "zscore":
                    nv = (v - mu) / sd if sd and math.isfinite(sd) and sd > 0 else None
                elif yk == "user":
                    env = dict(_FUNCS)
                    env.update(Y=v, X=t.x_value(r) if t.has_x() else float(r + 1), K=k)
                    try:
                        nv = float(eval(user, {"__builtins__": {}}, env))
                        nv = nv if math.isfinite(nv) else None
                    except Exception:
                        nv = None
                else:
                    nv = _f(yk, v, k)
                if nv is not None:
                    out.set(r, f_out, nv, emit=False)
    info = [("Y", [Y_FUNCS[yk] + (f" (K = {k:g})" if "K" in Y_FUNCS[yk] else "")
                   + (f": {p.get('equation')}" if yk == "user" else "")], "row")]
    if t.has_x():
        info.append(("X", [X_FUNCS[xk] + (f" (K = {kx:g})" if "K" in X_FUNCS[xk] else "")], "row"))
    info.append(("Values that can't be transformed", ["Left blank (for example the log of zero)"], "row"))
    return _result(out, info)


def normalize(an) -> AnalysisResult:
    t, cols, p = an.table, list(an.columns), an.params
    if t.is_summary():
        raise ValueError("Normalize needs raw values (this table holds means and errors).")
    zero, hundred = p.get("zero", "min"), p.get("hundred", "max")
    z0, h0 = float(p.get("zero_value", 0.0)), float(p.get("hundred_value", 100.0))
    scale = 100.0 if p.get("percent", True) else 1.0
    out = _frame(t, cols, an.name)
    _copy_rows(t, out)
    info = []
    for j, c in enumerate(cols):
        rows = [r for r in range(t.nrows_used()) if len(t.row_values(r, c))]
        means = [float(t.row_values(r, c).mean()) for r in rows]
        if not means:
            continue
        lo = {"min": min(means), "first": means[0], "value": z0}[zero]
        hi = {"max": max(means), "first": means[0], "last": means[-1], "sum": float(np.sum(means)),
              "mean": float(np.mean(means)), "value": h0}[hundred]
        span = hi - lo
        info.append((t.label(c), [f"0% = {fmt(lo)}, 100% = {fmt(hi)}"], "row"))
        if span == 0:
            continue
        for sub in range(t.width()):
            f_in, f_out = t.flat(c, sub), out.flat(j, sub)
            for r in range(len(t.y[f_in])):
                v = t._ok(r, f_in)
                if v is not None:
                    out.set(r, f_out, (v - lo) / span * scale, emit=False)
    return _result(out, info + [("Result", ["Percentages" if scale == 100 else "Fractions"], "row")])


BASELINE_OPS = {"subtract": "Subtract the baseline", "divide": "Divide by the baseline",
                "percent": "Percent of the baseline", "percent_change": "Percent change from the baseline"}


def baseline(an) -> AnalysisResult:
    t, cols, p = an.table, list(an.columns), an.params
    if t.is_summary():
        raise ValueError("Baseline and column maths need raw values (this table holds means and errors).")
    op = p.get("op", "subtract")
    source = p.get("source", "set")                 # set | rows
    base_col = p.get("baseline", cols[0])
    nrows_base = int(p.get("rows", 1))

    def apply(v, b):
        if b is None:
            return None
        if op == "subtract":
            return v - b
        if b == 0:
            return None
        return {"divide": v / b, "percent": v / b * 100, "percent_change": (v - b) / b * 100}[op]
    if source == "set":
        if base_col not in range(t.ncols):
            raise ValueError("Choose the data set to use as the baseline.")
        keep = [c for c in cols if c != base_col]
        if not keep:
            raise ValueError("Choose at least one data set besides the baseline.")
    else:
        keep = cols
    out = _frame(t, keep, an.name)
    _copy_rows(t, out)
    for j, c in enumerate(keep):
        if source == "rows":
            rows = [r for r in range(t.nrows_used()) if len(t.row_values(r, c))][:nrows_base]
            bvals = np.concatenate([t.row_values(r, c) for r in rows]) if rows else np.array([])
            b_all = float(bvals.mean()) if len(bvals) else None
        for sub in range(t.width()):
            f_in, f_out = t.flat(c, sub), out.flat(j, sub)
            for r in range(len(t.y[f_in])):
                v = t._ok(r, f_in)
                if v is None:
                    continue
                if source == "rows":
                    b = b_all
                else:
                    b = t._ok(r, t.flat(base_col, sub)) if p.get("match_replicates", True) else None
                    if b is None:
                        bv = t.row_values(r, base_col)
                        b = float(bv.mean()) if len(bv) else None
                nv = apply(v, b)
                if nv is not None:
                    out.set(r, f_out, nv, emit=False)
    what = (f"data set {t.label(base_col)}" if source == "set" else
            f"the mean of the first {nrows_base} row{'s' if nrows_base != 1 else ''} of each data set")
    return _result(out, [("Operation", [BASELINE_OPS[op]], "row"), ("Baseline", [what], "row")])


def prune(an) -> AnalysisResult:
    t, cols, p = an.table, list(an.columns), an.params
    mode = p.get("mode", "range")                   # range | every | average
    rows = list(range(t.nrows_used()))
    if mode == "range":
        lo, hi = p.get("from"), p.get("to")
        if t.has_x():
            keep = [r for r in rows if t.x_value(r) is not None and (lo is None or t.x_value(r) >= lo)
                    and (hi is None or t.x_value(r) <= hi)]
        else:
            keep = [r for r in rows if (lo is None or r + 1 >= lo) and (hi is None or r + 1 <= hi)]
        groups = [[r] for r in keep]
    elif mode == "every":
        n = max(1, int(p.get("n", 2)))
        groups = [[r] for r in rows[::n]]
    else:
        k = max(1, int(p.get("k", 2)))
        groups = [rows[i:i + k] for i in range(0, len(rows), k)]
    avg = mode == "average"
    out = _frame(t, cols, an.name, y_format="single" if avg else None, replicates=1 if avg else None)
    for i, g in enumerate(groups):
        if out.has_x():
            xs = [t.x_value(r) for r in g if t.x_value(r) is not None]
            if xs:
                out.set(i, "x", float(np.mean(xs)), emit=False)
        if out.has_row_titles and t.has_row_titles:
            out.set(i, "row", t.row_label(g[0]) if not avg else f"{t.row_label(g[0])}–{t.row_label(g[-1])}", emit=False)
        for j, c in enumerate(cols):
            if avg:
                v = np.concatenate([t.row_values(r, c) for r in g]) if g else np.array([])
                if len(v):
                    out.set(i, out.flat(j), float(v.mean()), emit=False)
            else:
                for sub in range(t.width()):
                    v = t._ok(g[0], t.flat(c, sub))
                    if v is not None:
                        out.set(i, out.flat(j, sub), v, emit=False)
    what = {"range": "Rows in a range", "every": f"Every {p.get('n', 2)}th row",
            "average": f"Average of every {p.get('k', 2)} rows"}[mode]
    return _result(out, [("Kept", [what], "row"), ("Rows", [f"{t.nrows_used()} → {len(groups)}"], "row")])


def transpose(an) -> AnalysisResult:
    t, cols, p = an.table, list(an.columns), an.params
    rows = [r for r in range(t.nrows_used()) if any(len(t.row_values(r, c)) for c in cols)]
    if not rows:
        raise ValueError("Nothing to transpose.")
    out = Table(an.name, "grouped", "single", ncols=max(1, len(rows)))
    for j, r in enumerate(rows):
        out.titles[j] = t.row_label(r) if not t.has_x() or t.has_row_titles else fmt(t.x_value(r))
    for i, c in enumerate(cols):
        out.set(i, "row", t.label(c), emit=False)
        for j, r in enumerate(rows):
            v = t.row_values(r, c)
            if len(v):
                out.set(i, out.flat(j), float(v.mean()), emit=False)
    return _result(out, [("Result", ["Each row became a data set; each data set became a row "
                                     "(replicates averaged)"], "row")])


def _savgol_valid(y: np.ndarray, k: int, order: int) -> np.ndarray:
    """Savitzky-Golay over 2k+1 points, interior only (the ends are dropped, as Prism)."""
    w = 2 * k + 1
    if len(y) < w:
        return np.array([])
    if order == 0:
        return np.convolve(y, np.ones(w) / w, mode="valid")
    from scipy.signal import savgol_coeffs
    coef = savgol_coeffs(w, order)
    return np.convolve(y, coef[::-1], mode="valid")


def smooth(an) -> AnalysisResult:
    t, cols, p = an.table, list(an.columns), an.params
    if t.table_type != "xy":
        raise ValueError("Smoothing, derivatives and integrals work on XY tables.")
    op = p.get("op", "smooth")                      # smooth | derivative | derivative2 | integral
    k, order = int(p.get("k", 2)), int(p.get("order", 2))
    do_smooth = op == "smooth" or p.get("smooth_after", False)
    out = Table(an.name, "xy", "single", ncols=max(1, len(cols)))
    for j, c in enumerate(cols):
        out.titles[j] = t.label(c)
    series = {}
    for j, c in enumerate(cols):
        pts = sorted((t.x_value(r), float(t.row_values(r, c).mean())) for r in range(t.nrows_used())
                     if t.x_value(r) is not None and len(t.row_values(r, c)))
        x = np.array([a for a, _ in pts])
        y = np.array([b for _, b in pts])
        for _ in range({"derivative": 1, "derivative2": 2}.get(op, 0)):
            if len(x) < 2:
                break
            dx = np.diff(x)
            y = np.where(dx != 0, np.diff(y) / np.where(dx != 0, dx, 1), np.nan)
            x = (x[1:] + x[:-1]) / 2
        if op == "integral" and len(x):
            area = np.concatenate([[float(p.get("start", 0.0))],
                                   np.cumsum(np.diff(x) * (y[1:] + y[:-1]) / 2) + float(p.get("start", 0.0))])
            y = area
        if do_smooth:
            ys = _savgol_valid(y, k, order)
            x = x[k:len(x) - k] if len(ys) else np.array([])
            y = ys
        series[j] = (x, y)
    # one shared X column: the union of X values (each data set's own points)
    allx = sorted({float(v) for x, _ in series.values() for v in x})
    index = {v: i for i, v in enumerate(allx)}
    for i, v in enumerate(allx):
        out.set(i, "x", v, emit=False)
    for j, (x, y) in series.items():
        for a, b in zip(x, y):
            if math.isfinite(b):
                out.set(index[float(a)], out.flat(j), float(b), emit=False)
    what = {"smooth": "Smoothed", "derivative": "First derivative", "derivative2": "Second derivative",
            "integral": "Integral (cumulative area)"}[op]
    info = [("Result", [what], "row")]
    if do_smooth:
        info.append(("Smoothing", [f"Savitzky-Golay, {k} neighbours on each side, "
                                   f"{'zero' if order == 0 else 'second'}-order polynomial "
                                   f"({k} points dropped at each end)"], "row"))
    if op != "smooth":
        info.append(("Note", ["Derivatives use the midpoints between adjacent X values" if "deriv" in op
                              else "Areas by the trapezoid rule, from the first X"], "row"))
    return _result(out, info)


def observed_expected(an) -> AnalysisResult:
    t, cols, p = an.table, list(an.columns), an.params
    c = cols[0]
    rows = [r for r in range(t.nrows_used()) if t._ok(r, t.flat(c)) is not None]
    obs = np.array([t._ok(r, t.flat(c)) for r in rows], float)
    if len(obs) < 2 or np.any(obs < 0) or np.any(np.abs(obs - np.round(obs)) > 1e-9):
        raise ValueError("Enter the observed counts (whole numbers) in the first data set, two or more rows.")
    n = obs.sum()
    if p.get("expected", "equal") == "column" and len(cols) > 1:
        e = np.array([t._ok(r, t.flat(cols[1])) or 0.0 for r in rows], float)
        if p.get("expected_as", "counts") == "percent":
            e = e / 100 * n
        e = e * n / e.sum() if e.sum() else e
    else:
        e = np.full(len(obs), n / len(obs))
    if np.any(e <= 0):
        raise ValueError("Every expected count must be greater than zero.")
    chi = float(((obs - e) ** 2 / e).sum())
    df = len(obs) - 1
    pv = float(sps.chi2.sf(chi, df))
    rows_out = [("Chi-square test", [], "section"), ("Chi-square, df", [f"{chi:.4g}, {df}"], "row"),
                ("P value", [fmt_p(pv)], "row"), ("P value summary", [p_summary(pv)], "row"),
                ("Observed differs from expected at α = 0.05", ["Yes" if pv < 0.05 else "No"], "row")]
    if len(obs) == 2:
        pb = float(sps.binomtest(int(obs[0]), int(n), e[0] / n).pvalue)
        rows_out += [("", [], "blank"), ("Exact binomial test", [], "section"), ("P value", [fmt_p(pb)], "row"),
                     ("P value summary", [p_summary(pb)], "row")]
    if np.any(e < 5):
        rows_out.append(("Note", ["Some expected counts are below 5: the chi-square approximation is rough"], "row"))
    tab = [(t.row_label(r), [fmt(o), fmt(x), fmt((o - x) / math.sqrt(x))], "row") for r, o, x in zip(rows, obs, e)]
    pg = ResultPage("Observed and expected", ["Observed", "Expected", "Residual (O − E)/√E"], tab)
    pg.first_column = "Category"
    res = AnalysisResult(pages=[ResultPage("Results", ["Observed vs. expected"], rows_out), pg])
    res.p = pv
    return res
