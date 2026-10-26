"""The Help window: contents and search on the left, the page on the right, back/forward.

One window for the whole app. Dialogs' Help buttons call `show_topic(topic)`, which opens
the page and scrolls to the dialog's section. The keyboard shortcuts page is built from
the live menus, so it never goes out of date.
"""

from __future__ import annotations

import html

from PySide6.QtCore import QSize, QUrl, Qt
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QSplitter, QStackedWidget, QTextBrowser, QToolButton, QTreeWidget,
                               QTreeWidgetItem, QVBoxLayout, QWidget)

from .. import help as H
from . import theme

_window: "HelpWindow | None" = None


def window() -> "HelpWindow":
    global _window
    if _window is None:
        _window = HelpWindow()
    return _window


def show_topic(topic: str = "") -> "HelpWindow":
    """Open the help at a dialog's topic (or the start page)."""
    w = window()
    slug, frag = H.resolve(topic) if topic else ("start", "")
    w.open(slug, frag)
    w.show()
    w.raise_()
    w.activateWindow()
    return w


def show_page(slug: str, frag: str = "") -> "HelpWindow":
    w = window()
    w.open(slug, frag)
    w.show()
    w.raise_()
    w.activateWindow()
    return w


def _shortcuts_md() -> str:
    """Every menu command that has a shortcut, from the frontmost project window."""
    from .main_window import MainWindow, windows
    ws = windows() or [w for w in QApplication.topLevelWidgets() if isinstance(w, MainWindow)]
    ws = [w for w in ws if w.isVisible()] or ws
    lines = ["# Keyboard shortcuts", "",
             "Every menu command with a shortcut. On Windows, Ctrl takes the place of ⌘.", ""]
    if not ws:
        return "\n".join(lines + ["Open a project window to see the shortcuts."])
    bar = ws[-1].menuBar()

    def walk(menu, path):
        rows = []
        for a in menu.actions():
            if a.menu():
                rows += walk(a.menu(), path + [a.menu().title().replace("&", "")])
            elif not a.isSeparator() and not a.shortcut().isEmpty():
                keys = a.shortcut().toString(QKeySequence.NativeText)
                rows.append((" › ".join(path), a.text().replace("&", ""), keys))
        return rows
    for top in bar.actions():
        if not top.menu():
            continue
        rows = walk(top.menu(), [])
        if not rows:
            continue
        lines += [f"## {top.text().replace('&', '')}", "", "| Command | Shortcut |", "|---|---|"]
        for sub, text, keys in rows:
            lines.append(f"| {(sub + ' › ') if sub else ''}{text} | {keys} |")
        lines.append("")
    return "\n".join(lines)


class HelpWindow(QWidget):
    def __init__(self):
        super().__init__(None, Qt.Window)
        self.setWindowTitle("ASTERISM Help")
        self.resize(980, 720)
        self.history: list[tuple[str, str]] = []
        self.pos = -1
        self.slug = ""

        # left: search + contents / results
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search help")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._search)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.itemActivated.connect(self._tree_go)
        self.tree.itemClicked.connect(self._tree_go)
        self.results = QListWidget()
        self.results.setWordWrap(True)
        self.results.itemActivated.connect(self._result_go)
        self.results.itemClicked.connect(self._result_go)
        self.left_stack = QStackedWidget()
        self.left_stack.addWidget(self.tree)
        self.left_stack.addWidget(self.results)
        self.back_b, self.fwd_b = QToolButton(), QToolButton()
        self.back_b.setText("‹")
        self.fwd_b.setText("›")
        self.back_b.setToolTip("Back")
        self.fwd_b.setToolTip("Forward")
        self.back_b.clicked.connect(self.back)
        self.fwd_b.clicked.connect(self.forward)
        top = QHBoxLayout()
        top.addWidget(self.back_b)
        top.addWidget(self.fwd_b)
        top.addWidget(self.search, 1)
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(10, 10, 4, 10)
        ll.addLayout(top)
        ll.addWidget(self.left_stack, 1)

        # right: the page
        self.view = QTextBrowser()
        self.view.setOpenLinks(False)
        self.view.anchorClicked.connect(self._link)
        self.view.document().setDocumentMargin(22)
        self.view.document().setIndentWidth(18)

        split = QSplitter()
        split.addWidget(left)
        split.addWidget(self.view)
        split.setSizes([270, 710])
        split.setChildrenCollapsible(False)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(split)

        QShortcut(QKeySequence.Back, self, self.back)
        QShortcut(QKeySequence.Forward, self, self.forward)
        QShortcut(QKeySequence.Find, self, lambda: (self.search.setFocus(), self.search.selectAll()))
        QShortcut(QKeySequence.Close, self, self.close)
        self._build_tree()
        self._buttons()
        theme.notifier.changed.connect(self._rerender)

    # --- contents -----------------------------------------------------------------

    def _build_tree(self) -> None:
        self.tree.clear()
        self.items: dict[tuple[str, str], QTreeWidgetItem] = {}
        for slug, title in H.PAGES:
            it = QTreeWidgetItem([title])
            it.setData(0, Qt.UserRole, (slug, ""))
            self.tree.addTopLevelItem(it)
            self.items[(slug, "")] = it
            if slug == "shortcuts":
                continue
            for s in H.sections(slug):
                if s.level == 2:
                    ch = QTreeWidgetItem([s.title])
                    ch.setData(0, Qt.UserRole, (slug, s.anchor))
                    it.addChild(ch)
                    self.items[(slug, s.anchor)] = ch

    def _tree_go(self, item, _col=0) -> None:
        slug, frag = item.data(0, Qt.UserRole)
        self.open(slug, frag)

    def _search(self, text: str) -> None:
        if not text.strip():
            self.left_stack.setCurrentWidget(self.tree)
            return
        self.results.clear()
        self.left_stack.setCurrentWidget(self.results)
        width = max(160, self.left_stack.width() - 24)
        hits = H.search(text)
        tk = theme.tokens()
        for s, snippet in hits:
            title = H.page_title(s.slug) if s.level == 1 else s.title
            page = "" if s.level == 1 else H.page_title(s.slug)
            lab = QLabel(f'<b>{html.escape(title)}</b>'
                         + (f' <span style="color:{tk["muted"]}">· {html.escape(page)}</span>' if page else "")
                         + (f'<br><span style="color:{tk["muted"]}">{html.escape(snippet)}</span>' if snippet else ""))
            lab.setWordWrap(True)
            lab.setContentsMargins(6, 5, 6, 5)
            lab.setAttribute(Qt.WA_TransparentForMouseEvents)
            it = QListWidgetItem()
            it.setData(Qt.UserRole, (s.slug, s.anchor))
            self.results.addItem(it)
            self.results.setItemWidget(it, lab)
            lab.setFixedWidth(width)
            it.setSizeHint(QSize(width, lab.heightForWidth(width) + 2))
        if not hits:
            it = QListWidgetItem("Nothing found.")
            it.setFlags(Qt.NoItemFlags)
            self.results.addItem(it)
        self.left_stack.setCurrentWidget(self.results)

    def _result_go(self, item) -> None:
        d = item.data(Qt.UserRole)
        if d:
            self.open(*d)

    # --- pages --------------------------------------------------------------------

    def _colours(self) -> dict:
        tk = theme.tokens()
        dark = theme.is_dark()
        return {"text": tk["text"], "muted": tk["muted"], "accent": tk["accent"],
                "code_bg": "#232a31" if dark else "#ecebe6", "note_bg": "#13323a" if dark else "#e4f1f4"}

    def _render(self, slug: str) -> None:
        md = _shortcuts_md() if slug == "shortcuts" else H.load(slug)
        self.view.setHtml(H.to_html(md, self._colours()))
        self.slug = slug

    def _rerender(self) -> None:
        if self.slug:
            v = self.view.verticalScrollBar().value()
            self._render(self.slug)
            self.view.verticalScrollBar().setValue(v)

    def open(self, slug: str, frag: str = "", record: bool = True) -> None:
        if slug not in dict(H.PAGES):
            slug, frag = "start", ""
        if slug != self.slug or slug == "shortcuts":
            self._render(slug)
        if frag:
            self.view.scrollToAnchor(frag)
        else:
            self.view.verticalScrollBar().setValue(0)
        if record:
            del self.history[self.pos + 1:]
            self.history.append((slug, frag))
            self.pos = len(self.history) - 1
        it = self.items.get((slug, frag)) or self.items.get((slug, ""))
        if it is not None:
            self.tree.blockSignals(True)
            self.tree.setCurrentItem(it)
            self.tree.blockSignals(False)
        self._buttons()

    def back(self) -> None:
        if self.pos > 0:
            self.pos -= 1
            self.open(*self.history[self.pos], record=False)

    def forward(self) -> None:
        if self.pos < len(self.history) - 1:
            self.pos += 1
            self.open(*self.history[self.pos], record=False)

    def _buttons(self) -> None:
        self.back_b.setEnabled(self.pos > 0)
        self.fwd_b.setEnabled(self.pos < len(self.history) - 1)

    def _link(self, url: QUrl) -> None:
        if url.scheme() in ("http", "https", "mailto"):
            QDesktopServices.openUrl(url)
            return
        s = url.toString()
        target, _, frag = s.partition("#")
        slug = target[:-3] if target.endswith(".md") else target
        self.open(slug or self.slug, frag)


def current() -> "HelpWindow | None":
    return _window
