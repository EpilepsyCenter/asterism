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
    from PySide6.QtWidgets import QToolButton
    win.resize(1400, 900)
    win.show()
    for width in (200, 251, 317, 360):
        sizes = win.split.sizes()
        win.split.setSizes([sizes[0], sizes[1] + sizes[2] - width, width])
        app.processEvents()
        assert abs(win.tools.width() - width) <= 6, (width, win.tools.width())
        inner = win.tools.findChild(QToolButton, "WideTool").parentWidget()
        tools = [b for b in inner.findChildren(QToolButton) if b.isVisible()]
        left = min(b.geometry().left() for b in tools)
        right = inner.width() - max(b.geometry().right() + 1 for b in tools)
        assert abs(left - right) <= 1, (width, left, right)
