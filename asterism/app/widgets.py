"""Small widgets shared by the window and the dialogs."""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QIcon, QPainter
from PySide6.QtWidgets import QStyle, QStyledItemDelegate

from . import theme


class NavDelegate(QStyledItemDelegate):
    """Sidebar rows (project sidebar and dialog sections), like NED-Net's nav items:
    rounded, filled with the accent when selected, a soft tint on hover."""

    ROW_H = 24

    def sizeHint(self, option, index):
        return QSize(option.rect.width(), self.ROW_H)

    def paint(self, p: QPainter, opt, index) -> None:
        sel = bool(opt.state & QStyle.State_Selected)
        hover = bool(opt.state & QStyle.State_MouseOver) and bool(index.flags() & Qt.ItemIsSelectable)
        r = QRectF(opt.rect).adjusted(0, 1, -1, -1)
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        if sel or hover:
            p.setPen(Qt.NoPen)
            p.setBrush(theme.color("accent") if sel else theme.mix("sidebar", "text", 0.07))
            p.drawRoundedRect(r, 6, 6)
        x = r.left() + 5
        ico = index.data(Qt.DecorationRole)
        if isinstance(ico, QIcon) and not ico.isNull():
            s = 15
            ico.paint(p, int(x), int(r.center().y() - s / 2), s, s, Qt.AlignCenter,
                      QIcon.Selected if sel else QIcon.Normal)
            x += s + 6
        f = index.data(Qt.FontRole) or opt.font
        p.setFont(f)
        fg = index.data(Qt.ForegroundRole)
        p.setPen(theme.color("on_accent") if sel else (fg.color() if fg is not None else theme.color("text")))
        text_r = QRectF(x, r.top(), r.right() - x - 4, r.height())
        text = p.fontMetrics().elidedText(index.data(Qt.DisplayRole) or "", Qt.ElideRight,
                                          int(text_r.width()))
        p.drawText(text_r, Qt.AlignVCenter | Qt.AlignLeft, text)
        p.restore()
