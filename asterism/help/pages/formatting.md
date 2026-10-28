# Formatting graphs

Almost everything about how a graph looks is set in one dialog, **Format Graph**. This page goes through its sections, then colour schemes, copying formatting between graphs, drawing on a graph and plotting a function. To choose a different kind of graph altogether, see [Graph types](graphs.md#graph-types).

Shortcuts on this page use ⌘ (the Mac command key); on Windows use Ctrl instead.

## Opening Format Graph

- **Graph › Format Graph…** (⌘⇧F), or **Format Graph…** in the Tools panel.
- **Graph › Axes…** opens it at the Y axis.
- Double-click part of the graph to open it at the matching section: a data set opens **Style** for that data set, an axis opens its axis page, a bracket opens **Significance**. The legend opens **Arrangement** (or **Slices**), or **Style** on column and XY graphs.
- Right-click the graph and choose **Format Graph…** or **Axes…**.

The sections are listed on the left, in three groups: **Graph** (Size and frame, Titles and fonts, Significance, and Arrangement, Slices or Variables for some table types), **Data sets** (Style, Show and order) and **Axes** (X axis, Y axis, Right Y axis). Parts-of-whole graphs have no Style, X axis or Right Y axis sections, and their Y axis section is called **Y axis (stacked bars)**, since only the stacked bar has a Y axis.

**Apply** draws your changes and keeps the dialog open; **OK** applies and closes; **Cancel** closes without the changes you have not applied. Each Apply is one step you can undo with ⌘Z. **Graph Type…** applies your pending changes, then opens the graph type gallery.

## Data sets: Style

One page holds everything about how a data set is drawn. The page shows only the options that apply to the plot type you choose.

### Which data sets you are changing

The **Apply to:** menu at the top of the page chooses **All data sets** or one data set; the arrows step through them. With **All data sets**, only the option you touch is changed on every data set, so differences you set earlier (one group in red, say) are kept.

### Plot

- **Plot as:** **Scatter dot plot**, **Column bar**, **Box and whiskers**, **Violin plot**, **Floating bar (minimum to maximum)** or **One symbol (mean or median)**. On XY graphs the choice is **Points (and lines)** or **Bars at each X**.
- **Summary line:** what the line and error bars show: **Mean ± SEM**, **Mean ± SD**, **Mean with 95% CI**, **Mean with range**, **Median with interquartile range**, **Median with range**, **Mean only**, **Median only** or **No summary line**. Box plots and violins always mark the median, so this is greyed out for them.
- **Show individual data points** draws every value as a symbol.
- **Arrange points:** **Side by side** spreads tied or close values sideways so each one is visible; **In a single line** stacks them in one vertical line.
- **Violin smoothing** (violins only): **Light (more detail)**, **Medium** or **Heavy (smoother shape)**.
- **Quartile / median lines** (violins only): the line style for the quartiles and for the median.

> **SD or SEM?** SD shows how spread out the values are. SEM shows how precisely the mean is known, and shrinks as you add values. To show variability, use SD (or show the points); say in the legend which one you used.

For box and whiskers, the box spans the 25th to 75th percentile with a line at the median. Values beyond the whiskers are drawn as symbols even when individual points are off.

### Axis, legend and position

- **Plot against:** **Left Y axis** or **Right Y axis** (column, grouped, contingency and XY graphs). See [Right Y axis](#right-y-axis).
- **Show in legend** includes this data set in the legend.
- **Show the legend (all data sets)** (column and XY graphs) turns the whole legend on or off, the same as **Graph › Show or Hide Legend**. Other graph types set this under Arrangement.
- **Nudge right** and **Nudge up** shift the data set by a number of points. Nudging up is for XY graphs only. You can also select a data set on the graph and use the arrow keys (Shift for 5 pt). **Graph › Nudge Data Set…** opens this page for the selected data set.

### Symbols

**Colour**, **Size** (1 to 10) and **Shape** (filled or open circle, square, triangle, diamond, cross, plus). Symbols apply when individual points are shown, and on box plots for the values beyond the whiskers.

### Lines and replicates (XY graphs)

- **Show:** **Mean with error bars**, **Each replicate**, or **Each replicate, connected (spaghetti)**.
- **Connect the points with a line**, with **Line thickness** and **Line style** (solid, dashed, dotted).
- **Break the line where a value is missing** leaves a gap instead of joining across it.
- **Label points with their row titles**.
- **A different colour for each row**.
- **Shade the area under the line**, with **Shading** as a percentage of opacity.

### Fitted curve {#fitted-curve}

Shown on XY graphs whose data sets have a fitted curve or regression line (from [Nonlinear regression](analyses-xy.md#nonlinear-regression) or [Linear regression](analyses-xy.md#linear-regression)). The settings belong to this graph only; other graphs of the same table keep their own.

- **Show the fitted curve on this graph:** untick to hide the curve here. The analysis and its results are unchanged.
- **Colour:** **The data set's colour**, or untick and choose another (for example black points with a red curve).
- **Thickness** and **Style:** **Same as the line** follows the data set's connecting line; or choose a thickness and solid, dashed or dotted.
- **Bands:** **Dashed lines**, **Shaded area** (with **Shading** opacity) or **Hidden**. Bands only exist if the analysis draws confidence or prediction bands (Analysis Settings › Confidence).

The legend's line follows the curve's colour and style when the points aren't connected. Double-clicking a curve on the graph opens this section.

### Bars

Tick the section title to draw bars. On box plots it reads **Fill the box**, on violins **Fill the violin**.

- **Fill**: the bar's colour.
- **Border** (thickness, or None) and **Border colour**.

### Error bars and whiskers

Tick the section title to draw error bars (the summary line chosen above sets what they show).

- **Colour** and **Thickness**.
- **Direction:** **Up and down**, **Up only** or **Down only**.
- **Ends:** **With caps** or **No caps**.

On box plots the section is called **Whiskers** and adds:

- **Extend to:** **Minimum to maximum**, **Tukey (1.5 × IQR)**, or the **10th–90th**, **5th–95th**, **2.5th–97.5th** or **1st–99th percentile**.
- **Mark the mean with +**.

Error bars do not apply to violins and floating bars.

## Data sets: Show and order

- **Join each row's values across data sets with a line (before-after)** draws paired data: each row's values joined across the groups. Set the **Line thickness** and **Line colour**. **Beside the points** adds a summary next to the dots: **Mean ± SD**, **Mean ± SEM**, **Mean with 95% CI** or **Median with interquartile range** (or **Nothing**).
- **Data sets and their order:** untick a data set to leave it out of this graph (the data stay in the table and in analyses). Drag data sets in the list, or select one and click **Move Up** or **Move Down**, to change their order on the graph: left to right, bottom to top in a stack, the drawing order on XY graphs, and the order in the legend. **Table Order** puts them back in the order of the table's columns. The order belongs to this graph only; the table and other graphs are unchanged.
- **Fitted curves on this graph** (XY graphs with fits): untick a data set's fit to hide its curve on this graph; the same switch as in Style › Fitted curve.

## Arrangement

This section appears for grouped, contingency, nested and survival graphs. Parts-of-whole graphs have a **Slices** section instead (below).

**Grouped and contingency graphs**

- **Arrange as:** **Side by side**, **Separated**, **Stacked**, **Stacked to 100%**, **Connected means** (one line per data set), **Heat map** or **Back to back** (the first data set to the left or down, the second to the right or up).
- **Connected means: also show each replicate**.
- **Show a legend for the data sets**. On stacked bars the legend lists the top segment first, in the same order as the stack.
- **Heat map colours:** the colours for the **Lowest value** and **Highest value**. The heat map's colour range follows the Y axis range: automatic, or the minimum and maximum you set on the Y axis page.

**Nested graphs**

- **Arrange as:** **Each subject in its own column**, **All values together, coloured by subject**, or **SuperPlot** (values coloured by subject, with subject means).

*Colours*

- **Colour points by:** **Subject** (a colour for each subject) or **Data set** (every point takes its data set's symbol colour from the Style page).
- **Subject colours:** **Continue across groups** gives every subject in the table its own colour. **Start again in each group** reuses the colours in each group, so subject 1 of one group matches subject 1 of the next. This is the usual choice for a SuperPlot when the same experiment or culture appears in every group.
- **Colour set:** fills the subject colours from **Distinct (default)**, **Colour-blind safe**, **Viridis**, **Greys**, **Warm** or **Cool**.
- Below, each subject has its own colour button: click one to change that colour.

The subject colours apply only when you colour points by subject.

*Subject means (SuperPlot)*

- **Size:** the subject-mean symbols, as a multiple of the points (**× the points**).
- **Outline:** the colour of their outline.

**Survival graphs**

- **Plot:** **Percent surviving**, **Fraction surviving**, **Percent with the event (deaths)** or **Fraction with the event**. The Y-axis title follows unless you have typed your own.
- **Confidence intervals:** **No confidence bands**, **Dashed lines**, **Shaded band** or **Error bars at each step**. The bands use the log-log method, as the survival analysis does by default.
- **Mark censored subjects with a tick**.
- **Show a legend for the groups**.

**Multiple-variable graphs** have a **Variables** section instead: the variable on the **X axis**, the variables on the Y axis (each one ticked is a data set), what **Symbol size shows** and what **Colour shows**, the **Smallest bubble** and **Largest bubble**, the colours for **Low values** and **High values** (for a numeric colour variable; a text variable such as Sex gives one colour per group), **Label each point with its row title** and **Show a legend**.

## Slices

Parts-of-whole graphs set everything about the chart here.

**Chart**

- **Draw as:** **Pie chart**, **Donut chart**, **Bar stacked to 100%** or **Percentage dot plot (100 squares)**.
- **Label the slices with:** **Percentages**, **Values** or **No labels**.
- **Diameter / height:** the size of the chart in millimetres (the same as the plot height on Size and frame).
- **Donut hole:** its size as a percentage of the radius (donut charts only).
- **Order:** **Standard (row order)** or **Reverse**.

**Slices**

Each row of the table is listed with a **Colour** and a **Pull out** percentage. Pull out moves that slice away from the centre, to draw attention to it (pie and donut charts only). **Automatic Colours** gives every slice its automatic colour again.

**Borders**

- **Outer**: a line around the whole chart.
- **Between slices**: the lines separating the slices.

Each has its own thickness and colour.

**Legend**

- **Show a legend for the slices**, and what each entry shows: **Colour**, **Row title**, **Percentage** and **Value**. Percentages and values appear in the legend only when the graph shows one data set. On a stacked bar the legend lists the top segment first.

**Total**

- **Show the total under each chart**, with text to put **Before** and **After** the number (for example "Total = " and " cells").

## Axes

### Range and scale

- **Scale:** **Linear** or **Logarithmic (base 10)**.
- **Choose the range and tick interval automatically**: untick it to set **From**, **To** and **Tick every** yourself. With automatic on, the boxes show the range ASTERISM chose, a good starting point for your own.

### Ticks

- **Ticks:** **Outside**, **Inside**, **Crossing** or **None**, and their **Length**.
- **Minor ticks between** the major ticks: none, 1, 2, 4 or 9.
- **Numbers:** **Show** or **Hide**.

### Number format

- **Style:** **Decimal (1500)**, **Power of ten (1.5×10³)**, **Scientific (1.5e+03)**, or **Antilog: values are log10 (10³)** for data you have already log-transformed, so the axis reads in the original units.
- **Decimals:** **Automatic** or 0 to 5.
- **Before numbers** and **After numbers**: text added to every number, such as a unit or %.

### Grid lines, extra ticks and bands

- **Grid lines at the major ticks**, with a colour.
- A small table adds up to four extra marks per axis. Type a value to draw a line or tick there; fill in **To (band)** as well to shade the band between the two values. For each row choose **Line**, **Tick**, the **Style** (dashed, dotted, solid) and an optional **Label**. Use it for a baseline, a threshold or a treatment period.

### Axis breaks

**Break the axis into two segments** when one group's values are far larger than the rest.

- **Bottom segment ends at** and **Top segment starts at**: the values on either side of the gap.
- **Bottom ticks every** and **Top ticks every**: tick spacing in each segment (0 = automatic).
- **Bottom segment length**: its share of the axis, as a percentage.
- **Gap**: the space between the segments, in points.

A break needs a linear scale.

### X axis

On graphs with a numeric X axis (XY, survival and multiple-variable graphs) the X axis page also has:

- **Scale** (linear or logarithmic) and **Automatic**; untick it to set the **Minimum**, **Maximum** and **Major ticks every**;
- **Numbers**: the number style, as for the Y axis;
- **Dates as**, when X holds dates, to choose the date format;
- the **X-axis title**;
- grid lines and extra ticks, lines and bands, as for the Y axis.

On all graphs it sets the **Ticks** and their **Length**, and the **Label angle** for the X labels: **Horizontal**, **Angled 45°** or **Vertical**. Angle long group names so they don't overlap.

### Right Y axis {#right-y-axis}

A second Y axis on the right, for a data set measured in other units. Available on column, grouped, contingency and XY graphs (not on stacked or horizontal ones).

- Tick the data sets to plot against it. This is the same setting as **Plot against** on the Style page.
- Give it a **Title**.
- It has its own range, ticks, number format, grid lines, extra ticks and break, as above.

## Titles and fonts

- **Graph title** and **Y-axis title** (the X-axis title of a numeric X axis is on the X axis page). You can also double-click a title on the graph to edit it there.
- **Fonts:** font, size, **Bold** and **Italic** for each kind of text: graph title, Y-axis title, Y-axis numbers, X-axis labels, significance P values, significance stars and legend.

The Text tools in the Tools panel change fonts directly on the graph; see [Graphs](graphs.md).

## Size and frame

- **Column width** (graphs with groups) or **X-axis length** (graphs with a numeric X axis), and **Plot height**, in millimetres. These set the plot area; the graph exports at this size.
- **Orientation** (column, grouped, contingency and nested graphs): **Vertical (columns go up)** or **Horizontal (bars go across)**.
- **Frame:** **Axes only**, **Axes, offset from the data** (the axes stand a little apart from the data, a common journal style) or **Closed box**.
- **Line thickness** and **Line colour** of the axes.
- **Show the graph title**.

## Significance

How [significance brackets](graphs.md#significance-brackets) look and which comparisons they show.

- **Draw significance brackets for comparisons in linked analyses** turns them all on or off (the same as **Graph › Show Significance**).

**Which comparisons**

- **Multiple comparisons:** **Only the significant ones**, **All of them**, **Only those against a control** (choose the **Control** data set) or **None**.
- **Significant when P <**: 0.05, 0.01, 0.001 or 0.10.
- **Show “ns” for a two-group test that isn't significant**.
- A list of every comparison with its P value: untick one to hide its bracket. Right-clicking a bracket on the graph does the same.

**Label**

- **Show:** **Stars** (from "ns" up to four stars), **P value (P = 0.0123)**, **Number only (0.0123)** or **Stars and P value**.
- **Stars:** the P value thresholds for one, two, three and four stars: **Four levels: 0.05, 0.01, 0.001, 0.0001**, **Three levels: 0.05, 0.01, 0.001**, **Prism's style: 0.0332, 0.0021, 0.0002, 0.0001**, or **My own thresholds** (type them in **Thresholds**, separated by commas).
- **At most:** the largest number of stars shown (1 to 4).
- **Size of stars** and **Size of P values** (the same sizes as on Titles and fonts).

Say in your figure legend which thresholds the stars mean.

**Lines**

- **Shape:** **Bracket with end ticks** or **Plain line**; **End ticks** sets the length of the ends.
- **Thickness** (or **Same as the axes**) and **Colour**.

**Placement**

- **Stacking:** **Shortest brackets lowest** or **In the analysis's order**.
- **Above the data**: the gap between the data and the lowest bracket.
- **Between levels**: extra space between stacked brackets.
- **Label gap**: the space between a line and its label.

## Colour schemes

**Graph › Colour Scheme** (or **Colour Scheme** in the Tools panel) recolours the data sets in one step. Each data set shown gets the next colour pair of the scheme, a lighter fill for bars and boxes and a darker colour for symbols.

| Scheme | Good for |
|---|---|
| ASTERISM | The default colours |
| Greys (print) | Black-and-white printing |
| Colour-blind safe (Okabe–Ito) | Readers with colour-vision deficiency |
| Viridis | An ordered series, such as increasing doses |
| NED-Net teal | Matching NED-Net's look |
| Warm | Reds and oranges |
| Pastel | Soft colours |
| Black and white | White and black only |

You can still change any single colour afterwards on the Style page. To give every new graph a scheme, see Settings below.

## Apply formatting to other graphs {#apply-to-other-graphs}

Once one graph looks right, copy its formatting to others instead of repeating the work. With that graph open, choose **Graph › Apply Formatting to Other Graphs…**.

- **To these graphs:** tick the graphs to change. Graphs of another table type are marked with their type in the list.
- **What to copy:** tick what to carry over:
  - **How the data sets are drawn (symbols, bars, error bars, colours)**
  - **Axis formatting (ticks, numbering, scale) — not the ranges**
  - **Axis ranges** (off at first, since different data usually need different ranges)
  - **Size and frame**
  - **Fonts**
  - **Significance brackets**
  - **Arrangement (grouped, nested, XY, survival and pie options)**

Data set styles are copied by position: the first data set's style goes to the first data set of each target graph, the second to the second, and so on. Titles are never copied. All the changes are one step you can undo.

You can also do this from the [graph overview](graphs.md#all-graphs-at-a-glance): select several graphs, right-click the one whose formatting you want, and choose **Apply This Graph's Formatting to the Other …** (the menu item says how many). That copies everything except the axis ranges.

## Drawings {#drawings}

Add lines, arrows, boxes, ellipses, text and pictures on top of a graph, for example to mark a stimulus period or label a peak. The tools are in **Graph › Draw** and the **Draw** group of the Tools panel: **Line**, **Arrow**, **Box**, **Ellipse**, **Text** and **Picture…**.

**Drawing**

- Choose a tool, then drag on the graph. A click without dragging makes a shape of a default size.
- Hold Shift while dragging to keep lines at 45° steps and boxes and ellipses square.
- With **Text**, click where the text should go and type. Return finishes.
- **Picture…** places an image file (PNG, JPEG, TIFF, BMP or GIF) in the middle of the plot.
- Esc cancels a tool.

**Changing drawings**

- Click to select, drag to move, or use the arrow keys (Shift for 5 pt steps).
- Drag the round handles to reshape: both ends of a line or arrow, the far corner of a box, ellipse or picture.
- Double-click a drawn text to edit it; emptying it removes it. Double-click any other drawing to open its Format dialog.
- Delete or Backspace removes the selected drawings.
- **Bring to Front** and **Send to Back** change which drawing lies on top. **Align Drawings** lines up two or more selected drawings by their left edges, centres, right edges, top edges, middles or bottom edges.
- Right-click a drawing for **Format…**, **Bring to Front**, **Send to Back**, **Align** and **Delete**.

**The Format dialog**

- Lines, arrows, boxes and ellipses: **Thickness**, **Style** (solid, dashed, dotted) and **Colour**. Arrows add **Arrowheads**: **At the end** or **At both ends**. Boxes and ellipses add **Fill the shape** with a fill **Colour**.
- Text: the text itself, **Size**, **Colour**, **Bold** and **Italic**. The Text tools in the Tools panel work on drawn text too, including **Align Left**, **Centre** and **Align Right**.
- **Position**, in millimetres from the top-left corner of the plot area: **Left** and **Top** with **Width** and **Height** for shapes and pictures, **Start X**, **Start Y**, **End X** and **End Y** for lines and arrows.

Drawings belong to the graph: they are saved with it, export with it and appear with it on figures.

## Plot a function {#plot-a-function}

Draw a curve from an equation on an XY graph, for example a theoretical curve to compare with your data or a fit from a paper. Open the XY graph and choose **Graph › Plot a Function…**.

**Equation**

Type the equation in X, such as `Y = Y0*exp(-K*X)` or `Y = Bottom + (Top-Bottom)/(1+10^((LogEC50-X)*HillSlope))`. You can use:

- `X` (or `x`) and numbers;
- `+`, `-`, `*`, `/` and `^` (power), with brackets for grouping;
- the functions `exp`, `ln` (natural log), `log` and `log10` (base 10), `sqrt`, `abs`, `sin`, `cos` and `tan`;
- `pi` and `e`.

Every other name is a constant. Write multiplication out in full (`2*X`, not `2X`). Other names are case-sensitive: `K` and `k` are two different constants. If the equation can't be read, a message in red says why and **OK** stays greyed out.

**Constants**

Each constant in the equation is listed with a **Value** (1 to begin with). Type the value you want.

**Range and line**

- **Across the whole X axis**, or untick it and set **From X =** and **To X =**.
- **Colour**, **Thickness** and **Style** (solid, dashed, dotted) of the curve.

To change the function later, double-click the curve, or right-click it and choose **Edit Function…**. **Remove Function** deletes it. A graph can hold several functions.

To fit a curve to your data instead, use [Nonlinear regression](analyses-xy.md#nonlinear-regression).

## Defaults for new graphs

The font, font size, axis thickness, frame, plot height, column width, colour scheme and significance style that new graphs start with are set in **Settings… › New graphs**. They apply only to graphs you create afterwards, never to existing ones. See [Settings, autosave and files](settings.md).
