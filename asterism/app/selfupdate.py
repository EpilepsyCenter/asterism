"""Install an update from inside ASTERISM (packaged apps only).

From the latest GitHub release: download this system's file, check it against the
release's SHA256SUMS.txt, ask to save open work, quit, and let the new version take over:

  macOS    ASTERISM-<v>-mac.zip → a small script waits for ASTERISM to quit, replaces the
           ASTERISM.app it was started from, and opens the new one.
  Windows  ASTERISM-<v>-windows-setup.exe runs over the installed copy (same installer
           ID, no questions, its progress window showing) and starts ASTERISM again.
  Linux    ASTERISM-<v>-linux-x86_64.AppImage replaces the AppImage file, which is started.

Files downloaded by the app itself (not a browser) aren't marked as coming from the
internet, so macOS and Windows don't ask again about the unsigned app after an update.
Running from source, there is nothing to replace: the release page opens instead.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile

from PySide6.QtCore import QEventLoop, QUrl
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

SUFFIX = {"darwin": "-mac.zip", "win32": "-windows-setup.exe", "linux": "-linux-x86_64.AppImage"}
DOWNLOAD_PREFIX = "https://github.com/EpilepsyCenter/asterism/releases/download/"


def frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def install_target() -> str | None:
    """What gets replaced: the .app (macOS), the install folder (Windows), the AppImage
    (Linux); None when running from source or from somewhere that can't be updated."""
    if not frozen():
        return None
    exe = os.path.abspath(sys.executable)
    if sys.platform == "darwin":
        app = os.path.dirname(os.path.dirname(os.path.dirname(exe)))       # …/ASTERISM.app
        if app.endswith(".app") and os.access(os.path.dirname(app), os.W_OK):
            return app
        return None
    if sys.platform == "win32":
        return os.path.dirname(exe)
    appimage = os.environ.get("APPIMAGE")
    if appimage and os.access(os.path.dirname(appimage), os.W_OK):
        return appimage
    return None


def can_install() -> bool:
    return sys.platform in SUFFIX and install_target() is not None


def pick_asset(release: dict) -> tuple[dict | None, dict | None]:
    """(this system's asset, the SHA256SUMS.txt asset) from a GitHub release."""
    suffix = SUFFIX.get(sys.platform if sys.platform != "linux2" else "linux")
    assets = release.get("assets") or []
    mine = next((a for a in assets if suffix and a.get("name", "").endswith(suffix)), None)
    sums = next((a for a in assets if a.get("name") == "SHA256SUMS.txt"), None)
    return mine, sums


def parse_sums(text: str) -> dict[str, str]:
    """'<sha256>  <file name>' lines → {file name: sha256}."""
    out = {}
    for line in text.splitlines():
        parts = line.strip().split()
        if len(parts) >= 2 and len(parts[0]) == 64:
            out[parts[-1].lstrip("*")] = parts[0].lower()
    return out


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Downloading (shown in the update window, dialogs/update.py)
# ---------------------------------------------------------------------------

def _download(manager: QNetworkAccessManager, url: str, path: str | None, progress=None) -> bytes | None:
    """Fetch `url` (GitHub release files only) to `path`, or return its bytes; None if it
    failed or was cancelled."""
    if not url.startswith(DOWNLOAD_PREFIX):
        return None
    req = QNetworkRequest(QUrl(url))
    req.setAttribute(QNetworkRequest.RedirectPolicyAttribute, QNetworkRequest.NoLessSafeRedirectPolicy)
    req.setRawHeader(b"User-Agent", b"ASTERISM-updater")
    reply = manager.get(req)
    loop = QEventLoop()
    out = open(path, "wb") if path else None
    data = bytearray()

    def chunk():
        b = bytes(reply.readAll())
        (out.write(b) if out else data.extend(b))

    def moved(done, total):
        if progress is not None:
            if total > 0:
                progress.setMaximum(int(total))
                progress.setValue(int(done))
            if progress.wasCanceled():
                reply.abort()
    reply.readyRead.connect(chunk)
    reply.downloadProgress.connect(moved)
    reply.finished.connect(loop.quit)
    loop.exec()
    chunk()
    if out:
        out.close()
    ok = reply.error() == QNetworkReply.NoError
    reply.deleteLater()
    if not ok:
        return None
    return b"" if out else bytes(data)


def _in_background(fn, *args):
    """Run fn(*args) in a thread while the Qt event loop keeps running (so the update
    window keeps animating); returns its result or raises its exception."""
    import threading
    from PySide6.QtCore import QTimer
    box: dict = {}

    def run():
        try:
            box["result"] = fn(*args)
        except BaseException as e:          # re-raised on the GUI thread below
            box["error"] = e
    t = threading.Thread(target=run, daemon=True)
    t.start()
    loop = QEventLoop()
    timer = QTimer(interval=50, timeout=lambda: None if t.is_alive() else loop.quit())
    timer.start()
    loop.exec()
    timer.stop()
    t.join()
    if "error" in box:
        raise box["error"]
    return box.get("result")


def download_and_verify(release: dict, parent=None, dlg=None) -> str | None:
    """Download this system's update and check its SHA-256. Returns the file's path, or
    None (with a message) if anything went wrong. `dlg`: the update window
    (dialogs/update.py) that shows the download and the check."""
    from PySide6.QtWidgets import QMessageBox
    asset, sums_asset = pick_asset(release)
    if asset is None or sums_asset is None:
        QMessageBox.warning(parent, "Update", "This release has no file for this system to install "
                                              "automatically. Download it from the release page instead.")
        return None
    if dlg is not None:
        dlg.downloading()
    manager = QNetworkAccessManager()
    sums = _download(manager, sums_asset["browser_download_url"], None)
    expected = parse_sums(sums.decode("utf-8", "replace")).get(asset["name"]) if sums is not None else None
    if not expected:
        QMessageBox.warning(parent, "Update", "The release's checksum list couldn't be read, so the "
                                              "update wasn't installed.")
        return None
    folder = tempfile.mkdtemp(prefix="asterism-update-")
    path = os.path.join(folder, asset["name"])
    if dlg is not None:
        dlg.setMaximum(int(asset.get("size") or 0))
        dlg.setValue(0)
    got = _download(manager, asset["browser_download_url"], path, dlg)
    cancelled = dlg is not None and dlg.wasCanceled()
    if got is None:
        _discard(path)
        if not cancelled:
            QMessageBox.warning(parent, "Update", "The download didn't finish. Try again later, or download "
                                                  "the update from the release page.")
        return None
    if dlg is not None:
        dlg.preparing()
    if _in_background(sha256, path) != expected:
        _discard(path)
        QMessageBox.warning(parent, "Update", "The downloaded file doesn't match the release's checksum, so "
                                              "it wasn't installed. Try again later.")
        return None
    return path


def _discard(path: str) -> None:
    """Remove a downloaded update and its temporary folder."""
    import shutil
    shutil.rmtree(os.path.dirname(path), ignore_errors=True)


# ---------------------------------------------------------------------------
# Handing over to the new version
# ---------------------------------------------------------------------------

def mac_script(pid: int, new_app: str, old_app: str, open_cmd: str = "open") -> str:
    """Shell script: wait for ASTERISM to quit, swap in the new app, open it.

    The new app is moved into place (instant on the same disk; a copy otherwise); the
    old one is kept until that worked and put back if it didn't."""
    q = lambda s: "'" + s.replace("'", "'\\''") + "'"
    old, new, backup = q(old_app), q(new_app), q(old_app + ".update-backup")
    return f"""#!/bin/bash
while kill -0 {pid} 2>/dev/null; do sleep 0.3; done
rm -rf {backup}
if mv {old} {backup}; then
  if mv {new} {old} 2>/dev/null || ditto {new} {old}; then
    rm -rf {backup}
  else
    rm -rf {old}; mv {backup} {old}
  fi
fi
xattr -dr com.apple.quarantine {old} 2>/dev/null
rm -rf {q(os.path.dirname(new_app))}
{open_cmd} {old}
"""


def unpack_mac(path: str) -> str | None:
    """macOS: unpack the downloaded .zip next to it; the new ASTERISM.app, or None."""
    unpacked = os.path.join(os.path.dirname(path), "new")
    if not os.path.isdir(unpacked):
        subprocess.run(["ditto", "-x", "-k", path, unpacked], check=True)
    new_app = os.path.join(unpacked, "ASTERISM.app")
    return new_app if os.path.isdir(new_app) else None


def prepare(path: str) -> list[str] | None:
    """Get the update ready to replace this copy; the command to run once ASTERISM has
    quit (None if it can't be installed this way)."""
    target = install_target()
    if target is None:
        return None
    if sys.platform == "darwin":
        new_app = unpack_mac(path)               # already unpacked by install(): reused
        if new_app is None:
            return None
        script = os.path.join(os.path.dirname(path), "install.sh")
        with open(script, "w", encoding="utf-8") as f:
            f.write(mac_script(os.getpid(), new_app, target))
        os.chmod(script, 0o755)
        return ["/bin/bash", script]
    if sys.platform == "win32":
        # /SILENT (not /VERYSILENT): no questions, but the installer shows its progress
        # window, so the user sees the update being installed. It restarts ASTERISM after.
        return [path, "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS", "/SP-"]
    # Linux AppImage: replace the file now (the running copy keeps its open file), start it later
    os.chmod(path, 0o755)
    staged = target + ".new"
    import shutil
    shutil.copy2(path, staged)
    os.replace(staged, target)
    return [target]


def launch_detached(cmd: list[str]) -> None:
    kwargs: dict = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL,
                    "close_fds": True}
    if sys.platform == "win32":
        kwargs["creationflags"] = 0x00000008 | 0x00000200          # DETACHED_PROCESS | NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    env = {k: v for k, v in os.environ.items() if not k.startswith("_PYI") and k != "APPIMAGE"} \
        if sys.platform.startswith("linux") else None
    subprocess.Popen(cmd, env=env, **kwargs)


def ready_note() -> str:
    """What "ready to install" says will happen."""
    if sys.platform == "darwin":
        what = ("ASTERISM will close, install the update and open again by itself. The first start "
                "of the new version can take up to a minute while macOS checks it.")
    elif sys.platform == "win32":
        what = ("ASTERISM will close and the installer will show its progress. ASTERISM opens again "
                "when it is done.")
    else:
        what = "ASTERISM will close and open again with the new version."
    return what + " You are asked to save open work first."


def install(release: dict, parent=None) -> None:
    """Download and verify (with the update window), then — once the user chooses Restart and
    Install — ask to save, quit, and start the new version."""
    from PySide6.QtWidgets import QApplication, QMessageBox
    from .dialogs.update import UpdateDialog
    version = str(release.get("tag_name") or "").lstrip("v")
    dlg = UpdateDialog(version, parent, unpacks=sys.platform == "darwin")
    dlg.show()
    path = download_and_verify(release, parent, dlg)
    if path is None:
        dlg.finish()
        return
    if sys.platform == "darwin":
        try:
            new_app = _in_background(unpack_mac, path)
        except (OSError, subprocess.CalledProcessError):
            new_app = None
        if new_app is None:
            dlg.finish()
            _discard(path)
            QMessageBox.warning(parent, "Update", "The update couldn't be unpacked. Download it from the "
                                                  "release page instead.")
            return
    choice = dlg.ready(ready_note())
    dlg.finish()
    if choice != "install":
        _discard(path)                            # offered again at the next check
        return
    from .main_window import windows
    for w in list(windows()):                     # each window asks about unsaved changes
        if not w.close():
            _discard(path)
            QMessageBox.information(parent, "Update", "The update wasn't installed. It will be offered "
                                                      "again next time you check for updates.")
            return
    try:
        cmd = prepare(path)
    except (OSError, subprocess.CalledProcessError) as e:
        cmd = None
        err = str(e)
    else:
        err = ""
    if not cmd:
        QMessageBox.warning(None, "Update", "The update couldn't be installed here"
                            + (f" ({err})" if err else "") + ". Download it from the release page instead.")
        from .main_window import new_window
        new_window()
        return
    app = QApplication.instance()
    server = getattr(app, "_server", None)
    if server is not None:                        # the new copy mustn't hand itself back to us
        server.close()
    launch_detached(cmd)
    app.quit()
