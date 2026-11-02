"""The example project behind File › Open Sample Project.

One project that shows most of ASTERISM: every table type, the main analyses (t test,
one- and two-way ANOVA, nested t test, curve fitting, regression, correlation,
contingency, survival, normalize, frequency distribution), many graph types (scatter,
SuperPlot, grouped, XY with a fitted curve, survival, donut, horizontal, two Y axes,
bubble) and a finished figure. Names and data are made up and general (Control,
Treated, Vehicle, Drug…): no lab's real experiments.

Built in code rather than shipped as a file, so it always matches the current version.
"""

from __future__ import annotations

import numpy as np

from ..doc.model import Analysis, InfoSheet, Project


def example_project(engine) -> Project:
    from ..analysis.models import BY_KEY as MODELS
    from .dialogs.graph_type import apply_preset
    from .figure.layout import place_panels
    from .graph.drawings import new_drawing

    p = Project(engine)

    def graph_of(t):
        return next(g for g in p.graphs if g.home is t)

    def result_graph(a):
        p.add_sheets([p.new_result_graph(a)], "New Graph")
        return next(g for g in p.graphs if g.source is a)

    def column(name, groups: dict, rng=None):
        t = p.add_table(name, table_type="column")
        for c, (title, vals) in enumerate(groups.items()):
            t.titles[c] = title
            for r, v in enumerate(vals):
                t.set(r, c, float(v), emit=False)
        t.changed.emit()
        return t

    # 1. Two groups: scatter dot plot and an unpaired t test.
    t1 = p.add_table("Response score", table_type="column", example=True)       # Control vs Treated
    g1 = graph_of(t1)
    g1.spec.y.title = "Response score"
    g1.spec.col_width_mm = 20.0                          # room for the group names, upright
    p.add_analysis(Analysis("ttest", t1, [0, 1], {"design": "unpaired", "distribution": "normal",
                                                  "test": "student", "bracket": True, "descriptive": True}))

    # 2. Four doses: one-way ANOVA with brackets, normality tests.
    t2 = column("Dose response", {"Vehicle": [24, 26, 31, 27, 29, 25], "Low": [31, 35, 30, 36, 33, 34],
                                  "Mid": [29, 27, 33, 28, 30, 31], "High": [40, 38, 36, 41, 39, 35]})
    g2 = graph_of(t2)
    g2.spec.y.title = "Response"
    p.add_analysis(Analysis("anova1", t2, [0, 1, 2, 3], {"bracket": True}))
    p.add_analysis(Analysis("normality", t2, [0, 1, 2, 3], {"lognormal": True}))

    # 2b. Many values per group: a frequency distribution, graphed as a histogram.
    rng = np.random.default_rng(5)
    t2b = column("Cell area", {"Control": np.round(rng.normal(100, 15, 120), 1),
                               "Treated": np.round(rng.normal(118, 18, 120), 1)})
    g2b = graph_of(t2b)
    g2b.spec = apply_preset(g2b.spec, "violin", t2b.used_columns())
    g2b.spec.y.title = "Cell area (µm²)"
    g2b.spec.col_width_mm = 20.0
    fg = result_graph(p.add_analysis(Analysis("frequency", t2b, [0, 1], {"bin_width": 10.0})))
    fg.spec.x.title = "Cell area (µm²)"

    # 3. The same design shown sideways: horizontal bars, comparisons with the control.
    rng = np.random.default_rng(3)
    t3 = column("Dose groups", {name: [m + rng.normal(0, 1.5) for _ in range(6)]
                                for name, m in (("Vehicle", 10), ("Low", 14), ("Mid", 11), ("High", 18))})
    for c in range(4):
        for r in range(6):
            t3.set(r, c, round(t3.get(r, c), 1), emit=False)
    t3.changed.emit()
    p.add_analysis(Analysis("anova1", t3, [0, 1, 2, 3], {}))
    g3 = graph_of(t3)
    g3.spec = apply_preset(g3.spec, "h_scatter_bar", t3.used_columns())
    g3.spec.y.title = "Events per week"
    g3.spec.sig.update(which="control", control=0, shape="bracket", label="stars")
    g3.changed.emit()

    # 4. Two factors: two-way ANOVA and multiple t tests on replicates.
    t4 = p.add_table("Activity by day", table_type="grouped", example=True,
                     y_format="replicates", replicates=4)                       # Wild type vs Knockout
    graph_of(t4).spec.y.title = "Activity (counts per hour)"
    p.add_analysis(Analysis("anova2", t4, [0, 1], {"design": "ordinary", "compare": "rows", "method": "sidak",
                                                   "row_factor": "Day", "col_factor": "Genotype"}))
    p.add_analysis(Analysis("multiple_t", t4, [0, 1], {"test": "welch", "correction": "fdr_bky"}))

    # 5. Summary data: means with SD and n typed in, graphed as bars.
    t5 = p.add_table("Means from a paper", table_type="grouped", example=True, y_format="mean_sd_n")
    graph_of(t5).spec.y.title = "Value"

    # 6. Nested data: cells within animals, a SuperPlot and a nested t test.
    t6 = p.add_table("Synapses per neuron", table_type="nested", example=True)  # Control vs Treated
    g6 = graph_of(t6)
    g6.spec.y.title = "Synapses"
    g6.set_spec(apply_preset(g6.spec, "n_superplot", t6.used_columns()))
    p.add_analysis(Analysis("nested", t6, [0, 1], {}))

    # 7. Dose-response curves: nonlinear fit comparing EC50, then normalized and refitted.
    t7 = p.add_table("Dose response curve", table_type="xy", y_format="replicates", replicates=3)
    f4 = MODELS["agonist_4"].f
    rng = np.random.default_rng(3)
    for r, x in enumerate(np.arange(-9, -4.5, 0.5)):
        t7.set(r, "x", float(x), emit=False)
        for k in range(3):
            t7.set(r, t7.flat(0, k), round(float(f4(x, 0, 100, -7, 1) + rng.normal(0, 3)), 1), emit=False)
            t7.set(r, t7.flat(1, k), round(float(f4(x, 0, 100, -6.2, 1) + rng.normal(0, 3)), 1), emit=False)
    t7.titles[:2] = ["Agonist", "Agonist + antagonist"]
    t7.changed.emit()
    g7 = graph_of(t7)
    g7.spec.x.title, g7.spec.y.title = "log[agonist], M", "Response (%)"
    p.add_analysis(Analysis("nonlin", t7, [0, 1], {"model": "agonist_4", "bands": "confidence",
                                                   "compare": "param", "compare_param": "LogEC50"}))
    norm = p.add_analysis(Analysis("normalize", t7, [0, 1], {}))
    result_graph(norm)
    out = norm.output_table()
    p.add_analysis(Analysis("nonlin", out, out.used_columns(), {"model": "agonist_norm_var"}))

    # 8. A time course: linear regression (comparing slopes) and a Spearman correlation.
    t8 = p.add_table("Growth over time", table_type="xy", example=True)         # Vehicle vs Drug
    g8 = graph_of(t8)
    g8.spec.x.title, g8.spec.y.title = "Day", "Size (mm)"
    g8.spec.drawings = [new_drawing("text", 6, 4, 6, 4, text="Dashed lines: 95% confidence bands",
                                    size=9, italic=True)]               # a text drawing
    p.add_analysis(Analysis("linreg", t8, t8.used_columns(), {"bands": "confidence", "compare": True}))
    p.add_analysis(Analysis("correlation", t8, t8.used_columns(), {"method": "spearman"}))

    # 9. Two measures over time on two Y axes, with a reference line and a plotted function.
    t9 = p.add_table("Temperature and activity", table_type="xy")
    t9.titles[0], t9.titles[1] = "Temperature", "Activity"
    for r in range(10):
        t9.set(r, "x", float(r), emit=False)
        t9.set(r, 0, round(36.5 + 0.3 * r + 0.2 * np.sin(r), 2), emit=False)
        t9.set(r, 1, round(12 + 6 * np.cos(r / 2), 2), emit=False)
    t9.changed.emit()
    sp = graph_of(t9).spec
    sp.style(0).connect = sp.style(1).connect = True
    sp.style(1).axis = "right"
    sp.style(1).symbol_shape = "square"
    sp.style(1).symbol_color = "#08519c"
    sp.y.title, sp.y2.title, sp.x.title = "Temperature (°C)", "Activity (counts per hour)", "Day"
    sp.y.grid = True
    sp.y.auto, sp.y.vmin, sp.y.vmax, sp.y.interval = False, 35.0, 40.0, 1.0
    sp.y.extra = [{"value": 38.0, "line": True, "dash": "dash", "label": "fever"}]
    sp.show_legend = True
    sp.functions = [{"id": "f", "text": "Y = 36.5 + 0.3*X", "params": {}, "from": None, "to": None,
                     "color": "#b3261e", "width": 1.0, "dash": "dash"}]
    graph_of(t9).changed.emit()

    # 10. Counts: a contingency table with Fisher's exact test.
    t10 = p.add_table("Response to treatment", table_type="contingency", example=True)
    p.add_analysis(Analysis("contingency", t10, t10.used_columns(), {}))

    # 11. Time to an event: Kaplan-Meier curves with shaded confidence bands, log-rank test.
    t11 = p.add_table("Event-free survival", table_type="survival")
    rng = np.random.default_rng(4)
    for r in range(40):
        grp = r % 2
        t11.set(r, "x", float(round(rng.exponential(12 if grp == 0 else 24), 1)), emit=False)
        t11.set(r, t11.flat(grp), 0.0 if rng.random() < 0.25 else 1.0, emit=False)
    t11.titles[:2] = ["Vehicle", "Treated"]
    t11.changed.emit()
    g11 = graph_of(t11)
    g11.spec.x.title = "Days"
    g11.spec.surv_ci = "shaded"
    p.add_analysis(Analysis("survival", t11, [0, 1], {}))

    # 12. Parts of a whole: a donut chart.
    t12 = p.add_table("Cell types", table_type="parts", example=True)
    graph_of(t12).spec.parts_layout = "donut"

    # 13. Several variables per subject: a bubble plot.
    t13 = p.add_table("Cohort", table_type="multivar", example=True)
    graph_of(t13).spec.mv.update(x=1, y=[2], size=0, color=3, labels=False)

    # A figure of four graphs with a legend underneath.
    fig = p.add_figure()
    fig.name = "Figure 1"
    place_panels(p, fig, [("graph", graph_of(t4).id), ("graph", g7.id), ("graph", g11.id),
                          ("graph", graph_of(t12).id)], 2)
    pw, ph = fig.page_mm()
    fig.panels.append(fig.new_panel(
        "text", "", x=15.0, y=ph - 45.0, w=pw - 30.0, h=20.0, font_size=9.0,
        text="Figure 1. (A) Activity by day in wild-type and knockout animals, two-way ANOVA with "
             "Šídák comparisons. (B) Dose-response curves with 95% confidence bands. (C) Event-free "
             "survival. (D) Cell types."))

    # Notes, and colour labels on the finished pieces.
    notes = InfoSheet("About this example")
    notes.fields["Project"] = "ASTERISM example"
    notes.notes = (
        "This project shows what ASTERISM does, with made-up data.\n\n"
        "Each data table in the sidebar has its analyses and graphs nested under it. Change a value "
        "in a table and its results and graphs update. Double-click anything on a graph to format "
        "it, and see Figure 1 for graphs placed on a page.\n\n"
        "Start your own project with File › New Project.")
    p.insert(notes)
    p.label_names.update({4: "Final", 2: "To check"})
    for s in (fig, g6, g7):
        s.tag = 4
    g3.tag = 2

    p.undo.clear()
    p.mark_saved()
    return p
