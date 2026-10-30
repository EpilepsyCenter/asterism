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


def _type(view, text):
    """Type as a user would: the first key opens the editor, the rest go into it."""
    from PySide6.QtTest import QTest
    QTest.keyClicks(view, text[0])
    if text[1:]:
        QTest.keyClicks(_editor(view), text[1:])


def _editor(view):
    from asterism.app.table_view import EntryEditor
    eds = [e for e in view.findChildren(EntryEditor) if e.isVisible()]
    assert len(eds) == 1
    return eds[0]


def test_arrows_save_and_move_while_typing(app, close_later):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    w = _window(app, "column", example=False)
    close_later(w)
    t = w.project.tables[0]
    w.show_sheet(t)
    w.show()
    view = w._widget_for(t)
    view.setFocus()
    m = view.model()
    view.setCurrentIndex(m.index(0, 0))
    _type(view, "12")
    QTest.keyClick(_editor(view), Qt.Key_Right)          # typed: → saves and moves right
    assert t.get(0, 0) == 12 and view.currentIndex() == m.index(0, 1)
    _type(view, "7")
    QTest.keyClick(_editor(view), Qt.Key_Down)
    assert t.get(0, 1) == 7 and view.currentIndex() == m.index(1, 1)
    QTest.keyClick(view, Qt.Key_Left)                     # not editing: plain cell moves
    assert view.currentIndex() == m.index(1, 0)
    # After F2 (edit what's there), ←/→ move the text cursor and ↑ still saves and moves.
    view.setCurrentIndex(m.index(0, 1))
    QTest.keyClick(view, Qt.Key_F2)
    ed = _editor(view)
    ed.setCursorPosition(1)
    QTest.keyClick(ed, Qt.Key_Left)
    assert ed.isVisible() and ed.cursorPosition() == 0 and view.currentIndex() == m.index(0, 1)
    QTest.keyClick(ed, Qt.Key_Down)
    assert view.currentIndex() == m.index(1, 1)


def test_arrows_reach_the_column_titles(app, close_later):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    w = _window(app, "column", example=False)
    close_later(w)
    t = w.project.tables[0]
    w.show_sheet(t)
    w.show()
    view = w._widget_for(t)
    view.setFocus()
    m = view.model()
    view.setCurrentIndex(m.index(0, 1))
    QTest.keyClick(view, Qt.Key_Up)                       # row 1 → title of data set B
    assert view.head == ("title", 1)
    QTest.keyClick(view, Qt.Key_Up)                       # nothing above the titles
    assert view.head == ("title", 1)
    QTest.keyClick(view, Qt.Key_Left)
    assert view.head == ("title", 0)
    _type(view, "WT")                           # typing replaces the title
    QTest.keyClick(_editor(view), Qt.Key_Right)           # → saves and moves to the next title
    assert t.titles[0] == "WT" and view.head == ("title", 1)
    _type(view, "KO")
    QTest.keyClick(_editor(view), Qt.Key_Return)          # Return saves and goes down to row 1
    assert t.titles[1] == "KO" and view.head is None and view.currentIndex() == m.index(0, 1)
    QTest.keyClick(view, Qt.Key_Up)
    QTest.keyClick(view, Qt.Key_F2)                       # F2 edits; Escape cancels
    ed = _editor(view)
    ed.setText("nope")
    QTest.keyClick(ed, Qt.Key_Escape)
    assert t.titles[1] == "KO" and view.head == ("title", 1)
    QTest.keyClick(view, Qt.Key_Backspace)                # clears the title (undoable)
    assert t.titles[1] == ""
    w.project.undo.undo()
    assert t.titles[1] == "KO"
    QTest.keyClick(view, Qt.Key_Down)
    assert view.head is None and view.currentIndex() == m.index(0, 1)
    # ↑ while typing in row 1 saves the value and goes up into the title
    _type(view, "3")
    QTest.keyClick(_editor(view), Qt.Key_Up)
    assert t.get(0, 1) == 3 and view.head == ("title", 1)


def test_arrows_reach_sub_column_titles(app, close_later):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    w = _window(app, "nested", example=False, replicates=3)
    close_later(w)
    t = w.project.tables[0]
    w.show_sheet(t)
    w.show()
    view = w._widget_for(t)
    view.setFocus()
    m = view.model()
    assert view.subs_editable()
    c = m.col_of(t.flat(0, 1))
    view.setCurrentIndex(m.index(0, c))
    QTest.keyClick(view, Qt.Key_Up)                       # row 1 → this sub-column's title
    assert view.head == ("sub", c)
    _type(view, "m2")
    QTest.keyClick(_editor(view), Qt.Key_Up)              # saves, then up to the data set title
    assert t.sub_titles[0][1] == "m2" and view.head == ("title", 0)
    QTest.keyClick(view, Qt.Key_Down)                     # back down to the same sub-column
    assert view.head == ("sub", c)
    QTest.keyClick(view, Qt.Key_Down)
    assert view.head is None and view.currentIndex() == m.index(0, c)


def test_resizing_a_sub_column_repaints_the_whole_header(app, close_later, monkeypatch):
    # A data set's name and title span its sub-columns; Qt alone repaints only from the
    # resized section rightwards, leaving stale text over the sub-columns to the left.
    from asterism.app import table_view
    calls = []
    monkeypatch.setattr(table_view.TableHeader, "_span_resized", lambda self, *a: calls.append(a))
    w = _window(app, "nested", replicates=3)
    close_later(w)
    t = w.project.tables[0]
    hdr = w._widget_for(t).horizontalHeader()
    hdr.resizeSection(2, 200)
    assert calls
