"""M7 in the app: result tables nested in the sidebar, analysable from the Analyze dialog,
graphed automatically; transform settings dialogs."""

from __future__ import annotations


def _project():
    from asterism.analysis import engine
    from asterism.doc.model import Analysis, Project
    p = Project(engine)
    t = p.add_table(table_type="xy", y_format="replicates", replicates=3, example=True)
    tr = p.add_analysis(Analysis("transform", t, [0, 1], {"y": "log10"}))
    return p, t, tr


def test_sidebar_nests_chains(app):
    from PySide6.QtCore import Qt
    from asterism.analysis import engine  # noqa: F401
    from asterism.app.main_window import MainWindow
    from asterism.doc.model import Analysis
    p, t, tr = _project()
    out = tr.output_table()
    lr = p.add_analysis(Analysis("linreg", out, out.used_columns(), {}))
    w = MainWindow(p)
    w.sidebar.rebuild()
    items = {it.data(0, Qt.UserRole): it for it in w.sidebar._items()}
    assert items[lr].parent() is items[tr]                # the regression sits under the transform
    assert items[tr].parent() is items[t]
    p.mark_saved()
    w.close()


def test_main_window_graphs_results_and_analyses_them(app):
    from asterism.app.main_window import MainWindow
    p, t, tr = _project()
    w = MainWindow(p)
    w._result_graph(tr)
    g = next(gr for gr in p.graphs if gr.source is tr)
    assert g.table is tr.output_table() and g.home is t
    w.show_sheet(tr)
    assert w._family_table() is tr.output_table()          # Analyze from the results → the result table
    w.show_sheet(g)
    assert w._family_table() is tr.output_table()
    p.mark_saved()
    w.close()


def test_analyze_dialog_lists_result_tables(app):
    from asterism.app.dialogs.analyze import AnalyzeDialog
    p, t, tr = _project()
    d = AnalyzeDialog(p, tr.output_table())
    names = [d.table_combo.itemText(i) for i in range(d.table_combo.count())]
    assert f"Results: {tr.name}" in names
    assert d.table_combo.currentData() is tr.output_table()


def test_transform_settings_dialogs(app):
    from asterism.app.dialogs.params_transforms import (BaselineParamsDialog, NormalizeParamsDialog,
                                                        ObservedExpectedParamsDialog, PruneParamsDialog,
                                                        SmoothParamsDialog, TransformParamsDialog)
    p, t, tr = _project()
    d = TransformParamsDialog({"y": "user", "equation": "Y = ln(Y)", "x": "log10"}, has_x=True)
    assert d.params()["y"] == "user" and d.eq.isEnabled() and d.params()["x"] == "log10"
    assert NormalizeParamsDialog({"hundred": "first"}).params()["hundred"] == "first"
    b = BaselineParamsDialog({"source": "rows", "rows": 3}, t, [0, 1])
    assert b.params()["rows"] == 3 and not b.base.isEnabled()
    assert PruneParamsDialog({"mode": "every", "n": 4}).params()["n"] == 4
    assert SmoothParamsDialog({"op": "integral", "start": 2.0}).params()["start"] == 2.0
    assert ObservedExpectedParamsDialog(None).params()["expected"] == "equal"


def test_result_graph_draws(app):
    from asterism.app.graph.layout import build
    p, t, tr = _project()
    g = p.new_result_graph(tr)
    p.add_sheets([g], "graph")
    assert {"data-A", "data-B"} <= {e.id for e in build(g)[0]}


def test_result_graph_shows_fits_of_the_result_table(app):
    from asterism.app.graph.layout import build
    from asterism.doc.model import Analysis
    p, t, tr = _project()
    g = p.new_result_graph(tr)
    p.add_sheets([g], "graph")
    out = tr.output_table()
    p.add_analysis(Analysis("linreg", out, out.used_columns(), {}))
    assert {"fit-A", "fit-B"} <= {e.id for e in build(g)[0]}
    assert g.spec.x.title == p.graphs[0].spec.x.title           # copied from the data's own graph
