"""XY graphs: numeric X axis, points / connecting lines / area fills / XY bars, mean with
error or every replicate (or each replicate connected), fitted lines and curves from
linked regressions with confidence or prediction bands, legend.

Same element contract as layout.py: each element draws itself on any canvas.
"""

from __future__ import annotations

import math

import numpy as np
from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainterPath

from ...doc.model import column_letter
from .canvas import MM, TextMetrics as TM
from .layout import (ORDER, TICK_LEN, AxisRange, Element, Plan, YMap, _frame, _guides, _legend, _rect_path,
                     _text_rect, _title, _y_axis, _y_title, draw_symbol, nice_range, summarize,
                     summarize_entered)


class XMap(YMap):
    """Like YMap, but left to right."""

    def __call__(self, v: float) -> float:
        return self.h - super().__call__(v)


def x_range(spec, xs: list[float]) -> AxisRange:
    ax = spec.x
    if not ax.auto:
        if ax.scale == "log10":
            return AxisRange(max(ax.vmin, 1e-12), max(ax.vmax, ax.vmin * 10), ax.interval)
        return AxisRange(ax.vmin, ax.vmax, ax.interval if ax.interval > 0 else 1)
    vals = [v for v in xs if v is not None and math.isfinite(v)]
    if not vals:
        return AxisRange(0.0, 10.0, 2.0)
    if ax.scale == "log10":
        pos = [v for v in vals if v > 0] or [1.0]
        return AxisRange(10.0 ** math.floor(math.log10(min(pos))),
                         10.0 ** math.ceil(math.log10(max(pos)) + 1e-9), 1)
    lo, hi = min(vals), max(vals)
    if lo > 0 and lo < hi * 0.5:
        lo = 0.0
    if hi < 0 and hi > lo * 0.5:
        hi = 0.0
    return nice_range(lo, hi)


def series(t, c: int, st) -> list[dict]:
    """Per row: x, center, lo, hi (error), reps [(sub-column, value)], xerr."""
    out = []
    for r in range(t.nrows_used()):
        x = t.x_value(r)
        if x is None:
            continue
        xe = t.get(r, "xerr") if t.x_format == "numbers_err" else None
        if t.is_summary():
            s = summarize_entered(t.summary(r, c), st)
            if s["center"] is None:
                continue
            out.append({"x": x, "center": s["center"], "lo": s["lo"], "hi": s["hi"], "reps": [],
                        "xerr": xe, "row": r})
            continue
        reps = [(k, v) for k in range(t.width()) if (v := t._ok(r, t.flat(c, k))) is not None]
        if not reps:
            continue
        v = np.array([b for _, b in reps])
        s = summarize(v, st)
        center = s["center"] if s["center"] is not None else float(v.mean())
        out.append({"x": x, "center": center, "lo": s["lo"], "hi": s["hi"], "reps": reps, "xerr": xe, "row": r})
    return out


def _curves(graph, cols: list[int], data: dict) -> list[dict]:
    """Fitted lines and curves from linked regressions: [{column, kind, fn, band, xs}]."""
    out = []
    for a in graph.analyses():
        r = a.result
        if r is None or r.error or not getattr(r, "fit", None) or not isinstance(r.fit, dict):
            continue
        kind = r.fit.get("kind")
        if kind not in ("line", "curve") or not a.params.get("graph", True):
            continue
        bands = a.params.get("bands", "none")
        conf = r.fit.get("conf", 0.95)
        if kind == "line":
            from ...analysis.xy import band
            for c, f in r.fit["fits"].items():
                if c not in cols:
                    continue
                fn = (lambda f: (lambda x: f["intercept"] + f["slope"] * np.asarray(x)))(f)
                bfn = None
                if bands != "none":
                    bfn = (lambda f, pred: (lambda x: band(f, np.asarray(x), pred)))(f, bands == "prediction")
                out.append({"column": c, "fn": fn, "band": bfn, "range": (f["x_min"], f["x_max"])})
        else:
            for c, (f, j) in r.fit["curves"].items():
                if c not in cols:
                    continue
                xs = [row["x"] for row in data.get(c, [])]
                if not xs:
                    continue
                fn = (lambda f, j: (lambda x: f.predict(j, np.asarray(x))))(f, j)
                bfn = None
                if bands != "none":
                    bfn = (lambda f, j, pred: (lambda x: f.band(j, np.asarray(x), pred, conf)))(
                        f, j, bands == "prediction")
                lo, hi = a.params.get("curve_from"), a.params.get("curve_to")
                out.append({"column": c, "fn": fn, "band": bfn,
                            "range": (lo if lo is not None else min(xs), hi if hi is not None else max(xs))})
    return out


def build_xy(graph) -> tuple[list[Element], AxisRange]:
    spec, t = graph.spec, graph.table
    cols = [c for c in t.used_columns() if c not in spec.hidden]
    pw, ph = spec.x_len_mm * MM, spec.y_len_mm * MM
    aw, ac = spec.axis_width, spec.axis_color
    off = 6.0 if spec.frame == "offset" else 0.0
    yx, xy = -off, ph + off
    data = {c: series(t, c, spec.style(c)) for c in cols}
    curves = _curves(graph, cols, data)
    xlog = spec.x.scale == "log10"

    def grid(lo, hi, n=240):
        if xlog and lo > 0 and hi > 0:
            return np.logspace(math.log10(lo), math.log10(hi), n)
        return np.linspace(lo, hi, n)

    # ranges
    xs_all = [row["x"] for c in cols for row in data[c]]
    xs_all += [row["x"] - (row["xerr"] or 0) for c in cols for row in data[c] if row["xerr"]]
    xs_all += [row["x"] + (row["xerr"] or 0) for c in cols for row in data[c] if row["xerr"]]
    xr = x_range(spec, xs_all)
    xm = XMap(spec.x, xr, pw)
    right = {c for c in cols if spec.style(c).axis == "right"}
    summaries, summaries2 = {}, {}
    k = 0
    for c in cols:
        for row in data[c]:
            vals = [row["center"]] + [v for _, v in row["reps"]]
            (summaries2 if c in right else summaries)[k] = {"min": min(vals), "max": max(vals),
                                                            "lo": row["lo"], "hi": row["hi"]}
            k += 1
    for cv_ in curves:
        g = grid(*cv_["range"], 60)
        y = cv_["fn"](g)
        ys = [float(v) for v in y if math.isfinite(v)]
        if cv_["band"] is not None:
            lo_b, hi_b = cv_["band"](g)
            ys += [float(v) for v in np.concatenate([lo_b, hi_b]) if math.isfinite(v)]
        if ys:
            (summaries2 if cv_["column"] in right else summaries)[k] = {"min": min(ys), "max": max(ys),
                                                                        "lo": None, "hi": None}
            k += 1
    from .layout import y_range
    rng = y_range(graph, summaries)
    ym = YMap(spec.y, rng, ph)
    ym2 = rng2 = None
    if right:
        rng2 = y_range(graph, summaries2, spec.y2)
        ym2 = YMap(spec.y2, rng2, ph)
    elements: list[Element] = []
    elements += _guides(spec, ym, pw, ph, ym2, xm)
    base_v0 = max(rng.vmin, 0.0) if spec.y.scale != "log10" else rng.vmin

    # XY bars: width from the bin width, else most of the smallest X spacing
    uniq = sorted({row["x"] for c in cols for row in data[c]})
    bin_w = getattr(t, "bin_width", None)
    if not bin_w:
        gaps = np.diff(uniq) if len(uniq) > 1 else np.array([abs(xr.vmax - xr.vmin) / 10 or 1.0])
        bin_w = float(np.min(gaps)) if len(gaps) else 1.0
    bar_cols = [c for c in cols if spec.style(c).appearance == "bar"]
    nb = max(len(bar_cols), 1)

    tops = []
    ym_left, rng_left = ym, rng
    for c in cols:
        ym, rng_c = (ym2, rng2) if c in right else (ym_left, rng_left)
        base_v = base_v0 if c not in right else (max(rng2.vmin, 0.0) if spec.y2.scale != "log10" else rng2.vmin)
        st = spec.style(c)
        xmc = (lambda f, n: (lambda v: f(v) + n))(xm, st.nudge)
        ymc = (lambda f, n: (lambda v: f(v) - n))(ym, st.nudge_y)
        rows = sorted(data[c], key=lambda r: r["x"])
        if not rows:
            continue
        d = max(1.0, st.symbol_size * 2.0)
        col = st.symbol_color
        dash = None if st.line_dash == "solid" else st.line_dash
        is_bar = st.appearance == "bar"
        bi = bar_cols.index(c) if c in bar_cols else 0
        hit_rects = []
        pts_mean = [(xmc(r_["x"]), ymc(r_["center"])) for r_ in rows]
        from ...doc.spec import SUBJECT_COLORS
        row_cols = [SUBJECT_COLORS[r_["row"] % len(SUBJECT_COLORS)] if st.by_row else None for r_ in rows]
        rep_cols = [SUBJECT_COLORS[r_["row"] % len(SUBJECT_COLORS)] if st.by_row else None
                    for r_ in rows for _ in r_["reps"]]
        fs_lab = spec.fonts["legend"]
        labels = [(x_, y_, t.row_label(r_["row"])) for r_, (x_, y_) in zip(rows, pts_mean)] if st.row_labels else []
        for x_, y_, lab in labels:
            hit_rects.append(_text_rect(x_ + d / 2 + 2, y_ + TM.cap_height(fs_lab) / 2, lab, fs_lab, "start"))
        runs = [pts_mean]
        if st.gaps and len(rows) > 1:          # break the line where a value is missing
            present = {r_["row"] for r_ in rows}
            missing = sorted(xv for r in range(t.nrows_used()) if r not in present
                             and (xv := t.x_value(r)) is not None)
            runs, cur = [], [pts_mean[0]]
            for (a_, pa), (b_, pb) in zip(zip(rows, pts_mean), zip(rows[1:], pts_mean[1:])):
                if any(a_["x"] < m < b_["x"] for m in missing):
                    runs.append(cur)
                    cur = []
                cur.append(pb)
            runs.append(cur)
        for x_, y_ in pts_mean:
            hit_rects.append(QRectF(x_ - d, y_ - d, 2 * d, 2 * d))
        rep_pts = [(xmc(r_["x"]), ymc(v), k_) for r_ in rows for k_, v in r_["reps"]]
        show_reps = st.xy_show in ("replicates", "spaghetti") and rep_pts
        if show_reps:
            hit_rects += [QRectF(x_ - d, y_ - d, 2 * d, 2 * d) for x_, y_, _ in rep_pts]
        bars = []
        if is_bar:
            full = abs(xmc(uniq[0] + bin_w) - xmc(uniq[0])) if uniq else 10.0
            w_each = full * (0.98 if getattr(t, "bin_width", None) else 0.8) / nb
            for r_ in rows:
                x0 = xmc(r_["x"]) - full * (0.98 if getattr(t, "bin_width", None) else 0.8) / 2 + bi * w_each
                yb, y0 = ymc(r_["center"]), ymc(base_v)
                bars.append((x0, min(yb, y0), w_each, abs(y0 - yb)))
                hit_rects.append(QRectF(x0, min(yb, y0), w_each, abs(y0 - yb)))
        top = min([y for _, y in pts_mean] + [y for _, y, _ in rep_pts]) - d
        for r_ in rows:
            if st.errors and r_["hi"] is not None and st.xy_show == "mean":
                top = min(top, ymc(r_["hi"]))
        tops.append(top)

        def draw_ds(cv, st=st, rows=rows, pts_mean=pts_mean, rep_pts=rep_pts, show_reps=show_reps, d=d,
                    col=col, dash=dash, bars=bars, is_bar=is_bar, ymc=ymc, xmc=xmc, base_v=base_v, runs=runs,
                    row_cols=row_cols, rep_cols=rep_cols, labels=labels, fs_lab=fs_lab):
            if st.fill and len(pts_mean) > 1:
                y0 = ymc(base_v)
                poly = [(pts_mean[0][0], y0)] + pts_mean + [(pts_mean[-1][0], y0)]
                cv.polygon(poly, fill=st.bar_fill if st.bar_fill != "#b4b4b4" else col, opacity=st.fill_alpha)
            for x0, y0, w, h in bars:
                if h < 0.01:
                    continue                    # empty bin: nothing to draw
                cv.rect(x0, y0, w, h, fill=st.bar_fill,
                        stroke=st.bar_border_color if st.bar_border > 0 else None, width=st.bar_border)
            if st.xy_show == "mean" and st.errors:
                cap = max(d * 0.75, 2.5)
                for r_ in rows:
                    xc = xmc(r_["x"])
                    yc = ymc(r_["center"])
                    ends = []
                    if r_["hi"] is not None and st.error_dir in ("both", "above") and r_["hi"] != r_["center"]:
                        ends.append(ymc(r_["hi"]))
                    if (r_["lo"] is not None and st.error_dir in ("both", "below") and not is_bar
                            and r_["lo"] != r_["center"]):
                        ends.append(ymc(r_["lo"]))
                    for ye in ends:
                        cv.line(xc, yc, xc, ye, st.error_color, st.error_width, "butt")
                        if st.error_style == "T":
                            cv.line(xc - cap, ye, xc + cap, ye, st.error_color, st.error_width, "butt")
                    if r_["xerr"]:
                        xl, xh = xmc(r_["x"] - r_["xerr"]), xmc(r_["x"] + r_["xerr"])
                        cv.line(xl, yc, xh, yc, st.error_color, st.error_width, "butt")
                        if st.error_style == "T":
                            cv.line(xl, yc - cap, xl, yc + cap, st.error_color, st.error_width, "butt")
                            cv.line(xh, yc - cap, xh, yc + cap, st.error_color, st.error_width, "butt")
            if st.xy_show == "spaghetti":
                for k_ in sorted({k for _, _, k in rep_pts}):
                    line = [(x_, y_) for x_, y_, kk in rep_pts if kk == k_]
                    if len(line) > 1:
                        cv.polyline(line, col, st.line_width, "round", dash)
            elif st.connect and len(pts_mean) > 1 and not is_bar:
                for run in runs:
                    if len(run) > 1:
                        cv.polyline(run, col, st.line_width, "round", dash)
            if st.show_points and not is_bar:
                if show_reps:
                    for (x_, y_, _), rc in zip(rep_pts, rep_cols):
                        draw_symbol(cv, st.symbol_shape, x_, y_, d, rc or col)
                else:
                    for (x_, y_), rc in zip(pts_mean, row_cols):
                        draw_symbol(cv, st.symbol_shape, x_, y_, d, rc or col)
            for x_, y_, lab in labels:
                cv.text(x_ + d / 2 + 2, y_ + TM.cap_height(fs_lab) / 2, lab, fs_lab, anchor="start")
        hit = _rect_path(*hit_rects) if hit_rects else QPainterPath()
        elements.append(Element(f"data-{column_letter(c)}", "dataset", hit.boundingRect().adjusted(-2, -2, 2, 2),
                                draw_ds, hit, {"column": c, "label": t.label(c)}))

    # fitted lines and curves (a second curve on the same data set gets -1, -2 …)
    seen: dict[int, int] = {}
    for cv_ in curves:
        c = cv_["column"]
        ym, rng = (ym2, rng2) if c in right else (ym_left, rng_left)
        i = seen.get(c, 0)
        seen[c] = i + 1
        st = spec.style(c)
        g = grid(*cv_["range"])
        y = np.asarray(cv_["fn"](g), float)
        ok = np.isfinite(y) & (y >= rng.vmin - (rng.vmax - rng.vmin) * 2) & (y <= rng.vmax + (rng.vmax - rng.vmin) * 2)
        nx, ny = st.nudge, st.nudge_y
        pts = [(xm(a) + nx, ym(b) - ny) for a, b in zip(g[ok], y[ok])]
        band_pts = None
        if cv_["band"] is not None:
            lo_b, hi_b = cv_["band"](g)
            band_pts = ([(xm(a) + nx, ym(b) - ny) for a, b in zip(g, lo_b) if math.isfinite(b)],
                        [(xm(a) + nx, ym(b) - ny) for a, b in zip(g, hi_b) if math.isfinite(b)])

        def draw_curve(cv, pts=pts, band_pts=band_pts, st=st):
            if band_pts:
                for line in band_pts:
                    if len(line) > 1:
                        cv.polyline(line, st.symbol_color, max(st.line_width * 0.75, 0.5), "butt", "dash")
            if len(pts) > 1:
                cv.polyline(pts, st.symbol_color, st.line_width, "round",
                            None if st.line_dash == "solid" else st.line_dash)
        box = QRectF()
        for x_, y_ in pts:
            box = box.united(QRectF(x_ - 1.5, y_ - 1.5, 3, 3))
        path = QPainterPath()
        if len(pts) > 1:
            path.moveTo(*pts[0])
            for p_ in pts[1:]:
                path.lineTo(*p_)
            from PySide6.QtGui import QPainterPathStroker
            s_ = QPainterPathStroker()
            s_.setWidth(6.0)
            path = s_.createStroke(path)
        elements.append(Element(f"fit-{column_letter(c)}" + (f"-{i}" if i else ""), "curve", box, draw_curve,
                                path, {"column": c}))

    # functions typed by the user ("Plot a function"), over the X axis range unless limited
    for i, fn in enumerate(spec.functions):
        from ...analysis.function import evaluate
        lo = fn.get("from") if fn.get("from") is not None else xr.vmin
        hi = fn.get("to") if fn.get("to") is not None else xr.vmax
        try:
            g = grid(float(lo), float(hi), 400)
            yv = evaluate(fn.get("text", ""), fn.get("params") or {}, g)
        except (ValueError, SyntaxError, TypeError, ZeroDivisionError):
            continue
        span = rng_left.vmax - rng_left.vmin
        runs, cur = [], []
        for a_, b_ in zip(g, yv):              # break where the function leaves the plot or is undefined
            if math.isfinite(b_) and rng_left.vmin - span * 0.05 <= b_ <= rng_left.vmax + span * 0.05:
                cur.append((xm(a_), ym_left(min(max(b_, rng_left.vmin), rng_left.vmax))))
            elif cur:
                runs.append(cur)
                cur = []
        if cur:
            runs.append(cur)
        col, lw = fn.get("color") or "#000000", float(fn.get("width", 1.0))
        dash = None if fn.get("dash", "solid") == "solid" else fn.get("dash")

        def draw_fn(cv, runs=runs, col=col, lw=lw, dash=dash):
            for run in runs:
                if len(run) > 1:
                    cv.polyline(run, col, lw, "round", dash)
        box, path = QRectF(), QPainterPath()
        for run in runs:
            for x_, y_ in run:
                box = box.united(QRectF(x_ - 1.5, y_ - 1.5, 3, 3))
            if len(run) > 1:
                path.moveTo(*run[0])
                for p_ in run[1:]:
                    path.lineTo(*p_)
        from PySide6.QtGui import QPainterPathStroker
        st_ = QPainterPathStroker()
        st_.setWidth(6.0)
        elements.append(Element(f"function-{i + 1}", "curve", box, draw_fn, st_.createStroke(path),
                                {"function": fn.get("id"), "column": None}))

    # axes
    ym, rng = ym_left, rng_left
    y_el, num_left = _y_axis(spec, ym, ph, yx)
    elements.append(y_el)
    elements.append(_x_axis_numeric(spec, xm, pw, xy, yx))
    legend_x = pw + 12.0
    if ym2 is not None:
        y2_el, num_right = _y_axis(spec, ym2, ph, pw + off, "right")
        elements.append(y2_el)
        t2 = _y_title(spec, num_right, ph, "right")
        elements += t2
        legend_x = (max(e.bounds.right() for e in t2) if t2 else num_right) + 12.0
    if spec.frame == "box":
        elements.append(_frame(spec, pw, ph, ym, right_axis=ym2 is not None))
    elements += _y_title(spec, num_left, ph)
    xt = _x_title(spec, pw, elements[-1] if False else None, xy)
    if xt:
        elements.append(xt)
    if spec.show_legend and len(cols) > 1:
        sw = "bar" if all(spec.style(c).appearance == "bar" for c in cols) else (
            "line" if any(spec.style(c).connect for c in cols) or curves else "auto")
        elements.append(_legend(spec, t, Plan([], pw, [], legend=list(cols), swatch=sw), legend_x, 0.0))
    content_top = min(tops + [0.0] + [e.bounds.top() for e in elements if e.id == "y-title"])
    elements += _title(spec, graph, pw, content_top)
    elements.sort(key=lambda e: ORDER[e.kind])
    return elements, rng


def _x_axis_numeric(spec, xm: XMap, pw: float, xy: float, yx: float) -> Element:
    ax, aw, ac = spec.x, spec.axis_width, spec.axis_color
    tl = TICK_LEN[ax.ticks_len]
    down = tl if ax.ticks_dir in ("out", "cross") else 0.0
    up = tl if ax.ticks_dir in ("in", "cross") else 0.0
    fs = spec.fonts["x_labels"]
    majors = xm.majors()
    labels = [xm.label(v) for v in majors]
    lab_y = xy + down + 3.0 + TM.ascent(fs)
    x_start = yx if spec.frame != "offset" else 0.0
    ys = xy

    def draw_x(cv):
        cv.line(x_start, ys, pw, ys, ac, aw)
        if ax.ticks_dir != "none":
            for v in majors:
                x = xm(v)
                cv.line(x, ys - up, x, ys + down, ac, aw)
            for v in xm.minors():
                x = xm(v)
                cv.line(x, ys - up * 0.55, x, ys + down * 0.55, ac, aw)
        if ax.numbering:
            for v, s in zip(majors, labels):
                cv.text(xm(v), lab_y, s, fs, anchor="middle")
    xb = QRectF(x_start - 2, ys - up - 3, pw - x_start + 4, down + up + 6)
    if ax.numbering:
        for v, s in zip(majors, labels):
            xb = xb.united(_text_rect(xm(v), lab_y, s, fs, "middle"))
    return Element("x-axis", "x-axis", xb, draw_x, _rect_path(xb), {"font_keys": ["x_labels"], "bottom": xb.bottom()})


def _x_title(spec, pw: float, _unused, xy: float) -> Element | None:
    ax = spec.x
    if not ax.title:
        return None
    fs_l, fs_t = spec.fonts["x_labels"], spec.fonts["y_title"]
    tl = TICK_LEN[ax.ticks_len] if ax.ticks_dir in ("out", "cross") else 0.0
    dx, dy = spec.offsets.get("x-title", (0.0, 0.0))
    tx = pw / 2 + dx
    ty = xy + tl + 3.0 + TM.ascent(fs_l) + TM.descent(fs_l) + 6.0 + TM.ascent(fs_t) + dy

    def draw(cv, tx=tx, ty=ty):
        cv.text(tx, ty, ax.title, fs_t, anchor="middle")
    r = _text_rect(tx, ty, ax.title, fs_t, "middle")
    return Element("x-title", "text", r, draw, _rect_path(r),
                   {"font_keys": ["y_title"], "field": "x_title", "text": ax.title, "rotate": 0,
                    "anchor_pt": (tx, ty)})
