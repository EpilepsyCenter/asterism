"""Stats core — execute the detected design (SPEC §8, §10, §11).

Seeded from the GliaAnalysis reference (`glia/stats.py`, SPEC §12): pingouin for
t-tests / ANOVA / post-hocs / effect sizes / normality, scipy for KS, and the
subject-mean aggregation as the default unit of analysis (SPEC §3). Adds the layer
Glia lacks — dispatch keyed on the auto-detected design, and the export artifacts
(§10): a results string and an info block.

Design principles carried over from Glia:
  * aggregate to subject means before testing (no pseudoreplication);
  * every executor is wrapped so a failure returns a StatResult with `error` set
    rather than throwing — a broken metric never takes down the batch;
  * normality / sphericity are advisory diagnostics, never blockers (SPEC §8).

The Welch default (SPEC §8) is surfaced in the results string, because the first
unexplained disagreement with a Prism file costs the project its credibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .contract import SUBJECT, VALUE, Dataset
from .design import DesignResult, detect_design


# ---------------------------------------------------------------------------
# Result object — what the §10 export consumes.
# ---------------------------------------------------------------------------

@dataclass
class StatResult:
    design: str
    test: str
    statistic_name: str = ""
    statistic: float | None = None
    df: tuple | float | None = None
    p: float | None = None
    effect_size: float | None = None
    effect_size_name: str | None = None
    posthoc: list[dict] = field(default_factory=list)
    n_by_level: dict = field(default_factory=dict)
    parametric: bool = True
    corrections: list[str] = field(default_factory=list)
    diagnostics: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    unit_of_analysis: str = "subject means"
    metric: str | None = None
    settings: dict = field(default_factory=dict)
    error: str | None = None

    # --- §10.3 results string ----------------------------------------------

    def results_string(self) -> str:
        if self.error:
            return f"({self.test}: {self.error})"
        parts: list[str] = []
        stat = self.statistic_name
        if stat and self.statistic is not None:
            if self.df is None:
                parts.append(f"{stat} = {_fmt(self.statistic)}")
            elif isinstance(self.df, tuple):
                d = ", ".join(_fmt_df(x) for x in self.df)
                parts.append(f"{stat}({d}) = {_fmt(self.statistic)}")
            else:
                parts.append(f"{stat}({_fmt_df(self.df)}) = {_fmt(self.statistic)}")
        if self.p is not None:
            parts.append(_fmt_p(self.p))
        tail = self.test
        if self.corrections:
            tail += f" ({', '.join(self.corrections)})"
        parts.append(tail)
        if self.effect_size is not None and self.effect_size_name:
            parts.append(f"{self.effect_size_name} = {_fmt(self.effect_size)}")
        return ", ".join(parts)

    # --- §10.4 info block ---------------------------------------------------

    def info_block(self) -> dict:
        return {
            "metric": self.metric,
            "design": self.design,
            "test": self.test,
            "parametric": self.parametric,
            "unit_of_analysis": self.unit_of_analysis,
            "n_by_level": self.n_by_level,
            "corrections": self.corrections,
            "diagnostics": self.diagnostics,
            "notes": self.notes,
            "settings": self.settings,
            "results_string": self.results_string(),
            "error": self.error,
        }

    def to_dict(self) -> dict:
        d = self.info_block()
        d.update({
            "statistic_name": self.statistic_name,
            "statistic": self.statistic,
            "df": list(self.df) if isinstance(self.df, tuple) else self.df,
            "p": self.p,
            "effect_size": self.effect_size,
            "effect_size_name": self.effect_size_name,
            "posthoc": self.posthoc,
        })
        return d


# ---------------------------------------------------------------------------
# Formatting helpers.
# ---------------------------------------------------------------------------

def _fmt(x: float | None, sig: int = 3) -> str:
    if x is None or (isinstance(x, float) and (np.isnan(x))):
        return "n/a"
    return f"{x:.{sig}g}"


def _fmt_df(x) -> str:
    xf = float(x)
    return str(int(round(xf))) if abs(xf - round(xf)) < 1e-6 else f"{xf:.2f}"


def _fmt_p(p: float) -> str:
    if p is None or np.isnan(p):
        return "p = n/a"
    if p < 1e-4:
        return "p < 0.0001"
    return f"p = {p:.4g}"


def p_to_stars(p: float | None) -> str:
    if p is None or np.isnan(p):
        return ""
    if p < 1e-3:
        return "***"
    if p < 1e-2:
        return "**"
    if p < 5e-2:
        return "*"
    return "ns"


# ---------------------------------------------------------------------------
# Data prep.
# ---------------------------------------------------------------------------

def subject_frame(ds: Dataset, *, metric: str | None = None,
                  on_subject_means: bool = True) -> pd.DataFrame:
    """The frame the tests run on: one value per subject per factor combo by
    default (SPEC §3). Filters to a single metric if the dataset carries several."""
    frame = ds.frame
    if "metric" in frame.columns:
        metrics = frame["metric"].dropna().unique().tolist()
        if metric is None:
            if len(metrics) > 1:
                raise ValueError(
                    f"Dataset carries {len(metrics)} metrics {metrics}; pass metric=."
                )
            metric = metrics[0] if metrics else None
        frame = frame[frame["metric"] == metric]
    keys = [SUBJECT, *[f for f in ds.factors if f in frame.columns]]
    if on_subject_means and SUBJECT in frame.columns:
        agg = frame.groupby(keys, dropna=False)[VALUE].mean().reset_index()
        return agg
    return frame[[c for c in [*keys, VALUE] if c in frame.columns]].copy()


def _n_by_level(sf: pd.DataFrame, factors: list[str]) -> dict:
    factors = [f for f in factors if f in sf.columns]
    if not factors or SUBJECT not in sf.columns:
        return {"subjects": int(sf[SUBJECT].nunique()) if SUBJECT in sf else len(sf)}
    counts = sf.groupby(factors, dropna=False)[SUBJECT].nunique()
    out = {}
    for idx, v in counts.items():
        key = idx if isinstance(idx, str) else "|".join(str(x) for x in np.atleast_1d(idx))
        out[str(key)] = int(v)
    return out


# ---------------------------------------------------------------------------
# Diagnostics (advisory — SPEC §8).
# ---------------------------------------------------------------------------

def _diagnostics(sf: pd.DataFrame, factor: str | None) -> dict:
    import pingouin as pg
    diag: dict = {}
    try:
        if factor and factor in sf.columns:
            norm = pg.normality(data=sf, dv=VALUE, group=factor)
            diag["normality"] = {
                str(idx): {"W": float(r["W"]), "p": float(r["pval"]),
                           "normal": bool(r["normal"])}
                for idx, r in norm.iterrows()
            }
            lev = pg.homoscedasticity(data=sf, dv=VALUE, group=factor, method="levene")
            diag["homogeneity"] = {"p": float(lev["pval"].iloc[0]),
                                   "equal_var": bool(lev["equal_var"].iloc[0])}
        else:
            norm = pg.normality(sf[VALUE])
            diag["normality"] = {"all": {"W": float(norm["W"].iloc[0]),
                                         "p": float(norm["pval"].iloc[0]),
                                         "normal": bool(norm["normal"].iloc[0])}}
    except Exception as e:  # advisory only — never block
        diag["error"] = str(e)
    return diag


# ---------------------------------------------------------------------------
# Executors.
# ---------------------------------------------------------------------------

def _two_group(sf: pd.DataFrame, factor: str, *, paired: bool,
               parametric: bool) -> StatResult:
    import pingouin as pg
    levels = sorted(sf[factor].dropna().unique().tolist(), key=str)
    a = sf[sf[factor] == levels[0]]
    b = sf[sf[factor] == levels[1]]
    if paired:
        merged = a.merge(b, on=SUBJECT, suffixes=("_a", "_b"))
        x, y = merged[f"{VALUE}_a"], merged[f"{VALUE}_b"]
    else:
        x, y = a[VALUE], b[VALUE]

    if parametric:
        if paired:
            r = pg.ttest(x, y, paired=True)
            test = "paired t-test"
        else:
            r = pg.ttest(x, y, correction=True)  # Welch
            test = "Welch's t-test"
        res = StatResult(
            design="", test=test, statistic_name="t",
            statistic=float(r["T"].iloc[0]), df=float(r["dof"].iloc[0]),
            p=float(r["p_val"].iloc[0]),
            effect_size=float(r["cohen_d"].iloc[0]), effect_size_name="Cohen's d",
            parametric=True,
        )
    else:
        res = _wilcoxon(x, y) if paired else _mann_whitney(x, y)
    res.posthoc = []
    return res


def exact_rank_sum_p(ranks: np.ndarray, n1: int) -> float:
    """Exact two-sided P for the rank sum of the first n1 values, from the permutation
    distribution of the (mid-)ranks: P(|R − E[R]| ≥ |R_obs − E[R]|). Handles ties exactly,
    which is what Prism does (verified on tied golden cases)."""
    r2 = np.rint(np.asarray(ranks, float) * 2).astype(np.int64)      # mid-ranks are halves
    N = len(r2)
    total_max = int(r2.sum())
    dp = np.zeros((n1 + 1, total_max + 1))
    dp[0, 0] = 1.0
    for x in r2:
        dp[1:, x:] = dp[1:, x:] + dp[:-1, :-x if x else None]
    dist = dp[n1]
    obs = int(r2[:n1].sum())
    expected = n1 * (N + 1)                 # E[R] in half-rank units: n1·(N+1)/2 · 2
    sums = np.arange(total_max + 1)
    far = np.abs(sums - expected) >= abs(obs - expected) - 1e-9
    return float(dist[far].sum() / dist.sum())


def _mann_whitney(x, y) -> StatResult:
    """Two-sample Mann–Whitney U, matching Prism.

    Prism computes the EXACT P for modest samples — also when there are ties, from the
    permutation distribution of the mid-ranks (golden-tested on tied lab data) — and the
    normal approximation for large samples. pingouin's `mwu` always uses the
    approximation, which disagreed with Prism ~17× on a small sample (qPCR golden case).
    We report the *minimum* U, the convention Prism prints.
    """
    from scipy import stats
    xv = np.asarray(x, float)
    yv = np.asarray(y, float)
    xv, yv = xv[~np.isnan(xv)], yv[~np.isnan(yv)]
    n1, n2 = len(xv), len(yv)
    combined = np.concatenate([xv, yv])
    has_ties = len(np.unique(combined)) < len(combined)
    use_exact = n1 + n2 <= 100
    u1, p_asym = stats.mannwhitneyu(xv, yv, alternative="two-sided", method="asymptotic")
    if use_exact:
        p = exact_rank_sum_p(stats.rankdata(combined), n1)
        method = "exact"
    else:
        p, method = float(p_asym), "asymptotic"
    u_min = min(u1, n1 * n2 - u1)  # Prism prints the minimum U
    res = StatResult(design="", test="Mann–Whitney U", statistic_name="U",
                     statistic=float(u_min), p=float(p), parametric=False)
    res.settings["mwu_method"] = method
    res.notes.append(f"Mann–Whitney p by {method} method"
                     + (" (exact with ties, from the permutation distribution of mid-ranks)"
                        if has_ties and use_exact else "") + "; matches Prism.")
    return res


def _wilcoxon(x, y) -> StatResult:
    """Paired Wilcoxon signed-rank, exact when no ties/zeros and n modest."""
    from scipy import stats
    xv = np.asarray(x, float)
    yv = np.asarray(y, float)
    d = xv - yv
    d = d[~np.isnan(d)]
    nz = d[d != 0]
    has_ties = len(np.unique(np.abs(nz))) < len(nz)
    use_exact = (not has_ties) and (len(d) == len(nz)) and len(nz) <= 50
    method = "exact" if use_exact else "approx"
    try:
        w, p = stats.wilcoxon(xv, yv, method=method)
    except Exception:
        w, p = stats.wilcoxon(xv, yv)
        method = "approx"
    res = StatResult(design="", test="Wilcoxon signed-rank", statistic_name="W",
                     statistic=float(w), p=float(p), parametric=False)
    res.settings["wilcoxon_method"] = method
    return res


def _one_way(sf: pd.DataFrame, factor: str, *, parametric: bool) -> StatResult:
    import pingouin as pg
    if parametric:
        a = pg.anova(data=sf, dv=VALUE, between=factor, detailed=True)
        src = a[a["Source"] == factor].iloc[0]
        within = a[a["Source"].isin(["Within", "Residual"])].iloc[0]
        res = StatResult(
            design="", test="one-way ANOVA", statistic_name="F",
            statistic=float(src["F"]),
            df=(float(src["DF"]), float(within["DF"])),
            p=float(src["p_unc"]),
            effect_size=float(src.get("np2", np.nan)),
            effect_size_name="ηp²", parametric=True,
        )
        # Tukey post-hoc (SPEC §8).
        try:
            tuk = pg.pairwise_tukey(data=sf, dv=VALUE, between=factor)
            res.posthoc = [
                {"a": str(r["A"]), "b": str(r["B"]),
                 "p": float(r["p_tukey"]), "stars": p_to_stars(float(r["p_tukey"]))}
                for _, r in tuk.iterrows()
            ]
            res.corrections.append("Tukey HSD post-hoc")
        except Exception:
            pass
    else:
        k = pg.kruskal(data=sf, dv=VALUE, between=factor)
        res = StatResult(design="", test="Kruskal–Wallis", statistic_name="H",
                         statistic=float(k["H"].iloc[0]),
                         df=float(k["ddof1"].iloc[0]),
                         p=float(k["p_unc"].iloc[0]), parametric=False)
    return res


def _rm_one_way(sf: pd.DataFrame, factor: str, *, parametric: bool) -> StatResult:
    import pingouin as pg
    if parametric:
        a = pg.rm_anova(data=sf, dv=VALUE, within=factor, subject=SUBJECT,
                        correction=True, detailed=True)
        row = a[a["Source"] == factor].iloc[0]
        p_gg = row.get("p_GG_corr", row["p_unc"])
        res = StatResult(
            design="", test="repeated-measures one-way ANOVA",
            statistic_name="F", statistic=float(row["F"]),
            df=(float(row["DF"]), float(a[a["Source"] == "Error"]["DF"].iloc[0]))
               if (a["Source"] == "Error").any() else float(row["DF"]),
            p=float(p_gg),
            effect_size=float(row.get("ng2", np.nan)), effect_size_name="ηG²",
            parametric=True, corrections=["Geisser–Greenhouse"],
        )
        try:
            ph = pg.pairwise_tests(data=sf, dv=VALUE, within=factor, subject=SUBJECT,
                                   padjust="holm")
            res.posthoc = [
                {"a": str(r["A"]), "b": str(r["B"]),
                 "p": float(r["p_corr"]), "stars": p_to_stars(float(r["p_corr"]))}
                for _, r in ph.iterrows()
            ]
            res.corrections.append("Holm-corrected pairwise")
        except Exception:
            pass
    else:
        f = pg.friedman(data=sf, dv=VALUE, within=factor, subject=SUBJECT)
        stat_col = "Q" if "Q" in f.columns else "W"
        res = StatResult(design="", test="Friedman", statistic_name=stat_col,
                         statistic=float(f[stat_col].iloc[0]),
                         p=float(f["p-unc"].iloc[0]), parametric=False)
    return res


def _two_way(sf: pd.DataFrame, factors: list[str], *, within=None) -> StatResult:
    """Headline = the interaction term (the question a two-way design asks); the
    full ANOVA table (main effects too) is attached in settings for the export."""
    import pingouin as pg
    if within:
        between = [f for f in factors if f != within][0]
        a = pg.mixed_anova(data=sf, dv=VALUE, within=within, between=between,
                           subject=SUBJECT)
        test = "mixed-design two-way ANOVA"
        corr = ["Geisser–Greenhouse (within)"]
        row = (a[a["Source"] == "Interaction"].iloc[0]
               if (a["Source"] == "Interaction").any() else a.iloc[0])
        df1, df2 = float(row["DF1"]), float(row["DF2"])
    else:
        a = pg.anova(data=sf, dv=VALUE, between=list(factors), detailed=True)
        test = "two-way ANOVA"
        corr = []
        inter = " * ".join(factors).replace(" ", "")
        cand = a[a["Source"].astype(str).str.replace(" ", "") == inter]
        row = cand.iloc[0] if not cand.empty else a.iloc[0]
        resid = a[a["Source"].isin(["Residual", "Within"])]
        df1 = float(row["DF"])
        df2 = float(resid["DF"].iloc[0]) if not resid.empty else None
    np2 = float(row["np2"]) if "np2" in a.columns and not pd.isna(row.get("np2")) else None
    res = StatResult(
        design="", test=test, statistic_name="F", statistic=float(row["F"]),
        df=(df1, df2) if df2 is not None else df1,
        p=float(row["p_unc"]),
        effect_size=np2, effect_size_name="ηp²" if np2 is not None else None,
        corrections=corr,
    )
    res.notes.append(f"Headline term: {row['Source']}. Full ANOVA table available.")
    res.settings["anova_table"] = a.round(6).to_dict("records")
    return res


def _regression(ds: Dataset, sf: pd.DataFrame, *, parametric: bool) -> StatResult:
    import pingouin as pg
    x = pd.to_numeric(ds.frame[ds.x], errors="coerce")
    y = pd.to_numeric(ds.frame[VALUE], errors="coerce")
    ok = x.notna() & y.notna()
    x, y = x[ok], y[ok]
    if parametric:
        lr = pg.linear_regression(x, y)
        slope = lr[lr["names"] == "x1"].iloc[0] if "x1" in set(lr["names"]) \
            else lr.iloc[-1]
        r2 = float(lr["r2"].iloc[0])
        corr = pg.corr(x, y, method="pearson")
        res = StatResult(
            design="regression", test="linear regression",
            statistic_name="R²", statistic=r2, df=None,
            p=float(slope["pval"]),
            effect_size=float(corr["r"].iloc[0]), effect_size_name="Pearson r",
            parametric=True,
        )
        res.settings["slope"] = float(slope["coef"])
    else:
        corr = pg.corr(x, y, method="spearman")
        res = StatResult(design="regression", test="Spearman correlation",
                         statistic_name="rho", statistic=float(corr["r"].iloc[0]),
                         p=float(corr["p_val"].iloc[0]), parametric=False)
    return res


def _ks(a: np.ndarray, b: np.ndarray) -> StatResult:
    from scipy import stats
    r = stats.ks_2samp(a, b)
    return StatResult(design="ungrouped", test="two-sample Kolmogorov–Smirnov",
                      statistic_name="D", statistic=float(r.statistic),
                      p=float(r.pvalue), parametric=False)


# ---------------------------------------------------------------------------
# Public entry point.
# ---------------------------------------------------------------------------

def run_analysis(
    ds: Dataset,
    design: DesignResult | None = None,
    *,
    metric: str | None = None,
    parametric: bool | None = None,
    on_subject_means: bool = True,
    ks_samples: tuple[np.ndarray, np.ndarray] | None = None,
) -> StatResult:
    """Execute the design's recommended test and return a StatResult (SPEC §8, §10).

    `design` may be omitted (it is detected). `parametric=None` follows the design's
    recommendation; pass True/False to force the parametric or non-parametric branch
    (this is how the advisory normality flag flips the test — SPEC §8).
    """
    if design is None:
        design = detect_design(ds)

    want_parametric = (
        parametric if parametric is not None
        else (design.recommended_test.parametric if design.recommended_test else True)
    )

    try:
        return _dispatch(ds, design, metric=metric, parametric=want_parametric,
                         on_subject_means=on_subject_means, ks_samples=ks_samples)
    except Exception as e:  # graceful degradation (glia pattern)
        return StatResult(
            design=design.design,
            test=(design.recommended_test.name if design.recommended_test else "n/a"),
            metric=metric, error=str(e),
        )


def _dispatch(ds, design, *, metric, parametric, on_subject_means, ks_samples):
    label = design.design

    if label == "regression":
        sf = subject_frame(ds, metric=metric, on_subject_means=False)
        res = _regression(ds, sf, parametric=parametric)
        res.design = label
        res.metric = metric
        res.unit_of_analysis = "raw observations"
        _finish(res, design)
        return res

    if label == "ungrouped":
        if ks_samples is None:
            raise ValueError("KS test needs two explicit samples (ks_samples=).")
        res = _ks(np.asarray(ks_samples[0], float), np.asarray(ks_samples[1], float))
        res.metric = metric
        res.unit_of_analysis = "raw observations"
        _finish(res, design)
        return res

    sf = subject_frame(ds, metric=metric, on_subject_means=on_subject_means)
    res_metric = metric
    factors = [f for f in ds.factors if f in sf.columns]

    if label in ("one_factor_2_unpaired", "one_factor_2_paired"):
        res = _two_group(sf, factors[0], paired=(label == "one_factor_2_paired"),
                         parametric=parametric)
    elif label == "one_factor_multi":
        res = _one_way(sf, factors[0], parametric=parametric)
    elif label == "one_factor_multi_rm":
        res = _rm_one_way(sf, factors[0], parametric=parametric)
    elif label == "two_factor":
        within = next((f.name for f in design.factor_facts if f.subjects_shared), None)
        res = _two_way(sf, factors, within=within)
    else:
        raise ValueError(f"No executor for design '{label}'.")

    res.design = label
    res.metric = res_metric
    res.unit_of_analysis = "subject means" if on_subject_means else "raw observations"
    res.n_by_level = _n_by_level(sf, factors)
    res.diagnostics = _diagnostics(sf, factors[0] if len(factors) == 1 else None)
    _finish(res, design)
    return res


def _finish(res: StatResult, design: DesignResult) -> None:
    """Carry the design's notes (e.g. the Welch caveat) onto the result and settings."""
    if design.recommended_test:
        for n in design.recommended_test.notes:
            if n not in res.notes:
                res.notes.append(n)
    res.settings.setdefault("parametric", res.parametric)
