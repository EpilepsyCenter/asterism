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


def test_units_sit_outside_the_number_boxes(app):
    """Spin boxes hold only the number; the unit is a label beside the box."""
    from PySide6.QtWidgets import QAbstractSpinBox, QLabel
    from asterism.analysis import engine
    from asterism.app.dialogs.format_graph import FormatGraphDialog
    from asterism.doc.model import Project
    p = Project(engine)
    p.add_table(table_type="nested", example=True)
    d = FormatGraphDialog(p.graphs[-1], p)
    d.show()
    spins = d.findChildren(QAbstractSpinBox)
    assert spins and all(not getattr(s, "suffix", lambda: "")().strip() for s in spins)
    assert d.n_mean.value() == 2.2
    labels = {lab.text() for lab in d.findChildren(QLabel)}
    assert "× the points" in labels and "mm" in labels
    d.close()


def test_every_table_type_and_analysis_has_a_picture(app):
    """Illustrations: each table type (New Table) and each available analysis (Analyze) has
    one, and they draw without errors in light and dark mode."""
    from asterism.app import theme
    from asterism.app.dialogs.analyze import CATALOGUE
    from asterism.app.sketches import DRAW, Sketch
    from asterism.doc.table import TABLE_TYPES
    keys = [f"table:{t}" for t in TABLE_TYPES]
    keys += sorted({akey for _k, _t, _i, items in CATALOGUE for _n, akey, _d in items if akey})
    missing = [k for k in keys if k not in DRAW]
    assert not missing, missing
    for dark in (False, True):
        theme._state["dark"] = dark
        for k in DRAW:
            img = Sketch(k).grab()
            assert not img.isNull()
    theme._state["dark"] = False


def test_every_icon_is_bundled(app):
    """Icons come from the bundled Lucide set on every platform: each name used in the code
    maps to a file that exists, and the licence ships with them."""
    import os
    import re
    from asterism.app import icons
    root = os.path.dirname(icons.__file__)
    used = set()
    for dirpath, _d, files in os.walk(root):
        for f in files:
            if f.endswith(".py"):
                src = open(os.path.join(dirpath, f), encoding="utf-8").read()
                used |= {n for n in re.findall(r'"([a-z0-9]+(?:\.[a-z0-9]+)*)"', src) if n in icons.LUCIDE}
    for name, file in icons.LUCIDE.items():
        assert os.path.exists(os.path.join(icons.ASSETS, f"{file}.svg")), name
    assert os.path.exists(os.path.join(icons.ASSETS, "LICENSE"))
    for name in used:
        assert not icons.icon(name).isNull(), name
    assert len(used) > 80
    # every place the code names an icon (dialog sections, actions, icon() calls) is covered
    named = set()
    pats = [r'add_section\([^)]*?,\s*"([a-z0-9.]+)"\s*\)', r'\bicon\(\s*"([a-z0-9.]+)"',
            r'\b(?:A|L|_act)\(\s*"[^"]*",\s*"([a-z0-9.]+)"']
    for dirpath, _d, files in os.walk(root):
        for f in files:
            if f.endswith(".py"):
                src = open(os.path.join(dirpath, f), encoding="utf-8").read()
                for pat in pats:
                    named |= set(re.findall(pat, src))
    assert not sorted(n for n in named if n not in icons.LUCIDE)


def test_second_launch_hands_files_to_the_running_app(app, tmp_path, monkeypatch):
    """A later launch (a separate process, as a double-click starts) gives its files to the
    running ASTERISM, waits for it to confirm, and quits."""
    import subprocess
    import sys
    import time
    from asterism.analysis import engine
    from asterism.app import main as M
    from asterism.app.main_window import windows
    from asterism.doc import fileformat
    from asterism.doc.sample import sample_project
    name = f"asterism-test-{os.getpid()}"
    monkeypatch.setenv("ASTERISM_SERVER_NAME", name)
    path = tmp_path / "handed.asterism"
    fileformat.save(sample_project(engine), str(path))
    code = ("import sys; from PySide6.QtCore import QCoreApplication; app = QCoreApplication([]); "
            "from asterism.app.main import hand_over; sys.exit(0 if hand_over([sys.argv[1]]) else 3)")
    env = {**os.environ, "ASTERISM_SERVER_NAME": name}
    nobody = subprocess.run([sys.executable, "-c", code, str(path)], env=env, timeout=60)
    assert nobody.returncode == 3                     # nothing listening yet
    M.listen(app)
    proc = subprocess.Popen([sys.executable, "-c", code, str(path)], env=env)
    same = lambda w: bool(w.path) and os.path.exists(w.path) and os.path.samefile(w.path, str(path))
    end = time.time() + 30
    while time.time() < end and (proc.poll() is None or not any(same(w) for w in windows())):
        app.processEvents()
        time.sleep(0.01)
    assert proc.poll() == 0                           # the running app confirmed
    opened = [w for w in windows() if same(w)]
    assert opened
    for w in opened:
        w.project.mark_saved()
        w.close()
    app._server.close()


def test_update_version_comparison():
    from asterism.app.updates import newer, parse_version
    assert parse_version("v0.2.1") == (0, 2, 1) and parse_version("x") == ()
    assert newer("v0.2.0", "0.1.0") and newer("0.1.1", "0.1") and newer("v1.0", "0.9.9")
    assert not newer("v0.1.0", "0.1.0") and not newer("0.1", "0.1.0") and not newer("", "0.1.0")


def test_selftest_passes(app, capsys):
    """The packaged apps run `--selftest`; it must pass from source too."""
    from asterism.app.selftest import run
    assert run(app) == 0, capsys.readouterr().out


def test_a_file_reopens_at_its_own_size_place_and_sheet(app, tmp_path):
    from asterism.analysis import engine
    from asterism.app.main_window import open_path, windows
    from asterism.doc import fileformat
    from asterism.doc.sample import sample_project
    path = str(tmp_path / "remember.asterism")
    fileformat.save(sample_project(engine), path)
    w = open_path(path)
    w.setGeometry(10, 20, 770, 520)          # fits the offscreen test screen (800 × 600)
    size = (w.width(), w.height())
    g = w.project.graphs[0]
    w.show_sheet(g)
    app.processEvents()
    w._save_geometry()
    w.close()
    other = open_path(path)
    assert (other.width(), other.height()) == size and size != (1480, 920)
    assert other.current is not None and other.current.id == g.id
    other.project.mark_saved()
    other.close()
    for x in windows():
        x.project.mark_saved()
        x.close()
