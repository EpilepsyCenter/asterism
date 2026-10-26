"""XY analyses: linear regression, correlation, area under the curve (Prism's functions,
our wording). Nonlinear regression is in nonlin.py.

Golden-tested findings (Prism 11, the lab's Seizure_data project):
- Linear regression treats each replicate as its own point by default; an excluded X
  leaves its row out.
- Correlation of X with each data set uses the mean of each row's replicates.
- Spearman: exact P from the permutation distribution of the (tied) ranks for small n,
  else the t approximation; the confidence interval uses Fisher's z with
  SE = √(1.06 / (n − 3)) and is reported only when n > 10.
"""

from __future__ import annotations

import math

import numpy as np
from scipy import stats as sps

from asterism.doc.model import column_letter

from .results import AnalysisResult, ResultPage, fmt, fmt_p, p_summary


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

def xy_points(t, c: int, replicates: str = "individual") -> tuple[np.ndarray, np.ndarray]:
    """(x, y) for one data set. replicates: individual (each replicate a point) or mean.
    Tables of means and errors always give the means."""
    xs, ys = [], []
    for r in range(t.nrows_used()):
        x = t.x_value(r)
        if x is None:
            continue
        if t.is_summary():
            sm = t.summary(r, c)
            if sm and sm.get("mean") is not None:
                xs.append(x)
                ys.append(sm["mean"])
            continue
        v = t.row_values(r, c)
        if not len(v):
            continue
        if replicates == "mean":
            xs.append(x)
            ys.append(float(v.mean()))
        else:
            xs += [x] * len(v)
            ys += [float(a) for a in v]
    return np.array(xs, float), np.array(ys, float)


def xy_rows(t, c: int) -> list[dict]:
    """Per-row summary: x, mean, sd, n, sem (for areas, graphs and weighting)."""
    out = []
    for r in range(t.nrows_used()):
        x = t.x_value(r)
        if x is None:
            continue
        if t.is_summary():
            sm = t.summary(r, c)
            if sm and sm.get("mean") is not None:
                out.append({"row": r, "x": x, "mean": sm["mean"], "sd": sm.get("sd"),
                            "n": sm.get("n"), "sem": sm.get("sem")})
            continue
        v = t.row_values(r, c)
        if len(v):
            sd = float(v.std(ddof=1)) if len(v) > 1 else None
            out.append({"row": r, "x": x, "mean": float(v.mean()), "sd": sd, "n": len(v),
                        "sem": sd / math.sqrt(len(v)) if sd is not None else None})
    return out


def _need_xy(t) -> None:
    if t.table_type != "xy":
        raise ValueError("This analysis works on an XY table.")


# ---------------------------------------------------------------------------
# Linear regression
# ---------------------------------------------------------------------------

def linfit(x: np.ndarray, y: np.ndarray, conf: float = 0.95, through: tuple | None = None) -> dict:
    """Least-squares line. through=(x0, y0) forces the line through that point."""
    n = len(x)
    if through is not None:
        x0, y0 = through
        dx, dy = x - x0, y - y0
        if n < 2 or not np.any(dx):
            raise ValueError("needs at least two points with different X")
        slope = float(dx @ dy / (dx @ dx))
        intercept = y0 - slope * x0
        df = n - 1
        res = y - (intercept + slope * x)
        ss = float(res @ res)
        s2 = ss / df if df > 0 else math.nan
        se_s = math.sqrt(s2 / (dx @ dx)) if df > 0 else math.nan
        se_i = abs(x0) * se_s
        sxx = float(dx @ dx)
        xm = x0
    else:
        if n < 3 and n < 2:
            raise ValueError("needs at least two points")
        xm, ym = x.mean(), y.mean()
        sxx = float(((x - xm) ** 2).sum())
        if sxx == 0:
            raise ValueError("needs at least two different X values")
        slope = float(((x - xm) * (y - ym)).sum() / sxx)
        intercept = float(ym - slope * xm)
        df = n - 2
        res = y - (intercept + slope * x)
        ss = float(res @ res)
        s2 = ss / df if df > 0 else math.nan
        se_s = math.sqrt(s2 / sxx) if df > 0 else math.nan
        se_i = math.sqrt(s2 * (1 / n + xm ** 2 / sxx)) if df > 0 else math.nan
    tc = float(sps.t.ppf(1 - (1 - conf) / 2, df)) if df > 0 else math.nan
    sst = float(((y - y.mean()) ** 2).sum())
    r2 = 1 - ss / sst if sst > 0 else math.nan
    F = (slope / se_s) ** 2 if se_s and se_s > 0 else math.inf
    p = float(sps.f.sf(F, 1, df)) if df > 0 else math.nan
    fit = {"n": n, "slope": slope, "intercept": intercept, "se_slope": se_s, "se_intercept": se_i,
           "ci_slope": (slope - tc * se_s, slope + tc * se_s),
           "ci_intercept": (intercept - tc * se_i, intercept + tc * se_i),
           "df": df, "ss": ss, "syx": math.sqrt(s2) if df > 0 else math.nan, "r2": r2,
           "F": F, "p": p, "xm": xm, "sxx": sxx, "tc": tc, "through": through,
           "x_min": float(x.min()), "x_max": float(x.max())}
    fit["x_intercept"] = -intercept / slope if slope else math.nan
    fit["ci_x_intercept"] = x_at_y_ci(fit, 0.0)
    return fit


def band(fit: dict, x: np.ndarray, prediction: bool = False) -> tuple[np.ndarray, np.ndarray]:
    """Confidence (or prediction) band of a fitted line at x."""
    y = fit["intercept"] + fit["slope"] * x
    s2 = fit["syx"] ** 2
    if fit["through"] is not None:
        var = s2 * (x - fit["through"][0]) ** 2 / fit["sxx"]
    else:
        var = s2 * (1 / fit["n"] + (x - fit["xm"]) ** 2 / fit["sxx"])
    if prediction:
        var = var + s2
    h = fit["tc"] * np.sqrt(var)
    return y - h, y + h


def x_at_y_ci(fit: dict, y0: float) -> tuple[float, float]:
    """Confidence interval of the X where the line reaches y0: where the confidence band
    crosses y0 (Fieller). Infinite when the slope's interval includes zero."""
    lo, hi = fit["ci_slope"]
    if not (lo > 0 or hi < 0) or not math.isfinite(fit["tc"]):
        return (-math.inf, math.inf)
    b, a, t2 = fit["slope"], fit["intercept"], fit["tc"] ** 2
    s2 = fit["syx"] ** 2
    if fit["through"] is not None:
        x0 = fit["through"][0]
        # (a + b x − y0)² = t² s² (x − x0)²/Sxx
        k = t2 * s2 / fit["sxx"]
        A, B, C = b * b - k, 2 * b * (a - y0) + 2 * k * x0, (a - y0) ** 2 - k * x0 * x0
    else:
        xm, sxx, n = fit["xm"], fit["sxx"], fit["n"]
        k = t2 * s2 / sxx
        A = b * b - k
        B = 2 * b * (a - y0) + 2 * k * xm
        C = (a - y0) ** 2 - t2 * s2 / n - k * xm * xm
    disc = B * B - 4 * A * C
    if A <= 0 or disc < 0:
        return (-math.inf, math.inf)
    r1, r2 = (-B - math.sqrt(disc)) / (2 * A), (-B + math.sqrt(disc)) / (2 * A)
    return (min(r1, r2), max(r1, r2))


def runs_test(residuals_in_x_order: np.ndarray) -> tuple[int, float]:
    """Wald-Wolfowitz runs test on the signs of the residuals (one-sided: too few runs)."""
    s = np.sign(residuals_in_x_order)
    s = s[s != 0]
    n1, n2 = int((s > 0).sum()), int((s < 0).sum())
    runs = 1 + int((s[1:] != s[:-1]).sum()) if len(s) else 0
    if n1 == 0 or n2 == 0:
        return runs, 1.0
    # exact probability of ≤ runs runs
    from math import comb
    total = comb(n1 + n2, n1)
    p = 0.0
    for r in range(2, runs + 1):
        if r % 2 == 0:
            k = r // 2
            p += 2 * comb(n1 - 1, k - 1) * comb(n2 - 1, k - 1)
        else:
            k = (r - 1) // 2
            p += comb(n1 - 1, k - 1) * comb(n2 - 1, k) + comb(n1 - 1, k) * comb(n2 - 1, k - 1)
    return runs, min(1.0, p / total)


def linearity_test(x: np.ndarray, y: np.ndarray, fit: dict) -> tuple[float, int, int, float] | None:
    """Replicates test: does the line deviate from the means more than replicates scatter?"""
    groups: dict[float, list[float]] = {}
    for a, b in zip(x, y):
        groups.setdefault(float(a), []).append(float(b))
    k = len(groups)
    pure = sum(((np.array(v) - np.mean(v)) ** 2).sum() for v in groups.values())
    df_pure = len(x) - k
    df_lack = k - (1 if fit["through"] is not None else 2)
    if df_pure <= 0 or df_lack <= 0 or pure <= 0:
        return None
    lack = fit["ss"] - pure
    F = (lack / df_lack) / (pure / df_pure)
    return F, df_lack, df_pure, float(sps.f.sf(F, df_lack, df_pure))


def compare_lines(fits: list[dict], data: list[tuple[np.ndarray, np.ndarray]]) -> dict:
    """Are the slopes equal (and, if so, the intercepts)? Analysis of covariance, as Prism."""
    k = len(fits)
    ss_sep = sum(f["ss"] for f in fits)
    df_sep = sum(f["df"] for f in fits)
    sxx = sum(f["sxx"] for f in fits)
    sxy = sum(((x - x.mean()) * (y - y.mean())).sum() for x, y in data)
    common = sxy / sxx
    ss_par = sum((((y - y.mean()) - common * (x - x.mean())) ** 2).sum() for x, y in data)
    df_par = df_sep + k - 1
    F1 = ((ss_par - ss_sep) / (k - 1)) / (ss_sep / df_sep)
    p1 = float(sps.f.sf(F1, k - 1, df_sep))
    out = {"slopes": (F1, k - 1, df_sep, p1), "common_slope": common}
    allx = np.concatenate([x for x, _ in data])
    ally = np.concatenate([y for _, y in data])
    ss_one = linfit(allx, ally)["ss"]
    df_one = len(allx) - 2
    F2 = ((ss_one - ss_par) / (k - 1)) / (ss_par / df_par)
    out["intercepts"] = (F2, k - 1, df_par, float(sps.f.sf(F2, k - 1, df_par)))
    return out


def linear_regression(an) -> AnalysisResult:
    t, cols, p = an.table, list(an.columns), an.params
    _need_xy(t)
    conf = p.get("conf", 0.95)
    through = (p.get("x0", 0.0), p.get("y0", 0.0)) if p.get("through") else None
    reps = p.get("replicates", "individual")
    labels = [t.label(c) for c in cols]
    letters = [column_letter(c) for c in cols]
    fits, data, errors = {}, {}, {}
    for c in cols:
        x, y = xy_points(t, c, reps)
        try:
            fits[c] = linfit(x, y, conf, through)
            data[c] = (x, y)
        except ValueError as e:
            errors[c] = str(e)
    if not fits:
        raise ValueError("Linear regression needs at least two points with different X values "
                         "(and three to estimate the scatter). " + "; ".join(errors.values()))
    heads = [f"{a}: {lab}" for a, lab in zip(letters, labels)]

    def row(name, f):
        return (name, [f(fits[c]) if c in fits else "" for c in cols], "row")
    ci = lambda lo_hi: f"{fmt(lo_hi[0])} to {fmt(lo_hi[1])}" if all(map(math.isfinite, lo_hi)) \
        else ("−∞ to +∞" if not any(map(math.isfinite, lo_hi)) else f"{fmt(lo_hi[0])} to {fmt(lo_hi[1])}")
    pct = f"{conf:.0%}"

    def data_x(f):
        c = next(k for k, v in fits.items() if v is f)
        return data[c][0]
    rows = [("Best-fit values", [], "section"),
            row("Slope", lambda f: fmt(f["slope"])),
            row("Y-intercept", lambda f: fmt(f["intercept"])),
            row("X-intercept", lambda f: fmt(f["x_intercept"])),
            row("1/slope", lambda f: fmt(1 / f["slope"]) if f["slope"] else ""),
            ("", [], "blank"), ("Standard errors", [], "section"),
            row("Slope", lambda f: fmt(f["se_slope"])),
            row("Y-intercept", lambda f: fmt(f["se_intercept"]) if through is None else ""),
            ("", [], "blank"), (f"{pct} confidence intervals", [], "section"),
            row("Slope", lambda f: ci(f["ci_slope"])),
            row("Y-intercept", lambda f: ci(f["ci_intercept"]) if through is None else ""),
            row("X-intercept", lambda f: ci(f["ci_x_intercept"])),
            ("", [], "blank"), ("Goodness of fit", [], "section"),
            row("R²", lambda f: f"{f['r2']:.4f}"),
            row("Sy.x", lambda f: fmt(f["syx"])),
            row("Sum of squares", lambda f: fmt(f["ss"])),
            ("", [], "blank"), ("Is the slope different from zero?", [], "section"),
            row("F", lambda f: f"{f['F']:.4g}"),
            row("DFn, DFd", lambda f: f"1, {f['df']}"),
            row("P value", lambda f: fmt_p(f["p"])),
            row("Deviation from zero?", lambda f: "Significant" if f["p"] < 0.05 else "Not significant"),
            ("", [], "blank"), ("Equation", [], "section"),
            row("", lambda f: f"Y = {fmt(f['slope'])}·X {'+' if f['intercept'] >= 0 else '−'} "
                              f"{fmt(abs(f['intercept']))}"),
            ("", [], "blank"), ("Data", [], "section"),
            row("Number of X values", lambda f: str(len(np.unique(data_x(f))))),
            row("Points analysed", lambda f: str(f["n"]))]

    if p.get("runs_test"):
        rows += [("", [], "blank"), ("Runs test", [], "section")]
        rt = {}
        for c, f in fits.items():
            x, y = data[c]
            o = np.argsort(x, kind="stable")
            rt[c] = runs_test((y - (f["intercept"] + f["slope"] * x))[o])
        rows.append(("Runs", [str(rt[c][0]) if c in rt else "" for c in cols], "row"))
        rows.append(("P value (too few runs)", [fmt_p(rt[c][1]) if c in rt else "" for c in cols], "row"))
    if p.get("linearity_test"):
        rows += [("", [], "blank"), ("Replicates test (departure from a line)", [], "section")]
        lt = {c: linearity_test(*data[c], f) for c, f in fits.items()}
        rows.append(("F", [f"{lt[c][0]:.4g}" if lt.get(c) else "n/a" for c in cols], "row"))
        rows.append(("P value", [fmt_p(lt[c][3]) if lt.get(c) else "" for c in cols], "row"))
    for c, e in errors.items():
        rows.append((f"{column_letter(c)}: not fitted", [e], "row"))
    res = AnalysisResult()
    first = next(iter(fits.values()))
    res.p = first["p"]
    res.fit = {"kind": "line", "fits": fits, "conf": conf}
    pages = [ResultPage("Results", heads, rows)]
    if p.get("compare") and len(fits) >= 2 and through is None:
        cmp_ = compare_lines([fits[c] for c in fits], [data[c] for c in fits])
        F1, d1, d2, p1 = cmp_["slopes"]
        F2, e1, e2, p2 = cmp_["intercepts"]
        crow = [("Are the slopes equal?", [], "section"),
                ("F (DFn, DFd)", [f"{F1:.4g} ({d1}, {d2})"], "row"), ("P value", [fmt_p(p1)], "row"),
                ("Conclusion", ["The slopes differ" if p1 < 0.05 else "The slopes are not significantly different"], "row")]
        if p1 >= 0.05:
            crow += [("", [], "blank"), ("Are the intercepts (elevations) equal?", [], "section"),
                     ("Pooled slope", [fmt(cmp_["common_slope"])], "row"),
                     ("F (DFn, DFd)", [f"{F2:.4g} ({e1}, {e2})"], "row"), ("P value", [fmt_p(p2)], "row"),
                     ("Conclusion", ["The intercepts differ" if p2 < 0.05 else
                                     "The intercepts are not significantly different"], "row")]
        else:
            crow.append(("Intercepts", ["Not compared: with different slopes the lines cross"], "row"))
        pages.append(ResultPage("Compare lines", ["Comparison"], crow))
    if p.get("interpolate"):
        pages.append(_interpolate_page(t, cols, fits, conf))
    if p.get("residual_plot"):
        res.out_table = residual_table(an.name, [(c, t.label(c), data[c][0],
                                                  data[c][1] - (fits[c]["intercept"] + fits[c]["slope"] * data[c][0]))
                                                 for c in fits])
    res.pages = pages
    return res


def residual_table(name: str, series: list) -> "object":
    """An XY table of residuals (X, and each data set's residuals as replicates of their X)."""
    from asterism.doc.model import Table
    xs = sorted({float(v) for _, _, x, _ in series for v in x})
    index = {v: i for i, v in enumerate(xs)}
    width = max([max([list(x).count(v) for v in set(x)], default=1) for _, _, x, _ in series] or [1])
    out = Table(name, "xy", "replicates" if width > 1 else "single", replicates=width, ncols=max(1, len(series)))
    for i, v in enumerate(xs):
        out.set(i, "x", v, emit=False)
    for j, (_, label, x, r) in enumerate(series):
        out.titles[j] = label
        used: dict[int, int] = {}
        for a, b in zip(x, r):
            i = index[float(a)]
            k = used.get(i, 0)
            used[i] = k + 1
            out.set(i, out.flat(j, k), float(b), emit=False)
    return out


def _interpolate_page(t, cols, fits, conf) -> ResultPage:
    """Unknowns: rows with Y but no X get X from the line; rows with X but no Y get Y."""
    rows = []
    for c in cols:
        f = fits.get(c)
        if f is None:
            continue
        for r in range(t.nrows_used()):
            xv = t.x_value(r)
            yv = t.row_values(r, c) if not t.is_summary() else np.array([])
            if t.get(r, "x") is None and len(yv) and f["slope"]:
                y0 = float(yv.mean())
                x_ = (y0 - f["intercept"]) / f["slope"]
                lo, hi = x_at_y_ci(f, y0)
                rows.append((f"{column_letter(c)}, row {r + 1}", ["Y → X", fmt(y0), fmt(x_),
                                                                 f"{fmt(lo)} to {fmt(hi)}"], "row"))
            elif xv is not None and not len(yv) and not _any_y(t, r) and t.get(r, "x") is not None and t.table_type == "xy":
                y_ = f["intercept"] + f["slope"] * xv
                lo, hi = band(f, np.array([xv]))
                rows.append((f"{column_letter(c)}, row {r + 1}", ["X → Y", fmt(xv), fmt(y_),
                                                                 f"{fmt(lo[0])} to {fmt(hi[0])}"], "row"))
    if not rows:
        rows = [("No unknowns", ["Rows with a Y value but no X (or an X but no Y) are interpolated."], "row")]
    pg = ResultPage("Interpolated", ["Direction", "From", "Interpolated", f"{conf:.0%} CI"], rows)
    pg.first_column = "Row"
    return pg


# ---------------------------------------------------------------------------
# Correlation
# ---------------------------------------------------------------------------

EXACT_SPEARMAN_MAX_N = 16


def spearman_exact_p(x: np.ndarray, y: np.ndarray) -> float | None:
    """Two-sided exact P of Spearman's r from the permutation distribution of the ranks,
    ties included (as Prism; golden-tested). None when n is too large to enumerate.

    Counts the n! assignments of y ranks to x positions by their sum of rank products: a
    dynamic programme over which y values are still unused (tied values grouped), one
    array of counts per state, layer by layer."""
    n = len(x)
    if n > EXACT_SPEARMAN_MAX_N or n < 3:
        return None
    rx, ry = sps.rankdata(x), sps.rankdata(y)
    scale = 1 if np.allclose(rx, np.round(rx)) and np.allclose(ry, np.round(ry)) else 2
    ax = np.rint(rx * scale).astype(np.int64)
    ay = np.rint(ry * scale).astype(np.int64)
    vals, counts = np.unique(ay, return_counts=True)
    width = int(np.dot(np.sort(ax), np.sort(ay))) + 1
    start = np.zeros(width)
    start[0] = 1.0
    layer = {tuple(int(c) for c in counts): start}
    for k in range(n):
        nxt: dict[tuple, np.ndarray] = {}
        a = int(ax[k])
        for st, arr in layer.items():
            for v, cnt in enumerate(st):
                if not cnt:
                    continue
                st2 = st[:v] + (cnt - 1,) + st[v + 1:]
                add = a * int(vals[v])
                tgt = nxt.get(st2)
                if tgt is None:
                    tgt = nxt[st2] = np.zeros(width)
                tgt[add:] += cnt * arr[:width - add]
        layer = nxt
    dist = next(iter(layer.values()))
    tot = dist.sum()
    obs = int((ax * ay).sum())
    e = ax.sum() * ay.sum() / n
    far = np.abs(np.arange(width) - e) >= abs(obs - e) - 1e-9
    return float(dist[far].sum() / tot)


def pearson(x, y, conf=0.95) -> dict:
    n = len(x)
    r = float(np.corrcoef(x, y)[0, 1])
    t_ = r * math.sqrt((n - 2) / (1 - r * r)) if abs(r) < 1 else math.inf
    p = float(2 * sps.t.sf(abs(t_), n - 2))
    z, zc = math.atanh(max(min(r, 0.9999999999), -0.9999999999)), float(sps.norm.ppf(1 - (1 - conf) / 2))
    se = 1 / math.sqrt(n - 3) if n > 3 else math.inf
    return {"n": n, "r": r, "r2": r * r, "p": p, "ci": (math.tanh(z - zc * se), math.tanh(z + zc * se)),
            "t": t_, "exact": None}


def spearman(x, y, conf=0.95) -> dict:
    n = len(x)
    rs = float(sps.spearmanr(x, y)[0])
    t_ = rs * math.sqrt((n - 2) / (1 - rs * rs)) if abs(rs) < 1 else math.inf
    p_approx = float(2 * sps.t.sf(abs(t_), n - 2)) if n > 2 else math.nan
    p_exact = spearman_exact_p(x, y)
    ci = None
    if n > 10:
        z, zc = math.atanh(max(min(rs, 0.9999999999), -0.9999999999)), float(sps.norm.ppf(1 - (1 - conf) / 2))
        se = math.sqrt(1.06 / (n - 3))
        ci = (math.tanh(z - zc * se), math.tanh(z + zc * se))
    return {"n": n, "r": rs, "r2": rs * rs, "p": p_exact if p_exact is not None else p_approx,
            "p_approx": p_approx, "exact": p_exact is not None, "ci": ci}


def correlation(an) -> AnalysisResult:
    t, cols, p = an.table, list(an.columns), an.params
    method = p.get("method", "pearson")
    conf = p.get("conf", 0.95)
    fn = spearman if method == "spearman" else pearson
    pairs = []                                  # (label, x, y, (ca, cb))
    if t.table_type == "xy":
        for c in cols:
            x, y = xy_points(t, c, "mean")
            pairs.append((f"X vs. {column_letter(c)}: {t.label(c)}", x, y, (None, c)))
    else:
        import itertools
        for a, b in itertools.combinations(cols, 2):
            xs, ys = [], []
            for r in range(t.nrows_used()):
                va, vb = t.row_values(r, a), t.row_values(r, b)
                if len(va) and len(vb):
                    xs.append(float(va.mean()))
                    ys.append(float(vb.mean()))
            pairs.append((f"{column_letter(a)} vs. {column_letter(b)}", np.array(xs), np.array(ys), (a, b)))
    out = []
    for lab, x, y, key in pairs:
        if len(x) < 3:
            out.append((lab, None, "needs at least three pairs of values"))
            continue
        out.append((lab, fn(x, y, conf), None))
    if all(o[1] is None for o in out):
        raise ValueError("Correlation needs at least three rows with both values.")
    name = "Spearman r" if method == "spearman" else "Pearson r"
    heads = [o[0] for o in out]
    get = lambda f: [f(o[1]) if o[1] else (o[2] or "") for o in out]
    rows = [("Correlation", [], "section"),
            (name, get(lambda d: f"{d['r']:.4f}"), "row"),
            (f"{conf:.0%} confidence interval", get(lambda d: f"{d['ci'][0]:.4f} to {d['ci'][1]:.4f}" if d["ci"]
                                                     else "Not reported (n ≤ 10)"), "row"),
            ("R²" if method == "pearson" else "r²", get(lambda d: f"{d['r2']:.4f}"), "row"),
            ("", [], "blank"), ("Is the correlation significant?", [], "section"),
            ("P value (two-sided)", get(lambda d: fmt_p(d["p"])), "row")]
    if method == "spearman":
        rows.append(("Exact or approximate?", get(lambda d: "Exact" if d["exact"] else "Approximate"), "row"))
    rows += [("Significance", get(lambda d: p_summary(d["p"])), "row"),
             ("Significant at α = 0.05", get(lambda d: "Yes" if d["p"] < 0.05 else "No"), "row"),
             ("", [], "blank"), ("Data", [], "section"),
             ("Number of XY pairs", get(lambda d: str(d["n"])), "row")]
    res = AnalysisResult()
    first = next(o[1] for o in out if o[1])
    res.p = first["p"]
    res.pages = [ResultPage("Results", heads, rows)]
    return res


# ---------------------------------------------------------------------------
# Area under the curve
# ---------------------------------------------------------------------------

def auc_one(rows: list[dict], baseline: float = 0.0, min_frac: float = 0.10, min_pts: int = 1,
            below: bool = False) -> dict:
    rows = sorted(rows, key=lambda r: r["x"])
    x = np.array([r["x"] for r in rows])
    y = np.array([r["mean"] for r in rows])
    if len(x) < 2:
        raise ValueError("needs at least two X values")
    h = y - baseline
    total = float(np.trapezoid(h, x))
    # SE of the total area from the SEMs (trapezoid weights), df = values − X values
    w = np.zeros(len(x))
    w[0] = (x[1] - x[0]) / 2
    w[-1] = (x[-1] - x[-2]) / 2
    w[1:-1] = (x[2:] - x[:-2]) / 2
    sems = [r.get("sem") for r in rows]
    se, df = None, None
    if all(s is not None for s in sems):
        se = float(math.sqrt(np.sum((w * np.array(sems)) ** 2)))
        ns = [r.get("n") or 0 for r in rows]
        df = int(sum(ns) - len(rows))
    # peaks: runs above (or below) the baseline, splitting at crossings
    thr = min_frac * (y.max() - y.min())
    peaks = []
    xi, hi = [x[0]], [h[0]]
    pts = []
    for i in range(len(x)):
        pts.append((x[i], h[i]))
    segs, cur = [], []
    for i in range(len(pts) - 1):
        (x0, h0), (x1, h1) = pts[i], pts[i + 1]
        if not cur:
            cur = [(x0, h0)]
        if (h0 > 0) != (h1 > 0) and h0 != 0 and h1 != 0:
            xc = x0 + (x1 - x0) * h0 / (h0 - h1)
            cur.append((xc, 0.0))
            segs.append(cur)
            cur = [(xc, 0.0)]
        cur.append((x1, h1))
    if cur:
        segs.append(cur)
    for seg in segs:
        sx = np.array([s[0] for s in seg])
        sh = np.array([s[1] for s in seg])
        sign = 1 if np.nanmax(sh) > 0 else -1
        if sign < 0 and not below:
            continue
        a = float(np.trapezoid(sh, sx))
        height = float(np.max(np.abs(sh)))
        npts = int(np.sum(np.isin(sx, x)))
        if height < thr or npts < min_pts:
            continue
        k = int(np.argmax(np.abs(sh)))
        peaks.append({"start": float(sx[0]), "end": float(sx[-1]), "peak_x": float(sx[k]),
                      "peak_y": float(sh[k] + baseline), "area": a})
    return {"total": total, "se": se, "df": df, "peaks": peaks, "n_x": len(x),
            "peak_total": float(sum(p_["area"] for p_ in peaks))}


def area_under_curve(an) -> AnalysisResult:
    t, cols, p = an.table, list(an.columns), an.params
    _need_xy(t)
    base = p.get("baseline", 0.0)
    conf = p.get("conf", 0.95)
    res_ = {}
    for c in cols:
        try:
            res_[c] = auc_one(xy_rows(t, c), base, p.get("min_peak_frac", 0.10), p.get("min_peak_points", 1),
                              p.get("below", False))
        except ValueError as e:
            res_[c] = str(e)
    if all(isinstance(v, str) for v in res_.values()):
        raise ValueError("Area under the curve needs at least two X values with Y values.")
    heads = [f"{column_letter(c)}: {t.label(c)}" for c in cols]
    def g(f):
        return [f(res_[c]) if isinstance(res_[c], dict) else res_[c] for c in cols]

    def ci(a):
        if a["se"] is None or not a["df"] or a["df"] <= 0:
            return ""
        tc = float(sps.t.ppf(1 - (1 - conf) / 2, a["df"]))
        return f"{fmt(a['total'] - tc * a['se'])} to {fmt(a['total'] + tc * a['se'])}"
    rows = [("Baseline", [fmt(base)] * len(cols), "row"),
            ("", [], "blank"), ("Total area", [], "section"),
            ("Area", g(lambda a: fmt(a["total"])), "row"),
            ("Standard error", g(lambda a: fmt(a["se"]) if a["se"] is not None else ""), "row"),
            (f"{conf:.0%} confidence interval", g(ci), "row"),
            ("", [], "blank"), ("Peaks", [], "section"),
            ("Number of peaks", g(lambda a: str(len(a["peaks"]))), "row"),
            ("Total peak area", g(lambda a: fmt(a["peak_total"])), "row")]
    res = AnalysisResult()
    pages = [ResultPage("Results", heads, rows)]
    prow = []
    for c in cols:
        a = res_[c]
        if not isinstance(a, dict):
            continue
        for i, pk in enumerate(a["peaks"]):
            prow.append((f"{column_letter(c)}, peak {i + 1}",
                         [fmt(pk["start"]), fmt(pk["end"]), fmt(pk["peak_x"]), fmt(pk["peak_y"]), fmt(pk["area"]),
                          f"{100 * pk['area'] / a['peak_total']:.1f}" if a["peak_total"] else ""], "row"))
    if prow:
        pg = ResultPage("Peaks", ["First X", "Last X", "Peak X", "Peak Y", "Area", "% of peak area"], prow)
        pg.first_column = "Peak"
        pages.append(pg)
    res.pages = pages
    return res


def _any_y(t, r: int) -> bool:
    """Whether any data set has a Y value in this row (then an empty cell isn't an unknown X)."""
    if t.is_summary():
        return any(t.summary(r, c) for c in t.used_columns())
    return any(len(t.row_values(r, c)) for c in t.used_columns())
