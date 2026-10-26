"""Horizontal column and grouped graphs: the vertical layout turned on its side.

Data, error bars, brackets, grid lines and the break band are drawn through a canvas that
maps (x, y) → (ph − y, x): categories run down the page (the first at the top) and values
grow to the right from the baseline at x = 0. Text stays upright. The value axis (along the
bottom) and the category labels (down the left) are built afresh.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QTransform

from .canvas import TextMetrics as TM


class FlipCanvas:
    def __init__(self, cv, ph: float):
        self.cv, self.ph = cv, ph

    def _p(self, x, y):
        return self.ph - y, x

    def line(self, x1, y1, x2, y2, *a, **k):
        X1, Y1 = self._p(x1, y1)
        X2, Y2 = self._p(x2, y2)
        self.cv.line(X1, Y1, X2, Y2, *a, **k)

    def polyline(self, pts, *a, **k):
        self.cv.polyline([self._p(x, y) for x, y in pts], *a, **k)

    def polygon(self, pts, *a, **k):
        self.cv.polygon([self._p(x, y) for x, y in pts], *a, **k)

    def rect(self, x, y, w, h, *a, **k):
        X, Y = self._p(x, y + h)
        self.cv.rect(X, Y, h, w, *a, **k)

    def shape(self, kind, x, y, w, h, *a, **k):
        X, Y = self._p(x, y + h)
        self.cv.shape(kind, X, Y, h, w, *a, **k)

    def circle(self, cx, cy, r, *a, **k):
        X, Y = self._p(cx, cy)
        self.cv.circle(X, Y, r, *a, **k)

    def image(self, x, y, w, h, png):
        X, Y = self._p(x, y + h)
        self.cv.image(X, Y, h, w, png)

    def text(self, x, y, s, fs, color=None, anchor="start", rotate=0.0):
        # upright, starting at the mapped point and centred on it vertically
        X, Y = self._p(x, y)
        self.cv.text(X + 2.0, Y + TM.cap_height(fs) / 2, s, fs, color=color, anchor="start")

    def begin_group(self, *a, **k):
        self.cv.begin_group(*a, **k)

    def end_group(self):
        self.cv.end_group()

    def __getattr__(self, name):
        return getattr(self.cv, name)


FLIPPED = ("dataset", "errors", "lines", "bracket", "grid", "gap", "curve")


def transform(ph: float) -> QTransform:
    """(x, y) → (ph − y, x)."""
    return QTransform(0.0, 1.0, -1.0, 0.0, ph, 0.0)


def horizontalize(spec, elements, plan, ym, ph: float, off: float, legend_entries):
    """Turn a vertical column/grouped graph's elements on their side; returns the new list
    and the horizontal extent (for the title)."""
    from .layout import Element, _legend, _rect_path, _text_rect, TICK_LEN
    T = transform(ph)
    W = plan.width
    out = []
    for e in elements:
        if e.kind in FLIPPED:
            def draw(cv, d=e.draw):
                d(FlipCanvas(cv, ph))
            hit = T.map(e.hit) if e.hit is not None else e.hit
            b = T.mapRect(e.bounds)
            if e.kind == "bracket" and e.meta.get("label"):     # the upright label is wider than it was tall
                b.setRight(b.right() + TM.width(e.meta["label"], e.meta["label_font"]) + 4.0)
            out.append(Element(e.id, e.kind, b, draw, hit, {**e.meta, "flipped": True}))
    aw, ac = spec.axis_width, spec.axis_color

    # value axis along the bottom (the Y axis's settings, numbers and title)
    ay = spec.y
    tl = TICK_LEN[ay.ticks_len]
    down = tl if ay.ticks_dir in ("out", "cross") else 0.0
    up = tl if ay.ticks_dir in ("in", "cross") else 0.0
    yb = W + off
    fs_n = spec.fonts["y_numbers"]
    majors = ym.majors()
    labels = [ym.label(v) for v in majors]
    num_y = yb + down + 3.0 + TM.ascent(fs_n)

    def draw_v(cv):
        for top, bot in ym.segments():
            cv.line(ph - bot, yb, ph - top, yb, ac, aw)
        g = ym.gap()
        if g:
            for y in g:
                cv.line(ph - y - 2, yb + 4, ph - y + 2, yb - 4, ac, aw, "butt")
        if ay.ticks_dir != "none":
            for v in majors:
                cv.line(ph - ym(v), yb - up, ph - ym(v), yb + down, ac, aw)
            for v in ym.minors():
                cv.line(ph - ym(v), yb - up * 0.55, ph - ym(v), yb + down * 0.55, ac, aw)
        if ay.numbering:
            for v, s in zip(majors, labels):
                cv.text(ph - ym(v), num_y, s, fs_n, anchor="middle")
    vb = QRectF(-2, yb - up - 3, ph + 4, down + up + 6)
    if ay.numbering:
        for v, s in zip(majors, labels):
            vb = vb.united(_text_rect(ph - ym(v), num_y, s, fs_n, "middle"))
    out.append(Element("y-axis", "y-axis", vb, draw_v, _rect_path(vb), {"font_keys": ["y_numbers"], "range": ym.r}))
    if ay.title:
        fs_t = spec.fonts["y_title"]
        dx, dy = spec.offsets.get("y-title", (0.0, 0.0))
        tx, ty = ph / 2 + dx, vb.bottom() + 6.0 + TM.ascent(fs_t) + dy

        def draw_t(cv, tx=tx, ty=ty):
            cv.text(tx, ty, ay.title, fs_t, anchor="middle")
        r = _text_rect(tx, ty, ay.title, fs_t, "middle")
        out.append(Element("y-title", "text", r, draw_t, _rect_path(r),
                           {"font_keys": ["y_title"], "field": "y_title", "text": ay.title, "rotate": 0,
                            "anchor_pt": (tx, ty)}))

    # category labels down the left
    ax = spec.x
    xtl = TICK_LEN[ax.ticks_len]
    left = xtl if ax.ticks_dir in ("out", "cross") else 0.0
    right = xtl if ax.ticks_dir in ("in", "cross") else 0.0
    xl = -off
    fs_x = spec.fonts["x_labels"]
    lab_x = xl - left - 4.0
    widest = max((TM.width(s, fs_x) for _, s in plan.labels), default=0.0)
    group_x = lab_x - widest - 8.0

    def draw_c(cv):
        cv.line(xl, 0, xl, W, ac, aw)
        if ax.ticks_dir != "none":
            for yc, _ in plan.labels:
                cv.line(xl - left, yc, xl + right, yc, ac, aw)
        for yc, s in plan.labels:
            cv.text(lab_x, yc + TM.cap_height(fs_x) / 2, s, fs_x, anchor="end")
        for yc, s in plan.groups:
            cv.text(group_x, yc + TM.cap_height(fs_x) / 2, s, fs_x, anchor="end")
    cb = QRectF(xl - left - 2, -2, left + right + 4, W + 4)
    for yc, s in plan.labels:
        cb = cb.united(_text_rect(lab_x, yc + TM.cap_height(fs_x) / 2, s, fs_x, "end"))
    for yc, s in plan.groups:
        cb = cb.united(_text_rect(group_x, yc + TM.cap_height(fs_x) / 2, s, fs_x, "end"))
    out.append(Element("x-axis", "x-axis", cb, draw_c, _rect_path(cb), {"font_keys": ["x_labels"]}))

    if spec.frame == "box":
        def draw_f(cv):
            cv.line(0, 0, ph, 0, ac, aw)
            cv.line(ph, 0, ph, W, ac, aw)
        fb = QRectF(-2, -2, ph + 4, W + 4)
        out.append(Element("frame", "frame", fb, draw_f, _rect_path(QRectF(-2, -2, ph + 4, 4),
                                                                     QRectF(ph - 2, -2, 4, W + 4))))
    if legend_entries is not None:
        out.append(_legend(spec, legend_entries[0], legend_entries[1], ph + 12.0, 0.0))
    return out
