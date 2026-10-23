"""Drawing back-ends.

Every graph element draws itself through this small API. `QtCanvas` targets a
QPainter (screen, PDF, PNG); `SvgCanvas` writes SVG directly so each element lands in
a named `<g id=…>` group with live `<text>` — the property Affinity/Illustrator
editing depends on, and the one Qt's own QSvgGenerator cannot provide.

Units are points (1/72 in) everywhere.
"""

from __future__ import annotations

from xml.sax.saxutils import escape, quoteattr

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QFont, QFontMetricsF, QGuiApplication,
                           QPainter, QPainterPath, QPen, QPolygonF)

from ...doc.spec import FontSpec

MM = 72.0 / 25.4


def qfont(fs: FontSpec, dpi: float = 72.0) -> QFont:
    """A QFont whose *point* size renders as `fs.size` scene units on a device of `dpi`."""
    f = QFont(fs.family)
    f.setPointSizeF(fs.size * 72.0 / dpi)
    f.setBold(fs.bold)
    f.setItalic(fs.italic)
    f.setKerning(True)
    return f


def _screen_dpi() -> float:
    s = QGuiApplication.primaryScreen()
    return s.logicalDotsPerInchY() if s else 72.0


class TextMetrics:
    """Measure text in points, independent of the screen's logical DPI."""

    @staticmethod
    def _fm(fs: FontSpec) -> QFontMetricsF:
        return QFontMetricsF(qfont(fs, _screen_dpi()))

    @classmethod
    def width(cls, s: str, fs: FontSpec) -> float:
        return cls._fm(fs).horizontalAdvance(s)

    @classmethod
    def ascent(cls, fs: FontSpec) -> float:
        return cls._fm(fs).ascent()

    @classmethod
    def descent(cls, fs: FontSpec) -> float:
        return cls._fm(fs).descent()

    @classmethod
    def cap_height(cls, fs: FontSpec) -> float:
        return cls._fm(fs).capHeight()


# ---------------------------------------------------------------------------

DASHES = {"dash": [4.0, 2.5], "dot": [1.0, 2.0]}   # in multiples of the line width


class QtCanvas:
    def __init__(self, painter: QPainter):
        self.p = painter
        self.p.setRenderHint(QPainter.Antialiasing, True)
        self.p.setRenderHint(QPainter.TextAntialiasing, True)
        self.dpi = painter.device().logicalDpiY() if painter.device() else 72.0

    def _pen(self, color, width, cap="square", dash=None):
        if color is None or width <= 0:
            return QPen(Qt.NoPen)
        pen = QPen(QColor(color))
        pen.setWidthF(width)
        pen.setCapStyle({"square": Qt.SquareCap, "butt": Qt.FlatCap, "round": Qt.RoundCap}[cap])
        pen.setJoinStyle(Qt.MiterJoin)
        if dash:
            pen.setDashPattern(DASHES[dash])     # in units of the line width
        return pen

    def _brush(self, fill):
        return QBrush(QColor(fill)) if fill else QBrush(Qt.NoBrush)

    def line(self, x1, y1, x2, y2, color="#000", width=1.0, cap="square", dash=None):
        self.p.setPen(self._pen(color, width, cap, dash))
        self.p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    def polyline(self, pts, color="#000", width=1.0, cap="square", dash=None):
        self.p.setPen(self._pen(color, width, cap, dash))
        self.p.setBrush(Qt.NoBrush)
        self.p.drawPolyline(QPolygonF([QPointF(x, y) for x, y in pts]))

    def rect(self, x, y, w, h, fill=None, stroke=None, width=1.0):
        self.p.setPen(self._pen(stroke, width))
        self.p.setBrush(self._brush(fill))
        self.p.drawRect(QRectF(x, y, w, h))

    def circle(self, cx, cy, r, fill=None, stroke=None, width=1.0):
        self.p.setPen(self._pen(stroke, width))
        self.p.setBrush(self._brush(fill))
        self.p.drawEllipse(QPointF(cx, cy), r, r)

    def polygon(self, pts, fill=None, stroke=None, width=1.0, opacity=1.0):
        self.p.setPen(self._pen(stroke, width))
        if fill and opacity < 1.0:
            c = QColor(fill)
            c.setAlphaF(max(0.0, min(1.0, opacity)))
            self.p.setBrush(QBrush(c))
        else:
            self.p.setBrush(self._brush(fill))
        self.p.drawPolygon(QPolygonF([QPointF(x, y) for x, y in pts]))

    def text(self, x, y, s, fs: FontSpec, color="#000", anchor="start", rotate=0.0):
        self.p.setFont(qfont(fs, self.dpi))
        self.p.setPen(QColor(color))
        w = TextMetrics.width(s, fs)
        dx = {"start": 0.0, "middle": -w / 2, "end": -w}[anchor]
        if rotate:
            self.p.save()
            self.p.translate(x, y)
            self.p.rotate(rotate)
            self.p.drawText(QPointF(dx, 0), s)
            self.p.restore()
        else:
            self.p.drawText(QPointF(x + dx, y), s)

    def begin_group(self, gid: str):
        pass

    def end_group(self):
        pass


# ---------------------------------------------------------------------------

def _n(v: float) -> str:
    return f"{v:.3f}".rstrip("0").rstrip(".")


class SvgCanvas:
    def __init__(self, bounds: QRectF):
        self.b = bounds
        self.parts: list[str] = []
        self._indent = 1

    def _emit(self, s: str):
        self.parts.append("  " * self._indent + s)

    @staticmethod
    def _stroke(color, width, cap="square", dash=None) -> str:
        if color is None or width <= 0:
            return 'stroke="none"'
        out = (f'stroke="{color}" stroke-width="{_n(width)}" '
               f'stroke-linecap="{cap}" stroke-linejoin="miter"')
        if dash:
            out += ' stroke-dasharray="' + ",".join(_n(d * width) for d in DASHES[dash]) + '"'
        return out

    def line(self, x1, y1, x2, y2, color="#000", width=1.0, cap="square", dash=None):
        self._emit(f'<line x1="{_n(x1)}" y1="{_n(y1)}" x2="{_n(x2)}" y2="{_n(y2)}" '
                   f'{self._stroke(color, width, cap, dash)}/>')

    def polyline(self, pts, color="#000", width=1.0, cap="square", dash=None):
        p = " ".join(f"{_n(x)},{_n(y)}" for x, y in pts)
        self._emit(f'<polyline points="{p}" fill="none" {self._stroke(color, width, cap, dash)}/>')

    def rect(self, x, y, w, h, fill=None, stroke=None, width=1.0):
        self._emit(f'<rect x="{_n(x)}" y="{_n(y)}" width="{_n(w)}" height="{_n(h)}" '
                   f'fill="{fill or "none"}" {self._stroke(stroke, width)}/>')

    def circle(self, cx, cy, r, fill=None, stroke=None, width=1.0):
        self._emit(f'<circle cx="{_n(cx)}" cy="{_n(cy)}" r="{_n(r)}" '
                   f'fill="{fill or "none"}" {self._stroke(stroke, width)}/>')

    def polygon(self, pts, fill=None, stroke=None, width=1.0, opacity=1.0):
        p = " ".join(f"{_n(x)},{_n(y)}" for x, y in pts)
        op = f' fill-opacity="{_n(opacity)}"' if fill and opacity < 1.0 else ""
        self._emit(f'<polygon points="{p}" fill="{fill or "none"}"{op} {self._stroke(stroke, width)}/>')

    def text(self, x, y, s, fs: FontSpec, color="#000", anchor="start", rotate=0.0):
        attrs = (f'x="{_n(x)}" y="{_n(y)}" font-family={quoteattr(fs.family)} '
                 f'font-size="{_n(fs.size)}" fill="{color}" text-anchor="{anchor}"')
        if fs.bold:
            attrs += ' font-weight="bold"'
        if fs.italic:
            attrs += ' font-style="italic"'
        if rotate:
            attrs += f' transform="rotate({_n(rotate)} {_n(x)} {_n(y)})"'
        self._emit(f"<text {attrs}>{escape(s)}</text>")

    def begin_group(self, gid: str):
        self._emit(f"<g id={quoteattr(gid)}>")
        self._indent += 1

    def end_group(self):
        self._indent -= 1
        self._emit("</g>")

    def tostring(self) -> str:
        w, h = self.b.width(), self.b.height()
        head = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" '
            f'width="{w / MM:.3f}mm" height="{h / MM:.3f}mm" viewBox="0 0 {_n(w)} {_n(h)}">\n'
            f'  <g transform="translate({_n(-self.b.x())} {_n(-self.b.y())})">\n'
        )
        return head + "\n".join("  " + p for p in self.parts) + "\n  </g>\n</svg>\n"
