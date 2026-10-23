"""Icons: SF Symbols on macOS (Qt's theme-icon engine), tinted with the theme colours.

Default icons take the theme's icon grey; named accents map to NED-Net's semantic
colours. `set_icon` re-tints an action or widget when the theme switches.
On Windows the same XDG names map to Segoe Fluent icons (Qt 6.7+); SF-only names
will need a fallback set before a Windows build — noted, not solved, in the spike.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QSize, Qt, Slot
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap

from . import theme

# Old Prism-ish accent names -> theme tokens.
ACCENTS = {"blue": "accent", "teal": "accent", "green": "success", "red": "danger",
           "orange": "warning", "purple": "purple", "muted": "muted", "accent": "accent"}

_cache: dict[tuple, QIcon] = {}


def _tint(base: QIcon, c: QColor, size: int, scale: int) -> QPixmap:
    pm = base.pixmap(QSize(size, size), scale)
    out = QPixmap(pm.size())
    out.setDevicePixelRatio(pm.devicePixelRatio())
    out.fill(Qt.transparent)
    p = QPainter(out)
    p.drawPixmap(0, 0, pm)
    p.setCompositionMode(QPainter.CompositionMode_SourceIn)
    p.fillRect(out.rect(), c)
    p.end()
    return out


def icon(name: str, accent: str | None = None, size: int = 20, selected: bool = False) -> QIcon:
    """Tinted theme icon; `selected` adds a white (on-accent) pixmap for selected rows."""
    key = (name, accent, size, selected, theme.is_dark())
    if key in _cache:
        return _cache[key]
    base = QIcon.fromTheme(name)
    if base.isNull():
        return base
    c = theme.color(ACCENTS.get(accent, "icon") if accent else "icon")
    if accent and accent.startswith("#"):
        c = QColor(accent)
    dis = theme.mix("chrome", "muted", 0.55)
    out = QIcon()
    for scale in (1, 2):
        out.addPixmap(_tint(base, c, size, scale), QIcon.Normal)
        out.addPixmap(_tint(base, c, size, scale), QIcon.Active)
        out.addPixmap(_tint(base, dis, size, scale), QIcon.Disabled)
        if selected:
            out.addPixmap(_tint(base, theme.color("on_accent"), size, scale), QIcon.Selected)
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
