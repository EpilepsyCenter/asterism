"""Offscreen Qt for app tests; settings go to a temp folder, never the user's."""

import os
import tempfile

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["ASTERISM_SETTINGS_DIR"] = tempfile.mkdtemp(prefix="asterism-test-settings-")

from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def win(app):
    from asterism.analysis import engine
    from asterism.app.main_window import MainWindow
    from asterism.doc.sample import sample_project
    w = MainWindow(sample_project(engine))
    yield w
    w.project.mark_saved()     # never block on a save prompt
    w.close()
