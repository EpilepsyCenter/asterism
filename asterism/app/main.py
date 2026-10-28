"""App entry point:  python -m asterism [FILE.asterism …] [--shots DIR] [--selftest]"""

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


def _server_name() -> str:
    if os.environ.get("ASTERISM_SERVER_NAME"):          # tests
        return os.environ["ASTERISM_SERVER_NAME"]
    import getpass
    try:
        user = getpass.getuser()
    except Exception:
        user = "user"
    return f"asterism-{''.join(ch for ch in user if ch.isalnum()) or 'user'}"


import time


def hand_over(files: list[str]) -> bool:
    """If ASTERISM is already running, give it these files (or ask it to come forward) and
    return True; this process then quits. Windows and Linux start a new process for every
    double-clicked file; this keeps one app with one window per project."""
    import json
    from PySide6.QtNetwork import QLocalSocket
    sock = QLocalSocket()
    sock.connectToServer(_server_name())
    if not sock.waitForConnected(400):
        return False
    sock.write(json.dumps([os.path.abspath(f) for f in files]).encode("utf-8") + b"\n")
    sock.flush()
    sock.waitForBytesWritten(2000)
    # wait for the running ASTERISM to confirm, so nothing is lost when this process exits
    ok = False
    end = time.time() + 5
    reply = bytearray()
    while time.time() < end and b"\n" not in reply:
        if sock.bytesAvailable() or sock.waitForReadyRead(250):
            reply.extend(bytes(sock.readAll()))
        if sock.state() == QLocalSocket.UnconnectedState:
            break
    ok = reply.startswith(b"ok")
    sock.disconnectFromServer()
    return ok


def listen(app) -> None:
    """Accept files handed over by later launches."""
    import json
    from PySide6.QtNetwork import QLocalServer
    QLocalServer.removeServer(_server_name())          # a stale socket from a crash
    server = QLocalServer(app)
    if not server.listen(_server_name()):
        return
    app._server = server

    def accept():
        conn = server.nextPendingConnection()
        if conn is None:
            return
        buf = bytearray()
        handled = [False]

        def read(final: bool = False):
            if handled[0]:
                return
            buf.extend(bytes(conn.readAll()))
            if not buf.endswith(b"\n") and not (final and buf):
                return
            handled[0] = True
            try:
                files = json.loads(buf.decode("utf-8"))
            except ValueError:
                files = []
            if conn.state() == conn.LocalSocketState.ConnectedState:
                conn.write(b"ok\n")                      # received: the new launch can quit
                conn.flush()
            from .main_window import new_window, open_path, windows
            ws = windows()
            for f in files:
                if os.path.exists(f) and not os.path.isdir(f):
                    open_path(f, ws[-1] if ws else None)
            ws = windows() or [new_window()]
            w = ws[-1]
            w.show()
            w.raise_()
            w.activateWindow()
            conn.disconnectFromServer()
        conn.readyRead.connect(read)
        conn.disconnected.connect(lambda: read(final=True))
        if conn.bytesAvailable():                    # Windows: the data can arrive before we listen
            read()
    server.newConnection.connect(accept)


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
    from PySide6.QtGui import QIcon
    from .logo import ASSETS
    app.setWindowIcon(QIcon(os.path.join(ASSETS, "icon.svg")))     # Dock and window icon

    if "--selftest" in argv:
        from .selftest import run
        return run(app)

    if "--shots" in argv:
        from .shots import take_shots
        return take_shots(app, argv[argv.index("--shots") + 1])

    from .dialogs.start import show_at_startup
    from .main_window import new_window, offer_recovery, open_path, run_start, windows
    files = [a for a in argv[1:] if not a.startswith("-")]
    if not os.environ.get("ASTERISM_MULTI"):          # one running ASTERISM per user
        if hand_over(files):
            return 0
        listen(app)
    restored = offer_recovery()                  # unsaved work from a session that didn't end normally
    if restored and not files:
        return app.exec()
    if files:
        first = new_window()
        for path in files:
            open_path(path, first)
        if not windows():          # every file failed and the blank window was replaced
            new_window()
    elif show_at_startup():
        run_start(None)            # the Start window: new, empty, open, recent, sample
    else:
        new_window()               # an empty project (one Column table)
    if not windows():
        new_window()
    from . import prefs
    if prefs.get("updates.auto") and not os.environ.get("ASTERISM_NO_UPDATE_CHECK"):
        from PySide6.QtCore import QTimer
        from . import updates
        QTimer.singleShot(4000, lambda: updates.check(windows()[-1] if windows() else None, silent=True))
    return app.exec()
