"""Native desktop window for ASTERISM (copied idiom from GliaAnalysis, SPEC §12).

Serves the Dash app with waitress on a background thread and shows it in a native OS
window via pywebview. Launch with:  python -m asterism_dash.desktop
Requires the optional desktop deps:  pip install -r requirements-desktop.txt
"""

from __future__ import annotations

import logging
import socket
import sys
import threading
import time

HOST = "127.0.0.1"
PREFERRED_PORT = 8060  # distinct from the browser launcher (8050)
TITLE = "ASTERISM"
WIN_WIDTH = 1440
WIN_HEIGHT = 900
MIN_SIZE = (1000, 640)
SERVER_THREADS = 8


def _pick_port(preferred: int) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((HOST, preferred))
            return preferred
        except OSError:
            pass
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, 0))
        return s.getsockname()[1]


def _run_server(port: int) -> None:
    """Serve the Dash WSGI app. Prefer waitress (production WSGI); if it isn't
    installed, fall back to Flask/werkzeug's threaded dev server so the native
    launcher still works with only the base requirements installed."""
    from asterism_dash.main import app
    try:
        from waitress import serve
    except ImportError:
        print("[ASTERISM] waitress not installed — using the built-in server. "
              "For the production server: pip install -r requirements-desktop.txt",
              file=sys.stderr)
        app.server.run(host=HOST, port=port, debug=False, use_reloader=False,
                       threaded=True)
        return
    logging.getLogger("waitress").setLevel(logging.ERROR)
    serve(app.server, host=HOST, port=port, threads=SERVER_THREADS)


def _wait_until_up(host: str, port: int, timeout: float = 30.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            if s.connect_ex((host, port)) == 0:
                return True
        time.sleep(0.15)
    return False


def main() -> None:
    import webview

    port = _pick_port(PREFERRED_PORT)
    threading.Thread(target=_run_server, args=(port,), daemon=True,
                     name="asterism-server").start()
    if not _wait_until_up(HOST, port):
        raise RuntimeError(f"ASTERISM server did not come up on {HOST}:{port} in 30s.")
    webview.create_window(TITLE, f"http://{HOST}:{port}",
                          width=WIN_WIDTH, height=WIN_HEIGHT, min_size=MIN_SIZE)
    webview.start()


if __name__ == "__main__":
    main()
