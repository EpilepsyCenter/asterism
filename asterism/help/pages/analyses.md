# Analyses

An analysis in ASTERISM is its own sheet. It stays linked to the data table it came from: change a value and the results, and any graph that shows them, update straight away. This page covers how to start an analysis, how results sheets work, and how to choose a test. Each analysis has its own section on the other analysis pages.

Shortcuts on this page use ⌘ for the Mac command key; on Windows use Ctrl instead.

## Starting an analysis

There are two ways in.

- **The Analyze dialog.** Choose **Analyze › Analyze…** (⌘⇧A), or click **Analyze** at the top of the tool panel on the right. You pick the analysis and exactly which data sets to include.
- **The quick commands.** The **Analyze** menu, and the Analyze group in the tool panel, also list the common analyses by name (**One-way ANOVA…**, **Normality Tests…**, **Two-way ANOVA…**, **Nested t Test or ANOVA…** and so on). These skip the Analyze dialog and use *every* data set of the current table, going straight to the analysis's settings. Commands that don't fit the current table type are greyed out.

The quick commands have two exceptions. **Descriptive Statistics** has no settings, so its results appear at once. **Multiple t Tests…** compares exactly two data sets, so if the table has more than two it opens the Analyze dialog so you can choose two.

There is no quick command for the t test: use the Analyze dialog and tick the two data sets you want to compare.

## The Analyze dialog

The dialog has three parts.

- **Categories** in the sidebar on the left: **Column data**, **Grouped data**, **Nested data**, **XY data**, **Counts**, **Survival**, **Parts of whole** and **Transform and normalize**. The dialog opens on the category that matches the current table.
- **The analyses** of that category, with a short description below the list. Type in **Find an analysis** at the top to search names and descriptions across all categories. Analyses marked *(coming later)* are listed so you can see what is planned; they can't be run yet.
- **Data to analyze** at the bottom. **Table:** picks the table (the current one is chosen for you). Result tables made by other analyses, such as a transform or a frequency distribution, are listed too, as "Results: …". Below it, tick the data sets to include; **All** and **None** tick or clear them all.

Click **Analyze** (or double-click the analysis) to go on to its settings. When you click **OK** in the settings, the results sheet opens.

### Which analyses work on which tables

| Table | Analyses offered |
|---|---|
| Column | t test, one-way ANOVA, one-sample tests, descriptive statistics, normality tests, frequency distribution, outlier detection, correlation, observed vs. expected counts, fraction of total |
| Grouped | two-way ANOVA, multiple t tests, chi-square and Fisher's test, fraction of total |
| Nested | nested t test, nested one-way ANOVA |
| XY | nonlinear regression, linear regression, correlation, area under the curve, smoothing; two-way ANOVA and multiple t tests when the XY table has replicates |
| Contingency | chi-square and Fisher's test, fraction of total, observed vs. expected counts |
| Survival | Kaplan-Meier survival analysis |
| Parts of whole | fraction of total, observed vs. expected counts |

Transform, normalize, remove baseline, prune rows and transpose are covered on [Transforms](transforms.md).

If you choose a combination that can't work, ASTERISM tells you why instead of running it. For example:

- a t test needs exactly two data sets, and a Column table;
- one-way ANOVA needs at least three data sets (use a t test for two);
- two-way ANOVA and the nested analyses need at least two;
- a Nested table only takes the nested analyses;
- most analyses need the raw values. A table where you typed means with SD or SEM and N (values calculated elsewhere) can only be used for the unpaired t test and a few others, such as regression and the counts analyses.

## Results sheets

Each analysis makes a results sheet. In the project sidebar it sits under its data table, in the **Data** section. Its name follows the analysis and the table, for example "Welch's t test of Control vs drug". The name updates when you change the settings, until you rename the sheet yourself.

A results sheet has one or more tabs along the top. Most analyses have a **Results** tab. Many add more tabs, for example **ANOVA table**, **Comparisons** and **Descriptive statistics**. Bold rows are section headings. Rows like **Significance** use the usual stars: ns (not significant, P ≥ 0.05), one star (P < 0.05), two (P < 0.01), three (P < 0.001) or four (P < 0.0001). P values below 0.0001 are shown as <0.0001.

### Results stay live

Results are never typed in or frozen. Every time the data table changes, the analysis is calculated again: edit a value, add a row, or exclude a value with **Edit › Exclude or Include Values**. Excluded values are left out of the calculation. If the data no longer suit the analysis (for example, a data set is left with only one value), the results sheet says what is wrong instead of showing numbers. When you fix the data, the results come back.

### Changing the settings later

With a results sheet in front, choose **Analyze › Analysis Settings…** (also in the tool panel). The same settings dialog opens with your current choices. Click **OK** to recalculate. You can undo the change like any other edit.

The data sets an analysis uses are fixed when you create it. To analyse a different set of columns, start a new analysis.

### Results you can graph or analyse further

Some analyses produce a table of numbers rather than a list of statistics: the frequency distribution, the QQ plot from the normality tests, the transforms, and fraction of total. For these:

- a graph of the result is made for you when you create the analysis (except for **Transpose**);
- with the results sheet in front, **Sheet › New Graph** makes another graph of the result table;
- the result table appears in the Analyze dialog's **Table:** list as "Results: …", so you can analyse it again (for example, a t test on normalized values). This works to any depth, and everything stays linked back to the original data.

Results sheets can also be placed on a figure; see [Figures and export](figures.md).

## Significance on graphs

Analyses that compare groups pass their P values to the graphs of the same data table, which draw them as brackets with stars. This applies to the t test, one-way and two-way ANOVA, the nested analyses and multiple t tests. Nothing needs to be copied by hand: when the data change, the brackets update too.

- Each analysis that can draw brackets has the option **Show the comparison on the linked graph** (t test) or **Show significant comparisons on the linked graph** (ANOVAs, nested) under **Options** in its settings. Clear it to keep that analysis off the graph.
- A test of two groups shows its result even when it is not significant ("ns"). To hide "ns", clear **Show “ns” for a two-group test that isn't significant** in **Format Graph › Significance**.
- For multiple comparisons, the graph shows only the significant ones by default. In **Format Graph › Significance**, **Multiple comparisons:** can show all of them, only those against a control, or none. **Significant when P <** sets the cut-off. You can also change the label (stars, exact P or both), the star thresholds, and the bracket shape.
- Right-click a bracket to choose **Hide this comparison**. **Show all comparisons** brings hidden ones back.
- **Graph › Show Significance** turns all brackets on the current graph on or off.

See [Formatting graphs](formatting.md) for the full set of significance options. Comparisons of row or column means in a two-way ANOVA (main effects) are reported on the results sheet but not drawn as brackets.

## Defaults for new analyses

**Settings…** (⌘,) has a **New analyses** section. On a Mac it is in the ASTERISM application menu; on Windows it is under **File**. It sets where a new analysis's settings start:

- **Unpaired t test:** Student's (the default, as in Prism) or Welch's;
- **One-way ANOVA comparisons:** Automatic (Tukey for all pairs, Dunnett against a control), or always Tukey, Šídák, Bonferroni or Holm-Šídák;
- **Confidence intervals:** 90%, 95% or 99%;
- **Significance level (α):** used by the normality tests and multiple t tests.

These apply only to analyses you create from then on. Saved analyses keep their own settings, and you can always change a single analysis in its own settings dialog. See [Settings, autosave and files](settings.md).

## Descriptive statistics

**Analyze › Descriptive Statistics** (or **Descriptive statistics** under **Column data** in the Analyze dialog) gives one column per data set. It lists N, minimum, 25th percentile, median, 75th percentile, maximum, range, mean, SD, SEM, the 95% confidence interval of the mean, the coefficient of variation and the sum. Percentiles use the same method as Prism. It has no settings. The t test and one-way ANOVA can also add these numbers as an extra tab: tick **Also report descriptive statistics for each data set** in their settings.

## Which test should I use? {#which-test}

Start from what you are comparing and how the data were collected.

### Two groups

- Different subjects in each group (unpaired): a [t test](analyses-groups.md#t-tests). Choose Welch's t test if the groups may have different SDs.
- The same subjects measured twice, or matched pairs: a paired [t test](analyses-groups.md#t-tests).
- Data clearly not normal, or ranks/scores: the Mann-Whitney test (unpaired) or Wilcoxon signed-rank test (paired), both under the [t test](analyses-groups.md#t-tests).
- Values that are naturally skewed and always positive (concentrations, for example): the t test on logarithms, or the ratio paired t test.

### Three or more groups

- Independent groups: [one-way ANOVA](analyses-groups.md#one-way-anova), followed by multiple comparisons.
- The same subjects measured under every condition: repeated-measures one-way ANOVA (same section).
- Not normal: Kruskal-Wallis (independent) or Friedman (matched), also in [one-way ANOVA](analyses-groups.md#one-way-anova).

### Two factors

For example, genotype × treatment, or treatment × time: [two-way ANOVA](analyses-groups.md#two-way-anova) on a Grouped table. Repeated measures (the same animal at every time point) are set on its Design page. If you only want "is there a difference at each row?", use [multiple t tests](analyses-groups.md#multiple-t-tests).

### Several measurements from each subject

For example, many cells from each animal, where the animal is the unit you want to compare: use the [nested t test or nested one-way ANOVA](analyses-groups.md#nested) on a Nested table. Treating every cell as independent would overstate your sample size.

### Against a fixed value

For example, "is the mean different from 100%?": the [one-sample t test or Wilcoxon signed-rank test](analyses-groups.md#one-sample).

### Checking your data first

- [Normality tests](analyses-groups.md#normality) and QQ plots, to help decide between a normal-based test and a rank test.
- [Outlier detection](analyses-groups.md#outliers) with ROUT or Grubbs' test.
- [Frequency distribution](analyses-groups.md#frequency-distribution) for a histogram.

### Other kinds of data

- Relationships between X and Y: [linear regression](analyses-xy.md#linear-regression), [correlation](analyses-xy.md#correlation), [curve fitting](analyses-xy.md#nonlinear-regression) (dose-response, kinetics and more), and [area under the curve](analyses-xy.md#area-under-the-curve).
- Counts of outcomes in groups: [chi-square and Fisher's exact test](analyses-counts.md#contingency).
- Time to an event: [survival analysis](analyses-counts.md#survival).
- Parts of a whole: [fraction of total](analyses-counts.md#fraction-of-total).
- Reshaping values before analysis (logs, percentages of control, baseline subtraction): [Transforms](transforms.md).

For the formulas behind each result, see [How results are calculated](methods.md).
