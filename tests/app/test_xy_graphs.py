"""M5 graphs and dialogs: XY graphs (points, lines, replicates, spaghetti, area, XY bars),
fitted curves with bands, log X axis, graphs of frequency distributions, XY settings."""

from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtCore import Qt

from asterism.core.qa import check_svg


def _dose(app):
    from asterism.analysis import engine, models
    from asterism.doc.model import Project
    p = Project(engine)
    t = p.add_table(table_type="xy", y_format="replicates", replicates=3, example=False)
    rng = np.random.default_rng(3)
    f4 = models.BY_KEY["agonist_4"].f
    for r, x in enumerate(np.arange(-9, -4.5, 0.5)):
        t.set(r, "x", float(x), emit=False)
        for k in range(3):
            t.set(r, t.flat(0, k), float(f4(x, 0, 100, -7, 1) + rng.normal(0, 3)), emit=False)
            t.set(r, t.flat(1, k), float(f4(x, 0, 80, -6.3, 1) + rng.normal(0, 3)), emit=False)
    t.titles[:2] = ["Agonist", "With antagonist"]
    t.changed.emit()
    return p, t, p.graphs[-1]


def _qa(g, gids):
    from asterism.app.graph.export import svg_bytes
    from asterism.app.graph.layout import build, content_bounds
    b = content_bounds(build(g)[0])
    mm = 25.4 / 72
    return check_svg(svg_bytes(g), expected_w_mm=b.width() * mm, expected_h_mm=b.height() * mm,
                     expected_gids=gids)


def _ids(g):
    from asterism.app.graph.layout import build
    return {e.id for e in build(g)[0]}


@pytest.mark.parametrize("key", [k for k, *_ in __import__(
    "asterism.app.dialogs.graph_type", fromlist=["XY_PRESETS"]).XY_PRESETS])
def test_every_xy_type_draws_and_passes_export_qa(app, key):
    from asterism.app.dialogs.graph_type import apply_preset
    p, t, g = _dose(app)
    g.set_spec(apply_preset(g.spec, key, t.used_columns()))
    rep = _qa(g, ["data-A", "data-B", "x-axis", "y-axis"])
    assert rep.ok, (key, rep.summary())


def test_xy_graph_defaults(app):
    from asterism.app.graph.view import GraphSheet
    p, t, g = _dose(app)
    assert g.spec.x.ticks_dir == "out" and g.spec.palette
    assert {"data-A", "data-B", "legend", "x-title"} <= _ids(g)
    assert GraphSheet(g, p).is_graphable()


def test_fitted_curves_and_bands_are_drawn(app):
    from asterism.app.graph.layout import build
    from asterism.doc.model import Analysis
    p, t, g = _dose(app)
    p.add_analysis(Analysis("nonlin", t, [0, 1], {"model": "agonist_4", "bands": "confidence"}))
    els, rng = build(g)
    ids = {e.id for e in els}
    assert {"fit-A", "fit-B"} <= ids
    assert _qa(g, ["fit-A", "fit-B", "data-A"]).ok
    p.add_analysis(Analysis("linreg", t, [0], {"graph": False}))
    assert "fit-A-1" not in {e.id for e in build(g)[0]}      # the line is not drawn when asked not to


def test_log_x_axis(app):
    from asterism.app.graph.xy_layout import x_range
    from asterism.doc.spec import GraphSpec
    s = GraphSpec()
    s.x.scale = "log10"
    r = x_range(s, [0.3, 7.0, 120.0])
    assert (r.vmin, r.vmax) == (0.1, 1000.0)


def test_frequency_distribution_graph(app):
    from asterism.analysis import engine
    from asterism.app.graph.layout import build
    from asterism.doc.model import Analysis, Project
    p = Project(engine)
    t = p.add_table(table_type="column", example=True)
    a = p.add_analysis(Analysis("frequency", t, t.used_columns(), {}))
    g = p.new_result_graph(a)
    p.add_sheets([g], "graph")
    assert g.spec.default_style.appearance == "bar"
    els, _ = build(g)
    assert {"data-A", "data-B", "x-axis"} <= {e.id for e in els}
    assert _qa(g, ["data-A", "x-axis"]).ok


def test_main_window_creates_the_frequency_graph(app):
    from asterism.app.main_window import MainWindow
    from asterism.analysis import engine
    from asterism.doc.model import Analysis, Project
    p = Project(engine)
    t = p.add_table(table_type="column", example=True)
    w = MainWindow(p)
    a = Analysis("frequency", t, t.used_columns(), {})
    p.add_analysis(a)
    w._result_graph(a)
    assert any(g.source is a for g in p.graphs)
    p.mark_saved()
    w.close()


def test_format_graph_xy_options(app):
    from asterism.app.dialogs.format_graph import FormatGraphDialog
    p, t, g = _dose(app)
    dlg = FormatGraphDialog(g, p, "style")
    dlg.connect_line.setChecked(True)
    dlg.fill_area.setChecked(True)
    dlg.x_scale.setCurrentIndex(0)
    dlg.x_title.setText("log[agonist]")
    dlg.apply()
    assert all(g.spec.style(c).connect and g.spec.style(c).fill for c in t.used_columns())
    assert g.spec.x.title == "log[agonist]"


def test_nonlinear_settings_dialog_round_trip(app):
    from asterism.app.dialogs.params_xy import NonlinParamsDialog
    d = NonlinParamsDialog({"model": "michaelis_menten", "constraints": {"Km": {"mode": "constant", "value": 2.0}},
                            "initial": {"Vmax": 9.0}, "ci_method": "asymptotic"}, ncols=2)
    p = d.params()
    assert p["model"] == "michaelis_menten"
    assert p["constraints"] == {"Km": {"mode": "constant", "value": 2.0}}
    assert p["initial"] == {"Vmax": 9.0} and p["ci_method"] == "asymptotic"
    d.families.setCurrentRow(d.families.count() - 1)               # user-defined
    d.equation.setText("Y = A*exp(-K*X)")
    d._model_changed()
    p2 = d.params()
    assert p2["model"] == "user" and d.cons.rowCount() == 2


def test_other_xy_settings_dialogs(app):
    from asterism.app.dialogs.params import OutlierParamsDialog
    from asterism.app.dialogs.params_xy import AucParamsDialog, CorrelationParamsDialog, LinRegParamsDialog
    assert LinRegParamsDialog({"bands": "prediction"}).params()["bands"] == "prediction"
    assert CorrelationParamsDialog({"method": "spearman"}).params()["method"] == "spearman"
    assert AucParamsDialog({"baseline": 5.0}).params()["baseline"] == 5.0
    assert OutlierParamsDialog(None).params()["method"] == "rout"


def test_excluded_x_is_struck_through(app):
    from asterism.app.table_view import TableModel
    p, t, g = _dose(app)
    t.set_excluded([(0, "x")], True)
    assert t.is_excluded(0, "x") and t.x_value(0) is None


def test_ticks_stop_at_axis_end(app):
    """An axis ending between ticks (0 to 5.5 every 1) gets no tick past its end."""
    from asterism.app.graph.layout import AxisRange, YMap
    from asterism.doc.spec import AxisSpec
    ym = YMap(AxisSpec(auto=False, vmin=0, vmax=5.5, interval=1), AxisRange(0, 5.5, 1), 100.0)
    assert ym.majors() == [0, 1, 2, 3, 4, 5]


def test_fitted_curve_style_and_hiding(app):
    """Format Graph › Style › Fitted curve: hide a fit on this graph only, give it its own
    colour, thickness and style, and draw bands shaded or not at all."""
    from asterism.analysis import engine
    from asterism.app.dialogs.format_graph import FormatGraphDialog
    from asterism.app.graph.layout import build
    from asterism.app.graph.xy_layout import fit_columns
    from asterism.doc.model import Analysis, Project
    p = Project(engine)
    t = p.add_table(table_type="xy", example=True)
    g = p.graphs[-1]
    p.add_analysis(Analysis("linreg", t, t.used_columns(), {"bands": "confidence"}))
    fits = fit_columns(g)
    assert fits and set(fits) == set(t.used_columns())
    c = next(iter(fits))
    ids = lambda: {e.id for e in build(g)[0]}
    assert any(i.startswith("fit-") for i in ids())
    d = FormatGraphDialog(g, p, "style", c)
    assert d.fit_box.isVisibleTo(d)
    d.curve_same.setChecked(False)
    d.curve_color.set_color("#d62728")
    d.curve_color.colorChanged.emit("#d62728")
    d.band_style.setCurrentIndex(d.band_style.findData("shaded"))
    d.apply()
    st = g.spec.style(c)
    assert st.curve_color == "#d62728" and st.band_style == "shaded"
    calls = []

    class Rec:
        def __getattr__(self, name):
            return lambda *a, **k: calls.append((name, a, k))
    fit_el = next(e for e in build(g)[0] if e.id.startswith(f"fit-{chr(65 + c)}"))
    fit_el.draw(Rec())
    assert any(n == "polygon" and k.get("opacity", 1) < 1 for n, a, k in calls)      # shaded band
    assert any(n == "polyline" and a[1] == "#d62728" for n, a, k in calls)           # red curve
    d2 = FormatGraphDialog(g, p, "datasets")
    it = d2.fit_list.item(0)
    it.setCheckState(Qt.Unchecked)
    d2.apply()
    hidden = it.data(Qt.UserRole)
    assert not g.spec.style(hidden).curve_show
    assert f"fit-{chr(65 + hidden)}" not in ids()
