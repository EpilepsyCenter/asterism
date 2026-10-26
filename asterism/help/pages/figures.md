# Figures and export

A figure is a page that holds several graphs, tables, results and text boxes, laid out the way you want them in a paper, poster or report. The graphs on it stay live: change the data and the figure updates. This page also covers exporting graphs and figures as files.

Prism users: ASTERISM calls Prism's layouts *figures*.

Shortcuts on this page use ⌘ (the Mac command key); on Windows use Ctrl instead.

## Making a figure

- **Sheet › New Figure** makes an empty page (A4, portrait, to begin with).
- From a graph, **Graph › Add to Figure…** places it on an existing figure or on a **New figure**.
- In the [graph overview](graphs.md#all-graphs-at-a-glance), select several graphs, right-click and choose to add them to a figure.

Figures are listed in the project sidebar. All the tools below are in the **Figure** menu and the **Figure** group of the Tools panel.

## Adding graphs, tables and results

**Figure › Add Graphs and Tables…** opens a list in three sections:

- **Graphs**: any graph in the project;
- **Data and result tables**: data tables, and the results tables of analyses such as transforms;
- **Analysis results**: the results of an analysis, as a table.

Tick what you want, set **Place new panels in columns:** (1 to 6 per row) and click **Add**. The new panels are placed below what is already on the page, in rows, and shrunk if needed to fit the page width.

You can also drag graphs, tables and analyses from the project sidebar onto the page; they land where you drop them.

Each panel is linked to its sheet. A graph panel redraws when its data, analyses or formatting change; a table or results panel updates with its table or analysis. If you delete a sheet that a figure uses, its panel shows a placeholder (undo brings the sheet back).

To change a graph, edit the graph itself: double-click its panel (or right-click › **Open**) to go to it. To show a different page of an analysis's results, right-click the panel and choose **Show Results Page**.

## Moving, resizing and arranging

- **Select** a panel by clicking it; drag across empty space or ⌘-click to select several.
- **Move** panels by dragging. They snap to the grid and to the edges of other panels (see [Page format](#page-format)).
- **Nudge** selected panels with the arrow keys: 1 mm per press, 5 mm with Shift.
- **Resize** by dragging the small square at the bottom-right corner of a selected panel. Graphs and tables scale as a whole, keeping their proportions, so text and lines scale with them. Text boxes change width and height instead.
- **Remove** a panel with Delete or Backspace, or right-click › **Remove from Figure**. This removes the panel only, never the graph or table.

Arranging several panels (select two or more first):

| Tool | What it does |
|---|---|
| Align Left Edges | Lines up the left edges |
| Align Top Edges | Lines up the top edges |
| Align Centres | Centres the panels on one vertical line |
| Same Width | Scales graphs and tables to the width of the first one selected |
| Arrange in a Grid… | Places the selected panels (or all, if none is selected) in rows, with the number of **Panels per row** you choose, in reading order |
| Bring to Front, Send to Back | Changes which panel lies on top where panels overlap |

Every change to a figure is one step you can undo with ⌘Z.

> **Tip:** to make panels the same size, give their graphs the same plot height and column width in [Format Graph](formatting.md) rather than resizing panels by eye. Then the fonts and lines also match across panels.

## Overlaying two graphs

Select exactly two graph panels, right-click and choose **Overlay Graphs (line up the plot areas)**. The front graph moves onto the back one and is scaled to match, so their plot areas line up, and it loses its own panel letter. Use it to show data from two tables on one set of axes. For the overlay to read correctly, give both graphs the same axis ranges and size.

## Panel letters

ASTERISM labels graph, table and results panels A, B, C… in reading order: rows from top to bottom, then left to right. Text boxes are not lettered. The letters update when you move panels.

Right-click a panel and choose **Panel Letter** to change it: **Automatic**, **None**, or **Custom…** to type your own label.

The letter style, font, size and position are set in Format Figure (below).

## Text

**Figure › Add Text** opens a box for the text and its **Size**. The new text box is placed near the bottom of the page across its width, ready for a figure legend. Double-click a text box to edit it; drag its corner to change its width and height.

## Page format {#page-format}

**Figure › Format Figure…** has three sections.

**Page**

- **Page:** **A4**, **US Letter**, **A5** or **Custom**. Set **Width** and **Height** (in millimetres) for a custom page, for example to match a journal's column width.
- **Orientation:** **Portrait** or **Landscape**.

A figure exports at exactly this page size.

**Panel letters**

- **Label the panels with letters (in reading order)**.
- **Style:** A, B, C · a, b, c · (A), (B), (C) · A., B., C. · (a), (b), (c).
- **Position:** **Outside the panel's top-left corner** or **Inside the top-left corner**.
- **Font**, **Size** and **Bold**.

**Grid**

- **Snap panels to the grid (and to each other's edges)**.
- **Grid spacing**, in millimetres.

## Exporting {#exporting}

Export the graph or figure that is open with **File › Export PDF…** (⌘E), **Export SVG…**, **Export PNG…** or **Export TIFF…**. The same commands are in the **Export** button at the right end of the top bar. You choose the file name and folder; the file is named after the graph or figure to begin with.

| Format | Kind | Use it for |
|---|---|---|
| PDF | Vector, live text | Journals, and editing in Illustrator or Affinity |
| SVG | Vector, live text | Editing in Illustrator, Affinity or Inkscape; every element is a named group |
| PNG | Image, 300 dpi unless you change it | Slides, documents, the web |
| TIFF | Image, 300 dpi unless you change it | Journals that ask for TIFF |

Vector files (PDF, SVG) stay sharp at any size and keep the text as text, so you can still correct a label in a drawing program. In an SVG, each part of the graph (each data set, each axis, the brackets, the title) is its own named group; in a figure, each panel is a group named after its letter, holding that graph's own groups. Use PDF or SVG whenever the receiver accepts them, and PNG or TIFF only when an image is required.

### Size and resolution

- **A graph** exports at the size it is drawn, the size you set in [Size and frame](formatting.md#size-and-frame), plus a narrow margin around everything on it. What you see at 100% zoom is what you get.
- **A figure** exports at exactly its page size, with a white background.
- PNG and TIFF are drawn on white at 300 dpi. To change this, choose 150, 600 or 1200 dpi under **Settings… › General › PNG and TIFF resolution** (see [Settings, autosave and files](settings.md#settings)). Journals often ask for 300 dpi for photos and 600 to 1200 dpi for line art.

To get a graph at a particular size, set its plot height and column width (or X-axis length) in millimetres in Format Graph, rather than scaling the exported file.

## Copying and printing

**Copy Graph to Clipboard** and **Print…** are shown in the menus but are not available yet (they are greyed out). Export a PDF instead: you can place it in Word, PowerPoint or Keynote, or print it from any PDF viewer.

Copying to the clipboard is planned for macOS only. On Windows, export a file and insert that.
