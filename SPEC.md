# ASTERISM — design spec

A desktop app for scientific graphing and statistics that does what **GraphPad Prism 11**
does (projects of live-linked data tables, analyses, graphs and figures, with Prism's
table types, analyses, options and numbers) in **ASTERISM's own interface**, a sibling
of NED-Net. Built with Qt (PySide6).

Status: **M1–M11 done; 0.1.1 was the first release, 0.1.2 is current (macOS, Windows, Linux).** The Qt spike (M0) passed on
2026-10-22.

> **Starting a new session on this repo?** Read this file, then check §15 for the current
> milestone and its acceptance list. Run the app with `./start-asterism.sh` and the tests
> with `.venv/bin/python -m pytest -q`. Prism 11 (and 10) are installed on the developer's machine
> for screenshots, sample files and reference numbers: when in doubt about *what* a
> feature does, look at Prism; decide *how it looks* ourselves (§2.1–2.3).

---

## 1. Product

**What it is:** a complete, polished app, not a lab script. It is **free for noncommercial use**
(PolyForm Noncommercial 1.0.0): shared with other labs. Selling it later (e.g. a lab
subscription, or commercial licences for companies) is being explored, not decided. Prism users should find every capability they rely on (the same sheet
types, analyses, options and live linking between data, results and graphs) and learn
ASTERISM's own interface in minutes.

**What makes it worth switching to:**
1. **Exports that open in Affinity/Illustrator essentially final**: live text, real fonts,
   named groups, exact millimetre sizes (§10).
2. **Numbers you can defend**: every analysis is checked against Prism's own output in the
   test suite (§13).
3. **A calm, modern native app** that looks like the developer's other tools (§12).
4. **It reads your existing work**: Prism files (`.pzfx`, `.prism`), Excel/CSV, and the
   lab instruments' and sibling apps' exports (§11).

**Who it is for:** anyone who uses Prism for column, grouped, XY, contingency and
survival work. Prism's long tail (e.g. every nonlinear model, power analysis,
multiple-variable methods) arrives after the core is solid, in the order users ask for it.

---

## 2. Principles and hard constraints

1. **Function follows Prism 11; form is ASTERISM's own.** What ASTERISM can do follows
   Prism: table types and sub-column formats, analyses and every option, defaults,
   calculations and the numbers in results, live linking, and reading Prism files.
   How it is presented is ours: window layout, navigation, toolbar, dialog layouts and
   groupings, names and wording (§12). Functionality and file formats are not protected
   (EU: *SAS Institute v World Programming*, 2012; US: *Lotus v Borland*); a product's
   distinctive look and arrangement can be (trade dress, GUI copyright, design rights),
   also when distributed free. So:
   - never reproduce Prism's window arrangement (ribbon with Prism's groups, Navigator
     sections and Family panel), its dialog layouts or tab sets, its icons or artwork;
   - never use Prism's coined terms ("Family", "Magic", "Welcome dialog", "Project
     Companion", "Layouts" for pages of panels — ours are **Figures**, …) or copy its text (help, dialog wording, result layouts beyond
     standard statistical terms such as "P value" or "t, df");
   - screenshots of Prism are used to learn *which options exist*, never as layouts to
     reproduce.
2. **Look and structure follow NED-Net.** The skin (colours, controls, typography) and the
   window structure (full-height sidebar, toolbar above the content, status bar) mirror
   NED-Net's desktop UI so the two apps read as coming from one developer (§12).
3. **Interoperate, don't copy.** Reading Prism files is for interoperability. Never use
   Prism's trademarks. ASTERISM is not affiliated with GraphPad. ASTERISM is owned by
   Marco Ledri; Lund University has no claim on it.
4. **Numbers match Prism.** Same defaults (Student's t, not Welch; Prism's percentile
   rule; exact P values where Prism uses them; Prism's P formatting and asterisk cutoffs).
   Any intentional difference is documented in the results sheet and in §14.
5. **One drawing path.** Every graph element is drawn once, through one canvas API, in
   points. Screen, PDF, SVG and PNG all come from that same layout. Never add a second
   renderer for previews.
6. **The document model is UI-free.** `asterism/doc`, `asterism/analysis` and
   `asterism/core` never import Qt. That keeps the model, file format and statistics
   testable without a display.
7. **Every user change is undoable**, and every project change marks the document as
   edited.
8. **Never modify the sibling apps** (TRACER, NED-Net, GliaAnalysis). ASTERISM consumes
   their exports. Borrowed code is copied and allowed to diverge; there are no import
   dependencies in either direction.
9. **Nothing is inferred silently** in imports: every guess is shown and can be overridden
   before it affects an analysis.
10. **Never lose work.** Atomic saves, autosave with crash recovery, versioned file format.

---

## 3. Stack

- **Python 3.12+**, **PySide6 6.11 (Qt Widgets)**. Fusion style + one app stylesheet
  (§12); native title bar, menu bar, file dialogs and system font.
- **Statistics:** numpy, scipy, pandas, pingouin, statsmodels. The pure-Python core in
  `asterism/core/stats.py` holds the golden-tested executors.
- **Export:** QPdfWriter (PDF), our own `SvgCanvas` (SVG with named groups), QImage (PNG/TIFF).
- **Packaging (M11):** PyInstaller (`packaging/asterism.spec`): macOS `.app` in a `.dmg`
  (Apple Silicon), Windows Inno Setup installer (per user, no admin), Linux AppImage. Not
  signed (user's decision 2026-10-28; the README explains the first open). File
  associations for `.asterism` (owner) and `.prism`/`.pzfx` (alternate). Built and
  self-tested (`--selftest`) by GitHub Actions on a `v*` tag, attached to a draft release;
  Help › Check for Updates reads the GitHub releases; **Install Update** (selfupdate.py)
  downloads this system's file, verifies it against the release's SHA256SUMS.txt, and swaps
  the app (macOS zip + helper script), runs the installer silently (Windows) or replaces the
  AppImage (Linux), then restarts.

**Why Qt, not Electron or the old Dash app:** the spike showed Qt Widgets gives a
genuinely native window, fast table editing, direct manipulation on the graph canvas,
and vector export that passes the fidelity QA, all in one language and one process.
Live linking (edit a cell, results and graphs follow) costs nothing in one process.
Electron would add a second language and build system for no capability we need.

---

## 4. Architecture

```
asterism/
  core/        UI-free, pre-existing: stats executors, importers, validation, export QA
  doc/         UI-free document model: sheets, graph specs, undo stack, file format
  analysis/    UI-free analysis registry: runs an Analysis sheet → result pages
  app/         PySide6 only: windows, project sidebar, toolbar, sheet views, dialogs, graph canvas,
               export, theme, icons
```

Dependency rule: `app → analysis → doc → core`. Lower layers never import upper ones.

- **Events.** Model objects expose plain-Python signals (`asterism.doc.events.Signal`,
  weak references to bound methods, so a deleted view never gets called). Views subscribe.
  A table emits `changed`, analyses recompute, graphs rebuild: Prism's live linking.
- **Undo.** `asterism.doc.undo.UndoStack` holds command objects with `redo()` / `undo()`.
  The app builds its Undo/Redo actions from the stack's signals. The stack's clean index
  plus a "touched" flag for non-undoable edits drive the window's edited state.
- **Recalculation** is synchronous for now (analyses are fast). If a long-running analysis
  arrives (e.g. nonlinear fits on large data), it gets a worker thread; the result object
  is immutable so it can be handed across.
- **Identity.** Every sheet has a stable UUID; links between sheets (analysis → table,
  graph → table/analysis, figure → graphs) are stored as ids in the file and resolved to
  objects on load.

---

## 5. Document model

A **project** contains five kinds of sheet. The project sidebar (§12) shows them in three
sections, with each table's analyses and graphs nested under it:

| Sidebar section | Sheets | Notes |
|---|---|---|
| Data | data table, and under it its analyses and graphs | tables are typed (§6); results are recomputed, never stored; a graph is a spec (§8) over one table |
| Notes | info sheet | constants (experiment date, ID, notebook ref, …) + free notes |
| Figures | figure | a page arranging graphs, tables and text as panels (§9) |

**Linked sheets:** a data table plus every analysis and graph fed by it. Deleting a table
deletes its linked sheets too (undoable). Renaming a table renames graphs that still carry
its name.

**New table → starter graph:** creating a data table also creates its graph.

---

## 6. Data tables

Prism's eight table types, each with its sub-column formats:

| Type | X | Y sub-columns | Typical graphs |
|---|---|---|---|
| Column | none | one value per row per group | scatter, bars, box, violin |
| XY | numbers / dates / elapsed times | replicates, or mean+SD/SEM+N | points + lines, fits |
| Grouped | row titles | replicates, or mean+SD/SEM+N | grouped bars, interleaved scatter |
| Contingency | row titles | counts | stacked/grouped bars |
| Survival | time | event codes per group | Kaplan-Meier staircase |
| Parts of whole | row titles | one value | pie, donut, stacked bar |
| Multiple variables | none | one variable per column | scatter matrices, correlation |
| Nested | none | sub-columns per subject | nested scatter / superplot |

Common features: column titles above group names (Group A, B, …), row titles, excluded
values (shown in blue italics, ignored by analyses and graphs), paste from Excel (TSV),
Enter moves down, every edit undoable, columns and rows insert/delete, unlimited growth.
The **New Table** dialog (also opened by "New project…" in the Start window) picks the table type, sub-column
format and a starter graph, in ASTERISM's own layout: table types in the dialog's section
sidebar, a live preview of the empty table and its graph beside them.

---

## 7. Analyses

ASTERISM offers the same analyses as Prism, with every option and the same numbers, in
its own presentation:
- The **Analyze** dialog lists analyses by table type in its section sidebar, with a
  search field and a short description of the selected analysis; unimplemented analyses
  are visible but disabled.
- Each analysis has a **parameters dialog** (section sidebar, our own grouping) carrying
  every choice Prism offers. Reopen it from the results sheet's toolbar.
- The **results sheet** reports the same quantities as Prism (test statistic, df, P
  value, effect sizes, confidence intervals, descriptive statistics), in our own layout
  and wording; standard statistical terms are kept. Results recompute live.

Priority order (each tier lands with golden tests, §13):

1. **Column:** descriptive statistics, normality and lognormality tests, one-sample t and
   Wilcoxon, t tests and nonparametric tests (done in the spike), one-way ANOVA (ordinary,
   Welch, Brown-Forsythe, RM, Kruskal-Wallis, Friedman) with multiple comparisons (Tukey,
   Dunnett, Šídák, Holm-Šídák, Bonferroni, Dunn, uncorrected Fisher's LSD), identify
   outliers (ROUT, Grubbs), frequency distribution.
2. **Grouped:** two-way ANOVA (ordinary and repeated measures, mixed-effects for missing
   values) with multiple comparisons; multiple t tests.
3. **XY:** linear regression, correlation (Pearson/Spearman), area under curve,
   smoothing, nonlinear regression with the common model families (dose-response,
   exponential, Michaelis-Menten, Gaussian, polynomial) and comparison of fits.
4. **Contingency:** chi-square, Fisher's exact, relative risk / odds ratio.
   **Survival:** Kaplan-Meier, log-rank (Mantel-Cox), Gehan-Breslow-Wilcoxon, hazard ratio.
   **Parts of whole:** fractions of total.
5. **Transforms and data manipulation:** transform, normalize, remove baseline, prune,
   transpose, fraction of total. These produce result *tables* that can be graphed and
   analyzed further, like Prism's.
6. Long tail on demand: multiple regression, PCA, power analysis, ROC, Bland-Altman, …

Results can feed graphs: multiple comparison results draw significance brackets
(stars or exact P) on the linked graph.

---

## 8. Graphs

- **Graph types by table type,** chosen in ASTERISM's **Graph Type** dialog (types grouped
  in its section sidebar, a preview of the current data in each).
- **Direct manipulation:** click to select an element (data set, axis, title, bracket,
  legend), drag to move titles, brackets and legends, double-click text to edit it in
  place, double-click any other element to open the Format Graph dialog at its section.
- **One Format Graph dialog** with a section sidebar (§12), in our own grouping:
  - *Graph:* Size and frame · Titles and fonts · Significance
  - *Data sets* (with a data-set picker, or all at once): **Style**, one page for everything
    about how a data set is drawn (plot type and summary line, show individual points,
    symbols, bars or box, error bars or whiskers) · Show and order
  - *Axes:* X axis · Y axis · Right Y axis

  It carries every option Prism offers for the graph type (§13a), with Apply/Cancel/OK and
  undo for each Apply.
- **Toolbar text tools** act on the selected text element: font, size, bold, italic,
  underline, superscript, subscript.
- **Colour schemes** and **Copy formatting** (apply one graph's formatting to others).
- Drawing and text tools on the graph (lines, arrows, boxes, free text); legends.
- Graph sizes are set in millimetres. The graph is drawn at final size: what you see at
  100% is what exports.
- A graph sheet shows the graph alone on a white area that fills the window, always
  centred (also when zooming, resizing or dragging a title). There is no page on a graph
  sheet; pages belong to figures (§9).
- Scatter plots spread tied values side by side within the column; only points that do
  not fit overlap, and the rest of the cloud keeps its true spacing.
- Box and whiskers follow Prism: box = 25th–75th percentile with the median line; seven
  whisker methods (min–max, min–max with all points, Tukey, 10–90, 5–95, 2.5–97.5,
  1–99 percentiles); points beyond the whiskers drawn individually; under four values
  the whiskers show the range; optional "+" at the mean; whiskers can be switched off.

---

### 8a. Graph catalogue, in order of implementation

Sources: Prism's user guide (graph families and Format Graph pages), the example
graphs Prism 11 ships in `Prism 11.app/Contents/SharedSupport/Portfolio`, and the
graphs Prism's analyses create. Every type also comes horizontal where Prism offers it.
Status: ✅ done · ◐ partly done · blank = to do.

**Column (M3)**
1. ✅ Scatter dot plot: points spread (ties side by side), line at mean/median ± SD/SEM/95% CI/IQR
2. ✅ Column bar: mean ± SD/SEM/95% CI/range, with or without points
3. ✅ Box and whiskers: seven whisker methods, outliers, mean "+", optional all points
4. ✅ Violin plot: truncated at the extremes (as Prism), light/medium/heavy smoothing, median and quartile lines, optional points
5. ✅ Before-after: symbols + lines, optional mean/median ± error beside (M9)
6. ✅ Mean (or median) with error only: one symbol per data set
7. ✅ Floating bars: min to max
8. ✅ Aligned dot plot (frequency dot plot: M5 with frequency-distribution graphs)
9. ✅ Significance brackets from multiple comparisons, stars or exact P, stacked
   - ✅ Formatting (requested 2026-10-23; done in M9). Format Graph › Significance:
     - **Shape:** bracket with end ticks or a plain line; tick length; line thickness and colour.
     - **Label:** stars or exact P ("P = 0.012", "P < 0.0001", or just the number); font and
       size of the stars separately from P text; gap between line and label.
     - **Which comparisons:** every comparison from the linked analysis listed with a show/hide
       tick; quick choices: significant only, all, only against a control, none; per-bracket
       hide from its context menu.
     - **When to draw stars:** star thresholds (Prism's default 0.0332 / 0.0021 / 0.0002 /
       < 0.0001, or the classic 0.05 / 0.01 / 0.001 / 0.0001), how many stars at most,
       "ns" shown or hidden, the significance level that counts.
     - **Placement:** stacking order (shortest first or table order), spacing between levels,
       distance above the data; brackets stay draggable.

**Grouped (M4)**
10. ✅ Interleaved bars, separated bars, with optional points
11. ✅ Stacked bars and 100% stacked bars (error bars drawn above each segment)
12. ✅ Interleaved / separated scatter with mean ± error
13. ✅ Grouped box and whiskers, grouped violin
14. ✅ Connected means; each replicate with connected means (M9)
15. ✅ Bars extending left and right (population pyramid, fold change both ways), and horizontal column/grouped graphs (M9)
16. ✅ Heat map of a grouped table (colour range from the Y axis range)
- ✅ Legends (draggable), palette colours per data set, brackets from two-way comparisons
  and multiple t tests, crowded X labels tilt automatically

**Nested (M4, right after grouped — the lab's cell-within-animal data)**
17. ✅ Nested scatter (sub-columns coloured per subject, each subject its own column or pooled)
18. ✅ Nested bar / box / violin / symbol-at-mean with nested points; SuperPlot (subject means)

**XY (M5)**
19. ✅ Points only, points + connecting line, line only; mean ± error or each replicate; X error bars; XY bars
20. ✅ Spaghetti plot (each replicate connected); discontinuous lines at missing values (M9)
21. ✅ Area fills, including semitransparent overlapping fills
22. ✅ Fitted curves with confidence / prediction bands (any linked linear or nonlinear fit)
23. ✅ Fit over a selected range, curve drawn over a chosen range; plot a typed function (M9)
24. ✅ Bubble plot (a third variable as symbol size), with multiple-variable graphs (M9)
25. ✅ Frequency distribution: histogram and cumulative, as a graph of the analysis's results (live)

**Survival, contingency, parts of whole (M6)**
26. ✅ Kaplan-Meier staircase with censor ticks, CI bands (dashed or shaded), % or fraction, survival or death or as error bars (M9)
27. ✅ Contingency: interleaved, separated and stacked bars of counts, stacked to 100%, heat map
28. ✅ Pie and donut charts (labels by percent or value, readable on any slice colour)
29. ✅ 100% stacked bar; percentage dot plot (waffle, M9)

**Graphs created by analyses (with each analysis, M3–M7)**
30. Estimation plots (t test: Gardner-Altman; one-way ANOVA: Cumming)
31. ✅ Residual plots for linear and nonlinear regression (result tables, graphed); normality QQ plot (M9; plotting positions to confirm against Prism)
32. Bland-Altman plot
33. ROC curve
34. Volcano plot (multiple t tests)
35. Forest plot (odds ratios, hazard ratios)

**Multiple variables (later, on demand)**
36. ◐ Scatter coloured / sized by a variable, labelled points (M9); confidence ellipses, convex hulls
37. Correlation matrix heat map, dendrograms (clustering)
38. PCA plots: scree, loadings, biplot / vector plot

**Graph features used across types (M3–M9, as each type needs them)**
Error bar direction (above/below/both); left and right Y axes; log axes; axis gaps;
time-scale axes; grid lines and shaded bands (QC graphs); nudging data sets
(waterfall); labelling points with row titles; colour by row ("rainbow"); colour
schemes; legends; text, lines, arrows and pictures on graphs; overlaying graphs in a
figure. All done by M9 except time-scale axes (with date/time columns, M10).

## 9. Figures

(Prism calls these "layouts"; ASTERISM's name, chosen 2026-10-26, is **figures**: what labs
call a multi-panel page.) A figure is a page (letter/A4, portrait/landscape, or custom size)
holding panels: graphs, data/result tables and text. Graphs are placed live (they update
with their data), snap to a grid and to each other, and can carry automatic panel letters
(A, B, C…). A figure exports as one PDF/SVG in which each graph is its own named group at
its own exact size. This replaces the old "figure set" export.

---

## 10. Export and clipboard

**Formats:** PDF, SVG, PNG and TIFF (chosen DPI), for a single graph, a figure, or a batch
of selected sheets. Results and data tables export as CSV/Excel.

**Fidelity is a hard requirement:** an exported graph must open in Affinity/Illustrator
needing only touch-up, never rebuilding. Enforced by the automated export QA
(`asterism/core/qa.py`) in the test suite:

- text stays live text (`<text>` in SVG; real text in PDF), never outlines;
- PDF fonts are TrueType/CID, never Type 3;
- nothing is rasterized (no `<image>` in SVG);
- canvas size matches the requested millimetres;
- every element is a named group (`data-A`, `y-axis`, `bracket`, `graph-title`, …), so it
  arrives as a selectable named object.

**Clipboard:** Copy (and Copy Graph to Clipboard) on a graph or figure puts **vector only**
on the clipboard, no bitmap flavour a receiving app might silently prefer: PDF and SVG on
the macOS pasteboard, EMF and SVG on Windows (our own EMF writer), SVG plus PNG on Linux.

---

## 11. Files and import

- **Native format `.asterism`:** a zip containing `project.json` (format id, format
  version, app version, sheets with data, parameters and specs). Results are recomputed
  on open, never trusted from disk. Saves are atomic (write temp, then replace). Files
  from a newer format version are refused with a clear message (read-only viewing may
  come later); older versions are migrated forward by explicit, tested migration steps
  (`asterism/doc/fileformat.py: migrate`).
- **Autosave and recovery (M11):** periodic snapshots beside the file. After a crash, the
  next launch offers to restore them.
- **Prism import (M10):** `.pzfx` (XML) and `.prism` (zip of JSON + CSV) → data tables
  first; analyses and graph formatting where they map cleanly. Report what could not be
  carried over; never drop it silently.
- **Spreadsheet import:** CSV/TSV/Excel into a chosen table type, with a preview.
- **Lab importers** (`asterism/core/importer`, pre-existing, and `asterism/io`): TRACER
  `cohort_summary.xlsx`, NED-Net `results_graph_data.xlsx` and QuantStudio qPCR runs (ΔΔCt
  with visible settings). (The manual template was dropped on 2026-10-26: a plain
  spreadsheet import covers it.) These go through the column inventory and role guessing (every
  guess shown and overridable), then land in typed tables.
  The importer's long-format data contract (`value | metric | unit | subject | replicate
  | factors… | batch | source_file`) stays as the intermediate form; `subject` remains
  the unit of independence when tables are built from it.

---

## 12. Look and feel

- **Skin:** `asterism/app/theme.py` mirrors NED-Net's `--ned-*` tokens
  (`NED-Net-desktop-ui/eeg_seizure_analyzer/dash_app/assets/style.css`): warm-paper
  palette, one desaturated cyan accent (`#007d93`, dark `#62c8df`), near-black text,
  boxed fields, filled-accent default button, segmented tabs, accent-filled sidebar
  selection, NED-Net's cool dark mode. Follows the system light/dark setting live.
  If NED-Net's tokens change, mirror them in `theme.py`. Never hardcode colours elsewhere.
- **Logo** ("Dipper pours into the i"): `asterism/app/assets/{logo,wordmark}-{light,dark}.svg`,
  built by `tools/make_logo.py` from the design reference (IBM Plex Sans 500 letters stored as
  outlines, so the app needs no font). Full logo with the Big Dipper on the Start window; the
  wordmark alone where it would be small. Light ink `#15171b` / accent `#007d93`; dark ink
  `#f3f2ee` / accent `#acdae6`. App icon (`icon.svg`, `asterism.icns` for a macOS bundle):
  the Dipper pouring into the star on a dark rounded square, set as the Dock/window icon.
- **Start window** (at launch without a file; File › Start Window…; can be switched off):
  a side panel with the logo and New project… (then the New Table dialog), Empty
  project (one Column table), Open…, Sample project; recent projects on the right (name,
  folder, when edited; missing files greyed). Closing it starts an empty project.
- **Windows remember their size and position** (saved shortly after each move or resize,
  and on close); a new window opens offset from the frontmost one, and always on screen.
- **Window structure (NED-Net's):**
  - *Project sidebar*, full window height: the asterism wordmark at the top (where NED-Net
    shows its name; the logo's small form, the star dotting the i, without the Dipper), a search field, then the Data / Notes / Figures sections (§5) as
    rounded rows; each section header has a "+" button to add a sheet. Analyses and
    graphs sit indented under their table.
  - *Top bar* above the sheet only (not across the sidebar): the sheet's name (click to
    rename) and a one-line description (e.g. "Column table · 2 data sets") on the left;
    then caption-less icon groups for project-wide actions: **Project** (new, open, save,
    undo, redo, print), **Sheet** (new table / graph / figure / notes, duplicate, delete),
    **Edit** (cut, copy, paste, insert/delete rows, exclude, sort, transpose); an
    **Export** button with a menu at the right end, and a button to show/hide the tool panel.
    Icons that don't fit go into a "»" overflow menu: the top bar never sets a minimum
    window width, so the sidebars can always be resized.
  - *Tool panel* on the right: the tools for the current sheet's content, in captioned
    groups: **Analyze** (a labelled Analyze… button plus analysis tools), **Graph** (a
    labelled Format graph… button, graph type, axes, significance, colours, copy
    formatting, legend, nudge), **Draw**, **Text**. Tools that do not apply to the current
    sheet are greyed out, not hidden; tools not built yet are greyed out with a tooltip.
    Icon buttons share the panel's width, so the right margin always equals the left.
  - Both sidebars are **resizable** by dragging their inner edge (left: about 180–480 px;
    right: about 200–360 px) and can be hidden; widths are remembered between sessions.
  - *Status bar*: muted items on the left (cell position; for a selection, n and mean),
    zoom on the right for graphs.
  - *Native menu bar* with every action, including those not on the toolbar.
- **Dialogs** use a **section sidebar** on the left (rounded rows with small group labels,
  like the project sidebar) and the selected section's controls on the right, with
  Help, Cancel and OK (and Apply where useful) along the bottom. No tab bars across the
  top of dialogs. Long dialogs scroll within the section, never the whole dialog.
- **Icons:** Lucide (ISC), bundled and used on every platform so all versions look the
  same (user's choice 2026-10-28), tinted with theme colours (`asterism/app/icons.py`).
- **Graphs and figures stay print colours** (white page) in both light and dark mode.
- **One window per project**, like Prism. Opening a file reuses an untouched empty window.

---

## 13. Testing

- **Model, file format and analyses:** plain pytest, no Qt.
- **App:** offscreen Qt tests (`QT_QPA_PLATFORM=offscreen`) for live linking, dialogs,
  undo, save/open.
- **Golden tests:** every analysis checked against Prism's output on real data
  (`tests/golden/prism_golden.json`, extracted from Prism projects kept locally in
  `sample_data/`, which is gitignored). Add cases with each analysis. These already caught
  one trap: pingouin's Mann-Whitney uses the normal approximation where Prism uses the
  exact test (~17× different P on a small sample).
- **Export QA** on every graph type (§10).
- **Screenshot tour** (`python -m asterism --shots DIR`) for visual review of every main
  screen and dialog, in light and dark mode.

---

## 13a. Checking Prism's options (parity sources)

Every dialog's options, defaults and behaviours are checked against Prism before a
milestone closes, using only legitimate sources:

1. **Prism's published user guide** (graphpad.com/guides/prism/latest/user-guide), which
   documents each dialog and calculation.
2. **Prism's own files:** projects saved in Prism with options varied one at a time;
   diffing the `.pzfx` (XML) / `.prism` (zip of JSON) files gives the exact option names,
   values and defaults. This also feeds the importer (M10).
3. **Screenshots** of each dialog, to learn which options exist (never as layouts to
   copy, §2.1), and Prism's numbers on the same data (golden tests).
4. **The example and sample files Prism installs** (`Prism 11.app/Contents/SharedSupport/`:
   `Portfolio/` example graphs with thumbnails, `SampleData/`, `Equations/`) and the
   published `.pzfx` schema (`Resources/PrismXMLSchema.xsd`). These are documents, not code.

Never decompile or disassemble Prism's program or open its interface files (`.nib`): its
licence forbids reverse engineering whether or not ASTERISM is sold, and other labs would
inherit the risk. Copying its code or text would also undermine principle 3 (§2).

## 14. Deliberate differences from Prism, and open questions

**Differences (by design, §2.1):**
- ASTERISM's own window structure (NED-Net's sidebar / toolbar / status bar) instead of a
  ribbon, navigator and family panel; linked sheets nested under their table.
- Dialogs with a section sidebar instead of tabs; one Format Graph dialog covering data
  sets and axes; our own groupings and wording.
- NED-Net skin instead of Prism's look (§12).
- Graph selection handles in the accent colour.
- Copy as vector on every system: PDF (macOS), EMF from our own writer (Windows), SVG
  (Linux), each with a PNG (`asterism/app/clipboard.py`, `graph/emf.py`).

**Open questions:**
- (Settled 2026-10-28: PyInstaller, unsigned, GitHub Releases as the update channel.)
- How deep `.prism` import goes beyond data tables (the format is undocumented and
  changes between Prism versions).
- Licence: PolyForm Noncommercial 1.0.0 (2026-10-29, replacing MIT; 0.1.0 was never
  downloaded and its release was withdrawn; 0.1.1 is the first release under it). Free
  for personal research, universities, hospitals, public research, charities and
  government; companies need a commercial licence. Not OSI open source, so
  JOSS and most open-source software grants are out. Outside contributions need the
  author's agreement that they may be relicensed. Qt under the LGPL as unmodified shared
  libraries (THIRD_PARTY_NOTICES.md).
- Possible paid version: test with other labs before building licensing; if sold, a merchant of record plus offline-signed licence
  files, "keep the versions released while subscribed".
- Whether ASTERISM files should embed fonts used in graphs (portability vs. size).

---

## 15. Build order

Each milestone ends with its acceptance list passing, the test suite green, and the
screenshot tour reviewed.

**M0 — Qt spike. Done (2026-10-22).** Native window, sidebar, Column table,
scatter-with-mean graph with Format dialogs, t tests, PDF/SVG export through the QA,
NED-Net skin.

**M1 — Foundation. Done (2026-10-22).**
- Real package layout (§4): spike code moved into `asterism/app`, the model into
  `asterism/doc`, the statistics bridge into `asterism/analysis`; `qt_spike/` removed.
- Old Dash UI, matplotlib figure engine and their launchers/tests removed (kept in git
  history).
- UI-free model with plain-Python signals and its own undo stack; adding/removing sheets
  and renaming are undoable.
- `.asterism` save / save as / open / revert, recent files, edited-state in the title bar,
  close/quit prompts to save unsaved changes, open files from the command line and Finder.
- Acceptance: create a project, enter data, run a t test, format the graph, save, quit,
  reopen: everything identical (data, titles, parameters, graph spec, sheet order,
  names). Undo works across every edit. Model and file-format tests run without Qt.
- Note for macOS: command-line arguments also arrive as Finder "open document" events;
  `asterism/app/main.py` ignores those duplicates (and folders).

**M1b — ASTERISM's own interface. Done (2026-10-22).** Replace the spike's Prism-like arrangement
(§2.1): NED-Net window structure (project sidebar with nested linked sheets, toolbar with
title block, status bar), dialogs with a section sidebar, one Format Graph dialog in our
own grouping, our own wording throughout (including results sheets: same numbers,
our own section titles and row wording). Top bar (project-wide tools) + right tool panel
(content tools), both sidebars resizable with remembered widths. Acceptance: no ribbon, navigator/family panel,
top tab bars or Prism-coined terms remain; every spike feature still works; screenshot
tour reviewed against NED-Net.

**M2 — Data tables. Done (2026-10-23).** All eight table types (XY, Column, Grouped,
Contingency, Survival, Parts of whole, Multiple variables, Nested) with Prism's entry
formats (one value; n replicates; mean with SD / SEM / %CV, with or without N; mean ± error;
mean with limits; XY X with error), row titles, data-set and sub-column titles, text in
row titles and variable tables, excluded values, insert/delete rows and data sets (linked
graphs and analyses follow), Table Format dialog, New Table dialog with preview and example
data, start screen, file format v2 with a v1 migration. Column tables entered as mean and
error are graphed from the entered values. Deferred: date and time X columns (M5);
graphs for the other table types arrive with their milestones (placeholder sheet until then).

**M3 — Column analyses and graphs. Done (2026-10-23).**
- Analyses: normality and lognormality (D'Agostino-Pearson, Anderson-Darling, Shapiro-Wilk,
  Kolmogorov-Smirnov/Lilliefors) and frequency distributions **match Prism exactly** on
  the golden cases harvested from the lab's projects (`tests/golden/harvest.py`; findings:
  Prism reports the uncorrected A² with P from A²*; bins use lower edges
  c0 − w/2 + i·w; automatic width = range/20 rounded to 1-2-5). One-way ANOVA family
  (ordinary, Welch + Brown-Forsythe, RM with Geisser-Greenhouse, Kruskal-Wallis,
  Friedman) with Tukey, Dunnett (exact multivariate-t integration, not Monte Carlo),
  Šídák, Holm-Šídák, Bonferroni, Fisher, Games-Howell, Dunnett T3, Tamhane T2 and Dunn,
  cross-checked against scipy/statsmodels/pingouin; Prism golden values for these are
  requested in `tests/golden/REQUESTS.md`. One-sample t / Wilcoxon, Grubbs outliers
  (ROUT → M5), t test from entered mean/SD/N.
- Graphs: stacked significance brackets for multiple comparisons, violin (truncated,
  three smoothing levels), floating bars, one-symbol mean/median, aligned dots, range
  error bars, before-after lines, Graph Type gallery previewed with the graph's data.
- Horizontal orientation and quartile-line styles for violins: done in M9.

**M3 (original plan)** §7 tier 1 with golden tests; column graph types
(scatter, bars, box, violin), error-bar options, brackets from multiple comparisons,
Graph Type dialog.

**M4 — Grouped and nested. Done (2026-10-23).**
- Golden-tested against Prism 11 on the lab's Seizure_data project: two-way ANOVA with
  matched rows and unequal group sizes (sums of squares, F, P; Bonferroni and Tukey post
  tests: difference, SE, df, CI, adjusted P), multiple Welch t tests and multiple
  Mann-Whitney tests with Holm-Šídák. Findings: Prism's matched two-way ANOVA is an
  unweighted-means analysis (n_h = harmonic mean of group sizes); between-group post tests
  use the pooled subjects + residual mean square; Prism's Mann-Whitney P is exact also
  with ties (permutation distribution of mid-ranks), now used everywhere.
- Two-way ANOVA: ordinary (Type III, = statsmodels), matched rows, matched data sets,
  matched every cell (= pingouin), Geisser-Greenhouse; comparisons within rows, within
  data sets, all cells, main effects; Tukey, Bonferroni, Šídák, Holm-Šídák, Fisher.
- Multiple t tests: Student, Welch, Mann-Whitney, paired, Wilcoxon; Holm-Šídák,
  Šídák, Bonferroni, none; FDR by two-stage step-up (BKY), BH, BY (= statsmodels).
- Nested t test and nested one-way ANOVA (REML mixed model; equals the test on subject
  means with equal replicates), variance between subjects, likelihood-ratio test.
- Graphs: §8a items 10–18 as marked; Format Graph "Arrangement" section; gallery per
  table type.
- Mixed-effects model for matched designs with missing values (done 2026-10-23, before
  M5): REML with compound symmetry (subject variance may be negative, so complete data
  give exactly RM ANOVA — golden-tested against Prism by fitting complete data both ways);
  three variance components when both factors are matched; Type III Wald F tests;
  containment degrees of freedom; post tests from the model's covariance; likelihood-ratio
  test of the matching; random-effect SDs and variances. Prism's three choices on the
  settings page (RM ANOVA only, mixed model always, mixed model only when values are
  missing — the default). Same for one-way RM ANOVA. Checked against R (nlme compound
  symmetry, lmerTest). Open: Prism's df method with gaps and its Geisser-Greenhouse
  handling (requested in `tests/golden/REQUESTS.md`).
- Deferred: three-way ANOVA. (Horizontal and left-right bars: done in M9.)

**M5 — XY. Done (2026-10-23).**
- Golden-tested against Prism 11 (Seizure_data): simple linear regression (each replicate a
  point, excluded X leaves the row out: slope, intercept, SEs, CIs, X-intercept and its
  interval, R², Sy.x, F test) and Spearman correlation (means of replicates). Findings:
  Spearman's exact P comes from the permutation distribution of the tied ranks (as for
  Mann-Whitney); approximate P is the t test; CI by Fisher's z with SE √(1.06/(n−3)), only
  for n > 10 (Prism's guide, after Zar).
- Linear regression: through a fixed point, compare slopes then intercepts (ANCOVA, =
  statsmodels), interpolation (X from Y with the Fieller interval, Y from X with the
  confidence band), runs test (exact), replicates test, confidence / prediction bands.
- Correlation: Pearson (Fisher z interval) and Spearman; X vs each data set (XY) or every
  pair of data sets (Column).
- Area under the curve: trapezoids, baseline, SE and CI from the SEMs, peaks with Prism's
  "ignore small peaks" rules.
- Nonlinear regression: 30 models in 9 families plus user-defined equations (safe parser);
  constants, bounds, shared parameters (global fits); weighting by 1/Y² or 1/Y using the
  curve's Y, 1/X², 1/X, 1/SD²; each replicate or means; profile-likelihood intervals
  (default, as Prism recommends) or asymptotic with SEs; derived values (EC50, half-life…);
  compare two models (extra sum-of-squares F, AICc) or data sets (one curve for all, one
  parameter shared); interpolation; residuals; runs test; ROUT outliers (identify or
  exclude). Cross-checked against R nls / MASS profile intervals.
- ROUT (Motulsky & Brown 2006) also in Identify outliers for column data.
- Graphs: XY graphs (§8a 19–25 as marked), numeric and log X axes, X title, legends,
  graphs of analysis results (Graph.source), Format Graph XY options, XY gallery.
- X values can be excluded (strike-through; leaves the row out).
- Open: Prism golden values for nonlinear fits, ROUT and the exact-Spearman cut-off
  (`tests/golden/REQUESTS.md`). Deferred: date/time X columns (M10 with import). Done
  since: plot a function and discontinuous lines (M9), residual plots as graphs (M7),
  smoothing / derivatives (M7).

**M6 — Contingency, survival, parts of whole. Done (2026-10-26).**
- Contingency: Fisher's exact test (2 × 2, golden-tested against Prism 11 on Seizure_data;
  larger tables by the Freeman-Halton enumeration, = R), chi-square with or without Yates'
  correction, chi-square test for trend (Cochran-Armitage, = R prop.trend.test); 2 × 2
  effect sizes with Prism 11's recommended methods (read from a saved Prism analysis):
  proportions and diagnostic measures by hybrid Wilson/Brown (= DescTools "modified
  wilson"), relative risk by Koopman (= PropCIs riskscoreci), difference by Newcombe/Wilson
  with or without continuity correction (= DescTools), odds ratio by Baptista-Pike (no
  reference implementation; checked to sit exactly on its rejection boundary), NNT,
  phi / Cramér's V with a noncentral chi-square interval. Older methods (Katz, Woolf,
  Clopper-Pearson) available.
- Survival: Kaplan-Meier with Greenwood SEs; log-log (default, as Prism) or symmetric
  clipped intervals (= R survfit); median survival and its interval from the log-log bands
  (= R); log-rank (= R survdiff, k − 1 df), Gehan-Breslow-Wilcoxon (= SAS LIFETEST's
  Wilcoxon on the Freireich data), log-rank test for trend; hazard ratio by Mantel-Haenszel
  and log-rank methods; ratio of medians with an interval assuming exponential survival.
- Parts of whole: fraction of total (column / row / grand total, percent or fraction,
  Wilson/Brown intervals for counts).
- Graphs: §8a items 26–29 as marked; Format Graph arrangement pages; galleries.
- Open: Prism golden values for survival and the 2 × 2 effect sizes
  (`tests/golden/REQUESTS.md`). Deferred: McNemar's test, comparing observed and expected
  counts (with M7's column tools), survival tables entered as percentages.

**M7 — Transforms and result tables. Done (2026-10-26).**
- Result tables: an analysis with tabular output owns one persistent output table
  (`<analysis id>.out` in files), refreshed in place on every recompute; it can be graphed
  (`Graph.source`) and analysed further, to any depth, and everything stays live. The sidebar
  nests graphs and analyses of results under their analysis; deleting an analysis removes its
  chain (undoable); files save and reload chains in dependency order. A new graph of results
  copies the format of the data's own graph and shows fits made on the result table.
- Transforms: Y and X functions (log, powers, reciprocals, logit, arcsine, Z score, your own
  equation in X, Y, K via the safe expression compiler); normalize (0% = smallest / first /
  value; 100% = largest / first / last / sum / mean / value); remove baseline and column maths
  (a baseline data set, matched replicates or means, or the first rows; subtract, divide,
  percent, percent change); prune rows (range, every nth, average every k); transpose;
  smooth (Savitzky-Golay over 2k + 1 points, ends dropped, as Prism documents), first and
  second derivatives (midpoint finite differences) and integrals (cumulative trapezoids from a
  starting value); fraction of total now makes a result table too.
- Also: compare observed and expected counts (chi-square, exact binomial for two
  categories; = SciPy), McNemar's test for matched pairs (continuity-corrected chi-square and
  exact binomial; = statsmodels), residual plots for linear and nonlinear regression.
- Frequency distributions use the same result-table machinery.

**M8 — Figures (Prism's layouts). Done (2026-10-26).**
- A figure is a page (A4, US Letter, A5 or custom, portrait or landscape) of panels: graphs,
  data or result tables, analysis results and text boxes; positions in millimetres, graphs and
  tables scaled as a whole. Panels refer to their sheets by id and redraw when they change;
  a deleted sheet leaves a placeholder (undo brings it back).
- Panel letters in reading order (A / a / (A) / A. / (a)), font, size, bold, outside or inside
  the corner; a panel can be left unlettered or given its own label.
- Editing: select, move (snapping to the grid and to other panels' edges), resize (scale), nudge
  with the arrow keys, delete, bring to front / send to back, align left / top / centres, same
  width, arrange in a grid; double-click opens the graph or table, or edits a text box. Every
  change is one undo step (FigureCommand).
- Adding: "Add Graphs and Tables…" (placed below what is there, in rows, shrunk to fit) and
  "Add to Figure…" from a graph (to an existing or a new figure); "Add Text".
- Export at the exact page size: SVG (each panel a named group "panel-A" holding the graph's
  own groups "A-data-A" …, live text), PDF, PNG and TIFF; graphs export to TIFF too.
- Done in M9: overlaying graphs, drag and drop from the sidebar, choosing which results page a
  panel shows, per-panel letters (automatic, none, custom).

**M9 — Graph polish. Done (2026-10-26).**
- Significance brackets (§8 item 9): bracket or plain line, end ticks, thickness, colour;
  stars, P value, number or both; four, three, Prism-style (0.0332/0.0021/0.0002/0.0001) or
  custom thresholds and the most stars; which comparisons (significant, all, against a
  control, none, or ticked one by one; hide from the bracket's menu); "ns" for two-group
  tests; stacking order, distance, spacing, label gap; separate font for stars.
- Axes: a right Y axis (any data set on column, grouped, contingency and XY graphs, own
  range, ticks, numbers and title); a break on linear Y axes (two segments, own tick
  spacing, bottom share, gap; data cut across the gap); grid lines; extra ticks, reference
  lines and shaded bands with labels; numeric X axis controls for multiple-variable and
  survival graphs.
- Colour schemes (ASTERISM, greys, colour-blind safe, viridis, NED-Net teal, warm,
  pastel, black and white) and "Apply Formatting to Other Graphs" (chosen aspects, one
  undo step).
- Drawing on graphs: lines, arrows (one or both heads), boxes, ellipses, text, pictures;
  Shift for 45° / squares; handles to reshape; move, nudge with arrows, delete, bring to
  front / send to back, align; Format dialog (colour, thickness, dash, fill, position in mm).
- Text: underline, colour, superscript / subscript (Unicode, so they survive every export),
  symbols (Greek, maths, units, marks), alignment of drawn text.
- Graph types: horizontal column and grouped graphs; bars extending left and right;
  replicates with connected means; before-after with mean/median ± error beside;
  discontinuous XY lines; plotted functions; normality QQ plot; Kaplan-Meier CIs as error
  bars; waffle; multiple-variable graphs (any variable against others, bubble size and
  colour by variables, row-title labels, legends); XY row labels and colour by row;
  nudging data sets (left/right, and up/down on XY for waterfalls); per-data-set legend
  entries; violin quartile and median line styles.
- Figures: drag graphs, tables and results from the sidebar onto a page; overlay two graphs
  (plot areas lined up); per-panel letters; which results page a panel shows.
- Fixed on the way: a crash when a graph or figure view was destroyed with something
  selected.
- Open: Prism's QQ plotting positions (`tests/golden/REQUESTS.md`); time-scale axes come
  with date/time columns (M10).

**M9b — Finding your way. Done (2026-10-26).** Two navigation aids for large projects.

*Graph overview* — every graph in the project on one page, to find and open graphs quickly.
- Opened from an "All graphs" row at the top of the project sidebar (under the search field),
  the View menu and a shortcut (⌘⇧G). It is a view, not a sheet: nothing is saved in the file
  except the user's last thumbnail size and filters (in settings).
- A grid of live thumbnails drawn by the graph layout engine (cached, redrawn when a graph
  changes, drawn lazily as cards scroll into view), grouped under their data table's name in
  sidebar order. Each card: thumbnail, graph name, one-line description ("Scatter dot plot ·
  4 data sets"), its colour label.
- Click selects; double-click or Return opens the graph; right-click: open, rename,
  duplicate, delete, add to figure, colour label. Several selected: add to a figure (or drag
  them onto one), apply formatting from one to the others, set a colour label.
- Above the grid: a search field (names), filters by table type and by colour label, a
  switch to include graphs of analysis results, sort (project order, name, last changed) and
  a thumbnail-size slider. Figures can be shown too, as a second group.

*Colour labels* — mark tables, graphs, analyses, notes and figures with a colour, as macOS
Finder tags folders, to recognise them at a glance.
- Seven colours and none (red, orange, yellow, green, blue, purple, grey; the theme's tokens,
  readable in light and dark mode). Each colour can be given a name for the project ("Final",
  "To check", "Supplement"), edited from the label menu; names are saved in the project.
- Shown as a dot at the end of the sheet's row in the sidebar (rows keep their normal look
  otherwise), on overview cards, and in sheet lists elsewhere (Analyze dialog, Add to figure,
  Apply formatting).
- Set from the sidebar's right-click menu (a row of colour swatches, like Finder's), the
  Sheet menu, and ⌃1–⌃7 / ⌃0 for the current sheet; works on several selected rows at once.
  Each change is one undo step; labels are per sheet (children do not inherit them).
- A colour strip under the sidebar's search field filters the sidebar to sheets with that
  label (parents stay visible, dimmed, for context); clicking again clears the filter.
- Saved in the file as `labels` (sheet id → colour) and `label_names`; older files load with
  no labels. (In code the label is `Sheet.tag`, as tables already have column labels.)
- As built: the overview's groups sit side by side and wrap to the window; Return opens the
  selected card, ⌘A selects all, Shift- and ⌘-click extend the selection; labels can be set
  from the overview's right-click menu and the ⌃0–⌃7 shortcuts act on selected cards too.

**M10 — Import. Done (2026-10-26).** File › Import Data (⌘⇧I), "Import data…" on the Start
window, File › Open for Prism files, and files or folders dropped on the window. Several files
(or an export folder of separate CSVs, as QuantStudio sometimes writes) import together as one
workbook; the preview shows any of the tables that will be made. **Import Settings…** (File and
Sheet menus, the sidebar's menu on an imported table) reopens the import window as it was left —
the sheets it read are kept in the project file — and updates that import's tables in place
(analyses and graphs stay linked; one undo step); newly ticked tables are added. For standard
curves the template volume is greyed out unless quantities are reported per µL or per mL
(titre = quantity per reaction × dilution [× 2] ÷ template µL [× 1000 per mL]).
- Spreadsheets: CSV / TSV / text (delimiter and decimal commas detected), Excel `.xlsx` and
  old `.xls`; sheet and header row (guessed, changeable), raw preview. Wide layout (each
  column a data set; same-named columns become replicates; row-title, X and X-error
  columns) or long layout (value, groups, second factor, subject, X, event columns) into any
  table type: subjects become nested sub-columns, keep their own sub-column across rows in
  grouped / XY tables (repeated measures line up), or are averaged to one value each;
  contingency tables count combinations; survival tables take time, event and group.
  A live preview of the table, with notes on everything skipped.
- Lab exports, recognised by their sheets' headers: NED-Net (per-animal measures → column
  tables, one value per animal, excluded animals reported; day-by-day and circadian sheets
  → grouped tables with each animal in its own sub-column, or XY; ISI distributions → XY),
  TRACER (per-cell measures → nested tables, animals as sub-columns, or per-animal means),
  QuantStudio (the Results table → relative expression 2^−ΔΔCt, ΔCt or mean Ct; reference
  gene(s) and reference sample read from the run's own file, groups guessed from sample
  names, all shown and editable; relative to a control group's mean or to one reference
  sample; NTC, omitted and undetermined wells counted). Checked on a real QuantStudio 5
  export: relative to its reference sample, our values equal QuantStudio's RQ column. With no
  endogenous control in the file and no housekeeping-gene name, nothing is pre-ticked.
  Standard-curve runs (absolute quantification, e.g. AAV titres): the curve is fitted here
  (Cq on log10 quantity: slope, intercept, R², efficiency — matching QuantStudio's within the
  CSV's rounding) → an XY table per target with its linear regression attached (fitted to the
  standards only) and every unknown well placed on the curve as a cross, one colour per sample
  (so extrapolated samples show at a glance), and the
  unknowns' quantities (samples × targets, technical replicates side by side), optionally
  × dilution, × 2 for single-stranded genomes on a plasmid standard, per µL or mL of sample;
  wells outside the standards' range are counted. Imported tables' graphs get axis titles
  from the data (measure names, "Copies per reaction (log scale)" / "Cq", units); titres and quantities on log axes in powers of ten (3×10¹³), standard curves labelled 10⁵ … 10⁹, and very large or small numbers in tables shown the same way.
- Prism `.prism` (10/11): every data table (titles, row titles, X, replicates, excluded
  values), info sheets, and analyses that map cleanly (t tests and their nonparametric
  forms, multiple t tests, two-way ANOVA, normality, linear regression, correlation,
  contingency, frequency distributions), recomputed — on the lab's files they reproduce
  Prism's results. Prism `.pzfx`: data tables and info sheets. A report lists what didn't
  come across (graph formatting and layouts for now; each table gets a default graph).
- Dates: X columns of dates (typed or imported), shown as dates in tables and labelled on
  axes as "26 Oct", ISO dates, months, or days since the first date.
- Open: Prism graph formatting and layouts; `.pzfx` analyses; TRACER wide-sheet tag
  columns (group only for now).

**M11a — Safety and settings. Done (2026-10-26).**
- Autosave and recovery: while a project has unsaved changes, a recovery copy is written every
  few minutes (Settings › General) into ASTERISM's own data folder — not beside the file, so
  synced folders stay clean — and removed on save or close. At launch, copies left by an
  ASTERISM that is no longer running are offered: restore (they open with unsaved changes,
  under their original file if it still exists), keep for later, or discard.
- Settings (⌘,): autosave; the Start window; how new graphs start (font and size, axis
  thickness, frame, plot height, column width, colour scheme, significance thresholds, label
  and shape); where new analyses start (Student's or Welch's t test, one-way ANOVA
  comparisons, confidence level, α); import defaults (ΔΔCt relative to a control group or a
  reference sample; the lab's titration settings for standard curves). They apply only to
  graphs and analyses made from then on, never to saved ones; defaults equal the built-in
  ones, so nothing changes until a setting does.
- Prism graph formatting (user's decision 2026-10-26: decode it, from the lab's own files only —
  never Prism's program): the graph binary (`graphs/<uid>/data.bin`, "PCFFGRA4") is a stream of
  tag/length records with containers closed by end markers (`asterism/io/prism_graphs.py`).
  Read: graph title (and whether Prism hides it), axis titles, axis ranges (log axes as
  exponents), major tick intervals, log scale, axis lengths (graph size), which data sets each
  graph plots, and per data set (matched to its column by data range): bars or points, bar
  fill and border colours, symbol shape, size and colour (solid/open), SD or SEM, connecting
  lines (solid or dashed), spaghetti, stacked bars, before-after lines (column and grouped),
  legend on/off. XY tables with an empty X column plot against row number, as in Prism.
  Checked against the lab's PNG exports of Seizure_data and Ephys_summary. Each Prism graph
  becomes an ASTERISM graph of its table (tables without one get a default graph). Not yet:
  fonts, axis gaps, extra lines (e.g. a dotted line at 0), free text placement.

**M11b — Help (done 2026-10-26):** built-in help window (Help › ASTERISM Help, ⌘?): 14 Markdown
pages in `asterism/help/pages/` shipped with the app (offline, matching the installed version),
rendered by a small converter in `asterism/help/__init__.py`; contents, full-text search,
back/forward; every dialog's ? button opens its section (`help.TOPICS`, checked by
tests/test_help.py, which also checks every link); Keyboard Shortcuts is generated from the live
menus; How Results Are Calculated documents the methods. Pages are written from the code; when
behaviour changes, update the page (the help tests catch broken anchors, not stale text).
Packaging must include `asterism/help/pages/*.md`.

**After M11b (2026-10-26):** parts-of-whole graphs get Format Graph › Slices (per-row colour and
pull-out, outer/internal borders, legend contents, total with prefix/suffix, order, diameter;
`GraphSpec.parts`); nested graphs get subject colours (by subject or data set, colour sets,
per-subject colours, restart per group, subject-mean size/outline; `GraphSpec.nested`). The α
set for new analyses reaches every analysis's "significant at α" answers; PNG/TIFF resolution
setting; Notes sheets undoable. Prism import now maps one-way ANOVAs (all designs and
comparison methods), sub-column titles and date X; checked against Prism's stored results in the
lab's "Anovas et al.prism" (Dunnett's T3 now uses the studentized maximum modulus with df rounded
down; repeated measures without sphericity compares each pair on its own differences; exact
Kruskal-Wallis P for small and moderate samples).

**M11 — Product:** autosave and recovery, preferences, help, Windows icon set, packaging,
signing, file associations, sample projects.
