"""Significance brackets — a custom draw function (SPEC §9).

matplotlib has nothing for this. Placement is automatic: given the significant
comparisons and the height each bar/point cloud reaches, sort spans by width,
stack narrow-over-wide, and offset each new bracket above whatever it would
otherwise collide with.

Geometry the eye cares about (cap length, height offset, stack gap) is specified
in *millimetres* and converted to data coordinates per-axis, so a bracket looks
identical whether it sits on a tall or short axis. Line widths and fonts stay in
points, correct at 1:1.
"""

from __future__ import annotations

from dataclasses import dataclass

from matplotlib.axes import Axes

from .style import MM_PER_INCH


@dataclass
class Comparison:
    """One significance annotation between two x positions."""

    x1: float
    x2: float
    p: float
    # `data_height` is the tallest ink under the span (bar top + error bar +
    # points), in data coords — the bracket must clear it.
    data_height: float

    @property
    def span(self) -> float:
        return abs(self.x2 - self.x1)


def p_to_stars(p: float) -> str:
    if p <= 1e-4:
        return "****"
    if p <= 1e-3:
        return "***"
    if p <= 1e-2:
        return "**"
    if p <= 5e-2:
        return "*"
    return "ns"


def _mm_to_data_y(ax: Axes, length_mm: float) -> float:
    """Convert a vertical length in mm to data units on this axis."""
    fig_h_in = ax.figure.get_size_inches()[1]
    ax_frac_h = ax.get_position().height
    ax_h_mm = fig_h_in * MM_PER_INCH * ax_frac_h
    y0, y1 = ax.get_ylim()
    data_per_mm = (y1 - y0) / ax_h_mm
    return length_mm * data_per_mm


def draw_brackets(
    ax: Axes,
    comparisons: list[Comparison],
    style: dict,
    *,
    gid_prefix: str = "bracket",
) -> list[float]:
    """Draw significance brackets with automatic stacking + collision avoidance.

    Returns the top y (data coords) each bracket reached, so the caller can grow
    the axis y-limit to fit them. Every line and label gets a gid so it arrives
    in Affinity as a named, selectable object (SPEC §10b).
    """
    cap_mm = float(style["cap_length_mm"])
    offset_mm = float(style["height_offset_mm"])
    stack_gap_mm = float(style["stack_gap_mm"])
    lw = float(style["line_width"])
    label_mode = style.get("label_mode", "stars")
    font_size = float(style.get("font_size", 7))

    cap = _mm_to_data_y(ax, cap_mm)
    offset = _mm_to_data_y(ax, offset_mm)
    stack_gap = _mm_to_data_y(ax, stack_gap_mm)

    # Narrowest span first: short local brackets settle low, wide spanning
    # brackets ride above them. This is the ordering that minimises stacking.
    ordered = sorted(enumerate(comparisons), key=lambda kv: kv[1].span)

    # `placed` holds (x1, x2, top_y) of everything already drawn, so a new
    # bracket can find the highest thing it overlaps in x and clear it.
    placed: list[tuple[float, float, float]] = []
    tops: list[float] = []

    for order_i, (orig_i, comp) in enumerate(ordered):
        lo, hi = sorted((comp.x1, comp.x2))
        # Floor: clear the tallest ink under this span.
        floor = comp.data_height + offset
        # Also clear any already-placed bracket whose x-range overlaps ours.
        for px1, px2, ptop in placed:
            if px1 <= hi and lo <= px2:  # x-overlap
                floor = max(floor, ptop + stack_gap)
        bar_y = floor

        line_gid = f"{gid_prefix}_{orig_i}"
        # Bracket: down-cap, across, down-cap (caps point downward toward bars).
        xs = [comp.x1, comp.x1, comp.x2, comp.x2]
        ys = [bar_y - cap, bar_y, bar_y, bar_y - cap]
        (line,) = ax.plot(xs, ys, lw=lw, color="black", solid_capstyle="butt")
        line.set_gid(f"{line_gid}_line")

        if label_mode == "p_value":
            label = f"p = {comp.p:.3g}"
        else:
            label = p_to_stars(comp.p)
        txt = ax.text(
            (comp.x1 + comp.x2) / 2.0,
            bar_y,
            label,
            ha="center",
            va="bottom",
            fontsize=font_size,
        )
        txt.set_gid(f"{line_gid}_label")

        # Reserve headroom for the label glyphs above the bar line.
        label_top = bar_y + _mm_to_data_y(ax, font_size / 72.0 * MM_PER_INCH)
        placed.append((lo, hi, label_top))
        tops.append(label_top)

    return tops
