"""Graph model → positioned, self-drawing elements.

`build(graph)` turns a Graph (data + GraphSpec + linked analyses) into a list of
Elements. Each Element knows its id, bounds, hit area and how to draw itself on any
canvas. The on-screen editor wraps each one in a selectable QGraphicsItem; export
walks the same list. One layout, one drawing path, so screen == file.

Coordinates: points, origin at the top-left of the plot area.
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field
from typing import Callable

import numpy as np
from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainterPath

from ...doc.model import Graph, column_letter
from ...doc.spec import AxisSpec, DataSetStyle, FontSpec
from ...analysis.results import fmt_p, p_summary
from .canvas import MM, TextMetrics as TM

TICK_LEN = {"very_short": 2.0, "short": 3.0, "normal": 4.5, "long": 6.5, "very_long": 9.0}


@dataclass
class Element:
    id: str
    kind: str                      # y-axis | x-axis | dataset | text | bracket | frame
    bounds: QRectF
    draw: Callable
    hit: QPainterPath | None = None
    meta: dict = field(default_factory=dict)


@dataclass
class AxisRange:
    vmin: float
    vmax: float
    interval: float


# ---------------------------------------------------------------------------
# Axis helpers
# ---------------------------------------------------------------------------

def nice_range(lo: float, hi: float, target: int = 5) -> AxisRange:
    if hi <= lo:
        hi = lo + (abs(lo) or 1.0)
    raw = (hi - lo) / target
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if raw <= m * mag + 1e-12)
    return AxisRange(math.floor(lo / step + 1e-9) * step, math.ceil(hi / step - 1e-9) * step, step)


def auto_decimals(step: float) -> int:
    for d in range(0, 7):
        if abs(step * 10 ** d - round(step * 10 ** d)) < 1e-6:
            return d
    return 6


class YMap:
    """Value → position along the axis (0 at the top). A linear axis can have a break:
    two segments, the bottom one ending at low_to and the top one starting at high_from,
    with a gap between them."""

    def __init__(self, ax: AxisSpec, rng: AxisRange, h: float):
        self.ax, self.r, self.h = ax, rng, h
        self.log = ax.scale == "log10"
        self.brk = None
        b = getattr(ax, "brk", None) or {}
        if b.get("on") and not self.log:
            lt, hf = float(b.get("low_to", 0)), float(b.get("high_from", 0))
            if rng.vmin < lt < hf < rng.vmax:
                gap = max(0.0, min(float(b.get("gap", 14.0)), h * 0.4))
                split = min(max(float(b.get("split", 0.5)), 0.1), 0.9)
                hl = (h - gap) * split
                ls = float(b.get("low_step") or 0) or nice_range(rng.vmin, lt).interval
                hs = float(b.get("high_step") or 0) or nice_range(hf, rng.vmax).interval
                self.brk = {"lt": lt, "hf": hf, "gap": gap, "hl": hl, "ls": ls, "hs": hs}

    def __call__(self, v: float) -> float:
        lo, hi = self.r.vmin, self.r.vmax
        if self.brk:
            b, h = self.brk, self.h
            top_len = h - b["hl"] - b["gap"]
            if v <= b["lt"]:
                return h - (v - lo) / (b["lt"] - lo) * b["hl"]
            if v >= b["hf"]:
                return top_len - (v - b["hf"]) / (hi - b["hf"]) * top_len
            return (h - b["hl"]) - (v - b["lt"]) / (b["hf"] - b["lt"]) * b["gap"]
        if self.log:
            v = math.log10(max(v, lo))            # zero or negative (e.g. mean − SD) stops at the axis
            lo, hi = math.log10(lo), math.log10(hi)
        return self.h - (v - lo) / (hi - lo) * self.h

    def segments(self) -> list[tuple[float, float]]:
        """(top, bottom) positions of the axis line's pieces."""
        if not self.brk:
            return [(0.0, self.h)]
        b = self.brk
        return [(self.h - b["hl"], self.h), (0.0, self.h - b["hl"] - b["gap"])]

    def gap(self) -> tuple[float, float] | None:
        if not self.brk:
            return None
        return self.h - self.brk["hl"] - self.brk["gap"], self.h - self.brk["hl"]

    @staticmethod
    def _steps(a: float, b: float, step: float) -> list[float]:
        n = int(math.floor((b - a) / step + 1e-9))
        return [a + i * step for i in range(n + 1)]

    def majors(self) -> list[float]:
        if self.brk:
            b = self.brk
            return self._steps(self.r.vmin, b["lt"], b["ls"]) + self._steps(b["hf"], self.r.vmax, b["hs"])
        if self.log:
            k0, k1 = round(math.log10(self.r.vmin)), round(math.log10(self.r.vmax))
            return [10.0 ** k for k in range(k0, k1 + 1)]
        n = int(round((self.r.vmax - self.r.vmin) / self.r.interval))
        return [self.r.vmin + i * self.r.interval for i in range(n + 1)]

    def minors(self) -> list[float]:
        m = self.ax.minor
        if m <= 0:
            return []
        if self.log:
            out = []
            for v in self.majors()[:-1]:
                out += [v * k for k in range(2, 10)]
            return out
        if self.brk:
            b, out = self.brk, []
            for a_, b_, st in ((self.r.vmin, b["lt"], b["ls"]), (b["hf"], self.r.vmax, b["hs"])):
                for v in self._steps(a_, b_, st)[:-1]:
                    out += [v + st / (m + 1) * (i + 1) for i in range(m)]
            return out
        out, step = [], self.r.interval / (m + 1)
        for v in self.majors()[:-1]:
            out += [v + step * (i + 1) for i in range(m)]
        return out

    def label(self, v: float) -> str:
        ax = self.ax
        if ax.fmt == "antilog":                   # values are log10 of something: show 10^v
            s = power_label(10.0 ** v, ax.decimals, bare_powers=True)
        elif ax.fmt == "power":
            s = power_label(v, ax.decimals, bare_powers=self.log)
        elif self.log:
            d = max(0, -int(round(math.log10(v)))) if ax.decimals < 0 else ax.decimals
            s = f"{v:.{d}f}"
        elif ax.fmt == "scientific":
            s = f"{v:.{max(ax.decimals, 1)}e}"
        else:
            step = min(self.brk["ls"], self.brk["hs"]) if self.brk else self.r.interval
            d = auto_decimals(step) if ax.decimals < 0 else ax.decimals
            s = f"{v:.{d}f}"
            if s.startswith("-") and float(s) == 0:
                s = s[1:]
        return f"{ax.prefix}{s}{ax.suffix}"


_SUP = str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻")


def power_label(v: float, decimals: int = -1, bare_powers: bool = False) -> str:
    """3×10¹³ (powers of ten with superscripts). With bare_powers, 1×10ⁿ is written 10ⁿ
    (log axes). decimals < 0: up to three significant digits, trailing zeros dropped."""
    if v == 0 or not math.isfinite(v):
        return "0" if v == 0 else str(v)
    e = int(math.floor(math.log10(abs(v)) + 1e-12))
    m = v / 10 ** e
    if abs(round(m, 6)) >= 10:
        m, e = m / 10, e + 1
    ms = f"{m:.{decimals}f}" if decimals >= 0 else f"{m:.2f}".rstrip("0").rstrip(".")
    if e == 0:
        return ms
    sup = str(e).translate(_SUP)
    if bare_powers and ms in ("1", "-1"):
        return ("−" if ms == "-1" else "") + f"10{sup}"
    return f"{ms.replace('-', '−')}×10{sup}"


def y_range(graph: Graph, summaries: dict[int, dict], ax: AxisSpec | None = None) -> AxisRange:
    ax = ax or graph.spec.y
    if not ax.auto:
        if ax.scale == "log10":
            return AxisRange(max(ax.vmin, 1e-12), max(ax.vmax, ax.vmin * 10), ax.interval)
        return AxisRange(ax.vmin, ax.vmax, ax.interval if ax.interval > 0 else 1)
    vals = [v for s in summaries.values() for v in (s["min"], s["max"], s["lo"], s["hi"])
            if v is not None and not np.isnan(v)]
    if not vals:
        return AxisRange(0.0, 100.0, 20.0) if ax.scale != "log10" else AxisRange(1, 100, 1)
    if ax.scale == "log10":
        pos = [v for v in vals if v > 0] or [1.0]
        return AxisRange(10.0 ** math.floor(math.log10(min(pos))),
                         10.0 ** math.ceil(math.log10(max(pos)) + 1e-9), 1)
    lo, hi = min(vals), max(vals)
    return nice_range(min(0.0, lo), max(0.0, hi))


# ---------------------------------------------------------------------------
# Data summaries and swarm layout
# ---------------------------------------------------------------------------

def summarize(x: np.ndarray, st: DataSetStyle) -> dict:
    from scipy import stats as sps
    out = {"n": len(x), "min": None, "max": None, "center": None, "lo": None, "hi": None,
           "mean": None}
    if len(x) == 0:
        return out
    out["min"], out["max"], out["mean"] = float(x.min()), float(x.max()), float(x.mean())
    mean, med = float(x.mean()), float(np.median(x))
    sd = float(x.std(ddof=1)) if len(x) > 1 else 0.0
    sem = sd / math.sqrt(len(x)) if len(x) > 1 else 0.0
    la = st.line_at
    if la in ("median_iqr", "median", "median_range"):
        out["center"] = med
        if la == "median_iqr" and len(x) > 1:
            out["lo"] = float(np.percentile(x, 25, method="weibull"))
            out["hi"] = float(np.percentile(x, 75, method="weibull"))
        elif la == "median_range":
            out["lo"], out["hi"] = out["min"], out["max"]
    elif la == "mean_range":
        out["center"] = mean
        out["lo"], out["hi"] = out["min"], out["max"]
    elif la != "none":
        out["center"] = mean
        err = {"mean_sem": sem, "mean_sd": sd,
               "mean_ci": sps.t.ppf(0.975, len(x) - 1) * sem if len(x) > 1 else 0.0}.get(la)
        if err is not None:
            out["lo"], out["hi"] = mean - err, mean + err
    if st.appearance in ("bar", "floating", "symbol") and out["center"] is None:
        out["center"] = mean
    # Symbols to draw: every value, or none when points are switched off.
    out["points"] = [float(v) for v in x] if st.show_points and st.appearance != "symbol" else []
    if st.appearance == "violin":
        out["center"] = med
        out["lo"] = out["hi"] = None
        if len(x) > 1:
            out["q1"] = float(np.percentile(x, 25, method="weibull"))
            out["q3"] = float(np.percentile(x, 75, method="weibull"))
            out["kde"] = violin_curve(x, st.violin_smooth)
    if st.appearance == "box":
        out["center"] = med
        if len(x) > 1:
            out.update(box_stats(x, st.whiskers))
            if st.show_points:                  # box with all points superimposed
                out["points"] = [float(v) for v in x]
    return out


SMOOTHING = {"light": 0.5, "medium": 1.0, "heavy": 2.0}   # × Scott's bandwidth


def violin_curve(x: np.ndarray, smooth: str, n: int = 81) -> list[tuple[float, float]]:
    """(value, relative density) from the smallest to the largest value: the violin is
    truncated at the data's extremes, as Prism draws it. Density scaled to a maximum of 1."""
    from scipy.stats import gaussian_kde
    x = np.asarray(x, float)
    lo, hi = float(x.min()), float(x.max())
    if hi <= lo or len(x) < 2:
        return [(lo, 1.0), (hi, 1.0)]
    kde = gaussian_kde(x)
    kde.set_bandwidth(kde.factor * SMOOTHING.get(smooth, 1.0))
    grid = np.linspace(lo, hi, n)
    dens = kde(grid)
    dens = dens / dens.max() if dens.max() > 0 else np.ones_like(dens)
    return list(zip(grid.tolist(), dens.tolist()))


GRAPHABLE_TYPES = {"column", "grouped", "nested", "xy", "contingency", "parts", "survival", "multivar"}


def summarize_entered(sm: dict | None, st: DataSetStyle) -> dict:
    """Summary for a data set whose mean and error were entered (no raw values):
    mean as the centre; SD, SEM or 95% CI error bars when they can be derived from what
    was entered, otherwise the entered error or limits."""
    from scipy import stats as sps
    out = {"n": 0, "min": None, "max": None, "center": None, "lo": None, "hi": None,
           "mean": None, "points": []}
    if not sm:
        return out
    m = sm["mean"]
    out.update(center=m, mean=m, min=m, max=m, n=int(sm["n"] or 0))
    err = None
    if st.line_at == "mean_sd" and sm["sd"] is not None:
        err = sm["sd"]
    elif st.line_at == "mean_sem" and sm["sem"] is not None:
        err = sm["sem"]
    elif st.line_at == "mean_ci" and sm["sem"] is not None and sm["n"] and sm["n"] > 1:
        err = sps.t.ppf(0.975, sm["n"] - 1) * sm["sem"]
    if err is not None:
        out["lo"], out["hi"] = m - err, m + err
    elif st.line_at != "none":
        out["lo"], out["hi"] = sm["lo"], sm["hi"]
    return out


WHISKER_PCT = {"p10": 10.0, "p5": 5.0, "p2_5": 2.5, "p1": 1.0}


def box_stats(x: np.ndarray, whiskers: str) -> dict:
    """Prism's box and whiskers: box = 25th–75th percentile, whiskers by the chosen
    method, points beyond the whiskers drawn individually. Fewer than four values:
    median and range, whatever the whisker choice (as Prism does)."""
    def pct(q: float) -> float:
        return float(np.percentile(x, q, method="weibull"))
    q1, q3 = pct(25), pct(75)
    vals = [float(v) for v in x]
    mode = whiskers if len(x) >= 4 else "minmax"
    if mode == "tukey":
        iqr = q3 - q1
        whi = max(v for v in vals if v <= q3 + 1.5 * iqr)
        wlo = min(v for v in vals if v >= q1 - 1.5 * iqr)
    elif mode in WHISKER_PCT:
        p = WHISKER_PCT[mode]
        wlo, whi = pct(p), pct(100 - p)
    else:
        wlo, whi = min(vals), max(vals)
    if mode == "minmax_all":
        points = vals
    elif mode == "minmax":
        points = []
    else:
        points = [v for v in vals if v < wlo or v > whi]
    return {"lo": q1, "hi": q3, "wlo": wlo, "whi": whi, "points": points}


def swarm(ys: list[float], d: float, max_half: float) -> list[float]:
    """Beeswarm within the column: each point takes the free spot nearest the centre.

    When a value has more ties than fit side by side, the extra points go where they
    overlap least (evenly between their neighbours) — only the crowded points overlap;
    the rest of the cloud keeps its true spacing (no squeezing of the whole column).
    """
    xs = [0.0] * len(ys)
    placed: list[tuple[float, float]] = []
    lim = max(max_half, 0.0)
    grid = [lim * (k / 16.0) for k in range(-16, 17)] if lim > 0 else [0.0]
    for i in sorted(range(len(ys)), key=lambda k: ys[k]):
        y = ys[i]
        near = [(px, py) for px, py in placed if abs(py - y) < d]
        cands = [0.0]
        for px, py in near:
            dx = math.sqrt(d * d - (py - y) ** 2)
            cands += [px + dx, px - dx]
        cands = sorted((c for c in cands if abs(c) <= lim + 1e-9), key=lambda c: (abs(c), c))
        x = None
        for c in cands:
            if all((c - px) ** 2 + (y - py) ** 2 >= d * d - 1e-6 for px, py in near):
                x = c
                break
        if x is None:   # no free spot: least overlap, ties broken towards the centre
            x = max(grid, key=lambda c: (min((c - px) ** 2 + (y - py) ** 2 for px, py in near),
                                         -abs(c)))
        xs[i] = x
        placed.append((x, y))
    return xs


def draw_symbol(cv, shape: str, x: float, y: float, d: float, color: str) -> None:
    r = d / 2
    if shape == "circle":
        cv.circle(x, y, r, fill=color)
    elif shape == "open_circle":
        cv.circle(x, y, r - 0.4, fill="#ffffff", stroke=color, width=0.8)
    elif shape == "square":
        s = r * 0.9
        cv.rect(x - s, y - s, 2 * s, 2 * s, fill=color)
    elif shape == "open_square":
        s = r * 0.9 - 0.4
        cv.rect(x - s, y - s, 2 * s, 2 * s, fill="#ffffff", stroke=color, width=0.8)
    elif shape == "triangle":
        cv.polygon([(x, y - r * 1.1), (x + r * 1.05, y + r * 0.75), (x - r * 1.05, y + r * 0.75)], fill=color)
    elif shape == "diamond":
        cv.polygon([(x, y - r * 1.2), (x + r * 1.2, y), (x, y + r * 1.2), (x - r * 1.2, y)], fill=color)
    elif shape in ("cross", "plus"):
        w = max(1.0, d * 0.2)
        k = r * (0.95 if shape == "cross" else 1.15)
        if shape == "cross":
            cv.line(x - k, y - k, x + k, y + k, color, w, "round")
            cv.line(x - k, y + k, x + k, y - k, color, w, "round")
        else:
            cv.line(x - k, y, x + k, y, color, w, "round")
            cv.line(x, y - k, x, y + k, color, w, "round")


def _text_rect(x, y, s, fs: FontSpec, anchor="middle", rotate=0.0) -> QRectF:
    w, a, dsc = TM.width(s, fs), TM.ascent(fs), TM.descent(fs)
    dx = {"start": 0.0, "middle": -w / 2, "end": -w}[anchor]
    if rotate == -90:
        return QRectF(x - a, y - dx - w, a + dsc, w)
    if rotate:
        c, sn = math.cos(math.radians(rotate)), math.sin(math.radians(rotate))
        pts = [(dx, -a), (dx + w, -a), (dx + w, dsc), (dx, dsc)]
        xs = [x + px * c - py * sn for px, py in pts]
        ys = [y + px * sn + py * c for px, py in pts]
        return QRectF(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
    return QRectF(x + dx, y - a, w, a + dsc)


def _rect_path(*rects: QRectF) -> QPainterPath:
    p = QPainterPath()
    for r in rects:
        p.addRect(r)
    return p


# ---------------------------------------------------------------------------
# Slots: where each summary (one column, one cell, one subject) sits on the X axis
# ---------------------------------------------------------------------------

@dataclass
class Slot:
    keys: tuple                    # what brackets attach to: column, (row, column), …
    column: int                    # data set (its style)
    x: float                       # centre
    w: float                       # width available (bars take 62%, points 84%)
    summary: dict
    values: np.ndarray
    point_colors: list | None = None    # one colour per point (nested: by subject)
    marks: list = field(default_factory=list)   # big symbols: (value, colour) (subject means)
    base: float | None = None      # stacked bars start here (data units)
    force_bar: bool = False        # stacked bars
    error_dir: str | None = None   # override (stacked: above only)
    no_line: bool = False          # suppress the centre line (connected means draw a symbol)


@dataclass
class Plan:
    slots: list[Slot]
    width: float                   # plot width
    labels: list[tuple[float, str]]                 # X labels, one tick each
    groups: list[tuple[float, str]] = field(default_factory=list)   # second label line
    legend: list[int] = field(default_factory=list)
    swatch: str = "auto"           # legend swatch: auto | bar | line
    lines: dict[int, list[tuple[float, float]]] = field(default_factory=dict)  # data units


def _summary(table, r: int | None, c: int, st: DataSetStyle) -> tuple[dict, np.ndarray]:
    if table.is_summary():
        return summarize_entered(table.summary(r or 0, c), st), np.array([], float)
    x = table.values(c) if r is None else table.row_values(r, c)
    return summarize(x, st), x


def plan_column(graph, cols: list[int], colw: float) -> Plan:
    spec, t = graph.spec, graph.table
    slots = []
    for i, c in enumerate(cols):
        s, x = _summary(t, None, c, spec.style(c))
        slots.append(Slot((c,), c, (i + 0.5) * colw, colw, s, x))
    return Plan(slots, max(1, len(cols)) * colw, [(sl.x, t.label(sl.column)) for sl in slots])


def grouped_rows(t, cols: list[int]) -> list[int]:
    out = []
    for r in range(t.nrows_used()):
        if t.is_summary():
            if any(t.summary(r, c) for c in cols):
                out.append(r)
        elif any(len(t.row_values(r, c)) for c in cols):
            out.append(r)
    return out


def plan_grouped(graph, cols: list[int], colw: float) -> Plan:
    spec, t = graph.spec, graph.table
    rows = grouped_rows(t, cols)
    lay = spec.grouped_layout
    slots: list[Slot] = []
    labels, groups = [], []
    gap = colw * 0.8
    if lay == "separated":
        x0 = gap / 2
        for c in cols:
            st = spec.style(c)
            start = x0
            for r in rows:
                s, x = _summary(t, r, c, st)
                xc = x0 + colw / 2
                slots.append(Slot(((r, c),), c, xc, colw, s, x))
                labels.append((xc, t.row_label(r)))
                x0 += colw
            groups.append(((start + x0) / 2, t.label(c)))
            x0 += gap
        return Plan(slots, x0 - gap / 2, labels, groups)
    if lay in ("stacked", "stacked_pct"):
        bw = colw * 1.6
        for i, r in enumerate(rows):
            xc = gap / 2 + i * (bw + gap) + bw / 2
            means = {}
            for c in cols:
                s, _ = _summary(t, r, c, spec.style(c))
                means[c] = (s, max(s["center"] if s["center"] is not None else (s["mean"] or 0.0), 0.0))
            total = sum(m for _, m in means.values()) or 1.0
            scale = 100.0 / total if lay == "stacked_pct" else 1.0
            base = 0.0
            for c in cols:
                s, m = means[c]
                m *= scale
                err_hi = (s["hi"] - s["center"]) * scale if s["hi"] is not None and s["center"] is not None else None
                top = base + m
                st_s = {"n": s["n"], "mean": top, "center": top, "min": base, "max": top,
                        "lo": None, "hi": top + err_hi if err_hi is not None else None, "points": []}
                slots.append(Slot(((r, c),), c, xc, bw, st_s, np.array([top]), base=base,
                                  force_bar=True, error_dir="above"))
                base = top
            labels.append((xc, t.row_label(r)))
        # legend top to bottom like the stack
        return Plan(slots, len(rows) * (bw + gap), labels, legend=list(reversed(cols)), swatch="bar")
    if lay == "pyramid":                     # two data sets back to back: the first leftwards (or down)
        bw = colw * 1.6
        step = bw + gap
        for i, r in enumerate(rows):
            xc = gap / 2 + i * step + bw / 2
            for k, c in enumerate(cols):
                s, x = _summary(t, r, c, spec.style(c))
                if k == 0:
                    s, x = _negate(s), -np.asarray(x, float)
                slots.append(Slot(((r, c),), c, xc, bw, s, x))
            labels.append((xc, t.row_label(r)))
        return Plan(slots, max(1, len(rows)) * step, labels, legend=list(cols), swatch="bar")
    if lay == "lines":
        step = colw * 2.0
        lines: dict[int, list] = {c: [] for c in cols}
        for i, r in enumerate(rows):
            xc = (i + 0.5) * step
            for c in cols:
                st = spec.style(c)
                s, x = _summary(t, r, c, st)
                if s["center"] is None and s["mean"] is not None:
                    s["center"] = s["mean"]
                s["points"] = [float(v) for v in x] if spec.lines_points else []
                slots.append(Slot(((r, c),), c, xc, colw, s, x, no_line=True))
                if s["center"] is not None:
                    lines[c].append((xc, s["center"]))
            labels.append((xc, t.row_label(r)))
        return Plan(slots, max(1, len(rows)) * step, labels, legend=list(cols), swatch="line", lines=lines)
    # interleaved (default)
    x0 = gap / 2
    for r in rows:
        start = x0
        for c in cols:
            s, x = _summary(t, r, c, spec.style(c))
            slots.append(Slot(((r, c),), c, x0 + colw / 2, colw, s, x))
            x0 += colw
        labels.append(((start + x0) / 2, t.row_label(r)))
        x0 += gap
    return Plan(slots, max(x0 - gap / 2, colw), labels, legend=list(cols))


def _negate(s: dict) -> dict:
    """A summary mirrored through zero (bars extending the other way); error ends keep their
    meaning (hi stays the end away from zero)."""
    out = dict(s)
    for k in ("center", "mean", "lo", "hi", "median", "q1", "q3", "wlo", "whi"):
        if isinstance(out.get(k), (int, float)):
            out[k] = -out[k]
    if out.get("min") is not None and out.get("max") is not None:
        out["min"], out["max"] = -s["max"], -s["min"]
    out["points"] = [-v for v in s.get("points", [])]
    return out


def plan_nested(graph, cols: list[int], colw: float) -> Plan:
    from ...doc.spec import SUBJECT_COLORS
    spec, t = graph.spec, graph.table
    lay = spec.nested_layout
    slots, labels = [], []
    x0 = 0.0
    k = 0                                  # subject counter → colour, continuing across groups
    for c in cols:
        st = spec.style(c)
        subjects = []
        for sub in range(t.width()):
            f = t.flat(c, sub)
            vals = [t._ok(r, f) for r in range(len(t.y[f]))]
            vals = np.array([v for v in vals if v is not None], float)
            if len(vals):
                subjects.append((sub, vals, SUBJECT_COLORS[k % len(SUBJECT_COLORS)]))
                k += 1
        if lay == "subjects":
            sw = max(colw / max(len(subjects), 1), 5.0 * MM)
            gw = sw * max(len(subjects), 1)
            for j, (sub, vals, col) in enumerate(subjects):
                s = summarize(vals, st)
                slots.append(Slot((c, (c, sub)), c, x0 + (j + 0.5) * sw, sw, s, vals,
                                  point_colors=[col] * len(s["points"])))
            labels.append((x0 + gw / 2, t.label(c)))
            x0 += gw + colw * 0.35
            continue
        allv = np.concatenate([v for _, v, _ in subjects]) if subjects else np.array([], float)
        colors = [col for _, v, col in subjects for _ in v]
        if lay == "superplot" and subjects:
            means = np.array([v.mean() for _, v, _ in subjects])
            s = summarize(means, st)
            s["points"] = [float(v) for v in allv] if st.show_points else []
            s["min"], s["max"] = float(allv.min()), float(allv.max())
            marks = [(float(v.mean()), col) for _, v, col in subjects]
        else:
            s = summarize(allv, st)
            marks = []
        order = colors if len(s["points"]) == len(colors) else None
        slots.append(Slot((c,), c, x0 + colw / 2, colw, s, allv, point_colors=order, marks=marks))
        labels.append((x0 + colw / 2, t.label(c)))
        x0 += colw
    if lay == "subjects" and slots:
        x0 -= colw * 0.35
    return Plan(slots, max(x0, colw), labels)


# ---------------------------------------------------------------------------
# Drawing one slot
# ---------------------------------------------------------------------------

class _SlotGeom:
    """Positions and hit area of one slot, and how to draw it."""

    def __init__(self, sl: Slot, st: DataSetStyle, ym: YMap, rng: AxisRange, spec, aligned: bool):
        self.sl, self.st, self.ym = sl, st, ym
        s = sl.summary
        colw, xc = sl.w, sl.x
        self.d = d = max(1.0, st.symbol_size * 2.0)
        # "Fill" means a bar behind the points only on scatter plots; on boxes, violins and
        # floating bars it fills the shape itself.
        self.show_bar = sl.force_bar or (not sl.no_line and (
            st.appearance == "bar" or (st.bars and st.appearance == "scatter")))
        if sl.base is not None:
            self.base = ym(max(sl.base, rng.vmin) if spec.y.scale != "log10" else max(sl.base, rng.vmin))
        else:
            self.base = ym(max(rng.vmin, 0.0) if spec.y.scale != "log10" else rng.vmin)
        shape_ok = not (sl.force_bar or sl.no_line)
        self.is_box = st.appearance == "box" and s.get("wlo") is not None and shape_ok
        self.is_violin = st.appearance == "violin" and s.get("kde") is not None and shape_ok
        self.is_float = st.appearance == "floating" and shape_ok
        self.is_symbol = (st.appearance == "symbol" or sl.no_line) and not sl.force_bar
        self.ys = ys = [ym(v) for v in s["points"]]
        self.xs = [0.0] * len(ys) if aligned else swarm(ys, d * 1.05, colw * 0.42)
        self.bar_w, self.line_w, self.cap_w = colw * 0.62, colw * 0.5, colw * 0.26
        hit = [QRectF(xc + dx - d / 2, y - d / 2, d, d) for dx, y in zip(self.xs, ys)]
        if ys:
            top = min(ys) - d / 2
        else:
            ref = s["center"] if s["center"] is not None else s["max"]
            top = ym(ref) if ref is not None else ym(rng.vmin)
        md = d * 2.2
        self.mark_xs = swarm([ym(v) for v, _ in sl.marks], md * 1.05, colw * 0.3) if sl.marks else []
        for (v, _), mx in zip(sl.marks, self.mark_xs):
            hit.append(QRectF(xc + mx - md / 2, ym(v) - md / 2, md, md))
            top = min(top, ym(v) - md / 2)
        if self.is_box:
            hit.append(QRectF(xc - colw * 0.25, ym(s["whi"]), colw * 0.5, ym(s["wlo"]) - ym(s["whi"])))
            top = min(top, ym(s["whi"]))
        if self.show_bar and s["center"] is not None:
            yb = ym(s["center"])
            hit.append(QRectF(xc - self.bar_w / 2, min(yb, self.base), self.bar_w, abs(self.base - yb)))
            top = min(top, yb)
        if (self.is_violin or self.is_float) and s["min"] is not None:
            y_hi, y_lo = ym(s["max"]), ym(s["min"])
            hit.append(QRectF(xc - colw * 0.42, y_hi, colw * 0.84, y_lo - y_hi))
            top = min(top, y_hi)
        if self.is_symbol and s["center"] is not None:
            top = min(top, ym(s["center"]) - d)
        if st.errors and s["hi"] is not None and not self.is_box:
            top = min(top, ym(s["hi"]))
        lo_y = ym(s["lo"]) if s["lo"] is not None else top
        hit.append(QRectF(xc - self.line_w / 2, top, self.line_w, max(4.0, lo_y - top)))
        self.hit, self.top = hit, top

    def draw(self, cv, part: str = "all") -> None:
        """part: all | body (all but the mean's error bar) | errors (only that error bar).
        Stacked bars draw their error bars last, so the next segment doesn't cover them."""
        sl, st, ym, s = self.sl, self.st, self.ym, self.sl.summary
        if part != "errors":
            self._draw_body(cv)
        if part != "body" and st.errors and s["hi"] is not None and s["center"] is not None \
                and (st.appearance not in ("box", "violin", "floating") or sl.force_bar or sl.no_line):
            err_dir = sl.error_dir or st.error_dir
            yc, cap_w, xc = ym(s["center"]), self.cap_w, sl.x
            segs = []
            if err_dir in ("both", "above"):
                segs.append(ym(s["hi"]))
            if err_dir in ("both", "below") and s["lo"] is not None:
                segs.append(ym(s["lo"]))
            for ye in segs:
                cv.line(xc, yc, xc, ye, st.error_color, st.error_width, "butt")
                if st.error_style == "T":
                    cv.line(xc - cap_w / 2, ye, xc + cap_w / 2, ye, st.error_color, st.error_width, "butt")

    def _draw_body(self, cv) -> None:
        sl, st, ym, s = self.sl, self.st, self.ym, self.sl.summary
        xc, colw = sl.x, sl.w
        bar_w, line_w, cap_w, d = self.bar_w, self.line_w, self.cap_w, self.d
        border = max(st.bar_border, 0.25)
        err_dir = sl.error_dir or st.error_dir
        if self.is_violin:
            half = colw * 0.42
            curve = s["kde"]
            right = [(xc + dens * half, ym(v)) for v, dens in curve]
            left = [(xc - dens * half, ym(v)) for v, dens in reversed(curve)]
            cv.polygon(right + left, fill=st.bar_fill if st.bars else "#ffffff",
                       stroke=st.bar_border_color, width=border)
            vals = [cv_[0] for cv_ in curve]
            dens_ = [cv_[1] for cv_ in curve]
            ql, ml = st.violin_quartiles, st.violin_median
            for v, sty, w in ((s["q1"], ql, border), (s["q3"], ql, border), (s["center"], ml, border * 1.5)):
                if sty == "none" or v is None:
                    continue
                dash = None if sty == "solid" else sty
                hw = float(np.interp(v, vals, dens_)) * half
                cv.line(xc - hw, ym(v), xc + hw, ym(v), st.bar_border_color, w, "butt", dash)
        if self.is_float and s["min"] is not None:
            y_hi, y_lo = ym(s["max"]), ym(s["min"])
            cv.rect(xc - bar_w / 2, y_hi, bar_w, y_lo - y_hi, fill=st.bar_fill,
                    stroke=st.bar_border_color if st.bar_border > 0 else None, width=st.bar_border)
            if s["center"] is not None:
                yc = ym(s["center"])
                cv.line(xc - bar_w / 2, yc, xc + bar_w / 2, yc, st.bar_border_color, border * 1.5, "butt")
        if self.show_bar and s["center"] is not None:
            yb = ym(s["center"])
            cv.rect(xc - bar_w / 2, min(yb, self.base), bar_w, abs(self.base - yb),
                    fill=st.bar_fill, stroke=st.bar_border_color if st.bar_border > 0 else None,
                    width=st.bar_border)
        if self.is_box:
            y1, y3, ym_ = ym(s["lo"]), ym(s["hi"]), ym(s["center"])
            bw = colw * 0.5
            if st.errors:                       # whiskers
                ends = []
                if err_dir in ("both", "above"):
                    ends.append((y3, ym(s["whi"])))
                if err_dir in ("both", "below"):
                    ends.append((y1, ym(s["wlo"])))
                for y0, ye in ends:
                    cv.line(xc, y0, xc, ye, st.error_color, st.error_width, "butt")
                    if st.error_style == "T":
                        cv.line(xc - cap_w / 2, ye, xc + cap_w / 2, ye, st.error_color, st.error_width, "butt")
            cv.rect(xc - bw / 2, y3, bw, y1 - y3, fill=st.bar_fill if st.bars else "#ffffff",
                    stroke=st.bar_border_color, width=border)
            cv.line(xc - bw / 2, ym_, xc + bw / 2, ym_, st.bar_border_color, border, "butt")
            if st.mean_plus and s["mean"] is not None:
                yp, h = ym(s["mean"]), min(cap_w, bw) * 0.35
                cv.line(xc - h, yp, xc + h, yp, st.bar_border_color, border, "butt")
                cv.line(xc, yp - h, xc, yp + h, st.bar_border_color, border, "butt")
        colors = sl.point_colors if sl.point_colors and len(sl.point_colors) == len(self.ys) else None
        for j, (dx, y) in enumerate(zip(self.xs, self.ys)):
            draw_symbol(cv, st.symbol_shape, xc + dx, y, d, colors[j] if colors else st.symbol_color)
        for (v, col), mx in zip(sl.marks, self.mark_xs):     # subject means (SuperPlot)
            y = ym(v)
            draw_symbol(cv, st.symbol_shape, xc + mx, y, d * 2.2, "#000000")
            draw_symbol(cv, st.symbol_shape, xc + mx, y, d * 1.7, col)
        if (st.appearance not in ("box", "violin", "floating") or sl.force_bar or sl.no_line) \
                and s["center"] is not None:
            yc = ym(s["center"])
            if self.is_symbol:
                draw_symbol(cv, st.symbol_shape, xc, yc, d * 1.6, st.symbol_color)
            elif not self.show_bar:
                cv.line(xc - line_w / 2, yc, xc + line_w / 2, yc, st.error_color, st.error_width * 1.5, "butt")


def _key_id(k) -> str:
    if isinstance(k, tuple):
        return f"{column_letter(k[1])}{k[0] + 1}"
    return column_letter(k)


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def build(graph: Graph) -> tuple[list[Element], AxisRange]:
    """Every element of the graph, with the things drawn on it on top."""
    els, rng = _build(graph)
    if graph.spec.drawings:
        from .drawings import drawing_elements
        els = els + drawing_elements(graph.spec)
        els.sort(key=lambda e: ORDER[e.kind])
    return els, rng


def _build(graph: Graph) -> tuple[list[Element], AxisRange]:
    spec, table = graph.spec, graph.table
    if table.table_type in ("grouped", "contingency") and spec.grouped_layout == "heatmap":
        return build_heatmap(graph)
    if table.table_type == "xy":
        from .xy_layout import build_xy
        return build_xy(graph)
    if table.table_type == "multivar":
        from .multivar_layout import build_multivar
        return build_multivar(graph)
    if table.table_type == "parts":
        from .parts_survival_layout import build_parts
        return build_parts(graph)
    if table.table_type == "survival":
        from .parts_survival_layout import build_survival
        return build_survival(graph)
    cols = [c for c in table.used_columns() if c not in spec.hidden]
    colw = spec.col_width_mm * MM
    if table.table_type in ("grouped", "contingency"):     # counts: rows × outcomes, as grouped bars
        plan = plan_grouped(graph, cols, colw)
    elif table.table_type == "nested":
        plan = plan_nested(graph, cols, colw)
    else:
        plan = plan_column(graph, cols, colw)
    pw, ph = plan.width, spec.y_len_mm * MM
    aw, ac = spec.axis_width, spec.axis_color
    off = 6.0 if spec.frame == "offset" else 0.0
    yx, xy = -off, ph + off                     # where the Y and X axis lines sit

    stacked = table.table_type in ("grouped", "contingency") and spec.grouped_layout in ("stacked", "stacked_pct")
    horizontal = spec.horizontal
    right = set() if (stacked or horizontal) else {c for c in cols if spec.style(c).axis == "right"}
    rng = y_range(graph, {i: sl.summary for i, sl in enumerate(plan.slots) if sl.column not in right})
    if table.table_type in ("grouped", "contingency") and spec.grouped_layout == "stacked_pct" and spec.y.auto:
        rng = AxisRange(0.0, 100.0, 20.0)
    pyramid = table.table_type in ("grouped", "contingency") and spec.grouped_layout == "pyramid"
    if pyramid:                                 # symmetric about zero, numbered without signs
        if spec.y.auto:
            m = max(abs(rng.vmin), abs(rng.vmax))
            r_ = nice_range(0.0, m)
            rng = AxisRange(-r_.vmax, r_.vmax, r_.interval)
    ym = YMap(spec.y, rng, ph)
    if pyramid:
        ym.label = (lambda f: (lambda v: f(abs(v))))(ym.label)
    ym2 = rng2 = None
    if right:
        rng2 = y_range(graph, {i: sl.summary for i, sl in enumerate(plan.slots) if sl.column in right}, spec.y2)
        ym2 = YMap(spec.y2, rng2, ph)

    def ymap(c):
        return (ym2, rng2) if c in right else (ym, rng)
    elements: list[Element] = []

    # --- data sets (one selectable element per data set, however many slots) ---------
    joined = spec.connect_rows and not table.is_summary() and (
        table.table_type == "column" or (table.table_type == "grouped" and spec.grouped_layout == "interleaved"))
    aligned = joined
    geoms: list[_SlotGeom] = []
    by_col: dict[int, list[_SlotGeom]] = {}
    for sl in plan.slots:
        st = spec.style(sl.column)
        if st.nudge:
            sl.x += st.nudge
        if not len(sl.values) and sl.summary["center"] is not None:
            sl.values = np.array([sl.summary["center"]])     # entered mean/error: no raw values
        if not len(sl.values) and not sl.marks:
            continue
        m_, r_ = ymap(sl.column)
        g = _SlotGeom(sl, st, m_, r_, spec, aligned or st.spread == "aligned")
        geoms.append(g)
        by_col.setdefault(sl.column, []).append(g)
    for c, gs in by_col.items():
        st = spec.style(c)
        pts = [(x_ + st.nudge, v) for x_, v in plan.lines.get(c, [])]

        part = "body" if stacked else "all"

        def draw_ds(cv, gs=gs, pts=pts, st=st, part=part, m_=ymap(c)[0]):
            if len(pts) > 1:
                cv.polyline([(x_, m_(v)) for x_, v in pts], st.symbol_color, max(st.error_width, 1.0), "round")
            for g in gs:
                g.draw(cv, part)
        hit = _rect_path(*[r for g in gs for r in g.hit])
        elements.append(Element(f"data-{column_letter(c)}", "dataset",
                                hit.boundingRect().adjusted(-2, -2, 2, 2), draw_ds, hit,
                                {"column": c, "label": table.label(c)}))

    if stacked and geoms:
        def draw_errs(cv, geoms=geoms):
            for g in geoms:
                g.draw(cv, "errors")
        eb = QRectF()
        for g in geoms:
            eb = eb.united(QRectF(g.sl.x - 2, g.top - 2, 4, 4))
        elements.append(Element("error-bars", "errors", eb, draw_errs, QPainterPath(), {}))

    # --- lines joining each row's values across data sets (before-after) -----
    if joined and len(cols) > 1:
        lines = []
        if table.table_type == "grouped":         # each replicate, across the data sets of a group
            xpos = {sl.keys[0]: sl.x for sl in plan.slots}
            for r in sorted({k[0] for k in xpos}):
                for sub in range(table.width()):
                    pts = []
                    for c in cols:
                        v = table._ok(r, table.flat(c, sub))
                        if v is not None and (r, c) in xpos:
                            pts.append((xpos[(r, c)], ymap(c)[0](float(v))))
                        elif pts:
                            if len(pts) > 1:
                                lines.append(pts)
                            pts = []
                    if len(pts) > 1:
                        lines.append(pts)
        xpos = {sl.column: sl.x for sl in plan.slots}
        for r in range(table.nrows_used() if table.table_type == "column" else 0):
            pts = []
            for c in cols:
                v = table.row_values(r, c)
                if len(v) == 1:
                    pts.append((xpos[c], ymap(c)[0](float(v[0]))))
                elif pts:
                    if len(pts) > 1:
                        lines.append(pts)
                    pts = []
            if len(pts) > 1:
                lines.append(pts)
        if lines:
            cc, cw_ = spec.connect_color, spec.connect_width

            def draw_lines(cv, lines=lines):
                for pts in lines:
                    cv.polyline(pts, cc, cw_, "round")
            box = QRectF()
            for pts in lines:
                for x_, y_ in pts:
                    box = box.united(QRectF(x_ - 1, y_ - 1, 2, 2))
            elements.append(Element("connecting-lines", "lines", box, draw_lines, _rect_path(box), {}))

    # --- before-after: mean (or median) with error beside each data set ------------
    if spec.connect_rows and spec.ba_summary != "none" and table.table_type == "column" and geoms:
        import copy as _copy
        marks = []
        n_slots = len(plan.slots)
        for i, g in enumerate(geoms):
            st = _copy.copy(g.st)
            st.line_at = spec.ba_summary
            sm = summarize(np.asarray(g.sl.values, float), st)
            if sm["center"] is None:
                continue
            side = -1.0 if (i == 0 and n_slots > 1) else 1.0         # outward on the first data set
            x = g.sl.x + side * g.sl.w * 0.42
            m_ = ymap(g.sl.column)[0]
            marks.append((x, m_(sm["center"]), m_(sm["lo"]) if sm["lo"] is not None else None,
                          m_(sm["hi"]) if sm["hi"] is not None else None, g.st))
        if marks:
            def draw_marks(cv, marks=marks):
                for x, yc, ylo, yhi, st in marks:
                    cap = 3.0
                    for ye in (ylo, yhi):
                        if ye is not None:
                            cv.line(x, yc, x, ye, st.error_color, st.error_width, "butt")
                            cv.line(x - cap, ye, x + cap, ye, st.error_color, st.error_width, "butt")
                    draw_symbol(cv, "square", x, yc, max(4.0, st.symbol_size * 2.2), st.symbol_color)
            box = QRectF()
            for x, yc, ylo, yhi, _st in marks:
                box = box.united(QRectF(x - 4, min(v for v in (yc, ylo, yhi) if v is not None) - 2, 8,
                                        abs(max(v for v in (yc, ylo, yhi) if v is not None)
                                            - min(v for v in (yc, ylo, yhi) if v is not None)) + 4))
            elements.append(Element("summary-beside", "errors", box, draw_marks, QPainterPath(), {}))

    # --- grid lines, extra ticks, axis break -------------------------------------
    elements += _guides(spec, ym, pw, ph, ym2)

    # --- Y axes -------------------------------------------------------------
    y_el, num_left = _y_axis(spec, ym, ph, yx)
    elements.append(y_el)
    legend_x = pw + 12.0
    if ym2 is not None:
        y2_el, num_right = _y_axis(spec, ym2, ph, pw + off, "right")
        elements.append(y2_el)
        t2 = _y_title(spec, num_right, ph, "right")
        elements += t2
        legend_x = max(num_right, *(e.bounds.right() for e in t2)) + 12.0 if t2 else num_right + 12.0

    # --- X axis -------------------------------------------------------------
    elements.append(_x_axis(spec, plan.labels, plan.groups, pw, xy, yx))

    if spec.frame == "box":
        elements.append(_frame(spec, pw, ph, ym, right_axis=ym2 is not None))

    # --- Y title ------------------------------------------------------------
    elements += _y_title(spec, num_left, ph)

    # --- legend ---------------------------------------------------------------
    if spec.show_legend and plan.legend and len(plan.legend) > 0:
        elements.append(_legend(spec, table, plan, legend_x, 0.0))

    # --- brackets -------------------------------------------------------------
    tops = [(g.sl.x, g.top) for g in geoms]
    anchors: dict = {}
    for g in geoms:
        for k in g.sl.keys:
            xs_, t_ = anchors.get(k, ([], 0.0))
            anchors[k] = (xs_ + [g.sl.x], min(t_, g.top) if xs_ else g.top)
    anchors = {k: (sum(xs_) / len(xs_), t_) for k, (xs_, t_) in anchors.items()}
    content_top = min((t_ for _, t_ in tops), default=0.0)
    content_top = min(content_top, 0.0)
    if spec.show_brackets:
        for gid, br, draw_br, label, fs_lab in _brackets(graph, anchors, tops, ac, aw):
            elements.append(Element(gid, "bracket", br, draw_br, _rect_path(br),
                                    {"font_keys": ["bracket", "stars"], "label": label, "label_font": fs_lab}))
            content_top = min(content_top, br.top())

    # --- horizontal: the same graph turned on its side --------------------------
    if horizontal:
        from .horizontal import horizontalize
        legend = (table, plan) if spec.show_legend and plan.legend else None
        elements = horizontalize(spec, elements, plan, ym, ph, off, legend)
        content_top = min([0.0] + [e.bounds.top() for e in elements if e.kind in ("dataset", "bracket")])
        elements += _title(spec, graph, ph, content_top)
        elements.sort(key=lambda e: ORDER[e.kind])
        return elements, rng

    # --- graph title ----------------------------------------------------------
    content_top = min([content_top] + [e.bounds.top() for e in elements if e.id == "y-title"])
    elements += _title(spec, graph, pw, content_top)

    elements.sort(key=lambda e: ORDER[e.kind])
    return elements, rng


def _y_axis(spec, ym: YMap, ph: float, yx: float, side: str = "left") -> tuple[Element, float]:
    """A Y axis line (in pieces when broken), ticks and numbers; returns the element and the
    numbers' outer edge (left edge for the left axis, right edge for the right one)."""
    right = side == "right"
    ay = spec.y2 if right else spec.y
    aw, ac = spec.axis_width, spec.axis_color
    tl = TICK_LEN[ay.ticks_len]
    out_len = tl if ay.ticks_dir in ("out", "cross") else 0.0
    in_len = tl if ay.ticks_dir in ("in", "cross") else 0.0
    sgn = 1.0 if right else -1.0                  # outward direction
    fs_num = spec.fonts["y_numbers"]
    majors = ym.majors()
    labels = [ym.label(v) for v in majors]
    num_w = max((TM.width(s, fs_num) for s in labels), default=0.0) if ay.numbering else 0.0
    num_x = yx + sgn * (out_len + 3.0)
    edge = num_x + sgn * num_w

    def draw_y(cv):
        for top, bot in ym.segments():
            cv.line(yx, top, yx, bot, ac, aw)
        g = ym.gap()
        if g:                                     # break marks: short slashes at both ends of the gap
            for y in g:
                cv.line(yx - 4, y + 2, yx + 4, y - 2, ac, aw, "butt")
        if ay.ticks_dir != "none":
            for v in majors:
                y = ym(v)
                cv.line(yx + sgn * out_len, y, yx - sgn * in_len, y, ac, aw)
            for v in ym.minors():
                y = ym(v)
                cv.line(yx + sgn * out_len * 0.55, y, yx - sgn * in_len * 0.55, y, ac, aw)
        if ay.numbering:
            capc = TM.cap_height(fs_num) / 2
            for v, s in zip(majors, labels):
                cv.text(num_x, ym(v) + capc, s, fs_num, anchor="start" if right else "end")

    x0, x1 = sorted((edge + 2 * sgn, yx - sgn * (in_len + 5)))
    yb = QRectF(x0, -TM.ascent(fs_num) / 2 - 2, x1 - x0, ph + TM.ascent(fs_num) + 4)
    gid = "y2-axis" if right else "y-axis"
    return Element(gid, "y-axis", yb, draw_y, _rect_path(yb), {"font_keys": ["y_numbers"], "range": ym.r}), edge


def _frame(spec, pw: float, ph: float, ym: YMap, right_axis: bool = False) -> Element:
    """Top and right lines of a boxed graph (the right one broken like the Y axis)."""
    aw, ac = spec.axis_width, spec.axis_color

    def draw_frame(cv):
        cv.line(0, 0, pw, 0, ac, aw)
        if not right_axis:
            for top, bot in ym.segments():
                cv.line(pw, top, pw, bot, ac, aw)
    fb = QRectF(-2, -2, pw + 4, ph + 4)
    hit = _rect_path(QRectF(-2, -2, pw + 4, 4), QRectF(pw - 2, -2, 4, ph + 4))
    return Element("frame", "frame", fb, draw_frame, hit)


def _y_title(spec, num_left: float, ph: float, side: str = "left") -> list[Element]:
    fs_yt = spec.fonts["y_title"]
    right = side == "right"
    ay = spec.y2 if right else spec.y
    if not ay.title:
        return []
    key = "y2-title" if right else "y-title"
    dx, dy = spec.offsets.get(key, (0.0, 0.0))
    if right:
        tx = num_left + 6.0 + TM.ascent(fs_yt) + dx
    else:
        tx = num_left - 6.0 - TM.descent(fs_yt) + dx
    ty = ph / 2 + dy

    def draw_yt(cv, tx=tx, ty=ty):
        cv.text(tx, ty, ay.title, fs_yt, anchor="middle", rotate=-90)
    r = _text_rect(tx, ty, ay.title, fs_yt, "middle", -90)
    return [Element(key, "text", r, draw_yt, _rect_path(r),
                    {"font_keys": ["y_title"], "field": "y2_title" if right else "y_title", "text": ay.title,
                     "rotate": -90, "anchor_pt": (tx, ty)})]


def _guides(spec, ym: YMap, pw: float, ph: float, ym2: YMap | None = None, xm=None) -> list[Element]:
    """Grid lines at major ticks and extra ticks / lines at chosen values (behind the data),
    plus the white band that carries an axis break across the plot."""
    out = []
    bands = []          # (x, y, w, h, color)
    lines = []          # (x1, y1, x2, y2, color, width, dash)
    labels = []         # (x, y, text, anchor)
    fs = spec.fonts["y_numbers"]
    for ax, m, side in ((spec.y, ym, "left"), (spec.y2, ym2, "right")):
        if m is None:
            continue
        if ax.grid:
            for v in m.majors():
                y = m(v)
                if 0.5 < y < ph + 0.5 or ax.grid:
                    lines.append((0.0, y, pw, y, ax.grid_color, ax.grid_width, None))
        for e in ax.extra or []:
            try:
                v = float(e.get("value"))
            except (TypeError, ValueError):
                continue
            y = m(v)
            to = e.get("to")
            if to not in (None, ""):                 # a shaded band from value to "to"
                try:
                    y2 = m(float(to))
                except (TypeError, ValueError):
                    y2 = None
                if y2 is not None:
                    top, bot = max(min(y, y2), 0.0), min(max(y, y2), ph)
                    if bot > top:
                        bands.append((0.0, top, pw, bot - top, e.get("band_color") or "#e6e6e6"))
                    if e.get("label"):
                        labels.append((pw - 2.0 if side == "right" else 2.0, top + TM.ascent(fs) + 1.0,
                                       e["label"], "end" if side == "right" else "start"))
                    continue
            if not (-0.5 <= y <= ph + 0.5):
                continue
            dash = None if e.get("dash", "dash") == "solid" else e.get("dash", "dash")
            col = e.get("color") or spec.axis_color
            if e.get("line", True):
                lines.append((0.0, y, pw, y, col, float(e.get("width", spec.axis_width)), dash))
            if e.get("tick", False):
                x0 = pw if side == "right" else 0.0
                d = 6.0 if side == "right" else -6.0
                lines.append((x0, y, x0 + d, y, spec.axis_color, spec.axis_width, None))
            if e.get("label"):
                if side == "right":
                    labels.append((pw - 2.0, y - 3.0, e["label"], "end"))
                else:
                    labels.append((2.0, y - 3.0, e["label"], "start"))
    if xm is not None:
        ax = spec.x
        if ax.grid:
            for v in xm.majors():
                x = xm(v)
                lines.append((x, 0.0, x, ph, ax.grid_color, ax.grid_width, None))
        for e in ax.extra or []:
            try:
                x = xm(float(e.get("value")))
            except (TypeError, ValueError):
                continue
            if not (-0.5 <= x <= pw + 0.5):
                continue
            dash = None if e.get("dash", "dash") == "solid" else e.get("dash", "dash")
            if e.get("line", True):
                lines.append((x, 0.0, x, ph, e.get("color") or spec.axis_color,
                              float(e.get("width", spec.axis_width)), dash))
            if e.get("label"):
                labels.append((x + 3.0, TM.ascent(fs) + 1.0, e["label"], "start"))
    if lines or labels or bands:
        def draw_guides(cv, lines=lines, labels=labels, bands=bands):
            for x, y, w, h, c in bands:
                cv.rect(x, y, w, h, fill=c)
            for x1, y1, x2, y2, c, w, dash in lines:
                cv.line(x1, y1, x2, y2, c, w, "butt", dash)
            for x, y, t, anchor in labels:
                cv.text(x, y, t, fs, anchor=anchor)
        box = QRectF(0, 0, pw, ph)
        out.append(Element("guides", "grid", box, draw_guides, QPainterPath(), {}))
    gaps = [g for g in (ym.gap(), ym2.gap() if ym2 else None) if g]
    if gaps:
        def draw_gap(cv, gaps=gaps):
            for top, bot in gaps:
                cv.rect(0.5, top + 0.5, pw - 0.5, max(bot - top - 1.0, 0.1), fill="#ffffff", stroke=None)
        out.append(Element("axis-break", "gap", QRectF(0, 0, pw, ph), draw_gap, QPainterPath(), {}))
    return out


# z-order: data underneath, axes, then annotations on top
ORDER = {"grid": -2, "lines": -1, "dataset": 0, "gap": 0.8, "drawing": 3.5, "curve": 0.3, "errors": 0.5, "frame": 1, "x-axis": 2, "y-axis": 2, "bracket": 3,
         "legend": 3, "text": 4}


def _x_axis(spec, x_labels, groups, pw, xy, yx) -> Element:
    ax, aw, ac = spec.x, spec.axis_width, spec.axis_color
    xtl = TICK_LEN[ax.ticks_len]
    down = xtl if ax.ticks_dir in ("out", "cross") else 0.0
    up = xtl if ax.ticks_dir in ("in", "cross") else 0.0
    fs_x = spec.fonts["x_labels"]
    rot = -ax.label_rotation
    if rot == 0 and _crowded(x_labels, fs_x):
        rot = -45                               # labels would overlap: tilt them
    lab_y = xy + down + 3.0
    x_rects, placements = [], []
    for xc, s in x_labels:
        if rot == 0:
            px, py, anchor = xc, lab_y + TM.ascent(fs_x), "middle"
        elif rot == -45:
            px, py, anchor = xc + TM.ascent(fs_x) * 0.35, lab_y + TM.ascent(fs_x) * 0.55, "end"
        else:
            px, py, anchor = xc + TM.cap_height(fs_x) / 2, lab_y, "end"
        placements.append((px, py, s, anchor))
        x_rects.append(_text_rect(px, py, s, fs_x, anchor, rot))
    x_start = yx if spec.frame != "offset" else 0.0
    bottom = max((r.bottom() for r in x_rects), default=lab_y)
    group_place = []
    for xc, s in groups:                       # second line: the group each label belongs to
        py = bottom + 4.0 + TM.ascent(fs_x)
        group_place.append((xc, py, s))
        x_rects.append(_text_rect(xc, py, s, fs_x, "middle"))

    def draw_x(cv):
        cv.line(x_start, xy, pw, xy, ac, aw)
        if ax.ticks_dir != "none":
            for xc, _ in x_labels:
                cv.line(xc, xy - up, xc, xy + down, ac, aw)
        for px, py, s, anchor in placements:
            cv.text(px, py, s, fs_x, anchor=anchor, rotate=rot)
        for px, py, s in group_place:
            cv.text(px, py, s, fs_x, anchor="middle")

    xb = QRectF(x_start - 2, xy - up - 3, pw - x_start + 4, down + up + 6)
    for r in x_rects:
        xb = xb.united(r)
    return Element("x-axis", "x-axis", xb, draw_x, _rect_path(xb), {"font_keys": ["x_labels"]})


def _crowded(x_labels, fs) -> bool:
    pos = sorted((x, TM.width(s, fs)) for x, s in x_labels)
    return any(b[0] - a[0] < (a[1] + b[1]) / 2 + 3.0 for a, b in zip(pos, pos[1:]))


def _legend(spec, table, plan: Plan, x0: float, y0: float) -> Element:
    fs = spec.fonts["legend"]
    dx, dy = spec.offsets.get("legend", (0.0, 0.0))
    x0, y0 = x0 + dx, y0 + dy
    row_h = max(TM.ascent(fs) + TM.descent(fs), 9.0) + 4.0
    sw = 12.0
    entries = []
    shown = [c for c in plan.legend if spec.style(c).legend]
    for i, c in enumerate(shown):
        st = spec.style(c)
        kind = plan.swatch
        if kind == "auto":
            barish = st.appearance in ("bar", "box", "violin", "floating") or (st.bars and st.appearance == "scatter")
            kind = "bar" if barish else "symbol"
        entries.append((y0 + i * row_h, table.label(c), st, kind))
    width = sw + 5.0 + max((TM.width(s, fs) for _, s, _, _ in entries), default=0.0)

    def draw_legend(cv):
        for y, s, st, kind in entries:
            yc = y + row_h / 2
            if kind == "bar":
                cv.rect(x0, yc - 4.5, sw, 9.0, fill=st.bar_fill,
                        stroke=st.bar_border_color if st.bar_border > 0 else None, width=max(st.bar_border, 0.25))
            elif kind == "line":
                cv.line(x0, yc, x0 + sw, yc, st.symbol_color, max(st.error_width, 1.0), "butt")
                draw_symbol(cv, st.symbol_shape, x0 + sw / 2, yc, max(1.0, st.symbol_size * 2.0), st.symbol_color)
            else:
                draw_symbol(cv, st.symbol_shape, x0 + sw / 2, yc, max(1.0, st.symbol_size * 2.0) * 1.3, st.symbol_color)
            cv.text(x0 + sw + 5.0, yc + TM.cap_height(fs) / 2, s, fs, anchor="start")
    box = QRectF(x0 - 1, y0, width + 2, row_h * len(entries))
    return Element("legend", "legend", box, draw_legend, _rect_path(box), {"font_keys": ["legend"]})


def sig_settings(spec) -> dict:
    """The graph's significance options, with the older fields (p_format, brackets_ns) still
    honoured."""
    sig = dict(spec.sig)
    if spec.p_format == "exact" and sig.get("label") == "stars":
        sig["label"] = "p"
    if spec.brackets_ns and sig.get("which") == "significant":
        sig["which"] = "all"
    return sig


STAR_LEVELS = {"four": [0.05, 0.01, 0.001, 0.0001], "three": [0.05, 0.01, 0.001],
               "gp": [0.0332, 0.0021, 0.0002, 0.0001]}


def star_label(p: float, sig: dict) -> str:
    cuts = STAR_LEVELS.get(sig.get("levels", "four"), sig.get("cuts") or STAR_LEVELS["four"])
    n = sum(1 for c in sorted(cuts, reverse=True) if p < c)
    n = min(n, int(sig.get("max_stars", 4) or 4))
    return "*" * n if n else "ns"


def bracket_label(p: float, sig: dict) -> str:
    stars = star_label(p, sig)
    exact = "P < 0.0001" if p < 0.0001 else f"P = {fmt_p(p)}"
    return {"stars": stars, "p": exact, "number": "<0.0001" if p < 0.0001 else fmt_p(p),
            "both": f"{stars}  {exact}"}.get(sig.get("label", "stars"), stars)


def bracket_id(ka, kb) -> str:
    return f"bracket-{_key_id(ka)}-{_key_id(kb)}"


def _comparisons(graph, anchors: dict) -> list[tuple]:
    """(key a, key b, P) for every comparison to draw, in the analysis's order. A two-group
    test shows its result (also "ns", unless switched off); multiple comparisons follow the
    'which' choice: all, the significant ones, those against a control, or none. Brackets
    hidden one by one are left out."""
    sig = sig_settings(graph.spec)
    alpha = float(sig.get("alpha", 0.05))
    hidden = set(sig.get("hidden") or [])
    which, control = sig.get("which", "significant"), sig.get("control")
    comps = []
    for a in graph.analyses():
        r = a.result
        if r is None or r.error or not a.params.get("bracket", True):
            continue
        multi = len(r.comparisons) > 1 or a.analysis_type == "anova1"
        cand = [(ca, cb, pv, multi) for ca, cb, pv in r.comparisons]
        cand += [(ka, kb, pv, True) for ka, kb, pv in r.cell_comparisons]
        if a.analysis_type == "multiple_t" and len(a.columns) == 2:
            ca, cb = a.columns
            cand += [((row, ca), (row, cb), padj, True) for row, _p, padj in r.rows]
        for ka, kb, pv, m in cand:
            if ka not in anchors or kb not in anchors or abs(anchors[ka][0] - anchors[kb][0]) <= 1e-6:
                continue
            if bracket_id(ka, kb) in hidden:
                continue
            if not m:
                if pv >= alpha and not sig.get("ns_single", True):
                    continue
            elif which == "none":
                continue
            elif which == "significant" and pv >= alpha:
                continue
            elif which == "control":
                col = lambda k: k[1] if isinstance(k, tuple) else k
                if control not in (col(ka), col(kb)):
                    continue
            comps.append((ka, kb, pv))
    return comps


def _brackets(graph, anchors: dict, tops: list, ac: str, aw: float):
    spec = graph.spec
    sig = sig_settings(spec)
    fs_b = spec.fonts["bracket"]
    fs_s = spec.fonts.get("stars", fs_b)
    color = sig.get("color") or ac
    width = float(sig.get("width") or 0) or aw
    tick = float(sig.get("tick", 4.5)) if sig.get("shape", "bracket") == "bracket" else 0.0
    gap = float(sig.get("label_gap", 2.5))
    comps = _comparisons(graph, anchors)
    if sig.get("order", "shortest") == "shortest":   # narrow spans lowest
        comps.sort(key=lambda t: (abs(anchors[t[1]][0] - anchors[t[0]][0]), min(anchors[t[0]][0], anchors[t[1]][0])))
    placed: list[tuple[float, float, float]] = []        # (x1, x2, y)
    step = max(TM.ascent(fs_b), TM.ascent(fs_s)) + float(sig.get("level_gap", 9.0)) + gap - 2.5
    out = []
    for ka, kb, pv in comps:
        x1, x2 = sorted((anchors[ka][0], anchors[kb][0]))
        span_top = min([t_ for x_, t_ in tops if x1 - 1e-6 <= x_ <= x2 + 1e-6] +
                       [anchors[ka][1], anchors[kb][1]])
        y = span_top - float(sig.get("distance", 8.0))
        moved = True
        while moved:
            moved = False
            for px1, px2, py in placed:
                if px1 - 2 < x2 and x1 < px2 + 2 and y > py - step + 0.01:
                    y = py - step
                    moved = True
        placed.append((x1, x2, y))
        label = bracket_label(pv, sig)
        fs = fs_s if sig.get("label", "stars") == "stars" else fs_b
        gid = bracket_id(ka, kb)
        dx, dy = spec.offsets.get(gid, (0.0, 0.0))
        ytop = y + dy

        def draw_br(cv, x1=x1 + dx, x2=x2 + dx, ytop=ytop, label=label, fs=fs):
            if tick > 0:
                cv.polyline([(x1, ytop + tick), (x1, ytop), (x2, ytop), (x2, ytop + tick)], color, width, "butt")
            else:
                cv.line(x1, ytop, x2, ytop, color, width, "butt")
            cv.text((x1 + x2) / 2, ytop - gap, label, fs, color=color, anchor="middle")
        tr = _text_rect((x1 + x2) / 2 + dx, ytop - gap, label, fs, "middle")
        br = QRectF(x1 + dx - 1, ytop - 1, (x2 - x1) + 2, max(tick, 2.0) + 2).united(tr)
        out.append((gid, br, draw_br, label, fs))
    return out


def _title(spec, graph, pw: float, content_top: float) -> list[Element]:
    fs_t = spec.fonts["title"]
    title = spec.title or graph.table.name
    if not (spec.show_title and title):
        return []
    dx, dy = spec.offsets.get("graph-title", (0.0, 0.0))
    tx, ty = pw / 2 + dx, content_top - 10.0 - TM.descent(fs_t) + dy

    def draw_t(cv, tx=tx, ty=ty):
        cv.text(tx, ty, title, fs_t, anchor="middle")
    r = _text_rect(tx, ty, title, fs_t, "middle")
    return [Element("graph-title", "text", r, draw_t, _rect_path(r),
                    {"font_keys": ["title"], "field": "title", "text": title,
                     "rotate": 0, "anchor_pt": (tx, ty)})]


# ---------------------------------------------------------------------------
# Heat map (grouped tables): rows down, data sets across, colour = mean
# ---------------------------------------------------------------------------

def _mix_hex(a: str, b: str, t: float) -> str:
    a, b = a.lstrip("#"), b.lstrip("#")
    ca = [int(a[i:i + 2], 16) for i in (0, 2, 4)]
    cb = [int(b[i:i + 2], 16) for i in (0, 2, 4)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ca, cb))


def build_heatmap(graph) -> tuple[list[Element], AxisRange]:
    spec, t = graph.spec, graph.table
    cols = [c for c in t.used_columns() if c not in spec.hidden]
    rows = grouped_rows(t, cols)
    cw = spec.col_width_mm * MM * 1.6
    rh = min(cw, spec.y_len_mm * MM / max(len(rows), 1))
    grid: dict[tuple[int, int], float] = {}
    for r in rows:
        for c in cols:
            if t.is_summary():
                sm = t.summary(r, c)
                if sm:
                    grid[(r, c)] = sm["mean"]
            else:
                v = t.row_values(r, c)
                if len(v):
                    grid[(r, c)] = float(v.mean())
    vals = list(grid.values()) or [0.0, 1.0]
    if spec.y.auto:
        lo, hi = min(vals), max(vals)
    else:
        lo, hi = spec.y.vmin, spec.y.vmax
    if hi <= lo:
        hi = lo + 1.0
    rng = AxisRange(lo, hi, (hi - lo) / 4)
    pw, ph = cw * len(cols), rh * len(rows)
    elements: list[Element] = []
    ac, aw = spec.axis_color, spec.axis_width

    def color(v):
        return _mix_hex(spec.heat_low, spec.heat_high, min(max((v - lo) / (hi - lo), 0.0), 1.0))

    def draw_cells(cv):
        for i, r in enumerate(rows):
            for j, c in enumerate(cols):
                v = grid.get((r, c))
                cv.rect(j * cw, i * rh, cw, rh, fill=color(v) if v is not None else "#ffffff",
                        stroke="#ffffff", width=0.75)
    box = QRectF(0, 0, pw, ph)
    elements.append(Element("data-heat", "dataset", box, draw_cells, _rect_path(box),
                            {"column": cols[0] if cols else 0, "label": "Heat map"}))
    fs_y = spec.fonts["y_numbers"]
    rlabels = [(i, t.row_label(r)) for i, r in enumerate(rows)]

    def draw_rows(cv):
        for i, s in rlabels:
            cv.text(-4.0, (i + 0.5) * rh + TM.cap_height(fs_y) / 2, s, fs_y, anchor="end")
    lw = max((TM.width(s, fs_y) for _, s in rlabels), default=0.0)
    yb = QRectF(-4.0 - lw - 2, -2, lw + 6, ph + 4)
    elements.append(Element("y-axis", "y-axis", yb, draw_rows, _rect_path(yb), {"font_keys": ["y_numbers"]}))
    xspec = copy.deepcopy(spec)
    xspec.x.ticks_dir = "none"
    xax = _x_axis(xspec, [((j + 0.5) * cw, t.label(c)) for j, c in enumerate(cols)], [], pw, ph, 0.0)
    xax_draw = xax.draw

    def draw_x_no_line(cv, inner=xax_draw):
        inner(_NoLine(cv, ph))
    xax.draw = draw_x_no_line
    elements.append(xax)
    # colour scale
    fs_l = spec.fonts["legend"]
    sx, sh = pw + 14.0, min(ph, 90.0)
    lab_hi, lab_lo = f"{hi:.3g}", f"{lo:.3g}"
    dx, dy = spec.offsets.get("legend", (0.0, 0.0))

    def draw_scale(cv, sx=sx + dx, sy=dy):
        n = 24
        for k in range(n):
            cv.rect(sx, sy + sh * k / n, 10.0, sh / n + 0.3, fill=_mix_hex(spec.heat_high, spec.heat_low, k / (n - 1)))
        cv.rect(sx, sy, 10.0, sh, fill=None, stroke=ac, width=0.5)
        cv.text(sx + 14.0, sy + TM.cap_height(fs_l), lab_hi, fs_l, anchor="start")
        cv.text(sx + 14.0, sy + sh, lab_lo, fs_l, anchor="start")
    sb = QRectF(sx + dx - 1, dy - 1, 16.0 + max(TM.width(lab_hi, fs_l), TM.width(lab_lo, fs_l)), sh + 2)
    elements.append(Element("legend", "legend", sb, draw_scale, _rect_path(sb), {"font_keys": ["legend"]}))
    elements += _title(spec, graph, pw, 0.0)
    elements.sort(key=lambda e: ORDER[e.kind])
    return elements, rng


class _NoLine:
    """Canvas proxy that skips the X axis line itself (heat maps have labels only)."""

    def __init__(self, cv, y):
        self.cv, self.y = cv, y

    def line(self, x1, y1, x2, y2, *a, **k):
        if abs(y1 - self.y) < 1e-6 and abs(y2 - self.y) < 1e-6:
            return
        self.cv.line(x1, y1, x2, y2, *a, **k)

    def __getattr__(self, name):
        return getattr(self.cv, name)


def content_bounds(elements: list[Element], margin: float = 3.0) -> QRectF:
    b = QRectF()
    for e in elements:
        b = b.united(e.bounds)
    return b.adjusted(-margin, -margin, margin, margin)
