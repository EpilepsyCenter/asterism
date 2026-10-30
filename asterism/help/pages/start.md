# Getting started

ASTERISM is a free app for graphing and statistics. You enter or import data into tables, run analyses on them, draw graphs, and arrange graphs into figures for a paper or poster. Everything in a project stays linked: change a value and its results and graphs update straight away.

On a Mac, shortcuts use ⌘. On Windows, use Ctrl wherever this help says ⌘.

## What a project holds

A project is one file (ending in `.asterism`) holding five kinds of sheet:

| Sheet | What it is |
|---|---|
| Data table | Your numbers, in one of eight table types. See [Data tables](tables.md). |
| Results | An analysis of a data table: a t test, an ANOVA, a curve fit and so on. See [Analyses](analyses.md). |
| Graph | A graph of a data table, or of a results table. See [Graphs](graphs.md). |
| Notes | A sheet of experiment details (date, ID, notebook reference, experimenter, protocol) and free notes. |
| Figure | A page of graphs, tables and text, laid out for export. See [Figures and export](figures.md). |

### How sheets stay linked

A data table, its analyses and its graphs belong together:

- Results are never stored as fixed numbers. They are recalculated whenever the data change, including when you exclude a value.
- Graphs redraw when their data or results change. A figure shows its graphs live, so it updates too.
- Creating a data table also creates its first graph.
- Renaming a table renames the graphs that still carry its name.
- Deleting a table deletes its analyses and graphs too. ASTERISM tells you how many linked sheets will go, and you can undo it.

## The window

Each project opens in its own window. From left to right:

- **Project sidebar**: every sheet in the project.
- **Top bar** and the current sheet in the middle.
- **Tool panel** on the right: the commands for the sheet in front.

You can drag the edges between them to make the sidebars wider or narrower. Hide or show them with **View › Show Project Sidebar** (⌃⌘S on a Mac, Ctrl+Shift+L on Windows and Linux) and **View › Show Tools** (⌥⌘0 on a Mac, Ctrl+Shift+T on Windows and Linux). ASTERISM remembers the widths, and each project file reopens at its own window size and position, showing the sheet you left it on.

### Project sidebar

The sidebar lists the sheets in three sections:

- **Data**: each data table, with its results and graphs nested under it.
- **Notes**: Notes sheets.
- **Figures**: figures.

Each section has a **+** button that adds a new sheet of that kind. Click a sheet to open it. ⌘-click or Shift-click selects several (for example to give them a colour label).

Above the list:

- **Search** shows only the sheets whose names contain what you type. A table stays visible, dimmed, when one of its graphs matches, so nothing appears out of context.
- The row of coloured dots filters by [colour label](#colour-labels). Click a dot to show only sheets with that label; click it again to show everything.
- **All graphs** opens the [graph overview](#all-graphs-at-a-glance).

Right-click a sheet for its colour label, **Label Names…**, **Rename**, **Import Settings…** (imported tables only, see [Importing data](importing.md)) and **Delete**. For a data table the delete command reads **Delete and its linked sheets**.

You can drag graphs, tables and results from the sidebar onto a figure.

### Top bar

On the left is the name of the current sheet, with a short description below it (for example "Column table · 2 groups" or "Graph · scatter dot plot · 2 data sets"). Click the name to rename the sheet.

Next come small buttons for the whole project: new project, open and save; undo and redo; and print (greyed out: printing isn't available yet). Then labelled buttons: **Table**, **Graph**, **Figure** and **Notes** add a new sheet, **Analyze** opens the Analyze dialog, and **Export** exports the current graph or figure. When the window is narrow, buttons that don't fit move into a **»** menu. The last button shows or hides the tool panel.

Cut, copy and paste, the row and column commands and **Delete Sheet** are in the menus (with their shortcuts). The row and column commands are also in the tool panel, and **Delete** is in the sidebar's right-click menu.

### Tool panel

The tool panel changes with the sheet in front and lists only the commands that apply to it, by name, with their shortcuts. Each section starts with its main command as a filled button.

- **Data table**: **Analyze…**, then the analyses that fit this kind of table, grouped as *Compare groups*, *Describe*, *Fit and relate* and *Transform data*; and **Data**: insert and delete rows and data sets, exclude values, table format.
- **Graph**: **Format Graph…** and the graph commands; **Draw**: lines, arrows, boxes, ellipses, text and pictures; **Text**: font, size and style of the selected text.
- **Results**: **Analysis Settings…**, **Analyze Further…** and how the results are calculated.
- **Figure**: **Add Graphs and Tables…**, text, grid and format commands, and buttons to line panels up.

Every command in the panel is also in the menus.

### Status bar

The bar along the bottom shows which cell you are in on a data table. When you select several numbers it shows their count and mean. On graphs and figures it has a zoom slider. The button at its left end shows or hides the project sidebar.

## The Start window

The Start window appears when ASTERISM opens (and from **File › Start Window…**):

- **New project…**: choose the type of your first data table (see [Data tables](tables.md#new-table)).
- **Empty project**: start with an empty Column table.
- **Import data…**: start from a spreadsheet, a lab export or a Prism file (see [Importing data](importing.md) and [Prism files](prism.md)).
- **Open…**: open a project file.
- **Sample project**: a small project with example data to explore.

On the right are your recent projects. Double-click one, or select it and click **Open**. Projects whose files have moved or been deleted are greyed out.

Closing the Start window starts an empty project. Untick **Show this window at startup** if you'd rather go straight to an empty project; you can turn it back on in [Settings](settings.md).

## All graphs at a glance

**View › All Graphs** (⌘⇧G), or **All graphs** in the sidebar, shows a live thumbnail of every graph in the project, grouped under its data table. Use it to find a graph quickly, to compare graphs side by side, or to act on several at once.

Along the top:

| Control | What it does |
|---|---|
| **Search graphs** | Shows only graphs whose names contain the text. |
| Table type | **All table types**, or only graphs of one type of table. |
| Label | **Any label**, or only graphs with one colour label. |
| **Graphs of results** | Include graphs of analysis results (on by default). |
| **Figures** | Include thumbnails of your figures. |
| **Sort:** | **Project order**, **Name** or **Last changed**. |
| Slider | Thumbnail size. |

Click a thumbnail to select it, ⌘-click to add or remove one, Shift-click to select a run, and ⌘A to select all. Double-click a thumbnail (or press Return) to open it.

Right-click for the colour label, **Label Names…**, **Open**, **Rename…**, **Duplicate**, **Add to Figure…** and **Delete…**. With several graphs selected you can add them all to a figure in one go, or choose **Apply This Graph's Formatting to the Other** graphs to give them the look of the one you right-clicked (see [Formatting graphs](formatting.md#apply-to-other-graphs)).

## Colour labels {#colour-labels}

Colour labels help you keep track of sheets, for example which graphs are final, which still need checking, and which go in the supplement. There are seven colours: Red, Orange, Yellow, Green, Blue, Purple and Grey. A sheet has one label or none.

To label sheets:

- right-click a sheet in the sidebar, or a thumbnail in the graph overview, and click a colour (the crossed circle removes the label);
- or select sheets and choose **Sheet › Colour Label**;
- or use the shortcuts. On a Mac, Control-1 to Control-7 set a label and Control-0 removes it. On Windows, use Ctrl+Shift+1 to Ctrl+Shift+7, and Ctrl+Shift+0 to remove it. The [Keyboard shortcuts](shortcuts.md) page shows the keys on your computer.

The label applies to all selected sheets. You can undo it.

### Label names

Choose **Label Names…** (in **Sheet › Colour Label**, or on the right-click menus) to give the colours names for this project, such as "Final", "To check" or "Supplement". Leave a name empty to use the colour's own name. The names appear in menus, tooltips and the filters, and are saved with the project.

### Filtering by label

- In the sidebar, click a coloured dot under the search field.
- In the graph overview, pick a label from the label menu.

## Undo

Every change to a project can be undone: typing and pasting data, excluding values, adding and deleting sheets, formatting graphs, labels, figure layouts, and text typed on Notes sheets. Choose **Edit › Undo** (⌘Z) and **Edit › Redo**. The menu names the step, for example "Undo Paste". Undo works across the whole project, so it also undoes changes on sheets that aren't in front.

## Opening and saving

- **File › New Project** (⌘N) opens a new window with an empty Column table.
- **File › Open…** (⌘O) opens an ASTERISM project or a Prism file. A Prism file opens as a new, unsaved project (see [Prism files](prism.md)). To bring in a spreadsheet, use **File › Import Data…** (see [Importing data](importing.md)).
- **File › Open Recent** lists recent projects.
- **File › Save** (⌘S) and **File › Save As…** save the project as an `.asterism` file.
- **File › Revert to Saved** throws away your changes since the last save.
- **File › Close** (⌘W) closes the window. If there are unsaved changes, ASTERISM asks whether to save them.

You can also drag files onto a project window: projects and Prism files open, and spreadsheets (or a folder of them) are imported into the project.

The window title shows when a project has unsaved changes. ASTERISM also keeps a recovery copy of unsaved work, so a crash doesn't lose it; see [Settings, autosave and files](settings.md#autosave).

## Your first project in five steps

1. In the Start window, click **New project…**. Choose **Column** and click **Create**. (Tick **Fill the table with example data** if you want something to try things on.)
2. Type a title over each column (double-click the title cell under "Group A"), then enter one value per animal or sample down each column. Press Enter to move down.
3. Click **Analyze…** in the tool panel, choose **t test and nonparametric equivalents** (or one-way ANOVA for three or more groups), and click **Analyze**. Set the options and click **OK**. The results sheet appears under your table.
4. Click the graph under your table in the sidebar. Double-click parts of the graph, or click **Format Graph…**, to change its look. See [Graphs](graphs.md).
5. Choose **File › Save** to save the project. When the graph is ready, use **Export** to save it as PDF, SVG, PNG or TIFF, or put it on a figure with other graphs.

## Getting help

- **Help › ASTERISM Help** (⌘?) opens the help page for the kind of sheet in front.
- The **?** button in a dialog opens the help for that dialog.
- **Help › How Results Are Calculated** explains the methods behind the numbers: see [How results are calculated](methods.md).
- **Help › Keyboard Shortcuts** lists every shortcut: see [Keyboard shortcuts](shortcuts.md).
