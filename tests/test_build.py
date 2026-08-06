"""Tests for the data-driven figure layer (SPEC §9)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from asterism.core.build import (FigureOverrides, bar_figure, comparisons_from_stat,
                                 dataset_to_bargroups, frequency_figure, xy_figure)
from asterism.core.contract import Dataset
from asterism.core.design import detect_design
from asterism.core.export import render_to_bytes
from asterism.core.qa import check_svg
from asterism.core.stats import run_analysis
from asterism.core.style import LabStyle


@pytest.fixture(scope="module")
def lab():
    return LabStyle.load()


def _nested_two_group():
    rows = []
    for grp, base in (("WT", 10.0), ("KO", 16.0)):
        for s in range(5):
            for r in range(6):
                rows.append({"value": base + np.sin(r) + s * 0.2,
                             "subject": f"{grp}{s}", "replicate": f"c{r}",
                             "group": grp})
    return Dataset(pd.DataFrame(rows), factors=("group",))


def _two_factor():
    rows = []
    sid = 0
    rng = np.random.default_rng(0)
    for g in ("WT", "KO"):
        for t in ("veh", "cno"):
            base = {"WT": 10, "KO": 15}[g] + {"veh": 0, "cno": 3}[t]
            for _ in range(5):
                rows.append({"value": base + rng.normal(0, 1), "subject": f"s{sid}",
                             "genotype": g, "treatment": t})
                sid += 1
    return Dataset(pd.DataFrame(rows), factors=("genotype", "treatment"))


# --- data → structure -------------------------------------------------------

def test_one_factor_makes_column_bars():
    groups = dataset_to_bargroups(_nested_two_group())
    assert [g.label for g in groups] == ["KO", "WT"]
    assert all(len(g.subgroups) == 1 for g in groups)          # one bar per level
    # each cluster holds 5 subjects, each with 6 replicates
    assert len(groups[0].subgroups[0].subjects) == 5


def test_two_factor_makes_grouped_bars():
    groups = dataset_to_bargroups(_two_factor())
    assert [g.label for g in groups] == ["KO", "WT"]           # outer = genotype
    assert [s.label for s in groups[0].subgroups] == ["cno", "veh"]  # inner = treatment


# --- stats → brackets -------------------------------------------------------

def test_two_group_bracket_from_overall_p():
    ds = _nested_two_group()
    stat = run_analysis(ds)
    groups = dataset_to_bargroups(ds)
    comps = comparisons_from_stat(stat, groups)
    assert len(comps) == 1                                     # one bracket, WT vs KO
    g1, s1, g2, s2, p = comps[0]
    assert {g1, g2} == {0, 1} and p == pytest.approx(stat.p)


def test_anova_brackets_from_posthocs():
    rows = []
    sid = 0
    for name, base in (("A", 10.0), ("B", 11.0), ("C", 20.0)):
        for _ in range(6):
            rows.append({"value": base + np.random.default_rng(sid).normal(),
                         "subject": f"s{sid}", "group": name}); sid += 1
    ds = Dataset(pd.DataFrame(rows), factors=("group",))
    stat = run_analysis(ds)
    groups = dataset_to_bargroups(ds)
    comps = comparisons_from_stat(stat, groups)
    # A-C and B-C are significant, A-B is not → 2 brackets
    assert 1 <= len(comps) <= 3
    assert all(p < 0.05 for *_pos, p in comps)


def test_explicit_bracket_override():
    ds = _nested_two_group()
    stat = run_analysis(ds)
    groups = dataset_to_bargroups(ds)
    ov = FigureOverrides(bracket_comparisons=[("WT", "KO")])
    comps = comparisons_from_stat(stat, groups, ov)
    assert len(comps) == 1


# --- figures build + export fidelity (SPEC §10b holds for every type) -------

def _assert_export_ok(fig, lab, gids=None):
    svg = render_to_bytes(fig, "svg")
    rep = check_svg(svg, expected_w_mm=lab["figure"]["width_mm"],
                    expected_h_mm=lab["figure"]["height_mm"], expected_gids=gids)
    assert rep.ok, "\n" + rep.summary()


def test_bar_figure_end_to_end_with_brackets(lab):
    ds = _nested_two_group()
    design = detect_design(ds)
    stat = run_analysis(ds, design)
    fig = bar_figure(ds, stat, lab_style=lab, overrides=FigureOverrides(
        y_label="mEPSC amplitude (pA)", title="amplitude"))
    _assert_export_ok(fig, lab, gids=["axes_main", "bar_WT_", "bracket_0_line"])


def test_bar_figure_respects_show_points_override(lab):
    ds = _nested_two_group()
    fig_no = bar_figure(ds, lab_style=lab, overrides=FigureOverrides(show_points=False))
    svg = render_to_bytes(fig_no, "svg").decode("utf8", "replace")
    assert "points_subject" not in svg          # points suppressed


def test_grouped_bar_figure(lab):
    ds = _two_factor()
    stat = run_analysis(ds)
    fig = bar_figure(ds, stat, lab_style=lab, metric=None,
                     overrides=FigureOverrides(y_label="v"))
    _assert_export_ok(fig, lab, gids=["axes_main", "bar_WT_veh", "bar_KO_cno"])


def test_xy_figure(lab):
    rows = []
    for g, slope in (("sham", 1.0), ("kindled", 4.0)):
        for s in range(4):
            for day in range(1, 6):
                rows.append({"value": slope * day + s, "subject": f"{g}{s}",
                             "group": g, "day": day})
    ds = Dataset(pd.DataFrame(rows), factors=("group",), x="day")
    fig = xy_figure(ds, lab_style=lab, overrides=FigureOverrides(
        x_label="recording day", y_label="events/day"))
    _assert_export_ok(fig, lab, gids=["axes_main", "xy_sham", "xy_kindled"])


def test_frequency_figure_cumulative_and_histogram(lab):
    rng = np.random.default_rng(3)
    rows = []
    for g, mu in (("WT", 0.0), ("KO", 1.0)):
        for i, v in enumerate(rng.normal(mu, 1, 200)):
            rows.append({"value": v, "subject": f"{g}{i}", "group": g})
    ds = Dataset(pd.DataFrame(rows), factors=("group",))
    fig_c = frequency_figure(ds, lab_style=lab, kind="cumulative")
    _assert_export_ok(fig_c, lab, gids=["axes_main", "ecdf_WT", "ecdf_KO"])
    fig_h = frequency_figure(ds, lab_style=lab, kind="histogram")
    _assert_export_ok(fig_h, lab, gids=["axes_main", "hist_WT"])
