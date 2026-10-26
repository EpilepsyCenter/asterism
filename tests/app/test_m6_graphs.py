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
