"""M10 in the app: the import window, File › Import Data, opening Prism files, date X columns."""

from __future__ import annotations

import pytest


def _csv(tmp_path, text, name="data.csv"):
    f = tmp_path / name
    f.write_text(text)
    return str(f)


def test_import_dialog_spreadsheet(app, tmp_path):
    from asterism.app.dialogs.import_data import ImportDialog
    path = _csv(tmp_path, "mouse,group,value\na,WT,1\nb,WT,2\nc,KO,5\n")
    d = ImportDialog(path)
    assert d.layout_combo.currentData() == "long"
    assert d.roles() == {0: "subject", 1: "group", 2: "value"}
    (t,), notes = d.result()
    assert t.titles[:2] == ["WT", "KO"] and list(t.values(1)) == [5]
    d.type_combo.setCurrentIndex(d.type_combo.findData("nested"))
    d.refresh_preview()
    (t,), _ = d.result()
    assert t.table_type == "nested" and t.sub_titles[0][:2] == ["a", "b"]
    assert d.ok.isEnabled() and "Nested table" in d.preview_title.text()
    # wide, with a header further down
    path = _csv(tmp_path, "exported 2026\n\nControl,Drug\n1,3\n2,4\n", "wide.csv")
    d = ImportDialog(path)
    assert d.header_spin.value() == 3 and d.layout_combo.currentData() == "wide"
    (t,), _ = d.result()
    assert list(t.values(0)) == [1, 2]


def test_import_dialog_quantstudio_settings(app, tmp_path):
    from PySide6.QtCore import Qt
    from asterism.app.dialogs.import_data import ImportDialog
    import sys
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
    from test_m10_import import _quantstudio_csv
    d = ImportDialog(str(_quantstudio_csv(tmp_path)))
    assert d.source == "QuantStudio" and d.using_recipe()
    labels = [d.ref_list.item(i).text() for i in range(d.ref_list.count())]
    assert any("Gapdh" in s and "from the file" in s for s in labels)
    (t,), notes = d.result()
    assert t.name == "Syt1 relative expression"
    d.sample_table.item(1, 1).setText("")                 # leave WT 2 out
    d.rel_sample.setChecked(True)
    s = d.qpcr_settings()
    assert s["relative_to"] == "sample" and s["reference_sample"] == "WT 1" and s["groups"]["WT 2"] == ""
    (t,), _ = d.result()
    assert len(t.values(0)) == 1 and t.values(0)[0] == pytest.approx(1.0)
    d.use_columns.setChecked(True)
    assert not d.using_recipe()


def test_main_window_import_and_prism(app, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from asterism.analysis import engine
    from asterism.app.dialogs.import_data import ImportDialog
    from asterism.app.main_window import MainWindow, open_path
    from asterism.doc.model import Project
    monkeypatch.setattr(QMessageBox, "exec", lambda *a, **k: 0)
    monkeypatch.setattr(ImportDialog, "exec", lambda self: True)
    p = Project(engine)
    w = MainWindow(p)
    w.import_data(_csv(tmp_path, "g,v\nA,1\nB,2\n", "Weights.csv"))
    assert p.tables[-1].name == "Weights" and p.graphs[-1].table is p.tables[-1]
    w.import_data(_csv(tmp_path, "g,v\nA,1\nB,2\n", "Weights.csv"))
    assert p.tables[-1].name == "Weights 2"                 # a second import doesn't clash
    pz = tmp_path / "t.pzfx"
    pz.write_text('<GraphPadPrismFile><Table TableType="OneWay" YFormat="replicates" Replicates="1">'
                  '<Title>From Prism</Title><YColumn Subcolumns="1"><Title>A</Title><Subcolumn><d>1</d>'
                  '<d>2</d></Subcolumn></YColumn></Table></GraphPadPrismFile>')
    w.import_data(str(pz))
    assert p.tables[-1].name == "From Prism"
    w2 = open_path(str(pz), w)
    assert w2 is not None and w2.display_name() == "t" and w2.project.tables[0].name == "From Prism"
    for win in (w, w2):
        win.project.mark_saved()
        win.close()


def test_date_x_columns_in_the_table(app):
    from asterism.analysis import engine
    from asterism.app.table_view import TableModel, parse_cell
    from asterism.doc import dates
    from asterism.doc.model import Project
    p = Project(engine)
    t = p.add_table(table_type="xy", x_format="date", example=False)
    assert t.x_format == "date"
    v = parse_cell(t, "x", "2026-10-26")
    assert v == dates.parse("2026-10-26")
    t.set(0, "x", v)
    t.set(0, 0, 3.0)
    m = TableModel(t, p)
    col = m.keys.index("x")
    assert m.data(m.index(0, col)) == "2026-10-26"
    from asterism.app.graph.layout import build
    els, _ = build(p.graphs[0])
    assert any(e.id == "x-axis" for e in els)


def test_preview_shows_every_table_and_imports_regression(app, tmp_path, monkeypatch):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from test_m10_import import _std_curve_csv
    from asterism.analysis import engine
    from asterism.app.dialogs.import_data import ImportDialog
    from asterism.app.main_window import MainWindow
    from asterism.doc.model import Project
    folder = _std_curve_csv(tmp_path)
    d = ImportDialog([folder])
    assert d.source == "QuantStudio" and d.std is not None
    assert d.preview_pick.count() == 2 and d.preview_pick.isEnabled()
    d.preview_pick.setCurrentIndex(1)
    assert "Quantities" in d.preview_title.text() and "2 of 2" in d.preview_title.text()
    d.dilution.setText("100")
    d.per.setCurrentIndex(2)
    d.volume.setText("2")
    d.refresh_preview()
    assert d.preview_pick.itemText(1).endswith("Titres")
    monkeypatch.setattr(ImportDialog, "exec", lambda self: True)
    p = Project(engine)
    w = MainWindow(p)
    w.import_data(str(folder))
    std = next(t for t in p.tables if t.name.endswith("standard curve"))
    lr = next(a for a in p.analyses if a.table is std)
    assert lr.analysis_type == "linreg" and not lr.result.error
    p.mark_saved()
    w.close()


def test_start_window_import_choice(app, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    from asterism.app.dialogs.start import StartDialog
    d = StartDialog()
    assert "import" in d.buttons
    path = _csv(tmp_path, "g,v\nA,1\n")
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", lambda *a, **k: ([path], ""))
    d.buttons["import"].click()
    assert d.result_choice() == ("import", [path])


def test_no_invented_reference_gene_and_axis_titles(app, tmp_path, monkeypatch):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from test_m10_import import _std_curve_csv
    from asterism.analysis import engine
    from asterism.app.dialogs.import_data import ImportDialog
    from asterism.app.main_window import MainWindow
    from asterism.doc.model import Project
    from asterism.io import quantstudio as Q
    from asterism.io.sheets import read_files
    folder = _std_curve_csv(tmp_path)
    assert Q.defaults(read_files([folder]))["reference_genes"] == []      # "ITR" is no housekeeping gene
    d = ImportDialog([folder])
    assert d.ddct_box.isHidden()                                           # no ΔΔCt table ticked
    d.item_table.item(2, 0).setCheckState(__import__("PySide6.QtCore", fromlist=["Qt"]).Qt.Checked)
    d._later()
    assert not d.ddct_box.isHidden()
    monkeypatch.setattr(ImportDialog, "exec", lambda self: True)
    p = Project(engine)
    w = MainWindow(p)
    w.import_data(str(folder))
    g = next(x for x in p.graphs if x.table.name.endswith("standard curve"))
    assert (g.spec.x.title, g.spec.y.title) == ("Copies per reaction (log scale)", "Cq")
    p.mark_saved()
    w.close()


def test_powers_of_ten_on_titre_graphs_and_tables(app, tmp_path):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from test_m10_import import _std_curve_csv
    from PySide6.QtCore import Qt
    from asterism.analysis import engine
    from asterism.app.graph.export import svg_bytes
    from asterism.app.graph.layout import power_label
    from asterism.app.main_window import MainWindow
    from asterism.app.table_view import TableModel, fmt_cell
    from asterism.doc.model import Project
    from asterism.io import labs
    from asterism.io.sheets import read_files
    assert power_label(3e13) == "3×10¹³" and power_label(1e9, bare_powers=True) == "10⁹"
    assert power_label(2.5e-4) == "2.5×10⁻⁴" and power_label(-3e6) == "−3×10⁶"
    assert fmt_cell(1.5028435e13, display=True) == "1.5028×10¹³" and fmt_cell(1.5028435e13) == "1.5028435e+13"
    sh = read_files([_std_curve_csv(tmp_path)])
    _src, items = labs.detect(sh)
    tables = []
    for it in items[:2]:
        tables += labs.build(it, sh, {"standard": {"dilution": 1000, "volume_ul": 2, "per": "ml"}})[0]
    p = Project(engine)
    w = MainWindow(p)
    w.add_imported(tables)
    titres = next(g for g in p.graphs if g.table.name == "Titres")
    assert titres.spec.y.fmt == "power" and titres.spec.y.scale == "log10"
    assert "10¹" in svg_bytes(titres).decode()
    std = next(g for g in p.graphs if g.table.name.endswith("standard curve"))
    assert std.spec.x.fmt == "antilog" and "10⁸" in svg_bytes(std).decode()
    m = TableModel(titres.table, p)
    col = m.keys.index(titres.table.flat(0, 0))
    shown, edited = m.data(m.index(0, col), Qt.DisplayRole), m.data(m.index(0, col), Qt.EditRole)
    assert "×10" in shown and "e+" in edited
    p.mark_saved()
    w.close()


def test_import_settings_reopen_and_update_in_place(app, tmp_path, monkeypatch):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from test_m10_import import _std_curve_csv
    from asterism.analysis import engine
    from asterism.app.dialogs.import_data import ImportDialog
    from asterism.app.main_window import MainWindow
    from asterism.doc import fileformat
    from asterism.doc.model import Project
    folder = _std_curve_csv(tmp_path)
    # the volume only counts per µL / mL: greyed out otherwise
    d = ImportDialog([folder])
    assert not d.volume.isEnabled()
    d.per.setCurrentIndex(2)
    assert d.volume.isEnabled()
    monkeypatch.setattr(ImportDialog, "exec", lambda self: True)
    p = Project(engine)
    w = MainWindow(p)
    w.import_data(str(folder))
    qty = next(t for t in p.tables if t.name == "Quantities")
    std = next(t for t in p.tables if t.name.endswith("standard curve"))
    lr = next(a for a in p.analyses if a.table is std)
    first = qty.get(0, qty.flat(0, 0))
    w.show_sheet(qty)
    assert w.a_import_settings.isEnabled()
    # survives save / load (the source rows and the choices are kept in the project)
    path = tmp_path / "proj.asterism"
    fileformat.save(p, str(path))
    q = fileformat.load(str(path), engine)
    assert next(t for t in q.tables if t.name == "Quantities").import_ref == qty.import_ref
    assert qty.import_ref["session"] in q.imports
    # change the dilution: the same tables update, analyses stay linked, one undo step
    orig_apply = ImportDialog.apply_state

    def apply_and_change(self, st):
        orig_apply(self, st)
        self.dilution.setText("1000")
    monkeypatch.setattr(ImportDialog, "apply_state", apply_and_change)
    n_tables = len(p.tables)
    w.import_settings(qty)
    assert len(p.tables) == n_tables and qty.get(0, qty.flat(0, 0)) == pytest.approx(first * 1000)
    assert lr.table is std and not lr.result.error
    p.undo.undo()
    assert qty.get(0, qty.flat(0, 0)) == pytest.approx(first)
    p.mark_saved()
    w.close()
