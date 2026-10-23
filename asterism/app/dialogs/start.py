"""Start window: shown when ASTERISM opens without a file (and from File › Start Window).

ASTERISM's own arrangement, a sibling of NED-Net's look: a side panel with the wordmark
and the ways to begin, recent projects on the right. Closing it starts an empty project.
"""

from __future__ import annotations

import os
import time

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import (QCheckBox, QDialog, QFileDialog, QFrame, QHBoxLayout, QLabel,
                               QListWidget, QListWidgetItem, QPushButton, QStyle,
                               QStyledItemDelegate, QVBoxLayout, QWidget)

from .. import documents, theme
from ..icons import icon

SHOW_KEY = "start/show"


def show_at_startup() -> bool:
    return documents.value(SHOW_KEY, True) not in (False, "false", "0", 0)


def _when(path: str) -> str:
    try:
        age = time.time() - os.path.getmtime(path)
    except OSError:
        return "not found"
    if age < 3600:
        return "edited just now" if age < 120 else f"edited {int(age // 60)} minutes ago"
    if age < 86400:
        return f"edited {int(age // 3600)} hours ago"
    if age < 86400 * 2:
        return "edited yesterday"
    return time.strftime("edited %d %b %Y", time.localtime(os.path.getmtime(path)))


class RecentDelegate(QStyledItemDelegate):
    """Two lines per project: the name, then its folder and when it was edited (muted,
    shortened with … so long paths never need a scroll bar)."""

    def sizeHint(self, option, index):
        return QSize(200, 50)

    def paint(self, p, option, index):
        p.save()
        r = option.rect.adjusted(4, 2, -4, -2)
        selected = bool(option.state & QStyle.State_Selected)
        enabled = bool(index.flags() & Qt.ItemIsEnabled)
        if selected:
            p.setPen(Qt.NoPen)
            p.setBrush(theme.color("accent"))
            p.drawRoundedRect(r, 6, 6)
        elif option.state & QStyle.State_MouseOver and enabled:
            p.setPen(Qt.NoPen)
            p.setBrush(theme.mix("field", "text", 0.06))
            p.drawRoundedRect(r, 6, 6)
        ico = index.data(Qt.DecorationRole)
        if ico is not None:
            from PySide6.QtGui import QIcon
            ico.paint(p, QRect(r.left() + 8, r.center().y() - 11, 22, 22), Qt.AlignCenter,
                      QIcon.Selected if selected else QIcon.Normal)
        name, sub = (index.data(Qt.DisplayRole) or "\n").split("\n", 1)
        x = r.left() + 40
        w = r.right() - x - 6
        f = QFont(option.font)
        f.setBold(True)
        p.setFont(f)
        ink = theme.color("on_accent") if selected else theme.color("text" if enabled else "muted")
        p.setPen(ink)
        p.drawText(QRect(x, r.top() + 5, w, 20), Qt.AlignLeft | Qt.AlignVCenter,
                   QFontMetrics(f).elidedText(name, Qt.ElideRight, w))
        f2 = QFont(option.font)
        f2.setPointSizeF(f2.pointSizeF() * 0.9)
        p.setFont(f2)
        p.setPen(theme.color("on_accent") if selected else theme.color("muted"))
        p.drawText(QRect(x, r.top() + 25, w, 18), Qt.AlignLeft | Qt.AlignVCenter,
                   QFontMetrics(f2).elidedText(sub, Qt.ElideMiddle, w))
        p.restore()


class StartDialog(QDialog):
    """result(): ("new",) | ("empty",) | ("open", path) | ("sample",)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ASTERISM")
        self.setObjectName("StartWindow")
        self._choice = ("empty",)
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Side panel: wordmark and the ways to begin -----------------------------------
        side = QFrame()
        side.setObjectName("StartSide")
        side.setFixedWidth(270)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(22, 26, 22, 18)
        sl.setSpacing(6)
        from ..logo import Logo
        self.logo = Logo(88, dipper=True)
        sl.addWidget(self.logo, 0, Qt.AlignLeft)
        sl.addSpacing(6)
        from asterism import __version__
        tag = QLabel(f"Graphs and statistics · {__version__}")
        tag.setObjectName("StartTagline")
        sl.addWidget(tag)
        sl.addSpacing(22)
        self.buttons = {}
        for key, text, ico, tip in (
                ("new", "New project…", "tablecells.badge.ellipsis", "Choose the kind of data table to start with"),
                ("empty", "Empty project", "doc", "Start with an empty Column table"),
                ("browse", "Open…", "folder", "Open a project file"),
                ("sample", "Sample project", "doc.text", "Explore a project with example data")):
            b = QPushButton(text)
            b.setObjectName("StartAction")
            b.setIcon(icon(ico, "accent"))
            b.setIconSize(QSize(18, 18))
            b.setToolTip(tip)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=key: self._pick(k))
            sl.addWidget(b)
            self.buttons[key] = b
        sl.addStretch(1)
        self.c_show = QCheckBox("Show this window at startup")
        self.c_show.setObjectName("StartShow")
        self.c_show.setChecked(show_at_startup())
        self.c_show.toggled.connect(lambda on: documents.set_value(SHOW_KEY, on))
        sl.addWidget(self.c_show)
        root.addWidget(side)

        # Recent projects --------------------------------------------------------------
        main = QWidget()
        ml = QVBoxLayout(main)
        ml.setContentsMargins(24, 26, 24, 18)
        ml.setSpacing(8)
        head = QLabel("Recent projects")
        head.setObjectName("StartHeading")
        ml.addWidget(head)
        self.recent = QListWidget()
        self.recent.setObjectName("StartRecent")
        self.recent.setIconSize(QSize(22, 22))
        self.recent.setSpacing(1)
        self.recent.setItemDelegate(RecentDelegate(self.recent))
        self.recent.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.recent.setMouseTracking(True)
        files = documents.recent_files()
        for path in files:
            exists = os.path.exists(path)
            name = os.path.splitext(os.path.basename(path))[0]
            folder = os.path.dirname(path).replace(os.path.expanduser("~"), "~")
            it = QListWidgetItem(icon("doc.richtext", "accent" if exists else None, selected=True),
                                 f"{name}\n{folder} · {_when(path)}")
            it.setData(Qt.UserRole, path)
            it.setToolTip(path)
            if not exists:
                it.setFlags(Qt.NoItemFlags)
            self.recent.addItem(it)
        self.empty_note = QLabel("Projects you open or save appear here.")
        self.empty_note.setObjectName("StartEmpty")
        self.empty_note.setAlignment(Qt.AlignCenter)
        self.empty_note.setVisible(not files)
        self.recent.setVisible(bool(files))
        self.recent.itemActivated.connect(self._open_item)
        self.recent.itemDoubleClicked.connect(self._open_item)
        ml.addWidget(self.recent, 1)
        ml.addWidget(self.empty_note, 1)
        row = QHBoxLayout()
        row.addStretch(1)
        self.open_btn = QPushButton("Open")
        self.open_btn.setDefault(True)
        self.open_btn.setEnabled(False)
        self.open_btn.clicked.connect(lambda: self._open_item(self.recent.currentItem()))
        self.recent.currentItemChanged.connect(
            lambda it, _p: self.open_btn.setEnabled(bool(it) and bool(it.flags() & Qt.ItemIsEnabled)))
        row.addWidget(self.open_btn)
        ml.addLayout(row)
        root.addWidget(main, 1)
        self.setStyleSheet(self._style())
        self.resize(820, 500)

    def _style(self) -> str:
        t = {k: theme.color(k).name() for k in ("accent", "sidebar", "text", "muted", "field")}
        t["border"] = theme.mix("chrome", "text", 0.12).name()      # solid: names drop alpha
        t["hover"] = theme.mix("sidebar", "text", 0.07).name()
        return f"""
QFrame#StartSide {{ background: {t['sidebar']}; border-right: 1px solid {t['border']}; }}
QLabel#StartWordmark {{ color: {t['accent']}; font-size: 26px; font-weight: 800; letter-spacing: 1px; }}
QLabel#StartTagline {{ color: {t['muted']}; font-size: 12px; }}
QLabel#StartHeading {{ color: {t['text']}; font-size: 15px; font-weight: 700; }}
QLabel#StartEmpty {{ color: {t['muted']}; }}
QPushButton#StartAction {{ text-align: left; padding: 8px 10px; border: none; border-radius: 7px;
                           background: transparent; color: {t['text']}; font-size: 14px; }}
QPushButton#StartAction:hover {{ background: {t['hover']}; }}
QListWidget#StartRecent {{ border: 1px solid {t['border']}; border-radius: 8px; background: {t['field']};
                           padding: 4px; }}
QListWidget#StartRecent::item {{ padding: 6px 6px; border-radius: 6px; }}
"""

    def _pick(self, key: str) -> None:
        if key == "browse":
            start = documents.last_dir()
            path, _ = QFileDialog.getOpenFileName(self, "Open Project", start,
                                                  "ASTERISM projects (*.asterism);;All files (*)")
            if not path:
                return
            self._choice = ("open", path)
        else:
            self._choice = (key,)
        self.accept()

    def _open_item(self, it) -> None:
        if it is None or not (it.flags() & Qt.ItemIsEnabled):
            return
        self._choice = ("open", it.data(Qt.UserRole))
        self.accept()

    def result_choice(self) -> tuple:
        return self._choice
