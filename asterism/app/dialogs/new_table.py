"""New Table dialog (also the start screen) and the Table Format dialog.

Table types in the section sidebar; each page explains the type in a sentence, offers
its entry formats, and previews the empty table's columns. SPEC §6, §2.1.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QFont, QPainter
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QHBoxLayout, QLabel,
                               QRadioButton, QSpinBox, QVBoxLayout, QWidget)

from ...doc.table import (SET_NOUN, SUMMARY_FORMATS, TABLE_TYPES, TYPE_NAMES, TYPE_X,
                          Y_FORMAT_NAMES, Y_FORMATS, ALWAYS_ROW_TITLES, TYPE_Y_FORMATS)
from .. import theme
from .common import FormGrid, Section, SectionDialog, tab_page

TYPE_ICON = {"xy": "chart.xyaxis.line", "column": "chart.bar", "grouped": "square.grid.3x2",
             "contingency": "tablecells", "survival": "heart.text.square", "parts": "chart.pie",
             "multivar": "list.bullet.rectangle", "nested": "square.stack.3d.down.right"}

TYPE_HELP = {
    "xy": "Each row has an X value (time, dose, concentration) and one or more Y data sets. "
          "For curves, regression and correlation.",
    "column": "Each column is a group, with its values stacked down the column. For t tests, "
              "one-way ANOVA, descriptive statistics and column graphs.",
    "grouped": "Rows and columns are two grouping factors (for example genotype × treatment). "
               "For two-way ANOVA and grouped graphs.",
    "contingency": "Counts of subjects in each combination of group (rows) and outcome "
                   "(columns). For chi-square and Fisher's exact tests.",
    "survival": "One row per subject: the time in X, and 1 (event) or 0 (censored) in the "
                "subject's group column. For Kaplan-Meier curves and log-rank tests.",
    "parts": "Values that add up to a whole, one per row. For fractions of the total and pie "
             "or donut charts.",
    "multivar": "One row per observation, one column per variable (numbers or text). For "
                "bubble and scatter graphs that map variables to position, size and colour.",
    "nested": "Groups, each split into subjects (for example animals) with several "
              "measurements per subject. For nested t tests and nested ANOVA.",
}


class TablePreview(QWidget):
    """A sketch of the empty table's columns for the chosen type and format."""

    def __init__(self):
        super().__init__()
        self.setFixedHeight(150)
        self.fmt: dict = {}
        self.table_type = "column"

    def set_format(self, table_type: str, fmt: dict) -> None:
        self.table_type, self.fmt = table_type, fmt
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        tt, f = self.table_type, self.fmt
        yf = f.get("y_format", TYPE_Y_FORMATS[tt][0])
        labels = Y_FORMATS[yf]
        n = f.get("replicates", 3) if labels is None else len(labels)
        sub = ([f"{'Subj' if tt == 'nested' else 'Rep'} {i + 1}" for i in range(n)]
               if labels is None else labels)
        cols: list[tuple[str, str, int]] = []      # (header, sub label, span group)
        if tt in ALWAYS_ROW_TITLES or f.get("row_titles"):
            cols.append(("Row titles", "", -1))
        if tt in TYPE_X:
            cols.append(("X", "", -2))
            if f.get("x_format") == "numbers_err":
                cols.append(("X error", "", -3))
        for ds in range(2):
            for s in range(n if len(sub) > 1 else 1):
                cols.append((f"{SET_NOUN[tt]} {'AB'[ds]}", sub[s] if len(sub) > 1 else "", ds))
        cw = min(78.0, (self.width() - 4) / max(len(cols), 1))
        rh = 18.0
        grid, head, field = (theme.mix("field", "text", 0.22), theme.color("sidebar"),
                             theme.color("field"))
        small = QFont(self.font())
        small.setPointSizeF(small.pointSizeF() - 2)
        p.setFont(small)
        has_sub = any(c[1] for c in cols)
        hrows = 2 if has_sub else 1
        x = 2.0
        i = 0
        while i < len(cols):
            name, _s, grp = cols[i]
            j = i
            while j + 1 < len(cols) and cols[j + 1][2] == grp and grp >= 0:
                j += 1
            span = QRectF(x, 2, cw * (j - i + 1), rh)
            p.fillRect(span, head)
            p.setPen(grid)
            p.drawRect(span)
            p.setPen(theme.color("text"))
            p.drawText(span, Qt.AlignCenter, name)
            for k in range(i, j + 1):
                cx = x + cw * (k - i)
                if has_sub:
                    r = QRectF(cx, 2 + rh, cw, rh)
                    p.fillRect(r, theme.mix("field", "sidebar", 0.5))
                    p.setPen(grid)
                    p.drawRect(r)
                    p.setPen(theme.color("muted"))
                    p.drawText(r, Qt.AlignCenter, cols[k][1])
                for row in range(5):
                    r = QRectF(cx, 2 + rh * (hrows + row), cw, rh)
                    p.fillRect(r, field if grp >= 0 else theme.mix("field", "sidebar", 0.45))
                    p.setPen(grid)
                    p.drawRect(r)
            x += cw * (j - i + 1)
            i = j + 1
        p.end()


class FormatOptions(QWidget):
    """Entry-format choices for one table type."""

    changed = Signal()

    def __init__(self, table_type: str):
        super().__init__()
        self.table_type = tt = table_type
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)
        self.x_err = None
        self.row_titles = None
        self.reps = None
        self.summary_combo = None
        self.g_y = QButtonGroup(self)
        if tt == "xy":
            v.addWidget(Section("X values"))
            g = FormGrid()
            self.x_num = QRadioButton("Numbers")
            self.x_err = QRadioButton("Numbers with error bars (X ± error)")
            self.x_date = QRadioButton("Dates (or dates and times)")
            self.x_num.setChecked(True)
            g.add((None, self.x_num))
            g.add((None, self.x_err))
            g.add((None, self.x_date))
            self.row_titles = QCheckBox("Add a row-title column")
            g.add((None, self.row_titles))
            v.addLayout(g)
        formats = TYPE_Y_FORMATS[tt]
        if len(formats) > 1 or tt == "nested":
            v.addWidget(Section("Y values" if tt == "xy" else "Values"))
            g = FormGrid()
            if "single" in formats:
                r = QRadioButton("One value per cell" if tt != "column"
                                 else "Raw values, stacked down each column")
                r.setProperty("fmt", "single")
                r.setChecked(True)
                self.g_y.addButton(r)
                g.add((None, r))
            if "replicates" in formats:
                if tt == "nested":
                    self.reps = QSpinBox()
                    self.reps.setRange(1, 50)
                    self.reps.setValue(4)
                    g.add(("Subjects per group:", self.reps))
                else:
                    r = QRadioButton("Replicate values side by side")
                    r.setProperty("fmt", "replicates")
                    self.g_y.addButton(r)
                    self.reps = QSpinBox()
                    self.reps.setRange(2, 50)
                    self.reps.setValue(3)
                    row = QWidget()
                    h = QHBoxLayout(row)
                    h.setContentsMargins(0, 0, 0, 0)
                    h.addWidget(r)
                    h.addWidget(self.reps)
                    h.addWidget(QLabel("replicates"))
                    h.addStretch(1)
                    g.add((None, row))
            summaries = [f for f in formats if f in SUMMARY_FORMATS]
            if summaries:
                r = QRadioButton("Mean and error calculated elsewhere:")
                r.setProperty("fmt", "summary")
                self.g_y.addButton(r)
                self.summary_combo = QComboBox()
                for f in ["mean_sd_n", "mean_sem_n", "mean_cv_n", "mean_sd", "mean_sem", "mean_cv",
                          "mean_pm", "mean_limits"]:
                    if f in summaries:
                        self.summary_combo.addItem(Y_FORMAT_NAMES[f], f)
                row = QWidget()
                h = QHBoxLayout(row)
                h.setContentsMargins(0, 0, 0, 0)
                h.addWidget(r)
                h.addWidget(self.summary_combo)
                h.addStretch(1)
                g.add((None, row))
                note = QLabel("Entering N lets graphs switch between SD, SEM and confidence "
                              "intervals, and lets analyses use the sample size.")
                note.setWordWrap(True)
                note.setEnabled(False)
                g.add_span(note, 1, 3)
            v.addLayout(g)
        elif tt in ("contingency", "survival", "parts", "multivar"):
            note = QLabel({"contingency": "Enter whole-number counts.",
                           "survival": "Enter 1 for an event (e.g. death) and 0 for a censored "
                                       "subject (lost to follow-up or still event-free at the end).",
                           "parts": "Enter each part's value; ASTERISM works out fractions of the total.",
                           "multivar": "Columns can hold numbers or text (e.g. sex, genotype)."}[tt])
            note.setWordWrap(True)
            note.setEnabled(False)
            v.addWidget(note)
        for w in self.findChildren(QRadioButton):
            w.toggled.connect(self.changed)
        for w in self.findChildren(QSpinBox):
            w.valueChanged.connect(self.changed)
        for w in self.findChildren(QComboBox):
            w.currentIndexChanged.connect(self.changed)
        for w in self.findChildren(QCheckBox):
            w.toggled.connect(self.changed)

    def values(self) -> dict:
        tt = self.table_type
        out: dict = {}
        b = self.g_y.checkedButton()
        choice = b.property("fmt") if b else TYPE_Y_FORMATS[tt][0]
        if choice == "summary":
            out["y_format"] = self.summary_combo.currentData()
        else:
            out["y_format"] = choice
        if out["y_format"] == "replicates" and self.reps is not None:
            out["replicates"] = self.reps.value()
        if tt == "xy":
            out["x_format"] = ("numbers_err" if self.x_err.isChecked() else
                               "date" if self.x_date.isChecked() else "numbers")
            out["row_titles"] = self.row_titles.isChecked()
        return out

    def set_values(self, y_format: str, replicates: int, x_format: str, row_titles: bool) -> None:
        if self.table_type == "xy":
            {"numbers_err": self.x_err, "date": self.x_date}.get(x_format, self.x_num).setChecked(True)
            self.row_titles.setChecked(row_titles)
        for b in self.g_y.buttons():
            fmt = b.property("fmt")
            if fmt == y_format or (fmt == "summary" and y_format in SUMMARY_FORMATS):
                b.setChecked(True)
        if self.summary_combo is not None and y_format in SUMMARY_FORMATS:
            self.summary_combo.setCurrentIndex(self.summary_combo.findData(y_format))
        if self.reps is not None and y_format == "replicates":
            self.reps.setValue(replicates)


class NewTableDialog(SectionDialog):
    def __init__(self, parent=None, start: bool = False, table_type: str = "column"):
        super().__init__("New Data Table", "New table", parent)
        if start:
            self.setWindowTitle("Start a New Project")
        self.options: dict[str, FormatOptions] = {}
        self.preview = TablePreview()
        self.add_group("Table type")
        for tt in TABLE_TYPES:
            page, pl = tab_page()
            help_ = QLabel(TYPE_HELP[tt])
            help_.setWordWrap(True)
            pl.addWidget(help_)
            pl.addSpacing(6)
            opts = FormatOptions(tt)
            opts.changed.connect(self._refresh_preview)
            pl.addWidget(opts)
            pl.addStretch(1)
            self.options[tt] = opts
            self.add_section(tt, TYPE_NAMES[tt], page, TYPE_ICON[tt])
        self.footer.addWidget(Section("Preview"))
        self.footer.addWidget(self.preview)
        self.example = QCheckBox("Fill the table with example data")
        self.footer.addWidget(self.example)
        self.ok.setText("Create")
        self.sectionChanged.connect(lambda _k: self._refresh_preview())
        self.show_section(table_type)
        self.resize(860, 640)

    def _refresh_preview(self) -> None:
        tt = self.current_section()
        if tt:
            self.preview.set_format(tt, self.options[tt].values())

    def choice(self) -> tuple[str, dict, bool]:
        tt = self.current_section() or "column"
        return tt, self.options[tt].values(), self.example.isChecked()


class TableFormatDialog(SectionDialog):
    """Change an existing table's entry format (the type stays)."""

    def __init__(self, table, parent=None):
        super().__init__("Table Format", "Table format", parent)
        tt = table.table_type
        page, pl = tab_page()
        pl.addWidget(QLabel(TYPE_HELP[tt]))
        self.opts = FormatOptions(tt)
        self.opts.set_values(table.y_format, table.replicates, table.x_format, table.has_row_titles)
        pl.addWidget(self.opts)
        note = QLabel("Values are kept where the new format has room for them. You can undo this.")
        note.setWordWrap(True)
        note.setEnabled(False)
        pl.addSpacing(8)
        pl.addWidget(note)
        pl.addStretch(1)
        self.preview = TablePreview()
        self.opts.changed.connect(lambda: self.preview.set_format(tt, self.opts.values()))
        self.preview.set_format(tt, self.opts.values())
        self.add_group(f"{TYPE_NAMES[tt]} table")
        self.add_section("format", "Format", page, TYPE_ICON[tt])
        self.footer.addWidget(Section("Preview"))
        self.footer.addWidget(self.preview)
        self.show_section("format")
        self.resize(760, 560)

    def values(self) -> dict:
        return self.opts.values()
