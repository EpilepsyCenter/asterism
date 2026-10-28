"""EMF (Enhanced Metafile) writer: the vector picture format Microsoft Office pastes from the
Windows clipboard. Same drawing interface as SvgCanvas, written record by record from
Microsoft's published format ([MS-EMF]); no Windows APIs needed, so it is built and
tested on every platform.

Coordinates: graph points (1/72 inch). Logical units are 1/20 pt (map mode
MM_ANISOTROPIC); the reference device is 96 dpi. Text is real text (font, size, bold,
italic, rotation), so it stays editable after pasting.
"""

from __future__ import annotations

import struct

from PySide6.QtCore import QRectF

from .canvas import DASHES, TextMetrics

K = 20.0                        # logical units per point
DPI = 96.0
STOCK_NULL_BRUSH, STOCK_NULL_PEN = 0x80000005, 0x80000008
PS_GEOMETRIC, PS_USERSTYLE = 0x00010000, 7
CAPS = {"round": 0x0000, "square": 0x0100, "butt": 0x0200, "flat": 0x0200}
JOIN_MITER = 0x2000
TA_BASELINE = 24
ALIGN = {"start": 0, "middle": 6, "end": 2}

EMR_HEADER, EMR_POLYGON, EMR_POLYLINE, EMR_SETWINDOWEXTEX, EMR_SETWINDOWORGEX = 1, 3, 4, 9, 10
EMR_SETVIEWPORTEXTEX, EMR_SETVIEWPORTORGEX, EMR_EOF, EMR_SETMAPMODE, EMR_SETBKMODE = 11, 12, 14, 17, 18
EMR_SETPOLYFILLMODE, EMR_SETTEXTALIGN, EMR_SETTEXTCOLOR = 19, 22, 24
EMR_SELECTOBJECT, EMR_CREATEBRUSHINDIRECT, EMR_DELETEOBJECT = 37, 39, 40
EMR_ELLIPSE, EMR_RECTANGLE, EMR_STRETCHDIBITS = 42, 43, 81
EMR_EXTCREATEFONTINDIRECTW, EMR_EXTTEXTOUTW, EMR_EXTCREATEPEN = 82, 84, 95


def _colorref(c) -> int:
    """'#rrggbb' (or a QColor-like name) → COLORREF 0x00BBGGRR."""
    from PySide6.QtGui import QColor
    q = QColor(c or "#000000")
    return q.red() | (q.green() << 8) | (q.blue() << 16)


def _blend(c, opacity: float) -> str:
    """EMF has no transparency: mix a fill with white."""
    from PySide6.QtGui import QColor
    q = QColor(c)
    m = lambda v: round(v * opacity + 255 * (1 - opacity))
    return QColor(m(q.red()), m(q.green()), m(q.blue())).name()


class EmfCanvas:
    def __init__(self, bounds: QRectF):
        self.b = bounds
        self.recs: list[bytes] = []
        self.stack = [(1.0, 0.0, 0.0)]            # (scale, dx, dy): figure panels nest
        self._setup()

    # --- records ---------------------------------------------------------------------

    def _rec(self, kind: int, payload: bytes) -> None:
        assert len(payload) % 4 == 0
        self.recs.append(struct.pack("<II", kind, 8 + len(payload)) + payload)

    def _setup(self) -> None:
        wl, hl = self._extent()
        wpx, hpx = self._device()
        self._rec(EMR_SETMAPMODE, struct.pack("<I", 8))              # MM_ANISOTROPIC
        self._rec(EMR_SETWINDOWORGEX, struct.pack("<ii", 0, 0))
        self._rec(EMR_SETWINDOWEXTEX, struct.pack("<ii", wl, hl))
        self._rec(EMR_SETVIEWPORTORGEX, struct.pack("<ii", 0, 0))
        self._rec(EMR_SETVIEWPORTEXTEX, struct.pack("<ii", wpx, hpx))
        self._rec(EMR_SETBKMODE, struct.pack("<I", 1))               # TRANSPARENT
        self._rec(EMR_SETPOLYFILLMODE, struct.pack("<I", 2))         # WINDING

    def _extent(self) -> tuple[int, int]:
        return max(1, round(self.b.width() * K)), max(1, round(self.b.height() * K))

    def _device(self) -> tuple[int, int]:
        return max(1, round(self.b.width() * DPI / 72)), max(1, round(self.b.height() * DPI / 72))

    # --- coordinates -----------------------------------------------------------------

    def _s(self) -> float:
        return self.stack[-1][0]

    def _pt(self, x, y) -> tuple[int, int]:
        s, dx, dy = self.stack[-1]
        return (round((s * x + dx - self.b.x()) * K), round((s * y + dy - self.b.y()) * K))

    def _w(self, width: float) -> int:
        return max(1, round(width * self._s() * K))

    @staticmethod
    def _bounds(pts) -> bytes:
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        return struct.pack("<iiii", min(xs), min(ys), max(xs), max(ys))

    # --- pens and brushes --------------------------------------------------------------

    def _pen(self, color, width, cap="square", dash=None) -> bool:
        """Create and select pen 1; False (null pen selected) when there's no stroke."""
        if color is None or width <= 0:
            self._rec(EMR_SELECTOBJECT, struct.pack("<I", STOCK_NULL_PEN))
            return False
        w = self._w(width)
        entries = [max(1, round(d * width * self._s() * K)) for d in DASHES[dash]] if dash else []
        style = PS_GEOMETRIC | CAPS.get(cap, 0x0100) | JOIN_MITER | (PS_USERSTYLE if entries else 0)
        fixed = 4 * 5 + 4 * 6 + 4 * len(entries)
        off = 8 + fixed
        payload = struct.pack("<IIIII", 1, off, 0, off, 0)
        payload += struct.pack("<IIIIII", style, w, 0, _colorref(color), 0, len(entries))
        payload += b"".join(struct.pack("<I", e) for e in entries)
        self._rec(EMR_EXTCREATEPEN, payload)
        self._rec(EMR_SELECTOBJECT, struct.pack("<I", 1))
        return True

    def _brush(self, fill) -> bool:
        if not fill or fill == "none":
            self._rec(EMR_SELECTOBJECT, struct.pack("<I", STOCK_NULL_BRUSH))
            return False
        self._rec(EMR_CREATEBRUSHINDIRECT, struct.pack("<IIII", 2, 0, _colorref(fill), 0))
        self._rec(EMR_SELECTOBJECT, struct.pack("<I", 2))
        return True

    def _release(self, pen: bool, brush: bool) -> None:
        self._rec(EMR_SELECTOBJECT, struct.pack("<I", STOCK_NULL_PEN))
        self._rec(EMR_SELECTOBJECT, struct.pack("<I", STOCK_NULL_BRUSH))
        if pen:
            self._rec(EMR_DELETEOBJECT, struct.pack("<I", 1))
        if brush:
            self._rec(EMR_DELETEOBJECT, struct.pack("<I", 2))

    def _poly(self, kind, pts) -> None:
        P = [self._pt(x, y) for x, y in pts]
        if len(P) < 2:
            return
        self._rec(kind, self._bounds(P) + struct.pack("<I", len(P)) + b"".join(struct.pack("<ii", *p) for p in P))

    # --- the canvas interface (as SvgCanvas / QtCanvas) ----------------------------------

    def line(self, x1, y1, x2, y2, color="#000", width=1.0, cap="square", dash=None):
        if self._pen(color, width, cap, dash):
            self._rec(EMR_SELECTOBJECT, struct.pack("<I", STOCK_NULL_BRUSH))
            self._poly(EMR_POLYLINE, [(x1, y1), (x2, y2)])
            self._release(True, False)

    def polyline(self, pts, color="#000", width=1.0, cap="square", dash=None):
        if len(pts) > 1 and self._pen(color, width, cap, dash):
            self._rec(EMR_SELECTOBJECT, struct.pack("<I", STOCK_NULL_BRUSH))
            self._poly(EMR_POLYLINE, pts)
            self._release(True, False)

    def polygon(self, pts, fill=None, stroke=None, width=1.0, opacity=1.0):
        if fill and opacity < 1.0:
            fill = _blend(fill, opacity)
        b = self._brush(fill)
        p = self._pen(stroke, width)
        if b or p:
            self._poly(EMR_POLYGON, pts)
        self._release(p, b)

    def rect(self, x, y, w, h, fill=None, stroke=None, width=1.0):
        self.shape("rect", x, y, w, h, fill, stroke, width)

    def circle(self, cx, cy, r, fill=None, stroke=None, width=1.0):
        self.shape("ellipse", cx - r, cy - r, 2 * r, 2 * r, fill, stroke, width)

    def shape(self, kind, x, y, w, h, fill=None, stroke=None, width=1.0, dash=None):
        b = self._brush(fill)
        p = self._pen(stroke, width, "butt", dash)
        if b or p:
            a, c = self._pt(x, y), self._pt(x + w, y + h)
            box = struct.pack("<iiii", min(a[0], c[0]), min(a[1], c[1]), max(a[0], c[0]), max(a[1], c[1]))
            self._rec(EMR_ELLIPSE if kind == "ellipse" else EMR_RECTANGLE, box)
        self._release(p, b)

    def text(self, x, y, s, fs, color=None, anchor="start", rotate=0.0):
        if not s:
            return
        color = color or getattr(fs, "color", "") or "#000000"
        size = fs.size * self._s()
        face = (fs.family or "Arial")[:31].encode("utf-16-le").ljust(64, b"\0")
        esc = int(round(-rotate * 10)) % 3600
        logfont = struct.pack("<iiiii", -round(size * K), 0, esc, esc, 700 if fs.bold else 400)
        logfont += struct.pack("<8B", 1 if fs.italic else 0, 1 if getattr(fs, "underline", False) else 0, 0,
                               1, 0, 0, 4, 0)       # DEFAULT_CHARSET, ANTIALIASED_QUALITY
        logfont += face
        self._rec(EMR_EXTCREATEFONTINDIRECTW, struct.pack("<I", 3) + logfont)
        self._rec(EMR_SELECTOBJECT, struct.pack("<I", 3))
        self._rec(EMR_SETTEXTCOLOR, struct.pack("<I", _colorref(color)))
        self._rec(EMR_SETTEXTALIGN, struct.pack("<I", TA_BASELINE | ALIGN.get(anchor, 0)))
        units = s.encode("utf-16-le")
        n = len(units) // 2
        string = units.ljust((len(units) + 3) // 4 * 4, b"\0")
        # character advances (logical units), measured with the same font the graph uses
        fm = TextMetrics._fm(fs)
        dx = []
        for ch in s:
            adv = round(fm.horizontalAdvance(ch) * self._s() * K)
            dx.append(adv)
            if ord(ch) > 0xFFFF:
                dx.append(0)
        ref = self._pt(x, y)
        width_l = sum(dx)
        hgt = round(size * K)
        bounds = struct.pack("<iiii", ref[0] - width_l, ref[1] - hgt, ref[0] + width_l, ref[1] + hgt)
        off_string = 8 + 16 + 12 + 40
        off_dx = off_string + len(string)
        emrtext = struct.pack("<iiIII", ref[0], ref[1], n, off_string, 0) + struct.pack("<iiii", 0, 0, -1, -1)
        emrtext += struct.pack("<I", off_dx)
        payload = bounds + struct.pack("<Iff", 1, 0.0, 0.0) + emrtext + string
        payload += b"".join(struct.pack("<i", d) for d in dx)
        self._rec(EMR_EXTTEXTOUTW, payload)
        self._rec(EMR_SELECTOBJECT, struct.pack("<I", 0x8000000D))     # SYSTEM_FONT
        self._rec(EMR_DELETEOBJECT, struct.pack("<I", 3))

    def image(self, x, y, w, h, png: bytes):
        from PySide6.QtGui import QImage
        img = QImage()
        if not img.loadFromData(png):
            return
        img = img.convertToFormat(QImage.Format_RGB32)           # B, G, R, x per pixel (DIB order)
        iw, ih = img.width(), img.height()
        bits = bytes(img.constBits())[: iw * ih * 4]
        bmi = struct.pack("<IiiHHIIiiII", 40, iw, -ih, 1, 32, 0, len(bits), 0, 0, 0, 0)   # top-down
        a, c = self._pt(x, y), self._pt(x + w, y + h)
        fixed = 8 + 16 + 4 * 14
        payload = struct.pack("<iiii", a[0], a[1], c[0], c[1])
        payload += struct.pack("<iiiiii", a[0], a[1], 0, 0, iw, ih)
        payload += struct.pack("<IIII", fixed, len(bmi), fixed + len(bmi), len(bits))
        payload += struct.pack("<IIii", 0, 0x00CC0020, c[0] - a[0], c[1] - a[1])      # DIB_RGB_COLORS, SRCCOPY
        self._rec(EMR_STRETCHDIBITS, payload + bmi + bits)

    def begin_group(self, gid: str, dx: float = 0.0, dy: float = 0.0, scale: float = 1.0):
        s, px, py = self.stack[-1]
        self.stack.append((s * scale, s * dx + px, s * dy + py))

    def end_group(self):
        if len(self.stack) > 1:
            self.stack.pop()

    # --- the file ---------------------------------------------------------------------

    def tobytes(self) -> bytes:
        wpx, hpx = self._device()
        frame = (0, 0, round(self.b.width() / 72 * 2540), round(self.b.height() / 72 * 2540))  # 0.01 mm
        desc = "ASTERISM\0Graph\0\0".encode("utf-16-le")
        desc = desc.ljust((len(desc) + 3) // 4 * 4, b"\0")
        eof = struct.pack("<II", EMR_EOF, 20) + struct.pack("<III", 0, 16, 20)
        body = b"".join(self.recs)
        head_size = 108 + len(desc)
        total = head_size + len(body) + len(eof)
        nrec = len(self.recs) + 2
        head = struct.pack("<II", EMR_HEADER, head_size)
        head += struct.pack("<iiii", 0, 0, wpx - 1, hpx - 1)
        head += struct.pack("<iiii", *frame)
        head += struct.pack("<IIIIHHIIIiiii", 0x464D4520, 0x10000, total, nrec, 4, 0,
                            len(desc) // 2, 108, 0, 1920, 1080, 508, 286)
        head += struct.pack("<IIIii", 0, 0, 0, 508000, 285750)
        return head + desc + body + eof


def records(data: bytes) -> list[tuple[int, bytes]]:
    """Split an EMF into (type, payload) records (for tests and checks)."""
    out, i = [], 0
    while i < len(data):
        kind, size = struct.unpack_from("<II", data, i)
        if size < 8 or i + size > len(data):
            raise ValueError(f"bad record at {i}")
        out.append((kind, data[i + 8:i + size]))
        i += size
    return out
