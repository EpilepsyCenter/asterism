"""Two-way ANOVA on grouped (and XY) tables, with multiple comparisons.

Rows are one factor and data sets (columns) the other; replicates (sub-columns) are the
values in each cell. Designs (Prism's choices, our wording):

  ordinary  no matching
  rm_rows   each sub-column is one subject measured in every row
            (rows within subjects, columns between subjects)
  rm_cols   each sub-column position is one subject measured in every column
            (columns within subjects, rows between subjects)
  rm_both   each sub-column position is one subject measured in every cell

Repeated-measures designs use an unweighted-means analysis, which reproduces Prism's sums
of squares exactly with unequal group sizes (golden tests): with G groups of sizes n_g,
n_h = harmonic mean of n_g,
  SS_between = R·n_h·Σ(group mean − mean of group means)²
  SS_within  = G·n_h·Σ(unweighted level mean − grand)²
  SS_inter   = n_h·Σ(cell − group − level + grand)²
Post tests reproduce Prism's: comparisons between groups at one level use the pooled
subjects + residual mean square (df pooled); comparisons between levels within a group use
the residual mean square. Ordinary designs use Type III sums of squares (regression with
effect coding), equal to the classical sums when the design is balanced.
"""

from __future__ import annotations

import itertools
import math

import numpy as np
from scipy import stats as sps

from asterism.doc.model import column_letter

from . import mixed as mm
from .anova import _holm_sidak
from .results import AnalysisResult, ResultPage, fmt, fmt_p, p_summary

RM_METHODS = {"auto": "Mixed-effects model only when values are missing",
              "anova": "Always repeated-measures ANOVA", "mixed": "Always the mixed-effects model"}
DESIGNS = {"ordinary": "Ordinary two-way ANOVA", "rm_rows": "Two-way ANOVA, matched values in rows",
           "rm_cols": "Two-way ANOVA, matched values across columns",
           "rm_both": "Two-way ANOVA, matched values in every cell"}
COMPARE = {"both": "Within each row and within each column",
           "rows": "Within each row (compare columns)", "cols": "Within each column (compare rows)",
           "main_cols": "Column means (main effect)", "main_rows": "Row means (main effect)",
           "cells": "Every cell with every other cell", "none": "No multiple comparisons"}
METHODS = {"tukey": "Tukey", "bonferroni": "Bonferroni", "sidak": "Šídák",
           "holm_sidak": "Holm-Šídák", "fisher": "Fisher's LSD (no correction)"}


def fmt_df(v) -> str:
    """Degrees of freedom: whole numbers as integers; corrected (fractional) df to 2 decimals."""
    v = float(v)
    return str(int(round(v))) if abs(v - round(v)) < 1e-9 else f"{v:.2f}"


def title(params: dict) -> str:
    if params.get("design", "ordinary") == "ordinary":
        return "Two-way ANOVA"
    return "Mixed-effects analysis" if params.get("rm_method") == "mixed" else "Two-way RM ANOVA"


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

def cells(t, rows: list[int], cols: list[int]) -> list[list[list[float | None]]]:
    """cells[r][c] = list of replicate values (None kept, so positions stay matched)."""
    out = []
    for r in rows:
        row = []
        for c in cols:
            row.append([_num(t.get(r, t.flat(c, s))) if (r, t.flat(c, s)) not in t.excluded else None
                        for s in range(t.width())])
        out.append(row)
    return out


def _num(v):
    return float(v) if isinstance(v, (int, float)) else None


def used_rows(t, cols: list[int]) -> list[int]:
    return [r for r in range(t.nrows_used())
            if any(len(t.row_values(r, c)) for c in cols)]


# ---------------------------------------------------------------------------
# Ordinary (Type III by regression)
# ---------------------------------------------------------------------------

def _effect_codes(levels: np.ndarray, k: int) -> np.ndarray:
    X = np.zeros((len(levels), k - 1))
    for j in range(k - 1):
        X[levels == j, j] = 1.0
    X[levels == k - 1, :] = -1.0
    return X


def ordinary(C: list[list[list[float | None]]]) -> dict:
    R, K = len(C), len(C[0])
    y, ra, ca = [], [], []
    for r in range(R):
        for c in range(K):
            for v in C[r][c]:
                if v is not None:
                    y.append(v)
                    ra.append(r)
                    ca.append(c)
    y, ra, ca = np.array(y), np.array(ra), np.array(ca)
    if any(not np.any((ra == r) & (ca == c)) for r in range(R) for c in range(K)):
        raise ValueError("Every cell needs at least one value for two-way ANOVA.")
    A = _effect_codes(ra, R)
    B = _effect_codes(ca, K)
    AB = np.column_stack([A[:, i] * B[:, j] for i in range(R - 1) for j in range(K - 1)]) \
        if R > 1 and K > 1 else np.zeros((len(y), 0))
    one = np.ones((len(y), 1))

    def rss(X):
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        e = y - X @ beta
        return float(e @ e)
    full = np.column_stack([one, A, B, AB])
    rss_full = rss(full)
    ss_a = rss(np.column_stack([one, B, AB])) - rss_full
    ss_b = rss(np.column_stack([one, A, AB])) - rss_full
    ss_ab = rss(np.column_stack([one, A, B])) - rss_full
    N = len(y)
    df_a, df_b, df_ab = R - 1, K - 1, (R - 1) * (K - 1)
    df_res = N - R * K
    if df_res <= 0:
        raise ValueError("Two-way ANOVA needs replicate values (more than one value per cell).")
    ms_res = rss_full / df_res
    cell_n = np.array([[sum(v is not None for v in C[r][c]) for c in range(K)] for r in range(R)])
    cell_m = np.array([[np.mean([v for v in C[r][c] if v is not None]) for c in range(K)] for r in range(R)])
    rows = {"rows": (ss_a, df_a), "cols": (ss_b, df_b), "inter": (ss_ab, df_ab)}
    out = {"table": {}, "residual": (rss_full, df_res, ms_res), "cell_m": cell_m, "cell_n": cell_n,
           "total": float(((y - y.mean()) ** 2).sum())}
    for key, (ss, df) in rows.items():
        F = (ss / df) / ms_res if df > 0 else math.nan
        out["table"][key] = {"ss": ss, "df": df, "ms": ss / df if df else math.nan, "F": F,
                             "dfd": df_res, "p": float(sps.f.sf(F, df, df_res)) if df > 0 else math.nan}
    return out


# ---------------------------------------------------------------------------
# Repeated measures (unweighted means analysis; Prism-exact)
# ---------------------------------------------------------------------------

def _subjects_by_group(C, matched_axis: str) -> list[np.ndarray]:
    """matched_axis 'rows': subjects are sub-columns within each column group, measured in
    every row → one (n_g × R) array per column. 'cols': subjects are sub-column positions
    within each row group, measured in every column → one (n_g × K) array per row."""
    R, K = len(C), len(C[0])
    groups = []
    if matched_axis == "rows":
        for c in range(K):
            w = len(C[0][c])
            subj = [[C[r][c][s] for r in range(R)] for s in range(w)]
            groups.append(np.array([v for v in subj if all(x is not None for x in v)], float).reshape(-1, R))
    else:
        for r in range(R):
            w = len(C[r][0])
            subj = [[C[r][c][s] for c in range(K)] for s in range(w)]
            groups.append(np.array([v for v in subj if all(x is not None for x in v)], float).reshape(-1, K))
    return groups


def mixed(groups: list[np.ndarray], gg: bool) -> dict:
    """One between factor (groups) × one within factor (columns of each array)."""
    G = len(groups)
    L = groups[0].shape[1]
    n = np.array([len(x) for x in groups], float)
    if np.any(n < 1) or G < 2 or L < 2:
        raise ValueError("Each group needs at least one subject with values at every level.")
    N = n.sum()
    nh = G / np.sum(1.0 / n)
    cell = np.array([x.mean(axis=0) for x in groups])          # G × L
    gm = cell.mean(axis=1)                                       # group means (balanced within)
    lm = cell.mean(axis=0)                                       # unweighted level means
    um = gm.mean()
    ss_between = L * nh * float(((gm - um) ** 2).sum())
    ss_within = G * nh * float(((lm - um) ** 2).sum())
    ss_inter = nh * float(((cell - gm[:, None] - lm[None, :] + um) ** 2).sum())
    ss_subj = float(sum(L * ((x.mean(axis=1) - x.mean()) ** 2).sum() for x in groups))
    ss_res = float(sum(((x - x.mean(axis=1, keepdims=True) - x.mean(axis=0) + x.mean()) ** 2).sum()
                       for x in groups))
    df_b, df_w, df_i = G - 1, L - 1, (G - 1) * (L - 1)
    df_s, df_r = int(N - G), int((N - G) * (L - 1))
    ms_s, ms_r = ss_subj / df_s, ss_res / df_r
    # Geisser-Greenhouse epsilon from the pooled within-group covariance of the levels
    S = sum(np.cov(x, rowvar=False, ddof=1) * (len(x) - 1) for x in groups if len(x) > 1) / max(df_s, 1)
    S = np.atleast_2d(S)
    Cm = np.eye(L) - np.ones((L, L)) / L
    Sc = Cm @ S @ Cm
    eps = float(np.trace(Sc) ** 2 / ((L - 1) * np.sum(Sc * Sc))) if L > 2 and np.sum(Sc * Sc) > 0 else 1.0
    eps = min(max(eps, 1.0 / (L - 1)), 1.0)
    e = eps if gg else 1.0
    table = {
        "between": {"ss": ss_between, "df": df_b, "ms": ss_between / df_b, "F": (ss_between / df_b) / ms_s,
                    "dfn": df_b, "dfd": df_s},
        "within": {"ss": ss_within, "df": df_w, "ms": ss_within / df_w, "F": (ss_within / df_w) / ms_r,
                   "dfn": df_w * e, "dfd": df_r * e},
        "inter": {"ss": ss_inter, "df": df_i, "ms": ss_inter / df_i, "F": (ss_inter / df_i) / ms_r,
                  "dfn": df_i * e, "dfd": df_r * e},
        "subjects": {"ss": ss_subj, "df": df_s, "ms": ms_s},
    }
    for k in ("between", "within", "inter"):
        t = table[k]
        t["p"] = float(sps.f.sf(t["F"], t["dfn"], t["dfd"]))
    return {"table": table, "residual": (ss_res, df_r, ms_r), "cell": cell, "n": n, "eps": eps, "gg": gg,
            "pooled": ((ss_subj + ss_res) / (df_s + df_r), df_s + df_r),
            "total": float(sum(((x - np.concatenate([g.ravel() for g in groups]).mean()) ** 2).sum()
                               for x in groups))}


def both_within(C) -> dict:
    """Subjects (sub-column positions) measured in every cell: Y[s, r, c]."""
    R, K = len(C), len(C[0])
    w = len(C[0][0])
    subj = []
    for s in range(w):
        vals = [[C[r][c][s] if s < len(C[r][c]) else None for c in range(K)] for r in range(R)]
        if all(v is not None for row in vals for v in row):
            subj.append(vals)
    Y = np.array(subj, float)
    n = Y.shape[0]
    if n < 2:
        raise ValueError("Matched cells need at least two subjects with every cell filled.")
    g = Y.mean()
    ms = Y.mean(axis=(1, 2))
    mr = Y.mean(axis=(0, 2))
    mc = Y.mean(axis=(0, 1))
    mrc = Y.mean(axis=0)
    msr = Y.mean(axis=2)
    msc = Y.mean(axis=1)
    ss_s = R * K * ((ms - g) ** 2).sum()
    ss_r = n * K * ((mr - g) ** 2).sum()
    ss_c = n * R * ((mc - g) ** 2).sum()
    ss_rc = n * ((mrc - mr[:, None] - mc[None, :] + g) ** 2).sum()
    ss_rs = K * ((msr - ms[:, None] - mr[None, :] + g) ** 2).sum()
    ss_cs = R * ((msc - ms[:, None] - mc[None, :] + g) ** 2).sum()
    ss_tot = ((Y - g) ** 2).sum()
    ss_rcs = ss_tot - ss_s - ss_r - ss_c - ss_rc - ss_rs - ss_cs
    df = {"s": n - 1, "r": R - 1, "c": K - 1, "rc": (R - 1) * (K - 1), "rs": (R - 1) * (n - 1),
          "cs": (K - 1) * (n - 1), "rcs": (R - 1) * (K - 1) * (n - 1)}
    table = {}
    for key, ss, err_ss, err_df in (("rows", ss_r, ss_rs, df["rs"]), ("cols", ss_c, ss_cs, df["cs"]),
                                    ("inter", ss_rc, ss_rcs, df["rcs"])):
        d = df[{"rows": "r", "cols": "c", "inter": "rc"}[key]]
        F = (ss / d) / (err_ss / err_df)
        table[key] = {"ss": float(ss), "df": d, "ms": float(ss / d), "F": float(F), "dfn": d, "dfd": err_df,
                      "p": float(sps.f.sf(F, d, err_df))}
    table["subjects"] = {"ss": float(ss_s), "df": df["s"], "ms": float(ss_s / df["s"])}
    return {"table": table, "cell_m": mrc, "n": n,
            "errors": {"rows": (ss_rs, df["rs"]), "cols": (ss_cs, df["cs"]), "inter": (ss_rcs, df["rcs"])},
            "total": float(ss_tot)}


# ---------------------------------------------------------------------------
# Mixed-effects model (matched designs with missing values; see mixed.py)
# ---------------------------------------------------------------------------

def long_data(C, design: str) -> dict:
    """Every value with its row, data set and subject. Subjects: sub-column s of data set c
    (rm_rows), sub-column position s within row r (rm_cols), or position s (rm_both)."""
    R, K = len(C), len(C[0])
    need = {"rm_rows": R, "rm_cols": K, "rm_both": R * K}[design]
    y, a, b, s = [], [], [], []
    seen: dict = {}
    for r in range(R):
        for c in range(K):
            for k, v in enumerate(C[r][c]):
                sid = (c, k) if design == "rm_rows" else (r, k) if design == "rm_cols" else k
                if v is not None:
                    y.append(v)
                    a.append(r)
                    b.append(c)
                    s.append(str(sid))
                    seen[sid] = seen.get(sid, 0) + 1
    missing = sum(need - n for n in seen.values())
    return {"y": np.array(y, float), "a": np.array(a), "b": np.array(b), "s": np.array(s),
            "subjects": len(seen), "missing": missing, "complete": missing == 0}


def fit_mixed(C, design: str, gg: bool, data: dict) -> dict:
    R, K = len(C), len(C[0])
    y, a, b, s = data["y"], data["a"], data["b"], data["s"]
    if any(not np.any((a == r) & (b == c)) for r in range(R) for c in range(K)):
        raise ValueError("Every cell needs at least one value for the mixed-effects model.")
    X, sl, vec = mm.two_factor_design(a, b, R, K)
    Zs = [mm.indicator(s)]
    names = ["Subject"]
    if design == "rm_both":
        Zs += [mm.indicator(np.char.add(np.char.add(s, ":r"), a.astype(str))),
               mm.indicator(np.char.add(np.char.add(s, ":c"), b.astype(str)))]
        names += ["Subject × row factor", "Subject × column factor"]
    f = mm.fit(y, X, Zs)
    # Geisser-Greenhouse ε from the subjects with every value (as RM ANOVA would)
    eps = 1.0
    if design in ("rm_rows", "rm_cols"):
        try:
            eps = mixed(_subjects_by_group(C, "rows" if design == "rm_rows" else "cols"), False)["eps"]
        except Exception:
            eps = 1.0
    within = {"rm_rows": ("a", "ab"), "rm_cols": ("b", "ab"), "rm_both": ()}[design]
    contain = {"rm_rows": {"b": 0}, "rm_cols": {"a": 0}, "rm_both": {"a": 1, "b": 2}}[design]
    table = {}
    for key, out in (("a", "rows"), ("b", "cols"), ("ab", "inter")):
        F, q = f.wald(mm.L_for(sl[key], X.shape[1]))
        dfd = f.df_terms[contain[key]] if key in contain else f.df_resid
        e = eps if (gg and key in within) else 1.0
        table[out] = {"F": F, "df": q, "dfn": q * e, "dfd": dfd * e,
                      "p": float(sps.f.sf(F, q * e, dfd * e))}
    t_ = f.df_terms

    def df_rule(ca, cb):
        (ra, ka), (rb, kb) = ca, cb
        if design == "rm_rows":
            return f.df_resid if ka == kb else t_[0] + f.df_resid
        if design == "rm_cols":
            return f.df_resid if ra == rb else t_[0] + f.df_resid
        if ra == rb:
            return t_[2] + f.df_resid
        if ka == kb:
            return t_[1] + f.df_resid
        return t_[1] + t_[2] + f.df_resid
    return {"mm": f, "vec": vec, "df": df_rule, "table": table, "eps": eps, "gg": gg,
            "random": list(zip(names, f.variances)), "data": data}


# ---------------------------------------------------------------------------
# Multiple comparisons
# ---------------------------------------------------------------------------

def _adjust(raw: list[tuple], method: str, k_means: int, conf: float) -> list[dict]:
    """raw: (label, diff, se, df). Returns dicts with p (adjusted), ci."""
    m = len(raw)
    alpha = 1 - conf
    out = []
    praw = [float(2 * sps.t.sf(abs(d / se), df)) if se > 0 else 0.0 for _, d, se, df in raw]
    adj_hs = _holm_sidak(praw) if method == "holm_sidak" else None
    for idx, (label, d, se, df) in enumerate(raw):
        ci = None
        if method == "tukey" and k_means > 1:
            q = abs(d) / (se / math.sqrt(2))
            p = float(sps.studentized_range.sf(q, k_means, df))
            half = float(sps.studentized_range.ppf(conf, k_means, df)) * se / math.sqrt(2)
            ci = (d - half, d + half)
        elif method == "bonferroni":
            p = min(1.0, praw[idx] * m)
            tc = float(sps.t.ppf(1 - alpha / (2 * m), df))
            ci = (d - tc * se, d + tc * se)
        elif method == "sidak":
            p = 1 - (1 - praw[idx]) ** m
            tc = float(sps.t.ppf(1 - (1 - (1 - alpha) ** (1 / m)) / 2, df))
            ci = (d - tc * se, d + tc * se)
        elif method == "holm_sidak":
            p = adj_hs[idx]
        else:
            p = praw[idx]
            tc = float(sps.t.ppf(1 - alpha / 2, df))
            ci = (d - tc * se, d + tc * se)
        out.append({"label": label, "diff": float(d), "se": float(se), "df": float(df),
                    "t": float(d / se) if se > 0 else math.inf, "ci": ci, "p": float(min(max(p, 0.0), 1.0))})
    return out


def comparisons(design: str, fit: dict, compare: str, method: str, conf: float,
                row_names: list[str], col_names: list[str]) -> list[tuple[str, list[dict], list]]:
    """Families of comparisons: [(family title, results, [(cell a, cell b)])]."""
    if compare == "none":
        return []
    R, K = len(row_names), len(col_names)
    fams: list[tuple[str, list[tuple], list]] = []

    mmf = fit.get("mm")

    def cell_mean(r, c):
        if mmf is not None:
            return float(fit["vec"](r, c) @ mmf.beta)
        if design in ("rm_rows",):
            return fit["cell"][c, r]
        if design == "rm_cols":
            return fit["cell"][r, c]
        return fit["cell_m"][r, c]

    def se_df(a, b):
        (ra, ca), (rb, cb) = a, b
        if mmf is not None:
            return mmf.contrast(fit["vec"](*a) - fit["vec"](*b))[1], fit["df"](a, b)
        if design == "ordinary":
            ss, df, ms = fit["residual"]
            na, nb = fit["cell_n"][ra, ca], fit["cell_n"][rb, cb]
            return math.sqrt(ms * (1 / na + 1 / nb)), df
        if design == "rm_rows":                     # subjects within columns; rows within subjects
            n = fit["n"]
            if ca == cb:
                ss, df, ms = fit["residual"]
                return math.sqrt(ms * 2 / n[ca]), df
            msp, dfp = fit["pooled"]
            return math.sqrt(msp * (1 / n[ca] + 1 / n[cb])), dfp
        if design == "rm_cols":                     # subjects within rows; columns within subjects
            n = fit["n"]
            if ra == rb:
                ss, df, ms = fit["residual"]
                return math.sqrt(ms * 2 / n[ra]), df
            msp, dfp = fit["pooled"]
            return math.sqrt(msp * (1 / n[ra] + 1 / n[rb])), dfp
        # rm_both: error of the factor that differs (pooled with the interaction error)
        e = fit["errors"]
        if ra == rb:
            ss, df = e["cols"][0] + e["inter"][0], e["cols"][1] + e["inter"][1]
        elif ca == cb:
            ss, df = e["rows"][0] + e["inter"][0], e["rows"][1] + e["inter"][1]
        else:
            ss = e["rows"][0] + e["cols"][0] + e["inter"][0]
            df = e["rows"][1] + e["cols"][1] + e["inter"][1]
        return math.sqrt(ss / df * 2 / fit["n"]), df

    def lab(cell):
        r, c = cell
        return f"{row_names[r]}: {col_names[c]}"

    if compare in ("both", "rows"):
        for r in range(R):
            pairs = [((r, a), (r, b)) for a, b in itertools.combinations(range(K), 2)]
            fams.append((f"Within {row_names[r]}", pairs, K))
    if compare in ("both", "cols"):
        for c in range(K):
            pairs = [((a, c), (b, c)) for a, b in itertools.combinations(range(R), 2)]
            fams.append((f"Within {col_names[c]}", pairs, R))
    if compare == "cells":
        allc = [(r, c) for r in range(R) for c in range(K)]
        fams.append(("All cells", list(itertools.combinations(allc, 2)), len(allc)))
    out = []
    if compare in ("main_cols", "main_rows"):
        # marginal (unweighted) means; SE from the residual (ordinary) or the relevant error
        axis_cols = compare == "main_cols"
        L = K if axis_cols else R
        names = col_names if axis_cols else row_names
        raw = []
        pairs = list(itertools.combinations(range(L), 2))
        for a, b in pairs:
            if mmf is not None:                 # marginal means straight from the model
                if axis_cols:
                    va = np.mean([fit["vec"](r, a) for r in range(R)], axis=0)
                    vb = np.mean([fit["vec"](r, b) for r in range(R)], axis=0)
                    df = fit["df"]((0, a), (0, b))
                else:
                    va = np.mean([fit["vec"](a, c) for c in range(K)], axis=0)
                    vb = np.mean([fit["vec"](b, c) for c in range(K)], axis=0)
                    df = fit["df"]((a, 0), (b, 0))
                d_, se_ = mmf.contrast(va - vb)
                raw.append((f"{names[a]} vs. {names[b]}", d_, se_, df))
                continue
            if axis_cols:
                ma = np.mean([cell_mean(r, a) for r in range(R)])
                mb = np.mean([cell_mean(r, b) for r in range(R)])
                se_a = np.mean([se_df((r, a), (r, a))[0] ** 2 / 2 for r in range(R)]) / R
                se_b = np.mean([se_df((r, b), (r, b))[0] ** 2 / 2 for r in range(R)]) / R
                df = se_df((0, a), (0, b))[1]
            else:
                ma = np.mean([cell_mean(a, c) for c in range(K)])
                mb = np.mean([cell_mean(b, c) for c in range(K)])
                se_a = np.mean([se_df((a, c), (a, c))[0] ** 2 / 2 for c in range(K)]) / K
                se_b = np.mean([se_df((b, c), (b, c))[0] ** 2 / 2 for c in range(K)]) / K
                df = se_df((a, 0), (b, 0))[1]
            raw.append((f"{names[a]} vs. {names[b]}", ma - mb, math.sqrt(se_a + se_b), df))
        res = _adjust(raw, method, L, conf)
        cells_ = [((-1, a), (-1, b)) if axis_cols else ((a, -1), (b, -1)) for a, b in pairs]
        return [("Column means" if axis_cols else "Row means", res, cells_)]
    for title_, pairs, k in fams:
        raw = []
        for a, b in pairs:
            se, df = se_df(a, b)
            raw.append((f"{lab(a)} vs. {lab(b)}", cell_mean(*a) - cell_mean(*b), se, df))
        out.append((title_, _adjust(raw, method, k, conf), pairs))
    return out


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def two_way(an) -> AnalysisResult:
    t, cols, p = an.table, list(an.columns), an.params
    if t.table_type not in ("grouped", "xy"):
        raise ValueError("Two-way ANOVA works on a Grouped table (or an XY table with replicates).")
    if t.is_summary():
        raise ValueError("Two-way ANOVA needs the raw replicate values.")
    if len(cols) < 2:
        raise ValueError("Two-way ANOVA needs at least two data sets (columns).")
    rows = p.get("rows") or used_rows(t, cols)
    if len(rows) < 2:
        raise ValueError("Two-way ANOVA needs at least two rows with values.")
    design = p.get("design", "ordinary")
    compare = p.get("compare", "both")
    method = p.get("method", "tukey" if design == "ordinary" else "sidak")
    conf = p.get("conf", 0.95)
    row_f, col_f = p.get("row_factor", "Row factor"), p.get("col_factor", "Column factor")
    row_names = [t.row_label(r) for r in rows]
    col_names = [t.label(c) for c in cols]
    C = cells(t, rows, cols)

    use_mixed = False
    if design in ("rm_rows", "rm_cols", "rm_both"):
        data = long_data(C, design)
        rm_method = p.get("rm_method", "auto")
        if rm_method == "anova" and not data["complete"]:
            raise ValueError(f"{data['missing']} value(s) are missing, so repeated-measures ANOVA "
                             "can't be calculated. Choose the mixed-effects model in the settings.")
        use_mixed = rm_method == "mixed" or not data["complete"]
    if use_mixed:
        fit = fit_mixed(C, design, p.get("gg", False), data)
        return _mixed_result(t, rows, cols, p, design, fit, compare, method, conf, row_f, col_f,
                             row_names, col_names)
    if design == "ordinary":
        fit = ordinary(C)
        tb = fit["table"]
        src = [(row_f, tb["rows"]), (col_f, tb["cols"]), (f"{row_f} × {col_f}", tb["inter"])]
        resid = fit["residual"]
        extra = []
    elif design in ("rm_rows", "rm_cols"):
        groups = _subjects_by_group(C, "rows" if design == "rm_rows" else "cols")
        fit = mixed(groups, p.get("gg", False))
        tb = fit["table"]
        if design == "rm_rows":
            src = [(row_f, tb["within"]), (col_f, tb["between"]), (f"{row_f} × {col_f}", tb["inter"])]
        else:
            src = [(row_f, tb["between"]), (col_f, tb["within"]), (f"{row_f} × {col_f}", tb["inter"])]
        resid = fit["residual"]
        extra = [("Subjects (matching)", tb["subjects"])]
    elif design == "rm_both":
        fit = both_within(C)
        tb = fit["table"]
        src = [(row_f, tb["rows"]), (col_f, tb["cols"]), (f"{row_f} × {col_f}", tb["inter"])]
        resid = None
        extra = [("Subjects (matching)", tb["subjects"])]
    else:
        raise ValueError(f"Unknown design {design!r}.")

    total = fit["total"]
    rows_out: list[tuple[str, list[str], str]] = [
        ("Data table", [t.name], "row"), ("Design", [DESIGNS[design]], "row"), ("", [], "blank")]
    for name, s in src:
        rows_out += [(name, [], "section"),
                     ("% of total variation", [f"{100 * s['ss'] / total:.2f}" if total else ""], "row"),
                     ("F", [f"{s['F']:.4g} ({fmt_df(s.get('dfn', s['df']))}, {fmt_df(s.get('dfd', 0))})"], "row"),
                     ("P value", [fmt_p(s["p"])], "row"), ("Significance", [p_summary(s["p"])], "row"),
                     ("Significant at α = 0.05", ["Yes" if s["p"] < 0.05 else "No"], "row"),
                     ("", [], "blank")]
    if design in ("rm_rows", "rm_cols"):
        rows_out.append(("Geisser-Greenhouse ε", [f"{fit['eps']:.4f}"], "row"))
        rows_out.append(("Correction applied", ["Geisser-Greenhouse" if fit["gg"] else "None (sphericity assumed)"], "row"))
    res = AnalysisResult()
    res.p = src[-1][1]["p"]
    pages = [ResultPage("Results", [title(p)], rows_out)]
    trows = [(name, [fmt(s["ss"]), fmt_df(s["df"]), fmt(s["ms"]),
                     f"{s['F']:.4g}", fmt_p(s["p"])], "row") for name, s in src]
    for name, s in extra:
        trows.append((name, [fmt(s["ss"]), fmt_df(s["df"]), fmt(s["ms"]), "", ""], "row"))
    if resid is not None:
        trows.append(("Residual", [fmt(resid[0]), fmt_df(resid[1]), fmt(resid[2]), "", ""], "row"))
    pages.append(ResultPage("ANOVA table", ["Sum of squares", "DF", "Mean square", "F", "P"], trows))

    fams = comparisons(design, fit, compare, method, conf, row_names, col_names)
    if fams:
        crow = []
        for fam, results, pairs in fams:
            crow.append((fam, [], "section"))
            for r_, (a, b) in zip(results, pairs):
                ci = f"{fmt(r_['ci'][0])} to {fmt(r_['ci'][1])}" if r_["ci"] else ""
                crow.append((r_["label"], [fmt(r_["diff"]), ci, "Yes" if r_["p"] < 0.05 else "No",
                                           p_summary(r_["p"]), fmt_p(r_["p"])], "row"))
                if a[0] >= 0 and a[1] >= 0:      # in table coordinates (row, data set)
                    res.cell_comparisons.append(((rows[a[0]], cols[a[1]]), (rows[b[0]], cols[b[1]]),
                                                 r_["p"]))
        cp = ResultPage("Comparisons", ["Mean difference", f"{conf:.0%} CI of difference", "Significant?",
                                        "Significance", "Adjusted P"],
                        [(f"{METHODS[method]}: {COMPARE[compare].lower()}", [], "section")] + crow)
        cp.first_column = "Comparison"
        pages.append(cp)
    res.pages = pages
    res.fit = fit
    res.families = fams
    return res


def _mixed_result(t, rows, cols, p, design, fit, compare, method, conf, row_f, col_f,
                  row_names, col_names) -> AnalysisResult:
    """Result pages for the mixed-effects model (Prism's layout of information, our wording)."""
    f, tb, data = fit["mm"], fit["table"], fit["data"]
    src = [(row_f, tb["rows"]), (col_f, tb["cols"]), (f"{row_f} × {col_f}", tb["inter"])]
    rows_out: list[tuple[str, list[str], str]] = [
        ("Data table", [t.name], "row"), ("Design", [DESIGNS[design]], "row"),
        ("Method", ["Mixed-effects model (REML, compound symmetry)"], "row"),
        ("Why", ["Values are missing" if not data["complete"] else "Chosen in the settings"], "row"),
        ("", [], "blank"), ("Fixed effects (type III)", [], "section")]
    for name, s in src:
        rows_out += [(name, [], "section"),
                     ("F", [f"{s['F']:.4g} ({fmt_df(s['dfn'])}, {fmt_df(s['dfd'])})"], "row"),
                     ("P value", [fmt_p(s["p"])], "row"), ("Significance", [p_summary(s["p"])], "row"),
                     ("Significant at α = 0.05", ["Yes" if s["p"] < 0.05 else "No"], "row"),
                     ("", [], "blank")]
    if design in ("rm_rows", "rm_cols"):
        rows_out.append(("Geisser-Greenhouse ε", [f"{fit['eps']:.4f}"], "row"))
        rows_out.append(("Correction applied", ["Geisser-Greenhouse" if fit["gg"] else
                                                "None (sphericity assumed)"], "row"))
        rows_out.append(("", [], "blank"))
    rows_out.append(("Random effects", [], "section"))
    for name, v in fit["random"]:
        rows_out.append((f"{name}: SD", [fmt(math.sqrt(v)) if v >= 0 else "(negative variance)"], "row"))
        rows_out.append((f"{name}: variance", [fmt(v)], "row"))
    rows_out.append(("Residual: SD", [fmt(math.sqrt(f.sigma2))], "row"))
    rows_out.append(("Residual: variance", [fmt(f.sigma2)], "row"))
    chi, dfc, pc = f.lrt()
    rows_out += [("", [], "blank"), ("Was the matching effective?", [], "section"),
                 ("χ² (likelihood ratio)", [f"{chi:.4g}"], "row"), ("Degrees of freedom", [str(dfc)], "row"),
                 ("P value", [fmt_p(pc)], "row"),
                 ("Matching effective at α = 0.05", ["Yes" if pc < 0.05 else "No"], "row"),
                 ("", [], "blank"), ("Data summary", [], "section"),
                 ("Subjects", [str(data["subjects"])], "row"),
                 ("Values analysed", [str(len(data["y"]))], "row"),
                 ("Missing values", [str(data["missing"])], "row"),
                 ("REML log-likelihood", [f"{f.loglik:.4f}"], "row")]
    res = AnalysisResult()
    res.p = src[-1][1]["p"]
    pages = [ResultPage("Results", ["Mixed-effects analysis"], rows_out)]
    trows = [(name, [f"{s['F']:.4g}", fmt_df(s["dfn"]), fmt_df(s["dfd"]), fmt_p(s["p"])], "row")
             for name, s in src]
    pages.append(ResultPage("Fixed effects", ["F", "DFn", "DFd", "P"], trows))
    fams = comparisons(design, fit, compare, method, conf, row_names, col_names)
    if fams:
        crow = []
        for fam, results, pairs in fams:
            crow.append((fam, [], "section"))
            for r_, (a, b) in zip(results, pairs):
                ci = f"{fmt(r_['ci'][0])} to {fmt(r_['ci'][1])}" if r_["ci"] else ""
                crow.append((r_["label"], [fmt(r_["diff"]), ci, "Yes" if r_["p"] < 0.05 else "No",
                                           p_summary(r_["p"]), fmt_p(r_["p"])], "row"))
                if a[0] >= 0 and a[1] >= 0:
                    res.cell_comparisons.append(((rows[a[0]], cols[a[1]]), (rows[b[0]], cols[b[1]]),
                                                 r_["p"]))
        cp = ResultPage("Comparisons", ["Mean difference", f"{conf:.0%} CI of difference", "Significant?",
                                        "Significance", "Adjusted P"],
                        [(f"{METHODS[method]}: {COMPARE[compare].lower()}", [], "section")] + crow)
        cp.first_column = "Comparison"
        pages.append(cp)
    res.pages = pages
    res.fit = fit
    res.families = fams
    return res
