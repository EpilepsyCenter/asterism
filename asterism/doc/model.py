"""Project model: data tables, info sheets, analyses, graphs, figures (no Qt).

Live linking is Prism's core promise: edit a table and its analyses recompute and
its graphs rebuild. Sheets wire themselves to their table when they are attached
to a project and unwire when removed, so a deleted sheet (kept alive by the undo
stack) stops listening until it is restored.

User actions go through the undoable `Project` methods (`add_table`, `delete`,
`rename`, …). `insert` / `take` are the low-level, non-undoable primitives used by
commands, file loading and sample projects.
"""

from __future__ import annotations

import uuid
from typing import Protocol

from .events import Signal
from .spec import GraphSpec
from .table import DataTable, column_letter  # noqa: F401  (column_letter re-exported)
from .undo import UndoStack


class AnalysisEngine(Protocol):
    """What the model needs from `asterism.analysis` (injected; keeps doc UI- and stats-free)."""

    def run(self, analysis: "Analysis"): ...
    def title(self, analysis: "Analysis") -> str: ...


# ---------------------------------------------------------------------------
# Sheets
# ---------------------------------------------------------------------------

# Functions called on every new graph (the app installs one that applies the user's settings).
NEW_GRAPH_HOOKS: list = []

# Colour labels (like Finder tags): 0 = none, 1–7; projects may rename them.
LABEL_NAMES = {1: "Red", 2: "Orange", 3: "Yellow", 4: "Green", 5: "Blue", 6: "Purple", 7: "Grey"}


class Sheet:
    kind = "sheet"

    def __init__(self, name: str = "", id: str | None = None):
        self.id = id or uuid.uuid4().hex
        self._name = name
        self._tag = 0
        self.auto_name = False       # name follows its table / analysis type
        self.project: Project | None = None
        self.renamed = Signal()      # name or colour label changed

    @property
    def tag(self) -> int:
        """Colour label (0 = none, 1–7)."""
        return self._tag

    @tag.setter
    def tag(self, v: int) -> None:
        v = int(v or 0)
        if v != self._tag:
            self._tag = v
            self.renamed.emit()

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, v: str) -> None:
        if v != self._name:
            self._name = v
            self.renamed.emit()

    def attach(self, project: "Project") -> None:
        self.project = project

    def detach(self) -> None:
        self.project = None

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.name!r}>"


class Table(Sheet, DataTable):
    """A data table sheet: one of Prism's eight table types (see table.py)."""

    kind = "table"

    def __init__(self, name: str = "", table_type: str = "column", y_format: str = "single",
                 replicates: int = 3, x_format: str | None = None, row_titles: bool | None = None,
                 ncols: int | None = None, id: str | None = None):
        Sheet.__init__(self, name, id)
        self._init_table(table_type, y_format, replicates, x_format, row_titles, ncols)


INFO_FIELDS = ("Experiment Date", "Experiment ID", "Notebook Reference", "Project",
               "Experimenter", "Protocol")


class InfoSheet(Sheet):
    kind = "info"

    def __init__(self, name: str = "", id: str | None = None):
        super().__init__(name, id)
        self.fields = {k: "" for k in INFO_FIELDS}
        self.notes = ""
        self.changed = Signal()      # a field or the notes changed (also by undo)


PAGE_SIZES = {"a4": ("A4", 210.0, 297.0), "letter": ("US Letter", 215.9, 279.4),
              "a5": ("A5", 148.0, 210.0), "custom": ("Custom", None, None)}
LETTER_STYLES = {"A": "A, B, C", "a": "a, b, c", "(A)": "(A), (B), (C)", "A.": "A., B., C.",
                 "(a)": "(a), (b), (c)"}


class FigureSheet(Sheet):
    """A figure (Prism calls these layouts): a page of panels — graphs, data or result
    tables, and text. Positions in millimetres from the page's top-left corner. Graphs and
    tables are drawn at their own size times `scale`; text boxes have a width and height.
    Panels refer to sheets by id, so they stay live."""

    kind = "figure"

    def __init__(self, name: str = "", id: str | None = None):
        super().__init__(name, id)
        self.page = {"size": "a4", "width": 210.0, "height": 297.0, "landscape": False,
                     "letters": True, "letter_style": "A", "letter_size": 14.0, "letter_bold": True,
                     "letter_font": "Arial", "letter_pos": "outside", "grid": 5.0, "snap": True}
        self.panels: list[dict] = []
        self.changed = Signal()

    # each panel: {"id", "kind": graph|table|results|text, "ref", "x", "y", "scale", "w", "h",
    #              "text", "font_size", "label": None (automatic) | "" (none) | custom}

    def page_mm(self) -> tuple[float, float]:
        w, h = self.page["width"], self.page["height"]
        return (h, w) if self.page["landscape"] else (w, h)

    def state(self) -> dict:
        return {"page": dict(self.page), "panels": [dict(p) for p in self.panels]}

    def set_state(self, st: dict) -> None:
        self.page = dict(st["page"])
        self.panels = [dict(p) for p in st["panels"]]
        self.changed.emit()

    def new_panel(self, kind: str, ref: str = "", **kw) -> dict:
        p = {"id": uuid.uuid4().hex[:8], "kind": kind, "ref": ref, "x": 20.0, "y": 20.0, "scale": 1.0,
             "w": 60.0, "h": 15.0, "text": "", "font_size": 10.0, "label": None}
        p.update(kw)
        return p


class Graph(Sheet):
    kind = "graph"

    def __init__(self, name: str, table: Table, spec: GraphSpec | None = None,
                 id: str | None = None, source: "Analysis | None" = None):
        super().__init__(name, id)
        self.home = table                  # the data table whose family the graph belongs to
        self.source = source               # set: the graph plots this analysis's results table
        self.spec = spec or GraphSpec()
        self.changed = Signal()

    @property
    def table(self):
        """What the graph plots: its data table, or its analysis's results table."""
        if self.source is not None:
            return self.source.result_table()
        return self.home

    def attach(self, project: "Project") -> None:
        super().attach(project)
        self.home.changed.connect(self.changed)
        self.home.renamed.connect(self._follow_table)
        project.analysis_changed.connect(self._analysis_changed)
        self.changed.emit()

    def detach(self) -> None:
        if self.project is not None:
            self.project.analysis_changed.disconnect(self._analysis_changed)
        self.home.changed.disconnect(self.changed)
        self.home.renamed.disconnect(self._follow_table)
        super().detach()

    def _follow_table(self) -> None:
        if self.auto_name:
            self.name = self.source.name if self.source is not None else self.home.name

    def _analysis_changed(self, a: "Analysis") -> None:
        target = getattr(self.source, "_output", None) if self.source is not None else self.home
        if a is self.source or a.table is target:
            self.changed.emit()

    def set_spec(self, spec: GraphSpec) -> None:
        self.spec = spec
        self.changed.emit()

    def analyses(self) -> list["Analysis"]:
        """Analyses of what the graph plots (its data table, or its analysis's result table),
        for curves and significance brackets."""
        if self.project is None:
            return []
        target = self.source.output_table() if self.source is not None else self.home
        return [a for a in self.project.analyses if a.table is target]


class Analysis(Sheet):
    kind = "analysis"

    def __init__(self, analysis_type: str, table: Table, columns: list[int],
                 params: dict | None = None, id: str | None = None, name: str = ""):
        super().__init__(name, id)
        self.analysis_type = analysis_type     # "ttest" | "descriptive"
        self.table = table
        self.columns = list(columns)
        self.params = dict(params or {})
        self.result = None                     # derived; never saved
        self.auto_name = not name
        self.changed = Signal()

    def attach(self, project: "Project") -> None:
        super().attach(project)
        self.table.changed.connect(self.recompute)
        self.table.renamed.connect(self._auto_rename)
        self.recompute()

    def detach(self) -> None:
        self.table.changed.disconnect(self.recompute)
        self.table.renamed.disconnect(self._auto_rename)
        project = self.project
        super().detach()
        if project is not None:
            project.analysis_changed.emit(self)

    def set_params(self, params: dict) -> None:
        self.params = dict(params)
        self.recompute()

    # --- output table (transforms, frequency distributions …) ----------------------------
    # An analysis whose result includes a table (result.out_table) owns one persistent
    # output Table, refreshed in place on every recompute, so graphs and further analyses
    # that use it stay live. Its id is "<analysis id>.out" (how files refer to it).

    def has_output(self) -> bool:
        return self.result is not None and getattr(self.result, "out_table", None) is not None

    def output_table(self) -> "Table":
        if getattr(self, "_output", None) is None:
            t = Table(self.name, "column", id=f"{self.id}.out")
            t.source_analysis = self
            self._output = t
            self._refresh_output(emit=False)
        return self._output

    def result_table(self) -> "Table":          # older name
        return self.output_table()

    def _refresh_output(self, emit: bool = True) -> None:
        out = getattr(self, "_output", None)
        if out is None:
            return
        src = getattr(self.result, "out_table", None) if self.result is not None else None
        if src is None:
            src = Table("", "column")
        out.set_state(src.state(), emit=False)
        for attr in ("bin_width", "cumulative"):
            setattr(out, attr, getattr(src, attr, None))
        out.name = self.name
        if emit:
            out.changed.emit()

    def _auto_rename(self) -> None:
        engine = self.project.engine if self.project else None
        if self.auto_name and engine is not None:
            self.name = f"{engine.title(self)} of {self.table.name}"

    def recompute(self) -> None:
        engine = self.project.engine if self.project else None
        self._auto_rename()
        self.result = engine.run(self) if engine is not None else None
        self._refresh_output()
        self.changed.emit()
        if self.project is not None:
            self.project.analysis_changed.emit(self)


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------

SECTION_OF = {"table": "tables", "info": "infos", "analysis": "analyses", "graph": "graphs",
              "figure": "figures"}


class Project:
    def __init__(self, engine: AnalysisEngine | None = None):
        self.tables: list[Table] = []
        self.infos: list[InfoSheet] = []
        self.analyses: list[Analysis] = []
        self.graphs: list[Graph] = []
        self.figures: list[FigureSheet] = []
        self.engine = engine
        self.undo = UndoStack()
        self._touched = False
        self.label_names: dict[int, str] = {}  # the project's own names for colour labels
        # imports whose settings can be changed later: id → {"source", "sheets", "state", "when"}
        self.imports: dict[str, dict] = {}
        self.structure_changed = Signal()     # sheets added / removed / reordered
        self.analysis_changed = Signal()      # (analysis) recomputed or removed
        self.edited = Signal()                # modified state may have changed
        self.undo.changed.connect(self.edited)

    # --- modified state --------------------------------------------------------

    def is_modified(self) -> bool:
        return self._touched or not self.undo.is_clean()

    def touch(self) -> None:
        """Mark a change that is not on the undo stack (e.g. typing in an info sheet)."""
        if not self._touched:
            self._touched = True
            self.edited.emit()

    def mark_saved(self) -> None:
        self._touched = False
        self.undo.set_clean()

    def is_pristine(self) -> bool:
        """Nothing has been done in this project since it was created or opened."""
        return not self._touched and self.undo.count() == 0 and self.undo.is_clean()

    # --- lookup ------------------------------------------------------------------

    def sheets(self) -> list[Sheet]:
        return [*self.tables, *self.infos, *self.analyses, *self.graphs, *self.figures]

    def list_for(self, sheet: Sheet) -> list:
        return getattr(self, SECTION_OF[sheet.kind])

    def find(self, sheet_id: str) -> Sheet | None:
        return next((s for s in self.sheets() if s.id == sheet_id), None)

    def label_name(self, k: int) -> str:
        return self.label_names.get(k) or LABEL_NAMES.get(k, "")

    def root_table(self, sheet: Sheet) -> "Table | None":
        """The data table at the top of a sheet's chain (through analysis output tables)."""
        t = sheet if isinstance(sheet, Table) else (sheet.home if isinstance(sheet, Graph)
                                                     else getattr(sheet, "table", None))
        seen = 0
        while t is not None and getattr(t, "source_analysis", None) is not None and seen < 100:
            t = t.source_analysis.table
            seen += 1
        return t

    def children(self, sheet: Sheet) -> list[Sheet]:
        """Sheets nested directly under a sheet: a table's analyses and graphs; an analysis's
        graphs of its results and the analyses of its output table."""
        if isinstance(sheet, Table):
            return ([a for a in self.analyses if a.table is sheet]
                    + [g for g in self.graphs if g.home is sheet and g.source is None])
        if isinstance(sheet, Analysis):
            out = getattr(sheet, "_output", None)
            return ([g for g in self.graphs if g.source is sheet]
                    + ([a for a in self.analyses if a.table is out] if out is not None else [])
                    + ([g for g in self.graphs if g.home is out and g.source is None] if out is not None else []))
        return []

    def descendants(self, sheet: Sheet) -> list[Sheet]:
        out = []
        for c in self.children(sheet):
            out.append(c)
            out += self.descendants(c)
        return out

    def family(self, sheet: Sheet) -> list[Sheet]:
        """Prism 'family': a data table plus every analysis and graph fed by it, directly or
        through analysis results."""
        table = self.root_table(sheet)
        if table is None or table not in self.tables:
            return [sheet]
        return [table] + self.descendants(table)

    def analysis_outputs(self) -> list["Table"]:
        """Output tables of analyses that produce one (can be analysed and graphed)."""
        return [a.output_table() for a in self.analyses if a.has_output()]

    def set_engine(self, engine: AnalysisEngine | None) -> None:
        self.engine = engine
        for a in self.analyses:
            a.recompute()

    # --- low-level (not undoable) --------------------------------------------------

    def insert(self, sheet: Sheet, index: int | None = None) -> None:
        lst = self.list_for(sheet)
        lst.insert(len(lst) if index is None else index, sheet)
        sheet.attach(self)
        self.structure_changed.emit()

    def take(self, sheet: Sheet) -> int:
        lst = self.list_for(sheet)
        i = lst.index(sheet)
        del lst[i]
        sheet.detach()
        self.structure_changed.emit()
        return i

    def unique_name(self, base: str, kind: str) -> str:
        names = {s.name for s in getattr(self, SECTION_OF[kind])}
        n = 1
        while f"{base} {n}" in names:
            n += 1
        return f"{base} {n}"

    def new_table(self, name: str | None = None, table_type: str = "column", **fmt) -> Table:
        return Table(name or self.unique_name("Data", "table"), table_type, **fmt)

    def new_graph(self, table: Table) -> Graph:
        g = Graph(table.name, table)
        g.auto_name = True
        g.spec.y.title = "Title"
        if table.table_type == "grouped":
            g.spec.palette = True
            g.spec.default_style.appearance = "bar"
            g.spec.default_style.line_at = "mean_sd"
            g.spec.default_style.show_points = False
            g.spec.default_style.bars = True
            g.spec.col_width_mm = 9.0
        elif table.table_type == "nested":
            g.spec.default_style.line_at = "mean_sem"
            g.spec.col_width_mm = 24.0
        elif table.table_type == "contingency":
            g.spec.palette = True
            st = g.spec.default_style
            st.appearance, st.bars, st.line_at, st.errors, st.show_points = "bar", True, "mean", False, False
            g.spec.col_width_mm = 9.0
            g.spec.y.title = "Number of subjects"
        elif table.table_type == "parts":
            g.spec.palette = True
            g.spec.y.title = ""
        elif table.table_type == "survival":
            g.spec.palette = True
            g.spec.x.ticks_dir = "out"
            g.spec.x.title = "Time"
            g.spec.y.title = "Percent survival"
            g.spec.default_style.line_width = 1.5
        elif table.table_type == "multivar":
            g.spec.palette = True
            g.spec.x.ticks_dir = "out"
            g.spec.x.title = g.spec.y.title = ""          # the variables' names are used
            g.spec.show_legend = True
        elif table.table_type == "xy":
            g.spec.palette = True
            g.spec.x.ticks_dir = "out"
            g.spec.x.title = "X"
            g.spec.default_style.line_at = "mean_sem"
            g.spec.default_style.symbol_size = 3
        for hook in NEW_GRAPH_HOOKS:
            try:
                hook(g)
            except Exception:                    # settings must never stop a graph being made
                pass
        return g

    def new_result_graph(self, a: "Analysis") -> Graph:
        """A graph of an analysis's results table (frequency distributions, transforms)."""
        if a.analysis_type != "frequency":
            out = a.output_table()
            g = self.new_graph(out)
            # Start from the format of the data's own graph when it plots the same kind of table.
            base = next((x for x in self.graphs if x.home is a.table and x.source is None
                         and x.table.table_type == out.table_type), None)
            if base is not None:
                import copy as _copy
                g.spec = _copy.deepcopy(base.spec)
                g.spec.title = ""
                g.spec.offsets = {}
            if a.analysis_type == "normalize" and g.spec.y.title in ("Title", ""):
                g.spec.y.title = "Percent" if a.params.get("percent", True) else "Fraction"
            if a.analysis_type == "normality":       # QQ plot: points and the line of identity
                g.spec.x.title, g.spec.y.title = "Actual", "Predicted"
                g.spec.default_style.xy_show = "replicates"
                g.spec.palette = True
                g.spec.datasets = {}
                g.spec.show_legend = len(a.columns) > 1
                g.spec.functions = [{"id": "identity", "text": "Y = X", "params": {}, "from": None, "to": None,
                                     "color": "#000000", "width": 1.0, "dash": "solid"}]
            g.home, g.source = a.table, a
            g.name = a.name
            return g
        g = Graph(a.name, a.table, source=a)
        g.auto_name = True
        g.spec.palette = True
        g.spec.x.ticks_dir = "out"
        g.spec.x.title = "Bin centre"
        tab = getattr(a.result, "table", None) or {}
        g.spec.y.title = tab.get("what", "Number of values")
        st = g.spec.default_style
        if a.params.get("cumulative"):
            st.connect, st.line_at, st.show_points = True, "mean", True
        else:
            st.appearance, st.bars, st.line_at, st.errors = "bar", True, "mean", False
        return g

    # --- user actions (undoable) -----------------------------------------------------

    def add_sheets(self, sheets: list[Sheet], text: str) -> None:
        from .commands import AddSheets
        self.undo.push(AddSheets(self, sheets, text))

    def add_table(self, name: str | None = None, with_graph: bool = True,
                  table_type: str = "column", example: bool = False, **fmt) -> Table:
        t = self.new_table(name, table_type, **fmt)
        if example:
            from .table import fill_example
            fill_example(t)
        self.add_sheets([t, self.new_graph(t)] if with_graph else [t], "New Data Table")
        return t

    def add_graph(self, table: Table) -> Graph:
        g = self.new_graph(table)
        self.add_sheets([g], "New Graph")
        return g

    def add_analysis(self, a: Analysis) -> Analysis:
        self.add_sheets([a], "New Analysis")
        return a

    def add_info(self) -> InfoSheet:
        info = InfoSheet(self.unique_name("Project info", "info"))
        self.add_sheets([info], "New Info")
        return info

    def add_figure(self) -> FigureSheet:
        lay = FigureSheet(self.unique_name("Figure", "figure"))
        self.add_sheets([lay], "New Figure")
        return lay

    def delete(self, sheet: Sheet) -> None:
        """Delete a sheet; deleting a data table deletes its whole family."""
        from .commands import RemoveSheets
        # A sheet goes with everything that depends on it (its family, for a data table;
        # graphs and analyses of its results, for an analysis); dependents first.
        doomed = [sheet] + self.descendants(sheet)
        doomed = list(reversed(doomed))
        self.undo.push(RemoveSheets(self, doomed, f"Delete {sheet.name}"))

    def rename(self, sheet: Sheet, name: str) -> None:
        from .commands import Rename
        if name and name != sheet.name:
            self.undo.push(Rename(sheet, name))
