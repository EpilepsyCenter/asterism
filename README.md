# ASTERISM

A GraphPad Prism replacement scoped to one lab. See [`SPEC.md`](SPEC.md) for the full design.

## Status

- **Step 0 — export-fidelity spike:** built, passing, and verified in Affinity (SPEC §10a–10b).
- **Step 1 — data contract + validation + design detection:** built, pure/unit-tested
  (`core/contract.py`, `validation.py`, `design.py`; SPEC §3–4, §7–8).
- **Step 2 — importer:** built, unit-tested against synthetic files that reproduce the
  frozen apps' export writers (`core/importer/`; SPEC §5–6). Exercises the long-format,
  wide-melt, two-row-header, and tag-to-factor paths. A real export is the final
  acceptance check, not a prerequisite.

Next: SPEC §13 step 3 (stats core, seeded from `glia/stats.py`) then step 4
(golden-dataset tests vs Prism).

## Running the spike

```bash
pip install -r requirements.txt
python spike.py            # builds figures, exports, runs QA, copies PDF to clipboard
pytest tests/ -q          # the CI half of the fidelity checks
```

`spike.py` writes to `spike_out/`:

| file | what |
|---|---|
| `single_panel.{svg,pdf,png}` | one grouped bar: SuperPlot nested points + stacked significance brackets |
| `figure_set.{svg,pdf,png}` | two panels on a 180 mm journal-column canvas, each at its own mm size, named groups, auto letters |

It also puts a **vector PDF on the macOS pasteboard** (PDF flavour only).

## What the spike proved (the machine half)

- `svg.fonttype: none` → text stays live `<text>`, not outlined to `<path>`.
- `pdf.fonttype: 42` → TrueType (`CIDFontType2`), **no Type 3** (Type 3 imports badly).
- No `<image>` elements — nothing silently rasterized.
- Canvas is **mm-exact** (45×40 mm single panel; 180 mm-wide figure set) — achieved by
  explicit `add_axes` placement and **never** `bbox_inches='tight'`.
- `set_gid` names survive into the SVG as selectable `<g id="…">` groups; figure-set
  panels arrive as independently named groups (`panel_A`, `panel_B`) at correct mm sizes.
- Clipboard carries **PDF only** — no PNG/TIFF flavour that a receiving app could
  silently prefer and rasterize.

### The one non-obvious trap (now guarded)

`savefig` reads the font-embedding rcParams (`svg.fonttype`, `pdf.fonttype`) at **save**
time, not at figure-build time. Building under the house style but saving outside it
silently outlines all text. Export therefore runs *inside* the house-style context; the
`test_svg_text_stays_live` CI test guards the regression.

## What you still have to check by hand (the human half, SPEC §13)

Open `spike_out/single_panel.pdf` and `figure_set.pdf` in Affinity and confirm:

1. **(a)** the file needs only touch-up, not rebuilding;
2. **(b)** a copy pasted from `spike.py`'s clipboard write arrives as **vector**, not a bitmap;
3. **(c)** the figure-set file imports as **separate named groups at correct mm sizes**.

If matplotlib clears this bar, the stack decision (§11) holds and the build proceeds to
SPEC §13 step 1. If it can't, that changes the stack, not the schedule.

## Platform note — clipboard is macOS-only

"Copy figure" (vector PDF straight onto the pasteboard, SPEC §10a) is **macOS-only**.
Windows has no native PDF clipboard flavour, and an EMF-based equivalent was considered
and **dropped** (external converter dependency + untestable clipboard path weren't worth
it). **Windows users take the file-export path instead** (SPEC §10, SVG/PDF), which is
fully cross-platform. Everything else — figures, figure sets, export, QA — runs anywhere.

## Font caveat (SPEC §10b)

`svg.fonttype: none` references the font **by name** rather than embedding it, so **Arial
or Helvetica must be installed on any machine that opens these files.** Fine within the
lab. Both were present on the machine the spike was built on.

## Layout

```
asterism/
  core/            # UI-free by contract (SPEC §11): pure functions, no Dash imports
    contract.py    #   canonical long-format data contract + subject logic (§3–4)
    validation.py  #   loud import-time validation checks (§7)
    design.py      #   design detection → test selection (§8)
    importer/      #   import layer (§5–6): pure functions, no UI
      roles.py     #     synonym-dictionary role guessing (§5.1)
      inventory.py #     column inventory + header/wide-long detection (§5.1)
      reshape.py   #     melt, two-row-header parse, tag explode/assign (§5.2–5.3, §6)
      recipes.py   #     confirmed-mapping recipes, YAML, signature reuse (§5.5)
      sources.py   #     TRACER + NED-Net source recipes, by header signature (§6)
    style.py       #   .mplstyle + lab YAML loading, mm→fraction geometry helpers
    figures.py     #   grouped bar builder (SuperPlot nesting), gids on every artist
    brackets.py    #   significance brackets: auto stacking + collision avoidance
    figure_set.py  #   multi-panel figure sets on a journal-column canvas
    export.py      #   SVG/PDF/PNG — no bbox_inches='tight'
    clipboard.py   #   macOS pasteboard, PDF-flavour-only
    qa.py          #   the export-fidelity assertions
  assets/
    asterism.mplstyle   # the non-negotiable settings
    lab_style.yaml      # version-controlled house style (SPEC §9)
spike.py           # the step-0 runner
tests/             # the CI half of the QA
```
