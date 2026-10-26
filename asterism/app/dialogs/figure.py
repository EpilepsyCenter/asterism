"""Figure dialogs: add panels, format the figure (page, panel letters, grid), edit text."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QDoubleSpinBox, QFontComboBox, QListWidget, QListWidgetItem,
                               QPlainTextEdit, QSpinBox)

from ...doc.model import LETTER_STYLES, PAGE_SIZES
from ..graph.layout import GRAPHABLE_TYPES
from .common import FormGrid, Section, SectionDialog, combo, tab_page
from .params import _note


def _mm(v, lo=1.0, hi=2000.0) -> QDoubleSpinBox:
    s = QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setDecimals(1)
    s.setSuffix(" mm")
    s.setValue(float(v))
    return s


class AddPanelsDialog(SectionDialog):
    """Choose graphs, tables and results to place on the figure."""

    def __init__(self, project, preselect=None, parent=None):
        super().__init__("Add to Figure", "Figures", parent)
        self.project = project
        self.add_group("Add")
        self.lists = {}
        sources = {
            "graph": [(g.name, ("graph", g.id)) for g in project.graphs if g.table.table_type in GRAPHABLE_TYPES],
            "table": [(t.name, ("table", t.id)) for t in project.tables]
                     + [(f"Results: {t.name}", ("table", t.id)) for t in project.analysis_outputs()],
            "results": [(a.name, ("results", a.id)) for a in project.analyses if a.result and not a.result.error],
        }
        titles = {"graph": ("Graphs", "chart.xyaxis.line"), "table": ("Data and result tables", "tablecells"),
                  "results": ("Analysis results", "doc.text")}
        for key, items in sources.items():
            page, pl = tab_page()
            lst = QListWidget()
            for name, data in items:
                it = QListWidgetItem(name)
                it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
                it.setCheckState(Qt.Checked if preselect and data[1] in preselect else Qt.Unchecked)
                it.setData(Qt.UserRole, data)
                lst.addItem(it)
            pl.addWidget(lst, 1)
            if not items:
                pl.addWidget(_note("Nothing of this kind in the project yet."))
            self.lists[key] = lst
            self.add_section(key, titles[key][0], page, titles[key][1])
        g = FormGrid()
        self.columns = QSpinBox()
        self.columns.setRange(1, 6)
        self.columns.setValue(2)
        g.add(("Place new panels in columns:", self.columns))
        self.footer.addLayout(g)
        self.ok.setText("Add")
        self.show_section("graph")
        self.resize(720, 500)

    def chosen(self) -> list[tuple[str, str]]:
        out = []
        for lst in self.lists.values():
            for i in range(lst.count()):
                if lst.item(i).checkState() == Qt.Checked:
                    out.append(tuple(lst.item(i).data(Qt.UserRole)))
        return out


class FormatFigureDialog(SectionDialog):
    def __init__(self, figure, parent=None):
        super().__init__("Format Figure", "Figures", parent)
        p = dict(figure.page)
        self.add_group("Figure")
        page, pl = tab_page()
        g = FormGrid()
        self.size = combo([(v[0], k) for k, v in PAGE_SIZES.items()], p.get("size", "a4"))
        self.w, self.h = _mm(p["width"]), _mm(p["height"])
        self.orient = combo([("Portrait", False), ("Landscape", True)], p.get("landscape", False))
        g.add(("Page:", self.size), ("Orientation:", self.orient))
        g.add(("Width:", self.w), ("Height:", self.h))
        pl.addLayout(g)
        pl.addWidget(_note("A figure exports at exactly this size, with every graph as its own group."))
        pl.addStretch(1)
        self.add_section("page", "Page", page, "doc")

        page, pl = tab_page()
        self.c_letters = QCheckBox("Label the panels with letters (in reading order)")
        self.c_letters.setChecked(p.get("letters", True))
        pl.addWidget(self.c_letters)
        g = FormGrid()
        self.style = combo([(v, k) for k, v in LETTER_STYLES.items()], p.get("letter_style", "A"))
        self.font = QFontComboBox()
        self.font.setCurrentText(p.get("letter_font", "Arial"))
        self.lsize = QDoubleSpinBox()
        self.lsize.setRange(4, 72)
        self.lsize.setSuffix(" pt")
        self.lsize.setValue(float(p.get("letter_size", 14.0)))
        self.bold = QCheckBox("Bold")
        self.bold.setChecked(p.get("letter_bold", True))
        self.pos = combo([("Outside the panel's top-left corner", "outside"), ("Inside the top-left corner", "inside")],
                         p.get("letter_pos", "outside"))
        g.add(("Style:", self.style))
        g.add(("Position:", self.pos))
        g.add(("Font:", self.font))
        g.add(("Size:", self.lsize), (None, self.bold))
        pl.addLayout(g)
        pl.addStretch(1)
        self.add_section("letters", "Panel letters", page, "textformat")

        page, pl = tab_page()
        self.c_snap = QCheckBox("Snap panels to the grid (and to each other's edges)")
        self.c_snap.setChecked(p.get("snap", True))
        pl.addWidget(self.c_snap)
        g = FormGrid()
        self.grid = _mm(p.get("grid", 5.0), 0.5, 50)
        g.add(("Grid spacing:", self.grid))
        pl.addLayout(g)
        pl.addStretch(1)
        self.add_section("grid", "Grid", page, "squareshape.split.3x3")
        self.size.currentIndexChanged.connect(self._size_changed)
        self._size_changed()
        self.show_section("page")
        self.resize(760, 460)

    def _size_changed(self, *_) -> None:
        key = self.size.currentData()
        _, w, h = PAGE_SIZES[key]
        custom = key == "custom"
        self.w.setEnabled(custom)
        self.h.setEnabled(custom)
        if not custom:
            self.w.setValue(w)
            self.h.setValue(h)

    def page(self) -> dict:
        return {"size": self.size.currentData(), "width": self.w.value(), "height": self.h.value(),
                "landscape": self.orient.currentData(), "letters": self.c_letters.isChecked(),
                "letter_style": self.style.currentData(), "letter_size": self.lsize.value(),
                "letter_bold": self.bold.isChecked(), "letter_font": self.font.currentFont().family(),
                "letter_pos": self.pos.currentData(), "grid": self.grid.value(), "snap": self.c_snap.isChecked()}


class TextPanelDialog(SectionDialog):
    def __init__(self, text: str = "", size: float = 10.0, parent=None):
        super().__init__("Text", "Figures", parent)
        self.add_group("Text")
        page, pl = tab_page()
        self.edit = QPlainTextEdit(text)
        pl.addWidget(self.edit, 1)
        g = FormGrid()
        self.size = QDoubleSpinBox()
        self.size.setRange(4, 72)
        self.size.setSuffix(" pt")
        self.size.setValue(size)
        g.add(("Size:", self.size))
        pl.addLayout(g)
        self.add_section("text", "Text", page, "textbox")
        self.show_section("text")
        self.resize(600, 380)

    def values(self) -> tuple[str, float]:
        return self.edit.toPlainText(), self.size.value()
