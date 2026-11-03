"""Start window (new, empty, open, recent, sample) and remembered window size/position."""

from __future__ import annotations

import pytest


@pytest.fixture
def cleanup(app):
    from asterism.app import main_window
    yield
    for w in main_window.windows():
        w.project.mark_saved()
        w.close()


def _saved_file(tmp_path, name="Study.asterism"):
    from asterism.analysis import engine
    from asterism.doc import fileformat
    from asterism.doc.sample import sample_project
    p = tmp_path / name
    fileformat.save(sample_project(engine), str(p))
    return str(p)


def test_start_window_lists_recent_projects(app, tmp_path):
    from PySide6.QtCore import Qt
    from asterism.app import documents
    from asterism.app.dialogs.start import StartDialog
    documents.clear_recent()
    good = _saved_file(tmp_path)
    documents.add_recent(good)
    documents.add_recent(str(tmp_path / "gone.asterism"))
    d = StartDialog()
    assert d.recent.count() == 2
    missing, present = d.recent.item(0), d.recent.item(1)
    assert not (missing.flags() & Qt.ItemIsEnabled)
    d.recent.setCurrentItem(present)
    assert d.open_btn.isEnabled()
    d.open_btn.click()
    assert d.result_choice() == ("open", good)


@pytest.mark.parametrize("key,choice", [("new", ("new",)), ("empty", ("empty",)), ("sample", ("sample",))])
def test_start_window_buttons(app, key, choice):
    from asterism.app.dialogs.start import StartDialog
    d = StartDialog()
    d.buttons[key].click()
    assert d.result_choice() == choice


def test_closing_the_start_window_means_an_empty_project(app):
    from asterism.app.dialogs.start import StartDialog
    d = StartDialog()
    d.reject()
    assert d.result_choice() == ("empty",)


def test_show_at_startup_is_remembered(app):
    from asterism.app.dialogs.start import StartDialog, show_at_startup
    d = StartDialog()
    d.c_show.setChecked(False)
    assert not show_at_startup()
    d.c_show.setChecked(True)
    assert show_at_startup()


def _pick(monkeypatch, *choices):
    from asterism.app.dialogs.start import StartDialog
    seq = list(choices)

    def fake_exec(self):
        self._choice = seq.pop(0)
        return 1
    monkeypatch.setattr(StartDialog, "exec", fake_exec)


def test_run_start_empty_and_new(app, cleanup, monkeypatch):
    from asterism.app.dialogs.new_table import NewTableDialog
    from asterism.app.main_window import run_start
    _pick(monkeypatch, ("empty",))
    w = run_start(None)
    assert [t.table_type for t in w.project.tables] == ["column"]
    _pick(monkeypatch, ("new",))
    monkeypatch.setattr(NewTableDialog, "exec", lambda self: (self.show_section("xy"), 1)[1])
    w2 = run_start(None)
    assert w2 is not w and [t.table_type for t in w2.project.tables] == ["xy"]


def test_run_start_opens_files_and_comes_back_after_a_failure(app, cleanup, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QMessageBox
    from asterism.app.main_window import run_start
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    good = _saved_file(tmp_path)
    _pick(monkeypatch, ("open", str(tmp_path / "nope.asterism")), ("open", good))
    w = run_start(None)
    assert w.path == good


def test_run_start_reuses_a_pristine_window(app, cleanup, monkeypatch):
    from asterism.app.main_window import new_window, run_start
    w = new_window()
    _pick(monkeypatch, ("empty",))
    assert run_start(w) is w


def test_window_size_and_position_are_remembered(app, cleanup):
    from PySide6.QtCore import QRect
    from asterism.app import documents
    from asterism.app.main_window import new_window
    w = new_window()
    w.setGeometry(QRect(4, 40, 792, 420))      # fits the 800×600 test screen and the minimum width
    w._save_geometry()
    assert documents.value("window/geometry") is not None
    w.project.mark_saved()
    w.close()
    w2 = new_window()                        # the next window opens where the last one was
    g = w2.geometry()
    assert (g.width(), g.height()) == (792, 420)
    assert abs(g.x() - 4) <= 2 and abs(g.y() - 40) <= 30
    w3 = new_window()                        # a second window cascades from the first …
    p2, p3 = w2.geometry().topLeft(), w3.geometry().topLeft()
    screen = app.primaryScreen().availableGeometry()
    assert p3 == p2 + type(p2)(28, 28) or (screen.contains(w3.geometry()) and p3 != p2)  # … or restarts on screen


def test_moving_the_window_saves_its_place(app, cleanup):
    from asterism.app import documents
    from asterism.app.main_window import new_window
    w = new_window()
    documents.set_value("window/geometry", None)
    w.move(w.x() + 15, w.y() + 10)
    w._geom_timer.timeout.emit()            # the debounce timer firing
    assert documents.value("window/geometry") is not None


def test_logo_assets_and_widgets(app):
    import os
    from PySide6.QtSvg import QSvgRenderer
    from asterism.app.logo import Logo, svg_path
    for dipper in (True, False):
        for dark in (True, False):
            path = svg_path(dipper, dark)
            assert os.path.exists(path) and QSvgRenderer(path).isValid()
            assert "<text" not in open(path).read()            # letters are outlines: no font needed
    big, small = Logo(88, dipper=True), Logo(24, dipper=False)
    assert big.height() == 88 and big.width() > 88
    assert small.height() == 24 and small.width() > 3 * 24
    assert not small.grab().isNull()


def test_app_icon(app):
    import os
    from PySide6.QtGui import QIcon
    from asterism.app.logo import ASSETS
    ico = QIcon(os.path.join(ASSETS, "icon.svg"))
    assert not ico.isNull() and not ico.pixmap(64, 64).isNull()
    assert os.path.exists(os.path.join(ASSETS, "asterism.icns"))


def test_start_window_preselects_the_latest_project_and_has_whats_new_and_help(app, tmp_path):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    from asterism import __version__
    from asterism.app import documents, help_window
    from asterism.app.dialogs.start import StartDialog
    from asterism.app.dialogs.whats_new import WhatsNewDialog
    documents.clear_recent()
    older, newer = _saved_file(tmp_path, "Older.asterism"), _saved_file(tmp_path, "Newer.asterism")
    documents.add_recent(older)
    documents.add_recent(newer)
    d = StartDialog()
    assert d.recent.currentItem().data(Qt.UserRole) == newer and d.open_btn.isEnabled()
    assert __version__ in d.version.text()
    d.whats_new_btn.click()
    wn = [w for w in QApplication.topLevelWidgets() if isinstance(w, WhatsNewDialog) and w.isVisible()]
    assert len(wn) == 1 and wn[0].parent() is d          # a child of the Start window: usable over it
    wn[0].close()
    d.help_btn.click()
    h = help_window.window()
    assert h.isVisible() and h.history[-1] == ("start", "the-start-window")
    h.close()


def test_help_opened_over_a_modal_window_can_be_used(app):
    """A modal dialog blocks every other window; help opened from it is modal too, on top."""
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtWidgets import QDialog
    from asterism.app import help_window
    seen = {}
    dlg = QDialog()

    def probe():
        seen["over"] = help_window.show_page("start").windowModality()
        help_window.window().close()
        dlg.reject()
    QTimer.singleShot(50, probe)
    dlg.exec()
    assert seen["over"] == Qt.ApplicationModal
    assert help_window.show_page("start").windowModality() == Qt.NonModal   # no dialog: an ordinary window
    help_window.window().close()


def test_open_follows_the_highlighted_project(app, tmp_path):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from asterism.app import documents
    from asterism.app.dialogs.start import StartDialog
    documents.clear_recent()
    a, b = _saved_file(tmp_path, "A.asterism"), _saved_file(tmp_path, "B.asterism")
    for p in (a, str(tmp_path / "gone.asterism"), b):
        documents.add_recent(p)                      # newest first: B, gone, A
    d = StartDialog()
    d.show()
    L = d.recent
    assert d.open_btn.isEnabled()                    # B, preselected
    r = L.visualItemRect(L.item(0))
    QTest.mouseClick(L.viewport(), Qt.LeftButton, Qt.ControlModifier, r.center())
    assert not L.selectedItems() and not d.open_btn.isEnabled()      # nothing highlighted
    QTest.mouseClick(L.viewport(), Qt.LeftButton, Qt.NoModifier, L.visualItemRect(L.item(2)).center())
    assert d.open_btn.isEnabled()
    d.open_btn.click()
    assert d.result_choice() == ("open", a)
    d.close()


def test_edited_hours_ago_is_singular_for_one(tmp_path):
    import os
    import time
    from asterism.app.dialogs.start import _when
    f = tmp_path / "x.asterism"
    f.write_text("")
    for hours, text in ((1, "edited 1 hour ago"), (3, "edited 3 hours ago")):
        t = time.time() - hours * 3600 - 60
        os.utime(f, (t, t))
        assert _when(str(f)) == text
