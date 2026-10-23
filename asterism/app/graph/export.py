"""Export a graph to SVG / PDF / PNG from the same elements the editor shows."""

from __future__ import annotations

from PySide6.QtCore import QMarginsF, QSizeF, Qt
from PySide6.QtGui import QColor, QImage, QPageLayout, QPageSize, QPainter, QPdfWriter

from .canvas import QtCanvas, SvgCanvas
from .layout import build, content_bounds


def svg_bytes(graph) -> bytes:
    els, _ = build(graph)
    b = content_bounds(els)
    cv = SvgCanvas(b)
    for e in els:
        cv.begin_group(e.id)
        e.draw(cv)
        cv.end_group()
    return cv.tostring().encode("utf-8")


def export_svg(graph, path: str) -> None:
    with open(path, "wb") as f:
        f.write(svg_bytes(graph))


def export_pdf(graph, path: str) -> None:
    els, _ = build(graph)
    b = content_bounds(els)
    w = QPdfWriter(path)
    w.setResolution(72)
    w.setPageSize(QPageSize(QSizeF(b.width(), b.height()), QPageSize.Point, "",
                            QPageSize.ExactMatch))
    w.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Point)
    w.setCreator("ASTERISM")
    w.setTitle(graph.name)
    p = QPainter(w)
    p.translate(-b.x(), -b.y())
    cv = QtCanvas(p)
    for e in els:
        e.draw(cv)
    p.end()


def export_png(graph, path: str, dpi: int = 300) -> None:
    els, _ = build(graph)
    b = content_bounds(els)
    s = dpi / 72.0
    img = QImage(int(b.width() * s), int(b.height() * s), QImage.Format_ARGB32)
    img.setDotsPerMeterX(int(dpi / 0.0254))
    img.setDotsPerMeterY(int(dpi / 0.0254))
    img.fill(QColor("white"))
    p = QPainter(img)
    p.scale(s, s)
    p.translate(-b.x(), -b.y())
    cv = QtCanvas(p)
    for e in els:
        e.draw(cv)
    p.end()
    img.save(path)
