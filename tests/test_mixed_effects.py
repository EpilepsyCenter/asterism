"""Mixed-effects model for matched designs with missing values (Prism's method: REML,
compound symmetry, same results as RM ANOVA when nothing is missing).

- Complete Prism data fitted as a mixed model must reproduce Prism's RM ANOVA (golden).
- Gapped data must match R (nlme gls with compound symmetry; lmerTest for three
  variance components): tests/golden/mixed_reference.json.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from asterism.analysis import anova2, engine, mixed
from asterism.doc.model import Analysis, Project

HERE = Path(__file__).parent / "golden"
GOLDEN = json.loads((HERE / "prism_golden.json").read_text())
REF = json.loads((HERE / "mixed_reference.json").read_text())["cases"]


def _cells(case):
    d = case["data"]
    R, K = len(d["rows"]), len(d["sets"])
    return [[d["sets"][k][r] for k in range(K)] for r in range(R)]


@pytest.mark.parametrize("case", GOLDEN["two_way"], ids=lambda c: c["method"])
def test_mixed_model_on_complete_data_equals_prism_rm_anova(case):
    C = _cells(case)
    data = anova2.long_data(C, "rm_rows")
    assert data["complete"]
    fit = anova2.fit_mixed(C, "rm_rows", False, data)
    pr = case["anova"]
    for ours, theirs in (("rows", "rowFactor"), ("cols", "colFactor"), ("inter", "rowFactorVsColFactor")):
        assert fit["table"][ours]["F"] == pytest.approx(pr[theirs]["fTest"]["f"], rel=1e-6)
        assert fit["table"][ours]["dfd"] == pr[theirs]["fTest"]["dfd"]
        assert fit["table"][ours]["p"] == pytest.approx(pr[theirs]["fTest"]["p"], rel=1e-6)
    method = {"Bonferroni-Dunn": "bonferroni", "Tukey": "tukey"}[case["method"]]
    R, K = len(C), len(C[0])
    fams = anova2.comparisons("rm_rows", fit, "both", method, 0.95,
                              [f"r{i}" for i in range(R)], [f"c{i}" for i in range(K)])
    ours = {frozenset(pair): r for _, res, pairs in fams for r, pair in zip(res, pairs)}
    for cp in case["comparisons"]:
        o = ours[frozenset(((cp["a"]["row"], cp["a"]["col"]), (cp["b"]["row"], cp["b"]["col"])))]
        assert o["se"] == pytest.approx(cp["se"], rel=1e-6)
        assert o["df"] == cp["df"]
        assert o["p"] == pytest.approx(cp["p_adj"], rel=1e-5, abs=1e-12)


def _fit_ref(key):
    c = REF[key]
    y, a, b, s = (np.array(c[k]) for k in ("y", "a", "b", "s"))
    X, sl, _ = mixed.two_factor_design(a, b, c["R"], c["K"])
    Zs = [mixed.indicator(s)]
    if key == "rm_both":
        Zs += [mixed.indicator(np.char.add(s.astype(str), a.astype(str))),
               mixed.indicator(np.char.add(np.char.add(s.astype(str), "c"), b.astype(str)))]
    f = mixed.fit(y, X, Zs)
    F = [f.wald(mixed.L_for(sl[k], X.shape[1]))[0] for k in ("a", "b", "ab")]
    return f, F, c["r"]


@pytest.mark.parametrize("key", ["rm_rows", "rm_cols"])
def test_compound_symmetry_with_gaps_matches_r_nlme(key):
    f, F, r = _fit_ref(key)
    assert F == pytest.approx(r["F"], rel=2e-5)
    assert f.loglik == pytest.approx(r["loglik"], abs=1e-6)
    total = f.sigma2 + f.variances[0]
    assert total == pytest.approx(r["sigma2_total"], rel=1e-5)
    assert f.variances[0] / total == pytest.approx(r["rho"], rel=1e-5)


def test_three_variance_components_with_gaps_match_r_lmertest():
    f, F, r = _fit_ref("rm_both")
    assert F == pytest.approx(r["F"], rel=1e-4)
    # R order: s:a, s:b, s, residual — ours: subject, subject×row, subject×column
    sa, sb, s_, res = r["variances"]
    assert f.variances == pytest.approx([s_, sa, sb], rel=1e-4)
    assert f.sigma2 == pytest.approx(res, rel=1e-4)
    assert f.loglik == pytest.approx(r["loglik"], abs=1e-5)


def test_negative_subject_variance_is_allowed():
    """Compound symmetry may have a negative covariance (as RM ANOVA implies); the fit must
    then still equal RM ANOVA rather than stopping at zero."""
    rng = np.random.default_rng(0)
    n, k = 8, 3
    base = rng.normal(0, 1, (n, k))
    Y = base - base.mean(axis=1, keepdims=True) * 1.6 + np.arange(k)    # anti-correlated within subject
    from asterism.analysis.anova import rm_anova
    ref = rm_anova(Y, False)
    y = Y.ravel()
    g = np.tile(np.arange(k), n)
    s = np.repeat(np.arange(n), k)
    X = np.column_stack([np.ones(len(y)), mixed.effect_codes(g, k)])
    f = mixed.fit(y, X, [mixed.indicator(s)])
    assert f.variances[0] < 0
    F, q = f.wald(mixed.L_for(slice(1, k), X.shape[1]))
    assert F == pytest.approx(ref["F"], rel=1e-6)
    assert f.df_resid == ref["df_r"]


# ---------------------------------------------------------------------------
# Through the document model
# ---------------------------------------------------------------------------

def _grouped(seed=1, reps=5):
    p = Project(engine)
    t = p.add_table(table_type="grouped", y_format="replicates", replicates=reps, ncols=2, example=False)
    rng = np.random.default_rng(seed)
    for ds in range(2):
        for s in range(reps):
            subj = rng.normal(0, 2)
            for r in range(3):
                t.set(r, t.flat(ds, s), float(10 + 2 * ds + r + subj + rng.normal(0, 1)), emit=False)
    t.changed.emit()
    return p, t


def test_two_way_switches_to_mixed_model_only_when_values_are_missing():
    p, t = _grouped()
    a = p.add_analysis(Analysis("anova2", t, [0, 1], {"design": "rm_rows"}))
    assert [pg.title for pg in a.result.pages][:2] == ["Results", "ANOVA table"]
    complete_p = a.result.p
    t.set(1, t.flat(0, 2), None)
    assert a.result.error is None
    assert [pg.title for pg in a.result.pages][:2] == ["Results", "Fixed effects"]
    assert a.result.pages[0].columns == ["Mixed-effects analysis"]
    assert a.result.p != complete_p
    labels = [r[0] for r in a.result.pages[0].rows]
    assert "Missing values" in labels and "χ² (likelihood ratio)" in labels


def test_always_mixed_equals_rm_anova_when_complete():
    p, t = _grouped()
    for design in ("rm_rows", "rm_cols", "rm_both"):
        a = p.add_analysis(Analysis("anova2", t, [0, 1], {"design": design}))
        m = p.add_analysis(Analysis("anova2", t, [0, 1], {"design": design, "rm_method": "mixed"}))
        assert m.result.error is None, (design, m.result.error)
        assert m.result.p == pytest.approx(a.result.p, rel=1e-6), design
        pa = [c[2] for c in a.result.cell_comparisons]
        pm = [c[2] for c in m.result.cell_comparisons]
        assert pm == pytest.approx(pa, rel=1e-5), design


def test_rm_anova_only_refuses_missing_values():
    p, t = _grouped()
    t.set(0, t.flat(1, 1), None)
    a = p.add_analysis(Analysis("anova2", t, [0, 1], {"design": "rm_rows", "rm_method": "anova"}))
    assert "missing" in a.result.error


@pytest.mark.parametrize("design", ["rm_rows", "rm_cols", "rm_both"])
@pytest.mark.parametrize("compare", ["both", "cells", "main_cols", "main_rows"])
def test_mixed_model_every_design_and_comparison(design, compare):
    p, t = _grouped(seed=3)
    t.set(2, t.flat(0, 0), None)
    t.set(0, t.flat(1, 3), None)
    a = p.add_analysis(Analysis("anova2", t, [0, 1], {"design": design, "compare": compare,
                                                       "gg": True}))
    assert a.result.error is None, a.result.error
    assert "Comparisons" in [pg.title for pg in a.result.pages]


def test_one_way_rm_with_missing_values():
    p = Project(engine)
    t = p.add_table(table_type="column", example=False)
    rng = np.random.default_rng(4)
    for r in range(8):
        subj = rng.normal(0, 3)
        for c in range(3):
            t.set(r, c, float(20 + 2 * c + subj + rng.normal(0, 1)), emit=False)
    t.changed.emit()
    full = p.add_analysis(Analysis("anova1", t, [0, 1, 2], {"design": "rm", "gg": False}))
    forced = p.add_analysis(Analysis("anova1", t, [0, 1, 2], {"design": "rm", "gg": False, "rm_method": "mixed"}))
    assert forced.result.p == pytest.approx(full.result.p, rel=1e-6)
    assert [c[2] for c in forced.result.comparisons] == pytest.approx(
        [c[2] for c in full.result.comparisons], rel=1e-5)
    t.set(2, 1, None)
    assert full.result.error is None
    assert full.result.pages[1].title == "Fixed effects"
    dun = p.add_analysis(Analysis("anova1", t, [0, 1, 2], {"design": "rm", "compare": "control",
                                                           "method": "dunnett"}))
    assert dun.result.error is None and len(dun.result.comparisons) == 2
    only = p.add_analysis(Analysis("anova1", t, [0, 1, 2], {"design": "rm", "rm_method": "anova"}))
    assert "missing" in only.result.error

