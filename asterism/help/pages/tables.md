# Data tables

A data table holds your numbers. Its type decides how the data are laid out, which analyses fit them and which graphs ASTERISM draws. Choose the type for the question you want to answer, not for how the data happen to sit in your spreadsheet.

On a Mac, shortcuts use ⌘. On Windows, use Ctrl wherever this page says ⌘.

## Making a new table {#new-table}

Choose **Sheet › New Data Table…**, click the **+** next to **Data** in the project sidebar, or click **New project…** in the Start window.

The **New Data Table** dialog lists the table types on the left. Each page explains the type in a sentence, shows a picture of the kind of data it holds with a concrete example and when to choose it, and offers its entry formats. At the bottom:

- **Preview** sketches the empty table's columns for the choices you've made.
- **Fill the table with example data** puts in a small, realistic data set, handy for trying out analyses and graphs.

Click **Create**. ASTERISM makes the table and its first graph.

From the Start window the dialog is titled **Start a New Project**. If you cancel it there, you keep an empty Column table.

## Table types

| Type | Layout | Use it for |
|---|---|---|
| **XY** | An X value per row (time, dose, concentration) and one or more Y data sets. | Curves, linear and nonlinear regression, correlation, area under the curve. |
| **Column** | Each column is a group, its values stacked down the column. | t tests, one-way ANOVA, descriptive statistics, normality tests, column graphs. |
| **Grouped** | Rows and columns are two grouping factors (for example genotype × treatment). | Two-way ANOVA, multiple t tests, grouped bar graphs. |
| **Contingency** | Counts of subjects in each group (rows) and outcome (columns). | Chi-square and Fisher's exact tests, relative risk, odds ratio. |
| **Survival** | One row per subject: time in X, and 1 (event) or 0 (censored) in the subject's group column. | Kaplan-Meier curves, log-rank tests. |
| **Parts of whole** | Values that add up to a whole, one per row. | Fractions of the total, pie and donut charts. |
| **Multiple variables** | One row per observation, one column per variable (numbers or text). | Scatter plots of one variable against another and bubble plots. |
| **Nested** | Groups, each split into subjects (for example animals) with several measurements per subject. | Nested t test and nested one-way ANOVA. |

### Which type?

- **Column or Grouped?** One factor (control vs treated, or several doses as separate groups): Column. Two factors (genotype and treatment, or treatment and time point): Grouped.
- **Column or Nested?** If you measured several cells or slices per animal, the animal is the unit of independence. Put the animals in a Nested table so the analysis doesn't treat every cell as an independent sample. If you have one value per animal (for example an average), use a Column table.
- **Grouped or XY?** Times or doses on a number scale, where you want a curve, a slope or an area: XY. Categories, or a few time points you compare one by one: Grouped.
- **Survival:** one row per animal, with the day it reached the event (or the last day you saw it) in X.

Each type's analyses are listed in [Analyses](analyses.md), and its graphs in [Graphs](graphs.md#graph-types).

## Entry formats

The format sets how many sub-columns each data set has.

### One value per cell

One number in each cell. In a Column table this option reads **Raw values, stacked down each column**. Use it whenever you have the individual measurements.

### Replicates side by side

(XY and Grouped tables.) **Replicate values side by side** gives each data set several sub-columns (2 to 50, default 3), labelled Rep 1, Rep 2 and so on. Each row holds the replicates for one X value or one row category. Use it for several animals or wells measured at each time point or under each condition.

When animals are measured repeatedly, keep each animal in the same sub-column on every row, so repeated-measures analyses can match its values.

### Mean and error calculated elsewhere

(XY, Column and Grouped tables.) Choose **Mean and error calculated elsewhere:** when you only have summary values, for example from a paper or another program. The list offers:

| Format | Sub-columns |
|---|---|
| Mean, SD, N | Mean, SD, N |
| Mean, SEM, N | Mean, SEM, N |
| Mean, %CV, N | Mean, %CV, N |
| Mean, SD | Mean, SD |
| Mean, SEM | Mean, SEM |
| Mean, %CV | Mean, %CV |
| Mean, + error, − error | Mean, the error above, the error below (for uneven error bars) |
| Mean, upper limit, lower limit | Mean, and the top and bottom of the error bar |

Enter N if you have it. With N, graphs can switch between SD, SEM and confidence intervals, and analyses can use the sample size. ASTERISM works out SEM from SD and N (and SD from SEM and N), and SD from %CV and the mean.

Some analyses (for example a t test from mean, SD and N, or a curve fit) work from summary values. Others need the raw values, and ASTERISM tells you so when you try them.

### Subjects (Nested tables)

**Subjects per group:** sets how many sub-columns each group has (1 to 50, default 4), labelled Subject 1, Subject 2 and so on. Put each animal in its own sub-column and its measurements (cells, slices, trials) down that sub-column.

### Contingency, Survival, Parts of whole, Multiple variables

These have a fixed format:

- **Contingency:** enter whole-number counts. Negative numbers aren't accepted.
- **Survival:** enter 1 for an event (for example death) and 0 for a censored subject (lost to follow-up, or still event-free at the end). Other values aren't accepted.
- **Parts of whole:** enter each part's value; ASTERISM works out the fractions.
- **Multiple variables:** columns can hold numbers or text (for example sex or genotype).

## X values

XY tables have an X column; Survival tables have one for the times. In the New Data Table dialog an XY table offers:

- **Numbers**: one X value per row.
- **Numbers with error bars (X ± error)**: adds an X error column, for horizontal error bars.
- **Dates (or dates and times)**: see below.
- **Add a row-title column**: a text label for each row, alongside its X.

### Dates

With **Dates (or dates and times)**, type dates into the X column in any of these forms:

- 2026-10-26, or 2026-10-26 14:30
- 26/10/2026 or 26.10.2026 (day first), or 26/10/2026 14:30
- 26 Oct 2026, 26 October 2026, or Oct 26 2026
- 2026/10/26

The table shows dates as 2026-10-26 (with the time when there is one). Behind the scenes a date is a day number, as in spreadsheets, so analyses work in days: a regression slope on dates is a change per day. How the X axis labels the dates (26 Oct, 26/10/2026, Oct 2026, days since the first date…) is set under **Dates as:** in the graph's axis settings; see [Formatting graphs](formatting.md).

## Entering and editing data

- Click a cell and type. Press Enter to move down to the next row.
- The arrow keys move between cells. While you are typing a value, an arrow key saves it and moves on, as in a spreadsheet. To change part of a value, press F2 or double-click the cell; then ← and → move within the text.
- **Edit › Copy**, **Cut** and **Paste** (⌘C, ⌘X, ⌘V) work on a block of cells. Paste from Excel or another spreadsheet: the block is pasted starting at the current cell.
- Delete or Backspace clears the selected cells.
- A decimal comma is accepted (1,5 is read as 1.5).
- Text is accepted only in row titles and in Multiple variables tables. If a value doesn't fit a cell (text in a number column, a 2 in a Survival table), ASTERISM beeps and keeps the old value. When pasting, cells that don't fit are skipped.
- Very large and very small numbers are shown as powers of ten (1.5×10¹³). When you edit the cell you see the plain number.
- The table grows as you type: there is always room for more rows.

The status bar shows the current row and column. Select several numbers to see their count and mean there.

Every edit can be undone with **Edit › Undo** (⌘Z). Analyses and graphs update as you type.

### Column titles

The header shows each data set's name ("Group A", "Data set B", "Outcome C" and so on) above its title. Double-click the title row under the name to type a title, such as "Control" or "EGFP". Graphs and results use the title, or the name if there is no title.

From the keyboard: press ↑ in the first row to move up to the title, and ← → to go from title to title. Type to replace a title, or press F2 to edit it; ↓ or Enter goes back to the first row, Escape cancels, and Backspace clears the title.

In tables with replicates or subjects, double-click a sub-column's label (Rep 1, Subject 1…) to rename it, for example with the animal's ID.

### Row titles

Grouped, Contingency and Parts of whole tables always have a **Row titles** column at the left; XY tables have one if you ticked **Add a row-title column**. Row titles label the rows on graphs and in results: for example the second factor of a Grouped table (time points, treatments) or the categories of a pie chart. A row without a title is labelled by its X value, or "Row 1", "Row 2" and so on.

### Rows and data sets

In the **Edit** menu, the Data section of the tool panel, or the table's right-click menu:

- **Insert Rows** inserts as many empty rows as you have selected, above the selection.
- **Delete Rows** deletes the selected rows.
- **Insert Data Set** inserts empty data sets (columns) before the selected ones.
- **Delete Data Set** deletes the selected data sets. A table always keeps at least one.

Linked analyses and graphs follow these changes.

## Excluding values

To leave a value out of the analyses and graphs without deleting it, select it and choose **Edit › Exclude or Include Values** (⌘⇧E). Excluded values stay in the table, struck through in muted italics, so you (and anyone reading the project later) can see what was left out. Choose the command again to include them.

- Any value in a data set can be excluded.
- Excluding an X value leaves its whole row out.
- Results and graphs update at once.

Exclude outliers only for a reason you can state (a failed injection, a technical fault). See [Comparing groups](analyses-groups.md#outliers) for outlier tests.

## Changing the format {#table-format}

Choose **Sheet › Table Format…**, or right-click in the table, to change an existing table's entry format. The **Table Format** dialog offers the same choices as the table's page in the New Data Table dialog, with a preview. The table type itself can't be changed.

- Values are kept where the new format has room for them: sub-columns are kept in order, from the left. For example, going from 4 replicates to 3 drops the fourth replicate; going from replicates to Mean, SD, N puts Rep 1 under Mean, Rep 2 under SD and Rep 3 under N, which is rarely what you want.
- Switching an XY table away from **Numbers with error bars (X ± error)** removes the X error values.
- You can undo the change.

## Notes sheets

A Notes sheet records the details of an experiment next to its data. Add one with **Sheet › New Notes**, or the **+** next to **Notes** in the project sidebar.

It has a **Constants** section with fields for **Experiment Date**, **Experiment ID**, **Notebook Reference**, **Project**, **Experimenter** and **Protocol**, and a **Notes** box for free text. Notes sheets are saved with the project. You can undo typing with **Edit › Undo** (⌘Z); continued typing in one field is a single step.

Prism users: these are Prism's info sheets, and info sheets in Prism files come across as Notes sheets (see [Prism files](prism.md)).
