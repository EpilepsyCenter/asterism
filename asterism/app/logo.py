"""The ASTERISM logo, drawn from the SVGs in assets/ (built by tools/make_logo.py).

`Logo(height, dipper=True)`: the wordmark with the Big Dipper pouring into the i (Start
window); `dipper=False`: the wordmark alone, the star dotting the i (small places such as
the sidebar). Follows the light/dark theme live.
"""

from __future__ import annotations

import os

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QSizePolicy, QWidget

from . import theme

ASSETS = os.path.join(os.path.dirname(__file__), "assets")


def svg_path(dipper: bool = True, dark: bool | None = None) -> str:
    dark = theme.is_dark() if dark is None else dark
    return os.path.join(ASSETS, f"{'logo' if dipper else 'wordmark'}-{'dark' if dark else 'light'}.svg")


class Logo(QWidget):
    def __init__(self, height: int, dipper: bool = True, parent=None):
        super().__init__(parent)
        self.dipper = dipper
        self._h = height
        self._renderer = None
        self._load()
        theme.notifier.changed.connect(self._load)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setToolTip("ASTERISM")

    def _load(self) -> None:
        self._renderer = QSvgRenderer(svg_path(self.dipper))
        self.setFixedSize(self.sizeHint())
        self.update()

    def sizeHint(self) -> QSize:
        s = self._renderer.defaultSize() if self._renderer else QSize(4, 1)
        return QSize(round(self._h * s.width() / max(s.height(), 1)), self._h)

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        self._renderer.render(p, QRectF(0, 0, self.width(), self.height()))
