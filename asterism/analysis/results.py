"""Prism-style result pages and number formatting (no Qt)."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


# ---------------------------------------------------------------------------
# Prism number formatting
# ---------------------------------------------------------------------------

def fmt_p(p: float) -> str:
    if p is None or np.isnan(p):
        return ""
    return "<0.0001" if p < 0.0001 else f"{p:.4f}"


def p_summary(p: float) -> str:
    if p is None or np.isnan(p):
        return ""
    for cut, s in ((0.0001, "****"), (0.001, "***"), (0.01, "**"), (0.05, "*")):
        if p < cut:
            return s
    return "ns"


def fmt(x: float, sig: int = 4) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return ""
    if x == 0:
        return "0"
    if not np.isfinite(x):
        return "+∞" if x > 0 else "−∞"
    mag = int(np.floor(np.log10(abs(x))))
    if mag < -4 or mag >= 9:                     # very small or large: scientific notation
        return f"{x:.{sig - 1}e}"
    decimals = max(0, sig - 1 - mag)
    return f"{x:.{min(decimals, 8)}f}"


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------

@dataclass
class ResultPage:
    title: str
    columns: list[str]                       # value column headers
    rows: list[tuple[str, list[str], str]]   # (label, values, style: section|row|blank)
    first_column: str | None = None          # header of the label column (default: title)


@dataclass
class AnalysisResult:
    pages: list[ResultPage] = field(default_factory=list)
    p: float | None = None
    pair: tuple[int, int] | None = None      # columns compared (for graph brackets)
    error: str | None = None
    # (data set, data set, adjusted P) for every comparison an analysis reports; graphs draw
    # significance brackets from these.
    comparisons: list[tuple[int, int, float]] = field(default_factory=list)
    table: dict | None = None                # tabular output (e.g. frequency distribution)
    # ((row, col), (row, col), adjusted P) for two-way comparisons between cells
    cell_comparisons: list = field(default_factory=list)
    fit: dict | None = None                  # model details (two-way ANOVA)
    families: list | None = None
    rows: list = field(default_factory=list)  # per-row tests: (row, P, adjusted P or q)
