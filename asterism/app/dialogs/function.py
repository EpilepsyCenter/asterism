"""Plot a function on an XY graph: the equation, its constants, the X range, the line."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QHeaderView, QLabel, QLineEdit, QTableWidget, QTableWidgetItem

from .common import ColorButton, FormGrid, Section, SectionDialog, combo, tab_page

THICK = [("¼ pt", 0.25), ("½ pt", 0.5), ("1 pt", 1.0), ("1½ pt", 1.5), ("2 pt", 2.0), ("3 pt", 3.0)]
EXAMPLES = ["Y = Bottom + (Top-Bottom)/(1+10^((LogEC50-X)*HillSlope))", "Y = Y0*exp(-K*X)", "Y = Slope*X + Intercept",
            "Y = Vmax*X/(Km + X)"]


def _num(v) -> QLineEdit:
    e = QLineEdit("" if v is None else f"{v:g}")
    e.setFixedWidth(110)
    return e


class FunctionDialog(SectionDialog):
    def __init__(self, fn: dict | None = None, auto_range=None, parent=None):
        super().__init__("Plot a Function", "Plot a function", parent)
        fn = dict(fn or {})
        self.add_group("Function")
        page, pl = tab_page()
        pl.addWidget(Section("Equation"))
        self.text = QLineEdit(fn.get("text", "Y = Y0*exp(-K*X)"))
        pl.addWidget(self.text)
        hint = QLabel("Use X, numbers, + − * / ^, and exp, ln, log (base 10), sqrt, sin, cos, abs … "
                      "Every other name is a constant you set below.   e.g. " + EXAMPLES[0])
        hint.setWordWrap(True)
        hint.setEnabled(False)
        pl.addWidget(hint)
        self.err = QLabel("")
        self.err.setStyleSheet("color: #b3261e;")
        pl.addWidget(self.err)
        pl.addWidget(Section("Constants"))
        self.params = QTableWidget(0, 2)
        self.params.setHorizontalHeaderLabels(["Name", "Value"])
        self.params.verticalHeader().hide()
        self.params.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.params.setFixedHeight(130)
        pl.addWidget(self.params)
        self._values = {k: float(v) for k, v in (fn.get("params") or {}).items()}

        pl.addWidget(Section("Range and line"))
        g = FormGrid()
        self.auto = QCheckBox("Across the whole X axis")
        self.auto.setChecked(fn.get("from") is None and fn.get("to") is None)
        lo = fn.get("from") if fn.get("from") is not None else (auto_range.vmin if auto_range else 0.0)
        hi = fn.get("to") if fn.get("to") is not None else (auto_range.vmax if auto_range else 10.0)
        self.x_from, self.x_to = _num(lo), _num(hi)
        g.add((None, self.auto))
        g.add(("From X =", self.x_from), ("To X =", self.x_to))
        self.color = ColorButton(fn.get("color") or "#000000")
        self.width = combo(THICK, float(fn.get("width", 1.0)))
        self.dash = combo([("Solid", "solid"), ("Dashed", "dash"), ("Dotted", "dot")], fn.get("dash", "solid"))
        g.add(("Colour:", self.color), ("Thickness:", self.width))
        g.add(("Style:", self.dash))
        pl.addLayout(g)
        pl.addStretch(1)
        self.add_section("function", "Function", page, "function")
        self.text.textChanged.connect(self._parse)
        self.auto.toggled.connect(lambda on: [w.setEnabled(not on) for w in (self.x_from, self.x_to)])
        self.x_from.setEnabled(not self.auto.isChecked())
        self.x_to.setEnabled(not self.auto.isChecked())
        self._parse()
        self.show_section("function")
        self.resize(720, 560)

    def _read_params(self) -> None:
        for i in range(self.params.rowCount()):
            name = self.params.item(i, 0).text()
            try:
                self._values[name] = float(self.params.item(i, 1).text().replace(",", "."))
            except (ValueError, AttributeError):
                pass

    def _parse(self, *_) -> None:
        from ...analysis.function import parse
        self._read_params()
        try:
            _, names = parse(self.text.text())
            self.err.setText("")
            self.ok.setEnabled(True)
        except (ValueError, SyntaxError) as e:
            self.err.setText(str(e) if isinstance(e, ValueError) else "The equation isn't complete.")
            self.ok.setEnabled(False)
            return
        self.params.setRowCount(len(names))
        for i, n in enumerate(names):
            it = QTableWidgetItem(n)
            it.setFlags(Qt.ItemIsEnabled)
            self.params.setItem(i, 0, it)
            self.params.setItem(i, 1, QTableWidgetItem(f"{self._values.get(n, 1.0):g}"))

    def value(self) -> dict:
        from ...analysis.function import parse
        self._read_params()
        _, names = parse(self.text.text())

        def f(e, default):
            try:
                return float(e.text().replace(",", "."))
            except ValueError:
                return default
        auto = self.auto.isChecked()
        return {"text": self.text.text().strip(), "params": {n: self._values.get(n, 1.0) for n in names},
                "from": None if auto else f(self.x_from, 0.0), "to": None if auto else f(self.x_to, 10.0),
                "color": self.color.color(), "width": self.width.currentData(), "dash": self.dash.currentData()}
