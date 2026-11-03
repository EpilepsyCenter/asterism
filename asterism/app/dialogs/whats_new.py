"""The "What's new" window: what changed in the version you're running.

Shown once, the first time a newer version starts (after an in-app update or a manual
install), and any time from Help › What's New…. A fresh install records its version
silently. If versions were skipped, the notes of each are shown, newest first. The notes
come from asterism/help/changelog.md; the decision is in asterism/help/changelog.py.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QTextBrowser, QVBoxLayout

from asterism import __version__

from ...help import changelog as C
from ...help import to_html
from .. import documents, theme


def startup_entries(keys_at_start: list[str]) -> tuple[list[C.Entry], str | None]:
    """Which notes to show at this start (and the version seen before), recording the
    running version as seen. `keys_at_start`: the settings keys as they were before
    anything at startup wrote one."""
    stored = documents.value(C.LAST_SEEN)
    stored = stored if isinstance(stored, str) else None
    others = any(k != C.LAST_SEEN for k in keys_at_start)
    show, record = C.decide(stored, others, __version__, C.load())
    if record:
        documents.set_value(C.LAST_SEEN, __version__)
    return show, stored


class WhatsNewDialog(QDialog):
    def __init__(self, entries: list[C.Entry], parent=None, since: str | None = None):
        super().__init__(parent)
        self.entries = entries
        self.setWindowTitle("What's New")
        self.setMinimumSize(520, 360)
        self.resize(620, 520)

        newest = entries[0].version if entries else __version__
        if len(entries) > 1:
            title = f"What's new since ASTERISM {since}" if since else \
                f"What's new in ASTERISM {entries[-1].version} to {newest}"
        else:
            title = f"What's new in ASTERISM {newest}"
        self.head = QLabel(title)
        f = self.head.font()
        f.setPointSizeF(f.pointSizeF() + 2)
        f.setBold(True)
        self.head.setFont(f)

        self.view = QTextBrowser()
        self.view.setOpenLinks(False)
        self.view.anchorClicked.connect(self._link)
        self.view.document().setDocumentMargin(14)
        self.view.document().setIndentWidth(18)

        self.help_btn = QPushButton("Open the Help")
        self.close_btn = QPushButton("Close")
        self.help_btn.setAutoDefault(False)
        self.close_btn.setDefault(True)
        self.help_btn.clicked.connect(lambda: self._open_help("start", ""))
        self.close_btn.clicked.connect(self.accept)
        buttons = QHBoxLayout()
        buttons.addWidget(self.help_btn)
        buttons.addStretch(1)
        buttons.addWidget(self.close_btn)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 16)
        lay.setSpacing(12)
        lay.addWidget(self.head)
        lay.addWidget(self.view, 1)
        lay.addLayout(buttons)
        self._render()
        theme.notifier.changed.connect(self._render)
        self.close_btn.setFocus()

    def markdown(self) -> str:
        if len(self.entries) == 1:
            return self.entries[0].body
        return "\n\n".join(f"## {e.version}\n\n{e.body}" for e in self.entries)

    def _render(self) -> None:
        from ..help_window import colours
        self.view.setHtml(to_html(self.markdown(), colours()))

    def _link(self, url: QUrl) -> None:
        if url.scheme() in ("http", "https", "mailto"):
            QDesktopServices.openUrl(url)
            return
        target, _, frag = url.toString().partition("#")
        self._open_help(target[:-3] if target.endswith(".md") else target or "start", frag)

    def _open_help(self, slug: str, frag: str) -> None:
        from ..help_window import show_page
        show_page(slug, frag)


def show(entries: list[C.Entry], parent=None, since: str | None = None) -> WhatsNewDialog | None:
    """Open the window (non-modal, so Read more can open the help beside it)."""
    if not entries:
        return None
    dlg = WhatsNewDialog(entries, parent, since)
    dlg.setAttribute(Qt.WA_DeleteOnClose)
    dlg.show()
    dlg.raise_()
    dlg.activateWindow()
    return dlg


def show_when_ready(entries: list[C.Entry], since: str | None = None, delay: int = 800) -> None:
    """At startup: once no modal window is open (the Start window, Restore Unsaved Work),
    over the frontmost project window. Shown during a modal window it couldn't be used."""
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    def attempt():
        if QApplication.activeModalWidget() is not None:
            QTimer.singleShot(400, attempt)
            return
        from ..main_window import windows
        ws = windows()
        show(entries, ws[-1] if ws else None, since)
    if entries:
        QTimer.singleShot(delay, attempt)


def show_from_menu(parent=None) -> WhatsNewDialog | None:
    return show(C.for_menu(C.load(), __version__), parent)
