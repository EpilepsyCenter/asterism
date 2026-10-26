"""Lab exports → typed tables (SPEC §11): NED-Net results workbooks, TRACER cohort
exports and QuantStudio qPCR runs.

The recipes in `asterism.core.importer` read each recognised sheet into the long data
contract (value | metric | subject | replicate | factors …); this module lays that out as
ASTERISM tables. The animal (subject) stays the unit of independence: per-animal sheets
give one value per animal, per-cell sheets give nested tables (animals as sub-columns),
and day-by-day sheets give grouped tables with each animal in its own sub-column so
repeated measures line up.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .build import Plan, build_table

LAYOUTS = {
    "per_subject": "Column table: one value per animal",
    "nested": "Nested table: animals side by side, their values below",
    "grouped_x": "Grouped table: rows by day/hour, animals side by side",
    "xy_x": "XY table: X = day/hour, animals as replicates",
    "xy_groups": "XY table: X = bin, one data set per group",
    "qpcr_rel": "Column table: relative expression (2^−ΔΔCt)",
    "qpcr_dct": "Column table: ΔCt",
    "qpcr_ct": "Grouped table: mean Ct by sample and target",
    "qpcr_std": "XY table per target: Cq against log10 quantity, with its regression",
    "qpcr_qty": "Grouped table: quantity of each sample by target, replicates side by side",
}


@dataclass
class LabItem:
    """One table the import can make: a sheet (and metric) with a choice of layouts."""
    key: str
    source: str              # NED-Net | TRACER | QuantStudio
    sheet: str
    title: str
    layouts: list[str]
    layout: str
    kind: str
    metric: str | None = None
    selected: bool = True
    note: str = ""


def detect(sheets: dict[str, list[list]]) -> tuple[str | None, list[LabItem]]:
    """(source name, items) when the workbook is a lab export, else (None, [])."""
    from ..core.importer.sources import NEDNET_DURATION_METRICS, NEDNET_PERANIMAL_METRICS, classify_sheets
    from .quantstudio import find_results
    qs = find_results(sheets)
    if qs is not None:
        from .quantstudio import has_standards
        name, hdr_row = qs
        std = has_standards(sheets)
        items = []
        if std:
            items += [LabItem(f"qpcr:{k}", "QuantStudio", name, t, [k], k, "qpcr")
                      for k, t in (("qpcr_std", "Standard curves"), ("qpcr_qty", "Quantities of the unknowns"))]
        items += [LabItem(f"qpcr:{k}", "QuantStudio", name, t, [k], k, "qpcr", selected=(k == "qpcr_rel" and not std))
                  for k, t in (("qpcr_rel", "Relative expression (2^−ΔΔCt)"), ("qpcr_dct", "ΔCt"),
                               ("qpcr_ct", "Mean Ct by sample and target"))]
        return "QuantStudio", items
    plans = classify_sheets(sheets)
    if not plans:
        return None, []
    items: list[LabItem] = []
    source = "NED-Net" if plans[0].source == "nednet" else "TRACER"
    for p in plans:
        rows = sheets[p.sheet]
        hdr = [str(c) if c is not None else "" for c in rows[0]] if rows else []
        if p.kind == "per_animal":
            for m in NEDNET_PERANIMAL_METRICS + NEDNET_DURATION_METRICS:
                if m in hdr:
                    items.append(LabItem(f"{p.sheet}:{m}", source, p.sheet, f"{m} ({p.sheet})", ["per_subject"],
                                         "per_subject", p.kind, metric=m))
        elif p.kind == "two_row":
            items.append(LabItem(p.sheet, source, p.sheet, p.sheet, ["grouped_x", "xy_x"], "grouped_x", p.kind,
                                 metric=p.metric))
        elif p.kind in ("isi_dist", "isi_cdf"):
            items.append(LabItem(p.sheet, source, p.sheet, p.sheet, ["xy_groups"], "xy_groups", p.kind))
        elif p.kind in ("cells_long", "cells_wide", "events"):
            for m in _tracer_metrics(rows, p):
                items.append(LabItem(f"{p.sheet}:{m}", source, p.sheet, f"{m} ({p.sheet})",
                                     ["nested", "per_subject"], "nested", p.kind, metric=m,
                                     selected=p.kind != "events"))
    return source, items


def _tracer_metrics(rows, plan) -> list[str]:
    from ..core.importer.sources import TRACER_WIDE_PREFIX, header_of
    hdr = header_of(rows)
    if plan.kind == "cells_long":
        j = hdr.index("metric")
        return list(dict.fromkeys(str(r[j]) for r in rows[1:] if j < len(r) and r[j] is not None))
    if plan.kind == "events":
        return [plan.metric or plan.sheet]
    after = hdr[len(TRACER_WIDE_PREFIX):]
    return [c for c in after if c and not c.startswith("meta.")]


def build(item: LabItem, sheets: dict[str, list[list]], settings: dict | None = None):
    """→ (tables, notes) for one item."""
    rows = sheets[item.sheet]
    notes: list[str] = []
    if item.kind == "qpcr":
        from .quantstudio import build_standard_tables, build_tables
        if item.layout in ("qpcr_std", "qpcr_qty"):
            return build_standard_tables(sheets, item.layout, (settings or {}).get("standard", {}))
        return build_tables(sheets, item.layout, settings or {})
    from ..core.importer import sources as S
    if item.kind == "per_animal":
        res = S.import_nednet_per_animal(rows, metrics=[item.metric])
        ds, notes = res.dataset, list(res.notes)
    elif item.kind == "two_row":
        ds = S.import_nednet_two_row(rows, item.metric or item.sheet)
    elif item.kind in ("isi_dist", "isi_cdf"):
        frame = S.parse_nednet_isi(rows, kind=item.kind)
        long = [["x", "group", "value"]] + [[r.x, r.group, r.value] for r in frame.itertuples()]
        t, n2 = build_table(long, Plan("xy", "long", 0, {0: "x", 1: "group", 2: "value"}, name=item.title))
        t.axis_titles = ("Inter-seizure interval (s)", "Fraction" if item.kind == "isi_cdf" else "Count")
        return [t], notes + n2
    elif item.kind == "cells_long":
        ds = S.import_tracer_cells_long(rows)
    elif item.kind == "events":
        ds = S.import_tracer_events(rows, metric=item.metric)
    else:
        ds = S.import_tracer_cells_wide(rows, metrics=[item.metric])
    frame = ds.frame.copy()
    if "subject" in frame.columns:                  # ids read as numbers: 24.0 → "24"
        from .sheets import text as _text
        frame["subject"] = frame["subject"].map(lambda v: _text(v) if v is not None else None)
    notes = [re.sub(r"\b(\d+)\.0\b", r"\1", n) for n in notes]
    if "metric" in frame.columns and item.metric is not None and item.kind != "two_row":
        frame = frame[frame["metric"].astype(str) == str(item.metric)]
    factor = ds.factors[0] if ds.factors else None
    head = ["value", "group", "subject", "x"]
    xcol = ds.x
    recs = frame.to_dict("records")
    if item.kind == "two_row" and len(rows) > 1:            # animals in the sheet's column order
        from .sheets import text as _text
        order = {_text(a): i for i, a in enumerate(rows[1][1:])}
        recs.sort(key=lambda r: order.get(r.get("subject"), 1e9))
    long = [head] + [[r["value"], r[factor] if factor else "All", r.get("subject"), r.get(xcol) if xcol else None]
                     for r in recs]
    name = item.title
    if item.layout == "per_subject":
        plan = Plan("column", "long", 0, {0: "value", 1: "group", 2: "subject"}, name=name,
                    average_subjects=True)
    elif item.layout == "nested":
        plan = Plan("nested", "long", 0, {0: "value", 1: "group", 2: "subject"}, name=name)
    elif item.layout == "xy_x":
        plan = Plan("xy", "long", 0, {0: "value", 1: "group", 2: "subject", 3: "x"}, name=name)
    else:                                                   # grouped_x
        plan = Plan("grouped", "long", 0, {0: "value", 1: "group", 2: "subject", 3: "factor2"}, name=name)
    t, n2 = build_table(long, plan)
    measure = item.metric or item.sheet
    t.axis_titles = ("Day" if item.layout == "xy_x" and "Daily" in item.sheet else
                     "Hour of day" if item.layout == "xy_x" else None, measure.replace("_", " "))
    if item.layout == "per_subject" and item.kind in ("per_animal",):
        n2 = [n for n in n2 if not n.startswith("Values averaged")]
    return [t], notes + [f"{item.title}: {n[0].lower()}{n[1:]}" for n in n2]
