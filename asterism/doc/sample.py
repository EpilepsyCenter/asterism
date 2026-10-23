"""Built-in projects: the empty starting project and a small worked example."""

from __future__ import annotations

from .model import AnalysisEngine, InfoSheet, Project


def blank_project(engine: AnalysisEngine | None = None) -> Project:
    """A new project: one empty Column table and its graph, as Prism starts."""
    p = Project(engine)
    t = p.new_table()
    p.insert(t)
    p.insert(p.new_graph(t))
    p.undo.clear()
    p.mark_saved()
    return p


def sample_project(engine: AnalysisEngine | None = None) -> Project:
    p = Project(engine)
    t = p.new_table("Cumulative SE seizure grade")
    t.titles[0], t.titles[1] = "EGFP", "SV2A"
    egfp = [52, 61, 47, 70, 58, 66, 49, 73, 55, 62]
    sv2a = [31, 40, 28, 45, 36, 22, 39, 33, 41, 29]
    for r, (a, b) in enumerate(zip(egfp, sv2a)):
        t.set(r, 0, a, emit=False)
        t.set(r, 1, b, emit=False)
    p.insert(t)
    g = p.new_graph(t)
    g.spec.y.title = "Cumulative SE seizure grade"
    p.insert(g)
    p.insert(InfoSheet("Project info 1"))
    p.undo.clear()
    p.mark_saved()
    return p
