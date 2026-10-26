"""Screenshot tour for visual review:  python -m qt_spike --shots DIR"""

from __future__ import annotations

import os
import time

from PySide6.QtCore import Qt


def take_shots(app, out: str) -> int:
    from .dialogs.analyze import AnalyzeDialog, TTestParamsDialog
    from .dialogs.format_graph import FormatGraphDialog
    from ..analysis import engine
    from ..doc.model import Analysis
    from ..doc.sample import sample_project
    from .main_window import MainWindow

    os.makedirs(out, exist_ok=True)

    def pump(n: int = 15) -> None:
        for _ in range(n):
            app.processEvents()
            time.sleep(0.02)

    def shot(widget, name: str) -> None:
        pump()
        widget.grab().save(os.path.join(out, f"{name}.png"))

    w = MainWindow(sample_project(engine))
    w.show()
    w.raise_()
    pump(40)
    p, t, g = w.project, w.project.tables[0], w.project.graphs[0]
    shot(w, "01_table")

    w.show_sheet(g)
    gs = w._widget_for(g)
    shot(w, "02_graph")
    for it in gs.items:
        it.setSelected(it.el.id == "data-A")
    shot(w, "03_graph_selected")
    gs.scene.clearSelection()

    a = Analysis("ttest", t, [0, 1], {"design": "unpaired", "distribution": "normal",
                                      "test": "student", "bracket": True, "descriptive": True})
    p.add_analysis(a)
    w.show_sheet(a)
    shot(w, "04_results")
    w.show_sheet(g)
    shot(w, "05_graph_bracket")

    for name, dlg in (("06_analyze", AnalyzeDialog(p, t, w)),
                      ("07_ttest_params", TTestParamsDialog({"distribution": "nonparametric", "test": "mw"}, w)),
                      ("08_format_graph", FormatGraphDialog(g, p, "style", None, gs.auto_range, w)),
                      ("09_format_axes", FormatGraphDialog(g, p, "y", None, gs.auto_range, w))):
        dlg.show()
        dlg.raise_()
        shot(dlg, name)
        dlg.close()

    # Data tables (M2): the New Table dialog and a few table types.
    from .dialogs.new_table import NewTableDialog
    for name, tt in (("12_new_table_xy", "xy"), ("13_new_table_nested", "nested")):
        dlg = NewTableDialog(w, table_type=tt)
        dlg.show()
        shot(dlg, name)
        dlg.close()
    for name, tt, fmt in (("14_table_xy", "xy", {"y_format": "replicates", "replicates": 3,
                                                 "x_format": "numbers_err", "row_titles": True}),
                          ("15_table_grouped_summary", "grouped", {"y_format": "mean_sd_n"}),
                          ("16_table_nested", "nested", {"replicates": 3}),
                          ("17_table_survival", "survival", {}),
                          ("18_table_multivar", "multivar", {})):
        t2 = p.add_table(table_type=tt, example=True, **fmt)
        w.show_sheet(t2)
        shot(w, name)
    w.show_sheet(p.graphs[-1])
    shot(w, "19_graph_placeholder")

    # Column analyses (M3): one-way ANOVA with stacked brackets, settings, normality.
    from ..doc.model import Analysis as _A
    from .dialogs.params import AnovaParamsDialog
    t3 = p.add_table("Dose response", table_type="column")
    for c, (name, vals) in enumerate({"Vehicle": [24, 26, 31, 27, 29, 25], "Low": [31, 35, 30, 36, 33, 34],
                                      "Mid": [29, 27, 33, 28, 30, 31], "High": [40, 38, 36, 41, 39, 35]}.items()):
        t3.titles[c] = name
        for r, v in enumerate(vals):
            t3.set(r, c, float(v), emit=False)
    t3.changed.emit()
    a3 = p.add_analysis(_A("anova1", t3, [0, 1, 2, 3], {"bracket": True}))
    w.show_sheet(a3)
    shot(w, "20_anova_results")
    w._widget_for(a3).tabs.setCurrentIndex(2)
    shot(w, "21_anova_comparisons")
    g3 = next(g for g in p.graphs if g.table is t3)
    g3.spec.y.title = "Response"
    g3.changed.emit()
    w.show_sheet(g3)
    shot(w, "22_graph_stacked_brackets")
    dlg = AnovaParamsDialog(None, t3, [0, 1, 2, 3], w)
    dlg.show_section("comparisons")
    dlg.show()
    shot(dlg, "23_anova_settings")
    dlg.close()
    a4 = p.add_analysis(_A("normality", t3, [0, 1, 2, 3], {"lognormal": True}))
    w.show_sheet(a4)
    shot(w, "24_normality")

    # Column graph types (M3b): the gallery, then violin and before-after.
    from .dialogs.graph_type import GraphTypeDialog, apply_preset
    dlg = GraphTypeDialog(g3, p, w)
    dlg.show()
    shot(dlg, "25_graph_types")
    dlg.close()
    for name, key in (("26_violin_points", "violin_points"), ("27_before_after", "before_after")):
        g3.set_spec(apply_preset(g3.spec, key, t3.used_columns()))
        w.show_sheet(g3)
        shot(w, name)

    # Grouped and nested data (M4).
    from .dialogs.analyze import AnalyzeDialog
    from .dialogs.format_graph import FormatGraphDialog
    from .dialogs.params_grouped import TwoWayParamsDialog
    t4 = p.add_table("Seizures by week", table_type="grouped", example=True,
                     y_format="replicates", replicates=4)
    g4 = next(g for g in p.graphs if g.table is t4)
    g4.spec.y.title = "Seizures per day"
    a5 = p.add_analysis(_A("anova2", t4, [0, 1], {"design": "ordinary", "compare": "rows",
                                                   "method": "sidak", "row_factor": "Day",
                                                   "col_factor": "Genotype"}))
    w.show_sheet(g4)
    shot(w, "28_grouped_graph")
    w.show_sheet(a5)
    shot(w, "29_two_way_results")
    w._widget_for(a5).tabs.setCurrentIndex(2)
    shot(w, "30_two_way_comparisons")
    dlg = TwoWayParamsDialog(a5.params, t4, w)
    dlg.show()
    shot(dlg, "31_two_way_settings")
    dlg.close()
    dlg = AnalyzeDialog(p, t4, w)
    dlg.show()
    shot(dlg, "32_analyze_grouped")
    dlg.close()
    for name, key in (("33_grouped_stacked", "g_stacked"), ("34_grouped_lines", "g_lines"),
                      ("35_grouped_heatmap", "g_heat"), ("36_grouped_box", "g_box")):
        g4.set_spec(apply_preset(g4.spec, key, t4.used_columns()))
        w.show_sheet(g4)
        shot(w, name)
    dlg = GraphTypeDialog(g4, p, w)
    dlg.show()
    shot(dlg, "37_grouped_gallery")
    dlg.close()
    a6 = p.add_analysis(_A("multiple_t", t4, [0, 1], {"test": "welch", "correction": "fdr_bky"}))
    w.show_sheet(a6)
    shot(w, "38_multiple_t")
    t5 = p.add_table("Synapses per neuron", table_type="nested", example=True)
    g5 = next(g for g in p.graphs if g.table is t5)
    g5.spec.y.title = "Synapses"
    a7 = p.add_analysis(_A("nested", t5, [0, 1], {}))
    for name, key in (("39_nested_subjects", "n_subjects"), ("40_nested_superplot", "n_superplot")):
        g5.set_spec(apply_preset(g5.spec, key, t5.used_columns()))
        w.show_sheet(g5)
        shot(w, name)
    w.show_sheet(a7)
    shot(w, "41_nested_t_test")
    dlg = FormatGraphDialog(g5, p, "arrangement", parent=w)
    dlg.show()
    shot(dlg, "42_format_arrangement")
    dlg.close()

    # XY data (M5): curve fitting, linear regression, correlation, frequency graphs.
    import numpy as _np
    from ..analysis.models import BY_KEY as _MODELS
    from .dialogs.params_xy import NonlinParamsDialog
    t6 = p.add_table("Dose response curve", table_type="xy", y_format="replicates", replicates=3)
    rng6 = _np.random.default_rng(3)
    f4 = _MODELS["agonist_4"].f
    for r, x in enumerate(_np.arange(-9, -4.5, 0.5)):
        t6.set(r, "x", float(x), emit=False)
        for k in range(3):
            t6.set(r, t6.flat(0, k), round(float(f4(x, 0, 100, -7, 1) + rng6.normal(0, 3)), 1), emit=False)
            t6.set(r, t6.flat(1, k), round(float(f4(x, 0, 100, -6.2, 1) + rng6.normal(0, 3)), 1), emit=False)
    t6.titles[:2] = ["Agonist", "Agonist + antagonist"]
    t6.changed.emit()
    g6 = next(g for g in p.graphs if g.home is t6)
    g6.spec.x.title, g6.spec.y.title = "log[agonist], M", "Response (%)"
    w.show_sheet(t6)
    shot(w, "43_xy_table")
    a8 = p.add_analysis(_A("nonlin", t6, [0, 1], {"model": "agonist_4", "bands": "confidence",
                                                   "compare": "param", "compare_param": "LogEC50"}))
    w.show_sheet(g6)
    shot(w, "44_xy_curve_fit")
    w.show_sheet(a8)
    shot(w, "45_nonlin_results")
    dlg = NonlinParamsDialog(a8.params, 2, w)
    dlg.show()
    shot(dlg, "46_nonlin_model")
    dlg.show_section("constrain")
    shot(dlg, "47_nonlin_constrain")
    dlg.close()
    t7 = p.add_table("Insulin sensitivity", table_type="xy", example=True)
    a9 = p.add_analysis(_A("linreg", t7, t7.used_columns(), {"bands": "confidence", "compare": True}))
    w.show_sheet(a9)
    shot(w, "48_linreg_results")
    w.show_sheet(next(g for g in p.graphs if g.home is t7))
    shot(w, "49_linreg_graph")
    a10 = p.add_analysis(_A("correlation", t7, t7.used_columns(), {"method": "spearman"}))
    w.show_sheet(a10)
    shot(w, "50_correlation")
    a11 = p.add_analysis(_A("frequency", t3, [0, 1, 2, 3], {}))
    w._result_graph(a11)
    w.show_sheet(next(g for g in p.graphs if g.source is a11))
    shot(w, "51_histogram")
    dlg = GraphTypeDialog(g6, p, w)
    dlg.show()
    shot(dlg, "52_xy_gallery")
    dlg.close()
    dlg = FormatGraphDialog(g6, p, "style", parent=w)
    dlg.show()
    shot(dlg, "53_format_xy_style")
    dlg.close()

    # Contingency, survival, parts of whole (M6).
    from .dialogs.params_counts import ContingencyParamsDialog
    t8 = p.add_table("Response to treatment", table_type="contingency", example=True)
    a12 = p.add_analysis(_A("contingency", t8, t8.used_columns(), {}))
    w.show_sheet(a12)
    shot(w, "54_contingency_results")
    w._widget_for(a12).tabs.setCurrentIndex(1)
    shot(w, "55_contingency_effects")
    dlg = ContingencyParamsDialog(a12.params, True, w)
    dlg.show_section("intervals")
    dlg.show()
    shot(dlg, "56_contingency_settings")
    dlg.close()
    w.show_sheet(next(g for g in p.graphs if g.home is t8))
    shot(w, "57_contingency_graph")
    t9 = p.add_table("Seizure-free survival", table_type="survival", example=False)
    rng9 = _np.random.default_rng(4)
    for r in range(40):
        grp = r % 2
        t9.set(r, "x", float(round(rng9.exponential(12 if grp == 0 else 24), 1)), emit=False)
        t9.set(r, t9.flat(grp), 0.0 if rng9.random() < 0.25 else 1.0, emit=False)
    t9.titles[:2] = ["Vehicle", "Treated"]
    t9.changed.emit()
    g9 = next(g for g in p.graphs if g.home is t9)
    g9.spec.x.title = "Days"
    g9.spec.surv_ci = "shaded"
    w.show_sheet(g9)
    shot(w, "58_survival_graph")
    a13 = p.add_analysis(_A("survival", t9, [0, 1], {}))
    w.show_sheet(a13)
    shot(w, "59_survival_results")
    t10 = p.add_table("Cell types", table_type="parts", example=True)
    g10 = next(g for g in p.graphs if g.home is t10)
    g10.spec.parts_layout = "donut"
    w.show_sheet(g10)
    shot(w, "60_donut")

    # Transforms and result tables (M7).
    from .dialogs.params_transforms import SmoothParamsDialog
    a14 = p.add_analysis(_A("normalize", t6, [0, 1], {}))
    w._result_graph(a14)
    w.show_sheet(a14)
    shot(w, "61_normalize_results")
    w.show_sheet(next(g for g in p.graphs if g.source is a14))
    shot(w, "62_normalize_graph")
    out14 = a14.output_table()
    a15 = p.add_analysis(_A("nonlin", out14, out14.used_columns(), {"model": "agonist_norm_var"}))
    w.show_sheet(a15)
    shot(w, "63_chain_fit_of_normalized")
    dlg = SmoothParamsDialog(None, w)
    dlg.show()
    shot(dlg, "64_smooth_settings")
    dlg.close()

    # Figures (M8).
    from .dialogs.figure import AddPanelsDialog, FormatFigureDialog
    fig = p.add_figure()
    w._place_panels(fig, [("graph", g4.id), ("graph", g6.id), ("graph", g9.id), ("graph", g10.id)], 2)
    import copy as _copy
    from ..doc.commands import FigureCommand
    st = _copy.deepcopy(fig.state())
    pw_, ph_ = fig.page_mm()
    st["panels"].append(fig.new_panel("text", "", x=15.0, y=ph_ - 45.0, w=pw_ - 30.0, h=20.0, font_size=9.0,
                                      text="Figure 1. (A) Seizures by week, two-way ANOVA with Šídák comparisons. "
                                           "(B) Dose-response curves with 95% confidence bands. (C) Seizure-free "
                                           "survival. (D) Cell types."))
    p.undo.push(FigureCommand(fig, st, "Add Text"))
    w.show_sheet(fig)
    fv = w._figure_view()
    fv.fit_page()
    pump(10)
    shot(w, "65_figure")
    dlg = FormatFigureDialog(fig, w)
    dlg.show_section("letters")
    dlg.show()
    shot(dlg, "66_format_figure")
    dlg.close()
    dlg = AddPanelsDialog(p, preselect={g4.id}, parent=w)
    dlg.show()
    shot(dlg, "67_add_to_figure")
    dlg.close()

    # Dark mode: a fresh window after switching the app's colour scheme.
    try:
        app.styleHints().setColorScheme(Qt.ColorScheme.Dark)
        pump(20)
        d = MainWindow(sample_project(engine))
        d.show()
        pump(30)
        shot(d, "10_dark_table")
        d.show_sheet(d.project.graphs[0])
        shot(d, "11_dark_graph")
        d.close()
    except Exception as e:  # colour-scheme override needs Qt 6.8+
        print("dark mode shot skipped:", e)
    w.close()
    return 0
