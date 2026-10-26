# Prism files

ASTERISM opens GraphPad Prism files, so you can bring existing work across and carry on in ASTERISM. It reads both of Prism's formats:

- `.prism`: the format of Prism 10 and 11.
- `.pzfx`: Prism's older XML format, which current Prism can still save.

The Prism file itself is never changed.

## Opening a Prism file

- **File › Open…**, or **Open…** in the Start window, and choose the file.
- **Import data…** in the Start window.
- Drag the file onto a project window.

The Prism file opens as a new, unsaved ASTERISM project named after the file. If the window you started from holds an untouched empty project, the Prism project takes its place. To keep the work, choose **File › Save As…**: it is saved as an `.asterism` project.

If you choose a Prism file with **File › Import Data…** instead, its sheets are added to the project that's open.

## What comes across

### Data tables

Data tables come across completely:

- all eight table types, with their entry formats (replicates, or mean with SD, SEM, %CV, N, or plus/minus errors or limits);
- column titles, row titles, X values and X error values;
- excluded values, still excluded;
- text in Multiple variables tables.

Each table gets ASTERISM's own graph unless the file brings its graphs across (below).

### Info sheets

Prism's info sheets become Notes sheets, with their constants (experiment date, ID, notebook reference and any others) and their notes. See [Data tables](tables.md#notes-sheets).

### Analyses (`.prism` files)

Analyses whose options have a clean ASTERISM equivalent are re-created with the same settings, then calculated by ASTERISM. Results are never copied from the Prism file, so the numbers you see are ASTERISM's own and stay live if you change the data. These analyses come across:

| Prism analysis | In ASTERISM |
|---|---|
| t tests and nonparametric tests | unpaired (Student's or Welch's), t test on logs, Mann-Whitney, Kolmogorov-Smirnov, paired, ratio paired, Wilcoxon; one- or two-tailed |
| Multiple t tests | the test, and the correction for multiple comparisons (Holm-Šídák, Šídák, Bonferroni) or the false discovery rate method and Q |
| Two-way ANOVA | ordinary or repeated measures (by rows, columns or both), the multiple comparisons method, the Geisser-Greenhouse correction, factor names |
| Normality tests | which tests, lognormality, the QQ plot |
| Simple linear regression | line through a fixed point, confidence or prediction bands, replicates, residual plot, test for departure from linearity |
| Correlation | Pearson or Spearman, the confidence level, tails |
| Contingency tables | Fisher's exact or chi-square test, tails |
| Frequency distribution | counts, fractions or percentages, cumulative, bin width and bin centres |

Other analyses are listed in the report as not carried over. You can run them again in ASTERISM from **Analyze…**: see [Analyses](analyses.md).

### Graphs (`.prism` files)

Each graph of a data table comes across with its name, the data sets it plots, and the formatting ASTERISM can read:

- the graph title (and whether it is shown), the axis titles, and the right Y axis title;
- axis ranges, log axes, and the interval between major ticks;
- the size of the graph (axis lengths, or column widths that give the same width);
- bars or points; bar fill and border colours;
- symbol shape, size and colour;
- error bars showing SD or SEM;
- on XY graphs: connecting lines, error bars on or off, and each replicate joined by its own line;
- dashed lines;
- stacked bars on Grouped and Contingency graphs;
- before-after graphs (points joined row by row), with the line colour;
- whether the legend is shown.

Anything ASTERISM can't read keeps ASTERISM's default, and you can change it in **Format Graph…**: see [Formatting graphs](formatting.md).

## What doesn't come across

- **Layouts.** Prism's pages of graphs aren't read. Make them again as Figures: see [Figures and export](figures.md).
- **Graphs of analysis results.** Prism's formatting of these isn't read; ASTERISM draws its own graphs of the results.
- **Fonts**, axis gaps and free text placed on graphs.
- **Analyses without a clean equivalent**, and analyses whose data table couldn't be read.
- **Analyses and graphs in `.pzfx` files.** Prism stores them in a part of the file ASTERISM can't read. The data tables and info sheets come across, each table with ASTERISM's default graph.
- **Table types ASTERISM doesn't have**, if a file contains one.

## The import report

After a Prism file opens, a message says what came across, for example "From “Experiment 3.prism”: 4 data tables, 2 analyses and 5 graphs with their formatting." Below it, **Not carried over:** lists everything that didn't come across and why, such as "1 layout not carried over (make figures in ASTERISM)". Nothing is dropped without being listed. If everything came across, the message says so.

> **Tip:** keep the report in mind when checking the new project: re-create any listed analyses with **Analyze…**, and compare a couple of key results with Prism's before you rely on them.
