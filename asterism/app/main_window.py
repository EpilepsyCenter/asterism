"""Main window: project sidebar | top bar + sheet + status strip | tool panel.

ASTERISM's own window structure (SPEC §2.1, §12), NED-Net's arrangement: the two
sidebars are resizable (widths remembered) and can be hidden. One window per project;
the window owns the file path and the edited state, and asks before closing unsaved work.
"""

from __future__ import annotations

import copy
import os
import sys

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QComboBox, QFileDialog, QFontComboBox, QLabel, QMainWindow,
                               QMenu, QMessageBox, QSplitter, QStackedWidget, QVBoxLayout,
                               QWidget)

from ..analysis import engine
from ..doc import fileformat
from ..doc.commands import ParamsCommand, SpecCommand
from ..doc.model import (Analysis, Table, Graph, InfoSheet, FigureSheet, Project, Sheet,
                         column_letter)
from ..doc.sample import blank_project, sample_project
from . import documents, prefs, theme
from .dialogs.analyze import AnalyzeDialog, TTestParamsDialog
from .dialogs.format_graph import APPEARANCES, FormatGraphDialog
from .graph import export as gexport
from .graph.layout import GRAPHABLE_TYPES
from .graph.view import GraphSheet
from .icons import set_icon
from .sheets import InfoSheetView, PlaceholderSheet, ResultsSheet
from .sidebar import ProjectSidebar
from .table_view import DataTableSheet
from .toolbar import StatusStrip, ToolPanel, TopBar

APP_NAME = "ASTERISM"
SIDEBAR_W, TOOLS_W = 250, 232

_windows: list["MainWindow"] = []
# Analyses whose result table gets its own graph when they are created (as Prism does).
def _install_graph_defaults() -> None:
    """New graphs follow the user's settings (once per process)."""
    from ..doc import model as _model
    from . import prefs as _prefs
    if _prefs.style_new_graph not in _model.NEW_GRAPH_HOOKS:
        _model.NEW_GRAPH_HOOKS.append(_prefs.style_new_graph)


_install_graph_defaults()

OUTPUT_GRAPHED = {"frequency", "transform", "normalize", "baseline", "prune", "smooth", "fraction"}


class MainWindow(QMainWindow):
    def __init__(self, project: Project | None = None, path: str | None = None):
        super().__init__()
        theme.install()
        self.project = project or blank_project(engine)
        if self.project.engine is None:
            self.project.set_engine(engine)
        self.path: str | None = os.path.abspath(path) if path else None
        self.setUnifiedTitleAndToolBarOnMac(False)
        self.resize(1480, 920)
        self.widgets: dict[int, QWidget] = {}
        self.current: Sheet | None = None
        self._enable_on: dict[QAction, set[str] | None] = {}
        self._table_types: dict[QAction, set[str]] = {}    # actions that need a table type

        self.setAcceptDrops(True)
        from . import recovery
        from PySide6.QtCore import QTimer
        self._autosave_key = recovery.new_key()
        self._autosave_timer = QTimer(self)
        self._autosave_timer.timeout.connect(self.autosave)
        self.apply_autosave_prefs()
        self._make_actions()
        self._make_menus()
        self._make_layout()

        self.project.structure_changed.connect(self._structure_changed)
        self.project.edited.connect(self._edited)
        self._edited()
        sheets = self._all_sheets()
        if sheets:
            self.show_sheet(self.project.tables[0] if self.project.tables else sheets[0])

    # ------------------------------------------------------------------ actions

    def _act(self, text, sf=None, slot=None, shortcut=None, accent=None, tip=None,
             kinds=None) -> QAction:
        """kinds: sheet kinds the action applies to (None = always)."""
        a = QAction(text, self)
        set_icon(a, sf or "questionmark", accent)
        if slot:
            a.triggered.connect(slot)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        a.setToolTip(tip or text.replace("…", ""))
        a.setIconVisibleInMenu(False)
        self._enable_on[a] = set(kinds) if kinds else None
        return a

    def _later(self, text, sf, milestone) -> QAction:
        """A tool that is not built yet: visible, greyed out, with a tooltip saying when."""
        a = QAction(text, self)
        set_icon(a, sf)
        a.setToolTip(f"{text.replace('…', '')} — not available yet")
        a.setEnabled(False)
        a.setIconVisibleInMenu(False)
        return a

    def _make_actions(self) -> None:
        A, L = self._act, self._later
        G, T = ("graph",), ("table",)
        # Project
        self.a_new = A("New Project", "doc.badge.plus", new_window, QKeySequence.New, "accent")
        self.a_open = A("Open…", "folder", self.open_file, QKeySequence.Open)
        self.a_import = A("Import Data…", "square.and.arrow.down.on.square", self.import_data, "Ctrl+Shift+I",
                          tip="Spreadsheets (CSV, Excel), lab exports (NED-Net, TRACER, QuantStudio) and Prism files")
        self.a_import_settings = A("Import Settings…", "slider.horizontal.3", lambda: self.import_settings(),
                                   tip="Change how this table was imported (its tables update in place)")
        self.a_close = A("Close", "xmark", self.close, QKeySequence.Close)
        self.a_save = A("Save", "square.and.arrow.down", self.save, QKeySequence.Save)
        self.a_save_as = A("Save As…", "save.as", self.save_as,
                           QKeySequence.SaveAs)
        self.a_revert = A("Revert to Saved", "arrow.counterclockwise", self.revert)
        self.a_sample = A("Open Sample Project", "doc.text", open_sample)
        self.a_start = A("Start Window…", "rectangle.grid.1x2", lambda: run_start(self))
        self.a_undo = A("Undo", "arrow.uturn.backward", self.project.undo.undo, QKeySequence.Undo)
        self.a_redo = A("Redo", "arrow.uturn.forward", self.project.undo.redo, QKeySequence.Redo)
        self.a_print = L("Print…", "printer", "M11")
        # Sheet
        self.a_new_table = A("New Data Table…", "tablecells.badge.ellipsis", lambda: self._command("new_table"), accent="accent")
        self.a_new_graph = A("New Graph", "chart.line.uptrend.xyaxis", lambda: self._command("new_graph"), accent="accent")
        self.a_new_figure = A("New Figure", "rectangle.split.2x2", lambda: self._command("new_figure"), accent="accent")
        self.a_new_info = A("New Notes", "note.text.badge.plus", lambda: self._command("new_info"), accent="accent")
        self.a_duplicate = L("Duplicate Sheet", "plus.square.on.square", "M2")
        self.a_delete = A("Delete Sheet", "trash", self._delete_sheet, accent="red")
        self.a_prev = A("Previous Sheet", "chevron.up", lambda: self._step_sheet(-1), "Ctrl+[")
        self.a_next = A("Next Sheet", "chevron.down", lambda: self._step_sheet(1), "Ctrl+]")
        # Edit
        self.a_cut = A("Cut", "scissors", lambda: self._table_op("cut"), QKeySequence.Cut, kinds=T)
        self.a_copy = A("Copy", "doc.on.doc", self._copy, QKeySequence.Copy, kinds=(*T, "graph", "figure"))
        self.a_paste = A("Paste", "doc.on.clipboard", lambda: self._table_op("paste"), QKeySequence.Paste, kinds=T)
        self.a_insert_row = A("Insert Rows", "text.insert", lambda: self._table_op("insert_rows"), kinds=T)
        self.a_delete_row = A("Delete Rows", "text.badge.minus", lambda: self._table_op("delete_rows"), kinds=T)
        self.a_insert_set = A("Insert Data Set", "rectangle.split.3x1", lambda: self._table_op("insert_sets"), kinds=T)
        self.a_delete_set = A("Delete Data Set", "rectangle.badge.minus", lambda: self._table_op("delete_sets"), kinds=T)
        self.a_exclude = A("Exclude or Include Values", "eye.slash", lambda: self._table_op("toggle_exclude"), "Ctrl+Shift+E", kinds=T)
        self.a_table_format = A("Table Format…", "tablecells.badge.ellipsis", self.table_format, kinds=T)
        self.a_sort = L("Sort", "arrow.up.arrow.down", "M2")
        self.a_transpose = L("Transpose", "arrow.left.arrow.right.square", "M7")
        # Export
        self.a_export_pdf = A("Export PDF…", "doc.richtext", lambda: self.export("pdf"), "Ctrl+E", kinds=("graph", "figure"))
        self.a_export_svg = A("Export SVG…", "square.and.arrow.up", lambda: self.export("svg"), kinds=("graph", "figure"))
        self.a_export_png = A("Export PNG…", "photo", lambda: self.export("png"), kinds=("graph", "figure"))
        self.a_export_tiff = A("Export TIFF…", "photo.stack", lambda: self.export("tiff"), kinds=("graph", "figure"))
        # Figures
        F = ("figure",)
        self.a_fig_add = A("Add Graphs and Tables…", "plus.rectangle.on.rectangle", self.figure_add, kinds=F,
                           accent="accent")
        self.a_fig_text = A("Add Text", "textbox", self.figure_add_text, kinds=F)
        self.a_fig_grid = A("Arrange in a Grid…", "square.grid.2x2", self.figure_grid, kinds=F)
        self.a_fig_left = A("Align Left Edges", "align.horizontal.left", lambda: self._figure_op("align", "left"), kinds=F)
        self.a_fig_top = A("Align Top Edges", "align.vertical.top", lambda: self._figure_op("align", "top"), kinds=F)
        self.a_fig_hc = A("Align Centres", "align.horizontal.center", lambda: self._figure_op("align", "hcenter"), kinds=F)
        self.a_fig_width = A("Same Width", "arrow.left.and.right.square", lambda: self._figure_op("same_width"), kinds=F)
        self.a_fig_front = A("Bring to Front", "square.3.layers.3d.top.filled", lambda: self._figure_op("restack", True), kinds=F)
        self.a_fig_back = A("Send to Back", "square.3.layers.3d.bottom.filled", lambda: self._figure_op("restack", False), kinds=F)
        self.a_fig_format = A("Format Figure…", "doc.badge.gearshape", self.figure_format, kinds=F)
        self.a_add_to_figure = A("Add to Figure…", "rectangle.split.2x2", self.add_graph_to_figure, kinds=G)
        self.a_copy_graph = A("Copy Graph to Clipboard", "doc.on.clipboard.fill", self.copy_graphic,
                              "Ctrl+Shift+C", kinds=("graph", "figure"),
                              tip="Copy as a vector picture: paste into Word, PowerPoint, Keynote or Illustrator")
        self.a_export_table = L("Export Table (CSV / Excel)…", "tablecells", "M10")
        # Analyze
        self.a_analyze = A("Analyze…", "function", self.analyze, "Ctrl+Shift+A", "accent", "Analyze data")
        self.a_params = A("Analysis Settings…", "slider.horizontal.3", self.change_params, kinds=("analysis",))
        self.a_desc = A("Descriptive Statistics", "sum", lambda: self._quick("descriptive"))
        self.a_anova = A("One-way ANOVA…", "square.split.1x2", lambda: self._quick("anova1"), kinds=T)
        self.a_normality = A("Normality Tests…", "checkmark.seal", lambda: self._quick("normality"), kinds=T)
        self.a_freq = A("Frequency Distribution…", "chart.bar.xaxis", lambda: self._quick("frequency"), kinds=T)
        self.a_outliers = A("Outlier Detection…", "line.3.horizontal.decrease", lambda: self._quick("outliers"), kinds=T)
        self.a_anova2 = A("Two-way ANOVA…", "square.grid.3x2", lambda: self._quick("anova2"), kinds=T)
        self.a_multi_t = A("Multiple t Tests…", "list.number", lambda: self._quick("multiple_t"), kinds=T)
        self.a_nested = A("Nested t Test or ANOVA…", "square.stack.3d.down.right",
                          lambda: self._quick("nested"), kinds=T)
        self.a_linreg = A("Linear Regression…", "line.diagonal", lambda: self._quick("linreg"), kinds=T)
        self.a_nonlin = A("Nonlinear Regression…", "point.topleft.down.to.point.bottomright.curvepath",
                          lambda: self._quick("nonlin"), kinds=T)
        self.a_corr = A("Correlation…", "chart.dots.scatter", lambda: self._quick("correlation"), kinds=T)
        self.a_auc = A("Area Under the Curve…", "waveform.path.ecg", lambda: self._quick("auc"), kinds=T)
        self.a_transform = A("Transform…", "x.squareroot", lambda: self._quick("transform"), kinds=T)
        self.a_normalize = A("Normalize…", "percent", lambda: self._quick("normalize"), kinds=T)
        for a_ in (self.a_transform, self.a_normalize):
            self._table_types[a_] = {"xy", "column", "grouped"}
        self.a_cont = A("Chi-square or Fisher's Test…", "tablecells", lambda: self._quick("contingency"), kinds=T)
        self.a_surv = A("Survival Analysis…", "waveform.path.ecg", lambda: self._quick("survival"), kinds=T)
        self.a_frac = A("Fraction of Total…", "chart.pie", lambda: self._quick("fraction"), kinds=T)
        self._table_types[self.a_cont] = {"contingency"}
        self._table_types[self.a_surv] = {"survival"}
        self._table_types[self.a_frac] = {"parts", "column", "grouped", "contingency"}
        for a_ in (self.a_linreg, self.a_nonlin, self.a_auc):
            self._table_types[a_] = {"xy"}
        self._table_types[self.a_corr] = {"xy", "column"}
        column_only = {"column", "xy"}
        for a_ in (self.a_anova, self.a_normality, self.a_freq, self.a_outliers):
            self._table_types[a_] = column_only
        self._table_types[self.a_anova2] = {"grouped", "xy"}
        self._table_types[self.a_multi_t] = {"grouped", "xy"}
        self._table_types[self.a_nested] = {"nested"}
        analyze_later = [self.a_cont, self.a_surv, self.a_frac, self.a_nonlin, self.a_linreg, self.a_corr, self.a_auc,
                         self.a_anova, self.a_anova2, self.a_multi_t, self.a_nested,
                         self.a_normality, self.a_freq, self.a_outliers,
                         self.a_transform, self.a_normalize]
        # Graph
        self.a_fmt_graph = A("Format Graph…", "paintbrush", lambda: self.format_graph(), "Ctrl+Shift+F", "accent", kinds=G)
        self.a_axes = A("Axes…", "ruler", lambda: self.format_graph("y"), kinds=G)
        self.a_bracket = A("Show Significance", "asterisk", self._toggle_brackets, kinds=G)
        self.a_graph_type = A("Graph Type…", "square.grid.3x3.square", self.graph_type, kinds=G)
        self.a_scheme = A("Colour Scheme", "paintpalette", self.colour_scheme_menu, kinds=G)
        self.a_copy_format = A("Apply Formatting to Other Graphs…", "wand.and.rays", self.copy_formatting, kinds=G)
        self.a_legend = A("Show or Hide Legend", "list.bullet.rectangle", self._toggle_legend, kinds=G)
        self.a_function = A("Plot a Function…", "function", self.plot_function, kinds=G,
                            tip="Draw a curve from an equation on an XY graph")
        self.a_nudge = A("Nudge Data Set…", "arrow.up.and.down.and.arrow.left.and.right", self._nudge, kinds=G,
                         tip="Shift a data set sideways (or up, on XY graphs): select it and use the arrow keys")
        graph_later = [self.a_graph_type,
                       self.a_scheme, self.a_copy_format,
                       self.a_legend, self.a_nudge, self.a_function]
        # Draw (M9)
        self.draw_tools = {}
        for kind, text, icon_ in (("line", "Line", "line.diagonal"), ("arrow", "Arrow", "arrow.up.right"),
                                  ("rect", "Box", "rectangle"), ("ellipse", "Ellipse", "circle"),
                                  ("text", "Text", "textbox")):
            a = A(text, icon_, lambda on=False, k=kind: self._draw_tool(k, on), kinds=G,
                  tip=f"Draw {text.lower()} on the graph (Shift keeps lines at 45°, boxes square; Esc cancels)")
            a.setCheckable(True)
            self.draw_tools[kind] = a
        self.a_picture = A("Picture…", "photo", self.add_picture, kinds=G)
        self.a_draw_front = A("Bring to Front", "square.3.layers.3d.top.filled", lambda: self._drawing_op("front"), kinds=G)
        self.a_draw_back = A("Send to Back", "square.3.layers.3d.bottom.filled", lambda: self._drawing_op("back"), kinds=G)
        self.a_draw_align = A("Align Drawings", "align.horizontal.center", self._align_menu, kinds=G)
        draw = [*self.draw_tools.values(), self.a_picture, self.a_draw_front, self.a_draw_align]
        # Text
        self.a_bold = A("Bold", "bold", lambda: self._font(bold=None), QKeySequence.Bold, kinds=G)
        self.a_italic = A("Italic", "italic", lambda: self._font(italic=None), QKeySequence.Italic, kinds=G)
        self.a_underline = A("Underline", "underline", lambda: self._font(underline=None), QKeySequence.Underline,
                             kinds=G)
        self.a_sup = A("Superscript", "textformat.superscript", lambda: self._script("sup"), "Ctrl+Shift+=", kinds=G,
                       tip="Superscript the selected characters (while editing a text)")
        self.a_sub = A("Subscript", "textformat.subscript", lambda: self._script("sub"), "Ctrl+=", kinds=G,
                       tip="Subscript the selected characters (while editing a text)")
        self.a_symbol = A("Symbol (Greek, ±, µ…)", "character", self._symbol_menu, kinds=G)
        self.a_text_color = A("Text Colour…", "textformat.alt", self._text_colour, kinds=G)
        self.a_text_left = A("Align Left", "text.alignleft", lambda: self._align_text("left"), kinds=G)
        self.a_text_center = A("Centre", "text.aligncenter", lambda: self._align_text("center"), kinds=G)
        self.a_text_right = A("Align Right", "text.alignright", lambda: self._align_text("right"), kinds=G)
        text_later = [self.a_underline, self.a_sup, self.a_sub, self.a_symbol, self.a_text_color,
                      self.a_text_left, self.a_text_center, self.a_text_right]
        # View
        self.a_overview = A("All Graphs", "square.grid.2x2", self.show_overview, "Ctrl+Shift+G")
        self.a_tags = []
        from ..doc.model import LABEL_NAMES
        from .widgets import tag_icon
        for k in range(0, 8):
            a = QAction("No Label" if k == 0 else LABEL_NAMES[k], self)
            a.triggered.connect(lambda _c=False, k=k: self.tag_selected(k))
            # Mac: Control-digit; elsewhere Ctrl+Shift+digit (Meta is the Windows key there)
            a.setShortcut(QKeySequence(f"Meta+{k}" if sys.platform == "darwin" else f"Ctrl+Shift+{k}"))
            if k:
                a.setIcon(tag_icon(k, 14))
            self.a_tags.append(a)
        self.a_label_names = A("Label Names…", "tag", self.edit_label_names)
        self.a_toggle_sidebar = A("Show Project Sidebar", "sidebar.left", self._toggle_sidebar,
                                  "Ctrl+Meta+S" if sys.platform == "darwin" else "Ctrl+Shift+L", "muted")
        # Ctrl+Alt is AltGr on many Windows keyboards (AltGr+0 types "}"), so not there
        self.a_toggle_tools = A("Show Tools", "sidebar.right", self._toggle_tools,
                                "Ctrl+Alt+0" if sys.platform == "darwin" else "Ctrl+Shift+T", "muted")
        for a in (self.a_toggle_sidebar, self.a_toggle_tools):
            a.setCheckable(True)
            a.setChecked(True)
        self.a_help = A("ASTERISM Help", "questionmark.circle", self.open_help, "Ctrl+?")
        self.a_help_methods = A("How Results Are Calculated", "function", lambda: self.open_help_page("methods"))
        self.a_help_shortcuts = A("Keyboard Shortcuts", "keyboard", lambda: self.open_help_page("shortcuts"))
        self.a_updates = A("Check for Updates…", "arrow.counterclockwise", self.check_updates)
        self.a_about = A("About ASTERISM", "info.circle", self._about)
        self.a_about.setMenuRole(QAction.AboutRole)
        self.a_settings = A("Settings…", "gearshape", self.open_settings, "Ctrl+,")
        self.a_settings.setMenuRole(QAction.PreferencesRole)

        self.top_groups = [
            [self.a_new, self.a_open, self.a_save, self.a_undo, self.a_redo, self.a_print],
            [self.a_new_table, self.a_new_graph, self.a_new_figure, self.a_new_info,
             self.a_duplicate, self.a_delete],
            [self.a_cut, self.a_copy, self.a_paste, self.a_insert_row, self.a_delete_row,
             self.a_insert_set, self.a_delete_set, self.a_exclude, self.a_sort],
        ]
        self.export_actions = [self.a_export_pdf, self.a_export_svg, self.a_export_png, self.a_export_tiff,
                               self.a_copy_graph, self.a_export_table]
        self.tool_groups = [
            ("Analyze", self.a_analyze, [self.a_params, self.a_desc, *analyze_later]),
            ("Graph", self.a_fmt_graph, [self.a_axes, self.a_bracket, self.a_add_to_figure, *graph_later]),
            ("Figure", self.a_fig_add, [self.a_fig_text, self.a_fig_grid, self.a_fig_left, self.a_fig_top,
                                        self.a_fig_hc, self.a_fig_width, self.a_fig_front, self.a_fig_back,
                                        self.a_fig_format]),
            ("Draw", None, draw),
            ("Text", "text", None),
        ]
        self.text_actions = [self.a_bold, self.a_italic, *text_later]
        self.project.undo.changed.connect(self._undo_changed)
        self._undo_changed()

    def _make_menus(self) -> None:
        mb = self.menuBar()

        def menu(title, items):
            m = mb.addMenu(title)
            for a in items:
                if a is None:
                    m.addSeparator()
                elif isinstance(a, QMenu):
                    m.addMenu(a)
                else:
                    m.addAction(a)
            return m

        self.recent_menu = QMenu("Open Recent", self)
        self.recent_menu.aboutToShow.connect(self._fill_recent)
        menu("File", [self.a_new, self.a_open, self.recent_menu, self.a_sample, self.a_start, None, self.a_import,
                      self.a_import_settings, None, self.a_settings,
                      None, self.a_close,
                      self.a_save, self.a_save_as, self.a_revert, None, *self.export_actions,
                      None, self.a_print])
        menu("Edit", [self.a_undo, self.a_redo, None, self.a_cut, self.a_copy, self.a_paste, None,
                      self.a_insert_row, self.a_delete_row, self.a_insert_set, self.a_delete_set,
                      None, self.a_exclude, self.a_sort, self.a_transpose])
        self.tag_menu = QMenu("Colour Label", self)
        self.tag_menu.aboutToShow.connect(self._fill_tag_menu)
        menu("Sheet", [self.a_new_table, self.a_new_graph, self.a_new_figure, self.a_new_info,
                       None, self.a_table_format, self.a_import_settings, None, self.a_duplicate, self.a_delete, None,
                       self.tag_menu, None, self.a_prev, self.a_next])
        menu("Analyze", [self.a_analyze, self.a_params, None, self.a_desc, self.a_anova,
                         self.a_normality, self.a_freq, self.a_outliers, None, self.a_anova2,
                         self.a_multi_t, None, self.a_nested, None, self.a_nonlin, self.a_linreg,
                         self.a_corr, self.a_auc, None, self.a_cont, self.a_surv, self.a_frac, None,
                         self.a_transform, self.a_normalize])
        self.scheme_menu = QMenu("Colour Scheme", self)
        self.scheme_menu.aboutToShow.connect(lambda: self._fill_scheme_menu(self.scheme_menu))
        self.draw_menu = QMenu("Draw", self)
        for a in [*self.draw_tools.values(), None, self.a_picture, None, self.a_draw_front, self.a_draw_back,
                  self.a_draw_align]:
            self.draw_menu.addSeparator() if a is None else self.draw_menu.addAction(a)
        menu("Graph", [self.a_fmt_graph, self.a_graph_type, self.a_axes, self.a_bracket, self.a_legend,
                       self.a_nudge, None, self.scheme_menu,
                       self.a_copy_format, None, self.a_function, self.draw_menu, None, self.a_add_to_figure])
        menu("Figure", [self.a_fig_add, self.a_fig_text, None, self.a_fig_grid, self.a_fig_left, self.a_fig_top,
                        self.a_fig_hc, self.a_fig_width, None, self.a_fig_front, self.a_fig_back, None,
                        self.a_fig_format])
        menu("View", [self.a_overview, None, self.a_toggle_sidebar, self.a_toggle_tools])
        mb.addMenu("Window")
        menu("Help", [self.a_help, None, self.a_help_methods, self.a_help_shortcuts, None, self.a_updates,
                      self.a_about])

    def _fill_recent(self) -> None:
        self.recent_menu.clear()
        files = documents.recent_files()
        for path in files:
            act = self.recent_menu.addAction(os.path.basename(path))
            act.setToolTip(path)
            act.setEnabled(os.path.exists(path))
            act.triggered.connect(lambda _=False, p=path: open_path(p, self))
        if files:
            self.recent_menu.addSeparator()
        clear = self.recent_menu.addAction("Clear Menu", documents.clear_recent)
        clear.setEnabled(bool(files))

    # ------------------------------------------------------------------ layout

    def _make_layout(self) -> None:
        self.font_size = QComboBox()
        self.font_size.setEditable(True)
        self.font_size.addItems([str(s) for s in (6, 7, 8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 36)])
        self.font_size.setFixedWidth(74)
        self.font_size.setCurrentText("12")
        self.font_size.textActivated.connect(lambda s: self._font(size=float(s)))
        self.font_family = QFontComboBox()
        self.font_family.setMinimumWidth(0)
        self.font_family.setCurrentText("Arial")
        self.font_family.currentFontChanged.connect(lambda f: self._font(family=f.family()))
        self.text_widgets = [self.font_family, self.font_size]

        self.sidebar = ProjectSidebar(self.project)
        self.sidebar.sheetActivated.connect(self.show_sheet)
        self.sidebar.commandRequested.connect(self._command)
        self.sidebar.renameRequested.connect(lambda s, name: self.project.rename(s, name))
        self.sidebar.deleteRequested.connect(self._delete_sheet)
        self.sidebar.overviewRequested.connect(self.show_overview)
        self.sidebar.importSettingsRequested.connect(self.import_settings)
        self.sidebar.labelNamesRequested.connect(self.edit_label_names)
        self.sidebar.overview_btn.setCheckable(True)
        self.sidebar.setMinimumWidth(180)
        self.sidebar.setMaximumWidth(480)

        self.top = TopBar(self.top_groups, self.export_actions, self.a_toggle_tools)
        self.top.title.renamed.connect(self._rename_current)
        self.stack = QStackedWidget()
        self.status = StatusStrip(self.a_toggle_sidebar)
        self.status.zoom.valueChanged.connect(self._zoom_slider)
        self.status.zoom_out.clicked.connect(lambda: self.status.zoom.setValue(int(self.status.zoom.value() / 1.25)))
        self.status.zoom_in.clicked.connect(lambda: self.status.zoom.setValue(int(self.status.zoom.value() * 1.25)))
        center = QWidget()
        cv = QVBoxLayout(center)
        cv.setContentsMargins(0, 0, 0, 0)
        cv.setSpacing(0)
        cv.addWidget(self.top)
        cv.addWidget(self.stack, 1)
        cv.addWidget(self.status)

        self.tools = ToolPanel(self.tool_groups, self.text_widgets, self.text_actions)
        self.tools.setMinimumWidth(200)
        self.tools.setMaximumWidth(360)

        split = QSplitter(Qt.Horizontal)
        split.setObjectName("MainSplitter")
        split.addWidget(self.sidebar)
        split.addWidget(center)
        split.addWidget(self.tools)
        split.setChildrenCollapsible(False)
        split.setHandleWidth(5)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setStretchFactor(2, 0)
        split.setSizes([SIDEBAR_W, 1480 - SIDEBAR_W - TOOLS_W, TOOLS_W])
        self.split = split
        self.setCentralWidget(split)
        self._layout_restored = False      # restored on first show, when sizes are real
        split.splitterMoved.connect(lambda *_: self._save_layout())

    def showEvent(self, e) -> None:
        super().showEvent(e)
        if not self._layout_restored:
            self._restore_layout()
            self._layout_restored = True

    # Window size and position are remembered (saved shortly after each move or resize).
    def moveEvent(self, e) -> None:
        super().moveEvent(e)
        self._geometry_changed()

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        self._geometry_changed()

    def _geometry_changed(self) -> None:
        if not getattr(self, "_layout_restored", False):
            return
        if not hasattr(self, "_geom_timer"):
            from PySide6.QtCore import QTimer
            self._geom_timer = QTimer(self)
            self._geom_timer.setSingleShot(True)
            self._geom_timer.setInterval(400)
            self._geom_timer.timeout.connect(self._save_geometry)
        self._geom_timer.start()

    def _save_geometry(self) -> None:
        if self.isVisible() and not (self.isMinimized() or self.isFullScreen()):
            geom = self.saveGeometry()
            documents.set_value("window/geometry", geom)
            if self.path:                            # this file opens where it was left
                documents.set_file_state(self.path, geometry=bytes(geom.toBase64()).decode("ascii"),
                                         sheet=getattr(self.current, "id", None))

    def restore_file_state(self) -> bool:
        """Size, position and front sheet this file had last time; False if none."""
        from PySide6.QtCore import QByteArray
        from PySide6.QtGui import QGuiApplication
        if not self.path:
            return False
        st = documents.file_state(self.path)
        sheet = next((s for s in self._all_sheets() if s.id == st.get("sheet")), None)
        if sheet is not None:
            self.show_sheet(sheet)
        geom = st.get("geometry")
        if not geom or not self.restoreGeometry(QByteArray.fromBase64(geom.encode("ascii"))):
            return False
        g = self.geometry()
        return any(sc.availableGeometry().intersects(g) for sc in QGuiApplication.screens())

    def _restore_layout(self) -> None:
        def width(key, default, lo, hi):
            try:
                return max(lo, min(hi, int(documents.value(key, default))))
            except (TypeError, ValueError):
                return default
        left = width("window/sidebar_w", SIDEBAR_W, 180, 480)
        right = width("window/tools_w", TOOLS_W, 200, 360)
        total = max(self.width(), left + right + 400)
        self.split.setSizes([left, total - left - right, right])
        for key, act, w in (("window/sidebar", self.a_toggle_sidebar, self.sidebar),
                            ("window/tools", self.a_toggle_tools, self.tools)):
            shown = documents.value(key, True) not in (False, "false", "0", 0)
            act.setChecked(shown)
            w.setVisible(shown)

    def _save_layout(self) -> None:
        if not self._layout_restored:      # never overwrite the saved layout from an unshown window
            return
        left, _, right = self.split.sizes()
        if self.sidebar.isVisibleTo(self) and left:
            documents.set_value("window/sidebar_w", left)
        if self.tools.isVisibleTo(self) and right:
            documents.set_value("window/tools_w", right)
        documents.set_value("window/sidebar", self.sidebar.isVisibleTo(self))
        documents.set_value("window/tools", self.tools.isVisibleTo(self))

    def _toggle_sidebar(self) -> None:
        self.sidebar.setVisible(self.a_toggle_sidebar.isChecked())
        self._save_layout()

    def _toggle_tools(self) -> None:
        self.tools.setVisible(self.a_toggle_tools.isChecked())
        self._save_layout()

    # ------------------------------------------------------------------ edited state

    def display_name(self) -> str:
        if self.path:
            return os.path.splitext(os.path.basename(self.path))[0]
        return getattr(self, "suggested_name", None) or "Untitled"

    def _edited(self) -> None:
        self.setWindowTitle(f"{self.display_name()}[*]")
        self.setWindowFilePath(self.path or "")
        self.setWindowModified(self.project.is_modified())
        self.a_revert.setEnabled(bool(self.path) and self.project.is_modified())
        if self.current is not None:
            self.top.title.set_name(self.current.name)
            self.top.subtitle.setText(self._describe(self.current))

    def _undo_changed(self) -> None:
        u = self.project.undo
        self.a_undo.setEnabled(u.can_undo())
        self.a_redo.setEnabled(u.can_redo())
        self.a_undo.setText(f"Undo {u.undo_text()}" if u.can_undo() else "Undo")
        self.a_redo.setText(f"Redo {u.redo_text()}" if u.can_redo() else "Redo")

    # ------------------------------------------------------------------ files

    def open_file(self) -> None:
        start = os.path.dirname(self.path) if self.path else documents.last_dir()
        path, _ = QFileDialog.getOpenFileName(self, "Open Project", start, documents.FILE_FILTER)
        if path:
            open_path(path, self)

    # --- importing ------------------------------------------------------------------------

    OPENABLE = (".asterism", ".prism", ".pzfx", ".csv", ".tsv", ".txt", ".xlsx", ".xlsm", ".xls")

    def dragEnterEvent(self, e) -> None:
        if any(u.toLocalFile().lower().endswith(self.OPENABLE) or os.path.isdir(u.toLocalFile())
               for u in e.mimeData().urls()):
            e.acceptProposedAction()

    def dropEvent(self, e) -> None:
        sheets_like = []
        for u in e.mimeData().urls():
            path = u.toLocalFile()
            ext = os.path.splitext(path)[1].lower()
            if os.path.isdir(path) or ext in (".csv", ".tsv", ".txt", ".xlsx", ".xlsm", ".xls"):
                sheets_like.append(path)              # imported together (one export, several files)
            elif ext in self.OPENABLE:
                open_path(path, self)
        if sheets_like:
            self.import_data(sheets_like if len(sheets_like) > 1 else sheets_like[0])
        e.acceptProposedAction()

    def import_data(self, path=None) -> None:
        """One file, several files (e.g. an export written as separate CSVs) or a folder of them."""
        if not path:
            paths, _ = QFileDialog.getOpenFileNames(self, "Import Data", documents.last_dir(), documents.IMPORT_FILTER)
            if not paths:
                return
            path = paths if len(paths) > 1 else paths[0]
        if isinstance(path, (list, tuple)):
            paths = list(path)
            path = paths[0]
        else:
            paths = [path]
        documents.set_last_dir(path)
        ext = os.path.splitext(path)[1].lower() if not os.path.isdir(path) else ""
        if ext in (".prism", ".pzfx"):
            self.import_prism(path)
            return
        from .dialogs.import_data import ImportDialog
        try:
            d = ImportDialog(paths, self)
        except Exception as e:
            QMessageBox.warning(self, "Can’t Import", f"“{os.path.basename(path)}” couldn’t be read.\n\n{e}")
            return
        if not d.exec():
            return
        try:
            tables, notes = d.result()
        except Exception as e:
            QMessageBox.warning(self, "Can’t Import", str(e))
            return
        self._remember_import(d, tables, paths)
        self.add_imported(tables)
        n = len(tables)
        self.statusBar().showMessage(f"Imported {n} table{'s' if n != 1 else ''} from {os.path.basename(path)}.", 6000)

    def _imported_table(self):
        """The table the current sheet shows (a table, or a graph's / analysis's table) — no fallback."""
        s = self.current
        if isinstance(s, Table):
            return s
        return getattr(s, "table", None) if isinstance(s, (Graph, Analysis)) else None

    def _remember_import(self, dialog, tables: list, paths: list) -> None:
        """Keep the source data and the choices, so Import Settings… can change them later."""
        import datetime
        import uuid
        from ..io.sheets import to_jsonable
        sid = uuid.uuid4().hex[:12]
        self.project.imports[sid] = {"source": [os.path.basename(str(p)) for p in paths],
                                     "sheets": to_jsonable(dialog.used_sheets()), "state": dialog.state(),
                                     "when": datetime.datetime.now().isoformat(timespec="seconds")}
        for t in tables:
            t.import_ref = {"session": sid, "key": getattr(t, "import_key", t.name)}

    def import_settings(self, table=None) -> None:
        """Reopen an imported table's import window with its choices; the tables of that import
        are updated in place (analyses and graphs stay linked), as one undo step."""
        from ..doc.commands import TableEditCommand
        from ..doc.undo import Macro
        from ..io.sheets import from_jsonable
        from .dialogs.import_data import ImportDialog
        t = table if table is not None else self._imported_table()
        ref = getattr(t, "import_ref", None) if t is not None else None
        sess = self.project.imports.get(ref["session"]) if ref else None
        if sess is None:
            QMessageBox.information(self, "Import Settings", "This table wasn't imported (or its import "
                                    "settings weren't kept).")
            return
        try:
            d = ImportDialog(sess["source"] or ["import"], self, sheets=from_jsonable(sess["sheets"]))
            d.apply_state(sess["state"])
        except Exception as e:
            QMessageBox.warning(self, "Import Settings", f"The import couldn't be reopened.\n\n{e}")
            return
        d.setWindowTitle("Import Settings")
        d.ok.setText("Update")
        if not d.exec():
            return
        try:
            new_tables, _notes = d.result()
        except Exception as e:
            QMessageBox.warning(self, "Import Settings", str(e))
            return
        sid = ref["session"]
        existing = {x.import_ref["key"]: x for x in self.project.tables
                    if getattr(x, "import_ref", None) and x.import_ref.get("session") == sid}
        cmds, added = [], []
        for nt in new_tables:
            key = getattr(nt, "import_key", nt.name)
            old = existing.get(key)
            if old is None:
                nt.import_ref = {"session": sid, "key": key}
                added.append(nt)
                continue
            st = nt.state()
            cmds.append(TableEditCommand(self.project, old, lambda tbl, st=st: tbl.set_state(st),
                                         "Update Import"))
        if cmds:
            self.project.undo.push(Macro("Change Import Settings", cmds))
        if added:
            self.add_imported(added)
        sess["state"] = d.state()
        self.statusBar().showMessage(f"Updated {len(cmds)} table{'s' if len(cmds) != 1 else ''}"
                                     + (f", added {len(added)}" if added else "") + ".", 6000)

    def add_imported(self, tables: list) -> None:
        if not tables:
            return
        sheets = []
        taken = {x.name for x in self.project.tables}
        for t in tables:
            base, k = t.name, 2
            while t.name in taken:                      # keep the file's name unless it's taken
                t.name = f"{base} {k}"
                k += 1
            taken.add(t.name)
            g = self.project.new_graph(t)
            xt, yt = getattr(t, "axis_titles", (None, None)) or (None, None)
            if xt and t.table_type in ("xy", "survival"):
                g.spec.x.title = xt
            if yt:
                g.spec.y.title = yt
            for axis, fields in (getattr(t, "axis_formats", None) or {}).items():
                for k, v in fields.items():
                    setattr(getattr(g.spec, axis), k, v)
            for col, fields in (getattr(t, "dataset_styles", None) or {}).items():
                st = g.spec.style(col)
                for k, v in fields.items():
                    setattr(st, k, v)
            for k, v in (getattr(t, "graph_options", None) or {}).items():
                setattr(g.spec, k, v)
            sheets += [t, g]
            for kind, cols, params in getattr(t, "import_analyses", []) or []:
                from ..doc.model import Analysis
                sheets.append(Analysis(kind, t, cols, params))      # e.g. a standard curve's regression
        self.project.add_sheets(sheets, "Import Data")
        self.show_sheet(tables[0])

    def import_prism(self, path: str) -> None:
        from ..io.prism import into_project, read
        try:
            imp = read(path)
        except Exception as e:
            QMessageBox.warning(self, "Can’t Import", f"“{os.path.basename(path)}” couldn’t be read.\n\n{e}")
            return
        into_project(imp, self.project)
        if imp.tables:
            self.show_sheet(imp.tables[0])
        prism_report(self, path, imp)

    def open_settings(self) -> None:
        from .dialogs.settings import SettingsDialog
        SettingsDialog(self).exec()
        for w in list(_windows) or [self]:       # also after Restore Defaults
            w.apply_autosave_prefs()

    # --- autosave ---------------------------------------------------------------------

    def apply_autosave_prefs(self) -> None:
        from . import prefs
        if prefs.get("autosave.enabled"):
            self._autosave_timer.start(max(1, int(prefs.get("autosave.minutes"))) * 60_000)
        else:
            self._autosave_timer.stop()

    def autosave(self) -> bool:
        """Snapshot unsaved changes into the recovery folder (never over the project's own file)."""
        from . import recovery
        if not self.project.is_modified():
            return False
        try:
            recovery.write(self._autosave_key, self.project, self.display_name(), self.path)
        except OSError as e:
            self.flash(f"Autosave failed: {e.strerror or e}")
            return False
        return True

    def save(self) -> bool:
        if self.path is None:
            return self.save_as()
        return self.save_to(self.path)

    def save_as(self) -> bool:
        start = self.path or os.path.join(documents.last_dir(),
                                          self.display_name() + fileformat.EXTENSION)
        path, _ = QFileDialog.getSaveFileName(self, "Save Project", start, documents.FILE_FILTER)
        if not path:
            return False
        if not path.endswith(fileformat.EXTENSION):
            path += fileformat.EXTENSION
        return self.save_to(path)

    def save_to(self, path: str) -> bool:
        path = os.path.abspath(path)
        try:
            fileformat.save(self.project, path)
        except OSError as e:
            QMessageBox.critical(self, "Save Failed",
                                 f"“{os.path.basename(path)}” could not be saved.\n\n{e.strerror or e}")
            return False
        self.path = path
        self.project.mark_saved()
        from . import recovery
        recovery.clear(self._autosave_key)          # saved: the autosaved copy isn't needed
        documents.add_recent(path)
        self._save_geometry()                        # remember this window for the file
        documents.set_last_dir(path)
        self.flash(f"Saved {os.path.basename(path)}")
        self._edited()
        return True

    def revert(self) -> None:
        if not self.path or not self.project.is_modified():
            return
        box = QMessageBox(QMessageBox.Warning, "Revert to Saved",
                          f"Revert “{self.display_name()}” to the last saved version?",
                          QMessageBox.Cancel, self)
        box.setInformativeText("Your current changes will be lost.")
        revert = box.addButton("Revert", QMessageBox.DestructiveRole)
        box.exec()
        if box.clickedButton() is revert:
            self.project.mark_saved()          # don't ask again while replacing
            if open_path(self.path, self, replace=True) is None:
                self.project.touch()           # reopening failed: changes are still unsaved

    def maybe_save(self) -> bool:
        """True if the window may close (saved, discarded, or nothing to save)."""
        if not self.project.is_modified():
            return True
        box = QMessageBox(QMessageBox.Warning, APP_NAME,
                          f"Do you want to save the changes you made to “{self.display_name()}”?",
                          QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, self)
        box.setInformativeText("Your changes will be lost if you don’t save them.")
        box.button(QMessageBox.Discard).setText("Don’t Save")
        box.setDefaultButton(QMessageBox.Save)
        choice = box.exec()
        if choice == QMessageBox.Save:
            return self.save()
        return choice == QMessageBox.Discard

    def closeEvent(self, e) -> None:
        if self.maybe_save():
            from . import recovery
            recovery.clear(self._autosave_key)
            self._autosave_timer.stop()
            self._save_layout()
            self._save_geometry()
            if self in _windows:
                _windows.remove(self)
            e.accept()
        else:
            e.ignore()

    def flash(self, text: str, ms: int = 3000) -> None:
        from PySide6.QtCore import QTimer
        self.status.message.setText(text)
        QTimer.singleShot(ms, lambda: self.status.message.text() == text and self.status.message.setText(""))

    # ------------------------------------------------------------------ sheets

    def _all_sheets(self) -> list[Sheet]:
        return self.project.sheets()

    def _widget_for(self, s: Sheet) -> QWidget:
        w = self.widgets.get(id(s))
        if w is None:
            if isinstance(s, Table):
                w = DataTableSheet(s, self.project)
                w.setContextMenuPolicy(Qt.CustomContextMenu)
                w.customContextMenuRequested.connect(lambda pos, w=w: self._table_menu(w, pos))
                w.cellChanged.connect(lambda *_: self._update_status())
                w.selectionModel().selectionChanged.connect(lambda *_: self._update_status())
            elif isinstance(s, Graph):
                w = GraphSheet(s, self.project)
                w.formatGraphRequested.connect(lambda section, col: self.format_graph(section, col))
                w.formatAxesRequested.connect(lambda section: self.format_graph(section))
                w.selectionChanged.connect(self._sync_text_controls)
                w.view.zoomChanged.connect(self._zoom_changed)
                w.toolFinished.connect(self._tools_off)
            elif isinstance(s, Analysis):
                w = ResultsSheet(s)
            elif isinstance(s, InfoSheet):
                w = InfoSheetView(s)
            elif isinstance(s, FigureSheet):
                from .figure.view import FigureSheetView
                w = FigureSheetView(s, self.project)
                w.openSheetRequested.connect(self.show_sheet)
                w.editTextRequested.connect(self._edit_text_panel)
                w.view.zoomChanged.connect(self._zoom_changed)
            else:
                w = PlaceholderSheet("This sheet has no view yet.")
            self.widgets[id(s)] = w
            self.stack.addWidget(w)
        return w

    def _describe(self, s: Sheet) -> str:
        if isinstance(s, Table):
            return s.describe()
        if isinstance(s, Graph) and s.table.table_type not in GRAPHABLE_TYPES:
            from ..doc.table import TYPE_NAMES
            return f"Graph · {TYPE_NAMES[s.table.table_type]} graphs are not available yet"
        if isinstance(s, Graph):
            cols = s.spec.shown(s.table.used_columns())
            kinds = {s.spec.style(c).appearance for c in cols} or {"scatter"}
            names = dict((v, k) for k, v in APPEARANCES)
            kind = names[kinds.pop()].lower() if len(kinds) == 1 else "mixed styles"
            if s.table.table_type == "xy":
                sts = [s.spec.style(c) for c in cols]
                if sts and all(st.appearance == "bar" for st in sts):
                    kind = "XY bars"
                elif any(st.xy_show == "spaghetti" for st in sts):
                    kind = "each replicate connected"
                elif any(st.connect for st in sts):
                    kind = "points and lines" if any(st.show_points for st in sts) else "lines"
                else:
                    kind = "XY points"
                if any(a.result is not None and isinstance(getattr(a.result, "fit", None), dict)
                       and a.result.fit.get("kind") in ("line", "curve") for a in s.analyses()):
                    kind += " with fitted curve"
            elif s.table.table_type == "parts":
                kind = {"pie": "pie chart", "donut": "donut chart", "stacked100": "bar stacked to 100%",
                        "waffle": "percentage dot plot"}.get(s.spec.parts_layout, "pie chart")
            elif s.table.table_type == "multivar":
                kind = "bubble plot" if s.spec.mv.get("size") is not None else "scatter of variables"
            elif s.table.table_type == "survival":
                kind = "cumulative deaths" if s.spec.surv_death else "survival curves"
            elif s.table.table_type in ("grouped", "contingency"):
                lay = s.spec.grouped_layout
                kind = {"interleaved": f"{kind}, side by side", "separated": f"{kind}, separated",
                        "stacked": "stacked bars", "stacked_pct": "stacked bars to 100%",
                        "lines": "connected means", "heatmap": "heat map",
                        "pyramid": "bars extending both ways"}.get(lay, kind)
            elif s.table.table_type == "nested":
                kind = {"subjects": "subjects side by side", "pooled": "values coloured by subject",
                        "superplot": "SuperPlot"}.get(s.spec.nested_layout, kind)
            if s.spec.horizontal and s.table.table_type in ("column", "grouped", "contingency", "nested"):
                kind = "horizontal " + kind
            return f"Graph · {kind} · {len(cols)} data set{'s' if len(cols) != 1 else ''}"
        if isinstance(s, Analysis):
            return f"Results · from “{s.table.name}”"
        if isinstance(s, InfoSheet):
            return "Notes"
        if isinstance(s, FigureSheet):
            from ..doc.model import PAGE_SIZES
            n = len(s.panels)
            size = PAGE_SIZES.get(s.page.get("size"), ("Custom",))[0]
            return (f"Figure · {n} panel{'s' if n != 1 else ''} · {size} "
                    f"{'landscape' if s.page.get('landscape') else 'portrait'}")
        return "Figure"

    # --- all graphs at a glance, colour labels -----------------------------------------

    def _overview(self):
        if getattr(self, "overview", None) is None:
            from .overview import GraphOverview
            ov = GraphOverview(self.project, self._describe)
            ov.openRequested.connect(self.show_sheet)
            ov.deleteRequested.connect(self._delete_sheet)
            ov.addToFigureRequested.connect(self.add_graphs_to_figure)
            ov.copyFormattingRequested.connect(self._copy_format_to)
            ov.duplicateRequested.connect(self.duplicate_graph)
            ov.renameRequested.connect(self._rename_dialog)
            ov.labelNamesRequested.connect(self.edit_label_names)
            ov.selectionChanged.connect(self._overview_subtitle)
            self.stack.addWidget(ov)
            self.overview = ov
        return self.overview

    def show_overview(self) -> None:
        prev = self.stack.currentWidget()
        if isinstance(prev, GraphSheet) and prev.tool:
            prev.set_tool(None)
        self._tools_off()
        ov = self._overview()
        self.stack.setCurrentWidget(ov)
        ov.setFocus()
        self.current = None
        self.sidebar.set_current(None)
        self.sidebar.overview_btn.setChecked(True)
        self.top.title.set_name("All graphs")
        self._overview_subtitle()
        self.status.zoom_w.setVisible(False)
        self._sync_actions()
        self._update_status()

    def _overview_subtitle(self) -> None:
        ov = getattr(self, "overview", None)
        if ov is None or self.stack.currentWidget() is not ov:
            return
        n, k = ov.count(), len(ov.selected)
        self.top.subtitle.setText(f"{n} graph{'s' if n != 1 else ''} shown" + (f" · {k} selected" if k else ""))

    def tag_selected(self, k: int) -> None:
        """Colour label on the selected sheets (overview cards, sidebar rows, or the current sheet)."""
        ov = getattr(self, "overview", None)
        if ov is not None and self.stack.currentWidget() is ov:
            targets = list(ov.selected)
        else:
            sel = self.sidebar.selected_sheets()
            targets = sel if (self.current in sel or self.current is None) else [self.current]
            if not targets and self.current is not None:
                targets = [self.current]
        self.sidebar.set_tag(targets, k)

    def _fill_tag_menu(self) -> None:
        m = self.tag_menu
        m.clear()
        for k, a in enumerate(self.a_tags):
            a.setText("No Label" if k == 0 else self.project.label_name(k))
            m.addAction(a)
        m.addSeparator()
        m.addAction(self.a_label_names)

    def edit_label_names(self) -> None:
        from ..doc.commands import LabelNamesCommand
        from .dialogs.labels import LabelNamesDialog
        d = LabelNamesDialog(self.project, self)
        if d.exec() and d.names() != self.project.label_names:
            self.project.undo.push(LabelNamesCommand(self.project, d.names()))

    def add_graphs_to_figure(self, graphs: list) -> None:
        from PySide6.QtWidgets import QInputDialog
        if not graphs:
            return
        names = [f.name for f in self.project.figures] + ["New figure"]
        what = "the graph" if len(graphs) == 1 else f"the {len(graphs)} graphs"
        name, ok = QInputDialog.getItem(self, "Add to Figure", f"Add {what} to:", names, 0, False)
        if not ok:
            return
        f = self.project.add_figure() if name == "New figure" else next(x for x in self.project.figures
                                                                         if x.name == name)
        self._place_panels(f, [("graph", g.id) for g in graphs], 2)
        self.show_sheet(f)

    def _copy_format_to(self, source, targets: list) -> None:
        from ..doc.undo import Macro
        from .graph.formatting import ASPECTS, copy_formatting
        aspects = set(ASPECTS) - {"ranges"}
        cmds = [SpecCommand(t, copy_formatting(source, t, aspects), "Format") for t in targets]
        if cmds:
            self.project.undo.push(Macro(f"Apply Formatting to {len(cmds)} Graph{'s' if len(cmds) != 1 else ''}", cmds))

    def duplicate_graph(self, g) -> None:
        from ..doc.model import Graph as _G
        new = _G(f"{g.name} copy", g.home, copy.deepcopy(g.spec), source=g.source)
        self.project.add_sheets([new], "Duplicate Graph")

    def _rename_dialog(self, sheet) -> None:
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Rename", "Name:", text=sheet.name)
        if ok and name.strip() and name.strip() != sheet.name:
            self.project.rename(sheet, name.strip())

    def show_sheet(self, s: Sheet) -> None:
        self.sidebar.overview_btn.setChecked(False)
        prev = self.stack.currentWidget()
        if isinstance(prev, GraphSheet) and prev.tool:
            prev.set_tool(None)
        self._tools_off()
        w = self._widget_for(s)
        self.stack.setCurrentWidget(w)
        self.current = s
        self.sidebar.set_current(s)
        self.top.title.set_name(s.name)
        self.top.subtitle.setText(self._describe(s))
        is_graph, is_table = isinstance(s, Graph), isinstance(s, Table)
        zooms = is_graph or isinstance(s, FigureSheet)          # graphs and figures zoom
        self.status.zoom_w.setVisible(zooms)
        if zooms:
            self._zoom_changed(w.view.transform().m11())
        if is_table:
            w.setFocus()
        self._sync_actions()
        self._update_status()
        self._sync_text_controls()

    def _sync_actions(self) -> None:
        kind = self.current.kind if self.current else None
        if isinstance(self.current, Graph) and self.current.table.table_type not in GRAPHABLE_TYPES:
            kind = "graph-placeholder"          # nothing to format or export yet
        for a, kinds in self._enable_on.items():
            if a in (self.a_undo, self.a_redo):
                continue
            a.setEnabled(kinds is None or kind in kinds)
        t = self._family_table() if self.current is not None else None
        for a, types in self._table_types.items():
            a.setEnabled(a.isEnabled() and t is not None and t.table_type in types)
        for wd in self.text_widgets:
            wd.setEnabled(kind == "graph")
        self.a_revert.setEnabled(bool(self.path) and self.project.is_modified())
        ft = self._imported_table()
        ref = getattr(ft, "import_ref", None) if ft is not None else None
        self.a_import_settings.setEnabled(bool(ref) and ref.get("session") in self.project.imports)
        self._undo_changed()

    def _update_status(self) -> None:
        w = self.stack.currentWidget()
        if not isinstance(w, DataTableSheet):
            self.status.left.setText("")
            return
        i = w.currentIndex()
        key = w.key(i.column()) if i.isValid() else None
        if isinstance(key, int):
            ds, sub = w.t.split(key)
            where = column_letter(ds) + (f" · {w.t.sub_label(ds, sub)}" if w.t.width() > 1 else "")
        else:
            where = {"row": "Row titles", "x": "X", "xerr": "X error"}.get(key, "")
        text = f"Row {i.row() + 1}, {where}"
        vals = [w.t.get(ix.row(), w.key(ix.column())) for ix in w.selectedIndexes()]
        vals = [v for v in vals if isinstance(v, float)]
        if len(vals) > 1:
            text += f"   ·   Selection: n = {len(vals)}, mean = {np.mean(vals):.4g}"
        self.status.left.setText(text)

    def _structure_changed(self) -> None:
        live = {id(s) for s in self._all_sheets()}
        for k in [k for k in self.widgets if k not in live]:
            w = self.widgets.pop(k)
            self.stack.removeWidget(w)
            w.deleteLater()
        if self.current is not None and id(self.current) not in live:
            sheets = self._all_sheets()
            self.current = None
            if sheets:
                self.show_sheet(self.project.tables[0] if self.project.tables else sheets[0])
            else:
                self.top.title.set_name("")
                self.top.subtitle.setText("")
                self._sync_actions()

    def _step_sheet(self, step: int) -> None:
        sheets = self._all_sheets()
        if self.current in sheets:
            self.show_sheet(sheets[(sheets.index(self.current) + step) % len(sheets)])

    def _rename_current(self, name: str) -> None:
        if self.current is not None and name and name != self.current.name:
            self.project.rename(self.current, name)
        elif self.current is not None:
            self.top.title.set_name(self.current.name)

    def _family_table(self) -> Table | None:
        s = self.current
        if isinstance(s, Table):
            return s
        if isinstance(s, Analysis) and s.has_output():      # analyse a transform's result table
            return s.output_table()
        if isinstance(s, Graph) and s.source is not None and s.source.has_output():
            return s.source.output_table()
        return getattr(s, "table", None) or (self.project.tables[0] if self.project.tables else None)

    def _copy(self) -> None:
        """Edit › Copy: cells on tables and results, the picture on graphs and figures."""
        if isinstance(self.current, (Graph, FigureSheet)):
            self.copy_graphic()
        else:
            self._table_op("copy")

    def copy_graphic(self) -> None:
        """The graph or figure in front, as a vector picture on the clipboard (PDF on macOS,
        EMF on Windows, SVG on Linux, each with a PNG)."""
        from . import clipboard
        try:
            if isinstance(self.current, FigureSheet):
                clipboard.copy_figure(self.current, self.project)
                what = self.current.name
            else:
                g, _ = self._family_graph()
                if g is None:
                    return
                clipboard.copy_graph(g)
                what = g.name
        except Exception as e:                       # the clipboard can be locked by another app
            QMessageBox.warning(self, "Copy", f"The picture couldn't be copied: {e}")
            return
        self.flash(f"Copied “{what}”: paste it into Word, PowerPoint, Keynote or Illustrator")

    def _family_graph(self) -> tuple[Graph | None, GraphSheet | None]:
        s = self.current
        if not isinstance(s, Graph):
            t = self._family_table()
            s = next((g for g in self.project.graphs if g.home is t and g.source is None), None)
            if s is None:
                return None, None
        return s, self._widget_for(s)

    # ------------------------------------------------------------------ commands

    def _command(self, cmd: str) -> None:
        p = self.project
        if cmd == "new_table":
            self.new_table()
        elif cmd == "new_graph":
            t = self._family_table()
            if t:
                self.show_sheet(p.add_graph(t))
        elif cmd == "new_info":
            self.show_sheet(p.add_info())
        elif cmd == "new_analysis":
            self.analyze()
        elif cmd == "new_figure":
            self.show_sheet(p.add_figure())

    def analyze(self) -> None:
        t = self._family_table()
        if t is None:
            return
        dlg = AnalyzeDialog(self.project, t, self)
        if not dlg.exec() or not dlg.result:
            return
        key, table, cols = dlg.result
        from . import prefs
        from .dialogs.params import settings_dialog
        params = prefs.analysis_defaults(key)
        sd = settings_dialog(key, dict(params) or None, table, cols, self)
        if sd is not None:
            if not sd.exec():
                return
            params = {**params, **sd.params()}      # keep defaults the dialog doesn't show (α)
        a = Analysis(key, table, cols, params)
        self.project.add_analysis(a)
        self._result_graph(a)
        self.show_sheet(a)

    def _quick(self, key: str) -> None:
        """Run an analysis on every data set of the current table (settings first)."""
        t = self._family_table()
        if not t or not t.used_columns():
            return
        cols = t.used_columns()
        if key == "anova1" and len(cols) < 3:
            QMessageBox.information(self, "One-way ANOVA", "One-way ANOVA needs three or more "
                                    "data sets with values.")
            return
        if key in ("anova2", "nested") and len(cols) < 2:
            QMessageBox.information(self, "Analyze", "This analysis needs two or more data sets "
                                    "with values.")
            return
        if key == "multiple_t" and len(cols) != 2:
            self.analyze()          # let the user pick the two data sets
            return
        from . import prefs
        from .dialogs.params import settings_dialog
        params = prefs.analysis_defaults(key)
        sd = settings_dialog(key, dict(params) or None, t, cols, self)
        if sd is not None:
            if not sd.exec():
                return
            params = {**params, **sd.params()}      # keep defaults the dialog doesn't show (α)
        a = Analysis(key, t, cols, params)
        self.project.add_analysis(a)
        self._result_graph(a)
        self.show_sheet(a)

    def _result_graph(self, a: Analysis) -> None:
        """Analyses whose output is itself graphed (frequency distributions) get a graph."""
        if a.has_output() and not a.result.error and (a.analysis_type in OUTPUT_GRAPHED or
                                                      a.params.get("residual_plot") or a.params.get("qq")):
            self.project.add_sheets([self.project.new_result_graph(a)], "New Graph")

    def change_params(self) -> None:
        a = self.current
        if not isinstance(a, Analysis):
            return
        from .dialogs.params import settings_dialog
        dlg = settings_dialog(a.analysis_type, a.params, a.table, a.columns, self)
        if dlg is not None and dlg.exec():
            self.project.undo.push(ParamsCommand(a, {**a.params, **dlg.params()}))

    def format_graph(self, section: str = "style", column=None) -> None:
        g, w = self._family_graph()
        if g:
            if self.current is not g:
                self.show_sheet(g)
            FormatGraphDialog(g, self.project, section, column, w.auto_range, self).exec()

    def graph_type(self) -> None:
        from .dialogs.graph_type import GraphTypeDialog
        g, _ = self._family_graph()
        if g and g.table.table_type in GRAPHABLE_TYPES:
            if self.current is not g:
                self.show_sheet(g)
            GraphTypeDialog(g, self.project, self).exec()
            self._edited()

    def _fill_scheme_menu(self, m: QMenu) -> None:
        from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
        from .graph.formatting import SCHEMES
        m.clear()
        for key, (name, pairs) in SCHEMES.items():
            pm = QPixmap(64, 14)
            pm.fill(QColor(0, 0, 0, 0))
            p = QPainter(pm)
            for i, (fill, ink) in enumerate(pairs[:6]):
                p.fillRect(i * 10 + 1, 1, 9, 12, QColor(ink if fill.lower() in ("#ffffff",) else fill))
            p.end()
            m.addAction(QIcon(pm), name, lambda k=key: self.apply_scheme(k))

    def colour_scheme_menu(self) -> None:
        from PySide6.QtGui import QCursor
        m = QMenu(self)
        self._fill_scheme_menu(m)
        m.exec(QCursor.pos())

    def apply_scheme(self, key: str) -> None:
        g, _ = self._family_graph()
        if g is None:
            return
        from .graph.formatting import SCHEMES, apply_scheme
        cols = g.spec.shown(g.table.used_columns())
        self.project.undo.push(SpecCommand(g, apply_scheme(g.spec, key, cols), f"Colours: {SCHEMES[key][0]}"))

    def copy_formatting(self) -> None:
        g, _ = self._family_graph()
        if g is None:
            return
        from ..doc.undo import Macro
        from .dialogs.graph_type import CopyFormattingDialog
        from .graph.formatting import copy_formatting
        d = CopyFormattingDialog(g, self.project, self)
        if d.exec():
            targets, aspects = d.chosen()
            if targets and aspects:
                cmds = [SpecCommand(t, copy_formatting(g, t, aspects), "Format") for t in targets]
                self.project.undo.push(Macro(f"Apply Formatting to {len(cmds)} Graph{'s' if len(cmds) != 1 else ''}", cmds))

    def plot_function(self) -> None:
        w = self.stack.currentWidget()
        if not isinstance(w, GraphSheet):
            return
        if w.graph.table.table_type != "xy":
            QMessageBox.information(self, "Plot a Function", "Functions are plotted on graphs of XY tables.")
            return
        w.edit_function(None)

    def _toggle_legend(self) -> None:
        g, _ = self._family_graph()
        if g is None:
            return
        spec = copy.deepcopy(g.spec)
        spec.show_legend = not spec.show_legend
        self.project.undo.push(SpecCommand(g, spec, "Show Legend" if spec.show_legend else "Hide Legend"))

    def _nudge(self) -> None:
        w = self.stack.currentWidget()
        if not isinstance(w, GraphSheet):
            return
        cols = [e.meta["column"] for e in w.selected_elements() if e.kind in ("dataset", "curve")]
        self.format_graph("style", cols[0] if cols else None)

    def _toggle_brackets(self) -> None:
        g, _ = self._family_graph()
        if g:
            spec = copy.deepcopy(g.spec)
            spec.show_brackets = not spec.show_brackets
            self.project.undo.push(SpecCommand(g, spec, "Significance"))

    def export(self, fmt: str) -> None:
        filt = {"pdf": "PDF (*.pdf)", "svg": "SVG (*.svg)", "png": "PNG image (*.png)",
                "tiff": "TIFF image (*.tif *.tiff)"}[fmt]
        if isinstance(self.current, FigureSheet):
            from .figure import export as fexport
            f = self.current
            start = os.path.join(os.path.dirname(self.path) if self.path else documents.last_dir(),
                                 f"{f.name}.{'tif' if fmt == 'tiff' else fmt}")
            path, _ = QFileDialog.getSaveFileName(self, f"Export {fmt.upper()}", start, filt)
            if not path:
                return
            if fmt == "pdf":
                fexport.export_pdf(f, self.project, path)
            elif fmt == "svg":
                fexport.export_svg(f, self.project, path)
            else:
                fexport.export_image(f, self.project, path, int(prefs.get("export.dpi")))
            self.flash(f"Exported {os.path.basename(path)}")
            return
        g, _ = self._family_graph()
        if not g:
            return
        start = os.path.join(os.path.dirname(self.path) if self.path else documents.last_dir(),
                             f"{g.name}.{fmt}")
        path, _ = QFileDialog.getSaveFileName(self, f"Export {fmt.upper()}", start, filt)
        if not path:
            return
        if fmt in ("png", "tiff"):                    # same raster path; the extension picks TIFF
            gexport.export_png(g, path, int(prefs.get("export.dpi")))
        else:
            {"pdf": gexport.export_pdf, "svg": gexport.export_svg}[fmt](g, path)
        self.flash(f"Exported {os.path.basename(path)}")

    # ------------------------------------------------------------------ figures

    def _figure_view(self):
        from .figure.view import FigureSheetView
        w = self.stack.currentWidget()
        return w if isinstance(w, FigureSheetView) else None

    def _figure_op(self, name: str, *args) -> None:
        v = self._figure_view()
        if v is not None:
            getattr(v, name)(*args)

    def _place_panels(self, figure, items: list[tuple[str, str]], columns: int = 2) -> None:
        """Add panels below what is already on the page, `columns` to a row."""
        import copy as _copy
        from ..doc.commands import FigureCommand
        from .figure.layout import build_figure
        st = _copy.deepcopy(figure.state())
        _, els = build_figure(figure, self.project)
        from .graph.canvas import MM
        bottom = max([e.rect.bottom() / MM for e in els if e.kind != "letter"] + [5.0])
        new = []
        for kind, ref in items:
            pn = figure.new_panel(kind, ref, font_size=8.0 if kind in ("table", "results") else 10.0)
            new.append(pn)
        tmp = FigureSheet()                       # measure the new panels at their own size
        tmp.page = dict(figure.page)
        tmp.panels = new
        _, nels = build_figure(tmp, self.project)
        sizes = {e.panel: (e.rect.width() / MM, e.rect.height() / MM) for e in nels if e.kind != "letter"}
        pw, _ = figure.page_mm()
        margin, gap = 15.0, 10.0
        y = bottom + gap if figure.panels else margin
        for i in range(0, len(new), columns):
            row = new[i:i + columns]
            x = margin
            for pn in row:
                w, h = sizes.get(pn["id"], (60.0, 40.0))
                avail = (pw - 2 * margin - gap * (len(row) - 1)) / len(row)
                if pn["kind"] in ("graph", "table", "results") and w > avail:
                    pn["scale"] = round(avail / w, 3)       # shrink to fit the row
                    w, h = avail, h * pn["scale"]
                pn["x"], pn["y"] = round(x, 1), round(y, 1)
                x += w + gap
            y += max(sizes.get(pn["id"], (0, 40.0))[1] * pn.get("scale", 1.0) for pn in row) + gap
        st["panels"] += new
        self.project.undo.push(FigureCommand(figure, st, "Add to Figure"))

    def figure_add(self) -> None:
        if not isinstance(self.current, FigureSheet):
            return
        from .dialogs.figure import AddPanelsDialog
        d = AddPanelsDialog(self.project, parent=self)
        if d.exec() and d.chosen():
            self._place_panels(self.current, d.chosen(), d.columns.value())

    def figure_add_text(self) -> None:
        if not isinstance(self.current, FigureSheet):
            return
        import copy as _copy
        from ..doc.commands import FigureCommand
        from .dialogs.figure import TextPanelDialog
        d = TextPanelDialog("Figure 1. ", 10.0, self)
        if d.exec():
            text, size = d.values()
            st = _copy.deepcopy(self.current.state())
            pw, ph = self.current.page_mm()
            st["panels"].append(self.current.new_panel("text", "", x=15.0, y=ph - 40.0, w=pw - 30.0, h=15.0,
                                                       text=text, font_size=size))
            self.project.undo.push(FigureCommand(self.current, st, "Add Text"))

    def _edit_text_panel(self, pid: str) -> None:
        f = self.current
        if not isinstance(f, FigureSheet):
            return
        import copy as _copy
        from ..doc.commands import FigureCommand
        from .dialogs.figure import TextPanelDialog
        pn = next((p for p in f.panels if p["id"] == pid), None)
        if pn is None:
            return
        d = TextPanelDialog(pn.get("text", ""), pn.get("font_size", 10.0), self)
        if d.exec():
            st = _copy.deepcopy(f.state())
            q = next(p for p in st["panels"] if p["id"] == pid)
            q["text"], q["font_size"] = d.values()
            self.project.undo.push(FigureCommand(f, st, "Edit Text"))

    def figure_grid(self) -> None:
        v = self._figure_view()
        if v is None:
            return
        from PySide6.QtWidgets import QInputDialog
        n, ok = QInputDialog.getInt(self, "Arrange in a Grid", "Panels per row:", 2, 1, 6)
        if ok:
            v.arrange_grid(n)

    def figure_format(self) -> None:
        f = self.current
        if not isinstance(f, FigureSheet):
            return
        import copy as _copy
        from ..doc.commands import FigureCommand
        from .dialogs.figure import FormatFigureDialog
        d = FormatFigureDialog(f, self)
        if d.exec():
            st = _copy.deepcopy(f.state())
            st["page"].update(d.page())
            self.project.undo.push(FigureCommand(f, st, "Format Figure"))

    def add_graph_to_figure(self) -> None:
        g, _ = self._family_graph()
        if g is None:
            return
        from PySide6.QtWidgets import QInputDialog
        names = [f.name for f in self.project.figures] + ["New figure"]
        name, ok = QInputDialog.getItem(self, "Add to Figure", "Add the graph to:", names, 0, False)
        if not ok:
            return
        if name == "New figure":
            f = self.project.add_figure()
        else:
            f = next(x for x in self.project.figures if x.name == name)
        self._place_panels(f, [("graph", g.id)], 2)
        self.show_sheet(f)

    def _delete_sheet(self, s: Sheet | None = None) -> None:
        s = s if isinstance(s, Sheet) else self.current
        if s is None:
            return
        extra = ""
        if isinstance(s, Table):
            n = len(self.project.family(s)) - 1
            extra = f" This also deletes its {n} linked sheet{'s' if n != 1 else ''}." if n else ""
        box = QMessageBox(QMessageBox.Warning, "Delete Sheet", f"Delete “{s.name}”?",
                          QMessageBox.Cancel, self)
        box.setInformativeText(f"You can undo this.{extra}")
        delete = box.addButton("Delete", QMessageBox.DestructiveRole)
        box.exec()
        if box.clickedButton() is delete:
            self.project.delete(s)

    def _table_op(self, op: str) -> None:
        w = self.stack.currentWidget()
        if isinstance(w, DataTableSheet):
            if op == "cut":
                w.copy()
                w.clear_selection()
            else:
                getattr(w, op)()

    def new_table(self) -> None:
        from .dialogs.new_table import NewTableDialog
        dlg = NewTableDialog(self)
        if dlg.exec():
            tt, fmt, example = dlg.choice()
            self.show_sheet(self.project.add_table(table_type=tt, example=example, **fmt))

    def show_start_screen(self) -> None:
        """At launch: choose the first table's type (Cancel keeps an empty Column table)."""
        from .dialogs.new_table import NewTableDialog
        dlg = NewTableDialog(self, start=True)
        if dlg.exec() and self.project.is_pristine():
            tt, fmt, example = dlg.choice()
            p = self.project
            for sheet in list(p.sheets()):
                p.take(sheet)
            t = p.new_table(None, tt, **fmt)
            if example:
                from ..doc.table import fill_example
                fill_example(t)
            p.insert(t)
            p.insert(p.new_graph(t))
            p.undo.clear()
            p.mark_saved()
            self.show_sheet(t)

    def table_format(self) -> None:
        from ..doc.commands import TableEditCommand
        from .dialogs.new_table import TableFormatDialog
        t = self.current
        if not isinstance(t, Table):
            return
        dlg = TableFormatDialog(t, self)
        if dlg.exec():
            vals = dlg.values()
            self.project.undo.push(TableEditCommand(self.project, t, lambda tb: tb.reformat(**vals),
                                                    "Change Table Format"))
            self._edited()

    def _table_menu(self, w: DataTableSheet, pos) -> None:
        m = QMenu(self)
        for a in (self.a_cut, self.a_copy, self.a_paste, None, self.a_insert_row, self.a_delete_row,
                  self.a_insert_set, self.a_delete_set, None, self.a_exclude, None,
                  self.a_table_format):
            m.addSeparator() if a is None else m.addAction(a)
        m.exec(w.viewport().mapToGlobal(pos))

    # --- drawing on graphs -----------------------------------------------------------

    def _draw_tool(self, kind: str, on: bool) -> None:
        w = self.stack.currentWidget()
        for k, a in self.draw_tools.items():
            if k != kind:
                a.setChecked(False)
        if isinstance(w, GraphSheet):
            w.set_tool(kind if on else None)
            w.view.setFocus()

    def _tools_off(self) -> None:
        for a in self.draw_tools.values():
            a.setChecked(False)

    def add_picture(self) -> None:
        w = self.stack.currentWidget()
        if not isinstance(w, GraphSheet):
            return
        from PySide6.QtWidgets import QFileDialog
        from .graph.drawings import image_drawing
        path, _ = QFileDialog.getOpenFileName(self, "Add Picture", "", "Images (*.png *.jpg *.jpeg *.tif *.tiff *.bmp *.gif)")
        if not path:
            return
        c = w.plot_center()
        d = image_drawing(path, c.x() - 60, c.y() - 40)
        if d is None:
            QMessageBox.warning(self, "Add Picture", "That file couldn't be read as an image.")
            return
        w.add_drawing(d, "Add Picture")

    def _drawing_op(self, op: str) -> None:
        w = self.stack.currentWidget()
        if isinstance(w, GraphSheet):
            w.restack_drawings(op == "front")

    def _align_menu(self) -> None:
        w = self.stack.currentWidget()
        if not isinstance(w, GraphSheet):
            return
        from PySide6.QtGui import QCursor
        from .graph.view import ALIGN
        m = QMenu(self)
        enough = len(w.selected_drawings()) > 1
        for key, text in ALIGN:
            a = m.addAction(text, lambda k=key: w.align_drawings(k))
            a.setEnabled(enough)
        if not enough:
            m.addSeparator()
            m.addAction("Select two or more drawings first").setEnabled(False)
        m.exec(QCursor.pos())

    def _font(self, **changes) -> None:
        w = self.stack.currentWidget()
        if not isinstance(w, GraphSheet):
            return
        fs = w.current_font()
        for k in ("bold", "italic", "underline"):
            if k in changes and changes[k] is None:
                changes[k] = not getattr(fs, k, False)
        w.apply_font(**changes)

    def _script(self, kind: str) -> None:
        w = self.stack.currentWidget()
        if isinstance(w, GraphSheet) and not w.script_selection(kind):
            self.statusBar().showMessage("Double-click a text, select characters, then choose "
                                         + ("Superscript." if kind == "sup" else "Subscript."), 4000)

    def _symbol_menu(self) -> None:
        w = self.stack.currentWidget()
        if not isinstance(w, GraphSheet):
            return
        from PySide6.QtGui import QCursor
        from .graph.drawings import SYMBOLS
        editor_open = w._editing is not None
        m = QMenu(self)
        for title, chars in SYMBOLS:
            sm = m.addMenu(title)
            for ch in chars.split():
                sm.addAction(ch, lambda c=ch: w.insert_text(c) or self.statusBar().showMessage(
                    "Select a text on the graph first.", 4000))
        m.exec(QCursor.pos())
        if editor_open and w._editing:
            w._editing[0].setFocus()

    def _text_colour(self) -> None:
        w = self.stack.currentWidget()
        if not isinstance(w, GraphSheet):
            return
        from PySide6.QtGui import QColor
        from PySide6.QtWidgets import QColorDialog
        fs = w.current_font()
        c = QColorDialog.getColor(QColor(getattr(fs, "color", "") or "#000000"), self, "Text Colour")
        if c.isValid():
            w.apply_font(color=c.name())

    def _align_text(self, how: str) -> None:
        w = self.stack.currentWidget()
        if isinstance(w, GraphSheet):
            w.align_text(how)

    def _sync_text_controls(self) -> None:
        w = self.stack.currentWidget()
        if not isinstance(w, GraphSheet):
            return
        fs = w.current_font()
        for wd in self.text_widgets:
            wd.blockSignals(True)
        self.font_size.setCurrentText(f"{fs.size:g}")
        self.font_family.setCurrentText(fs.family)
        for wd in self.text_widgets:
            wd.blockSignals(False)

    def _zoom_slider(self, v: int) -> None:
        w = self.stack.currentWidget()
        if isinstance(w, GraphSheet) or hasattr(w, "fit_page"):
            w.set_zoom(v / 100)

    def _zoom_changed(self, z: float) -> None:
        self.status.zoom.blockSignals(True)
        self.status.zoom.setValue(int(round(z * 100)))
        self.status.zoom.blockSignals(False)
        self.status.zoom_label.setText(f"{z * 100:.0f}%")

    def check_updates(self) -> None:
        from . import updates
        updates.check(self)

    def open_help(self) -> None:
        """Help opens where you are: the page for the kind of sheet in front."""
        from .help_window import show_page
        show_page(self._help_context())

    def open_help_page(self, slug: str) -> None:
        from .help_window import show_page
        show_page(slug)

    def _help_context(self) -> str:
        from ..doc.model import Analysis, Graph
        sh = getattr(self, "current", None)
        name = type(sh).__name__
        if isinstance(sh, Graph):
            return "graphs"
        if isinstance(sh, Analysis):
            return "analyses"
        return {"Table": "tables", "FigureSheet": "figures"}.get(name, "start")

    def _about(self) -> None:
        from asterism import __version__
        QMessageBox.about(self, APP_NAME, f"<b>{APP_NAME}</b> {__version__}"
                          "<p>Scientific graphing and statistics.</p>")


# ---------------------------------------------------------------------------
# Window management (one window per project)
# ---------------------------------------------------------------------------

def windows() -> list[MainWindow]:
    return list(_windows)


def _place(w: MainWindow) -> None:
    """Where a new window goes: offset from the frontmost window, else where the last
    window was (saved size and position), else a default size centred on the screen."""
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QGuiApplication
    others = [x for x in _windows if x.isVisible()]
    if others:
        g = others[-1].geometry().translated(28, 28)
        scr = QGuiApplication.screenAt(g.center()) or QGuiApplication.primaryScreen()
        if scr is not None and not scr.availableGeometry().contains(g):
            a = scr.availableGeometry()            # ran off the screen: start again top-left
            g.moveTopLeft(a.topLeft() + QPoint(20, 20))
            if not a.contains(g):
                g.moveTopLeft(a.topLeft())
            if not a.contains(g):
                g = g.intersected(a)               # bigger than the screen: shrink to fit
        w.setGeometry(g)
        return
    saved = documents.value("window/geometry")
    if saved is not None and w.restoreGeometry(saved):
        g = w.geometry()
        if any(s.availableGeometry().intersects(g) for s in QGuiApplication.screens()):
            return
    w.resize(1480, 920)
    scr = QGuiApplication.primaryScreen()
    if scr is not None:
        a = scr.availableGeometry()
        w.resize(min(1480, a.width() - 40), min(920, a.height() - 40))
        w.move(a.center() - w.rect().center())


def _show(w: MainWindow, origin: MainWindow | None = None, replace: bool = False) -> MainWindow:
    reuse = origin is not None and (replace or (origin.path is None and origin.project.is_pristine()))
    if w.restore_file_state():
        pass                                         # a file reopens at its own size and place
    elif reuse:
        w.setGeometry(origin.geometry())
    else:
        _place(w)
    _windows.append(w)
    w.show()
    w.raise_()
    w.activateWindow()
    if reuse:
        origin.close()
    return w


def new_window(project: Project | None = None) -> MainWindow:
    return _show(MainWindow(project))


def open_sample(origin: MainWindow | None = None) -> MainWindow:
    return _show(MainWindow(sample_project(engine)), origin if isinstance(origin, MainWindow) else None)


def run_start(origin: MainWindow | None = None) -> MainWindow | None:
    """The Start window: new project (choose the first table), empty project, open a file
    or the sample. Closing it starts an empty project. A file that fails to open brings the
    Start window back."""
    from .dialogs.start import StartDialog
    while True:
        dlg = StartDialog(origin)
        dlg.exec()
        kind, *rest = dlg.result_choice()
        if kind == "open":
            w = open_path(rest[0], origin)
            if w is None:
                continue
            return w
        if kind == "sample":
            return open_sample(origin)
        if kind == "import":
            paths = rest[0]
            if len(paths) == 1 and os.path.splitext(paths[0])[1].lower() in (".prism", ".pzfx"):
                w = open_prism(paths[0], origin)
                if w is None:
                    continue
                return w
            reuse = origin is not None and origin.path is None and origin.project.is_pristine()
            w = origin if reuse else new_window()
            w.import_data(paths if len(paths) > 1 else paths[0])
            if not w.project.tables and not reuse:        # nothing imported: back to the Start window
                w.project.mark_saved()
                w.close()
                continue
            return w
        reuse = origin is not None and origin.path is None and origin.project.is_pristine()
        w = origin if reuse else new_window()
        if kind == "new":
            w.show_start_screen()
        return w


def offer_recovery(origin: MainWindow | None = None) -> list[MainWindow]:
    """At launch: projects whose changes weren't saved last time can be restored."""
    from . import recovery
    from .dialogs.recovery import RecoveryDialog
    snaps = recovery.pending()
    if not snaps:
        return []
    d = RecoveryDialog(snaps, origin)
    restored = []
    if d.exec():
        for snap in d.chosen():
            try:
                project = recovery.load(snap, engine)
            except Exception as e:
                QMessageBox.warning(origin, "Can’t Restore", f"“{snap.name}” couldn’t be restored.\n\n{e}")
                continue
            project.touch()                         # restored changes are unsaved changes
            path = snap.original if snap.original and os.path.exists(os.path.dirname(snap.original)) else None
            w = MainWindow(project, path)
            if path is None:
                w.suggested_name = f"{snap.name} (recovered)"
            w._edited()
            restored.append(_show(w, None))
            recovery.clear(snap.key)                 # the new window autosaves under its own name
        # snapshots not ticked are kept for next time
    elif d.discarded:
        for snap in snaps:
            recovery.clear(snap.key)
    return restored


def prism_report(parent, path: str, imp) -> None:
    """What came across from a Prism file, and what didn't (never dropped silently)."""
    n_t, n_a, n_g = len(imp.tables), len(imp.analyses), len(imp.graphs)
    parts = [f"{n_t} data table{'s' if n_t != 1 else ''}", f"{n_a} analys{'is' if n_a == 1 else 'es'}"]
    if n_g:
        parts.append(f"{n_g} graph{'s' if n_g != 1 else ''} with their formatting")
    box = QMessageBox(QMessageBox.Information, "Prism File Imported",
                      f"From “{os.path.basename(path)}”: " + ", ".join(parts[:-1]) + " and " + parts[-1] + ".",
                      QMessageBox.Ok, parent)
    if imp.notes:
        box.setInformativeText("Not carried over:\n• " + "\n• ".join(imp.notes))
    else:
        box.setInformativeText("Everything came across.")
    if parent is not None and not os.environ.get("ASTERISM_NO_MODAL"):
        box.exec()


def open_prism(path: str, origin: MainWindow | None = None) -> MainWindow | None:
    """A Prism file opens as a new, unsaved ASTERISM project."""
    from ..io.prism import into_project, read
    try:
        imp = read(path)
    except Exception as e:
        QMessageBox.warning(origin, "Can’t Open", f"“{os.path.basename(path)}” couldn’t be read.\n\n{e}")
        return None
    project = Project(engine)
    into_project(imp, project)
    project.undo.clear()
    project.mark_saved()
    w = MainWindow(project)
    w.suggested_name = os.path.splitext(os.path.basename(path))[0]
    w._edited()
    documents.set_last_dir(path)
    shown = _show(w, origin)
    prism_report(shown, path, imp)
    return shown


def open_path(path: str, origin: MainWindow | None = None, replace: bool = False) -> MainWindow | None:
    """Open a project file in its own window (or bring its window forward)."""
    path = os.path.abspath(path)
    ext = os.path.splitext(path)[1].lower()
    if ext in (".prism", ".pzfx"):
        return open_prism(path, origin)
    if ext in (".csv", ".tsv", ".txt", ".xlsx", ".xlsm", ".xls"):
        w = origin if isinstance(origin, MainWindow) else new_window()
        w.import_data(path)
        return w
    if not replace:
        for w in _windows:
            if w.path and os.path.exists(w.path) and os.path.samefile(w.path, path):
                w.raise_()
                w.activateWindow()
                return w
    name = os.path.basename(path)
    try:
        project = fileformat.load(path, engine)
    except fileformat.ProjectFileError as e:
        QMessageBox.warning(origin, "Can’t Open Project", f"“{name}” couldn’t be opened.\n\n{e}")
        return None
    except OSError as e:
        documents.remove_recent(path)
        QMessageBox.warning(origin, "Can’t Open Project",
                            f"“{name}” couldn’t be opened.\n\n{e.strerror or e}")
        return None
    documents.add_recent(path)
    documents.set_last_dir(path)
    return _show(MainWindow(project, path), origin, replace)
