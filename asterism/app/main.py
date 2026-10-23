"""App entry point:  python -m asterism [FILE.asterism …] [--shots DIR]"""

from __future__ import annotations

import os
import sys

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication


class App(QApplication):
    """Receives Finder "open document" events (double-click, drag onto the Dock icon).

    macOS also turns the process's command-line arguments into such events. Those
    files are opened from argv at startup, so their events are ignored, as are
    events for folders (e.g. a script's working directory argument).
    """

    def __init__(self, argv: list[str]):
        super().__init__(argv)
        self.launch_args = {os.path.abspath(a) for a in sys.argv[1:] + argv[1:]}

    def event(self, e):
        if e.type() == QEvent.FileOpen and e.file():
            path = os.path.abspath(e.file())
            if path not in self.launch_args and not os.path.isdir(path):
                from .main_window import open_path, windows
                ws = windows()
                open_path(path, ws[-1] if ws else None)
            return True
        return super().event(e)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    # Qt's macOS accessibility bridge logs a harmless warning when table rows grow.
    os.environ.setdefault("QT_LOGGING_RULES", "qt.accessibility.table=false")
    app = App(argv)
    app.setApplicationName("ASTERISM")
    app.setApplicationDisplayName("ASTERISM")
    app.setOrganizationName("ASTERISM")
    from . import theme
    theme.install(app)

    if "--shots" in argv:
        from .shots import take_shots
        return take_shots(app, argv[argv.index("--shots") + 1])

    from PySide6.QtCore import QTimer
    from .main_window import new_window, open_path, windows
    first = new_window()
    files = [a for a in argv[1:] if not a.startswith("-")]
    for path in files:
        open_path(path, first)
    if not windows():          # every file failed and the blank window was replaced
        new_window()
    if not files:              # start screen: pick the first table's type
        QTimer.singleShot(0, lambda: first in windows() and first.show_start_screen())
    return app.exec()
