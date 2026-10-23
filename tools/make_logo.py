"""Build the ASTERISM logo SVGs from the design reference ("Dipper pours into the i").

    .venv/bin/python tools/make_logo.py

Needs IBM Plex Sans installed (only here, to draw the letters); the SVGs it writes hold
the letters as outlines, so the app needs no font. Output: asterism/app/assets/

  logo-light.svg / logo-dark.svg          wordmark with the Big Dipper pouring into the i
  wordmark-light.svg / wordmark-dark.svg  wordmark only (the star dots the i), for small sizes

Design values (from the mockup): lowercase "asterism", IBM Plex Sans 500, letter-spacing
−0.03 em; dotless ı with a four-pointed star (0.4 em, centred on the ı, top −0.12 em);
the Dipper in a 200 × 120 unit box (1 unit = 0.01 em) at ı-centre − 1.62 em, top −1.28 em,
seven stars joined by a line, the pour a dotted line in the accent colour down to the star.
Light: ink #15171b, accent #007d93. Dark: ink #f3f2ee, accent #acdae6.
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF  # noqa: E402
from PySide6.QtGui import QFont, QFontMetricsF, QPainterPath  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "asterism", "app", "assets")
S = 100.0                                    # font size in SVG units (1 em = 100)
STARS = [(136, 104), (166, 86), (196, 78), (226, 70), (262, 74), (262, 34), (228, 34)]
LINE = [(136, 104), (166, 86), (196, 78), (226, 70), (262, 74), (262, 34), (228, 34), (226, 70)]
STAR = [(50, 6), (57, 43), (94, 50), (57, 57), (50, 94), (43, 57), (6, 50), (43, 43)]
# The mockup's small-size version (heavier strokes) reads better at app sizes.
STROKE, R, POUR_W, POUR_GAP, POUR = 4.0, 7.0, 5.0, 11.0, (88, 112)
THEMES = {"light": ("#15171b", "#007d93"), "dark": ("#f3f2ee", "#acdae6")}


def _d(path: QPainterPath) -> str:
    """QPainterPath → SVG path data (moves, lines, cubic curves)."""
    out, i, n = [], 0, path.elementCount()
    while i < n:
        e = path.elementAt(i)
        if e.isMoveTo():
            out.append(f"M{e.x:.2f} {e.y:.2f}")
        elif e.isLineTo():
            out.append(f"L{e.x:.2f} {e.y:.2f}")
        elif e.isCurveTo():
            c2, end = path.elementAt(i + 1), path.elementAt(i + 2)
            out.append(f"C{e.x:.2f} {e.y:.2f} {c2.x:.2f} {c2.y:.2f} {end.x:.2f} {end.y:.2f}")
            i += 2
        i += 1
    return "".join(out) + "Z"


def build(dipper: bool, ink: str, accent: str) -> str:
    font = QFont("IBM Plex Sans")
    font.setPixelSize(int(S))
    font.setWeight(QFont.Medium)
    font.setLetterSpacing(QFont.AbsoluteSpacing, -0.03 * S)
    fm = QFontMetricsF(font)
    # The ı's box (line-height 1): baseline sits half-leading + ascent below the box top.
    box_baseline = ((S - (fm.ascent() + fm.descent())) / 2 + fm.ascent())
    x0, base = 0.0, 0.0
    text = QPainterPath()
    x = x0
    for part in ("aster", "ı", "sm"):
        text.addText(QPointF(x, base), font, part)
        if part == "ı":
            cx = x + fm.horizontalAdvance(part) / 2
        x += fm.horizontalAdvance(part)
    top = base - box_baseline                   # top of the ı's em box
    star = QPainterPath()
    sx, sy, size = cx - 0.2 * S, top - 0.12 * S, 0.4 * S
    for k, (u, v) in enumerate(STAR):
        p = QPointF(sx + u / 100 * size, sy + v / 100 * size)
        star.moveTo(p) if k == 0 else star.lineTo(p)
    star.closeSubpath()
    parts = [f'<path d="{_d(text)}" fill="{ink}"/>', f'<path d="{_d(star)}" fill="{accent}"/>']
    if dipper:
        ox, oy = cx - 1.62 * S, top - 1.28 * S

        def m(u, v):
            return ox + (u - 100) * 0.01 * S, oy + v * 0.01 * S
        pts = " ".join(f"{a:.2f},{b:.2f}" for a, b in (m(u, v) for u, v in LINE))
        parts.append(f'<polyline points="{pts}" fill="none" stroke="{ink}" stroke-width="{STROKE * 0.01 * S:.2f}" '
                     f'stroke-linecap="round" stroke-linejoin="round"/>')
        for u, v in STARS:
            a, b = m(u, v)
            parts.append(f'<circle cx="{a:.2f}" cy="{b:.2f}" r="{R * 0.01 * S:.2f}" fill="{ink}"/>')
        v = POUR[0]
        while v <= POUR[1] + 1e-9:              # the pour: round dots every POUR_GAP units
            a, b = m(262, v)
            parts.append(f'<circle cx="{a:.2f}" cy="{b:.2f}" r="{POUR_W / 2 * 0.01 * S:.2f}" fill="{accent}"/>')
            v += POUR_GAP
    # bounds: text, star, dipper
    br = text.boundingRect().united(star.boundingRect())
    left, right, top_, bottom = br.left(), br.right(), br.top(), br.bottom()
    if dipper:
        for u, v in STARS:
            a, b = m(u, v)
            left, right = min(left, a - R), max(right, a + R)
            top_ = min(top_, b - R)
    pad = 2.0
    vb = (left - pad, top_ - pad, right - left + 2 * pad, bottom - top_ + 2 * pad)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb[0]:.2f} {vb[1]:.2f} {vb[2]:.2f} {vb[3]:.2f}" '
            f'width="{vb[2]:.1f}" height="{vb[3]:.1f}" role="img" aria-label="asterism">'
            + "".join(parts) + "</svg>\n")


def build_icon() -> str:
    """App icon: the Dipper pouring into the star, on a dark rounded square (macOS grid:
    824-unit tile with 100-unit margins in a 1024 canvas)."""
    bg, ink, accent = "#15171b", "#f3f2ee", "#acdae6"
    # Logo geometry in Dipper units: the star sits at (262, 136), 40 units wide.
    x0, x1, y0, y1 = 129.0, 290.0, 26.0, 166.0
    k = 600.0 / (x1 - x0)
    ox = 512 - (x0 + x1) / 2 * k
    oy = 512 - (y0 + y1) / 2 * k

    def m(u, v):
        return ox + u * k, oy + v * k
    sw, r, dot = 5.0 * k, 8.0 * k, 3.4 * k              # a little bolder than the logo
    pts = " ".join(f"{a:.1f},{b:.1f}" for a, b in (m(u, v) for u, v in LINE))
    parts = [f'<rect x="100" y="100" width="824" height="824" rx="185" fill="{bg}"/>',
             f'<polyline points="{pts}" fill="none" stroke="{ink}" stroke-width="{sw:.1f}" '
             f'stroke-linecap="round" stroke-linejoin="round"/>']
    parts += [f'<circle cx="{a:.1f}" cy="{b:.1f}" r="{r:.1f}" fill="{ink}"/>' for a, b in (m(u, v) for u, v in STARS)]
    for v in (89.0, 100.0, 111.0):
        a, b = m(262, v)
        parts.append(f'<circle cx="{a:.1f}" cy="{b:.1f}" r="{dot:.1f}" fill="{accent}"/>')
    cx, cy, size = 262, 140, 60.0                       # larger than the logo's: reads at 32 px
    star = " ".join(f"{a:.1f},{b:.1f}" for a, b in (m(cx + (u - 50) / 100 * size, cy + (v - 50) / 100 * size)
                                                      for u, v in STAR))
    parts.append(f'<polygon points="{star}" fill="{accent}"/>')
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024" width="1024" height="1024">'
            + "".join(parts) + "</svg>\n")


def write_icns(svg: str) -> None:
    """asterism.icns for a macOS app bundle (needs iconutil, which ships with macOS)."""
    import shutil
    import subprocess
    import tempfile
    from PySide6.QtCore import QByteArray, QRectF, Qt
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer
    if not shutil.which("iconutil"):
        print("iconutil not found: skipping asterism.icns")
        return
    r = QSvgRenderer(QByteArray(svg.encode()))
    with tempfile.TemporaryDirectory() as tmp:
        iconset = os.path.join(tmp, "asterism.iconset")
        os.makedirs(iconset)
        for size in (16, 32, 128, 256, 512):
            for scale in (1, 2):
                px = size * scale
                img = QImage(px, px, QImage.Format_ARGB32)
                img.fill(Qt.transparent)
                p = QPainter(img)
                p.setRenderHint(QPainter.Antialiasing)
                r.render(p, QRectF(0, 0, px, px))
                p.end()
                img.save(os.path.join(iconset, f"icon_{size}x{size}{'@2x' if scale == 2 else ''}.png"))
        subprocess.run(["iconutil", "-c", "icns", iconset, "-o", os.path.join(OUT, "asterism.icns")], check=True)


def main() -> int:
    app = QApplication(sys.argv)  # noqa: F841
    if "IBM Plex Sans" not in __import__("PySide6.QtGui", fromlist=["QFontDatabase"]).QFontDatabase.families():
        print("IBM Plex Sans is not installed; it is needed to draw the letters.")
        return 1
    os.makedirs(OUT, exist_ok=True)
    for theme, (ink, accent) in THEMES.items():
        for name, dipper in (("logo", True), ("wordmark", False)):
            with open(os.path.join(OUT, f"{name}-{theme}.svg"), "w") as fh:
                fh.write(build(dipper, ink, accent))
    icon = build_icon()
    with open(os.path.join(OUT, "icon.svg"), "w") as fh:
        fh.write(icon)
    write_icns(icon)
    print("written to", os.path.abspath(OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
