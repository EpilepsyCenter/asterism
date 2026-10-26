"""Nested t test and nested one-way ANOVA (Nested tables: groups → subjects → replicates).

Model: value = group effect + random subject effect + residual, fitted by REML. The fixed
group effect is tested with "containment" degrees of freedom (number of subjects − number
of groups); with equal replicates per subject this equals the ordinary t test / ANOVA on
the subject means, as Prism notes. The random-effect part reports the variance between
subjects, its share of the total, and a likelihood-ratio test of whether subjects differ.
"""

from __future__ import annotations

import itertools
import math
import warnings

import numpy as np
from scipy import stats as sps

from asterism.doc.model import column_letter

from .anova2 import _adjust
from .results import AnalysisResult, ResultPage, fmt, fmt_p, p_summary


def title(params: dict) -> str:
    return "Nested t test" if params.get("_ncols", 2) == 2 else "Nested one-way ANOVA"


def gather(t, cols: list[int]):
    """(values, group index, subject id) for every included value."""
    y, g, s = [], [], []
    for gi, c in enumerate(cols):
        for sub in range(t.width()):
            f = t.flat(c, sub)
            for r in range(len(t.y[f])):
                v = t.get(r, f)
                if isinstance(v, float) and (r, f) not in t.excluded:
                    y.append(v)
                    g.append(gi)
                    s.append(gi * 10000 + sub)
    return np.array(y), np.array(g), np.array(s)


def fit(y, g, s, k):
    import pandas as pd
    import statsmodels.formula.api as smf
    df = pd.DataFrame({"y": y, "g": pd.Categorical(g, categories=range(k)), "s": s})
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        m = smf.mixedlm("y ~ C(g)", df, groups=df["s"]).fit(reml=True)
        m_ml = smf.mixedlm("y ~ C(g)", df, groups=df["s"]).fit(reml=False)
    import statsmodels.api as sm
    ols = sm.OLS(df["y"].to_numpy(), pd.get_dummies(df["g"], drop_first=True).assign(c=1.0).astype(float).to_numpy()).fit()
    lrt = max(0.0, 2 * (m_ml.llf - ols.llf))
    p_lrt = 0.5 * sps.chi2.sf(lrt, 1) if lrt > 0 else 1.0     # boundary: mixture of χ²₀ and χ²₁
    return m, lrt, p_lrt


def nested(an) -> AnalysisResult:
    ALPHA = float(an.params.get("alpha", 0.05))      # significance level (Settings)
    t, cols, p = an.table, list(an.columns), an.params
    if t.table_type != "nested":
        raise ValueError("Nested analyses work on a Nested table (groups split into subjects).")
    k = len(cols)
    if k < 2:
        raise ValueError("Choose at least two groups.")
    y, g, s = gather(t, cols)
    subjects = np.unique(s)
    S = len(subjects)
    if S - k < 1 or any(len(np.unique(s[g == i])) < 1 for i in range(k)):
        raise ValueError("Each group needs subjects, and there must be more subjects than groups.")
    m, lrt, p_lrt = fit(y, g, s, k)
    fe = m.fe_params.to_numpy()
    cov = m.cov_params().to_numpy()[:k, :k]
    df_fixed = S - k
    means = np.array([fe[0]] + [fe[0] + fe[i] for i in range(1, k)])
    var_subj = float(m.cov_re.iloc[0, 0])
    var_res = float(m.scale)
    labels = [t.label(c) for c in cols]
    letters = [column_letter(c) for c in cols]
    rows: list[tuple[str, list[str], str]] = [
        ("Data table", [t.name], "row"),
        ("Groups", [", ".join(f"{a}: {b}" for a, b in zip(letters, labels))], "row"),
        ("Subjects", [str(S)], "row"), ("Values", [str(len(y))], "row"), ("", [], "blank")]
    res = AnalysisResult()
    if k == 2:
        diff = means[1] - means[0]
        se = math.sqrt(cov[1, 1])
        tv = diff / se
        pv = float(2 * sps.t.sf(abs(tv), df_fixed))
        conf = float(p.get("conf", 0.95))
        tc = sps.t.ppf(0.5 + conf / 2, df_fixed)
        rows += [("Nested t test", [], "section"),
                 ("t", [f"{abs(tv):.4g}"], "row"), ("Degrees of freedom", [str(df_fixed)], "row"),
                 ("P value", [fmt_p(pv)], "row"), ("Significance", [p_summary(pv)], "row"),
                 (f"Significant at α = {ALPHA:g}", ["Yes" if pv < ALPHA else "No"], "row"),
                 ("", [], "blank"), ("Size of the difference", [], "section"),
                 (f"Mean, {letters[0]}", [fmt(means[0])], "row"), (f"Mean, {letters[1]}", [fmt(means[1])], "row"),
                 (f"Difference ({letters[1]} − {letters[0]})", [fmt(diff)], "row"),
                 ("Standard error of the difference", [fmt(se)], "row"),
                 (f"{100 * conf:g}% CI of the difference", [f"{fmt(diff - tc * se)} to {fmt(diff + tc * se)}"], "row")]
        res.p = pv
        res.comparisons = [(cols[0], cols[1], pv)]
        name = "Nested t test"
    else:
        L = np.zeros((k - 1, k))
        L[:, 1:] = np.eye(k - 1)
        beta = fe[:k]
        Lb = L @ beta
        F = float(Lb @ np.linalg.solve(L @ cov @ L.T, Lb) / (k - 1))
        pv = float(sps.f.sf(F, k - 1, df_fixed))
        rows += [("Nested one-way ANOVA", [], "section"),
                 ("F", [f"{F:.4g} ({k - 1}, {df_fixed})"], "row"),
                 ("P value", [fmt_p(pv)], "row"), ("Significance", [p_summary(pv)], "row"),
                 (f"Significant at α = {ALPHA:g}", ["Yes" if pv < ALPHA else "No"], "row")]
        res.p = pv
        name = "Nested one-way ANOVA"
    total = var_subj + var_res
    rows += [("", [], "blank"), ("Variation between subjects", [], "section"),
             ("Variance between subjects", [fmt(var_subj)], "row"),
             ("Residual variance", [fmt(var_res)], "row"),
             ("% of variance between subjects", [f"{100 * var_subj / total:.1f}" if total else ""], "row"),
             ("Likelihood-ratio χ²", [f"{lrt:.4g}"], "row"), ("P value", [fmt_p(p_lrt)], "row"),
             (f"Subjects differ at α = {ALPHA:g}", ["Yes" if p_lrt < ALPHA else "No"], "row")]
    pages = [ResultPage("Results", [name], rows)]
    if k > 2 and p.get("compare", "all") != "none":
        method = p.get("method", "tukey")
        raw = []
        pairs = list(itertools.combinations(range(k), 2))
        for i, j in pairs:
            # group 0 is the intercept; the others are offsets from it
            var = cov[j, j] if i == 0 else cov[i, i] + cov[j, j] - 2 * cov[i, j]
            se = math.sqrt(max(var, 0.0))
            raw.append((f"{letters[i]}: {labels[i]}  vs.  {letters[j]}: {labels[j]}",
                        means[i] - means[j], se, df_fixed))
        comps = _adjust(raw, method, k, p.get("conf", 0.95))
        crow = []
        for c_, (i, j) in zip(comps, pairs):
            ci = f"{fmt(c_['ci'][0])} to {fmt(c_['ci'][1])}" if c_["ci"] else ""
            crow.append((c_["label"], [fmt(c_["diff"]), ci, "Yes" if c_["p"] < ALPHA else "No",
                                       p_summary(c_["p"]), fmt_p(c_["p"])], "row"))
            res.comparisons.append((cols[i], cols[j], c_["p"]))
        cp = ResultPage("Comparisons", ["Mean difference", f"{100 * p.get('conf', 0.95):g}% CI of difference", "Significant?",
                                        "Significance", "Adjusted P"], crow)
        cp.first_column = "Comparison"
        pages.append(cp)
    res.pages = pages
    return res
