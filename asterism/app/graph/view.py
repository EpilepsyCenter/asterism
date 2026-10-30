"""Graph sheet: a page with selectable, directly editable graph elements."""

from __future__ import annotations

import weakref

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


HANDLE = 6.0                # handle size on drawings (points at 100 %)
SNAP_PX = 5.0               # snapping distance while dragging, in screen pixels


def _handles(el) -> dict:
    """Draggable points of a drawing: both ends of a line, the far corner of a shape."""
    if el.kind != "drawing" or el.meta.get("drawing_kind") == "text":
        return {}
    d = el.meta.get("_d")
    if d is None:
        return {}
    if el.meta["drawing_kind"] in ("line", "arrow"):
        return {"p1": QPointF(d["x1"], d["y1"]), "p2": QPointF(d["x2"], d["y2"])}
    return {"p2": QPointF(max(d["x1"], d["x2"]), max(d["y1"], d["y2"]))}


class ElementItem(QGraphicsObject):
    activated = Signal(object)
    moved = Signal(str, float, float)
    reshaped = Signal(str, str, float, float)       # drawing id, handle, new x, new y

    def __init__(self, el: Element, parent: QGraphicsItem):
        super().__init__(parent)
        self.el = el
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        if el.kind in ("text", "bracket", "legend", "drawing"):
            self.setFlag(QGraphicsItem.ItemIsMovable, True)
        if el.kind == "errors":                 # overlay drawn on top; clicks go to the bars
            self.setFlag(QGraphicsItem.ItemIsSelectable, False)
            self.setAcceptedMouseButtons(Qt.NoButton)
        self.setCursor(Qt.ArrowCursor)
        self._press = None
        self._handle = None          # (name, current point) while a handle is dragged
        self._drag = None            # (press point in parent coords, {item: start pos}) while dragging
        self.snapper = None          # weak GraphSheet hook: (item, group, delta, axis) -> delta

    def boundingRect(self) -> QRectF:
        return self.el.bounds.adjusted(-8, -8, 8, 8)

    def shape(self):
        return self.el.hit if self.el.hit is not None else super().shape()

    def paint(self, painter: QPainter, option, widget=None) -> None:
        self.el.draw(QtCanvas(painter))
        hs = _handles(self.el)
        if self.isSelected() and hs:
            s = HANDLE / max(painter.worldTransform().m11(), 0.01) * 1.6
            accent = QColor(theme.LIGHT["accent"])
            pen = QPen(accent, 1.2)
            pen.setCosmetic(True)
            painter.setPen(pen)
            if self._handle:                    # preview of the new shape
                name, pt = self._handle
                d = self.el.meta["_d"]
                p1 = pt if name == "p1" else QPointF(d["x1"], d["y1"])
                p2 = pt if name == "p2" else QPointF(d["x2"], d["y2"])
                if self.el.meta["drawing_kind"] in ("line", "arrow"):
                    painter.drawLine(p1, p2)
                else:
                    painter.setBrush(Qt.NoBrush)
                    painter.drawRect(QRectF(p1, p2).normalized())
            painter.setBrush(QColor("#ffffff"))
            for pt in hs.values():
                painter.drawEllipse(pt, s / 2, s / 2)
            return
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
        if self.isSelected() and e.button() == Qt.LeftButton:
            tol = HANDLE * 1.6 / max(self.scene().views()[0].transform().m11(), 0.01) if self.scene() and \
                self.scene().views() else HANDLE
            for name, pt in _handles(self.el).items():
                if (e.pos() - pt).manhattanLength() <= tol * 1.2:
                    self._handle = (name, QPointF(pt))
                    e.accept()
                    return
        self._press = QPointF(self.pos())
        self._drag = None
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._handle:
            self._handle = (self._handle[0], e.pos())
            self.update()
            return
        if not (self.flags() & QGraphicsItem.ItemIsMovable) or self._press is None \
                or not e.buttons() & Qt.LeftButton:
            super().mouseMoveEvent(e)
            return
        parent = self.parentItem()
        here = parent.mapFromScene(e.scenePos()) if parent else e.scenePos()
        if self._drag is None:
            # A click that wobbles a pixel is not a drag (it would snap the element).
            from PySide6.QtWidgets import QApplication
            moved = e.screenPos() - e.buttonDownScreenPos(Qt.LeftButton)
            if moved.manhattanLength() < QApplication.startDragDistance():
                e.accept()
                return
            # What moves together is what a move saves: selected drawings move as a group,
            # anything else moves alone.
            group = [self]
            if self.el.kind == "drawing" and self.scene():
                group += [it for it in self.scene().selectedItems() if it is not self
                          and isinstance(it, ElementItem) and it.el.kind == "drawing"]
            start = parent.mapFromScene(e.buttonDownScenePos(Qt.LeftButton)) if parent \
                else e.buttonDownScenePos(Qt.LeftButton)
            self._drag = (start, {it: QPointF(it.pos()) for it in group})
        start, group = self._drag
        d = here - start
        axis = None
        if e.modifiers() & Qt.ShiftModifier:        # Shift: straight across or straight up/down
            axis = "x" if abs(d.x()) >= abs(d.y()) else "y"
            d = QPointF(d.x(), 0.0) if axis == "x" else QPointF(0.0, d.y())
        snap = self.snapper() if self.snapper is not None else None
        if snap is not None:
            d = snap(self, list(group), d, axis)
        for it, p0 in group.items():
            it.setPos(p0 + d)
        e.accept()

    def mouseReleaseEvent(self, e):
        if self._handle:
            name, pt = self._handle
            self._handle = None
            self.reshaped.emit(self.el.meta["drawing"], name, pt.x(), pt.y())
            return
        super().mouseReleaseEvent(e)
        self._drag = None
        snap = self.snapper() if self.snapper is not None else None
        if snap is not None:
            snap(None, [], QPointF(), None)                  # clear the guides
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
        if e.reason() != Qt.PopupFocusReason:        # a menu (e.g. Symbol) keeps the edit open
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
    toolFinished = Signal()                       # a drawing tool was used (or cancelled)
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
        self._guides = []           # snap guide lines shown while dragging
        self.tool = None                          # drawing tool in use: line, arrow, rect, ellipse, text
        self._draw_start = None
        self._preview = None
        self.view.viewport().installEventFilter(self)
        self.view.installEventFilter(self)
        self.auto_range = None
        # Forward through a weak reference: when the sheet is destroyed, Python frees its
        # items first and each selected one makes the scene report a selection change.
        self.scene.selectionChanged.connect(_forward_selection(weakref.ref(self)))
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
        by_id = {d["id"]: d for d in self.graph.spec.drawings}
        for e in els:
            if e.kind == "drawing":
                e.meta["_d"] = by_id.get(e.meta["drawing"])
            it = ElementItem(e, self.root)
            it.activated.connect(self._activated)
            it.moved.connect(self._moved)
            it.reshaped.connect(self._reshaped)
            it.snapper = weakref.WeakMethod(self._snap)   # weak: no item → sheet cycle
            it.setSelected(e.id in selected)
            self.items.append(it)
        self.scene.blockSignals(False)
        self._fit_scene()
        self.selectionChanged.emit()

    def _show_placeholder(self) -> None:
        from ...doc.table import TYPE_NAMES
        milestone = "a later milestone"
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
        if k == "drawing":
            if item.el.meta["drawing_kind"] == "text":
                self._start_edit(item)
            else:
                self.edit_drawing(item.el.meta["drawing"])
        elif k == "text":
            self._start_edit(item)
        elif k == "curve" and item.el.meta.get("function"):
            self.edit_function(item.el.meta["function"])
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

    def _hide_bracket(self, gid: str) -> None:
        spec = copy.deepcopy(self.graph.spec)
        spec.sig["hidden"] = sorted(set(spec.sig.get("hidden") or []) | {gid})
        self.project.undo.push(SpecCommand(self.graph, spec, "Hide Comparison"))

    def _show_all_brackets(self) -> None:
        spec = copy.deepcopy(self.graph.spec)
        spec.sig["hidden"] = []
        self.project.undo.push(SpecCommand(self.graph, spec, "Show All Comparisons"))

    def _snap(self, item, group: list, d: QPointF, axis: str | None) -> QPointF:
        """While dragging: pull the moving element's edges and centre onto the edges and
        centres of the other elements when they come within a few pixels, and show a guide
        line for each snap. `axis` "x"/"y" means the move is locked to that direction.
        Called with item None to clear the guides."""
        for g in self._guides:
            self.scene.removeItem(g)
        self._guides = []
        if item is None:
            return d
        tol = SNAP_PX / max(self.view.transform().m11(), 0.01)
        r = item.el.bounds.translated(self._drag_origin(item) + d)
        others = [it for it in self.items if it not in group and it.el.kind != "errors"]
        best = {"x": None, "y": None}
        for it in others:
            o = it.el.bounds.translated(it.pos())
            for name, mine, theirs in (
                    ("x", (r.left(), r.right()), (o.left(), o.right())),
                    ("y", (r.top(), r.bottom()), (o.top(), o.bottom()))):
                if axis is not None and axis != name:
                    continue
                c_mine = (mine[0] + mine[1]) / 2
                c_theirs = (theirs[0] + theirs[1]) / 2
                pairs = [(a, b) for a in mine for b in theirs] + [(c_mine, c_theirs)]
                for a, b in pairs:
                    off = b - a
                    if abs(off) <= tol and (best[name] is None or abs(off) < abs(best[name][0])):
                        best[name] = (off, b, o)
        dx = best["x"][0] if best["x"] else 0.0
        dy = best["y"][0] if best["y"] else 0.0
        snapped = r.translated(dx, dy)
        pen = QPen(QColor(theme.LIGHT["accent"]), 1, Qt.DashLine)
        pen.setCosmetic(True)
        if best["x"]:
            _, x, o = best["x"]
            self._guide(QPointF(x, min(snapped.top(), o.top())), QPointF(x, max(snapped.bottom(), o.bottom())), pen)
        if best["y"]:
            _, y, o = best["y"]
            self._guide(QPointF(min(snapped.left(), o.left()), y), QPointF(max(snapped.right(), o.right()), y), pen)
        return QPointF(d.x() + dx, d.y() + dy)

    def _drag_origin(self, item) -> QPointF:
        """Where the item sat when the drag began (its position before any of `d`)."""
        return item._drag[1][item] if item._drag else QPointF(item.pos())

    def _guide(self, a: QPointF, b: QPointF, pen: QPen) -> None:
        from PySide6.QtWidgets import QGraphicsLineItem
        g = QGraphicsLineItem(a.x(), a.y(), b.x(), b.y(), self.root)
        g.setPen(pen)
        g.setZValue(1000)
        self._guides.append(g)

    def _moved(self, gid: str, dx: float, dy: float) -> None:
        if gid.startswith("draw-"):
            moving = {it.el.meta["drawing"] for it in self.items if it.isSelected() and it.el.kind == "drawing"}
            moving.add(gid[5:])
            spec = copy.deepcopy(self.graph.spec)
            for d in spec.drawings:
                if d["id"] in moving:
                    d["x1"] += dx
                    d["x2"] += dx
                    d["y1"] += dy
                    d["y2"] += dy
            self.project.undo.push(SpecCommand(self.graph, spec, "Move Drawing"))
            return
        el = next((it.el for it in self.items if it.el.id == gid), None)
        if el is not None and el.meta.get("flipped"):        # stored in the upright layout's coordinates
            dx, dy = dy, -dx
        spec = copy.deepcopy(self.graph.spec)
        ox, oy = spec.offsets.get(gid, (0.0, 0.0))
        spec.offsets[gid] = (ox + dx, oy + dy)
        self.project.undo.push(SpecCommand(self.graph, spec, "Move"))

    def apply_font(self, **changes) -> None:
        """Ribbon Text group → fonts of the selected elements (all text if none). Drawn text
        keeps its own font."""
        texts = {it.el.meta["drawing"] for it in self.items if it.isSelected() and it.el.kind == "drawing"
                 and it.el.meta["drawing_kind"] == "text"}
        if texts:
            spec = copy.deepcopy(self.graph.spec)
            for d in spec.drawings:
                if d["id"] in texts:
                    d.update(changes)
            self.project.undo.push(SpecCommand(self.graph, spec, "Change Font"))
            return
        keys = sorted({k for e in self.selected_elements() for k in e.meta.get("font_keys", [])})
        spec = copy.deepcopy(self.graph.spec)
        for k in keys or list(spec.fonts):
            for attr, v in changes.items():
                setattr(spec.fonts[k], attr, v)
        self.project.undo.push(SpecCommand(self.graph, spec, "Change Font"))

    def current_font(self):
        for e in self.selected_elements():
            if e.meta.get("fontspec"):
                return e.meta["fontspec"]
            if e.meta.get("font_keys"):
                return self.graph.spec.fonts[e.meta["font_keys"][0]]
        return self.graph.spec.fonts["y_numbers"]

    def _start_edit(self, item: ElementItem) -> None:
        el = item.el
        fs = el.meta.get("fontspec") or self.graph.spec.fonts[el.meta["font_keys"][0]]
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
        if el.meta["field"].startswith("drawing:"):
            did = el.meta["field"][8:]
            spec = copy.deepcopy(self.graph.spec)
            if not text:                                   # emptied: the text goes
                spec.drawings = [d for d in spec.drawings if d["id"] != did]
                self.project.undo.push(SpecCommand(self.graph, spec, "Delete Text"))
            elif commit and text != el.meta["text"]:
                for d in spec.drawings:
                    if d["id"] == did:
                        d["text"] = text
                self.project.undo.push(SpecCommand(self.graph, spec, "Edit Text"))
            else:
                self.rebuild()
            return
        if commit and text != el.meta["text"]:
            spec = copy.deepcopy(self.graph.spec)
            if el.meta["field"] == "title":
                spec.title = text
                spec.show_title = bool(text)
            elif el.meta["field"] == "x_title":
                spec.x.title = text
            elif el.meta["field"] == "y2_title":
                spec.y2.title = text
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
        if isinstance(item, ElementItem) and item.el.kind == "drawing":
            did = item.el.meta["drawing"]
            m.addAction("Format…", lambda: self.edit_drawing(did))
            m.addAction("Bring to Front", lambda: self.restack_drawings(True))
            m.addAction("Send to Back", lambda: self.restack_drawings(False))
            if len(self.selected_drawings()) > 1:
                am = m.addMenu("Align")
                for key, text in ALIGN:
                    am.addAction(text, lambda k=key: self.align_drawings(k))
            m.addAction("Delete", self.delete_drawings)
            m.exec(self.view.viewport().mapToGlobal(pos))
            return
        if isinstance(item, ElementItem) and item.el.meta.get("function"):
            fid = item.el.meta["function"]
            m.addAction("Edit Function…", lambda: self.edit_function(fid))
            m.addAction("Remove Function", lambda: self.remove_function(fid))
            m.exec(self.view.viewport().mapToGlobal(pos))
            return
        if isinstance(item, ElementItem) and item.el.kind == "bracket":
            m.addAction("Hide this comparison", lambda gid=item.el.id: self._hide_bracket(gid))
            m.addAction("Format significance…", lambda: self.formatGraphRequested.emit("significance", None))
            m.addSeparator()
        if self.graph.spec.sig.get("hidden"):
            m.addAction("Show all comparisons", self._show_all_brackets)
        m.addAction("Format Graph…", lambda: self.formatGraphRequested.emit("style", None))
        m.addAction("Axes…", lambda: self.formatAxesRequested.emit("y"))
        m.exec(self.view.viewport().mapToGlobal(pos))

    def set_zoom(self, z: float) -> None:
        self.view.set_zoom(z)

    # --- text editing helpers (ribbon Text group) ------------------------------------

    def _editor(self, start: bool = True):
        """The inline editor; with start, begins editing the selected text if none is open."""
        if self._editing:
            return self._editing[0]
        if not start:
            return None
        item = next((it for it in self.items if it.isSelected() and it.el.meta.get("field")), None)
        if item is None:
            return None
        self._start_edit(item)
        ed = self._editing[0]
        cur = ed.textCursor()
        cur.movePosition(QTextCursor.End)
        ed.setTextCursor(cur)
        return ed

    def insert_text(self, s: str) -> bool:
        ed = self._editor()
        if ed is None:
            return False
        ed.textCursor().insertText(s)
        ed.setFocus()
        return True

    def script_selection(self, kind: str) -> bool:
        """Superscript or subscript the characters selected in the text being edited."""
        from .drawings import script
        ed = self._editor(start=False)
        if ed is None:
            return False
        cur = ed.textCursor()
        if not cur.hasSelection():
            return False
        cur.insertText(script(cur.selectedText(), kind))
        ed.setFocus()
        return True

    def align_text(self, how: str) -> None:
        ids = {it.el.meta["drawing"] for it in self.items if it.isSelected() and it.el.kind == "drawing"
               and it.el.meta["drawing_kind"] == "text"}
        if not ids:
            return
        spec = copy.deepcopy(self.graph.spec)
        for d in spec.drawings:
            if d["id"] in ids:
                d["align"] = how
        self.project.undo.push(SpecCommand(self.graph, spec, "Align Text"))

    # --- drawing tools ------------------------------------------------------------

    def set_tool(self, kind: str | None) -> None:
        self.tool = kind
        self.view.setDragMode(QGraphicsView.NoDrag if kind else QGraphicsView.RubberBandDrag)
        self.view.viewport().setCursor(Qt.CrossCursor if kind else Qt.ArrowCursor)
        if kind:
            self.scene.clearSelection()

    def _end_tool(self) -> None:
        if self._preview is not None:
            self.scene.removeItem(self._preview)
            self._preview = None
        self._draw_start = None
        self.set_tool(None)
        self.toolFinished.emit()

    def eventFilter(self, obj, e):
        from PySide6.QtCore import QEvent
        t = e.type()
        if obj is self.view and t == QEvent.KeyPress:
            if e.key() == Qt.Key_Escape and self.tool:
                self._end_tool()
                return True
            if e.key() in (Qt.Key_Delete, Qt.Key_Backspace) and self.selected_drawings() and not self._editing:
                self.delete_drawings()
                return True
            arrows = {Qt.Key_Left: (-1, 0), Qt.Key_Right: (1, 0), Qt.Key_Up: (0, 1), Qt.Key_Down: (0, -1)}
            if e.key() in arrows and not self._editing:
                step = 5.0 if e.modifiers() & Qt.ShiftModifier else 1.0
                dx, dy = arrows[e.key()]
                if self.nudge_selected(dx * step, dy * step):
                    return True
        if obj is self.view.viewport() and self.tool:
            if t == QEvent.MouseButtonPress and e.button() == Qt.LeftButton:
                self._draw_start = self.view.mapToScene(e.position().toPoint())
                return True
            if t == QEvent.MouseMove and self._draw_start is not None:
                self._update_preview(self._constrain(self.view.mapToScene(e.position().toPoint()), e.modifiers()))
                return True
            if t == QEvent.MouseButtonRelease and self._draw_start is not None:
                end = self._constrain(self.view.mapToScene(e.position().toPoint()), e.modifiers())
                self._commit_drawing(self._draw_start, end)
                return True
        return super().eventFilter(obj, e)

    def _constrain(self, p: QPointF, mods) -> QPointF:
        """Shift keeps lines at 45° steps and boxes square."""
        if not (mods & Qt.ShiftModifier) or self._draw_start is None:
            return p
        import math
        s = self._draw_start
        dx, dy = p.x() - s.x(), p.y() - s.y()
        if self.tool in ("line", "arrow"):
            ang = round(math.atan2(dy, dx) / (math.pi / 4)) * (math.pi / 4)
            r = math.hypot(dx, dy)
            return QPointF(s.x() + r * math.cos(ang), s.y() + r * math.sin(ang))
        m = max(abs(dx), abs(dy))
        return QPointF(s.x() + math.copysign(m, dx or 1), s.y() + math.copysign(m, dy or 1))

    def _update_preview(self, p: QPointF) -> None:
        from PySide6.QtWidgets import QGraphicsEllipseItem, QGraphicsLineItem
        s = self._draw_start
        pen = QPen(QColor(theme.LIGHT["accent"]), 1.0, Qt.DashLine)
        pen.setCosmetic(True)
        if self._preview is None:
            if self.tool in ("line", "arrow"):
                self._preview = QGraphicsLineItem()
            elif self.tool == "ellipse":
                self._preview = QGraphicsEllipseItem()
            else:
                self._preview = QGraphicsRectItem()
            self._preview.setPen(pen)
            self.scene.addItem(self._preview)
        if self.tool in ("line", "arrow"):
            self._preview.setLine(s.x(), s.y(), p.x(), p.y())
        else:
            self._preview.setRect(QRectF(s, p).normalized())

    def _commit_drawing(self, s: QPointF, e: QPointF) -> None:
        from .drawings import new_drawing
        kind = self.tool
        small = (e - s).manhattanLength() < 3.0
        if kind == "text":
            d = new_drawing("text", s.x(), s.y(), s.x(), s.y(), text="Text",
                            size=self.graph.spec.fonts["legend"].size)
        elif small:                                # a click: a default size
            w, h = (40.0, 0.0) if kind in ("line", "arrow") else (50.0, 30.0)
            d = new_drawing(kind, s.x(), s.y(), s.x() + w, s.y() + h)
        else:
            d = new_drawing(kind, s.x(), s.y(), e.x(), e.y())
        self._end_tool()
        spec = copy.deepcopy(self.graph.spec)
        spec.drawings.append(d)
        from .drawings import NAMES
        self.project.undo.push(SpecCommand(self.graph, spec, f"Draw {NAMES[kind]}"))
        it = next((i for i in self.items if i.el.id == f"draw-{d['id']}"), None)
        if it is not None:
            it.setSelected(True)
            if kind == "text":
                self._start_edit(it)

    def add_drawing(self, d: dict, text: str = "Add Drawing") -> None:
        spec = copy.deepcopy(self.graph.spec)
        spec.drawings.append(d)
        self.project.undo.push(SpecCommand(self.graph, spec, text))

    def plot_center(self) -> QPointF:
        r = QRectF()
        for it in self.items:
            if it.el.kind in ("x-axis", "y-axis"):
                r = r.united(it.el.bounds)
        return r.center() if not r.isNull() else QPointF(0, 0)

    def nudge_selected(self, dx: float, dy: float) -> bool:
        """Arrow keys: drawings move; data sets are nudged (up/down only on XY graphs)."""
        if self.selected_drawings():
            ids = set(self.selected_drawings())
            spec = copy.deepcopy(self.graph.spec)
            for d in spec.drawings:
                if d["id"] in ids:
                    d["x1"] += dx
                    d["x2"] += dx
                    d["y1"] -= dy
                    d["y2"] -= dy
            self.project.undo.push(SpecCommand(self.graph, spec, "Move Drawing"))
            return True
        cols = sorted({e.meta["column"] for e in self.selected_elements() if e.kind in ("dataset", "curve")})
        if not cols:
            return False
        xy = self.graph.table.table_type == "xy"
        if dy and not xy:
            return False
        spec = copy.deepcopy(self.graph.spec)
        for c in cols:
            st = spec.style(c)
            st.nudge += dx
            if xy:
                st.nudge_y += dy
        self.project.undo.push(SpecCommand(self.graph, spec, "Nudge Data Set"))
        return True

    def selected_drawings(self) -> list[str]:
        return [it.el.meta["drawing"] for it in self.items if it.isSelected() and it.el.kind == "drawing"]

    def delete_drawings(self) -> None:
        ids = set(self.selected_drawings())
        if not ids:
            return
        spec = copy.deepcopy(self.graph.spec)
        spec.drawings = [d for d in spec.drawings if d["id"] not in ids]
        self.project.undo.push(SpecCommand(self.graph, spec, "Delete Drawing"))

    def restack_drawings(self, front: bool) -> None:
        ids = set(self.selected_drawings())
        if not ids:
            return
        spec = copy.deepcopy(self.graph.spec)
        sel = [d for d in spec.drawings if d["id"] in ids]
        rest = [d for d in spec.drawings if d["id"] not in ids]
        spec.drawings = rest + sel if front else sel + rest
        self.project.undo.push(SpecCommand(self.graph, spec, "Bring to Front" if front else "Send to Back"))

    def align_drawings(self, how: str) -> None:
        from .drawings import bounds
        ids = set(self.selected_drawings())
        if len(ids) < 2:
            return
        spec = copy.deepcopy(self.graph.spec)
        ds = [d for d in spec.drawings if d["id"] in ids]
        bs = {d["id"]: bounds(d, spec) for d in ds}
        ref = {"left": min(b.left() for b in bs.values()), "right": max(b.right() for b in bs.values()),
               "top": min(b.top() for b in bs.values()), "bottom": max(b.bottom() for b in bs.values()),
               "hcenter": sum(b.center().x() for b in bs.values()) / len(bs),
               "vcenter": sum(b.center().y() for b in bs.values()) / len(bs)}[how]
        for d in ds:
            b = bs[d["id"]]
            dx = dy = 0.0
            if how == "left":
                dx = ref - b.left()
            elif how == "right":
                dx = ref - b.right()
            elif how == "hcenter":
                dx = ref - b.center().x()
            elif how == "top":
                dy = ref - b.top()
            elif how == "bottom":
                dy = ref - b.bottom()
            else:
                dy = ref - b.center().y()
            d["x1"] += dx
            d["x2"] += dx
            d["y1"] += dy
            d["y2"] += dy
        self.project.undo.push(SpecCommand(self.graph, spec, "Align"))

    def _reshaped(self, did: str, handle: str, x: float, y: float) -> None:
        spec = copy.deepcopy(self.graph.spec)
        for d in spec.drawings:
            if d["id"] != did:
                continue
            if handle == "p1":
                d["x1"], d["y1"] = x, y
            elif d["kind"] in ("line", "arrow"):
                d["x2"], d["y2"] = x, y
            else:                                   # far corner of a box, ellipse or picture
                if d["x2"] >= d["x1"]:
                    d["x2"] = x
                else:
                    d["x1"] = x
                if d["y2"] >= d["y1"]:
                    d["y2"] = y
                else:
                    d["y1"] = y
        self.project.undo.push(SpecCommand(self.graph, spec, "Resize Drawing"))

    def edit_function(self, fid: str | None = None) -> bool:
        """Add a function (fid None) or edit one; returns whether something changed."""
        import uuid
        from ..dialogs.function import FunctionDialog
        old = next((f for f in self.graph.spec.functions if f.get("id") == fid), None)
        dlg = FunctionDialog(old, self.auto_range, self)
        if not dlg.exec():
            return False
        new = dlg.value()
        spec = copy.deepcopy(self.graph.spec)
        if old is None:
            new["id"] = uuid.uuid4().hex[:8]
            spec.functions.append(new)
        else:
            new["id"] = fid
            spec.functions = [new if f.get("id") == fid else f for f in spec.functions]
        self.project.undo.push(SpecCommand(self.graph, spec, "Plot Function" if old is None else "Edit Function"))
        return True

    def remove_function(self, fid: str) -> None:
        spec = copy.deepcopy(self.graph.spec)
        spec.functions = [f for f in spec.functions if f.get("id") != fid]
        self.project.undo.push(SpecCommand(self.graph, spec, "Remove Function"))

    def edit_drawing(self, did: str) -> None:
        from ..dialogs.drawing import DrawingDialog
        d = next((x for x in self.graph.spec.drawings if x["id"] == did), None)
        if d is None:
            return
        dlg = DrawingDialog(d, self)
        if dlg.exec():
            spec = copy.deepcopy(self.graph.spec)
            spec.drawings = [dlg.value() if x["id"] == did else x for x in spec.drawings]
            self.project.undo.push(SpecCommand(self.graph, spec, "Format Drawing"))


ALIGN = [("left", "Left edges"), ("hcenter", "Centres (horizontally)"), ("right", "Right edges"),
         ("top", "Top edges"), ("vcenter", "Middles (vertically)"), ("bottom", "Bottom edges")]


def _forward_selection(ref):
    """Scene selection → the sheet's selectionChanged, unless the sheet is being destroyed."""
    def forward():
        sheet = ref()
        if sheet is None:
            return
        from shiboken6 import isValid
        if not isValid(sheet) or not all(isValid(i) for i in getattr(sheet, "items", [])):
            return                              # the scene is tearing its items down
        try:
            sheet.selectionChanged.emit()
        except (RuntimeError, TypeError):      # its Qt side is already gone
            pass
    return forward
