"""Parts-of-whole graphs (pie, donut, 100% stacked bars) and survival graphs (Kaplan-Meier
staircases with censoring ticks and confidence bands). Same element contract as layout.py.
"""

from __future__ import annotations

import math

import numpy as np
from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainterPath, QPainterPathStroker

from ...doc.model import column_letter
from ...doc.spec import PALETTE
from .canvas import MM, TextMetrics as TM
from .layout import (ORDER, AxisRange, Element, Plan, YMap, _legend, _rect_path, _text_rect, _title,
                     _y_axis, _y_title, nice_range)
from .xy_layout import XMap, _x_axis_numeric, _x_title, x_range


# ---------------------------------------------------------------------------
# Parts of whole
# ---------------------------------------------------------------------------

def slice_color(i: int) -> str:
    return PALETTE[i % len(PALETTE)][0] if i % len(PALETTE) else "#4f4f4f"


def ink_on(fill: str) -> str:
    """Black or white text, whichever reads better on the fill."""
    h = fill.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return "#ffffff" if 0.2126 * r + 0.7152 * g + 0.0722 * b < 0.45 else "#000000"


def _parts_values(t, c):
    rows, vals = [], []
    for r in range(t.nrows_used()):
        v = t._ok(r, t.flat(c))
        if v is not None and v > 0:
            rows.append(r)
            vals.append(v)
    return rows, np.array(vals, float)


def build_parts(graph) -> tuple[list[Element], AxisRange]:
    spec, t = graph.spec, graph.table
    cols = [c for c in t.used_columns() if c not in spec.hidden]
    elements: list[Element] = []
    lay = spec.parts_layout
    fs = spec.fonts["x_labels"]
    fs_l = spec.fonts["legend"]
    all_rows = sorted({r for c in cols for r in _parts_values(t, c)[0]})
    color_of = {r: slice_color(i) for i, r in enumerate(all_rows)}
    d = spec.y_len_mm * MM
    if lay == "stacked100":
        bw, gap = spec.col_width_mm * MM * 1.6, spec.col_width_mm * MM
        ph = d
        rng = AxisRange(0.0, 100.0, 20.0)
        from ...doc.spec import AxisSpec
        ym = YMap(spec.y, rng, ph)
        tops = []
        for i, c in enumerate(cols):
            rows, vals = _parts_values(t, c)
            if not len(vals):
                continue
            x0 = gap / 2 + i * (bw + gap)
            pct = vals / vals.sum() * 100
            segs = []
            base = 0.0
            for r, v in zip(rows, pct):
                segs.append((r, base, base + v))
                base += v

            def draw(cv, x0=x0, segs=segs, rows=rows, vals=vals, pct=pct):
                for r, a, b in segs:
                    cv.rect(x0, ym(b), bw, ym(a) - ym(b), fill=color_of[r], stroke="#ffffff", width=0.75)
                    if spec.parts_labels != "none" and ym(a) - ym(b) > TM.ascent(fs_l) + 2:
                        k = rows.index(r)
                        lab = f"{pct[k]:.0f}%" if spec.parts_labels == "percent" else f"{vals[k]:g}"
                        cv.text(x0 + bw / 2, (ym(a) + ym(b)) / 2 + TM.cap_height(fs_l) / 2, lab, fs_l,
                                color=ink_on(color_of[r]), anchor="middle")
            box = QRectF(x0, 0, bw, ph)
            elements.append(Element(f"data-{column_letter(c)}", "dataset", box, draw, _rect_path(box),
                                    {"column": c, "label": t.label(c)}))
        pw = max(len(cols), 1) * (bw + gap)
        y_el, num_left = _y_axis(spec, ym, ph, 0.0)
        elements.append(y_el)
        from .layout import _x_axis
        elements.append(_x_axis(spec, [(gap / 2 + i * (bw + gap) + bw / 2, t.label(c)) for i, c in enumerate(cols)],
                                [], pw, ph, 0.0))
        elements += _y_title(spec, num_left, ph)
    else:
        rng = AxisRange(0.0, 1.0, 1.0)
        gap = d * 0.35
        for i, c in enumerate(cols):
            rows, vals = _parts_values(t, c)
            if not len(vals):
                continue
            cx, cy, R = i * (d + gap) + d / 2, d / 2, d / 2
            hole = spec.donut_hole if lay == "donut" else 0.0
            fracs = vals / vals.sum()

            def draw(cv, cx=cx, cy=cy, R=R, hole=hole, rows=rows, fracs=fracs, vals=vals):
                a0 = -90.0                               # start at 12 o'clock, clockwise
                for r, f, v in zip(rows, fracs, vals):
                    a1 = a0 + f * 360.0
                    n = max(2, int(abs(a1 - a0) / 3) + 2)
                    outer = [(cx + R * math.cos(math.radians(a)), cy + R * math.sin(math.radians(a)))
                             for a in np.linspace(a0, a1, n)]
                    if hole > 0:
                        inner = [(cx + R * hole * math.cos(math.radians(a)), cy + R * hole * math.sin(math.radians(a)))
                                 for a in np.linspace(a1, a0, n)]
                        pts = outer + inner
                    else:
                        pts = [(cx, cy)] + outer
                    cv.polygon(pts, fill=color_of[r], stroke="#ffffff", width=1.0)
                    if spec.parts_labels != "none" and f >= 0.04:
                        mid = math.radians((a0 + a1) / 2)
                        rr = R * (0.62 if hole == 0 else (1 + hole) / 2)
                        lab = f"{f * 100:.0f}%" if spec.parts_labels == "percent" else f"{v:g}"
                        cv.text(cx + rr * math.cos(mid), cy + rr * math.sin(mid) + TM.cap_height(fs_l) / 2, lab,
                                fs_l, color=ink_on(color_of[r]), anchor="middle")
                    a0 = a1
                cv.text(cx, cy + R + 6 + TM.ascent(fs), t.label(c), fs, anchor="middle")
            box = QRectF(cx - R, cy - R, 2 * R, 2 * R + 8 + TM.ascent(fs) + TM.descent(fs))
            p = QPainterPath()
            p.addEllipse(QRectF(cx - R, cy - R, 2 * R, 2 * R))
            elements.append(Element(f"data-{column_letter(c)}", "dataset", box, draw, p,
                                    {"column": c, "label": t.label(c)}))
        pw = max(len(cols), 1) * (d + gap) - gap
    # legend: one entry per row (slice)
    if spec.show_legend and all_rows:
        entries = [(r, t.row_label(r)) for r in all_rows]
        row_h = max(TM.ascent(fs_l) + TM.descent(fs_l), 9.0) + 4.0
        lx = pw + 14.0
        dx, dy = spec.offsets.get("legend", (0.0, 0.0))
        lx, ly = lx + dx, dy

        def draw_legend(cv, lx=lx, ly=ly):
            for k, (r, s) in enumerate(entries):
                yc = ly + k * row_h + row_h / 2
                cv.rect(lx, yc - 4.5, 12.0, 9.0, fill=color_of[r], stroke=None)
                cv.text(lx + 17.0, yc + TM.cap_height(fs_l) / 2, s, fs_l, anchor="start")
        w = 17.0 + max(TM.width(s, fs_l) for _, s in entries)
        box = QRectF(lx - 1, ly, w + 2, row_h * len(entries))
        elements.append(Element("legend", "legend", box, draw_legend, _rect_path(box), {"font_keys": ["legend"]}))
    elements += _title(spec, graph, pw, 0.0 if lay != "stacked100" else min(0.0, -6.0))
    elements.sort(key=lambda e: ORDER[e.kind])
    return elements, rng


# ---------------------------------------------------------------------------
# Survival
# ---------------------------------------------------------------------------

def build_survival(graph) -> tuple[list[Element], AxisRange]:
    from ...analysis.survival import km, subjects
    spec, t = graph.spec, graph.table
    cols = [c for c in t.used_columns() if c not in spec.hidden]
    pw, ph = spec.x_len_mm * MM, spec.y_len_mm * MM
    scale = 100.0 if spec.surv_percent else 1.0
    death = spec.surv_death
    curves = {}
    for c in cols:
        tm, ev = subjects(t, c)
        if len(tm):
            curves[c] = (km(tm, ev), tm, ev)
    xmax = max([float(v[1].max()) for v in curves.values()] or [1.0])
    xr = x_range(spec, [0.0, xmax])
    xm = XMap(spec.x, xr, pw)
    rng = AxisRange(0.0, scale, scale / 5) if spec.y.auto else AxisRange(spec.y.vmin, spec.y.vmax, spec.y.interval)
    ym = YMap(spec.y, rng, ph)
    elements: list[Element] = []

    def val(s):
        return (1 - s if death else s) * scale

    for c, (cv_, tm, ev) in curves.items():
        st = spec.style(c)
        col = st.symbol_color
        pts = [(xm(0.0), ym(val(1.0)))]
        lo_pts, hi_pts = [(xm(0.0), ym(val(1.0)))], [(xm(0.0), ym(val(1.0)))]
        prev, prev_lo, prev_hi = 1.0, 1.0, 1.0
        ticks = []
        for r in cv_["rows"]:
            x = xm(r["time"])
            if r["events"]:
                pts += [(x, ym(val(prev))), (x, ym(val(r["S"])))]
                if math.isfinite(r["lo"]) and math.isfinite(r["hi"]):
                    lo_pts += [(x, ym(val(prev_lo))), (x, ym(val(r["lo"])))]
                    hi_pts += [(x, ym(val(prev_hi))), (x, ym(val(r["hi"])))]
                    prev_lo, prev_hi = r["lo"], r["hi"]
                prev = r["S"]
            if r["censored"]:
                ticks.append((x, ym(val(prev))))
        last_x = xm(float(tm.max()))
        pts.append((last_x, ym(val(prev))))
        lo_pts.append((last_x, ym(val(prev_lo))))
        hi_pts.append((last_x, ym(val(prev_hi))))

        def draw(cv, pts=pts, ticks=ticks, lo_pts=lo_pts, hi_pts=hi_pts, st=st, col=col):
            if spec.surv_ci == "shaded":
                band = hi_pts + list(reversed(lo_pts))
                cv.polygon(band, fill=st.bar_fill if st.bar_fill != "#b4b4b4" else col, opacity=0.2)
            elif spec.surv_ci == "dashed":
                for line in (lo_pts, hi_pts):
                    cv.polyline(line, col, max(st.line_width * 0.6, 0.5), "butt", "dash")
            cv.polyline(pts, col, st.line_width, "butt", None if st.line_dash == "solid" else st.line_dash)
            if spec.surv_ticks:
                h = max(st.symbol_size * 1.2, 3.0)
                for x, y in ticks:
                    cv.line(x, y - h, x, y + h, col, st.line_width, "butt")
        path = QPainterPath()
        path.moveTo(*pts[0])
        for p_ in pts[1:]:
            path.lineTo(*p_)
        stroke = QPainterPathStroker()
        stroke.setWidth(6.0)
        hit = stroke.createStroke(path)
        elements.append(Element(f"data-{column_letter(c)}", "dataset", hit.boundingRect().adjusted(-3, -3, 3, 3),
                                draw, hit, {"column": c, "label": t.label(c)}))
    y_el, num_left = _y_axis(spec, ym, ph, 0.0)
    elements.append(y_el)
    elements.append(_x_axis_numeric(spec, xm, pw, ph, 0.0))
    elements += _y_title(spec, num_left, ph)
    xt = _x_title(spec, pw, None, ph)
    if xt:
        elements.append(xt)
    if spec.show_legend and len(curves) > 1:
        elements.append(_legend(spec, t, Plan([], pw, [], legend=list(curves), swatch="line"), pw + 12.0, 0.0))
    content_top = min([0.0] + [e.bounds.top() for e in elements if e.id == "y-title"])
    elements += _title(spec, graph, pw, content_top)
    elements.sort(key=lambda e: ORDER[e.kind])
    return elements, rng
