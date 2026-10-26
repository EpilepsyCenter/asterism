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
                               QListWidget, QListWidgetItem, QMessageBox, QPushButton,
                               QTableWidget, QToolButton, QWidget)

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
                        ("Heat map", "heatmap")]
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
        self.cols = graph.table.used_columns()
        for c in self.cols:
            self.spec.style(c)
        self._loading = False

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
        if self.xy:
            g.add(("X-axis length:", self.x_axis_len), ("Plot height:", self.height_mm))
        else:
            g.add(("Column width:", self.col_w), ("Plot height:", self.height_mm))
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
                                          ("bracket", "Significance labels"),
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

    def _arrangement_page(self, tt: str) -> QWidget:
        page, pl = tab_page()
        s = self.spec
        g = FormGrid()
        if tt == "parts":
            self.arrangement = combo([("Pie chart", "pie"), ("Donut chart", "donut"),
                                      ("Bar stacked to 100%", "stacked100")], s.parts_layout)
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
                                  ("Shaded band", "shaded")], s.surv_ci)
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
        page, pl = tab_page()
        pl.addWidget(Section("Comparisons from analyses"))
        self.show_br = QCheckBox("Draw significance brackets for comparisons in linked analyses")
        self.show_br.setChecked(self.spec.show_brackets)
        pl.addWidget(self.show_br)
        g = FormGrid()
        self.p_fmt = combo([("Stars (ns, *, **, ***, ****)", "stars"),
                            ("P value (P = 0.0123)", "exact")], self.spec.p_format)
        g.add(("Label:", self.p_fmt))
        pl.addLayout(g)
        pl.addStretch(1)
        self.show_br.toggled.connect(lambda v: setattr(self.spec, "show_brackets", v))
        self.p_fmt.currentIndexChanged.connect(
            lambda _: setattr(self.spec, "p_format", self.p_fmt.currentData()))
        return page

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
        pl.addLayout(g)
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
        g.add(("Colour:", self.sym_color), ("Shape:", self.sym_shape), ("Size:", self.sym_size))
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
        g.add(("Show:", self.xy_show))
        g.add((None, self.connect_line))
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
        g.add(("Fill:", self.bar_fill), ("Border:", self.bar_border),
              ("Border colour:", self.bar_border_color))
        pl.addLayout(g)

        self.sec_err = Section("Error bars", checkable=True)
        pl.addWidget(self.sec_err)
        g = FormGrid()
        self.err_color = ColorButton()
        self.err_dir = combo([("Up and down", "both"), ("Up only", "above"), ("Down only", "below")])
        self.err_style = combo([("With caps", "T"), ("No caps", "line")])
        self.err_width = combo(THICK[1:])
        g.add(("Colour:", self.err_color), ("Direction:", self.err_dir), ("Ends:", self.err_style))
        g.add(("Thickness:", self.err_width))
        self.whisk_box = QWidget()             # box and whiskers: the method comes first
        wl = FormGrid()
        wl.setContentsMargins(18, 2, 0, 0)
        self.whisk_box.setLayout(wl)
        self.whiskers = combo(WHISKERS)
        self.mean_plus = QCheckBox("Mark the mean with +")
        wl.add(("Extend to:", self.whiskers), (None, self.mean_plus))
        pl.addWidget(self.whisk_box)
        pl.addLayout(g)

        pl.addSpacing(6)
        pl.addWidget(Section("Plotting"))
        g = FormGrid()
        left, legend = QCheckBox("Left Y axis"), QCheckBox("Show in legend")
        left.setChecked(True)
        for c in (left, legend):
            c.setEnabled(False)
            c.setToolTip("A right Y axis and per-data-set legend choices arrive in M9")
        g.add(("Plot against:", left), (None, legend))
        pl.addLayout(g)
        pl.addStretch(1)

        for w in (self.appearance, self.line_at, self.bar_border, self.sym_shape, self.sym_size,
                  self.err_dir, self.err_style, self.err_width, self.whiskers, self.spread,
                  self.smooth):
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
        self.mean_plus.setChecked(st.mean_plus)
        set_combo(self.xy_show, st.xy_show)
        self.connect_line.setChecked(st.connect)
        set_combo(self.line_w, st.line_width)
        set_combo(self.line_dash, st.line_dash)
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
            connect=self.connect_line.isChecked(), line_width=self.line_w.currentData(),
            line_dash=self.line_dash.currentData(), fill=self.fill_area.isChecked(),
            fill_alpha=self.fill_alpha.value() / 100)
        sender = self.sender()
        # With "All data sets", only the field that was touched is pushed, so per-data-set
        # differences (e.g. one red group) survive a change elsewhere.
        changed = {k: v for k, v in vals.items()
                   if sender is None or self.ds_combo.currentData() is not None
                   or getattr(self._targets()[0], k) != v}
        for st in self._targets():
            for k, v in changed.items():
                setattr(st, k, v)

    # --- Axes -----------------------------------------------------------------------

    def _x_page(self) -> QWidget:
        page, pl = tab_page()
        x = self.spec.x
        if self.xy:
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
        pl.addStretch(1)
        return page

    def _y_page(self) -> QWidget:
        page, pl = tab_page()
        y = self.spec.y
        r = self.auto_range
        pl.addWidget(Section("Range"))
        g = FormGrid()
        self.y_scale = combo([("Linear", "linear"), ("Logarithmic (base 10)", "log10")], y.scale)
        g.add(("Scale:", self.y_scale))
        pl.addLayout(g)
        self.y_auto = QCheckBox("Choose the range and tick interval automatically")
        self.y_auto.setChecked(y.auto)
        self.y_auto.setContentsMargins(18, 0, 0, 0)
        pl.addWidget(self.y_auto)
        g = FormGrid()
        vmin = r.vmin if (y.auto and r) else y.vmin
        vmax = r.vmax if (y.auto and r) else y.vmax
        step = r.interval if (y.auto and r) else y.interval
        self.y_min, self.y_max = num_edit(vmin), num_edit(vmax)
        self.y_step = num_edit(step)
        g.add(("From:", self.y_min), ("To:", self.y_max))
        g.add(("Tick every:", self.y_step))
        pl.addLayout(g)

        pl.addWidget(Section("Ticks"))
        g = FormGrid()
        self.y_ticks = combo([("Outside", "out"), ("Inside", "in"), ("Crossing", "cross"),
                              ("None", "none")], y.ticks_dir)
        self.y_len = combo(TICK_LEN, y.ticks_len)
        self.y_minor = combo([("None", 0), ("1", 1), ("2", 2), ("4", 4), ("9", 9)], y.minor)
        self.y_num = combo([("Show", True), ("Hide", False)], y.numbering)
        g.add(("Ticks:", self.y_ticks), ("Length:", self.y_len))
        g.add(("Minor ticks between:", self.y_minor), ("Numbers:", self.y_num))
        pl.addLayout(g)

        pl.addWidget(Section("Number format"))
        g = FormGrid()
        self.y_fmt = combo([("Decimal", "decimal"), ("Scientific", "scientific")], y.fmt)
        self.y_dec = combo([("Automatic", -1)] + [(str(i), i) for i in range(0, 6)], y.decimals)
        self.y_prefix = QLineEdit(y.prefix)
        self.y_prefix.setFixedWidth(80)
        self.y_suffix = QLineEdit(y.suffix)
        self.y_suffix.setFixedWidth(80)
        g.add(("Style:", self.y_fmt), ("Decimals:", self.y_dec))
        g.add(("Before numbers:", self.y_prefix), ("After numbers:", self.y_suffix))
        pl.addLayout(g)

        pl.addWidget(Section("Extra ticks and grid lines"))
        extra = QTableWidget(3, 4)
        extra.setHorizontalHeaderLabels(["Y value", "Tick", "Line", "Label"])
        extra.verticalHeader().hide()
        extra.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        extra.setFixedHeight(104)
        extra.setEnabled(False)
        extra.setToolTip("Arrives with graph polish (M9)")
        row = QHBoxLayout()
        row.setContentsMargins(18, 0, 0, 0)
        row.addWidget(extra)
        pl.addLayout(row)
        pl.addStretch(1)
        self.y_auto.toggled.connect(self._auto_toggled)
        self._auto_toggled(y.auto)
        return page

    def _auto_toggled(self, on: bool) -> None:
        for w in (self.y_min, self.y_max, self.y_step):
            w.setEnabled(not on)

    def _right_page(self) -> QWidget:
        page, pl = tab_page()
        msg = QLabel("No data sets are plotted against a right Y axis. Choose “Plot against: "
                     "Right Y axis” for a data set under Data sets → Style (arrives in M9).")
        msg.setWordWrap(True)
        msg.setEnabled(False)
        pl.addWidget(msg)
        pl.addStretch(1)
        return page

    # --- commit ---------------------------------------------------------------------

    def _collect(self) -> None:
        s = self.spec
        s.col_width_mm = self.col_w.value()
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
        s.x.ticks_dir = self.x_ticks.currentData()
        s.x.ticks_len = self.x_len.currentData()
        s.x.label_rotation = self.x_rot.currentData()
        if self.xy:
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
        y = s.y
        y.scale = self.y_scale.currentData()
        y.auto = self.y_auto.isChecked()

        def f(e: QLineEdit, default: float) -> float:
            try:
                return float(e.text().replace(",", "."))
            except ValueError:
                return default
        if not y.auto:
            y.vmin = f(self.y_min, y.vmin)
            y.vmax = f(self.y_max, y.vmax)
            y.interval = abs(f(self.y_step, y.interval)) or 1.0
        y.ticks_dir = self.y_ticks.currentData()
        y.ticks_len = self.y_len.currentData()
        y.minor = self.y_minor.currentData()
        y.numbering = self.y_num.currentData()
        y.fmt = self.y_fmt.currentData()
        y.decimals = self.y_dec.currentData()
        y.prefix, y.suffix = self.y_prefix.text(), self.y_suffix.text()
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
