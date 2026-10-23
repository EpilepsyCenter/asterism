"""Column graph types (M3b): violin, floating bars, one symbol, aligned, before-after."""

from __future__ import annotations

import numpy as np
import pytest

from asterism.core.qa import check_svg


def _graph(app, groups=None):
    from asterism.analysis import engine
    from asterism.doc.model import Project
    p = Project(engine)
    t = p.add_table(table_type="column")
    groups = groups or {"Before": [12, 15, 11, 18, 14, 16], "After": [15, 19, 13, 22, 17, 18],
                        "Washout": [13, 16, 12, 19, 15, 16]}
    for c, (name, vals) in enumerate(groups.items()):
        t.titles[c] = name
        for r, v in enumerate(vals):
            t.set(r, c, float(v), emit=False)
    t.changed.emit()
    return p, t, p.graphs[0]


@pytest.mark.parametrize("key", [k for k, _, _ in __import__(
    "asterism.app.dialogs.graph_type", fromlist=["COLUMN_PRESETS"]).COLUMN_PRESETS])
def test_every_graph_type_draws_and_passes_export_qa(app, key):
    from asterism.app.dialogs.graph_type import apply_preset
    from asterism.app.graph.export import svg_bytes
    from asterism.app.graph.layout import build, content_bounds
    p, t, g = _graph(app)
    g.set_spec(apply_preset(g.spec, key, t.used_columns()))
    els, _ = build(g)
    b = content_bounds(els)
    mm = 25.4 / 72
    rep = check_svg(svg_bytes(g), expected_w_mm=b.width() * mm, expected_h_mm=b.height() * mm,
                    expected_gids=["data-A", "data-B", "data-C", "y-axis"])
    assert rep.ok, (key, rep.summary())


def test_violin_is_truncated_at_the_data_extremes(app):
    from asterism.app.graph.layout import violin_curve
    x = np.array([1.0, 2.0, 2.5, 3.0, 7.0])
    for smooth in ("light", "medium", "heavy"):
        curve = violin_curve(x, smooth)
        assert curve[0][0] == 1.0 and curve[-1][0] == 7.0
        assert max(d for _, d in curve) == pytest.approx(1.0)
    light = np.array([d for _, d in violin_curve(x, "light")])
    heavy = np.array([d for _, d in violin_curve(x, "heavy")])
    assert np.std(np.diff(light)) > np.std(np.diff(heavy))       # heavier = smoother


def test_before_after_joins_each_row(app):
    from asterism.app.dialogs.graph_type import apply_preset
    from asterism.app.graph.export import svg_bytes
    p, t, g = _graph(app)
    g.set_spec(apply_preset(g.spec, "before_after", t.used_columns()))
    svg = svg_bytes(g).decode()
    assert 'id="connecting-lines"' in svg
    block = svg.split('id="connecting-lines"')[1].split("</g>")[0]
    assert block.count("<polyline") == 6                         # one line per subject


def test_aligned_points_share_one_x(app):
    from asterism.app.graph.layout import build
    p, t, g = _graph(app, {"A": [5, 5, 5, 6, 7]})
    st = g.spec.style(0)
    st.spread = "aligned"
    els, _ = build(g)
    ds = next(e for e in els if e.id == "data-A")
    from asterism.app.graph.canvas import SvgCanvas
    from PySide6.QtCore import QRectF
    cv = SvgCanvas(QRectF(0, 0, 500, 500))
    ds.draw(cv)
    xs = {part.split('cx="')[1].split('"')[0] for part in cv.parts if "<circle" in part}
    assert len(xs) == 1


def test_range_error_bars_span_min_to_max(app):
    from asterism.app.graph.layout import summarize
    from asterism.doc.spec import DataSetStyle
    s = summarize(np.array([1.0, 4.0, 9.0]), DataSetStyle(appearance="bar", line_at="mean_range"))
    assert (s["lo"], s["hi"], s["center"]) == (1.0, 9.0, pytest.approx(14 / 3))


def test_graph_type_dialog_applies_and_undoes(app, monkeypatch):
    from asterism.app.dialogs.graph_type import GraphTypeDialog
    p, t, g = _graph(app)
    dlg = GraphTypeDialog(g, p)
    assert dlg.gallery.count() >= 12 and not dlg.gallery.item(0).icon().isNull()
    dlg.gallery.setCurrentRow([dlg.gallery.item(i).data(0x0100) for i in range(dlg.gallery.count())].index("violin"))
    dlg.accept()
    assert all(g.spec.style(c).appearance == "violin" for c in t.used_columns())
    p.undo.undo()
    assert g.spec.style(0).appearance == "scatter"


@pytest.mark.parametrize("kind", ["box", "violin", "floating"])
def test_fill_does_not_add_a_bar_behind_shapes(app, kind):
    from asterism.app.graph.export import svg_bytes
    p, t, g = _graph(app)
    for c in t.used_columns():
        st = g.spec.style(c)
        st.appearance, st.bars = kind, False
    plain = svg_bytes(g).count(b"<rect")
    for c in t.used_columns():
        g.spec.style(c).bars = True
    assert svg_bytes(g).count(b"<rect") == plain             # filling adds no bar
