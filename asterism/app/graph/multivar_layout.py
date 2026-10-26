"""Graphs of multiple-variable tables: one variable against others, with symbol size
(bubble plot) and colour optionally showing two more variables, and points labelled with
their row titles. Same element contract as layout.py."""

from __future__ import annotations

import math

from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainterPath

from ...doc.model import column_letter
from ...doc.spec import PALETTE
from .canvas import TextMetrics as TM, MM
from .layout import (ORDER, AxisRange, Element, YMap, _frame, _guides, _mix_hex, _rect_path, _text_rect,
                     _title, _y_axis, _y_title, draw_symbol, y_range)
from .xy_layout import XMap, _x_axis_numeric, _x_title, x_range


def numeric_columns(t) -> list[int]:
    out = []
    for c in t.used_columns():
        vals = [t.get(r, t.flat(c)) for r in range(t.nrows_used())]
        if any(isinstance(v, (int, float)) and not isinstance(v, bool) for v in vals):
            out.append(c)
    return out


def roles(spec, t) -> dict:
    """The variables in use: x, ys, size, color (automatic choices filled in)."""
    nums = numeric_columns(t)
    used = t.used_columns()
    mv = spec.mv
    x = mv.get("x") if mv.get("x") in nums else (nums[0] if nums else None)
    ys = [c for c in (mv.get("y") or []) if c in nums and c != x]
    if not ys:
        ys = [c for c in nums if c != x][:1]
    taken = {x, *ys}
    if mv.get("size") == "auto":               # the next numeric variable not plotted yet
        size = next((c for c in nums if c not in taken), None)
    else:
        size = mv.get("size") if mv.get("size") in nums else None
    if mv.get("color") == "auto":              # a text variable (groups), else the next numeric one
        color = next((c for c in used if c not in nums), None)
        if color is None:
            color = next((c for c in nums if c not in taken and c != size), None)
    else:
        color = mv.get("color") if mv.get("color") in used else None
    return {"x": x, "ys": ys, "size": size, "color": color, "numeric": nums}


def _num(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) else None


def build_multivar(graph) -> tuple[list[Element], AxisRange]:
    import copy
    spec, t = copy.copy(graph.spec), graph.table        # shallow: axis titles default to variable names
    ro = roles(spec, t)
    spec.x, spec.y = copy.copy(spec.x), copy.copy(spec.y)
    if not spec.x.title and ro["x"] is not None:
        spec.x.title = t.label(ro["x"])
    if not spec.y.title and len(ro["ys"]) == 1:
        spec.y.title = t.label(ro["ys"][0])
    pw, ph = spec.x_len_mm * MM, spec.y_len_mm * MM
    off = 6.0 if spec.frame == "offset" else 0.0
    yx, xy = -off, ph + off
    n = t.nrows_used()
    xc, ys = ro["x"], [c for c in ro["ys"] if c not in spec.hidden]
    cell = lambda r, c: t.get(r, t.flat(c)) if c is not None else None
    pts = {c: [(r, _num(cell(r, xc)), _num(cell(r, c))) for r in range(n)] for c in ys}
    pts = {c: [(r, a, b) for r, a, b in v if a is not None and b is not None] for c, v in pts.items()}

    # size and colour scales
    sz = None
    if ro["size"] is not None:
        sv = [v for r in range(n) if (v := _num(cell(r, ro["size"]))) is not None]
        if sv:
            sz = (min(sv), max(sv))
    smin, smax = float(spec.mv.get("size_min", 4.0)), float(spec.mv.get("size_max", 22.0))

    def diameter(r, st):
        if sz is None:
            return max(1.0, st.symbol_size * 2.0)
        v = _num(cell(r, ro["size"]))
        if v is None:
            return smin
        lo, hi = sz
        f = (v - lo) / (hi - lo) if hi > lo else 1.0
        return math.sqrt(smin ** 2 + f * (smax ** 2 - smin ** 2))      # area grows with the value

    cats, cnum = [], None
    if ro["color"] is not None:
        raw = [cell(r, ro["color"]) for r in range(n)]
        nums = [v for v in raw if _num(v) is not None]
        if ro["color"] in ro["numeric"] and len(nums) == len([v for v in raw if v is not None]):
            cnum = (min(nums), max(nums)) if nums else None
        else:
            cats = sorted({str(v) for v in raw if v is not None and v != ""})

    def colour(r, st):
        if ro["color"] is None:
            return st.symbol_color
        v = cell(r, ro["color"])
        if cnum is not None and _num(v) is not None:
            lo, hi = cnum
            return _mix_hex(spec.heat_low, spec.heat_high, (_num(v) - lo) / (hi - lo) if hi > lo else 1.0)
        if cats and v not in (None, ""):
            return PALETTE[(cats.index(str(v)) + 1) % len(PALETTE)][1]
        return "#999999"

    xr = x_range(spec, [a for v in pts.values() for _, a, _ in v])
    xm = XMap(spec.x, xr, pw)
    summ = {i: {"min": b, "max": b, "lo": None, "hi": None} for i, (_, _, b) in
            enumerate(p_ for v in pts.values() for p_ in v)}
    rng = y_range(graph, summ)
    ym = YMap(spec.y, rng, ph)
    elements: list[Element] = []
    elements += _guides(spec, ym, pw, ph, None, xm)
    fs_lab = spec.fonts["legend"]
    for c in ys:
        st = spec.style(c)
        marks = [(xm(a), ym(b), diameter(r, st), colour(r, st), t.row_label(r) if spec.mv.get("labels") else "")
                 for r, a, b in pts[c]]
        bubble = sz is not None

        def draw(cv, marks=marks, st=st, bubble=bubble):
            for x_, y_, d, col, lab in sorted(marks, key=lambda m: -m[2]):     # big ones underneath
                if bubble:
                    cv.polygon(_circle(x_, y_, d / 2), fill=col, stroke="#333333", width=0.5, opacity=0.75)
                else:
                    draw_symbol(cv, st.symbol_shape, x_, y_, d, col)
                if lab:
                    cv.text(x_ + d / 2 + 2, y_ + TM.cap_height(fs_lab) / 2, lab, fs_lab, anchor="start")
        rects = [QRectF(x_ - d / 2, y_ - d / 2, d, d) for x_, y_, d, _, _ in marks]
        for x_, y_, d, _, lab in marks:
            if lab:
                rects.append(_text_rect(x_ + d / 2 + 2, y_ + TM.cap_height(fs_lab) / 2, lab, fs_lab, "start"))
        hit = _rect_path(*rects) if rects else QPainterPath()
        elements.append(Element(f"data-{column_letter(c)}", "dataset", hit.boundingRect().adjusted(-2, -2, 2, 2),
                                draw, hit, {"column": c, "label": t.label(c)}))

    y_el, num_left = _y_axis(spec, ym, ph, yx)
    elements.append(y_el)
    elements.append(_x_axis_numeric(spec, xm, pw, xy, yx))
    if spec.frame == "box":
        elements.append(_frame(spec, pw, ph, ym))
    elements += _y_title(spec, num_left, ph)
    xt = _x_title(spec, pw, None, xy)
    if xt:
        elements.append(xt)

    # legends: data sets (if several), colour, size
    if spec.show_legend:
        entries = []
        if len(ys) > 1:
            entries += [("sym", spec.style(c).symbol_shape, spec.style(c).symbol_color, t.label(c)) for c in ys]
        if cats:
            entries.append(("head", None, None, t.label(ro["color"])))
            entries += [("dot", "circle", PALETTE[(i + 1) % len(PALETTE)][1], s) for i, s in enumerate(cats)]
        elif cnum is not None:
            entries.append(("head", None, None, t.label(ro["color"])))
            entries.append(("grad", None, None, f"{cnum[0]:g} – {cnum[1]:g}"))
        if sz is not None:
            entries.append(("head", None, None, t.label(ro["size"])))
            for v in (sz[0], (sz[0] + sz[1]) / 2, sz[1]):
                f = (v - sz[0]) / (sz[1] - sz[0]) if sz[1] > sz[0] else 1.0
                entries.append(("size", math.sqrt(smin ** 2 + f * (smax ** 2 - smin ** 2)), None, f"{v:g}"))
        if entries:
            right = max([pw] + [e.bounds.right() for e in elements if e.kind == "dataset"])
            elements.append(_mv_legend(spec, entries, right + 12.0))
    content_top = min([0.0] + [e.bounds.top() for e in elements if e.id == "y-title"])
    elements += _title(spec, graph, pw, content_top)
    elements.sort(key=lambda e: ORDER[e.kind])
    return elements, rng


def _circle(x, y, r, n=28):
    return [(x + r * math.cos(2 * math.pi * i / n), y + r * math.sin(2 * math.pi * i / n)) for i in range(n)]


def _mv_legend(spec, entries, x0) -> Element:
    fs = spec.fonts["legend"]
    dx, dy = spec.offsets.get("legend", (0.0, 0.0))
    x0, y = x0 + dx, dy
    rows = []
    for kind, a, col, text in entries:
        h = max(TM.ascent(fs) + TM.descent(fs), 9.0) + 4.0
        if kind == "size":
            h = max(h, a + 4.0)
        rows.append((kind, a, col, text, y, h))
        y += h
    sw = max([a for k, a, *_ in entries if k == "size"] + [12.0])
    width = sw + 6.0 + max(TM.width(e[3], fs) for e in entries)

    def draw(cv):
        for kind, a, col, text, y0, h in rows:
            yc = y0 + h / 2
            if kind == "head":
                bold = type(fs)(**{**fs.__dict__, "bold": True})
                cv.text(x0, yc + TM.cap_height(fs) / 2, text, bold, anchor="start")
                continue
            if kind == "sym":
                draw_symbol(cv, a, x0 + sw / 2, yc, 6.0, col)
            elif kind == "dot":
                draw_symbol(cv, "circle", x0 + sw / 2, yc, 7.0, col)
            elif kind == "size":
                cv.polygon(_circle(x0 + sw / 2, yc, a / 2), fill="#bbbbbb", stroke="#333333", width=0.5)
            elif kind == "grad":
                n = 12
                for i in range(n):
                    cv.rect(x0 + sw * i / n, yc - 4.5, sw / n + 0.2, 9.0,
                            fill=_mix_hex(spec.heat_low, spec.heat_high, i / (n - 1)))
            cv.text(x0 + sw + 6.0, yc + TM.cap_height(fs) / 2, text, fs, anchor="start")
    box = QRectF(x0 - 1, dy, width + 2, y - dy)
    return Element("legend", "legend", box, draw, _rect_path(box), {"font_keys": ["legend"]})
