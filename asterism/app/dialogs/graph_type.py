"""Graph Type dialog: a gallery of graph types, each previewed with the graph's own data.

Types are grouped by table type in the section sidebar; the gallery offers the types for
the graph's table (column, grouped or nested now; XY and the others with their milestones). Choosing one sets every data set's style
in one undoable step; the rest of the graph's formatting is kept.
"""

from __future__ import annotations

import copy

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QListView, QListWidget, QListWidgetItem

from ...doc.commands import SpecCommand
from ...doc.spec import GraphSpec
from ..graph.canvas import QtCanvas
from ..graph.layout import build, content_bounds
from .common import SectionDialog, tab_page

S = dict  # readability for the preset table below

COLUMN_PRESETS = [
    ("scatter_sem", "Scatter, mean ± SEM", S(appearance="scatter", line_at="mean_sem", show_points=True, bars=False, errors=True, spread="swarm")),
    ("scatter_bar", "Scatter on bars", S(appearance="scatter", line_at="mean_sem", show_points=True, bars=True, errors=True, spread="swarm")),
    ("bar_sd", "Bars, mean ± SD", S(appearance="bar", line_at="mean_sd", show_points=False, bars=True, errors=True)),
    ("bar_points", "Bars with points", S(appearance="bar", line_at="mean_sd", show_points=True, bars=True, errors=True, spread="swarm")),
    ("bar_range", "Bars, mean with range", S(appearance="bar", line_at="mean_range", show_points=False, bars=True, errors=True)),
    ("box", "Box and whiskers", S(appearance="box", whiskers="minmax", show_points=False, errors=True, bars=False)),
    ("box_points", "Box (Tukey) with points", S(appearance="box", whiskers="tukey", show_points=True, errors=True, bars=False, spread="swarm")),
    ("violin", "Violin", S(appearance="violin", show_points=False, bars=True)),
    ("violin_points", "Violin with points", S(appearance="violin", show_points=True, bars=False, spread="swarm")),
    ("symbol", "Mean ± SEM, one symbol", S(appearance="symbol", line_at="mean_sem", errors=True, bars=False)),
    ("floating", "Floating bars (min to max)", S(appearance="floating", line_at="mean", show_points=False, bars=True)),
    ("aligned", "Aligned dots, median", S(appearance="scatter", line_at="median", show_points=True, bars=False, errors=False, spread="aligned")),
    ("before_after", "Before-after", S(appearance="scatter", line_at="none", show_points=True, bars=False, errors=False, spread="aligned")),
]


# Grouped tables: (key, name, data-set style, graph settings)
BAR = S(appearance="bar", line_at="mean_sd", show_points=False, bars=True, errors=True)
GROUPED_PRESETS = [
    ("g_bars", "Bars side by side, mean ± SD", BAR, S(grouped_layout="interleaved")),
    ("g_bars_points", "Bars side by side, with points",
     S(BAR, show_points=True, spread="swarm"), S(grouped_layout="interleaved")),
    ("g_scatter", "Scatter side by side, mean ± SEM",
     S(appearance="scatter", line_at="mean_sem", show_points=True, bars=False, errors=True, spread="swarm"),
     S(grouped_layout="interleaved")),
    ("g_box", "Box and whiskers side by side",
     S(appearance="box", whiskers="minmax", show_points=False, errors=True, bars=True),
     S(grouped_layout="interleaved")),
    ("g_violin", "Violins side by side", S(appearance="violin", show_points=False, bars=True),
     S(grouped_layout="interleaved")),
    ("g_separated", "Separated bars", BAR, S(grouped_layout="separated")),
    ("g_stacked", "Stacked bars", S(BAR, line_at="mean_sem"), S(grouped_layout="stacked")),
    ("g_stacked_pct", "Stacked bars to 100%", S(BAR, errors=False), S(grouped_layout="stacked_pct")),
    ("g_lines", "Connected means ± SEM",
     S(appearance="symbol", line_at="mean_sem", errors=True, bars=False, show_points=False),
     S(grouped_layout="lines")),
    ("g_heat", "Heat map", S(), S(grouped_layout="heatmap")),
]
DOT = S(appearance="scatter", line_at="mean_sem", show_points=True, bars=False, errors=True, spread="swarm")
NESTED_PRESETS = [
    ("n_subjects", "Each subject in its own column", DOT, S(nested_layout="subjects")),
    ("n_pooled", "All values, coloured by subject", DOT, S(nested_layout="pooled")),
    ("n_superplot", "SuperPlot (subject means)", DOT, S(nested_layout="superplot")),
    ("n_superplot_bars", "SuperPlot on bars", S(DOT, bars=True), S(nested_layout="superplot")),
    ("n_box", "Box and whiskers with points",
     S(appearance="box", whiskers="minmax", show_points=True, errors=True, bars=False),
     S(nested_layout="pooled")),
]
XYBASE = S(appearance="scatter", show_points=True, connect=False, fill=False, xy_show="mean",
           line_at="mean_sem", errors=True, bars=False)
XY_PRESETS = [
    ("xy_points", "Points, mean ± SEM", XYBASE, S()),
    ("xy_points_line", "Points and connecting line", S(XYBASE, connect=True), S()),
    ("xy_line", "Line only", S(XYBASE, connect=True, show_points=False, errors=False), S()),
    ("xy_replicates", "Each replicate", S(XYBASE, xy_show="replicates", errors=False), S()),
    ("xy_spaghetti", "Each replicate connected (spaghetti)", S(XYBASE, xy_show="spaghetti", errors=False), S()),
    ("xy_area", "Line with shaded area", S(XYBASE, connect=True, fill=True, show_points=False, errors=False), S()),
    ("xy_bars", "Bars at each X, mean ± SD", S(XYBASE, appearance="bar", bars=True, line_at="mean_sd"), S()),
]
PRESETS = {"column": [(k, n, f, S(connect_rows=k == "before_after")) for k, n, f in COLUMN_PRESETS],
           "grouped": GROUPED_PRESETS, "nested": NESTED_PRESETS, "xy": XY_PRESETS}
SECTIONS = {"column": ("Column graphs", "chart.bar"), "grouped": ("Grouped graphs", "square.grid.3x2"),
            "nested": ("Nested graphs", "square.stack.3d.down.right"),
            "xy": ("XY graphs", "chart.xyaxis.line")}


def apply_preset(spec: GraphSpec, key: str, columns: list[int]) -> GraphSpec:
    _, _, fields, graph_fields = next(p for ps in PRESETS.values() for p in ps if p[0] == key)
    new = copy.deepcopy(spec)
    for st in [new.default_style, *(new.style(c) for c in columns)]:
        for f, v in fields.items():
            setattr(st, f, v)
    for f, v in graph_fields.items():
        setattr(new, f, v)
    return new


class _Preview:
    """Just enough of a Graph for the layout engine."""

    def __init__(self, graph, spec: GraphSpec):
        self.table, self.spec, self._g = graph.table, spec, graph

    def analyses(self):
        return self._g.analyses()


def thumbnail(graph, spec: GraphSpec, size: QSize = QSize(150, 118)) -> QIcon:
    els, _ = build(_Preview(graph, spec))
    b = content_bounds(els, margin=6)
    img = QImage(size * 2, QImage.Format_ARGB32)
    img.setDevicePixelRatio(2)
    img.fill(QColor("#ffffff"))
    p = QPainter(img)
    scale = min(size.width() / max(b.width(), 1), size.height() / max(b.height(), 1))
    p.translate((size.width() - b.width() * scale) / 2, (size.height() - b.height() * scale) / 2)
    p.scale(scale, scale)
    p.translate(-b.x(), -b.y())
    cv = QtCanvas(p)
    for e in els:
        e.draw(cv)
    p.end()
    return QIcon(QPixmap.fromImage(img))


class GraphTypeDialog(SectionDialog):
    def __init__(self, graph, project, parent=None):
        super().__init__("Graph Type", "Graph type", parent)
        self.graph, self.project = graph, project
        self.cols = graph.table.used_columns()
        page, pl = tab_page()
        self.gallery = QListWidget()
        self.gallery.setViewMode(QListView.IconMode)
        self.gallery.setIconSize(QSize(150, 118))
        self.gallery.setGridSize(QSize(176, 156))
        self.gallery.setResizeMode(QListView.Adjust)
        self.gallery.setMovement(QListView.Static)
        self.gallery.setWordWrap(True)
        self.gallery.setSpacing(4)
        tt = graph.table.table_type if graph.table.table_type in PRESETS else "column"
        for key, name, *_ in PRESETS[tt]:
            it = QListWidgetItem(thumbnail(graph, apply_preset(graph.spec, key, self.cols)), name)
            it.setData(Qt.UserRole, key)
            it.setTextAlignment(Qt.AlignHCenter | Qt.AlignTop)
            self.gallery.addItem(it)
        self.gallery.itemDoubleClicked.connect(lambda _it: self.accept())
        self.gallery.setCurrentRow(0)
        pl.addWidget(self.gallery, 1)
        self.add_group("Graph types")
        title, ico = SECTIONS[tt]
        self.add_section(tt, title, page, ico)
        self.ok.setText("Apply")
        self.show_section(tt)
        self.resize(900, 640)

    def chosen(self) -> str | None:
        it = self.gallery.currentItem()
        return it.data(Qt.UserRole) if it else None

    def accept(self) -> None:
        key = self.chosen()
        if key:
            new = apply_preset(self.graph.spec, key, self.cols)
            self.project.undo.push(SpecCommand(self.graph, new, "Change Graph Type"))
        super().accept()
