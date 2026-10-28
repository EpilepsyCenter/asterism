"""Icons: Lucide's outline icons (ISC licence, asterism/app/assets/lucide), bundled so the
app looks the same on macOS, Windows and Linux. Drawn in the theme's colours.

Code asks for icons by short names (originally Apple's SF Symbol names); `LUCIDE` maps each
to its Lucide file. Default icons take the theme's icon grey; named accents map to NED-Net's
semantic colours. `set_icon` re-tints an action or widget when the theme switches.
"""

from __future__ import annotations

import os

from PySide6.QtCore import QByteArray, QObject, QRectF, QSize, Qt, Slot
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from . import theme

ASSETS = os.path.join(os.path.dirname(__file__), "assets", "lucide")

# Old Prism-ish accent names -> theme tokens.
ACCENTS = {"blue": "accent", "teal": "accent", "green": "success", "red": "danger",
           "orange": "warning", "purple": "purple", "muted": "muted", "accent": "accent"}

# icon name used in the code -> Lucide file (without .svg)
LUCIDE = {
    "align.horizontal.center": "align-horizontal-justify-center",
    "align.horizontal.left": "align-horizontal-justify-start",
    "align.vertical.top": "align-vertical-justify-start",
    "arrow.counterclockwise": "rotate-ccw",
    "arrow.left.and.right": "move-horizontal",
    "arrow.left.and.right.square": "stretch-horizontal",
    "arrow.left.arrow.right.square": "arrow-left-right",
    "arrow.up.and.down": "move-vertical",
    "arrow.up.and.down.and.arrow.left.and.right": "move",
    "arrow.up.and.down.square": "panel-right-open",
    "arrow.up.arrow.down": "arrow-up-down",
    "arrow.up.right": "arrow-up-right",
    "arrow.uturn.backward": "undo-2",
    "arrow.uturn.forward": "redo-2",
    "asterisk": "asterisk",
    "bold": "bold",
    "character": "omega",
    "chart.bar": "chart-column",
    "chart.bar.xaxis": "chart-column-big",
    "chart.dots.scatter": "chart-scatter",
    "chart.line.uptrend.xyaxis": "chart-line",
    "chart.pie": "chart-pie",
    "chart.xyaxis.line": "chart-spline",
    "checkmark.seal": "badge-check",
    "chevron.down": "chevron-down",
    "chevron.up": "chevron-up",
    "circle": "circle",
    "circle.grid.2x2": "grip",
    "circle.hexagongrid": "orbit",
    "doc.badge.gearshape": "file-cog",
    "doc.badge.plus": "file-plus",
    "doc.on.clipboard": "clipboard-paste",
    "doc.on.clipboard.fill": "clipboard-copy",
    "doc.on.doc": "copy",
    "doc.richtext": "file-output",
    "doc.text": "file-text",
    "eye": "eye",
    "eye.slash": "eye-off",
    "folder": "folder-open",
    "function": "square-function",
    "gearshape": "settings",
    "heart.text.square": "heart-pulse",
    "info.circle": "info",
    "italic": "italic",
    "keyboard": "keyboard",
    "line.3.horizontal.decrease": "list-filter",
    "line.diagonal": "slash",
    "list.bullet.rectangle": "list",
    "list.number": "list-ordered",
    "magnifyingglass": "search",
    "minus.magnifyingglass": "zoom-out",
    "note.text": "notebook-text",
    "note.text.badge.plus": "notebook-pen",
    "paintbrush": "paintbrush",
    "paintpalette": "palette",
    "percent": "percent",
    "photo": "image",
    "photo.stack": "images",
    "plus.magnifyingglass": "zoom-in",
    "plus.rectangle.on.rectangle": "image-plus",
    "plus.square.on.square": "copy-plus",
    "point.topleft.down.to.point.bottomright.curvepath": "spline",
    "printer": "printer",
    "questionmark.circle": "circle-help",
    "rectangle": "square",
    "rectangle.badge.minus": "square-minus",
    "rectangle.grid.1x2": "app-window",
    "rectangle.split.2x2": "layout-dashboard",
    "rectangle.split.3x1": "columns-3",
    "ruler": "ruler",
    "save.as": "save-all",
    "scissors": "scissors",
    "sidebar.left": "panel-left",
    "sidebar.right": "panel-right",
    "slider.horizontal.3": "sliders-horizontal",
    "square.3.layers.3d.bottom.filled": "send-to-back",
    "square.3.layers.3d.top.filled": "bring-to-front",
    "square.and.arrow.down": "save",
    "square.and.arrow.down.on.square": "import",
    "square.and.arrow.up": "share",
    "square.dashed": "square-dashed",
    "square.grid.2x2": "layout-grid",
    "square.grid.3x2": "grid-3x2",
    "square.grid.3x3.square": "grid-3x3",
    "square.split.1x2": "columns-3",
    "square.stack.3d.down.right": "layers",
    "sum": "sigma",
    "tablecells": "table",
    "tablecells.badge.ellipsis": "table-properties",
    "tag": "tag",
    "text.aligncenter": "align-center",
    "text.alignleft": "align-left",
    "text.alignright": "align-right",
    "text.badge.minus": "list-minus",
    "text.insert": "between-horizontal-start",
    "textbox": "text-cursor-input",
    "textformat": "type",
    "textformat.alt": "baseline",
    "textformat.subscript": "subscript",
    "textformat.superscript": "superscript",
    "trash": "trash-2",
    "underline": "underline",
    "wand.and.rays": "wand-sparkles",
    "waveform.path.ecg": "activity",
    "x.squareroot": "radical",
    "xmark": "x",
    "arrow.left.arrow.right": "arrow-left-right",
    "arrow.right.to.line": "arrow-right-to-line",
    "clock.arrow.circlepath": "history",
    "doc": "file",
    "list.bullet": "list",
    "lock": "lock",
    "minus.forwardslash.plus": "diff",
    "pencil": "pencil",
    "rectangle.split.2x1": "columns-2",
    "squareshape.split.3x3": "grid-3x3",
    "waveform.path": "audio-waveform",
    "xmark.circle": "circle-x",
}

_cache: dict[tuple, QIcon] = {}
_svg: dict[str, str] = {}


def _source(name: str) -> str | None:
    file = LUCIDE.get(name)
    if file is None:
        return None
    if file not in _svg:
        try:
            with open(os.path.join(ASSETS, f"{file}.svg"), encoding="utf-8") as f:
                _svg[file] = f.read()
        except OSError:
            return None
    return _svg[file]


def _render(svg: str, c: QColor, size: int, scale: int) -> QPixmap:
    data = svg.replace("currentColor", c.name())
    r = QSvgRenderer(QByteArray(data.encode("utf-8")))
    img = QImage(size * scale, size * scale, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    pad = size * scale * 0.04                  # Lucide fills its 24-unit box; leave a hair of air
    r.render(p, QRectF(pad, pad, size * scale - 2 * pad, size * scale - 2 * pad))
    p.end()
    pm = QPixmap.fromImage(img)
    pm.setDevicePixelRatio(scale)
    return pm


def icon(name: str, accent: str | None = None, size: int = 20, selected: bool = False) -> QIcon:
    """Tinted icon; `selected` adds a white (on-accent) pixmap for selected rows."""
    key = (name, accent, size, selected, theme.is_dark())
    if key in _cache:
        return _cache[key]
    svg = _source(name)
    if svg is None:
        return QIcon()
    c = theme.color(ACCENTS.get(accent, "icon") if accent else "icon")
    if accent and accent.startswith("#"):
        c = QColor(accent)
    dis = theme.mix("chrome", "muted", 0.55)
    out = QIcon()
    for scale in (1, 2):
        out.addPixmap(_render(svg, c, size, scale), QIcon.Normal)
        out.addPixmap(_render(svg, c, size, scale), QIcon.Active)
        out.addPixmap(_render(svg, dis, size, scale), QIcon.Disabled)
        if selected:
            out.addPixmap(_render(svg, theme.color("on_accent"), size, scale), QIcon.Selected)
    _cache[key] = out
    return out


class _Binder(QObject):
    """Child of the target, so the connection dies with it."""

    def __init__(self, target, args):
        super().__init__(target)
        self.setObjectName("_iconbinder")
        self.target, self.args = target, args
        theme.notifier.changed.connect(self.reapply)

    @Slot()
    def reapply(self) -> None:
        self.target.setIcon(icon(*self.args))


def set_icon(target, name: str, accent: str | None = None) -> None:
    """Set a tinted icon on a QAction / QAbstractButton and keep it in step with the theme."""
    target.setIcon(icon(name, accent))
    b = target.findChild(_Binder, "_iconbinder")
    if b is None:
        _Binder(target, (name, accent))
    else:
        b.args = (name, accent)
