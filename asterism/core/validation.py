"""Loud validation — at import, never at analysis (SPEC §7).

Everything questionable about a dataset is surfaced *before* anything runs, as a
flat list of structured `Issue`s the UI can display. Nothing is silently dropped or
repaired (SPEC §2: "Nothing is inferred silently"). These are reports, not
exceptions: a dataset with errors still returns a list — the caller decides whether
to block.

The §7 checklist, implemented:
    - missing required columns; unknown/extra columns
    - non-numeric values in `value`; `Undetermined`-style sentinel strings
    - missing values, and where
    - duplicate subject+replicate keys
    - unequal n across groups
    - a subject present in only one group when the design says paired
    - groups with n < 3
    - template version older than current
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import pandas as pd
from pandas.api import types as ptypes

from .contract import REPLICATE, SUBJECT, VALUE, Dataset
from .design import DesignResult

# Sentinel strings that masquerade as data (SPEC §7). QuantStudio emits
# "Undetermined"; Excel emits "#DIV/0!"; the rest are the usual suspects.
SENTINELS = frozenset({
    "undetermined", "undet", "n/a", "na", "nan", "null", "none", "",
    "#div/0!", "#value!", "#n/a", "inf", "-inf", "#ref!",
})

DEFAULT_MIN_N = 3


class Severity(str, Enum):
    ERROR = "error"      # analysis cannot run correctly
    WARNING = "warning"  # analysis will run but results may mislead
    INFO = "info"        # worth showing, not a problem


@dataclass(frozen=True)
class Issue:
    severity: Severity
    code: str
    message: str
    where: str | None = None  # locator: column name, row indices, level, …

    def to_dict(self) -> dict:
        return {
            "severity": self.severity.value,
            "code": self.code,
            "message": self.message,
            "where": self.where,
        }


def _sample_rows(mask: pd.Series, limit: int = 8) -> str:
    idx = mask[mask].index.tolist()
    shown = ", ".join(str(i) for i in idx[:limit])
    more = f" … (+{len(idx) - limit} more)" if len(idx) > limit else ""
    return f"rows [{shown}{more}]"


def validate(
    ds: Dataset,
    *,
    design: DesignResult | None = None,
    min_n: int = DEFAULT_MIN_N,
    template_version: int | None = None,
    current_template_version: int | None = None,
) -> list[Issue]:
    """Run every applicable §7 check and return all issues found.

    `design` enables the design-dependent checks (paired completeness). Template
    versions enable the template-staleness check; both are optional so the same
    function serves every source.
    """
    issues: list[Issue] = []
    frame = ds.frame

    # --- structure: required + extra columns --------------------------------
    for col in ds.missing_required():
        issues.append(Issue(
            Severity.ERROR, "missing_required_column",
            f"Required column '{col}' is missing.", where=col,
        ))
    extra = ds.extra_columns()
    if extra:
        issues.append(Issue(
            Severity.INFO, "extra_columns",
            f"{len(extra)} column(s) not assigned a role: {', '.join(extra)}. "
            f"They will be ignored unless assigned (e.g. as tags/filters).",
            where=", ".join(extra),
        ))
    for factor in ds.factors:
        if not ds.has(factor):
            issues.append(Issue(
                Severity.ERROR, "missing_factor_column",
                f"Declared factor '{factor}' is not a column in the data.",
                where=factor,
            ))

    # Everything below needs `value`; bail on the value-specific checks if absent.
    if VALUE in frame.columns:
        issues.extend(_check_value_column(frame))

    # --- duplicate subject+replicate keys -----------------------------------
    if SUBJECT in frame.columns and REPLICATE in frame.columns:
        key = frame[[SUBJECT, REPLICATE]].dropna()
        dup_mask = key.duplicated(keep=False)
        if dup_mask.any():
            n = int(dup_mask.sum())
            issues.append(Issue(
                Severity.WARNING, "duplicate_subject_replicate",
                f"{n} row(s) share a (subject, replicate) key — replicate ids are "
                f"not unique within a subject.",
                where=_sample_rows(dup_mask.reindex(frame.index, fill_value=False)),
            ))

    # --- n per group: unequal, and < min_n ----------------------------------
    issues.extend(_check_group_ns(ds, min_n))

    # --- paired completeness (design-dependent) -----------------------------
    if design is not None:
        issues.extend(_check_paired_completeness(ds, design))

    # --- template staleness --------------------------------------------------
    if template_version is not None and current_template_version is not None:
        if template_version < current_template_version:
            issues.append(Issue(
                Severity.WARNING, "template_out_of_date",
                f"Template version {template_version} is older than the current "
                f"{current_template_version}. Re-export from the current template "
                f"if columns have changed.",
            ))

    return issues


def _check_value_column(frame: pd.DataFrame) -> list[Issue]:
    issues: list[Issue] = []
    col = frame[VALUE]

    if ptypes.is_numeric_dtype(col):
        # Purely numeric already; only missing values to report.
        miss = col.isna()
        if miss.any():
            issues.append(Issue(
                Severity.WARNING, "missing_values",
                f"{int(miss.sum())} missing value(s) in '{VALUE}'.",
                where=_sample_rows(miss),
            ))
        return issues

    # Object/string dtype: separate sentinels, other non-numeric, and blanks.
    as_str = col.astype(str).str.strip()
    lowered = as_str.str.lower()
    is_blank = col.isna() | (as_str == "")
    coerced = pd.to_numeric(as_str.where(~is_blank), errors="coerce")

    sentinel_mask = lowered.isin(SENTINELS) & ~is_blank
    if sentinel_mask.any():
        bad = sorted(as_str[sentinel_mask].unique().tolist())
        issues.append(Issue(
            Severity.ERROR, "sentinel_values",
            f"{int(sentinel_mask.sum())} sentinel string(s) in '{VALUE}' "
            f"({', '.join(bad)}) — decide drop vs censor before analysis.",
            where=_sample_rows(sentinel_mask),
        ))

    non_numeric = coerced.isna() & ~is_blank & ~sentinel_mask
    if non_numeric.any():
        bad = sorted(as_str[non_numeric].unique().tolist())[:8]
        issues.append(Issue(
            Severity.ERROR, "non_numeric_value",
            f"{int(non_numeric.sum())} non-numeric value(s) in '{VALUE}' "
            f"(e.g. {', '.join(bad)}).",
            where=_sample_rows(non_numeric),
        ))

    if is_blank.any():
        issues.append(Issue(
            Severity.WARNING, "missing_values",
            f"{int(is_blank.sum())} missing/blank value(s) in '{VALUE}'.",
            where=_sample_rows(is_blank),
        ))
    return issues


def _check_group_ns(ds: Dataset, min_n: int) -> list[Issue]:
    """Unequal n across groups, and any group with n subjects < min_n (SPEC §7).

    n is counted in **subjects** (the unit of independence, SPEC §3), not rows —
    counting rows would reward pseudoreplication.
    """
    issues: list[Issue] = []
    factors = [f for f in ds.factors if ds.has(f)]
    if not factors or SUBJECT not in ds.frame.columns:
        return issues

    counts = (
        ds.frame[[SUBJECT, *factors]].dropna()
        .groupby(factors, dropna=False)[SUBJECT]
        .nunique()
    )
    if counts.empty:
        return issues

    def label(idx) -> str:
        if len(factors) == 1:
            return f"{factors[0]}={idx}"
        return ", ".join(f"{k}={v}" for k, v in zip(factors, idx))

    if counts.nunique() > 1:
        detail = "; ".join(f"{label(i)}: n={int(v)}" for i, v in counts.items())
        issues.append(Issue(
            Severity.INFO, "unequal_group_n",
            f"Unequal n across groups ({detail}).",
        ))

    small = counts[counts < min_n]
    for idx, v in small.items():
        issues.append(Issue(
            Severity.WARNING, "small_group_n",
            f"Group {label(idx)} has n={int(v)} subjects (< {min_n}); tests will be "
            f"underpowered and normality checks unreliable.",
            where=label(idx),
        ))
    return issues


def _check_paired_completeness(ds: Dataset, design: DesignResult) -> list[Issue]:
    """When the design is paired/RM (subjects shared), every subject should appear
    in every level; a subject present in only one level can't be paired (SPEC §7)."""
    issues: list[Issue] = []
    shared = [f for f in design.factor_facts if f.subjects_shared]
    if not shared or SUBJECT not in ds.frame.columns:
        return issues

    for f in shared:
        if not ds.has(f.name):
            continue
        per_subject = (
            ds.frame[[SUBJECT, f.name]].dropna()
            .groupby(SUBJECT)[f.name].nunique()
        )
        incomplete = per_subject[per_subject < f.n_levels]
        if len(incomplete):
            subs = ", ".join(str(s) for s in incomplete.index.tolist()[:8])
            issues.append(Issue(
                Severity.WARNING, "incomplete_pairing",
                f"Design is repeated-measures on '{f.name}' ({f.n_levels} levels) but "
                f"{len(incomplete)} subject(s) are present in fewer levels: {subs}. "
                f"They contribute no complete pair.",
                where=f.name,
            ))
    return issues


def worst_severity(issues: list[Issue]) -> Severity | None:
    order = {Severity.ERROR: 2, Severity.WARNING: 1, Severity.INFO: 0}
    if not issues:
        return None
    return max((i.severity for i in issues), key=lambda s: order[s])
