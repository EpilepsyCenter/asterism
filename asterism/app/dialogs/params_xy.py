"""Settings dialogs for XY analyses (section sidebar; Prism's options, our wording):
linear regression, correlation, area under the curve, nonlinear regression."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QHBoxLayout, QHeaderView,
                               QLabel, QLineEdit, QListWidget, QListWidgetItem, QSpinBox,
                               QTableWidget, QWidget)

from ...analysis.models import BY_KEY, FAMILIES, MODELS, user_model
from ...analysis.nonlin import WEIGHTINGS
from .common import FormGrid, Section, SectionDialog, combo, set_combo, tab_page
from .params import _key, _note, _radio_group

CONF = [("90%", 0.90), ("95%", 0.95), ("99%", 0.99)]
BANDS = [("No bands", "none"), ("Confidence bands", "confidence"), ("Prediction bands", "prediction")]


def _num(v=None) -> QLineEdit:
    e = QLineEdit("" if v is None else f"{v:g}")
    e.setPlaceholderText("automatic")
    e.setMaximumWidth(140)
    return e


def _val(e: QLineEdit):
    try:
        return float(e.text().replace(",", "."))
    except ValueError:
        return None


class LinRegParamsDialog(SectionDialog):
    def __init__(self, params: dict | None, parent=None):
        super().__init__("Linear Regression Settings", "Linear regression", parent)
        p = {"replicates": "individual", "through": False, "x0": 0.0, "y0": 0.0, "compare": False,
             "interpolate": False, "runs_test": False, "linearity_test": False, "conf": 0.95,
             "bands": "none", "graph": True, **(params or {})}
        self.add_group("Settings")
        page, pl = tab_page()
        pl.addWidget(Section("Replicates"))
        self.g_reps = _radio_group(self, pl, [("individual", "Each replicate is a separate point"),
                                              ("mean", "Fit the mean of the replicates")], p["replicates"])
        pl.addWidget(Section("Constraint"))
        self.c_through = QCheckBox("Force the line through a point")
        self.c_through.setChecked(p["through"])
        pl.addWidget(self.c_through)
        g = FormGrid()
        self.x0, self.y0 = _num(p["x0"]), _num(p["y0"])
        g.add(("X:", self.x0), ("Y:", self.y0))
        pl.addLayout(g)
        pl.addStretch(1)
        self.add_section("fit", "Fit", page, "function")

        page, pl = tab_page()
        self.c_compare = QCheckBox("Test whether the slopes and intercepts differ between data sets")
        self.c_compare.setChecked(p["compare"])
        pl.addWidget(self.c_compare)
        pl.addWidget(_note("Slopes are compared first; intercepts only when the slopes don't differ."))
        pl.addStretch(1)
        self.add_section("compare", "Compare", page, "arrow.left.arrow.right")

        page, pl = tab_page()
        for attr, text in (("interpolate", "Interpolate unknowns (rows with Y but no X, or X but no Y)"),
                           ("runs_test", "Runs test: do the points systematically deviate from the line?"),
                           ("linearity_test", "Replicates test: does the line fit worse than replicates scatter?")):
            c = QCheckBox(text)
            c.setChecked(p[attr])
            setattr(self, "c_" + attr, c)
            pl.addWidget(c)
        g = FormGrid()
        self.conf = combo(CONF, p["conf"])
        g.add(("Confidence intervals:", self.conf))
        pl.addLayout(g)
        pl.addStretch(1)
        self.add_section("output", "Output", page, "list.bullet")

        page, pl = tab_page()
        self.c_graph = QCheckBox("Draw the line on the graph of the data")
        self.c_graph.setChecked(p["graph"])
        pl.addWidget(self.c_graph)
        g = FormGrid()
        self.bands = combo(BANDS, p["bands"])
        g.add(("Bands:", self.bands))
        pl.addLayout(g)
        pl.addStretch(1)
        self.add_section("graph", "Graph", page, "chart.xyaxis.line")
        self.show_section("fit")
        self.resize(720, 500)

    def params(self) -> dict:
        return {"replicates": _key(self.g_reps), "through": self.c_through.isChecked(),
                "x0": _val(self.x0) or 0.0, "y0": _val(self.y0) or 0.0, "compare": self.c_compare.isChecked(),
                "interpolate": self.c_interpolate.isChecked(), "runs_test": self.c_runs_test.isChecked(),
                "linearity_test": self.c_linearity_test.isChecked(), "conf": self.conf.currentData(),
                "bands": self.bands.currentData(), "graph": self.c_graph.isChecked()}


class CorrelationParamsDialog(SectionDialog):
    def __init__(self, params: dict | None, parent=None):
        super().__init__("Correlation Settings", "Correlation", parent)
        p = {"method": "pearson", "conf": 0.95, **(params or {})}
        self.add_group("Settings")
        page, pl = tab_page()
        pl.addWidget(Section("Correlation coefficient"))
        self.g_method = _radio_group(self, pl, [("pearson", "Pearson (assumes a Gaussian distribution)"),
                                                ("spearman", "Spearman (nonparametric, rank-based)")], p["method"])
        pl.addWidget(_note("XY tables: X is correlated with each data set, using the mean of each row's "
                           "replicates. Column tables: every pair of data sets."))
        g = FormGrid()
        self.conf = combo(CONF, p["conf"])
        g.add(("Confidence interval:", self.conf))
        pl.addLayout(g)
        pl.addStretch(1)
        self.add_section("method", "Method", page, "function")
        self.show_section("method")
        self.resize(640, 400)

    def params(self) -> dict:
        return {"method": _key(self.g_method), "conf": self.conf.currentData()}


class AucParamsDialog(SectionDialog):
    def __init__(self, params: dict | None, parent=None):
        super().__init__("Area Under the Curve Settings", "Area under the curve", parent)
        p = {"baseline": 0.0, "min_peak_frac": 0.10, "min_peak_points": 1, "below": False, "conf": 0.95,
             **(params or {})}
        self.add_group("Settings")
        page, pl = tab_page()
        g = FormGrid()
        self.baseline = _num(p["baseline"])
        self.baseline.setPlaceholderText("0")
        self.frac = QDoubleSpinBox()
        self.frac.setRange(0, 100)
        self.frac.setSuffix(" %")
        self.frac.setValue(p["min_peak_frac"] * 100)
        self.pts = QSpinBox()
        self.pts.setRange(1, 1000)
        self.pts.setValue(p["min_peak_points"])
        self.conf = combo(CONF, p["conf"])
        g.add(("Baseline (Y =):", self.baseline))
        g.add(("Ignore peaks smaller than:", self.frac))
        g.add(("…or defined by fewer points than:", self.pts))
        g.add(("Confidence interval:", self.conf))
        pl.addLayout(g)
        pl.addWidget(_note("Peak size is measured as a percentage of the distance from the smallest to "
                           "the largest Y."))
        self.c_below = QCheckBox("Also count peaks that go below the baseline")
        self.c_below.setChecked(p["below"])
        pl.addWidget(self.c_below)
        pl.addStretch(1)
        self.add_section("peaks", "Baseline and peaks", page, "waveform.path")
        self.show_section("peaks")
        self.resize(640, 420)

    def params(self) -> dict:
        return {"baseline": _val(self.baseline) or 0.0, "min_peak_frac": self.frac.value() / 100,
                "min_peak_points": self.pts.value(), "below": self.c_below.isChecked(),
                "conf": self.conf.currentData()}


# ---------------------------------------------------------------------------
# Nonlinear regression
# ---------------------------------------------------------------------------

MODES = [("Fit", "fit"), ("Constant equal to", "constant"), ("Shared by all data sets", "shared"),
         ("Fit within bounds", "bounds")]


class NonlinParamsDialog(SectionDialog):
    def __init__(self, params: dict | None, ncols: int = 1, parent=None):
        super().__init__("Nonlinear Regression Settings", "Nonlinear regression", parent)
        p = {"model": "agonist_4", "equation": "Y = Bottom + (Top-Bottom)/(1+exp(-K*(X-X50)))",
             "replicates": "individual", "weighting": "none", "compare": "none", "compare_method": "f",
             "model_b": "agonist_3", "compare_param": None, "constraints": {}, "initial": {},
             "x_min": None, "x_max": None, "curve_from": None, "curve_to": None, "interpolate": False,
             "residuals": False, "runs_test": False, "outliers": "none", "rout_q": 0.01,
             "ci_method": "profile", "report_se": False, "conf": 0.95, "bands": "none", "graph": True,
             **(params or {})}
        self.p = p
        self.ncols = ncols
        self.add_group("Settings")

        # Model --------------------------------------------------------------------------
        page, pl = tab_page()
        row = QHBoxLayout()
        self.families = QListWidget()
        self.families.setMaximumWidth(230)
        for fam in FAMILIES + ["User-defined"]:
            self.families.addItem(fam)
        self.models = QListWidget()
        row.addWidget(self.families)
        row.addWidget(self.models, 1)
        pl.addLayout(row, 1)
        self.formula = QLabel()
        self.formula.setWordWrap(True)
        self.formula.setTextInteractionFlags(Qt.TextSelectableByMouse)
        pl.addWidget(self.formula)
        self.desc = _note("")
        pl.addWidget(self.desc)
        self.equation = QLineEdit(p["equation"])
        self.equation.setPlaceholderText("Y = … (use X; ^ for powers; exp, ln, log, sqrt, sin, cos)")
        self.equation.editingFinished.connect(self._model_changed)
        pl.addWidget(self.equation)
        self.add_section("model", "Model", page, "function")

        # Method -------------------------------------------------------------------------
        page, pl = tab_page()
        pl.addWidget(Section("Replicates"))
        self.g_reps = _radio_group(self, pl, [("individual", "Each replicate is a separate point"),
                                              ("mean", "Fit the mean of the replicates")], p["replicates"])
        pl.addWidget(Section("Weighting"))
        g = FormGrid()
        self.weighting = combo([(v, k) for k, v in WEIGHTINGS.items()], p["weighting"])
        g.add(("Minimize:", self.weighting))
        pl.addLayout(g)
        pl.addWidget(_note("Weights by Y use the Y of the curve, not of the data, so a point's weight "
                           "doesn't depend on its own scatter."))
        pl.addWidget(Section("Outliers (ROUT)"))
        self.g_out = _radio_group(self, pl, [("none", "No outlier detection"),
                                             ("identify", "Identify outliers"),
                                             ("exclude", "Identify outliers and leave them out of the fit")],
                                  p["outliers"])
        g = FormGrid()
        self.q = QDoubleSpinBox()
        self.q.setRange(0.01, 10)
        self.q.setSuffix(" %")
        self.q.setValue(p["rout_q"] * 100)
        g.add(("Q (false discovery rate):", self.q))
        pl.addLayout(g)
        pl.addStretch(1)
        self.add_section("method", "Method", page, "slider.horizontal.3")

        # Compare ------------------------------------------------------------------------
        page, pl = tab_page()
        self.g_cmp = _radio_group(self, pl, [
            ("none", "No comparison"),
            ("models", "Compare this model with another model"),
            ("one_curve", "Is one curve adequate for all data sets?"),
            ("param", "Does one parameter differ between data sets?")], p["compare"])
        g = FormGrid()
        self.model_b = QComboBox()
        for m in MODELS:
            self.model_b.addItem(f"{m.family}: {m.name}", m.key)
        set_combo(self.model_b, p["model_b"])
        self.cmp_param = QComboBox()
        self.cmp_method = combo([("Extra sum-of-squares F test", "f"), ("AICc (information criterion)", "aicc")],
                                p["compare_method"])
        g.add(("Other model:", self.model_b))
        g.add(("Parameter:", self.cmp_param))
        g.add(("Test:", self.cmp_method))
        pl.addLayout(g)
        pl.addWidget(_note("The F test needs nested models (the simpler one a special case of the other). "
                           "AICc works for any pair."))
        pl.addStretch(1)
        self.add_section("compare", "Compare", page, "arrow.left.arrow.right")

        # Constrain ----------------------------------------------------------------------
        page, pl = tab_page()
        self.cons = QTableWidget(0, 4)
        self.cons.setHorizontalHeaderLabels(["Parameter", "How", "Value", "Upper bound"])
        self.cons.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.cons.verticalHeader().setVisible(False)
        pl.addWidget(self.cons, 1)
        pl.addWidget(_note("“Constant” holds the parameter at the value; “Fit within bounds” uses Value as "
                           "the lower bound. “Shared” fits one value for every data set (a global fit)."))
        self.add_section("constrain", "Constrain", page, "lock")

        # Initial values ---------------------------------------------------------------
        page, pl = tab_page()
        self.init = QTableWidget(0, 2)
        self.init.setHorizontalHeaderLabels(["Parameter", "Initial value"])
        self.init.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.init.verticalHeader().setVisible(False)
        pl.addWidget(self.init, 1)
        pl.addWidget(_note("Leave blank for an automatic value from the range and shape of the data."))
        self.add_section("initial", "Initial values", page, "arrow.right.to.line")

        # Range ----------------------------------------------------------------------------
        page, pl = tab_page()
        g = FormGrid()
        self.x_min, self.x_max = _num(p["x_min"]), _num(p["x_max"])
        self.c_from, self.c_to = _num(p["curve_from"]), _num(p["curve_to"])
        g.add(("Fit only X from:", self.x_min), ("to:", self.x_max))
        g.add(("Draw the curve from X =", self.c_from), ("to:", self.c_to))
        pl.addLayout(g)
        pl.addStretch(1)
        self.add_section("range", "Range", page, "arrow.left.and.right")

        # Output and confidence ---------------------------------------------------------
        page, pl = tab_page()
        for attr, text in (("interpolate", "Interpolate unknowns"),
                           ("residuals", "Table of residuals"),
                           ("runs_test", "Runs test")):
            c = QCheckBox(text)
            c.setChecked(p[attr])
            setattr(self, "c_" + attr, c)
            pl.addWidget(c)
        pl.addStretch(1)
        self.add_section("output", "Output", page, "list.bullet")

        page, pl = tab_page()
        pl.addWidget(Section("Confidence intervals of the parameters"))
        self.g_ci = _radio_group(self, pl, [("profile", "Asymmetric (profile likelihood): recommended"),
                                            ("asymptotic", "Symmetric (asymptotic)")], p["ci_method"])
        self.c_se = QCheckBox("Also report standard errors")
        self.c_se.setChecked(p["report_se"])
        pl.addWidget(self.c_se)
        g = FormGrid()
        self.conf = combo(CONF, p["conf"])
        self.bands = combo(BANDS, p["bands"])
        g.add(("Confidence level:", self.conf))
        g.add(("Bands on the graph:", self.bands))
        pl.addLayout(g)
        self.c_graph = QCheckBox("Draw the curve on the graph of the data")
        self.c_graph.setChecked(p["graph"])
        pl.addWidget(self.c_graph)
        pl.addStretch(1)
        self.add_section("confidence", "Confidence", page, "chart.line.uptrend.xyaxis")

        self.families.currentRowChanged.connect(self._family_changed)
        self.models.currentItemChanged.connect(lambda *_: self._model_changed())
        cur = BY_KEY.get(p["model"])
        fam = cur.family if cur else "User-defined"
        self.families.setCurrentRow((FAMILIES + ["User-defined"]).index(fam))
        if cur:
            for i in range(self.models.count()):
                if self.models.item(i).data(Qt.UserRole) == cur.key:
                    self.models.setCurrentRow(i)
        self.show_section("model")
        self.resize(900, 640)

    def _family_changed(self, row: int) -> None:
        fam = (FAMILIES + ["User-defined"])[row]
        self.models.blockSignals(True)
        self.models.clear()
        if fam == "User-defined":
            it = QListWidgetItem("User-defined equation")
            it.setData(Qt.UserRole, "user")
            self.models.addItem(it)
        else:
            for m in MODELS:
                if m.family == fam:
                    it = QListWidgetItem(m.name)
                    it.setData(Qt.UserRole, m.key)
                    self.models.addItem(it)
        self.models.blockSignals(False)
        self.models.setCurrentRow(0)
        self._model_changed()

    def _current_model(self):
        it = self.models.currentItem()
        key = it.data(Qt.UserRole) if it else "agonist_4"
        if key == "user":
            try:
                return user_model(self.equation.text())
            except Exception as e:
                self.formula.setText(f"Equation problem: {e}")
                return None
        return BY_KEY[key]

    def _model_changed(self) -> None:
        it = self.models.currentItem()
        self.equation.setVisible(bool(it) and it.data(Qt.UserRole) == "user")
        m = self._current_model()
        if m is None:
            return
        self.formula.setText(m.formula)
        self.desc.setText(m.description)
        sig = (m.key, tuple(m.params))
        if getattr(self, "_built_for", None) == sig:
            return
        self._built_for = sig
        cons, init = self.p.get("constraints") or {}, self.p.get("initial") or {}
        for tbl in (self.cons, self.init):
            tbl.clearContents()
            tbl.setRowCount(0)
        self.cons.setRowCount(len(m.params))
        self.init.setRowCount(len(m.params))
        self.cmp_param.clear()
        for i, name in enumerate(m.params):
            self.cmp_param.addItem(name, name)
            c = cons.get(name, {})
            for tbl in (self.cons, self.init):
                lab = QLabel(name)
                lab.setContentsMargins(6, 0, 0, 0)
                tbl.setCellWidget(i, 0, lab)
            has_bounds = c.get("lo") is not None or c.get("hi") is not None
            how = combo(MODES, "bounds" if has_bounds and c.get("mode", "fit") == "fit" else c.get("mode", "fit"))
            if self.ncols < 2:
                how.model().item(2).setEnabled(False)
            self.cons.setCellWidget(i, 1, how)
            v = c.get("value", c.get("lo"))
            self.cons.setCellWidget(i, 2, _num(v))
            self.cons.setCellWidget(i, 3, _num(c.get("hi")))
            self.init.setCellWidget(i, 1, _num(init.get(name)))
        if self.p.get("compare_param"):
            set_combo(self.cmp_param, self.p["compare_param"])

    def params(self) -> dict:
        m = self._current_model()
        key = self.models.currentItem().data(Qt.UserRole) if self.models.currentItem() else "agonist_4"
        cons, init = {}, {}
        if m is not None:
            for i, name in enumerate(m.params):
                how = self.cons.cellWidget(i, 1).currentData()
                v, hi = _val(self.cons.cellWidget(i, 2)), _val(self.cons.cellWidget(i, 3))
                if how == "constant" and v is not None:
                    cons[name] = {"mode": "constant", "value": v}
                elif how == "shared":
                    cons[name] = {"mode": "shared"}
                elif how == "bounds" and (v is not None or hi is not None):
                    cons[name] = {"mode": "fit", "lo": v, "hi": hi}
                iv = _val(self.init.cellWidget(i, 1))
                if iv is not None:
                    init[name] = iv
        return {"model": key, "equation": self.equation.text(), "replicates": _key(self.g_reps),
                "weighting": self.weighting.currentData(), "outliers": _key(self.g_out),
                "rout_q": self.q.value() / 100, "compare": _key(self.g_cmp),
                "model_b": self.model_b.currentData(), "compare_param": self.cmp_param.currentData(),
                "compare_method": self.cmp_method.currentData(), "constraints": cons, "initial": init,
                "x_min": _val(self.x_min), "x_max": _val(self.x_max), "curve_from": _val(self.c_from),
                "curve_to": _val(self.c_to), "interpolate": self.c_interpolate.isChecked(),
                "residuals": self.c_residuals.isChecked(), "runs_test": self.c_runs_test.isChecked(),
                "ci_method": _key(self.g_ci), "report_se": self.c_se.isChecked(),
                "conf": self.conf.currentData(), "bands": self.bands.currentData(),
                "graph": self.c_graph.isChecked()}
