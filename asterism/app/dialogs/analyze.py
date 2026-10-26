"""Analyze dialog (choose an analysis and data sets) and the t test parameters dialog.

ASTERISM's own arrangement (SPEC §2.1, §7): analysis categories in the dialog's section
sidebar, the analyses of the chosen category on the right with a short description, and
the data sets to analyze below.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
                               QPushButton, QRadioButton, QVBoxLayout, QWidget)

from ...doc.model import Table, Project
from .. import theme
from .common import FormGrid, Section, SectionDialog, combo, tab_page

# (section key, title, icon, [(analysis name, key or None, description)])
CATALOGUE = [
    ("column", "Column data", "chart.bar", [
        ("t test and nonparametric equivalents", "ttest",
         "Compare two groups: Student's or Welch's t test, t test on logs, Mann-Whitney, "
         "Kolmogorov-Smirnov; paired, ratio paired and Wilcoxon signed-rank for matched pairs."),
        ("One-way ANOVA and nonparametric equivalents", "anova1",
         "Compare three or more groups: ordinary, Welch or repeated-measures ANOVA, "
         "Kruskal-Wallis or Friedman, with multiple comparisons."),
        ("One-sample t test and Wilcoxon signed-rank test", "onesample",
         "Compare each group with a hypothetical value."),
        ("Descriptive statistics", "descriptive",
         "N, mean, SD, SEM, median, quartiles, range, confidence interval and more for each data set."),
        ("Normality and lognormality tests", "normality",
         "D'Agostino-Pearson, Anderson-Darling, Shapiro-Wilk and Kolmogorov-Smirnov tests."),
        ("Frequency distribution", "frequency", "Counts, fractions or a cumulative distribution in bins."),
        ("ROC curve", None, "Sensitivity against 1 − specificity for a diagnostic test."),
        ("Bland-Altman agreement", None, "Agreement between two methods of measurement."),
        ("Outlier detection", "outliers", "Find outliers with ROUT or Grubbs' test."),
        ("Correlation", "correlation", "Pearson or Spearman correlation between every pair of data sets."),
        ("Compare observed and expected counts", "observed_expected",
         "Chi-square (or exact binomial) test of observed counts against equal or entered expected counts."),
        ("Combine P values", None, "Analyze a set of P values (false discovery rate, combined P)."),
    ]),
    ("grouped", "Grouped data", "square.grid.3x2", [
        ("Two-way ANOVA", "anova2",
         "Two factors (rows and data sets), with or without matched values, and multiple comparisons "
         "within rows, within data sets or between all cells."),
        ("Multiple t tests and Mann-Whitney tests", "multiple_t",
         "Compare two data sets in every row, correcting for multiple comparisons or controlling "
         "the false discovery rate."),
        ("Two-way mixed-effects model", None, "Matched designs with missing values."),
        ("Three-way ANOVA", None, "Three factors."),
    ]),
    ("nested", "Nested data", "square.stack.3d.down.right", [
        ("Nested t test", "nested", "Compare two groups whose subjects were each measured several times."),
        ("Nested one-way ANOVA", "nested",
         "Compare three or more groups whose subjects were each measured several times."),
    ]),
    ("xy", "XY data", "chart.xyaxis.line", [
        ("Nonlinear regression (curve fitting)", "nonlin",
         "Fit dose-response, enzyme kinetics, binding, exponential, growth, Gaussian, polynomial, sine "
         "or your own equation; compare models or data sets; global fits; ROUT outliers."),
        ("Linear regression", "linreg", "Fit a straight line; compare slopes and intercepts; interpolate."),
        ("Correlation", "correlation", "Pearson or Spearman correlation of X with each data set."),
        ("Area under the curve", "auc", "Total area, its confidence interval, and the peaks above a baseline."),
    ]),
    ("contingency", "Counts", "tablecells", [
        ("Chi-square and Fisher's exact test", "contingency",
         "Is the outcome associated with the group? Fisher's exact or chi-square test, test for trend, "
         "relative risk, odds ratio, sensitivity and specificity."),
    ]),
    ("survival", "Survival", "waveform.path.ecg", [
        ("Kaplan-Meier survival analysis", "survival",
         "Survival curves and median survival; log-rank and Gehan-Breslow-Wilcoxon tests, test for trend, "
         "hazard ratios."),
    ]),
    ("parts", "Parts of whole", "chart.pie", [
        ("Fraction of total", "fraction", "Each value as a fraction or percentage of its column, row or grand total."),
    ]),
    ("transform", "Transform and normalize", "function", [
        ("Transform", "transform", "Logarithms, reciprocals, powers, Z scores or your own equation, for Y and X. "
                                   "Makes a result table you can graph and analyse."),
        ("Normalize", "normalize", "Each data set from 0% to 100% (smallest or first value to largest, last, "
                                   "sum, mean or a value)."),
        ("Remove baseline and column maths", "baseline",
         "Subtract or divide by a baseline data set, or by the first rows of each data set."),
        ("Prune rows", "prune", "Keep a range of rows, every nth row, or the average of every k rows."),
        ("Transpose", "transpose", "Rows become data sets and data sets become rows."),
        ("Smooth, differentiate or integrate a curve", "smooth",
         "Savitzky-Golay smoothing, first or second derivative, or the cumulative area of an XY curve."),
        ("Fraction of total", "fraction", "Each value as a fraction of its column, row or grand total."),
    ]),
]


class AnalyzeDialog(SectionDialog):
    def __init__(self, project: Project, table: Table, parent=None):
        super().__init__("Analyze", "Analyze", parent)
        self.project = project
        self.result = None
        self.lists: dict[str, QListWidget] = {}

        search = QLineEdit()
        search.setPlaceholderText("Find an analysis")
        search.setClearButtonEnabled(True)
        search.textChanged.connect(self._filter)
        self.search = search
        self.header.addWidget(search)

        self.add_group("Analyses")
        for key, title, ico, items in CATALOGUE:
            page, pl = tab_page()
            lst = QListWidget()
            for name, akey, desc in items:
                it = QListWidgetItem(name if akey else f"{name}  (coming later)")
                it.setData(Qt.UserRole, akey)
                it.setData(Qt.UserRole + 1, desc)
                it.setToolTip(desc)
                if akey is None:
                    it.setForeground(theme.color("muted"))
                lst.addItem(it)
            lst.currentItemChanged.connect(self._describe)
            lst.itemDoubleClicked.connect(lambda _it: self._ok())
            pl.addWidget(lst, 1)
            self.lists[key] = lst
            self.add_section(key, title, page, ico)
        self.description = QLabel()
        self.description.setWordWrap(True)
        self.description.setEnabled(False)
        self.description.setMinimumHeight(36)
        self.footer.addWidget(self.description)

        self.footer.addWidget(Section("Data to analyze"))
        trow = QHBoxLayout()
        trow.addWidget(QLabel("Table:"))
        self.table_combo = QComboBox()
        for t in project.tables:
            self.table_combo.addItem(t.name, t)
        for t in project.analysis_outputs():           # result tables of transforms etc.
            self.table_combo.addItem(f"Results: {t.name}", t)
        idx = self.table_combo.findData(table)
        self.table_combo.setCurrentIndex(max(idx, 0))
        self.table_combo.currentIndexChanged.connect(self._fill_sets)
        trow.addWidget(self.table_combo, 1)
        self.btn_all = QPushButton("All")
        self.btn_none = QPushButton("None")
        self.btn_all.clicked.connect(lambda: self._check_all(True))
        self.btn_none.clicked.connect(lambda: self._check_all(False))
        trow.addWidget(self.btn_all)
        trow.addWidget(self.btn_none)
        self.footer.addLayout(trow)
        self.sets = QListWidget()
        self.sets.setFixedHeight(110)
        self.footer.addWidget(self.sets)

        self.ok.clicked.disconnect()
        self.ok.clicked.connect(self._ok)
        self.ok.setText("Analyze")
        self._fill_sets()
        start = {"grouped": "grouped", "xy": "xy", "contingency": "contingency",
                 "survival": "survival", "nested": "nested", "parts": "parts"}.get(table.table_type, "column")
        self.show_section(start)
        self.lists[start].setCurrentRow(0)
        self.resize(820, 620)

    def _current_list(self) -> QListWidget:
        return self.lists[self.current_section() or "column"]

    def _describe(self, it, _prev=None) -> None:
        self.description.setText(it.data(Qt.UserRole + 1) if it else "")

    def _fill_sets(self) -> None:
        self.sets.clear()
        t: Table = self.table_combo.currentData()
        for c in t.used_columns():
            it = QListWidgetItem(t.short_label(c))
            it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked)
            it.setData(Qt.UserRole, c)
            self.sets.addItem(it)

    def _check_all(self, on: bool) -> None:
        for i in range(self.sets.count()):
            self.sets.item(i).setCheckState(Qt.Checked if on else Qt.Unchecked)

    def _filter(self, text: str) -> None:
        text = text.lower().strip()
        first_hit = None
        for key, lst in self.lists.items():
            hits = 0
            for i in range(lst.count()):
                it = lst.item(i)
                vis = not text or text in it.text().lower() or text in (it.data(Qt.UserRole + 1) or "").lower()
                it.setHidden(not vis)
                hits += vis
            if text and hits and first_hit is None:
                first_hit = key
        if first_hit and first_hit != self.current_section():
            self.show_section(first_hit)

    def _ok(self) -> None:
        it = self._current_list().currentItem()
        key = it.data(Qt.UserRole) if it else None
        if not key:
            QMessageBox.information(self, "Analyze", "This analysis isn’t available yet.\n"
                                    "Try the t test or descriptive statistics.")
            return
        cols = [self.sets.item(i).data(Qt.UserRole) for i in range(self.sets.count())
                if self.sets.item(i).checkState() == Qt.Checked]
        table = self.table_combo.currentData()
        if key == "ttest" and table.table_type != "column":
            QMessageBox.information(self, "Analyze", "The t test works on a Column table.")
            return
        if key not in ("ttest", "linreg", "nonlin", "auc", "contingency", "survival", "fraction",
                       "transpose", "prune", "smooth", "observed_expected") and table.is_summary():
            QMessageBox.information(self, "Analyze", "This analysis needs raw values; this table "
                                    "holds means and errors calculated elsewhere.")
            return
        if key == "anova1" and len(cols) < 3:
            QMessageBox.warning(self, "Analyze", "One-way ANOVA compares three or more data sets. "
                                "Choose at least three (or use a t test for two).")
            return
        if key == "ttest" and len(cols) != 2:
            QMessageBox.warning(self, "Analyze", "A t test compares exactly two data sets. Choose two.")
            return
        need = {"anova2": ("grouped", "xy"), "multiple_t": ("grouped", "xy"), "nested": ("nested",),
                "linreg": ("xy",), "nonlin": ("xy",), "auc": ("xy",), "correlation": ("xy", "column"),
                "contingency": ("contingency", "grouped"), "survival": ("survival",),
                "fraction": ("parts", "column", "grouped", "contingency"),
                "smooth": ("xy",), "observed_expected": ("column", "parts", "contingency")}
        if key in need and table.table_type not in need[key]:
            QMessageBox.information(self, "Analyze", {
                "anova2": "Two-way ANOVA works on a Grouped table.",
                "multiple_t": "Multiple t tests work on a Grouped table.",
                "nested": "Nested analyses work on a Nested table.",
                "linreg": "Linear regression works on an XY table.",
                "nonlin": "Nonlinear regression works on an XY table.",
                "auc": "Area under the curve works on an XY table.",
                "correlation": "Correlation works on an XY or Column table.",
                "contingency": "This analysis works on a Contingency table of counts.",
                "survival": "Survival analysis works on a Survival table.",
                "fraction": "Fraction of total works on Parts of whole, Column or Grouped tables.",
                "smooth": "Smoothing, derivatives and integrals work on XY tables.",
                "observed_expected": "Enter the observed counts in a Column table."}[key])
            return
        if key in ("ttest", "anova1", "onesample", "normality", "frequency", "outliers", "descriptive") \
                and table.table_type == "nested":
            QMessageBox.information(self, "Analyze", "Use the nested analyses for a Nested table.")
            return
        if key == "multiple_t" and len(cols) != 2:
            QMessageBox.warning(self, "Analyze", "Multiple t tests compare two data sets in each row. "
                                "Choose exactly two.")
            return
        if key in ("anova2", "nested") and len(cols) < 2:
            QMessageBox.warning(self, "Analyze", "Choose at least two data sets.")
            return
        if not cols:
            return
        self.result = (key, self.table_combo.currentData(), cols)
        self.accept()


# ---------------------------------------------------------------------------

class DesignSketch(QWidget):
    """ASTERISM's own design illustration, drawn as data rather than as a table:
    unpaired = two separate groups of different subjects (each its own symbol);
    paired = the same subjects measured twice, each pair joined by a line."""

    def __init__(self):
        super().__init__()
        self.paired = False
        self.setFixedSize(240, 150)

    # (value in group 1, value in group 2) for five subjects; same numbers both ways
    VALUES = [(0.30, 0.52), (0.42, 0.66), (0.55, 0.71), (0.36, 0.60), (0.48, 0.80)]

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        ink, muted = theme.color("text"), theme.color("muted")
        a_col, b_col = theme.color("accent"), theme.color("purple")
        left, right, top, bottom = 34.0, w - 18.0, 10.0, h - 28.0
        p.setPen(QPen(muted, 1.2))
        p.drawLine(QPointF(left, top), QPointF(left, bottom))
        p.drawLine(QPointF(left, bottom), QPointF(right, bottom))
        f = p.font()
        f.setPointSizeF(10)
        p.setFont(f)
        xa, xb = left + (right - left) * 0.3, left + (right - left) * 0.72
        labels = ("Before", "After") if self.paired else ("Group 1", "Group 2")
        for x, s_ in zip((xa, xb), labels):
            p.setPen(ink)
            p.drawText(QRectF(x - 40, bottom + 4, 80, 18), Qt.AlignCenter, s_)

        def yv(v):
            return bottom - v * (bottom - top)
        if self.paired:
            for i, (v1, v2) in enumerate(self.VALUES):
                p.setPen(QPen(muted, 1.4))
                p.drawLine(QPointF(xa, yv(v1)), QPointF(xb, yv(v2)))
            for v1, v2 in self.VALUES:
                for x, v in ((xa, v1), (xb, v2)):
                    p.setPen(QPen(a_col.darker(115), 1.2))
                    p.setBrush(a_col)
                    p.drawEllipse(QPointF(x, yv(v)), 4.2, 4.2)
        else:
            offs = [-9, 6, -3, 10, 2]
            for (v1, _), dx in zip(self.VALUES, offs):
                p.setPen(QPen(a_col.darker(115), 1.2))
                p.setBrush(a_col)
                p.drawEllipse(QPointF(xa + dx, yv(v1)), 4.2, 4.2)
            for (_, v2), dx in zip(self.VALUES, offs):
                p.setPen(QPen(b_col.darker(115), 1.2))
                p.setBrush(b_col)
                s_ = 4.0
                p.drawRect(QRectF(xb + dx - s_, yv(v2) - s_, 2 * s_, 2 * s_))


TEST_CHOICES = {
    ("unpaired", "normal"): [("student", "Student's t test (assumes equal SDs)"),
                             ("welch", "Welch's t test (does not assume equal SDs)")],
    ("unpaired", "lognormal"): [("student", "t test on the logarithms (compares geometric means)")],
    ("unpaired", "nonparametric"): [("mw", "Mann-Whitney U test (compares ranks)"),
                                    ("ks", "Kolmogorov-Smirnov test (compares whole distributions)")],
    ("paired", "normal"): [("student", "Paired t test (on the differences)")],
    ("paired", "lognormal"): [("student", "Ratio paired t test (on the log of the ratios)")],
    ("paired", "nonparametric"): [("wilcoxon", "Wilcoxon signed-rank test (on the differences)")],
}


class TTestParamsDialog(SectionDialog):
    def __init__(self, params: dict | None = None, parent=None):
        super().__init__("t Test Settings", "t tests", parent)
        p = {"design": "unpaired", "distribution": "normal", "test": "student", "tails": 2,
             "conf": 0.95, "bracket": True, "descriptive": False, **(params or {})}

        # Design ---------------------------------------------------------------
        page, pl = tab_page()
        pl.addWidget(QLabel("Are the two data sets matched row by row?"))
        self.g_design = QButtonGroup(self)
        self.r_unpaired = QRadioButton("No: independent groups (unpaired)")
        self.r_paired = QRadioButton("Yes: each row is a matched pair (paired)")
        for i, r in enumerate((self.r_unpaired, self.r_paired)):
            self.g_design.addButton(r, i)
            pl.addWidget(r)
        (self.r_paired if p["design"] == "paired" else self.r_unpaired).setChecked(True)
        self.sketch = DesignSketch()
        sk = QHBoxLayout()
        sk.setContentsMargins(24, 8, 0, 4)
        sk.addWidget(self.sketch)
        sk.addStretch(1)
        pl.addLayout(sk)
        pl.addStretch(1)
        self.add_group("Settings")
        self.add_section("design", "Design", page, "rectangle.split.2x1")

        # Test -----------------------------------------------------------------
        page, pl = tab_page()
        pl.addWidget(Section("What can be assumed about the data?"))
        self.g_dist = QButtonGroup(self)
        for key, title, desc in (
                ("normal", "Normal distribution", "Compares means."),
                ("lognormal", "Lognormal distribution", "Compares geometric means."),
                ("nonparametric", "No distribution assumed", "Rank-based; compares medians or distributions.")):
            r = QRadioButton(title)
            r.setProperty("key", key)
            self.g_dist.addButton(r)
            pl.addWidget(r)
            d = QLabel(desc)
            d.setContentsMargins(26, 0, 0, 6)
            d.setEnabled(False)
            pl.addWidget(d)
            if key == p["distribution"]:
                r.setChecked(True)
        pl.addWidget(Section("Test"))
        self.test_box = QVBoxLayout()
        pl.addLayout(self.test_box)
        self.g_test = QButtonGroup(self)
        pl.addStretch(1)
        self.add_section("test", "Test", page, "function")
        self._want_test = p["test"]

        # Options --------------------------------------------------------------
        page, pl = tab_page()
        pl.addWidget(Section("Calculations"))
        g = FormGrid()
        tails = QWidget()
        th = QHBoxLayout(tails)
        th.setContentsMargins(0, 0, 0, 0)
        self.r_two, self.r_one = QRadioButton("Two-sided"), QRadioButton("One-sided")
        (self.r_one if p["tails"] == 1 else self.r_two).setChecked(True)
        th.addWidget(self.r_two)
        th.addWidget(self.r_one)
        th.addStretch(1)
        self.conf = combo([("90%", 0.90), ("95%", 0.95), ("99%", 0.99)], p["conf"])
        g.add(("P value:", tails))
        g.add(("Confidence intervals:", self.conf))
        g.add(("Differences as:", combo([("Second minus first data set", "ba")])))
        pl.addLayout(g)
        pl.addWidget(Section("Output"))
        self.c_bracket = QCheckBox("Show the comparison on the linked graph")
        self.c_bracket.setChecked(p["bracket"])
        pl.addWidget(self.c_bracket)
        self.c_desc = QCheckBox("Also report descriptive statistics for each data set")
        self.c_desc.setChecked(p["descriptive"])
        pl.addWidget(self.c_desc)
        pl.addStretch(1)
        self.add_section("options", "Options", page, "slider.horizontal.3")

        # Residuals (not built yet) -------------------------------------------------
        page, pl = tab_page()
        for s in ("Residual plot", "Normal QQ plot of residuals", "Spread vs. fitted value plot",
                  "Test the residuals for normality"):
            c = QCheckBox(s)
            c.setEnabled(False)
            pl.addWidget(c)
        note = QLabel("Residual diagnostics arrive with the column analyses (M3).")
        note.setEnabled(False)
        pl.addWidget(note)
        pl.addStretch(1)
        self.add_section("residuals", "Residuals", page, "waveform.path")

        self.g_design.idToggled.connect(lambda *_: self._refresh())
        self.g_dist.buttonToggled.connect(lambda *_: self._refresh())
        self._refresh()
        self.show_section("design")
        self.resize(760, 560)

    def _refresh(self) -> None:
        design = "paired" if self.r_paired.isChecked() else "unpaired"
        self.sketch.paired = design == "paired"
        self.sketch.update()
        dist = self.g_dist.checkedButton().property("key")
        cur = self.g_test.checkedButton().property("key") if self.g_test.checkedButton() else self._want_test
        for b in self.g_test.buttons():
            self.g_test.removeButton(b)
            b.deleteLater()
        for key, text in TEST_CHOICES[(design, dist)]:
            r = QRadioButton(text)
            r.setProperty("key", key)
            self.g_test.addButton(r)
            self.test_box.addWidget(r)
            if key == cur:
                r.setChecked(True)
        if not self.g_test.checkedButton():
            self.g_test.buttons()[0].setChecked(True)

    def params(self) -> dict:
        return {
            "design": "paired" if self.r_paired.isChecked() else "unpaired",
            "distribution": self.g_dist.checkedButton().property("key"),
            "test": self.g_test.checkedButton().property("key"),
            "tails": 1 if self.r_one.isChecked() else 2,
            "conf": self.conf.currentData(),
            "bracket": self.c_bracket.isChecked(),
            "descriptive": self.c_desc.isChecked(),
        }
