"""Style loading + mm-exact geometry helpers (SPEC §9, §10b).

The whole point of authoring in millimetres is that a figure leaves ASTERISM at
its final journal size, so line widths and font sizes — specified in points — are
correct at 1:1 and never rescaled in Affinity. Every geometry helper here works in
mm and converts to the figure-fraction coordinates matplotlib wants, so callers
never touch fractions directly.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import matplotlib as mpl
import matplotlib.style  # noqa: F401  (registers mpl.style)
import yaml

_ASSETS = Path(__file__).resolve().parent.parent / "assets"
MPLSTYLE_PATH = _ASSETS / "asterism.mplstyle"
LAB_STYLE_PATH = _ASSETS / "lab_style.yaml"

MM_PER_INCH = 25.4


def mm(value_mm: float) -> float:
    """Millimetres → inches (matplotlib's figure unit)."""
    return value_mm / MM_PER_INCH


@dataclass(frozen=True)
class LabStyle:
    """Parsed lab style file. A thin typed view over the YAML (SPEC §9)."""

    raw: dict = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path | str = LAB_STYLE_PATH) -> "LabStyle":
        with open(path, "r") as fh:
            return cls(raw=yaml.safe_load(fh))

    def __getitem__(self, key: str):
        return self.raw[key]

    def get(self, key: str, default=None):
        return self.raw.get(key, default)


@contextlib.contextmanager
def house_style() -> Iterator[None]:
    """Apply the non-negotiable .mplstyle for the duration of a figure build.

    Used as a context manager so a figure build cannot leak rcParams into the
    rest of the process — important once this runs inside a long-lived Dash
    server where a stray global rcParam would silently corrupt later exports.
    """
    with mpl.style.context(MPLSTYLE_PATH):
        yield


def axes_rect_mm(
    *,
    fig_w_mm: float,
    fig_h_mm: float,
    left_mm: float,
    bottom_mm: float,
    right_mm: float,
    top_mm: float,
) -> list[float]:
    """Axes rectangle [left, bottom, width, height] in figure fractions.

    Callers pass margins in mm; we return the fraction rectangle for
    `fig.add_axes(...)`. Using explicit placement (never `bbox_inches='tight'`)
    is what keeps the output canvas exactly `fig_w_mm × fig_h_mm` (SPEC §10b).
    """
    ax_w_mm = fig_w_mm - left_mm - right_mm
    ax_h_mm = fig_h_mm - bottom_mm - top_mm
    if ax_w_mm <= 0 or ax_h_mm <= 0:
        raise ValueError(
            f"Margins exceed figure size: {fig_w_mm}x{fig_h_mm} mm with "
            f"L{left_mm} R{right_mm} B{bottom_mm} T{top_mm}"
        )
    return [
        left_mm / fig_w_mm,
        bottom_mm / fig_h_mm,
        ax_w_mm / fig_w_mm,
        ax_h_mm / fig_h_mm,
    ]
