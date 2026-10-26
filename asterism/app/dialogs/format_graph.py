"""Format Graph: one dialog for a graph's data sets, frame, titles, significance and axes.

ASTERISM's own arrangement (SPEC §2.1, §8): sections in a sidebar, grouped as
Graph · Data sets · Axes. Data-set sections share a picker at the top ("All data
sets" or one data set). Every Apply is one undo step.
"""

from __future__ import annotations

import copy

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QDoubleValidator, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFontComboBox,
                               QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QMessageBox, QPushButton, QSpinBox,
                               QTableWidget, QTableWidgetItem, QToolButton, QVBoxLayout, QWidget)

from ...doc.commands import SpecCommand
from ...doc.model import Graph, Project
from ...doc.spec import DataSetStyle
from ..graph.canvas import QtCanvas
from ..graph.layout import draw_symbol
from .common import (ColorButton, FormGrid, Section, SectionDialog, combo, set_combo,
                     tab_page)

APPEARANCES = [("Scatter dot plot", "scatter"), ("Column bar", "bar"), ("Box and whiskers", "box"),
               ("Violin plot", "violin"), ("Floating bar (minimum to maximum)", "floating"),
               ("One symbol (mean or median)", "symbol")]
LINE_AT = [("Mean ± SEM", "mean_sem"), ("Mean ± SD", "mean_sd"), ("Mean with 95% CI", "mean_ci"),
           ("Mean with range", "mean_range"), ("Median with interquartile range", "median_iqr"),
           ("Median with range", "median_range"), ("Mean only", "mean"), ("Median only", "median"),
           ("No summary line", "none")]
WHISKERS = [("Minimum to maximum", "minmax"), ("Tukey (1.5 × IQR)", "tukey"), ("10th–90th percentile", "p10"),
            ("5th–95th percentile", "p5"), ("2.5th–97.5th percentile", "p2_5"),
            ("1st–99th percentile", "p1")]
THICK = [("None", 0.0), ("¼ pt", 0.25), ("½ pt", 0.5), ("1 pt", 1.0), ("1½ pt", 1.5),
         ("2 pt", 2.0), ("3 pt", 3.0)]
TICK_LEN = [("Very short", "very_short"), ("Short", "short"), ("Medium", "normal"),
            ("Long", "long"), ("Very long", "very_long")]
SHAPES = ["circle", "square", "triangle", "diamond", "open_circle", "open_square"]

# Old section names (graph view, main window) → section keys.
GROUPED_ARRANGEMENTS = [("Side by side (data sets next to each other in each row)", "interleaved"),
                        ("Separated (one group per data set)", "separated"),
                        ("Stacked", "stacked"), ("Stacked to 100%", "stacked_pct"),
                        ("Connected means (one line per data set)", "lines"),
                        ("Heat map", "heatmap"),
                        ("Back to back (first data set left or down, second right or up)", "pyramid")]
NESTED_ARRANGEMENTS = [("Each subject in its own column", "subjects"),
                       ("All values together, coloured by subject", "pooled"),
                       ("SuperPlot: values coloured by subject, with subject means", "superplot")]

ALIASES = {"appearance": "style", "symbols": "style", "bars": "style", "errors": "style",
           "annotations": "significance", "settings": "frame", "fonts": "fonts",
           "frame": "frame", "x": "x", "y": "y", "datasets": "datasets"}


def shape_icon(shape: str) -> QIcon:
    pm = QPixmap(QSize(16, 16) * 2)
    pm.setDevicePixelRatio(2)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    draw_symbol(QtCanvas(p), shape, 8, 8, 10, "#000000")
    p.end()
    return QIcon(pm)


def num_edit(v: float) -> QLineEdit:
    e = QLineEdit(f"{v:g}")
    e.setValidator(QDoubleValidator())
    e.setFixedWidth(110)
    return e


def mm_spin(v: float, lo: float, hi: float) -> QDoubleSpinBox:
    s = QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setDecimals(1)
    s.setSuffix(" mm")
    s.setValue(v)
    s.setFixedWidth(110)
    return s


class FormatGraphDialog(SectionDialog):
    DATASET_SECTIONS = ("style",)

    def __init__(self, graph: Graph, project: Project, section: str = "style",
                 column: int | None = None, auto_range=None, parent=None):
        graph_type = QPushButton("Graph Type…")
        super().__init__("Format Graph", "Format Graph", parent, apply=True,
                         extra_left=[graph_type])
        graph_type.clicked.connect(self._graph_type)
        self.graph, self.project = graph, project
        self.spec = copy.deepcopy(graph.spec)
        self.auto_range = auto_range
        self.xy = graph.table.table_type == "xy"
        self.numx = graph.table.table_type in ("xy", "multivar", "survival")      # numeric X axis
        self.cols = graph.table.used_columns()
        for c in self.cols:
            self.spec.style(c)
        self._loading = False
        self.axis_ctl: dict = {}            # per axis ("x", "y", "y2"): its controls

        self._make_picker()
        self.add_group("Graph")
        self.add_section("frame", "Size and frame", self._frame_page(), "square.dashed")
        self.add_section("fonts", "Titles and fonts", self._fonts_page(), "textformat")
        self.add_section("significance", "Significance", self._significance_page(), "asterisk")
        tt = graph.table.table_type
        if tt in ("grouped", "nested", "contingency", "parts", "survival"):
            self.add_section("arrangement", "Arrangement", self._arrangement_page(tt),
                             {"nested": "square.stack.3d.down.right", "parts": "chart.pie",
                              "survival": "waveform.path.ecg"}.get(tt, "square.grid.3x2"))
        if tt == "multivar":
            self.add_section("arrangement", "Variables", self._variables_page(), "circle.hexagongrid")
        self.add_group("Data sets")
        self.add_section("style", "Style", self._style_page(), "circle.grid.2x2")
        self.add_section("datasets", "Show and order", self._datasets_page(), "eye")
        self.add_group("Axes")
        self.add_section("x", "X axis", self._x_page(), "arrow.left.and.right")
        self.add_section("y", "Y axis", self._y_page(), "arrow.up.and.down")
        self.add_section("right", "Right Y axis", self._right_page(), "arrow.up.and.down.square")

        self.apply_button.clicked.connect(self.apply)
        self.sectionChanged.connect(self._section_changed)
        if column is not None and column in self.cols:
            self.ds_combo.setCurrentIndex(self.cols.index(column) + 1)
        self._load()
        self.show_section(ALIASES.get(section, section))
        self.resize(900, 640)

    def _graph_type(self) -> None:
        """Choose a graph type; the dialog's pending edits are applied first."""
        from .graph_type import GraphTypeDialog
        self.apply()
        if GraphTypeDialog(self.graph, self.project, self).exec():
            self.spec = copy.deepcopy(self.graph.spec)
            for c in self.cols:
                self.spec.style(c)
            self._load()
            self.connect.setChecked(self.spec.connect_rows)
            if hasattr(self, "arrangement"):
                tt = self.graph.table.table_type
                set_combo(self.arrangement, {"nested": self.spec.nested_layout, "parts": self.spec.parts_layout}
                          .get(tt, self.spec.grouped_layout))

    # --- data-set picker (shown above the data-set sections) -------------------

    def _make_picker(self) -> None:
        self.picker = QWidget()
        h = QHBoxLayout(self.picker)
        h.setContentsMargins(0, 0, 0, 4)
        h.addWidget(QLabel("Apply to:"))
        self.ds_combo = QComboBox()
        self.ds_combo.addItem("All data sets", None)
        for c in self.cols:
            self.ds_combo.addItem(self.graph.table.short_label(c), c)
        self.ds_combo.currentIndexChanged.connect(self._load)
        h.addWidget(self.ds_combo, 1)
        for arrow, step, tip in ((Qt.LeftArrow, -1, "Previous data set"),
                                 (Qt.RightArrow, 1, "Next data set")):
            b = QToolButton()
            b.setArrowType(arrow)
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False, s=step: self.ds_combo.setCurrentIndex(
                (self.ds_combo.currentIndex() + s) % self.ds_combo.count()))
            h.addWidget(b)
        self.header.addWidget(self.picker)

    def _section_changed(self, key: str) -> None:
        self.picker.setVisible(key in self.DATASET_SECTIONS)

    # --- Graph: size and frame ------------------------------------------------------

    def _frame_page(self) -> QWidget:
        page, pl = tab_page()
        pl.addWidget(Section("Size"))
        g = FormGrid()
        self.col_w = mm_spin(self.spec.col_width_mm, 4, 80)
        self.height_mm = mm_spin(self.spec.y_len_mm, 10, 250)
        self.x_axis_len = mm_spin(self.spec.x_len_mm, 10, 300)
        if self.numx:
            g.add(("X-axis length:", self.x_axis_len), ("Plot height:", self.height_mm))
        else:
            g.add(("Column width:", self.col_w), ("Plot height:", self.height_mm))
        self.orient = combo([("Vertical (columns go up)", False), ("Horizontal (bars go across)", True)],
                            self.spec.horizontal)
        if self.graph.table.table_type in ("column", "grouped", "contingency", "nested"):
            g.add(("Orientation:", self.orient))
        pl.addLayout(g)
        pl.addWidget(Section("Axis lines and frame"))
        g = FormGrid()
        self.frame = combo([("Axes only", "plain"), ("Axes, offset from the data", "offset"),
                            ("Closed box", "box")], self.spec.frame)
        self.axis_w = combo(THICK[1:], self.spec.axis_width)
        self.axis_c = ColorButton(self.spec.axis_color)
        g.add(("Frame:", self.frame))
        g.add(("Line thickness:", self.axis_w), ("Line colour:", self.axis_c))
        pl.addLayout(g)
        pl.addWidget(Section("Title"))
        self.show_title = QCheckBox("Show the graph title")
        self.show_title.setChecked(self.spec.show_title)
        pl.addWidget(self.show_title)
        pl.addStretch(1)
        return page

    # --- Graph: titles and fonts ----------------------------------------------------

    def _fonts_page(self) -> QWidget:
        page, pl = tab_page()
        pl.addWidget(Section("Titles"))
        g = FormGrid()
        self.t_title = QLineEdit(self.spec.title or self.graph.table.name)
        self.t_title.setMinimumWidth(320)
        self.t_ytitle = QLineEdit(self.spec.y.title)
        g.add(("Graph title:", self.t_title))
        g.add(("Y-axis title:", self.t_ytitle))
        pl.addLayout(g)
        pl.addWidget(Section("Fonts"))
        grid = QGridLayout()
        grid.setContentsMargins(18, 4, 0, 0)
        grid.setHorizontalSpacing(10)
        self.font_rows = {}
        for i, (key, label) in enumerate((("title", "Graph title"), ("y_title", "Y-axis title"),
                                          ("y_numbers", "Y-axis numbers"),
                                          ("x_labels", "X-axis labels"),
                                          ("bracket", "Significance P values"),
                                          ("stars", "Significance stars"),
                                          ("legend", "Legend"))):
            fs = self.spec.fonts[key]
            fam = QFontComboBox()
            fam.setCurrentText(fs.family)
            size = QDoubleSpinBox()
            size.setRange(4, 72)
            size.setDecimals(1)
            size.setSuffix(" pt")
            size.setValue(fs.size)
            b, it = QCheckBox("Bold"), QCheckBox("Italic")
            b.setChecked(fs.bold)
            it.setChecked(fs.italic)
            lab = QLabel(label + ":")
            lab.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            for col, w in enumerate((lab, fam, size, b, it)):
                grid.addWidget(w, i, col)
            self.font_rows[key] = (fam, size, b, it)
        grid.setColumnStretch(5, 1)
        pl.addLayout(grid)
        pl.addStretch(1)
        return page

    # --- Graph: arrangement (grouped and nested tables) -------------------------------

    def _variables_page(self) -> QWidget:
        from ..graph.multivar_layout import roles
        page, pl = tab_page()
        t, mv = self.graph.table, self.spec.mv
        ro = roles(self.spec, t)
        nums = ro["numeric"]
        name = lambda c: t.short_label(c)
        pl.addWidget(Section("Axes"))
        g = FormGrid()
        self.mv_x = combo([(name(c), c) for c in nums], ro["x"])
        g.add(("X axis:", self.mv_x))
        pl.addLayout(g)
        pl.addWidget(QLabel("Y axis (each ticked variable is a data set):"))
        self.mv_y = QListWidget()
        self.mv_y.setMaximumHeight(140)
        for c in nums:
            it = QListWidgetItem(name(c))
            it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if c in ro["ys"] else Qt.Unchecked)
            it.setData(Qt.UserRole, c)
            self.mv_y.addItem(it)
        pl.addWidget(self.mv_y)
        pl.addWidget(Section("Size and colour"))
        g = FormGrid()
        self.mv_size = combo([("Nothing (same size)", None)] + [(name(c), c) for c in nums], ro["size"])
        self.mv_color = combo([("Nothing (data set colour)", None)] + [(name(c), c) for c in t.used_columns()],
                              ro["color"])
        self.mv_smin, self.mv_smax = QDoubleSpinBox(), QDoubleSpinBox()
        for w, v in ((self.mv_smin, mv.get("size_min", 4.0)), (self.mv_smax, mv.get("size_max", 22.0))):
            w.setRange(1, 80)
            w.setSuffix(" pt")
            w.setValue(float(v))
        g.add(("Symbol size shows:", self.mv_size), ("Colour shows:", self.mv_color))
        g.add(("Smallest bubble:", self.mv_smin), ("Largest bubble:", self.mv_smax))
        pl.addLayout(g)
        note = QLabel("Bubble areas grow with the value. A numeric colour variable uses the colour range "
                      "below; a text variable (e.g. Sex) gives one colour per group.")
        note.setWordWrap(True)
        note.setEnabled(False)
        pl.addWidget(note)
        g = FormGrid()
        self.heat_low, self.heat_high = ColorButton(self.spec.heat_low), ColorButton(self.spec.heat_high)
        g.add(("Low values:", self.heat_low), ("High values:", self.heat_high))
        pl.addLayout(g)
        self.mv_labels = QCheckBox("Label each point with its row title")
        self.mv_labels.setChecked(bool(mv.get("labels")))
        pl.addWidget(self.mv_labels)
        self.legend = QCheckBox("Show a legend")
        self.legend.setChecked(self.spec.show_legend)
        pl.addWidget(self.legend)
        pl.addStretch(1)
        return page

    def _arrangement_page(self, tt: str) -> QWidget:
        page, pl = tab_page()
        s = self.spec
        g = FormGrid()
        if tt == "parts":
            self.arrangement = combo([("Pie chart", "pie"), ("Donut chart", "donut"),
                                      ("Bar stacked to 100%", "stacked100"),
                                      ("Percentage dot plot (100 squares)", "waffle")], s.parts_layout)
            self.parts_labels = combo([("Percentages", "percent"), ("Values", "value"), ("No labels", "none")],
                                      s.parts_labels)
            self.hole = QDoubleSpinBox()
            self.hole.setRange(10, 90)
            self.hole.setDecimals(0)
            self.hole.setSuffix(" % of the radius")
            self.hole.setValue(s.donut_hole * 100)
            g.add(("Draw as:", self.arrangement))
            g.add(("Label the slices with:", self.parts_labels))
            g.add(("Donut hole:", self.hole))
            pl.addLayout(g)
            self.legend = QCheckBox("Show a legend for the slices")
            self.legend.setChecked(s.show_legend)
            pl.addWidget(self.legend)
            pl.addStretch(1)
            return page
        if tt == "survival":
            self.surv_y = combo([("Percent surviving", "pct"), ("Fraction surviving", "frac"),
                                 ("Percent with the event (deaths)", "pct_death"),
                                 ("Fraction with the event", "frac_death")],
                                ("pct" if s.surv_percent else "frac") + ("_death" if s.surv_death else ""))
            self.surv_ci = combo([("No confidence bands", "none"), ("Dashed lines", "dashed"),
                                  ("Shaded band", "shaded"), ("Error bars at each step", "bars")], s.surv_ci)
            g.add(("Plot:", self.surv_y))
            g.add(("Confidence intervals:", self.surv_ci))
            pl.addLayout(g)
            self.surv_ticks = QCheckBox("Mark censored subjects with a tick")
            self.surv_ticks.setChecked(s.surv_ticks)
            pl.addWidget(self.surv_ticks)
            self.legend = QCheckBox("Show a legend for the groups")
            self.legend.setChecked(s.show_legend)
            pl.addWidget(self.legend)
            note = QLabel("Confidence bands use the log-log transform, as the survival analysis does by "
                          "default.")
            note.setWordWrap(True)
            note.setEnabled(False)
            pl.addWidget(note)
            pl.addStretch(1)
            return page
        if tt in ("grouped", "contingency"):
            self.arrangement = combo(GROUPED_ARRANGEMENTS, s.grouped_layout)
            g.add(("Arrange as:", self.arrangement))
            pl.addLayout(g)
            self.lines_points = QCheckBox("Connected means: also show each replicate")
            self.lines_points.setChecked(s.lines_points)
            self.lines_points.toggled.connect(lambda v: setattr(self.spec, "lines_points", v))
            pl.addWidget(self.lines_points)
            pl.addWidget(Section("Legend"))
            self.legend = QCheckBox("Show a legend for the data sets")
            self.legend.setChecked(s.show_legend)
            pl.addWidget(self.legend)
            pl.addWidget(Section("Heat map colours"))
            g2 = FormGrid()
            self.heat_low, self.heat_high = ColorButton(s.heat_low), ColorButton(s.heat_high)
            g2.add(("Lowest value:", self.heat_low), ("Highest value:", self.heat_high))
            pl.addLayout(g2)
            note = QLabel("The heat map's colour range follows the Y axis range: automatic, or "
                          "the minimum and maximum set on the Y axis page.")
            note.setWordWrap(True)
            note.setEnabled(False)
            pl.addWidget(note)
        else:
            self.arrangement = combo(NESTED_ARRANGEMENTS, s.nested_layout)
            g.add(("Arrange as:", self.arrangement))
            pl.addLayout(g)
            note = QLabel("Each sub-column of a nested table is one subject; its values are "
                          "replicate measurements. Subjects take colours in table order.")
            note.setWordWrap(True)
            note.setEnabled(False)
            pl.addWidget(note)
        pl.addStretch(1)
        return page

    # --- Graph: significance --------------------------------------------------------

    def _significance_page(self) -> QWidget:
        from ..graph.layout import bracket_id
        page, pl = tab_page()
        sig = dict(self.spec.sig)
        if self.spec.p_format == "exact" and sig.get("label") == "stars":
            sig["label"] = "p"
        if self.spec.brackets_ns and sig.get("which") == "significant":
            sig["which"] = "all"
        self.show_br = QCheckBox("Draw significance brackets for comparisons in linked analyses")
        self.show_br.setChecked(self.spec.show_brackets)
        pl.addWidget(self.show_br)

        pl.addWidget(Section("Which comparisons"))
        g = FormGrid()
        self.sig_which = combo([("Only the significant ones", "significant"), ("All of them", "all"),
                                ("Only those against a control", "control"), ("None", "none")], sig["which"])
        self.sig_control = QComboBox()
        for c in self.cols:
            self.sig_control.addItem(self.graph.table.short_label(c), c)
        set_combo(self.sig_control, sig.get("control"))
        self.sig_alpha = combo([("0.05", 0.05), ("0.01", 0.01), ("0.001", 0.001), ("0.10", 0.10)], sig["alpha"])
        g.add(("Multiple comparisons:", self.sig_which))
        g.add(("Control:", self.sig_control), ("Significant when P <", self.sig_alpha))
        pl.addLayout(g)
        self.sig_ns = QCheckBox("Show “ns” for a two-group test that isn't significant")
        self.sig_ns.setChecked(sig.get("ns_single", True))
        pl.addWidget(self.sig_ns)
        self.sig_list = QListWidget()
        self.sig_list.setMaximumHeight(130)
        hidden = set(sig.get("hidden") or [])
        t = self.graph.table

        def lab(k):
            return f"{t.row_label(k[0])}: {t.label(k[1])}" if isinstance(k, tuple) else t.label(k)
        for a in self.graph.analyses():
            r = a.result
            if r is None or r.error:
                continue
            pairs = [(ka, kb, pv) for ka, kb, pv in r.comparisons] + list(r.cell_comparisons)
            if a.analysis_type == "multiple_t" and len(a.columns) == 2:
                pairs += [((row, a.columns[0]), (row, a.columns[1]), padj) for row, _p, padj in r.rows]
            for ka, kb, pv in pairs:
                gid = bracket_id(ka, kb)
                it = QListWidgetItem(f"{lab(ka)}  vs.  {lab(kb)}    (P = {pv:.4g})")
                it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
                it.setCheckState(Qt.Unchecked if gid in hidden else Qt.Checked)
                it.setData(Qt.UserRole, gid)
                self.sig_list.addItem(it)
        if self.sig_list.count():
            note = QLabel("Untick a comparison to hide its bracket (or right-click the bracket on the graph).")
            note.setEnabled(False)
            pl.addWidget(note)
            pl.addWidget(self.sig_list)

        pl.addWidget(Section("Label"))
        g = FormGrid()
        self.sig_label = combo([("Stars (ns, *, **, ***, ****)", "stars"), ("P value (P = 0.0123)", "p"),
                                ("Number only (0.0123)", "number"), ("Stars and P value", "both")], sig["label"])
        self.sig_levels = combo([("Four levels: 0.05, 0.01, 0.001, 0.0001", "four"),
                                 ("Three levels: 0.05, 0.01, 0.001", "three"),
                                 ("Prism's style: 0.0332, 0.0021, 0.0002, 0.0001", "gp"),
                                 ("My own thresholds", "custom")], sig["levels"])
        self.sig_max = combo([("1", 1), ("2", 2), ("3", 3), ("4", 4)], int(sig.get("max_stars", 4)))
        self.sig_cuts = QLineEdit(", ".join(f"{c:g}" for c in sig.get("cuts", [0.05, 0.01, 0.001, 0.0001])))
        g.add(("Show:", self.sig_label))
        g.add(("Stars:", self.sig_levels))
        g.add(("Thresholds:", self.sig_cuts), ("At most:", self.sig_max))
        self.sig_star_size, self.sig_p_size = QDoubleSpinBox(), QDoubleSpinBox()
        for w, key in ((self.sig_star_size, "stars"), (self.sig_p_size, "bracket")):
            w.setRange(4, 48)
            w.setDecimals(1)
            w.setSuffix(" pt")
            w.setValue(float(self.spec.fonts[key].size))
            other = self.font_rows.get(key, (None, None))[1]
            if other is not None:                      # the same size as on "Titles and fonts"
                w.valueChanged.connect(lambda v, o=other: o.value() != v and o.setValue(v))
                other.valueChanged.connect(lambda v, me=w: me.value() != v and me.setValue(v))
        g.add(("Size of stars:", self.sig_star_size), ("Size of P values:", self.sig_p_size))
        pl.addLayout(g)

        pl.addWidget(Section("Lines"))
        g = FormGrid()
        self.sig_shape = combo([("Bracket with end ticks", "bracket"), ("Plain line", "line")], sig["shape"])
        self.sig_tick = QDoubleSpinBox()
        self.sig_tick.setRange(0, 30)
        self.sig_tick.setSuffix(" pt")
        self.sig_tick.setValue(sig["tick"])
        self.sig_width = combo([("Same as the axes", 0.0)] + THICK[1:], sig.get("width", 0.0))
        self.sig_color = ColorButton(sig.get("color") or self.spec.axis_color)
        g.add(("Shape:", self.sig_shape), ("End ticks:", self.sig_tick))
        g.add(("Thickness:", self.sig_width), ("Colour:", self.sig_color))
        pl.addLayout(g)

        pl.addWidget(Section("Placement"))
        g = FormGrid()
        self.sig_order = combo([("Shortest brackets lowest", "shortest"), ("In the analysis's order", "table")],
                               sig["order"])
        self.sig_dist, self.sig_level, self.sig_gap = QDoubleSpinBox(), QDoubleSpinBox(), QDoubleSpinBox()
        for w, v in ((self.sig_dist, sig["distance"]), (self.sig_level, sig["level_gap"]), (self.sig_gap, sig["label_gap"])):
            w.setRange(0, 60)
            w.setSuffix(" pt")
            w.setValue(float(v))
        g.add(("Stacking:", self.sig_order), ("Label gap:", self.sig_gap))
        g.add(("Above the data:", self.sig_dist), ("Between levels:", self.sig_level))
        pl.addLayout(g)
        pl.addStretch(1)
        self.sig_which.currentIndexChanged.connect(lambda *_: self._sync_sig())
        self.sig_levels.currentIndexChanged.connect(lambda *_: self._sync_sig())
        self.sig_shape.currentIndexChanged.connect(lambda *_: self._sync_sig())
        self._sync_sig()
        return page

    def _sync_sig(self) -> None:
        self.sig_control.setEnabled(self.sig_which.currentData() == "control")
        self.sig_cuts.setEnabled(self.sig_levels.currentData() == "custom")
        self.sig_tick.setEnabled(self.sig_shape.currentData() == "bracket")

    def _collect_sig(self) -> None:
        s = self.spec
        s.show_brackets = self.show_br.isChecked()
        try:
            cuts = sorted({float(v) for v in self.sig_cuts.text().replace(";", ",").split(",") if v.strip()},
                          reverse=True) or [0.05, 0.01, 0.001, 0.0001]
        except ValueError:
            cuts = list(s.sig.get("cuts", [0.05, 0.01, 0.001, 0.0001]))
        hidden = [self.sig_list.item(i).data(Qt.UserRole) for i in range(self.sig_list.count())
                  if self.sig_list.item(i).checkState() != Qt.Checked]
        color = self.sig_color.color()
        s.sig = {**s.sig, "which": self.sig_which.currentData(), "control": self.sig_control.currentData(),
                 "alpha": self.sig_alpha.currentData(), "ns_single": self.sig_ns.isChecked(),
                 "label": self.sig_label.currentData(), "levels": self.sig_levels.currentData(), "cuts": cuts,
                 "max_stars": self.sig_max.currentData(),
                 "shape": self.sig_shape.currentData(), "tick": self.sig_tick.value(),
                 "width": self.sig_width.currentData(), "color": "" if color == s.axis_color else color,
                 "order": self.sig_order.currentData(), "distance": self.sig_dist.value(),
                 "level_gap": self.sig_level.value(), "label_gap": self.sig_gap.value(), "hidden": hidden}
        s.p_format = "exact" if s.sig["label"] == "p" else "stars"       # older readers
        s.brackets_ns = False

    # --- Data sets ------------------------------------------------------------------

    def _style_page(self) -> QWidget:
        """Everything about how a data set is drawn, on one page: plot type and points,
        symbols, bars or box, error bars or whiskers."""
        page, pl = tab_page()
        pl.addWidget(Section("Plot"))
        g = FormGrid()
        self.appearance = combo(APPEARANCES)
        self.line_at = combo(LINE_AT)
        self.line_at_label = QLabel("Summary line:")
        g.add(("Plot as:", self.appearance))
        g.addWidget(self.line_at_label, g._row, 0, Qt.AlignRight | Qt.AlignVCenter)
        g.addWidget(self.line_at, g._row, 1)
        g._row += 1
        self.show_points = QCheckBox("Show individual data points")
        g.add((None, self.show_points))
        self.spread = combo([("Side by side", "swarm"), ("In a single line", "aligned")])
        self.spread_label = QLabel("Arrange points:")
        g.addWidget(self.spread_label, g._row, 0, Qt.AlignRight | Qt.AlignVCenter)
        g.addWidget(self.spread, g._row, 1)
        g._row += 1
        self.smooth = combo([("Light (more detail)", "light"), ("Medium", "medium"),
                             ("Heavy (smoother shape)", "heavy")])
        self.smooth_label = QLabel("Violin smoothing:")
        g.addWidget(self.smooth_label, g._row, 0, Qt.AlignRight | Qt.AlignVCenter)
        g.addWidget(self.smooth, g._row, 1)
        g._row += 1
        styles = [("Dashed", "dash"), ("Dotted", "dot"), ("Solid", "solid"), ("None", "none")]
        self.v_quart = combo(styles)
        self.v_median = combo([("Solid", "solid"), ("Dashed", "dash"), ("Dotted", "dot"), ("None", "none")])
        self.v_lines_label = QLabel("Quartile / median lines:")
        row = QHBoxLayout()
        row.addWidget(self.v_quart)
        row.addWidget(self.v_median)
        row.addStretch(1)
        g.addWidget(self.v_lines_label, g._row, 0, Qt.AlignRight | Qt.AlignVCenter)
        g.addLayout(row, g._row, 1)
        g._row += 1
        pl.addLayout(g)
        plot_at = pl.count()                     # "Plotting" (axis, legend, nudge) goes right here
        self.box_note = QLabel("The box spans the 25th to 75th percentile, with a line at the "
                               "median. Without individual points, values beyond the whiskers "
                               "are still drawn.")
        self.box_note.setEnabled(False)
        self.box_note.setWordWrap(True)
        self.box_note.setContentsMargins(18, 0, 0, 0)
        pl.addWidget(self.box_note)

        self.sec_symbols = Section("Symbols")
        pl.addWidget(self.sec_symbols)
        self.symbols_box = QWidget()
        g = FormGrid()
        self.symbols_box.setLayout(g)
        self.sym_color = ColorButton()
        self.sym_shape = QComboBox()
        for sh in SHAPES:
            self.sym_shape.addItem(shape_icon(sh), "", sh)
        self.sym_size = combo([(str(i), i) for i in range(1, 11)])
        g.add(("Colour:", self.sym_color), ("Size:", self.sym_size))
        g.add(("Shape:", self.sym_shape))
        pl.addWidget(self.symbols_box)

        self.xy_box = QWidget()                 # XY graphs: replicates, lines, area fill
        g = FormGrid()
        g.setContentsMargins(0, 0, 0, 0)
        self.xy_box.setLayout(g)
        self.xy_show = combo([("Mean with error bars", "mean"), ("Each replicate", "replicates"),
                              ("Each replicate, connected (spaghetti)", "spaghetti")])
        self.connect_line = QCheckBox("Connect the points with a line")
        self.line_w = combo(THICK[1:])
        self.line_dash = combo([("Solid", "solid"), ("Dashed", "dash"), ("Dotted", "dot")])
        self.fill_area = QCheckBox("Shade the area under the line")
        self.fill_alpha = QDoubleSpinBox()
        self.fill_alpha.setRange(5, 100)
        self.fill_alpha.setSuffix(" % opaque")
        self.fill_alpha.setDecimals(0)
        self.gaps = QCheckBox("Break the line where a value is missing")
        g.add(("Show:", self.xy_show))
        g.add((None, self.connect_line))
        g.add((None, self.gaps))
        self.row_labels = QCheckBox("Label points with their row titles")
        self.by_row = QCheckBox("A different colour for each row")
        g.add((None, self.row_labels))
        g.add((None, self.by_row))
        g.add(("Line thickness:", self.line_w), ("Line style:", self.line_dash))
        g.add((None, self.fill_area), ("Shading:", self.fill_alpha))
        lines_sec = Section("Lines and replicates")
        pl.addWidget(lines_sec)
        pl.addWidget(self.xy_box)
        lines_sec.setVisible(self.xy)
        self.xy_box.setVisible(self.xy)
        if self.xy:
            self.appearance.clear()
            for label, key in (("Points (and lines)", "scatter"), ("Bars at each X", "bar")):
                self.appearance.addItem(label, key)

        self.sec_bars = Section("Bars", checkable=True)
        pl.addWidget(self.sec_bars)
        g = FormGrid()
        self.bar_fill = ColorButton()
        self.bar_border = combo(THICK)
        self.bar_border_color = ColorButton()
        g.add(("Fill:", self.bar_fill), ("Border colour:", self.bar_border_color))
        g.add(("Border:", self.bar_border))
        pl.addLayout(g)

        self.sec_err = Section("Error bars", checkable=True)
        pl.addWidget(self.sec_err)
        g = FormGrid()
        self.err_color = ColorButton()
        self.err_dir = combo([("Up and down", "both"), ("Up only", "above"), ("Down only", "below")])
        self.err_style = combo([("With caps", "T"), ("No caps", "line")])
        self.err_width = combo(THICK[1:])
        g.add(("Colour:", self.err_color), ("Thickness:", self.err_width))
        g.add(("Direction:", self.err_dir), ("Ends:", self.err_style))
        self.whisk_box = QWidget()             # box and whiskers: the method comes first
        wl = FormGrid()
        wl.setContentsMargins(18, 2, 0, 0)
        self.whisk_box.setLayout(wl)
        self.whiskers = combo(WHISKERS)
        self.mean_plus = QCheckBox("Mark the mean with +")
        wl.add(("Extend to:", self.whiskers), (None, self.mean_plus))
        pl.addWidget(self.whisk_box)
        pl.addLayout(g)

        plot_box = QWidget()
        bl = QVBoxLayout(plot_box)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.addWidget(Section("Axis, legend and position"))
        g = FormGrid()
        self.plot_axis = combo([("Left Y axis", "left"), ("Right Y axis", "right")])
        self.in_legend = QCheckBox("Show in legend")
        g.add(("Plot against:", self.plot_axis), (None, self.in_legend))
        self.nudge, self.nudge_y = QDoubleSpinBox(), QDoubleSpinBox()
        for w in (self.nudge, self.nudge_y):
            w.setRange(-500, 500)
            w.setDecimals(1)
            w.setSuffix(" pt")
            w.valueChanged.connect(self._store)
        g.add(("Nudge right:", self.nudge), ("Nudge up:", self.nudge_y))
        self.nudge_y.setEnabled(self.xy)
        bl.addLayout(g)
        note = QLabel("Tip: select a data set on the graph and nudge it with the arrow keys (Shift: 5 pt).")
        note.setEnabled(False)
        bl.addWidget(note)
        pl.insertWidget(plot_at, plot_box)
        self.plot_axis.currentIndexChanged.connect(self._store)
        self.in_legend.toggled.connect(self._store)
        self.gaps.toggled.connect(self._store)
        self.row_labels.toggled.connect(self._store)
        self.by_row.toggled.connect(self._store)
        if self.graph.table.table_type not in ("column", "grouped", "xy", "contingency"):
            self.plot_axis.setEnabled(False)
        pl.addStretch(1)

        for w in (self.appearance, self.line_at, self.bar_border, self.sym_shape, self.sym_size,
                  self.err_dir, self.err_style, self.err_width, self.whiskers, self.spread,
                  self.smooth, self.v_quart, self.v_median):
            w.currentIndexChanged.connect(self._store)
        for w in (self.bar_fill, self.bar_border_color, self.sym_color, self.err_color):
            w.colorChanged.connect(self._store)
        for w in (self.sec_bars, self.sec_err):
            w.toggled.connect(self._store)
        for w in (self.mean_plus, self.show_points, self.connect_line, self.fill_area):
            w.toggled.connect(self._store)
        for w in (self.xy_show, self.line_w, self.line_dash):
            w.currentIndexChanged.connect(self._store)
        self.fill_alpha.valueChanged.connect(self._store)
        self.show_points.toggled.connect(lambda _on: self._sync_symbols())
        self.appearance.currentIndexChanged.connect(self._appearance_changed)
        return page

    def _appearance_changed(self, *_) -> None:
        # A new box plot starts without individual points, as box plots usually are drawn.
        if not self._loading and self.appearance.currentData() == "box" and self.show_points.isChecked():
            self.show_points.setChecked(False)
        self._sync_box_mode()

    def _datasets_page(self) -> QWidget:
        page, pl = tab_page()
        self.connect = QCheckBox("Join each row's values across data sets with a line (before-after)")
        self.connect.setChecked(self.spec.connect_rows)
        self.connect.toggled.connect(lambda v: setattr(self.spec, "connect_rows", v))
        pl.addWidget(self.connect)
        g = FormGrid()
        self.connect_w = combo(THICK[1:], self.spec.connect_width)
        self.connect_c = ColorButton(self.spec.connect_color)
        self.connect_w.currentIndexChanged.connect(
            lambda _: setattr(self.spec, "connect_width", self.connect_w.currentData()))
        self.connect_c.colorChanged.connect(lambda c: setattr(self.spec, "connect_color", c))
        g.add(("Line thickness:", self.connect_w), ("Line colour:", self.connect_c))
        self.ba_summary = combo([("Nothing", "none"), ("Mean ± SD", "mean_sd"), ("Mean ± SEM", "mean_sem"),
                                 ("Mean with 95% CI", "mean_ci"), ("Median with interquartile range", "median_iqr")],
                                self.spec.ba_summary)
        self.ba_summary.currentIndexChanged.connect(
            lambda _: setattr(self.spec, "ba_summary", self.ba_summary.currentData()))
        g.add(("Beside the points:", self.ba_summary))
        pl.addLayout(g)
        pl.addSpacing(8)
        pl.addWidget(QLabel("Data sets drawn on this graph:"))
        self.ds_list = QListWidget()
        for c in self.cols:
            it = QListWidgetItem(self.graph.table.short_label(c))
            it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Unchecked if c in self.spec.hidden else Qt.Checked)
            it.setData(Qt.UserRole, c)
            self.ds_list.addItem(it)
        self.ds_list.itemChanged.connect(self._store_hidden)
        pl.addWidget(self.ds_list, 1)
        return page

    def _store_hidden(self, *_) -> None:
        self.spec.hidden = {self.ds_list.item(i).data(Qt.UserRole)
                            for i in range(self.ds_list.count())
                            if self.ds_list.item(i).checkState() != Qt.Checked}

    def _targets(self) -> list[DataSetStyle]:
        c = self.ds_combo.currentData()
        cols = self.cols if c is None else [c]
        return [self.spec.style(k) for k in cols] or [self.spec.default_style]

    def _load(self) -> None:
        self._loading = True
        st = self._targets()[0]
        set_combo(self.appearance, st.appearance)
        set_combo(self.line_at, st.line_at)
        self.sec_bars.check.setChecked(st.bars)
        self.bar_fill.set_color(st.bar_fill)
        set_combo(self.bar_border, st.bar_border)
        self.bar_border_color.set_color(st.bar_border_color)
        self.sym_color.set_color(st.symbol_color)
        set_combo(self.sym_shape, st.symbol_shape)
        set_combo(self.sym_size, max(1, st.symbol_size))
        legacy_all = st.whiskers == "minmax_all"      # old "min to max, all points" choice
        self.show_points.setChecked(st.show_points or legacy_all)
        self.sec_err.check.setChecked(st.errors)
        self.err_color.set_color(st.error_color)
        set_combo(self.err_dir, st.error_dir)
        set_combo(self.err_style, st.error_style)
        set_combo(self.err_width, st.error_width)
        set_combo(self.whiskers, "minmax" if legacy_all else st.whiskers)
        set_combo(self.spread, st.spread)
        set_combo(self.smooth, st.violin_smooth)
        set_combo(self.v_quart, st.violin_quartiles)
        set_combo(self.v_median, st.violin_median)
        self.mean_plus.setChecked(st.mean_plus)
        set_combo(self.xy_show, st.xy_show)
        self.connect_line.setChecked(st.connect)
        set_combo(self.line_w, st.line_width)
        set_combo(self.line_dash, st.line_dash)
        set_combo(self.plot_axis, st.axis)
        self.in_legend.setChecked(st.legend)
        self.gaps.setChecked(st.gaps)
        self.row_labels.setChecked(st.row_labels)
        self.by_row.setChecked(st.by_row)
        self.nudge.setValue(st.nudge)
        self.nudge_y.setValue(st.nudge_y)
        self.fill_area.setChecked(st.fill)
        self.fill_alpha.setValue(st.fill_alpha * 100)
        self._loading = False
        self._sync_box_mode()

    def _sync_box_mode(self, *_) -> None:
        """Box and whiskers: the error-bar section controls the whiskers and the bar section
        fills the box; the box always marks the median, so the summary line does not apply."""
        kind = self.appearance.currentData()
        box = kind == "box"
        violin = kind == "violin"
        self.sec_err.check.setText("Whiskers" if box else "Error bars")
        self.sec_bars.check.setText({"box": "Fill the box", "violin": "Fill the violin",
                                     "floating": "Bars"}.get(kind, "Bars"))
        fixed_centre = kind in ("box", "violin")
        self.line_at.setEnabled(not fixed_centre)
        self.line_at_label.setEnabled(not fixed_centre)
        self.box_note.setVisible(box)
        self.whisk_box.setVisible(box)
        self.sec_err.setEnabled(not violin and kind != "floating")
        self.smooth.setVisible(violin)
        self.smooth_label.setVisible(violin)
        for w in (self.v_quart, self.v_median, self.v_lines_label):
            w.setVisible(violin)
        points_ok = kind != "symbol"
        self.show_points.setEnabled(points_ok)
        self.spread.setEnabled(points_ok)
        self.spread_label.setEnabled(points_ok)
        self.spread.setVisible(not self.xy)
        self.spread_label.setVisible(not self.xy)
        self._sync_symbols()

    def _sync_symbols(self) -> None:
        # Symbols matter when points are shown, and on box plots (values beyond the whiskers).
        box = self.appearance.currentData() == "box"
        self.symbols_box.setEnabled(self.show_points.isChecked() or box)

    def _store(self, *_) -> None:
        if self._loading:
            return
        vals = dict(
            appearance=self.appearance.currentData(), line_at=self.line_at.currentData(),
            bars=self.sec_bars.check.isChecked(), bar_fill=self.bar_fill.color(),
            bar_border=self.bar_border.currentData(),
            bar_border_color=self.bar_border_color.color(),
            symbol_color=self.sym_color.color(), symbol_shape=self.sym_shape.currentData(),
            symbol_size=self.sym_size.currentData(), errors=self.sec_err.check.isChecked(),
            error_color=self.err_color.color(), error_dir=self.err_dir.currentData(),
            error_style=self.err_style.currentData(), error_width=self.err_width.currentData(),
            whiskers=self.whiskers.currentData(), mean_plus=self.mean_plus.isChecked(),
            show_points=self.show_points.isChecked(), spread=self.spread.currentData(),
            violin_smooth=self.smooth.currentData(), xy_show=self.xy_show.currentData(),
            violin_quartiles=self.v_quart.currentData(), violin_median=self.v_median.currentData(),
            connect=self.connect_line.isChecked(), line_width=self.line_w.currentData(),
            line_dash=self.line_dash.currentData(), fill=self.fill_area.isChecked(),
            fill_alpha=self.fill_alpha.value() / 100, axis=self.plot_axis.currentData(),
            legend=self.in_legend.isChecked(), gaps=self.gaps.isChecked(), nudge=self.nudge.value(),
            row_labels=self.row_labels.isChecked(), by_row=self.by_row.isChecked(),
            nudge_y=self.nudge_y.value())
        sender = self.sender()
        # With "All data sets", only the field that was touched is pushed, so per-data-set
        # differences (e.g. one red group) survive a change elsewhere.
        changed = {k: v for k, v in vals.items()
                   if sender is None or self.ds_combo.currentData() is not None
                   or getattr(self._targets()[0], k) != v}
        for st in self._targets():
            for k, v in changed.items():
                setattr(st, k, v)
        self._sync_right_list()

    # --- Axes -----------------------------------------------------------------------

    def _x_page(self) -> QWidget:
        page, pl = tab_page()
        x = self.spec.x
        if self.numx:
            pl.addWidget(Section("Range"))
            g = FormGrid()
            self.x_scale = combo([("Linear", "linear"), ("Logarithmic (base 10)", "log10")], x.scale)
            self.x_auto = QCheckBox("Automatic")
            self.x_auto.setChecked(x.auto)
            self.x_min, self.x_max, self.x_step = (num_edit(x.vmin), num_edit(x.vmax), num_edit(x.interval))
            g.add(("Scale:", self.x_scale), (None, self.x_auto))
            g.add(("Minimum:", self.x_min), ("Maximum:", self.x_max), ("Major ticks every:", self.x_step))
            pl.addLayout(g)
            self.x_auto.toggled.connect(lambda on: [w.setEnabled(not on) for w in (self.x_min, self.x_max, self.x_step)])
            for w in (self.x_min, self.x_max, self.x_step):
                w.setEnabled(not x.auto)
            pl.addWidget(Section("Title"))
            g = FormGrid()
            self.x_title = QLineEdit(x.title)
            g.add(("X-axis title:", self.x_title))
            pl.addLayout(g)
        pl.addWidget(Section("Ticks"))
        g = FormGrid()
        self.x_ticks = combo([("None", "none"), ("Outside", "out"), ("Inside", "in"),
                              ("Crossing", "cross")], x.ticks_dir)
        self.x_len = combo(TICK_LEN, x.ticks_len)
        g.add(("Ticks:", self.x_ticks), ("Length:", self.x_len))
        pl.addLayout(g)
        pl.addWidget(Section("Labels"))
        g = FormGrid()
        self.x_rot = combo([("Horizontal", 0), ("Angled 45°", 45), ("Vertical", 90)],
                           x.label_rotation)
        g.add(("Label angle:", self.x_rot))
        pl.addLayout(g)
        if self.numx:
            self.axis_ctl["x"] = {}
            self._guide_controls(pl, x, self.axis_ctl["x"], "X value")
        pl.addStretch(1)
        return page

    def _y_page(self) -> QWidget:
        page, w = self._axis_controls(self.spec.y, self.auto_range, "y")
        for k in ("scale", "auto", "min", "max", "step", "ticks", "len", "minor", "num", "fmt", "dec",
                  "prefix", "suffix"):
            setattr(self, f"y_{k}", w[k])           # older names, used by tests and callers
        return page

    def _right_page(self) -> QWidget:
        tt = self.graph.table.table_type
        supported = tt in ("column", "grouped", "xy", "contingency")
        rng = None
        try:
            from ..graph.layout import build
            rng = next((e.meta.get("range") for e in build(self.graph)[0] if e.id == "y2-axis"), None)
        except Exception:
            rng = None
        page, w = self._axis_controls(self.spec.y2, rng, "y2")
        lay = page.layout()
        self.right_list = QListWidget()
        self.right_list.setMaximumHeight(120)
        for c in self.cols:
            it = QListWidgetItem(self.graph.table.short_label(c))
            it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if self.spec.style(c).axis == "right" else Qt.Unchecked)
            it.setData(Qt.UserRole, c)
            self.right_list.addItem(it)
        self.right_list.itemChanged.connect(self._right_ticked)
        if supported:
            msg = QLabel("Tick the data sets to plot against the right Y axis (the same as “Plot against” "
                         "under Data sets › Style).")
        else:
            msg = QLabel("This kind of graph has no right Y axis.")
            page.setEnabled(False)
        msg.setWordWrap(True)
        msg.setEnabled(False)
        lay.insertWidget(0, Section("Data sets on the right axis"))
        lay.insertWidget(1, msg)
        lay.insertWidget(2, self.right_list)
        g = FormGrid()
        self.y2_title = QLineEdit(self.spec.y2.title)
        g.add(("Title:", self.y2_title))
        lay.insertWidget(3, Section("Title"))
        lay.insertLayout(4, g)
        return page

    def _right_ticked(self, it) -> None:
        if self._loading:
            return
        self.spec.style(it.data(Qt.UserRole)).axis = "right" if it.checkState() == Qt.Checked else "left"
        self._load()                                   # the Style page's "Plot against" follows

    def _sync_right_list(self) -> None:
        if not hasattr(self, "right_list"):
            return
        self.right_list.blockSignals(True)
        for i in range(self.right_list.count()):
            it = self.right_list.item(i)
            it.setCheckState(Qt.Checked if self.spec.style(it.data(Qt.UserRole)).axis == "right" else Qt.Unchecked)
        self.right_list.blockSignals(False)

    def _axis_controls(self, ax, r, key: str) -> tuple[QWidget, dict]:
        """Range, ticks, number format, grid lines, extra ticks and a break for one Y axis."""
        page, pl = tab_page()
        w: dict = {}
        self.axis_ctl[key] = w
        pl.addWidget(Section("Range"))
        g = FormGrid()
        w["scale"] = combo([("Linear", "linear"), ("Logarithmic (base 10)", "log10")], ax.scale)
        g.add(("Scale:", w["scale"]))
        pl.addLayout(g)
        w["auto"] = QCheckBox("Choose the range and tick interval automatically")
        w["auto"].setChecked(ax.auto)
        w["auto"].setContentsMargins(18, 0, 0, 0)
        pl.addWidget(w["auto"])
        g = FormGrid()
        vmin = r.vmin if (ax.auto and r) else ax.vmin
        vmax = r.vmax if (ax.auto and r) else ax.vmax
        step = r.interval if (ax.auto and r) else ax.interval
        w["min"], w["max"], w["step"] = num_edit(vmin), num_edit(vmax), num_edit(step)
        g.add(("From:", w["min"]), ("To:", w["max"]))
        g.add(("Tick every:", w["step"]))
        pl.addLayout(g)

        pl.addWidget(Section("Ticks"))
        g = FormGrid()
        w["ticks"] = combo([("Outside", "out"), ("Inside", "in"), ("Crossing", "cross"), ("None", "none")],
                           ax.ticks_dir)
        w["len"] = combo(TICK_LEN, ax.ticks_len)
        w["minor"] = combo([("None", 0), ("1", 1), ("2", 2), ("4", 4), ("9", 9)], ax.minor)
        w["num"] = combo([("Show", True), ("Hide", False)], ax.numbering)
        g.add(("Ticks:", w["ticks"]), ("Length:", w["len"]))
        g.add(("Minor ticks between:", w["minor"]), ("Numbers:", w["num"]))
        pl.addLayout(g)

        pl.addWidget(Section("Number format"))
        g = FormGrid()
        w["fmt"] = combo([("Decimal", "decimal"), ("Scientific", "scientific")], ax.fmt)
        w["dec"] = combo([("Automatic", -1)] + [(str(i), i) for i in range(0, 6)], ax.decimals)
        w["prefix"], w["suffix"] = QLineEdit(ax.prefix), QLineEdit(ax.suffix)
        w["prefix"].setFixedWidth(80)
        w["suffix"].setFixedWidth(80)
        g.add(("Style:", w["fmt"]), ("Decimals:", w["dec"]))
        g.add(("Before numbers:", w["prefix"]), ("After numbers:", w["suffix"]))
        pl.addLayout(g)

        self._guide_controls(pl, ax, w, "Y value")

        pl.addWidget(Section("Break"))
        b = dict(ax.brk or {})
        w["brk_on"] = QCheckBox("Break the axis into two segments")
        w["brk_on"].setChecked(bool(b.get("on")))
        w["brk_on"].setContentsMargins(18, 0, 0, 0)
        pl.addWidget(w["brk_on"])
        g = FormGrid()
        lo_d = b.get("low_to", (vmin + (vmax - vmin) * 0.3))
        hi_d = b.get("high_from", (vmin + (vmax - vmin) * 0.6))
        w["brk_lo"], w["brk_hi"] = num_edit(lo_d), num_edit(hi_d)
        w["brk_ls"], w["brk_hs"] = num_edit(b.get("low_step", 0) or 0), num_edit(b.get("high_step", 0) or 0)
        w["brk_split"] = QSpinBox()
        w["brk_split"].setRange(10, 90)
        w["brk_split"].setSuffix(" %")
        w["brk_split"].setValue(int(round(float(b.get("split", 0.5)) * 100)))
        w["brk_gap"] = QDoubleSpinBox()
        w["brk_gap"].setRange(1, 40)
        w["brk_gap"].setSuffix(" pt")
        w["brk_gap"].setValue(float(b.get("gap", 14.0)))
        g.add(("Bottom segment ends at:", w["brk_lo"]), ("Top segment starts at:", w["brk_hi"]))
        g.add(("Bottom ticks every:", w["brk_ls"]), ("Top ticks every:", w["brk_hs"]))
        g.add(("Bottom segment length:", w["brk_split"]), ("Gap:", w["brk_gap"]))
        pl.addLayout(g)
        note = QLabel("Tick spacing 0 = automatic. A break needs a linear scale.")
        note.setEnabled(False)
        pl.addWidget(note)
        pl.addStretch(1)

        def sync(*_):
            manual = not w["auto"].isChecked()
            for k in ("min", "max", "step"):
                w[k].setEnabled(manual)
            on = w["brk_on"].isChecked() and w["scale"].currentData() == "linear"
            w["brk_on"].setEnabled(w["scale"].currentData() == "linear")
            for k in ("brk_lo", "brk_hi", "brk_ls", "brk_hs", "brk_split", "brk_gap"):
                w[k].setEnabled(on)
        w["auto"].toggled.connect(sync)
        w["brk_on"].toggled.connect(sync)
        w["scale"].currentIndexChanged.connect(sync)
        sync()
        return page, w

    def _guide_controls(self, pl, ax, w: dict, value_label: str) -> None:
        pl.addWidget(Section("Grid lines and extra ticks"))
        row = QHBoxLayout()
        row.setContentsMargins(18, 0, 0, 0)
        w["grid"] = QCheckBox("Grid lines at the major ticks")
        w["grid"].setChecked(ax.grid)
        w["grid_color"] = ColorButton(ax.grid_color)
        row.addWidget(w["grid"])
        row.addWidget(w["grid_color"])
        row.addStretch(1)
        pl.addLayout(row)
        t = QTableWidget(4, 6)
        t.setHorizontalHeaderLabels([value_label, "To (band)", "Line", "Tick", "Style", "Label"])
        t.setToolTip("A value draws a line or tick there; fill in “To” as well for a shaded band.")
        t.verticalHeader().hide()
        t.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        t.setFixedHeight(126)
        extra = list(ax.extra or [])
        for i in range(4):
            e = extra[i] if i < len(extra) else {}
            t.setItem(i, 0, QTableWidgetItem("" if e.get("value") is None else f"{e['value']:g}"))
            t.setItem(i, 1, QTableWidgetItem("" if e.get("to") in (None, "") else f"{float(e['to']):g}"))
            for j, k, default in ((2, "line", True), (3, "tick", False)):
                it = QTableWidgetItem()
                it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
                it.setCheckState(Qt.Checked if e.get(k, default) else Qt.Unchecked)
                t.setItem(i, j, it)
            dash = combo([("Dashed", "dash"), ("Dotted", "dot"), ("Solid", "solid")], e.get("dash", "dash"))
            t.setCellWidget(i, 4, dash)
            t.setItem(i, 5, QTableWidgetItem(e.get("label", "")))
        w["extra"] = t
        row = QHBoxLayout()
        row.setContentsMargins(18, 0, 0, 0)
        row.addWidget(t)
        pl.addLayout(row)

    @staticmethod
    def _collect_guides(ax, w: dict) -> None:
        ax.grid = w["grid"].isChecked()
        ax.grid_color = w["grid_color"].color()
        t, extra = w["extra"], []
        for i in range(t.rowCount()):
            txt = (t.item(i, 0).text() if t.item(i, 0) else "").strip().replace(",", ".")
            try:
                v = float(txt)
            except ValueError:
                continue
            e = {"value": v, "line": t.item(i, 2).checkState() == Qt.Checked,
                 "tick": t.item(i, 3).checkState() == Qt.Checked,
                 "dash": t.cellWidget(i, 4).currentData(), "label": t.item(i, 5).text().strip()}
            to = (t.item(i, 1).text() if t.item(i, 1) else "").strip().replace(",", ".")
            try:
                e["to"] = float(to)
            except ValueError:
                pass
            extra.append(e)
        ax.extra = extra

    def _collect_axis(self, ax, w: dict) -> None:
        def f(e: QLineEdit, default: float) -> float:
            try:
                return float(e.text().replace(",", "."))
            except ValueError:
                return default
        ax.scale = w["scale"].currentData()
        ax.auto = w["auto"].isChecked()
        if not ax.auto:
            ax.vmin = f(w["min"], ax.vmin)
            ax.vmax = f(w["max"], ax.vmax)
            ax.interval = abs(f(w["step"], ax.interval)) or 1.0
        ax.ticks_dir = w["ticks"].currentData()
        ax.ticks_len = w["len"].currentData()
        ax.minor = w["minor"].currentData()
        ax.numbering = w["num"].currentData()
        ax.fmt = w["fmt"].currentData()
        ax.decimals = w["dec"].currentData()
        ax.prefix, ax.suffix = w["prefix"].text(), w["suffix"].text()
        self._collect_guides(ax, w)
        lo, hi = f(w["brk_lo"], 0.0), f(w["brk_hi"], 0.0)
        ax.brk = {"on": w["brk_on"].isChecked() and hi > lo, "low_to": lo, "high_from": hi,
                  "low_step": abs(f(w["brk_ls"], 0.0)), "high_step": abs(f(w["brk_hs"], 0.0)),
                  "split": w["brk_split"].value() / 100, "gap": w["brk_gap"].value()}

    # --- commit ---------------------------------------------------------------------

    def _collect(self) -> None:
        s = self.spec
        self._collect_sig()
        s.col_width_mm = self.col_w.value()
        s.horizontal = bool(self.orient.currentData())
        s.x_len_mm = self.x_axis_len.value()
        s.y_len_mm = self.height_mm.value()
        s.frame = self.frame.currentData()
        s.axis_width = self.axis_w.currentData()
        s.axis_color = self.axis_c.color()
        s.show_title = self.show_title.isChecked()
        tt = self.graph.table.table_type
        if tt == "parts":
            s.parts_layout = self.arrangement.currentData()
            s.parts_labels = self.parts_labels.currentData()
            s.donut_hole = self.hole.value() / 100
            s.show_legend = self.legend.isChecked()
        elif tt == "survival":
            k = self.surv_y.currentData()
            s.surv_percent, s.surv_death = k.startswith("pct"), k.endswith("death")
            s.surv_ci = self.surv_ci.currentData()
            s.surv_ticks = self.surv_ticks.isChecked()
            s.show_legend = self.legend.isChecked()
            auto = ("Percent survival", "Fraction survival", "Percent death", "Fraction death", "")
            if self.t_ytitle.text().strip() in auto:          # a title the user hasn't changed: follow
                self.t_ytitle.setText(("Percent " if s.surv_percent else "Fraction ")
                                      + ("death" if s.surv_death else "survival"))
        elif tt in ("grouped", "contingency"):
            s.grouped_layout = self.arrangement.currentData()
            s.show_legend = self.legend.isChecked()
            s.heat_low, s.heat_high = self.heat_low.color(), self.heat_high.color()
        elif tt == "nested":
            s.nested_layout = self.arrangement.currentData()
        elif tt == "multivar":
            ys = [self.mv_y.item(i).data(Qt.UserRole) for i in range(self.mv_y.count())
                  if self.mv_y.item(i).checkState() == Qt.Checked]
            s.mv = {**s.mv, "x": self.mv_x.currentData(), "y": ys, "size": self.mv_size.currentData(),
                    "color": self.mv_color.currentData(), "labels": self.mv_labels.isChecked(),
                    "size_min": self.mv_smin.value(), "size_max": self.mv_smax.value()}
            s.show_legend = self.legend.isChecked()
            s.heat_low, s.heat_high = self.heat_low.color(), self.heat_high.color()
        s.x.ticks_dir = self.x_ticks.currentData()
        s.x.ticks_len = self.x_len.currentData()
        s.x.label_rotation = self.x_rot.currentData()
        if self.numx:
            s.x.scale = self.x_scale.currentData()
            s.x.auto = self.x_auto.isChecked()
            s.x.title = self.x_title.text().strip()

            def fx(e, default):
                try:
                    return float(e.text().replace(",", "."))
                except ValueError:
                    return default
            if not s.x.auto:
                s.x.vmin, s.x.vmax = fx(self.x_min, s.x.vmin), fx(self.x_max, s.x.vmax)
                s.x.interval = abs(fx(self.x_step, s.x.interval)) or 1.0
        self._collect_axis(s.y, self.axis_ctl["y"])
        self._collect_axis(s.y2, self.axis_ctl["y2"])
        s.y2.title = self.y2_title.text().strip()
        if self.numx and "x" in self.axis_ctl:
            self._collect_guides(s.x, self.axis_ctl["x"])
        y = s.y
        title = self.t_title.text().strip()
        s.title = "" if title == self.graph.table.name else title
        y.title = self.t_ytitle.text().strip()
        for key, (fam, size, b, it) in self.font_rows.items():
            fs = s.fonts[key]
            fs.family, fs.size = fam.currentFont().family(), size.value()
            fs.bold, fs.italic = b.isChecked(), it.isChecked()

    def apply(self) -> None:
        self._collect()
        self.project.undo.push(SpecCommand(self.graph, self.spec, "Format Graph"))
        self.spec = copy.deepcopy(self.graph.spec)
        for c in self.cols:
            self.spec.style(c)
        self._load()

    def accept(self) -> None:
        self.apply()
        super().accept()
