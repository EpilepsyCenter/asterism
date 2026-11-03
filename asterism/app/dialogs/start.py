"""Start window: shown when ASTERISM opens without a file (and from File › Start Window).

ASTERISM's own arrangement, a sibling of NED-Net's look: the logo with what ASTERISM does
and its version on top, the ways to begin as a row of tiles, recent projects below.
Closing it starts an empty project.
"""

from __future__ import annotations

import os
import time

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import (QCheckBox, QDialog, QFileDialog, QFrame, QHBoxLayout, QLabel,
                               QListWidget, QListWidgetItem, QPushButton, QSizePolicy, QStyle,
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
        h = int(age // 3600)
        return f"edited {h} hour{'s' if h != 1 else ''} ago"
    if age < 86400 * 2:
        return "edited yesterday"
    return time.strftime("edited %d %b %Y", time.localtime(os.path.getmtime(path)))


TAGLINE = "Graphs and statistics for lab data"
ABOUT = ("Enter or import data into tables, run the analyses (t tests, ANOVA, curve fits, "
         "survival…) and make publication-ready graphs and figures. Compatible with Prism files.")

# the ways to begin: key, title, icon, hint under the title, tooltip
ACTIONS = (
    ("new", "New project…", "tablecells.badge.ellipsis", "Choose the first table",
     "Choose the kind of data table to start with"),
    ("empty", "Empty project", "doc", "One Column table", "Start with an empty Column table"),
    ("import", "Import data…", "square.and.arrow.down.on.square", "Spreadsheets, lab exports, Prism",
     "Spreadsheets (CSV, Excel), lab exports (NED-Net, TRACER, QuantStudio) or Prism files"),
    ("browse", "Open…", "folder", "A project file", "Open a project file"),
    ("sample", "Sample project", "doc.text", "Example data to explore", "Explore a project with example data"),
)


class RecentDelegate(QStyledItemDelegate):
    """Two lines per project: the name, then its folder and when it was edited (muted,
    shortened with … so long paths never need a scroll bar)."""

    def sizeHint(self, option, index):
        return QSize(200, 44)

    def paint(self, p, option, index):
        p.save()
        r = option.rect.adjusted(4, 1, -4, -1)
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
            ico.paint(p, QRect(r.left() + 8, r.center().y() - 10, 20, 20), Qt.AlignCenter,
                      QIcon.Selected if selected else QIcon.Normal)
        name, sub = (index.data(Qt.DisplayRole) or "\n").split("\n", 1)
        x = r.left() + 38
        w = r.right() - x - 6
        f = QFont(option.font)
        f.setBold(True)
        p.setFont(f)
        ink = theme.color("on_accent") if selected else theme.color("text" if enabled else "muted")
        p.setPen(ink)
        p.drawText(QRect(x, r.top() + 4, w, 18), Qt.AlignLeft | Qt.AlignVCenter,
                   QFontMetrics(f).elidedText(name, Qt.ElideRight, w))
        f2 = QFont(option.font)
        f2.setPointSizeF(f2.pointSizeF() * 0.9)
        p.setFont(f2)
        p.setPen(theme.color("on_accent") if selected else theme.color("muted"))
        p.drawText(QRect(x, r.top() + 22, w, 16), Qt.AlignLeft | Qt.AlignVCenter,
                   QFontMetrics(f2).elidedText(sub, Qt.ElideMiddle, w))
        p.restore()


class Tile(QPushButton):
    """A way to begin: icon, title and a short hint, as one button."""

    def __init__(self, title: str, ico: str, hint: str, tip: str):
        super().__init__()
        self.setObjectName("StartTile")
        self.setToolTip(tip)
        self.setCursor(Qt.PointingHandCursor)
        self.setAccessibleName(title)
        self.setFixedHeight(96)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 10)
        lay.setSpacing(3)
        self.icon_label = QLabel()
        self.icon_label.setPixmap(icon(ico, "accent").pixmap(22, 22))
        self.title_label = QLabel(title)
        self.title_label.setObjectName("StartTileTitle")
        self.hint_label = QLabel(hint)
        self.hint_label.setObjectName("StartTileHint")
        self.hint_label.setWordWrap(True)
        for w in (self.icon_label, self.title_label, self.hint_label):
            w.setAttribute(Qt.WA_TransparentForMouseEvents)
        lay.addWidget(self.icon_label)
        lay.addSpacing(2)
        lay.addWidget(self.title_label)
        lay.addWidget(self.hint_label)
        lay.addStretch(1)


class StartDialog(QDialog):
    """result(): ("new",) | ("empty",) | ("open", path) | ("import", paths) | ("sample",).

    Top to bottom: the logo with what ASTERISM does and its version, the ways to begin as
    a row of tiles, recent projects (the newest preselected: Return opens it), and a footer.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ASTERISM")
        self.setObjectName("StartWindow")
        self._choice = ("empty",)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Logo, what ASTERISM does, version ---------------------------------------------
        hero = QFrame()
        hero.setObjectName("StartHero")
        hl = QVBoxLayout(hero)
        hl.setContentsMargins(32, 28, 32, 22)
        hl.setSpacing(6)
        from ..logo import Logo
        self.logo = Logo(90, dipper=True)
        hl.addWidget(self.logo, 0, Qt.AlignLeft)
        hl.addSpacing(8)
        tag = QLabel(TAGLINE)
        tag.setObjectName("StartTagline")
        hl.addWidget(tag)
        about = QLabel(ABOUT)
        about.setObjectName("StartAbout")
        about.setWordWrap(True)
        about.setMaximumWidth(600)
        hl.addWidget(about)
        from asterism import __version__
        self.version = QLabel(f"Version {__version__}")
        self.version.setObjectName("StartVersion")
        self.whats_new_btn = QPushButton("What's New")
        self.whats_new_btn.setIcon(icon("doc.text", "accent"))
        self.whats_new_btn.setToolTip("What changed in this version")
        self.whats_new_btn.clicked.connect(self._whats_new)
        self.help_btn = QPushButton("Help")
        self.help_btn.setIcon(icon("questionmark.circle", "accent"))
        self.help_btn.setToolTip("Open ASTERISM Help")
        self.help_btn.clicked.connect(self._help)
        info = QHBoxLayout()
        info.setSpacing(8)
        info.addWidget(self.version)
        info.addSpacing(8)
        for b in (self.whats_new_btn, self.help_btn):
            b.setAutoDefault(False)              # Return still opens the selected project
            b.setCursor(Qt.PointingHandCursor)
            info.addWidget(b)
        info.addStretch(1)
        hl.addSpacing(4)
        hl.addLayout(info)
        root.addWidget(hero)

        # The ways to begin ----------------------------------------------------------------
        body = QWidget()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(24, 20, 24, 16)
        bl.setSpacing(10)
        tiles = QHBoxLayout()
        tiles.setSpacing(10)
        self.buttons = {}
        for key, title, ico, hint, tip in ACTIONS:
            b = Tile(title, ico, hint, tip)
            b.clicked.connect(lambda _=False, k=key: self._pick(k))
            tiles.addWidget(b)
            self.buttons[key] = b
        bl.addLayout(tiles)
        bl.addSpacing(10)

        # Recent projects ------------------------------------------------------------------
        head = QLabel("Recent projects")
        head.setObjectName("StartHeading")
        bl.addWidget(head)
        self.recent = QListWidget()
        self.recent.setObjectName("StartRecent")
        self.recent.setIconSize(QSize(20, 20))
        self.recent.setSpacing(1)
        self.recent.setItemDelegate(RecentDelegate(self.recent))
        self.recent.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.recent.setMouseTracking(True)
        files = documents.recent_files()
        for path in files:
            exists = os.path.exists(path)
            name = os.path.splitext(os.path.basename(path))[0]
            folder = os.path.dirname(path).replace(os.path.expanduser("~"), "~")
            it = QListWidgetItem(icon("doc.text", "accent" if exists else None, selected=True),
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
        bl.addWidget(self.recent, 1)
        bl.addWidget(self.empty_note, 1)
        root.addWidget(body, 1)

        # Footer -----------------------------------------------------------------------------
        foot = QFrame()
        foot.setObjectName("StartFoot")
        fl = QHBoxLayout(foot)
        fl.setContentsMargins(24, 10, 24, 14)
        self.c_show = QCheckBox("Show this window at startup")
        self.c_show.setObjectName("StartShow")
        self.c_show.setChecked(show_at_startup())
        self.c_show.toggled.connect(lambda on: documents.set_value(SHOW_KEY, on))
        fl.addWidget(self.c_show)
        fl.addStretch(1)
        self.open_btn = QPushButton("Open")
        self.open_btn.setDefault(True)
        self.open_btn.setEnabled(False)
        self.open_btn.clicked.connect(lambda: self._open_item(self._chosen()))
        self.recent.itemSelectionChanged.connect(self._sync_open)      # Open follows the highlighted row
        self.recent.currentItemChanged.connect(lambda *_: self._sync_open())
        fl.addWidget(self.open_btn)
        root.addWidget(foot)

        first = next((self.recent.item(i) for i in range(self.recent.count())
                      if self.recent.item(i).flags() & Qt.ItemIsEnabled), None)
        if first is not None:                  # Return reopens the latest project
            self.recent.setCurrentItem(first)
            self.recent.setFocus()
        # Set Open from the highlight now, not only on change signals: launched from Finder,
        # Qt can make the first row current before they're connected, and no signal follows.
        self._sync_open()
        self.setStyleSheet(self._style())
        theme.notifier.changed.connect(lambda: self.setStyleSheet(self._style()))
        self.resize(880, 700)

    def _style(self) -> str:
        t = {k: theme.color(k).name() for k in ("accent", "sidebar", "text", "muted", "field")}
        t["border"] = theme.mix("chrome", "text", 0.12).name()      # solid: names drop alpha
        t["tile_hover"] = theme.mix("field", "accent", 0.08).name()
        return f"""
QFrame#StartHero {{ background: {t['sidebar']}; border-bottom: 1px solid {t['border']}; }}
QLabel#StartTagline {{ color: {t['text']}; font-size: 17px; font-weight: 700; }}
QLabel#StartAbout {{ color: {t['muted']}; font-size: 13px; }}
QLabel#StartVersion {{ color: {t['muted']}; font-size: 12px; }}
QLabel#StartHeading {{ color: {t['text']}; font-size: 15px; font-weight: 700; }}
QLabel#StartEmpty {{ color: {t['muted']}; border: 1px dashed {t['border']}; border-radius: 8px; }}
QPushButton#StartTile {{ text-align: left; border: 1px solid {t['border']}; border-radius: 10px;
                         background: {t['field']}; padding: 0; min-height: 96px; max-height: 96px; }}
QPushButton#StartTile:hover {{ border-color: {t['accent']}; background: {t['tile_hover']}; }}
QPushButton#StartTile:focus {{ border-color: {t['accent']}; }}
QLabel#StartTileTitle {{ color: {t['text']}; font-size: 14px; font-weight: 600; background: transparent; }}
QLabel#StartTileHint {{ color: {t['muted']}; font-size: 12px; background: transparent; }}
QListWidget#StartRecent {{ border: 1px solid {t['border']}; border-radius: 8px; background: {t['field']};
                           padding: 4px; }}
QListWidget#StartRecent::item {{ padding: 4px 6px; border-radius: 6px; }}
QFrame#StartFoot {{ border-top: 1px solid {t['border']}; }}
"""

    def _chosen(self):
        """The highlighted project, if it can be opened."""
        return next((it for it in self.recent.selectedItems() if it.flags() & Qt.ItemIsEnabled), None)

    def _sync_open(self) -> None:
        self.open_btn.setEnabled(self._chosen() is not None)

    def _whats_new(self) -> None:
        from .whats_new import show_from_menu
        show_from_menu(self)                     # a child of this window, so it can be used

    def _help(self) -> None:
        from ..help_window import show_page
        show_page("start", "the-start-window")

    def _pick(self, key: str) -> None:
        if key == "browse":
            start = documents.last_dir()
            path, _ = QFileDialog.getOpenFileName(self, "Open Project", start, documents.FILE_FILTER)
            if not path:
                return
            self._choice = ("open", path)
        elif key == "import":
            paths, _ = QFileDialog.getOpenFileNames(self, "Import Data", documents.last_dir(),
                                                    documents.IMPORT_FILTER)
            if not paths:
                return
            self._choice = ("import", paths)
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
