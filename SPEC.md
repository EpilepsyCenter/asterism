# ASTERISM — design spec

A GraphPad Prism replacement scoped to one lab. Not a product, not a Prism clone — a
consumer of data the lab's existing tools already produce, plus a house-style figure
engine.

Status: design agreed, nothing built yet.

> **Starting a new session on this repo?** Read this file first, then start at
> **§13 step 0** — the export-fidelity spike. It is an afternoon of work and it tests
> the assumption everything else depends on. Do not begin the importer before it passes.
>
> Sibling apps referenced throughout live at `~/Software/TRACER`, `~/Software/NED-Net`,
> and `~/Software/GliaAnalysis`. See §2 — the first two are **frozen** and must not be
> modified.

---

## 1. Scope

**In:** paired/unpaired t-tests, one- and two-way ANOVA (incl. repeated measures),
linear regression, correlation, Kolmogorov–Smirnov. Grouped and column bar graphs,
XY plots, frequency distributions. Import from TRACER, NED-Net, QuantStudio, and a
manual template. Publication-quality vector export.

**Out:** general-purpose stats menu, direct-manipulation figure editing, `.pzfx`
import, cross-platform packaging, anything aimed at users outside the lab.

**Assay coverage:** electrophysiology (via TRACER), EEG (via NED-Net), immunostaining
(via GliaAnalysis), qPCR (via QuantStudio export), western blot and other manual
assays (via template).

---

## 2. Hard constraints

- **TRACER and NED-Net are frozen.** No code changes to either. They are relied-upon
  production tools; destabilising them is not an acceptable cost. The new app is a
  pure consumer and does all reconciliation in its own import layer.
- **Harvest by copy, never by dependency.** Useful code in the existing apps is copied
  as a seed and allowed to diverge. No import coupling in either direction.
- **Nothing is inferred silently.** Every guess the importer makes is displayed and
  overridable before it affects an analysis.

---

## 3. Data contract

One canonical long format. Everything upstream converges on this:

```
value | metric | unit | subject | replicate | <factor columns…> | batch | source_file
```

- `subject` — the unit of independence (animal, culture, blot). **Required.**
- `replicate` — cell / ROI / field / well / event, within a subject. Optional.
- `batch` — plate, blot, cohort, session. Optional; usable later as a blocking factor.

`subject` is load-bearing. It drives paired-vs-unpaired detection, repeated-measures
detection, and honest n reporting (`n = 8 animals, 217 cells`). Stats run on subject
means by default.

## 4. Factor model

Factors are **a user-defined list, not named slots.** No built-in `genotype` or
`treatment` fields.

- `factors: [group]` — the default and the common case. One-way.
- `factors: [genotype, treatment]` — opt-in, only for factorial designs.

Design detection keys off the *number and structure* of factor columns, never their
names. A single-factor import requires no annotation step at all.

---

## 5. Import layer

### 5.1 Column inventory
On import, display every column: name, dtype, n unique, sample values, and a guessed
role (pre-filled dropdown, always overridable). Role guesses come from fuzzy matching
against a synonym dictionary:

- `value` ← amp / amplitude / intensity / intden / area / ct / dct / ddct / fold / count / rate
- `subject` ← animal / animal_id / mouse / rat / id / prep / culture / blot
- `replicate` ← cell / cell_id / roi / field / well / event_id / rep
- `group` ← group / group_id / genotype / treatment / condition / tx

Also detect header row and wide-vs-long (multiple numeric columns with short,
low-cardinality, non-numeric headers ⇒ wide; offer to melt).

### 5.2 Level map (optional)
Splits one existing column into multiple factors. Only shown when the user asks for a
second factor. An editable table over the observed unique values:

| group | genotype | treatment |
|---|---|---|
| WT_veh | WT | vehicle |
| KO_CNO | KO | CNO |

Offer "split on delimiter" as a pre-fill, but the table is the source of truth — typed
by the user, so it cannot guess wrong.

### 5.3 Tag map (TRACER only)
TRACER's `group_tags` / `series_specific_tags` are **atomic tag lists**, not delimited
strings, so this is assignment rather than parsing. Show distinct observed tags; user
assigns each to a factor or leaves it unassigned (unassigned tags remain usable as
filters).

### 5.4 Subject map (optional)
A per-project `animals.csv` (`subject, genotype, sex, age_wk, cohort, …`) left-joined
on `subject`. Supplies metadata that no source app exports — TRACER has no sex/age/date
fields, NED-Net has no genotype. Written once per cohort, inherited by every file from
every source app. **This is why no upstream changes are needed.**

### 5.5 Recipes
The confirmed mapping (roles + level map + tag map) is saved keyed on the file's column
signature plus its set of unique level values. Second file from the same experiment
imports with zero clicks. Recipes are small YAML files, version-controlled with the
project.

---

## 6. Source recipes

### TRACER — `cohort_summary.xlsx`
- **`Cells (long)` sheet** is already the target shape:
  `cell_id, animal_id, group, file_name, metric, value`.
  Map `animal_id`→subject, `cell_id`→replicate. Nothing else required.
- `Cells (wide)` also available; carries `group_tags`, `series_specific_tags`,
  `meta.*` columns.
- Per-event sheets: `cell_id, animal_id, group, file_name, event_index, value` —
  use for frequency distributions and KS.
- Note: TRACER's **per-recording CSVs carry no subject identity** (keyed on `file` +
  HEKA tree indices only). Import the cohort export, not the per-recording CSVs.

### NED-Net — `results_graph_data.xlsx` (Results tab)
Three recipes:
1. **`PerAnimal`** — one row per animal, wide across metrics
   (`rate_per_h`, `mean_duration_s`, `conv_rate_per_h`, …). Melt to long,
   `animal`→subject, `group`→group.
   ⚠️ Carries an `excluded` column — respect it and report the count
   ("3 animals excluded per source file"). Never silently drop or include.
2. **`Daily_counts_byGroup` / `Daily_rate_byGroup` / `Circadian_byGroup`** —
   **two-row header** (row 1 = group labels, row 2 = `recording_day` or `hour_of_day`
   then animal IDs). Needs its own recipe. Maps to XY plots, one line per group,
   mean ± SEM.
3. **`ISI_distribution` / `ISI_CDF`** — pre-binned, one column per group. Maps
   directly to the frequency-distribution figure type; `ISI_CDF` pairs with KS.

### QuantStudio — ΔΔCt
Parsing is a standard recipe: skip the metadata preamble by detecting the header row
(the one containing `Well`), then read `Well, Sample Name, Target Name, CT, Ct Mean, Ct SD`.

The ΔΔCt transform ships with the app, as **visible settings with defaults**:

| Setting | Default | Notes |
|---|---|---|
| Undetermined wells | drop | alternative: censor at cycle max (40) |
| Technical replicates | recompute from wells | alternative: use QuantStudio's `Ct Mean` |
| Replicate outlier cutoff | SD > 0.5 → flag | off by default; flag rather than auto-drop |
| Reference gene(s) | one, user-selected | support geometric mean of ≥2 |
| Calibrator | control group mean | computed **within plate** |
| Plate scope | per plate | `plate` becomes a column; never pool ΔΔCt across plates |

Whatever is chosen is recorded in the export's info block.

### Manual assays — template
Normalization is done by the user in Excel beforehand. The app does not attempt it.

- **Sheet 1 (`data`)** — flat rectangle, no preamble:
  `subject, group, value` + optional `replicate` and extra factor columns.
- **Sheet 2 (`info`)** — two columns, `field` / `value`: metric name, unit, free-text
  normalization note, template version.

The normalization note is not verified, only recorded — it travels into the results
block so the methods section stays answerable.

---

## 7. Validation (loud, at import, never at analysis)

Check and display before anything runs:
- missing required columns; unknown/extra columns
- non-numeric values in `value`; `Undetermined`-style sentinel strings
- missing values, and where
- duplicate `subject`+`replicate` keys
- unequal n across groups
- a `subject` present in only one group when the design says paired
- groups with n < 3
- template version older than current

---

## 8. Design detection → test selection

| Design detected | Test |
|---|---|
| 2 levels, one factor, subjects distinct | Welch's t-test (Mann–Whitney if non-normal) |
| 2 levels, one factor, subjects shared | Paired t-test (Wilcoxon signed-rank) |
| ≥3 levels, one factor, distinct | One-way ANOVA → Tukey, or Dunnett vs. control |
| ≥3 levels, one factor, shared | RM one-way ANOVA, Geisser–Greenhouse correction |
| Two factors | Two-way ANOVA; RM on whichever factor shares subjects |
| Numeric x present | Linear regression; Pearson or Spearman |
| Two distributions, no grouping | Two-sample Kolmogorov–Smirnov |

Always display the inferred design and the chosen test; always allow override.
Normality and sphericity checks are advisory flags, not blockers.

**Welch caveat:** Prism defaults to Student's t-test, this defaults to Welch's. The
numbers will differ. Make the choice visible in the output string and document it —
the first unexplained disagreement with a Prism file costs the project its credibility.

---

## 9. Figure layer

Types: grouped bar, column bar, XY, frequency distribution (histogram and cumulative).
Default overlay is **points on bars**; for nested data, subject means as large points
over replicate-level small points, coloured by subject (SuperPlot format, Lord et al.
2020 *J Cell Biol*).

Two layers of customization:

**Lab style file** — version-controlled YAML, set once, inherited by every figure:
bar width, within-group and between-group gaps, edge width, fill alpha, point sizes,
jitter width, point colouring mode, bracket geometry (style, line width, cap length,
height offset, stack gap, label mode, font size), palette, figure dimensions in mm,
font, DPI.

**Per-figure overrides in the UI** — y limits, axis labels, plot type, which comparisons
get brackets, whether points show. Anything overridden on every figure is a signal the
style default is wrong.

Significance brackets are a custom draw function (matplotlib has none). Placement is
automatic: compute significant comparisons, sort spans by width, stack, collision-avoid.

---

## 10. Export

Always emit together:
1. Figure — SVG and PDF (live text, not outlines), plus PNG at configured DPI.
2. Numbers — the underlying values as CSV.
3. Results string — e.g. `F(2,21) = 8.43, p = 0.0021, one-way ANOVA with Tukey's post-hoc`.
4. Info block — n at each level, test chosen, settings used (ΔΔCt params, normalization
   note, style file version, app version).

### 10a. Clipboard is the primary path for single graphs

The real workflow is paste-into-Affinity, not export-then-import. So:

- **"Copy figure" puts vector PDF on the macOS pasteboard** (`NSPasteboardTypePDF` via
  PyObjC), rendered from the same matplotlib figure as the file export — never
  screenshotted from the on-screen preview.
- **Put the PDF flavour on the pasteboard and nothing else.** If a PNG representation is
  also offered "for convenience", some receiving app will eventually prefer it and you
  get a silent rasterisation with no error and no visible symptom until print.
- File export stays canonical for anything going into a manuscript, because the §10b
  QA checks validate files, not pasteboards.
- Verify in the step-0 spike: paste into Affinity, then confirm what landed is vector
  and not a bitmap.

### 10b-pre. Figure sets — the actual answer to multi-panel figures

A finished panel routinely contains ~12 graphs. Exporting or pasting them one at a time
is the real friction, and neither files nor clipboard fixes it at per-graph granularity.

**Figure set export:** select N analyses → **one** PDF/SVG containing all N, each
positioned on a canvas at journal column width (e.g. 180 mm), each an independently
named group (§10b gids), each still at its own exact mm size. Optional auto panel
letters (A, B, C…) in the house style.

One import into Affinity, everything present and pre-arranged in a rough grid, and the
remaining work is nudging rather than assembling. This is cheap to build — it is
explicit axes placement on a larger canvas, which the mm-exact authoring discipline
already requires — and it saves far more time than the clipboard path does.

Do **not** attempt full panel composition (precise alignment, shared legends, cross-panel
annotation). Rough grid plus correct sizes plus named groups is the 90% win; Affinity is
better at the last 10% and people already know how to do it there.

---

## 10b. Export fidelity — hard requirement

**The exported file must open in Affinity essentially final.** If it needs rebuilding
rather than touching up, the tool has failed and has merely replaced Prism's copy-paste
tax with a redraw tax. This constrains the figure layer more than anything else in this
spec.

### Non-negotiable matplotlib settings (bake into the `.mplstyle`)

```
svg.fonttype:        none      # text stays <text>; default 'path' OUTLINES ALL TEXT
pdf.fonttype:        42        # TrueType. Default Type 3 imports badly
ps.fonttype:         42
axes.unicode_minus:  False     # avoid the U+2212 glyph-substitution mess
font.family:         Arial     # or Helvetica. NEVER DejaVu Sans (matplotlib default)
savefig.transparent: True      # composites cleanly over panel backgrounds
```

`svg.fonttype: none` references the font by name rather than embedding it, so the font
must be installed on the machine opening the file. Fine within a lab; note it in the
README.

### Geometry

- **Author at final panel size in millimetres.** `figsize = (w_mm/25.4, h_mm/25.4)`.
  Never draw big and scale down in Affinity — scaling desynchronises line widths and
  font sizes from the journal spec.
- All line widths and font sizes in **points**, correct at 1:1.
- **Position axes explicitly** with `fig.add_axes([...])`. Do *not* use
  `bbox_inches='tight'` — it silently changes the output canvas size, which destroys
  mm-exactness and makes panels from different figures inconsistent.
- **Nothing rasterized.** No `rasterized=True` unless deliberately chosen for a very
  large point cloud, and surfaced in the UI when it happens.

### Named layers

Call `set_gid()` on every artist and artist group — `bars_WT`, `points_subject_KO`,
`bracket_1`, `errorbar_WT`, `axis_y`. matplotlib writes gids through as SVG element ids,
so they arrive in Affinity as **named, selectable objects** instead of anonymous nested
groups. This is the single highest-leverage thing for a touch-up workflow and it is
almost free.

Honest caveat: matplotlib SVG is still nested-group-heavy even with gids. It will not be
as clean as hand-authored SVG, and expect to ungroup once on arrival.

### Automated export QA

Run against a reference figure in CI — cheap, and catches silent regressions when a
matplotlib version or a style edit breaks one of the settings above:

- parse the exported SVG; assert `<text>` elements are present and non-zero
- assert **no `<image>` elements** (nothing was rasterized)
- assert canvas width/height match the requested mm within tolerance
- assert the expected `gid`s are present

---

## 11. Stack

- Core: plain Python package, **zero UI imports**. Functions in, figure + results object out.
- Stats: `pingouin` (t-tests, RM/mixed ANOVA, post-hocs with p-adjustment, effect sizes,
  normality, sphericity), `scipy.stats` (KS), `statsmodels` (`MixedLM` for nested models).
- Figures: `matplotlib`, house style in a `.mplstyle` + the YAML above.
- UI: **Dash + pywebview desktop shell**, following the NED-Net / GliaAnalysis pattern.
  Copy their app skeleton wholesale — `server_state.py` session store, `components.py`
  (`alert`, `metric_card`), `desktop.py` pywebview launcher, the `--ned-*` CSS token
  set, sidebar layout, native folder/file pickers, `Start … (Native)` launcher scripts.

**Why Dash over Marimo/Streamlit:** the lab already runs two apps in this exact idiom,
so there is no new UI vocabulary for anyone to learn and the "how does a biologist launch
this" problem is already solved with working code. Dash also has a higher layout ceiling
(React underneath, arbitrary CSS) which matters for the figure customization panel, and
it adds no new dependency family to a project where bus factor is a stated risk.

Marimo's reactivity is genuinely nicer than Dash callbacks, and it would be the right
call if the primary users were code-comfortable and wanted to drop into Python
mid-analysis. That is not the requirement here.

**Why not Electron, like TRACER?** Considered and rejected, but it is a close call.
TRACER's architecture is justified by TRACER's complexity — 15 analysis windows,
interactive trace viewing, manual event curation, cross-window state sync. This app is
import → map → test → plot → export, roughly a tenth the surface area, and most
interaction is dropdowns over a static image. Electron costs two languages and two
build systems (PyInstaller + electron-builder), and means a future maintainer needs
React, TypeScript, Python *and* the packaging pipeline rather than just Python.

The one real thing Electron buys is that direct figure manipulation (dragging brackets,
nudging legends) stays possible. Dash closes that door. That is an acceptable loss only
because final polish is expected to happen in Illustrator — the same workflow already
used for Prism figures.

**Flip to Electron if:** (a) this app is meant to eventually absorb TRACER's cohort
module and become the lab's primary analysis surface, so architectural consistency pays
back; or (b) the author is realistically the sole maintainer indefinitely and is already
fluent in the TRACER stack, which largely negates the bus-factor argument.

**Do not** mix renderers — e.g. Plotly for an interactive preview plus matplotlib for
export. Two rendering paths that must agree is how the preview stops matching the
exported file, which is the same trust failure this spec is built to avoid.

Keeping the core UI-free is what makes this reversible — and makes the golden-dataset
tests possible.

All three existing apps are Python, so a shared pip package would be *possible* — but
see the frozen-app constraint. Copy, don't couple.

---

## 12. Harvest list

GliaAnalysis is the closest existing implementation of this app — it already does
per-cell → per-animal aggregation, pingouin stats with an LMM path, group/split/
replicate-unit selection, and Prism-ready export. Treat it as the reference build.

| From | What | Path |
|---|---|---|
| GliaAnalysis | **whole Dash app skeleton** — session store, shared components, pywebview launcher | `glia_dash/server_state.py`, `components.py`, `desktop.py` |
| GliaAnalysis | design system — CSS tokens, sidebar layout, native pickers | `glia_dash/assets/style.css` |
| GliaAnalysis | pingouin + statsmodels stats layer, LMM path, post-hocs, per-animal aggregation | `glia/stats.py` |
| GliaAnalysis | group / split / replicate-unit selection UI | `glia_dash/pages/explore.py`, `pages/stats.py` |
| GliaAnalysis | `info` sheet convention for run metadata | `glia_dash/exporters.py` |
| TRACER | matplotlib figure rendering to SVG/PDF/PNG | `backend/export/trace_export.py:302` (`render_to_bytes`) |
| TRACER | cohort graph construction | `backend/api/cohort.py`, `CohortWindow.tsx` |

Copy as seed code. Do not create an import dependency in either direction.

---

## 13. Build order

0. **Export fidelity spike, before anything else.** Hand-build one representative
   grouped bar figure with points and brackets, then check three things in Affinity:
   (a) the exported file needs only touch-up, not rebuilding; (b) a pasted copy arrives
   as vector, not a bitmap; (c) a two-panel figure-set file imports as separate named
   groups at correct mm sizes. This is the assumption the whole project rests on
   (§10a–10b) and it is testable in an afternoon. If matplotlib can't clear this bar,
   that changes the stack decision, not the schedule.
1. Data contract + validation + design detection (pure functions, unit-testable).
2. Importer: column inventory, role assignment, recipes. Test against one real
   `cohort_summary.xlsx` and one real `results_graph_data.xlsx` — between them they
   exercise the long-format path, the two-row-header path, and the tag-to-factor path.
3. Stats core, seeded from `glia/stats.py`.
4. **Golden-dataset tests**: a handful of datasets already analysed in Prism, with
   Prism's output as expected values, in CI. Build this early — it is what makes the
   tool trustworthy when its numbers are questioned.
5. Figure layer + style file, seeded from TRACER's renderer.
6. Marimo UI.
7. Level map / subject map / tag map.
8. QuantStudio ΔΔCt + manual template.

---

## 14. Open

- Normalization for manual assays: **resolved** — user does it in Excel, app records
  the note only.
- Whether qPCR also goes through the manual template rather than QuantStudio parsing:
  **resolved** — build the QuantStudio ΔΔCt path, exports are consistent enough.
- Adoption risk: v1 must do one thing dramatically faster than Prism, or it won't get
  used. Most likely candidate: TRACER cohort export → finished figure in one step.
- Bus factor: keep it boring. Pure Python, no build step, pinned deps, README a
  first-year can follow, on the lab GitHub rather than one laptop.
