# Settings, autosave and files

This page covers the Settings window, autosave and crash recovery, and how ASTERISM opens and saves project files. Shortcuts are written with ⌘; on Windows, use Ctrl instead.

## Settings {#settings}

Choose **Settings…** (⌘,) to change how ASTERISM starts, how often it autosaves, and where new graphs and new analyses begin. On macOS, **Settings…** is in the **ASTERISM** application menu; on Windows it is in the **File** menu.

The window has four sections: **General**, **New graphs**, **New analyses** and **Import**. Click **OK** to keep your changes or **Cancel** to leave everything as it was.

> **Important:** Graph and analysis settings only apply to graphs and analyses you make *afterwards*. Saved graphs keep their own formatting and saved analyses keep their own choices. To change an existing graph, use **Format Graph** or **Apply Formatting to Other Graphs** (see [Formatting graphs](formatting.md#apply-to-other-graphs)); to change an existing analysis, open its **Analysis Settings…**.

### General

| Option | Default | What it does |
|---|---|---|
| Show the Start window when ASTERISM opens | On | Off opens an empty project instead. The same choice is on the Start window itself. |
| Save a recovery copy of unsaved changes every … min | On, 2 min | Autosave (see [Autosave and recovery](#autosave)). Any interval from 1 to 60 minutes. |

### New graphs

How a new graph looks when it is first made.

| Option | Default | Notes |
|---|---|---|
| Font | Arial | Used for every text item of the graph. |
| Size | 12 pt | Axis titles and numbers use this size; the graph title is 2 pt larger and the legend 1 pt smaller. |
| Axis thickness | 1 pt | ½, 1, 1½ or 2 pt. |
| Frame | Plain axes | **Plain axes**, **Offset axes** or **Box**. |
| Plot height | 50 mm | The height of the plotting area. |
| Column width | 16 mm | Width per data set on graphs of Column tables (Nested tables get 1.5 times this). |
| Colour scheme | ASTERISM (default) | Any of the colour schemes from the **Graph › Colour Scheme** menu. |
| Star thresholds | 0.05, 0.01, 0.001, 0.0001 | Also **0.05, 0.01, 0.001**, or Prism's own cut-offs (0.0332, 0.0021, 0.0002, 0.0001). |
| Label | Stars | What a significance bracket shows: **Stars**, **P value**, **Number** or **Stars and P value**. |
| Shape | Bracket | **Bracket** or **Plain line**. |

With the default thresholds, P < 0.05 gets one star, P < 0.01 two, P < 0.001 three and P < 0.0001 four; anything else is marked "ns". See [How results are calculated](methods.md#significance-stars).

### New analyses

Where a new analysis's settings start. You can still change each analysis in its own settings.

| Option | Default | Notes |
|---|---|---|
| Unpaired t test | Student's t test | Or Welch's t test, which does not assume the two groups have the same SD. Student's is Prism's default too. |
| One-way ANOVA comparisons | Automatic | Automatic uses Tukey when comparing all pairs and Dunnett when comparing each group with a control. You can instead start every new one-way ANOVA with **Tukey**, **Šídák**, **Bonferroni** or **Holm-Šídák**. |
| Confidence intervals | 95% | 90%, 95% or 99%. Used by new t tests, one-sample tests, one-way and two-way ANOVA, nested analyses, linear regression, correlation and contingency tables. |
| Significance level (α) | 0.05 | 0.05, 0.01 or 0.10. Used by new normality tests and multiple t tests to decide what counts as significant. |

### Import

Your lab's defaults for importing instrument files (see [Importing data](importing.md)).

| Option | Default | Notes |
|---|---|---|
| ΔΔCt relative to | The mean of a control group | Or **One reference sample (as QuantStudio)**. Applies to qPCR (QuantStudio) imports. |
| Dilution factor | 1 | Filled in for every standard-curve import; you can change it there. |
| Template volume | (empty) | µL of template per reaction. |
| Report | Per reaction | Or **Per µL of sample** or **Per mL of sample**. |
| × 2 for single-stranded genomes on a double-stranded standard | Off | Doubles the titre. |

The titre is calculated as quantity per reaction × dilution [× 2] ÷ template µL [× 1000 per mL].

### Restore Defaults

**Restore Defaults** (bottom left of the window) puts every option above back to its default, including **Show the Start window when ASTERISM opens**, and closes the window. As with any change here, existing graphs and analyses are not affected.

## Autosave and recovery {#autosave}

While a project has unsaved changes, ASTERISM saves a recovery copy of it every few minutes (every 2 minutes unless you change it in **Settings… › General**). If ASTERISM or your computer stops unexpectedly, you can get that work back the next time you open ASTERISM.

- **Where the copies go.** Recovery copies are kept in a **Recovery** folder inside ASTERISM's own application-data folder (Application Support on macOS, AppData on Windows). They are never written over or beside your project file, so a synced folder (Dropbox, OneDrive and so on) stays clean.
- **When they are written.** Only when the project has changes that are not saved yet. A project with nothing new to save is not copied.
- **When they are removed.** As soon as you save the project, or when you close its window (whether you save or choose **Don’t Save**).
- **If a recovery copy can't be written** (for example, the disk is full), a short message appears in the status bar and your project is untouched.

### After a crash

If ASTERISM didn't close normally, the next launch opens **Restore Unsaved Work** before anything else. It lists each project that had unsaved changes, when it was last autosaved, and its file (or "never saved").

- Tick the projects you want back and click **Restore**. Each opens in its own window with its unsaved changes. Projects you untick are kept for next time.
- **Cancel** keeps all the copies; you will be asked again at the next launch.
- **Discard** deletes all the recovery copies.

A restored project still counts as unsaved: save it to keep it.

- If the project had been saved before, its window is linked to the original file again, so **Save** writes the restored version over that file. Use **Save As…** if you want to keep the old file as it was.
- If it had never been saved (or its folder no longer exists), it opens as an untitled project named "*name* (recovered)", and **Save** asks where to put it.

Copies left by an ASTERISM that is still running (for example, a second copy of the app) are not offered.

## Opening and saving projects {#files}

### One window per project

Each project opens in its own window. If you open a file that is already open, ASTERISM brings its window to the front instead of opening it twice. If the front window is an untitled project you haven't touched yet, the file you open takes its place.

ASTERISM remembers the size and position of its window; each new window opens slightly offset from the one in front.

### Opening files

- **File › Open…** (⌘O) opens an ASTERISM project, or a Prism file (`.prism`, `.pzfx`), which opens as a new, unsaved ASTERISM project (see [Prism files](prism.md)).
- **File › Open Recent** lists the last 10 projects you opened or saved. Files that have moved or been deleted are greyed out. **Clear Menu** empties the list. The Start window shows the same recent projects.
- **Drag files onto a window.** Each project file you drop opens in its own window. Spreadsheets (`.csv`, `.tsv`, `.txt`, `.xlsx`, `.xlsm`, `.xls`) are imported instead; several dropped together are imported together, as one export split over several files (see [Importing data](importing.md)).
- **On macOS** you can also double-click a project in the Finder or drop it on ASTERISM's icon in the Dock.

To open several projects at once, drag them onto a window together, or open them one after another; each gets its own window.

### Saving

- **File › Save** (⌘S) saves to the project's file. The first time, it asks where (the same as **Save As…**).
- **File › Save As…** (⇧⌘S) saves a copy under a new name; the window then belongs to the new file. The `.asterism` extension is added if you leave it out.
- **File › Revert to Saved** throws away your changes and reopens the last saved version (it asks first).
- **File › Close** (⌘W) closes the window. If there are unsaved changes, you are asked to **Save**, **Don’t Save** or **Cancel**.

Saving is safe: ASTERISM writes the new file next to the old one and only then replaces it, so a crash during a save never leaves a half-written project.

## The ASTERISM file format {#file-format}

An ASTERISM project is a single `.asterism` file. Inside, it is a zip archive holding one text file (`project.json`) with:

- every data table (values, titles, excluded values, and the table's format);
- info sheets;
- every analysis: which data it uses and all its settings;
- every graph with its formatting, and every figure;
- colour labels and their names;
- for imported tables, the source data and the choices you made, so **Import Settings…** can change them later.

Analysis results are not stored. ASTERISM recalculates them from the data each time you open the file, so the results always match the data and the version of ASTERISM you are using.

**Older and newer files.** Files saved by an earlier version of ASTERISM open normally; they are brought up to date when opened. A file saved by a newer version of ASTERISM, with a newer file format, is not opened: ASTERISM tells you to update instead of reading it only partly.

## macOS and Windows {#macos-and-windows}

ASTERISM works the same way on both systems, with these differences:

| | macOS | Windows |
|---|---|---|
| Shortcuts | ⌘ | Ctrl (for example Ctrl+S to save) |
| Settings… | **ASTERISM** menu | **File** menu |
| Opening from the Finder or Dock | Yes | Use **File › Open…** or drag files onto a window |
| Copying a graph to the clipboard | Planned (macOS only) | Not planned: export a file |

**Copy Graph to Clipboard** is in the **File** menu but greyed out: it is not available yet, and when it arrives it will work on macOS only. On both systems, use **Export PDF…**, **Export SVG…**, **Export PNG…** or **Export TIFF…** to put a graph or figure into another program (see [Figures and export](figures.md)). Copying and pasting cells in data tables works on both systems.

For every shortcut, see [Keyboard shortcuts](shortcuts.md).
