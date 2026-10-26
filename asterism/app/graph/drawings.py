"""Things drawn on a graph with the Draw tools: lines, arrows, boxes, ellipses, text and
pictures. They live in GraphSpec.drawings (points, in the graph's own coordinates: the
plot area's top-left corner is 0, 0) and draw on any canvas like other elements."""

from __future__ import annotations

import base64
import math
import uuid

from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainterPath, QPainterPathStroker

from ...doc.spec import FontSpec
from .canvas import TextMetrics as TM

KINDS = ("line", "arrow", "rect", "ellipse", "text", "image")
NAMES = {"line": "Line", "arrow": "Arrow", "rect": "Box", "ellipse": "Ellipse", "text": "Text", "image": "Picture"}


def new_drawing(kind: str, x1: float, y1: float, x2: float, y2: float, **extra) -> dict:
    d = {"id": uuid.uuid4().hex[:8], "kind": kind, "x1": float(x1), "y1": float(y1), "x2": float(x2),
         "y2": float(y2), "color": "#000000", "width": 1.0, "dash": "solid", "fill": "",
         "head": "end", "text": "", "size": 12.0, "bold": False, "italic": False, "png": ""}
    d.update(extra)
    return d


def font_of(d: dict, spec) -> FontSpec:
    family = spec.fonts["legend"].family if spec is not None else "Arial"
    return FontSpec(family=d.get("family") or family, size=float(d.get("size", 12.0)),
                    bold=bool(d.get("bold")), italic=bool(d.get("italic")), underline=bool(d.get("underline")),
                    color=d.get("color") or "")


def _arrow_head(x1, y1, x2, y2, width) -> list[tuple[float, float]]:
    ang = math.atan2(y2 - y1, x2 - x1)
    L, W = max(7.0, width * 4.5), max(2.6, width * 1.8)
    bx, by = x2 - L * math.cos(ang), y2 - L * math.sin(ang)
    nx, ny = -math.sin(ang) * W, math.cos(ang) * W
    return [(x2, y2), (bx + nx, by + ny), (bx - nx, by - ny)]


def text_lines(d: dict) -> list[str]:
    return (d.get("text") or "").split("\n") or [""]


def text_rect(d: dict, spec) -> QRectF:
    fs = font_of(d, spec)
    lines = text_lines(d)
    lh = TM.ascent(fs) + TM.descent(fs)
    w = max((TM.width(s, fs) for s in lines), default=0.0)
    return QRectF(d["x1"], d["y1"], max(w, 4.0), lh * len(lines))


def bounds(d: dict, spec=None) -> QRectF:
    if d["kind"] == "text":
        return text_rect(d, spec)
    r = QRectF(min(d["x1"], d["x2"]), min(d["y1"], d["y2"]), abs(d["x2"] - d["x1"]), abs(d["y2"] - d["y1"]))
    pad = float(d.get("width", 1.0)) / 2 + (6.0 if d["kind"] == "arrow" else 0.0)
    return r.adjusted(-pad, -pad, pad, pad)


def drawing_elements(spec) -> list:
    from .layout import Element, _rect_path
    out = []
    for d in spec.drawings:
        if d.get("kind") not in KINDS:
            continue
        kind = d["kind"]
        x1, y1, x2, y2 = d["x1"], d["y1"], d["x2"], d["y2"]
        col, w = d.get("color") or "#000000", float(d.get("width", 1.0))
        dash = None if d.get("dash", "solid") == "solid" else d["dash"]
        b = bounds(d, spec)
        if kind in ("line", "arrow"):
            path = QPainterPath()
            path.moveTo(x1, y1)
            path.lineTo(x2, y2)
            st = QPainterPathStroker()
            st.setWidth(max(w, 1.0) + 6.0)
            hit = st.createStroke(path)

            def draw(cv, d=d, col=col, w=w, dash=dash):
                xa, ya, xb, yb = d["x1"], d["y1"], d["x2"], d["y2"]
                if d["kind"] == "arrow":
                    L = max(7.0, w * 4.5)
                    n = math.hypot(xb - xa, yb - ya) or 1.0
                    ux, uy = (xb - xa) / n, (yb - ya) / n
                    sx, sy = xa, ya
                    ex, ey = xb - ux * L * 0.8, yb - uy * L * 0.8      # the line stops inside the head
                    if d.get("head") == "both":
                        sx, sy = xa + ux * L * 0.8, ya + uy * L * 0.8
                    cv.line(sx, sy, ex, ey, col, w, "butt", dash)
                    cv.polygon(_arrow_head(xa, ya, xb, yb, w), fill=col)
                    if d.get("head") == "both":
                        cv.polygon(_arrow_head(xb, yb, xa, ya, w), fill=col)
                else:
                    cv.line(xa, ya, xb, yb, col, w, "round", dash)
        elif kind in ("rect", "ellipse"):
            r = QRectF(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))
            hit = _rect_path(r.adjusted(-3, -3, 3, 3))

            def draw(cv, r=r, d=d, col=col, w=w, dash=dash):
                cv.shape(d["kind"], r.x(), r.y(), r.width(), r.height(), fill=d.get("fill") or None,
                         stroke=col if w > 0 else None, width=w, dash=dash)
        elif kind == "text":
            hit = _rect_path(b.adjusted(-2, -2, 2, 2))
            fs = font_of(d, spec)

            def draw(cv, d=d, fs=fs, col=col, bw=b.width()):
                y = d["y1"] + TM.ascent(fs)
                lh = TM.ascent(fs) + TM.descent(fs)
                al = d.get("align", "left")
                x, anchor = {"left": (d["x1"], "start"), "center": (d["x1"] + bw / 2, "middle"),
                             "right": (d["x1"] + bw, "end")}.get(al, (d["x1"], "start"))
                for s in text_lines(d):
                    cv.text(x, y, s, fs, color=col, anchor=anchor)
                    y += lh
        else:                                   # picture
            r = QRectF(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))
            hit = _rect_path(r)
            png = base64.b64decode(d.get("png") or "") if d.get("png") else b""

            def draw(cv, r=r, png=png):
                if png:
                    cv.image(r.x(), r.y(), r.width(), r.height(), png)
                else:
                    cv.shape("rect", r.x(), r.y(), r.width(), r.height(), stroke="#999999", width=0.5, dash="dash")
        meta = {"drawing": d["id"], "drawing_kind": kind}
        if kind == "text":
            meta.update({"field": f"drawing:{d['id']}", "text": d.get("text", ""), "rotate": 0,
                         "anchor_pt": (d["x1"], d["y1"] + TM.ascent(font_of(d, spec))), "fontspec": font_of(d, spec)})
        out.append(Element(f"draw-{d['id']}", "drawing", b, draw, hit, meta))
    return out


def image_drawing(path: str, x: float, y: float, width: float = 120.0) -> dict | None:
    """A picture drawing from an image file (stored inside the project as PNG; very large
    images are scaled down to 1600 pixels)."""
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
    from PySide6.QtGui import QImage
    img = QImage(path)
    if img.isNull():
        return None
    if max(img.width(), img.height()) > 1600:
        img = img.scaled(1600, 1600, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "PNG")
    buf.close()
    h = width * img.height() / max(img.width(), 1)
    return new_drawing("image", x, y, x + width, y + h, png=base64.b64encode(bytes(ba)).decode("ascii"))


# ---------------------------------------------------------------------------
# Superscript, subscript and symbols (Unicode characters, so they survive every export)
# ---------------------------------------------------------------------------

_SUP = dict(zip("0123456789+-−=()nix", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁻⁼⁽⁾ⁿⁱˣ"))
_SUB = dict(zip("0123456789+-−=()aeoxhklmnpst", "₀₁₂₃₄₅₆₇₈₉₊₋₋₌₍₎ₐₑₒₓₕₖₗₘₙₚₛₜ"))
_UNSUP = {v: k for k, v in _SUP.items() if k != "−"}
_UNSUB = {v: k for k, v in _SUB.items() if k != "−"}

SYMBOLS = [
    ("Greek", "α β γ δ ε ζ η θ κ λ μ ν ξ π ρ σ τ φ χ ψ ω Γ Δ Θ Λ Π Σ Φ Ψ Ω"),
    ("Maths", "± × ÷ − ≤ ≥ ≈ ≠ ≡ ∝ ∞ √ ∑ ∫ ∂ ∆ ‰ °"),
    ("Units", "µ Å ° ℃ Ω ² ³ ⁻¹ ⁻² ½ ¼ ¾"),
    ("Arrows and marks", "→ ← ↑ ↓ ↔ ⇒ • · † ‡ § ¶ ✓ ✗ ★ ■ □ ● ○ ▲ △ ▼ ◆ ◇"),
]


def script(text: str, kind: str) -> str:
    """Characters as superscript or subscript; if they already all are, back to normal.
    Characters without a Unicode form are left as they are."""
    fwd, back = (_SUP, _UNSUP) if kind == "sup" else (_SUB, _UNSUB)
    if text and all(c in back or c.isspace() for c in text):
        return "".join(back.get(c, c) for c in text)
    return "".join(fwd.get(c, c) for c in text)
