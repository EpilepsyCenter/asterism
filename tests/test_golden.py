"""Golden-dataset tests: ASTERISM vs real GraphPad Prism output (SPEC §13 step 4).

Ground truth extracted from the lab's Prism projects (see extract_prism.py). The point
is trust when numbers are questioned (SPEC §8) — and these caught a real one: pingouin's
default Mann-Whitney uses the normal approximation, disagreeing with Prism's exact test
by ~17× on a clean small sample. ASTERISM now matches Prism's exact result.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from asterism.core.contract import Dataset
from asterism.core.stats import run_analysis

GOLDEN = json.loads((Path(__file__).parent / "golden" / "prism_golden.json").read_text())
CASES = GOLDEN["cases"]


def _two_group_ds(groups: dict) -> Dataset:
    rows = []
    for gname, vals in groups.items():
        for i, v in enumerate(vals):
            rows.append({"value": v, "subject": f"{gname}{i}", "group": gname})
    return Dataset(pd.DataFrame(rows), factors=("group",))


@pytest.mark.parametrize("case_key", ["qpcr_deltaCt_mannwhitney", "qpcr_ddCt_mannwhitney"])
def test_mannwhitney_matches_prism_exact(case_key):
    case = CASES[case_key]
    ds = _two_group_ds(case["groups"])
    # Prism ran Mann-Whitney (non-parametric) → force that branch.
    res = run_analysis(ds, parametric=False)
    assert res.test == "Mann–Whitney U"
    # U: Prism prints the minimum U (0 here) — ASTERISM matches the convention.
    assert res.statistic == pytest.approx(case["prism"]["U"], abs=1e-9)
    # p: must match Prism's EXACT p, not the normal approximation.
    assert res.p == pytest.approx(case["prism"]["p_exact"], rel=1e-3)
    assert res.settings["mwu_method"] == "exact"


def test_mannwhitney_default_would_have_used_approx():
    """Documents the trap: the normal approximation (what pingouin defaults to, and
    what Prism labels 'approximate') is ~17× larger here. The fix is to prefer exact."""
    case = CASES["qpcr_deltaCt_mannwhitney"]
    g = case["groups"]
    _, p_approx = stats.mannwhitneyu(g["EGFP"], g["SV2A"],
                                     alternative="two-sided", method="asymptotic")
    assert p_approx == pytest.approx(case["prism"]["p_approx"], rel=1e-3)
    # and it really is far from the exact value Prism reports
    assert p_approx > 10 * case["prism"]["p_exact"]


def test_welch_formula_matches_prism():
    """ASTERISM's Welch (pingouin correction=True, itself cross-checked against scipy
    in test_stats) reproduces Prism's Welch t/df/p from the Ephys TTX-amplitude test."""
    case = CASES["ephys_ttx_amplitude_welch"]
    s = case["summary"]
    t, p = stats.ttest_ind_from_stats(
        s["SV2A"]["mean"], s["SV2A"]["sd"], s["SV2A"]["n"],
        s["EGFP"]["mean"], s["EGFP"]["sd"], s["EGFP"]["n"], equal_var=False)
    n1, sd1, n2, sd2 = s["SV2A"]["n"], s["SV2A"]["sd"], s["EGFP"]["n"], s["EGFP"]["sd"]
    df = ((sd1**2/n1 + sd2**2/n2)**2 /
          ((sd1**2/n1)**2/(n1-1) + (sd2**2/n2)**2/(n2-1)))
    assert t == pytest.approx(case["prism"]["t"], rel=1e-4)
    assert df == pytest.approx(case["prism"]["df"], rel=1e-4)
    assert p == pytest.approx(case["prism"]["p"], rel=1e-4)
