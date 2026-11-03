"""Dragging the handles of a selected axis resizes the plot area (one undo step)."""

from __future__ import annotations

import pytest


def _drag(gs, handle: str, dx: float, dy: float) -> None:
    """Drag one of the plot-area handles by (dx, dy) points, with the mouse."""
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    a = gs.resizer.mapToScene(gs.resizer._handles()[handle])
    vp = gs.view.viewport()
    start = gs.view.mapFromScene(a)
    z = gs.view.transform().m11()
    end = start + QPoint(round(dx * z), round(dy * z))
    QTest.mousePress(vp, Qt.LeftButton, Qt.NoModifier, start)
    QTest.mouseMove(vp, start + QPoint(3, 3))
    QTest.mouseMove(vp, end)
    QTest.mouseRelease(vp, Qt.LeftButton, Qt.NoModifier, end)


def _sheet(g, p):
    from asterism.app.graph.view import GraphSheet
    gs = GraphSheet(g, p)
    gs.resize(900, 700)
    gs.show()
    gs.view.set_zoom(1.0)
    return gs


def _select(gs, gid: str) -> None:
    gs.scene.clearSelection()
    next(it for it in gs.items if it.el.id == gid).setSelected(True)


def test_column_graph_axes_drag_wider_and_taller(app):
    from asterism.analysis import engine
    from asterism.doc.sample import sample_project
    p = sample_project(engine)
    g = p.graphs[0]
    gs = _sheet(g, p)
    assert not gs.resizer.isVisible()
    _select(gs, "y-axis")
    assert gs.resizer.isVisible()
    r = gs.resizer.rect
    cw, yl = g.spec.col_width_mm, g.spec.y_len_mm
    _drag(gs, "r", r.width() / 2, 0)               # half as wide again
    assert g.spec.col_width_mm == pytest.approx(cw * 1.5, abs=0.2)
    assert g.spec.y_len_mm == yl
    _select(gs, "x-axis")
    r = gs.resizer.rect
    _drag(gs, "t", 0, -r.height())                 # dragging the top up doubles the height
    assert g.spec.y_len_mm == pytest.approx(yl * 2, abs=0.2)
    p.undo.undo()
    p.undo.undo()
    assert (g.spec.col_width_mm, g.spec.y_len_mm) == (cw, yl)
    gs.close()


def test_xy_graph_corner_drag_sets_both_lengths(app):
    from asterism.analysis import engine
    from asterism.doc.sample import sample_project
    p = sample_project(engine)
    t = p.add_table(table_type="xy", example=True)
    g = next(g for g in p.graphs if g.table is t)
    gs = _sheet(g, p)
    _select(gs, "x-axis")
    r = gs.resizer.rect
    xl, yl = g.spec.x_len_mm, g.spec.y_len_mm
    _drag(gs, "br", -r.width() / 2, r.height() / 2)
    assert g.spec.x_len_mm == pytest.approx(xl / 2, abs=0.2)
    assert g.spec.y_len_mm == pytest.approx(yl * 1.5, abs=0.2)
    gs.close()


def test_horizontal_graph_maps_across_to_the_value_axis(app):
    from asterism.analysis import engine
    from asterism.doc.sample import sample_project
    p = sample_project(engine)
    g = p.graphs[0]
    g.spec.horizontal = True
    gs = _sheet(g, p)
    _select(gs, "y-axis")
    r = gs.resizer.rect
    cw, yl = g.spec.col_width_mm, g.spec.y_len_mm
    _drag(gs, "r", r.width(), 0)                   # across = the value axis = the height setting
    assert g.spec.y_len_mm == pytest.approx(yl * 2, abs=0.2)
    assert g.spec.col_width_mm == cw
    gs.close()
