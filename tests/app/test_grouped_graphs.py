"""M4 graphs: grouped (side by side, separated, stacked, connected means, heat map) and
nested (subjects, pooled, SuperPlot), legends, and brackets from two-way comparisons."""

from __future__ import annotations

import pytest

from asterism.core.qa import check_svg


def _grouped(app, reps=4):
    from asterism.analysis import engine
    from asterism.doc.model import Project
    p = Project(engine)
    t = p.add_table(table_type="grouped", y_format="replicates", replicates=reps, example=True)
    return p, t, p.graphs[-1]


def _nested(app):
    from asterism.analysis import engine
    from asterism.doc.model import Project
    p = Project(engine)
    t = p.add_table(table_type="nested", example=True)
    return p, t, p.graphs[-1]


def _ids(g):
    from asterism.app.graph.layout import build
    return {e.id for e in build(g)[0]}


def _qa(g, gids):
    from asterism.app.graph.export import svg_bytes
    from asterism.app.graph.layout import build, content_bounds
    b = content_bounds(build(g)[0])
    mm = 25.4 / 72
    return check_svg(svg_bytes(g), expected_w_mm=b.width() * mm, expected_h_mm=b.height() * mm,
                     expected_gids=gids)


def test_grouped_graph_defaults_use_the_palette(app):
    p, t, g = _grouped(app)
    a, b = g.spec.style(0), g.spec.style(1)
    assert g.spec.palette and a.bar_fill != b.bar_fill
    assert a.appearance == "bar"
    assert {"data-A", "data-B", "legend", "x-axis", "y-axis"} <= _ids(g)


def _presets(tt):
    from asterism.app.dialogs.graph_type import PRESETS
    return [k for k, *_ in PRESETS[tt]]


@pytest.mark.parametrize("key", _presets("grouped"))
def test_every_grouped_type_draws_and_passes_export_qa(app, key):
    from asterism.app.dialogs.graph_type import apply_preset
    p, t, g = _grouped(app)
    g.set_spec(apply_preset(g.spec, key, t.used_columns()))
    gids = ["data-heat", "y-axis"] if key == "g_heat" else ["data-A", "data-B", "y-axis"]
    rep = _qa(g, gids)
    assert rep.ok, (key, rep.summary())


@pytest.mark.parametrize("key", _presets("nested"))
def test_every_nested_type_draws_and_passes_export_qa(app, key):
    from asterism.app.dialogs.graph_type import apply_preset
    p, t, g = _nested(app)
    g.set_spec(apply_preset(g.spec, key, t.used_columns()))
    rep = _qa(g, ["data-A", "data-B", "y-axis"])
    assert rep.ok, (key, rep.summary())


def test_interleaved_puts_data_sets_side_by_side_in_each_row(app):
    from asterism.app.graph.layout import plan_grouped
    p, t, g = _grouped(app)
    plan = plan_grouped(g, [0, 1], 20.0)
    assert len(plan.slots) == 6 and len(plan.labels) == 3      # 3 rows × 2 data sets
    xs = [sl.x for sl in plan.slots]
    assert xs == sorted(xs)
    assert [sl.column for sl in plan.slots] == [0, 1, 0, 1, 0, 1]
    assert plan.legend == [0, 1]


def test_separated_groups_by_data_set(app):
    from asterism.app.graph.layout import plan_grouped
    p, t, g = _grouped(app)
    g.spec.grouped_layout = "separated"
    plan = plan_grouped(g, [0, 1], 20.0)
    assert [sl.column for sl in plan.slots] == [0, 0, 0, 1, 1, 1]
    assert [s for _, s in plan.groups] == ["Wild type", "Knockout"]


def test_stacked_segments_sit_on_each_other(app):
    from asterism.app.graph.layout import build, plan_grouped
    p, t, g = _grouped(app)
    g.spec.grouped_layout = "stacked"
    plan = plan_grouped(g, [0, 1], 20.0)
    a, b = plan.slots[0], plan.slots[1]                 # row 1: Wild type, then Knockout
    assert a.x == b.x and b.base == pytest.approx(a.summary["center"])
    assert "error-bars" in _ids(g)
    g.spec.grouped_layout = "stacked_pct"
    plan = plan_grouped(g, [0, 1], 20.0)
    assert plan.slots[1].summary["center"] == pytest.approx(100.0)
    _, rng = build(g)
    assert (rng.vmin, rng.vmax) == (0.0, 100.0)


def test_connected_means_draw_one_line_per_data_set(app):
    from asterism.app.graph.layout import plan_grouped
    p, t, g = _grouped(app)
    g.spec.grouped_layout = "lines"
    plan = plan_grouped(g, [0, 1], 20.0)
    assert set(plan.lines) == {0, 1} and all(len(v) == 3 for v in plan.lines.values())
    assert plan.swatch == "line"


def test_heat_map_colours_follow_the_means(app):
    from asterism.app.graph.layout import _mix_hex
    p, t, g = _grouped(app)
    g.spec.grouped_layout = "heatmap"
    ids = _ids(g)
    assert {"data-heat", "legend", "x-axis", "y-axis"} <= ids
    assert _mix_hex("#000000", "#ffffff", 0.5) == "#808080"


def test_two_way_comparisons_become_brackets_within_rows(app):
    from asterism.doc.model import Analysis
    p, t, g = _grouped(app)
    p.add_analysis(Analysis("anova2", t, [0, 1], {"compare": "rows", "method": "sidak"}))
    ids = _ids(g)
    assert {"bracket-A1-B1", "bracket-A2-B2", "bracket-A3-B3"} <= ids


def test_multiple_t_tests_become_brackets(app):
    from asterism.doc.model import Analysis
    p, t, g = _grouped(app)
    p.add_analysis(Analysis("multiple_t", t, [0, 1], {"correction": "holm_sidak"}))
    assert any(i.startswith("bracket-A") for i in _ids(g))


def test_nested_layouts(app):
    from asterism.app.graph.layout import plan_nested
    p, t, g = _nested(app)
    cols = t.used_columns()
    plan = plan_nested(g, cols, 60.0)                    # subjects side by side
    assert len(plan.slots) == t.width() * len(cols)
    assert len({sl.point_colors[0] for sl in plan.slots}) == len(plan.slots)   # one colour each
    g.spec.nested_layout = "superplot"
    plan = plan_nested(g, cols, 60.0)
    assert len(plan.slots) == len(cols)
    assert all(len(sl.marks) == t.width() for sl in plan.slots)
    g.spec.nested_layout = "pooled"
    plan = plan_nested(g, cols, 60.0)
    assert all(len(sl.point_colors) == len(sl.summary["points"]) for sl in plan.slots)


def test_nested_t_test_bracket(app):
    from asterism.doc.model import Analysis
    p, t, g = _nested(app)
    p.add_analysis(Analysis("nested", t, [0, 1], {}))
    assert "bracket-A-B" in _ids(g)


def test_new_spec_fields_round_trip(app):
    from asterism.doc.spec import spec_from_dict, spec_to_dict
    p, t, g = _grouped(app)
    g.spec.grouped_layout, g.spec.show_legend, g.spec.heat_high = "lines", False, "#123456"
    s = spec_from_dict(spec_to_dict(g.spec))
    assert (s.grouped_layout, s.show_legend, s.heat_high, s.palette) == ("lines", False, "#123456", True)
    assert spec_from_dict({}).grouped_layout == "interleaved"           # old files


def test_crowded_x_labels_tilt(app):
    from asterism.app.graph.layout import build
    p, t, g = _grouped(app)
    for r, name in enumerate(["A very long row title", "Another long row title", "Third long title"]):
        t.set(r, "row", name)
    g.spec.grouped_layout = "separated"
    els, _ = build(g)
    x = next(e for e in els if e.id == "x-axis")
    assert x.bounds.height() > 40                       # tilted labels take vertical room


def test_format_graph_arrangement_section(app):
    from asterism.app.dialogs.format_graph import FormatGraphDialog
    p, t, g = _grouped(app)
    dlg = FormatGraphDialog(g, p, "arrangement")
    assert dlg.current_section() == "arrangement"
    dlg.arrangement.setCurrentIndex([k for _, k in __import__(
        "asterism.app.dialogs.format_graph", fromlist=["x"]).GROUPED_ARRANGEMENTS].index("stacked"))
    dlg.legend.setChecked(False)
    dlg.apply()
    assert g.spec.grouped_layout == "stacked" and not g.spec.show_legend
    p.undo.undo()
    assert g.spec.grouped_layout == "interleaved"


def test_graph_type_gallery_offers_the_tables_types(app):
    from asterism.app.dialogs.graph_type import GraphTypeDialog
    for make, first in ((_grouped, "g_bars"), (_nested, "n_subjects")):
        p, t, g = make(app)
        dlg = GraphTypeDialog(g, p)
        assert dlg.chosen() == first
        dlg.gallery.setCurrentRow(dlg.gallery.count() - 1)
        dlg.accept()
        assert p.undo.can_undo()


def test_grouped_graph_sheet_is_not_a_placeholder(app):
    from asterism.app.graph.view import GraphSheet
    p, t, g = _grouped(app)
    w = GraphSheet(g, p)
    assert w.is_graphable() and w.items


def test_settings_dialogs_offer_the_missing_values_choice(app):
    from asterism.app.dialogs.params import AnovaParamsDialog
    from asterism.app.dialogs.params_grouped import TwoWayParamsDialog
    d = TwoWayParamsDialog({"design": "rm_rows", "rm_method": "mixed"})
    assert d.params()["rm_method"] == "mixed"
    from asterism.analysis import engine
    from asterism.doc.model import Project
    p = Project(engine)
    t = p.add_table(table_type="column", example=True)
    d1 = AnovaParamsDialog({"design": "rm"}, t, [0, 1, 2])
    assert d1.params()["rm_method"] == "auto"
