"""QuantStudio qPCR exports (.xls / .xlsx / .txt): the Results table → ΔCt, ΔΔCt and
relative expression, with every setting visible (SPEC §11).

The Results sheet has a preamble of run settings, then a table (Well, Well Position,
Omit, Sample Name, Target Name, Task, Reporter, …, CT, Ct Mean, …), then a footer with
the endogenous control and the reference sample QuantStudio used. Ct "Undetermined" is a
missing value; NTC wells and omitted wells are left out (and counted in the notes).

Relative expression: for each biological sample, technical replicates are averaged
(mean Ct per sample and target); ΔCt = Ct(target) − Ct(reference gene) (the mean of the
reference genes' Ct when there are several); ΔΔCt = ΔCt − the control's ΔCt — the mean
over the samples of a control group (default), or one reference sample, as QuantStudio
does; relative expression = 2^−ΔΔCt.
"""

from __future__ import annotations

import math
import re
from collections import OrderedDict

from .sheets import is_blank, number, text

HOUSEKEEPING = ("gapdh", "actb", "b-act", "bact", "beta-actin", "β-actin", "b-actin", "actin", "18s", "hprt",
                "hprt1", "tbp", "rplp0", "rpl13a", "ppia", "b2m", "ywhaz", "ubc", "sdha", "pgk1", "gusb")


def _norm(h) -> str:
    return re.sub(r"[^a-z]", "", text(h).lower().replace("т", "t"))


def _cols(header: list) -> dict | None:
    n = [_norm(h) for h in header]
    def find(*names):
        return next((i for i, h in enumerate(n) if h in names), None)
    c = {"well": find("well"), "sample": find("samplename", "sample"), "target": find("targetname", "target"),
         "ct": find("ct", "cq", "crt"), "task": find("task"), "omit": find("omit"),
         "position": find("wellposition"), "quantity": find("quantity")}
    if c["sample"] is None or c["target"] is None or c["ct"] is None:
        return None
    return c


def find_results(sheets: dict[str, list[list]]) -> tuple[str, int] | None:
    """(sheet, header row) of a QuantStudio results table, or None."""
    order = sorted(sheets, key=lambda s: (0 if s.lower() == "results" else 1, s))
    for name in order:
        for i, row in enumerate(sheets[name][:80]):
            if _cols(row) is not None and any(_norm(h) == "well" for h in row):
                return name, i
    return None


def footer(sheets) -> dict:
    """The run's own settings from the footer: endogenous control, reference sample."""
    found = find_results(sheets)
    out = {}
    if found is None:
        return out
    name, hr = found
    for row in sheets[name][hr + 1:]:
        if len(row) >= 2 and isinstance(row[0], str):
            k = row[0].strip().lower()
            if k == "endogenous control":
                out["reference_gene"] = text(row[1])
            elif k in ("reference sample", "reference biogroup name") and not is_blank(row[1]):
                out["reference_sample"] = text(row[1])
    return out


def parse(sheets) -> tuple[list[dict], list[str]]:
    """Wells: {sample, target, ct (None if undetermined), task}; notes on what was left out."""
    found = find_results(sheets)
    if found is None:
        raise ValueError("No QuantStudio results table found.")
    name, hr = found
    rows = sheets[name]
    c = _cols(rows[hr])
    wells, notes = [], []
    undet = omitted = ntc = 0
    for r in rows[hr + 1:]:
        if c["well"] is not None and (c["well"] >= len(r) or is_blank(r[c["well"]])):
            if wells:
                break                                     # the footer starts after a blank row
            continue
        get = lambda k: r[c[k]] if c[k] is not None and c[k] < len(r) else None
        sample, target = text(get("sample")), text(get("target"))
        if not sample or not target:
            continue
        task = text(get("task")).upper()
        om = get("omit")
        if om not in (None, "", 0, 0.0, False) and text(om).lower() not in ("false", "0", "no"):
            omitted += 1
            continue
        if task in ("NTC", "NEGATIVE CONTROL"):
            ntc += 1
            continue
        ct = number(get("ct"))
        if ct is None:
            undet += 1
        wells.append({"sample": sample, "target": target, "ct": ct, "task": task,
                      "quantity": number(get("quantity")) if c["quantity"] is not None else None})
    if ntc:
        notes.append(f"{ntc} no-template control well{'s' if ntc != 1 else ''} (NTC) left out.")
    if omitted:
        notes.append(f"{omitted} omitted well{'s' if omitted != 1 else ''} left out.")
    if undet:
        notes.append(f"{undet} well{'s' if undet != 1 else ''} with undetermined Ct treated as missing.")
    return wells, notes


def group_of(sample: str) -> str:
    """'Control 1' → 'Control', 'gRNA3_2' → 'gRNA3' (a trailing replicate number goes)."""
    g = re.sub(r"[\s_\-.]*#?\d+$", "", sample).strip()
    return g or sample


def has_standards(sheets) -> bool:
    try:
        wells, _ = parse(sheets)
    except ValueError:
        return False
    return any(w["task"] == "STANDARD" and w["quantity"] for w in wells)


def defaults(sheets) -> dict:
    """Choices for the settings panel: targets, samples, groups, and first guesses."""
    wells, _ = parse(sheets)
    wells = [w for w in wells if w["task"] != "STANDARD"]
    targets = list(OrderedDict.fromkeys(w["target"] for w in wells))
    samples = list(OrderedDict.fromkeys(w["sample"] for w in wells))
    groups = OrderedDict((s, group_of(s)) for s in samples)
    foot = footer(sheets)
    ref = foot.get("reference_gene")
    if ref not in targets:
        ref = next((t for t in targets if t.lower() in HOUSEKEEPING), None)   # no name match: the user chooses
    glist = list(OrderedDict.fromkeys(groups.values()))
    ctrl = next((g for g in glist if any(k in g.lower() for k in ("control", "ctrl", "wt", "vehicle", "egfp",
                                                                  "scramble", "sham"))), glist[0] if glist else None)
    return {"targets": targets, "samples": samples, "groups": dict(groups), "reference_genes": [ref] if ref else [],
            "control_group": ctrl, "relative_to": "group", "reference_sample": foot.get("reference_sample"),
            "group_list": glist}


def compute(sheets, settings: dict) -> dict:
    """Per sample: mean Ct by target, ΔCt and relative expression for each target of interest."""
    wells, notes = parse(sheets)
    wells = [w for w in wells if w["task"] != "STANDARD"]
    d = defaults(sheets)
    s = {**d, **{k: v for k, v in settings.items() if v is not None}}
    refs = [r for r in s["reference_genes"] if r in d["targets"]]
    if not refs:
        raise ValueError("Choose a reference gene (endogenous control).")
    groups = {**d["groups"], **(s.get("groups") or {})}
    ct: "OrderedDict[tuple, list]" = OrderedDict()
    for w in wells:
        ct.setdefault((w["sample"], w["target"]), [])
        if w["ct"] is not None:
            ct[(w["sample"], w["target"])].append(w["ct"])
    mean_ct = {k: (sum(v) / len(v) if v else None) for k, v in ct.items()}
    samples = [x for x in d["samples"] if groups.get(x)]
    targets = [t for t in d["targets"] if t not in refs]
    dct: dict = {}
    for smp in samples:
        rv = [mean_ct.get((smp, r)) for r in refs]
        if any(v is None for v in rv):
            continue
        ref_ct = sum(rv) / len(rv)
        for t in targets:
            v = mean_ct.get((smp, t))
            if v is not None:
                dct[(smp, t)] = v - ref_ct
    rel, ddct = {}, {}
    for t in targets:
        if s.get("relative_to") == "sample" and s.get("reference_sample"):
            base = dct.get((s["reference_sample"], t))
        else:
            vals = [dct[(x, t)] for x in samples if groups.get(x) == s["control_group"] and (x, t) in dct]
            base = sum(vals) / len(vals) if vals else None
        if base is None:
            continue
        for x in samples:
            if (x, t) in dct:
                ddct[(x, t)] = dct[(x, t)] - base
                rel[(x, t)] = 2.0 ** (-ddct[(x, t)])
    basis = (f"reference sample {s['reference_sample']}" if s.get("relative_to") == "sample"
             else f"mean of the {s['control_group']} group")
    notes.append(f"Reference gene{'s' if len(refs) > 1 else ''}: {', '.join(refs)}; relative to the {basis}; "
                 f"technical replicates averaged.")
    return {"samples": samples, "targets": targets, "groups": groups, "mean_ct": mean_ct, "dct": dct,
            "ddct": ddct, "rel": rel, "notes": notes, "all_targets": d["targets"]}


def build_tables(sheets, layout: str, settings: dict):
    """→ (tables, notes) for a layout: qpcr_rel, qpcr_dct or qpcr_ct."""
    from ..doc.model import Table
    res = compute(sheets, settings)
    groups = res["groups"]
    glist = list(OrderedDict.fromkeys(groups[x] for x in res["samples"]))
    tables = []
    if layout == "qpcr_ct":
        tg = res["all_targets"]
        t = Table("Mean Ct", "grouped", ncols=len(tg))
        t.titles[:len(tg)] = tg
        for i, smp in enumerate(res["samples"]):
            t.set(i, "row", smp, emit=False)
            for j, target in enumerate(tg):
                v = res["mean_ct"].get((smp, target))
                if v is not None:
                    t.set(i, t.flat(j), v, emit=False)
        t.axis_titles = (None, "Ct")
        return [t], res["notes"]
    key, what = ("rel", "relative expression") if layout == "qpcr_rel" else ("dct", "ΔCt")
    for target in res["targets"]:
        t = Table(f"{target} {what}", "column", ncols=len(glist))
        t.axis_titles = (None, f"{target} relative expression (2^−ΔΔCt)" if key == "rel" else f"{target} ΔCt")
        t.titles[:len(glist)] = glist
        fill = {g: 0 for g in glist}
        for smp in res["samples"]:
            v = res[key].get((smp, target))
            if v is None or (isinstance(v, float) and math.isnan(v)):
                continue
            g = groups[smp]
            t.set(fill[g], t.flat(glist.index(g)), v, emit=False)
            fill[g] += 1
        tables.append(t)
    return tables, res["notes"]


# ---------------------------------------------------------------------------
# Standard curves (absolute quantification, e.g. AAV titres)
# ---------------------------------------------------------------------------

def standard_curves(sheets) -> dict:
    """Per target: the fit of Cq against log10(quantity) over the standard wells —
    slope, intercept, R², efficiency = (10^(−1/slope) − 1) × 100 % — and the points."""
    import numpy as np
    wells, _ = parse(sheets)
    out = OrderedDict()
    for target in OrderedDict.fromkeys(w["target"] for w in wells if w["task"] == "STANDARD"):
        pts = [(w["quantity"], w["ct"]) for w in wells
               if w["task"] == "STANDARD" and w["target"] == target and w["quantity"] and w["ct"] is not None
               and w["quantity"] > 0]
        if len(pts) < 2:
            continue
        x = np.log10([q for q, _ in pts])
        y = np.array([c for _, c in pts])
        slope, intercept = np.polyfit(x, y, 1)
        r2 = float(np.corrcoef(x, y)[0, 1] ** 2) if len(set(x)) > 1 else float("nan")
        eff = (10 ** (-1.0 / slope) - 1.0) * 100.0 if slope else float("nan")
        out[target] = {"slope": float(slope), "intercept": float(intercept), "r2": r2, "efficiency": eff,
                       "points": pts, "range": (min(q for q, _ in pts), max(q for q, _ in pts))}
    return out


def quantify(sheets, settings: dict | None = None) -> dict:
    """Quantity of every unknown well from its target's standard curve, converted as asked:
    × dilution factor, × 2 for single-stranded genomes against a double-stranded standard,
    ÷ template volume (µL) for a concentration per µL (× 1000 per mL)."""
    s = {"dilution": 1.0, "volume_ul": 0.0, "per": "reaction", "single_stranded": False, **(settings or {})}
    curves = standard_curves(sheets)
    wells, notes = parse(sheets)
    factor = float(s["dilution"] or 1.0) * (2.0 if s["single_stranded"] else 1.0)
    unit = "copies per reaction"
    if s["per"] in ("ul", "ml") and float(s["volume_ul"] or 0) > 0:
        factor /= float(s["volume_ul"])
        unit = "copies per µL"
        if s["per"] == "ml":
            factor *= 1000.0
            unit = "copies per mL"
    q: "OrderedDict[tuple, list]" = OrderedDict()
    outside = 0
    for w in wells:
        if w["task"] == "STANDARD" or w["target"] not in curves or w["ct"] is None:
            continue
        cv = curves[w["target"]]
        qty = 10 ** ((w["ct"] - cv["intercept"]) / cv["slope"])
        lo, hi = cv["range"]
        if not (lo <= qty <= hi):
            outside += 1
        q.setdefault((w["sample"], w["target"]), []).append(qty * factor)
    for t, cv in curves.items():
        notes.append(f"{t}: slope {cv['slope']:.4g}, intercept {cv['intercept']:.4g}, R² {cv['r2']:.4f}, "
                     f"efficiency {cv['efficiency']:.1f}% (from {len(cv['points'])} standard wells).")
    if outside:
        notes.append(f"{outside} unknown well{'s' if outside != 1 else ''} outside the standards' range "
                     "(extrapolated — check).")
    conv = []
    if float(s["dilution"] or 1) != 1:
        conv.append(f"× dilution {float(s['dilution']):g}")
    if s["single_stranded"]:
        conv.append("× 2 (single-stranded genomes)")
    if unit != "copies per reaction":
        conv.append(f"÷ {float(s['volume_ul']):g} µL template")
    notes.append(f"Quantities in {unit}" + (f" ({', '.join(conv)})" if conv else "") + "; technical replicates "
                 "side by side.")
    return {"curves": curves, "quantities": q, "unit": unit, "notes": notes,
            "samples": list(OrderedDict.fromkeys(k[0] for k in q)), "targets": list(curves)}


def build_standard_tables(sheets, layout: str, settings: dict):
    """qpcr_std: one XY table per target (X = log10 quantity, Y = Cq of each standard well, with a
    linear regression attached); qpcr_qty: samples × targets, technical replicates side by side."""
    import math
    from ..doc.model import Table
    res = quantify(sheets, settings)
    if layout == "qpcr_std":
        from ..doc.spec import PALETTE
        tables = []
        wells, _ = parse(sheets)
        for target, cv in res["curves"].items():
            levels = OrderedDict()
            for qty, ct in cv["points"]:
                levels.setdefault(qty, []).append(ct)
            # the unknowns, where they land on the curve: one data set per sample, every well
            unknown = OrderedDict()
            for w in wells:
                if w["task"] != "STANDARD" and w["target"] == target and w["ct"] is not None:
                    q = 10 ** ((w["ct"] - cv["intercept"]) / cv["slope"])
                    unknown.setdefault(w["sample"], []).append((math.log10(q), w["ct"]))
            width = max(len(v) for v in levels.values())
            t = Table(f"{target} standard curve", "xy", y_format="replicates" if width > 1 else "single",
                      replicates=width, ncols=1 + len(unknown))
            t.titles[0] = f"{target} standards"
            i = 0
            for qty, cts in sorted(levels.items(), key=lambda kv: -kv[0]):
                t.set(i, "x", math.log10(qty), emit=False)
                for k, ct in enumerate(cts):
                    t.set(i, t.flat(0, k), ct, emit=False)
                i += 1
            styles = {0: {"symbol_shape": "circle", "symbol_color": "#000000"}}
            for ds, (smp, pts) in enumerate(unknown.items(), start=1):
                t.titles[ds] = smp
                for lq, ct in pts:
                    t.set(i, "x", lq, emit=False)
                    t.set(i, t.flat(ds, 0), ct, emit=False)
                    i += 1
                styles[ds] = {"symbol_shape": "cross", "symbol_size": 4, "errors": False,
                              "symbol_color": PALETTE[ds % (len(PALETTE) - 1) or 1][1], "xy_show": "replicates"}
            t.import_analyses = [("linreg", [0], {})]                # the fit uses the standards only
            t.dataset_styles = styles
            t.graph_options = {"show_legend": bool(unknown)}
            t.axis_titles = ("Copies per reaction (log scale)", "Cq")   # in the well: no dilution here
            t.axis_formats = {"x": {"fmt": "antilog"}}         # X holds log10(quantity): label it 10⁵ … 10⁹
            tables.append(t)
        return tables, res["notes"]
    q = res["quantities"]
    width = max([len(v) for v in q.values()] + [1])
    targets, samples = res["targets"], res["samples"]
    t = Table("Quantities" if res["unit"] == "copies per reaction" else "Titres", "grouped",
              y_format="replicates" if width > 1 else "single", replicates=width, ncols=len(targets))
    t.titles[:len(targets)] = targets
    t.axis_titles = (None, res["unit"][0].upper() + res["unit"][1:])
    t.axis_formats = {"y": {"fmt": "power", "scale": "log10"}}  # 3×10¹³ on a log axis: titres span decades
    for i, smp in enumerate(samples):
        t.set(i, "row", smp, emit=False)
        for j, target in enumerate(targets):
            for k, v in enumerate(q.get((smp, target), [])):
                t.set(i, t.flat(j, k), v, emit=False)
    return [t], res["notes"]
