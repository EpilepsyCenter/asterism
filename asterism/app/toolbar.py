"""Top bar, tool panel and status strip (SPEC §12).

Top bar: the sheet's name (click to rename) and description, then caption-less icon
groups for project-wide actions (Project · Sheet · Edit), Export at the right end.
Tool panel (right): captioned groups for the current sheet's content (Analyze · Graph ·
Draw · Text). Both are built from the window's QActions, so menus, top bar and panel
always agree on what is enabled.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QComboBox, QFontComboBox, QFrame, QGridLayout, QHBoxLayout,
                               QLabel, QLineEdit, QMenu, QScrollArea, QSizePolicy, QSlider,
                               QToolBar, QToolButton, QVBoxLayout, QWidget)

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


def wide_button(action: QAction) -> QToolButton:
    b = QToolButton()
    b.setObjectName("WideTool")
    b.setDefaultAction(action)
    b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
    b.setIconSize(QSize(16, 16))
    b.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)   # never widen the panel
    b.setMinimumWidth(0)
    b.setFixedHeight(32)
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
    def __init__(self, groups: list[list[QAction]], export_actions: list[QAction],
                 toggle_tools: QAction):
        super().__init__()
        self.setObjectName("TopBar")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedHeight(52)
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
        h.addSpacing(12)
        # A QToolBar, so icons that don't fit go into its » overflow menu instead of
        # forcing a minimum window width (which would also block resizing the sidebars).
        self.tools = QToolBar()
        self.tools.setObjectName("TopTools")
        self.tools.setMovable(False)
        self.tools.setFloatable(False)
        self.tools.setIconSize(QSize(18, 18))
        self.tools.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.tools.setLayoutDirection(Qt.LeftToRight)
        for gi, actions in enumerate(groups):
            if gi:
                self.tools.addSeparator()
            self.tools.addActions(actions)
        h.addWidget(self.tools, 0)
        h.addSpacing(14)
        self.export = QToolButton()
        self.export.setObjectName("ExportButton")
        set_icon(self.export, "square.and.arrow.up", "accent")
        self.export.setText("Export")
        self.export.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.export.setPopupMode(QToolButton.InstantPopup)
        self.export.setFixedHeight(30)
        self.export.setFocusPolicy(Qt.NoFocus)
        menu = QMenu(self.export)
        menu.addActions(export_actions)
        self.export.setMenu(menu)
        h.addWidget(self.export)
        h.addSpacing(4)
        h.addWidget(icon_button(toggle_tools))


class ToolPanel(QWidget):
    """The tool sidebar: captioned groups, a wide button for each group's main action, an
    icon grid for the rest. `groups` = [(caption, wide action or None, [actions]) or
    (caption, "text", None) for the text controls]."""

    COLS = 5

    def __init__(self, groups, text_widgets: list[QWidget], text_actions: list[QAction]):
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
        v = QVBoxLayout(inner)
        v.setContentsMargins(12, 10, 12, 12)
        v.setSpacing(4)
        for caption, wide, actions in groups:
            cap = QLabel(caption)
            cap.setObjectName("ToolGroup")
            v.addSpacing(4)
            v.addWidget(cap)
            if wide == "text":
                row = QHBoxLayout()
                for w in text_widgets:
                    if isinstance(w, QFontComboBox):
                        w.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
                        w.setMinimumWidth(0)
                    row.addWidget(w, 1 if isinstance(w, QFontComboBox) else 0)
                v.addLayout(row)
                actions = text_actions
            elif wide is not None:
                v.addWidget(wide_button(wide))
            grid = QGridLayout()
            grid.setHorizontalSpacing(2)
            grid.setVerticalSpacing(2)
            for i, a in enumerate(actions):
                b = icon_button(a, "Tool", (36, 32))
                # Buttons share the panel width, so the right margin always equals the left.
                b.setMinimumWidth(26)
                b.setMaximumWidth(16777215)
                b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                grid.addWidget(b, i // self.COLS, i % self.COLS)
            for c in range(self.COLS):
                grid.setColumnStretch(c, 1)
            v.addLayout(grid)
            rule = QFrame()
            rule.setObjectName("ToolRule")
            rule.setFixedHeight(1)
            v.addSpacing(6)
            v.addWidget(rule)
        v.addStretch(1)
        scroll.setWidget(inner)
        outer.addWidget(scroll)


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
