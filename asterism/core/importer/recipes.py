"""Import recipes (SPEC §5.5).

The confirmed mapping (roles + level map + tag map + reshape plan) saved keyed on the
file's column signature plus its set of unique level values. A second file from the
same experiment then imports with zero clicks. Recipes are small YAML files,
version-controlled with the project.

Keying on the *values* as well as the columns matters: two files with identical
headers but different group levels (a pilot vs the real cohort) are different
experiments and should not silently share a mapping.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import yaml

from .roles import Role

RECIPE_FORMAT_VERSION = 1


def column_signature(
    columns: list[str],
    level_values: dict[str, list[str]] | None = None,
) -> str:
    """Stable signature of a file's shape: sorted column names + sorted unique
    level values of the keyed columns. Same experiment → same signature."""
    parts = ["|".join(sorted(str(c) for c in columns))]
    if level_values:
        for col in sorted(level_values):
            vals = "|".join(sorted(str(v) for v in level_values[col]))
            parts.append(f"{col}={vals}")
    blob = "\n".join(parts)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


@dataclass
class Recipe:
    """A re-applicable import mapping."""

    signature: str
    source: str                              # 'tracer' | 'nednet' | 'quantstudio' | 'manual'
    sheet: str | None = None
    shape: str = "long"                      # 'long' | 'wide' | 'two_row_header'
    roles: dict[str, str] = field(default_factory=dict)   # column -> Role.value
    factors: list[str] = field(default_factory=list)
    x: str | None = None
    # reshape params
    id_vars: list[str] = field(default_factory=list)
    value_vars: list[str] = field(default_factory=list)
    metric_name: str | None = None
    # level map (SPEC §5.2): source column -> {level -> {factor: value}}
    level_map: dict = field(default_factory=dict)
    # tag map (SPEC §5.3): tag -> factor
    tag_map: dict[str, str] = field(default_factory=dict)
    tag_column: str | None = None
    format_version: int = RECIPE_FORMAT_VERSION

    # --- role helpers -------------------------------------------------------

    def role_mapping(self) -> dict[str, Role]:
        return {col: Role(r) for col, r in self.roles.items()}

    def set_role_mapping(self, mapping: dict[str, Role]) -> None:
        self.roles = {col: role.value for col, role in mapping.items()}

    # --- persistence --------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "format_version": self.format_version,
            "signature": self.signature,
            "source": self.source,
            "sheet": self.sheet,
            "shape": self.shape,
            "roles": self.roles,
            "factors": self.factors,
            "x": self.x,
            "id_vars": self.id_vars,
            "value_vars": self.value_vars,
            "metric_name": self.metric_name,
            "level_map": self.level_map,
            "tag_map": self.tag_map,
            "tag_column": self.tag_column,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Recipe":
        return cls(
            signature=d["signature"],
            source=d["source"],
            sheet=d.get("sheet"),
            shape=d.get("shape", "long"),
            roles=d.get("roles", {}),
            factors=d.get("factors", []),
            x=d.get("x"),
            id_vars=d.get("id_vars", []),
            value_vars=d.get("value_vars", []),
            metric_name=d.get("metric_name"),
            level_map=d.get("level_map", {}),
            tag_map=d.get("tag_map", {}),
            tag_column=d.get("tag_column"),
            format_version=d.get("format_version", RECIPE_FORMAT_VERSION),
        )

    def save(self, path: Path | str) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            yaml.safe_dump(self.to_dict(), fh, sort_keys=False)
        return path

    @classmethod
    def load(cls, path: Path | str) -> "Recipe":
        with open(path, "r", encoding="utf-8") as fh:
            return cls.from_dict(yaml.safe_load(fh))


class RecipeBook:
    """A directory of recipe YAMLs, indexed by signature for zero-click reuse."""

    def __init__(self, directory: Path | str):
        self.directory = Path(directory)

    def find(self, signature: str) -> Recipe | None:
        for p in self.directory.glob("*.yaml") if self.directory.exists() else []:
            try:
                r = Recipe.load(p)
            except Exception:
                continue
            if r.signature == signature:
                return r
        return None

    def add(self, recipe: Recipe, name: str | None = None) -> Path:
        name = name or f"{recipe.source}_{recipe.signature}.yaml"
        return recipe.save(self.directory / name)
