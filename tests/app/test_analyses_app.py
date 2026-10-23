"""Column analyses in the app: settings dialogs, running, stacked brackets (M3)."""

from __future__ import annotations

import pytest


def _window_with(groups):
    from asterism.analysis import engine
    from asterism.app.main_window import MainWindow
    from asterism.doc.model import Project
    p = Project(engine)
    t = p.add_table(table_type="column")
    for c, (name, vals) in enumerate(groups.items()):
        t.titles[c] = name
        for r, v in enumerate(vals):
            t.set(r, c, v, emit=False)
    p.undo.clear()
    p.mark_saved()
    return MainWindow(p)


GROUPS = {"Vehicle": [24, 26, 31, 27, 29, 25], "Low": [31, 35, 30, 36, 33, 34],
          "Mid": [29, 27, 33, 28, 30, 31], "High": [40, 38, 36, 41, 39, 35]}


@pytest.fixture
def w(app):
    win = _window_with(GROUPS)
    yield win
    win.project.mark_saved()
    win.close()


def test_anova_settings_offer_the_right_methods(w):
    from asterism.app.dialogs.params import AnovaParamsDialog
    t = w.project.tables[0]
    dlg = AnovaParamsDialog(None, t, [0, 1, 2, 3])
    methods = [dlg.method.itemData(i) for i in range(dlg.method.count())]
    assert methods[0] == "tukey" and "dunnett" not in methods
    for b in dlg.g_compare.buttons():
        if b.property("key") == "control":
            b.setChecked(True)
    assert dlg.method.currentData() == "dunnett" and dlg.control.isEnabled()
    for b in dlg.g_dist.buttons():
        if b.property("key") == "nonparametric":
            b.setChecked(True)
    assert [dlg.method.itemData(i) for i in range(dlg.method.count())] == ["dunn", "dunn_none"]
    assert dlg.params()["distribution"] == "nonparametric"


def test_run_anova_from_the_window_and_draw_stacked_brackets(w, monkeypatch):
    from asterism.app.dialogs.params import AnovaParamsDialog
    monkeypatch.setattr(AnovaParamsDialog, "exec", lambda self: 1)
    w.show_sheet(w.project.tables[0])
    w.a_anova.trigger()
    a = w.current
    assert a.analysis_type == "anova1" and a.result.error is None
    assert [pg.title for pg in a.result.pages][:3] == ["Results", "ANOVA table", "Comparisons"]
    g = w.project.graphs[0]
    gs = w._widget_for(g)
    brackets = [it.el for it in gs.items if it.el.kind == "bracket"]
    significant = [c for c in a.result.comparisons if c[2] < 0.05]
    assert len(brackets) == len(significant) >= 3
    for i, b1 in enumerate(brackets):                   # no two brackets overlap
        for b2 in brackets[i + 1:]:
            assert not b1.bounds.adjusted(1, 1, -1, -1).intersects(b2.bounds.adjusted(1, 1, -1, -1))
    spec = g.spec
    spec.brackets_ns = True
    g.changed.emit()
    assert len([it for it in gs.items if it.el.kind == "bracket"]) == len(a.result.comparisons)


@pytest.mark.parametrize("kind", ["normality", "onesample", "outliers", "frequency", "descriptive"])
def test_quick_analyses_run_on_the_current_table(w, monkeypatch, kind):
    from asterism.app.dialogs import params
    for cls in (params.NormalityParamsDialog, params.OneSampleParamsDialog,
                params.OutlierParamsDialog, params.FrequencyParamsDialog):
        monkeypatch.setattr(cls, "exec", lambda self: 1)
    w.show_sheet(w.project.tables[0])
    w._quick(kind)
    a = w.current
    assert a.analysis_type == kind and a.result.error is None and a.result.pages


def test_analysis_settings_reopen_and_undo(w, monkeypatch):
    from asterism.app.dialogs.params import NormalityParamsDialog
    monkeypatch.setattr(NormalityParamsDialog, "exec", lambda self: 1)
    w.show_sheet(w.project.tables[0])
    w._quick("normality")
    a = w.current

    def run(self):
        self.c_log.setChecked(True)
        return 1
    monkeypatch.setattr(NormalityParamsDialog, "exec", run)
    w.change_params()
    assert a.params["lognormal"] and [pg.title for pg in a.result.pages] == ["Normality", "Lognormality"]
    w.a_undo.trigger()
    assert not a.params["lognormal"]
