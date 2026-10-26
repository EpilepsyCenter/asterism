"""Settings dialogs for contingency, survival and fraction-of-total analyses (section
sidebar; Prism's options and recommended methods, our wording)."""

from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QLabel, QSpinBox

from .common import FormGrid, Section, SectionDialog, combo, tab_page
from .params import _key, _note, _radio_group

CONF = [("90%", 0.90), ("95%", 0.95), ("99%", 0.99)]


class ContingencyParamsDialog(SectionDialog):
    def __init__(self, params: dict | None, is22: bool = True, parent=None):
        super().__init__("Contingency Settings", "Contingency tables", parent)
        p = {"test": "fisher" if is22 else "chi2", "yates": False, "tails": 2, "trend": True,
             "effect": "rr", "rr_ci": "koopman", "diff_ci": "newcombe_cc", "or_ci": "baptista_pike",
             "prop_ci": "wilson_brown", "association": True, "conf": 0.95, **(params or {})}
        self.add_group("Settings")
        page, pl = tab_page()
        pl.addWidget(Section("Test"))
        self.g_test = _radio_group(self, pl, [("fisher", "Fisher's exact test" +
                                               ("" if is22 else " (extended to larger tables)")),
                                              ("chi2", "Chi-square test"),
                                              ("mcnemar", "McNemar's test (the same subjects measured twice; 2 × 2)")],
                                   p["test"])
        if not is22:
            self.g_test.buttons()[2].setEnabled(False)
        self.c_yates = QCheckBox("Yates' continuity correction (chi-square, 2 × 2 only)")
        self.c_yates.setChecked(p["yates"])
        self.c_yates.setEnabled(is22)
        pl.addWidget(self.c_yates)
        pl.addWidget(_note("Fisher's test is exact and preferred when counts are small; the chi-square "
                           "test is an approximation for large counts."))
        self.c_trend = QCheckBox("Chi-square test for trend (ordered rows or columns, 2 × 3 or larger)")
        self.c_trend.setChecked(p["trend"])
        pl.addWidget(self.c_trend)
        g = FormGrid()
        self.tails = combo([("Two-sided", 2), ("One-sided", 1)], p["tails"])
        g.add(("P value:", self.tails))
        pl.addLayout(g)
        pl.addStretch(1)
        self.add_section("test", "Test", page, "function")

        page, pl = tab_page()
        pl.addWidget(Section("2 × 2 tables: which effect size?"))
        self.g_effect = _radio_group(self, pl, [
            ("rr", "Relative risk and difference between proportions (prospective and experimental studies)"),
            ("or", "Odds ratio (case-control studies)"),
            ("diagnostic", "Sensitivity, specificity and predictive values (diagnostic tests)")], p["effect"])
        pl.addWidget(_note("Rows are the groups (the exposed or treated group first) and columns the "
                           "outcomes (the outcome of interest first). For a diagnostic test, rows are the "
                           "test result (positive first) and columns the true condition (present first)."))
        self.c_assoc = QCheckBox("Strength of association (phi, or Cramér's V for larger tables)")
        self.c_assoc.setChecked(p["association"])
        pl.addWidget(self.c_assoc)
        pl.addStretch(1)
        self.add_section("effect", "Effect size", page, "ruler")

        page, pl = tab_page()
        g = FormGrid()
        self.rr_ci = combo([("Koopman asymptotic score (recommended)", "koopman"), ("Katz (older)", "katz")],
                           p["rr_ci"])
        self.diff_ci = combo([("Newcombe/Wilson, continuity-corrected (recommended)", "newcombe_cc"),
                              ("Newcombe/Wilson, uncorrected", "newcombe")], p["diff_ci"])
        self.or_ci = combo([("Baptista-Pike (recommended)", "baptista_pike"), ("Woolf (older)", "woolf")],
                           p["or_ci"])
        self.prop_ci = combo([("Wilson/Brown (recommended)", "wilson_brown"),
                              ("Clopper-Pearson exact (older)", "clopper_pearson")], p["prop_ci"])
        self.conf = combo(CONF, p["conf"])
        g.add(("Relative risk:", self.rr_ci))
        g.add(("Difference between proportions:", self.diff_ci))
        g.add(("Odds ratio:", self.or_ci))
        g.add(("Proportions, sensitivity …:", self.prop_ci))
        g.add(("Confidence level:", self.conf))
        pl.addLayout(g)
        pl.addStretch(1)
        self.add_section("intervals", "Intervals", page, "arrow.left.and.right")
        self.show_section("test")
        self.resize(900, 540)

    def params(self) -> dict:
        return {"test": _key(self.g_test), "yates": self.c_yates.isChecked(), "tails": self.tails.currentData(),
                "trend": self.c_trend.isChecked(), "effect": _key(self.g_effect),
                "association": self.c_assoc.isChecked(), "rr_ci": self.rr_ci.currentData(),
                "diff_ci": self.diff_ci.currentData(), "or_ci": self.or_ci.currentData(),
                "prop_ci": self.prop_ci.currentData(), "conf": self.conf.currentData()}


class SurvivalParamsDialog(SectionDialog):
    def __init__(self, params: dict | None, parent=None):
        super().__init__("Survival Settings", "Survival analysis", parent)
        p = {"event_code": 1, "censor_code": 0, "ci": "loglog", "conf": 0.95, "percent": True, **(params or {})}
        self.add_group("Settings")
        page, pl = tab_page()
        pl.addWidget(QLabel("Each row is one subject: its time in X, and in its group's column a code for\n"
                            "whether the event happened or the subject was censored."))
        g = FormGrid()
        self.ev, self.ce = QSpinBox(), QSpinBox()
        for w, v in ((self.ev, p["event_code"]), (self.ce, p["censor_code"])):
            w.setRange(-99, 99)
            w.setValue(int(v))
        g.add(("Event (death) code:", self.ev), ("Censored code:", self.ce))
        pl.addLayout(g)
        pl.addStretch(1)
        self.add_section("data", "Data", page, "tablecells")
        page, pl = tab_page()
        pl.addWidget(Section("Confidence intervals of the fraction surviving"))
        self.g_ci = _radio_group(self, pl, [("loglog", "Asymmetric (log-log transform): recommended"),
                                            ("symmetric", "Symmetric (±z·SE, clipped to 0–100%)")], p["ci"])
        g = FormGrid()
        self.conf = combo(CONF, p["conf"])
        self.pct = combo([("Percentages", True), ("Fractions", False)], p["percent"])
        g.add(("Confidence level:", self.conf), ("Report survival as:", self.pct))
        pl.addLayout(g)
        pl.addWidget(_note("Curves are compared with the log-rank (Mantel-Cox) and Gehan-Breslow-Wilcoxon "
                           "tests; three or more groups also get the log-rank test for trend; two groups get "
                           "hazard ratios and the ratio of median survival times."))
        pl.addStretch(1)
        self.add_section("output", "Output", page, "list.bullet")
        self.show_section("data")
        self.resize(720, 460)

    def params(self) -> dict:
        return {"event_code": self.ev.value(), "censor_code": self.ce.value(), "ci": _key(self.g_ci),
                "conf": self.conf.currentData(), "percent": self.pct.currentData()}


class FractionParamsDialog(SectionDialog):
    def __init__(self, params: dict | None, parent=None):
        super().__init__("Fraction of Total Settings", "Fraction of total", parent)
        p = {"of": "column", "percent": True, "ci": False, "conf": 0.95, **(params or {})}
        self.add_group("Settings")
        page, pl = tab_page()
        pl.addWidget(Section("Divide each value by"))
        self.g_of = _radio_group(self, pl, [("column", "Its column total"), ("row", "Its row total"),
                                            ("grand", "The grand total")], p["of"])
        g = FormGrid()
        self.pct = combo([("Percentages", True), ("Fractions", False)], p["percent"])
        self.conf = combo(CONF, p["conf"])
        g.add(("Show as:", self.pct))
        pl.addLayout(g)
        self.c_ci = QCheckBox("Confidence interval of each fraction (when the values are counts)")
        self.c_ci.setChecked(p["ci"])
        pl.addWidget(self.c_ci)
        g2 = FormGrid()
        g2.add(("Confidence level:", self.conf))
        pl.addLayout(g2)
        pl.addStretch(1)
        self.add_section("settings", "Fractions", page, "percent")
        self.show_section("settings")
        self.resize(640, 420)

    def params(self) -> dict:
        return {"of": _key(self.g_of), "percent": self.pct.currentData(), "ci": self.c_ci.isChecked(),
                "conf": self.conf.currentData()}
