"""The "What's new" window in the app: the startup paths against real settings files
(each test its own folder), the dialog, its links into the help and the Help menu item."""

from __future__ import annotations

import pytest


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("ASTERISM_SETTINGS_DIR", str(tmp_path))
    from asterism.app import documents
    return documents


def _start(documents):
    from asterism.app.dialogs import whats_new
    return whats_new.startup_entries(documents.own_keys())


def test_fresh_install_records_the_version_and_shows_nothing(app, settings):
    from asterism import __version__
    assert settings.own_keys() == []
    news, before = _start(settings)
    assert news == [] and before is None
    assert settings.value("lastSeenVersion") == __version__
    assert _start(settings) == ([], __version__)          # and next time, still nothing


def test_update_from_a_version_before_this_window_shows_the_current_notes(app, settings, monkeypatch):
    from asterism.app.dialogs import whats_new
    monkeypatch.setattr(whats_new, "__version__", "0.3.0")
    settings.set_value("recentFiles", ["/tmp/a.asterism"])     # used before, no version stored
    news, before = _start(settings)
    assert [e.version for e in news] == ["0.3.0"] and before is None
    assert settings.value("lastSeenVersion") == "0.3.0"
    assert _start(settings)[0] == []                         # once per version


def test_older_stored_version_shows_every_version_since(app, settings, monkeypatch):
    from asterism.app.dialogs import whats_new
    from asterism.help import changelog as C
    log = C.parse("## 0.4.0\n\n- **D.**\n\n## 0.3.0\n\n- **C.**\n\n## 0.2.0\n\n- **B.**\n")
    monkeypatch.setattr(whats_new.C, "load", lambda: log)
    monkeypatch.setattr(whats_new, "__version__", "0.4.0")
    settings.set_value("lastSeenVersion", "0.2.0")
    news, before = _start(settings)
    assert [e.version for e in news] == ["0.4.0", "0.3.0"] and before == "0.2.0"
    dlg = whats_new.WhatsNewDialog(news, since=before)
    assert dlg.head.text() == "What's new since ASTERISM 0.2.0"
    text = dlg.view.toPlainText()
    assert text.index("0.4.0") < text.index("D.") < text.index("0.3.0") < text.index("C.")
    assert "B." not in text
    dlg.close()


def test_dialog_links_open_the_help_at_the_section(app, settings):
    from PySide6.QtCore import QUrl
    from asterism.app import help_window
    from asterism.app.dialogs import whats_new
    from asterism.help import changelog as C
    dlg = whats_new.WhatsNewDialog(C.load()[:1])
    assert dlg.head.text().startswith("What's new in ASTERISM ")
    assert "Read more" in dlg.view.toPlainText()
    dlg._link(QUrl("graphs.md#selecting-and-moving"))
    w = help_window.window()
    assert w.slug == "graphs" and w.history[-1] == ("graphs", "selecting-and-moving")
    dlg.help_btn.click()
    assert w.history[-1] == ("start", "")
    w.close()
    dlg.close()


def test_escape_closes_the_window(app, settings):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from asterism.app.dialogs import whats_new
    from asterism.help import changelog as C
    dlg = whats_new.show(C.load()[:1])
    assert dlg.isVisible()
    QTest.keyClick(dlg, Qt.Key_Escape)
    assert not dlg.isVisible()


def test_help_menu_opens_whats_new(win):
    from PySide6.QtWidgets import QApplication
    from asterism.app.dialogs.whats_new import WhatsNewDialog
    help_menu = next(a.menu() for a in win.menuBar().actions() if a.text().replace("&", "") == "Help")
    assert win.a_whats_new in help_menu.actions()
    win.a_whats_new.trigger()
    dlgs = [w for w in QApplication.topLevelWidgets() if isinstance(w, WhatsNewDialog) and w.isVisible()]
    assert len(dlgs) == 1 and dlgs[0].entries
    dlgs[0].close()
