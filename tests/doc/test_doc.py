"""Document model, undo and project files — all without Qt (SPEC §2.6, §11, M1)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import zipfile

import pytest

from asterism.analysis import engine
from asterism.doc import fileformat
from asterism.doc.commands import CellsCommand, ParamsCommand, SpecCommand, TitleCommand
from asterism.doc.events import Signal
from asterism.doc.model import Analysis, Project
from asterism.doc.sample import blank_project, sample_project
from asterism.doc.spec import GraphSpec, spec_from_dict, spec_to_dict


def test_model_and_analysis_never_import_qt():
    code = ("import sys, asterism.doc, asterism.doc.fileformat, asterism.analysis, "
            "asterism.doc.sample; print('PySide6' in sys.modules)")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False"


# --- events and undo ---------------------------------------------------------------

def test_signal_drops_dead_bound_methods():
    class View:
        def __init__(self):
            self.hits = 0

        def slot(self):
            self.hits += 1

    sig, v = Signal(), View()
    sig.connect(v.slot)
    sig.emit()
    assert v.hits == 1
    del v
    sig.emit()                      # no error, slot gone
    assert len(sig) == 0


def test_undo_stack_clean_state():
    p = sample_project(engine)
    t = p.tables[0]
    assert not p.is_modified()
    p.undo.push(CellsCommand(t, [(0, 0, 99.0)]))
    assert p.is_modified()
    p.undo.undo()
    assert not p.is_modified()                     # back at the saved state
    p.undo.redo()
    p.mark_saved()
    p.undo.undo()
    assert p.is_modified()
    p.undo.redo()
    assert not p.is_modified()


def test_touch_marks_modified_until_saved():
    p = blank_project(engine)
    p.touch()
    assert p.is_modified() and not p.is_pristine()
    p.mark_saved()
    assert not p.is_modified()


# --- live linking --------------------------------------------------------------------

def _ttest(p: Project, **params) -> Analysis:
    a = Analysis("ttest", p.tables[0], [0, 1], {"design": "unpaired", "distribution": "normal",
                                                "test": "student", **params})
    return p.add_analysis(a)


def test_edit_recomputes_analysis_and_rebuilds_graph():
    p = sample_project(engine)
    a = _ttest(p)
    g = p.graphs[0]
    hits = []
    g.changed.connect(lambda: hits.append(1))
    p0 = a.result.p
    p.undo.push(CellsCommand(p.tables[0], [(10, 1, 300.0)]))
    assert a.result.p != p0 and hits
    assert a.name == "Student's t test of Cumulative SE seizure grade"


def test_params_change_is_undoable():
    p = sample_project(engine)
    a = _ttest(p)
    p.undo.push(ParamsCommand(a, {**a.params, "test": "welch"}))
    assert a.name.startswith("Welch's t test")
    p.undo.undo()
    assert a.params["test"] == "student" and a.name.startswith("Student's t test of")


# --- sheet operations ------------------------------------------------------------------

def test_add_table_creates_graph_and_undoes():
    p = blank_project(engine)
    t = p.add_table()
    assert t.name == "Data 2" and p.graphs[-1].table is t
    p.undo.undo()
    assert t not in p.tables and all(g.table is not t for g in p.graphs)
    p.undo.redo()
    assert t in p.tables


def test_delete_table_removes_family_and_undo_restores_links():
    p = sample_project(engine)
    a = _ttest(p)
    t, g = p.tables[0], p.graphs[0]
    p.delete(t)
    assert p.tables == [] and p.analyses == [] and p.graphs == []
    p.undo.undo()
    assert p.tables == [t] and p.analyses == [a] and p.graphs == [g]
    before = a.result.p
    p.undo.push(CellsCommand(t, [(0, 1, 500.0)]))
    assert a.result.p != before                         # relinked after restore


def test_deleted_analysis_stops_listening():
    p = sample_project(engine)
    a = _ttest(p)
    p.delete(a)
    stale = a.result
    p.tables[0].set(0, 0, 1.0)
    assert a.result is stale


def test_rename_stops_auto_naming_and_undo_restores():
    p = sample_project(engine)
    t, g = p.tables[0], p.graphs[0]
    p.rename(t, "Grades")
    assert g.name == "Grades"                            # graph follows its table
    p.rename(g, "Figure 1")
    p.rename(t, "Grades v2")
    assert g.name == "Figure 1"                          # user name sticks
    p.undo.undo()
    p.undo.undo()
    assert g.name == "Grades" and g.auto_name


# --- graph spec --------------------------------------------------------------------------

def test_spec_round_trip_and_tolerance():
    s = GraphSpec()
    s.style(1).symbol_size = 6
    s.hidden = {2}
    s.y.vmax, s.y.auto = 120.0, False
    s.fonts["title"].italic = True
    s.offsets["bracket"] = (1.5, -3.0)
    d = json.loads(json.dumps(spec_to_dict(s)))
    s2 = spec_from_dict(d)
    assert spec_to_dict(s2) == spec_to_dict(s)
    # unknown keys are ignored, missing keys get defaults
    s3 = spec_from_dict({"title": "T", "future_option": 1, "y": {"vmax": 5, "nope": 2}})
    assert s3.title == "T" and s3.y.vmax == 5.0 and s3.x.ticks_dir == "none"


# --- project files ---------------------------------------------------------------------

def test_project_file_round_trip(tmp_path):
    p = sample_project(engine)
    a = _ttest(p, test="welch")
    p.add_analysis(Analysis("descriptive", p.tables[0], [0, 1], {}))
    t = p.tables[0]
    p.undo.push(TitleCommand(t, 2, "Extra"))
    p.undo.push(CellsCommand(t, [(0, 2, 7.5), (3, 2, -1.0)]))
    g = p.graphs[0]
    spec = spec_from_dict(spec_to_dict(g.spec))
    spec.style(0).bars = True
    spec.y.title = "Seizure score"
    p.undo.push(SpecCommand(g, spec))
    p.infos[0].fields["Experimenter"] = "M.L."
    p.infos[0].notes = "pilot cohort"
    p.add_figure()
    p.rename(g, "Figure 1")

    path = tmp_path / "proj.asterism"
    fileformat.save(p, path)
    q = fileformat.load(path, engine)

    assert [s.name for s in q.sheets()] == [s.name for s in p.sheets()]
    assert [s.id for s in q.sheets()] == [s.id for s in p.sheets()]
    qt = q.tables[0]
    assert qt.cols == t.cols and qt.titles == t.titles
    assert q.graphs[0].table is qt and q.graphs[0].name == "Figure 1"
    assert not q.graphs[0].auto_name
    assert spec_to_dict(q.graphs[0].spec) == spec_to_dict(g.spec)
    assert q.infos[0].fields["Experimenter"] == "M.L." and q.infos[0].notes == "pilot cohort"
    qa = q.analyses[0]
    assert qa.table is qt and qa.params == a.params
    assert qa.result.p == pytest.approx(a.result.p)       # recomputed, not stored
    assert not q.is_modified() and q.undo.count() == 0


def test_results_are_not_stored(tmp_path):
    p = sample_project(engine)
    _ttest(p)
    path = tmp_path / "p.asterism"
    fileformat.save(p, path)
    with zipfile.ZipFile(path) as z:
        assert z.namelist() == ["mimetype", "project.json"]
        assert z.read("mimetype") == fileformat.MIMETYPE
        text = z.read("project.json").decode()
    assert "P value" not in text and "result" not in json.loads(text)["analyses"][0]


def test_save_is_atomic_and_leaves_no_temp_files(tmp_path, monkeypatch):
    p = sample_project(engine)
    path = tmp_path / "p.asterism"
    fileformat.save(p, path)
    good = path.read_bytes()

    def boom(*_a, **_k):
        raise OSError("disk full")
    monkeypatch.setattr(fileformat.zipfile.ZipFile, "writestr", boom)
    with pytest.raises(OSError):
        fileformat.save(p, path)
    assert path.read_bytes() == good                    # old file untouched
    assert os.listdir(tmp_path) == ["p.asterism"]       # temp file cleaned up


def test_newer_and_damaged_files_are_refused(tmp_path):
    d = fileformat.project_to_dict(sample_project(engine))
    d["version"] = fileformat.FORMAT_VERSION + 1
    with pytest.raises(fileformat.NewerVersionError):
        fileformat.project_from_dict(d)
    bad = tmp_path / "bad.asterism"
    bad.write_bytes(b"not a zip")
    with pytest.raises(fileformat.ProjectFileError):
        fileformat.load(bad)
    with pytest.raises(fileformat.ProjectFileError):
        fileformat.project_from_dict({"format": "something-else"})
