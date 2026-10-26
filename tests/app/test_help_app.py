"""The Help window: Help buttons open their section, history, links, search, the live
shortcuts page and the Help menu."""

from __future__ import annotations

from PySide6.QtCore import QUrl


def test_help_button_opens_its_section(app):
    from asterism.app.dialogs.common import HelpButton
    from asterism.app.help_window import window
    b = HelpButton("One-way ANOVA")
    b.click()
    w = window()
    assert w.isVisible() and w.slug == "analyses-groups"
    assert w.history[-1] == ("analyses-groups", "one-way-anova")
    w.close()


def test_history_links_and_search(app):
    from asterism.app.help_window import show_page
    w = show_page("start")
    w._link(QUrl("tables.md#new-table"))
    assert w.slug == "tables" and w.history[-1] == ("tables", "new-table")
    w.back()
    assert w.slug == "start"
    w.forward()
    assert w.slug == "tables"
    w.search.setText("autosave")
    assert w.left_stack.currentWidget() is w.results and w.results.count() > 0
    w._result_go(w.results.item(0))
    assert w.slug in {s for s, _ in __import__("asterism.help", fromlist=["PAGES"]).PAGES}
    w.search.setText("")
    assert w.left_stack.currentWidget() is w.tree
    w.close()


def test_shortcuts_page_from_menus_and_help_menu(win):
    from asterism.app.help_window import window
    win.show()
    win.a_help_shortcuts.trigger()
    w = window()
    text = w.view.toPlainText()
    assert w.slug == "shortcuts" and "Save" in text and "Settings" in text
    win.a_help.trigger()                 # opens the page for the sheet in front
    assert w.slug in ("start", "tables", "graphs", "analyses", "figures")
    w.close()
