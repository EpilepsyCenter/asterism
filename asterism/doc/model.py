"""Project model: data tables, info sheets, analyses, graphs, layouts (no Qt).

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

class Sheet:
    kind = "sheet"

    def __init__(self, name: str = "", id: str | None = None):
        self.id = id or uuid.uuid4().hex
        self._name = name
        self.auto_name = False       # name follows its table / analysis type
        self.project: Project | None = None
        self.renamed = Signal()

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


class LayoutSheet(Sheet):
    kind = "layout"


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
        if a is self.source or (self.source is None and a.table is self.home):
            self.changed.emit()

    def set_spec(self, spec: GraphSpec) -> None:
        self.spec = spec
        self.changed.emit()

    def analyses(self) -> list["Analysis"]:
        if self.project is None or self.source is not None:
            return []
        return [a for a in self.project.analyses if a.table is self.home]


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

    def result_table(self) -> "Table":
        """The analysis's tabular output as an XY table (frequency distributions), rebuilt
        when the result changes. Graphs of an analysis plot this."""
        cached = getattr(self, "_rt", None)
        if cached is not None and cached[0] is self.result:
            return cached[1]
        t = Table(self.name, "xy", "single", ncols=max(1, len(self.columns)))
        tab = getattr(self.result, "table", None) if self.result is not None else None
        if tab:
            for r, cx in enumerate(tab.get("centers", [])):
                t.set(r, "x", float(cx), emit=False)
            for j, vals in enumerate(tab.get("values", [])):
                for r, v in enumerate(vals):
                    if v is not None:
                        t.set(r, t.flat(j), float(v), emit=False)
            for j, c in enumerate(self.columns[:t.ncols]):
                t.titles[j] = self.table.label(c)
            t.bin_width = tab.get("width")
            t.cumulative = bool(self.params.get("cumulative"))
        self._rt = (self.result, t)
        return t

    def _auto_rename(self) -> None:
        engine = self.project.engine if self.project else None
        if self.auto_name and engine is not None:
            self.name = f"{engine.title(self)} of {self.table.name}"

    def recompute(self) -> None:
        engine = self.project.engine if self.project else None
        self._auto_rename()
        self.result = engine.run(self) if engine is not None else None
        self.changed.emit()
        if self.project is not None:
            self.project.analysis_changed.emit(self)


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------

SECTION_OF = {"table": "tables", "info": "infos", "analysis": "analyses", "graph": "graphs",
              "layout": "layouts"}


class Project:
    def __init__(self, engine: AnalysisEngine | None = None):
        self.tables: list[Table] = []
        self.infos: list[InfoSheet] = []
        self.analyses: list[Analysis] = []
        self.graphs: list[Graph] = []
        self.layouts: list[LayoutSheet] = []
        self.engine = engine
        self.undo = UndoStack()
        self._touched = False
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
        return [*self.tables, *self.infos, *self.analyses, *self.graphs, *self.layouts]

    def list_for(self, sheet: Sheet) -> list:
        return getattr(self, SECTION_OF[sheet.kind])

    def find(self, sheet_id: str) -> Sheet | None:
        return next((s for s in self.sheets() if s.id == sheet_id), None)

    def family(self, sheet: Sheet) -> list[Sheet]:
        """Prism 'family': a data table plus the analyses and graphs fed by it."""
        table = getattr(sheet, "table", sheet if isinstance(sheet, Table) else None)
        if table is None:
            return [sheet]
        return ([table] + [a for a in self.analyses if a.table is table]
                + [g for g in self.graphs if g.home is table])

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
        elif table.table_type == "xy":
            g.spec.palette = True
            g.spec.x.ticks_dir = "out"
            g.spec.x.title = "X"
            g.spec.default_style.line_at = "mean_sem"
            g.spec.default_style.symbol_size = 3
        return g

    def new_result_graph(self, a: "Analysis") -> Graph:
        """A graph of an analysis's results table (frequency distributions)."""
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

    def add_layout(self) -> LayoutSheet:
        lay = LayoutSheet(self.unique_name("Layout", "layout"))
        self.add_sheets([lay], "New Layout")
        return lay

    def delete(self, sheet: Sheet) -> None:
        """Delete a sheet; deleting a data table deletes its whole family."""
        from .commands import RemoveSheets
        doomed = self.family(sheet) if isinstance(sheet, Table) else [sheet]
        if isinstance(sheet, Analysis):            # graphs of its results go with it
            doomed += [g for g in self.graphs if g.source is sheet]
        # Dependents first, so nothing points at a missing table while removing.
        doomed = doomed[1:] + doomed[:1] if len(doomed) > 1 else doomed
        self.undo.push(RemoveSheets(self, doomed, f"Delete {sheet.name}"))

    def rename(self, sheet: Sheet, name: str) -> None:
        from .commands import Rename
        if name and name != sheet.name:
            self.undo.push(Rename(sheet, name))
