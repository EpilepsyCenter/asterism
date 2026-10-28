"""Check for updates: compare this version with the latest release on GitHub.

Help › Check for Updates asks now and always answers. With Settings › General › "Check for
updates when ASTERISM starts" on, a silent check runs at most once a day and speaks only
when a newer version exists. Nothing is downloaded or installed without asking: an update
can be installed from inside the app (selfupdate.py) or downloaded from the release page.
"""

from __future__ import annotations

import json
import re
import time

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

REPO = "EpilepsyCenter/asterism"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES = f"https://github.com/{REPO}/releases"

_manager: QNetworkAccessManager | None = None


def parse_version(v: str) -> tuple[int, ...]:
    """'v0.2.1' → (0, 2, 1); anything unreadable → ()."""
    m = re.match(r"^\s*v?(\d+(?:\.\d+)*)", v or "")
    return tuple(int(x) for x in m.group(1).split(".")) if m else ()


def newer(latest: str, current: str) -> bool:
    a, b = parse_version(latest), parse_version(current)
    if not a or not b:
        return False
    n = max(len(a), len(b))
    return a + (0,) * (n - len(a)) > b + (0,) * (n - len(b))


def check(parent=None, silent: bool = False) -> None:
    """Ask GitHub for the latest release. `silent`: say nothing unless there's an update."""
    from asterism import __version__
    from . import documents
    global _manager
    if silent:
        last = float(documents.value("updates/last_check", 0) or 0)
        if time.time() - last < 24 * 3600:
            return
    documents.set_value("updates/last_check", time.time())
    if _manager is None:
        _manager = QNetworkAccessManager()
    req = QNetworkRequest(QUrl(API))
    req.setRawHeader(b"Accept", b"application/vnd.github+json")
    req.setRawHeader(b"User-Agent", f"ASTERISM/{__version__}".encode())
    req.setTransferTimeout(10000)
    reply = _manager.get(req)

    def done():
        reply.deleteLater()
        status = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
        if status == 404:                            # no release published yet
            if not silent:
                _say(parent, "ASTERISM is up to date", f"You have the latest version, {__version__}.", link=False)
            return
        if reply.error() != QNetworkReply.NoError:
            if not silent:
                _say(parent, "Couldn't check for updates",
                     "ASTERISM couldn't reach GitHub. Check your internet connection, or look at "
                     f"the releases page yourself:\n{RELEASES}", link=False)
            return
        try:
            info = json.loads(bytes(reply.readAll()).decode("utf-8"))
        except ValueError:
            info = {}
        latest = info.get("tag_name", "")
        url = info.get("html_url") or RELEASES
        if latest and newer(latest, __version__):
            offer(parent, info, latest.lstrip("v"), __version__, url)
        elif not silent:
            _say(parent, "ASTERISM is up to date", f"You have the latest version, {__version__}.", link=False)
    reply.finished.connect(done)


def offer(parent, release: dict, latest: str, current: str, url: str) -> None:
    """An update exists: install it now (packaged apps), see what's new, or later."""
    from PySide6.QtWidgets import QMessageBox
    from . import selfupdate
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Information)
    box.setWindowTitle("An update is available")
    box.setText(f"ASTERISM {latest} is available (you have {current}).")
    can = selfupdate.can_install() and selfupdate.pick_asset(release)[0] is not None
    box.setInformativeText("Install it now? ASTERISM asks to save your work, restarts and opens the new version."
                           if can else "Open the download page?")
    install = box.addButton("Install Update" if can else "Open Download Page", QMessageBox.AcceptRole)
    notes = box.addButton("What's New", QMessageBox.HelpRole) if can else None
    box.addButton("Later", QMessageBox.RejectRole)
    box.setDefaultButton(install)
    box.exec()
    clicked = box.clickedButton()
    if clicked is install:
        if can:
            selfupdate.install(release, parent)
        else:
            QDesktopServices.openUrl(QUrl(url))
    elif notes is not None and clicked is notes:
        QDesktopServices.openUrl(QUrl(url))


def _say(parent, title: str, text: str, link: bool, url: str = RELEASES) -> None:
    from PySide6.QtWidgets import QMessageBox
    box = QMessageBox(QMessageBox.Information, title, text,
                      (QMessageBox.Open | QMessageBox.Cancel) if link else QMessageBox.Ok, parent)
    if link:
        box.button(QMessageBox.Open).setText("Open Download Page")
    if box.exec() == QMessageBox.Open:
        QDesktopServices.openUrl(QUrl(url))
