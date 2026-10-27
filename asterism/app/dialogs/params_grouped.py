"""Settings dialogs for grouped and nested analyses (section sidebar; Prism's options,
our wording): two-way ANOVA, multiple t tests, nested t test / one-way ANOVA."""

from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QComboBox, QDoubleSpinBox, QHBoxLayout, QLabel, QLineEdit

from ...analysis.anova2 import COMPARE, METHODS
from ...analysis.multiple_t import CORRECTIONS
from .common import FormGrid, Section, SectionDialog, combo, set_combo, tab_page
from .params import _key, _note, _radio_group, _rm_method_combo

CONF = [("90%", 0.90), ("95%", 0.95), ("99%", 0.99)]


class TwoWayParamsDialog(SectionDialog):
    def __init__(self, params: dict | None, table=None, parent=None):
        super().__init__("Two-way ANOVA Settings", "Two-way ANOVA", parent)
        p = {"design": "ordinary", "gg": False, "compare": "both", "method": None, "conf": 0.95,
             "row_factor": "Row factor", "col_factor": "Column factor", "bracket": True,
             "rm_method": "auto", **(params or {})}
        self.add_group("Settings")

        page, pl = tab_page()
        pl.addWidget(QLabel("Which values come from the same subject?"))
        self.g_design = _radio_group(self, pl, [
            ("ordinary", "None: every value is from a different subject"),
            ("rm_rows", "Each sub-column is one subject, measured in every row"),
            ("rm_cols", "Each sub-column position is one subject, measured in every data set"),
            ("rm_both", "Each sub-column position is one subject, measured in every cell")], p["design"])
        from ..sketches import Sketch
        self.design_sketch = Sketch("", 230, 130)
        sync = lambda *_: self.design_sketch.set_key(f"design:{_key(self.g_design)}")
        self.g_design.buttonToggled.connect(sync)
        sync()
        srow = QHBoxLayout()
        srow.setContentsMargins(18, 4, 0, 4)
        srow.addWidget(self.design_sketch)
        hint = QLabel("Lines join the values of one subject. Circles and squares are the two data sets; "
                      "Day 1 and Day 7 are rows.")
        hint.setWordWrap(True)
        hint.setEnabled(False)
        srow.addSpacing(10)
        srow.addWidget(hint, 1)
        pl.addLayout(srow)
        g0 = FormGrid()
        self.rm_method = _rm_method_combo(p["rm_method"])
        g0.add(("Missing values:", self.rm_method))
        pl.addLayout(g0)
        pl.addWidget(_note("Repeated-measures ANOVA needs every value. A mixed-effects model (REML, "
                           "compound symmetry) gives the same results when nothing is missing and "
                           "also handles gaps, if values are missing for reasons unrelated to them."))
        pl.addWidget(Section("Factor names"))
        g = FormGrid()
        self.row_factor = QLineEdit(p["row_factor"])
        self.col_factor = QLineEdit(p["col_factor"])
        g.add(("Rows are:", self.row_factor))
        g.add(("Data sets are:", self.col_factor))
        pl.addLayout(g)
        pl.addStretch(1)
        self.add_section("design", "Design", page, "rectangle.split.2x1")

        page, pl = tab_page()
        pl.addWidget(Section("Sphericity"))
        self.c_gg = QCheckBox("Correct for unequal variability of differences (Geisser-Greenhouse)")
        self.c_gg.setChecked(p["gg"])
        pl.addWidget(self.c_gg)
        pl.addWidget(_note("Applies when one factor is matched and the other is not."))
        pl.addStretch(1)
        self.add_section("test", "Test", page, "function")

        page, pl = tab_page()
        pl.addWidget(Section("Which comparisons?"))
        self.g_compare = _radio_group(self, pl, list(COMPARE.items()), p["compare"])
        pl.addWidget(Section("Method"))
        g = FormGrid()
        self.method = QComboBox()
        for k, v in METHODS.items():
            self.method.addItem(v, k)
        set_combo(self.method, p["method"] or ("tukey" if p["design"] == "ordinary" else "sidak"))
        g.add(("Test:", self.method))
        pl.addLayout(g)
        pl.addStretch(1)
        self.add_section("comparisons", "Comparisons", page, "arrow.left.arrow.right")

        page, pl = tab_page()
        g = FormGrid()
        self.conf = combo(CONF, p["conf"])
        g.add(("Confidence intervals:", self.conf))
        pl.addLayout(g)
        pl.addWidget(Section("Output"))
        self.c_bracket = QCheckBox("Show significant comparisons on the linked graph")
        self.c_bracket.setChecked(p["bracket"])
        pl.addWidget(self.c_bracket)
        pl.addStretch(1)
        self.add_section("options", "Options", page, "slider.horizontal.3")
        self.g_design.buttonToggled.connect(lambda *_: self._refresh())
        self._refresh()
        self.show_section("design")
        self.resize(760, 560)

    def _refresh(self) -> None:
        self.c_gg.setEnabled(_key(self.g_design) in ("rm_rows", "rm_cols"))
        self.rm_method.setEnabled(_key(self.g_design) != "ordinary")

    def params(self) -> dict:
        return {"design": _key(self.g_design), "gg": self.c_gg.isChecked(),
                "compare": _key(self.g_compare), "method": self.method.currentData(),
                "conf": self.conf.currentData(), "bracket": self.c_bracket.isChecked(),
                "row_factor": self.row_factor.text().strip() or "Row factor",
                "col_factor": self.col_factor.text().strip() or "Column factor",
                "rm_method": self.rm_method.currentData()}


class MultipleTParamsDialog(SectionDialog):
    def __init__(self, params: dict | None, parent=None):
        super().__init__("Multiple t Tests Settings", "Multiple t tests", parent)
        p = {"design": "unpaired", "test": "welch", "correction": "holm_sidak", "q": 0.01,
             "alpha": 0.05, **(params or {})}
        self.add_group("Settings")

        page, pl = tab_page()
        pl.addWidget(QLabel("Each row compares two data sets. Are the replicates matched?"))
        paired = p["test"] in ("paired", "wilcoxon")
        self.g_design = _radio_group(self, pl, [
            ("unpaired", "No: independent groups"),
            ("paired", "Yes: replicate 1 of one data set pairs with replicate 1 of the other")],
            "paired" if paired else "unpaired")
        pl.addWidget(Section("Test"))
        self.test = QComboBox()
        g = FormGrid()
        g.add(("Test in each row:", self.test))
        pl.addLayout(g)
        pl.addStretch(1)
        self.add_section("design", "Design", page, "rectangle.split.2x1")
        self._want_test = p["test"]

        page, pl = tab_page()
        pl.addWidget(Section("Multiple comparisons"))
        self.g_kind = _radio_group(self, pl, [
            ("fdr", "Control the false discovery rate"),
            ("fwer", "Correct for multiple comparisons (family-wise error rate)"),
            ("none", "No correction: each row on its own")],
            "fdr" if p["correction"].startswith("fdr") else ("none" if p["correction"] == "none" else "fwer"))
        g = FormGrid()
        self.fdr = QComboBox()
        for k in ("fdr_bky", "fdr_bh", "fdr_by"):
            self.fdr.addItem(CORRECTIONS[k], k)
        self.fwer = QComboBox()
        for k in ("holm_sidak", "sidak", "bonferroni"):
            self.fwer.addItem(CORRECTIONS[k], k)
        set_combo(self.fdr if p["correction"].startswith("fdr") else self.fwer, p["correction"])
        self.q = QDoubleSpinBox()
        self.q.setRange(0.001, 0.5)
        self.q.setDecimals(3)
        self.q.setSingleStep(0.01)
        self.q.setValue(p["q"])
        self.alpha = QDoubleSpinBox()
        self.alpha.setRange(0.001, 0.5)
        self.alpha.setDecimals(3)
        self.alpha.setSingleStep(0.01)
        self.alpha.setValue(p["alpha"])
        g.add(("FDR method:", self.fdr))
        g.add(("Desired FDR (Q):", self.q))
        g.add(("Correction:", self.fwer))
        g.add(("Significance level (α):", self.alpha))
        pl.addLayout(g)
        pl.addStretch(1)
        self.add_section("comparisons", "Comparisons", page, "arrow.left.arrow.right")
        self.g_design.buttonToggled.connect(lambda *_: self._refresh())
        self.g_kind.buttonToggled.connect(lambda *_: self._refresh())
        self._refresh()
        self.show_section("design")
        self.resize(720, 500)

    def _refresh(self) -> None:
        paired = _key(self.g_design) == "paired"
        cur = self.test.currentData() or self._want_test
        self.test.clear()
        opts = ([("paired", "Paired t test"), ("wilcoxon", "Wilcoxon signed-rank test")] if paired else
                [("welch", "Welch's t test (does not assume equal SDs)"),
                 ("student", "Student's t test (assumes equal SDs)"), ("mw", "Mann-Whitney test")])
        for k, v in opts:
            self.test.addItem(v, k)
        set_combo(self.test, cur)
        kind = _key(self.g_kind)
        self.fdr.setEnabled(kind == "fdr")
        self.q.setEnabled(kind == "fdr")
        self.fwer.setEnabled(kind == "fwer")
        self.alpha.setEnabled(kind != "fdr")

    def params(self) -> dict:
        kind = _key(self.g_kind)
        corr = self.fdr.currentData() if kind == "fdr" else (self.fwer.currentData() if kind == "fwer" else "none")
        return {"design": _key(self.g_design), "test": self.test.currentData(), "correction": corr,
                "q": self.q.value(), "alpha": self.alpha.value()}


class NestedParamsDialog(SectionDialog):
    def __init__(self, params: dict | None, ngroups: int = 2, parent=None):
        super().__init__("Nested Analysis Settings", "Nested t test" if ngroups == 2 else "Nested one-way ANOVA",
                         parent)
        p = {"compare": "all", "method": "tukey", "conf": 0.95, "bracket": True, **(params or {})}
        self.add_group("Settings")
        page, pl = tab_page()
        pl.addWidget(QLabel("Each data set is a group; each sub-column is one subject, and\n"
                            "the values in it are replicate measurements of that subject."))
        from ..sketches import Sketch
        srow = QHBoxLayout()
        srow.setContentsMargins(18, 4, 0, 4)
        srow.addWidget(Sketch("table:nested", 230, 130))
        hint = QLabel("Small dots are the measurements, big dots each subject's mean, one colour per "
                      "subject. The subjects, not the measurements, are the independent units.")
        hint.setWordWrap(True)
        hint.setEnabled(False)
        srow.addSpacing(10)
        srow.addWidget(hint, 1)
        pl.addLayout(srow)
        pl.addWidget(_note("Subjects are a random factor. With the same number of replicates per "
                           "subject, the group test equals an ordinary test on the subject means."))
        pl.addStretch(1)
        self.add_section("design", "Design", page, "rectangle.split.2x1")

        page, pl = tab_page()
        self.g_compare = _radio_group(self, pl, [("all", "Compare every pair of groups"),
                                                 ("none", "No multiple comparisons")], p["compare"])
        g = FormGrid()
        self.method = QComboBox()
        for k in ("tukey", "holm_sidak", "sidak", "bonferroni", "fisher"):
            self.method.addItem(METHODS[k], k)
        set_combo(self.method, p["method"])
        self.conf = combo(CONF, p["conf"])
        g.add(("Test:", self.method))
        g.add(("Confidence intervals:", self.conf))
        pl.addLayout(g)
        if ngroups == 2:                      # one comparison: only the interval's level applies
            for b in self.g_compare.buttons():
                b.setEnabled(False)
            self.method.setEnabled(False)
        self.c_bracket = QCheckBox("Show significant comparisons on the linked graph")
        self.c_bracket.setChecked(p["bracket"])
        pl.addStretch(1)
        self.add_section("comparisons", "Comparisons", page, "arrow.left.arrow.right")
        page, pl = tab_page()
        pl.addWidget(self.c_bracket)
        pl.addStretch(1)
        self.add_section("options", "Options", page, "slider.horizontal.3")
        self.show_section("design")
        self.resize(700, 460)

    def params(self) -> dict:
        return {"compare": _key(self.g_compare), "method": self.method.currentData(),
                "conf": self.conf.currentData(), "bracket": self.c_bracket.isChecked()}
