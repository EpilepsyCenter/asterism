# Graphs

A graph in ASTERISM is drawn from one data table (or from the results of an analysis). It stays linked: when you change a value, exclude a point or change an analysis, the graph redraws. This page covers making graphs, choosing a graph type, editing on the graph itself, significance brackets and the overview of all graphs. For the Format Graph dialog, colour schemes, drawings and plotted functions, see [Formatting graphs](formatting.md).

Shortcuts on this page use ⌘ (the Mac command key); on Windows use Ctrl instead.

## Making a graph

- **A new data table comes with a graph.** When you create a table, ASTERISM also creates its starter graph, listed under the table in the project sidebar.
- **More graphs of the same table:** select the table (or any sheet under it) and choose **Sheet › New Graph**. Each graph has its own type and formatting, so you can show the same data as bars in one graph and as a scatter plot in another.
- **Graphs of results:** some analyses make a graph of their own results table, for example a frequency distribution, a transform or normalization, or a residual or QQ plot when you ask for one in the analysis settings. These graphs are listed with the analysis and update with it. A new graph of results starts from the format of the data's own graph when both plot the same kind of table.
- **Fitted lines and curves** from linear or nonlinear regression are drawn on the XY graph of the data, unless you untick **Draw the line on the graph of the data** (or **Draw the curve on the graph of the data**) in the analysis settings. See [Regression and curves](analyses-xy.md).

Graph sizes are set in millimetres, and the graph is drawn at its final size: what you see at 100% zoom is what exports. A graph sheet shows the graph alone on white, centred in the window. Pages with several graphs are [Figures](figures.md).

## Graph types {#graph-types}

Choose **Graph › Graph Type…**, or click **Graph Type…** at the bottom of the Format Graph dialog. The gallery shows the types available for the graph's table type, each previewed with your own data.

Click a type and then **Apply**, or double-click it. The new type changes how every data set is drawn, in one step you can undo (⌘Z). The rest of the formatting (titles, axes, fonts, size) is kept. Every type is a starting point: you can change any part of it afterwards in [Format Graph](formatting.md).

### Column graphs

For column tables (one group per column).

| Type | What it shows |
|---|---|
| Scatter, mean ± SEM | Every value as a dot, spread side by side, with a mean line and SEM error bars |
| Scatter on bars | The same dots on top of a bar at the mean |
| Bars, mean ± SD | Bars at the mean with SD error bars, no dots |
| Bars with points | Bars with SD error bars and every value as a dot |
| Bars, mean with range | Bars at the mean, error bars from the smallest to the largest value |
| Box and whiskers | Box from the 25th to the 75th percentile, line at the median, whiskers to the minimum and maximum |
| Box (Tukey) with points | Box with Tukey whiskers (1.5 × IQR) and every value as a dot |
| Violin | The shape of the distribution |
| Violin with points | The violin with every value as a dot |
| Mean ± SEM, one symbol | One symbol per group at the mean, with SEM error bars |
| Floating bars (min to max) | A bar from the smallest to the largest value, with a line at the mean |
| Aligned dots, median | Dots in a single vertical line with a line at the median |
| Before-after | Dots in a line, each row joined across the groups (paired data) |
| Horizontal bars, mean ± SD | Bars going across instead of up |
| Horizontal bars with points | Horizontal bars with every value as a dot |

> **Tip:** with few values per group (say under 10), show the points. A bar alone hides how many values there are and how they spread.

### Grouped graphs

For grouped tables (rows are one factor, data sets the other). Most types show bars, dots, boxes or violins in one of several arrangements, which you can also change later under **Format Graph › Arrangement**.

| Type | What it shows |
|---|---|
| Bars side by side, mean ± SD | In each row, the data sets' bars next to each other |
| Bars side by side, with points | The same, with every replicate as a dot |
| Scatter side by side, mean ± SEM | Dots with mean and SEM, side by side in each row |
| Box and whiskers side by side | A box per data set in each row |
| Violins side by side | A violin per data set in each row |
| Separated bars | One block per data set, its rows next to each other |
| Stacked bars | The data sets stacked on top of each other in each row |
| Stacked bars to 100% | Stacks scaled so each row totals 100% |
| Connected means ± SEM | One line per data set joining its means across the rows |
| Each replicate, with connected means | The connected means plus every replicate |
| Heat map | Each row × data set cell coloured by its value |
| Horizontal bars side by side | Side-by-side bars going across |
| Horizontal stacked bars | Stacked bars going across |
| Bars extending left and right | Back to back: the first data set to one side, the second to the other (for example, two sexes in an age pyramid) |

### Nested graphs

For nested tables, where each sub-column is one subject (an animal, a culture) holding replicate measurements.

| Type | What it shows |
|---|---|
| Each subject in its own column | Every subject's values in a column of their own, grouped by treatment |
| All values, coloured by subject | All values of a group together, each subject in its own colour |
| SuperPlot (subject means) | The values coloured by subject, with each subject's mean marked |
| SuperPlot on bars | The SuperPlot on top of bars |
| Box and whiskers with points | A box per group with every value as a dot |

A SuperPlot shows both levels at once: the spread of the replicates and the subject means that the nested test compares.

### XY graphs

For XY tables (a numeric X and one or more Y data sets).

| Type | What it shows |
|---|---|
| Points, mean ± SEM | A point at each X with SEM error bars over the replicates |
| Points and connecting line | The same points joined by a line |
| Line only | A line through the means, no points or error bars |
| Each replicate | Every replicate as its own point |
| Each replicate connected (spaghetti) | Each replicate column as its own line |
| Line with shaded area | A line with the area under it shaded |
| Bars at each X, mean ± SD | A bar at each X value |

If the X column is entirely empty, the values are plotted against their row number.

### Contingency graphs

For contingency tables (counts).

| Type | What it shows |
|---|---|
| Bars side by side (counts) | The counts of each outcome next to each other |
| Separated bars | One block per outcome |
| Stacked bars (counts) | The outcomes stacked in each row |
| Stacked to 100% (percentages) | Each row as percentages of its total |
| Heat map | Each cell coloured by its count |

### Parts of whole

For parts-of-whole tables: **Pie chart**, **Donut chart**, **Bar stacked to 100%** and **Percentage dot plot** (100 squares, coloured in proportion).

### Survival graphs

For survival tables (Kaplan-Meier curves).

| Type | What it shows |
|---|---|
| Survival curves with censoring ticks | Step curves, with a tick where a subject was censored |
| With confidence bands (dashed) | Confidence limits as dashed lines |
| With confidence bands (shaded) | Confidence limits as a shaded band |
| With confidence intervals as error bars | Error bars at each step |
| Cumulative deaths | The curve turned upside down: the share that has had the event |

### Multiple-variable graphs

For multiple-variable tables (one row per subject, one column per variable).

| Type | What it shows |
|---|---|
| Scatter of two variables | One variable against another |
| Bubble plot (a third variable as size) | Symbol size shows a third variable |
| Coloured by a variable | Symbol colour shows a variable (numeric or text, such as Sex) |
| Bubbles sized and coloured by variables | Both at once |
| Points labelled with row titles | Each point labelled with its row title |

Which variables go on the axes, size and colour is set under **Format Graph › Variables**.

## Live updating

A graph is a description of how to draw its data, not a picture. ASTERISM redraws it whenever something it depends on changes:

- values typed, pasted, imported or excluded in the data table;
- data sets added, removed or renamed (the names appear on the axis and in the legend);
- the results of linked analyses (significance brackets, fitted curves);
- for graphs of results, the analysis that produced them.

The same graph placed on a figure updates there too.

## Editing on the graph

You can change most things by working on the graph itself.

### Selecting and moving

- **Click** an element to select it: a data set, an axis, a title, a bracket, the legend or a drawing. Selection handles appear around it. Drag across empty space to select several elements.
- **Drag** titles, significance brackets, the legend and drawings to move them. The graph itself stays centred.
- **Arrow keys** nudge a selected data set sideways by 1 pt (5 pt with Shift). On XY graphs you can also nudge it up and down, for example to make a waterfall plot. Selected drawings move with the arrow keys too.
- **Double-click** a data set, an axis, a bracket or the legend to open Format Graph at the matching section. Double-clicking a data set picks that data set in the dialog.
- **Right-click** for a menu: **Format Graph…**, **Axes…**, and for brackets **Hide this comparison** and **Format significance…**.

Every change is one step you can undo with **Edit › Undo** (⌘Z).

### Editing text in place

Double-click the graph title or an axis title to edit it on the graph. Press Return to finish (Shift+Return starts a new line) or Esc to cancel. Emptying the graph title hides it.

### Text tools

The **Text** group of the Tools panel on the right changes the fonts of the selected text: font, size, **Bold** (⌘B), **Italic** (⌘I) and **Underline** (⌘U), and **Text Colour…**. With nothing selected, the change applies to all the text on the graph.

While you edit a text in place you can also:

- select characters and choose **Superscript** (⌘⇧=) or **Subscript** (⌘=), for units such as cm² or names such as CO₂. These are real Unicode characters, so they survive every export. Choosing it again turns them back;
- insert a character from **Symbol (Greek, ±, µ…)**: Greek letters, maths signs, units, arrows and marks.

**Align Left**, **Centre** and **Align Right** apply to text you have drawn with the Text tool (see [Drawings](formatting.md#drawings)).

### Zoom

Use the zoom slider in the status bar, or hold ⌘ and scroll. Zoom only changes the view, never the graph's size.

## Significance brackets

When a graph's data table has an analysis that compares groups, ASTERISM draws the result on the graph as brackets labelled with stars or P values. These come from:

- t tests and their nonparametric versions (one bracket for the two groups);
- multiple comparisons after a one-way ANOVA, Kruskal-Wallis or Friedman test;
- multiple comparisons after a two-way ANOVA;
- multiple t tests on two data sets (one bracket per row);
- nested t tests and nested one-way ANOVA.

See [Comparing groups](analyses-groups.md) for the tests themselves.

Brackets appear on column, grouped (except heat maps) and nested graphs, including horizontal ones. They are not drawn on XY, survival, parts-of-whole or multiple-variable graphs.

### Which comparisons are shown

- A two-group test always shows its result, as stars or "ns" when it is not significant (you can switch the "ns" off).
- For multiple comparisons, ASTERISM shows only the significant ones at first, so the graph does not fill with "ns" brackets. You can show all of them, only those against a control group, or none.
- Brackets stack upwards without overlapping, the shortest ones lowest.
- The results update with the analysis: change its settings or the data and the brackets follow.

### Changing brackets

- **Hide one bracket:** right-click it and choose **Hide this comparison**. To bring hidden ones back, right-click the graph and choose **Show all comparisons**.
- **Move a bracket:** drag it.
- **Turn all brackets on or off:** **Graph › Show Significance**.
- **Leave out one analysis:** untick **Show the comparison on the linked graph** (or **Show significant comparisons on the linked graph**) in that analysis's settings.
- **Everything else** (stars or P values, star thresholds, which comparisons, line shape and spacing): **Format Graph › Significance**, described in [Formatting graphs](formatting.md#significance). Double-clicking a bracket opens it.

## All graphs at a glance

**View › All Graphs** (⌘⇧G), or the **All graphs** row at the top of the project sidebar, shows every graph in the project as a live thumbnail, grouped under its data table. It helps you find a graph in a large project and work on several at once.

- **Click** to select a graph, ⌘-click to add to the selection, Shift-click to select a range, ⌘A to select all.
- **Double-click** a thumbnail, or press Return, to open the graph.
- **Right-click** for: a colour label, **Label Names…**, **Open**, **Rename…**, **Duplicate**, **Add to Figure…** and **Delete…**. With several graphs selected you can add them all to a figure, or apply the formatting of the graph you right-clicked to the others (everything except the axis ranges).

Above the thumbnails:

- **Search graphs** filters by name;
- the table-type and label menus show only graphs of one table type or with one [colour label](start.md#colour-labels);
- **Graphs of results** includes or hides graphs made by analyses;
- **Figures** adds your figures as a group of their own;
- **Sort** orders the graphs by project order, name or last changed;
- the slider sets the thumbnail size.

The thumbnails redraw when a graph changes. The overview is a view, not a sheet: nothing about it is saved in the project.
