"""The figure editor: the page on a canvas, panels you can select, move (snapping to the
grid and to other panels' edges), resize (scale), delete and open. Every change is one
undoable FigureCommand; the view rebuilds from the model, so undo, file loading and live
updates of the graphs all just redraw."""

from __future__ import annotations

import copy

from PySide6.QtCore import QPointF, QRectF, QSizeF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QGraphicsDropShadowEffect, QGraphicsItem, QGraphicsObject,
                               QGraphicsRectItem, QGraphicsScene, QGraphicsView, QMenu, QVBoxLayout,
                               QWidget)

from ...doc.commands import FigureCommand
from .. import theme
from ..graph.canvas import MM, QtCanvas
from ..graph.view import GraphView
from .layout import build_figure

HANDLE = 7.0
SNAP_EDGE_MM = 2.0


class PanelItem(QGraphicsObject):
    moved = Signal()
    resized = Signal(object, float, float)        # item, new width, new height (points)
    activated = Signal(object)

    def __init__(self, el, sheet: "FigureSheetView"):
        super().__init__()
        self.el, self.sheet = el, sheet
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setAcceptHoverEvents(True)
        self._resizing = None

    def boundingRect(self) -> QRectF:
        return self.el.rect.adjusted(-HANDLE, -HANDLE, HANDLE, HANDLE)

    def _handle_rect(self) -> QRectF:
        r = self.el.rect
        s = HANDLE / max(self.sheet.view.transform().m11(), 0.01)
        return QRectF(r.right() - s / 2, r.bottom() - s / 2, s, s)

    def paint(self, p: QPainter, option, widget=None) -> None:
        self.el.draw(QtCanvas(p))
        if self.isSelected():
            pen = QPen(QColor(theme.LIGHT["accent"]), 1.2)
            pen.setCosmetic(True)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawRect(self.el.rect)
            p.setBrush(QColor("#ffffff"))
            p.drawRect(self._handle_rect())

    def hoverMoveEvent(self, e) -> None:
        self.setCursor(Qt.SizeFDiagCursor if self.isSelected() and self._handle_rect().contains(e.pos())
                       else Qt.ArrowCursor)

    def mousePressEvent(self, e) -> None:
        if self.isSelected() and self._handle_rect().contains(e.pos()) and e.button() == Qt.LeftButton:
            self._resizing = (e.pos(), QRectF(self.el.rect))
            e.accept()
            return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e) -> None:
        if self._resizing:
            start, r0 = self._resizing
            d = e.pos() - start
            self.prepareGeometryChange()
            self.el.rect = QRectF(r0.topLeft(), r0.size() + QSizeF(d.x(), d.y()))
            self.update()
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e) -> None:
        if self._resizing:
            r = self.el.rect
            self._resizing = None
            self.resized.emit(self, r.width(), r.height())
            return
        super().mouseReleaseEvent(e)
        if self.pos() != QPointF(0, 0):
            self.moved.emit()

    def mouseDoubleClickEvent(self, e) -> None:
        self.activated.emit(self)


class FigureSheetView(QWidget):
    openSheetRequested = Signal(object)
    editTextRequested = Signal(str)               # panel id
    selectionChanged = Signal()

    def __init__(self, figure, project, parent=None):
        super().__init__(parent)
        self.figure, self.project = figure, project
        self.scene = QGraphicsScene(self)
        self.view = GraphView(self.scene)
        self.view.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        self.view.setDragMode(QGraphicsView.RubberBandDrag)
        self.view.setFrameShape(QGraphicsView.NoFrame)
        self.view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self._context_menu)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.view)
        self.items: list[PanelItem] = []
        self._watched: list = []
        self._apply_theme()
        theme.notifier.changed.connect(self._apply_theme)
        figure.changed.connect(self.rebuild)
        project.structure_changed.connect(self.rebuild)
        self.scene.selectionChanged.connect(self.selectionChanged)
        self.rebuild()
        self.fit_page()

    def _apply_theme(self) -> None:
        self.view.setBackgroundBrush(theme.color("canvas"))

    def fit_page(self) -> None:
        w, h = self.figure.page_mm()
        vw, vh = max(self.view.viewport().width(), 400), max(self.view.viewport().height(), 400)
        self.view.set_zoom(min(vw / (w * MM + 60), vh / (h * MM + 60), 2.0))

    def set_zoom(self, z: float) -> None:
        self.view.set_zoom(z)

    # --- building ----------------------------------------------------------------

    def _watch(self) -> None:
        for sig in self._watched:
            try:
                sig.disconnect(self.rebuild)
            except Exception:
                pass
        self._watched = []
        for p in self.figure.panels:
            ref = p.get("ref", "")
            # a graph (follows its data and analyses), a table, an analysis (its results), or
            # an analysis's result table ("<id>.out": follow the analysis)
            s = self.project.find(ref[:-4] if isinstance(ref, str) and ref.endswith(".out") else ref)
            if s is not None and hasattr(s, "changed"):
                s.changed.connect(self.rebuild)
                self._watched.append(s.changed)

    def rebuild(self) -> None:
        selected = {it.el.panel for it in self.items if it.isSelected()}
        self.scene.blockSignals(True)
        self.scene.clear()
        self.items = []
        page, els = build_figure(self.figure, self.project)
        shadow_host = QGraphicsRectItem(page)
        shadow_host.setBrush(QColor("#ffffff"))
        shadow_host.setPen(QPen(QColor(0, 0, 0, 40), 0.5))
        fx = QGraphicsDropShadowEffect()
        fx.setBlurRadius(18)
        fx.setOffset(0, 2)
        fx.setColor(QColor(0, 0, 0, 60))
        shadow_host.setGraphicsEffect(fx)
        self.scene.addItem(shadow_host)
        letters = [e for e in els if e.kind == "letter"]
        for e in els:
            if e.kind == "letter":
                continue
            it = PanelItem(e, self)
            it.moved.connect(self._commit_moves)
            it.resized.connect(self._commit_resize)
            it.activated.connect(self._activated)
            self.scene.addItem(it)
            it.setSelected(e.panel in selected)
            self.items.append(it)
        for e in letters:
            li = _Static(e)
            li.setZValue(10)
            self.scene.addItem(li)
        margin = 40
        self.scene.setSceneRect(page.adjusted(-margin, -margin, margin, margin))
        self.scene.blockSignals(False)
        self._watch()
        self.selectionChanged.emit()

    # --- edits --------------------------------------------------------------------

    def selected_ids(self) -> list[str]:
        return [it.el.panel for it in self.items if it.isSelected()]

    def _push(self, st: dict, text: str) -> None:
        self.project.undo.push(FigureCommand(self.figure, st, text))

    def _snap(self, pid: str, x_mm: float, y_mm: float, w_mm: float, h_mm: float) -> tuple[float, float]:
        """Snap a panel's top-left to other panels' edges (within 2 mm), else to the grid."""
        page = self.figure.page
        others = [it.el.rect for it in self.items if it.el.panel != pid]
        ex = [(r.left() / MM, r.right() / MM) for r in others]
        ey = [(r.top() / MM, r.bottom() / MM) for r in others]

        def best(v, size, edges):
            cands = []
            for a, b in edges:
                for target in (a, b):
                    cands += [(abs(v - target), target), (abs(v + size - target), target - size)]
            cands = [c for c in cands if c[0] <= SNAP_EDGE_MM]
            return min(cands)[1] if cands else None
        sx, sy = best(x_mm, w_mm, ex), best(y_mm, h_mm, ey)
        g = float(page.get("grid", 5.0) or 0)
        if page.get("snap", True) and g > 0:
            if sx is None:
                sx = round(x_mm / g) * g
            if sy is None:
                sy = round(y_mm / g) * g
        return (sx if sx is not None else x_mm, sy if sy is not None else y_mm)

    def _commit_moves(self) -> None:
        st = copy.deepcopy(self.figure.state())
        by_id = {p["id"]: p for p in st["panels"]}
        moved = [it for it in self.items if it.pos() != QPointF(0, 0)]
        if not moved:
            return
        lead = moved[0]
        r = lead.el.rect.translated(lead.pos())          # where it was dropped
        nx, ny = self._snap(lead.el.panel, r.left() / MM, r.top() / MM, r.width() / MM, r.height() / MM)
        # every moved panel shifts by the lead panel's snapped displacement
        ddx, ddy = nx - lead.el.rect.left() / MM, ny - lead.el.rect.top() / MM
        for it in moved:
            pn = by_id[it.el.panel]
            pn["x"] = round(pn["x"] + ddx, 2)
            pn["y"] = round(pn["y"] + ddy, 2)
        self._push(st, "Move Panel" if len(moved) == 1 else "Move Panels")

    def _commit_resize(self, item: PanelItem, w: float, h: float) -> None:
        st = copy.deepcopy(self.figure.state())
        pn = next(p for p in st["panels"] if p["id"] == item.el.panel)
        if pn["kind"] == "text":
            pn["w"], pn["h"] = max(10.0, w / MM), max(5.0, h / MM)
        else:
            # graphs and tables scale, keeping their proportions: the larger relative change wins
            old = self._natural_size(pn)
            if old is not None:
                sw, sh = w / old[0], h / old[1]
                pn["scale"] = round(max(0.1, min(5.0, max(sw, sh))), 3)
        self._push(st, "Resize Panel")

    def _natural_size(self, pn) -> tuple[float, float] | None:
        """A panel's size at scale 1 (points)."""
        st = copy.deepcopy(self.figure.state())
        one = next(p for p in st["panels"] if p["id"] == pn["id"])
        one["scale"] = 1.0
        from ...doc.model import FigureSheet
        tmp = FigureSheet()
        tmp.page = st["page"]
        tmp.panels = [one]
        _, els = build_figure(tmp, self.project)
        r = next((e.rect for e in els if e.panel == pn["id"] and e.kind != "letter"), None)
        return (r.width(), r.height()) if r is not None else None

    def remove_selected(self) -> None:
        ids = set(self.selected_ids())
        if not ids:
            return
        st = copy.deepcopy(self.figure.state())
        st["panels"] = [p for p in st["panels"] if p["id"] not in ids]
        self._push(st, "Remove Panel" if len(ids) == 1 else "Remove Panels")

    def nudge(self, dx_mm: float, dy_mm: float) -> None:
        ids = set(self.selected_ids())
        if not ids:
            return
        st = copy.deepcopy(self.figure.state())
        for p in st["panels"]:
            if p["id"] in ids:
                p["x"] = round(p["x"] + dx_mm, 2)
                p["y"] = round(p["y"] + dy_mm, 2)
        self._push(st, "Nudge")

    def restack(self, front: bool) -> None:
        ids = set(self.selected_ids())
        if not ids:
            return
        st = copy.deepcopy(self.figure.state())
        sel = [p for p in st["panels"] if p["id"] in ids]
        rest = [p for p in st["panels"] if p["id"] not in ids]
        st["panels"] = rest + sel if front else sel + rest
        self._push(st, "Bring to Front" if front else "Send to Back")

    def align(self, how: str) -> None:
        """left | right | top | bottom | hcenter | vcenter for the selected panels."""
        sel = [it for it in self.items if it.isSelected()]
        if len(sel) < 2:
            return
        st = copy.deepcopy(self.figure.state())
        by_id = {p["id"]: p for p in st["panels"]}
        rs = {it.el.panel: it.el.rect for it in sel}
        if how == "left":
            v = min(r.left() for r in rs.values())
            for pid, r in rs.items():
                by_id[pid]["x"] = round(by_id[pid]["x"] + (v - r.left()) / MM, 2)
        elif how == "right":
            v = max(r.right() for r in rs.values())
            for pid, r in rs.items():
                by_id[pid]["x"] = round(by_id[pid]["x"] + (v - r.right()) / MM, 2)
        elif how == "top":
            v = min(r.top() for r in rs.values())
            for pid, r in rs.items():
                by_id[pid]["y"] = round(by_id[pid]["y"] + (v - r.top()) / MM, 2)
        elif how == "bottom":
            v = max(r.bottom() for r in rs.values())
            for pid, r in rs.items():
                by_id[pid]["y"] = round(by_id[pid]["y"] + (v - r.bottom()) / MM, 2)
        elif how == "hcenter":
            v = sum(r.center().x() for r in rs.values()) / len(rs)
            for pid, r in rs.items():
                by_id[pid]["x"] = round(by_id[pid]["x"] + (v - r.center().x()) / MM, 2)
        elif how == "vcenter":
            v = sum(r.center().y() for r in rs.values()) / len(rs)
            for pid, r in rs.items():
                by_id[pid]["y"] = round(by_id[pid]["y"] + (v - r.center().y()) / MM, 2)
        self._push(st, "Align Panels")

    def same_width(self) -> None:
        """Scale the selected graphs and tables to the width of the first selected."""
        sel = [it for it in self.items if it.isSelected() and it.el.kind in ("graph", "table", "results")]
        if len(sel) < 2:
            return
        st = copy.deepcopy(self.figure.state())
        by_id = {p["id"]: p for p in st["panels"]}
        target = sel[0].el.rect.width()
        for it in sel[1:]:
            nat = self._natural_size(by_id[it.el.panel])
            if nat:
                by_id[it.el.panel]["scale"] = round(target / nat[0], 3)
        self._push(st, "Same Width")

    def arrange_grid(self, columns: int, gap_mm: float = 8.0, margin_mm: float = 15.0) -> None:
        """Arrange the selected panels (or all) in a grid, in their current reading order."""
        sel = [it for it in self.items if it.isSelected()] or list(self.items)
        if not sel:
            return
        sel.sort(key=lambda it: (round(it.el.rect.top() / (8 * MM)), it.el.rect.left()))
        st = copy.deepcopy(self.figure.state())
        by_id = {p["id"]: p for p in st["panels"]}
        cols = max(1, columns)
        x0 = y = margin_mm
        for i in range(0, len(sel), cols):
            row = sel[i:i + cols]
            x = x0
            for it in row:
                r = it.el.rect
                pn = by_id[it.el.panel]
                pn["x"], pn["y"] = round(x, 2), round(y, 2)
                x += r.width() / MM + gap_mm
            y += max(it.el.rect.height() for it in row) / MM + gap_mm
        self._push(st, "Arrange in a Grid")

    # --- interaction ------------------------------------------------------------------

    def _activated(self, item: PanelItem) -> None:
        kind = item.el.kind
        if kind == "text":
            self.editTextRequested.emit(item.el.panel)
            return
        ref = next((p["ref"] for p in self.figure.panels if p["id"] == item.el.panel), "")
        s = self.project.find(ref)
        if s is None and ref.endswith(".out"):
            s = self.project.find(ref[:-4])
        if s is not None:
            self.openSheetRequested.emit(s)

    def keyPressEvent(self, e) -> None:
        step = 5.0 if e.modifiers() & Qt.ShiftModifier else 1.0
        if e.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            self.remove_selected()
        elif e.key() == Qt.Key_Left:
            self.nudge(-step, 0)
        elif e.key() == Qt.Key_Right:
            self.nudge(step, 0)
        elif e.key() == Qt.Key_Up:
            self.nudge(0, -step)
        elif e.key() == Qt.Key_Down:
            self.nudge(0, step)
        else:
            super().keyPressEvent(e)

    def _context_menu(self, pos) -> None:
        item = self.view.itemAt(pos)
        if isinstance(item, PanelItem) and not item.isSelected():
            self.scene.clearSelection()
            item.setSelected(True)
        m = QMenu(self)
        if self.selected_ids():
            if isinstance(item, PanelItem) and item.el.kind != "text":
                m.addAction("Open", lambda: self._activated(item))
            m.addAction("Bring to Front", lambda: self.restack(True))
            m.addAction("Send to Back", lambda: self.restack(False))
            m.addSeparator()
            m.addAction("Remove from Figure", self.remove_selected)
        m.exec(self.view.viewport().mapToGlobal(pos))


class _Static(QGraphicsItem):
    """A non-interactive element (panel letters)."""

    def __init__(self, el):
        super().__init__()
        self.el = el

    def boundingRect(self) -> QRectF:
        return self.el.rect.adjusted(-2, -2, 2, 2)

    def paint(self, p, option, widget=None) -> None:
        self.el.draw(QtCanvas(p))
