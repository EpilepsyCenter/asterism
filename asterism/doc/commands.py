"""Undoable commands for every user change to a project."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from .undo import Command

if TYPE_CHECKING:
    from .model import Analysis, Table, Graph, Project, Sheet
    from .spec import GraphSpec


class CellsCommand(Command):
    """Set many cells at once (typing, paste, clear) — one undo step."""

    def __init__(self, table: "Table", changes: list[tuple[int, int, float | None]],
                 text: str = "Edit Cell"):
        self.text = text
        self.table = table
        self.new = list(changes)
        self.old = [(r, c, table.get(r, c)) for r, c, _ in changes]
        keys = {(r, c) for r, c, _ in changes}
        self.old_excluded = {rc for rc in table.excluded if rc in keys}

    def _apply(self, changes) -> None:
        for r, c, v in changes:
            self.table.set(r, c, v, emit=False)
        self.table.changed.emit()

    def redo(self) -> None:
        self._apply(self.new)

    def undo(self) -> None:
        self._apply(reversed(self.old))
        if self.old_excluded:            # clearing a cell drops its exclusion; bring it back
            self.table.set_excluded(list(self.old_excluded), True)


class TitleCommand(Command):
    text = "Edit Title"

    def __init__(self, table: "Table", col: int, title: str):
        self.table, self.col, self.new, self.old = table, col, title, table.titles[col]

    def redo(self) -> None:
        self.table.set_title(self.col, self.new)

    def undo(self) -> None:
        self.table.set_title(self.col, self.old)


class SpecCommand(Command):
    """Snapshot-based undo for anything a Format dialog or direct edit changes."""

    def __init__(self, graph: "Graph", new_spec: "GraphSpec", text: str = "Format Graph"):
        self.text = text
        self.graph = graph
        self.old = copy.deepcopy(graph.spec)
        self.new = copy.deepcopy(new_spec)

    def redo(self) -> None:
        self.graph.set_spec(copy.deepcopy(self.new))

    def undo(self) -> None:
        self.graph.set_spec(copy.deepcopy(self.old))


class FigureCommand(Command):
    """Snapshot-based undo for any change to a figure (panels moved, added, formatted …)."""

    def __init__(self, figure, new_state: dict, text: str = "Edit Figure"):
        self.text = text
        self.figure = figure
        self.old = copy.deepcopy(figure.state())
        self.new = copy.deepcopy(new_state)

    def redo(self) -> None:
        self.figure.set_state(copy.deepcopy(self.new))

    def undo(self) -> None:
        self.figure.set_state(copy.deepcopy(self.old))


class ParamsCommand(Command):
    text = "Change Analysis Parameters"

    def __init__(self, analysis: "Analysis", params: dict):
        self.analysis = analysis
        self.old, self.new = dict(analysis.params), dict(params)

    def redo(self) -> None:
        self.analysis.set_params(self.new)

    def undo(self) -> None:
        self.analysis.set_params(self.old)


class Rename(Command):
    def __init__(self, sheet: "Sheet", name: str):
        self.text = "Rename Sheet"
        self.sheet = sheet
        self.old, self.new = sheet.name, name
        self.old_auto = sheet.auto_name

    def redo(self) -> None:
        self.sheet.auto_name = False            # a user-chosen name stops following
        self.sheet.name = self.new

    def undo(self) -> None:
        self.sheet.name = self.old
        self.sheet.auto_name = self.old_auto


class LabelCommand(Command):
    """Colour label on one or more sheets."""

    def __init__(self, sheets: list, label: int):
        from .model import LABEL_NAMES
        self.sheets = list(sheets)
        self.old = [sh.tag for sh in self.sheets]
        self.new = int(label or 0)
        self.text = "Remove Label" if not self.new else f"Label {LABEL_NAMES.get(self.new, '')}"

    def redo(self) -> None:
        for sh in self.sheets:
            sh.tag = self.new

    def undo(self) -> None:
        for sh, v in zip(self.sheets, self.old):
            sh.tag = v


class LabelNamesCommand(Command):
    def __init__(self, project, names: dict):
        self.text = "Rename Labels"
        self.project = project
        self.old, self.new = dict(project.label_names), {int(k): v for k, v in names.items() if v}

    def redo(self) -> None:
        self.project.label_names = dict(self.new)
        self.project.structure_changed.emit()

    def undo(self) -> None:
        self.project.label_names = dict(self.old)
        self.project.structure_changed.emit()


class AddSheets(Command):
    def __init__(self, project: "Project", sheets: list["Sheet"], text: str):
        self.project, self.sheets, self.text = project, list(sheets), text

    def redo(self) -> None:
        for s in self.sheets:
            self.project.insert(s)

    def undo(self) -> None:
        for s in reversed(self.sheets):
            self.project.take(s)


class RemoveSheets(Command):
    def __init__(self, project: "Project", sheets: list["Sheet"], text: str):
        self.project, self.sheets, self.text = project, list(sheets), text
        self.positions: list[int] = []

    def redo(self) -> None:
        self.positions = [self.project.take(s) for s in self.sheets]

    def undo(self) -> None:
        for s, i in reversed(list(zip(self.sheets, self.positions))):
            self.project.insert(s, i)


class SubTitleCommand(Command):
    text = "Edit Sub-column Title"

    def __init__(self, table: "Table", ds: int, sub: int, title: str):
        self.table, self.ds, self.sub = table, ds, sub
        self.new, self.old = title, table.sub_titles[ds][sub]

    def redo(self) -> None:
        self.table.set_sub_title(self.ds, self.sub, self.new)

    def undo(self) -> None:
        self.table.set_sub_title(self.ds, self.sub, self.old)


class ExcludeCommand(Command):
    """Exclude or include values: kept in the table, ignored by analyses and graphs."""

    def __init__(self, table: "Table", cells: list[tuple[int, int]], flag: bool):
        self.text = "Exclude Values" if flag else "Include Values"
        self.table, self.flag = table, flag
        self.cells = [rc for rc in cells if table.get(*rc) is not None]
        self.before = {rc for rc in self.cells if rc in table.excluded}

    def redo(self) -> None:
        self.table.set_excluded(self.cells, self.flag)

    def undo(self) -> None:
        self.table.set_excluded(self.cells, False, emit=False)
        self.table.set_excluded(list(self.before), True)


class TableEditCommand(Command):
    """A structural change to a table (insert/delete rows or data sets, change format).

    `mutate(table)` does the change and may return an old → new data-set index map
    (None = deleted); linked graphs and analyses are remapped so styles and analysed
    columns follow their data sets. Undo/redo restore snapshots, so `mutate` runs once.
    """

    def __init__(self, project: "Project", table: "Table", mutate, text: str):
        self.text = text
        self.project, self.table, self.mutate = project, table, mutate
        self.before = self._snapshot()
        self.after = None

    def _linked(self):
        p = self.project
        return ([g for g in p.graphs if g.home is self.table and g.source is None],
                [a for a in p.analyses if a.table is self.table])

    def _snapshot(self) -> dict:
        graphs, analyses = self._linked()
        return {"table": self.table.state(),
                "specs": {id(g): copy.deepcopy(g.spec) for g in graphs},
                "columns": {id(a): list(a.columns) for a in analyses}}

    def _restore(self, snap: dict) -> None:
        graphs, analyses = self._linked()
        self.table.set_state(snap["table"], emit=False)
        for a in analyses:
            if id(a) in snap["columns"]:
                a.columns = list(snap["columns"][id(a)])
        for g in graphs:
            if id(g) in snap["specs"]:
                g.spec = copy.deepcopy(snap["specs"][id(g)])
        self.table.changed.emit()

    def redo(self) -> None:
        if self.after is not None:
            self._restore(self.after)
            return
        mapping = self.mutate(self.table)
        if mapping:
            graphs, analyses = self._linked()
            for g in graphs:
                spec = g.spec
                spec.datasets = {mapping[k]: v for k, v in spec.datasets.items()
                                 if mapping.get(k) is not None}
                spec.hidden = {mapping[k] for k in spec.hidden if mapping.get(k) is not None}
            for a in analyses:
                a.columns = [mapping[c] for c in a.columns if mapping.get(c) is not None]
            self.table.changed.emit()
        self.after = self._snapshot()

    def undo(self) -> None:
        self._restore(self.before)


class InfoCommand(Command):
    """Typing in a Notes sheet: one constant's value, or the notes (key None). Continued
    typing in the same place merges into one undo step."""

    def __init__(self, info, key: str | None, value: str):
        self.info, self.key, self.new = info, key, value
        self.old = info.notes if key is None else info.fields.get(key, "")
        self.text = "Edit Notes" if key is None else f"Edit {key}"

    def _set(self, v: str) -> None:
        if self.key is None:
            self.info.notes = v
        else:
            self.info.fields[self.key] = v
        self.info.changed.emit()

    def redo(self) -> None:
        self._set(self.new)

    def undo(self) -> None:
        self._set(self.old)

    def merge(self, other) -> bool:
        if isinstance(other, InfoCommand) and other.info is self.info and other.key == self.key:
            self.new = other.new
            return True
        return False
