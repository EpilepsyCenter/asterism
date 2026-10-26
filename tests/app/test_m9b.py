"""M9b: colour labels on sheets and the overview of all graphs."""

from __future__ import annotations

import pytest


def _project():
    from asterism.analysis import engine
    from asterism.doc.sample import sample_project
    p = sample_project(engine)
    p.add_table(table_type="xy", example=True)
    p.add_table(table_type="grouped", y_format="replicates", replicates=3, example=True)
    p.add_figure()
    return p


def test_labels_are_undoable_and_saved(app, tmp_path):
    from asterism.analysis import engine
    from asterism.doc import fileformat
    from asterism.doc.commands import LabelCommand, LabelNamesCommand
    p = _project()
    t, g = p.tables[0], p.graphs[0]
    p.undo.push(LabelCommand([t, g], 4))
    assert t.tag == g.tag == 4
    p.undo.undo()
    assert t.tag == g.tag == 0
    p.undo.redo()
    p.undo.push(LabelNamesCommand(p, {4: "Final"}))
    assert p.label_name(4) == "Final" and p.label_name(1) == "Red"
    path = tmp_path / "l.asterism"
    fileformat.save(p, str(path))
    q = fileformat.load(str(path), engine)
    assert q.find(t.id).tag == 4 and q.find(g.id).tag == 4 and q.label_names == {4: "Final"}
    assert sum(1 for sh in q.sheets() if sh.tag) == 2
    assert t.label(t.used_columns()[0])                # a table's column labels are untouched


def test_sidebar_dots_filter_and_menu(app):
    from PySide6.QtCore import Qt
    from asterism.app.sidebar import ProjectSidebar
    from asterism.app.widgets import TAG_ROLE
    p = _project()
    sb = ProjectSidebar(p)
    g = p.graphs[0]
    sb.set_tag([g], 2)
    sb.rebuild()
    items = list(sb._items())
    row = next(it for it in items if it.data(0, Qt.UserRole) is g)
    assert row.data(0, TAG_ROLE) == 2
    sb._tag_filter_picked(2)
    visible = [it.data(0, Qt.UserRole) for it in sb._items() if it.data(0, Qt.UserRole) is not None
               and not it.isHidden()]
    assert g in visible and p.root_table(g) in visible            # its table stays, for context
    assert all(s.tag == 2 or s is p.root_table(g) for s in visible)
    sb._tag_filter_picked(2)                                       # again: filter off
    assert all(not it.isHidden() for it in sb._items())


def test_overview_groups_filters_and_actions(app, monkeypatch):
    from asterism.app.main_window import MainWindow
    p = _project()
    w = MainWindow(p)
    w.show_overview()
    ov = w.overview
    assert w.stack.currentWidget() is ov and w.current is None
    assert ov.count() == len(p.graphs)
    titles = [title for title, _k, _items in ov.groups()]
    assert titles[0] == p.tables[0].name
    ov.render_all()
    assert all(c.pixmap is not None for c in ov.cards)
    ov.search.setText(p.graphs[0].name[:6])
    assert 1 <= ov.count() <= len(p.graphs)
    ov.search.setText("")
    ov.c_results.setChecked(False)
    assert all(c.sheet.source is None for c in ov.cards)
    ov.c_results.setChecked(True)
    ov.c_figures.setChecked(True)
    # selection, labels from the shortcut actions
    from PySide6.QtCore import Qt
    ov.click(ov.cards[0], Qt.NoModifier)
    ov.click(ov.cards[1], Qt.ShiftModifier)
    assert len(ov.selected) == 2
    w.a_tags[5].trigger()
    assert all(s.tag == 5 for s in ov.selected)
    ov.tag_combo.setCurrentIndex(ov.tag_combo.findData(5))
    assert ov.count() == 2
    ov.tag_combo.setCurrentIndex(0)
    # duplicate, apply formatting, add to figure
    n = len(p.graphs)
    w.duplicate_graph(p.graphs[0])
    assert len(p.graphs) == n + 1 and p.graphs[-1].name.endswith("copy")
    src, dst = p.graphs[0], p.graphs[-1]
    src.spec.y_len_mm = 77.0
    w._copy_format_to(src, [dst])
    assert dst.spec.y_len_mm == 77.0
    from PySide6.QtWidgets import QInputDialog
    monkeypatch.setattr(QInputDialog, "getItem", lambda *a, **k: ("New figure", True))
    w.add_graphs_to_figure([p.graphs[0], p.graphs[1]])
    assert len(p.figures[-1].panels) == 2
    # opening a sheet leaves the overview
    w.show_sheet(p.graphs[0])
    assert not w.sidebar.overview_btn.isChecked()
    p.mark_saved()
    w.close()


def test_label_names_dialog(app):
    from asterism.app.dialogs.labels import LabelNamesDialog
    p = _project()
    d = LabelNamesDialog(p)
    d.edits[1].setText("To check")
    assert d.names() == {1: "To check"}
