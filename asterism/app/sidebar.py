"""Project sidebar (NED-Net's sidebar structure): wordmark, search, and the project's
sheets in three sections — Data (each table with its analyses and graphs nested under
it), Notes and Figures — each with a "+" button. SPEC §5, §12."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QLabel, QLineEdit, QMenu, QPushButton,
                               QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
                               QWidgetAction)

from . import theme
from .icons import icon, set_icon
from .widgets import TAG_ROLE, NavDelegate, tag_icon
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


class TagSwatches(QWidget):
    """A row of colour-label swatches (none + 1–7), as in Finder's menu; `picked(k)`."""
    picked = Signal(int)

    def __init__(self, project, checkable: bool = False, size: int = 18, current: int | None = None):
        super().__init__()
        self.buttons = []
        h = QHBoxLayout(self)
        h.setContentsMargins(10 if not checkable else 0, 2, 10 if not checkable else 0, 2)
        h.setSpacing(4 if checkable else 6)
        for k in ([] if checkable else [0]) + list(range(1, 8)):
            b = QToolButton()
            b.setAutoRaise(True)
            b.setIcon(tag_icon(k, size) if k else icon("xmark.circle", "muted"))
            b.setIconSize(QSize(size, size))
            b.setToolTip(project.label_name(k) if k else "No label")
            b.setCheckable(checkable)
            b.setChecked(current == k)
            b.setObjectName("TagSwatch")
            b.clicked.connect(lambda _on=False, k=k: self.picked.emit(k))
            h.addWidget(b)
            self.buttons.append((k, b))
        h.addStretch(1)

    def set_checked(self, k: int) -> None:
        for kk, b in self.buttons:
            b.setChecked(kk == k)


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
    overviewRequested = Signal()
    importSettingsRequested = Signal(object)
    labelNamesRequested = Signal()
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
        self.tag_filter = 0
        self.tag_strip = TagSwatches(project, checkable=True, size=12)
        self.tag_strip.picked.connect(self._tag_filter_picked)
        body.addWidget(self.tag_strip)
        self.overview_btn = QPushButton("All graphs")
        self.overview_btn.setObjectName("NavButton")
        self.overview_btn.setFlat(True)
        set_icon(self.overview_btn, "square.grid.2x2", "accent")
        self.overview_btn.setToolTip("Every graph in the project at a glance (⌘⇧G)")
        self.overview_btn.clicked.connect(self.overviewRequested)
        body.addWidget(self.overview_btn)
        self.tree = NavTree()
        self.tree.setObjectName("NavTree")
        self.tree.setDragEnabled(True)
        self.tree.setDragDropMode(QTreeWidget.DragOnly)
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
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
        it.setData(0, TAG_ROLE, sheet.tag)
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
        if self.search.text() or self.tag_filter:
            self._filter(self.search.text())
        for k, b in self.tag_strip.buttons:
            b.setToolTip(f"Show only sheets labelled “{p.label_name(k)}”")

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

    def set_current(self, sheet: Sheet | None) -> None:
        self.current = sheet
        if sheet is None:
            self.tree.clearSelection()
            self.tree.setCurrentItem(None)
        self._select_current()

    def selected_sheets(self) -> list[Sheet]:
        return [it.data(0, Qt.UserRole) for it in self.tree.selectedItems() if it.data(0, Qt.UserRole) is not None]

    def set_tag(self, sheets: list[Sheet], k: int) -> None:
        from ..doc.commands import LabelCommand
        sheets = [sh for sh in sheets if sh.tag != k]
        if sheets:
            self.project.undo.push(LabelCommand(sheets, k))

    def _tag_filter_picked(self, k: int) -> None:
        self.tag_filter = 0 if self.tag_filter == k else k
        self.tag_strip.set_checked(self.tag_filter)
        self._filter(self.search.text())

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
        sel = self.selected_sheets()
        targets = sel if s in sel else [s]
        if len(targets) == 1:
            self.sheetActivated.emit(s)
        m = QMenu(self)
        sw = TagSwatches(self.project, current=s.tag if len(targets) == 1 else None)
        sw.picked.connect(lambda k: (self.set_tag(targets, k), m.close()))
        wa = QWidgetAction(m)
        wa.setDefaultWidget(sw)
        m.addAction(wa)
        m.addAction("Label Names…", self.labelNamesRequested)
        m.addSeparator()
        if len(targets) > 1:
            m.exec(self.tree.viewport().mapToGlobal(pos))
            return
        m.addAction("Rename", lambda: self.rename(s))
        ref = getattr(s, "import_ref", None)
        if ref and ref.get("session") in self.project.imports:
            m.addAction("Import Settings…", lambda: self.importSettingsRequested.emit(s))
        dup = m.addAction("Duplicate")
        dup.setEnabled(False)
        dup.setToolTip("Arrives with the data tables (M2)")
        m.addSeparator()
        extra = " and its linked sheets" if isinstance(s, Table) and len(self.project.family(s)) > 1 else ""
        m.addAction(f"Delete{extra}", lambda: self.deleteRequested.emit(s))
        m.exec(self.tree.viewport().mapToGlobal(pos))

    def _filter(self, text: str) -> None:
        """Search text and colour-label filter. Parents of matching sheets stay visible,
        dimmed, so nothing appears out of context."""
        text = (text or "").lower().strip()
        tag = self.tag_filter
        active = bool(text or tag)

        def own(it):
            s = it.data(0, Qt.UserRole)
            return s is not None and (not text or text in s.name.lower()) and (not tag or s.tag == tag)

        def visit(it) -> bool:
            kids = [visit(it.child(j)) for j in range(it.childCount())]
            s = it.data(0, Qt.UserRole)
            if s is None:
                it.setHidden(active and it.data(0, Qt.UserRole + 1) != "header")
                return False
            mine = own(it)
            show = not active or mine or any(kids)
            it.setHidden(not show)
            dim = active and show and not mine
            it.setForeground(0, theme.color("muted") if dim else theme.color("text"))
            return show
        for i in range(self.tree.topLevelItemCount()):
            visit(self.tree.topLevelItem(i))
