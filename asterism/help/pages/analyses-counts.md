# Counts, survival and proportions

This page covers analyses of counted subjects (contingency tables), of time to an event (survival), and of parts of a whole. Find them under **Analyze** (**Chi-square or Fisher's Test…**, **Survival Analysis…**, **Fraction of Total…**), or choose **Analyze › Analyze…** (⌘⇧A; Ctrl+Shift+A on Windows) and open the **Counts**, **Survival** or **Parts of whole** section. Each needs the matching kind of table; see [Choosing a table format](tables.md#table-format).

Results are live: change the data and they update. To change the settings later, open the result and choose **Analyze › Analysis Settings…**.

## Contingency tables {#contingency}

Asks whether an outcome is associated with a group: are treated animals less likely to have seizures than controls? Enter the data in a Contingency table as whole-number counts of subjects, not percentages or means.

- Rows are the groups, with the exposed or treated group first.
- Columns are the outcomes, with the outcome of interest first.
- For a diagnostic test, rows are the test result (positive first) and columns the true condition (present first).

For example, 3 of 20 treated mice and 11 of 20 controls had a seizure:

| | Seizure | No seizure |
|---|---|---|
| Treated | 3 | 17 |
| Control | 11 | 9 |

The analysis also runs on a Grouped table of counts when you choose it from **Analyze › Analyze…**.

### Test

- **Fisher's exact test**: exact, and the better choice when counts are small. It is the default for 2 × 2 tables. For larger tables ASTERISM uses the exact extension to any number of rows and columns; if there are too many possible tables to work through, it reports the chi-square test instead and says so.
- **Chi-square test**: an approximation that is fine for large counts. It is the default for larger tables. If any expected count is below 5, the results add a note recommending Fisher's test.
- **McNemar's test (the same subjects measured twice; 2 × 2)**: for matched pairs, such as each patient before and after treatment. Rows are the first measurement and columns the second. It uses only the pairs that changed.
- **Yates' continuity correction (chi-square, 2 × 2 only)**: makes the chi-square test more cautious. Most statisticians now prefer Fisher's test instead.
- **Chi-square test for trend (ordered rows or columns, 2 × 3 or larger)**: asks whether the proportion with the outcome rises or falls steadily across ordered groups, such as increasing doses. It is reported for tables with two columns and three or more rows (or the reverse).
- **P value:** **Two-sided** or **One-sided**. The one-sided choice applies to Fisher's test on a 2 × 2 table; use it only if you decided the direction of the effect before seeing the data.

### Effect size

For 2 × 2 tables, choose what to report:

- **Relative risk and difference between proportions (prospective and experimental studies)**: the proportion with the outcome in each group, their ratio, their difference, and the number needed to treat (or harm).
- **Odds ratio (case-control studies)**: use when you chose subjects by their outcome, so the proportions themselves mean little.
- **Sensitivity, specificity and predictive values (diagnostic tests)**: also gives the likelihood ratios of a positive and a negative test.
- **Strength of association (phi, or Cramér's V for larger tables)**: from 0 (no association) to 1. Cramér's V is always reported for tables larger than 2 × 2.

### Intervals

The method for each confidence interval. The recommended methods are selected already; the older ones are there to match published results.

| Setting | Choices |
|---|---|
| **Relative risk:** | Koopman asymptotic score (recommended); Katz (older) |
| **Difference between proportions:** | Newcombe/Wilson, continuity-corrected (recommended); Newcombe/Wilson, uncorrected |
| **Odds ratio:** | Baptista-Pike (recommended); Woolf (older) |
| **Proportions, sensitivity …:** | Wilson/Brown (recommended); Clopper-Pearson exact (older) |
| **Confidence level:** | 90%, 95% or 99% |

### Reading the results

- **Results**: the table size and number of subjects, the test with its P value and whether it is significant at α = 0.05, the test for trend, and the strength of association with its interval.
- **Effect size** (2 × 2 tables): each measure with its confidence interval. A relative risk or odds ratio whose interval includes 1, or a difference whose interval includes 0, is not statistically significant. When the difference isn't significant, the interval of the number needed to treat includes infinity, and the results say so.
- **Expected counts**: the counts you would expect if group and outcome were unrelated.

## Survival analysis {#survival}

Kaplan-Meier survival curves, median survival, and tests that compare the curves. Use it for time to any event: death, a first seizure, tumour onset, relapse.

### Entering survival data

Make a Survival table. Each row is one subject:

- In X, the time: when the event happened, or when you last saw the subject event-free.
- In the subject's group column, **1** if the event happened at that time, or **0** if the subject was *censored*: still event-free at the end of the study, lost to follow-up, or removed for another reason.
- Leave the subject's row empty in the other groups' columns.

| X (days) | Control | Treated |
|---|---|---|
| 12 | 1 | |
| 30 | 0 | |
| 18 | | 1 |
| 45 | | 0 |

Censored subjects still count: they show that the subject survived at least that long. Don't leave them out, and don't enter them as events.

### Settings

**Data**

- **Event (death) code:** and **Censored code:** set the codes, if your data use something other than 1 and 0. Rows with any other value are ignored. The survival graph uses the same codes.

**Output**

- **Confidence intervals of the fraction surviving**: **Asymmetric (log-log transform): recommended**, which stays between 0% and 100% naturally, or **Symmetric (±z·SE, clipped to 0–100%)**, the older method.
- **Confidence level:** 90%, 95% or 99%.
- **Report survival as:** **Percentages** or **Fractions**.

### Comparing curves

With two or more groups, ASTERISM compares the curves with two tests:

- **Log-rank (Mantel-Cox)**: gives every time point equal weight. It is the usual choice, and the most powerful when one group's risk is a constant multiple of the other's.
- **Gehan-Breslow-Wilcoxon**: gives more weight to early events, when more subjects are at risk. Use it when early differences matter most, or when the curves cross.

With three or more groups, the **Log-rank test for trend** asks whether survival changes steadily across the groups in the order of their columns. It makes sense only for ordered groups, such as increasing doses.

With exactly two groups you also get:

- The **hazard ratio** (first group over second), by the Mantel-Haenszel and log-rank methods, each with its confidence interval and its reciprocal (second over first). A hazard ratio of 0.5 means the first group has the event at half the rate of the second.
- The **Ratio of median survival times** (when both medians are defined), with a confidence interval that assumes exponential survival.

### Reading the results

- **Comparison of survival curves**: chi-square, degrees of freedom and P value for each test.
- **Median survival**: the time at which half the subjects have had the event, with its confidence interval. If more than half are still event-free at the end, it is **Undefined (survival stays above 50%)**.
- **Data**: subjects, events and censored subjects in each group.
- **Survival proportions**: for each group and each time, the survival, its standard error and confidence interval, and the number at risk, events and censored.

The Survival table's own graph draws the Kaplan-Meier curves as steps, with ticks for censored subjects. You can switch to cumulative events, or add confidence bands as dashed lines, a shaded band or error bars, in **Graph › Format Graph…** or **Graph › Graph Type…** (see [Graph types](graphs.md#graph-types)).

## Fraction of total {#fraction-of-total}

Divides each value by a total, as a fraction or a percentage: what share of all cells were neurons, or what percentage of each animal's sleep was REM. It works on Parts of whole, Column, Grouped and Contingency tables. All values must be zero or positive.

### Settings

- **Divide each value by**: **Its column total**, **Its row total** or **The grand total**.
- **Show as:** **Percentages** or **Fractions**.
- **Confidence interval of each fraction (when the values are counts)**: adds an interval to each fraction (Wilson/Brown method). It is computed only when every value is a whole number, because an interval for a fraction only makes sense for counts.
- **Confidence level:** 90%, 95% or 99%.

### Results

The **Fractions** page shows each value's fraction. When you divide by column totals, a **Total** row confirms each column adds up to 100% (or 1). The fractions also go into a result table, with a graph made for you. That table is live and can be graphed and analysed further like any data table (see [Transforms](transforms.md)).

### Parts of whole tables

A Parts of whole table holds values that add up to a whole, one part per row (for example the number of cells of each type). ASTERISM works out the fractions for its graphs, which can be pie or donut charts, bars stacked to 100% or percentage dot plots (see [Graph types](graphs.md#graph-types)). Use **Fraction of Total…** when you want the fractions as numbers, or their confidence intervals. To test whether counts across categories match what you expected, see [Observed vs. expected](transforms.md#observed-vs-expected).
