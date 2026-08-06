#!/usr/bin/env python3
"""ASTERISM step-0 export-fidelity spike (SPEC §13 step 0).

Builds one representative grouped bar figure (nested points + brackets), a two-
panel figure set, exports the canonical trio, runs the §10b QA assertions, and
puts a vector PDF on the macOS pasteboard. Then you check three things in Affinity
(SPEC §13):

  (a) the exported file needs only touch-up, not rebuilding
  (b) a pasted copy arrives as vector, not a bitmap
  (c) the figure-set file imports as separate named groups at correct mm sizes

If matplotlib can't clear this bar, that changes the stack decision, not the
schedule. Run:  python spike.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

from asterism.core.export import export_all, render_to_bytes
from asterism.core.figure_set import Panel, figure_set
from asterism.core.figures import BarGroup, SubGroup, grouped_bar
from asterism.core.qa import check_svg
from asterism.core.style import LabStyle

OUT = Path(__file__).resolve().parent / "spike_out"


def make_subgroup(label: str, n_subjects: int, n_reps: int, mean: float, sd: float,
                  subj_spread: float, prefix: str, rng) -> SubGroup:
    """Nested data: each subject has a true mean drawn around `mean`, and
    `n_reps` replicates scattered around that subject mean (SuperPlot shape)."""
    subjects = {}
    for s in range(n_subjects):
        subj_mean = rng.normal(mean, subj_spread)
        reps = rng.normal(subj_mean, sd, size=n_reps)
        subjects[f"{prefix}{s+1}"] = np.clip(reps, 0, None)
    return SubGroup(label=label, subjects=subjects)


def build_dataset(rng) -> list[BarGroup]:
    """Grouped design: genotype (WT/KO) × treatment (veh/CNO), nested cells."""
    wt = BarGroup("WT", [
        make_subgroup("veh", 6, 15, 10.0, 2.5, 1.2, "wt_v_a", rng),
        make_subgroup("CNO", 6, 15, 11.5, 2.6, 1.3, "wt_c_a", rng),
    ])
    ko = BarGroup("KO", [
        make_subgroup("veh", 6, 15, 10.2, 2.5, 1.2, "ko_v_a", rng),
        make_subgroup("CNO", 6, 15, 16.0, 3.0, 1.6, "ko_c_a", rng),
    ])
    return [wt, ko]


def main() -> int:
    lab = LabStyle.load()
    OUT.mkdir(exist_ok=True)

    # --- Single-panel figure --------------------------------------------------
    rng = np.random.default_rng(42)
    groups = build_dataset(rng)
    # Bracket the two comparisons that would come back significant: WT veh vs
    # KO CNO (wide) and KO veh vs KO CNO (narrow) — exercises stacking.
    comparisons = [
        (1, 0, 1, 1, 0.0008),   # KO veh vs KO CNO   (narrow)
        (0, 1, 1, 1, 0.012),    # WT CNO vs KO CNO   (medium)
        (0, 0, 1, 1, 0.0003),   # WT veh vs KO CNO   (widest)
    ]
    fig = grouped_bar(
        groups, lab_style=lab, comparisons=comparisons,
        y_label="mEPSC amplitude (pA)", title="Grouped bar (SuperPlot)",
    )
    paths = export_all(fig, OUT / "single_panel", dpi=lab["figure"]["dpi"])
    print("Single-panel exported:")
    for fmt, p in paths.items():
        print(f"   {fmt.upper():4} {p}  ({p.stat().st_size:,} bytes)")

    # QA the single-panel SVG.
    expected_gids = [
        "axes_main", "bar_WT_veh", "bar_KO_CNO",
        "points_subject_KO_CNO", "errorbar_WT_CNO",
        "bracket_0_line", "bracket_0_label", "axis_y",
    ]
    rep = check_svg(
        paths["svg"].read_bytes(),
        expected_w_mm=lab["figure"]["width_mm"],
        expected_h_mm=lab["figure"]["height_mm"],
        expected_gids=expected_gids,
    )
    print("\nSingle-panel export QA:")
    print(rep.summary())
    single_ok = rep.ok

    # --- Two-panel figure set -------------------------------------------------
    rng2 = np.random.default_rng(7)
    groups_b = build_dataset(rng2)
    panels = [
        Panel(groups, width_mm=lab["figure"]["width_mm"],
              height_mm=lab["figure"]["height_mm"],
              comparisons=comparisons, y_label="mEPSC amplitude (pA)",
              title="Amplitude", rng_seed=1),
        Panel(groups_b, width_mm=55, height_mm=42,
              comparisons=[(1, 0, 1, 1, 0.02)], y_label="frequency (Hz)",
              title="Frequency", rng_seed=2),
    ]
    fset = figure_set(panels, lab_style=lab)
    fset_paths = export_all(fset, OUT / "figure_set", dpi=lab["figure"]["dpi"])
    print("\nFigure-set exported:")
    for fmt, p in fset_paths.items():
        print(f"   {fmt.upper():4} {p}  ({p.stat().st_size:,} bytes)")

    # Canvas must be journal column width; panels keep their own gids/groups.
    col_w = lab["figure_set"]["column_width_mm"]
    svg_root = fset_paths["svg"].read_bytes()
    import re
    m = re.search(rb'height="([0-9.]+)pt"', svg_root)
    canvas_h_mm = float(m.group(1)) / 72.0 * 25.4 if m else 0.0
    fset_rep = check_svg(
        svg_root,
        expected_w_mm=col_w,
        expected_h_mm=canvas_h_mm,   # height is packed, so read it back
        expected_gids=["panel_A", "panel_B", "panel_letter_A", "panel_letter_B",
                       "A_bar_WT_veh", "B_bar_KO_CNO"],
    )
    print("\nFigure-set export QA:")
    print(fset_rep.summary())
    fset_ok = fset_rep.ok

    # --- Clipboard (macOS pasteboard, PDF only) -------------------------------
    clip_ok = False
    try:
        from asterism.core.clipboard import copy_figure_to_pasteboard, pasteboard_flavours
        count = copy_figure_to_pasteboard(fig)
        flavours = pasteboard_flavours()
        pdf_only = any("pdf" in f.lower() for f in flavours) and not any(
            "png" in f.lower() or "tiff" in f.lower() for f in flavours
        )
        print(f"\nClipboard: wrote PDF to pasteboard (changeCount={count})")
        print(f"   flavours on pasteboard: {flavours}")
        print(f"   PDF-only (no raster flavour): {pdf_only}")
        clip_ok = pdf_only
    except Exception as exc:  # noqa: BLE001
        print(f"\nClipboard: SKIPPED ({exc})")

    # --- Verdict --------------------------------------------------------------
    print("\n" + "=" * 60)
    print("STEP-0 SPIKE RESULT")
    print(f"  single-panel QA : {'PASS' if single_ok else 'FAIL'}")
    print(f"  figure-set QA   : {'PASS' if fset_ok else 'FAIL'}")
    print(f"  clipboard PDF   : {'PASS' if clip_ok else 'SKIP/FAIL'}")
    print("=" * 60)
    print(f"\nNow open {OUT}/single_panel.pdf and figure_set.pdf in Affinity")
    print("and confirm (a) touch-up-only, (b) pasted copy is vector, (c) named groups.")

    return 0 if (single_ok and fset_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
