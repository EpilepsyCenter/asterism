"""Data tables in the app: the grid per type, entry, structure tools, dialogs (M2)."""

from __future__ import annotations

import pytest


def _window(app, tt="column", example=True, **fmt):
    from asterism.analysis import engine
    from asterism.app.main_window import MainWindow
    from asterism.doc.model import Project
    p = Project(engine)
    p.add_table(table_type=tt, example=example, **fmt)
    p.undo.clear()
    p.mark_saved()
    return MainWindow(p)


@pytest.fixture
def close_later():
    wins = []
    yield wins.append
    for w in wins:
        w.project.mark_saved()
        w.close()


def test_grid_columns_follow_the_table_type(app, close_later):
    w = _window(app, "xy", y_format="replicates", replicates=2, x_format="numbers_err",
                row_titles=True)
    close_later(w)
    view = w._widget_for(w.project.tables[0])
    assert view.model().keys[:5] == ["row", "x", "xerr", 0, 1]
    assert view.horizontalHeader().has_sub_row()
    assert view.horizontalHeader().sizeHint().height() > 40


def test_text_only_where_allowed(app, close_later):
    w = _window(app, "multivar", example=False)
    close_later(w)
    view = w._widget_for(w.project.tables[0])
    m = view.model()
    assert m.setData(m.index(0, 0), "female") and w.project.tables[0].get(0, 0) == "female"
    w2 = _window(app, "column", example=False)
    close_later(w2)
    m2 = w2._widget_for(w2.project.tables[0]).model()
    assert not m2.setData(m2.index(0, 0), "female")
    w3 = _window(app, "survival", example=False)
    close_later(w3)
    m3 = w3._widget_for(w3.project.tables[0]).model()
    assert not m3.setData(m3.index(0, 1), "2") and m3.setData(m3.index(0, 1), "1")


def test_structure_tools_from_the_window(app, close_later):
    w = _window(app, "column")
    close_later(w)
    t = w.project.tables[0]
    w.show_sheet(t)
    view = w._widget_for(t)
    view.setCurrentIndex(view.model().index(0, 0))
    view.selectRow(0)
    n0 = t.nrows_used()
    w.a_insert_row.trigger()
    assert t.get(0, 0) is None and t.nrows_used() == n0 + 1
    w.a_undo.trigger()
    assert t.nrows_used() == n0
    view.setCurrentIndex(view.model().index(0, 0))
    w.a_insert_set.trigger()
    assert t.titles[:3] == ["", "Control", "Treated"]
    w.a_undo.trigger()
    view.setCurrentIndex(view.model().index(2, 1))
    view.selectionModel().select(view.model().index(2, 1), __import__("PySide6.QtCore", fromlist=["QItemSelectionModel"]).QItemSelectionModel.ClearAndSelect)
    w.a_exclude.trigger()
    assert t.is_excluded(2, 1) and view.model().index(2, 1).data(0x0100)
    w.a_exclude.trigger()
    assert not t.is_excluded(2, 1)


def test_new_table_dialog_for_every_type(app, close_later, monkeypatch):
    from asterism.app.dialogs.new_table import NewTableDialog
    from asterism.doc.table import TABLE_TYPES
    w = _window(app, "column")
    close_later(w)
    for tt in TABLE_TYPES:
        dlg = NewTableDialog(w, table_type=tt)
        assert dlg.current_section() == tt
        got_tt, fmt, _ = dlg.choice()
        assert got_tt == tt and "y_format" in fmt
    monkeypatch.setattr(NewTableDialog, "exec", lambda self: (self.show_section("grouped"),
                                                              self.example.setChecked(True), 1)[2])
    w.new_table()
    t = w.project.tables[-1]
    assert t.table_type == "grouped" and t.used_columns() and w.current is t
    assert w.project.graphs[-1].table is t                     # starter graph


def test_table_format_dialog_and_undo(app, close_later, monkeypatch):
    from asterism.app.dialogs.new_table import TableFormatDialog
    w = _window(app, "grouped", y_format="replicates", replicates=3)
    close_later(w)
    t = w.project.tables[0]
    w.show_sheet(t)

    def run(self):
        self.opts.reps.setValue(2)
        return 1
    monkeypatch.setattr(TableFormatDialog, "exec", run)
    w.table_format()
    assert t.replicates == 2
    w.a_undo.trigger()
    assert t.replicates == 3


def test_start_screen_replaces_the_empty_project(app, close_later, monkeypatch):
    from asterism.app.dialogs.new_table import NewTableDialog
    from asterism.app.main_window import MainWindow
    w = MainWindow()
    close_later(w)
    monkeypatch.setattr(NewTableDialog, "exec", lambda self: (self.show_section("survival"), 1)[1])
    w.show_start_screen()
    assert [t.table_type for t in w.project.tables] == ["survival"]
    assert len(w.project.graphs) == 1 and not w.project.is_modified()


@pytest.fixture
def no_multivar_graphs():
    """Every table type has graphs now; pretend one doesn't, to exercise the placeholder."""
    from asterism.app.graph.layout import GRAPHABLE_TYPES
    GRAPHABLE_TYPES.discard("multivar")
    yield
    GRAPHABLE_TYPES.add("multivar")


def test_graph_placeholder_for_types_without_graphs_yet(app, close_later, no_multivar_graphs):
    w = _window(app, "multivar")
    close_later(w)
    g = w.project.graphs[0]
    gs = w._widget_for(g)
    assert not gs.is_graphable() and gs._placeholder is not None and not gs.items


def test_summary_column_table_graphs_entered_error(app):
    from asterism.analysis import engine
    from asterism.app.graph.layout import build
    from asterism.doc.model import Project
    p = Project(engine)
    t = p.add_table(table_type="column", y_format="mean_sd_n", example=False)
    for s, v in enumerate((10.0, 2.0, 4.0)):
        t.set(0, t.flat(0, s), v)
    g = p.graphs[0]
    g.spec.style(0).line_at = "mean_sd"
    els, rng = build(g)
    assert any(e.id == "data-A" for e in els) and rng.vmax >= 12.0
    g.spec.style(0).line_at = "mean_sem"
    _, rng2 = build(g)
    assert rng2.vmax >= 11.0


def test_placeholder_graph_disables_graph_tools(app, close_later, no_multivar_graphs):
    w = _window(app, "multivar")
    close_later(w)
    w.show_sheet(w.project.graphs[0])
    assert not w.a_fmt_graph.isEnabled() and not w.a_export_pdf.isEnabled()
    assert "not available yet" in w.top.subtitle.text()
