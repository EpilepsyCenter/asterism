"""Reference values taken from the lab's own Prism projects and data (the "golden" checks
that ASTERISM matches Prism). They contain unpublished experimental values, so they live
only locally in sample_data/golden/ (gitignored), never in the repository. Without them,
the tests that need them skip; everything else runs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLACES = [ROOT / "sample_data" / "golden", Path(__file__).parent / "golden"]


class Missing(dict):
    """Stands in for absent reference values: parametrised tests get no cases, and a test
    that reads a value skips."""

    def __getitem__(self, key):
        pytest.skip("lab reference values (sample_data/golden/) are not present")

    def get(self, key, default=None):
        return default if default is not None else Missing()


def golden(name: str = "prism_golden.json"):
    for d in PLACES:
        p = d / name
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    return Missing()
