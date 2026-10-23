"""Results, Info and Layout sheets."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QAbstractItemView, QFormLayout, QLabel, QLineEdit,
                               QPlainTextEdit, QStyle, QStyledItemDelegate, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from . import theme
from ..doc.model import Analysis, InfoSheet
from .table_view import ROW_H, RowHeader


class _NoFocusDelegate(QStyledItemDelegate):
    def paint(self, p, option, index):
        option.state &= ~QStyle.State_HasFocus
        super().paint(p, option, index)


class ResultsSheet(QWidget):
    def __init__(self, analysis: Analysis, parent=None):
        super().__init__(parent)
        self.a = analysis
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addSpacing(8)
        self.tabs = theme.Tabs(name="ResultsTabs")
        lay.addWidget(self.tabs)
        analysis.changed.connect(self.refresh)
        theme.notifier.changed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        cur = self.tabs.currentIndex()
        while self.tabs.count():
            w = self.tabs.widget(0)
            self.tabs.removeTab(0)
            w.deleteLater()
        res = self.a.result
        for page in (res.pages if res else []):
            t = QTableWidget(len(page.rows), 1 + len(page.columns))
            t.setVerticalHeader(RowHeader(t))
            t.setItemDelegate(_NoFocusDelegate(t))
            t.setHorizontalHeaderLabels([page.first_column or page.title] + page.columns)
            t.setEditTriggers(QAbstractItemView.NoEditTriggers)
            t.setSelectionMode(QAbstractItemView.ContiguousSelection)
            t.setFrameShape(QTableWidget.NoFrame)
            t.setWordWrap(False)
            hh = t.horizontalHeader()
            hh.setDefaultAlignment(Qt.AlignCenter)
            t.setColumnWidth(0, 330 if len(page.columns) < 4 else 300)
            fm = hh.fontMetrics()
            for i, head in enumerate(page.columns):
                t.setColumnWidth(i + 1, max(190, fm.horizontalAdvance(head) + 28))
            bold = QFont(t.font())
            bold.setBold(True)
            sec_bg = theme.mix("field", "accent", 0.09)
            for r, (label, vals, style) in enumerate(page.rows):
                it = QTableWidgetItem(label)
                if style == "section":
                    it.setFont(bold)
                    it.setBackground(sec_bg)
                elif style == "row" and label:
                    it.setText("  " + label)
                t.setItem(r, 0, it)
                for c, v in enumerate(vals):
                    vi = QTableWidgetItem(v)
                    vi.setTextAlignment(Qt.AlignCenter)
                    t.setItem(r, c + 1, vi)
                if style == "section":
                    for c in range(1, t.columnCount()):
                        if not t.item(r, c):
                            t.setItem(r, c, QTableWidgetItem(""))
                        t.item(r, c).setBackground(sec_bg)
                t.setRowHeight(r, ROW_H)
            # value columns fit their contents (headers included), within sensible limits
            for i in range(1, t.columnCount()):
                t.resizeColumnToContents(i)
                t.setColumnWidth(i, min(max(t.columnWidth(i) + 16, 96), 260))
            t.resizeColumnToContents(0)
            t.setColumnWidth(0, min(max(t.columnWidth(0) + 24, 220), 420))
            self.tabs.addTab(t, page.title)
        if 0 <= cur < self.tabs.count():
            self.tabs.setCurrentIndex(cur)


class InfoSheetView(QWidget):
    def __init__(self, info: InfoSheet, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 22, 28, 22)
        title = QLabel("Constants")
        title.setObjectName("SectionTitle")
        lay.addWidget(title)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        for k, v in info.fields.items():
            e = QLineEdit(v)
            e.setMaximumWidth(420)
            e.textEdited.connect(lambda s, k=k: self._set_field(k, s))
            form.addRow(k + ":", e)
        lay.addLayout(form)
        lay.addSpacing(14)
        notes = QLabel("Notes")
        notes.setObjectName("SectionTitle")
        lay.addWidget(notes)
        ed = QPlainTextEdit(info.notes)
        ed.textChanged.connect(lambda: self._set_notes(ed.toPlainText()))
        self.info = info
        lay.addWidget(ed, 1)


    def _set_field(self, key: str, value: str) -> None:
        self.info.fields[key] = value
        if self.info.project is not None:
            self.info.project.touch()

    def _set_notes(self, text: str) -> None:
        if text != self.info.notes:
            self.info.notes = text
            if self.info.project is not None:
                self.info.project.touch()


class PlaceholderSheet(QWidget):
    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lab = QLabel(text)
        lab.setAlignment(Qt.AlignCenter)
        lab.setEnabled(False)
        lay.addWidget(lab)
