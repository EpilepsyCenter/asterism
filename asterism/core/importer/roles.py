"""Column role guessing from a synonym dictionary (SPEC §5.1).

A role guess is only ever a *pre-filled dropdown default* — always overridable, never
silently applied (SPEC §2). Matching is fuzzy: names are normalised (lowercased,
punctuation → underscores, tokenised) and compared to a synonym dictionary by exact
token hit first, then close-string similarity. Every guess carries a confidence and
the reason, so the UI can show *why* it guessed and rank the alternatives.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from enum import Enum


class Role(str, Enum):
    """Roles a source column can map to. Factor columns use GROUP (the contract's
    factors are a user-defined list; GROUP just marks 'this is a factor')."""

    VALUE = "value"
    METRIC = "metric"
    UNIT = "unit"
    SUBJECT = "subject"
    REPLICATE = "replicate"
    GROUP = "group"          # a factor column (SPEC §4)
    BATCH = "batch"
    SOURCE_FILE = "source_file"
    X = "x"                  # numeric predictor for regression/correlation (§8)
    EXCLUDE = "exclude"      # exclusion flag — must be respected, never dropped (§6)
    IGNORE = "ignore"        # not part of the analysis (may still be a tag/filter)


# The synonym dictionary (SPEC §5.1). Keys are roles, values are the tokens/aliases
# that, if they match a column name, vote for that role.
SYNONYMS: dict[Role, tuple[str, ...]] = {
    Role.VALUE: ("value", "amp", "amplitude", "intensity", "intden", "area",
                 "ct", "dct", "ddct", "fold", "count", "rate"),
    Role.SUBJECT: ("subject", "animal", "animal_id", "mouse", "rat", "id",
                   "prep", "culture", "blot"),
    Role.REPLICATE: ("replicate", "cell", "cell_id", "roi", "field", "well",
                     "event_id", "event_index", "rep"),
    Role.GROUP: ("group", "group_id", "genotype", "treatment", "condition", "tx"),
    Role.METRIC: ("metric", "measure", "target", "target_name"),
    Role.UNIT: ("unit", "units"),
    Role.BATCH: ("batch", "plate", "cohort", "session", "blot", "run"),
    Role.SOURCE_FILE: ("source_file", "file", "file_name", "filename", "path",
                        "file_path"),
    Role.EXCLUDE: ("exclude", "excluded", "include", "drop", "omit"),
}

# Some aliases are ambiguous across roles (e.g. 'id', 'rate', 'count', 'blot').
# When a token votes for more than one role we prefer the more specific one via
# this priority order; SUBJECT beats REPLICATE for a bare 'id', etc.
_ROLE_PRIORITY = (
    Role.SUBJECT, Role.REPLICATE, Role.GROUP, Role.METRIC, Role.UNIT,
    Role.EXCLUDE, Role.BATCH, Role.SOURCE_FILE, Role.VALUE,
)


@dataclass(frozen=True)
class RoleGuess:
    role: Role
    confidence: float          # 0..1
    reason: str
    alternatives: tuple[Role, ...] = ()

    def to_dict(self) -> dict:
        return {
            "role": self.role.value,
            "confidence": round(self.confidence, 3),
            "reason": self.reason,
            "alternatives": [r.value for r in self.alternatives],
        }


def normalize(name: str) -> str:
    """Lowercase, collapse punctuation to single underscores, strip edges."""
    s = re.sub(r"[^0-9a-zA-Z]+", "_", str(name).strip().lower())
    return s.strip("_")


def tokens(name: str) -> list[str]:
    return [t for t in normalize(name).split("_") if t]


def _meta_prefixed(name: str) -> bool:
    # TRACER wide sheet emits `meta.<k>` metadata columns; treat as ignore-by-default.
    return str(name).lower().startswith("meta.")


def guess_role(name: str) -> RoleGuess:
    """Guess a single column's role from its name alone (SPEC §5.1)."""
    if _meta_prefixed(name):
        return RoleGuess(Role.IGNORE, 0.4,
                         "`meta.*` metadata column — assign only if needed.")

    norm = normalize(name)
    toks = set(tokens(name))
    scores: dict[Role, tuple[float, str]] = {}

    for role in _ROLE_PRIORITY if False else SYNONYMS:  # iterate all roles
        aliases = SYNONYMS[role]
        best = 0.0
        why = ""
        for alias in aliases:
            if norm == alias:
                best, why = 1.0, f"exact match to '{alias}'"
                break
            if alias in toks:
                if best < 0.9:
                    best, why = 0.9, f"token '{alias}' present"
            elif alias in norm:
                if best < 0.7:
                    best, why = 0.7, f"contains '{alias}'"
            else:
                ratio = difflib.SequenceMatcher(None, norm, alias).ratio()
                if ratio >= 0.85 and ratio > best:
                    best, why = ratio * 0.8, f"~'{alias}' ({ratio:.2f})"
        if best > 0:
            scores[role] = (best, why)

    if not scores:
        return RoleGuess(Role.IGNORE, 0.0, "no synonym matched")

    # Resolve ties by the specificity priority order.
    def sort_key(item):
        role, (score, _why) = item
        prio = _ROLE_PRIORITY.index(role) if role in _ROLE_PRIORITY else 99
        return (-score, prio)

    ranked = sorted(scores.items(), key=sort_key)
    top_role, (top_score, top_why) = ranked[0]
    alts = tuple(r for r, _ in ranked[1:4])
    return RoleGuess(top_role, top_score, top_why, alts)
