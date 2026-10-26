"""M8 figures: pages of panels (graphs, tables, results, text) — model, layout, letters,
editing, export at exact page size, live updates."""

from __future__ import annotations

import pytest

from asterism.core.qa import check_svg


def _project():
    from asterism.analysis import engine
    from asterism.doc.model import Analysis
    from asterism.doc.sample import sample_project
    p = sample_project(engine)
    t = p.tables[0]
    p.add_table(table_type="grouped", y_format="replicates", replicates=4, example=True)
    a = p.add_analysis(Analysis("ttest", t, t.used_columns()[:2], {}))
    f = p.add_figure()
    return p, f, a


def _fill(p, f, a):
    import copy
    from asterism.doc.commands import FigureCommand
    st = copy.deepcopy(f.state())
    st["panels"] = [f.new_panel("graph", p.graphs[0].id, x=20, y=20), f.new_panel("graph", p.graphs[1].id, x=110, y=20,
                                                                                   scale=0.8),
                    f.new_panel("table", p.tables[0].id, x=20, y=130, font_size=7),
                    f.new_panel("results", a.id, x=110, y=130, font_size=7),
                    f.new_panel("text", "", x=20, y=260, w=170, h=15, text="Figure 1. " + "Words " * 160)]
    p.undo.push(FigureCommand(f, st, "fill"))


def test_figure_state_saves_and_loads(app, tmp_path):
    from asterism.analysis import engine
    from asterism.doc import fileformat
    p, f, a = _project()
    _fill(p, f, a)
    f.page["landscape"] = True
    path = tmp_path / "fig.asterism"
    fileformat.save(p, str(path))
    q = fileformat.load(str(path), engine)
    g = q.figures[0]
    assert g.page["landscape"] and [pn["kind"] for pn in g.panels] == ["graph", "graph", "table", "results", "text"]
    assert g.page_mm() == (297.0, 210.0)


def test_letters_follow_reading_order_and_styles(app):
    from asterism.app.figure.layout import build_figure, letter_text
    p, f, a = _project()
    _fill(p, f, a)
    page, els = build_figure(f, p)
    letters = {e.meta["text"]: e.panel for e in els if e.kind == "letter"}
    ids = [pn["id"] for pn in f.panels]
    assert letters == {"A": ids[0], "B": ids[1], "C": ids[2], "D": ids[3]}      # text gets no letter
    assert [letter_text(i, "(a)") for i in (0, 1, 26)] == ["(a)", "(b)", "(aa)"]
    f.page["letters"] = False
    assert not [e for e in build_figure(f, p)[1] if e.kind == "letter"]


def test_text_wraps_and_missing_sheets_show_a_placeholder(app):
    from asterism.app.figure.layout import build_figure
    p, f, a = _project()
    _fill(p, f, a)
    page, els = build_figure(f, p)
    text = next(e for e in els if e.kind == "text")
    assert text.rect.height() > 15 * 72 / 25.4                         # grew to fit the wrapped lines
    p.delete(p.graphs[1])
    assert "missing" in [e.kind for e in build_figure(f, p)[1]]
    p.undo.undo()
    assert "missing" not in [e.kind for e in build_figure(f, p)[1]]


def test_figure_exports_at_exact_page_size(app, tmp_path):
    from pypdf import PdfReader
    from PySide6.QtGui import QImage
    from asterism.app.figure.export import export_image, export_pdf, svg_bytes
    p, f, a = _project()
    _fill(p, f, a)
    rep = check_svg(svg_bytes(f, p), expected_w_mm=210, expected_h_mm=297,
                    expected_gids=["panel-A", "panel-B", "A-data-A", "label-A", "panel-C", "panel-D"])
    assert rep.ok, rep.summary()
    pdf = tmp_path / "f.pdf"
    export_pdf(f, p, str(pdf))
    box = PdfReader(str(pdf)).pages[0].mediabox
    assert float(box.width) * 25.4 / 72 == pytest.approx(210, abs=0.3)
    assert float(box.height) * 25.4 / 72 == pytest.approx(297, abs=0.3)
    png, tif = tmp_path / "f.png", tmp_path / "f.tif"
    export_image(f, p, str(png), 150)
    export_image(f, p, str(tif), 150)
    img = QImage(str(png))
    assert img.width() == round(210 / 25.4 * 150) and img.height() == round(297 / 25.4 * 150)
    assert QImage(str(tif)).width() == img.width()


def test_editing_panels(app):
    from PySide6.QtCore import QPointF
    from asterism.app.figure.view import FigureSheetView
    p, f, a = _project()
    _fill(p, f, a)
    v = FigureSheetView(f, p)
    first = v.items[0]
    first.setSelected(True)
    first.setPos(QPointF(7.3 * 72 / 25.4, 3.1 * 72 / 25.4))       # dropped 7.3 mm right, 3.1 mm down
    v._commit_moves()
    pn = f.panels[0]
    assert (pn["x"], pn["y"]) == (25.0, 25.0)                       # snapped to the 5 mm grid
    p.undo.undo()
    assert (f.panels[0]["x"], f.panels[0]["y"]) == (20, 20)
    v.nudge(0, 0)                                                # (nothing selected after undo: no-op)
    import copy
    from asterism.doc.commands import FigureCommand
    st = copy.deepcopy(f.state())
    st["panels"][1]["y"] = 47.0
    p.undo.push(FigureCommand(f, st, "move"))
    v.items[0].setSelected(True)
    v.items[1].setSelected(True)
    v.align("top")
    assert f.panels[1]["y"] == pytest.approx(f.panels[0]["y"], abs=0.01)
    v.items[0].setSelected(True)
    v.items[1].setSelected(True)
    v.same_width()
    from asterism.app.figure.layout import build_figure
    rs = {e.panel: e.rect for e in build_figure(f, p)[1]}
    assert rs[f.panels[0]["id"]].width() == pytest.approx(rs[f.panels[1]["id"]].width(), rel=1e-3)
    n = len(f.panels)
    v.items[-1].setSelected(True)
    v.remove_selected()
    assert len(f.panels) < n
    v.arrange_grid(2)
    assert f.panels[0]["x"] == 15.0


def test_resizing_a_graph_scales_it(app):
    from asterism.app.figure.view import FigureSheetView
    p, f, a = _project()
    _fill(p, f, a)
    v = FigureSheetView(f, p)
    it = v.items[0]
    r = it.el.rect
    v._commit_resize(it, r.width() * 0.5, r.height() * 0.5)
    assert f.panels[0]["scale"] == pytest.approx(0.5, abs=0.01)


def test_figures_follow_their_graphs(app):
    from asterism.app.figure.view import FigureSheetView
    p, f, a = _project()
    _fill(p, f, a)
    v = FigureSheetView(f, p)
    before = v.items[0].el.rect
    p.graphs[0].spec.y_len_mm = 90.0
    p.graphs[0].changed.emit()
    assert v.items[0].el.rect.height() > before.height()


def test_main_window_figure_commands(app, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QFileDialog, QInputDialog
    from asterism.app.main_window import MainWindow
    p, f, a = _project()
    w = MainWindow(p)
    w._place_panels(f, [("graph", p.graphs[0].id), ("graph", p.graphs[1].id), ("table", p.tables[0].id)], 2)
    assert [pn["kind"] for pn in f.panels] == ["graph", "graph", "table"]
    assert f.panels[1]["y"] == f.panels[0]["y"] and f.panels[2]["y"] > f.panels[0]["y"]
    w.show_sheet(f)
    assert "3 panels" in w.top.subtitle.text() and w.a_fig_add.isEnabled() and w.a_export_pdf.isEnabled()
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(tmp_path / "fig.svg"), ""))
    w.export("svg")
    assert (tmp_path / "fig.svg").exists()
    w.show_sheet(p.graphs[0])
    monkeypatch.setattr(QInputDialog, "getItem", lambda *a, **k: ("New figure", True))
    w.add_graph_to_figure()
    assert len(p.figures) == 2 and p.figures[1].panels[0]["ref"] == p.graphs[0].id
    p.mark_saved()
    w.close()


def test_figure_dialogs(app):
    from asterism.app.dialogs.figure import AddPanelsDialog, FormatFigureDialog, TextPanelDialog
    p, f, a = _project()
    d = AddPanelsDialog(p, preselect={p.graphs[0].id})
    assert ("graph", p.graphs[0].id) in d.chosen()
    fd = FormatFigureDialog(f)
    fd.size.setCurrentIndex(1)                         # US Letter
    pg = fd.page()
    assert pg["size"] == "letter" and pg["width"] == pytest.approx(215.9)
    assert TextPanelDialog("Hi", 9.0).values() == ("Hi", 9.0)
