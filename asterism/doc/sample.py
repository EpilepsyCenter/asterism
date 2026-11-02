"""Built-in projects: the empty starting project and a small worked example (used by the
tests and the startup self-test; File › Open Sample Project opens app/example.py's larger one)."""

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
    t = p.new_table("Response score")
    t.titles[0], t.titles[1] = "Control", "Treated"
    control = [52, 61, 47, 70, 58, 66, 49, 73, 55, 62]
    treated = [31, 40, 28, 45, 36, 22, 39, 33, 41, 29]
    for r, (a, b) in enumerate(zip(control, treated)):
        t.set(r, 0, a, emit=False)
        t.set(r, 1, b, emit=False)
    p.insert(t)
    g = p.new_graph(t)
    g.spec.y.title = "Response score"
    p.insert(g)
    p.insert(InfoSheet("Project info 1"))
    p.undo.clear()
    p.mark_saved()
    return p
