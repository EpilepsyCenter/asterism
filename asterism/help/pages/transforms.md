# Transforms

Transforms change your numbers rather than test them: take logarithms, express values as percentages, subtract a baseline, thin out a long recording, smooth a noisy trace. Your data table is never altered. Each transform makes a new **result table** that:

- stays live: edit the data table and the result table updates, along with everything made from it;
- gets a graph of its own when you create it (except Transpose);
- can be graphed and analysed further like any data table. With the transform's result (or its graph) open, the **Analyze** menu works on the result table, and in **Analyze › Analyze…** it appears in the **Table:** list as **Results:** followed by its name.

Choose **Analyze › Transform…** or **Analyze › Normalize…** (for XY, Column and Grouped tables), or choose **Analyze › Analyze…** (⌘⇧A; Ctrl+Shift+A on Windows) and open the **Transform and normalize** section for all of them. To change a transform later, open its result and choose **Analyze › Analysis Settings…**.

**Transform**, **Normalize** and **Remove baseline** need the individual values. They don't run on a table that holds means with SD or SEM calculated elsewhere.

## Transform {#transform}

Applies a function to every Y value, and on XY tables optionally to every X value.

### Transform Y values

Choose the function in **Y =**. Functions that use a constant take it from **K =**.

- **Y × K**, **Y + K**, **Y − K**, **Y ÷ K**: change units or offsets (for example K = 1000 to turn µM into nM).
- **Y²**, **Y to the power K**, **√Y**, **1 / Y**, **|Y|** (the absolute value).
- **log₁₀(Y)**, **−log₁₀(Y)**, **ln(Y)**: logarithms, for data that spread over several orders of magnitude or whose scatter grows with the mean. −log₁₀ turns concentrations into pEC50-style values.
- **10 to the power Y**, **e to the power Y**: undo a logarithm.
- **ln(Y / (1 − Y))**: the logit, for fractions between 0 and 1.
- **arcsine √Y (proportions)**: an older way to stabilise the scatter of proportions (values from 0 to 1).
- **Z score within each data set: (Y − mean) / SD**: how many SDs each value lies from its data set's mean (all values in the data set count).
- **Your own equation**: type it in **Equation:** (see below).

### Your own equation

With **Your own equation** chosen, type a formula such as `Y = 100 * Y / K`. You can use:

- `Y`, the value being transformed;
- `X`, the row's X value on an XY table, or the row number (1, 2, 3 …) on other tables;
- `K`, the number in **K =**;
- numbers, `+` `-` `/`, the multiplication sign `*`, `^` for powers, and brackets;
- the functions `exp`, `ln` (natural log), `log` and `log10` (both base 10), `sqrt`, `abs`, `sin`, `cos` and `tan`, and the constants `pi` and `e`.

Any other name is refused, and the result sheet explains why.

### Transform X values

On XY tables, **X =** can also be changed: **Leave X alone**, **X × K**, **X + K**, **log₁₀(X)**, **ln(X)**, **1 / X**, **X²**, **√X**, **10 to the power X** or **e to the power X**, with its own **K =**. On other tables these settings are greyed out.

Values that can't be transformed, such as the log of zero or a negative number, are left blank in the result table.

> **Example:** your XY table has drug concentrations in X and you want a log(agonist) dose-response fit. Transform with **Y =** **Y × K** and **K =** 1 (Y unchanged) and **X =** **log₁₀(X)**, then fit the result table with [Nonlinear regression](analyses-xy.md#nonlinear-regression). The zero-concentration row gets no X (the log of zero doesn't exist), so it drops out of the fit.

## Normalize {#normalize}

Rescales each data set so that a value you choose becomes 0% and another becomes 100%. Use it to compare data sets with different absolute levels, such as responses from different cells or experiments.

- **0% is:** **The smallest value in each data set**, **The first value**, or **A value** (type it in **value:**).
- **100% is:** **The largest value in each data set**, **The first value**, **The last value**, **The sum of the values**, **The mean of the values**, or **A value**.
- **Show the result as:** **Percentages** or **Fractions** (0 to 1).

With replicates, the smallest, largest, first and so on come from each row's mean; every replicate is then rescaled. "The first value" means the first row that has a value. The result sheet lists the 0% and 100% values used for each data set. A data set whose 0% and 100% are the same is left empty.

> **Example:** to express a time course as a percentage of the first measurement, set **0% is:** **A value** with value 0, and **100% is:** **The first value**. The first row becomes 100%, and a later value of 80% means a 20% drop.

## Remove baseline and column maths {#remove-baseline}

Subtracts a baseline from each value, or divides by it.

**The baseline is**

- **A data set (row by row)**: pick it in **Baseline data set:**. Each value is combined with the baseline value in the same row. With **Match replicates (replicate 1 with replicate 1 …); otherwise use the baseline's mean** ticked, each replicate is paired with the same replicate of the baseline; unticked, every replicate uses the mean of the baseline's row. The baseline data set itself is left out of the result.
- **The first rows of each data set**: set how many in **Baseline rows:**. The mean of those rows (all replicates) is each data set's own baseline.

**Operation** (**Each value:**)

- **Subtract the baseline**: value − baseline.
- **Divide by the baseline**: value ÷ baseline.
- **Percent of the baseline**: value ÷ baseline × 100.
- **Percent change from the baseline**: (value − baseline) ÷ baseline × 100.

Where the baseline is missing, or is zero when dividing, the result is left blank.

> **Example:** you recorded 3 minutes of baseline before applying a drug, one row per minute. Choose **The first rows of each data set** with **Baseline rows:** 3 and **Percent change from the baseline**. Each recording now starts near 0%, and the drug's effect reads as a percentage change.

> **Example:** a plate with a vehicle control column: choose **A data set (row by row)**, pick the vehicle column, and **Subtract the baseline** to remove the background from every other column, row by row.

## Prune rows {#prune-rows}

Makes a shorter table from a long one.

- **Keep the rows with X between …** (XY tables) or **Keep rows from … to …** (other tables, by row number): fill in **From:** and **to:**. The ends are included; leave one empty to keep everything on that side.
- **Keep every nth row**: set **n:**. Keeps rows 1, 1 + n, 1 + 2n …
- **Average every k rows**: set **k:**. Each block of k rows becomes one row: the mean of all their values (replicates included) and, on XY tables, the mean of their X.

> **Example:** a recording sampled every second is too dense to graph over an hour. **Average every k rows** with **k:** 60 gives one point per minute, each the average of that minute.

## Transpose {#transpose}

Turns rows into data sets and data sets into rows, so you can graph the same numbers the other way round. The result is a Grouped table; replicates are averaged. Transpose has no settings and doesn't make a graph by itself.

## Smooth, differentiate or integrate {#smooth}

Works on XY tables. When a row has replicates, their mean is used, so the result has one value per row.

- **Smooth the curve**: replaces each point by an average of itself and its neighbours, to show the trend under the noise.
- **First derivative**: the slope between each pair of neighbouring points (the rate of change), placed at the X halfway between them.
- **Second derivative**: the derivative of the derivative (how fast the rate changes).
- **Integral (cumulative area)**: the running area under the curve from the first X, by the trapezoid rule, starting from **Integral starts at Y =**.

Smoothing settings:

- **Neighbours on each side:** how many points either side are averaged. More neighbours give a smoother curve but flatten sharp peaks.
- **Smoothing polynomial:** **Zero order (moving average)** weights all the neighbours equally; **Second order (Savitzky-Golay)** fits a small curve through them and keeps the height and width of peaks better.
- **Smooth the derivative or integral**: smooths the result of a derivative or integral as well.

Smoothing drops as many points at each end as there are neighbours, since those points don't have enough neighbours.

> **Note:** use smoothed data to display a trend, not to run statistics on. Smoothing makes neighbouring points depend on each other, and it can create apparent trends out of random noise.

> **Example:** for a growth curve (cell number against time), **First derivative** gives the growth rate at each time. Turning on **Smooth the derivative or integral** reduces the jitter that differences between neighbouring points always add.

## Observed vs. expected {#observed-vs-expected}

Tests whether counts in several categories match what you expected, for example whether offspring genotypes follow a 1 : 2 : 1 ratio, or whether animals chose four arms of a maze equally often. Unlike the transforms above, it gives a test result, not a result table. Find it in **Analyze › Analyze…** as **Compare observed and expected counts** (under **Column data**). It works on Column, Parts of whole and Contingency tables.

Enter the observed counts (whole numbers, one category per row, at least two rows) in the first data set. Then choose:

- **Expect equal counts in every category**, or
- **Expected values are in the second data set**: enter the expected values in the next data set, and set **Expected values are:** to **Counts (or relative numbers)** or **Percentages**. Expected values are scaled to the observed total, so a ratio such as 1, 2, 1 works as well as actual counts.

### Reading the results

- **Chi-square test**: chi-square, degrees of freedom and P value. A small P value means the counts differ from what you expected.
- **Exact binomial test**: added when there are exactly two categories; it is exact, so prefer it for small counts.
- A note appears when some expected counts are below 5, where the chi-square test is only a rough approximation.
- The **Observed and expected** page lists each category's observed and expected count and its residual, (O − E)/√E. Large residuals (beyond about ±2) show which categories differ most.

> **Example:** a heterozygous cross gave 18, 52 and 30 pups of genotypes +/+, +/− and −/−. Enter 18, 52, 30 in data set A and 1, 2, 1 in data set B, then choose **Expected values are in the second data set** with **Counts (or relative numbers)**.

For the formulas behind these, see [How results are calculated](methods.md).
