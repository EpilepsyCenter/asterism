"""M11: autosave and recovery, settings."""

from __future__ import annotations

import json
import os

import pytest


def _orphan(key: str) -> None:
    """Make a snapshot look as if its ASTERISM had quit unexpectedly."""
    from asterism.app import recovery
    meta = os.path.join(recovery.folder(), f"{key}.json")
    with open(meta, encoding="utf-8") as f:
        m = json.load(f)
    m["pid"] = 2 ** 22 + 12345                     # no such process
    with open(meta, "w", encoding="utf-8") as f:
        json.dump(m, f)


def test_autosave_writes_only_unsaved_changes_and_clears_on_save(app, tmp_path):
    from asterism.analysis import engine
    from asterism.app import recovery
    from asterism.app.main_window import MainWindow
    from asterism.doc.model import Project
    p = Project(engine)
    t = p.add_table(table_type="column", example=False)
    w = MainWindow(p)
    p.mark_saved()
    assert not w.autosave()                          # nothing unsaved: nothing written
    t.set(0, 0, 4.0)
    p.touch()
    assert w.autosave()
    data, meta = (os.path.join(recovery.folder(), f"{w._autosave_key}{ext}") for ext in (".asterism", ".json"))
    assert os.path.exists(data) and os.path.exists(meta)
    assert w._autosave_key not in [s.key for s in recovery.pending()]    # this ASTERISM is still running
    w.save_to(str(tmp_path / "saved.asterism"))
    assert not os.path.exists(data) and not os.path.exists(meta)
    w.close()


def test_recovery_after_a_crash(app, tmp_path, monkeypatch):
    from asterism.analysis import engine
    from asterism.app import recovery
    from asterism.app.dialogs.recovery import RecoveryDialog
    from asterism.app.main_window import MainWindow, offer_recovery
    from asterism.doc.model import Project
    for f in os.listdir(recovery.folder()):
        os.remove(os.path.join(recovery.folder(), f))
    p = Project(engine)
    t = p.add_table(table_type="column", example=False)
    t.titles[0] = "Unsaved work"
    w = MainWindow(p)
    p.touch()
    w.autosave()
    key = w._autosave_key
    _orphan(key)
    snaps = recovery.pending()
    assert [s.key for s in snaps] == [key] and snaps[0].original is None
    # Cancel: kept for later
    monkeypatch.setattr(RecoveryDialog, "exec", lambda self: False)
    assert offer_recovery() == [] and recovery.pending()
    # Restore
    monkeypatch.setattr(RecoveryDialog, "exec", lambda self: True)
    (rw,) = offer_recovery()
    assert rw.project.tables[0].titles[0] == "Unsaved work" and rw.project.is_modified()
    assert rw.display_name().endswith("(recovered)") and not recovery.pending()
    for win in (w, rw):
        win.project.mark_saved()
        win.close()


def test_discarding_snapshots(app, monkeypatch):
    from asterism.analysis import engine
    from asterism.app import recovery
    from asterism.app.dialogs.recovery import RecoveryDialog
    from asterism.app.main_window import MainWindow, offer_recovery
    from asterism.doc.model import Project
    p = Project(engine)
    p.add_table(table_type="column", example=False)
    w = MainWindow(p)
    p.touch()
    w.autosave()
    _orphan(w._autosave_key)

    def discard(self):
        self.discarded = True
        return False
    monkeypatch.setattr(RecoveryDialog, "exec", discard)
    offer_recovery()
    assert w._autosave_key not in [s.key for s in recovery.pending()]
    p.mark_saved()
    w.close()


@pytest.fixture
def clean_prefs():
    from asterism.app import prefs
    prefs.reset()
    yield prefs
    prefs.reset()


def test_settings_apply_to_new_graphs_and_analyses_only(app, clean_prefs, monkeypatch):
    from asterism.analysis import engine
    from asterism.app.dialogs.params import settings_dialog
    from asterism.app.main_window import MainWindow
    from asterism.doc.model import Project
    prefs = clean_prefs
    p = Project(engine)
    old = p.add_table(table_type="column", example=True)
    old_graph = p.graphs[0]
    prefs.set("graph.font", "Helvetica")
    prefs.set("graph.font_size", 9.0)
    prefs.set("graph.frame", "box")
    prefs.set("graph.sig_levels", "gp")
    prefs.set("graph.scheme", "greys")
    p.add_table(table_type="column", example=True)
    g = p.graphs[-1]
    assert g.spec.fonts["y_numbers"].family == "Helvetica" and g.spec.fonts["title"].size == 11.0
    assert g.spec.frame == "box" and g.spec.sig["levels"] == "gp" and g.spec.style(0).bar_fill == "#ffffff"
    assert old_graph.spec.frame == "plain"                         # existing graphs keep theirs
    prefs.set("analysis.ttest", "welch")
    prefs.set("analysis.conf", 0.99)
    assert prefs.analysis_defaults("ttest") == {"test": "welch", "conf": 0.99, "alpha": 0.05}
    w = MainWindow(p)
    w.show_sheet(old)
    monkeypatch.setattr(type(settings_dialog("ttest", None, old, [0, 1])), "exec", lambda self: True)
    w._quick("ttest")
    a = p.analyses[-1]
    assert a.params["test"] == "welch" and a.params["conf"] == 0.99
    p.mark_saved()
    w.close()


def test_settings_dialog_and_import_defaults(app, clean_prefs, tmp_path):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from test_m10_import import _std_curve_csv
    from asterism.app.dialogs.import_data import ImportDialog
    from asterism.app.dialogs.settings import SettingsDialog
    prefs = clean_prefs
    d = SettingsDialog()
    d.w["autosave.minutes"].setValue(7)
    d.w["import.titre_dilution"].setText("100")
    d.w["import.titre_volume_ul"].setText("1")
    d.w["import.titre_per"].setCurrentIndex(2)
    d.accept()
    assert prefs.get("autosave.minutes") == 7 and prefs.get("import.titre_dilution") == 100.0
    imp = ImportDialog([_std_curve_csv(tmp_path)])
    s = imp.qpcr_settings()["standard"]
    assert (s["dilution"], s["volume_ul"], s["per"]) == (100.0, 1.0, "ml") and imp.volume.isEnabled()
    SettingsDialog()._reset()
    assert prefs.get("autosave.minutes") == 2
