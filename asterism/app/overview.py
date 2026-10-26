"""All graphs at a glance: live thumbnails of every graph in the project, grouped under
their data table, to find and open graphs quickly (SPEC M9b). A view, not a sheet."""

from __future__ import annotations

import weakref

from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QLayout, QLineEdit,
                               QMenu, QScrollArea, QSizePolicy, QSlider, QVBoxLayout, QWidget,
                               QWidgetAction)

from . import theme
from .graph.canvas import QtCanvas
from .icons import icon, set_icon
from .widgets import tag_icon


# ---------------------------------------------------------------------------
# Thumbnails
# ---------------------------------------------------------------------------

def render_graph(graph, w: int, h: int) -> QPixmap:
    from .graph.layout import GRAPHABLE_TYPES, build, content_bounds
    img = QImage(QSize(w, h) * 2, QImage.Format_ARGB32)
    img.setDevicePixelRatio(2)
    img.fill(QColor("#ffffff"))
    if graph.table.table_type in GRAPHABLE_TYPES:
        els, _ = build(graph)
        _paint(img, els, content_bounds(els, margin=6), w, h)
    return QPixmap.fromImage(img)


def render_figure(fig, project, w: int, h: int) -> QPixmap:
    from .figure.layout import build_figure
    img = QImage(QSize(w, h) * 2, QImage.Format_ARGB32)
    img.setDevicePixelRatio(2)
    img.fill(QColor("#ffffff"))
    page, els = build_figure(fig, project)
    _paint(img, els, page, w, h)
    return QPixmap.fromImage(img)


def _paint(img, els, b: QRectF, w: int, h: int) -> None:
    p = QPainter(img)
    s = min(w / max(b.width(), 1), h / max(b.height(), 1))
    p.translate((w - b.width() * s) / 2, (h - b.height() * s) / 2)
    p.scale(s, s)
    p.translate(-b.x(), -b.y())
    cv = QtCanvas(p)
    for e in els:
        e.draw(cv)
    p.end()


# ---------------------------------------------------------------------------
# Flow layout (cards wrap to the width)
# ---------------------------------------------------------------------------

class FlowLayout(QLayout):
    def __init__(self, parent=None, spacing: int = 12):
        super().__init__(parent)
        self._items = []
        self.setSpacing(spacing)
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, i):
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i):
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientations(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        s = QSize()
        for it in self._items:
            s = s.expandedTo(it.minimumSize())
        return s

    def _do(self, rect, test: bool) -> int:
        x, y, line = rect.x(), rect.y(), 0
        sp = self.spacing()
        for it in self._items:
            hint = it.sizeHint()
            if x + hint.width() > rect.right() + 1 and line > 0:
                x, y, line = rect.x(), y + line + sp, 0
            if not test:
                it.setGeometry(QRect(QPoint(x, y), hint))
            x += hint.width() + sp
            line = max(line, hint.height())
        return y + line - rect.y()


# ---------------------------------------------------------------------------
# Cards
# ---------------------------------------------------------------------------

class Card(QFrame):
    def __init__(self, view: "GraphOverview", sheet, size: int):
        super().__init__()
        self.view, self.sheet = view, sheet
        self.pixmap: QPixmap | None = None
        self.selected = False
        self.set_size(size)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(sheet.name)

    def set_size(self, size: int) -> None:
        self.tw, self.th = size, int(size * 0.78)
        self.setFixedSize(self.tw + 16, self.th + 52)
        self.pixmap = None

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setPen(theme.color("accent") if self.selected else theme.color("border"))
        p.setBrush(theme.color("surface"))
        p.drawRoundedRect(r, 8, 8)
        if self.selected:
            pen = p.pen()
            pen.setWidthF(2.0)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), 8, 8)
        tr = QRectF(8, 8, self.tw, self.th)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#ffffff"))
        p.drawRoundedRect(tr, 4, 4)
        if self.pixmap is not None:
            p.drawPixmap(tr.topLeft(), self.pixmap)
        x, right = 8.0, self.width() - 8.0
        if self.sheet.tag:
            p.setBrush(theme.tag_color(self.sheet.tag))
            p.drawEllipse(QRectF(right - 9, self.th + 15, 9, 9))
            right -= 14
        f = p.font()
        f.setBold(True)
        p.setFont(f)
        p.setPen(theme.color("text"))
        name = p.fontMetrics().elidedText(self.sheet.name, Qt.ElideRight, int(right - x))
        p.drawText(QRectF(x, self.th + 11, right - x, 18), Qt.AlignLeft | Qt.AlignVCenter, name)
        f.setBold(False)
        f.setPointSizeF(max(f.pointSizeF() - 1.5, 8))
        p.setFont(f)
        p.setPen(theme.color("muted"))
        text = self.view.describe(self.sheet)
        for prefix in ("Graph · ", "Figure · "):
            if text.startswith(prefix):
                text = text[len(prefix):]
        desc = p.fontMetrics().elidedText(text, Qt.ElideRight, int(self.width() - 16))
        p.drawText(QRectF(8, self.th + 29, self.width() - 16, 16), Qt.AlignLeft | Qt.AlignVCenter, desc)
        p.end()

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.LeftButton:
            self.view.click(self, e.modifiers())
        elif e.button() == Qt.RightButton and not self.selected:
            self.view.click(self, Qt.NoModifier)

    def mouseDoubleClickEvent(self, e) -> None:
        self.view.openRequested.emit(self.sheet)

    def contextMenuEvent(self, e) -> None:
        self.view.context_menu(self, e.globalPos())


# ---------------------------------------------------------------------------
# The view
# ---------------------------------------------------------------------------

SORTS = [("Project order", "project"), ("Name", "name"), ("Last changed", "changed")]


class GraphOverview(QWidget):
    openRequested = Signal(object)
    deleteRequested = Signal(object)
    addToFigureRequested = Signal(list)
    copyFormattingRequested = Signal(object, list)      # source graph, target graphs
    duplicateRequested = Signal(object)
    renameRequested = Signal(object)
    labelNamesRequested = Signal()
    selectionChanged = Signal()

    def __init__(self, project, describe, parent=None):
        super().__init__(parent)
        self.project, self.describe = project, describe
        self.cards: list[Card] = []
        self.selected: list = []
        self._anchor = None
        self._changed_at: dict[str, int] = {}
        self._tick = 0
        self._watched: set[int] = set()
        self.size = 180
        self.setObjectName("Overview")
        self.setAttribute(Qt.WA_StyledBackground, True)

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        bar = QWidget()
        bar.setObjectName("OverviewBar")
        h = QHBoxLayout(bar)
        h.setContentsMargins(16, 8, 16, 8)
        h.setSpacing(10)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search graphs")
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(160)
        self.search.setMaximumWidth(240)
        set_icon(self.search.addAction(icon("magnifyingglass"), QLineEdit.LeadingPosition), "magnifyingglass", "muted")
        self.type_combo = QComboBox()
        self.tag_combo = QComboBox()
        self.sort_combo = QComboBox()
        for text, key in SORTS:
            self.sort_combo.addItem(text, key)
        self.c_results = QCheckBox("Graphs of results")
        self.c_results.setChecked(True)
        self.c_figures = QCheckBox("Figures")
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(110, 340)
        self.slider.setValue(self.size)
        self.slider.setFixedWidth(110)
        self.slider.setToolTip("Thumbnail size")
        for wd in (self.search, self.type_combo, self.tag_combo, self.c_results, self.c_figures):
            h.addWidget(wd)
        h.addStretch(1)
        h.addWidget(QLabel("Sort:"))
        h.addWidget(self.sort_combo)
        h.addWidget(self.slider)
        v.addWidget(bar)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.body = QWidget()
        self.body.setObjectName("OverviewBody")
        self.body_layout = FlowLayout(self.body, spacing=22)
        self.body_layout.setContentsMargins(20, 12, 20, 20)
        self.clusters: list[tuple[QWidget, int]] = []
        self.scroll.setWidget(self.body)
        v.addWidget(self.scroll, 1)
        self.empty = QLabel("No graphs match.")
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setEnabled(False)

        self._timer = QTimer(self)
        self._timer.setInterval(0)
        self._timer.timeout.connect(self._render_some)
        self._rebuild_timer = QTimer(self)
        self._rebuild_timer.setSingleShot(True)
        self._rebuild_timer.setInterval(0)
        self._rebuild_timer.timeout.connect(self.rebuild)
        self.search.textChanged.connect(self.rebuild)
        for c in (self.type_combo, self.tag_combo, self.sort_combo):
            c.currentIndexChanged.connect(self.rebuild)
        self.c_results.toggled.connect(self.rebuild)
        self.c_figures.toggled.connect(self.rebuild)
        self.slider.valueChanged.connect(self._resize_cards)
        self.scroll.verticalScrollBar().valueChanged.connect(lambda _v: self._timer.start())
        ref = weakref.ref(self)
        project.structure_changed.connect(lambda: (s := ref()) is not None and s._rebuild_later())
        self._fill_filters()
        self.rebuild()

    # --- filters ---------------------------------------------------------------

    def _fill_filters(self) -> None:
        from ..doc.table import TYPE_NAMES
        cur_t, cur_k = self.type_combo.currentData(), self.tag_combo.currentData()
        for c in (self.type_combo, self.tag_combo):
            c.blockSignals(True)
            c.clear()
        self.type_combo.addItem("All table types", None)
        for tt in sorted({g.table.table_type for g in self.project.graphs}, key=lambda t: TYPE_NAMES.get(t, t)):
            self.type_combo.addItem(TYPE_NAMES.get(tt, tt), tt)
        self.tag_combo.addItem("Any label", None)
        for k in range(1, 8):
            self.tag_combo.addItem(tag_icon(k), self.project.label_name(k), k)
        for c, cur in ((self.type_combo, cur_t), (self.tag_combo, cur_k)):
            i = c.findData(cur)
            c.setCurrentIndex(i if i >= 0 else 0)
            c.blockSignals(False)

    def _matches(self, sh) -> bool:
        text = self.search.text().strip().lower()
        if text and text not in sh.name.lower():
            return False
        k = self.tag_combo.currentData()
        if k and sh.tag != k:
            return False
        if sh.kind == "graph":
            tt = self.type_combo.currentData()
            if tt and sh.table.table_type != tt:
                return False
            if sh.source is not None and not self.c_results.isChecked():
                return False
        return True

    # --- building --------------------------------------------------------------

    def _rebuild_later(self) -> None:
        self._rebuild_timer.start()

    def groups(self) -> list[tuple[str, int, list]]:
        """(title, tag of the table, sheets) in sidebar order, filtered and sorted."""
        p = self.project
        out = []
        for t in p.tables:
            gs = [g for g in p.graphs if p.root_table(g) is t and self._matches(g)]
            if gs:
                out.append((t.name, t.tag, gs))
        orphans = [g for g in p.graphs if p.root_table(g) not in p.tables and self._matches(g)]
        if orphans:
            out.append(("Other graphs", 0, orphans))
        if self.c_figures.isChecked():
            fs = [f for f in p.figures if self._matches(f)]
            if fs:
                out.append(("Figures", 0, fs))
        key = self.sort_combo.currentData()
        for _t, _k, items in out:
            if key == "name":
                items.sort(key=lambda s: s.name.lower())
            elif key == "changed":
                items.sort(key=lambda s: -self._changed_at.get(s.id, 0))
        return out

    def rebuild(self) -> None:
        sel_ids = {s.id for s in self.selected}
        while self.body_layout.count():
            it = self.body_layout.takeAt(0)
            wd = it.widget()
            if wd is not None:
                wd.hide()
                wd.deleteLater()
        old = {c.sheet.id: c.pixmap for c in self.cards}
        self.cards = []
        self.clusters = []
        self._fill_filters()
        groups = self.groups()
        for title, tag, items in groups:
            cluster = QWidget()
            cl = QVBoxLayout(cluster)
            cl.setContentsMargins(0, 0, 0, 0)
            cl.setSpacing(4)
            head = QWidget()
            hl = QHBoxLayout(head)
            hl.setContentsMargins(0, 10, 0, 2)
            hl.setSpacing(6)
            lab = QLabel(title)
            lab.setObjectName("OverviewGroup")
            hl.addWidget(lab)
            if tag:
                dot = QLabel()
                dot.setPixmap(tag_icon(tag, 12).pixmap(12, 12))
                hl.addWidget(dot)
            n = QLabel(f"{len(items)}")
            n.setEnabled(False)
            hl.addWidget(n)
            hl.addStretch(1)
            cl.addWidget(head)
            box = QWidget()
            flow = FlowLayout(box)
            for sh in items:
                c = Card(self, sh, self.size)
                c.pixmap = old.get(sh.id)
                c.selected = sh.id in sel_ids
                flow.addWidget(c)
                self.cards.append(c)
                self._watch(sh)
            cl.addWidget(box)
            self.body_layout.addWidget(cluster)
            self.clusters.append((cluster, len(items)))
        self._fit_clusters()
        if not groups:
            self.empty = QLabel("No graphs match." if self.project.graphs else "No graphs yet.")
            self.empty.setAlignment(Qt.AlignCenter)
            self.empty.setEnabled(False)
            self.body_layout.addWidget(self.empty)
        self.selected = [c.sheet for c in self.cards if c.selected]
        self._timer.start()
        self.selectionChanged.emit()

    def _watch(self, sh) -> None:
        if id(sh) in self._watched:
            return
        self._watched.add(id(sh))
        ref = weakref.ref(self)
        sig = getattr(sh, "changed", None)
        if sig is not None:
            sig.connect(lambda sh=sh: (s := ref()) is not None and s._sheet_changed(sh))
        sh.renamed.connect(lambda: (s := ref()) is not None and s._rebuild_later())

    def _sheet_changed(self, sh) -> None:
        self._tick += 1
        self._changed_at[sh.id] = self._tick
        for c in self.cards:
            if c.sheet is sh:
                c.pixmap = None
        self._timer.start()

    def _render_some(self) -> None:
        """Draw missing thumbnails, visible cards first, one per turn of the event loop."""
        todo = [c for c in self.cards if c.pixmap is None]
        if not todo:
            self._timer.stop()
            return
        vis = [c for c in todo if not c.visibleRegion().isEmpty()]
        c = (vis or todo)[0]
        try:
            if c.sheet.kind == "figure":
                c.pixmap = render_figure(c.sheet, self.project, c.tw, c.th)
            else:
                c.pixmap = render_graph(c.sheet, c.tw, c.th)
        except Exception:                      # a thumbnail must never break the view
            c.pixmap = QPixmap(1, 1)
        c.update()

    def render_all(self) -> None:
        while any(c.pixmap is None for c in self.cards):
            self._render_some()

    def _fit_clusters(self) -> None:
        """Each group is as wide as its cards need, up to the whole width (then it wraps)."""
        avail = max(self.scroll.viewport().width() - 40, 200)
        cw, sp = self.size + 16, 12
        per_row = max(1, (avail + sp) // (cw + sp))
        for cluster, n in self.clusters:
            k = min(n, per_row)
            w = k * cw + (k - 1) * sp
            rows = -(-n // k)
            cluster.setFixedWidth(w)
            cluster.setFixedHeight(32 + rows * (int(self.size * 0.78) + 52) + (rows - 1) * sp)

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        self._fit_clusters()

    def _resize_cards(self, v: int) -> None:
        self.size = v
        for c in self.cards:
            c.set_size(v)
        self._fit_clusters()
        self.body.updateGeometry()
        self._timer.start()

    # --- selection ---------------------------------------------------------------

    def click(self, card: Card, mods) -> None:
        if mods & (Qt.ControlModifier | Qt.MetaModifier):
            card.selected = not card.selected
            self._anchor = card
        elif mods & Qt.ShiftModifier and self._anchor in self.cards:
            a, b = sorted((self.cards.index(self._anchor), self.cards.index(card)))
            for i, c in enumerate(self.cards):
                c.selected = a <= i <= b
        else:
            for c in self.cards:
                c.selected = c is card
            self._anchor = card
        for c in self.cards:
            c.update()
        self.selected = [c.sheet for c in self.cards if c.selected]
        self.selectionChanged.emit()

    def select_all(self) -> None:
        for c in self.cards:
            c.selected = True
            c.update()
        self.selected = [c.sheet for c in self.cards]
        self.selectionChanged.emit()

    def keyPressEvent(self, e) -> None:
        if e.key() in (Qt.Key_Return, Qt.Key_Enter) and self.selected:
            self.openRequested.emit(self.selected[0])
        elif e.key() == Qt.Key_A and e.modifiers() & (Qt.ControlModifier | Qt.MetaModifier):
            self.select_all()
        else:
            super().keyPressEvent(e)

    # --- menu ----------------------------------------------------------------------

    def context_menu(self, card: Card, pos) -> None:
        from .sidebar import TagSwatches
        sh = card.sheet
        sel = self.selected if sh in self.selected else [sh]
        graphs = [s for s in sel if s.kind == "graph"]
        m = QMenu(self)
        sw = TagSwatches(self.project, current=sh.tag if len(sel) == 1 else None)
        sw.picked.connect(lambda k: (self.set_tag(sel, k), m.close()))
        wa = QWidgetAction(m)
        wa.setDefaultWidget(sw)
        m.addAction(wa)
        m.addAction("Label Names…", self.labelNamesRequested)
        m.addSeparator()
        if len(sel) == 1:
            m.addAction("Open", lambda: self.openRequested.emit(sh))
            m.addAction("Rename…", lambda: self.renameRequested.emit(sh))
            if sh.kind == "graph":
                m.addAction("Duplicate", lambda: self.duplicateRequested.emit(sh))
        if graphs:
            m.addAction("Add to Figure…" if len(graphs) == 1 else f"Add {len(graphs)} Graphs to a Figure…",
                        lambda: self.addToFigureRequested.emit(graphs))
        if sh.kind == "graph" and len(graphs) > 1:
            others = [g for g in graphs if g is not sh]
            m.addAction(f"Apply This Graph's Formatting to the Other {len(others)}",
                        lambda: self.copyFormattingRequested.emit(sh, others))
        if len(sel) == 1:
            m.addSeparator()
            m.addAction("Delete…", lambda: self.deleteRequested.emit(sh))
        m.exec(pos)

    def set_tag(self, sheets, k: int) -> None:
        from ..doc.commands import LabelCommand
        sheets = [s for s in sheets if s.tag != k]
        if sheets:
            self.project.undo.push(LabelCommand(sheets, k))

    def count(self) -> int:
        return len(self.cards)
