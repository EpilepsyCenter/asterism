"""Top bar, tool panel and status strip (SPEC §12).

Top bar: the sheet's name (click to rename) and description, a small unlabelled group of
file and edit commands, then labelled buttons for new sheets, Analyze and Export.
Tool panel (right): one page per kind of sheet, listing only the commands that apply to it,
by name. Both are built from the window's QActions, so menus, top bar and panel always
agree on what is enabled.
"""

from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QAction, QFont, QFontMetrics, QIcon, QKeySequence, QPainter
from PySide6.QtWidgets import (QAbstractButton, QFontComboBox, QFrame, QGridLayout, QHBoxLayout,
                               QLabel, QLineEdit, QMenu, QScrollArea, QSizePolicy, QSlider,
                               QToolBar, QToolButton, QVBoxLayout, QWidget)

from . import theme
from .icons import set_icon


def _sep(h: int = 20) -> QFrame:
    f = QFrame()
    f.setObjectName("ToolSep")
    f.setFixedSize(1, h)
    return f


def icon_button(action: QAction, name: str = "TopTool", size=(32, 30)) -> QToolButton:
    b = QToolButton()
    b.setObjectName(name)
    b.setDefaultAction(action)
    b.setToolButtonStyle(Qt.ToolButtonIconOnly)
    b.setIconSize(QSize(18, 18))
    b.setFixedSize(*size)
    b.setAutoRaise(True)
    b.setFocusPolicy(Qt.NoFocus)
    return b


class SheetTitle(QLineEdit):
    """The sheet name in the top bar: looks like a label, edits like a field."""

    renamed = Signal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("SheetTitle")
        self.setFrame(False)
        self.setToolTip("Click to rename this sheet")
        self.setMinimumWidth(120)
        self.setMaximumWidth(460)
        self.editingFinished.connect(self._done)

    _full = ""

    def set_name(self, name: str) -> None:
        self._full = name
        if not self.hasFocus():
            self._show_elided()

    def _show_elided(self) -> None:
        w = max(20, self.width() - 10)
        self.setText(self.fontMetrics().elidedText(self._full, Qt.ElideRight, w))
        self.setToolTip(f"{self._full}\nClick to rename this sheet")
        self.setCursorPosition(0)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if not self.hasFocus():
            self._show_elided()

    def focusInEvent(self, e):
        self.setText(self._full)
        super().focusInEvent(e)
        self.selectAll()

    def focusOutEvent(self, e):
        super().focusOutEvent(e)
        self._show_elided()

    def _done(self) -> None:
        if self.hasFocus() or self.text() != self.fontMetrics().elidedText(self._full, Qt.ElideRight, max(20, self.width() - 10)):
            self.renamed.emit(self.text().strip())
        self.clearFocus()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.clearFocus()
            return
        super().keyPressEvent(e)


class TopBar(QWidget):
    """Sheet name and description, a small unlabelled group of file and edit commands,
    then the labelled sheet commands (labels under the icons) and Export.

    `file_groups` and `groups` are lists of action groups (separators between groups).
    The labelled buttons show each action's iconText, so they can be shorter than the
    menu text ("Table" for "New Data Table…").
    """

    def __init__(self, file_groups: list[list[QAction]], groups: list[list[QAction]],
                 export_actions: list[QAction], toggle_tools: QAction):
        super().__init__()
        self.setObjectName("TopBar")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedHeight(58)
        h = QHBoxLayout(self)
        h.setContentsMargins(16, 0, 12, 0)
        h.setSpacing(2)
        col = QVBoxLayout()
        col.setSpacing(0)
        self.title = SheetTitle()
        self.subtitle = QLabel()
        self.subtitle.setObjectName("SheetSubtitle")
        self.subtitle.setContentsMargins(4, 0, 0, 0)
        self.subtitle.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)  # clip, never widen
        self.title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        col.addStretch(1)
        col.addWidget(self.title)
        col.addWidget(self.subtitle)
        col.addStretch(1)
        h.addLayout(col, 1)
        h.addSpacing(8)
        # QToolBars, so buttons that don't fit go into a » overflow menu instead of forcing
        # a minimum window width (which would also block resizing the sidebars).
        self.file_tools = self._bar("FileTools", Qt.ToolButtonIconOnly, 16, file_groups)
        h.addWidget(self.file_tools, 0)
        h.addSpacing(4)
        h.addWidget(_sep(30))
        h.addSpacing(4)
        menu = QMenu("Export", self)
        menu.addActions(export_actions)
        self.export_action = menu.menuAction()
        self.export_action.setIconText("Export")
        set_icon(self.export_action, "square.and.arrow.up", "accent")
        self.tools = self._bar("TopTools", Qt.ToolButtonTextUnderIcon, 20, [*groups, [self.export_action]])
        self.export = self.tools.widgetForAction(self.export_action)
        self.export.setPopupMode(QToolButton.InstantPopup)
        h.addWidget(self.tools, 0)
        h.addSpacing(8)
        h.addWidget(icon_button(toggle_tools))

    @staticmethod
    def _bar(name, style, icon, groups) -> QToolBar:
        bar = QToolBar()
        bar.setObjectName(name)
        bar.setMovable(False)
        bar.setFloatable(False)
        bar.setIconSize(QSize(icon, icon))
        bar.setToolButtonStyle(style)
        bar.setLayoutDirection(Qt.LeftToRight)
        for gi, actions in enumerate(groups):
            if gi:
                bar.addSeparator()
            bar.addActions(actions)
        for a in bar.actions():
            b = bar.widgetForAction(a)
            if b is not None:
                b.setFocusPolicy(Qt.NoFocus)
        return bar


class ActionRow(QAbstractButton):
    """One command in the tool panel: icon, name, and its shortcut at the right.
    Follows its action (enabled state, tooltip) and triggers it when clicked."""

    def __init__(self, action: QAction, text: str | None = None):
        super().__init__()
        self.action, self._text = action, text
        self.setObjectName("PanelRow")
        self.setFocusPolicy(Qt.NoFocus)
        self.setAttribute(Qt.WA_Hover, True)
        self.setFixedHeight(28)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumWidth(0)
        self.clicked.connect(action.trigger)
        action.changed.connect(self._sync)
        self._sync()

    def text(self) -> str:                                  # noqa: D401 - QAbstractButton API
        return self._text or self.action.text()

    def _sync(self) -> None:
        self.setEnabled(self.action.isEnabled())
        self.setToolTip(self.action.toolTip())
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(160, 28)

    def paintEvent(self, e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect()
        on = self.isEnabled()
        if on and (self.isDown() or self.underMouse()):
            p.setPen(Qt.NoPen)
            p.setBrush(theme.color("surface_hover") if not self.isDown()
                       else theme.mix("surface_hover", "text", 0.08))
            p.drawRoundedRect(r, 5, 5)
        self.action.icon().paint(p, QRect(8, (r.height() - 16) // 2, 16, 16), Qt.AlignCenter,
                                 QIcon.Normal if on else QIcon.Disabled)
        right = r.width() - 8
        keys = self.action.shortcut().toString(QKeySequence.NativeText)
        if keys:
            f = QFont(self.font())
            f.setPointSizeF(f.pointSizeF() - 2)
            p.setFont(f)
            p.setPen(theme.color("muted") if on else theme.mix("chrome", "muted", 0.6))
            kw = QFontMetrics(f).horizontalAdvance(keys)
            p.drawText(QRect(right - kw, 0, kw, r.height()), Qt.AlignVCenter | Qt.AlignRight, keys)
            right -= kw + 10
        p.setFont(self.font())
        p.setPen(theme.color("text") if on else theme.mix("chrome", "muted", 0.6))
        x = 33
        text = self.fontMetrics().elidedText(self.text(), Qt.ElideRight, max(0, right - x))
        p.drawText(QRect(x, 0, max(0, right - x), r.height()), Qt.AlignVCenter | Qt.AlignLeft, text)


class ToolPanel(QWidget):
    """The right-hand tool panel. It shows one page at a time, chosen by the current sheet
    (data table of a given type, graph, results, figure…), so it only ever lists commands
    that apply. Pages are built on first use from a list of items:

        ("head", "Analyze")          section title (a rule above all but the first)
        ("primary", action)          the section's main command, as a filled button
        ("sub", "Compare groups")    small heading inside a section
        ("row", action[, text])      a command by name, with its shortcut
        ("tiles", [actions])         icon tiles with a short label (the action's iconText)
        ("icons", [actions])         a row of icon-only buttons (text formatting)
        ("widgets", [widgets])       widgets side by side (font controls)
        ("note", "text")             a muted line of text
    """

    def __init__(self):
        super().__init__()
        self.setObjectName("ToolPanel")
        self.setAttribute(Qt.WA_StyledBackground, True)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.viewport().setAutoFillBackground(False)
        inner = QWidget()
        inner.setAutoFillBackground(False)
        inner.setMinimumWidth(0)
        self._v = QVBoxLayout(inner)
        self._v.setContentsMargins(12, 10, 12, 12)
        self._v.setSpacing(0)
        self._v.addStretch(1)
        scroll.setWidget(inner)
        outer.addWidget(scroll)
        self.pages: dict[str, QWidget] = {}
        self.current_key: str | None = None

    def show_page(self, key: str, items) -> None:
        """Show page `key`, building it from `items()` (a callable) the first time."""
        if key not in self.pages:
            page = self._build(items())
            self._v.insertWidget(self._v.count() - 1, page)
            self.pages[key] = page
        for k, page in self.pages.items():
            page.setVisible(k == key)
        self.current_key = key

    def current_page(self) -> QWidget | None:
        return self.pages.get(self.current_key)

    def _build(self, items) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(1)
        first = True
        for item in items:
            kind = item[0]
            if kind == "head":
                if not first:
                    v.addSpacing(8)
                    rule = QFrame()
                    rule.setObjectName("ToolRule")
                    rule.setFixedHeight(1)
                    v.addWidget(rule)
                    v.addSpacing(6)
                first = False
                lab = QLabel(item[1])
                lab.setObjectName("PanelHead")
                lab.setContentsMargins(2, 2, 0, 4)
                v.addWidget(lab)
            elif kind == "primary":
                b = QToolButton()
                b.setObjectName("PanelPrimary")
                b.setDefaultAction(item[1])
                b.setText(item[1].text())
                b.setToolButtonStyle(Qt.ToolButtonTextOnly)
                b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                b.setMinimumWidth(0)
                b.setFixedHeight(32)
                b.setFocusPolicy(Qt.NoFocus)
                item[1].changed.connect(lambda b=b, a=item[1]: b.setText(a.text()))
                v.addWidget(b)
                v.addSpacing(5)
            elif kind == "sub":
                lab = QLabel(item[1].upper())
                lab.setObjectName("PanelSub")
                lab.setContentsMargins(8, 6, 0, 1)
                v.addWidget(lab)
            elif kind == "row":
                v.addWidget(ActionRow(item[1], item[2] if len(item) > 2 else None))
            elif kind == "tiles":
                v.addLayout(self._tiles(item[1]))
            elif kind == "icons":
                row = QHBoxLayout()
                row.setSpacing(2)
                for a in item[1]:
                    b = icon_button(a, "Tool", (36, 30))
                    b.setMinimumWidth(26)
                    b.setMaximumWidth(16777215)
                    b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                    row.addWidget(b)
                v.addLayout(row)
            elif kind == "widgets":
                row = QHBoxLayout()
                for w in item[1]:
                    if isinstance(w, QFontComboBox):
                        w.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
                        w.setMinimumWidth(0)
                    row.addWidget(w, 1 if isinstance(w, QFontComboBox) else 0)
                v.addLayout(row)
                v.addSpacing(4)
            elif kind == "note":
                lab = QLabel(item[1])
                lab.setObjectName("PanelNote")
                lab.setWordWrap(True)
                lab.setContentsMargins(2, 4, 2, 0)
                v.addWidget(lab)
        return page

    @staticmethod
    def _tiles(actions, cols: int = 3) -> QGridLayout:
        g = QGridLayout()
        g.setSpacing(2)
        for i, a in enumerate(actions):
            b = QToolButton()
            b.setObjectName("PanelTile")
            b.setDefaultAction(a)
            b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            b.setIconSize(QSize(18, 18))
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            b.setMinimumWidth(0)
            b.setFixedHeight(46)
            b.setFocusPolicy(Qt.NoFocus)
            g.addWidget(b, i // cols, i % cols)
        for c in range(cols):
            g.setColumnStretch(c, 1)
        return g


class StatusStrip(QWidget):
    def __init__(self, toggle_sidebar: QAction):
        super().__init__()
        self.setObjectName("StatusStrip")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedHeight(26)
        h = QHBoxLayout(self)
        h.setContentsMargins(6, 0, 12, 0)
        h.setSpacing(6)
        h.addWidget(icon_button(toggle_sidebar, "TopTool", (26, 22)))
        self.left = QLabel("")
        h.addWidget(self.left)
        h.addStretch(1)
        self.message = QLabel("")
        h.addWidget(self.message)
        self.zoom_w = QWidget()
        zh = QHBoxLayout(self.zoom_w)
        zh.setContentsMargins(0, 0, 0, 0)
        zh.setSpacing(4)
        self.zoom_out = QToolButton()
        self.zoom_out.setObjectName("TopTool")
        set_icon(self.zoom_out, "minus.magnifyingglass", "muted")
        self.zoom_out.setAutoRaise(True)
        self.zoom = QSlider(Qt.Horizontal)
        self.zoom.setRange(25, 400)
        self.zoom.setFixedWidth(130)
        self.zoom_in = QToolButton()
        self.zoom_in.setObjectName("TopTool")
        set_icon(self.zoom_in, "plus.magnifyingglass", "muted")
        self.zoom_in.setAutoRaise(True)
        self.zoom_label = QLabel("200%")
        self.zoom_label.setMinimumWidth(40)
        for w in (self.zoom_out, self.zoom, self.zoom_in, self.zoom_label):
            zh.addWidget(w)
        h.addWidget(self.zoom_w)
