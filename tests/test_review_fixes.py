"""Fixes from the help-writing review: excluded values in paired tests, replicate pairing in
paired multiple t tests, the KS test's tails, nested intervals, unknowns in regression."""

from __future__ import annotations

import numpy as np
import pytest
from scipy import stats

from asterism.analysis import engine
from asterism.doc.model import Analysis, Project


def _rows(page) -> dict:
    return {lab: vals for lab, vals, _ in page.rows}


def _column(groups):
    p = Project(engine)
    t = p.add_table(table_type="column")
    for c, vals in enumerate(groups):
        for r, v in enumerate(vals):
            t.set(r, c, v, emit=False)
    return p, t


def test_paired_t_leaves_out_excluded_values():
    a = [10.0, 12.0, 11.0, 14.0, 13.0, 100.0]
    b = [12.0, 15.0, 12.5, 16.0, 15.5, 0.0]
    p, t = _column([a, b])
    t.set_excluded([(5, 0)], True, emit=False)            # the outlier pair goes
    an = p.add_analysis(Analysis("ttest", t, [0, 1], {"design": "paired"}))
    assert an.result.error is None
    assert an.result.p == pytest.approx(stats.ttest_rel(a[:5], b[:5]).pvalue, rel=1e-9)


def test_paired_multiple_t_pairs_replicates_by_position():
    p = Project(engine)
    t = p.add_table(table_type="grouped", y_format="replicates", replicates=4, ncols=2, example=False)
    a = [1.0, None, 3.0, 4.0]                              # a gap in the middle of the row
    b = [2.0, 9.0, 3.5, 6.0]
    for k in range(4):
        if a[k] is not None:
            t.set(0, t.flat(0, k), a[k], emit=False)
        t.set(0, t.flat(1, k), b[k], emit=False)
    an = p.add_analysis(Analysis("multiple_t", t, [0, 1], {"test": "paired", "correction": "none"}))
    assert an.result.error is None, an.result.error
    want = stats.ttest_rel([1.0, 3.0, 4.0], [2.0, 3.5, 6.0]).pvalue
    text = repr([pg.rows for pg in an.result.pages])
    from asterism.analysis.results import fmt_p
    assert fmt_p(want) in text


def test_ks_is_always_two_sided():
    a, b = [1.0, 2, 3, 4, 5, 6], [4.0, 5, 6, 7, 8, 9]
    p, t = _column([a, b])
    two = p.add_analysis(Analysis("ttest", t, [0, 1], {"distribution": "nonparametric", "test": "ks"}))
    one = p.add_analysis(Analysis("ttest", t, [0, 1], {"distribution": "nonparametric", "test": "ks",
                                                       "tails": 1}))
    assert one.result.p == pytest.approx(two.result.p)
    assert _rows(one.result.pages[0])["Tails"] == ["Two-sided"]


def test_nested_t_interval_follows_the_confidence_level():
    p = Project(engine)
    t = p.add_table(table_type="nested", example=True)
    an = p.add_analysis(Analysis("nested", t, [0, 1], {"conf": 0.99}))
    assert an.result.error is None, an.result.error
    labels = [lab for lab, _, _ in an.result.pages[0].rows]
    assert "99% CI of the difference" in labels


def test_regression_unknowns_ignore_other_data_sets_rows():
    p = Project(engine)
    t = p.add_table(table_type="xy")
    for r, (x, ya, yb) in enumerate([(1, 2, None), (2, 4, None), (3, 6, None),
                                     (4, None, 1), (5, None, 2), (6, None, 3)]):
        t.set(r, "x", float(x), emit=False)
        if ya is not None:
            t.set(r, 0, float(ya), emit=False)
        if yb is not None:
            t.set(r, 1, float(yb), emit=False)
    an = p.add_analysis(Analysis("linreg", t, [0, 1], {"interpolate": True}))
    assert an.result.error is None, an.result.error
    page = next(pg for pg in an.result.pages if any("→" in str(v) or "unknowns" in lab.lower()
                                                      for lab, v, _ in pg.rows))
    assert not any("X → Y" in vals for _, vals, _ in page.rows)


def test_alpha_reaches_every_analysis():
    """The significance level set for an analysis (Settings › New analyses) is used in its
    'Significant at α' answers, not a fixed 0.05."""
    a, b = [1.0, 2, 3, 4, 5, 6], [2.0, 3.5, 4, 5.5, 6, 8]
    p, t = _column([a, b])
    an = p.add_analysis(Analysis("ttest", t, [0, 1], {"alpha": 0.5}))
    rows = _rows(an.result.pages[0])
    assert "Significant at α = 0.5" in rows and "Significant at α = 0.05" not in rows
    want = "Yes" if an.result.p < 0.5 else "No"
    assert rows["Significant at α = 0.5"] == [want]
    p3, t3 = _column([a, b, [5.0, 6, 7, 8, 9, 10]])
    an1 = p3.add_analysis(Analysis("anova1", t3, [0, 1, 2], {"alpha": 0.01}))
    assert an1.result.error is None
    labels = [lab for pg in an1.result.pages for lab, _, _ in pg.rows]
    assert any("α = 0.01" in lab for lab in labels)


def test_notes_typing_is_undoable_in_one_step():
    from asterism.doc.commands import InfoCommand
    p = Project(engine)
    info = p.add_info()
    n0 = p.undo.index
    for text in ("a", "ab", "abc"):                     # typing: merged into one step
        p.undo.push(InfoCommand(info, None, text))
    p.undo.push(InfoCommand(info, "Experimenter", "ML"))
    assert info.notes == "abc" and info.fields["Experimenter"] == "ML"
    p.undo.undo()
    assert info.fields["Experimenter"] == ""
    p.undo.undo()
    assert info.notes == "" and p.undo.index == n0
    p.undo.redo()
    assert info.notes == "abc"
