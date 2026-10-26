# ASTERISM

Scientific graphing and statistics that does what GraphPad Prism does (live-linked data
tables, analyses, graphs and layouts, with Prism's options and numbers) in ASTERISM's own
interface. A native desktop app (Qt / PySide6) that shares its look with NED-Net. Free for
labs; not affiliated with GraphPad.

The design, principles and build order are in [`SPEC.md`](SPEC.md). Start there.

## Status

- **M0 — Qt spike:** done. Native window, Navigator, Column table, scatter graph with
  Format Graph / Format Axes dialogs, t tests, PDF/SVG export that passes the fidelity QA.
- **M1 — Foundation:** done. Real package layout, UI-free document model with its own undo
  stack, `.asterism` project files (save, save as, open, revert, recent files), edited
  state in the title bar, save prompts on close, files opened from the command line and
  Finder.
- **M1b — Own interface:** done. NED-Net window structure (resizable project sidebar with
  linked sheets nested under their table, top bar with project-wide tools, resizable tool
  panel on the right), dialogs with a section sidebar, one Format Graph dialog, our own
  wording throughout (including results sheets).
- **M2 — Data tables:** done. All eight table types with every entry format (replicates,
  mean/SD/N and friends), row titles, excluded values, insert/delete rows and data sets,
  New Table dialog and start screen, Table Format dialog; file format v2.
- **M3 — Column analyses and graphs:** done. Normality tests and frequency distributions
  match Prism exactly on real lab data; one-way ANOVA family with ten multiple-comparison
  methods; one-sample tests, outliers; violin, before-after, floating bars and more, with
  a Graph Type gallery and stacked significance brackets.
- **M4 — Grouped and nested:** done. Two-way ANOVA (ordinary and matched) and multiple
  t / Mann-Whitney tests match Prism exactly on real lab data; nested t test and nested
  one-way ANOVA; grouped bars (side by side, separated, stacked), connected means, heat
  maps, legends, nested scatter and SuperPlots.
- **M5 — XY:** done. Linear regression and Spearman correlation match Prism exactly on real
  lab data; nonlinear regression with 30 models, global fits, model comparison,
  profile-likelihood intervals and ROUT (checked against R); area under the curve; XY graphs
  with fitted curves and bands; frequency-distribution histograms.
- **M6 — Contingency, survival, parts of whole:** done. Fisher's exact test matches Prism on
  real lab data; chi-square and trend tests, relative risk, odds ratio and diagnostic measures
  with Prism's recommended intervals (checked against R); Kaplan-Meier, log-rank,
  Gehan-Breslow-Wilcoxon and hazard ratios (checked against R and SAS); fraction of total;
  contingency bars, survival curves, pie and donut charts.
- **M7 — Transforms and result tables:** done. Transform, normalize, remove baseline, prune,
  transpose, smooth/differentiate/integrate, residual plots; result tables are live and can be
  graphed and analysed further in chains. Also observed vs. expected and McNemar's test.
- **M8 — Figures:** done. Pages of live panels (graphs, tables, results, text) with automatic
  panel letters, snapping, alignment and grid arrangement; export at exact page size to SVG,
  PDF, PNG and TIFF with every panel as its own group.
- **Next — M9:** graph polish (colour schemes, copy formatting, drawing tools, right Y axis,
  axis breaks, significance-bracket formatting).

## Run

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # first time
./start-asterism.sh                     # or: .venv/bin/python -m asterism [file.asterism]
```

On macOS you can also double-click `Start ASTERISM.command`.

## Test

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m asterism --shots /tmp/asterism-shots    # screenshot tour for visual review
```

- `tests/doc/`: document model, undo, project files (no Qt).
- `tests/app/`: the desktop app, offscreen.
- `tests/test_golden.py`: statistics checked against real Prism output. The Prism projects
  they were extracted from stay local in `sample_data/` (gitignored).

## Layout

| Path | What |
|---|---|
| `asterism/core/` | statistics executors, lab importers, validation, export QA (no Qt) |
| `asterism/doc/` | document model, graph specs, undo stack, `.asterism` file format (no Qt) |
| `asterism/analysis/` | analysis registry: analyses → Prism-style result pages (no Qt) |
| `asterism/app/` | the PySide6 app: window, project sidebar, top bar and tool panel, sheets, dialogs, graph canvas, export, theme |

Graph text uses Arial by default and stays live text in exported PDF/SVG, so the font must
be installed on the machine that opens the file.
