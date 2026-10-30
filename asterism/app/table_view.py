"""Data table sheet: one grid for all eight table types (SPEC §6).

Columns, left to right: row titles (if the table has them), X and X error (XY and
survival tables), then each data set's sub-columns. The header has a row with the data
set's name and its editable title, both spanning its sub-columns, plus a row of
sub-column labels when a data set has more than one (replicates, Mean/SD/N, subjects).
Excluded values stay visible, struck through in muted italics.

Keyboard, as in a spreadsheet: the arrows move between cells; ↑ from the first row goes up
into the data set titles (and editable sub-column titles), ↓ comes back down. While typing
into a cell or title, the arrows save it and move on (←/→ only when the edit started by
typing; after a double-click or F2 they move the text cursor).
"""

from __future__ import annotations

import math

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QKeySequence, QPainter, QPen
from PySide6.QtWidgets import (QAbstractItemDelegate, QAbstractItemView, QApplication,
                               QHeaderView, QLineEdit, QStyle, QStyledItemDelegate, QTableView)

from . import theme
from ..doc.commands import (CellsCommand, ExcludeCommand, SubTitleCommand, TableEditCommand,
                            TitleCommand)
from ..doc.model import Project, Table
from ..doc.table import Y_FORMATS

ROW_H = 20
SUB_H = 18

_ARROWS = {Qt.Key_Up: (-1, 0), Qt.Key_Down: (1, 0), Qt.Key_Left: (0, -1), Qt.Key_Right: (0, 1)}
_MODS = Qt.ShiftModifier | Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier


def _plain_arrow(e) -> tuple[int, int] | None:
    """(rows, cols) for an arrow key without modifiers (macOS adds the keypad flag; ignored)."""
    if e.modifiers() & _MODS:
        return None
    return _ARROWS.get(e.key())


class EntryEditor(QLineEdit):
    """Editor for a cell or a title. `typing`: the edit started with a typed character, so
    ←/→ also save and move (otherwise they move the text cursor). `on_arrow(dr, dc)` saves
    and moves; `on_cancel()` closes without saving (title editors only)."""

    def __init__(self, parent, typing: bool, on_arrow, on_cancel=None):
        super().__init__(parent)
        self.typing, self.on_arrow, self.on_cancel = typing, on_arrow, on_cancel

    def keyPressEvent(self, e):
        move = _plain_arrow(e)
        if move and (self.typing or move[1] == 0):
            self.on_arrow(*move)
            return
        if self.on_cancel and e.key() == Qt.Key_Escape:
            self.on_cancel()
            return
        if self.on_cancel and e.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.on_arrow(1, 0)
            return
        super().keyPressEvent(e)


def blend(a: QColor, b: QColor, t: float) -> QColor:
    return QColor(round(a.red() + (b.red() - a.red()) * t),
                  round(a.green() + (b.green() - a.green()) * t),
                  round(a.blue() + (b.blue() - a.blue()) * t))


_SUP = str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻")


def fmt_cell(v, display: bool = False) -> str:
    """A cell's text. Shown (display=True), very large or very small numbers read as powers of
    ten (1.503×10¹³); edited, they stay plain numbers that can be typed back."""
    if isinstance(v, str):
        return v
    if display and v != 0 and (abs(v) >= 1e7 or abs(v) < 1e-4):
        e = math.floor(math.log10(abs(v)))
        m = f"{v / 10 ** e:.4f}".rstrip("0").rstrip(".")
        return f"{m}×10{str(e).translate(_SUP)}"
    return f"{v:.10g}"


def parse_cell(table: Table, key, text: str):
    """Text typed or pasted into a cell → stored value, or raise ValueError."""
    s = text.strip()
    if s == "":
        return None
    if key == "row":
        return s
    if key == "x" and table.x_format == "date":
        from ..doc.dates import parse
        d = parse(s)
        if d is not None:
            return d
    try:
        v = float(s.replace(",", "."))
    except ValueError:
        if table.table_type == "multivar" and key not in ("x", "xerr"):
            return s
        raise
    if not table.accepts(key, v):
        raise ValueError(s)
    return v


def column_keys(t: Table) -> list:
    keys = []
    if t.has_row_titles:
        keys.append("row")
    if t.has_x():
        keys.append("x")
        if t.x_format == "numbers_err":
            keys.append("xerr")
    keys += list(range(t.nflat))
    return keys


class TableModel(QAbstractTableModel):
    def __init__(self, table: Table, project: Project):
        super().__init__()
        self.t, self.project = table, project
        self.keys = column_keys(table)
        self._shape = self._signature()
        self._rows = self._wanted_rows()
        table.changed.connect(self._on_changed)

    def _signature(self):
        t = self.t
        return (t.table_type, t.y_format, t.replicates, t.x_format, t.has_row_titles, t.ncols)

    def _wanted_rows(self) -> int:
        return max(200, self.t.nrows_used() + 100)

    def _on_changed(self) -> None:
        if self._signature() != self._shape:      # columns changed: rebuild the grid
            self.beginResetModel()
            self._shape = self._signature()
            self.keys = column_keys(self.t)
            self._rows = self._wanted_rows()
            self.endResetModel()
            return
        want = self._wanted_rows()
        if want > self._rows:
            self.beginInsertRows(QModelIndex(), self._rows, want - 1)
            self._rows = want
            self.endInsertRows()
        self.dataChanged.emit(self.index(0, 0), self.index(self._rows - 1, len(self.keys) - 1))
        self.headerDataChanged.emit(Qt.Horizontal, 0, len(self.keys) - 1)

    def key(self, col: int):
        return self.keys[col]

    def col_of(self, key) -> int:
        return self.keys.index(key)

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else self._rows

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.keys)

    def data(self, idx, role=Qt.DisplayRole):
        key = self.keys[idx.column()]
        if role in (Qt.DisplayRole, Qt.EditRole):
            v = self.t.get(idx.row(), key)
            if key == "x" and self.t.x_format == "date" and isinstance(v, (int, float)):
                from ..doc.dates import fmt
                return fmt(v)
            return "" if v is None else fmt_cell(v, display=role == Qt.DisplayRole)
        if role == Qt.TextAlignmentRole:
            v = self.t.get(idx.row(), key)
            left = key == "row" or isinstance(v, str)
            return int((Qt.AlignLeft if left else Qt.AlignRight) | Qt.AlignVCenter)
        if role == Qt.UserRole:                    # excluded?
            return self.t.is_excluded(idx.row(), key)
        return None

    def setData(self, idx, value, role=Qt.EditRole) -> bool:
        if role != Qt.EditRole:
            return False
        key = self.keys[idx.column()]
        try:
            v = parse_cell(self.t, key, str(value))
        except ValueError:
            QApplication.beep()
            return False
        if v == self.t.get(idx.row(), key):
            return True
        self.project.undo.push(CellsCommand(self.t, [(idx.row(), key, v)]))
        return True

    def flags(self, idx):
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Vertical:
            return str(section + 1)
        return None


class TableHeader(QHeaderView):
    """Data set name over its editable title (both spanning the data set's sub-columns),
    then sub-column labels when a data set has several."""

    def __init__(self, view: "DataTableSheet"):
        super().__init__(Qt.Horizontal, view)
        self.view = view
        self.setSectionsClickable(True)
        self.setHighlightSections(True)
        self.setDefaultSectionSize(84)
        self.setMinimumSectionSize(36)
        self._editor: QLineEdit | None = None
        # Names and titles are centred over all of a data set's sub-columns, but Qt only
        # repaints from the resized section rightwards: repaint everything, or the
        # sub-columns to the left keep the text at its old position.
        self.sectionResized.connect(self._span_resized)

    def _span_resized(self, *_) -> None:
        self.viewport().update()

    @property
    def t(self) -> Table:
        return self.view.t

    def has_sub_row(self) -> bool:
        return self.t.width() > 1

    def sizeHint(self):
        s = super().sizeHint()
        s.setHeight(ROW_H * 2 + (SUB_H if self.has_sub_row() else 0))
        return s

    def _span(self, idx: int) -> tuple[int, int]:
        """Sections covered by the data set (or special column) at section idx."""
        key = self.view.model().key(idx)
        if not isinstance(key, int):
            return idx, idx
        ds, sub = self.t.split(key)
        return idx - sub, idx - sub + self.t.width() - 1

    def _span_rect(self, idx: int, top: int, h: int) -> QRect:
        a, b = self._span(idx)
        x0 = self.sectionViewportPosition(a)
        x1 = self.sectionViewportPosition(b) + self.sectionSize(b)
        return QRect(x0, top, x1 - x0, h)

    def paintSection(self, p: QPainter, rect: QRect, idx: int) -> None:
        t, key = self.t, self.view.model().key(idx)
        head_bg, grid = theme.color("sidebar"), theme.mix("field", "text", 0.13)
        text, muted = theme.color("text"), theme.color("muted")
        cur = self.view.currentIndex()
        a, b = self._span(idx)
        sel = cur.isValid() and a <= cur.column() <= b
        sub_row = self.has_sub_row()
        p.save()
        p.setClipRect(rect)
        r1 = self._span_rect(idx, 0, ROW_H)
        r2 = self._span_rect(idx, ROW_H, ROW_H)
        p.fillRect(rect, theme.color("field"))
        p.fillRect(QRect(rect.x(), 0, rect.width(), ROW_H),
                   theme.mix(head_bg, "accent", 0.22) if sel else head_bg)
        small = QFont(self.font())
        small.setPointSizeF(small.pointSizeF() - 1)
        if key == "row":
            name, title = "Row titles", ""
        elif key == "x":
            name, title = "X", ""
        elif key == "xerr":
            name, title = "X error", ""
        else:
            ds, _ = t.split(key)
            name, title = t.group_name(ds), t.titles[ds]
        head = self.view.head
        on_title = isinstance(key, int) and head == ("title", t.split(key)[0])
        on_sub = isinstance(key, int) and head == ("sub", idx)
        p.setFont(small)
        p.setPen(text if sel else muted)
        p.drawText(r1, Qt.AlignCenter, name)
        p.setFont(self.font())
        if on_title:
            p.fillRect(r2, theme.mix("field", "accent", 0.12))
        if isinstance(key, int):
            p.setPen(text if title else theme.mix("field", "muted", 0.7))
            p.drawText(r2.adjusted(4, 0, -4, 0), Qt.AlignCenter, title or "Title")
        if sub_row:
            r3 = QRect(rect.x(), ROW_H * 2, rect.width(), SUB_H)
            p.fillRect(r3, theme.mix("field", "accent", 0.12) if on_sub else theme.mix("field", "sidebar", 0.5))
            if isinstance(key, int):
                ds, sub = t.split(key)
                p.setFont(small)
                p.setPen(muted)
                p.drawText(r3, Qt.AlignCenter, t.sub_label(ds, sub))
        p.setPen(grid)
        # vertical rules: full height at span edges, sub-row only inside a span
        if idx == b:
            p.drawLine(rect.topRight(), rect.bottomRight())
        elif sub_row:
            p.drawLine(rect.right(), ROW_H * 2, rect.right(), rect.bottom())
        p.drawLine(rect.left(), ROW_H, rect.right(), ROW_H)
        if sub_row:
            p.drawLine(rect.left(), ROW_H * 2, rect.right(), ROW_H * 2)
        p.drawLine(rect.bottomLeft(), rect.bottomRight())
        if on_title or on_sub:          # the same 2 px outline as the current cell
            p.setPen(QPen(theme.color("accent"), 2))
            p.drawRect((r2 if on_title else QRect(rect.x(), ROW_H * 2, rect.width(), SUB_H)).adjusted(1, 1, -1, -1))
        p.restore()

    def head_at(self, pos):
        """("title", data set) or ("sub", column) under a point in the header, or None."""
        idx = self.logicalIndexAt(pos)
        key = self.view.model().key(idx) if idx >= 0 else None
        if not isinstance(key, int):
            return None
        if ROW_H <= pos.y() < ROW_H * 2:
            return ("title", self.t.split(key)[0])
        if pos.y() >= ROW_H * 2 and self.view.subs_editable():
            return ("sub", idx)
        return None

    def head_rect(self, head) -> QRect:
        kind, n = head
        if kind == "title":
            return self._span_rect(self.view.col_of_set(n), ROW_H, ROW_H)
        return QRect(self.sectionViewportPosition(n), ROW_H * 2, self.sectionSize(n), SUB_H)

    def mousePressEvent(self, e):
        head = self.head_at(e.position().toPoint())
        if head is None:
            self.view.leave_head()
            super().mousePressEvent(e)
            return
        self.view.set_head(head, scroll=False)
        self.view.setFocus()

    def mouseDoubleClickEvent(self, e):
        head = self.head_at(e.position().toPoint())
        if head is None:
            super().mouseDoubleClickEvent(e)
            return
        self.view.set_head(head, scroll=False)
        self.edit_head(head)

    def edit_head(self, head, typed: str | None = None) -> None:
        """Edit a title in place; `typed` replaces it (the edit started by typing)."""
        if self._editor is not None:
            return
        rect = self.head_rect(head)
        old = self.view.head_text(head)
        state = {"open": True}

        def close(commit: bool, move=None):
            if not state["open"]:
                return
            state["open"] = False
            self._editor = None
            new = ed.text().strip()
            ed.hide()
            ed.deleteLater()
            if commit:
                self.view.set_head_text(head, new)
            self.view.setFocus()
            if move:
                self.view.head_move(*move)

        ed = EntryEditor(self.viewport(), typed is not None, lambda dr, dc: close(True, (dr, dc)),
                         lambda: close(False))
        ed.setAlignment(Qt.AlignCenter)
        ed.setFrame(False)
        ed.setGeometry(rect.adjusted(2, 2, -2, -2))
        if typed is None:
            ed.setText(old)
            ed.selectAll()
        else:
            ed.setText(typed)
        ed.show()
        ed.setFocus()
        ed.editingFinished.connect(lambda: close(True))
        self._editor = ed

    def edit_title(self, idx: int) -> None:
        self.edit_head(("title", self.t.split(self.view.model().key(idx))[0]))


class RowHeader(QHeaderView):
    def __init__(self, parent=None):
        super().__init__(Qt.Vertical, parent)
        self.setMinimumSectionSize(14)
        self.setDefaultSectionSize(ROW_H)
        self.setSectionResizeMode(QHeaderView.Fixed)
        self.setFixedWidth(40)

    def paintSection(self, p: QPainter, rect: QRect, idx: int) -> None:
        cur = self.parent().currentIndex() if self.parent() else None
        is_cur = cur is not None and cur.isValid() and cur.row() == idx
        bg = theme.color("sidebar")
        if is_cur:
            bg = theme.mix(bg, "accent", 0.22)
        p.save()
        p.fillRect(rect, bg)
        p.setPen(theme.mix("field", "text", 0.13))
        p.drawLine(rect.topRight(), rect.bottomRight())
        p.drawLine(rect.bottomLeft(), rect.bottomRight())
        f = QFont(self.font())
        f.setPointSizeF(f.pointSizeF() - 1)
        p.setFont(f)
        p.setPen(theme.color("text") if is_cur else theme.color("muted"))
        p.drawText(rect, Qt.AlignCenter, str(idx + 1))
        p.restore()


class CellDelegate(QStyledItemDelegate):
    """Plain cells; row-title and X columns lightly tinted; excluded values struck through
    in muted italics; the current cell gets a 2 px accent outline, as in a spreadsheet."""

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        if index.data(Qt.UserRole):
            option.font.setItalic(True)
            option.font.setStrikeOut(True)
            option.palette.setColor(option.palette.ColorRole.Text, theme.color("muted"))
            option.palette.setColor(option.palette.ColorRole.HighlightedText, theme.color("muted"))

    def paint(self, p, option, index):
        option.state &= ~QStyle.State_HasFocus
        key = index.model().key(index.column())
        if key in ("row", "x", "xerr") and not (option.state & QStyle.State_Selected):
            p.fillRect(option.rect, theme.mix("field", "sidebar", 0.45))
        super().paint(p, option, index)
        view = self.parent()
        if view is not None and index == view.currentIndex() and view.head is None:
            p.save()
            p.setPen(QPen(theme.color("accent"), 2))
            p.drawRect(option.rect.adjusted(1, 1, -1, -1))
            p.restore()

    def createEditor(self, parent, option, index):
        view = self.parent()
        ed = EntryEditor(parent, getattr(view, "_typing", True), lambda dr, dc: view.editor_arrow(ed, dr, dc))
        ed.setFrame(False)
        key = index.model().key(index.column())
        ed.setAlignment((Qt.AlignLeft if key == "row" else Qt.AlignRight) | Qt.AlignVCenter)
        return ed


class DataTableSheet(QTableView):
    cellChanged = Signal(int, int)
    head = None           # keyboard focus in the header: ("title", data set) or ("sub", column)
    _typing = True        # the next cell edit starts from a typed character

    def __init__(self, table: Table, project: Project, parent=None):
        super().__init__(parent)
        self.t, self.project = table, project
        self.setModel(TableModel(table, project))
        self.setHorizontalHeader(TableHeader(self))
        self.setVerticalHeader(RowHeader(self))
        self.setItemDelegate(CellDelegate(self))
        self.setEditTriggers(QAbstractItemView.AnyKeyPressed | QAbstractItemView.DoubleClicked
                             | QAbstractItemView.EditKeyPressed)
        self.setSelectionMode(QAbstractItemView.ContiguousSelection)
        self.setFrameShape(QTableView.NoFrame)
        self.setCornerButtonEnabled(False)
        self.setWordWrap(False)
        self.setTabKeyNavigation(True)
        self.model().modelReset.connect(self._after_reset)
        self.selectionModel().currentChanged.connect(
            lambda cur, _: (self.verticalHeader().viewport().update(),
                            self.horizontalHeader().viewport().update(),
                            self.cellChanged.emit(cur.row(), cur.column())))
        self._size_columns()
        self.setCurrentIndex(self.model().index(0, self._first_data_col()))

    def _after_reset(self) -> None:
        self.head = None
        self.horizontalHeader().updateGeometry()
        self.updateGeometries()
        self._size_columns()
        self.setCurrentIndex(self.model().index(0, self._first_data_col()))

    def _first_data_col(self) -> int:
        keys = self.model().keys
        return next((i for i, k in enumerate(keys) if isinstance(k, int)), 0)

    def _size_columns(self) -> None:
        w = self.t.width()
        for i, key in enumerate(self.model().keys):
            if key == "row":
                self.setColumnWidth(i, 130)
            elif key in ("x", "xerr"):
                self.setColumnWidth(i, 72)
            else:
                self.setColumnWidth(i, 84 if w == 1 else 66)

    # --- helpers --------------------------------------------------------------------------

    def key(self, col: int):
        return self.model().key(col)

    def selected_cells(self) -> list[tuple[int, object]]:
        idx = self.selectedIndexes() or [self.currentIndex()]
        return [(i.row(), self.key(i.column())) for i in idx if i.isValid()]

    def selected_rows(self) -> list[int]:
        return sorted({r for r, _ in self.selected_cells()})

    def selected_sets(self) -> list[int]:
        return sorted({self.t.split(k)[0] for _, k in self.selected_cells() if isinstance(k, int)})

    # --- keyboard focus in the header (data set titles, sub-column titles) ---------------

    def subs_editable(self) -> bool:
        return self.horizontalHeader().has_sub_row() and Y_FORMATS[self.t.y_format] is None

    def col_of_set(self, ds: int) -> int:
        return self.model().col_of(self.t.flat(ds, 0))

    def set_head(self, head, scroll: bool = True) -> None:
        self.head = head
        col = self.currentIndex().column()
        if head[0] == "sub":
            col = head[1]
        elif not (isinstance(self.key(col), int) and self.t.split(self.key(col))[0] == head[1]):
            col = self.col_of_set(head[1])
        # The current cell follows along in row 1, so ↓ lands there and the column stays lit.
        auto = self.hasAutoScroll()
        self.setAutoScroll(scroll)
        self.setCurrentIndex(self.model().index(0, col))
        self.setAutoScroll(auto)
        if scroll:
            self.scrollTo(self.model().index(0, col))
        self.horizontalHeader().viewport().update()
        self.viewport().update()

    def leave_head(self) -> None:
        if self.head is not None:
            self.head = None
            self.horizontalHeader().viewport().update()
            self.viewport().update()

    def _enter_head(self, col: int) -> None:
        """↑ from row 1 of a data set column."""
        self.set_head(("sub", col) if self.subs_editable() else ("title", self.t.split(self.key(col))[0]))

    def head_text(self, head) -> str:
        kind, n = head
        if kind == "title":
            return self.t.titles[n]
        ds, sub = self.t.split(self.key(n))
        return self.t.sub_titles[ds][sub]

    def set_head_text(self, head, new: str) -> None:
        if new == self.head_text(head):
            return
        kind, n = head
        if kind == "title":
            self.project.undo.push(TitleCommand(self.t, n, new))
        else:
            ds, sub = self.t.split(self.key(n))
            self.project.undo.push(SubTitleCommand(self.t, ds, sub, new))

    def head_move(self, dr: int, dc: int) -> None:
        kind, n = self.head
        keys = self.model().keys
        if dc:
            if kind == "title":
                self.set_head(("title", min(max(n + dc, 0), self.t.ncols - 1)))
            elif 0 <= n + dc < len(keys) and isinstance(keys[n + dc], int):
                self.set_head(("sub", n + dc))
        elif dr < 0:
            if kind == "sub":
                self.set_head(("title", self.t.split(keys[n])[0]))
        elif kind == "title" and self.subs_editable():
            self.set_head(("sub", self.currentIndex().column()))
        else:
            col = self.currentIndex().column()
            self.leave_head()
            self.setCurrentIndex(self.model().index(0, col))

    def _head_key(self, e) -> bool:
        move = _plain_arrow(e)
        k = e.key()
        if k == Qt.Key_Tab:
            move = (0, 1)
        elif k == Qt.Key_Backtab:
            move = (0, -1)
        elif k in (Qt.Key_Return, Qt.Key_Enter):
            move = (1, 0)
        if move:
            self.head_move(*move)
        elif k == Qt.Key_Escape:
            self.head_move(1, 0) if self.head[0] == "sub" else self.leave_head()
        elif k == Qt.Key_F2:
            self.horizontalHeader().edit_head(self.head)
        elif k in (Qt.Key_Delete, Qt.Key_Backspace):
            self.set_head_text(self.head, "")
        elif e.text() and e.text().isprintable() and not e.modifiers() & (Qt.ControlModifier | Qt.MetaModifier):
            self.horizontalHeader().edit_head(self.head, typed=e.text())
        else:
            return False
        return True

    def editor_arrow(self, editor, dr: int, dc: int) -> None:
        """An arrow key in a cell editor: save the value and move."""
        i = self.currentIndex()
        self.commitData(editor)
        self.closeEditor(editor, QAbstractItemDelegate.NoHint)
        if dr < 0 and i.row() == 0 and isinstance(self.key(i.column()), int):
            self._enter_head(i.column())
            return
        r = min(max(i.row() + dr, 0), self.model().rowCount() - 1)
        c = min(max(i.column() + dc, 0), self.model().columnCount() - 1)
        self.setCurrentIndex(self.model().index(r, c))

    def mousePressEvent(self, e):
        self.leave_head()
        super().mousePressEvent(e)

    def mouseDoubleClickEvent(self, e):
        self._typing = False
        super().mouseDoubleClickEvent(e)

    # Enter commits and moves down, like a spreadsheet.
    def closeEditor(self, editor, hint):
        super().closeEditor(editor, hint)
        if hint == QAbstractItemDelegate.SubmitModelCache:
            i = self.currentIndex()
            self.setCurrentIndex(self.model().index(i.row() + 1, i.column()))

    def keyPressEvent(self, e):
        editing = self.state() == QAbstractItemView.EditingState
        if self.head is not None and not editing:
            if self._head_key(e):
                return
            self.leave_head()
        if not editing:
            self._typing = e.key() != Qt.Key_F2
        cur = self.currentIndex()
        if not editing and _plain_arrow(e) == (-1, 0) and cur.row() == 0 and isinstance(self.key(cur.column()), int):
            self._enter_head(cur.column())
        elif not editing and e.key() == Qt.Key_F2:      # edit what's there (on macOS too)
            self.edit(cur)
        elif e.matches(QKeySequence.Copy):
            self.copy()
        elif e.matches(QKeySequence.Paste):
            self.paste()
        elif e.matches(QKeySequence.Cut):
            self.copy()
            self.clear_selection()
        elif e.key() in (Qt.Key_Delete, Qt.Key_Backspace) and self.state() != QAbstractItemView.EditingState:
            self.clear_selection()
        elif e.key() in (Qt.Key_Return, Qt.Key_Enter) and self.state() != QAbstractItemView.EditingState:
            i = self.currentIndex()
            self.setCurrentIndex(self.model().index(i.row() + 1, i.column()))
        else:
            super().keyPressEvent(e)

    def _sel_box(self):
        idx = self.selectedIndexes() or [self.currentIndex()]
        rows = [i.row() for i in idx]
        cols = [i.column() for i in idx]
        return min(rows), max(rows), min(cols), max(cols)

    # --- clipboard --------------------------------------------------------------------------

    def copy(self) -> None:
        r0, r1, c0, c1 = self._sel_box()
        lines = []
        for r in range(r0, r1 + 1):
            vals = [self.t.get(r, self.key(c)) for c in range(c0, c1 + 1)]
            lines.append("\t".join("" if v is None else fmt_cell(v) for v in vals))
        QGuiApplication.clipboard().setText("\n".join(lines))

    def paste(self) -> None:
        text = QGuiApplication.clipboard().text()
        if not text:
            return
        i = self.currentIndex()
        ncols = self.model().columnCount()
        changes = []
        for dr, line in enumerate(text.rstrip("\n").split("\n")):
            for dc, cell in enumerate(line.rstrip("\r").split("\t")):
                r, c = i.row() + dr, i.column() + dc
                if c >= ncols:
                    continue
                key = self.key(c)
                try:
                    changes.append((r, key, parse_cell(self.t, key, cell)))
                except ValueError:
                    continue
        if changes:
            self.project.undo.push(CellsCommand(self.t, changes, "Paste"))

    def clear_selection(self) -> None:
        changes = [(r, k, None) for r, k in self.selected_cells() if self.t.get(r, k) is not None]
        if changes:
            self.project.undo.push(CellsCommand(self.t, changes, "Clear"))

    # --- structure (undoable; linked graphs and analyses follow) ---------------------------

    def _edit(self, mutate, text: str) -> None:
        self.project.undo.push(TableEditCommand(self.project, self.t, mutate, text))

    def insert_rows(self) -> None:
        rows = self.selected_rows() or [0]
        at, n = rows[0], len(rows)
        self._edit(lambda t: t.insert_rows(at, n), "Insert Row" if n == 1 else "Insert Rows")

    def delete_rows(self) -> None:
        rows = self.selected_rows()
        if rows:
            self._edit(lambda t: t.delete_rows(rows), "Delete Row" if len(rows) == 1 else "Delete Rows")

    def insert_sets(self) -> None:
        sets = self.selected_sets() or [0]
        at, n = sets[0], len(sets)
        self._edit(lambda t: t.insert_sets(at, n), "Insert Data Set" if n == 1 else "Insert Data Sets")

    def delete_sets(self) -> None:
        sets = self.selected_sets()
        if sets and len(sets) < self.t.ncols:
            self._edit(lambda t: t.delete_sets(sets),
                       "Delete Data Set" if len(sets) == 1 else "Delete Data Sets")

    def toggle_exclude(self) -> None:
        cells = [(r, k) for r, k in self.selected_cells()
                 if (isinstance(k, int) or (k == "x" and self.t.has_x())) and self.t.get(r, k) is not None]
        if not cells:
            return
        flag = not all(self.t.is_excluded(r, k) for r, k in cells)
        self.project.undo.push(ExcludeCommand(self.t, cells, flag))
