"""Export-fidelity CI tests (SPEC §10b, §13 step 4 spirit).

These are the cheap regression guards that fail loudly when a matplotlib bump or
a stray .mplstyle edit breaks one of the non-negotiable export settings. They are
the machine half of the step-0 spike; the human half (open in Affinity, confirm
touch-up-only) can't be automated.
"""

from __future__ import annotations

import numpy as np
import pytest

from asterism.core.export import render_to_bytes
from asterism.core.figure_set import Panel, figure_set
from asterism.core.figures import BarGroup, SubGroup, grouped_bar
from asterism.core.qa import check_svg
from asterism.core.style import LabStyle


def _subgroup(label, mean, seed):
    rng = np.random.default_rng(seed)
    subjects = {
        f"s{i}": np.clip(rng.normal(rng.normal(mean, 1.2), 2.5, 15), 0, None)
        for i in range(6)
    }
    return SubGroup(label=label, subjects=subjects)


def _dataset():
    return [
        BarGroup("WT", [_subgroup("veh", 10.0, 1), _subgroup("CNO", 11.0, 2)]),
        BarGroup("KO", [_subgroup("veh", 10.0, 3), _subgroup("CNO", 16.0, 4)]),
    ]


@pytest.fixture(scope="module")
def lab():
    return LabStyle.load()


def test_single_panel_export_fidelity(lab):
    fig = grouped_bar(
        _dataset(), lab_style=lab,
        comparisons=[(0, 0, 1, 1, 0.0003), (1, 0, 1, 1, 0.0008)],
        y_label="value (pA)", title="test",
    )
    svg = render_to_bytes(fig, "svg")
    report = check_svg(
        svg,
        expected_w_mm=lab["figure"]["width_mm"],
        expected_h_mm=lab["figure"]["height_mm"],
        expected_gids=["axes_main", "bar_WT_veh", "points_subject_KO_CNO",
                       "bracket_0_line", "axis_y"],
    )
    assert report.ok, "\n" + report.summary()


def test_no_bbox_tight_keeps_canvas_exact(lab):
    """Regression guard for the single most damaging mistake: bbox_inches='tight'
    silently resizing the canvas and destroying mm-exactness."""
    fig = grouped_bar(_dataset(), lab_style=lab, y_label="v")
    svg = render_to_bytes(fig, "svg")
    report = check_svg(
        svg,
        expected_w_mm=lab["figure"]["width_mm"],
        expected_h_mm=lab["figure"]["height_mm"],
    )
    size_check = next(c for c in report.checks if c[0] == "canvas_size")
    assert size_check[1], size_check[2]


def test_pdf_has_no_type3_fonts(lab):
    """Type 3 fonts import badly into Affinity; pdf.fonttype:42 must yield TrueType
    (CIDFontType2), never Type3."""
    fig = grouped_bar(_dataset(), lab_style=lab, y_label="v")
    pdf = render_to_bytes(fig, "pdf")
    assert b"/Type3" not in pdf
    assert b"CIDFontType2" in pdf  # TrueType CID embedding


def test_figure_set_named_groups_and_width(lab):
    panels = [
        Panel(_dataset(), width_mm=45, height_mm=40, title="A", rng_seed=1),
        Panel(_dataset(), width_mm=55, height_mm=42, title="B", rng_seed=2),
    ]
    fig = figure_set(panels, lab_style=lab)
    svg = render_to_bytes(fig, "svg")
    # width is fixed to the journal column; height is packed, so don't assert it.
    report = check_svg(
        svg,
        expected_w_mm=lab["figure_set"]["column_width_mm"],
        expected_h_mm=fig.get_size_inches()[1] * 25.4,
        expected_gids=["panel_A", "panel_B", "panel_letter_A",
                       "A_bar_WT_veh", "B_bar_KO_CNO"],
    )
    assert report.ok, "\n" + report.summary()


def test_svg_text_stays_live(lab):
    """svg.fonttype:none must keep text as <text>, not outline it to <path>."""
    fig = grouped_bar(_dataset(), lab_style=lab, y_label="v", title="live")
    svg = render_to_bytes(fig, "svg")
    assert b"<text" in svg
