"""Building a data table from spreadsheet rows and a column plan (SPEC §11).

Two layouts:

* **wide** — each chosen column is a data set (columns with the same name become
  replicates of one data set); optional row-title and X columns.
* **long** ("tidy") — one value per row: a value column plus a group column (data sets),
  and optionally a second factor (rows of a grouped table, or X of an XY table) and a
  subject column (sub-columns of a nested table; one sub-column per subject in grouped
  and XY tables, so repeated measures line up; or averaged to one value per subject).

`build_table` returns the table and notes on everything it skipped or guessed.
"""

from __future__ import annotations

import datetime as _dt
import re
from collections import OrderedDict
from dataclasses import dataclass, field

from .sheets import is_blank, number, text

ROLES = {
    "ignore": "Ignore",
    "set": "Data set",
    "row": "Row titles",
    "x": "X values",
    "xerr": "X error",
    "value": "Values",
    "group": "Groups (data sets)",
    "factor2": "Second factor (rows / X)",
    "subject": "Subject (animal)",
    "event": "Event (1) / censored (0)",
}
WIDE_ROLES = ("ignore", "set", "row", "x", "xerr")
LONG_ROLES = ("ignore", "value", "group", "factor2", "subject", "x", "event")


@dataclass
class Plan:
    table_type: str = "column"
    layout: str = "wide"                          # wide | long
    header_row: int = 0                           # -1: no header row
    roles: dict = field(default_factory=dict)     # column index → role
    name: str = "Imported data"
    average_subjects: bool = False                # long: one value per subject (its mean)
    merge_same_names: bool = True                 # wide: same-named columns → one data set


EXCEL_EPOCH = _dt.datetime(1899, 12, 30)


def date_number(v):
    """Days since 1899-12-30 (Excel's day numbers) for a date or datetime, else None."""
    if isinstance(v, _dt.datetime):
        return (v - EXCEL_EPOCH).total_seconds() / 86400.0
    if isinstance(v, _dt.date):
        return float((v - EXCEL_EPOCH.date()).days)
    if isinstance(v, str):
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M"):
            try:
                return date_number(_dt.datetime.strptime(v.strip(), fmt))
            except ValueError:
                continue
    return None


def headers(rows: list[list], header_row: int) -> list[str]:
    width = max((len(r) for r in rows), default=0)
    if header_row < 0 or header_row >= len(rows):
        from ..doc.table import column_letter
        return [f"Column {column_letter(j)}" for j in range(width)]
    h = rows[header_row]
    out = []
    for j in range(width):
        t = text(h[j]) if j < len(h) else ""
        out.append(t or f"Column {j + 1}")
    return out


def body(rows: list[list], header_row: int) -> list[list]:
    data = rows[header_row + 1:] if header_row >= 0 else rows
    return [r for r in data if not all(is_blank(c) for c in r)]


def _base(name: str) -> str:
    """'Control_2', 'Control 2', 'Control.2' → 'Control' (replicate columns)."""
    return re.sub(r"[\s._-]*\(?\d+\)?$", "", name).strip() or name


def guess_plan(rows: list[list], header_row: int | None = None, table_type: str | None = None) -> Plan:
    """A first plan: wide when several numeric columns sit under text headers, long when there
    is one numeric column and a few text columns (group / subject)."""
    from .sheets import guess_header_row
    hr = guess_header_row(rows) if header_row is None else header_row
    hs = headers(rows, hr)
    data = body(rows, hr)
    n = len(hs)
    numeric = []
    for j in range(n):
        vals = [r[j] for r in data if j < len(r) and not is_blank(r[j])]
        numeric.append(bool(vals) and sum(1 for v in vals if number(v) is not None) / len(vals) >= 0.6)
    plan = Plan(header_row=hr)
    low = [h.lower() for h in hs]
    num_cols = [j for j in range(n) if numeric[j]]
    text_cols = [j for j in range(n) if not numeric[j]]
    if len(num_cols) == 1 and text_cols:
        plan.layout = "long"
        plan.table_type = table_type or "column"
        plan.roles = {num_cols[0]: "value"}
        for j in text_cols:
            if any(k in low[j] for k in ("animal", "subject", "mouse", "rat", "id")):
                plan.roles[j] = "subject"
            elif "group" not in plan.roles.values():
                plan.roles[j] = "group"
            elif "factor2" not in plan.roles.values():
                plan.roles[j] = "factor2"
            else:
                plan.roles[j] = "ignore"
        return plan
    plan.layout = "wide"
    plan.table_type = table_type or "column"
    for j in range(n):
        plan.roles[j] = "set" if numeric[j] else "ignore"
    if text_cols and text_cols[0] == 0:
        plan.roles[0] = "row"
        if plan.table_type == "column":
            plan.table_type = "grouped" if len(num_cols) > 1 else "column"
    if plan.table_type == "xy" and num_cols:
        plan.roles[num_cols[0]] = "x"
    return plan


# ---------------------------------------------------------------------------

def build_table(rows: list[list], plan: Plan):
    """→ (Table, notes). The table carries `axis_titles` (X, Y) for its first graph."""
    t, notes = _build_long(rows, plan) if plan.layout == "long" else _build_wide(rows, plan)
    hs = headers(rows, plan.header_row) if plan.header_row >= 0 else []
    if hs:
        col = lambda role: next((hs[j] for j in sorted(plan.roles) if plan.roles[j] == role and j < len(hs)), None)
        y = col("value") if plan.layout == "long" else None
        x = col("x") or (col("factor2") if plan.table_type == "xy" else None)
        t.axis_titles = (x, y)
    return t, notes


def _new_table(plan, **fmt):
    from ..doc.model import Table
    return Table(plan.name, plan.table_type, **fmt)


def _build_wide(rows, plan):
    hs, data = headers(rows, plan.header_row), body(rows, plan.header_row)
    notes: list[str] = []
    roles = plan.roles
    set_cols = [j for j in sorted(roles) if roles[j] == "set"]
    row_col = next((j for j in sorted(roles) if roles[j] == "row"), None)
    x_col = next((j for j in sorted(roles) if roles[j] == "x"), None)
    xerr_col = next((j for j in sorted(roles) if roles[j] == "xerr"), None)
    tt = plan.table_type
    if not set_cols:
        raise ValueError("Choose at least one column as a data set.")
    # data sets: same-named columns side by side become replicates of one data set
    groups: "OrderedDict[str, list[int]]" = OrderedDict()
    for j in set_cols:
        key = _base(hs[j]) if plan.merge_same_names and tt in ("xy", "grouped") else f"{hs[j]}\u0000{j}"
        groups.setdefault(key, []).append(j)
    width = max(len(v) for v in groups.values())
    y_format = "replicates" if width > 1 else "single"
    if tt == "nested":
        y_format = "replicates"
    if tt == "multivar":
        groups = OrderedDict((f"{hs[j]}\u0000{j}", [j]) for j in sorted(roles) if roles[j] in ("set", "row"))
        width, y_format = 1, "single"
    x_format = None
    if tt == "xy":
        x_format = "numbers_err" if xerr_col is not None else "numbers"
        if x_col is not None and any(date_number(r[x_col]) is not None and number(r[x_col]) is None
                                     for r in data if x_col < len(r)):
            x_format = "date"
    t = _new_table(plan, y_format=y_format, replicates=max(width, 1), ncols=len(groups),
                   row_titles=row_col is not None, x_format=x_format)
    skipped = 0
    for ds, (key, cols) in enumerate(groups.items()):
        t.titles[ds] = key.split("\u0000")[0]
        if width > 1:
            t.sub_titles[ds] = [hs[j] for j in cols] + [""] * (t.width() - len(cols))
        for i, r in enumerate(data):
            for k, j in enumerate(cols):
                v = r[j] if j < len(r) else None
                if is_blank(v):
                    continue
                if tt == "multivar" and number(v) is None:
                    t.set(i, t.flat(ds, k), text(v), emit=False)
                    continue
                n = number(v)
                if n is None:
                    skipped += 1
                    continue
                if tt == "survival" or tt == "contingency":
                    n = max(n, 0)
                t.set(i, t.flat(ds, k), n, emit=False)
    for i, r in enumerate(data):
        if row_col is not None and row_col < len(r) and not is_blank(r[row_col]):
            t.set(i, "row", text(r[row_col]), emit=False)
        if x_col is not None and x_col < len(r):
            xv = number(r[x_col]) if x_format != "date" else (date_number(r[x_col]) or number(r[x_col]))
            if xv is not None:
                t.set(i, "x", xv, emit=False)
        if xerr_col is not None and xerr_col < len(r) and number(r[xerr_col]) is not None:
            t.set(i, "xerr", number(r[xerr_col]), emit=False)
    if skipped:
        notes.append(f"{skipped} text cell{'s' if skipped != 1 else ''} in data columns left out.")
    if tt == "xy" and x_col is None:
        notes.append("No X column chosen: rows are numbered 1, 2, 3 …")
        for i in range(len(data)):
            t.set(i, "x", float(i + 1), emit=False)
    return t, notes


def _levels(values) -> list[str]:
    seen: "OrderedDict[str, None]" = OrderedDict()
    for v in values:
        if not is_blank(v):
            seen.setdefault(text(v), None)
    return list(seen)


def _build_long(rows, plan):
    hs, data = headers(rows, plan.header_row), body(rows, plan.header_row)
    notes: list[str] = []
    role_col = {}
    for j in sorted(plan.roles):
        role_col.setdefault(plan.roles[j], j)
    vc, gc = role_col.get("value"), role_col.get("group")
    fc, sc = role_col.get("factor2"), role_col.get("subject")
    xc, ec = role_col.get("x"), role_col.get("event")
    tt = plan.table_type
    get = lambda r, j: (r[j] if j is not None and j < len(r) else None)
    if tt == "survival":
        if xc is None and vc is None:
            raise ValueError("Choose a column of times (X values).")
        tcol = xc if xc is not None else vc
        groups = _levels(get(r, gc) for r in data) if gc is not None else ["Data"]
        t = _new_table(plan, ncols=len(groups))
        t.titles[:len(groups)] = groups
        i = 0
        for r in data:
            tm = number(get(r, tcol))
            if tm is None:
                continue
            g = text(get(r, gc)) if gc is not None else "Data"
            ev = number(get(r, ec)) if ec is not None else 1.0
            t.set(i, "x", tm, emit=False)
            t.set(i, t.flat(groups.index(g)), 1.0 if ev else 0.0, emit=False)
            if sc is not None and not is_blank(get(r, sc)):
                t.has_row_titles = True
                t.set(i, "row", text(get(r, sc)), emit=False)
            i += 1
        return t, notes
    if tt == "contingency":
        if gc is None or fc is None:
            raise ValueError("Choose the outcome (groups) column and the row factor column.")
        outs, rws = _levels(get(r, gc) for r in data), _levels(get(r, fc) for r in data)
        t = _new_table(plan, ncols=len(outs))
        t.titles[:len(outs)] = outs
        counts = {}
        for r in data:
            a, b = get(r, fc), get(r, gc)
            if is_blank(a) or is_blank(b):
                continue
            w = number(get(r, vc)) if vc is not None else 1.0
            counts[(text(a), text(b))] = counts.get((text(a), text(b)), 0.0) + (w or 0.0)
        for i, rl in enumerate(rws):
            t.set(i, "row", rl, emit=False)
            for j, o in enumerate(outs):
                t.set(i, t.flat(j), counts.get((rl, o), 0.0), emit=False)
        if vc is None:
            notes.append("Counted the rows for each combination (no value column).")
        return t, notes
    if vc is None:
        raise ValueError("Choose the column holding the values.")
    groups = _levels(get(r, gc) for r in data) if gc is not None else [hs[vc]]
    second = fc if fc is not None else (xc if tt == "xy" else None)
    rows_of = _levels(get(r, second) for r in data) if second is not None else None
    if rows_of and all(number(v) is not None for v in rows_of):
        rows_of = sorted(rows_of, key=lambda v: number(v))       # days, hours … in numeric order
    # collect values: (group, rowkey) → [(subject, value)]
    cells: "OrderedDict[tuple, list]" = OrderedDict()
    subj_rank: dict = {}                       # subjects in the order they first appear in the file
    skipped = 0
    for r in data:
        v = number(get(r, vc))
        if v is None:
            if not is_blank(get(r, vc)):
                skipped += 1
            continue
        g = text(get(r, gc)) if gc is not None else groups[0]
        if is_blank(g):
            continue
        rk = text(get(r, second)) if second is not None else None
        subj = text(get(r, sc)) if sc is not None else None
        if subj is not None and subj not in subj_rank:
            subj_rank[subj] = len(subj_rank)
        cells.setdefault((g, rk), []).append((subj, v))
    if plan.average_subjects and sc is not None:
        for k, lst in cells.items():
            by: "OrderedDict[str, list]" = OrderedDict()
            for s, v in lst:
                by.setdefault(s, []).append(v)
            cells[k] = [(s, sum(vs) / len(vs)) for s, vs in by.items()]
        notes.append("Values averaged to one per subject (the unit of independence).")
    if tt == "nested":
        # data sets = groups; sub-columns = subjects; rows = that subject's values
        subjects = {g: sorted(_levels(s for (gg, _), lst in cells.items() if gg == g for s, _v in lst),
                              key=lambda s: subj_rank.get(s, 1e9)) for g in groups}
        width = max([len(v) for v in subjects.values()] + [1])
        t = _new_table(plan, y_format="replicates", replicates=width, ncols=len(groups))
        for ds, g in enumerate(groups):
            t.titles[ds] = g
            subs = subjects[g] or [""]
            t.sub_titles[ds] = subs + [""] * (width - len(subs))
            fill = {s: 0 for s in subs}
            for (gg, _), lst in cells.items():
                if gg != g:
                    continue
                for s, v in lst:
                    k = subs.index(s if s in subs else subs[0])
                    t.set(fill[subs[k]], t.flat(ds, k), v, emit=False)
                    fill[subs[k]] += 1
        if sc is None:
            notes.append("No subject column: each group's values sit in one sub-column.")
        return t, notes
    if tt == "column":
        t = _new_table(plan, ncols=len(groups))
        for ds, g in enumerate(groups):
            t.titles[ds] = g
            vals = [v for (gg, _), lst in cells.items() if gg == g for _s, v in lst]
            for i, v in enumerate(vals):
                t.set(i, t.flat(ds), v, emit=False)
    else:
        # grouped / xy: rows = second factor levels; replicates side by side; a subject keeps its
        # own sub-column across rows (repeated measures line up)
        rows_of = rows_of or [None]
        subj_cols = {}
        width = 1
        for g in groups:
            subs = sorted(_levels(s for (gg, _), lst in cells.items() if gg == g for s, _v in lst),
                          key=lambda s: subj_rank.get(s, 1e9)) if sc is not None else []
            subj_cols[g] = subs
            per_cell = max([len(lst) for (gg, _), lst in cells.items() if gg == g] + [1])
            width = max(width, len(subs) if subs else per_cell)
        x_numeric = tt == "xy" and rows_of != [None] and all(number(rk) is not None for rk in rows_of)
        t = _new_table(plan, y_format="replicates" if width > 1 else "single", replicates=width,
                       ncols=len(groups), row_titles=tt == "xy" and not x_numeric)
        if tt == "xy" and rows_of != [None] and x_numeric:
            rows_of = sorted(rows_of, key=lambda s: number(s))
        for i, rk in enumerate(rows_of):
            if rk is not None:
                if tt == "xy" and x_numeric:
                    t.set(i, "x", number(rk), emit=False)
                else:
                    t.set(i, "row", rk, emit=False)
                    if tt == "xy":
                        t.set(i, "x", float(i + 1), emit=False)
            for ds, g in enumerate(groups):
                subs = subj_cols[g]
                for k, (s, v) in enumerate(cells.get((g, rk), [])):
                    col = subs.index(s) if subs and s in subs else k
                    if col < t.width():
                        t.set(i, t.flat(ds, col), v, emit=False)
        for ds, g in enumerate(groups):
            t.titles[ds] = g
            if subj_cols[g] and width > 1:
                t.sub_titles[ds] = subj_cols[g] + [""] * (width - len(subj_cols[g]))
    if skipped:
        notes.append(f"{skipped} non-numeric value{'s' if skipped != 1 else ''} left out.")
    return t, notes
