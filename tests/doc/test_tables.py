"""Data tables: the eight types, entry formats, exclusion, structure edits, files (M2)."""

from __future__ import annotations

import json

import numpy as np
import pytest

from asterism.analysis import engine
from asterism.doc import fileformat
from asterism.doc.commands import CellsCommand, ExcludeCommand, TableEditCommand
from asterism.doc.model import Analysis, Project, Table
from asterism.doc.table import (SUMMARY_FORMATS, TABLE_TYPES, TYPE_Y_FORMATS, Y_FORMATS,
                                fill_example)


@pytest.mark.parametrize("tt", TABLE_TYPES)
def test_every_type_and_format_builds_and_fills(tt):
    for fmt in TYPE_Y_FORMATS[tt]:
        t = Table("T", tt, fmt, replicates=3)
        labels = Y_FORMATS[fmt]
        assert t.width() == (3 if labels is None else len(labels))
        assert len(t.y) == t.ncols * t.width()
        fill_example(t)
        assert t.used_columns(), (tt, fmt)
        assert t.describe().startswith(t.describe().split(" ·")[0])


def test_columns_by_type():
    assert Table("", "xy").has_x() and not Table("", "xy").has_row_titles
    assert Table("", "xy", row_titles=True, x_format="numbers_err").x_format == "numbers_err"
    assert Table("", "grouped").has_row_titles and not Table("", "grouped").has_x()
    assert Table("", "survival").has_x() and Table("", "contingency").has_row_titles
    assert Table("", "nested", "replicates", replicates=5).width() == 5
    assert Table("", "contingency", "mean_sd").y_format == "single"   # not offered → default


def test_summary_formats_give_mean_and_error():
    t = Table("", "column", "mean_sd_n")
    for s, v in enumerate((10.0, 2.0, 4.0)):
        t.set(0, t.flat(0, s), v)
    sm = t.summary(0, 0)
    assert (sm["mean"], sm["sd"], sm["sem"], sm["n"]) == (10.0, 2.0, 1.0, 4.0)
    assert (sm["lo"], sm["hi"]) == (8.0, 12.0)
    t = Table("", "column", "mean_cv")
    t.set(0, 0, 50.0)
    t.set(0, 1, 10.0)
    assert t.summary(0, 0)["sd"] == pytest.approx(5.0)
    t = Table("", "column", "mean_pm")
    for s, v in enumerate((10.0, 3.0, 1.0)):
        t.set(0, s, v)
    assert (t.summary(0, 0)["lo"], t.summary(0, 0)["hi"]) == (9.0, 13.0)
    assert len(t.values(0)) == 0                     # no raw values in summary tables


def test_values_use_every_replicate_and_skip_excluded():
    t = Table("", "grouped", "replicates", replicates=3)
    for s, v in enumerate((1.0, 2.0, 3.0)):
        t.set(0, t.flat(1, s), v)
    assert sorted(t.values(1)) == [1.0, 2.0, 3.0]
    t.set_excluded([(0, t.flat(1, 1))], True)
    assert sorted(t.values(1)) == [1.0, 3.0]
    assert list(t.row_values(0, 1)) == [1.0, 3.0]


def test_what_each_cell_accepts():
    surv, mv, col = Table("", "survival"), Table("", "multivar"), Table("", "column")
    assert surv.accepts(0, 1.0) and not surv.accepts(0, 2.0) and surv.accepts("x", 37.5)
    assert mv.accepts(0, "male") and not col.accepts(0, "male")
    assert col.accepts("row", "Day 1") is True and not Table("", "contingency").accepts(0, -1.0)


def test_insert_and_delete_rows_shift_everything():
    t = Table("", "grouped")
    for r in range(3):
        t.set(r, "row", f"r{r}")
        t.set(r, 0, float(r))
    t.set_excluded([(2, 0)], True)
    t.insert_rows(1, 2)
    assert t.row_title_values[:5] == ["r0", None, None, "r1", "r2"] and (4, 0) in t.excluded
    t.delete_rows([1, 2])
    assert t.row_title_values == ["r0", "r1", "r2"] and t.excluded == {(2, 0)}


def test_insert_and_delete_data_sets_return_maps():
    t = Table("", "grouped", "replicates", replicates=2, ncols=3)
    t.titles[:] = ["A", "B", "C"]
    t.set(0, t.flat(2, 1), 5.0)
    t.set_excluded([(0, t.flat(2, 1))], True)
    m = t.insert_sets(1)
    assert t.titles == ["A", "", "B", "C"] and m == {0: 0, 1: 2, 2: 3}
    assert t.get(0, t.flat(3, 1)) == 5.0 and (0, t.flat(3, 1)) in t.excluded
    m = t.delete_sets([0, 1])
    assert t.titles == ["B", "C"] and m == {0: None, 1: None, 2: 0, 3: 1}
    assert t.get(0, t.flat(1, 1)) == 5.0 and (0, t.flat(1, 1)) in t.excluded


def test_reformat_keeps_what_fits():
    t = Table("", "xy", "replicates", replicates=3)
    for s in range(3):
        t.set(0, t.flat(1, s), float(s))
    t.reformat(replicates=2)
    assert t.width() == 2 and [t.get(0, t.flat(1, s)) for s in range(2)] == [0.0, 1.0]
    t.reformat(x_format="numbers_err", row_titles=True)
    assert t.x_format == "numbers_err" and t.has_row_titles


def _project_with_linked_sheets():
    p = Project(engine)
    t = p.add_table(table_type="column", example=True)
    g = p.graphs[0]
    g.spec.style(1).symbol_color = "#ff0000"
    a = p.add_analysis(Analysis("ttest", t, [0, 1], {}))
    return p, t, g, a


def test_structure_edit_remaps_linked_graph_and_analysis_and_undoes():
    p, t, g, a = _project_with_linked_sheets()
    p0 = a.result.p
    p.undo.push(TableEditCommand(p, t, lambda tb: tb.insert_sets(0), "Insert Data Set"))
    assert a.columns == [1, 2] and g.spec.style(2).symbol_color == "#ff0000"
    assert a.result.p == pytest.approx(p0)            # same data, still compared
    p.undo.undo()
    assert a.columns == [0, 1] and g.spec.datasets[1].symbol_color == "#ff0000"
    p.undo.redo()
    assert a.columns == [1, 2]


def test_exclusion_changes_results_and_undoes():
    p, t, g, a = _project_with_linked_sheets()
    p0 = a.result.p
    p.undo.push(ExcludeCommand(t, [(0, 0), (1, 0)], True))
    assert a.result.p != p0
    p.undo.undo()
    assert a.result.p == pytest.approx(p0)


def test_clearing_an_excluded_cell_and_undo_restores_exclusion():
    p, t, g, a = _project_with_linked_sheets()
    t.set_excluded([(0, 0)], True)
    p.undo.push(CellsCommand(t, [(0, 0, None)], "Clear"))
    assert (0, 0) not in t.excluded
    p.undo.undo()
    assert (0, 0) in t.excluded and t.get(0, 0) is not None


@pytest.mark.parametrize("tt", TABLE_TYPES)
def test_every_type_round_trips_through_a_file(tt, tmp_path):
    p = Project(engine)
    fmt = {"xy": {"y_format": "replicates", "replicates": 2, "x_format": "numbers_err",
                  "row_titles": True},
           "column": {"y_format": "mean_sd_n"}, "nested": {"replicates": 3}}.get(tt, {})
    t = p.add_table(table_type=tt, example=True, **fmt)
    t.titles[0] = "First"
    used = t.used_columns()
    t.set_excluded([(0, t.flat(used[0]))], True)
    path = tmp_path / f"{tt}.asterism"
    fileformat.save(p, path)
    q = fileformat.load(path, engine)
    assert q.tables[0].state() == t.state()


def test_version_1_files_open_as_column_tables():
    v1 = {"format": "asterism-project", "version": 1, "app_version": "0.1.0",
          "tables": [{"id": "t1", "name": "Old", "type": "column", "titles": ["EGFP", "SV2A"],
                      "columns": [[1.0, 2.0, None, 4.0], [3.0]]}],
          "infos": [], "layouts": [],
          "analyses": [{"id": "a1", "name": "", "auto_name": True, "type": "ttest", "table": "t1",
                        "columns": [0, 1], "params": {}}],
          "graphs": [{"id": "g1", "name": "Old", "auto_name": True, "table": "t1", "spec": {}}]}
    p = fileformat.project_from_dict(json.loads(json.dumps(v1)), engine)
    t = p.tables[0]
    assert (t.table_type, t.y_format) == ("column", "single")
    assert t.titles == ["EGFP", "SV2A"] and t.get(3, 0) == 4.0 and t.get(0, 1) == 3.0
    assert p.analyses[0].table is t and p.graphs[0].table is t
