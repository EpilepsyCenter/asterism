"""Grouped bar figure builder (SPEC §9).

Representative of the hardest figure type for export fidelity: bars + a nested
point overlay (SuperPlot; Lord et al. 2020 J Cell Biol) + significance brackets.
Everything is authored at final mm size with explicit axes placement, and every
artist carries a `set_gid` so it lands in Affinity as a named object (SPEC §10b).

`render_grouped_bar_into` draws onto an axes that has already been placed at its
final mm rectangle — this is what lets a single-panel figure and a figure-set
panel (§10b-pre) share one drawing routine and stay pixel-identical.

Stats are NOT computed here — bar heights and error come from subject means,
honest n is the subject count. The caller supplies the significant comparisons;
this module only draws them.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from .brackets import Comparison, draw_brackets
from .style import LabStyle, axes_rect_mm, house_style, mm


@dataclass
class SubGroup:
    """One bar: a within-group level (e.g. treatment 'veh')."""

    label: str
    # subject_id -> replicate values (cells/ROIs/wells within that subject).
    subjects: dict[str, np.ndarray] = field(default_factory=dict)

    def subject_means(self) -> np.ndarray:
        return np.array([np.mean(v) for v in self.subjects.values()])


@dataclass
class BarGroup:
    """A cluster of bars sharing an x-axis label (e.g. genotype 'WT')."""

    label: str
    subgroups: list[SubGroup]


def _slot_positions(n_groups: int, n_sub: int, style: dict) -> tuple[np.ndarray, np.ndarray]:
    """Return (bar_centres[n_groups, n_sub], group_centres[n_groups]).

    Bars within a group are separated by `within_group_gap`; whole groups are
    separated by the larger `between_group_gap`, so clusters read as clusters.
    """
    bar_w = style["width"]
    within = style["within_group_gap"]
    between = style["between_group_gap"]
    step = bar_w + within
    group_w = n_sub * bar_w + (n_sub - 1) * within
    group_stride = group_w + between
    group_centres = np.arange(n_groups) * group_stride
    offsets = (np.arange(n_sub) - (n_sub - 1) / 2.0) * step
    bar_centres = group_centres[:, None] + offsets[None, :]
    return bar_centres, group_centres


def render_grouped_bar_into(
    ax: Axes,
    groups: list[BarGroup],
    *,
    lab_style: LabStyle,
    comparisons: list[tuple[int, int, int, int, float]] | None = None,
    y_label: str = "value",
    title: str | None = None,
    rng_seed: int = 0,
    gid_ns: str = "",
) -> None:
    """Draw a grouped bar onto an already-placed axes.

    `gid_ns` namespaces every gid so multiple panels on one figure-set canvas
    don't collide (e.g. 'A_bar_WT_veh'). `comparisons` is a list of
    (g1, s1, g2, s2, p): the two bars to bracket and the p-value.
    """
    bar_cfg = lab_style["bar"]
    pt_cfg = lab_style["points"]
    pal = lab_style["palette"]

    def gid(name: str) -> str:
        return f"{gid_ns}_{name}" if gid_ns else name

    n_groups = len(groups)
    n_sub = max(len(g.subgroups) for g in groups)
    centres, group_centres = _slot_positions(n_groups, n_sub, bar_cfg)
    bar_w = bar_cfg["width"]
    rng = np.random.default_rng(rng_seed)

    # Stable colour per subject across the whole panel (SuperPlot).
    all_subjects: list[str] = []
    for g in groups:
        for s in g.subgroups:
            all_subjects.extend(s.subjects.keys())
    subj_order = list(dict.fromkeys(all_subjects))
    subj_colour = {sid: pal[i % len(pal)] for i, sid in enumerate(subj_order)}

    max_ink = 0.0  # tallest thing drawn, for bracket floor + ylim

    for gi, g in enumerate(groups):
        for si, sub in enumerate(g.subgroups):
            x = centres[gi, si]
            means = sub.subject_means()
            bar_h = float(np.mean(means))
            sem = (
                float(np.std(means, ddof=1) / np.sqrt(len(means)))
                if len(means) > 1 else 0.0
            )

            sub_colour = pal[si % len(pal)]
            bar = ax.bar(
                x, bar_h, width=bar_w,
                facecolor=sub_colour, edgecolor="black",
                linewidth=bar_cfg["edge_width"], alpha=bar_cfg["fill_alpha"],
                zorder=1,
            )
            bar[0].set_gid(gid(f"bar_{g.label}_{sub.label}"))

            if sem > 0:
                eb = ax.errorbar(
                    x, bar_h, yerr=sem, fmt="none",
                    ecolor="black", elinewidth=bar_cfg["edge_width"],
                    capsize=2, capthick=bar_cfg["edge_width"], zorder=4,
                )
                # ErrorbarContainer is not an Artist; gid its component lines
                # (the vertical bar line and the caplines) so they survive to SVG.
                eb_gid = gid(f"errorbar_{g.label}_{sub.label}")
                for part in (*eb.lines[1], *eb.lines[2]):
                    if part is not None:
                        part.set_gid(eb_gid)
            max_ink = max(max_ink, bar_h + sem)

            if pt_cfg["show"]:
                jw = pt_cfg["jitter_width"]
                for sid, reps in sub.subjects.items():
                    jitter = rng.uniform(-jw, jw, size=len(reps))
                    pc = ax.scatter(
                        np.full(len(reps), x) + jitter, reps,
                        s=pt_cfg["replicate_size"],
                        facecolor=subj_colour[sid], edgecolor="none",
                        alpha=pt_cfg["replicate_alpha"], zorder=2,
                    )
                    pc.set_gid(gid(f"points_replicate_{g.label}_{sub.label}_{sid}"))
                    max_ink = max(max_ink, float(np.max(reps)))

                sx = np.linspace(-jw, jw, len(means)) if len(means) > 1 else np.array([0.0])
                colours = [subj_colour[sid] for sid in sub.subjects.keys()]
                pc2 = ax.scatter(
                    np.full(len(means), x) + sx, means,
                    s=pt_cfg["subject_size"],
                    facecolor=colours, edgecolor="black",
                    linewidth=pt_cfg["subject_edge_width"], zorder=3,
                )
                pc2.set_gid(gid(f"points_subject_{g.label}_{sub.label}"))

    ax.set_xticks(group_centres)
    ax.set_xticklabels([g.label for g in groups])
    ax.set_ylabel(y_label)
    ax.set_ylim(0, max_ink * 1.15)
    ax.yaxis.set_gid(gid("axis_y"))
    ax.xaxis.set_gid(gid("axis_x"))
    if title:
        ax.set_title(title).set_gid(gid("title"))

    if comparisons:
        comps = [
            Comparison(
                x1=float(centres[g1, s1]), x2=float(centres[g2, s2]),
                p=p, data_height=max_ink,
            )
            for (g1, s1, g2, s2, p) in comparisons
        ]
        tops = draw_brackets(ax, comps, lab_style["brackets"], gid_prefix=gid("bracket"))
        if tops:
            ax.set_ylim(0, max(ax.get_ylim()[1], max(tops) * 1.05))


def grouped_bar(
    groups: list[BarGroup],
    *,
    lab_style: LabStyle,
    comparisons: list[tuple[int, int, int, int, float]] | None = None,
    y_label: str = "value",
    title: str | None = None,
    rng_seed: int = 0,
) -> Figure:
    """Build a single-panel grouped bar figure at final mm size."""
    with house_style():
        fig_cfg = lab_style["figure"]
        w_mm, h_mm = fig_cfg["width_mm"], fig_cfg["height_mm"]
        fig = Figure(figsize=(mm(w_mm), mm(h_mm)))
        rect = axes_rect_mm(
            fig_w_mm=w_mm, fig_h_mm=h_mm,
            left_mm=9, bottom_mm=6, right_mm=1.5, top_mm=5,
        )
        ax = fig.add_axes(rect)
        ax.set_gid("axes_main")
        render_grouped_bar_into(
            ax, groups, lab_style=lab_style, comparisons=comparisons,
            y_label=y_label, title=title, rng_seed=rng_seed,
        )
        return fig
