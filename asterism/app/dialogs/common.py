"""Building blocks shared by the Prism-style dialogs."""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QDialog, QFrame,
                               QGridLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
                               QMessageBox, QPushButton, QScrollArea, QSizePolicy,
                               QStackedWidget, QToolButton, QVBoxLayout, QWidget)

from .. import theme
from ..icons import icon
from ..widgets import NavDelegate


def bold(text: str) -> QLabel:
    lab = QLabel(text)
    f = lab.font()
    f.setBold(True)
    lab.setFont(f)
    return lab


def hline() -> QFrame:
    ln = QFrame()
    ln.setObjectName("Rule")
    ln.setFixedHeight(1)
    ln.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    return ln


class Section(QWidget):
    """Bold section title followed by a rule, optionally with a checkbox (Prism style)."""

    toggled = Signal(bool)

    def __init__(self, title: str, checkable: bool = False, checked: bool = True):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 6, 0, 0)
        lay.setSpacing(8)
        self.check: QCheckBox | None = None
        if checkable:
            self.check = QCheckBox(title)
            self.check.setObjectName("SectionTitle")
            self.check.setChecked(checked)
            self.check.toggled.connect(self.toggled)
            lay.addWidget(self.check)
        else:
            lab = QLabel(title)
            lab.setObjectName("SectionTitle")
            lay.addWidget(lab)
        lay.addWidget(hline(), 1, Qt.AlignVCenter)


class FormGrid(QGridLayout):
    """Rows of right-aligned 'Label:' + control pairs, two pairs per row like Prism."""

    def __init__(self, indent: int = 18):
        super().__init__()
        self.setContentsMargins(indent, 2, 0, 4)
        self.setHorizontalSpacing(8)
        self.setVerticalSpacing(6)
        self._row = 0

    def add(self, *pairs) -> None:
        col = 0
        for label, widget in pairs:
            if label is not None:
                lab = QLabel(label)
                lab.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if isinstance(widget, QWidget):
                    lab.setBuddy(widget)
                self.addWidget(lab, self._row, col)
            if widget is not None:
                if isinstance(widget, QWidget):
                    self.addWidget(widget, self._row, col + 1)
                else:
                    self.addLayout(widget, self._row, col + 1)
            col += 2
        self._row += 1

    def add_span(self, widget: QWidget, col: int = 0, span: int = 4) -> None:
        self.addWidget(widget, self._row, col, 1, span)
        self._row += 1


class ColorButton(QPushButton):
    colorChanged = Signal(str)

    def __init__(self, color: str = "#000000"):
        super().__init__()
        self._color = color
        self.setObjectName("ColorButton")
        self.setFixedSize(46, 24)
        self.clicked.connect(self._pick)
        self._refresh()

    def color(self) -> str:
        return self._color

    def set_color(self, c: str) -> None:
        self._color = c
        self._refresh()

    def _refresh(self) -> None:
        pm = QPixmap(QSize(30, 14) * 2)
        pm.setDevicePixelRatio(2)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QColor(0, 0, 0, 90))
        p.setBrush(QColor(self._color))
        p.drawRoundedRect(QRectF(0.5, 0.5, 29, 13), 3, 3)
        p.end()
        self.setIcon(QIcon(pm))
        self.setIconSize(QSize(30, 14))

    def _pick(self) -> None:
        c = QColorDialog.getColor(QColor(self._color), self, "Color")
        if c.isValid():
            self.set_color(c.name())
            self.colorChanged.emit(c.name())


class HelpButton(QToolButton):
    def __init__(self, topic: str = ""):
        super().__init__()
        self.setText("?")
        self.setObjectName("HelpButton")
        self.setFixedSize(20, 20)
        self.setToolTip("Help")
        self.topic = topic
        self.clicked.connect(self._open)

    def _open(self) -> None:
        from ..help_window import show_topic
        show_topic(self.topic)


def combo(items: list[tuple[str, object]], current=None) -> QComboBox:
    c = QComboBox()
    for label, data in items:
        c.addItem(label, data)
    if current is not None:
        set_combo(c, current)
    return c


def set_combo(c: QComboBox, data) -> None:
    i = c.findData(data)
    if i >= 0:
        c.setCurrentIndex(i)


def button_row(dialog: QDialog, topic: str, extra_left: list[QWidget] = (),
               apply: bool = False):
    """[?] [extra…]  stretch  [Apply] [Cancel] [OK] — OK is the default (blue) button."""
    row = QHBoxLayout()
    row.addWidget(HelpButton(topic))
    for w in extra_left:
        row.addWidget(w)
    row.addStretch(1)
    btn_apply = None
    if apply:
        btn_apply = QPushButton("Apply")
        row.addWidget(btn_apply)
    cancel = QPushButton("Cancel")
    cancel.clicked.connect(dialog.reject)
    ok = QPushButton("OK")
    ok.setDefault(True)
    ok.setAutoDefault(True)
    ok.clicked.connect(dialog.accept)
    row.addWidget(cancel)
    row.addWidget(ok)
    return row, ok, btn_apply


def tab_page() -> tuple[QWidget, QVBoxLayout]:
    """A section page's content widget and its layout."""
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 6, 0, 6)
    lay.setSpacing(2)
    return w, lay


class SectionDialog(QDialog):
    """ASTERISM's dialog frame: a section sidebar on the left (rounded rows under small
    group labels), the selected section on the right, Help / extras / Apply / Cancel / OK
    along the bottom. Dialogs never use a tab bar across the top."""

    sectionChanged = Signal(str)

    def __init__(self, title: str, help_topic: str, parent=None, apply: bool = False,
                 extra_left: list[QWidget] = (), sidebar_width: int = 196):
        super().__init__(parent)
        self.setWindowTitle(title)
        self._keys: list[str] = []
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        body = QHBoxLayout()
        body.setSpacing(0)
        side = QWidget()
        side.setObjectName("DialogSidebar")
        side.setAttribute(Qt.WA_StyledBackground, True)
        side.setFixedWidth(sidebar_width)
        sv = QVBoxLayout(side)
        sv.setContentsMargins(10, 12, 10, 10)
        self.sections = QListWidget()
        self.sections.setObjectName("DialogSections")
        self.sections.setItemDelegate(NavDelegate(self.sections))
        self.sections.setMouseTracking(True)
        self.sections.setIconSize(QSize(15, 15))
        self.sections.setAttribute(Qt.WA_MacShowFocusRect, False)
        sv.addWidget(self.sections)
        body.addWidget(side)
        right = QWidget()
        right.setObjectName("DialogPage")
        right.setAttribute(Qt.WA_StyledBackground, True)
        rv = QVBoxLayout(right)
        rv.setContentsMargins(22, 16, 22, 8)
        rv.setSpacing(6)
        self.page_title = QLabel()
        self.page_title.setObjectName("PageTitle")
        rv.addWidget(self.page_title)
        self.header = QVBoxLayout()           # optional controls above every page (e.g. a picker)
        self.header.setContentsMargins(0, 0, 0, 0)
        rv.addLayout(self.header)
        self.stack = QStackedWidget()
        rv.addWidget(self.stack, 1)
        self.footer = QVBoxLayout()           # optional controls below every page
        self.footer.setContentsMargins(0, 0, 0, 0)
        rv.addLayout(self.footer)
        body.addWidget(right, 1)
        outer.addLayout(body, 1)
        rule = hline()
        outer.addWidget(rule)
        row, self.ok, self.apply_button = button_row(self, help_topic, list(extra_left), apply)
        row.setContentsMargins(16, 10, 16, 12)
        outer.addLayout(row)
        self.sections.currentItemChanged.connect(self._picked)

    def add_group(self, name: str) -> None:
        it = QListWidgetItem(name)
        it.setFlags(Qt.ItemIsEnabled)
        f = QFont(self.sections.font())
        f.setPixelSize(11)
        f.setWeight(QFont.DemiBold)
        it.setFont(f)
        it.setForeground(theme.color("muted"))
        self.sections.addItem(it)

    def add_section(self, key: str, title: str, content: QWidget, icon_name: str = "circle") -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.viewport().setAutoFillBackground(False)
        content.setAutoFillBackground(False)
        scroll.setWidget(content)
        self.stack.addWidget(scroll)
        it = QListWidgetItem(icon(icon_name, "accent", selected=True), title)
        it.setData(Qt.UserRole, key)
        self.sections.addItem(it)
        self._keys.append(key)

    def show_section(self, key: str) -> None:
        for i in range(self.sections.count()):
            if self.sections.item(i).data(Qt.UserRole) == key:
                self.sections.setCurrentRow(i)
                return
        if self._keys:
            self.show_section(self._keys[0])

    def current_section(self) -> str | None:
        it = self.sections.currentItem()
        return it.data(Qt.UserRole) if it else None

    def _picked(self, it, _prev) -> None:
        if it is None or it.data(Qt.UserRole) is None:
            return
        key = it.data(Qt.UserRole)
        self.stack.setCurrentIndex(self._keys.index(key))
        self.page_title.setText(it.text())
        self.sectionChanged.emit(key)
