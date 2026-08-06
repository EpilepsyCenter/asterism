"""Figure sets — the real answer to multi-panel figures (SPEC §10b-pre).

Select N analyses → ONE PDF/SVG containing all N, each positioned on a journal-
column-width canvas, each still at its own exact mm size, each an independently
named group (its axes gid), with optional auto panel letters in the house style.

This is deliberately NOT full panel composition — no shared legends, no cross-
panel alignment. A rough grid at correct sizes with named groups is the 90% win;
Affinity does the last 10% and people already know how to.

The layout is explicit axes placement on a larger canvas, which the mm-exact
authoring discipline already requires — so it reuses `render_grouped_bar_into`
verbatim and every panel stays byte-for-byte what it would be standalone.
"""

from __future__ import annotations

import string
from dataclasses import dataclass, field

from matplotlib.figure import Figure

from .figures import BarGroup, render_grouped_bar_into
from .style import LabStyle, mm

# internal margins of a panel (mm), matching the single-panel builder
_PANEL_MARGINS = dict(left=9.0, bottom=6.0, right=1.5, top=5.0)


@dataclass
class Panel:
    """One analysis to place in the set, at its own final mm size."""

    groups: list[BarGroup]
    width_mm: float
    height_mm: float
    comparisons: list[tuple[int, int, int, int, float]] | None = None
    y_label: str = "value"
    title: str | None = None
    rng_seed: int = 0


@dataclass
class _Placed:
    panel: Panel
    x_mm: float
    y_mm: float  # top-left origin, measured from canvas top
    letter: str


def _pack(panels: list[Panel], col_w_mm: float, gap_mm: float, margin_mm: float) -> tuple[list[_Placed], float]:
    """Greedy left-to-right / wrap-down packing into a rough grid.

    Returns placed panels (with top-left origins from the canvas top) and the
    total canvas height in mm.
    """
    placed: list[_Placed] = []
    x = margin_mm
    y = margin_mm
    row_h = 0.0
    avail = col_w_mm - margin_mm
    for i, p in enumerate(panels):
        if x > margin_mm and x + p.width_mm > avail + 1e-6:
            # wrap to next row
            x = margin_mm
            y += row_h + gap_mm
            row_h = 0.0
        placed.append(_Placed(p, x, y, string.ascii_uppercase[i]))
        x += p.width_mm + gap_mm
        row_h = max(row_h, p.height_mm)
    total_h = y + row_h + margin_mm
    return placed, total_h


def figure_set(panels: list[Panel], *, lab_style: LabStyle) -> Figure:
    """Compose panels into one mm-exact, vector, named-group figure set."""
    from .style import house_style

    fs_cfg = lab_style["figure_set"]
    col_w = float(fs_cfg["column_width_mm"])
    gap = float(fs_cfg["panel_gap_mm"])
    margin = float(fs_cfg["margin_mm"])

    placed, total_h = _pack(panels, col_w, gap, margin)

    with house_style():
        fig = Figure(figsize=(mm(col_w), mm(total_h)))
        for item in placed:
            p = item.panel
            # Panel box origin from the BOTTOM (matplotlib fig fraction is
            # bottom-left origin); we packed from the top, so flip.
            box_left = item.x_mm
            box_bottom = total_h - item.y_mm - p.height_mm

            ax_left = box_left + _PANEL_MARGINS["left"]
            ax_bottom = box_bottom + _PANEL_MARGINS["bottom"]
            ax_w = p.width_mm - _PANEL_MARGINS["left"] - _PANEL_MARGINS["right"]
            ax_h = p.height_mm - _PANEL_MARGINS["top"] - _PANEL_MARGINS["bottom"]

            rect = [ax_left / col_w, ax_bottom / total_h, ax_w / col_w, ax_h / total_h]
            ax = fig.add_axes(rect)
            # The axes gid IS the panel's named group in the SVG.
            ax.set_gid(f"panel_{item.letter}")
            render_grouped_bar_into(
                ax, p.groups, lab_style=lab_style, comparisons=p.comparisons,
                y_label=p.y_label, title=p.title, rng_seed=p.rng_seed,
                gid_ns=item.letter,
            )

            if fs_cfg.get("panel_letters", True):
                # Letter at the panel box top-left, in figure fraction.
                lx = box_left / col_w
                ly = (box_bottom + p.height_mm) / total_h
                t = fig.text(
                    lx, ly, item.letter,
                    fontsize=fs_cfg.get("letter_font_size", 9),
                    fontweight=fs_cfg.get("letter_weight", "bold"),
                    ha="left", va="top",
                )
                t.set_gid(f"panel_letter_{item.letter}")
        return fig
