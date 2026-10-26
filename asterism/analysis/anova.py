"""One-way ANOVA family and multiple comparisons (Prism's options, our presentation).

Designs: ordinary (equal SDs; or Welch and Brown-Forsythe ANOVA when SDs may differ),
repeated measures (matched rows; optional Geisser-Greenhouse correction), Kruskal-Wallis
and Friedman. Multiple comparisons: all pairs or each group against a control.

  ordinary   : Tukey (Tukey-Kramer), Dunnett, Šídák, Holm-Šídák, Bonferroni, Fisher's LSD
  Welch/BF   : Games-Howell, Dunnett T3, Tamhane T2, Fisher's LSD (Welch t)
  repeated   : as ordinary, using the residual mean square of the RM model
  rank tests : Dunn's test (Bonferroni-adjusted), uncorrected Dunn

Multiplicity-adjusted P values are reported for every method, as Prism does.
"""

from __future__ import annotations

import itertools
import math

import numpy as np
from scipy import stats as sps

from asterism.doc.model import column_letter

from .results import AnalysisResult, ResultPage, fmt, fmt_p, p_summary

METHOD_NAMES = {
    "tukey": "Tukey's multiple comparisons test", "dunnett": "Dunnett's multiple comparisons test",
    "sidak": "Šídák's multiple comparisons test", "holm_sidak": "Holm-Šídák's multiple comparisons test",
    "bonferroni": "Bonferroni's multiple comparisons test", "fisher": "Fisher's LSD (no correction)",
    "games_howell": "Games-Howell's multiple comparisons test",
    "t3": "Dunnett's T3 multiple comparisons test", "t2": "Tamhane's T2 multiple comparisons test",
    "dunn": "Dunn's multiple comparisons test", "dunn_none": "Uncorrected Dunn's test",
}
DEFAULT_METHOD = {("ordinary", "all"): "tukey", ("ordinary", "control"): "dunnett",
                  ("welch", "all"): "t3", ("welch", "control"): "t3",
                  ("rm", "all"): "tukey", ("rm", "control"): "dunnett",
                  ("kw", "all"): "dunn", ("kw", "control"): "dunn",
                  ("friedman", "all"): "dunn", ("friedman", "control"): "dunn"}
METHODS_FOR = {
    "ordinary": ["tukey", "dunnett", "sidak", "holm_sidak", "bonferroni", "fisher"],
    "rm": ["tukey", "dunnett", "sidak", "holm_sidak", "bonferroni", "fisher"],
    "welch": ["games_howell", "t3", "t2", "fisher"],
    "kw": ["dunn", "dunn_none"], "friedman": ["dunn", "dunn_none"],
}


def model_of(params: dict) -> str:
    design = params.get("design", "ordinary")
    nonpar = params.get("distribution", "normal") == "nonparametric"
    if design == "rm":
        return "friedman" if nonpar else "rm"
    if nonpar:
        return "kw"
    return "welch" if params.get("welch", False) else "ordinary"


def title(params: dict) -> str:
    return {"ordinary": "One-way ANOVA", "welch": "Welch and Brown-Forsythe ANOVA",
            "rm": "Repeated-measures one-way ANOVA", "kw": "Kruskal-Wallis test",
            "friedman": "Friedman test"}[model_of(params)]


# ---------------------------------------------------------------------------
# Omnibus tests
# ---------------------------------------------------------------------------

def ordinary(groups: list[np.ndarray]) -> dict:
    n = np.array([len(g) for g in groups], float)
    means = np.array([g.mean() for g in groups])
    allv = np.concatenate(groups)
    N, k = len(allv), len(groups)
    grand = allv.mean()
    ssb = float(np.sum(n * (means - grand) ** 2))
    ssw = float(sum(((g - g.mean()) ** 2).sum() for g in groups))
    dfb, dfw = k - 1, N - k
    msb, msw = ssb / dfb, ssw / dfw
    F = msb / msw if msw > 0 else math.inf
    p = float(sps.f.sf(F, dfb, dfw))
    return {"ssb": ssb, "ssw": ssw, "sst": ssb + ssw, "dfb": dfb, "dfw": dfw, "msb": msb,
            "msw": msw, "F": F, "p": p, "r2": ssb / (ssb + ssw) if ssb + ssw else 0.0}


def welch_anova(groups: list[np.ndarray]) -> dict:
    k = len(groups)
    n = np.array([len(g) for g in groups], float)
    m = np.array([g.mean() for g in groups])
    v = np.array([g.var(ddof=1) for g in groups])
    w = n / v
    mw = np.sum(w * m) / np.sum(w)
    a = np.sum(w * (m - mw) ** 2) / (k - 1)
    tmp = np.sum((1 - w / np.sum(w)) ** 2 / (n - 1))
    b = 1 + 2 * (k - 2) / (k ** 2 - 1) * tmp
    F = a / b
    df2 = (k ** 2 - 1) / (3 * tmp)
    welch = {"F": float(F), "df1": k - 1, "df2": float(df2), "p": float(sps.f.sf(F, k - 1, df2))}
    # Brown-Forsythe ANOVA (F*), Satterthwaite df
    N = n.sum()
    grand = np.concatenate(groups).mean()
    num = np.sum(n * (m - grand) ** 2)
    c = (1 - n / N) * v
    Fs = num / np.sum(c)
    df2b = np.sum(c) ** 2 / np.sum(c ** 2 / (n - 1))
    bf = {"F": float(Fs), "df1": k - 1, "df2": float(df2b), "p": float(sps.f.sf(Fs, k - 1, df2b))}
    return {"welch": welch, "bf": bf}


def rm_anova(Y: np.ndarray, gg: bool) -> dict:
    """Y: subjects × treatments (complete rows only)."""
    n, k = Y.shape
    grand = Y.mean()
    ss_treat = n * np.sum((Y.mean(axis=0) - grand) ** 2)
    ss_subj = k * np.sum((Y.mean(axis=1) - grand) ** 2)
    ss_total = np.sum((Y - grand) ** 2)
    ss_res = ss_total - ss_treat - ss_subj
    df_t, df_s, df_r = k - 1, n - 1, (n - 1) * (k - 1)
    ms_t, ms_s, ms_r = ss_treat / df_t, ss_subj / df_s, ss_res / df_r
    F = ms_t / ms_r if ms_r > 0 else math.inf
    # Geisser-Greenhouse epsilon from the double-centred covariance matrix
    S = np.cov(Y, rowvar=False, ddof=1)
    C = np.eye(k) - np.ones((k, k)) / k
    Sc = C @ S @ C
    eps = float(np.trace(Sc) ** 2 / ((k - 1) * np.sum(Sc * Sc))) if np.sum(Sc * Sc) > 0 else 1.0
    eps = min(max(eps, 1.0 / (k - 1)), 1.0)
    e = eps if gg else 1.0
    p = float(sps.f.sf(F, df_t * e, df_r * e))
    F_subj = ms_s / ms_r if ms_r > 0 else math.inf
    return {"ss_treat": ss_treat, "ss_subj": ss_subj, "ss_res": ss_res, "ss_total": ss_total,
            "df_t": df_t, "df_s": df_s, "df_r": df_r, "ms_t": ms_t, "ms_s": ms_s, "ms_r": ms_r,
            "F": F, "p": p, "eps": eps, "gg": gg, "F_subj": F_subj,
            "p_subj": float(sps.f.sf(F_subj, df_s, df_r)),
            "r2": ss_treat / (ss_treat + ss_res) if ss_treat + ss_res else 0.0}


# ---------------------------------------------------------------------------
# Multiple comparisons
# ---------------------------------------------------------------------------

def _pairs(k: int, family: str, control: int) -> list[tuple[int, int]]:
    if family == "control":
        return [(control, j) for j in range(k) if j != control]
    return list(itertools.combinations(range(k), 2))


def _holm_sidak(p: list[float]) -> list[float]:
    m = len(p)
    order = np.argsort(p)
    adj = np.empty(m)
    running = 0.0
    for rank, i in enumerate(order):
        a = 1 - (1 - p[i]) ** (m - rank)
        running = max(running, a)
        adj[i] = min(running, 1.0)
    return adj.tolist()


def smm_cdf(q: float, m: int, df: float) -> float:
    """Studentized maximum modulus: P(max of m |Z_i| / S ≤ q), the Z_i independent normals
    sharing one S = √(χ²_df / df). Used by Dunnett's T3."""
    from scipy import integrate, special
    if not math.isfinite(df):
        return float((2 * sps.norm.cdf(q) - 1) ** m)
    logk = 0.5 * df * math.log(df) - special.gammaln(df / 2) - (df / 2 - 1) * math.log(2)

    def f(s):
        if s <= 0:
            return 0.0
        return math.exp(logk + (df - 1) * math.log(s) - df * s * s / 2) * (2 * sps.norm.cdf(q * s) - 1) ** m
    val, _ = integrate.quad(f, 0, np.inf, limit=200, epsabs=1e-14, epsrel=1e-11)
    return min(max(val, 0.0), 1.0)


def compare(groups: list[np.ndarray], model: str, method: str, family: str, control: int,
            conf: float, omnibus: dict, Y: np.ndarray | None = None,
            individual: bool = False) -> list[dict]:
    """One dict per comparison: i, j, diff (j − i for control family; i − j otherwise),
    ci (lo, hi) or None, p (adjusted). `individual` (repeated measures without assuming
    sphericity, as Prism): each comparison uses only its two columns' differences, with
    n − 1 degrees of freedom."""
    k = len(groups)
    pairs = _pairs(k, family, control)
    m = len(pairs)
    alpha = 1 - conf
    out = []
    if model in ("kw", "friedman"):
        return _dunn(groups, model, method, pairs, Y)
    if model == "rm":
        mse, df = omnibus["ms_r"], omnibus["df_r"]
        means = Y.mean(axis=0)
        ns = np.full(k, Y.shape[0], float)
    else:
        means = np.array([g.mean() for g in groups])
        ns = np.array([len(g) for g in groups], float)
        mse = omnibus.get("msw")
        df = omnibus.get("dfw")
    if method == "dunnett" and model in ("ordinary", "rm") and not (individual and model == "rm"):
        return _dunnett(groups, means, ns, mse, df, control, conf)
    raw = []
    for i, j in pairs:
        diff = means[i] - means[j]
        if model == "rm" and individual:
            d = Y[:, i] - Y[:, j]
            se = float(d.std(ddof=1) / math.sqrt(len(d)))
            dfp = len(d) - 1
        elif model == "welch":
            vi, vj = groups[i].var(ddof=1) / ns[i], groups[j].var(ddof=1) / ns[j]
            se = math.sqrt(vi + vj)
            dfp = (vi + vj) ** 2 / (vi ** 2 / (ns[i] - 1) + vj ** 2 / (ns[j] - 1))
        else:
            se = math.sqrt(mse * (1 / ns[i] + 1 / ns[j]))
            dfp = df
        t = diff / se if se > 0 else math.inf
        p_raw = float(2 * sps.t.sf(abs(t), dfp))
        raw.append((i, j, diff, se, dfp, t, p_raw))
    if method == "holm_sidak":
        adj = _holm_sidak([r[6] for r in raw])
    for idx, (i, j, diff, se, dfp, t, p_raw) in enumerate(raw):
        ci = None
        if method in ("tukey", "games_howell"):
            q = abs(diff) / (se / math.sqrt(2))
            p = float(sps.studentized_range.sf(q, k, dfp))
            qc = float(sps.studentized_range.ppf(conf, k, dfp))
            half = qc * se / math.sqrt(2)
            ci = (diff - half, diff + half)
        elif method == "t3":                    # studentized maximum modulus, each pair's own df
            from scipy.optimize import brentq      # (Welch df rounded down, as Prism and the tables)
            dft = max(1.0, math.floor(dfp)) if math.isfinite(dfp) else dfp
            p = 1.0 - smm_cdf(abs(t), m, dft)
            tc = brentq(lambda c: smm_cdf(c, m, dft) - conf, 1e-6, 100.0, xtol=1e-10)
            ci = (diff - tc * se, diff + tc * se)
        elif method == "dunnett":               # individual variances: Dunnett on each pair's t
            lam = np.full(m, math.sqrt(0.5))
            p = 1.0 - dunnett_cdf(abs(t), lam, dfp)
            from scipy.optimize import brentq
            tc = brentq(lambda c: dunnett_cdf(c, lam, dfp) - conf, 0.5, 50.0, xtol=1e-10)
            ci = (diff - tc * se, diff + tc * se)
        elif method == "sidak":
            p = 1 - (1 - p_raw) ** m
            tc = float(sps.t.ppf(1 - (1 - (1 - alpha) ** (1 / m)) / 2, dfp))
            ci = (diff - tc * se, diff + tc * se)
        elif method in ("bonferroni", "t2"):
            p = min(1.0, p_raw * m)
            tc = float(sps.t.ppf(1 - alpha / (2 * m), dfp))
            ci = (diff - tc * se, diff + tc * se)
        elif method == "holm_sidak":
            p = adj[idx]
        else:                                   # fisher
            p = p_raw
            tc = float(sps.t.ppf(1 - alpha / 2, dfp))
            ci = (diff - tc * se, diff + tc * se)
        out.append({"i": i, "j": j, "diff": float(diff), "ci": ci, "p": float(min(max(p, 0.0), 1.0))})
    return out


def _dunnett_inner(c: float, s: float, lam: np.ndarray, zs: np.ndarray, ws: np.ndarray) -> float:
    """P(|T_j| ≤ c for all j | S = s): Gauss-Hermite over the shared normal component."""
    q = np.sqrt(1 - lam ** 2)
    prod = np.ones_like(zs)
    for l, qq in zip(lam, q):
        prod *= sps.norm.cdf((c * s + l * zs) / qq) - sps.norm.cdf((-c * s + l * zs) / qq)
    return float(np.sum(ws * prod))


def dunnett_cdf(c: float, lam: np.ndarray, df: float) -> float:
    """P(max_j |T_j| ≤ c) for Dunnett's multivariate t (correlations λ_i λ_j), computed by
    numerical integration: deterministic and accurate (scipy's version is Monte Carlo)."""
    zs, ws = np.polynomial.hermite_e.hermegauss(96)
    ws = ws / math.sqrt(2 * math.pi)
    if not math.isfinite(df):
        return _dunnett_inner(c, 1.0, lam, zs, ws)
    from scipy import integrate, special
    logk = 0.5 * df * math.log(df) - special.gammaln(df / 2) - (df / 2 - 1) * math.log(2)

    def f(s):
        if s <= 0:
            return 0.0
        return math.exp(logk + (df - 1) * math.log(s) - df * s * s / 2) * _dunnett_inner(c, s, lam, zs, ws)
    val, _ = integrate.quad(f, 0, np.inf, limit=200, epsabs=1e-14, epsrel=1e-11)
    return min(max(val, 0.0), 1.0)


def _dunnett(groups, means, ns, mse, df, control, conf) -> list[dict]:
    """Dunnett's test against a control, using the pooled mean square of the ANOVA."""
    from scipy.optimize import brentq
    k = len(groups)
    others = [j for j in range(k) if j != control]
    lam = np.array([math.sqrt(ns[j] / (ns[j] + ns[control])) for j in others])
    crit = brentq(lambda c: dunnett_cdf(c, lam, df) - conf, 0.5, 50.0, xtol=1e-10)
    out = []
    for j in others:
        se = math.sqrt(mse * (1 / ns[control] + 1 / ns[j]))
        diff = means[control] - means[j]
        p = 1.0 - dunnett_cdf(abs(diff / se), lam, df)
        out.append({"i": control, "j": j, "diff": float(diff),
                    "ci": (float(diff - crit * se), float(diff + crit * se)),
                    "p": float(min(max(p, 0.0), 1.0))})
    return out


def _dunn(groups, model, method, pairs, Y) -> list[dict]:
    k = len(groups)
    m = len(pairs)
    out = []
    if model == "kw":
        allv = np.concatenate(groups)
        N = len(allv)
        ranks = sps.rankdata(allv)
        bounds = np.cumsum([0] + [len(g) for g in groups])
        mean_ranks = [ranks[bounds[i]:bounds[i + 1]].mean() for i in range(k)]
        _, tie_counts = np.unique(allv, return_counts=True)
        tie = np.sum(tie_counts ** 3 - tie_counts) / (12 * (N - 1))
        for i, j in pairs:
            ni, nj = len(groups[i]), len(groups[j])
            se = math.sqrt((N * (N + 1) / 12 - tie) * (1 / ni + 1 / nj))
            d = mean_ranks[i] - mean_ranks[j]
            p = float(2 * sps.norm.sf(abs(d / se)))
            out.append({"i": i, "j": j, "diff": float(d), "ci": None,
                        "p": min(1.0, p * m) if method == "dunn" else p})
    else:
        n = Y.shape[0]
        R = np.apply_along_axis(sps.rankdata, 1, Y)
        rank_sums = R.sum(axis=0)
        se = math.sqrt(n * k * (k + 1) / 6)
        for i, j in pairs:
            d = rank_sums[i] - rank_sums[j]
            p = float(2 * sps.norm.sf(abs(d / se)))
            out.append({"i": i, "j": j, "diff": float(d), "ci": None,
                        "p": min(1.0, p * m) if method == "dunn" else p})
    return out


# ---------------------------------------------------------------------------
# Runner → result pages
# ---------------------------------------------------------------------------

def one_way(an) -> AnalysisResult:
    ALPHA = float(an.params.get("alpha", 0.05))      # significance level (Settings)
    t, cols, p = an.table, list(an.columns), an.params
    if len(cols) < 3:
        raise ValueError("One-way ANOVA compares three or more data sets. Choose at least three.")
    model = model_of(p)
    conf = p.get("conf", 0.95)
    family = p.get("compare", "all")             # all | control | none
    control_col = p.get("control", cols[0])
    control = cols.index(control_col) if control_col in cols else 0
    method = p.get("method") or DEFAULT_METHOD[(model, "control" if family == "control" else "all")]
    if method not in METHODS_FOR[model]:
        method = DEFAULT_METHOD[(model, "control" if family == "control" else "all")]
    letters = [column_letter(c) for c in cols]
    labels = [t.label(c) for c in cols]

    Y = None
    if model == "rm":
        # Prism: a mixed-effects model when values are missing (or when asked for)
        partial = []
        for r in range(t.nrows_used()):
            vals = [t.row_values(r, c) for c in cols]
            n_ok = sum(len(v) == 1 for v in vals)
            if 0 < n_ok < len(cols):
                partial.append(r)
        rm_method = p.get("rm_method", "auto")
        if rm_method == "anova" and partial:
            raise ValueError(f"{len(partial)} row(s) have missing values, so repeated-measures ANOVA "
                             "can't be calculated. Choose the mixed-effects model in the settings.")
        if rm_method == "mixed" or partial:
            return _one_way_mixed(t, cols, p, method, family, control, conf, letters, labels)
    if model in ("rm", "friedman"):
        rows_ok = []
        nrows = t.nrows_used()
        for r in range(nrows):
            vals = [t.row_values(r, c) for c in cols]
            if all(len(v) == 1 for v in vals):
                rows_ok.append([float(v[0]) for v in vals])
        Y = np.array(rows_ok, float)
        if Y.shape[0] < 2:
            raise ValueError("Repeated measures need at least two complete rows (one per subject).")
        groups = [Y[:, i] for i in range(len(cols))]
    else:
        groups = [t.values(c) for c in cols]
        if any(len(g) < 2 for g in groups):
            raise ValueError("Each data set needs at least two values.")

    name = title(p)
    rows: list[tuple[str, list[str], str]] = [
        ("Data table", [t.name], "row"),
        ("Data sets", [", ".join(f"{a}: {lab}" for a, lab in zip(letters, labels))], "row"),
        ("", [], "blank"), (name, [], "section")]
    res = AnalysisResult()

    def p_rows(pv, label="P value"):
        rows.extend([(label, [fmt_p(pv)], "row"), ("Significance", [p_summary(pv)], "row"),
                     (f"Significant at α = {ALPHA:g}", ["Yes" if pv < ALPHA else "No"], "row")])

    table_page = None
    if model == "ordinary":
        o = ordinary(groups)
        res.p = o["p"]
        rows.append(("F", [f"{o['F']:.4g}"], "row"))
        rows.append(("Degrees of freedom (between, within)", [f"{o['dfb']}, {o['dfw']}"], "row"))
        p_rows(o["p"])
        rows.append(("R²", [f"{o['r2']:.4f}"], "row"))
        bf = sps.levene(*groups, center="median")
        bt = sps.bartlett(*groups)
        rows += [("", [], "blank"), ("Equal SDs?", [], "section"),
                 ("Brown-Forsythe test F", [f"{bf.statistic:.4g}"], "row"),
                 ("Brown-Forsythe test P", [fmt_p(bf.pvalue)], "row"),
                 ("Bartlett's test χ²", [f"{bt.statistic:.4g}"], "row"),
                 ("Bartlett's test P", [fmt_p(bt.pvalue)], "row"),
                 (f"SDs differ at α = {ALPHA:g}", ["Yes" if min(bf.pvalue, bt.pvalue) < ALPHA else "No"], "row")]
        table_page = ResultPage("ANOVA table", ["Sum of squares", "DF", "Mean square", "F", "P"], [
            ("Between data sets", [fmt(o["ssb"]), str(o["dfb"]), fmt(o["msb"]), f"{o['F']:.4g}", fmt_p(o["p"])], "row"),
            ("Within data sets (residual)", [fmt(o["ssw"]), str(o["dfw"]), fmt(o["msw"]), "", ""], "row"),
            ("Total", [fmt(o["sst"]), str(o["dfb"] + o["dfw"]), "", "", ""], "row")])
        omni = o
    elif model == "welch":
        w = welch_anova(groups)
        res.p = w["welch"]["p"]
        rows += [("Welch's ANOVA F", [f"{w['welch']['F']:.4g}"], "row"),
                 ("Degrees of freedom", [f"{w['welch']['df1']}, {fmt(w['welch']['df2'])}"], "row")]
        p_rows(w["welch"]["p"])
        rows += [("", [], "blank"), ("Brown-Forsythe ANOVA", [], "section"),
                 ("F*", [f"{w['bf']['F']:.4g}"], "row"),
                 ("Degrees of freedom", [f"{w['bf']['df1']}, {fmt(w['bf']['df2'])}"], "row"),
                 ("P value", [fmt_p(w["bf"]["p"])], "row"),
                 ("Significance", [p_summary(w["bf"]["p"])], "row")]
        omni = {}
    elif model == "rm":
        r = rm_anova(Y, p.get("gg", True))
        res.p = r["p"]
        rows.append(("F", [f"{r['F']:.4g}"], "row"))
        rows.append(("Degrees of freedom (treatment, residual)", [f"{r['df_t']}, {r['df_r']}"], "row"))
        p_rows(r["p"])
        rows.append(("Geisser-Greenhouse ε", [f"{r['eps']:.4f}"], "row"))
        rows.append(("Correction applied", ["Geisser-Greenhouse" if r["gg"] else "None (sphericity assumed)"], "row"))
        rows.append(("R²", [f"{r['r2']:.4f}"], "row"))
        rows += [("", [], "blank"), ("Matching", [], "section"),
                 ("F (subjects)", [f"{r['F_subj']:.4g}"], "row"),
                 ("P value", [fmt_p(r["p_subj"])], "row"),
                 (f"Matching effective at α = {ALPHA:g}", ["Yes" if r["p_subj"] < ALPHA else "No"], "row"),
                 ("Subjects (complete rows)", [str(Y.shape[0])], "row")]
        table_page = ResultPage("ANOVA table", ["Sum of squares", "DF", "Mean square", "F", "P"], [
            ("Treatment (between columns)", [fmt(r["ss_treat"]), str(r["df_t"]), fmt(r["ms_t"]), f"{r['F']:.4g}", fmt_p(r["p"])], "row"),
            ("Subjects (between rows)", [fmt(r["ss_subj"]), str(r["df_s"]), fmt(r["ms_s"]), f"{r['F_subj']:.4g}", fmt_p(r["p_subj"])], "row"),
            ("Residual", [fmt(r["ss_res"]), str(r["df_r"]), fmt(r["ms_r"]), "", ""], "row"),
            ("Total", [fmt(r["ss_total"]), str(r["df_t"] + r["df_s"] + r["df_r"]), "", "", ""], "row")])
        omni = r
    elif model == "kw":
        h = sps.kruskal(*groups)
        exact = kw_exact_p(groups)                 # small and moderate samples, as Prism
        pv = exact if exact is not None else float(h.pvalue)
        res.p = pv
        allv = np.concatenate(groups)
        ranks = sps.rankdata(allv)
        bounds = np.cumsum([0] + [len(g) for g in groups])
        rows.append(("Kruskal-Wallis statistic (H)", [f"{h.statistic:.4g}"], "row"))
        p_rows(pv)
        rows.append(("P value method", ["Exact" if exact is not None else "Approximate (χ²)"], "row"))
        rows += [("", [], "blank"), ("Mean ranks", [], "section")]
        rows += [(f"{a}: {lab}", [fmt(ranks[bounds[i]:bounds[i + 1]].mean())], "row")
                 for i, (a, lab) in enumerate(zip(letters, labels))]
        omni = {}
    else:                                           # friedman
        fr = sps.friedmanchisquare(*[Y[:, i] for i in range(Y.shape[1])])
        res.p = float(fr.pvalue)
        rows.append(("Friedman statistic", [f"{fr.statistic:.4g}"], "row"))
        p_rows(float(fr.pvalue))
        rows.append(("P value method", ["Approximate (χ²)"], "row"))
        rows.append(("Subjects (complete rows)", [str(Y.shape[0])], "row"))
        omni = {}

    pages = [ResultPage("Results", [name], rows)]
    if table_page is not None:
        pages.append(table_page)

    if family != "none":
        comps = compare(groups, model, method, family, control, conf, omni, Y,
                        individual=model == "rm" and bool(p.get("gg", True)))
        crow = []
        nonpar = model in ("kw", "friedman")
        for c in comps:
            i, j = c["i"], c["j"]
            ci = f"{fmt(c['ci'][0])} to {fmt(c['ci'][1])}" if c["ci"] else ""
            crow.append((f"{letters[i]}: {labels[i]}  vs.  {letters[j]}: {labels[j]}",
                         [fmt(c["diff"]), ci, "Yes" if c["p"] < ALPHA else "No", p_summary(c["p"]),
                          fmt_p(c["p"])], "row"))
            res.comparisons.append((cols[i], cols[j], c["p"]))
        heads = ["Mean rank difference" if model == "kw" else
                 "Rank sum difference" if model == "friedman" else "Mean difference",
                 "" if nonpar or method == "holm_sidak" else f"{conf:.0%} CI of difference",
                 "Significant?", "Significance", "Adjusted P"]
        cp = ResultPage("Comparisons", heads, [(METHOD_NAMES[method], [], "section")] + crow)
        cp.first_column = "Comparison"
        pages.append(cp)
    if p.get("descriptive", False):
        from .column import _descriptive_page
        pages.append(_descriptive_page(t, cols))
    res.pages = pages
    return res


def _one_way_mixed(t, cols, p, method, family, control, conf, letters, labels) -> AnalysisResult:
    """Repeated-measures one-way ANOVA with missing values: mixed-effects model (REML,
    compound symmetry; mixed.py). Rows are subjects."""
    ALPHA = float(p.get("alpha", 0.05))      # significance level (Settings)
    from . import mixed as mm
    from .anova2 import _adjust, fmt_df
    k = len(cols)
    y, g, s = [], [], []
    for r in range(t.nrows_used()):
        for i, c in enumerate(cols):
            v = t.row_values(r, c)
            if len(v) == 1:
                y.append(float(v[0]))
                g.append(i)
                s.append(r)
    y, g, s = np.array(y), np.array(g), np.array(s)
    if any(not np.any(g == i) for i in range(k)):
        raise ValueError("Every data set needs at least one value.")
    X = np.column_stack([np.ones(len(y)), mm.effect_codes(g, k)])
    f = mm.fit(y, X, [mm.indicator(s)])
    F, q = f.wald(mm.L_for(slice(1, k), X.shape[1]))
    df_r = f.df_resid
    # Geisser-Greenhouse ε from the complete rows, as RM ANOVA would
    complete = [[float(t.row_values(r, c)[0]) for c in cols] for r in range(t.nrows_used())
                if all(len(t.row_values(r, c)) == 1 for c in cols)]
    eps = rm_anova(np.array(complete), False)["eps"] if len(complete) >= 2 else 1.0
    gg = p.get("gg", True)
    e = eps if gg else 1.0
    pv = float(sps.f.sf(F, q * e, df_r * e))
    subjects = len(np.unique(s))
    missing = subjects * k - len(y)
    chi, dfc, pc = f.lrt()
    rows = [("Data table", [t.name], "row"),
            ("Data sets", [", ".join(f"{a}: {lab}" for a, lab in zip(letters, labels))], "row"),
            ("Method", ["Mixed-effects model (REML, compound symmetry)"], "row"),
            ("Why", ["Values are missing" if missing else "Chosen in the settings"], "row"),
            ("", [], "blank"), ("Fixed effect (type III)", [], "section"),
            ("F", [f"{F:.4g} ({fmt_df(q * e)}, {fmt_df(df_r * e)})"], "row"),
            ("P value", [fmt_p(pv)], "row"), ("Significance", [p_summary(pv)], "row"),
            (f"Significant at α = {ALPHA:g}", ["Yes" if pv < ALPHA else "No"], "row"),
            ("Geisser-Greenhouse ε", [f"{eps:.4f}"], "row"),
            ("Correction applied", ["Geisser-Greenhouse" if gg else "None (sphericity assumed)"], "row"),
            ("", [], "blank"), ("Random effects", [], "section"),
            ("Subject: SD", [fmt(math.sqrt(f.variances[0])) if f.variances[0] >= 0 else "(negative variance)"], "row"),
            ("Subject: variance", [fmt(f.variances[0])], "row"),
            ("Residual: SD", [fmt(math.sqrt(f.sigma2))], "row"),
            ("Residual: variance", [fmt(f.sigma2)], "row"),
            ("", [], "blank"), ("Was the matching effective?", [], "section"),
            ("χ² (likelihood ratio)", [f"{chi:.4g}"], "row"), ("Degrees of freedom", [str(dfc)], "row"),
            ("P value", [fmt_p(pc)], "row"),
            (f"Matching effective at α = {ALPHA:g}", ["Yes" if pc < ALPHA else "No"], "row"),
            ("", [], "blank"), ("Data summary", [], "section"),
            ("Subjects (rows)", [str(subjects)], "row"), ("Values analysed", [str(len(y))], "row"),
            ("Missing values", [str(missing)], "row")]
    res = AnalysisResult()
    res.p = pv
    pages = [ResultPage("Results", ["Mixed-effects analysis"], rows),
             ResultPage("Fixed effects", ["F", "DFn", "DFd", "P"],
                        [("Treatment (between columns)", [f"{F:.4g}", fmt_df(q * e), fmt_df(df_r * e), fmt_p(pv)], "row")])]
    if family != "none":
        def vec(i):
            v = np.zeros(k)
            v[0] = 1.0
            if i < k - 1:
                v[1 + i] = 1.0
            else:
                v[1:] = -1.0
            return v
        pairs = _pairs(k, family, control)
        comps = []
        if method == "dunnett":
            from scipy.optimize import brentq
            ns = np.array([np.sum(g == i) for i in range(k)], float)
            others = [j for j in range(k) if j != control]
            lam = np.array([math.sqrt(ns[j] / (ns[j] + ns[control])) for j in others])
            crit = brentq(lambda c_: dunnett_cdf(c_, lam, df_r) - conf, 0.5, 50.0, xtol=1e-10)
            for j in others:
                d, se = f.contrast(vec(control) - vec(j))
                pj = 1.0 - dunnett_cdf(abs(d / se), lam, df_r)
                comps.append({"i": control, "j": j, "diff": d, "ci": (d - crit * se, d + crit * se),
                              "p": float(min(max(pj, 0.0), 1.0))})
        else:
            raw = []
            for i, j in pairs:
                d, se = f.contrast(vec(i) - vec(j))
                raw.append(("", d, se, df_r))
            for (i, j), r_ in zip(pairs, _adjust(raw, method, k, conf)):
                comps.append({"i": i, "j": j, "diff": r_["diff"], "ci": r_["ci"], "p": r_["p"]})
        crow = []
        for c in comps:
            i, j = c["i"], c["j"]
            ci = f"{fmt(c['ci'][0])} to {fmt(c['ci'][1])}" if c["ci"] else ""
            crow.append((f"{letters[i]}: {labels[i]}  vs.  {letters[j]}: {labels[j]}",
                         [fmt(c["diff"]), ci, "Yes" if c["p"] < ALPHA else "No", p_summary(c["p"]),
                          fmt_p(c["p"])], "row"))
            res.comparisons.append((cols[i], cols[j], c["p"]))
        cp = ResultPage("Comparisons", ["Mean difference", "" if method == "holm_sidak" else
                                        f"{conf:.0%} CI of difference", "Significant?", "Significance",
                                        "Adjusted P"], [(METHOD_NAMES[method], [], "section")] + crow)
        cp.first_column = "Comparison"
        pages.append(cp)
    if p.get("descriptive", False):
        from .column import _descriptive_page
        pages.append(_descriptive_page(t, cols))
    res.pages = pages
    return res


# ---------------------------------------------------------------------------
# Exact Kruskal-Wallis P (as Prism: small and moderate samples, also with ties)
# ---------------------------------------------------------------------------

def kw_exact_p(groups: list[np.ndarray], max_cells: float = 1.2e7) -> float | None:
    """P(H ≥ H observed) over every way of dealing the observed values (ties kept) into
    groups of the same sizes. Counting by dynamic programming over the distinct values;
    None when the samples are too large (then the χ² approximation is used)."""
    from math import comb
    sizes = [len(g) for g in groups]
    k, allv = len(groups), np.concatenate(groups)
    N = len(allv)
    if k < 2 or N < 2:
        return None
    ranks2 = np.rint(sps.rankdata(allv) * 2).astype(int)        # doubled midranks: integers
    bounds = np.cumsum([0] + sizes)
    obs = [int(ranks2[bounds[i]:bounds[i + 1]].sum()) for i in range(k)]
    stat = lambda sums: sum(s * s / n for s, n in zip(sums, sizes))
    t_obs = stat(obs)
    vals, counts = np.unique(ranks2, return_counts=True)        # each tie block: (rank, size)
    total = float(math.factorial(N))
    for n in sizes:
        total /= math.factorial(n)
    if k == 3:
        n1, n2, _n3 = sizes
        S = int(ranks2.sum())
        cells = (n1 + 1) * (n2 + 1) * (S + 1) ** 2
        if cells > max_cells:
            return None
        W = np.zeros((n1 + 1, n2 + 1, S + 1, S + 1))
        W[0, 0, 0, 0] = 1.0
        for r, t in zip(vals, counts):
            r, t = int(r), int(t)
            new = np.zeros_like(W)
            for a1 in range(min(t, n1) + 1):
                for a2 in range(min(t - a1, n2) + 1):
                    w = comb(t, a1) * comb(t - a1, a2)
                    d1, d2 = a1 * r, a2 * r
                    new[a1:, a2:, d1:, d2:] += w * W[:n1 + 1 - a1, :n2 + 1 - a2, :S + 1 - d1, :S + 1 - d2]
            W = new
        F = W[n1, n2]
        s1, s2 = np.nonzero(F)
        s3 = S - s1 - s2
        tv = s1 ** 2 / sizes[0] + s2 ** 2 / sizes[1] + s3 ** 2 / sizes[2]
        hit = tv >= t_obs * (1 - 1e-10) - 1e-9
        return float(min(1.0, F[s1[hit], s2[hit]].sum() / total))
    if total > 2e6:                                  # more groups: a dictionary of states
        return None
    states = {(tuple([0] * (k - 1)), tuple([0] * (k - 1))): 1.0}
    done = 0
    for r, t in zip(vals, counts):
        r, t = int(r), int(t)
        nxt: dict = {}

        def splits(left, i):
            if i == k - 1:
                yield ()
                return
            for a in range(left + 1):
                for rest in splits(left - a, i + 1):
                    yield (a,) + rest
        for (cs, ss), w in states.items():
            used = sum(cs)
            for parts in splits(t, 0):
                last = t - sum(parts)
                if any(c + a > sizes[i] for i, (c, a) in enumerate(zip(cs, parts))) or \
                        (done - used) + last > sizes[-1]:
                    continue
                mult, left = 1, t
                for a in parts:
                    mult *= comb(left, a)
                    left -= a
                key = (tuple(c + a for c, a in zip(cs, parts)), tuple(s + a * r for s, a in zip(ss, parts)))
                nxt[key] = nxt.get(key, 0.0) + w * mult
        states = nxt
        done += t
    S = int(ranks2.sum())
    hit = sum(w for (cs, ss), w in states.items()
              if stat(list(ss) + [S - sum(ss)]) >= t_obs * (1 - 1e-10) - 1e-9)
    return float(min(1.0, hit / total))
