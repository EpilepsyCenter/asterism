"""M7: transforms that make result tables, chains of analyses, observed vs expected,
McNemar, residual plots."""

from __future__ import annotations

import math

import numpy as np
import pytest
from scipy import stats

from asterism.analysis import engine
from asterism.doc.model import Analysis, Project


def _xy(reps=3):
    p = Project(engine)
    t = p.add_table(table_type="xy", y_format="replicates", replicates=reps, example=True)
    return p, t


def _out(a):
    assert a.result.error is None, a.result.error
    return a.output_table()


def _col(t, ds=0, sub=0):
    return [t.get(r, t.flat(ds, sub)) for r in range(t.nrows_used())]


def test_transform_y_and_x():
    p, t = _xy()
    o = _out(p.add_analysis(Analysis("transform", t, [0, 1], {"y": "log10", "x": "k_times", "kx": 2})))
    assert o.table_type == "xy" and o.width() == 3
    assert o.get(0, o.flat(0, 1)) == pytest.approx(math.log10(t.get(0, t.flat(0, 1))))
    assert o.get(2, "x") == pytest.approx(2 * t.get(2, "x"))


def test_transform_leaves_impossible_values_blank_and_user_equations():
    p = Project(engine)
    t = p.add_table(table_type="column", example=False)
    for r, v in enumerate([4.0, 0.0, -1.0, 9.0]):
        t.set(r, 0, v)
    o = _out(p.add_analysis(Analysis("transform", t, [0], {"y": "sqrt"})))
    assert _col(o) == [2.0, 0.0, None, 3.0]
    o2 = _out(p.add_analysis(Analysis("transform", t, [0], {"y": "user", "equation": "Y = Y*K + 1", "k": 3})))
    assert _col(o2) == [13.0, 1.0, -2.0, 28.0]
    bad = p.add_analysis(Analysis("transform", t, [0], {"y": "user", "equation": "Y = __import__('os')"}))
    assert "can't be used" in bad.result.error
    z = _out(p.add_analysis(Analysis("transform", t, [0], {"y": "zscore"})))
    v = np.array([4.0, 0.0, -1.0, 9.0])
    assert _col(z) == pytest.approx(list((v - v.mean()) / v.std(ddof=1)))


def test_normalize():
    p = Project(engine)
    t = p.add_table(table_type="column", example=False)
    for r, v in enumerate([10.0, 20.0, 30.0, 50.0]):
        t.set(r, 0, v)
    o = _out(p.add_analysis(Analysis("normalize", t, [0], {})))
    assert _col(o) == pytest.approx([0, 25, 50, 100])
    o2 = _out(p.add_analysis(Analysis("normalize", t, [0], {"zero": "value", "zero_value": 0, "hundred": "first",
                                                             "percent": False})))
    assert o2.name.startswith("Normalize") and _col(o2) == pytest.approx([1, 2, 3, 5])


def test_baseline_subtract_a_data_set_and_percent_change_from_rows():
    p, t = _xy()
    o = _out(p.add_analysis(Analysis("baseline", t, [0, 1], {"source": "set", "baseline": 0, "op": "subtract"})))
    assert o.ncols == 1
    assert o.get(0, o.flat(0, 2)) == pytest.approx(t.get(0, t.flat(1, 2)) - t.get(0, t.flat(0, 2)))
    o2 = _out(p.add_analysis(Analysis("baseline", t, [0], {"source": "rows", "rows": 2, "op": "percent_change"})))
    base = np.concatenate([t.row_values(0, 0), t.row_values(1, 0)]).mean()
    assert o2.get(3, o2.flat(0, 0)) == pytest.approx((t.get(3, t.flat(0, 0)) - base) / base * 100)


def test_prune_and_transpose():
    p, t = _xy()
    o = _out(p.add_analysis(Analysis("prune", t, [0, 1], {"mode": "range", "from": 2, "to": 6})))
    assert [o.get(r, "x") for r in range(o.nrows_used())] == [2.0, 4.0, 6.0]
    o2 = _out(p.add_analysis(Analysis("prune", t, [0, 1], {"mode": "average", "k": 2})))
    assert o2.width() == 1 and o2.get(0, "x") == pytest.approx(1.0)
    assert o2.get(0, 0) == pytest.approx(np.concatenate([t.row_values(0, 0), t.row_values(1, 0)]).mean())
    o3 = _out(p.add_analysis(Analysis("prune", t, [0], {"mode": "every", "n": 3})))
    assert o3.nrows_used() == 2
    tr = _out(p.add_analysis(Analysis("transpose", t, [0, 1], {})))
    assert tr.table_type == "grouped" and tr.ncols == 6 and tr.nrows_used() == 2
    assert tr.get(1, tr.flat(2)) == pytest.approx(t.row_values(2, 1).mean())


def _xy_single(x, y):
    p = Project(engine)
    t = p.add_table(table_type="xy", example=False)
    for r, (a, b) in enumerate(zip(x, y)):
        t.set(r, "x", float(a), emit=False)
        t.set(r, 0, float(b), emit=False)
    t.changed.emit()
    return p, t


def test_smoothing_is_savitzky_golay_without_the_ends():
    from scipy.signal import savgol_filter
    rng = np.random.default_rng(0)
    x = np.arange(20.0)
    y = np.sin(x / 3) + rng.normal(0, 0.2, 20)
    p, t = _xy_single(x, y)
    o = _out(p.add_analysis(Analysis("smooth", t, [0], {"op": "smooth", "k": 3, "order": 2})))
    ref = savgol_filter(y, 7, 2)[3:-3]
    assert [o.get(r, "x") for r in range(o.nrows_used())] == list(x[3:-3])
    assert _col(o) == pytest.approx(list(ref))
    o0 = _out(p.add_analysis(Analysis("smooth", t, [0], {"op": "smooth", "k": 2, "order": 0})))
    assert _col(o0)[0] == pytest.approx(y[:5].mean())


def test_derivatives_and_integral_follow_prisms_procedure():
    x = np.array([0, 1, 3, 4, 7.0])
    y = np.array([0, 2, 3, 7, 1.0])
    p, t = _xy_single(x, y)
    d = _out(p.add_analysis(Analysis("smooth", t, [0], {"op": "derivative"})))
    assert [d.get(r, "x") for r in range(d.nrows_used())] == list((x[1:] + x[:-1]) / 2)
    assert _col(d) == pytest.approx(list(np.diff(y) / np.diff(x)))
    d2 = _out(p.add_analysis(Analysis("smooth", t, [0], {"op": "derivative2"})))
    assert d2.nrows_used() == 3
    i = _out(p.add_analysis(Analysis("smooth", t, [0], {"op": "integral", "start": 5.0})))
    expected = 5.0 + np.concatenate([[0], np.cumsum(np.diff(x) * (y[1:] + y[:-1]) / 2)])
    assert _col(i) == pytest.approx(list(expected))


def test_observed_expected():
    p = Project(engine)
    t = p.add_table(table_type="column", example=False)
    for r, (o, e) in enumerate([(30, 25), (14, 25), (34, 25), (22, 25)]):
        t.set(r, 0, float(o))
        t.set(r, 1, float(e))
    a = p.add_analysis(Analysis("observed_expected", t, [0, 1], {"expected": "column"}))
    ref = stats.chisquare([30, 14, 34, 22], [25, 25, 25, 25])
    assert a.result.p == pytest.approx(ref.pvalue)
    t2 = p.add_table(table_type="column", example=False)
    t2.set(0, 0, 18.0)
    t2.set(1, 0, 7.0)
    b = p.add_analysis(Analysis("observed_expected", t2, [0], {}))
    assert "Exact binomial test" in [r[0] for r in b.result.pages[0].rows]


def test_mcnemar_matches_statsmodels():
    from statsmodels.stats.contingency_tables import mcnemar
    p = Project(engine)
    t = p.add_table(table_type="contingency", example=False)
    for r, row in enumerate([(25, 12), (4, 30)]):
        t.set(r, "row", f"R{r}")
        for c, v in enumerate(row):
            t.set(r, t.flat(c), float(v))
    a = p.add_analysis(Analysis("contingency", t, [0, 1], {"test": "mcnemar"}))
    ref = mcnemar(np.array([[25, 12], [4, 30]]), exact=False, correction=True)
    assert a.result.p == pytest.approx(ref.pvalue)
    exact = mcnemar(np.array([[25, 12], [4, 30]]), exact=True)
    row = [r for r in a.result.pages[0].rows if r[0] == "Exact binomial P value"][0]
    assert float(row[1][0]) == pytest.approx(exact.pvalue, abs=5e-5)


# ---------------------------------------------------------------------------
# Result tables are live, can be analysed further, saved, and deleted with their chain
# ---------------------------------------------------------------------------

def test_chains_are_live_saved_and_deleted_together(tmp_path):
    from asterism.doc import fileformat
    p, t = _xy()
    tr = p.add_analysis(Analysis("smooth", t, [0, 1], {"op": "derivative"}))
    out = tr.output_table()
    lr = p.add_analysis(Analysis("linreg", out, out.used_columns(), {}))
    g = p.new_result_graph(tr)
    p.add_sheets([g], "graph")
    slope = lr.result.fit["fits"][0]["slope"]
    t.set(0, t.flat(0, 0), 99.0)                         # edit the data: the chain follows
    assert tr.output_table() is out and lr.result.fit["fits"][0]["slope"] != slope
    assert p.children(tr) == [g, lr]
    assert set(p.family(t)) >= {t, tr, lr, g}
    path = tmp_path / "chain.asterism"
    fileformat.save(p, str(path))
    q = fileformat.load(str(path), engine)
    tr2 = next(a for a in q.analyses if a.analysis_type == "smooth")
    lr2 = next(a for a in q.analyses if a.analysis_type == "linreg")
    assert lr2.table is tr2.output_table()
    assert lr2.result.fit["fits"][0]["slope"] == pytest.approx(lr.result.fit["fits"][0]["slope"])
    assert next(gr for gr in q.graphs if gr.source is not None).source is tr2
    p.delete(tr)
    assert tr not in p.analyses and lr not in p.analyses and g not in p.graphs
    p.undo.undo()
    assert tr in p.analyses and lr in p.analyses and g in p.graphs


def test_residual_plots_make_a_result_table():
    p, t = _xy()
    a = p.add_analysis(Analysis("linreg", t, [0], {"residual_plot": True}))
    o = _out(a)
    x, y = [], []
    for r in range(t.nrows_used()):
        for v in t.row_values(r, 0):
            x.append(t.x_value(r))
            y.append(v)
    f = a.result.fit["fits"][0]
    res = np.array(y) - (f["intercept"] + f["slope"] * np.array(x))
    got = [o.get(r, o.flat(0, k)) for r in range(o.nrows_used()) for k in range(o.width())]
    assert sorted(v for v in got if v is not None) == pytest.approx(sorted(res))
    n = p.add_analysis(Analysis("nonlin", t, [0, 1], {"model": "line", "residual_plot": True,
                                                      "ci_method": "asymptotic"}))
    assert n.has_output() and n.output_table().ncols == 2
