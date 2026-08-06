"""Reshaping source frames into canonical long format (SPEC §5–6).

The three shapes the sources actually produce (proven by reading the frozen apps'
export writers):

  * already-long          — TRACER `Cells (long)`, QuantStudio after melt
  * wide metrics          — NED-Net `PerAnimal`/`Duration_perAnimal`: melt to long
  * two-row-header groups — NED-Net `Daily_*`/`Circadian_byGroup`: row1 = group per
                            animal column, row2 = x-axis label + animal ids
  * joined tag strings    — TRACER `group_tags`/`series_specific_tags` written with
                            ', '.join(...); split back to atoms, then assign to factors

Every function is pure: frame(s) in, canonical-ish frame out. Role → canonical
renaming is the last step, done from an explicit, user-confirmed mapping.
"""

from __future__ import annotations

import pandas as pd

from ..contract import (BATCH, METRIC, REPLICATE, SOURCE_FILE, SUBJECT, UNIT,
                        VALUE, Dataset)
from .roles import Role

TAG_JOIN_SEP = ", "  # exactly what TRACER's export writer used (', '.join)


def apply_roles(
    df: pd.DataFrame,
    mapping: dict[str, Role],
    *,
    x: str | None = None,
) -> Dataset:
    """Rename columns to canonical names from a confirmed role mapping and wrap in
    a `Dataset`. GROUP-role columns keep their own names and become the factor list
    (SPEC §4: factors are user-defined, not named slots). IGNORE columns are left in
    place (they may still be tags/filters) but excluded from `known` roles.
    """
    canonical_name = {
        Role.VALUE: VALUE, Role.METRIC: METRIC, Role.UNIT: UNIT,
        Role.SUBJECT: SUBJECT, Role.REPLICATE: REPLICATE, Role.BATCH: BATCH,
        Role.SOURCE_FILE: SOURCE_FILE,
    }
    renames: dict[str, str] = {}
    factors: list[str] = []
    for col, role in mapping.items():
        if role in canonical_name:
            renames[col] = canonical_name[role]
        elif role == Role.GROUP:
            factors.append(col)  # keep the meaningful name (genotype, treatment…)
    out = df.rename(columns=renames)
    # coerce value to numeric now that it's identified (sentinels become NaN;
    # validation reports them separately from the *raw* frame, so do this on a copy)
    if VALUE in out.columns:
        out = out.copy()
        out[VALUE] = pd.to_numeric(out[VALUE], errors="coerce")
    return Dataset(out, factors=tuple(factors), x=x)


def melt_to_long(
    df: pd.DataFrame,
    *,
    id_vars: list[str],
    value_vars: list[str],
    metric_col: str = METRIC,
    value_col: str = VALUE,
) -> pd.DataFrame:
    """Wide metrics → long (NED-Net `PerAnimal`). Each value column becomes rows
    tagged by its name in `metric`."""
    keep = [c for c in id_vars if c in df.columns]
    vals = [c for c in value_vars if c in df.columns]
    long = df.melt(
        id_vars=keep, value_vars=vals,
        var_name=metric_col, value_name=value_col,
    )
    long[value_col] = pd.to_numeric(long[value_col], errors="coerce")
    return long


def two_row_header_to_long(
    rows: list[list],
    *,
    subject_col: str = SUBJECT,
    group_col: str = "group",
    value_col: str = VALUE,
    metric: str | None = None,
    metric_col: str = METRIC,
) -> pd.DataFrame:
    """Parse a NED-Net two-row-header grouped-wide block into long format.

    Layout (from `results.py::_wide`):
        row 0:  ['',           group_a, group_a, group_b, …]   # group per animal col
        row 1:  [x_label,      animal1, animal2, animal3, …]   # x-axis name + ids
        row 2+: [x_value,      v,       v,       v,       …]   # one row per x

    Produces long rows: {x_label: x_value, subject: animal, group: group, value: v}
    (plus a `metric` column if a metric name is supplied).
    """
    if len(rows) < 3:
        return pd.DataFrame(columns=[subject_col, group_col, value_col])
    group_row = rows[0]
    id_row = rows[1]
    x_label = str(id_row[0]) if id_row and id_row[0] not in (None, "") else "x"
    n_cols = len(id_row)

    animals = [id_row[j] for j in range(1, n_cols)]
    groups = [group_row[j] if j < len(group_row) else "" for j in range(1, n_cols)]

    out: list[dict] = []
    for data_row in rows[2:]:
        if not data_row:
            continue
        x_val = data_row[0]
        for j, animal in enumerate(animals, start=1):
            v = data_row[j] if j < len(data_row) else None
            if v is None or (isinstance(v, str) and v.strip() == ""):
                continue
            rec = {
                x_label: x_val,
                subject_col: animal,
                group_col: groups[j - 1],
                value_col: v,
            }
            if metric is not None:
                rec[metric_col] = metric
            out.append(rec)
    long = pd.DataFrame(out)
    if value_col in long.columns:
        long[value_col] = pd.to_numeric(long[value_col], errors="coerce")
    return long


def explode_tags(series: pd.Series, *, sep: str = TAG_JOIN_SEP) -> pd.Series:
    """Recover atomic tag lists from TRACER's joined tag strings (SPEC §5.3).

    The export writer wrote `', '.join(tags)`, so a cell like 'WT, male, DG'
    is three atoms, NOT one delimited factor value. Returns a Series of lists.
    """
    def split(v):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return []
        s = str(v).strip()
        if not s:
            return []
        return [t.strip() for t in s.split(sep) if t.strip()]
    return series.map(split)


def assign_tags_to_factors(
    df: pd.DataFrame,
    tag_column: str,
    assignment: dict[str, str],
    *,
    sep: str = TAG_JOIN_SEP,
    keep_unassigned_as: str | None = "tags_unassigned",
) -> pd.DataFrame:
    """Tag map (SPEC §5.3): assign each observed tag to a factor column.

    `assignment` maps a tag → a factor column name. For every row, each assigned
    factor gets the value of whichever of that row's tags maps to it. Unassigned
    tags are preserved (as a list) in `keep_unassigned_as` so they stay usable as
    filters. Assignment (not parsing) — the atoms already exist.
    """
    out = df.copy()
    exploded = explode_tags(out[tag_column], sep=sep)
    factor_names = sorted(set(assignment.values()))
    for factor in factor_names:
        wanted = {tag for tag, f in assignment.items() if f == factor}

        def pick(tag_list, wanted=wanted):
            hits = [t for t in tag_list if t in wanted]
            return hits[0] if hits else None
        out[factor] = exploded.map(pick)
    if keep_unassigned_as is not None:
        assigned = set(assignment)

        def leftovers(tag_list):
            return [t for t in tag_list if t not in assigned]
        out[keep_unassigned_as] = exploded.map(leftovers)
    return out
