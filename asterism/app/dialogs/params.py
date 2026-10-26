"""Settings dialogs for column analyses (section sidebar; Prism's options, our wording)."""

from __future__ import annotations

from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QDoubleSpinBox, QHBoxLayout,
                               QLabel, QLineEdit, QRadioButton, QWidget)

from ...analysis.anova import DEFAULT_METHOD, METHOD_NAMES, METHODS_FOR, model_of
from ...doc.model import column_letter
from .common import FormGrid, Section, SectionDialog, combo, set_combo, tab_page


def _radio_group(parent, layout, options, current) -> QButtonGroup:
    g = QButtonGroup(parent)
    for key, text in options:
        r = QRadioButton(text)
        r.setProperty("key", key)
        g.addButton(r)
        layout.addWidget(r)
        if key == current:
            r.setChecked(True)
    if g.checkedButton() is None and g.buttons():
        g.buttons()[0].setChecked(True)
    return g


def _key(g: QButtonGroup):
    b = g.checkedButton()
    return b.property("key") if b else None


def _rm_method_combo(current: str) -> QComboBox:
    from ...analysis.anova2 import RM_METHODS
    return combo([(v, k) for k, v in RM_METHODS.items()], current)


def _note(text: str) -> QLabel:
    lab = QLabel(text)
    lab.setWordWrap(True)
    lab.setEnabled(False)
    lab.setContentsMargins(24, 0, 0, 6)
    return lab


class AnovaParamsDialog(SectionDialog):
    def __init__(self, params: dict | None, table, columns: list[int], parent=None):
        super().__init__("One-way ANOVA Settings", "One-way ANOVA", parent)
        p = {"design": "ordinary", "distribution": "normal", "welch": False, "gg": True,
             "compare": "all", "control": columns[0] if columns else 0, "method": None,
             "conf": 0.95, "bracket": True, "descriptive": False, "rm_method": "auto", **(params or {})}
        self.table, self.columns = table, columns
        self.add_group("Settings")

        page, pl = tab_page()
        pl.addWidget(QLabel("Are the values matched across data sets?"))
        self.g_design = _radio_group(self, pl, [
            ("ordinary", "No: independent groups"),
            ("rm", "Yes: each row is one subject measured under every condition")], p["design"])
        g0 = FormGrid()
        self.rm_method = _rm_method_combo(p["rm_method"])
        g0.add(("Missing values:", self.rm_method))
        pl.addLayout(g0)
        pl.addWidget(_note("Repeated-measures ANOVA needs every value. A mixed-effects model (REML, "
                           "compound symmetry) gives the same results when nothing is missing and "
                           "also handles gaps, if values are missing for reasons unrelated to them."))
        pl.addStretch(1)
        self.add_section("design", "Design", page, "rectangle.split.2x1")

        page, pl = tab_page()
        pl.addWidget(Section("Distribution"))
        self.g_dist = _radio_group(self, pl, [
            ("normal", "Assume normal distributions (ANOVA)"),
            ("nonparametric", "No distribution assumed (rank-based test)")], p["distribution"])
        pl.addWidget(Section("Variability"))
        self.c_welch = QCheckBox("Groups may have different SDs: use Welch and Brown-Forsythe ANOVA")
        self.c_welch.setChecked(p["welch"])
        pl.addWidget(self.c_welch)
        self.c_gg = QCheckBox("Correct for unequal variability of differences (Geisser-Greenhouse)")
        self.c_gg.setChecked(p["gg"])
        pl.addWidget(self.c_gg)
        self.test_note = _note("")
        pl.addWidget(self.test_note)
        pl.addStretch(1)
        self.add_section("test", "Test", page, "function")

        page, pl = tab_page()
        pl.addWidget(Section("Which comparisons?"))
        self.g_compare = _radio_group(self, pl, [
            ("all", "Compare every pair of data sets"),
            ("control", "Compare each data set with a control"),
            ("none", "No multiple comparisons")], p["compare"])
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(24, 0, 0, 0)
        h.addWidget(QLabel("Control:"))
        self.control = QComboBox()
        for c in columns:
            self.control.addItem(table.short_label(c), c)
        set_combo(self.control, p["control"])
        h.addWidget(self.control)
        h.addStretch(1)
        pl.addWidget(row)
        pl.addWidget(Section("Method"))
        g = FormGrid()
        self.method = QComboBox()
        g.add(("Test:", self.method))
        pl.addLayout(g)
        pl.addStretch(1)
        self.add_section("comparisons", "Comparisons", page, "arrow.left.arrow.right")
        self._want_method = p["method"]

        page, pl = tab_page()
        g = FormGrid()
        self.conf = combo([("90%", 0.90), ("95%", 0.95), ("99%", 0.99)], p["conf"])
        g.add(("Confidence intervals:", self.conf))
        pl.addLayout(g)
        pl.addWidget(Section("Output"))
        self.c_bracket = QCheckBox("Show significant comparisons on the linked graph")
        self.c_bracket.setChecked(p["bracket"])
        pl.addWidget(self.c_bracket)
        self.c_desc = QCheckBox("Also report descriptive statistics for each data set")
        self.c_desc.setChecked(p["descriptive"])
        pl.addWidget(self.c_desc)
        pl.addStretch(1)
        self.add_section("options", "Options", page, "slider.horizontal.3")

        for g_ in (self.g_design, self.g_dist, self.g_compare):
            g_.buttonToggled.connect(lambda *_: self._refresh())
        self.c_welch.toggled.connect(lambda *_: self._refresh())
        self._refresh()
        self.show_section("design")
        self.resize(780, 560)

    def _params_now(self) -> dict:
        return {"design": _key(self.g_design), "distribution": _key(self.g_dist),
                "welch": self.c_welch.isChecked()}

    def _refresh(self) -> None:
        pp = self._params_now()
        model = model_of(pp)
        normal = pp["distribution"] == "normal"
        self.c_welch.setVisible(normal and pp["design"] == "ordinary")
        self.c_gg.setVisible(normal and pp["design"] == "rm")
        self.rm_method.setEnabled(normal and pp["design"] == "rm")
        self.test_note.setText({
            "ordinary": "Ordinary one-way ANOVA (assumes equal SDs).",
            "welch": "Welch's ANOVA and Brown-Forsythe ANOVA (SDs may differ).",
            "rm": "Repeated-measures one-way ANOVA.",
            "kw": "Kruskal-Wallis test (compares mean ranks).",
            "friedman": "Friedman test (compares ranks within each subject)."}[model])
        family = _key(self.g_compare)
        self.control.setEnabled(family == "control")
        self.method.setEnabled(family != "none")
        cur = self.method.currentData() or self._want_method
        self.method.blockSignals(True)
        self.method.clear()
        for m in METHODS_FOR[model]:
            if m == "dunnett" and family != "control":
                continue
            if m == "tukey" and family == "control":
                continue
            self.method.addItem(METHOD_NAMES[m], m)
        idx = self.method.findData(cur)
        if idx < 0:
            idx = self.method.findData(DEFAULT_METHOD[(model, "control" if family == "control" else "all")])
        self.method.setCurrentIndex(max(idx, 0))
        self.method.blockSignals(False)

    def params(self) -> dict:
        pp = self._params_now()
        pp.update(gg=self.c_gg.isChecked(), compare=_key(self.g_compare),
                  control=self.control.currentData(), method=self.method.currentData(),
                  conf=self.conf.currentData(), bracket=self.c_bracket.isChecked(),
                  descriptive=self.c_desc.isChecked(), rm_method=self.rm_method.currentData())
        return pp


class NormalityParamsDialog(SectionDialog):
    def __init__(self, params: dict | None, parent=None):
        super().__init__("Normality Test Settings", "Normality tests", parent)
        p = {"dagostino": True, "anderson": True, "shapiro": True, "ks": True,
             "lognormal": False, "alpha": 0.05, **(params or {})}
        page, pl = tab_page()
        pl.addWidget(Section("Tests"))
        self.checks = {}
        for key, text in (("dagostino", "D'Agostino-Pearson omnibus test (needs 8 or more values)"),
                          ("anderson", "Anderson-Darling test (needs 8 or more values)"),
                          ("shapiro", "Shapiro-Wilk test"),
                          ("ks", "Kolmogorov-Smirnov test with the Lilliefors P value")):
            c = QCheckBox(text)
            c.setChecked(p[key])
            pl.addWidget(c)
            self.checks[key] = c
        pl.addWidget(Section("Also test"))
        self.c_log = QCheckBox("Lognormal distribution (tests run on the logarithms)")
        self.c_log.setChecked(p["lognormal"])
        pl.addWidget(self.c_log)
        g = FormGrid()
        self.alpha = combo([("0.05", 0.05), ("0.01", 0.01), ("0.10", 0.10)], p["alpha"])
        g.add(("Significance level (α):", self.alpha))
        pl.addLayout(g)
        pl.addStretch(1)
        self.add_group("Settings")
        self.add_section("tests", "Tests", page, "checkmark.seal")
        self.show_section("tests")
        self.resize(700, 460)

    def params(self) -> dict:
        out = {k: c.isChecked() for k, c in self.checks.items()}
        out.update(lognormal=self.c_log.isChecked(), alpha=self.alpha.currentData())
        return out


class OneSampleParamsDialog(SectionDialog):
    def __init__(self, params: dict | None, parent=None):
        super().__init__("One-sample Test Settings", "One-sample tests", parent)
        p = {"test": "t", "mu": 0.0, "tails": 2, "conf": 0.95, **(params or {})}
        page, pl = tab_page()
        pl.addWidget(Section("Test"))
        self.g_test = _radio_group(self, pl, [
            ("t", "One-sample t test (compares the mean)"),
            ("wilcoxon", "Wilcoxon signed-rank test (compares the median)")], p["test"])
        pl.addWidget(Section("Compare with"))
        g = FormGrid()
        self.mu = QLineEdit(f"{p['mu']:g}")
        self.mu.setFixedWidth(120)
        g.add(("Hypothetical value:", self.mu))
        pl.addLayout(g)
        pl.addWidget(Section("Calculations"))
        g = FormGrid()
        self.tails = combo([("Two-sided", 2), ("One-sided", 1)], p["tails"])
        self.conf = combo([("90%", 0.90), ("95%", 0.95), ("99%", 0.99)], p["conf"])
        g.add(("P value:", self.tails), ("Confidence intervals:", self.conf))
        pl.addLayout(g)
        pl.addStretch(1)
        self.add_group("Settings")
        self.add_section("test", "Test", page, "function")
        self.show_section("test")
        self.resize(700, 460)

    def params(self) -> dict:
        try:
            mu = float(self.mu.text().replace(",", "."))
        except ValueError:
            mu = 0.0
        return {"test": _key(self.g_test), "mu": mu, "tails": self.tails.currentData(),
                "conf": self.conf.currentData()}


class OutlierParamsDialog(SectionDialog):
    def __init__(self, params: dict | None, parent=None):
        super().__init__("Outlier Detection Settings", "Outliers", parent)
        p = {"method": "rout", "alpha": 0.05, "q": 0.01, **(params or {})}
        page, pl = tab_page()
        pl.addWidget(Section("Method"))
        self.g_method = _radio_group(self, pl, [
            ("rout", "ROUT (robust regression and outlier removal): can find several outliers"),
            ("grubbs", "Grubbs' test: find at most one outlier"),
            ("grubbs_iterative", "Grubbs' test, repeated until no more outliers are found")], p["method"])
        g = FormGrid()
        self.q = combo([("0.1%", 0.001), ("1%", 0.01), ("5%", 0.05), ("10%", 0.10)], p["q"])
        self.alpha = combo([("0.05", 0.05), ("0.01", 0.01), ("0.001", 0.001), ("0.0001", 0.0001)], p["alpha"])
        g.add(("ROUT: Q (maximum false discovery rate):", self.q))
        g.add(("Grubbs: significance level (α):", self.alpha))
        pl.addLayout(g)
        self.g_method.buttonToggled.connect(lambda *_: self._sync())
        self._sync()
        pl.addStretch(1)
        self.add_group("Settings")
        self.add_section("method", "Method", page, "line.3.horizontal.decrease")
        self.show_section("method")
        self.resize(700, 420)

    def _sync(self) -> None:
        rout = _key(self.g_method) == "rout"
        self.q.setEnabled(rout)
        self.alpha.setEnabled(not rout)

    def params(self) -> dict:
        return {"method": _key(self.g_method), "alpha": self.alpha.currentData(), "q": self.q.currentData()}


class FrequencyParamsDialog(SectionDialog):
    def __init__(self, params: dict | None, parent=None):
        super().__init__("Frequency Distribution Settings", "Frequency distribution", parent)
        p = {"tabulate": "counts", "cumulative": False, "bin_width": None, "first_center": None,
             "last_center": None, **(params or {})}
        page, pl = tab_page()
        pl.addWidget(Section("Distribution"))
        self.g_kind = _radio_group(self, pl, [(False, "Frequency distribution (each bin separately)"),
                                              (True, "Cumulative distribution")], p["cumulative"])
        g = FormGrid()
        self.tab = combo([("Number of values", "counts"), ("Fraction of values", "fractions"),
                          ("Percentage of values", "percentages")], p["tabulate"])
        g.add(("Tabulate:", self.tab))
        pl.addLayout(g)
        pl.addWidget(Section("Bins"))
        g = FormGrid()
        self.width, self.width_auto = self._num_auto(p["bin_width"])
        self.first, self.first_auto = self._num_auto(p["first_center"])
        self.last, self.last_auto = self._num_auto(p["last_center"])
        for label, (e, a) in (("Bin width:", (self.width, self.width_auto)),
                              ("First bin centre:", (self.first, self.first_auto)),
                              ("Last bin centre:", (self.last, self.last_auto))):
            row = QWidget()
            h = QHBoxLayout(row)
            h.setContentsMargins(0, 0, 0, 0)
            h.addWidget(a)
            h.addWidget(e)
            h.addStretch(1)
            g.add((label, row))
        pl.addLayout(g)
        pl.addWidget(_note("Automatic: bins about a twentieth of the data's range wide (a 1-2-5 "
                           "number); the first and last bins hold the smallest and largest values."))
        pl.addStretch(1)
        self.add_group("Settings")
        self.add_section("bins", "Bins", page, "chart.bar.xaxis")
        self.show_section("bins")
        self.resize(720, 480)

    def _num_auto(self, value):
        e = QDoubleSpinBox()
        e.setRange(-1e12, 1e12)
        e.setDecimals(6)
        e.setFixedWidth(130)
        a = QCheckBox("Automatic")
        a.setChecked(value is None)
        if value is not None:
            e.setValue(float(value))
        e.setEnabled(value is not None)
        a.toggled.connect(lambda on: e.setEnabled(not on))
        return e, a

    def params(self) -> dict:
        def val(e, a):
            return None if a.isChecked() else e.value()
        w = val(self.width, self.width_auto)
        return {"cumulative": bool(_key(self.g_kind)), "tabulate": self.tab.currentData(),
                "bin_width": w if (w is None or w > 0) else None,
                "first_center": val(self.first, self.first_auto),
                "last_center": val(self.last, self.last_auto)}


def settings_dialog(kind: str, params: dict | None, table, columns: list[int], parent=None):
    """The settings dialog for an analysis type, or None when it has no settings."""
    from .analyze import TTestParamsDialog
    if kind == "ttest":
        return TTestParamsDialog(params, parent)
    if kind == "anova1":
        return AnovaParamsDialog(params, table, columns, parent)
    if kind == "normality":
        return NormalityParamsDialog(params, parent)
    if kind == "onesample":
        return OneSampleParamsDialog(params, parent)
    if kind == "outliers":
        return OutlierParamsDialog(params, parent)
    if kind == "frequency":
        return FrequencyParamsDialog(params, parent)
    from .params_grouped import MultipleTParamsDialog, NestedParamsDialog, TwoWayParamsDialog
    if kind == "anova2":
        return TwoWayParamsDialog(params, table, parent)
    from .params_transforms import (BaselineParamsDialog, NormalizeParamsDialog, ObservedExpectedParamsDialog,
                                    PruneParamsDialog, SmoothParamsDialog, TransformParamsDialog)
    if kind == "transform":
        return TransformParamsDialog(params, table.has_x(), parent)
    if kind == "normalize":
        return NormalizeParamsDialog(params, parent)
    if kind == "baseline":
        return BaselineParamsDialog(params, table, columns, parent)
    if kind == "prune":
        return PruneParamsDialog(params, table.has_x(), parent)
    if kind == "smooth":
        return SmoothParamsDialog(params, parent)
    if kind == "observed_expected":
        return ObservedExpectedParamsDialog(params, parent)
    from .params_counts import ContingencyParamsDialog, FractionParamsDialog, SurvivalParamsDialog
    if kind == "contingency":
        rows = sum(1 for r in range(table.nrows_used()) if any(table.get(r, table.flat(c)) is not None for c in columns))
        return ContingencyParamsDialog(params, rows == 2 and len(columns) == 2, parent)
    if kind == "survival":
        return SurvivalParamsDialog(params, parent)
    if kind == "fraction":
        return FractionParamsDialog(params, parent)
    from .params_xy import AucParamsDialog, CorrelationParamsDialog, LinRegParamsDialog, NonlinParamsDialog
    if kind == "linreg":
        return LinRegParamsDialog(params, parent)
    if kind == "correlation":
        return CorrelationParamsDialog(params, parent)
    if kind == "auc":
        return AucParamsDialog(params, parent)
    if kind == "nonlin":
        return NonlinParamsDialog(params, len(columns), parent)
    if kind == "multiple_t":
        return MultipleTParamsDialog(params, parent)
    if kind == "nested":
        return NestedParamsDialog(params, len(columns), parent)
    return None
