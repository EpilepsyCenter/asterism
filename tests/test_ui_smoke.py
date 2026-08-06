"""UI wiring smoke test (SPEC §11–12).

Drives the real page callbacks with a populated session — the native file picker is
the only thing a test can't click, so we simulate the post-browse state and exercise
everything after it. Skips cleanly where Dash isn't installed (the core test suite
doesn't depend on the UI layer).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

pytest.importorskip("dash")
pytest.importorskip("dash_bootstrap_components")

from fixtures import build_tracer_cohort_summary  # noqa: E402

from asterism.core.importer import sources  # noqa: E402


def _session_with_dataset():
    from asterism_dash import server_state
    from asterism_dash.pages import import_page

    sid = server_state.create_session()
    st = server_state.get_session(sid)
    tmp = Path(tempfile.mkdtemp())
    st.file_path = str(build_tracer_cohort_summary(tmp / "cohort_summary.xlsx"))
    st.sheets = sources.load_sheets_raw(st.file_path)
    st.sheet_plans = sources.classify_sheets(st.sheets)
    import_page.on_build(1, "Cells (long)", [], [], sid, 0)
    return sid, st, tmp


def test_app_constructs_with_all_pages():
    import asterism_dash.main as m
    assert m.app.title == "ASTERISM"
    assert set(m._PAGE_LAYOUTS) == {"import", "analyze", "figure", "export"}


def test_import_build_populates_dataset():
    _sid, st, _tmp = _session_with_dataset()
    assert st.dataset is not None
    assert st.dataset.frame["subject"].nunique() == 4
    assert st.design is not None


def test_analyse_and_figure_and_export_flow():
    from asterism.core.export import export_all
    from asterism_dash.pages import analyze, export as export_pg, figure

    sid, st, tmp = _session_with_dataset()

    analyze.layout(sid)
    analyze.on_run(1, "amplitude_pA", "auto", sid, 0)
    assert st.analyses["amplitude_pA"].test == "Welch's t-test"

    figure.layout(sid)
    figure.on_render(1, "bar", "amplitude_pA", "Amp", "pA", ["on"], "stars", sid, 0)
    assert st.last_figure is not None

    export_pg.layout(sid)
    paths = export_all(st.last_figure, tmp / "out", dpi=100)
    assert paths["svg"].exists() and paths["pdf"].exists()
