"""Graph layout rules: Prism's whiskers, tie spreading, whisker on/off, centring."""

from __future__ import annotations

import numpy as np
import pytest

from asterism.app.graph.layout import box_stats, build, swarm


def test_tukey_whiskers_stop_at_data_values_within_1_5_iqr():
    x = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 30], float)
    s = box_stats(x, "tukey")
    q1 = np.percentile(x, 25, method="weibull")
    q3 = np.percentile(x, 75, method="weibull")
    assert (s["lo"], s["hi"]) == (q1, q3)
    assert s["whi"] == 9.0 and s["wlo"] == 1.0        # whisker ends are real values
    assert s["points"] == [30.0]                       # beyond the whisker → own point


def test_percentile_minmax_and_small_n_whiskers():
    x = np.arange(1, 101, dtype=float)
    s = box_stats(x, "p10")
    assert s["wlo"] == pytest.approx(np.percentile(x, 10, method="weibull"))
    assert s["whi"] == pytest.approx(np.percentile(x, 90, method="weibull"))
    assert len(s["points"]) == sum((x < s["wlo"]) | (x > s["whi"]))
    assert box_stats(x, "minmax")["points"] == []
    assert len(box_stats(x, "minmax_all")["points"]) == 100
    small = box_stats(np.array([1.0, 2.0, 10.0]), "tukey")   # n < 4: median and range
    assert (small["wlo"], small["whi"], small["points"]) == (1.0, 10.0, [])


def test_ties_spread_side_by_side_within_the_column():
    d, half = 6.0, 20.0
    xs = swarm([50.0] * 5, d, half)
    assert sorted(xs) == pytest.approx([-12, -6, 0, 6, 12])  # one row, touching, centred
    many = swarm([50.0] * 20, d, half)
    assert max(abs(x) for x in many) <= half + 1e-9          # never outside the column


def test_crowded_ties_do_not_squeeze_the_rest_of_the_cloud():
    d, half = 6.0, 20.0
    ys = [50.0] * 20 + [10.0, 90.0]                          # a big tie + two loners
    xs = swarm(ys, d, half)
    assert xs[20] == 0.0 and xs[21] == 0.0                   # loners stay centred


def _project_with_box(app):
    from asterism.analysis import engine
    from asterism.doc.sample import sample_project
    p = sample_project(engine)
    g = p.graphs[0]
    for c in (0, 1):
        g.spec.style(c).appearance = "box"
    return p, g


def _lines(g, app) -> int:
    from asterism.app.graph.export import svg_bytes
    return svg_bytes(g).count(b"<line") + svg_bytes(g).count(b"<polyline")


def test_box_whiskers_can_be_switched_off(app):
    p, g = _project_with_box(app)
    with_whiskers = _lines(g, app)
    for c in (0, 1):
        g.spec.style(c).errors = False
    assert _lines(g, app) == with_whiskers - 2 * 4          # 2 whiskers + 2 caps per box


def test_graph_stays_centred_when_a_title_is_dragged(app):
    from asterism.app.graph.view import GraphSheet
    from asterism.analysis import engine
    from asterism.doc.sample import sample_project
    p = sample_project(engine)
    g = p.graphs[0]
    gs = GraphSheet(g, p)
    c0 = gs.scene.sceneRect().center()
    gs._moved("graph-title", 80.0, -40.0)
    c1 = gs.scene.sceneRect().center()
    assert (c1.x(), c1.y()) == pytest.approx((c0.x(), c0.y()))
    moved = next(it for it in gs.items if it.el.id == "graph-title")
    assert gs.scene.sceneRect().contains(moved.el.bounds)    # still reachable by scrolling


def test_points_can_be_hidden_on_scatter_bar_and_box(app):
    from asterism.analysis import engine
    from asterism.app.graph.export import svg_bytes
    from asterism.doc.sample import sample_project
    p = sample_project(engine)
    g = p.graphs[0]
    circles = lambda: svg_bytes(g).count(b"<circle")
    assert circles() == 20                             # 10 + 10 points
    for c in (0, 1):
        g.spec.style(c).show_points = False
    assert circles() == 0                              # mean ± error only
    for c in (0, 1):
        g.spec.style(c).appearance = "bar"
    assert circles() == 0                              # bars without points
    for c in (0, 1):
        g.spec.style(c).appearance, g.spec.style(c).show_points = "box", True
    assert circles() == 20                             # box with all points
