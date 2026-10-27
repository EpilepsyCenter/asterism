"""Small illustrations that help people choose: what each table type holds and what each
analysis asks. Drawn with QPainter in the theme's colours (they follow light and dark mode);
ASTERISM's own pictures, not copies of anyone's artwork.

`Sketch(key)` is a widget; `KEYS` lists what can be drawn: "table:<type>" for the New Table
dialog, an analysis key (as in the Analyze dialog), or "design:<name>" for settings dialogs.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

from . import theme

# deterministic "scatter" offsets and values, so pictures never change between views
JIT = [0.1, -0.5, 0.45, -0.2, 0.6, -0.35, 0.25, -0.6, 0.0, 0.4]
G1 = [0.18, 0.38, 0.27, 0.46, 0.23, 0.33]
G2 = [0.55, 0.78, 0.63, 0.86, 0.58, 0.70]
G3 = [0.36, 0.55, 0.30, 0.62, 0.44, 0.50]


class P:
    """Painter helpers in plot units: x and y run 0..1 inside the plot area."""

    def __init__(self, p: QPainter, rect: QRectF):
        self.p, self.r = p, rect
        self.ink, self.muted = theme.color("text"), theme.color("muted")
        self.a, self.b = theme.color("accent"), theme.color("purple")
        self.c = theme.color("warning")
        self.light = theme.mix("bg", "muted", 0.25)
        f = QFont(p.font())
        f.setPointSizeF(9.5)
        p.setFont(f)

    def X(self, u):
        return self.r.left() + u * self.r.width()

    def Y(self, v):
        return self.r.bottom() - v * self.r.height()

    def pt(self, u, v):
        return QPointF(self.X(u), self.Y(v))

    def axes(self, x=True, y=True):
        self.p.setPen(QPen(self.muted, 1.2))
        if y:
            self.p.drawLine(self.pt(0, 0), self.pt(0, 1))
        if x:
            self.p.drawLine(self.pt(0, 0), self.pt(1, 0))

    def dot(self, u, v, col, r=3.4, square=False, hollow=False):
        self.p.setPen(QPen(QColor(col).darker(120), 1.1))
        self.p.setBrush(Qt.NoBrush if hollow else QColor(col))
        if square:
            self.p.drawRect(QRectF(self.X(u) - r, self.Y(v) - r, 2 * r, 2 * r))
        else:
            self.p.drawEllipse(self.pt(u, v), r, r)

    def group(self, u, vals, col, width=0.13, square=False, mean=True):
        for i, v in enumerate(vals):
            self.dot(u + JIT[i % len(JIT)] * width, v, col, square=square)
        if mean:
            m = sum(vals) / len(vals)
            self.line([(u - width * 1.1, m), (u + width * 1.1, m)], self.ink, 1.6)

    def line(self, pts, col, w=1.4, dash=False):
        pen = QPen(QColor(col), w)
        pen.setCapStyle(Qt.RoundCap)
        if dash:
            pen.setStyle(Qt.DashLine)
        self.p.setPen(pen)
        self.p.setBrush(Qt.NoBrush)
        self.p.drawPolyline(QPolygonF([self.pt(u, v) for u, v in pts]))

    def curve(self, f, col, u0=0.0, u1=1.0, w=1.6, dash=False, n=60):
        self.line([(u0 + (u1 - u0) * i / n, f(u0 + (u1 - u0) * i / n)) for i in range(n + 1)], col, w, dash)

    def bar(self, u, v, col, width=0.16, base=0.0, border=None):
        self.p.setPen(QPen(QColor(border or QColor(col).darker(125)), 1.0))
        self.p.setBrush(QColor(col))
        self.p.drawRect(QRectF(self.X(u - width / 2), self.Y(v), self.X(u + width / 2) - self.X(u - width / 2),
                               self.Y(base) - self.Y(v)))

    def text(self, u, v, s, col=None, align=Qt.AlignCenter, w=90.0, dy=0.0):
        self.p.setPen(QColor(col) if col is not None else self.muted)
        self.p.drawText(QRectF(self.X(u) - w / 2, self.Y(v) - 9 + dy, w, 18), align, s)

    def labels(self, items):
        """Category labels under the X axis: [(u, text)]."""
        for u, s in items:
            self.text(u, 0, s, dy=12)


# ---------------------------------------------------------------------------
# table types: a typical graph of what the table holds
# ---------------------------------------------------------------------------

def t_column(d: P):
    d.axes()
    d.group(0.28, G1, d.a)
    d.group(0.72, G2, d.b, square=True)
    d.labels([(0.28, "Control"), (0.72, "Treated")])


def t_xy(d: P):
    d.axes()
    f = lambda u: 0.1 + 0.8 / (1 + math.exp(-(u - 0.5) * 10))
    d.curve(f, d.a)
    for i, u in enumerate([0.08, 0.2, 0.32, 0.44, 0.56, 0.68, 0.8, 0.92]):
        d.dot(u, f(u) + JIT[i] * 0.06, d.a)
    d.text(0.5, 0, "Dose, time, concentration…", dy=12, w=180)


def t_grouped(d: P):
    d.axes()
    for k, (u, a, b) in enumerate([(0.25, 0.35, 0.55), (0.72, 0.45, 0.85)]):
        d.bar(u - 0.08, a, d.a, 0.14)
        d.bar(u + 0.08, b, d.b, 0.14)
    d.labels([(0.25, "Wild type"), (0.72, "Mutant")])
    x0, y0 = d.X(0.06), d.r.top() - 4
    for i, (col, s) in enumerate(((d.a, "Vehicle"), (d.b, "Drug"))):
        x = x0 + i * 74
        d.p.setPen(Qt.NoPen)
        d.p.setBrush(col)
        d.p.drawRect(QRectF(x, y0 + 4, 9, 9))
        d.p.setPen(d.muted)
        d.p.drawText(QRectF(x + 13, y0, 60, 17), Qt.AlignLeft | Qt.AlignVCenter, s)


def t_contingency(d: P):
    d.axes(y=False)
    for u, frac, s in ((0.3, 0.7, "Control"), (0.7, 0.3, "Treated")):
        d.bar(u, 1.0, d.light, 0.26, base=frac)
        d.bar(u, frac, d.a, 0.26)
        d.text(u, frac / 2, f"{round(frac * 20)}", col="#000000" if d.a.lightness() > 150 else "#ffffff")
        d.text(u, (1 + frac) / 2, f"{round((1 - frac) * 20)}", col=d.ink)
    d.labels([(0.3, "Control"), (0.7, "Treated")])


def t_survival(d: P):
    d.axes()
    for col, steps in ((d.a, [(0, 1), (0.2, 0.85), (0.38, 0.7), (0.6, 0.55), (0.85, 0.5), (1, 0.5)]),
                       (d.b, [(0, 1), (0.12, 0.8), (0.25, 0.55), (0.42, 0.35), (0.6, 0.2), (1, 0.2)])):
        pts = []
        for (u0, v0), (u1, _v1) in zip(steps, steps[1:]):
            pts += [(u0, v0), (u1, v0)]
        pts.append((steps[-1][0], steps[-1][1]))
        d.line(pts, col, 1.8)
    d.text(0.5, 0, "Time", dy=12)


def t_parts(d: P):
    c = d.pt(0.5, 0.5)
    rad = min(d.r.width(), d.r.height()) * 0.48
    start = 90 * 16
    for frac, col in ((0.46, d.a), (0.31, d.b), (0.13, d.c), (0.10, d.light)):
        span = -int(frac * 360 * 16)
        d.p.setPen(QPen(theme.color("bg"), 1.5))
        d.p.setBrush(col)
        d.p.drawPie(QRectF(c.x() - rad, c.y() - rad, 2 * rad, 2 * rad), start, span)
        start += span


def t_multivar(d: P):
    d.axes()
    pts = [(0.15, 0.25, 4, d.a), (0.3, 0.4, 7, d.b), (0.45, 0.35, 5, d.a), (0.6, 0.62, 9, d.c),
           (0.75, 0.55, 6, d.b), (0.88, 0.82, 11, d.c), (0.38, 0.7, 3, d.a)]
    for u, v, r, col in pts:
        c = QColor(col)
        c.setAlpha(170)
        d.dot(u, v, c, r)
    d.text(0.5, 0, "x, y, size, colour", dy=12, w=180)


def t_nested(d: P):
    d.axes()
    cols = [d.a, d.b, d.c]
    for g, u in enumerate((0.28, 0.72)):
        for s in range(3):
            base = (0.32 if g == 0 else 0.62) + (s - 1) * 0.1
            for i in range(4):
                d.dot(u + (s - 1) * 0.11 + JIT[(3 * i + s) % 10] * 0.035, base + JIT[i + 2 * s] * 0.2, cols[s], 2.4)
            d.dot(u + (s - 1) * 0.11, base, cols[s], 5.0)
    d.labels([(0.28, "Control"), (0.72, "Treated")])


# ---------------------------------------------------------------------------
# analyses: the question, drawn on the kind of data it needs
# ---------------------------------------------------------------------------

def a_ttest(d: P):
    t_column(d)


def a_anova1(d: P):
    d.axes()
    d.group(0.2, G1, d.a)
    d.group(0.5, G3, d.c)
    d.group(0.8, G2, d.b, square=True)
    d.labels([(0.2, "A"), (0.5, "B"), (0.8, "C")])


def a_onesample(d: P):
    d.axes()
    d.group(0.5, G2, d.a)
    d.line([(0.05, 0.42), (0.95, 0.42)], d.muted, 1.2, dash=True)
    d.text(0.5, 0.42, "Hypothetical value", dy=11, w=130)


def a_descriptive(d: P):
    d.axes()
    u, w = 0.5, 0.18
    q1, med, q3, lo, hi = 0.32, 0.52, 0.72, 0.12, 0.93
    d.p.setPen(QPen(d.ink, 1.3))
    d.p.setBrush(theme.mix("bg", "accent", 0.25))
    d.p.drawRect(QRectF(d.X(u - w / 2), d.Y(q3), d.X(u + w / 2) - d.X(u - w / 2), d.Y(q1) - d.Y(q3)))
    d.line([(u - w / 2, med), (u + w / 2, med)], d.ink, 1.8)
    d.line([(u, q3), (u, hi)], d.ink, 1.2)
    d.line([(u, q1), (u, lo)], d.ink, 1.2)
    for s, v in (("Max", hi), ("Q3", q3), ("Median", med), ("Q1", q1), ("Min", lo)):
        d.text(0.78, v, s, align=Qt.AlignLeft, w=60, dy=0)


def _hist(d: P, heights, col):
    n = len(heights)
    for i, h in enumerate(heights):
        d.bar((i + 0.5) / n, h, col, width=1.0 / n * 0.92)


def a_normality(d: P):
    d.axes()
    hs = [0.08, 0.2, 0.45, 0.7, 0.82, 0.66, 0.4, 0.18, 0.06]
    _hist(d, hs, theme.mix("bg", "accent", 0.45))
    d.curve(lambda u: 0.84 * math.exp(-((u - 0.5) ** 2) / 0.035), d.b, w=2.0)


def a_frequency(d: P):
    d.axes()
    _hist(d, [0.15, 0.35, 0.62, 0.85, 0.55, 0.3, 0.12], d.a)
    d.text(0.5, 0, "Bins", dy=12)


def a_outliers(d: P):
    d.axes()
    d.group(0.4, [v + 0.05 for v in G1] + [0.31, 0.41], d.a, mean=False)
    d.dot(0.4, 0.92, d.c, 4.2)
    d.p.setPen(QPen(d.c, 1.3))
    d.p.setBrush(Qt.NoBrush)
    d.p.drawEllipse(d.pt(0.4, 0.92), 9, 9)
    d.text(0.68, 0.92, "Outlier?", col=d.c, w=70)


def a_correlation(d: P):
    d.axes()
    import random
    rnd = random.Random(3)
    for i in range(16):
        u = 0.08 + i * 0.055
        d.dot(u, 0.12 + 0.75 * u + rnd.uniform(-0.12, 0.12), d.a, 3.0)
    d.text(0.25, 0.85, "r = ?", col=d.ink, w=60)


def a_observed_expected(d: P):
    d.axes()
    for i, (o, e) in enumerate(((0.75, 0.5), (0.3, 0.5), (0.45, 0.5))):
        u = 0.2 + i * 0.3
        d.bar(u, o, d.a, 0.18)
        d.line([(u - 0.14, e), (u + 0.14, e)], d.c, 2.0, dash=True)
    d.text(0.5, 0, "Observed vs expected", dy=12, w=160)


def a_anova2(d: P):
    t_grouped(d)


def a_multiple_t(d: P):
    d.axes()
    for k, (u, a, b) in enumerate([(0.18, 0.3, 0.42), (0.5, 0.35, 0.7), (0.82, 0.4, 0.45)]):
        d.group(u - 0.07, [a - 0.05, a, a + 0.04], d.a, 0.03, mean=False)
        d.group(u + 0.07, [b - 0.04, b, b + 0.05], d.b, 0.03, square=True, mean=False)
        d.text(u, 0.95, "?", col=d.ink, w=20)
    d.labels([(0.18, "Row 1"), (0.5, "Row 2"), (0.82, "Row 3")])


def a_nested(d: P):
    t_nested(d)


def a_nonlin(d: P):
    t_xy(d)


def a_linreg(d: P):
    d.axes()
    import random
    rnd = random.Random(7)
    for i in range(10):
        u = 0.08 + i * 0.09
        d.dot(u, 0.15 + 0.65 * u + rnd.uniform(-0.08, 0.08), d.a)
    d.line([(0.03, 0.17), (0.97, 0.78)], d.b, 2.0)


def a_auc(d: P):
    d.axes()
    f = lambda u: 0.08 + 0.8 * math.exp(-((u - 0.35) ** 2) / 0.03) * (1 if u < 0.35 else 0.9) + 0.06 * u
    path = QPainterPath(d.pt(0, 0))
    for i in range(61):
        u = i / 60
        path.lineTo(d.pt(u, f(u)))
    path.lineTo(d.pt(1, 0))
    path.closeSubpath()
    d.p.setPen(Qt.NoPen)
    d.p.setBrush(theme.mix("bg", "accent", 0.35))
    d.p.drawPath(path)
    d.curve(f, d.a, w=1.8)
    d.text(0.35, 0.3, "Area", col=d.ink)


def a_contingency(d: P):
    t_contingency(d)


def a_survival(d: P):
    t_survival(d)


def a_fraction(d: P):
    t_parts(d)


def _before_after(d: P, left, right, label_l="Before", label_r="After"):
    """Two small panels with an arrow between them."""
    W = 0.42
    for off, fn in ((0.0, left), (1 - W, right)):
        sub = QRectF(d.X(off), d.r.top(), d.r.width() * W, d.r.height())
        q = P(d.p, sub)
        fn(q)
    d.p.setPen(QPen(d.muted, 1.4))
    y = d.Y(0.5)
    d.p.drawLine(QPointF(d.X(W + 0.03), y), QPointF(d.X(1 - W - 0.03), y))
    d.p.drawLine(QPointF(d.X(1 - W - 0.03), y), QPointF(d.X(1 - W - 0.06), y - 4))
    d.p.drawLine(QPointF(d.X(1 - W - 0.03), y), QPointF(d.X(1 - W - 0.06), y + 4))
    d.text(W / 2, 0, label_l, dy=12)
    d.text(1 - W / 2, 0, label_r, dy=12)


def a_transform(d: P):
    def raw(q):
        q.axes()
        q.curve(lambda u: 0.04 + 0.9 * u ** 3, q.a)

    def logged(q):
        q.axes()
        q.curve(lambda u: 0.1 + 0.8 * u, q.b)
    _before_after(d, raw, logged, "Y", "log Y")


def a_normalize(d: P):
    def raw(q):
        q.axes()
        q.curve(lambda u: 0.25 + 0.3 * u, q.a)
        q.curve(lambda u: 0.45 + 0.5 * u, q.b)

    def norm(q):
        q.axes()
        q.curve(lambda u: 0.05 + 0.9 * u, q.a)
        q.curve(lambda u: 0.05 + 0.9 * u, q.b, dash=True)
        q.text(0.32, 0.97, "100%", align=Qt.AlignLeft, w=40, dy=0)
    _before_after(d, raw, norm, "Raw", "0–100%")


def a_baseline(d: P):
    def raw(q):
        q.axes()
        q.curve(lambda u: 0.35 + 0.4 * math.sin(u * 6) * 0.3 + 0.2 * u, q.a)
        q.curve(lambda u: 0.3, q.muted, dash=True)

    def sub(q):
        q.axes()
        q.curve(lambda u: 0.05 + 0.4 * math.sin(u * 6) * 0.3 + 0.2 * u + 0.12, q.a)
    _before_after(d, raw, sub, "With baseline", "Subtracted")


def a_prune(d: P):
    def raw(q):
        q.axes()
        for i in range(14):
            q.dot(0.05 + i * 0.068, 0.45 + 0.35 * math.sin(i / 3.0), q.a, 2.2)

    def pruned(q):
        q.axes()
        for i in range(0, 14, 3):
            q.dot(0.05 + i * 0.068, 0.45 + 0.35 * math.sin(i / 3.0), q.a, 3.0)
    _before_after(d, raw, pruned, "Every row", "Every 3rd")


def a_transpose(d: P):
    def grid(q, rows, cols, col):
        for i in range(rows):
            for j in range(cols):
                q.p.setPen(QPen(q.muted, 0.8))
                q.p.setBrush(col if i == 0 else theme.color("field"))
                q.p.drawRect(QRectF(q.X(0.1 + j * 0.8 / cols), q.Y(0.9 - i * 0.8 / rows),
                                    q.r.width() * 0.8 / cols, q.r.height() * 0.8 / rows))
    _before_after(d, lambda q: grid(q, 4, 2, d.a), lambda q: grid(q, 2, 4, d.b), "Rows × sets", "Sets × rows")


def a_smooth(d: P):
    import random
    rnd = random.Random(5)
    noise = [rnd.uniform(-0.12, 0.12) for _ in range(41)]

    def raw(q):
        q.axes()
        q.line([(i / 40, 0.45 + 0.3 * math.sin(i / 40 * 6) + noise[i]) for i in range(41)], q.a, 1.1)

    def smooth(q):
        q.axes()
        q.curve(lambda u: 0.45 + 0.3 * math.sin(u * 6), q.b, w=1.8)
    _before_after(d, raw, smooth, "Noisy", "Smoothed")


# ---------------------------------------------------------------------------
# designs (settings dialogs)
# ---------------------------------------------------------------------------

def d_independent(d: P):
    d.axes()
    for g, (u, vals, col) in enumerate(((0.2, G1, d.a), (0.5, G3, d.c), (0.8, G2, d.b))):
        for i, v in enumerate(vals[:5]):
            d.dot(u + JIT[i] * 0.1, v, col, square=(g == 2))
    d.labels([(0.2, "A"), (0.5, "B"), (0.8, "C")])


def d_matched(d: P):
    d.axes()
    for i in range(5):
        vals = (G1[i], G3[i], G2[i])
        d.line([(0.2, vals[0]), (0.5, vals[1]), (0.8, vals[2])], d.muted, 1.2)
        for u, v in zip((0.2, 0.5, 0.8), vals):
            d.dot(u, v, d.a)
    d.labels([(0.2, "A"), (0.5, "B"), (0.8, "C")])


def d_twoway_matched(d: P):
    d.axes()
    for i in range(3):
        a, b = 0.42 + i * 0.1, 0.62 + i * 0.13
        d.line([(0.25, a), (0.75, b)], d.muted, 1.2)
        d.dot(0.25, a, d.a)
        d.dot(0.75, b, d.a)
        c, e = 0.04 + i * 0.12, 0.1 + i * 0.11
        d.line([(0.25, c), (0.75, e)], d.muted, 1.2, dash=True)
        d.dot(0.25, c, d.b, square=True)
        d.dot(0.75, e, d.b, square=True)
    d.labels([(0.25, "Day 1"), (0.75, "Day 7")])


def _twoway(d: P, rows: bool, cols: bool):
    """Two rows (Day 1, Day 7) × two data sets (filled circles, squares); three subjects.
    Lines join one subject's values: across rows, across data sets, or both."""
    d.axes()
    xs = {(0, 0): 0.18, (0, 1): 0.36, (1, 0): 0.64, (1, 1): 0.82}      # (row, data set) → x
    base = {0: [0.3, 0.45, 0.6], 1: [0.04, 0.17, 0.3]}                # data set → subject values at row 0
    rise = {0: 0.28, 1: 0.16}
    val = lambda r, ds, k: base[ds][k] + rise[ds] * r + (0.06 * r * (k - 1))
    for k in range(3):
        if rows:
            for ds in (0, 1):
                d.line([(xs[(0, ds)], val(0, ds, k)), (xs[(1, ds)], val(1, ds, k))], d.muted, 1.1,
                       dash=ds == 1)
        if cols:
            for r in (0, 1):
                d.line([(xs[(r, 0)], val(r, 0, k)), (xs[(r, 1)], val(r, 1, k))], d.muted, 1.1)
        for (r, ds), x in xs.items():
            d.dot(x, val(r, ds, k), d.a if ds == 0 else d.b, square=ds == 1)
    d.labels([(0.27, "Day 1"), (0.73, "Day 7")])


DRAW = {
    "table:column": t_column, "table:xy": t_xy, "table:grouped": t_grouped,
    "table:contingency": t_contingency, "table:survival": t_survival, "table:parts": t_parts,
    "table:multivar": t_multivar, "table:nested": t_nested,
    "ttest": a_ttest, "anova1": a_anova1, "onesample": a_onesample, "descriptive": a_descriptive,
    "normality": a_normality, "frequency": a_frequency, "outliers": a_outliers,
    "correlation": a_correlation, "observed_expected": a_observed_expected, "anova2": a_anova2,
    "multiple_t": a_multiple_t, "nested": a_nested, "nonlin": a_nonlin, "linreg": a_linreg,
    "auc": a_auc, "contingency": a_contingency, "survival": a_survival, "fraction": a_fraction,
    "transform": a_transform, "normalize": a_normalize, "baseline": a_baseline, "prune": a_prune,
    "transpose": a_transpose, "smooth": a_smooth,
    "design:independent": d_independent, "design:matched": d_matched,
    "design:twoway_matched": d_twoway_matched,
    "design:ordinary": lambda d: _twoway(d, False, False), "design:rm_rows": lambda d: _twoway(d, True, False),
    "design:rm_cols": lambda d: _twoway(d, False, True), "design:rm_both": lambda d: _twoway(d, True, True),
}
KEYS = tuple(DRAW)


class Sketch(QWidget):
    """One illustration; `set_key` switches it (a key without a picture shows nothing)."""

    def __init__(self, key: str = "", w: int = 220, h: int = 130, framed: bool = True):
        super().__init__()
        self.key, self.framed = key, framed
        self.setFixedSize(w, h)
        sp = self.sizePolicy()
        sp.setRetainSizeWhenHidden(True)          # no jump when a choice has no picture
        self.setSizePolicy(sp)
        theme.notifier.changed.connect(self.update)

    def set_key(self, key: str | None) -> None:
        self.key = key or ""
        self.setVisible(self.key in DRAW)
        self.update()

    def paintEvent(self, _e):
        fn = DRAW.get(self.key)
        if fn is None:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self.framed:
            p.setPen(QPen(theme.mix("bg", "muted", 0.25), 1))
            p.setBrush(theme.color("field"))
            p.drawRoundedRect(QRectF(0.5, 0.5, self.width() - 1, self.height() - 1), 8, 8)
        plot = QRectF(18, 16, self.width() - 34, self.height() - 40)
        fn(P(p, plot))
        p.end()
