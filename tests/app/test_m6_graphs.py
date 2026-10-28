"""M6 graphs and dialogs: contingency bars, pie / donut / 100% bars, Kaplan-Meier curves."""

from __future__ import annotations

import numpy as np
import pytest

from asterism.core.qa import check_svg


def _project(tt):
    from asterism.analysis import engine
    from asterism.doc.model import Project
    p = Project(engine)
    t = p.add_table(table_type=tt, example=True)
    if tt == "survival":
        rng = np.random.default_rng(4)
        for r in range(30):
            g = r % 2
            t.set(r, "x", float(round(rng.exponential(10 if g == 0 else 20), 1)), emit=False)
            t.set(r, t.flat(g), 0.0 if rng.random() < 0.25 else 1.0, emit=False)
        t.changed.emit()
    return p, t, p.graphs[-1]


def _qa(g, gids):
    from asterism.app.graph.export import svg_bytes
    from asterism.app.graph.layout import build, content_bounds
    b = content_bounds(build(g)[0])
    mm = 25.4 / 72
    return check_svg(svg_bytes(g), expected_w_mm=b.width() * mm, expected_h_mm=b.height() * mm, expected_gids=gids)


def _presets(tt):
    from asterism.app.dialogs.graph_type import PRESETS
    return [(tt, k) for k, *_ in PRESETS[tt]]


@pytest.mark.parametrize("tt,key", _presets("contingency") + _presets("parts") + _presets("survival"))
def test_every_m6_graph_type_draws_and_passes_export_qa(app, tt, key):
    from asterism.app.dialogs.graph_type import apply_preset
    p, t, g = _project(tt)
    g.set_spec(apply_preset(g.spec, key, t.used_columns()))
    gids = ["data-heat"] if key == "c_heat" else ["data-A"]
    rep = _qa(g, gids)
    assert rep.ok, (key, rep.summary())


def test_contingency_graph_defaults(app):
    from asterism.app.graph.layout import build
    p, t, g = _project("contingency")
    assert g.spec.y.title == "Number of subjects" and g.spec.default_style.appearance == "bar"
    ids = {e.id for e in build(g)[0]}
    assert {"data-A", "data-B", "legend"} <= ids


def test_pie_has_a_slice_per_row_and_a_legend(app):
    from asterism.app.graph.layout import build
    from asterism.app.graph.parts_survival_layout import ink_on
    p, t, g = _project("parts")
    els, _ = build(g)
    assert {"data-A", "legend"} <= {e.id for e in els}
    assert ink_on("#4f4f4f") == "#ffffff" and ink_on("#fee391") == "#000000"


def test_survival_graph_options(app):
    from asterism.app.graph.layout import build
    p, t, g = _project("survival")
    for ci in ("none", "dashed", "shaded"):
        g.spec.surv_ci = ci
        els, rng = build(g)
        assert {"data-A", "data-B", "x-axis", "y-axis", "legend"} <= {e.id for e in els}
        assert (rng.vmin, rng.vmax) == (0.0, 100.0)
    g.spec.surv_percent = False
    assert build(g)[1].vmax == 1.0


def test_format_graph_arrangement_for_new_types(app):
    from asterism.app.dialogs.format_graph import FormatGraphDialog
    p, t, g = _project("parts")
    d = FormatGraphDialog(g, p, "arrangement")
    d.arrangement.setCurrentIndex(1)                      # donut
    d.apply()
    assert g.spec.parts_layout == "donut"
    p2, t2, g2 = _project("survival")
    d2 = FormatGraphDialog(g2, p2, "arrangement")
    d2.surv_y.setCurrentIndex(2)                          # percent deaths
    d2.surv_ci.setCurrentIndex(2)
    d2.apply()
    assert g2.spec.surv_death and g2.spec.surv_ci == "shaded" and g2.spec.y.title == "Percent death"


def test_m6_settings_dialogs(app):
    from asterism.app.dialogs.params_counts import (ContingencyParamsDialog, FractionParamsDialog,
                                                    SurvivalParamsDialog)
    d = ContingencyParamsDialog({"effect": "or", "or_ci": "woolf"}, True)
    assert d.params()["effect"] == "or" and d.params()["or_ci"] == "woolf"
    assert ContingencyParamsDialog(None, False).params()["test"] == "chi2"
    assert SurvivalParamsDialog({"ci": "symmetric"}).params()["ci"] == "symmetric"
    assert FractionParamsDialog({"of": "grand"}).params()["of"] == "grand"


def test_graph_type_gallery_for_new_types(app):
    from asterism.app.dialogs.graph_type import GraphTypeDialog
    for tt, first in (("contingency", "c_bars"), ("parts", "p_pie"), ("survival", "s_steps")):
        p, t, g = _project(tt)
        assert GraphTypeDialog(g, p).chosen() == first


def test_parts_slices_colours_borders_total_and_order(app):
    """Format Graph › Slices: each slice's colour and pull-out, borders, legend contents,
    total, order; saved and reloaded with the project."""
    from asterism.app.dialogs.format_graph import FormatGraphDialog
    from asterism.app.graph.layout import build
    from asterism.app.graph.parts_survival_layout import parts_colors, parts_rows
    from asterism.doc.spec import spec_from_dict, spec_to_dict
    p, t, g = _project("parts")
    d = FormatGraphDialog(g, p, "arrangement")
    r0 = sorted(d.slice_ctl)[0]
    btn, pull, _ = d.slice_ctl[r0]
    btn.set_color("#123456")
    btn.colorChanged.emit("#123456")
    pull.setValue(15)
    d.outer_on.setChecked(True)
    d.total_on.setChecked(True)
    d.leg_bits["legend_percent"].setChecked(True)
    d.parts_order.setCurrentIndex(1)
    d.apply()
    P = g.spec.parts
    assert P["colors"] == {str(r0): "#123456"} and P["explode"] == {str(r0): 15.0}
    assert P["outer"] and P["total"] and P["legend_percent"] and P["reverse"]
    assert parts_colors(g)[r0] == "#123456" and parts_rows(g)[0] != r0       # reversed
    assert "Style" not in [d.sections.item(i).text() for i in range(d.sections.count())]
    build(g)                                               # draws without error
    back = spec_from_dict(spec_to_dict(g.spec))
    assert back.parts["colors"] == {str(r0): "#123456"} and back.parts["reverse"]


def test_nested_subject_colours(app):
    """Nested graphs: colour by subject (palette, edited, restart per group) or by data set,
    subject-mean size; saved with the project."""
    from asterism.app.dialogs.format_graph import FormatGraphDialog
    from asterism.app.graph.layout import plan_nested, subject_color_keys
    from asterism.doc.spec import spec_from_dict, spec_to_dict
    p, t, g = _project("nested")
    g.spec.nested_layout = "superplot"
    cols = t.used_columns()
    keys = subject_color_keys(t, cols, restart=True)
    assert [k for c, sub, k in keys if c == cols[1]][0] == 0       # starts again in the second group
    d = FormatGraphDialog(g, p, "arrangement")
    d.n_restart.setCurrentIndex(1)
    k0, b0 = d.n_buttons[0]
    b0.set_color("#ff0000")
    b0.colorChanged.emit("#ff0000")
    d.n_mean.setValue(3.0)
    d.apply()
    N = g.spec.nested
    assert N["restart"] and N["colors"][k0] == "#ff0000" and N["mean_size"] == 3.0
    plan = plan_nested(g, cols, 40.0)
    assert all(sl.marks[0][1] == "#ff0000" for sl in plan.slots)    # subject 1 red in every group
    g.spec.nested["color_by"] = "dataset"
    g.spec.style(cols[0]).symbol_color = "#00aa00"
    plan = plan_nested(g, cols, 40.0)
    assert set(plan.slots[0].point_colors) == {"#00aa00"}
    assert spec_from_dict(spec_to_dict(g.spec)).nested["mean_size"] == 3.0


def test_data_set_order(app):
    """Format Graph › Show and order: drag or move data sets to change their order on the
    graph (left to right) and in the legend; saved with the project."""
    from asterism.app.dialogs.format_graph import FormatGraphDialog
    from asterism.app.graph.layout import build
    from asterism.doc.spec import spec_from_dict, spec_to_dict
    p, t, g = _project("grouped")
    cols = t.used_columns()
    assert len(cols) >= 2
    d = FormatGraphDialog(g, p, "datasets")
    d.ds_list.setCurrentRow(len(cols) - 1)
    for _ in range(len(cols) - 1):
        d._move_ds(-1)                                   # last data set to the front
    d.apply()
    assert g.spec.order[0] == cols[-1]
    assert g.spec.shown(cols)[0] == cols[-1]
    els, _ = build(g)
    xs = {e.meta["column"]: e.bounds.center().x() for e in els if e.kind == "dataset"}
    assert xs[cols[-1]] < xs[cols[0]]                    # drawn first, on the left
    assert spec_from_dict(spec_to_dict(g.spec)).order == g.spec.order
    d2 = FormatGraphDialog(g, p, "datasets")
    d2._table_order()
    d2.apply()
    assert g.spec.order == []                            # back to the table's order
