"""Contingency tables (Prism's functions, our wording): chi-square (with or without Yates'
correction for 2 × 2), Fisher's exact test (2 × 2 and larger tables), chi-square test for
trend (Cochran-Armitage), and for 2 × 2 tables the effect sizes with Prism 11's
recommended interval methods:

  proportions, sensitivity, specificity …   hybrid Wilson/Brown ("modified Wilson")
  relative risk                              Koopman asymptotic score
  difference between proportions             Newcombe/Wilson with continuity correction
  odds ratio                                 Baptista-Pike
  association                                phi (2 × 2) / Cramér's V

Layout: rows are groups (exposed / treated first), columns are outcomes (the outcome of
interest first). Diagnostic tests: rows are the test result (positive first), columns the
true condition (present first).
"""

from __future__ import annotations

import math
from functools import lru_cache

import numpy as np
from scipy import optimize
from scipy import stats as sps

from .results import AnalysisResult, ResultPage, fmt, fmt_p, p_summary


def counts(t, cols: list[int]) -> tuple[np.ndarray, list[str], list[str]]:
    rows = []
    for r in range(t.nrows_used()):
        vals = [t.get(r, t.flat(c)) for c in cols]
        vals = [None if (r, t.flat(c)) in t.excluded else v for v, c in zip(vals, cols)]
        if any(isinstance(v, (int, float)) for v in vals):
            rows.append((r, [float(v) if isinstance(v, (int, float)) else 0.0 for v in vals]))
    if len(rows) < 2 or len(cols) < 2:
        raise ValueError("A contingency table needs at least two rows and two columns of counts.")
    m = np.array([v for _, v in rows])
    if np.any(m < 0) or np.any(np.abs(m - np.round(m)) > 1e-9):
        raise ValueError("Contingency tables hold counts: whole numbers of subjects, not means or percentages.")
    row_names = [t.row_label(r) for r, _ in rows]
    col_names = [t.label(c) for c in cols]
    return np.round(m).astype(int), row_names, col_names


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def chi_square(m: np.ndarray, yates: bool = False) -> dict:
    n = m.sum()
    e = np.outer(m.sum(1), m.sum(0)) / n
    if np.any(e == 0):
        raise ValueError("A row or column total is zero.")
    if yates and m.shape == (2, 2):
        d = np.maximum(np.abs(m - e) - 0.5, 0)
        chi = float((d ** 2 / e).sum())
    else:
        chi = float(((m - e) ** 2 / e).sum())
    df = (m.shape[0] - 1) * (m.shape[1] - 1)
    return {"chi2": chi, "df": df, "p": float(sps.chi2.sf(chi, df)), "expected": e,
            "small_expected": int((e < 5).sum())}


def fisher_2x2(m: np.ndarray, alternative: str = "two-sided") -> float:
    return float(sps.fisher_exact(m, alternative=alternative)[1])


def fisher_rxc(m: np.ndarray, max_tables: int = 5_000_000) -> float | None:
    """Freeman-Halton exact test: the probability of every table with the same margins that
    is no more likely than the one observed. None when there are too many tables."""
    rows, cols = m.sum(1), m.sum(0)
    n = int(m.sum())
    logf = np.array([math.lgamma(i + 1) for i in range(n + 1)])
    const = logf[rows].sum() + logf[cols].sum() - logf[n]
    obs = const - logf[m.ravel()].sum()
    tol = 1e-7
    total, seen = 0.0, 0
    R, C = m.shape

    # recursive fill, column by column, cell by cell (last row/col determined)
    def rec(c, colrem, rowrem, acc):
        nonlocal total, seen
        if c == C - 1:
            lp = acc - logf[rowrem].sum()
            seen += 1
            if seen > max_tables:
                raise OverflowError
            if lp <= obs + tol * abs(obs) + 1e-12:
                total += math.exp(lp)
            return
        need = cols[c]

        def fill(r, left, rowrem, acc):
            if r == R - 1:
                if left <= rowrem[r]:
                    rr = rowrem.copy()
                    rr[r] -= left
                    rec(c + 1, None, rr, acc - logf[left])
                return
            hi = min(left, rowrem[r])
            # the remaining rows must be able to take what is left
            lo = max(0, left - int(rowrem[r + 1:].sum()))
            for v in range(lo, hi + 1):
                rr = rowrem.copy()
                rr[r] -= v
                fill(r + 1, left - v, rr, acc - logf[v])
        fill(0, need, rowrem, acc)
    try:
        rec(0, None, rows.astype(int).copy(), const)
    except OverflowError:
        return None
    return min(1.0, total)


def trend(m: np.ndarray, scores=None) -> dict | None:
    """Chi-square test for trend (Cochran-Armitage) for 2 columns × k ordered rows (or the
    transpose), equally spaced scores unless given. Same as R's prop.trend.test."""
    if m.shape[1] == 2 and m.shape[0] >= 3:
        x, n = m[:, 0].astype(float), m.sum(1).astype(float)
    elif m.shape[0] == 2 and m.shape[1] >= 3:
        x, n = m[0, :].astype(float), m.sum(0).astype(float)
    else:
        return None
    s = np.arange(1, len(x) + 1, dtype=float) if scores is None else np.asarray(scores, float)
    N, X = n.sum(), x.sum()
    p = X / N
    num = (np.sum(x * s) - X * np.sum(n * s) / N) ** 2
    den = p * (1 - p) * (np.sum(n * s * s) - np.sum(n * s) ** 2 / N)
    chi = float(num / den) if den > 0 else 0.0
    return {"chi2": chi, "df": 1, "p": float(sps.chi2.sf(chi, 1))}


# ---------------------------------------------------------------------------
# Intervals
# ---------------------------------------------------------------------------

def wilson(x: int, n: int, conf: float = 0.95) -> tuple[float, float]:
    if n == 0:
        return (math.nan, math.nan)
    z = float(sps.norm.ppf(1 - (1 - conf) / 2))
    p = x / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    d = 1 + z * z / n
    return ((c - h) / d, (c + h) / d)


def wilson_brown(x: int, n: int, conf: float = 0.95) -> tuple[float, float]:
    """Prism's hybrid Wilson/Brown: Wilson, with the Poisson-based limit of Brown, Cai &
    DasGupta (2001) for the lower limit when x = 1 or 2 (or 3 with n > 50), and likewise
    for the upper limit near n."""
    lo, hi = wilson(x, n, conf)
    a = 1 - conf
    if x == 0:
        lo = 0.0
    elif x in (1, 2) or (x == 3 and n > 50):
        lo = 0.5 * float(sps.chi2.ppf(a, 2 * x)) / n
    if x == n:
        hi = 1.0
    elif n - x in (1, 2) or (n - x == 3 and n > 50):
        hi = 1 - 0.5 * float(sps.chi2.ppf(a, 2 * (n - x))) / n
    return (max(0.0, lo), min(1.0, hi))


def clopper_pearson(x: int, n: int, conf: float = 0.95) -> tuple[float, float]:
    a = 1 - conf
    lo = 0.0 if x == 0 else float(sps.beta.ppf(a / 2, x, n - x + 1))
    hi = 1.0 if x == n else float(sps.beta.ppf(1 - a / 2, x + 1, n - x))
    return (lo, hi)


def newcombe_diff(x1, n1, x2, n2, conf=0.95, cc: bool = True) -> tuple[float, float]:
    """Newcombe's hybrid score interval (method 10, or 11 with continuity correction) for
    p1 − p2."""
    p1, p2 = x1 / n1, x2 / n2
    z = float(sps.norm.ppf(1 - (1 - conf) / 2))

    def score(x, n):
        if not cc:
            return wilson(x, n, conf)
        p = x / n
        q = 1 - p
        lo = 0.0 if x == 0 else (2 * n * p + z * z - 1 - z * math.sqrt(z * z - 2 - 1 / n + 4 * p * (n * q + 1))) / (2 * (n + z * z))
        hi = 1.0 if x == n else (2 * n * p + z * z + 1 + z * math.sqrt(z * z + 2 - 1 / n + 4 * p * (n * q - 1))) / (2 * (n + z * z))
        return (max(0.0, lo), min(1.0, hi))
    l1, u1 = score(x1, n1)
    l2, u2 = score(x2, n2)
    d = p1 - p2
    lo = d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2)
    hi = d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)
    return (lo, hi)


def koopman_rr(x1, n1, x2, n2, conf=0.95) -> tuple[float, float]:
    """Koopman's asymptotic score interval for the risk ratio (p1/p2)."""
    z2 = float(sps.chi2.ppf(conf, 1))
    if x1 == 0 and x2 == 0:
        return (0.0, math.inf)

    def stat(theta):
        # constrained MLE of p2 under p1 = theta·p2 (Koopman 1984), solved as a quadratic
        a = theta * (n1 + n2)
        b = -(theta * (n1 + x2) + x1 + n2)
        c = x1 + x2
        disc = max(b * b - 4 * a * c, 0.0)
        p2 = (-b - math.sqrt(disc)) / (2 * a)
        p1 = theta * p2
        if not (0 < p1 < 1 and 0 < p2 < 1):
            return math.inf
        return ((x1 - n1 * p1) ** 2 / (n1 * p1 * (1 - p1))) * (1 + n1 * (theta - p1) / (n2 * (1 - p1)))

    est = (x1 / n1) / (x2 / n2) if x2 else math.inf

    def g(log_t):
        return stat(math.exp(log_t)) - z2
    lo = 0.0
    hi = math.inf
    if x1 > 0:
        top = math.log(est) if math.isfinite(est) else 10.0
        a_ = top - 1
        while g(a_) < 0 and a_ > -50:
            a_ -= 1
        if a_ > -50:
            lo = math.exp(optimize.brentq(g, a_, top - 1e-12 if math.isfinite(est) else top, xtol=1e-14))
    if x2 > 0:
        bot = math.log(est) if est > 0 else -10.0
        b_ = bot + 1
        while g(b_) < 0 and b_ < 50:
            b_ += 1
        if b_ < 50:
            hi = math.exp(optimize.brentq(g, bot + 1e-12 if est > 0 else bot, b_, xtol=1e-14))
    return (lo, hi)


@lru_cache(maxsize=4096)
def _nchg_logpmf_support(m1: int, n1: int, n2: int) -> tuple:
    lo, hi = max(0, m1 - n2), min(n1, m1)
    xs = np.arange(lo, hi + 1)
    lb = np.array([math.lgamma(n1 + 1) - math.lgamma(k + 1) - math.lgamma(n1 - k + 1)
                   + math.lgamma(n2 + 1) - math.lgamma(m1 - k + 1) - math.lgamma(n2 - m1 + k + 1) for k in xs])
    return xs, lb


def _nchg_pmf(psi, m1, n1, n2):
    xs, lb = _nchg_logpmf_support(m1, n1, n2)
    lw = lb + xs * math.log(psi)
    lw -= lw.max()
    w = np.exp(lw)
    return xs, w / w.sum()


def baptista_pike_or(a, b, c, d, conf=0.95) -> tuple[float, float]:
    """Baptista & Pike (1977) exact interval for the odds ratio: the odds ratios whose
    conditional (noncentral hypergeometric) test, with the acceptance region formed from
    the most probable tables, does not reject the observed table."""
    alpha = 1 - conf
    n1, n2, m1 = a + b, c + d, a + c

    def pval(psi):
        xs, pr = _nchg_pmf(psi, m1, n1, n2)
        po = pr[xs == a][0]
        return float(pr[pr <= po * (1 + 1e-7)].sum())
    est = (a * d) / (b * c) if b * c else math.inf
    lo, hi = 0.0, math.inf

    def scan(direction, start):
        """Walk out from the estimate (log scale) to the first odds ratio rejected, then
        bisect for the boundary."""
        x_in = start
        step = 0.25
        for _ in range(400):
            x_out = x_in + direction * step
            if pval(math.exp(x_out)) <= alpha:
                for _ in range(80):
                    mid = (x_in + x_out) / 2
                    if pval(math.exp(mid)) > alpha:
                        x_in = mid
                    else:
                        x_out = mid
                return math.exp((x_in + x_out) / 2)
            x_in = x_out
            step *= 1.2
            if abs(x_in) > 60:
                return None
        return None
    start = math.log(est) if 0 < est < math.inf else (30.0 if est == math.inf else -30.0)
    if a > max(0, m1 - n2):
        v = scan(-1, start)
        lo = v if v is not None else 0.0
    if a < min(n1, m1):
        v = scan(+1, start)
        hi = v if v is not None else math.inf
    return (lo, hi)


def woolf_or(a, b, c, d, conf=0.95):
    if 0 in (a, b, c, d):
        a, b, c, d = a + 0.5, b + 0.5, c + 0.5, d + 0.5
    z = float(sps.norm.ppf(1 - (1 - conf) / 2))
    l = math.log(a * d / (b * c))
    se = math.sqrt(1 / a + 1 / b + 1 / c + 1 / d)
    return (math.exp(l - z * se), math.exp(l + z * se))


def katz_rr(x1, n1, x2, n2, conf=0.95):
    z = float(sps.norm.ppf(1 - (1 - conf) / 2))
    if x1 == 0 or x2 == 0:
        return (math.nan, math.nan)
    l = math.log((x1 / n1) / (x2 / n2))
    se = math.sqrt(1 / x1 - 1 / n1 + 1 / x2 - 1 / n2)
    return (math.exp(l - z * se), math.exp(l + z * se))


def cramers_v(m: np.ndarray, chi: float, conf=0.95) -> dict:
    n = m.sum()
    k = min(m.shape) - 1
    v = math.sqrt(chi / (n * k)) if n * k else math.nan
    df = (m.shape[0] - 1) * (m.shape[1] - 1)

    def lam_for(q):           # noncentrality with P(χ² ≤ observed) = q
        f = lambda lam: sps.ncx2.cdf(chi, df, lam) - q if lam > 0 else sps.chi2.cdf(chi, df) - q
        if f(1e-12) < 0:
            return 0.0
        hi = max(chi * 4 + 50, 10.0)
        while f(hi) > 0:
            hi *= 2
        return optimize.brentq(f, 1e-12, hi, xtol=1e-12)
    a = 1 - conf
    lo_l, hi_l = lam_for(1 - a / 2), lam_for(a / 2)
    conv = lambda lam: math.sqrt(min((lam + df) / (n * k), 1.0)) if lam > 0 else 0.0
    return {"v": v, "ci": (conv(lo_l), conv(hi_l))}


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def contingency(an) -> AnalysisResult:
    t, cols, p = an.table, list(an.columns), an.params
    if t.table_type not in ("contingency", "grouped"):
        raise ValueError("This analysis works on a Contingency table of counts.")
    m, rn, cn = counts(t, cols)
    conf = p.get("conf", 0.95)
    test = p.get("test", "fisher" if m.shape == (2, 2) else "chi2")
    tails = p.get("tails", 2)
    is22 = m.shape == (2, 2)
    rows: list[tuple[str, list[str], str]] = [
        ("Table", [f"{m.shape[0]} rows × {m.shape[1]} columns, {int(m.sum())} subjects"], "row"), ("", [], "blank")]
    res = AnalysisResult()
    chi = chi_square(m, yates=p.get("yates", False))
    if test == "fisher":
        if is22:
            pv = fisher_2x2(m, "two-sided" if tails == 2 else ("greater" if (m[0, 0] * m[1, 1] >= m[0, 1] * m[1, 0]) else "less"))
            name = "Fisher's exact test"
        else:
            pv = fisher_rxc(m)
            name = "Fisher's exact test (Freeman-Halton extension)"
            if pv is None:
                pv, name = chi["p"], "Chi-square (the exact test has too many tables to enumerate)"
        rows += [(name, [], "section"), ("P value", [fmt_p(pv)], "row"),
                 ("P value summary", [p_summary(pv)], "row"),
                 ("One- or two-sided", ["Two-sided" if tails == 2 else "One-sided"], "row"),
                 ("Significant at α = 0.05", ["Yes" if pv < 0.05 else "No"], "row")]
    else:
        pv = chi["p"]
        rows += [("Chi-square test" + (" with Yates' correction" if p.get("yates") and is22 else ""), [], "section"),
                 ("Chi-square, df", [f"{chi['chi2']:.4g}, {chi['df']}"], "row"),
                 ("P value", [fmt_p(pv)], "row"), ("P value summary", [p_summary(pv)], "row"),
                 ("Significant at α = 0.05", ["Yes" if pv < 0.05 else "No"], "row")]
        if chi["small_expected"]:
            rows.append(("Note", [f"{chi['small_expected']} expected count(s) below 5: "
                                  "Fisher's exact test is more accurate here"], "row"))
    res.p = pv
    tr = trend(m)
    if tr is not None and p.get("trend", True):
        rows += [("", [], "blank"), ("Chi-square test for trend", [], "section"),
                 ("Chi-square, df", [f"{tr['chi2']:.4g}, 1"], "row"), ("P value", [fmt_p(tr["p"])], "row"),
                 ("P value summary", [p_summary(tr["p"])], "row"),
                 ("Note", ["Meaningful only when the rows (or columns) are in order"], "row")]
    if m.shape != (2, 2) or p.get("association", True):
        cv = cramers_v(m, chi_square(m)["chi2"], conf)
        rows += [("", [], "blank"), ("Strength of association", [], "section"),
                 ("Phi (φ)" if is22 else "Cramér's V", [f"{cv['v']:.4f}"], "row"),
                 (f"{conf:.0%} confidence interval", [f"{cv['ci'][0]:.4f} to {cv['ci'][1]:.4f}"], "row")]
    pages = [ResultPage("Results", ["Contingency"], rows)]
    if is22:
        pages.append(_effects_page(m, rn, cn, p, conf))
    exp = chi["expected"]
    erows = [(rn[i], [fmt(exp[i, j]) for j in range(m.shape[1])], "row") for i in range(m.shape[0])]
    pg = ResultPage("Expected counts", cn, erows)
    pg.first_column = "Row"
    pages.append(pg)
    res.pages = pages
    return res


def _ci(lohi, f=fmt):
    lo, hi = lohi
    a = f(lo) if math.isfinite(lo) else ("0" if lo == 0 else "−∞")
    b = f(hi) if math.isfinite(hi) else "∞"
    return f"{a} to {b}"


def _effects_page(m, rn, cn, p, conf) -> ResultPage:
    a, b, c, d = (int(v) for v in m.ravel())
    n1, n2 = a + b, c + d
    kind = p.get("effect", "rr")             # rr | or | diagnostic
    rows: list[tuple[str, list[str], str]] = []
    pc = p.get("prop_ci", "wilson_brown")
    prop = wilson_brown if pc == "wilson_brown" else clopper_pearson
    if kind == "diagnostic":
        sens, spec = a / (a + c) if a + c else math.nan, d / (b + d) if b + d else math.nan
        ppv, npv = a / (a + b) if a + b else math.nan, d / (c + d) if c + d else math.nan
        rows += [("Diagnostic test", [], "section"),
                 ("Sensitivity", [f"{sens:.4f}", _ci(prop(a, a + c, conf), lambda v: f"{v:.4f}")], "row"),
                 ("Specificity", [f"{spec:.4f}", _ci(prop(d, b + d, conf), lambda v: f"{v:.4f}")], "row"),
                 ("Positive predictive value", [f"{ppv:.4f}", _ci(prop(a, a + b, conf), lambda v: f"{v:.4f}")], "row"),
                 ("Negative predictive value", [f"{npv:.4f}", _ci(prop(d, c + d, conf), lambda v: f"{v:.4f}")], "row"),
                 ("Likelihood ratio (positive test)", [fmt(sens / (1 - spec)) if spec < 1 else "∞", ""], "row"),
                 ("Likelihood ratio (negative test)", [fmt((1 - sens) / spec) if spec > 0 else "∞", ""], "row")]
    else:
        p1, p2 = a / n1, c / n2
        rows += [("Proportions with the outcome", [], "section"),
                 (f"{rn[0]}", [f"{p1:.4f}", _ci(prop(a, n1, conf), lambda v: f"{v:.4f}")], "row"),
                 (f"{rn[1]}", [f"{p2:.4f}", _ci(prop(c, n2, conf), lambda v: f"{v:.4f}")], "row"),
                 ("", [], "blank")]
        if kind == "rr":
            rr = p1 / p2 if p2 else math.inf
            rr_ci = koopman_rr(a, n1, c, n2, conf) if p.get("rr_ci", "koopman") == "koopman" else katz_rr(a, n1, c, n2, conf)
            cc = p.get("diff_ci", "newcombe_cc")
            diff_ci = newcombe_diff(a, n1, c, n2, conf, cc=(cc == "newcombe_cc"))
            diff = p1 - p2
            rows += [("Relative risk", [fmt(rr), _ci(rr_ci)], "row"),
                     ("Difference between proportions", [f"{diff:.4f}", _ci(diff_ci, lambda v: f"{v:.4f}")], "row")]
            if diff:
                nnt = 1 / abs(diff)
                lo, hi = diff_ci
                txt = "" if lo < 0 < hi else _ci(tuple(sorted((1 / abs(lo), 1 / abs(hi)))))
                rows.append(("Number needed to treat (or harm)", [fmt(nnt), txt or "Includes ∞ (no significant difference)"], "row"))
        else:
            orv = (a * d) / (b * c) if b * c else math.inf
            or_ci = baptista_pike_or(a, b, c, d, conf) if p.get("or_ci", "baptista_pike") == "baptista_pike" \
                else woolf_or(a, b, c, d, conf)
            rows.append(("Odds ratio", [fmt(orv), _ci(or_ci)], "row"))
    pg = ResultPage("Effect size", ["Value", f"{conf:.0%} confidence interval"], rows)
    pg.first_column = "Measure"
    return pg
