# Importing data

ASTERISM reads spreadsheets (CSV, TSV, text and Excel files), the exports of the lab's own apps (NED-Net and TRACER), QuantStudio qPCR runs, and Prism files. Every guess the import makes is shown before anything is created, and you can change it.

On a Mac, shortcuts use ⌘. On Windows, use Ctrl wherever this page says ⌘.

## Starting an import

- **File › Import Data…** (⌘⇧I), or **Import data…** in the Start window.
- Drag spreadsheet files, or a folder of them, onto a project window.

You can choose several files at once, or drag several files or a folder: they are read together as one workbook, with each file (and each Excel sheet) as a sheet. This suits exports written as several CSV files.

Prism files (`.prism`, `.pzfx`) skip the import window; see [Prism files](prism.md).

Each table made by an import comes with its own graph, and is added to the project that's open. If a table name is already taken, a number is added to it.

## File types

| File | Notes |
|---|---|
| CSV, TSV, TXT | The separator (comma, semicolon or tab) is detected. Decimal commas are understood. |
| Excel `.xlsx`, `.xlsm` | Every sheet is read, with the values the cells show (not formulas). |
| Old Excel `.xls` | Every sheet is read; dates stay dates. |

Numbers stored as text in the file ("1,5", " 2e-3 ") are read as numbers. Empty rows and columns at the end of a sheet are ignored.

## The Import Data window

The window has sections on the left:

- **File and columns**: which sheet to read and how to turn it into a table.
- **Preview**: the table that will be made, exactly as it will look.
- For lab exports, a first section named after the source (for example **NED-Net export**), and for QuantStudio runs also **qPCR settings**.

Click **Import** to make the tables.

### Sheet and header row

At the top of **File and columns**:

- **Sheet:** the sheet to read (for a CSV file there is one, named after the file).
- **Column names in row:** the row holding the column names. ASTERISM guesses it (it skips a preamble of notes above the data). The raw sheet is shown below with that row in bold, so you can check it.
- **No row of column names**: tick it if the data start in the first row. Columns are then called Column A, Column B and so on.

### Making the table

Under **Make a table**:

- **Table name:** defaults to the file's name.
- **Table type:** any of the eight types (see [Data tables](tables.md)). ASTERISM guesses Column or Grouped; change it if your data are XY, Nested, Survival and so on.
- **Layout:** how the sheet is arranged. See the next two sections.

Then the column list shows each column's name, a few example values, and **Use as**: what the column becomes in the table. Change any guess here. Columns set to **Ignore** are left out.

The Preview updates as you change things. Notes below the preview say what was skipped or guessed, for example "3 text cells in data columns left out."

## Wide layout {#wide-layout}

**Wide: each column is a data set** suits a sheet laid out like an ASTERISM table: one column per group.

| Use as | Meaning |
|---|---|
| **Data set** | The column becomes a data set (a group). |
| **Row titles** | Labels for the rows (Grouped tables; also XY). |
| **X values** | The X column of an XY table. Dates are recognised and give an XY table with date X values. |
| **X error** | Horizontal error bars of an XY table. |
| **Ignore** | Left out. |

**Columns with the same name (e.g. Control 1, Control 2) are replicates of one data set** (on by default; shown only for XY and Grouped tables): columns whose names differ only by a trailing number become replicate sub-columns of one data set, each sub-column keeping its column's name.

What each table type does with a wide sheet:

- **Column**: each data set column becomes a group.
- **Grouped**: data set columns become groups (or replicates, see above); the row-titles column labels the rows.
- **XY**: one column is X, the others are data sets. Without an X column, rows are numbered 1, 2, 3 … (the notes say so).
- **Nested**: each data set column becomes a group with one subject; for several subjects per group, use the long layout.
- **Contingency**, **Survival**: each data set column becomes a column of counts, or of 1/0 event codes. Negative numbers become 0.
- **Parts of whole**: each data set column becomes a column of values.
- **Multiple variables**: each data set column becomes a variable; text is kept.

## Long layout {#long-layout}

**Long: one value per row, with group (and subject) columns** suits "tidy" sheets, where each row is one measurement and other columns say which group, animal or time point it belongs to. Statistics programs and many instruments write data this way.

| Use as | Meaning |
|---|---|
| **Values** | The measurements. |
| **Groups (data sets)** | Which group each value belongs to. Each different entry becomes a data set. |
| **Second factor (rows / X)** | A second grouping: the rows of a Grouped table, or X of an XY table. Numbers (days, hours) are put in numeric order. |
| **Subject (animal)** | Which animal (or subject) each value comes from. |
| **X values** | X of an XY table, or the times of a Survival table. |
| **Event (1) / censored (0)** | The event codes of a Survival table. |
| **Ignore** | Left out. |

ASTERISM guesses the roles: a single number column becomes **Values**, and a text column whose name contains "animal", "subject", "mouse", "rat" or "id" becomes the subject.

**Average to one value per subject (the unit of independence)** (shown only for the long layout): tick it when you have several values per animal (cells, trials) but want one value per animal in the table, their mean.

What each table type does with a long sheet:

- **Column**: one data set per group, the group's values stacked down it.
- **Grouped**: data sets from the group column, rows from the second factor. With a subject column, each animal gets its own sub-column and keeps it on every row, so repeated measures line up.
- **XY**: X from the second factor or the X column, data sets from the group column, animals as replicates as for Grouped. If X isn't numeric, its entries become row titles and the rows are numbered.
- **Nested**: data sets from the group column, one sub-column per subject (named after it), and each subject's values down its sub-column.
- **Contingency**: rows from the second factor, outcome columns from the group column. With a values column the values are added up; without one, ASTERISM counts the rows of each combination.
- **Survival**: one row per subject, with its time in X and 1 or 0 in its group's column. Without an event column every row counts as an event. A subject column becomes the row titles.

## Preview

The **Preview** section shows each table the import will make. When an import makes several (a lab export usually does), pick one under **Show:**. The heading gives its type, number of data sets and rows. Notes below list everything that was skipped, guessed or left out.

## Lab exports

ASTERISM recognises the results files of the lab's own apps, and offers ready-made tables from them. The first section of the window is then named after the source:

- **Use the … layout (recommended)**: make the tables listed below.
- **Choose the columns myself (File and columns)**: ignore the recognised layout and set up the table by hand, as for any spreadsheet.

Under **Tables to make**, tick the tables you want. Where a table can be laid out more than one way, choose under **Layout**. Throughout, the animal stays the unit of independence: one value per animal, or animals side by side with their values below.

### NED-Net

| Sheet in the export | Tables |
|---|---|
| Per-animal results (seizure rates, durations) | One **Column table: one value per animal** for each measure. |
| Day-by-day or hour-of-day results | **Grouped table: rows by day/hour, animals side by side**, or **XY table: X = day/hour, animals as replicates**. |
| Inter-seizure interval distributions | **XY table: X = bin, one data set per group**. |

### TRACER

| Sheet in the export | Tables |
|---|---|
| Cell-level results (long or wide) | One table per measure: **Nested table: animals side by side, their values below**, or **Column table: one value per animal** (the mean of each animal's cells). |
| Event sheets | The same layouts; unticked to start with. |

## QuantStudio qPCR

ASTERISM reads the Results table of a QuantStudio run (`.xls`, `.xlsx` or `.txt`), and also the run's settings recorded below it. In every case:

- No-template controls (NTC) and wells marked as omitted are left out.
- An "Undetermined" Ct counts as a missing value.
- The notes say how many wells of each kind were left out.

### Relative expression (ΔΔCt)

The tables offered are:

- **Relative expression (2^−ΔΔCt)**: a Column table for each target gene, one data set per group, one value per biological sample. Ticked to start with.
- **ΔCt**: the same, with ΔCt values.
- **Mean Ct by sample and target**: a Grouped table, samples in rows, targets in columns.

How it is calculated: technical replicate wells are averaged to one Ct per sample and target. ΔCt = Ct of the target − Ct of the reference gene. ΔΔCt = ΔCt − the control's ΔCt. Relative expression = 2^−ΔΔCt.

The settings, in **qPCR settings**:

- **Reference gene (endogenous control)**: the run's endogenous control is ticked and marked "(from the file)". If the file doesn't name one, a gene with a housekeeping name (GAPDH, ACTB, 18S, HPRT…) is ticked and marked as a guess. Check it. If you tick several, their mean Ct is the reference.
- **Relative to**:
  - **The mean of a control group**: the control's ΔCt is the mean over the samples of the **Control group:** you choose. ASTERISM guesses a group with a name like Control, WT, Vehicle, Sham, EGFP or Scramble.
  - **One reference sample (as QuantStudio reports RQ)**: one **Reference sample:**. The run's reference sample is marked "(from the file)".
- **Samples and their groups**: the biological samples and the group of each. Groups are guessed by dropping a trailing number ("Control 2" → Control). Edit them here. Leave a group empty to leave that sample out.

Which of the two **Relative to** options is chosen first is set in [Settings](settings.md).

### Standard curves and titres

When the run has STANDARD wells with quantities, ASTERISM fits a standard curve for each target (Cq against log10 of the quantity) and shows its slope, R² and efficiency in **qPCR settings**. The tables offered are:

- **Standard curves**: an XY table for each target, with the standards' Cq against log10 quantity and a linear regression attached. The unknown samples are added as crosses where they fall on the curve. The X axis is labelled in copies per reaction (10⁵, 10⁶ …).
- **Quantities of the unknowns**: a Grouped table, samples in rows, targets in columns, technical replicates side by side, on a log axis. It is called "Titres" when you report per µL or per mL, otherwise "Quantities".

Both are ticked to start with; the ΔΔCt tables are offered too, unticked. The ΔΔCt settings appear only when you tick one of them.

The notes warn when unknown wells fall outside the range of the standards: their quantities are extrapolated, so check them.

To turn the copies measured in each well into a titre, set:

| Setting | Meaning |
|---|---|
| **Dilution factor:** | How much the sample was diluted before it went into the reaction (digestion, dilution). |
| **Template volume:** | µL of that diluted sample in each reaction. Used only when reporting per µL or per mL. |
| **Report quantities:** | **Per reaction (× dilution factor)**, **Per µL of sample** or **Per mL of sample**. |
| **Single-stranded genomes against a double-stranded (plasmid) standard: × 2** | For single-stranded vector genomes (for example AAV) measured against a double-stranded plasmid standard. |

ASTERISM multiplies each quantity per reaction by the dilution factor (and by 2 if ticked); for per µL it then divides by the template volume, and for per mL it also multiplies by 1000:

titre = quantity per reaction × dilution factor [× 2] ÷ template volume in µL [× 1000 for per mL]

The dilution factor and the × 2 apply whatever you choose under **Report quantities:**. Leave **Dilution factor:** at 1 if you want the copies actually measured in each well.

> **Worked example:** you digest and dilute an AAV prep 1 in 100, and put 1 µL of the dilution into each reaction. Set **Dilution factor:** 100, **Template volume:** 1 and **Report quantities:** Per mL of sample. Each quantity is multiplied by 100 × 1000 ÷ 1 = 10⁵, so 3.2×10⁴ copies in a well become 3.2×10⁹ copies per mL. With 2 µL per reaction the factor would be 100 × 1000 ÷ 2 = 5×10⁴. With the × 2 box ticked, both double.

Your lab's usual dilution, volume, unit and × 2 choice can be filled in for every import: see [Settings](settings.md). You can still change them in the import window.

## Changing an import later

ASTERISM keeps a copy of the imported sheets and your choices in the project. To change how a table was imported, open the table (or one of its graphs or results) and choose **File › Import Settings…** or **Sheet › Import Settings…**, or right-click the table in the project sidebar and choose **Import Settings…**.

The import window reopens with your earlier choices. Change what you need (a column's role, the reference gene, the control group, the dilution factor…) and click **Update**:

- The tables from that import are updated in place. Their analyses and graphs stay linked and recalculate.
- Tables you tick that weren't made before (from the same sheets of the export) are added.
- Tables you untick are kept; delete them yourself if you no longer want them.
- Changes you made by hand to the values of those tables are replaced by the import.
- The whole update is one step you can undo.

The original file isn't needed: the data come from the copy kept in the project. **Import Settings…** is greyed out for tables that weren't imported, including tables from Prism files.

## Import defaults

In **Settings… › Import** you can set:

- **ΔΔCt relative to:** **The mean of a control group** or **One reference sample (as QuantStudio)**.
- Under **Standard curves: titres**, your lab's **Dilution factor:**, **Template volume:**, **Report:** unit and the × 2 for single-stranded genomes.

These fill in the import window each time. See [Settings, autosave and files](settings.md).
