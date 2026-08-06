"""The canonical long-format data contract (SPEC §3–4).

Everything upstream (TRACER, NED-Net, QuantStudio, the manual template) converges
on ONE shape:

    value | metric | unit | subject | replicate | <factor columns…> | batch | source_file

`subject` is load-bearing (SPEC §3): it is the unit of independence and drives
paired-vs-unpaired detection, repeated-measures detection, and honest n reporting.
Stats run on subject means by default.

Factors are a **user-defined list, not named slots** (SPEC §4). There is no built-in
`genotype`/`treatment`; a `Dataset` just carries the ordered list of factor column
names, and design detection keys off their number and structure, never their names.

Vocabulary note vs the GliaAnalysis reference build (SPEC §12): Glia's `animal_col`
is our `subject`; Glia's wide `feature_cols` are our single long-form `value` keyed by
`metric`; Glia's `between_cols` are our `factors`; Glia's `within_col` (`roi_tag`) is
detected automatically here via shared subjects rather than being named by the user.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

# --- Canonical column names (fixed part of the contract) -------------------
VALUE = "value"
METRIC = "metric"
UNIT = "unit"
SUBJECT = "subject"
REPLICATE = "replicate"
BATCH = "batch"
SOURCE_FILE = "source_file"

CANONICAL_COLUMNS: tuple[str, ...] = (
    VALUE, METRIC, UNIT, SUBJECT, REPLICATE, BATCH, SOURCE_FILE,
)
REQUIRED_COLUMNS: tuple[str, ...] = (VALUE, SUBJECT)
OPTIONAL_COLUMNS: tuple[str, ...] = (METRIC, UNIT, REPLICATE, BATCH, SOURCE_FILE)


@dataclass(frozen=True)
class Dataset:
    """A long-format frame plus the roles that aren't fixed by name.

    A thin, typed holder — it does NOT validate loudly (that is `validation.py`,
    which runs at import and reports everything). It only records *which* columns
    are factors and which, if any, is the numeric predictor `x` (SPEC §8
    regression/correlation row).
    """

    frame: pd.DataFrame
    factors: tuple[str, ...] = ("group",)
    x: str | None = None  # numeric predictor for regression/correlation (§8)

    def __post_init__(self):
        # Normalise factors to a tuple so the dataclass stays hashable/frozen
        # even if a list was passed.
        object.__setattr__(self, "factors", tuple(self.factors))

    # --- structural queries (safe even on a not-yet-validated frame) --------

    def has(self, column: str) -> bool:
        return column in self.frame.columns

    def present_canonical(self) -> list[str]:
        return [c for c in CANONICAL_COLUMNS if c in self.frame.columns]

    def missing_required(self) -> list[str]:
        return [c for c in REQUIRED_COLUMNS if c not in self.frame.columns]

    def known_columns(self) -> set[str]:
        """Every column the contract accounts for: canonical + factors + x."""
        known = set(CANONICAL_COLUMNS) | set(self.factors)
        if self.x:
            known.add(self.x)
        return known

    def extra_columns(self) -> list[str]:
        """Columns present but unaccounted for. Not an error — may be unassigned
        tags/filters (SPEC §5.3) — but surfaced by validation."""
        return [c for c in self.frame.columns if c not in self.known_columns()]

    # --- the load-bearing subject logic (SPEC §3) ---------------------------

    def levels(self, factor: str) -> list:
        """Sorted unique observed levels of a factor column."""
        return sorted(self.frame[factor].dropna().unique().tolist(), key=str)

    def subjects_shared_across(self, factor: str) -> bool:
        """True if any subject appears in ≥2 levels of `factor`.

        This is what distinguishes repeated-measures / paired (shared) from
        independent (distinct) designs (SPEC §3, §8) — computed from the data,
        never guessed from column names.
        """
        if SUBJECT not in self.frame.columns or factor not in self.frame.columns:
            return False
        per_subject_levels = (
            self.frame[[SUBJECT, factor]].dropna()
            .groupby(SUBJECT)[factor].nunique()
        )
        return bool((per_subject_levels > 1).any())

    def subject_means(self) -> pd.DataFrame:
        """One row per (subject, factor-combo): mean of `value`.

        The default unit of analysis (SPEC §3), mirroring Glia's
        `aggregate_to_animal`. Replicates within a subject collapse to the
        subject mean before any test runs.
        """
        keys = [SUBJECT, *self.factors]
        keys = [k for k in keys if k in self.frame.columns]
        return (
            self.frame.groupby(keys, dropna=False)[VALUE]
            .mean()
            .reset_index()
        )

    def n_report(self) -> dict[str, int]:
        """Honest n (SPEC §3): subjects, replicates, total observations.

        Produces the numbers behind a string like 'n = 8 animals, 217 cells'.
        """
        report = {"observations": int(len(self.frame))}
        if SUBJECT in self.frame.columns:
            report["subjects"] = int(self.frame[SUBJECT].nunique())
        if REPLICATE in self.frame.columns:
            # replicates are only unique within a subject
            report["replicates"] = int(
                self.frame[[SUBJECT, REPLICATE]].dropna().drop_duplicates().shape[0]
            ) if SUBJECT in self.frame.columns else int(self.frame[REPLICATE].nunique())
        return report
