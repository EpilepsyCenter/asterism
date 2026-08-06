"""Data-driven figure builders (SPEC §9).

Turns a `Dataset` (+ optional `StatResult`) into a house-styled, Affinity-ready
figure. This is the layer on top of the step-0 rendering primitives (`figures.py`,
`brackets.py`): it decides the figure shape from the data, builds the SuperPlot
nesting, and — crucially — draws significance brackets from the *actual* post-hoc
p-values in the StatResult, not hand-typed numbers.

Figure types (§9): column bar (one factor), grouped bar (two factors), XY (numeric x,
one line per group, mean ± SEM), frequency distribution (histogram or cumulative).

Per-figure overrides (§9) live in `FigureOverrides`: y-limits, axis labels, whether
points show, which comparisons get brackets, bracket label mode. Anything overridden
on every figure is a signal the lab-style default is wrong.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .contract import SUBJECT, VALUE, Dataset
from .figures import (BarGroup, SubGroup, _slot_positions, grouped_bar)
from .stats import StatResult
from .style import LabStyle, axes_rect_mm, house_style, mm


@dataclass
class FigureOverrides:
    """Per-figure UI overrides (SPEC §9). None = fall back to the lab-style default."""

    title: str | None = None
    x_label: str | None = None
    y_label: str | None = None
    y_limits: tuple[float, float] | None = None
    show_points: bool | None = None
    bracket_comparisons: list[tuple[str, str]] | None = None   # explicit pairs to bracket
    bracket_label_mode: str | None = None                       # 'stars' | 'p_value'
    plot_kind: str | None = None                                # override auto choice


# ---------------------------------------------------------------------------
# Data → bar structure.
# ---------------------------------------------------------------------------

def _metric_frame(ds: Dataset, metric: str | None) -> pd.DataFrame:
    frame = ds.frame
    if "metric" in frame.columns:
        metrics = frame["metric"].dropna().unique().tolist()
        if metric is None:
            if len(metrics) > 1:
                raise ValueError(f"Dataset carries {len(metrics)} metrics; pass metric=.")
            metric = metrics[0] if metrics else None
        if metric is not None:
            frame = frame[frame["metric"] == metric]
    return frame


def _subjects_dict(cell: pd.DataFrame) -> dict:
    """subject id -> array of that subject's raw (replicate) values."""
    out: dict[str, np.ndarray] = {}
    if SUBJECT not in cell.columns:
        out["all"] = cell[VALUE].dropna().to_numpy()
        return out
    for sid, g in cell.groupby(SUBJECT):
        vals = g[VALUE].dropna().to_numpy()
        if len(vals):
            out[str(sid)] = vals
    return out


def dataset_to_bargroups(ds: Dataset, *, metric: str | None = None) -> list[BarGroup]:
    """Build the bar structure from a long-format Dataset (SPEC §9).

    0/1 factor → column bar (one cluster per level, single bar each).
    2 factors  → grouped bar (outer factor = clusters, inner factor = bars).
    Each SubGroup carries per-subject replicate arrays so the renderer can draw the
    SuperPlot (subject means over replicate clouds).
    """
    frame = _metric_frame(ds, metric)
    factors = [f for f in ds.factors if f in frame.columns]

    if not factors:
        return [BarGroup("all", [SubGroup("", _subjects_dict(frame))])]

    if len(factors) == 1:
        f = factors[0]
        return [
            BarGroup(str(lv), [SubGroup("", _subjects_dict(frame[frame[f] == lv]))])
            for lv in sorted(frame[f].dropna().unique(), key=str)
        ]

    outer, inner = factors[0], factors[1]
    groups: list[BarGroup] = []
    inner_levels = sorted(frame[inner].dropna().unique(), key=str)
    for olv in sorted(frame[outer].dropna().unique(), key=str):
        subs = [
            SubGroup(str(ilv),
                     _subjects_dict(frame[(frame[outer] == olv) & (frame[inner] == ilv)]))
            for ilv in inner_levels
        ]
        groups.append(BarGroup(str(olv), subs))
    return groups


# ---------------------------------------------------------------------------
# Stats → brackets.
# ---------------------------------------------------------------------------

def _find_bar(groups: list[BarGroup], name: str) -> list[tuple[int, int]]:
    """All (group_idx, subgroup_idx) whose cluster or bar label matches `name`."""
    hits: list[tuple[int, int]] = []
    for gi, g in enumerate(groups):
        if str(g.label) == str(name):
            hits.extend((gi, si) for si in range(len(g.subgroups)))
        else:
            hits.extend((gi, si) for si, s in enumerate(g.subgroups)
                        if str(s.label) == str(name))
    return hits


def comparisons_from_stat(
    stat: StatResult | None,
    groups: list[BarGroup],
    overrides: FigureOverrides | None = None,
) -> list[tuple[int, int, int, int, float]]:
    """Translate a StatResult's significant comparisons into bar-coordinate brackets.

    Default: bracket the post-hoc pairs with p < 0.05 (or, for a two-group test with
    no post-hoc, the single overall comparison if significant). An explicit
    `overrides.bracket_comparisons` list forces exactly those pairs regardless of
    significance (SPEC §9: which comparisons get brackets is a per-figure choice).
    """
    if stat is None:
        return []
    ov = overrides or FigureOverrides()
    pmap = {frozenset((str(ph["a"]), str(ph["b"]))): ph.get("p")
            for ph in (stat.posthoc or [])}

    pairs: list[tuple[str, str, float]] = []
    if ov.bracket_comparisons:
        for a, b in ov.bracket_comparisons:
            p = pmap.get(frozenset((str(a), str(b))))
            if p is None:
                p = stat.p if stat.p is not None else 1.0
            pairs.append((a, b, p))
    elif stat.posthoc:
        for ph in stat.posthoc:
            if ph.get("p") is not None and ph["p"] < 0.05:
                pairs.append((ph["a"], ph["b"], ph["p"]))
    elif stat.p is not None and stat.p < 0.05 and len(groups) == 2:
        pairs.append((str(groups[0].label), str(groups[1].label), stat.p))

    out: list[tuple[int, int, int, int, float]] = []
    for a, b, p in pairs:
        ca, cb = _find_bar(groups, a), _find_bar(groups, b)
        if not ca or not cb:
            continue  # can't place this bracket (e.g. ambiguous 2-way term) — skip
        (g1, s1), (g2, s2) = ca[0], cb[0]
        out.append((g1, s1, g2, s2, float(p)))
    return out


# ---------------------------------------------------------------------------
# Public builders.
# ---------------------------------------------------------------------------

def _style_with_overrides(lab_style: LabStyle, ov: FigureOverrides) -> LabStyle:
    raw = lab_style.raw
    if ov.show_points is not None:
        raw = {**raw, "points": {**raw["points"], "show": ov.show_points}}
    if ov.bracket_label_mode is not None:
        raw = {**raw, "brackets": {**raw["brackets"], "label_mode": ov.bracket_label_mode}}
    return LabStyle(raw=raw)


def bar_figure(
    ds: Dataset,
    stat: StatResult | None = None,
    *,
    lab_style: LabStyle,
    metric: str | None = None,
    overrides: FigureOverrides | None = None,
):
    """Column or grouped bar with SuperPlot points and stats-driven brackets (§9)."""
    ov = overrides or FigureOverrides()
    groups = dataset_to_bargroups(ds, metric=metric)
    comparisons = comparisons_from_stat(stat, groups, ov)
    style = _style_with_overrides(lab_style, ov)
    y_label = ov.y_label if ov.y_label is not None else (metric or "value")
    fig = grouped_bar(groups, lab_style=style, comparisons=comparisons,
                      y_label=y_label, title=ov.title)
    ax = fig.axes[0]
    if ov.y_limits is not None:
        ax.set_ylim(*ov.y_limits)
    if ov.x_label is not None:
        ax.set_xlabel(ov.x_label)
    return fig


def _new_axes(lab_style: LabStyle, *, left=13.0, bottom=9.0, right=2.0, top=5.0):
    fig_cfg = lab_style["figure"]
    w_mm, h_mm = fig_cfg["width_mm"], fig_cfg["height_mm"]
    from matplotlib.figure import Figure
    fig = Figure(figsize=(mm(w_mm), mm(h_mm)))
    rect = axes_rect_mm(fig_w_mm=w_mm, fig_h_mm=h_mm,
                        left_mm=left, bottom_mm=bottom, right_mm=right, top_mm=top)
    ax = fig.add_axes(rect)
    ax.set_gid("axes_main")
    return fig, ax


def _gid_errorbar(container, gid: str) -> None:
    for part in (*container.lines[1], *container.lines[2]):
        if part is not None:
            part.set_gid(gid)


def xy_figure(
    ds: Dataset,
    *,
    lab_style: LabStyle,
    metric: str | None = None,
    overrides: FigureOverrides | None = None,
):
    """XY plot: numeric x vs value, one line per group, mean ± SEM across subjects (§9)."""
    ov = overrides or FigureOverrides()
    if ds.x is None:
        raise ValueError("xy_figure needs a numeric x column (ds.x).")
    frame = _metric_frame(ds, metric)
    x = ds.x
    factors = [f for f in ds.factors if f in frame.columns]
    group_col = factors[0] if factors else None
    pal = lab_style["palette"]

    with house_style():
        fig, ax = _new_axes(lab_style)
        levels = ([None] if group_col is None
                  else sorted(frame[group_col].dropna().unique(), key=str))
        for i, gv in enumerate(levels):
            sub = frame if gv is None else frame[frame[group_col] == gv]
            # subject means first (one value per subject per x), then mean ± SEM across subjects
            per = sub.groupby([SUBJECT, x], dropna=False)[VALUE].mean().reset_index()
            agg = (per.groupby(x)[VALUE].agg(["mean", "sem"]).reset_index()
                   .sort_values(x))
            colour = pal[i % len(pal)]
            eb = ax.errorbar(agg[x], agg["mean"], yerr=agg["sem"].fillna(0),
                             marker="o", ms=3, lw=1.0, color=colour, capsize=2,
                             capthick=0.75, label=(str(gv) if gv is not None else None))
            gid = f"xy_{gv}" if gv is not None else "xy"
            if eb.lines[0] is not None:
                eb.lines[0].set_gid(gid)
            _gid_errorbar(eb, f"{gid}_err")

        ax.set_xlabel(ov.x_label if ov.x_label is not None else x)
        ax.set_ylabel(ov.y_label if ov.y_label is not None else (metric or "value"))
        ax.xaxis.set_gid("axis_x")
        ax.yaxis.set_gid("axis_y")
        if group_col is not None:
            leg = ax.legend(frameon=False, fontsize=6)
            leg.set_gid("legend")
        if ov.title:
            ax.set_title(ov.title).set_gid("title")
        if ov.y_limits is not None:
            ax.set_ylim(*ov.y_limits)
        return fig


def frequency_figure(
    ds: Dataset,
    *,
    lab_style: LabStyle,
    metric: str | None = None,
    kind: str = "cumulative",
    bins: int = 30,
    overrides: FigureOverrides | None = None,
):
    """Frequency distribution: 'histogram' or 'cumulative' (ECDF), one series per
    group (SPEC §9). Cumulative pairs with the KS test (§8)."""
    ov = overrides or FigureOverrides()
    frame = _metric_frame(ds, metric)
    factors = [f for f in ds.factors if f in frame.columns]
    group_col = factors[0] if factors else None
    pal = lab_style["palette"]

    values_by_group: dict = {}
    if group_col is None:
        values_by_group["all"] = frame[VALUE].dropna().to_numpy()
    else:
        for lv in sorted(frame[group_col].dropna().unique(), key=str):
            values_by_group[str(lv)] = frame.loc[frame[group_col] == lv, VALUE].dropna().to_numpy()

    all_vals = np.concatenate([v for v in values_by_group.values() if len(v)]) \
        if any(len(v) for v in values_by_group.values()) else np.array([0.0, 1.0])
    edges = np.linspace(float(np.min(all_vals)), float(np.max(all_vals)), bins + 1)

    with house_style():
        fig, ax = _new_axes(lab_style)
        for i, (gname, vals) in enumerate(values_by_group.items()):
            colour = pal[i % len(pal)]
            if len(vals) == 0:
                continue
            if kind == "cumulative":
                xs = np.sort(vals)
                ys = np.arange(1, len(xs) + 1) / len(xs)
                line, = ax.step(xs, ys, where="post", lw=1.0, color=colour,
                                label=gname)
                line.set_gid(f"ecdf_{gname}")
            else:  # histogram (density), step outline so it stays clean vector
                counts, _ = np.histogram(vals, bins=edges, density=True)
                centres = (edges[:-1] + edges[1:]) / 2
                line, = ax.step(centres, counts, where="mid", lw=1.0, color=colour,
                                label=gname)
                line.set_gid(f"hist_{gname}")

        ax.set_xlabel(ov.x_label if ov.x_label is not None else (metric or "value"))
        default_y = "cumulative probability" if kind == "cumulative" else "density"
        ax.set_ylabel(ov.y_label if ov.y_label is not None else default_y)
        ax.xaxis.set_gid("axis_x")
        ax.yaxis.set_gid("axis_y")
        if group_col is not None:
            ax.legend(frameon=False, fontsize=6).set_gid("legend")
        if ov.title:
            ax.set_title(ov.title).set_gid("title")
        if ov.y_limits is not None:
            ax.set_ylim(*ov.y_limits)
        return fig
