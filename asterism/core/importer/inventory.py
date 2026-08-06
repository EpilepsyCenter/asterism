"""Column inventory + shape detection (SPEC §5.1).

On import, display every column: name, dtype, n unique, sample values, and a guessed
role. Also detect the header row and whether a sheet is wide (multiple numeric columns
under short, low-cardinality, non-numeric headers) so the UI can offer to melt.

All read-only inspection — produces a description for the UI to render and the user to
correct. Nothing here reshapes data.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd
from pandas.api import types as ptypes

from .roles import Role, RoleGuess, guess_role, normalize


@dataclass(frozen=True)
class ColumnInfo:
    name: str
    dtype: str
    n_unique: int
    n_missing: int
    is_numeric: bool
    samples: tuple
    guess: RoleGuess

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "dtype": self.dtype,
            "n_unique": self.n_unique,
            "n_missing": self.n_missing,
            "is_numeric": self.is_numeric,
            "samples": [str(s) for s in self.samples],
            "guess": self.guess.to_dict(),
        }


def inventory(df: pd.DataFrame, *, n_samples: int = 5) -> list[ColumnInfo]:
    """Describe every column of a (header-resolved) frame (SPEC §5.1)."""
    out: list[ColumnInfo] = []
    for col in df.columns:
        s = df[col]
        numeric_coerced = pd.to_numeric(s, errors="coerce")
        # "numeric" if already numeric OR cleanly coercible where non-missing
        non_missing = s.notna()
        is_numeric = bool(
            ptypes.is_numeric_dtype(s)
            or (non_missing.any()
                and numeric_coerced[non_missing].notna().all())
        )
        samples = tuple(s.dropna().unique()[:n_samples])
        out.append(ColumnInfo(
            name=str(col),
            dtype=str(s.dtype),
            n_unique=int(s.nunique(dropna=True)),
            n_missing=int(s.isna().sum()),
            is_numeric=is_numeric,
            samples=samples,
            guess=guess_role(str(col)),
        ))
    return out


def detect_header_row(rows: list[list], *, max_scan: int = 15) -> int:
    """Index of the most likely header row in raw sheet rows (SPEC §5.1).

    QuantStudio and TRACER's meta sheets carry a preamble before the table. The
    header row is the first mostly-non-numeric, mostly-non-empty row whose cell
    count is matched by the row below it (i.e. a real table starts there).
    """
    best_idx = 0
    best_score = -1.0
    for i, row in enumerate(rows[:max_scan]):
        cells = [c for c in row if c is not None and str(c).strip() != ""]
        if len(cells) < 2:
            continue
        non_numeric = sum(1 for c in cells if pd.to_numeric(pd.Series([c]),
                                                            errors="coerce").isna()[0])
        frac_text = non_numeric / len(cells)
        # reward rows followed by a row of similar width (the data)
        follows = 0.0
        if i + 1 < len(rows):
            below = [c for c in rows[i + 1] if c is not None and str(c).strip() != ""]
            if below and abs(len(below) - len(cells)) <= 1:
                follows = 0.5
        score = frac_text + follows - i * 0.02  # prefer earlier rows on ties
        if score > best_score:
            best_score, best_idx = score, i
    return best_idx


@dataclass(frozen=True)
class ShapeGuess:
    is_wide: bool
    reason: str
    value_like_columns: tuple[str, ...] = ()   # numeric metric columns to melt
    id_like_columns: tuple[str, ...] = ()       # id/factor columns to keep

    def to_dict(self) -> dict:
        return {
            "is_wide": self.is_wide,
            "reason": self.reason,
            "value_like_columns": list(self.value_like_columns),
            "id_like_columns": list(self.id_like_columns),
        }


def detect_wide_or_long(df: pd.DataFrame) -> ShapeGuess:
    """Guess whether a frame is wide (needs melting) or already long (SPEC §5.1).

    Wide ⇒ several numeric columns whose headers are short, low-cardinality, and
    non-numeric — i.e. the headers are metric/level names, not data. A frame that
    already has a `value`+`metric` pair (or a single numeric column) is long.
    """
    cols = [str(c) for c in df.columns]
    lowered = {c.lower() for c in cols}
    if {"value", "metric"} <= lowered or ("value" in lowered):
        return ShapeGuess(False, "has a 'value' column — already long.")

    numeric_cols = [c for c in cols
                    if pd.to_numeric(df[c], errors="coerce").notna().any()
                    and _mostly_numeric(df[c])]
    id_cols = [c for c in cols if c not in numeric_cols]

    if len(numeric_cols) >= 2:
        return ShapeGuess(
            True,
            f"{len(numeric_cols)} numeric columns under text headers "
            f"⇒ wide; offer to melt.",
            value_like_columns=tuple(numeric_cols),
            id_like_columns=tuple(id_cols),
        )
    return ShapeGuess(False, "at most one numeric column ⇒ treat as long.")


def _mostly_numeric(s: pd.Series, threshold: float = 0.8) -> bool:
    non_missing = s.notna()
    if not non_missing.any():
        return False
    coerced = pd.to_numeric(s[non_missing], errors="coerce")
    return (coerced.notna().mean()) >= threshold
