"""`ASTERISM --selftest`: exercise everything a packaged app needs, without a window.

Run by the release builds on each frozen app (macOS, Windows, Linux) to catch files or
libraries the packager left out: help pages, icons, every table type's graph, PDF/SVG/
PNG/EMF output, every analysis (including those built on statsmodels), project files,
spreadsheet import and the main dialogs. Prints one line per check; exit code 0 = all ok.
"""

from __future__ import annotations

import os
import tempfile
import traceback

# table formats for analyses that need more than the default example (three groups; replicates)
FORMATS = {"anova1": {"ncols": 3}, "anova2": {"y_format": "replicates", "replicates": 3},
           "multiple_t": {"y_format": "replicates", "replicates": 3}}
# (analysis, table type, data sets) — each run on the table type's example data
ANALYSES = [
    ("ttest", "column", 2), ("descriptive", "column", 0), ("anova1", "column", 3), ("normality", "column", 0),
    ("onesample", "column", 0), ("outliers", "column", 0), ("frequency", "column", 0),
    ("observed_expected", "column", 1), ("anova2", "grouped", 0), ("multiple_t", "grouped", 2),
    ("nested", "nested", 0), ("linreg", "xy", 0), ("correlation", "xy", 0), ("auc", "xy", 0),
    ("nonlin", "xy", 0), ("contingency", "contingency", 0), ("survival", "survival", 0),
    ("fraction", "parts", 0), ("transform", "xy", 0), ("normalize", "xy", 0), ("baseline", "xy", 0),
    ("prune", "xy", 0), ("transpose", "xy", 0), ("smooth", "xy", 0),
]


def run(app) -> int:
    results: list[tuple[str, bool, str]] = []

    def check(name, fn):
        try:
            fn()
            results.append((name, True, ""))
        except Exception as e:                       # report and carry on
            results.append((name, False, f"{type(e).__name__}: {e}\n{traceback.format_exc(limit=3)}"))

    from asterism import __version__
    from asterism.analysis import engine
    from asterism.doc import fileformat
    from asterism.doc.model import Analysis, Project
    from asterism.doc.table import TABLE_TYPES
    tmp = tempfile.mkdtemp(prefix="asterism-selftest-")

    def help_pages():
        from asterism import help as H
        for slug, _t in H.PAGES:
            if slug != "shortcuts":
                assert len(H.to_html(H.load(slug))) > 500, slug
    check("help pages", help_pages)

    def icons():
        from . import icons as I
        bad = [n for n in I.LUCIDE if I.icon(n).isNull()]
        assert not bad, bad
    check("icons", icons)

    def graphs():
        from .clipboard import render_formats
        from .graph import export
        from .graph.layout import build, content_bounds
        for tt in TABLE_TYPES:
            p = Project(engine)
            p.add_table(table_type=tt, example=True)
            g = p.graphs[-1]
            els, _ = build(g)
            assert els, tt
            fm = render_formats(els, content_bounds(els))
            assert all(fm[k] for k in ("pdf", "svg", "png", "emf")), tt
        export.export_pdf(g, os.path.join(tmp, "g.pdf"))
        export.export_png(g, os.path.join(tmp, "g.png"), 150)
        export.export_svg(g, os.path.join(tmp, "g.svg"))
    check("graphs and export (every table type)", graphs)

    for kind, tt, nsets in ANALYSES:
        def one(kind=kind, tt=tt, nsets=nsets):
            p = Project(engine)
            t = p.add_table(table_type=tt, example=True, **FORMATS.get(kind, {}))
            if kind == "anova1":                     # the example fills two groups; add a third
                for r, v in enumerate([5.1, 6.3, 5.8, 7.0, 6.1, 5.5]):
                    t.set(r, 2, v)
            cols = t.used_columns()
            if nsets:
                cols = cols[:nsets]
            a = p.add_analysis(Analysis(kind, t, cols, {}))
            assert a.result is not None and not a.result.error, a.result.error if a.result else "no result"
        check(f"analysis: {kind}", one)

    def files():
        from asterism.doc.sample import sample_project
        path = os.path.join(tmp, "roundtrip.asterism")
        fileformat.save(sample_project(engine), path)
        back = fileformat.load(path, engine)
        assert back.tables and back.graphs
    check("project files", files)

    def import_csv():
        from asterism.io.build import build_table, guess_plan
        from asterism.io.sheets import read_files
        path = os.path.join(tmp, "data.csv")
        with open(path, "w", encoding="utf-8") as f:
            f.write("Control,Treated\n1.2,3.4\n2.1,4.0\n1.8,3.1\n")
        sheets = read_files([path])
        rows = next(iter(sheets.values()))
        t, _ = build_table(rows, guess_plan(rows))
        assert t.used_columns() == [0, 1]
    check("spreadsheet import", import_csv)

    def dialogs():
        from asterism.doc.sample import sample_project
        from .dialogs.analyze import AnalyzeDialog
        from .dialogs.format_graph import FormatGraphDialog
        from .dialogs.new_table import NewTableDialog
        from .dialogs.settings import SettingsDialog
        from .main_window import MainWindow
        w = MainWindow(sample_project(engine))
        FormatGraphDialog(w.project.graphs[0], w.project)
        AnalyzeDialog(w.project, w.project.tables[0])
        NewTableDialog()
        SettingsDialog()
        w.project.mark_saved()
        w.close()
    check("main window and dialogs", dialogs)

    failed = [r for r in results if not r[1]]
    lines = [f"ASTERISM {__version__} self-test"]
    for name, ok, msg in results:
        lines.append(f"  {'ok  ' if ok else 'FAIL'}  {name}")
        if not ok:
            lines.append("        " + msg.replace("\n", "\n        "))
    lines.append(f"{len(results) - len(failed)} of {len(results)} checks passed")
    report = "\n".join(lines)
    import sys
    if sys.stdout is not None:                   # a windowed app on Windows has no console
        print(report)
    log = os.environ.get("ASTERISM_SELFTEST_LOG")
    if log:
        with open(log, "w", encoding="utf-8") as f:
            f.write(report + "\n")
    return 1 if failed else 0
