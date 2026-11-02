"""File › Open Sample Project: the example project (app/example.py)."""

from __future__ import annotations

import zipfile


def test_example_project_computes_saves_and_reopens(app, tmp_path):
    from asterism.analysis import engine
    from asterism.app.example import example_project
    from asterism.app.figure.layout import build_figure
    from asterism.app.graph.layout import build
    from asterism.doc import fileformat

    p = example_project(engine)
    types = {t.table_type for t in p.tables}
    assert types >= {"column", "xy", "grouped", "nested", "contingency", "survival", "parts", "multivar"}
    kinds = {a.analysis_type for a in p.analyses}
    assert kinds >= {"ttest", "anova1", "anova2", "nested", "nonlin", "linreg", "correlation",
                     "contingency", "survival", "normalize", "frequency", "normality", "multiple_t"}
    for a in p.analyses:                                 # every analysis has a result, no errors
        assert a.result is not None and not a.result.error, (a.name, a.result.error)
    for g in p.graphs:                                   # every graph draws
        els, _ = build(g)
        assert els, g.name
    fig = next(s for s in p.figures)
    _, els = build_figure(fig, p)
    assert len([e for e in els if e.kind == "graph"]) == 4
    assert not p.undo.can_undo() and not p.is_modified()

    path = tmp_path / "example.asterism"
    fileformat.save(p, path)
    q = fileformat.load(path, engine)
    assert [s.name for s in q.tables] == [s.name for s in p.tables]
    assert len(q.analyses) == len(p.analyses) and len(q.graphs) == len(p.graphs)
    text = zipfile.ZipFile(path).read("project.json").decode().lower()
    for word in ("sv2a", "egfp", "cumulative se"):       # made-up, general names only
        assert word not in text, word


def test_open_sample_opens_the_example(app):
    from asterism.app.main_window import open_sample
    w = open_sample()
    try:
        assert len(w.project.tables) >= 10 and w.project.figures
    finally:
        w.project.mark_saved()
        w.close()
