"""Project sidebar (NED-Net's sidebar structure): wordmark, search, and the project's
sheets in three sections — Data (each table with its analyses and graphs nested under
it), Notes and Figures — each with a "+" button. SPEC §5, §12."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QLineEdit, QMenu, QToolButton,
                               QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from . import theme
from .icons import icon, set_icon
from .widgets import NavDelegate
from ..doc.model import Table, Project, Sheet

KIND_ICON = {"table": "tablecells", "analysis": "list.bullet.rectangle",
             "graph": "chart.xyaxis.line", "info": "note.text", "figure": "rectangle.split.2x2"}
SECTIONS = [("Data", "new_table", "New data table"), ("Notes", "new_info", "New notes"),
            ("Figures", "new_figure", "New figure")]


SHEET_MIME = "application/x-asterism-sheet"


class NavTree(QTreeWidget):
    """The sheet list; graphs, tables and results can be dragged onto a figure."""

    def mimeTypes(self):
        return [SHEET_MIME]

    def mimeData(self, items):
        from PySide6.QtCore import QMimeData
        md = QMimeData()
        refs = []
        for it in items:
            sh = it.data(0, Qt.UserRole)
            kind = {"graph": "graph", "table": "table", "analysis": "results"}.get(getattr(sh, "kind", ""))
            if kind:
                refs.append(f"{kind}:{sh.id}")
        md.setData(SHEET_MIME, "\n".join(refs).encode())
        return md


class _SectionHeader(QWidget):
    def __init__(self, title: str, tip: str, on_add):
        super().__init__()
        h = QHBoxLayout(self)
        h.setContentsMargins(6, 10, 0, 2)
        lab = QLabel(title)
        lab.setObjectName("SectionLabel")
        add = QToolButton()
        add.setObjectName("SectionAdd")
        add.setText("+")
        add.setToolTip(tip)
        add.setAutoRaise(True)
        add.clicked.connect(on_add)
        h.addWidget(lab)
        h.addStretch(1)
        h.addWidget(add)


class ProjectSidebar(QWidget):
    sheetActivated = Signal(object)
    commandRequested = Signal(str)
    renameRequested = Signal(object, str)
    deleteRequested = Signal(object)

    def __init__(self, project: Project, parent=None):
        super().__init__(parent)
        self.project = project
        self.current: Sheet | None = None
        self._watched: set[int] = set()
        self.setObjectName("ProjectSidebar")
        self.setAttribute(Qt.WA_StyledBackground, True)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        from .logo import Logo
        mark = QWidget()
        mark.setObjectName("Wordmark")
        mark.setFixedHeight(52)
        ml = QHBoxLayout(mark)
        ml.setContentsMargins(18, 6, 8, 4)
        self.logo = Logo(24, dipper=False)       # the wordmark alone: the Dipper is too small here
        ml.addWidget(self.logo, 0, Qt.AlignLeft | Qt.AlignVCenter)
        ml.addStretch(1)
        v.addWidget(mark)
        body = QVBoxLayout()
        body.setContentsMargins(10, 0, 8, 8)
        body.setSpacing(4)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search")
        self.search.setClearButtonEnabled(True)
        set_icon(self.search.addAction(icon("magnifyingglass"), QLineEdit.LeadingPosition),
                 "magnifyingglass", "muted")
        self.search.textChanged.connect(self._filter)
        body.addWidget(self.search)
        self.tree = NavTree()
        self.tree.setObjectName("NavTree")
        self.tree.setDragEnabled(True)
        self.tree.setDragDropMode(QTreeWidget.DragOnly)
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(16)
        self.tree.setRootIsDecorated(False)
        self.tree.setItemDelegate(NavDelegate(self.tree))
        self.tree.setMouseTracking(True)
        self.tree.setIconSize(QSize(15, 15))
        self.tree.setAttribute(Qt.WA_MacShowFocusRect, False)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._context_menu)
        self.tree.itemClicked.connect(self._clicked)
        self.tree.itemActivated.connect(self._clicked)
        self.tree.itemChanged.connect(self._edited)
        body.addWidget(self.tree, 1)
        v.addLayout(body, 1)
        project.structure_changed.connect(self.rebuild)
        theme.notifier.changed.connect(self.rebuild)
        self.rebuild()

    # --- building -----------------------------------------------------------------

    def _item(self, parent, sheet: Sheet) -> QTreeWidgetItem:
        it = QTreeWidgetItem(parent, [sheet.name])
        it.setIcon(0, icon(KIND_ICON[sheet.kind], "accent", selected=True))
        it.setData(0, Qt.UserRole, sheet)
        flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable
        if sheet.kind in ("graph", "table", "analysis"):
            flags |= Qt.ItemIsDragEnabled
        it.setFlags(flags)
        if id(sheet) not in self._watched:
            self._watched.add(id(sheet))
            sheet.renamed.connect(self._rebuild_later)
        return it

    def _header(self, title: str, cmd: str, tip: str) -> QTreeWidgetItem:
        h = QTreeWidgetItem(self.tree)
        h.setFlags(Qt.ItemIsEnabled)
        h.setData(0, Qt.UserRole + 1, "header")
        self.tree.setItemWidget(h, 0, _SectionHeader(title, tip, lambda: self.commandRequested.emit(cmd)))
        return h

    def _placeholder(self, text: str) -> None:
        it = QTreeWidgetItem(self.tree, [text])
        it.setFlags(Qt.ItemIsEnabled)
        f = QFont(it.font(0))
        f.setItalic(True)
        it.setFont(0, f)
        it.setForeground(0, theme.color("muted"))

    def _rebuild_later(self) -> None:
        # A rename can come from editing an item of this tree; rebuild after that edit ends.
        if not getattr(self, "_pending", False):
            self._pending = True
            QTimer.singleShot(0, self._run_pending)

    def _run_pending(self) -> None:
        self._pending = False
        self.rebuild()

    def rebuild(self) -> None:
        self.tree.blockSignals(True)
        self.tree.clear()
        p = self.project
        self._header(*SECTIONS[0])
        def add_children(parent_item, sheet, depth=0):
            for child in p.children(sheet):
                ci = self._item(parent_item, child)
                if depth < 20:
                    add_children(ci, child, depth + 1)
                    ci.setExpanded(True)
        for t in p.tables:
            ti = self._item(self.tree, t)
            add_children(ti, t)
            ti.setExpanded(True)
        if not p.tables:
            self._placeholder("No data tables")
        self._header(*SECTIONS[1])
        for info in p.infos:
            self._item(self.tree, info)
        if not p.infos:
            self._placeholder("No notes")
        self._header(*SECTIONS[2])
        for lay in p.figures:
            self._item(self.tree, lay)
        if not p.figures:
            self._placeholder("No figures")
        self.tree.blockSignals(False)
        self._select_current()
        if self.search.text():
            self._filter(self.search.text())

    def _items(self):
        stack = [self.tree.topLevelItem(i) for i in range(self.tree.topLevelItemCount())]
        while stack:
            it = stack.pop(0)
            yield it
            stack[0:0] = [it.child(j) for j in range(it.childCount())]

    def _select_current(self) -> None:
        for it in self._items():
            if self.current is not None and it.data(0, Qt.UserRole) is self.current:
                self.tree.setCurrentItem(it)
                return

    def set_current(self, sheet: Sheet) -> None:
        self.current = sheet
        self._select_current()

    # --- interaction ----------------------------------------------------------------

    def _clicked(self, item: QTreeWidgetItem, _col: int = 0) -> None:
        s = item.data(0, Qt.UserRole)
        if s is not None:
            self.sheetActivated.emit(s)

    def _edited(self, item: QTreeWidgetItem, _col: int) -> None:
        s = item.data(0, Qt.UserRole)
        if s is not None and item.text(0).strip() and item.text(0) != s.name:
            self.renameRequested.emit(s, item.text(0).strip())

    def rename(self, sheet: Sheet) -> None:
        for it in self._items():
            if it.data(0, Qt.UserRole) is sheet:
                self.tree.editItem(it, 0)
                return

    def _context_menu(self, pos) -> None:
        it = self.tree.itemAt(pos)
        s = it.data(0, Qt.UserRole) if it else None
        if s is None:
            return
        self.sheetActivated.emit(s)
        m = QMenu(self)
        m.addAction("Rename", lambda: self.rename(s))
        dup = m.addAction("Duplicate")
        dup.setEnabled(False)
        dup.setToolTip("Arrives with the data tables (M2)")
        m.addSeparator()
        extra = " and its linked sheets" if isinstance(s, Table) and len(self.project.family(s)) > 1 else ""
        m.addAction(f"Delete{extra}", lambda: self.deleteRequested.emit(s))
        m.exec(self.tree.viewport().mapToGlobal(pos))

    def _filter(self, text: str) -> None:
        text = text.lower().strip()
        for it in self._items():
            s = it.data(0, Qt.UserRole)
            if s is None:
                it.setHidden(bool(text) and it.data(0, Qt.UserRole + 1) != "header")
                continue
            match = not text or text in s.name.lower()
            kids = [it.child(j) for j in range(it.childCount())]
            kid_match = any(text in (k.data(0, Qt.UserRole).name.lower()) for k in kids) if text else False
            it.setHidden(not (match or kid_match))
