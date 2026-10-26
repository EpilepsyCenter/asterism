# Comparing groups

This page covers the analyses that compare groups of values, plus the checks you may want to run on your data first. Each section explains when to use the analysis, the choices in its settings dialog, and how to read the results sheet. For how to start an analysis and how results stay linked to your data, see [Analyses](analyses.md). For the formulas, see [How results are calculated](methods.md).

A few things are the same on every results sheet:

- **Significance** uses stars: ns (not significant, P ≥ 0.05), one star (P < 0.05), two (P < 0.01), three (P < 0.001) or four (P < 0.0001).
- **Significant at α = 0.05** is a plain Yes or No at the usual 0.05 cut-off.
- P values below 0.0001 are shown as <0.0001.
- Data sets are named by their column letter and title, for example "A: Control".

## t tests {#t-tests}

Use a t test (or one of its rank-based versions) to compare **two** data sets in a Column table. Open the Analyze dialog, choose **t test and nonparametric equivalents** under **Column data**, and tick exactly two data sets.

### Design: paired or unpaired?

**Are the two data sets matched row by row?**

- **No: independent groups (unpaired)**: different subjects in each group, for example control mice and treated mice.
- **Yes: each row is a matched pair (paired)**: the same subject measured twice (before and after), or pairs matched by design (littermates, the same culture split in two). The values in one row belong together.

The picture in the dialog shows the difference: two separate clouds of points for unpaired data, and points joined by lines for paired data. Pairing removes the variation between subjects, so a paired test is often much more sensitive. Use it only when the pairing is real.

### Test

First choose **What can be assumed about the data?**:

- **Normal distribution**: compares means. The usual choice for measurements that scatter roughly symmetrically.
- **Lognormal distribution**: compares geometric means. For values that are always positive and skewed to the right, such as concentrations or fold changes. The test runs on the logarithms.
- **No distribution assumed**: rank-based tests. For data that are clearly not normal, or that are scores or ranks.

Then pick the test. The choices depend on the design:

| | Unpaired | Paired |
|---|---|---|
| Normal | **Student's t test (assumes equal SDs)** or **Welch's t test (does not assume equal SDs)** | **Paired t test (on the differences)** |
| Lognormal | **t test on the logarithms (compares geometric means)** | **Ratio paired t test (on the log of the ratios)** |
| No distribution | **Mann-Whitney U test (compares ranks)** or **Kolmogorov-Smirnov test (compares whole distributions)** | **Wilcoxon signed-rank test (on the differences)** |

**Student or Welch?** Student's t test assumes the two groups have the same SD. Welch's correction drops that assumption, at a small cost in power when the SDs really are equal. If one group is clearly more variable than the other, or the group sizes differ a lot, choose Welch. Student's test is the default, as in Prism. You can make Welch the default for new t tests in [Settings](settings.md).

**Mann-Whitney or Kolmogorov-Smirnov?** Mann-Whitney asks whether values in one group tend to be larger than in the other. Kolmogorov-Smirnov asks whether the two distributions differ in any way (location, spread or shape). It is less sensitive to a simple shift.

### Options

- **P value:** **Two-sided** or **One-sided**. The one-sided P is half the two-sided P. ASTERISM doesn't ask which direction you expected, so a one-sided P is only valid if you predicted the direction before seeing the data and the difference went that way. When in doubt, use two-sided.
- **Confidence intervals:** 90%, 95% or 99%.
- **Differences as:** differences are always the second data set minus the first.
- **Show the comparison on the linked graph**: draws the result as a bracket on graphs of this table (see [Significance on graphs](analyses.md#significance-on-graphs)).
- **Also report descriptive statistics for each data set**: adds a **Descriptive statistics** tab.

The **Residuals** page lists residual plots and checks that aren't available yet; its options are greyed out.

### Reading the results

The **Results** tab names the table and the two data sets, then gives:

- **P value**, **Significance**, **Significant at α = 0.05** and **Tails**. Mann-Whitney and Wilcoxon also show **P value method**: **Exact** or **Normal approximation**. Mann-Whitney uses the exact P when the two groups together have up to 100 values, also when values are tied, as Prism does. Wilcoxon uses the exact P for up to 50 pairs with no tied or zero differences. The Kolmogorov-Smirnov P is exact and always two-sided (the **One-sided** choice doesn't apply to it).
- The test statistic: **t** with its **Degrees of freedom** (fractional for Welch), **U** for Mann-Whitney (the smaller of the two U values, as Prism reports it), **D** for Kolmogorov-Smirnov, or **W (sum of signed ranks)** for Wilcoxon.
- **Size of the difference**, the part to report alongside P:
  - Unpaired t tests: each mean, the **Difference of means (B − A)**, its standard error and confidence interval, and **η² (R²)**, the share of the total variation explained by the group.
  - Paired t test: the **Mean difference (B − A)**, the SD and standard error of the differences, the confidence interval and **Partial η²**.
  - Lognormal tests: geometric means and their ratio (B/A) with a confidence interval. A ratio of 1 means no difference.
  - Mann-Whitney: each median, the difference of medians, and the **Hodges-Lehmann estimate of the difference** (the median of all differences between a value in B and a value in A).
  - Wilcoxon: the sums of positive and negative ranks and the **Median difference (B − A)**.
- **Equal variances (F test)** (unpaired t tests): tests whether the two SDs differ. If they clearly do, consider Welch's test.
- **Pairing** (paired t tests): the correlation between the pairs and whether the pairing was effective. If it wasn't, the pairs don't vary together and the paired test gains nothing.
- **Sample sizes** or **Pairs**: the number of values used. A paired test uses only the rows where both values are present.

### From means and SDs

If your table holds means, SD (or SEM or %CV) and N calculated elsewhere, you can still run an unpaired Student's or Welch's t test. The values are read from the first row. Paired and rank tests need the raw values. The results sheet notes "(from summary data)".

### Agreement with Prism

The tests in ASTERISM's test suite check its results against Prism's own output on real lab data. Welch's t, df and P match Prism. Mann-Whitney's U and exact P match Prism, also with tied values.

## One-way ANOVA {#one-way-anova}

Use one-way ANOVA to compare **three or more** data sets, for example a control and several doses. Choose **Analyze › One-way ANOVA…** to use every data set in the table, or pick data sets in the Analyze dialog (**One-way ANOVA and nonparametric equivalents**). For two data sets, use a [t test](#t-tests).

The settings have four pages.

### Design

**Are the values matched across data sets?**

- **No: independent groups**: different subjects in each data set.
- **Yes: each row is one subject measured under every condition**: repeated measures. Each row is one animal, cell culture or person, with one value in every column.

**Missing values:** (for repeated measures with a normal distribution) decides what happens when a row has a gap:

- **Mixed-effects model only when values are missing** (default): repeated-measures ANOVA when every row is complete; a mixed-effects model when values are missing.
- **Always repeated-measures ANOVA**: refuses to run if a value is missing.
- **Always the mixed-effects model.**

The mixed-effects model (REML, compound symmetry) gives the same results as repeated-measures ANOVA when nothing is missing. It can also use the incomplete rows, as long as the values are missing for reasons unrelated to what they would have been.

### Test

**Distribution:** **Assume normal distributions (ANOVA)** or **No distribution assumed (rank-based test)**.

**Variability:**

- **Groups may have different SDs: use Welch and Brown-Forsythe ANOVA** (independent groups only). Use this when the groups' SDs clearly differ.
- **Correct for unequal variability of differences (Geisser-Greenhouse)** (repeated measures only, on by default). Repeated-measures ANOVA assumes the differences between every pair of conditions are equally variable. This correction protects you when they aren't, and it is rarely a reason to turn it off.

A note under the options names the test that will run:

| Matched? | Normal | No distribution assumed |
|---|---|---|
| No | Ordinary one-way ANOVA, or Welch's and Brown-Forsythe ANOVA | Kruskal-Wallis test |
| Yes | Repeated-measures one-way ANOVA | Friedman test |

### Comparisons

ANOVA tells you whether the groups differ somewhere. Multiple comparisons tell you which ones differ, while keeping the chance of a false positive under control.

**Which comparisons?**

- **Compare every pair of data sets**
- **Compare each data set with a control**: choose the **Control:** data set. Fewer comparisons give more power.
- **No multiple comparisons**

**Test:** the methods offered depend on the test and the comparisons:

| Test | Methods |
|---|---|
| Ordinary or repeated-measures ANOVA | Tukey's (every pair only), Dunnett's (against a control only), Šídák's, Holm-Šídák's, Bonferroni's, Fisher's LSD (no correction) |
| Welch's ANOVA | Games-Howell's, Dunnett's T3, Tamhane's T2, Fisher's LSD (no correction) |
| Kruskal-Wallis or Friedman | Dunn's multiple comparisons test, Uncorrected Dunn's test |

The defaults are Tukey for every pair and Dunnett against a control (ordinary and repeated measures), Dunnett's T3 after Welch's ANOVA, and Dunn's after the rank tests. You can change the starting choice in [Settings](settings.md). Fisher's LSD and uncorrected Dunn's don't correct for multiple comparisons. Use them only for a few comparisons planned in advance.

### Options

- **Confidence intervals:** 90%, 95% or 99%.
- **Show significant comparisons on the linked graph**: draws brackets for the comparisons on graphs of this table.
- **Also report descriptive statistics for each data set.**

### Reading the results

The **Results** tab gives the overall test first:

- Ordinary ANOVA: **F**, **Degrees of freedom (between, within)**, the P value and **R²** (the share of the variation explained by the groups). Under **Equal SDs?**, the Brown-Forsythe and Bartlett's tests check whether the groups' SDs differ. If they do, consider Welch's ANOVA.
- Welch's ANOVA: **Welch's ANOVA F** with its degrees of freedom and P. Under **Brown-Forsythe ANOVA**, a second test that also allows unequal SDs: `F*`, degrees of freedom and P.
- Repeated measures: F, **Degrees of freedom (treatment, residual)**, P, **Geisser-Greenhouse ε** (1 means no correction was needed), **Correction applied** and R². Under **Matching**, the test shows whether the subjects really differ from each other, that is, whether matching was worth it. **Subjects (complete rows)** counts the rows used.
- Kruskal-Wallis: the statistic **H**, the P value (**Approximate (χ²)**) and each data set's **Mean ranks**.
- Friedman: the statistic, the P value (approximate) and the number of complete rows. Rows with a missing value are left out.

The **ANOVA table** tab (ordinary and repeated measures) has the sums of squares, degrees of freedom, mean squares, F and P.

The **Comparisons** tab has one row per comparison:

- **Mean difference**: the first data set minus the second. Against a control, it is the control minus the other data set. Rank tests show the **Mean rank difference** (Kruskal-Wallis) or **Rank sum difference** (Friedman) instead.
- The confidence interval of the difference (not given for rank tests or Holm-Šídák).
- **Significant?**, **Significance** and **Adjusted P**. The P value is already adjusted for the number of comparisons, as in Prism, so you compare it directly with 0.05. Fisher's LSD and uncorrected Dunn's are the exceptions: their P values are not adjusted.

When the mixed-effects model was used, the results show the method and why (**Values are missing** or **Chosen in the settings**). They also show the F test of the fixed effect, the random-effect SDs and variances, a likelihood-ratio test of whether the matching was effective, and how many values were missing. A **Fixed effects** tab replaces the ANOVA table.

### Agreement with other software

ASTERISM's tests check ordinary ANOVA, Tukey, Welch's ANOVA, Games-Howell, repeated-measures ANOVA with the Geisser-Greenhouse correction, Kruskal-Wallis and Friedman against established statistics packages. Dunnett's test uses the exact distribution.

## Two-way ANOVA {#two-way-anova}

Use two-way ANOVA when each value is classified by **two factors**, for example genotype and treatment, or treatment and time. Enter the data in a Grouped table: one factor in the rows, the other as data sets (columns), and the replicates in the sub-columns. An XY table with replicates also works, with X as the row factor. Choose **Analyze › Two-way ANOVA…**, or **Two-way ANOVA** under **Grouped data** in the Analyze dialog.

Two-way ANOVA needs the raw replicate values, at least two data sets and at least two rows with values.

### Design

**Which values come from the same subject?**

- **None: every value is from a different subject**: ordinary two-way ANOVA.
- **Each sub-column is one subject, measured in every row**: for example, rows are time points, and each animal is one sub-column of its group's data set.
- **Each sub-column position is one subject, measured in every data set**: for example, each animal was tested under every data set's condition, and the rows are separate groups of animals. Replicate 1 in every data set is the same animal.
- **Each sub-column position is one subject, measured in every cell**: both factors are repeated. The same subject appears in every row and every data set.

**Missing values:** has the same three choices as for one-way ANOVA. By default, ASTERISM uses repeated-measures ANOVA when the data are complete and a mixed-effects model when values are missing.

**Factor names:** **Rows are:** and **Data sets are:** name the two factors (for example "Time" and "Genotype"). The names label the results.

### Test

**Correct for unequal variability of differences (Geisser-Greenhouse)** applies when one factor is matched and the other is not (the second and third designs above). It is off by default here.

### Comparisons

**Which comparisons?**

- **Within each row and within each column** (default)
- **Within each row (compare columns)**: for example, genotypes compared at each time point.
- **Within each column (compare rows)**: for example, time points compared within each genotype.
- **Column means (main effect)**, or **Row means (main effect)**: compares the factor's means averaged over the other factor.
- **Every cell with every other cell**
- **No multiple comparisons**

**Test:** **Tukey**, **Bonferroni**, **Šídák**, **Holm-Šídák** or **Fisher's LSD (no correction)**. New analyses start with Tukey for ordinary designs and Šídák for repeated measures. Each row or column is corrected as its own family of comparisons.

### Options

- **Confidence intervals:** 90%, 95% or 99%.
- **Show significant comparisons on the linked graph**: comparisons between cells are drawn as brackets. Main-effect comparisons are not drawn.

### Reading the results

The **Results** tab names the design. It then gives three tests: the row factor, the column factor, and their interaction (**row factor × column factor**). For each, it shows **% of total variation**, **F** with its two degrees of freedom, the P value and significance. Repeated-measures designs with one matched factor also show **Geisser-Greenhouse ε** and whether the correction was applied.

Read the interaction first. A significant interaction means the effect of one factor depends on the other: for example, the drug works in one genotype but not the other. Then the main effects alone can mislead, and comparisons within rows or columns are more informative.

The **ANOVA table** tab gives the sums of squares, degrees of freedom, mean squares, F and P for each factor, plus **Subjects (matching)** for repeated measures and the **Residual**.

The **Comparisons** tab groups the comparisons under headings such as "Within 30 min" or "Within WT". Each row gives the **Mean difference** (first cell minus second), its confidence interval, **Significant?**, **Significance** and **Adjusted P**.

When the mixed-effects model was used, the results show the fixed-effect F tests, the random-effect SDs and variances, a test of whether the matching was effective, and a data summary (subjects, values analysed, missing values). A **Fixed effects** tab replaces the ANOVA table.

### Agreement with Prism

For repeated measures with matched rows, ASTERISM reproduces Prism's sums of squares, F, P and the post-test results (Tukey and Bonferroni) exactly, including groups of unequal size. A mixed-effects model on complete data gives Prism's repeated-measures ANOVA. Ordinary designs use Type III sums of squares, which equal the classical ones when every cell has the same number of values. There is no rank-based version of two-way ANOVA.

## Multiple t tests {#multiple-t-tests}

Use multiple t tests when a Grouped table has **two data sets** and you want a separate comparison in **every row**. For example: wild type vs knockout for each of 20 genes, or at each of several time points analysed independently. Choose **Analyze › Multiple t Tests…**, or **Multiple t tests and Mann-Whitney tests** under **Grouped data** in the Analyze dialog. If the table has more than two data sets, choose the two to compare.

If the rows are levels of a factor you care about as a whole (time, dose), [two-way ANOVA](#two-way-anova) is usually the better analysis.

### Design

**Each row compares two data sets. Are the replicates matched?**

- **No: independent groups**: **Test in each row:** **Welch's t test (does not assume equal SDs)** (default), **Student's t test (assumes equal SDs)** or **Mann-Whitney test**.
- **Yes: replicate 1 of one data set pairs with replicate 1 of the other**: **Paired t test** or **Wilcoxon signed-rank test**.

Each row is tested on its own values only. Student's t uses that row's own pooled SD, not one SD for the whole table.

### Comparisons

With many rows, some will look significant by chance. Choose how to deal with that:

- **Control the false discovery rate**: limits the expected share of false positives among the rows called discoveries. A good choice when you are screening many rows. Choose the **FDR method:** **Two-stage step-up (Benjamini, Krieger, Yekutieli)**, **Benjamini-Hochberg** or **Benjamini-Yekutieli**, and the **Desired FDR (Q):** (default 0.01).
- **Correct for multiple comparisons (family-wise error rate)** (default): limits the chance of even one false positive. **Correction:** **Holm-Šídák** (default), **Šídák** or **Bonferroni**, with a **Significance level (α):** (default 0.05).
- **No correction: each row on its own**: plain P values compared with α.

### Reading the results

The **Results** tab has one row per table row:

- **Significant?** (or **Discovery?** with FDR control);
- **P value** (before correction) and **Adjusted P** (or **q value** with FDR control);
- **Mean, A** and **Mean, B** (medians for the rank tests) and the **Difference** (B − A);
- for t tests, the **SE of difference**, **t** and **df**; for Mann-Whitney, **U**.

A row that couldn't be tested (fewer than two values on one side, for example) is listed with the reason. The **Summary** tab gives the test, the correction, the threshold, the number of rows analysed and the number of significant rows or discoveries. The adjusted P values (or q values) are drawn as brackets on graphs of this table.

### Agreement with Prism

Per-row Welch's t and Mann-Whitney statistics and P values, and the Holm-Šídák adjusted P values, match Prism's own output. The FDR methods are checked against an established statistics package.

## Nested t test and nested one-way ANOVA {#nested}

Use these when each group contains several **subjects**, and each subject was measured several times: many cells from each animal, or several wells from each culture. The subject is the independent unit. Treating every cell as an independent value would make your sample look much larger than it is.

Enter the data in a Nested table: each data set is a group, each sub-column is one subject, and the values down a sub-column are that subject's replicate measurements. Choose **Analyze › Nested t Test or ANOVA…**, or one of the two analyses under **Nested data** in the Analyze dialog. With two groups you get a nested t test; with three or more, a nested one-way ANOVA.

### Settings

- **Design** explains the layout. Subjects are treated as a random factor.
- **Comparisons:** **Confidence intervals:** 90%, 95% or 99% (for the nested t test this sets the interval of the difference). For nested one-way ANOVA also **Compare every pair of groups** or **No multiple comparisons**, and the **Test:** **Tukey**, **Holm-Šídák**, **Šídák**, **Bonferroni** or **Fisher's LSD (no correction)**.
- **Options:** **Show significant comparisons on the linked graph**.

### Reading the results

The **Results** tab gives the number of groups, subjects and values, then:

- Nested t test: **t**, **Degrees of freedom** (number of subjects minus number of groups), the P value, each group's mean, the **Difference (B − A)**, its standard error and confidence interval (at the level set under **Comparisons**).
- Nested one-way ANOVA: **F** with its degrees of freedom and the P value. The **Comparisons** tab lists each pair of groups with the mean difference, confidence interval and **Adjusted P**.
- **Variation between subjects**: the **Variance between subjects**, the **Residual variance** (within subjects) and the **% of variance between subjects**. A likelihood-ratio test asks whether subjects differ more than chance would explain (**Subjects differ at α = 0.05**).

When every subject has the same number of replicates, the group test gives the same result as an ordinary t test or ANOVA on the subject means. ASTERISM's tests check this. With unequal numbers of replicates, the two can differ: the nested model uses every value and accounts for the variation both between and within subjects.

## Normality tests {#normality}

Normality tests ask whether each data set is consistent with a normal (Gaussian) distribution. They help you choose between a test that assumes normality and a rank-based test. Choose **Analyze › Normality Tests…**, or **Normality and lognormality tests** under **Column data**.

### Settings

- **Tests:** tick any of
  - **D'Agostino-Pearson omnibus test (needs 8 or more values)**
  - **Anderson-Darling test (needs 8 or more values)**
  - **Shapiro-Wilk test** (needs 3 or more)
  - **Kolmogorov-Smirnov test with the Lilliefors P value** (needs 5 or more)
- **Also test:** **Lognormal distribution (tests run on the logarithms)**. Needs every value to be positive.
- **Significance level (α):** 0.05, 0.01 or 0.10.
- **Graph:** **Create a QQ plot (actual values against those predicted from a Gaussian)**. Makes a result table and a graph. Points close to the line of identity suggest normal data.

### Reading the results

The **Normality** tab (and **Lognormality** tab, if chosen) has one column per data set. For each test it gives the statistic (**K²**, **A²**, **W** or **Distance (D)**), the **P value**, and **Consistent with a normal distribution (α = …)?**. The Kolmogorov-Smirnov P is shown as "> 0.10" when it is larger than 0.10, as in Prism. When a data set has too few values for a test, the cell says so (for example "Needs ≥ 8 values").

A small P value is evidence that the data are not normal. A large P value doesn't prove they are: with small samples these tests have little power. With very large samples, they flag deviations too small to matter. Look at the QQ plot too, and consider what you know about the kind of measurement.

### Agreement with Prism

All four tests reproduce Prism's statistics and P values, and they use the same minimum sample sizes.

## One-sample tests {#one-sample}

Use a one-sample test to compare each data set with a fixed, hypothetical value. For example: is the mean percentage of control different from 100? Is a ratio different from 1? Choose **One-sample t test and Wilcoxon signed-rank test** under **Column data** in the Analyze dialog. Each ticked data set is tested on its own.

### Settings

- **Test:** **One-sample t test (compares the mean)**, or **Wilcoxon signed-rank test (compares the median)** for data that are not normal.
- **Hypothetical value:** the value to compare with (default 0).
- **P value:** **Two-sided** or **One-sided** (half the two-sided P; see the note under [t tests](#t-tests)).
- **Confidence intervals:** 90%, 95% or 99% (t test).

### Reading the results

The **Results** tab has one column per data set.

- One-sample t test: **Hypothetical mean**, **Actual mean**, **Number of values**, **t**, **Degrees of freedom**, the P value and significance. Under **Size of the discrepancy** come the **Discrepancy (actual − hypothetical)**, its confidence interval and **η² (R²)**.
- Wilcoxon signed-rank test: **Hypothetical median**, **Actual median**, **Number of values**, **W (sum of signed ranks)**, the sums of positive and negative ranks, the P value and its method (**Exact** or **Normal approximation**).

## Outlier detection {#outliers}

Outlier detection flags values that lie unusually far from the rest of their data set. Choose **Analyze › Outlier Detection…**, or **Outlier detection** under **Column data**. Each data set is tested separately.

### Settings

**Method:**

- **ROUT (robust regression and outlier removal): can find several outliers.** **ROUT: Q (maximum false discovery rate):** 0.1%, 1% (default), 5% or 10%. A higher Q finds more outliers, but more of them will be false.
- **Grubbs' test: find at most one outlier.** **Grubbs: significance level (α):** 0.05 (default), 0.01, 0.001 or 0.0001.
- **Grubbs' test, repeated until no more outliers are found.** Uses the same α.

Grubbs' test assumes the rest of the data are normal and works best for one outlier. Repeating it can miss outliers that hide each other, which ROUT handles better.

### Reading the results

- The **Outliers** tab, per data set: the method and its Q or α, **Values analysed**, **Outliers found**, **Outlier values** and **Values kept**.
- The **Cleaned data** tab lists the values that remain in each data set.

Outlier detection doesn't change your data table. If you decide a value should be left out, select it in the table and choose **Edit › Exclude or Include Values**. All analyses and graphs then leave it out, and you can include it again later. Remove outliers only when you have a reason to think the value is a mistake, not just because it is inconvenient.

## Frequency distribution {#frequency-distribution}

A frequency distribution counts how many values fall into each bin, for a histogram or a cumulative distribution. Choose **Analyze › Frequency Distribution…**, or **Frequency distribution** under **Column data**.

### Settings

- **Distribution:** **Frequency distribution (each bin separately)** or **Cumulative distribution** (each bin also counts every value below it).
- **Tabulate:** **Number of values**, **Fraction of values** or **Percentage of values**.
- **Bins:** **Bin width:**, **First bin centre:** and **Last bin centre:**. Each has an **Automatic** box; clear it to type your own value.

With **Automatic**, the bins are about a twentieth of the data's range wide, rounded to a 1, 2 or 5 number. The first and last bins are the ones that hold the smallest and largest values. All data sets use the same bins, so their distributions can be compared.

### Reading the results

- The **Distribution** tab has one row per bin, labelled by its **Bin centre**, and one column per data set.
- The **Bins** tab gives the bin width, first bin centre, number of bins, what was tabulated, the number of values binned, and the **Values outside the bins** (values beyond the first or last bin you set, which are left out).

A value exactly on the edge between two bins goes into the higher bin. A graph of the distribution is made for you, and the result table stays linked to the data. You can graph it again or analyse it further; see [Results you can graph or analyse further](analyses.md#results-you-can-graph-or-analyse-further).

### Agreement with Prism

The bins and the counts, fractions and cumulative values match Prism's own output, including Prism's automatic bin width.
