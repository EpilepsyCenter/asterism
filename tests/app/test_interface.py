"""ASTERISM's own interface (SPEC §2.1, §12, M1b)."""

from __future__ import annotations

import pathlib
import re

import pytest


def test_sidebars_resize_hide_and_are_remembered(app):
    from asterism.analysis import engine
    from asterism.app.main_window import MainWindow
    from asterism.doc.sample import sample_project
    w = MainWindow(sample_project(engine))
    w.resize(1400, 900)
    w.show()
    app.processEvents()
    sizes = w.split.sizes()
    w.split.setSizes([360, sizes[1] - 110 - 40, 270])
    w._save_layout()
    left, _, right = w.split.sizes()
    w.a_toggle_tools.trigger()                       # hide the tool panel
    assert not w.tools.isVisible()
    w.project.mark_saved()
    w.close()

    w2 = MainWindow(sample_project(engine))
    w2.resize(1400, 900)
    w2.show()
    app.processEvents()
    assert abs(w2.split.sizes()[0] - left) <= 2      # width remembered
    assert not w2.tools.isVisible() and not w2.a_toggle_tools.isChecked()
    w2.a_toggle_tools.trigger()
    assert w2.tools.isVisible()
    assert w2.sidebar.minimumWidth() == 180 and w2.sidebar.maximumWidth() == 480
    w2.project.mark_saved()
    w2.close()


def test_linked_sheets_nest_under_their_table(win):
    from asterism.doc.model import Analysis
    win.project.add_analysis(Analysis("descriptive", win.project.tables[0], [0, 1], {}))
    tree = win.sidebar.tree
    table_item = next(it for it in win.sidebar._items()
                      if it.data(0, 0x0100) is win.project.tables[0])
    kids = {table_item.child(i).data(0, 0x0100).kind for i in range(table_item.childCount())}
    assert kids == {"analysis", "graph"}
    assert tree.topLevelItemCount() >= 3                # Data / Notes / Layouts sections


def test_tools_follow_the_current_sheet(win):
    t, g = win.project.tables[0], win.project.graphs[0]
    win.show_sheet(t)
    assert win.a_paste.isEnabled() and not win.a_fmt_graph.isEnabled()
    assert not win.font_family.isEnabled()
    win.show_sheet(g)
    assert win.a_fmt_graph.isEnabled() and not win.a_paste.isEnabled()
    assert win.font_family.isEnabled()
    assert not win.a_print.isEnabled() and "not available yet" in win.a_print.toolTip()


def test_rename_from_the_top_bar_title(win):
    t = win.project.tables[0]
    win.show_sheet(t)
    win.top.title.setText("Seizure grades")
    win.top.title.editingFinished.emit()
    assert t.name == "Seizure grades"
    win.a_undo.trigger()
    assert t.name == "Cumulative SE seizure grade"


def test_dialogs_use_a_section_sidebar_not_tabs(win):
    from PySide6.QtWidgets import QTabBar
    from asterism.app.dialogs.analyze import AnalyzeDialog, TTestParamsDialog
    from asterism.app.dialogs.format_graph import FormatGraphDialog
    g = win.project.graphs[0]
    for dlg in (AnalyzeDialog(win.project, win.project.tables[0], win), TTestParamsDialog(None, win),
                FormatGraphDialog(g, win.project, parent=win)):
        assert not dlg.findChildren(QTabBar)
        assert dlg.sections.count() > 2


def test_format_graph_opens_at_the_section_for_the_clicked_element(win):
    from asterism.app.dialogs.format_graph import FormatGraphDialog
    g = win.project.graphs[0]
    for asked, expected in (("appearance", "style"), ("errors", "style"), ("x", "x"),
                            ("annotations", "significance"), ("frame", "frame")):
        dlg = FormatGraphDialog(g, win.project, asked)
        assert dlg.current_section() == expected
        assert dlg.picker.isVisibleTo(dlg) == (expected == "style")


COINED = re.compile(r"[\"'][^\"'\n]*\b(Family|Magic|Welcome dialog|Project Companion|Navigator)\b")


def test_no_prism_coined_terms_in_interface_text():
    root = pathlib.Path(__file__).resolve().parents[2] / "asterism"
    hits = []
    for p in root.rglob("*.py"):
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if COINED.search(line) and not line.lstrip().startswith("#"):
                hits.append(f"{p.relative_to(root)}:{n}: {line.strip()}")
    assert not hits, "\n".join(hits)


def test_tool_panel_margins_are_equal_at_any_width(win, app):
    from PySide6.QtWidgets import QAbstractButton
    win.resize(1400, 900)
    win.show()
    win.show_sheet(win.project.graphs[0])         # rows, tiles and icon rows
    for width in (200, 251, 317, 360):
        sizes = win.split.sizes()
        win.split.setSizes([sizes[0], sizes[1] + sizes[2] - width, width])
        app.processEvents()
        assert abs(win.tools.width() - width) <= 6, (width, win.tools.width())
        page = win.tools.current_page()
        tools = [b for b in page.findChildren(QAbstractButton) if b.isVisible()]
        left = min(b.geometry().left() for b in tools)
        right = page.width() - max(b.geometry().right() + 1 for b in tools)
        assert abs(left - right) <= 1, (width, left, right)


def test_tool_panel_follows_the_sheet(win):
    from asterism.app.toolbar import ActionRow
    from asterism.doc.model import Analysis
    p = win.project
    t, g = p.tables[0], p.graphs[0]

    def rows():
        return [r.action for r in win.tools.current_page().findChildren(ActionRow)]

    win.show_sheet(t)
    assert win.tools.current_key == "table:column"
    assert win.a_ttest in rows() and win.a_anova in rows() and win.a_insert_row in rows()
    assert win.a_linreg not in rows() and win.a_surv not in rows()      # not for column tables
    assert all(a.isEnabled() for a in rows())                          # nothing greyed out
    win.show_sheet(g)
    assert win.tools.current_key == "graph" and win.a_axes in rows() and win.a_ttest not in rows()
    a = Analysis("descriptive", t, [0, 1], {})
    p.add_analysis(a)
    win.show_sheet(a)
    assert win.tools.current_key == "analysis" and win.a_help_methods in rows()
    xy = p.add_table(table_type="xy", example=True)
    win.show_sheet(xy)
    assert win.tools.current_key == "table:xy" and win.a_linreg in rows() and win.a_ttest not in rows()
    win.show_overview()
    assert win.tools.current_key == "none"


def test_top_bar_labels_and_file_group(win):
    from PySide6.QtCore import Qt
    bar, files = win.top.tools, win.top.file_tools
    assert files.toolButtonStyle() == Qt.ToolButtonIconOnly
    assert {win.a_open, win.a_save, win.a_undo, win.a_redo} <= set(files.actions())
    assert bar.toolButtonStyle() == Qt.ToolButtonTextUnderIcon
    labels = [a.iconText() for a in bar.actions() if not a.isSeparator()]
    assert labels == ["Table", "Graph", "Figure", "Notes", "Analyze", "Export"]
    assert win.a_new_table.text() == "New Data Table…"                  # menus keep the full name
    on_bar = set(files.actions()) | set(bar.actions())
    assert win.a_delete not in on_bar and win.a_cut not in on_bar      # menus, sidebar and panel only


def test_t_test_from_the_panel(win, monkeypatch):
    from asterism.app.dialogs import params
    monkeypatch.setattr(params, "settings_dialog", lambda *a, **k: None)
    t = win.project.tables[0]
    win.show_sheet(t)
    win.a_ttest.trigger()
    assert win.current.analysis_type == "ttest" and win.current.columns == [0, 1]
