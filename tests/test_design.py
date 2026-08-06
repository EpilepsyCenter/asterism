"""Tests for design detection → test selection (SPEC §8)."""

from __future__ import annotations

import pandas as pd

from asterism.core.contract import Dataset
from asterism.core.design import WELCH_CAVEAT, detect_design


def _between(levels, n_subj=5):
    """Independent-groups long frame: distinct subjects per level."""
    rows = []
    sid = 0
    for lv in levels:
        for _ in range(n_subj):
            rows.append({"value": 1.0, "subject": f"s{sid}", "group": lv})
            sid += 1
    return Dataset(pd.DataFrame(rows), factors=("group",))


def _within(levels, n_subj=5):
    """Repeated-measures long frame: same subjects across all levels."""
    rows = []
    for s in range(n_subj):
        for lv in levels:
            rows.append({"value": 1.0, "subject": f"s{s}", "cond": lv})
    return Dataset(pd.DataFrame(rows), factors=("cond",))


def test_two_level_unpaired_is_welch_with_caveat():
    res = detect_design(_between(["A", "B"]))
    assert res.design == "one_factor_2_unpaired"
    assert res.recommended_test.name == "Welch's t-test"
    assert res.recommended_test.nonparametric_alternative == "Mann–Whitney U"
    assert WELCH_CAVEAT in res.recommended_test.notes


def test_two_level_paired():
    res = detect_design(_within(["pre", "post"]))
    assert res.design == "one_factor_2_paired"
    assert res.recommended_test.name == "Paired t-test"
    assert res.recommended_test.nonparametric_alternative == "Wilcoxon signed-rank"


def test_three_level_one_way_anova():
    res = detect_design(_between(["A", "B", "C"]))
    assert res.design == "one_factor_multi"
    assert res.recommended_test.name == "One-way ANOVA"
    assert "Tukey" in res.recommended_test.posthoc


def test_three_level_rm_anova_geisser():
    res = detect_design(_within(["d1", "d2", "d3"]))
    assert res.design == "one_factor_multi_rm"
    assert "Repeated-measures" in res.recommended_test.name
    assert res.recommended_test.correction == "Geisser–Greenhouse"


def test_two_factor_between():
    rows = []
    sid = 0
    for g in ("WT", "KO"):
        for t in ("veh", "cno"):
            for _ in range(4):
                rows.append({"value": 1.0, "subject": f"s{sid}",
                             "genotype": g, "treatment": t})
                sid += 1
    res = detect_design(Dataset(pd.DataFrame(rows), factors=("genotype", "treatment")))
    assert res.design == "two_factor"
    assert res.recommended_test.name == "Two-way ANOVA"


def test_two_factor_mixed_rm_on_shared():
    # genotype between-subjects, timepoint within-subjects
    rows = []
    sid = 0
    for g in ("WT", "KO"):
        for _ in range(4):
            for t in ("pre", "post"):
                rows.append({"value": 1.0, "subject": f"s{sid}",
                             "genotype": g, "time": t})
            sid += 1
    res = detect_design(Dataset(pd.DataFrame(rows), factors=("genotype", "time")))
    assert res.design == "two_factor"
    assert "Mixed" in res.recommended_test.name
    assert "time" in res.recommended_test.notes[0]


def test_numeric_x_is_regression():
    df = pd.DataFrame({"value": [1, 2, 3], "subject": ["a", "b", "c"],
                       "dose": [0.1, 0.2, 0.3]})
    res = detect_design(Dataset(df, factors=(), x="dose"))
    assert res.design == "regression"
    assert res.recommended_test.name == "Linear regression"


def test_no_factors_ungrouped_ks():
    df = pd.DataFrame({"value": [1, 2, 3], "subject": ["a", "b", "c"]})
    res = detect_design(Dataset(df, factors=()))
    assert res.design == "ungrouped"
    assert not res.detectable
    assert "Kolmogorov" in res.recommended_test.name


def test_single_level_is_degenerate():
    res = detect_design(_between(["only"]))
    assert res.design == "degenerate"
    assert res.recommended_test is None
    assert not res.detectable


def test_result_is_serialisable():
    res = detect_design(_between(["A", "B"]))
    d = res.to_dict()
    assert d["design"] == "one_factor_2_unpaired"
    assert d["recommended_test"]["name"] == "Welch's t-test"
    assert d["factor_facts"][0]["subjects_shared"] is False
