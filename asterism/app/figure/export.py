"""Export a figure at its exact page size: SVG (every panel a named group, live text),
PDF (vector), PNG and TIFF (chosen resolution)."""

from __future__ import annotations

from PySide6.QtCore import QMarginsF, QSizeF
from PySide6.QtGui import QColor, QImage, QPageLayout, QPageSize, QPainter, QPdfWriter

from ..graph.canvas import QtCanvas, SvgCanvas
from .layout import build_figure


def _draw_all(cv, elements) -> None:
    for e in elements:
        e.draw(cv)


def svg_bytes(fig, project) -> bytes:
    page, els = build_figure(fig, project)
    cv = SvgCanvas(page)
    cv.rect(0, 0, page.width(), page.height(), fill="#ffffff")
    _draw_all(cv, els)
    return cv.tostring().encode("utf-8")


def export_svg(fig, project, path: str) -> None:
    with open(path, "wb") as f:
        f.write(svg_bytes(fig, project))


def export_pdf(fig, project, path: str) -> None:
    page, els = build_figure(fig, project)
    w = QPdfWriter(path)
    w.setResolution(72)
    w.setPageSize(QPageSize(QSizeF(page.width(), page.height()), QPageSize.Point, "", QPageSize.ExactMatch))
    w.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Point)
    w.setCreator("ASTERISM")
    w.setTitle(fig.name)
    p = QPainter(w)
    _draw_all(QtCanvas(p), els)
    p.end()


def render_image(fig, project, dpi: int = 300) -> QImage:
    page, els = build_figure(fig, project)
    s = dpi / 72.0
    img = QImage(int(round(page.width() * s)), int(round(page.height() * s)), QImage.Format_ARGB32)
    img.setDotsPerMeterX(int(dpi / 0.0254))
    img.setDotsPerMeterY(int(dpi / 0.0254))
    img.fill(QColor("white"))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(s, s)
    _draw_all(QtCanvas(p), els)
    p.end()
    return img


def export_image(fig, project, path: str, dpi: int = 300) -> None:
    """PNG or TIFF, chosen by the file's extension."""
    fmt = "TIFF" if path.lower().endswith((".tif", ".tiff")) else "PNG"
    render_image(fig, project, dpi).save(path, fmt)
