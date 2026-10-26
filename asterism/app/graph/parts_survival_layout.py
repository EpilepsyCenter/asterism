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


def waffle_counts(vals) -> list[int]:
    """Squares out of 100 for each part, by largest remainder (so they add to 100)."""
    v = np.asarray(vals, float)
    exact = v / v.sum() * 100 if v.sum() > 0 else np.zeros_like(v)
    base = np.floor(exact).astype(int)
    for k in np.argsort(-(exact - base))[: 100 - int(base.sum())]:
        base[k] += 1
    return [int(b) for b in base]


def parts_rows(graph) -> list[int]:
    """Rows drawn as slices, in drawing order (reversed when asked)."""
    spec, t = graph.spec, graph.table
    cols = [c for c in t.used_columns() if c not in spec.hidden]
    rows = sorted({r for c in cols for r in _parts_values(t, c)[0]})
    return rows[::-1] if spec.parts.get("reverse") else rows


def parts_colors(graph) -> dict[int, str]:
    """Each slice row's fill: the colour set for it, else the automatic one (by row order)."""
    spec, t = graph.spec, graph.table
    cols = [c for c in t.used_columns() if c not in spec.hidden]
    rows = sorted({r for c in cols for r in _parts_values(t, c)[0]})
    chosen = spec.parts.get("colors") or {}
    return {r: (chosen.get(str(r)) or slice_color(i)) for i, r in enumerate(rows)}


def _total_text(P: dict, vals) -> str:
    tot = float(np.sum(vals))
    return f"{P.get('total_prefix', '')}{tot:g}{P.get('total_suffix', '')}"


def build_parts(graph) -> tuple[list[Element], AxisRange]:
    spec, t = graph.spec, graph.table
    P = spec.parts
    cols = [c for c in t.used_columns() if c not in spec.hidden]
    elements: list[Element] = []
    lay = spec.parts_layout
    fs = spec.fonts["x_labels"]
    fs_l = spec.fonts["legend"]
    all_rows = parts_rows(graph)
    color_of = parts_colors(graph)
    rev = bool(P.get("reverse"))
    inner = (P.get("inner_color", "#ffffff"), float(P.get("inner_width", 1.0))) if P.get("inner", True) else None
    outer = (P.get("outer_color", "#000000"), float(P.get("outer_width", 1.0))) if P.get("outer") else None
    explode = {int(k): float(v) for k, v in (P.get("explode") or {}).items() if float(v or 0) > 0}
    show_total = bool(P.get("total"))
    line_h = TM.ascent(fs) + TM.descent(fs)

    def ordered(c):
        rows, vals = _parts_values(t, c)
        if rev:
            rows, vals = rows[::-1], vals[::-1]
        return rows, vals

    d = spec.y_len_mm * MM
    if lay == "stacked100":
        bw, gap = spec.col_width_mm * MM * 1.6, spec.col_width_mm * MM
        ph = d
        rng = AxisRange(0.0, 100.0, 20.0)
        ym = YMap(spec.y, rng, ph)
        for i, c in enumerate(cols):
            rows, vals = ordered(c)
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
                    cv.rect(x0, ym(b), bw, ym(a) - ym(b), fill=color_of[r], stroke=None)
                if inner:
                    for r, a, b in segs[:-1]:
                        cv.line(x0, ym(b), x0 + bw, ym(b), inner[0], inner[1], "butt")
                if outer:
                    cv.rect(x0, ym(100.0), bw, ym(0.0) - ym(100.0), fill=None, stroke=outer[0], width=outer[1])
                for r, a, b in segs:
                    if spec.parts_labels != "none" and ym(a) - ym(b) > TM.ascent(fs_l) + 2:
                        k = rows.index(r)
                        lab = f"{pct[k]:.0f}%" if spec.parts_labels == "percent" else f"{vals[k]:g}"
                        cv.text(x0 + bw / 2, (ym(a) + ym(b)) / 2 + TM.cap_height(fs_l) / 2, lab, fs_l,
                                color=ink_on(color_of[r]), anchor="middle")
                if show_total:
                    cv.text(x0 + bw / 2, ym(100.0) - 4, _total_text(P, vals), fs_l, anchor="middle")
            top = -(line_h + 4) if show_total else 0.0
            box = QRectF(x0, top, bw, ph - top)
            elements.append(Element(f"data-{column_letter(c)}", "dataset", box, draw, _rect_path(box),
                                    {"column": c, "label": t.label(c)}))
        pw = max(len(cols), 1) * (bw + gap)
        y_el, num_left = _y_axis(spec, ym, ph, 0.0)
        elements.append(y_el)
        from .layout import _x_axis
        elements.append(_x_axis(spec, [(gap / 2 + i * (bw + gap) + bw / 2, t.label(c)) for i, c in enumerate(cols)],
                                [], pw, ph, 0.0))
        elements += _y_title(spec, num_left, ph)
    elif lay == "waffle":                                 # percentage dot plot: 100 squares
        rng = AxisRange(0.0, 100.0, 20.0)
        gap = d * 0.25
        cell = d / 10
        for i, c in enumerate(cols):
            rows, vals = ordered(c)
            if not len(vals):
                continue
            counts = waffle_counts(vals)
            x0 = i * (d + gap)
            owner = [r for r, k in zip(rows, counts) for _ in range(k)]

            def draw(cv, x0=x0, owner=owner, c=c, vals=vals):
                for k, r in enumerate(owner):           # row by row from the top left
                    row, col = divmod(k, 10)
                    cv.rect(x0 + col * cell + cell * 0.08, row * cell + cell * 0.08, cell * 0.84, cell * 0.84,
                            fill=color_of[r])
                if outer:
                    cv.rect(x0, 0, d, d, fill=None, stroke=outer[0], width=outer[1])
                cv.text(x0 + d / 2, d + 6 + TM.ascent(fs), t.label(c), fs, anchor="middle")
                if show_total:
                    cv.text(x0 + d / 2, d + 6 + line_h + TM.ascent(fs_l), _total_text(P, vals), fs_l, anchor="middle")
            box = QRectF(x0, 0, d, d + 8 + line_h * (2 if show_total else 1))
            elements.append(Element(f"data-{column_letter(c)}", "dataset", box, draw, _rect_path(box),
                                    {"column": c, "label": t.label(c)}))
        pw = max(len(cols), 1) * (d + gap) - gap
    else:
        rng = AxisRange(0.0, 1.0, 1.0)
        pull = max(explode.values(), default=0.0) / 100.0         # room for pulled-out slices
        gap = d * 0.35 + 2 * pull * d / 2
        for i, c in enumerate(cols):
            rows, vals = ordered(c)
            if not len(vals):
                continue
            R = d / 2
            cx, cy = i * (d + gap) + d / 2 + pull * R, d / 2 + pull * R
            hole = spec.donut_hole if lay == "donut" else 0.0
            fracs = vals / vals.sum()

            def arc(cx_, cy_, rad, a0, a1, n):
                return [(cx_ + rad * math.cos(math.radians(a)), cy_ + rad * math.sin(math.radians(a)))
                        for a in np.linspace(a0, a1, n)]

            def draw(cv, cx=cx, cy=cy, R=R, hole=hole, rows=rows, fracs=fracs, vals=vals):
                a0 = -90.0                               # start at 12 o'clock, clockwise
                for r, f, v in zip(rows, fracs, vals):
                    a1 = a0 + f * 360.0
                    n = max(2, int(abs(a1 - a0) / 3) + 2)
                    mid = math.radians((a0 + a1) / 2)
                    off = explode.get(r, 0.0) / 100.0 * R
                    sx, sy = cx + off * math.cos(mid), cy + off * math.sin(mid)
                    outer_pts = arc(sx, sy, R, a0, a1, n)
                    if hole > 0:
                        inner_pts = arc(sx, sy, R * hole, a1, a0, n)
                        pts = outer_pts + inner_pts
                    else:
                        pts = [(sx, sy)] + outer_pts
                    full = f >= 0.9999
                    cv.polygon(pts, fill=color_of[r], stroke=None if full else (inner[0] if inner else None),
                               width=inner[1] if inner else 0.0)
                    if outer:
                        cv.polyline(outer_pts, outer[0], outer[1], "butt")
                        if hole > 0:
                            cv.polyline(inner_pts, outer[0], outer[1], "butt")
                    if spec.parts_labels != "none" and f >= 0.04:
                        rr = R * (0.62 if hole == 0 else (1 + hole) / 2)
                        lab = f"{f * 100:.0f}%" if spec.parts_labels == "percent" else f"{v:g}"
                        cv.text(sx + rr * math.cos(mid), sy + rr * math.sin(mid) + TM.cap_height(fs_l) / 2, lab,
                                fs_l, color=ink_on(color_of[r]), anchor="middle")
                    a0 = a1
                below = cy + R * (1 + pull) + 6
                cv.text(cx, below + TM.ascent(fs), t.label(c), fs, anchor="middle")
                if show_total:
                    cv.text(cx, below + line_h + TM.ascent(fs_l), _total_text(P, vals), fs_l, anchor="middle")
            Rp = R * (1 + pull)
            box = QRectF(cx - Rp, cy - Rp, 2 * Rp, 2 * Rp + 8 + line_h * (2 if show_total else 1))
            p = QPainterPath()
            p.addEllipse(QRectF(cx - Rp, cy - Rp, 2 * Rp, 2 * Rp))
            elements.append(Element(f"data-{column_letter(c)}", "dataset", box, draw, p,
                                    {"column": c, "label": t.label(c)}))
        pw = max(len(cols), 1) * (d + gap) - gap
    # legend: one entry per row (slice) — colour, label, percentage and value as chosen
    if spec.show_legend and all_rows:
        one = cols[0] if len(cols) == 1 else None
        share = {}
        if one is not None:
            rr, vv = _parts_values(t, one)
            tot = float(vv.sum()) or 1.0
            share = {r: (v, v / tot * 100) for r, v in zip(rr, vv)}
        entries = []
        for r in (all_rows[::-1] if lay == "stacked100" else all_rows):     # stacked: top segment first
            bits = [t.row_label(r)] if P.get("legend_label", True) else []
            if r in share and P.get("legend_percent"):
                bits.append(f"{share[r][1]:.0f}%")
            if r in share and P.get("legend_value"):
                bits.append(f"{share[r][0]:g}")
            entries.append((r, "  ".join(bits)))
        swatch = bool(P.get("legend_color", True))
        sw = 17.0 if swatch else 0.0
        row_h = max(TM.ascent(fs_l) + TM.descent(fs_l), 9.0) + 4.0
        lx = pw + 14.0
        dx, dy = spec.offsets.get("legend", (0.0, 0.0))
        lx, ly = lx + dx, dy

        def draw_legend(cv, lx=lx, ly=ly):
            for k, (r, s_) in enumerate(entries):
                yc = ly + k * row_h + row_h / 2
                if swatch:
                    cv.rect(lx, yc - 4.5, 12.0, 9.0, fill=color_of[r],
                            stroke=outer[0] if outer else None, width=outer[1] * 0.75 if outer else 0.0)
                cv.text(lx + sw, yc + TM.cap_height(fs_l) / 2, s_, fs_l, anchor="start")
        w = sw + max([TM.width(s_, fs_l) for _, s_ in entries] + [0.0])
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
    # the event/censored codes (and interval settings) of the table's survival analysis, if any
    sa = next((a for a in graph.analyses() if a.kind == "survival"), None)
    sp = sa.params if sa is not None else {}
    ev_code, ce_code = sp.get("event_code", 1), sp.get("censor_code", 0)
    for c in cols:
        tm, ev = subjects(t, c, ev_code, ce_code)
        if len(tm):
            curves[c] = (km(tm, ev, sp.get("conf", 0.95), sp.get("ci", "loglog")), tm, ev)
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
        ticks, bars = [], []
        for r in cv_["rows"]:
            x = xm(r["time"])
            if r["events"]:
                pts += [(x, ym(val(prev))), (x, ym(val(r["S"])))]
                if math.isfinite(r["lo"]) and math.isfinite(r["hi"]):
                    lo_pts += [(x, ym(val(prev_lo))), (x, ym(val(r["lo"])))]
                    hi_pts += [(x, ym(val(prev_hi))), (x, ym(val(r["hi"])))]
                    prev_lo, prev_hi = r["lo"], r["hi"]
                    bars.append((x, ym(val(r["lo"])), ym(val(r["hi"]))))
                prev = r["S"]
            if r["censored"]:
                ticks.append((x, ym(val(prev))))
        last_x = xm(float(tm.max()))
        pts.append((last_x, ym(val(prev))))
        lo_pts.append((last_x, ym(val(prev_lo))))
        hi_pts.append((last_x, ym(val(prev_hi))))

        def draw(cv, pts=pts, ticks=ticks, lo_pts=lo_pts, hi_pts=hi_pts, st=st, col=col, bars=bars):
            if spec.surv_ci == "bars":                 # error bars at each step
                cap = 2.5
                for x, ya, yb in bars:
                    cv.line(x, ya, x, yb, st.error_color if st.error_color != "#000000" else col,
                            st.error_width, "butt")
                    for y_ in (ya, yb):
                        cv.line(x - cap, y_, x + cap, y_, col, st.error_width, "butt")
            elif spec.surv_ci == "shaded":
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
