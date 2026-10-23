"""Desktop app: live linking, undo, dialogs, export fidelity, project files (offscreen)."""

from __future__ import annotations

import pytest

from asterism.core.qa import check_svg


def _ttest(w, **params):
    from asterism.doc.model import Analysis
    t = w.project.tables[0]
    p = {"design": "unpaired", "distribution": "normal", "test": "student", "bracket": True, **params}
    return w.project.add_analysis(Analysis("ttest", t, [0, 1], p))


def test_edit_cell_updates_results_and_graph_then_undo(win):
    t, g = win.project.tables[0], win.project.graphs[0]
    a = _ttest(win)
    win.show_sheet(g)
    gs = win._widget_for(g)
    p_before = a.result.p
    assert any(it.el.id.startswith("bracket") for it in gs.items)

    model = win._widget_for(t).model()
    model.setData(model.index(10, 1), "300")          # outlier into SV2A
    assert a.result.p != p_before                     # analysis recomputed
    assert gs.auto_range.vmax >= 300                  # graph rescaled

    win.a_undo.trigger()
    assert t.get(10, 1) is None
    assert a.result.p == pytest.approx(p_before)


def test_mann_whitney_matches_core_exact(win):
    a = _ttest(win, distribution="nonparametric", test="mw")
    rows = {lab: v for lab, v, _ in a.result.pages[0].rows}
    assert rows["P value method"] == ["Exact"]
    assert rows["U"] == ["0"]


def test_format_graph_dialog_applies_and_undoes(win):
    from asterism.app.dialogs.format_graph import FormatGraphDialog
    g = win.project.graphs[0]
    dlg = FormatGraphDialog(g, win.project, column=0)
    dlg.sym_size.setCurrentIndex(dlg.sym_size.findData(6))
    dlg.sec_bars.check.setChecked(True)
    dlg.apply()
    assert g.spec.style(0).symbol_size == 6 and g.spec.style(0).bars
    assert g.spec.style(1).symbol_size == 3            # other data set untouched
    win.project.undo.undo()
    assert g.spec.style(0).symbol_size == 3


def test_format_axes_manual_range(win):
    from asterism.app.dialogs.format_graph import FormatGraphDialog
    g = win.project.graphs[0]
    win.show_sheet(g)
    gs = win._widget_for(g)
    dlg = FormatGraphDialog(g, win.project, "y", None, gs.auto_range)
    assert dlg.current_section() == "y"
    dlg.y_auto.setChecked(False)
    dlg.y_max.setText("120")
    dlg.y_step.setText("40")
    dlg.apply()
    assert (gs.auto_range.vmax, gs.auto_range.interval) == (120, 40)


def test_inline_title_edit(win):
    g = win.project.graphs[0]
    win.show_sheet(g)
    gs = win._widget_for(g)
    item = next(it for it in gs.items if it.el.id == "y-title")
    gs._start_edit(item)
    ed, _ = gs._editing
    ed.setPlainText("Seizure score")
    ed._finish(True)
    assert g.spec.y.title == "Seizure score"


def test_svg_export_passes_fidelity_qa(win, tmp_path):
    from asterism.app.graph.export import export_pdf, svg_bytes
    from asterism.app.graph.layout import build, content_bounds
    _ttest(win)
    g = win.project.graphs[0]
    els, _ = build(g)
    b = content_bounds(els)
    mm = 25.4 / 72
    rep = check_svg(svg_bytes(g), expected_w_mm=b.width() * mm, expected_h_mm=b.height() * mm,
                    expected_gids=["data-A", "data-B", "y-axis", "x-axis", "bracket-A-B", "y-title",
                                   "graph-title"])
    assert rep.ok, rep.summary()

    pdf = tmp_path / "g.pdf"
    export_pdf(g, str(pdf))
    pypdf = pytest.importorskip("pypdf")
    page = pypdf.PdfReader(str(pdf)).pages[0]
    fonts = [f.get_object() for f in page["/Resources"]["/Font"].values()]
    assert fonts and all(f["/Subtype"] != "/Type3" for f in fonts)   # TrueType, not Type 3
    assert "EGFP" in page.extract_text()                                # live text


# --- project files and window state (M1) ---------------------------------------------

def test_save_quit_reopen_is_identical(win, tmp_path):
    from asterism.app.main_window import open_path, windows
    from asterism.doc.spec import spec_to_dict
    a = _ttest(win, test="welch")
    t, g = win.project.tables[0], win.project.graphs[0]
    win._widget_for(t).model().setData(win._widget_for(t).model().index(2, 2), "12.5")
    win.project.rename(g, "Figure 1")
    assert win.isWindowModified()

    path = str(tmp_path / "seizures.asterism")
    assert win.save_to(path)
    assert not win.isWindowModified() and win.windowTitle() == "seizures[*]"

    w2 = open_path(path)
    try:
        assert w2 is not None and w2 is not win and w2 in windows()
        p2 = w2.project
        assert [s.name for s in p2.sheets()] == [s.name for s in win.project.sheets()]
        assert p2.tables[0].cols == t.cols
        assert spec_to_dict(p2.graphs[0].spec) == spec_to_dict(g.spec)
        assert p2.analyses[0].result.p == pytest.approx(a.result.p)
        assert open_path(path) is w2                  # already open: same window
    finally:
        w2.close()


def test_open_replaces_pristine_untitled_window(app, tmp_path):
    from asterism.analysis import engine
    from asterism.app.main_window import new_window, open_path, windows
    from asterism.doc import fileformat
    from asterism.doc.sample import sample_project
    path = tmp_path / "p.asterism"
    fileformat.save(sample_project(engine), path)
    blank = new_window()
    w = open_path(str(path), blank)
    try:
        assert blank not in windows() and w in windows()
    finally:
        w.close()


def test_undo_actions_follow_the_stack(win):
    t = win.project.tables[0]
    assert not win.a_undo.isEnabled()
    model = win._widget_for(t).model()
    model.setData(model.index(0, 0), "1")
    assert win.a_undo.isEnabled() and win.a_undo.text() == "Undo Edit Cell"
    win.a_undo.trigger()
    assert win.a_redo.text() == "Redo Edit Cell"


def test_delete_sheet_is_undoable_in_the_window(win, monkeypatch):
    t = win.project.tables[0]
    win.show_sheet(t)
    win.project.delete(t)
    assert win.project.tables == [] and win.current is not t
    win.a_undo.trigger()
    assert win.project.tables == [t]
    win.show_sheet(t)                                  # a fresh view for the restored sheet
    assert win._widget_for(t).t is t


def test_revert_restores_saved_version(win, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from asterism.app.main_window import windows
    path = str(tmp_path / "r.asterism")
    win.save_to(path)
    win.project.rename(win.project.tables[0], "Changed")
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
    monkeypatch.setattr(QMessageBox, "clickedButton",
                        lambda self: next(b for b in self.buttons() if b.text() == "Revert"))
    win.revert()
    fresh = windows()[-1]
    try:
        assert fresh is not win and fresh.project.tables[0].name == "Cumulative SE seizure grade"
    finally:
        fresh.close()


def test_closing_unsaved_window_asks_first(app, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from asterism.app.main_window import new_window, windows
    w = new_window()
    w.project.add_table()
    asked = []

    def answer(choice):
        def exec_(self):
            asked.append(self.text())
            return choice
        return exec_

    monkeypatch.setattr(QMessageBox, "exec", answer(QMessageBox.Cancel))
    assert not w.close() and w in windows()           # Cancel keeps it open
    monkeypatch.setattr(QMessageBox, "exec", answer(QMessageBox.Discard))
    assert w.close() and w not in windows()            # Don't Save closes
    assert asked and "Untitled" in asked[0]


def test_launch_argument_open_events_are_ignored(app, tmp_path, monkeypatch):
    """macOS re-sends command-line arguments as open events; they must not reopen or error."""
    from PySide6.QtGui import QFileOpenEvent
    from asterism.app import main as appmain
    from asterism.app import main_window
    opened = []
    monkeypatch.setattr(main_window, "open_path", lambda p, o=None: opened.append(p))
    handler = appmain.App.event
    fake = type("FakeApp", (), {"launch_args": {str(tmp_path / "launched.asterism")}})()
    handler(fake, QFileOpenEvent(str(tmp_path / "launched.asterism")))   # from argv
    handler(fake, QFileOpenEvent(str(tmp_path)))                          # a folder
    handler(fake, QFileOpenEvent(str(tmp_path / "other.asterism")))      # Finder double-click
    assert opened == [str(tmp_path / "other.asterism")]


def test_format_graph_box_mode_controls_whiskers(win):
    from asterism.app.dialogs.format_graph import FormatGraphDialog
    g = win.project.graphs[0]
    dlg = FormatGraphDialog(g, win.project, column=0)
    dlg.appearance.setCurrentIndex(dlg.appearance.findData("box"))
    assert dlg.sec_err.check.text() == "Whiskers" and not dlg.line_at.isEnabled()
    assert not dlg.show_points.isChecked()          # a new box plot starts without points
    assert not dlg.whisk_box.isHidden()
    dlg.whiskers.setCurrentIndex(dlg.whiskers.findData("tukey"))
    dlg.sec_err.check.setChecked(False)
    dlg.apply()
    st = g.spec.style(0)
    assert (st.appearance, st.whiskers, st.errors) == ("box", "tukey", False)
    dlg.appearance.setCurrentIndex(dlg.appearance.findData("scatter"))
    assert dlg.sec_err.check.text() == "Error bars" and dlg.whisk_box.isHidden()


def test_style_page_hides_points_and_greys_out_symbols(win):
    from asterism.app.dialogs.format_graph import FormatGraphDialog
    g = win.project.graphs[0]
    dlg = FormatGraphDialog(g, win.project)           # all data sets
    assert dlg.symbols_box.isEnabled()
    dlg.show_points.setChecked(False)
    assert not dlg.symbols_box.isEnabled()
    dlg.apply()
    assert all(not g.spec.style(c).show_points for c in (0, 1))
