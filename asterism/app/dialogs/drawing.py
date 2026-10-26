"""Format a drawn line, arrow, box, ellipse, text or picture."""

from __future__ import annotations

import copy

from PySide6.QtWidgets import QCheckBox, QDoubleSpinBox, QPlainTextEdit

from ..graph.canvas import MM
from ..graph.drawings import NAMES
from .common import ColorButton, FormGrid, Section, SectionDialog, combo, tab_page

THICK = [("None", 0.0), ("¼ pt", 0.25), ("½ pt", 0.5), ("1 pt", 1.0), ("1½ pt", 1.5), ("2 pt", 2.0),
         ("3 pt", 3.0), ("4 pt", 4.0)]


def _mm(v: float, lo: float = -500.0) -> QDoubleSpinBox:
    s = QDoubleSpinBox()
    s.setRange(lo, 1000.0)
    s.setDecimals(1)
    s.setSuffix(" mm")
    s.setValue(v / MM)
    return s


class DrawingDialog(SectionDialog):
    def __init__(self, d: dict, parent=None):
        super().__init__(f"Format {NAMES[d['kind']]}", "Drawing", parent)
        self.d = copy.deepcopy(d)
        k = d["kind"]
        self.add_group("Drawing")
        page, pl = tab_page()
        if k == "text":
            pl.addWidget(Section("Text"))
            self.text = QPlainTextEdit(d.get("text", ""))
            self.text.setFixedHeight(90)
            pl.addWidget(self.text)
            g = FormGrid()
            self.size = QDoubleSpinBox()
            self.size.setRange(4, 96)
            self.size.setSuffix(" pt")
            self.size.setValue(float(d.get("size", 12)))
            self.bold, self.italic = QCheckBox("Bold"), QCheckBox("Italic")
            self.bold.setChecked(bool(d.get("bold")))
            self.italic.setChecked(bool(d.get("italic")))
            self.color = ColorButton(d.get("color") or "#000000")
            g.add(("Size:", self.size), ("Colour:", self.color))
            g.add((None, self.bold), (None, self.italic))
            pl.addLayout(g)
        elif k != "image":
            pl.addWidget(Section("Line"))
            g = FormGrid()
            self.width = combo(THICK if k in ("rect", "ellipse") else THICK[1:], float(d.get("width", 1.0)))
            self.dash = combo([("Solid", "solid"), ("Dashed", "dash"), ("Dotted", "dot")], d.get("dash", "solid"))
            self.color = ColorButton(d.get("color") or "#000000")
            g.add(("Thickness:", self.width), ("Style:", self.dash))
            g.add(("Colour:", self.color))
            if k == "arrow":
                self.head = combo([("At the end", "end"), ("At both ends", "both")], d.get("head", "end"))
                g.add(("Arrowheads:", self.head))
            pl.addLayout(g)
            if k in ("rect", "ellipse"):
                pl.addWidget(Section("Fill"))
                g = FormGrid()
                self.filled = QCheckBox("Fill the shape")
                self.filled.setChecked(bool(d.get("fill")))
                self.fill = ColorButton(d.get("fill") or "#e6e6e6")
                g.add((None, self.filled), ("Colour:", self.fill))
                pl.addLayout(g)
        pl.addWidget(Section("Position"))
        g = FormGrid()
        self.x1, self.y1 = _mm(d["x1"]), _mm(d["y1"])
        g.add(("Left:" if k != "line" and k != "arrow" else "Start X:", self.x1),
              ("Top:" if k != "line" and k != "arrow" else "Start Y:", self.y1))
        if k in ("line", "arrow"):
            self.x2, self.y2 = _mm(d["x2"]), _mm(d["y2"])
            g.add(("End X:", self.x2), ("End Y:", self.y2))
        elif k != "text":
            self.w, self.h = _mm(abs(d["x2"] - d["x1"]), 0.5), _mm(abs(d["y2"] - d["y1"]), 0.5)
            g.add(("Width:", self.w), ("Height:", self.h))
        pl.addLayout(g)
        pl.addStretch(1)
        self.add_section("format", NAMES[k], page, "pencil")
        self.show_section("format")
        self.resize(620, 420)

    def value(self) -> dict:
        d, k = copy.deepcopy(self.d), self.d["kind"]
        if k == "text":
            d.update(text=self.text.toPlainText(), size=self.size.value(), bold=self.bold.isChecked(),
                     italic=self.italic.isChecked(), color=self.color.color())
        elif k != "image":
            d.update(width=self.width.currentData(), dash=self.dash.currentData(), color=self.color.color())
            if k == "arrow":
                d["head"] = self.head.currentData()
            if k in ("rect", "ellipse"):
                d["fill"] = self.fill.color() if self.filled.isChecked() else ""
        d["x1"], d["y1"] = self.x1.value() * MM, self.y1.value() * MM
        if k in ("line", "arrow"):
            d["x2"], d["y2"] = self.x2.value() * MM, self.y2.value() * MM
        elif k != "text":
            d["x2"], d["y2"] = d["x1"] + self.w.value() * MM, d["y1"] + self.h.value() * MM
        else:
            d["x2"], d["y2"] = d["x1"], d["y1"]
        return d
