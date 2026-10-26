"""Nonlinear regression (curve fitting), Prism's functions in our presentation.

Least squares (Levenberg-Marquardt; trust-region when bounds are set) on one or more data
sets at once. Each parameter is fitted, held constant, kept within bounds, or shared by
every data set (a global fit). Options follow Prism's dialog: weighting (1/Y², 1/Y, 1/X²,
1/X, 1/SD²; Y weights use the curve's Y, as Prism does), each replicate or the mean,
profile-likelihood (default, as Prism recommends) or asymptotic confidence intervals,
comparison of two models (extra sum-of-squares F test or AICc) or of data sets (one curve
for all, or a shared parameter), interpolation of unknowns, residuals, runs test, ROUT
outlier detection, confidence and prediction bands for the graph.

Profile-likelihood limits: the parameter value, with the others refitted, at which the sum
of squares reaches SS·(1 + F(α; 1, df)/df) — Prism's extra sum-of-squares description; the
same threshold as R's profile-t intervals (MASS::confint for nls), used to cross-check.
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass, field

import numpy as np
from scipy import optimize
from scipy import stats as sps

from asterism.doc.model import column_letter

from .models import BY_KEY, Model, user_model
from .results import AnalysisResult, ResultPage, fmt, fmt_p, p_summary
from .xy import runs_test, xy_points, xy_rows


# ---------------------------------------------------------------------------
# Fitting engine
# ---------------------------------------------------------------------------

@dataclass
class Data:
    x: np.ndarray
    y: np.ndarray
    sd: np.ndarray | None = None     # for 1/SD² weighting


@dataclass
class Fit:
    model: Model
    values: list[dict]               # per data set {param: value}
    se: list[dict]
    ci: list[dict]                   # per data set {param: (lo, hi)} (None = could not be determined)
    ss: float                        # (weighted) sum of squares, all data sets
    ss_each: list[float]
    df: int
    n: int
    n_each: list[int]
    k: int                           # number of fitted parameters
    cov: np.ndarray
    theta: np.ndarray
    layout: list                     # theta index or ('const', v) per (data set, param)
    r2: list[float]
    syx: float
    converged: bool
    message: str = ""
    unstable: list[set] = field(default_factory=list)
    outliers: list[np.ndarray] = field(default_factory=list)

    def predict(self, j: int, x: np.ndarray) -> np.ndarray:
        return np.asarray(self.model.f(np.asarray(x, float), *[self.values[j][p] for p in self.model.params]), float)

    def band(self, j: int, x: np.ndarray, prediction: bool = False, conf: float = 0.95):
        """Confidence (or prediction) band from the delta method."""
        x = np.asarray(x, float)
        y = self.predict(j, x)
        G = np.zeros((len(x), len(self.theta)))
        for i in range(len(self.theta)):
            h = 1e-6 * max(abs(self.theta[i]), 1e-3)
            tp = self.theta.copy()
            tp[i] += h
            G[:, i] = (self._predict_theta(j, x, tp) - y) / h
        var = np.einsum("ij,jk,ik->i", G, self.cov, G)
        if prediction:
            var = var + self.syx ** 2
        tc = float(sps.t.ppf(1 - (1 - conf) / 2, max(self.df, 1)))
        h = tc * np.sqrt(np.maximum(var, 0))
        return y - h, y + h

    def _predict_theta(self, j, x, theta):
        p = [theta[l] if not isinstance(l, tuple) else l[1] for l in self.layout[j]]
        return np.asarray(self.model.f(x, *p), float)


def _weights(kind: str, d: Data, yfit: np.ndarray) -> np.ndarray:
    """Multipliers applied to residuals (sqrt of the weight)."""
    if kind == "y2":
        return 1 / np.maximum(np.abs(yfit), 1e-12)
    if kind == "y":
        return 1 / np.sqrt(np.maximum(np.abs(yfit), 1e-12))
    if kind == "x2":
        return 1 / np.maximum(np.abs(d.x), 1e-12)
    if kind == "x":
        return 1 / np.sqrt(np.maximum(np.abs(d.x), 1e-12))
    if kind == "sd2" and d.sd is not None:
        return 1 / np.maximum(d.sd, 1e-12)
    return np.ones_like(d.y)


def fit(model: Model, data: list[Data], constraints: dict | None = None,
        initial: dict | None = None, weighting: str = "none", conf: float = 0.95,
        ci_method: str = "profile", robust: float | None = None) -> Fit:
    """constraints: {param: {"mode": fit|constant|shared, "value": v, "lo": a, "hi": b}}.
    initial: {param: value} overrides the automatic starting values (all data sets).
    robust: a scale for a Lorentzian (Cauchy) merit function instead of least squares."""
    constraints = constraints or {}
    initial = initial or {}
    P = model.params
    layout: list[list] = []
    theta0, lo, hi, names = [], [], [], []
    shared_index: dict[str, int] = {}
    for j, d in enumerate(data):
        if len(d.x) == 0:
            raise ValueError("A data set has no points to fit.")
        auto = list(model.initial(d.x, d.y))
        row = []
        for i, p in enumerate(P):
            c = constraints.get(p, {})
            mode = c.get("mode", "fit")
            if mode == "constant":
                row.append(("const", float(c.get("value", 0.0))))
                continue
            if mode == "shared" and p in shared_index:
                row.append(shared_index[p])
                continue
            start = float(initial.get(p, auto[i]))
            b_lo, b_hi = model.bounds.get(p, (-np.inf, np.inf))
            b_lo = c.get("lo", b_lo) if c.get("lo") is not None else b_lo
            b_hi = c.get("hi", b_hi) if c.get("hi") is not None else b_hi
            if b_lo > -np.inf and start <= b_lo:
                start = b_lo + (abs(b_lo) * 0.1 or 0.1) if b_hi == np.inf else (b_lo + b_hi) / 2
            if b_hi < np.inf and start >= b_hi:
                start = b_hi - (abs(b_hi) * 0.1 or 0.1) if b_lo == -np.inf else (b_lo + b_hi) / 2
            idx = len(theta0)
            theta0.append(start)
            lo.append(b_lo)
            hi.append(b_hi)
            names.append((j, p))
            if mode == "shared":
                shared_index[p] = idx
            row.append(idx)
        layout.append(row)
    theta0 = np.array(theta0, float)
    k = len(theta0)
    n_each = [len(d.x) for d in data]
    n = sum(n_each)
    if k == 0:
        raise ValueError("Every parameter is held constant: there is nothing to fit.")
    if n <= k:
        raise ValueError(f"Too few points ({n}) to fit {k} parameters.")

    def params_of(theta, j):
        return [theta[l] if not isinstance(l, tuple) else l[1] for l in layout[j]]

    def resid(theta):
        out = []
        for j, d in enumerate(data):
            with np.errstate(all="ignore"):
                yf = np.asarray(model.f(d.x, *params_of(theta, j)), float) + 0 * d.x
            r = (d.y - yf) * _weights(weighting, d, yf)
            out.append(np.where(np.isfinite(r), r, 1e10))
        return np.concatenate(out)

    bounded = any(np.isfinite(lo)) or any(np.isfinite(hi))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        loss = "cauchy" if robust else "linear"
        if bounded or robust:
            sol = optimize.least_squares(resid, theta0, bounds=(lo, hi), method="trf", loss=loss,
                                         f_scale=float(robust) if robust else 1.0,
                                         x_scale="jac", max_nfev=5000 * (k + 1), xtol=1e-14, ftol=1e-14,
                                         gtol=1e-14)
        else:
            sol = optimize.least_squares(resid, theta0, method="lm", x_scale="jac", xtol=1e-15,
                                         ftol=1e-15, gtol=1e-15, max_nfev=5000 * (k + 1))
            # a second start from the best point polishes slow convergence
            sol = optimize.least_squares(resid, sol.x, method="lm", x_scale="jac", xtol=1e-15,
                                         ftol=1e-15, gtol=1e-15, max_nfev=5000 * (k + 1))
    theta = sol.x
    r = resid(theta)
    ss = float(r @ r)
    df = n - k
    s2 = ss / df
    J = _jacobian(resid, theta)
    try:
        cov = s2 * np.linalg.inv(J.T @ J)
    except np.linalg.LinAlgError:
        cov = np.full((k, k), np.nan)
    values = [dict(zip(P, params_of(theta, j))) for j in range(len(data))]
    se = []
    for j in range(len(data)):
        e = {}
        for p, l in zip(P, layout[j]):
            e[p] = math.sqrt(cov[l, l]) if not isinstance(l, tuple) and cov[l, l] >= 0 else None
        se.append(e)
    ss_each, r2 = [], []
    for j, d in enumerate(data):
        yf = np.asarray(model.f(d.x, *params_of(theta, j)), float)
        w = _weights(weighting, d, yf)
        sse = float((((d.y - yf) * w) ** 2).sum())
        ss_each.append(sse)
        ybar = np.average(d.y, weights=w ** 2)
        sst = float((((d.y - ybar) * w) ** 2).sum())
        r2.append(1 - sse / sst if sst > 0 else math.nan)
    f_ = Fit(model, values, se, [], ss, ss_each, df, n, n_each, k, cov, theta, layout, r2,
             math.sqrt(s2), bool(sol.success), sol.message)
    tc = float(sps.t.ppf(1 - (1 - conf) / 2, df))
    unstable = [set() for _ in data]
    cis: list[dict] = [dict() for _ in data]
    done: dict[int, tuple] = {}
    for j in range(len(data)):
        for p, l in zip(P, layout[j]):
            if isinstance(l, tuple):
                continue
            if l in done:
                cis[j][p] = done[l]
                continue
            if ci_method == "asymptotic":
                s = math.sqrt(cov[l, l]) if cov[l, l] >= 0 else math.nan
                ci = (theta[l] - tc * s, theta[l] + tc * s)
            else:
                ci = _profile(resid, theta, l, ss, df, conf, lo[l], hi[l],
                              math.sqrt(cov[l, l]) if cov[l, l] > 0 else abs(theta[l]) * 0.1 or 0.1)
            if ci is None or not all(np.isfinite(ci)):
                unstable[j].add(p)
            done[l] = ci
            cis[j][p] = ci
    f_.ci = cis
    f_.unstable = unstable
    return f_


def _jacobian(resid, theta):
    r0 = resid(theta)
    J = np.zeros((len(r0), len(theta)))
    for i in range(len(theta)):
        h = 1e-7 * max(abs(theta[i]), 1e-4)
        tp, tm = theta.copy(), theta.copy()
        tp[i] += h
        tm[i] -= h
        J[:, i] = -(resid(tp) - resid(tm)) / (2 * h)
    return J


def _profile(resid, theta, l, ss, df, conf, lo_b, hi_b, se):
    """Profile-likelihood limits for parameter l."""
    fcrit = float(sps.f.ppf(conf, 1, df))
    target = ss * (1 + fcrit / df)
    others = [i for i in range(len(theta)) if i != l]

    def ss_at(v, start):
        if not others:
            t = theta.copy()
            t[l] = v
            r = resid(t)
            return float(r @ r), start

        def rr(o):
            t = np.empty(len(theta))
            t[l] = v
            t[others] = o
            return resid(t)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            sol = optimize.least_squares(rr, start, method="lm", x_scale="jac", xtol=1e-14, ftol=1e-14,
                                         gtol=1e-14, max_nfev=2000 * len(theta))
        return float(sol.fun @ sol.fun), sol.x

    out = []
    for sign in (-1, 1):
        start = theta[others].copy()
        step = se
        prev_v, prev_d = theta[l], ss - target
        found = None
        for _ in range(60):
            v = theta[l] + sign * step
            if (sign < 0 and v <= lo_b) or (sign > 0 and v >= hi_b):
                break
            s_v, start_new = ss_at(v, start)
            d = s_v - target
            if d >= 0:
                # bracketed between prev_v and v
                a, b = sorted((prev_v, v))
                st = [start]

                def g(vv):
                    sv, st[0] = ss_at(vv, st[0])
                    return sv - target
                try:
                    found = optimize.brentq(g, a, b, xtol=1e-12 * max(1.0, abs(theta[l])), rtol=1e-12)
                except ValueError:
                    found = v
                break
            prev_v, prev_d, start = v, d, start_new
            step *= 1.6
        out.append(found)
    if out[0] is None and out[1] is None:
        return None
    return (out[0] if out[0] is not None else -math.inf, out[1] if out[1] is not None else math.inf)


# ---------------------------------------------------------------------------
# Comparisons and outliers
# ---------------------------------------------------------------------------

def aicc(ss: float, n: int, k: int) -> float:
    K = k + 1
    return n * math.log(ss / n) + 2 * K + (2 * K * (K + 1)) / (n - K - 1) if n - K - 1 > 0 else math.inf


def extra_ss(simple: Fit, complex_: Fit) -> tuple[float, int, int, float]:
    dfn = simple.df - complex_.df
    F = ((simple.ss - complex_.ss) / dfn) / (complex_.ss / complex_.df) if dfn > 0 else math.nan
    return F, dfn, complex_.df, float(sps.f.sf(F, dfn, complex_.df)) if dfn > 0 else math.nan


def rout(model: Model, d: Data, q: float = 0.01, constraints=None, initial=None) -> np.ndarray:
    """ROUT (Motulsky & Brown 2006): robust fit (Lorentzian/Cauchy merit function), robust SD
    of the residuals (68.27th percentile × N/(N − K)), then a false-discovery-rate test of
    each residual (Benjamini-Hochberg at Q). Returns a boolean mask of outliers."""
    rf = fit(model, [d], constraints, initial, ci_method="asymptotic")
    n, k = len(d.y), rf.k
    if n - k < 1:
        return np.zeros(n, bool)

    def rsdr_of(f_):
        r_ = d.y - f_.predict(0, d.x)
        return float(np.percentile(np.abs(r_), 68.27)) * n / (n - k), r_
    rsdr, res = rsdr_of(rf)
    start = dict(rf.values[0])
    for _ in range(20):                   # robust fit with the scale re-estimated each time
        if rsdr <= 0:
            return np.zeros(n, bool)
        rf = fit(model, [d], constraints, start, robust=rsdr, ci_method="asymptotic")
        new, res = rsdr_of(rf)
        start = dict(rf.values[0])
        if abs(new - rsdr) <= 1e-9 * max(rsdr, 1e-300):
            break
        rsdr = new
    if rsdr <= 0:
        return np.zeros(n, bool)
    t = np.abs(res) / rsdr
    p = 2 * sps.t.sf(t, n - k)
    # Benjamini-Hochberg: the k-th largest residual (k-th smallest P) is compared with Q·k/N;
    # the largest k that passes marks it and every larger residual as an outlier.
    order = np.argsort(-np.abs(res))
    out = np.zeros(n, bool)
    cut = None
    for k_, i in enumerate(order, start=1):
        if p[i] < q * k_ / n:
            cut = k_
    if cut is not None:
        out[order[:cut]] = True
    return out


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

WEIGHTINGS = {"none": "No weighting", "y2": "1/Y² (relative)", "y": "1/Y (Poisson)",
              "x2": "1/X²", "x": "1/X", "sd2": "1/SD²"}


def model_from(p: dict) -> Model:
    if p.get("model") == "user":
        return user_model(p.get("equation", ""), p.get("initial") or {})
    m = BY_KEY.get(p.get("model", "agonist_4"))
    if m is None:
        raise ValueError(f"Unknown model {p.get('model')!r}.")
    return m


def title(p: dict) -> str:
    try:
        return f"Nonlinear fit: {model_from(p).name}"
    except Exception:
        return "Nonlinear fit"


def _data(t, c, p) -> Data:
    reps = p.get("replicates", "individual")
    x, y = xy_points(t, c, reps)
    sd = None
    if p.get("weighting") == "sd2":
        rows = xy_rows(t, c)
        x = np.array([r["x"] for r in rows])
        y = np.array([r["mean"] for r in rows])
        sd = np.array([r["sd"] if r["sd"] else np.nan for r in rows])
        keep = np.isfinite(sd)
        x, y, sd = x[keep], y[keep], sd[keep]
    lo, hi = p.get("x_min"), p.get("x_max")
    keep = np.ones(len(x), bool)
    if lo is not None:
        keep &= x >= lo
    if hi is not None:
        keep &= x <= hi
    if p.get("drop_nonpositive_x") or (p.get("model", "").endswith("_conc_3") and False):
        keep &= x > 0
    return Data(x[keep], y[keep], sd[keep] if sd is not None else None)


def nonlinear(an) -> AnalysisResult:
    t, cols, p = an.table, list(an.columns), an.params
    if t.table_type != "xy":
        raise ValueError("Nonlinear regression works on an XY table.")
    model = model_from(p)
    conf = p.get("conf", 0.95)
    weighting = p.get("weighting", "none")
    ci_method = p.get("ci_method", "profile")
    cons = p.get("constraints") or {}
    init = p.get("initial") or {}
    datas = [_data(t, c, p) for c in cols]
    keep_cols = [c for c, d in zip(cols, datas) if len(d.x)]
    datas = [d for d in datas if len(d.x)]
    if not datas:
        raise ValueError("No data set has XY values to fit.")
    outlier_masks = []
    if p.get("outliers") in ("identify", "exclude"):
        q = p.get("rout_q", 0.01)
        for d in datas:
            try:
                outlier_masks.append(rout(model, d, q, cons, init))
            except Exception:
                outlier_masks.append(np.zeros(len(d.x), bool))
        if p.get("outliers") == "exclude":
            datas = [Data(d.x[~m], d.y[~m], d.sd[~m] if d.sd is not None else None)
                     for d, m in zip(datas, outlier_masks)]
    shared = any(c.get("mode") == "shared" for c in cons.values())
    if shared:
        fits = [fit(model, datas, cons, init, weighting, conf, ci_method)]
        per = [(fits[0], j) for j in range(len(datas))]
    else:
        fits, per = [], []
        for d in datas:
            try:
                f_ = fit(model, [d], cons, init, weighting, conf, ci_method)
            except ValueError as e:
                f_ = e
            fits.append(f_)
            per.append((f_, 0))
    good = [(c, f_, j) for c, (f_, j) in zip(keep_cols, per) if isinstance(f_, Fit)]
    if not good:
        raise ValueError(str(per[0][0]))
    res = AnalysisResult()
    res.fit = {"kind": "curve", "model": model.key, "curves": {c: (f_, j) for c, f_, j in good},
               "conf": conf, "x_is_log": model.x_is_log}
    heads = [f"{column_letter(c)}: {t.label(c)}" for c in keep_cols]
    lookup = {c: (f_, j) for c, (f_, j) in zip(keep_cols, per)}

    def cell(c, fn):
        f_, j = lookup[c]
        if not isinstance(f_, Fit):
            return str(f_)
        try:
            return fn(f_, j)
        except Exception:
            return ""
    rows = []
    P = model.params

    def const(f_, j, q):
        return isinstance(f_.layout[j][P.index(q)], tuple)

    def shared_p(f_, j, q):
        return cons.get(q, {}).get("mode") == "shared"
    rows.append(("Best-fit values", [], "section"))
    for q in P:
        rows.append((q, [cell(c, lambda f_, j, q=q: fmt(f_.values[j][q]) + (" (constant)" if const(f_, j, q) else "")
                              + (" (shared)" if shared_p(f_, j, q) else "")
                              + (" — unstable" if q in f_.unstable[j] else "")) for c in keep_cols], "row"))
    derived_names = []
    if model.derived:
        f0, j0 = good[0][1], good[0][2]
        derived_names = list(model.derived(f0.values[j0]))
        for dn in derived_names:
            rows.append((dn, [cell(c, lambda f_, j, dn=dn: fmt(model.derived(f_.values[j])[dn])) for c in keep_cols], "row"))
    if ci_method == "asymptotic" or p.get("report_se"):
        rows += [("", [], "blank"), ("Standard errors", [], "section")]
        for q in P:
            rows.append((q, [cell(c, lambda f_, j, q=q: fmt(f_.se[j][q]) if f_.se[j][q] is not None else "")
                             for c in keep_cols], "row"))
    label_ci = f"{conf:.0%} confidence intervals ({'profile likelihood' if ci_method == 'profile' else 'asymptotic'})"
    rows += [("", [], "blank"), (label_ci, [], "section")]

    def ci_txt(ci):
        if ci is None:
            return "Could not be determined"
        lo, hi = ci
        a = fmt(lo) if math.isfinite(lo) else "−∞ (very wide)"
        b = fmt(hi) if math.isfinite(hi) else "+∞ (very wide)"
        return f"{a} to {b}"
    for q in P:
        rows.append((q, [cell(c, lambda f_, j, q=q: "" if const(f_, j, q) else ci_txt(f_.ci[j].get(q)))
                         for c in keep_cols], "row"))
    # derived intervals: transform the interval of the parameter they come from
    for dn in derived_names:
        src = {"EC50": "LogEC50", "IC50": "LogIC50"}.get(dn)
        if src:
            rows.append((dn, [cell(c, lambda f_, j, src=src: ci_txt(tuple(10 ** v if math.isfinite(v) else v
                                                                       for v in f_.ci[j][src])) if f_.ci[j].get(src) else "")
                              for c in keep_cols], "row"))
    rows += [("", [], "blank"), ("Goodness of fit", [], "section"),
             ("Degrees of freedom", [cell(c, lambda f_, j: str(f_.df)) for c in keep_cols], "row"),
             ("R²", [cell(c, lambda f_, j: f"{f_.r2[j]:.4f}") for c in keep_cols], "row"),
             ("Sum of squares", [cell(c, lambda f_, j: fmt(f_.ss_each[j])) for c in keep_cols], "row"),
             ("Sy.x", [cell(c, lambda f_, j: fmt(f_.syx)) for c in keep_cols], "row")]
    if weighting != "none":
        rows.append(("Weighting", [WEIGHTINGS[weighting]] * len(keep_cols), "row"))
    if shared:
        rows.append(("Global fit", ["Shared: " + ", ".join(q for q, c_ in cons.items() if c_.get("mode") == "shared")]
                     * len(keep_cols), "row"))
    rows += [("", [], "blank"), ("Data", [], "section"),
             ("Points analysed", [cell(c, lambda f_, j: str(f_.n_each[j])) for c in keep_cols], "row")]
    if outlier_masks:
        rows.append(("Outliers (ROUT, Q = " + f"{p.get('rout_q', 0.01) * 100:g}%)",
                     [str(int(m.sum())) for m in outlier_masks], "row"))
        if p.get("outliers") == "exclude":
            rows.append(("Outliers", ["Excluded from the fit"] * len(keep_cols), "row"))
    if p.get("runs_test"):
        rows += [("", [], "blank"), ("Runs test", [], "section")]
        rr = {}
        for c, d in zip(keep_cols, datas):
            f_, j = lookup[c]
            if isinstance(f_, Fit):
                o = np.argsort(d.x, kind="stable")
                rr[c] = runs_test((d.y - f_.predict(j, d.x))[o])
        rows.append(("Runs", [str(rr[c][0]) if c in rr else "" for c in keep_cols], "row"))
        rows.append(("P value (too few runs)", [fmt_p(rr[c][1]) if c in rr else "" for c in keep_cols], "row"))
    for c, (f_, j) in lookup.items():
        if isinstance(f_, Fit) and not f_.converged:
            rows.append((f"{column_letter(c)}: note", ["The fit did not converge: " + str(f_.message)], "row"))
    pages = [ResultPage("Results", heads, rows)]
    pages += _compare_pages(model, datas, keep_cols, p, cons, init, weighting, conf, t)
    if p.get("interpolate"):
        pages.append(_interpolate(t, keep_cols, lookup))
    if p.get("residuals"):
        rrows = []
        for c, d in zip(keep_cols, datas):
            f_, j = lookup[c]
            if not isinstance(f_, Fit):
                continue
            yf = f_.predict(j, d.x)
            for xi, yi, fi in zip(d.x, d.y, yf):
                rrows.append((f"{column_letter(c)}", [fmt(xi), fmt(yi), fmt(fi), fmt(yi - fi)], "row"))
        pg = ResultPage("Residuals", ["X", "Y", "Fitted Y", "Residual"], rrows)
        pg.first_column = "Data set"
        pages.append(pg)
    if p.get("residual_plot"):
        from .xy import residual_table
        series = []
        for c, d in zip(keep_cols, datas):
            f_, j = lookup[c]
            if isinstance(f_, Fit):
                series.append((c, t.label(c), d.x, d.y - f_.predict(j, d.x)))
        res.out_table = residual_table(an.name, series)
    res.pages = pages
    res.p = None
    return res


def _compare_pages(model, datas, cols, p, cons, init, weighting, conf, t) -> list[ResultPage]:
    ALPHA = float(p.get("alpha", 0.05))      # significance level (Settings)
    cmp_ = p.get("compare", "none")
    if cmp_ == "models":
        alt = BY_KEY.get(p.get("model_b", ""))
        if alt is None:
            return []
        rows = []
        for c, d in zip(cols, datas):
            try:
                fa = fit(model, [d], cons, init, weighting, conf, "asymptotic")
                fb = fit(alt, [d], None, None, weighting, conf, "asymptotic")
            except ValueError as e:
                rows.append((f"{column_letter(c)}", [str(e), "", "", "", ""], "row"))
                continue
            simple, complex_ = (fa, fb) if fa.k <= fb.k else (fb, fa)
            if p.get("compare_method", "f") == "aicc":
                a1, a2 = aicc(simple.ss, simple.n, simple.k), aicc(complex_.ss, complex_.n, complex_.k)
                delta = a2 - a1
                prob_c = math.exp(-0.5 * delta) / (1 + math.exp(-0.5 * delta))
                pref = complex_.model.name if prob_c > 0.5 else simple.model.name
                rows.append((f"{column_letter(c)}: {t.label(c)}", [pref, f"{delta:.4g}", f"{100 * prob_c:.2f}%",
                                                                   f"{100 * (1 - prob_c):.2f}%", ""], "row"))
            else:
                F, dfn, dfd, pv = extra_ss(simple, complex_)
                pref = complex_.model.name if pv < ALPHA else simple.model.name
                rows.append((f"{column_letter(c)}: {t.label(c)}", [pref, f"{F:.4g} ({dfn}, {dfd})", fmt_p(pv), "", ""], "row"))
        heads = (["Preferred model", "Difference in AICc", "Probability the more complex is correct",
                  "Probability the simpler is correct", ""] if p.get("compare_method") == "aicc"
                 else ["Preferred model", "F (DFn, DFd)", "P value", "", ""])
        pg = ResultPage("Compare models", heads, [(f"{model.name}  vs.  {alt.name}", [], "section")] + rows)
        pg.first_column = "Data set"
        return [pg]
    if cmp_ in ("one_curve", "param") and len(datas) >= 2:
        sep = fit(model, datas, {q: v for q, v in cons.items() if v.get("mode") != "shared"}, init,
                  weighting, conf, "asymptotic")
        if cmp_ == "one_curve":
            shared_cons = {q: {**cons.get(q, {}), "mode": cons.get(q, {}).get("mode") if
                               cons.get(q, {}).get("mode") == "constant" else "shared"} for q in model.params}
            question = "Is one curve adequate for all data sets?"
        else:
            q = p.get("compare_param", model.params[0])
            shared_cons = {**{k_: v for k_, v in cons.items() if v.get("mode") != "shared"}, q: {"mode": "shared"}}
            question = f"Does {q} differ between data sets?"
        one = fit(model, datas, shared_cons, init, weighting, conf, "asymptotic")
        rows = [(question, [], "section")]
        if p.get("compare_method", "f") == "aicc":
            a1, a2 = aicc(one.ss, one.n, one.k), aicc(sep.ss, sep.n, sep.k)
            delta = a2 - a1
            prob = math.exp(-0.5 * delta) / (1 + math.exp(-0.5 * delta))
            rows += [("Difference in AICc (separate − shared)", [f"{delta:.4g}"], "row"),
                     ("Probability that separate fits are correct", [f"{100 * prob:.2f}%"], "row"),
                     ("Preferred", ["Different for each data set" if prob > 0.5 else "The same for all data sets"], "row")]
        else:
            F, dfn, dfd, pv = extra_ss(one, sep)
            rows += [("F (DFn, DFd)", [f"{F:.4g} ({dfn}, {dfd})"], "row"), ("P value", [fmt_p(pv)], "row"),
                     ("Conclusion", ["Different for each data set" if pv < ALPHA else
                                     "No significant difference: one shared value fits"], "row")]
        return [ResultPage("Compare data sets", ["Comparison"], rows)]
    return []


def _interpolate(t, cols, lookup) -> ResultPage:
    rows = []
    for c in cols:
        f_, j = lookup[c]
        if not isinstance(f_, Fit):
            continue
        xs = [t.x_value(r) for r in range(t.nrows_used())]
        known = np.array([x for x in xs if x is not None], float)
        lo, hi = (float(known.min()), float(known.max())) if len(known) else (0.0, 1.0)
        for r in range(t.nrows_used()):
            xv = t.x_value(r)
            yv = t.row_values(r, c) if not t.is_summary() else np.array([])
            if t.get(r, "x") is None and len(yv):
                y0 = float(yv.mean())
                grid = np.linspace(lo, hi, 400)
                g = f_.predict(j, grid) - y0
                hit = np.nonzero(np.sign(g[:-1]) * np.sign(g[1:]) <= 0)[0]
                if len(hit):
                    a, b = grid[hit[0]], grid[hit[0] + 1]
                    try:
                        x_ = optimize.brentq(lambda v: float(f_.predict(j, np.array([v]))[0] - y0), a, b)
                        txt = fmt(x_)
                    except ValueError:
                        txt = "Not found"
                else:
                    txt = "Outside the curve's range"
                rows.append((f"{column_letter(c)}, row {r + 1}", ["Y → X", fmt(y0), txt], "row"))
            elif xv is not None and not len(yv) and not _any_y(t, r):
                rows.append((f"{column_letter(c)}, row {r + 1}", ["X → Y", fmt(xv), fmt(float(f_.predict(j, np.array([xv]))[0]))], "row"))
    if not rows:
        rows = [("No unknowns", ["Rows with a Y value but no X (or an X but no Y) are interpolated."], "row")]
    pg = ResultPage("Interpolated", ["Direction", "From", "Interpolated"], rows)
    pg.first_column = "Row"
    return pg


def _any_y(t, r: int) -> bool:
    """Whether any data set has a Y value in this row (then an empty cell isn't an unknown X)."""
    if t.is_summary():
        return any(t.summary(r, c) for c in t.used_columns())
    return any(len(t.row_values(r, c)) for c in t.used_columns())
