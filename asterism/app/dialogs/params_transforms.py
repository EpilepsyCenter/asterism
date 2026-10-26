"""Settings dialogs for transforms that make result tables (section sidebar; Prism's
options, our wording)."""

from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QComboBox, QLabel, QLineEdit, QSpinBox

from ...analysis.transforms import BASELINE_OPS, X_FUNCS, Y_FUNCS
from .common import FormGrid, Section, SectionDialog, combo, set_combo, tab_page
from .params import _key, _note, _radio_group


def _num(v) -> QLineEdit:
    e = QLineEdit("" if v is None else f"{v:g}")
    e.setMaximumWidth(140)
    return e


def _val(e: QLineEdit, default=None):
    try:
        return float(e.text().replace(",", "."))
    except ValueError:
        return default


class TransformParamsDialog(SectionDialog):
    def __init__(self, params: dict | None, has_x: bool = False, parent=None):
        super().__init__("Transform Settings", "Transform", parent)
        p = {"y": "log10", "k": 1.0, "x": "none", "kx": 1.0, "equation": "Y = Y * K", **(params or {})}
        self.add_group("Settings")
        page, pl = tab_page()
        pl.addWidget(Section("Transform Y values"))
        g = FormGrid()
        self.y = combo([(v, k) for k, v in Y_FUNCS.items()], p["y"])
        self.k = _num(p["k"])
        self.eq = QLineEdit(p["equation"])
        self.eq.setPlaceholderText("Y = … (use Y, X and K; ^ for powers; log, ln, exp, sqrt)")
        g.add(("Y =", self.y), ("K =", self.k))
        g.add(("Equation:", self.eq))
        pl.addLayout(g)
        pl.addWidget(Section("Transform X values"))
        g2 = FormGrid()
        self.x = combo([(v, k) for k, v in X_FUNCS.items()], p["x"])
        self.kx = _num(p["kx"])
        g2.add(("X =", self.x), ("K =", self.kx))
        pl.addLayout(g2)
        self.x.setEnabled(has_x)
        self.kx.setEnabled(has_x)
        pl.addWidget(_note("Values that can't be transformed (such as the log of zero or a negative "
                           "number) are left blank in the result table."))
        pl.addStretch(1)
        self.add_section("transform", "Transform", page, "x.squareroot")
        self.y.currentIndexChanged.connect(lambda *_: self._sync())
        self._sync()
        self.show_section("transform")
        self.resize(720, 460)

    def _sync(self) -> None:
        self.eq.setEnabled(self.y.currentData() == "user")

    def params(self) -> dict:
        return {"y": self.y.currentData(), "k": _val(self.k, 1.0), "x": self.x.currentData(),
                "kx": _val(self.kx, 1.0), "equation": self.eq.text()}


class NormalizeParamsDialog(SectionDialog):
    def __init__(self, params: dict | None, parent=None):
        super().__init__("Normalize Settings", "Normalize", parent)
        p = {"zero": "min", "zero_value": 0.0, "hundred": "max", "hundred_value": 100.0, "percent": True,
             **(params or {})}
        self.add_group("Settings")
        page, pl = tab_page()
        g = FormGrid()
        self.zero = combo([("The smallest value in each data set", "min"), ("The first value", "first"),
                           ("A value", "value")], p["zero"])
        self.zv = _num(p["zero_value"])
        self.hundred = combo([("The largest value in each data set", "max"), ("The first value", "first"),
                              ("The last value", "last"),
                              ("The sum of the values", "sum"), ("The mean of the values", "mean"),
                              ("A value", "value")], p["hundred"])
        self.hv = _num(p["hundred_value"])
        self.pct = combo([("Percentages", True), ("Fractions", False)], p["percent"])
        g.add(("0% is:", self.zero), ("value:", self.zv))
        g.add(("100% is:", self.hundred), ("value:", self.hv))
        g.add(("Show the result as:", self.pct))
        pl.addLayout(g)
        pl.addWidget(_note("With replicates, the smallest and largest are taken from each row's mean; "
                           "every replicate is then normalized."))
        pl.addStretch(1)
        self.add_section("normalize", "Normalize", page, "percent")
        self.show_section("normalize")
        self.resize(720, 400)

    def params(self) -> dict:
        return {"zero": self.zero.currentData(), "zero_value": _val(self.zv, 0.0),
                "hundred": self.hundred.currentData(), "hundred_value": _val(self.hv, 100.0),
                "percent": self.pct.currentData()}


class BaselineParamsDialog(SectionDialog):
    def __init__(self, params: dict | None, table=None, columns=None, parent=None):
        super().__init__("Baseline and Column Maths Settings", "Remove baseline", parent)
        columns = list(columns or [])
        p = {"source": "set", "baseline": columns[0] if columns else 0, "rows": 1, "op": "subtract",
             "match_replicates": True, **(params or {})}
        self.add_group("Settings")
        page, pl = tab_page()
        pl.addWidget(Section("The baseline is"))
        self.g_src = _radio_group(self, pl, [("set", "A data set (row by row)"),
                                             ("rows", "The first rows of each data set")], p["source"])
        g = FormGrid()
        self.base = QComboBox()
        for c in (range(table.ncols) if table is not None else []):
            if table.label(c) and (c in columns or table.used_columns().count(c)):
                self.base.addItem(table.short_label(c), c)
        set_combo(self.base, p["baseline"])
        self.rows = QSpinBox()
        self.rows.setRange(1, 1000)
        self.rows.setValue(int(p["rows"]))
        g.add(("Baseline data set:", self.base), ("Baseline rows:", self.rows))
        pl.addLayout(g)
        self.c_match = QCheckBox("Match replicates (replicate 1 with replicate 1 …); otherwise use the "
                                 "baseline's mean")
        self.c_match.setChecked(p["match_replicates"])
        pl.addWidget(self.c_match)
        pl.addWidget(Section("Operation"))
        g2 = FormGrid()
        self.op = combo([(v, k) for k, v in BASELINE_OPS.items()], p["op"])
        g2.add(("Each value:", self.op))
        pl.addLayout(g2)
        pl.addStretch(1)
        self.add_section("baseline", "Baseline", page, "minus.forwardslash.plus")
        self.g_src.buttonToggled.connect(lambda *_: self._sync())
        self._sync()
        self.show_section("baseline")
        self.resize(760, 460)

    def _sync(self) -> None:
        rows = _key(self.g_src) == "rows"
        self.base.setEnabled(not rows)
        self.c_match.setEnabled(not rows)
        self.rows.setEnabled(rows)

    def params(self) -> dict:
        return {"source": _key(self.g_src), "baseline": self.base.currentData(), "rows": self.rows.value(),
                "op": self.op.currentData(), "match_replicates": self.c_match.isChecked()}


class PruneParamsDialog(SectionDialog):
    def __init__(self, params: dict | None, has_x: bool = False, parent=None):
        super().__init__("Prune Rows Settings", "Prune rows", parent)
        p = {"mode": "range", "from": None, "to": None, "n": 2, "k": 2, **(params or {})}
        self.add_group("Settings")
        page, pl = tab_page()
        self.g_mode = _radio_group(self, pl, [
            ("range", "Keep the rows with X between …" if has_x else "Keep rows from … to …"),
            ("every", "Keep every nth row"), ("average", "Average every k rows")], p["mode"])
        g = FormGrid()
        self.lo, self.hi = _num(p["from"]), _num(p["to"])
        self.n, self.k = QSpinBox(), QSpinBox()
        for w, v in ((self.n, p["n"]), (self.k, p["k"])):
            w.setRange(1, 10000)
            w.setValue(int(v))
        g.add(("From:", self.lo), ("to:", self.hi))
        g.add(("n:", self.n), ("k:", self.k))
        pl.addLayout(g)
        pl.addStretch(1)
        self.add_section("prune", "Prune", page, "scissors")
        self.show_section("prune")
        self.resize(640, 380)

    def params(self) -> dict:
        return {"mode": _key(self.g_mode), "from": _val(self.lo), "to": _val(self.hi), "n": self.n.value(),
                "k": self.k.value()}


class SmoothParamsDialog(SectionDialog):
    def __init__(self, params: dict | None, parent=None):
        super().__init__("Smooth, Differentiate or Integrate", "Smooth", parent)
        p = {"op": "smooth", "k": 2, "order": 2, "smooth_after": False, "start": 0.0, **(params or {})}
        self.add_group("Settings")
        page, pl = tab_page()
        self.g_op = _radio_group(self, pl, [("smooth", "Smooth the curve"), ("derivative", "First derivative"),
                                            ("derivative2", "Second derivative"),
                                            ("integral", "Integral (cumulative area)")], p["op"])
        g = FormGrid()
        self.k = QSpinBox()
        self.k.setRange(1, 100)
        self.k.setValue(int(p["k"]))
        self.order = combo([("Zero order (moving average)", 0), ("Second order (Savitzky-Golay)", 2)], p["order"])
        self.start = _num(p["start"])
        g.add(("Neighbours on each side:", self.k), ("Smoothing polynomial:", self.order))
        g.add(("Integral starts at Y =", self.start))
        pl.addLayout(g)
        self.c_after = QCheckBox("Smooth the derivative or integral")
        self.c_after.setChecked(p["smooth_after"])
        pl.addWidget(self.c_after)
        pl.addWidget(_note("Smoothing drops as many points at each end as there are neighbours. Don't "
                           "analyse smoothed data: smoothing can create trends in random noise."))
        pl.addStretch(1)
        self.add_section("smooth", "Curve", page, "waveform.path")
        self.show_section("smooth")
        self.resize(700, 440)

    def params(self) -> dict:
        return {"op": _key(self.g_op), "k": self.k.value(), "order": self.order.currentData(),
                "smooth_after": self.c_after.isChecked(), "start": _val(self.start, 0.0)}


class ObservedExpectedParamsDialog(SectionDialog):
    def __init__(self, params: dict | None, parent=None):
        super().__init__("Observed vs. Expected Settings", "Compare observed and expected", parent)
        p = {"expected": "equal", "expected_as": "counts", **(params or {})}
        self.add_group("Settings")
        page, pl = tab_page()
        pl.addWidget(QLabel("The first data set holds the observed counts, one category per row."))
        self.g_exp = _radio_group(self, pl, [("equal", "Expect equal counts in every category"),
                                             ("column", "Expected values are in the second data set")],
                                  p["expected"])
        g = FormGrid()
        self.as_ = combo([("Counts (or relative numbers)", "counts"), ("Percentages", "percent")], p["expected_as"])
        g.add(("Expected values are:", self.as_))
        pl.addLayout(g)
        pl.addStretch(1)
        self.add_section("expected", "Expected", page, "list.number")
        self.show_section("expected")
        self.resize(640, 360)

    def params(self) -> dict:
        return {"expected": _key(self.g_exp), "expected_as": self.as_.currentData()}
