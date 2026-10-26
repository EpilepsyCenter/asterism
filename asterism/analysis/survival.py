"""Survival analysis (Prism's functions, our wording).

Table: X = time; each data set (group) holds an event code per subject — 1 = the event
happened, 0 = censored (other codes can be chosen) — one subject per row.

- Kaplan-Meier product-limit estimate, Greenwood standard errors.
- Confidence intervals of the fraction surviving: the log-log transform ("exponential
  Greenwood", Prism's default; = R survfit conf.type = "log-log"), or symmetric ±z·SE
  clipped to 0–1 (Prism's legacy choice).
- Median survival: first time the curve reaches 50% or below (the midpoint of a flat
  stretch at exactly 50%); its interval from the log-log bands (Prism 10.5+).
- Comparing curves: log-rank (Mantel-Cox; k − 1 df with the full covariance, as SAS/SPSS
  and Prism's recommended setting), Gehan-Breslow-Wilcoxon (weights = number at risk),
  log-rank test for trend (3+ groups, equally spaced).
- Two groups: hazard ratio by the Mantel-Haenszel and log-rank methods, ratio of median
  survival times with an interval assuming exponential survival.
"""

from __future__ import annotations

import math

import numpy as np
from scipy import stats as sps

from .results import AnalysisResult, ResultPage, fmt, fmt_p, p_summary


def subjects(t, c: int, event=1, censor=0) -> tuple[np.ndarray, np.ndarray]:
    times, events = [], []
    for r in range(t.nrows_used()):
        x = t.x_value(r)
        v = t._ok(r, t.flat(c))
        if x is None or v is None:
            continue
        if v == event:
            times.append(x)
            events.append(1)
        elif v == censor:
            times.append(x)
            events.append(0)
    return np.array(times, float), np.array(events, int)


def km(times: np.ndarray, events: np.ndarray, conf: float = 0.95, ci: str = "loglog") -> dict:
    """Kaplan-Meier at each distinct time with an event (and each censoring time)."""
    order = np.argsort(times, kind="stable")
    t, e = times[order], events[order]
    n = len(t)
    uniq = np.unique(t)
    z = float(sps.norm.ppf(1 - (1 - conf) / 2))
    S, gw = 1.0, 0.0
    rows = []
    at_risk = n
    for u in uniq:
        here = t == u
        d = int(e[here].sum())
        c = int(here.sum() - d)
        if d:
            S *= (at_risk - d) / at_risk
            gw += d / (at_risk * (at_risk - d)) if at_risk > d else math.inf
        se = S * math.sqrt(gw) if math.isfinite(gw) else 0.0
        if S <= 0 or not math.isfinite(gw):
            lo, hi = math.nan, math.nan          # undefined once everyone has had the event
        elif gw == 0:
            lo, hi = 1.0, 1.0
        elif ci == "symmetric":
            lo, hi = max(0.0, S - z * se), min(1.0, S + z * se)
        else:
            if S >= 1:
                lo, hi = 1.0, 1.0
            else:
                k = z * math.sqrt(gw) / abs(math.log(S))
                lo, hi = S ** math.exp(k), S ** math.exp(-k)
        rows.append({"time": float(u), "at_risk": at_risk, "events": d, "censored": c, "S": S, "se": se,
                     "lo": lo, "hi": hi})
        at_risk -= int(here.sum())
    return {"rows": rows, "n": n, "events": int(e.sum())}


def median_survival(curve: dict, key: str = "S") -> float | None:
    """First time the curve is at or below 50%; the midpoint of a flat stretch at exactly
    50% (Prism's and R's rule). None if the curve stays above 50%."""
    rows = [r for r in curve["rows"] if r["events"] > 0 or key != "S"]
    rs = curve["rows"]
    for i, r in enumerate(rs):
        if r[key] <= 0.5 + 1e-12:
            if abs(r[key] - 0.5) < 1e-12 and key == "S":
                nxt = next((q for q in rs[i + 1:] if q[key] < 0.5 - 1e-12), None)
                if nxt is not None:
                    return (r["time"] + nxt["time"]) / 2
            return r["time"]
    return None


def median_ci(curve: dict) -> tuple[float | None, float | None]:
    """From the confidence bands (as R's survfit): the lower limit is the first time the
    lower band reaches 50%, the upper limit the first time the upper band does."""
    lo = next((r["time"] for r in curve["rows"] if r["lo"] <= 0.5 + 1e-12), None)
    hi = next((r["time"] for r in curve["rows"] if r["hi"] <= 0.5 + 1e-12), None)
    return lo, hi


def weighted_logrank(groups: list[tuple[np.ndarray, np.ndarray]], weight: str = "logrank") -> dict:
    """O − E, its covariance, and the k − 1 df chi-square. weight: logrank (1) or gehan
    (number at risk)."""
    k = len(groups)
    allt = np.concatenate([g[0] for g in groups])
    alle = np.concatenate([g[1] for g in groups])
    gid = np.concatenate([np.full(len(g[0]), i) for i, g in enumerate(groups)])
    ev_times = np.unique(allt[alle == 1])
    O = np.zeros(k)
    E = np.zeros(k)
    V = np.zeros((k, k))
    Ow, Ew = np.zeros(k), np.zeros(k)
    for u in ev_times:
        risk = allt >= u
        n_j = np.array([np.sum(risk & (gid == i)) for i in range(k)], float)
        d_j = np.array([np.sum((allt == u) & (alle == 1) & (gid == i)) for i in range(k)], float)
        n, d = n_j.sum(), d_j.sum()
        w = n if weight == "gehan" else 1.0
        e_j = d * n_j / n
        O += d_j
        E += e_j
        Ow += w * d_j
        Ew += w * e_j
        if n > 1:
            f = d * (n - d) / (n - 1)
            V += w * w * f * (np.diag(n_j / n) - np.outer(n_j, n_j) / (n * n))
    U = Ow - Ew
    idx = list(range(k - 1))
    Vr = V[np.ix_(idx, idx)]
    try:
        chi = float(U[idx] @ np.linalg.solve(Vr, U[idx]))
    except np.linalg.LinAlgError:
        chi = math.nan
    return {"O": O, "E": E, "U": U, "V": V, "chi2": chi, "df": k - 1,
            "p": float(sps.chi2.sf(chi, k - 1)) if math.isfinite(chi) else math.nan}


def logrank_trend(lr: dict, scores=None) -> dict:
    k = len(lr["O"])
    s = np.arange(1, k + 1, dtype=float) if scores is None else np.asarray(scores, float)
    num = float(s @ lr["U"]) ** 2
    den = float(s @ lr["V"] @ s)
    chi = num / den if den > 0 else math.nan
    return {"chi2": chi, "df": 1, "p": float(sps.chi2.sf(chi, 1))}


def hazard_ratios(lr: dict, conf: float = 0.95) -> dict:
    """Group 1 relative to group 2."""
    z = float(sps.norm.ppf(1 - (1 - conf) / 2))
    O, E, V = lr["O"], lr["E"], lr["V"]
    out = {}
    if E[0] > 0 and E[1] > 0 and O[1] > 0:
        hr = (O[0] / E[0]) / (O[1] / E[1])
        se = math.sqrt(1 / E[0] + 1 / E[1])
        out["logrank"] = (hr, hr * math.exp(-z * se), hr * math.exp(z * se))
    if V[0, 0] > 0:
        L = (O[0] - E[0]) / V[0, 0]
        se = 1 / math.sqrt(V[0, 0])
        out["mh"] = (math.exp(L), math.exp(L - z * se), math.exp(L + z * se))
    return out


def survival(an) -> AnalysisResult:
    t, cols, p = an.table, list(an.columns), an.params
    if t.table_type != "survival":
        raise ValueError("Survival analysis works on a Survival table (X = time, 1 = event, 0 = censored).")
    conf = p.get("conf", 0.95)
    ci = p.get("ci", "loglog")
    ev, ce = p.get("event_code", 1), p.get("censor_code", 0)
    data = [subjects(t, c, ev, ce) for c in cols]
    keep = [(c, d) for c, d in zip(cols, data) if len(d[0])]
    if not keep:
        raise ValueError("No subjects: enter each subject's time in X and 1 (event) or 0 (censored) in its group.")
    cols = [c for c, _ in keep]
    data = [d for _, d in keep]
    curves = [km(tm, e, conf, ci) for tm, e in data]
    labels = [t.label(c) for c in cols]
    res = AnalysisResult()
    rows: list[tuple[str, list[str], str]] = []
    if len(cols) >= 2:
        lr = weighted_logrank(data, "logrank")
        gb = weighted_logrank(data, "gehan")
        rows += [("Comparison of survival curves", [], "section"),
                 ("Log-rank (Mantel-Cox): chi-square, df", [f"{lr['chi2']:.4g}, {lr['df']}"], "row"),
                 ("P value", [fmt_p(lr["p"])], "row"), ("P value summary", [p_summary(lr["p"])], "row"),
                 ("Curves differ at α = 0.05", ["Yes" if lr["p"] < 0.05 else "No"], "row"),
                 ("", [], "blank"),
                 ("Gehan-Breslow-Wilcoxon: chi-square, df", [f"{gb['chi2']:.4g}, {gb['df']}"], "row"),
                 ("P value", [fmt_p(gb["p"])], "row"), ("P value summary", [p_summary(gb["p"])], "row")]
        res.p = lr["p"]
        if len(cols) >= 3:
            tr = logrank_trend(lr)
            rows += [("", [], "blank"), ("Log-rank test for trend", [], "section"),
                     ("Chi-square, df", [f"{tr['chi2']:.4g}, 1"], "row"), ("P value", [fmt_p(tr["p"])], "row"),
                     ("Note", ["Meaningful only for ordered, equally spaced groups"], "row")]
        if len(cols) == 2:
            hr = hazard_ratios(lr, conf)
            rows += [("", [], "blank"), (f"Hazard ratio ({labels[0]} / {labels[1]})", [], "section")]
            for key, name in (("mh", "Mantel-Haenszel"), ("logrank", "Log-rank")):
                if key in hr:
                    v, lo, hi = hr[key]
                    rows.append((f"{name}: ratio", [fmt(v)], "row"))
                    rows.append((f"{name}: {conf:.0%} CI", [f"{fmt(lo)} to {fmt(hi)}"], "row"))
                    rows.append((f"{name}: reciprocal", [f"{fmt(1 / v)} ({fmt(1 / hi)} to {fmt(1 / lo)})"], "row"))
            m1, m2 = median_survival(curves[0]), median_survival(curves[1])
            if m1 is not None and m2 is not None and m2 > 0:
                z = float(sps.norm.ppf(1 - (1 - conf) / 2))
                O = lr["O"]
                ratio = m1 / m2
                if O[0] > 0 and O[1] > 0:
                    se = math.sqrt(1 / O[0] + 1 / O[1])
                    rci = f"{fmt(ratio * math.exp(-z * se))} to {fmt(ratio * math.exp(z * se))}"
                else:
                    rci = ""
                rows += [("", [], "blank"), ("Ratio of median survival times", [], "section"),
                         (f"{labels[0]} / {labels[1]}", [fmt(ratio)], "row"),
                         (f"{conf:.0%} CI (assuming exponential survival)", [rci], "row")]
        rows.append(("", [], "blank"))
    rows.append(("Median survival", [], "section"))
    for lab, cv in zip(labels, curves):
        m = median_survival(cv)
        lo, hi = median_ci(cv)
        txt = "Undefined (survival stays above 50%)" if m is None else fmt(m)
        ci_txt = "" if m is None else f"{fmt(lo) if lo is not None else '—'} to {fmt(hi) if hi is not None else 'undefined'}"
        rows.append((lab, [txt + (f"  ({conf:.0%} CI {ci_txt})" if ci_txt else "")], "row"))
    rows += [("", [], "blank"), ("Data", [], "section")]
    for lab, cv in zip(labels, curves):
        rows.append((lab, [f"{cv['n']} subjects, {cv['events']} events, {cv['n'] - cv['events']} censored"], "row"))
    pages = [ResultPage("Results", ["Survival"], rows)]
    pct = p.get("percent", True)
    sc = 100.0 if pct else 1.0
    srows = []
    for lab, cv in zip(labels, curves):
        srows.append((lab, [], "section"))
        for r in cv["rows"]:
            srows.append((fmt(r["time"]), [f"{r['S'] * sc:.4g}", f"{r['se'] * sc:.3g}",
                                           f"{r['lo'] * sc:.4g} to {r['hi'] * sc:.4g}", str(r["at_risk"]),
                                           str(r["events"]), str(r["censored"])], "row"))
    sp = ResultPage("Survival proportions", ["Survival (%)" if pct else "Fraction surviving", "SE",
                                             f"{conf:.0%} CI", "At risk", "Events", "Censored"], srows)
    sp.first_column = "Time"
    pages.append(sp)
    res.pages = pages
    res.fit = {"kind": "survival", "curves": dict(zip(cols, curves))}
    return res
