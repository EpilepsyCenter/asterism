"""M9 graph polish."""

from __future__ import annotations

import numpy as np
import pytest


def _anova_graph(seed=1):
    from asterism.analysis import engine
    from asterism.doc.model import Analysis, Project
    p = Project(engine)
    t = p.add_table(table_type="column", example=False)
    rng = np.random.default_rng(seed)
    for c, m in enumerate((10, 14, 11, 18)):
        t.titles[c] = ["Vehicle", "Low", "Mid", "High"][c]
        for r in range(6):
            t.set(r, c, float(m + rng.normal(0, 1.5)), emit=False)
    t.changed.emit()
    a = p.add_analysis(Analysis("anova1", t, [0, 1, 2, 3], {}))
    return p, t, p.graphs[0], a


def _brackets(g):
    from asterism.app.graph.layout import build
    return {e.id for e in build(g)[0] if e.kind == "bracket"}


# ---------------------------------------------------------------------------
# Significance brackets
# ---------------------------------------------------------------------------

def test_star_levels_and_labels():
    from asterism.app.graph.layout import bracket_label, star_label
    from asterism.doc.spec import default_sig
    sig = default_sig()
    assert [star_label(p, sig) for p in (0.2, 0.04, 0.009, 0.0009, 0.00001)] == ["ns", "*", "**", "***", "****"]
    sig["levels"] = "three"
    assert star_label(0.00001, sig) == "***"
    sig.update(levels="custom", cuts=[0.1, 0.05])
    assert [star_label(p, sig) for p in (0.2, 0.07, 0.01)] == ["ns", "*", "**"]
    sig = default_sig()
    sig["label"] = "p"
    assert bracket_label(0.01234, sig) == "P = 0.0123" and bracket_label(0.00001, sig) == "P < 0.0001"
    sig["label"] = "both"
    assert bracket_label(0.003, sig) == "**  P = 0.0030"


def test_which_comparisons(app):
    p, t, g, a = _anova_graph()
    sig_all = {(ca, cb) for ca, cb, pv in a.result.comparisons}
    signif = {(ca, cb) for ca, cb, pv in a.result.comparisons if pv < 0.05}
    assert len(_brackets(g)) == len(signif)
    g.spec.sig["which"] = "all"
    assert len(_brackets(g)) == len(sig_all)
    g.spec.sig.update(which="control", control=0)
    assert all("-A-" in b or b.startswith("bracket-A-") or b.endswith("-A") for b in _brackets(g))
    g.spec.sig["which"] = "none"
    assert not _brackets(g)
    g.spec.sig["which"] = "all"
    one = sorted(_brackets(g))[0]
    g.spec.sig["hidden"] = [one]
    assert one not in _brackets(g)


def test_two_group_ns_and_line_shape(app):
    from asterism.analysis import engine
    from asterism.app.graph.layout import build
    from asterism.doc.model import Analysis, Project
    p = Project(engine)
    t = p.add_table(table_type="column", example=False)
    for r, (a_, b_) in enumerate(zip([1, 2, 3, 4, 5], [2, 1, 4, 3, 5])):
        t.set(r, 0, float(a_))
        t.set(r, 1, float(b_))
    p.add_analysis(Analysis("ttest", t, [0, 1], {}))
    g = p.graphs[0]
    assert _brackets(g) == {"bracket-A-B"}
    g.spec.sig["ns_single"] = False
    assert not _brackets(g)
    g.spec.sig.update(ns_single=True, shape="line", color="#ff0000", width=2.0)
    from asterism.app.graph.export import svg_bytes
    svg = svg_bytes(g).decode()
    assert 'stroke="#ff0000" stroke-width="2"' in svg


def test_old_files_keep_their_significance_choices():
    from asterism.doc.spec import spec_from_dict
    s = spec_from_dict({"p_format": "exact", "brackets_ns": True})
    assert s.sig["label"] == "p" and s.sig["which"] == "all"
    assert spec_from_dict({}).sig["which"] == "significant"


def test_format_graph_significance_page_and_hiding_from_the_graph(app):
    from asterism.app.dialogs.format_graph import FormatGraphDialog
    from asterism.app.graph.view import GraphSheet
    p, t, g, a = _anova_graph()
    d = FormatGraphDialog(g, p, "significance")
    d.sig_label.setCurrentIndex(1)                         # P values
    d.sig_shape.setCurrentIndex(1)                         # plain line
    d.sig_list.item(0).setCheckState(__import__("PySide6.QtCore", fromlist=["Qt"]).Qt.Unchecked)
    d.apply()
    assert g.spec.sig["label"] == "p" and g.spec.sig["shape"] == "line" and len(g.spec.sig["hidden"]) == 1
    gs = GraphSheet(g, p)
    gs._show_all_brackets()
    assert g.spec.sig["hidden"] == []
    gs._hide_bracket("bracket-A-B")
    assert g.spec.sig["hidden"] == ["bracket-A-B"]
    p.undo.undo()
    assert g.spec.sig["hidden"] == []


# ---------------------------------------------------------------------------
# Colour schemes and applying formatting to other graphs
# ---------------------------------------------------------------------------

def test_colour_schemes_colour_data_sets_in_order(app):
    from asterism.app.graph.formatting import SCHEMES, apply_scheme
    p, t, g, a = _anova_graph()
    new = apply_scheme(g.spec, "greys", [0, 1, 2, 3])
    pairs = SCHEMES["greys"][1]
    assert [(new.style(c).bar_fill, new.style(c).symbol_color) for c in range(4)] == pairs[:4]
    two = apply_scheme(g.spec, "black", [0, 1, 2])
    assert two.style(2).bar_fill == two.style(0).bar_fill        # schemes repeat


def test_main_window_scheme_and_copy_formatting(app, monkeypatch):
    from asterism.app.dialogs.graph_type import CopyFormattingDialog
    from asterism.app.main_window import MainWindow
    p, t, g, a = _anova_graph()
    t2 = p.add_table(table_type="column", example=True)
    g2 = next(x for x in p.graphs if x.table is t2)
    w = MainWindow(p)
    w.show_sheet(g)
    w.apply_scheme("viridis")
    assert g.spec.style(0).symbol_color == "#440154"
    g.spec.y_len_mm, g.spec.sig["shape"] = 77.0, "line"
    g.spec.y.vmax = 123.0
    g2_before = g2.spec.y.vmax

    def fake_exec(d):
        d.targets.item(0).setCheckState(__import__("PySide6.QtCore", fromlist=["Qt"]).Qt.Checked)
        return True
    monkeypatch.setattr(CopyFormattingDialog, "exec", fake_exec)
    w.copy_formatting()
    assert g2.spec.y_len_mm == 77.0 and g2.spec.sig["shape"] == "line"
    assert g2.spec.style(0).symbol_color == "#440154"
    assert g2.spec.y.vmax == g2_before                            # ranges aren't copied by default
    p.undo.undo()                                                 # one step for all target graphs
    assert g2.spec.y_len_mm != 77.0
    p.mark_saved()
    w.close()


# ---------------------------------------------------------------------------
# Right Y axis, axis breaks, grid lines and extra ticks
# ---------------------------------------------------------------------------

def _xy_two_units():
    from asterism.analysis import engine
    from asterism.doc.model import Project
    p = Project(engine)
    t = p.add_table(table_type="xy", example=False)
    for r in range(8):
        t.set(r, "x", float(r), emit=False)
        t.set(r, 0, 20.0 + r, emit=False)
        t.set(r, 1, 1000.0 + 50 * r, emit=False)
    t.changed.emit()
    return p, t, p.graphs[0]


def test_right_y_axis_on_xy_graphs(app):
    from asterism.app.graph.layout import build
    p, t, g = _xy_two_units()
    els, rng = build(g)
    assert "y2-axis" not in {e.id for e in els} and rng.vmax >= 1350
    g.spec.style(1).axis = "right"
    g.spec.y2.title = "Counts"
    els, rng = build(g)
    by = {e.id: e for e in els}
    assert rng.vmax < 100                                         # the left axis fits its own data
    assert by["y2-axis"].meta["range"].vmax >= 1350
    assert by["y2-title"].bounds.left() > by["y2-axis"].bounds.left()
    data_b = by["data-B"].bounds
    assert data_b.top() < 40                                     # the right data fill the height too


def test_right_y_axis_on_column_graphs_and_legend_choice(app):
    from asterism.app.graph.layout import build
    p, t, g, a = _anova_graph()
    g.spec.style(3).axis = "right"
    els, rng = build(g)
    by = {e.id: e for e in els}
    assert "y2-axis" in by and by["y2-axis"].bounds.left() > by["data-C"].bounds.right()
    # legend: one data set can be left out
    from asterism.analysis import engine
    from asterism.doc.model import Project
    p2 = Project(engine)
    t2 = p2.add_table(table_type="grouped", y_format="replicates", replicates=3, example=True)
    g2 = p2.graphs[0]
    leg = lambda: next(e for e in build(g2)[0] if e.id == "legend").bounds.height()
    full = leg()
    g2.spec.style(0).legend = False
    assert leg() < full


def test_axis_break_maps_two_segments():
    from asterism.app.graph.layout import AxisRange, YMap
    from asterism.doc.spec import AxisSpec
    ax = AxisSpec(brk={"on": True, "low_to": 10, "high_from": 400, "split": 0.5, "gap": 10})
    m = YMap(ax, AxisRange(0, 600, 100), 210.0)
    assert m(0) == pytest.approx(210) and m(600) == pytest.approx(0)
    assert m(10) == pytest.approx(110) and m(400) == pytest.approx(100)          # 10-point gap between
    assert m.segments() == [(110.0, 210.0), (0.0, 100.0)] and m.gap() == (100.0, 110.0)
    assert m.majors()[:2] == [0.0, 2.0] and m.majors()[-1] == 600 and 400 in m.majors()
    ax.scale = "log10"                                            # no break on log axes
    assert YMap(ax, AxisRange(1, 1000, 1), 210.0).brk is None
    ax.scale, ax.brk = "linear", {"on": True, "low_to": 700, "high_from": 800}
    assert YMap(ax, AxisRange(0, 600, 100), 210.0).brk is None    # outside the range: ignored


def test_breaks_grid_lines_and_extra_ticks_draw(app):
    from asterism.app.graph.export import svg_bytes
    from asterism.app.graph.layout import build
    from asterism.core.qa import check_svg
    p, t, g, a = _anova_graph()
    g.spec.y.grid = True
    g.spec.y.extra = [{"value": 12.0, "line": True, "dash": "dot", "label": "baseline", "tick": True}]
    g.spec.y.brk = {"on": True, "low_to": 4, "high_from": 8, "split": 0.3, "gap": 14}
    kinds = {e.kind for e in build(g)[0]}
    assert {"grid", "gap"} <= kinds
    svg = svg_bytes(g)
    assert b"baseline" in svg and b"stroke-dasharray" in svg
    import re
    w_mm, h_mm = (float(v) for v in re.search(rb'width="([\d.]+)mm" height="([\d.]+)mm"', svg).groups())
    rep = check_svg(svg, expected_w_mm=w_mm, expected_h_mm=h_mm, expected_gids=["y-axis", "guides", "axis-break"])
    assert rep.ok, rep.summary()


def test_new_spec_fields_save_and_load():
    from asterism.doc.spec import GraphSpec, spec_from_dict, spec_to_dict
    import json
    s = GraphSpec()
    s.style(1).axis = "right"
    s.style(1).legend = False
    s.y2.title, s.y2.vmax, s.y2.auto = "Right", 7.0, False
    s.y.extra = [{"value": 3.0, "line": True, "label": "x"}]
    s.y.brk = {"on": True, "low_to": 1.0, "high_from": 5.0}
    s.drawings = [{"id": "a", "kind": "rect", "x1": 0, "y1": 0, "x2": 5, "y2": 5}]
    r = spec_from_dict(json.loads(json.dumps(spec_to_dict(s))))
    assert r.style(1).axis == "right" and not r.style(1).legend
    assert (r.y2.title, r.y2.vmax, r.y2.auto) == ("Right", 7.0, False)
    assert r.y.extra[0]["label"] == "x" and r.y.brk["high_from"] == 5.0 and r.drawings[0]["kind"] == "rect"


def test_format_graph_right_axis_and_guides(app):
    from asterism.app.dialogs.format_graph import FormatGraphDialog
    p, t, g = _xy_two_units()
    d = FormatGraphDialog(g, p, "style", column=1)
    d.plot_axis.setCurrentIndex(1)
    d.y2_title.setText("Counts per day")
    w = d.axis_ctl["y"]
    w["grid"].setChecked(True)
    w["extra"].item(0, 0).setText("25")
    w["extra"].item(0, 5).setText("limit")
    w["extra"].item(1, 0).setText("10")
    w["extra"].item(1, 1).setText("20")
    w["brk_on"].setChecked(True)
    w["brk_lo"].setText("5")
    w["brk_hi"].setText("15")
    d.apply()
    s = g.spec
    assert s.style(1).axis == "right" and s.style(0).axis == "left" and s.y2.title == "Counts per day"
    assert s.y.grid and s.y.extra[0]["value"] == 25.0 and s.y.extra[0]["label"] == "limit"
    assert "to" not in s.y.extra[0] and s.y.extra[1]["to"] == 20.0
    assert s.y.brk["on"] and s.y.brk["low_to"] == 5.0


# ---------------------------------------------------------------------------
# Drawing on graphs
# ---------------------------------------------------------------------------

def _png(tmp_path):
    from PySide6.QtGui import QColor, QImage
    img = QImage(40, 20, QImage.Format_RGB32)
    img.fill(QColor("#336699"))
    path = tmp_path / "pic.png"
    img.save(str(path))
    return str(path)


def test_every_kind_of_drawing_builds_and_exports(app, tmp_path):
    from asterism.app.graph.drawings import image_drawing, new_drawing
    from asterism.app.graph.export import svg_bytes
    from asterism.app.graph.layout import build
    p, t, g, a = _anova_graph()
    g.spec.drawings = [new_drawing("line", 0, 0, 30, 30), new_drawing("arrow", 0, 0, 30, -20, head="both"),
                       new_drawing("rect", 5, 5, 40, 30, fill="#ffeeaa", dash="dash"),
                       new_drawing("ellipse", 10, 10, 50, 30), new_drawing("text", 20, -30, 20, -30, text="n = 6\nmice"),
                       image_drawing(_png(tmp_path), 60, 0)]
    els = [e for e in build(g)[0] if e.kind == "drawing"]
    assert [e.meta["drawing_kind"] for e in els] == ["line", "arrow", "rect", "ellipse", "text", "image"]
    svg = svg_bytes(g).decode()
    assert "<ellipse" in svg and "data:image/png;base64," in svg and ">mice<" in svg
    assert 'stroke-dasharray' in svg


def test_drawing_with_the_tools(app):
    from PySide6.QtCore import QPointF
    from asterism.app.graph.view import GraphSheet
    p, t, g, a = _anova_graph()
    gs = GraphSheet(g, p)
    gs.set_tool("rect")
    gs._commit_drawing(QPointF(10, 10), QPointF(60, 40))
    assert gs.tool is None and len(g.spec.drawings) == 1
    d = g.spec.drawings[0]
    assert (d["kind"], d["x2"] - d["x1"], d["y2"] - d["y1"]) == ("rect", 50, 30)
    gs._moved(f"draw-{d['id']}", 5, -5)
    assert (g.spec.drawings[0]["x1"], g.spec.drawings[0]["y1"]) == (15, 5)
    gs._reshaped(d["id"], "p2", 100, 100)
    assert (g.spec.drawings[0]["x2"], g.spec.drawings[0]["y2"]) == (100, 100)
    gs.set_tool("line")
    gs._draw_start = QPointF(0, 0)
    from PySide6.QtCore import Qt
    end = gs._constrain(QPointF(40, 37), Qt.ShiftModifier)           # Shift: 45°
    assert end.x() == pytest.approx(end.y())
    gs._commit_drawing(QPointF(0, 0), QPointF(0.5, 0.5))              # a click: default length
    line = g.spec.drawings[-1]
    assert line["kind"] == "line" and line["x2"] - line["x1"] == 40
    for it in gs.items:
        it.setSelected(it.el.kind == "drawing")
    gs.align_drawings("left")
    assert len({round(min(x["x1"], x["x2"]) - x["width"] / 2, 3) for x in g.spec.drawings}) == 1
    gs.restack_drawings(False)
    for it in gs.items:
        it.setSelected(it.el.kind == "drawing")
    gs.delete_drawings()
    assert g.spec.drawings == []
    p.undo.undo()
    assert len(g.spec.drawings) == 2


def test_text_tool_edits_in_place(app):
    from PySide6.QtCore import QPointF
    from asterism.app.graph.view import GraphSheet
    p, t, g, a = _anova_graph()
    gs = GraphSheet(g, p)
    gs.set_tool("text")
    gs._commit_drawing(QPointF(20, -20), QPointF(20, -20))
    assert gs._editing is not None
    ed, el = gs._editing
    ed.setPlainText("P < 0.05")
    gs._finish_edit(True)
    assert g.spec.drawings[0]["text"] == "P < 0.05"
    item = next(i for i in gs.items if i.el.kind == "drawing")
    gs._start_edit(item)
    gs._editing[0].setPlainText("")
    gs._finish_edit(True)                                            # emptied: removed
    assert g.spec.drawings == []


def test_drawing_dialog(app):
    from asterism.app.dialogs.drawing import DrawingDialog
    from asterism.app.graph.drawings import new_drawing
    from asterism.app.graph.canvas import MM
    d = new_drawing("ellipse", 0, 0, 20 * MM, 10 * MM)
    dlg = DrawingDialog(d)
    dlg.filled.setChecked(True)
    dlg.w.setValue(30.0)
    dlg.width.setCurrentIndex(0)                                      # no outline
    v = dlg.value()
    assert v["fill"] and v["width"] == 0.0 and v["x2"] == pytest.approx(30 * MM)
    a = DrawingDialog(new_drawing("arrow", 0, 0, 10, 10))
    a.head.setCurrentIndex(1)
    assert a.value()["head"] == "both"
    tx = DrawingDialog(new_drawing("text", 0, 0, 0, 0, text="hi"))
    tx.bold.setChecked(True)
    assert tx.value()["bold"] and tx.value()["text"] == "hi"


def test_main_window_draw_tools_and_picture(app, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QFileDialog
    from asterism.app.main_window import MainWindow
    p, t, g, a = _anova_graph()
    w = MainWindow(p)
    w.show_sheet(g)
    gs = w.stack.currentWidget()
    w.draw_tools["arrow"].setChecked(True)
    w.draw_tools["arrow"].trigger()
    w.draw_tools["arrow"].setChecked(True)
    w._draw_tool("arrow", True)
    assert gs.tool == "arrow"
    w.show_sheet(t)                                                   # leaving the graph ends the tool
    assert gs.tool is None and not w.draw_tools["arrow"].isChecked()
    w.show_sheet(g)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a_, **k: (_png(tmp_path), ""))
    w.add_picture()
    assert g.spec.drawings[0]["kind"] == "image" and g.spec.drawings[0]["png"]
    p.mark_saved()
    w.close()


# ---------------------------------------------------------------------------
# Text formatting
# ---------------------------------------------------------------------------

def test_superscript_subscript_and_back():
    from asterism.app.graph.drawings import script
    assert script("2+", "sup") == "²⁺" and script("²⁺", "sup") == "2+"
    assert script("-3", "sup") == "⁻³" and script("2", "sub") == "₂"
    assert script("Q", "sup") == "Q"                              # no Unicode form: unchanged


def test_text_tools_on_titles_and_drawn_text(app):
    from PySide6.QtGui import QTextCursor
    from asterism.app.graph.drawings import new_drawing
    from asterism.app.graph.export import svg_bytes
    from asterism.app.graph.view import GraphSheet
    p, t, g, a = _anova_graph()
    g.spec.y.title = "Ca2+ (mM)"
    gs = GraphSheet(g, p)
    title = next(i for i in gs.items if i.el.id == "y-title")
    title.setSelected(True)
    assert gs.insert_text(" µ")                                    # opens the editor, inserts at the end
    ed = gs._editing[0]
    cur = ed.textCursor()
    cur.setPosition(2)
    cur.setPosition(4, QTextCursor.KeepAnchor)
    ed.setTextCursor(cur)
    del cur, ed                     # a cursor must not outlive the editor's document
    assert gs.script_selection("sup")
    gs._finish_edit(True)
    assert g.spec.y.title == "Ca²⁺ (mM) µ"
    # underline and colour on the axis title font
    title = next(i for i in gs.items if i.el.id == "y-title")
    title.setSelected(True)
    gs.apply_font(underline=True, color="#aa0000")
    svg = svg_bytes(g).decode()
    assert 'text-decoration="underline"' in svg and 'fill="#aa0000"' in svg
    # drawn text keeps its own font and alignment
    g.spec.drawings = [new_drawing("text", 0, 0, 0, 0, text="short\na much longer line")]
    g.changed.emit()
    for it in gs.items:
        it.setSelected(it.el.kind == "drawing")
    gs.apply_font(bold=True, size=9.0)
    gs.align_text("right")
    d = g.spec.drawings[0]
    assert d["bold"] and d["size"] == 9.0 and d["align"] == "right"
    assert g.spec.fonts["y_title"].size != 9.0
    assert 'text-anchor="end"' in svg_bytes(g).decode()


def test_main_window_text_actions(app, monkeypatch):
    from asterism.app.main_window import MainWindow
    p, t, g, a = _anova_graph()
    w = MainWindow(p)
    w.show_sheet(g)
    gs = w.stack.currentWidget()
    next(i for i in gs.items if i.el.id == "y-axis").setSelected(True)
    w.a_underline.trigger()
    assert g.spec.fonts["y_numbers"].underline
    w.a_underline.trigger()
    assert not g.spec.fonts["y_numbers"].underline
    w._script("sup")                                               # nothing being edited: just a hint
    assert "Superscript" in w.statusBar().currentMessage()
    p.mark_saved()
    w.close()


# ---------------------------------------------------------------------------
# Nudging, discontinuous lines, legend toggle, star styles
# ---------------------------------------------------------------------------

def test_prism_style_stars_and_most_stars():
    from asterism.app.graph.layout import star_label
    from asterism.doc.spec import default_sig
    sig = default_sig()
    sig["levels"] = "gp"
    assert [star_label(p, sig) for p in (0.04, 0.03, 0.002, 0.0001, 0.00001)] == ["ns", "*", "**", "***", "****"]
    sig["max_stars"] = 2
    assert star_label(0.00001, sig) == "**"


def test_nudging_data_sets(app):
    from asterism.app.graph.layout import build
    from asterism.app.graph.view import GraphSheet
    p, t, g, a = _anova_graph()
    x0 = build(g)[0]
    b0 = {e.id: e.bounds for e in x0}
    gs = GraphSheet(g, p)
    next(i for i in gs.items if i.el.id == "data-B").setSelected(True)
    assert gs.nudge_selected(5, 0) and not gs.nudge_selected(0, 1)          # no vertical nudge on columns
    b1 = {e.id: e.bounds for e in build(g)[0]}
    assert b1["data-B"].left() == pytest.approx(b0["data-B"].left() + 5)
    assert b1["data-A"] == b0["data-A"]
    # XY: both directions, curves follow
    p2, t2, g2 = _xy_two_units()
    gs2 = GraphSheet(g2, p2)
    next(i for i in gs2.items if i.el.id == "data-A").setSelected(True)
    before = next(e for e in build(g2)[0] if e.id == "data-A").bounds
    gs2.nudge_selected(0, 4)
    after = next(e for e in build(g2)[0] if e.id == "data-A").bounds
    assert after.top() == pytest.approx(before.top() - 4)
    p2.undo.undo()
    assert g2.spec.style(0).nudge_y == 0


def test_discontinuous_lines(app):
    from asterism.analysis import engine
    from asterism.app.graph.export import svg_bytes
    from asterism.doc.model import Project
    p = Project(engine)
    t = p.add_table(table_type="xy", example=False)
    for r in range(6):
        t.set(r, "x", float(r), emit=False)
        if r != 3:
            t.set(r, 0, float(r * 2), emit=False)
    t.changed.emit()
    g = p.graphs[0]
    g.spec.style(0).connect = True
    n_lines = lambda: svg_bytes(g).decode().split('id="data-A"')[1].split("</g>")[0].count("<polyline")
    assert n_lines() == 1
    g.spec.style(0).gaps = True
    assert n_lines() == 2


def test_legend_toggle(app):
    from asterism.app.main_window import MainWindow
    p, t, g, a = _anova_graph()
    w = MainWindow(p)
    w.show_sheet(g)
    before = g.spec.show_legend
    w.a_legend.trigger()
    assert g.spec.show_legend != before
    p.mark_saved()
    w.close()


def test_shaded_bands_and_survival_error_bars(app):
    from asterism.app.graph.export import svg_bytes
    p, t, g, a = _anova_graph()
    g.spec.y.extra = [{"value": 8, "to": 12, "label": "normal range"}]
    svg = svg_bytes(g).decode()
    assert 'fill="#e6e6e6"' in svg and "normal range" in svg
    from asterism.analysis import engine
    from asterism.doc.model import Project
    p2 = Project(engine)
    p2.add_table(table_type="survival", example=True)
    g2 = p2.graphs[0]
    n0 = svg_bytes(g2).decode().count("<line")
    g2.spec.surv_ci = "bars"
    assert svg_bytes(g2).decode().count("<line") > n0 + 6


# ---------------------------------------------------------------------------
# Plotting a function
# ---------------------------------------------------------------------------

def test_function_parser():
    from asterism.analysis.function import evaluate, parse
    assert parse("Y = Top/(1+exp(-K*(X-X0)))")[1] == ["Top", "K", "X0"]
    assert list(evaluate("Y = 2*X + B", {"B": 1}, [0, 1, 2])) == [1, 3, 5]
    with pytest.raises(ValueError):
        evaluate("Y = A*X", {}, [1])
    with pytest.raises(ValueError):
        parse("Y = __import__('os')")


def test_functions_draw_on_xy_graphs(app):
    from asterism.app.dialogs.function import FunctionDialog
    from asterism.app.graph.layout import build
    from asterism.app.graph.view import GraphSheet
    p, t, g = _xy_two_units()
    g.spec.functions = [{"id": "f1", "text": "Y = 20 + A*X", "params": {"A": 1.5}, "from": None, "to": None}]
    el = next(e for e in build(g)[0] if e.id == "function-1")
    assert el.kind == "curve" and el.bounds.width() > 50
    g.spec.functions[0]["params"]["A"] = 1e6                       # off the plot: clipped, still no error
    build(g)
    d = FunctionDialog(None)
    d.text.setText("Y = Vmax*X/(Km + X)")
    assert [d.params.item(i, 0).text() for i in range(d.params.rowCount())] == ["Vmax", "Km"]
    d.params.item(0, 1).setText("50")
    d.auto.setChecked(False)
    d.x_from.setText("1")
    v = d.value()
    assert v["params"] == {"Vmax": 50.0, "Km": 1.0} and v["from"] == 1.0
    d.text.setText("Y = (")
    assert not d.ok.isEnabled()
    gs = GraphSheet(g, p)
    gs.remove_function("f1")
    assert g.spec.functions == []


def test_qq_plot_from_the_normality_test(app):
    from asterism.analysis import engine
    from asterism.analysis.normality import qq_points
    from asterism.app.graph.layout import build
    from asterism.app.main_window import MainWindow
    from asterism.doc.model import Analysis
    from scipy import stats
    x, pred = qq_points([5.0, 1.0, 3.0, 2.0, 4.0])
    assert list(x) == [1, 2, 3, 4, 5]
    z = stats.norm.ppf((3 - 0.375) / 5.25)
    assert pred[2] == pytest.approx(3.0 + stats.tstd([1, 2, 3, 4, 5]) * z)      # the middle value: mean
    p, t, g, a = _anova_graph()
    w = MainWindow(p)
    an = Analysis("normality", t, [0, 1], {"qq": True})
    p.add_analysis(an)
    w._result_graph(an)
    qg = p.graphs[-1]
    assert qg.source is an and qg.table.table_type == "xy" and qg.spec.x.title == "Actual"
    ids = {e.id for e in build(qg)[0]}
    assert {"data-A", "data-B", "function-1"} <= ids
    p.mark_saved()
    w.close()


def test_before_after_summary_and_grouped_replicates_with_means(app):
    from asterism.analysis import engine
    from asterism.app.dialogs.graph_type import apply_preset
    from asterism.app.graph.layout import build
    from asterism.doc.model import Project
    p = Project(engine)
    t = p.add_table(table_type="column", example=False)
    for r in range(6):
        t.set(r, 0, float(10 + r), emit=False)
        t.set(r, 1, float(13 + r), emit=False)
    t.changed.emit()
    g = p.graphs[0]
    g.spec = apply_preset(g.spec, "before_after", [0, 1])
    assert "summary-beside" not in {e.id for e in build(g)[0]}
    g.spec.ba_summary = "mean_sd"
    by = {e.id: e for e in build(g)[0]}
    assert by["summary-beside"].bounds.left() < by["data-A"].bounds.left()      # outward of the first set
    t2 = p.add_table(table_type="grouped", y_format="replicates", replicates=3, example=True)
    g2 = p.graphs[1]
    g2.spec = apply_preset(g2.spec, "g_lines", t2.used_columns())
    h0 = next(e for e in build(g2)[0] if e.id == "data-A").hit.boundingRect().height()
    g2.spec = apply_preset(g2.spec, "g_lines_reps", t2.used_columns())
    h1 = next(e for e in build(g2)[0] if e.id == "data-A").hit.boundingRect().height()
    assert h1 > h0


# ---------------------------------------------------------------------------
# Multiple-variable graphs (scatter, bubble, coloured, labelled)
# ---------------------------------------------------------------------------

def _mv():
    from asterism.analysis import engine
    from asterism.doc.model import Project
    p = Project(engine)
    t = p.add_table(table_type="multivar", example=True)       # Age, Weight, Seizures, Sex (text)
    return p, t, p.graphs[0]


def test_multivariable_roles_and_defaults(app):
    from asterism.app.graph.layout import build
    from asterism.app.graph.multivar_layout import roles
    p, t, g = _mv()
    ro = roles(g.spec, t)
    assert ro["numeric"] == [0, 1, 2] and ro["x"] == 0 and ro["ys"] == [1]
    by = {e.id: e for e in build(g)[0]}
    assert by["x-title"].meta["text"] == "Age (weeks)" and by["y-title"].meta["text"] == "Weight (g)"
    g.spec.mv.update(size="auto", color="auto")
    ro = roles(g.spec, t)
    assert ro["size"] == 2 and ro["color"] == 3                  # next numeric; the text variable


def test_bubble_and_colour_legends(app):
    from asterism.app.graph.export import svg_bytes
    from asterism.app.graph.layout import build
    p, t, g = _mv()
    g.spec.mv.update(x=1, y=[2], size=0, color=3, labels=True)
    els = build(g)[0]
    data = next(e for e in els if e.id == "data-C")
    leg = next(e for e in els if e.id == "legend")
    assert leg.bounds.left() > data.bounds.right()
    svg = svg_bytes(g).decode()
    assert "Row 6" in svg and "Sex" in svg and "Age (weeks)" in svg and 'fill-opacity="0.75"' in svg
    g.spec.mv.update(color=0, size=None)                          # numeric colour: a gradient key
    assert "8 – 13" in svg_bytes(g).decode()


def test_multivariable_presets_and_dialog(app):
    from asterism.app.dialogs.format_graph import FormatGraphDialog
    from asterism.app.dialogs.graph_type import GraphTypeDialog, apply_preset
    p, t, g = _mv()
    new = apply_preset(g.spec, "mv_bubble_colour", t.used_columns())
    assert new.mv["size"] == "auto" and new.mv["color"] == "auto"
    GraphTypeDialog(g, p)                                          # thumbnails build
    d = FormatGraphDialog(g, p, "arrangement")
    d.mv_x.setCurrentIndex(1)                                      # Weight on X
    for i in range(d.mv_y.count()):
        d.mv_y.item(i).setCheckState(__import__("PySide6.QtCore", fromlist=["Qt"]).Qt.Checked)
    d.mv_size.setCurrentIndex(1)                                   # Age as size
    d.apply()
    assert g.spec.mv["x"] == 1 and g.spec.mv["y"] == [0, 1, 2] and g.spec.mv["size"] == 0
    from asterism.app.graph.multivar_layout import roles
    assert roles(g.spec, t)["ys"] == [0, 2]                         # X itself is left out


def test_waffle_plot(app):
    from asterism.analysis import engine
    from asterism.app.graph.export import svg_bytes
    from asterism.app.graph.parts_survival_layout import waffle_counts
    from asterism.doc.model import Project
    assert waffle_counts([46, 31, 13, 10]) == [46, 31, 13, 10]
    assert sum(waffle_counts([1, 1, 1])) == 100 and sorted(waffle_counts([1, 1, 1])) == [33, 33, 34]
    p = Project(engine)
    p.add_table(table_type="parts", example=True)
    g = p.graphs[0]
    g.spec.parts_layout = "waffle"
    svg = svg_bytes(g).decode()
    assert svg.split('id="data-A"')[1].split("</g>")[0].count("<rect") == 100


def test_xy_row_labels_and_colour_by_row(app):
    from asterism.app.graph.export import svg_bytes
    p, t, g = _xy_two_units()
    t.has_row_titles = True
    t.set(0, "row", "Mouse 1")
    st = g.spec.style(0)
    st.row_labels, st.by_row = True, True
    svg = svg_bytes(g).decode()
    from asterism.doc.spec import SUBJECT_COLORS
    assert "Mouse 1" in svg and SUBJECT_COLORS[1] in svg and SUBJECT_COLORS[2] in svg


# ---------------------------------------------------------------------------
# Figures: drop from the sidebar, overlay graphs, panel letters, results page
# ---------------------------------------------------------------------------

def test_figure_drop_overlay_letters_and_results_page(app):
    from asterism.app.figure.layout import build_figure
    from asterism.app.figure.view import FigureSheetView
    p, t, g, a = _anova_graph()
    t2 = p.add_table(table_type="column", example=True)
    g2 = p.graphs[-1]
    f = p.add_figure()
    v = FigureSheetView(f, p)
    v.drop_panels([("graph", g.id), ("graph", g2.id), ("results", a.id)], 21.0, 33.0)
    assert [pn["kind"] for pn in f.panels] == ["graph", "graph", "results"]
    assert (f.panels[0]["x"], f.panels[0]["y"]) == (20.0, 35.0)              # snapped to the grid
    for it in v.items:
        it.setSelected(it.el.kind == "graph")
    assert v.overlay_selected()
    els = {e.panel: e for e in build_figure(f, p)[1] if e.kind == "graph"}
    o1, o2 = els[f.panels[0]["id"]].meta["origin"], els[f.panels[1]["id"]].meta["origin"]
    assert o1 == pytest.approx(o2, abs=0.01) and f.panels[1]["label"] == ""
    letters = [e.meta["text"] for e in build_figure(f, p)[1] if e.kind == "letter"]
    assert letters == ["A", "B"]                                              # the overlaid graph has none
    v.set_label(f.panels[0]["id"], "i")
    assert "i" in [e.meta["text"] for e in build_figure(f, p)[1] if e.kind == "letter"]
    v.set_results_page(f.panels[2]["id"], 1)
    assert f.panels[2]["page"] == 1


def test_sidebar_drags_sheets(app):
    from asterism.app.sidebar import SHEET_MIME, ProjectSidebar
    p, t, g, a = _anova_graph()
    sb = ProjectSidebar(p)
    items = []
    it = sb.tree.topLevelItem(0)
    stack = [sb.tree.topLevelItem(i) for i in range(sb.tree.topLevelItemCount())]
    while stack:
        it = stack.pop()
        if it.data(0, __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.UserRole) in (g, a):
            items.append(it)
        stack += [it.child(i) for i in range(it.childCount())]
    md = sb.tree.mimeData(items)
    refs = set(bytes(md.data(SHEET_MIME)).decode().split("\n"))
    assert refs == {f"graph:{g.id}", f"results:{a.id}"}


# ---------------------------------------------------------------------------
# Horizontal graphs and bars extending both ways
# ---------------------------------------------------------------------------

def test_horizontal_column_graph(app):
    from asterism.app.graph.export import svg_bytes
    from asterism.app.graph.layout import build
    from asterism.app.graph.view import GraphSheet
    p, t, g, a = _anova_graph()
    v = {e.id: e.bounds for e in build(g)[0]}
    g.spec.horizontal = True
    els = build(g)[0]
    h = {e.id: e for e in els}
    # data sets now run down the page, first at the top; values grow to the right
    assert h["data-A"].bounds.center().y() < h["data-B"].bounds.center().y() < h["data-D"].bounds.center().y()
    assert h["data-D"].bounds.right() > h["data-A"].bounds.right()                 # High > Vehicle
    assert h["y-axis"].bounds.top() > h["data-D"].bounds.bottom()                  # value axis at the bottom
    assert h["x-axis"].bounds.right() <= h["data-A"].bounds.left() + 1             # labels on the left
    brs = [e for e in els if e.kind == "bracket"]
    assert brs and all(e.meta.get("flipped") for e in brs)
    assert all(e.bounds.left() > h["data-A"].bounds.left() for e in brs)
    svg = svg_bytes(g).decode()
    assert "Vehicle" in svg and "****" in svg
    # dragging a sideways bracket stores the move in upright coordinates
    gs = GraphSheet(g, p)
    gid = brs[0].id
    gs._moved(gid, 10.0, 0.0)
    assert g.spec.offsets[gid] == (0.0, -10.0)


def test_bars_extending_both_ways(app):
    from asterism.analysis import engine
    from asterism.app.dialogs.graph_type import apply_preset
    from asterism.app.graph.layout import build
    from asterism.doc.model import Project
    p = Project(engine)
    t = p.add_table(table_type="grouped", y_format="replicates", replicates=3, example=True)
    g = p.graphs[0]
    g.spec = apply_preset(g.spec, "g_pyramid", t.used_columns())
    assert g.spec.horizontal and g.spec.grouped_layout == "pyramid"
    els, rng = build(g)
    assert rng.vmin == -rng.vmax
    by = {e.id: e for e in els}
    zero_x = g.spec.y_len_mm * 72 / 25.4 / 2                                        # the middle of the value axis
    assert by["data-A"].bounds.right() <= zero_x + 2 and by["data-B"].bounds.left() >= zero_x - 2
    from asterism.app.graph.export import svg_bytes
    assert ">-" not in svg_bytes(g).decode()                                         # numbers without signs


def test_violin_line_styles(app):
    from asterism.app.graph.export import svg_bytes
    p, t, g, a = _anova_graph()
    for c in range(4):
        g.spec.style(c).appearance = "violin"
    body = lambda: svg_bytes(g).decode().split('id="data-A"')[1].split("</g>")[0]
    assert body().count("stroke-dasharray") == 2                      # dashed quartiles
    g.spec.style(0).violin_quartiles = "none"
    g.spec.style(0).violin_median = "dot"
    assert body().count("stroke-dasharray") == 1 and body().count("<line") == 1


def test_star_size_and_right_axis_list_in_format_graph(app):
    from PySide6.QtCore import Qt
    from asterism.app.dialogs.format_graph import FormatGraphDialog
    p, t, g, a = _anova_graph()
    d = FormatGraphDialog(g, p, "significance")
    d.sig_star_size.setValue(18.0)
    assert d.font_rows["stars"][1].value() == 18.0                 # same size as on "Titles and fonts"
    d.sig_p_size.setValue(8.0)
    # the right-axis page's list and the Style page's "Plot against" stay in step
    d.right_list.item(2).setCheckState(Qt.Checked)
    d.ds_combo.setCurrentIndex(3)                                   # data set C
    assert d.plot_axis.currentData() == "right"
    d.ds_combo.setCurrentIndex(2)                                   # data set B
    d.plot_axis.setCurrentIndex(1)
    assert d.right_list.item(1).checkState() == Qt.Checked
    d.apply()
    assert g.spec.fonts["stars"].size == 18.0 and g.spec.fonts["bracket"].size == 8.0
    assert [g.spec.style(c).axis for c in range(4)] == ["left", "right", "right", "left"]
