"""Graph sheet: a page with selectable, directly editable graph elements."""

from __future__ import annotations

import copy

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QTextCursor, QTransform
from PySide6.QtWidgets import (QGraphicsDropShadowEffect, QGraphicsItem, QGraphicsObject,
                               QGraphicsRectItem, QGraphicsScene, QGraphicsTextItem,
                               QGraphicsView, QMenu, QVBoxLayout, QWidget)

from .. import theme
from ...doc.commands import SpecCommand
from ...doc.model import Graph, Project
from .canvas import QtCanvas, TextMetrics, qfont
from .layout import GRAPHABLE_TYPES, Element, build

# Graph sheets show the graph alone on white, centred in the view. Pages belong to
# layout sheets (SPEC §9), not to graph sheets.
VIEW_MARGIN = 36.0          # points of white kept around the graph when zoomed in


class ElementItem(QGraphicsObject):
    activated = Signal(object)
    moved = Signal(str, float, float)

    def __init__(self, el: Element, parent: QGraphicsItem):
        super().__init__(parent)
        self.el = el
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        if el.kind in ("text", "bracket", "legend"):
            self.setFlag(QGraphicsItem.ItemIsMovable, True)
        if el.kind == "errors":                 # overlay drawn on top; clicks go to the bars
            self.setFlag(QGraphicsItem.ItemIsSelectable, False)
            self.setAcceptedMouseButtons(Qt.NoButton)
        self.setCursor(Qt.ArrowCursor)
        self._press = None

    def boundingRect(self) -> QRectF:
        return self.el.bounds.adjusted(-4, -4, 4, 4)

    def shape(self):
        return self.el.hit if self.el.hit is not None else super().shape()

    def paint(self, painter: QPainter, option, widget=None) -> None:
        self.el.draw(QtCanvas(painter))
        if self.isSelected():
            r = self.el.bounds
            s = 5.0 / max(painter.worldTransform().m11(), 0.01)
            accent = QColor(theme.LIGHT["accent"])     # the page is always white
            pen = QPen(accent, 1.2)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.setBrush(QColor("#ffffff"))
            c = r.center()
            for pt in (r.topLeft(), r.topRight(), r.bottomLeft(), r.bottomRight(),
                       QPointF(c.x(), r.top()), QPointF(c.x(), r.bottom()),
                       QPointF(r.left(), c.y()), QPointF(r.right(), c.y())):
                painter.drawRect(QRectF(pt.x() - s / 2, pt.y() - s / 2, s, s))

    def mousePressEvent(self, e):
        self._press = QPointF(self.pos())
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        super().mouseReleaseEvent(e)
        if self._press is not None and (self.pos() - self._press).manhattanLength() > 0.5:
            d = self.pos() - self._press
            self.moved.emit(self.el.id, d.x(), d.y())
        self._press = None

    def mouseDoubleClickEvent(self, e):
        self.activated.emit(self)


class InlineText(QGraphicsTextItem):
    finished = Signal(bool)

    def __init__(self, text: str):
        super().__init__(text)
        self._done = False
        self.setTextInteractionFlags(Qt.TextEditorInteraction)
        self.document().setDocumentMargin(0)

    def _finish(self, commit: bool):
        if not self._done:
            self._done = True
            self.finished.emit(commit)

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Return, Qt.Key_Enter) and not e.modifiers() & Qt.ShiftModifier:
            self._finish(True)
        elif e.key() == Qt.Key_Escape:
            self._finish(False)
        else:
            super().keyPressEvent(e)

    def focusOutEvent(self, e):
        super().focusOutEvent(e)
        self._finish(True)


class GraphView(QGraphicsView):
    zoomChanged = Signal(float)

    def wheelEvent(self, e):
        if e.modifiers() & (Qt.ControlModifier | Qt.MetaModifier):
            z = self.transform().m11() * (1.1 if e.angleDelta().y() > 0 else 1 / 1.1)
            self.set_zoom(z)
        else:
            super().wheelEvent(e)

    def set_zoom(self, z: float):
        z = max(0.25, min(4.0, z))
        self.setTransform(QTransform.fromScale(z, z))
        self.zoomChanged.emit(z)


class GraphSheet(QWidget):
    selectionChanged = Signal()
    formatGraphRequested = Signal(str, object)    # tab, column
    formatAxesRequested = Signal(str)             # tab

    def __init__(self, graph: Graph, project: Project, parent=None):
        super().__init__(parent)
        self.graph, self.project = graph, project
        self.scene = QGraphicsScene(self)
        self.view = GraphView(self.scene)
        self.view.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        self.view.setDragMode(QGraphicsView.RubberBandDrag)
        self.view.setFrameShape(QGraphicsView.NoFrame)
        self.view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self._context_menu)
        self._apply_theme()
        theme.notifier.changed.connect(self._apply_theme)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.view)

        self.view.setAlignment(Qt.AlignCenter)
        self.root = QGraphicsRectItem(0, 0, 0, 0)
        self.root.setPen(Qt.NoPen)
        self.scene.addItem(self.root)

        self.items: list[ElementItem] = []
        self._placeholder = None
        self._editing = None
        self.auto_range = None
        self.scene.selectionChanged.connect(self.selectionChanged)
        graph.changed.connect(self.rebuild)
        self.rebuild()
        self.view.set_zoom(2.0)

    def _apply_theme(self) -> None:
        # Graphs are print colours: always on white, in light and dark mode.
        self.view.setBackgroundBrush(QColor("#ffffff"))

    def _fit_scene(self) -> None:
        """Keep the graph centred. The scene rect is symmetric around the graph's own
        centre (its layout without any dragged offsets), and the view centres the scene
        when it is smaller than the window; so resizing, zooming or dragging a title
        never shifts the graph itself."""
        design, everything = QRectF(), QRectF()
        for it in self.items:
            ox, oy = self.graph.spec.offsets.get(it.el.id, (0.0, 0.0))
            design = design.united(it.el.bounds.translated(-ox, -oy))
            everything = everything.united(it.el.bounds)
        if design.isNull():
            design = everything = QRectF(-50, -50, 100, 100)
        c = design.center()
        hw = max(c.x() - everything.left(), everything.right() - c.x()) + VIEW_MARGIN
        hh = max(c.y() - everything.top(), everything.bottom() - c.y()) + VIEW_MARGIN
        self.scene.setSceneRect(QRectF(c.x() - hw, c.y() - hh, 2 * hw, 2 * hh))

    # --- building ---------------------------------------------------------------

    def rebuild(self) -> None:
        if self._editing:
            return
        selected = {it.el.id for it in self.items if it.isSelected()}
        self.scene.blockSignals(True)
        for it in self.items:
            self.scene.removeItem(it)
        self.items = []
        if self._placeholder is not None:
            self.scene.removeItem(self._placeholder)
            self._placeholder = None
        if self.graph.table.table_type not in GRAPHABLE_TYPES:
            self._show_placeholder()
            self.scene.blockSignals(False)
            return
        els, self.auto_range = build(self.graph)
        for e in els:
            it = ElementItem(e, self.root)
            it.activated.connect(self._activated)
            it.moved.connect(self._moved)
            it.setSelected(e.id in selected)
            self.items.append(it)
        self.scene.blockSignals(False)
        self._fit_scene()
        self.selectionChanged.emit()

    def _show_placeholder(self) -> None:
        from ...doc.table import TYPE_NAMES
        milestone = {"grouped": "M4", "nested": "M4", "xy": "M5", "contingency": "M6",
                     "survival": "M6", "parts": "M6"}.get(self.graph.table.table_type, "a later milestone")
        kind = TYPE_NAMES[self.graph.table.table_type]
        t = self.scene.addText(f"Graphs of {kind} tables arrive in {milestone}.\n"
                               "The data table and file are ready now.")
        t.setDefaultTextColor(QColor("#55585f"))
        self._placeholder = t
        self.auto_range = None
        self.scene.setSceneRect(t.boundingRect().adjusted(-40, -40, 40, 40))

    def is_graphable(self) -> bool:
        return self.graph.table.table_type in GRAPHABLE_TYPES

    def selected_elements(self) -> list[Element]:
        return [it.el for it in self.items if it.isSelected()]

    # --- direct manipulation ------------------------------------------------------

    def _activated(self, item: ElementItem) -> None:
        k = item.el.kind
        if k == "text":
            self._start_edit(item)
        elif k in ("dataset", "curve"):
            self.formatGraphRequested.emit("style", item.el.meta["column"])
        elif k == "bracket":
            self.formatGraphRequested.emit("significance", None)
        elif k == "legend":
            self.formatGraphRequested.emit("arrangement", None)
        elif k == "x-axis":
            self.formatAxesRequested.emit("x")
        elif k == "frame":
            self.formatAxesRequested.emit("frame")
        else:
            self.formatAxesRequested.emit("y")

    def _moved(self, gid: str, dx: float, dy: float) -> None:
        spec = copy.deepcopy(self.graph.spec)
        ox, oy = spec.offsets.get(gid, (0.0, 0.0))
        spec.offsets[gid] = (ox + dx, oy + dy)
        self.project.undo.push(SpecCommand(self.graph, spec, "Move"))

    def apply_font(self, **changes) -> None:
        """Ribbon Text group → fonts of the selected elements (all text if none)."""
        keys = sorted({k for e in self.selected_elements() for k in e.meta.get("font_keys", [])})
        spec = copy.deepcopy(self.graph.spec)
        for k in keys or list(spec.fonts):
            for attr, v in changes.items():
                setattr(spec.fonts[k], attr, v)
        self.project.undo.push(SpecCommand(self.graph, spec, "Change Font"))

    def current_font(self):
        for e in self.selected_elements():
            if e.meta.get("font_keys"):
                return self.graph.spec.fonts[e.meta["font_keys"][0]]
        return self.graph.spec.fonts["y_numbers"]

    def _start_edit(self, item: ElementItem) -> None:
        el = item.el
        fs = self.graph.spec.fonts[el.meta["font_keys"][0]]
        ed = InlineText(el.meta["text"])
        ed.setFont(qfont(fs, self.view.viewport().logicalDpiY()))
        ed.setDefaultTextColor(QColor("black"))
        ed.setParentItem(self.root)
        tx, ty = el.meta["anchor_pt"]
        w, asc = ed.boundingRect().width(), TextMetrics.ascent(fs)
        if el.meta.get("rotate") == -90:
            ed.setRotation(-90)
            ed.setPos(tx - asc, ty + w / 2)
        else:
            ed.setPos(tx - w / 2, ty - asc)
        item.hide()
        self._editing = (ed, el)
        ed.finished.connect(self._finish_edit)
        ed.setFocus()
        cur = ed.textCursor()
        cur.select(QTextCursor.Document)
        ed.setTextCursor(cur)

    def _finish_edit(self, commit: bool) -> None:
        ed, el = self._editing
        text = ed.toPlainText().strip()
        self._editing = None
        self.scene.removeItem(ed)
        ed.deleteLater()
        if commit and text != el.meta["text"]:
            spec = copy.deepcopy(self.graph.spec)
            if el.meta["field"] == "title":
                spec.title = text
                spec.show_title = bool(text)
            elif el.meta["field"] == "x_title":
                spec.x.title = text
            else:
                spec.y.title = text
            self.project.undo.push(SpecCommand(self.graph, spec, "Edit Text"))
        else:
            self.rebuild()

    def _context_menu(self, pos) -> None:
        item = self.view.itemAt(pos)
        if isinstance(item, ElementItem) and not item.isSelected():
            self.scene.clearSelection()
            item.setSelected(True)
        m = QMenu(self)
        m.addAction("Format Graph…", lambda: self.formatGraphRequested.emit("style", None))
        m.addAction("Axes…", lambda: self.formatAxesRequested.emit("y"))
        m.exec(self.view.viewport().mapToGlobal(pos))

    def set_zoom(self, z: float) -> None:
        self.view.set_zoom(z)
