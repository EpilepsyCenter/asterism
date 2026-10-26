# How results are calculated

This page says how ASTERISM computes each result, for writing the methods section of a paper or checking a number by hand. How to choose and run each analysis is covered in [Analyses](analyses.md) and the pages after it.

Some general rules apply everywhere:

- **Results are always recalculated.** They are never stored in the project file; ASTERISM recomputes them from the data whenever the data or the settings change, and when you open the file.
- **Numbers on result pages** are shown to 4 significant digits. P values are shown to 4 decimal places, and as "<0.0001" when smaller than 0.0001.
- **SD** always uses n − 1 in the denominator. **SEM** = SD / √n.
- **Confidence intervals** use the level chosen in each analysis's settings (95% unless you change it; see [Settings](settings.md#settings)), except where this page says otherwise.
- **Two-sided P values** are the default. Where an analysis offers a one-sided P, it is half the two-sided P: ASTERISM assumes the difference goes in the direction you predicted.
- **Excluded values** are left out of every calculation.

## Checked against Prism {#checked-against-prism}

ASTERISM's test suite compares its results with numbers that GraphPad Prism 11 calculated on real lab data sets. ASTERISM's results match Prism's on these tests:

- **Mann-Whitney test:** the exact P value (also with tied values) and U, on qPCR data.
- **Welch's t test:** t, degrees of freedom and P.
- **Normality tests:** all four tests (statistic, P value, and the minimum sample size), on six data sets.
- **Frequency distributions:** bin width, bin centres, automatic first and last bins, and the counts, on six data sets.
- **Two-way repeated-measures ANOVA** with unequal group sizes: sums of squares, F, P, and the Bonferroni and Tukey multiple comparisons (difference, SE, degrees of freedom, adjusted P, interval width).
- **Mixed-effects model:** fitted to complete repeated-measures data, it reproduces Prism's repeated-measures ANOVA and its comparisons.
- **Multiple t tests** (Welch) and **multiple Mann-Whitney tests:** each row's statistic and P, and the Holm-Šídák adjusted P values.
- **Linear regression:** slope, intercepts, standard errors, confidence intervals, F, P, R², Sy.x and the sum of squares.
- **Spearman correlation:** r, the exact P (with ties), the approximate P and the confidence interval.
- **Fisher's exact test** on a 2 × 2 table.

Other results are checked against established statistics software: scipy, statsmodels and pingouin (Python), R (including the survival, nlme, lmerTest and DescTools packages, and nls profile intervals), SAS's published Gehan-Breslow-Wilcoxon example, and brute-force enumeration for the exact tests.

## Descriptive statistics {#descriptive-statistics}

| Result | How it is calculated |
|---|---|
| Mean, SD, SEM | SD with n − 1; SEM = SD / √n. |
| 95% CI of the mean | Mean ± t × SEM, with t for n − 1 degrees of freedom. Always 95% on this page. |
| Median | The middle value (the mean of the two middle values when n is even). |
| 25th and 75th percentiles | The (n + 1)·p rule, interpolating between neighbouring values; the same rule Prism uses. |
| Coefficient of variation | SD / mean, as a percentage. |
| Range, minimum, maximum, sum | As named. |

Graphs use the same rules for error bars (SD, SEM, 95% CI by t, median with interquartile range) and for box-and-whisker plots.

## t tests {#t-tests}

| Test | How it is calculated |
|---|---|
| Student's unpaired t test (default) | Pooled variance from both groups; df = n₁ + n₂ − 2. |
| Welch's unpaired t test | Each group's own variance; Welch-Satterthwaite degrees of freedom (usually not a whole number). |
| t test on logarithms | Student's t test on log₁₀ of the values; the difference is reported as the ratio of geometric means, with its interval. |
| Paired t test | One-sample t test of the differences (B − A); df = number of pairs − 1. |
| Ratio paired t test | Paired t test on log₁₀(B / A); reported as the geometric mean of the ratios. |
| From mean, SD and N | Student's or Welch's t test from the entered summary values (SEM or %CV are converted to SD). |

- The difference is always B − A (second data set minus first). Its interval is difference ± t × SE.
- **η² (R²)** = t² / (t² + df).
- Every unpaired t test also reports the **F test for equal variances**: larger variance / smaller variance, two-sided P.
- The paired t test reports the **correlation between pairs** (Pearson r) with a one-sided P for r > 0, to show whether pairing helped.

### Mann-Whitney test {#mann-whitney}

- **P value:** exact when the two groups together have 100 values or fewer, *including when there are ties*. The exact P comes from the permutation distribution of the ranks (tied values get the average of their ranks). With more than 100 values, the normal approximation is used. The result page says which method was used.
- **U** is reported as the smaller of the two possible U values (the convention Prism uses).
- Also reported: the rank sums, the medians, their difference, and the Hodges-Lehmann estimate of the difference (the median of all pairwise differences B − A).

### Kolmogorov-Smirnov test

The two-sample test with an exact, always two-sided P value; D is the largest distance between the two cumulative distributions.

### Wilcoxon signed-rank test {#wilcoxon}

- **P value:** exact when there are no tied differences, no zero differences, and at most 50 pairs; otherwise the normal approximation, with zero differences left out.
- **W** is the sum of the signed ranks (positive ranks plus negative ranks), as Prism reports it; the sums of positive and negative ranks are listed too.

## One-sample tests {#one-sample}

- **One-sample t test:** t = (mean − hypothetical value) / SEM, df = n − 1. The discrepancy (mean − hypothetical value) is reported with its confidence interval, and η² = t² / (t² + df).
- **Wilcoxon signed-rank test** against a hypothetical median: the same rules as the paired [Wilcoxon test](#wilcoxon), applied to each value minus the hypothetical median.

Each data set is tested on its own.

## One-way ANOVA {#one-way-anova}

| Design | How it is calculated |
|---|---|
| Ordinary one-way ANOVA | Between- and within-group sums of squares; F = MS between / MS within. R² = SS between / SS total. |
| Equal SDs? (with ordinary ANOVA) | Brown-Forsythe test (Levene's test centred on medians) and Bartlett's test. |
| Welch and Brown-Forsythe ANOVA | Welch's F with its approximate denominator df; Brown-Forsythe F* with Satterthwaite df. For groups whose SDs may differ. |
| Repeated-measures one-way ANOVA | Treatment, subject (row) and residual sums of squares from the complete rows; F = MS treatment / MS residual. |
| Geisser-Greenhouse correction | On by default for repeated measures. ε is estimated from the double-centred covariance matrix (between 1/(k − 1) and 1); both degrees of freedom are multiplied by ε. |
| Was the matching effective? | F = MS subjects / MS residual. |
| Repeated measures with missing values | A [mixed-effects model](#mixed-effects) instead (automatically, or always if chosen in the settings). |

### Multiple comparisons after one-way ANOVA {#multiple-comparisons}

Every method reports a multiplicity-adjusted P value for each comparison. *m* is the number of comparisons in the family (all pairs, or each group against the control).

| Method | How it is calculated |
|---|---|
| Tukey (all pairs) | Tukey-Kramer: q = absolute difference / √(MS × (1/nᵢ + 1/nⱼ) / 2), P from the studentized range distribution for k groups. Simultaneous confidence intervals. |
| Dunnett (against a control) | Exact multivariate t distribution, calculated by numerical integration (the same answer every time, unlike random-sampling methods). Simultaneous confidence intervals. |
| Šídák | Adjusted P = 1 − (1 − P)ᵐ; intervals at the matching per-comparison level. |
| Bonferroni | Adjusted P = P × m (at most 1); intervals at α / m. |
| Holm-Šídák | Step-down: the smallest P is adjusted with m, the next with m − 1, and so on, never smaller than the one before. No confidence intervals (the method doesn't define them). |
| Fisher's LSD | No correction. |
| Games-Howell (Welch ANOVA) | Like Tukey, but each pair uses its own SE and Welch degrees of freedom. |
| Dunnett's T3 (Welch ANOVA, default) | Welch t for each pair, with the studentized maximum modulus distribution for the number of comparisons and that pair's Welch degrees of freedom rounded down. Matches Prism. |
| Tamhane's T2 (Welch ANOVA) | Bonferroni correction of Welch t tests. |

The ordinary methods use the ANOVA's pooled mean square (MS within) and its degrees of freedom. After repeated-measures ANOVA that assumes sphericity they use the residual mean square; when sphericity isn't assumed (Geisser-Greenhouse on, the default), each comparison uses only the differences between its two columns: standard error SD(differences)/√n with n − 1 degrees of freedom, as Prism does. When nothing is chosen, ASTERISM uses Tukey for all pairs and Dunnett against a control (Dunnett's T3 after Welch ANOVA).

### Kruskal-Wallis and Friedman tests {#kruskal-wallis-and-friedman}

- **Kruskal-Wallis:** H with the correction for ties. For small and moderate samples the P value is exact, also with ties: the share of all ways of dealing the observed values into groups of these sizes that give an H at least as large (shown as "Exact"). For larger samples, the χ² approximation (k − 1 df). With ties, Prism's exact P can differ slightly, as there is no single standard method.
- **Friedman:** values ranked within each row (complete rows only), with the correction for ties; P from the χ² approximation.
- **Dunn's test** after either: the difference in mean ranks (Kruskal-Wallis, with the tie correction in the SE) or in rank sums (Friedman, SE = √(n·k·(k + 1)/6)), a z test, and Bonferroni adjustment (P × m). **Uncorrected Dunn's test** skips the adjustment.

## Two-way ANOVA {#two-way-anova}

Rows are one factor and data sets the other; the replicates in each cell are the values.

- **Ordinary two-way ANOVA:** Type III sums of squares, from a regression with effect coding. With equal numbers of values in every cell this equals the classical calculation. Every cell needs at least one value, and the table needs replicates.
- **Repeated measures (matched rows or matched data sets):** an *unweighted-means* analysis. With unequal numbers of subjects per group, each group mean counts equally and the sums of squares use the harmonic mean of the group sizes. This reproduces Prism's results exactly. Only subjects with a value in every cell are used.
- **Geisser-Greenhouse correction:** off by default in two-way ANOVA. When on, ε comes from the pooled within-group covariance and is applied to the repeated factor and the interaction.
- **Matched in every cell:** each effect is tested against its own error term (that factor × subjects); the interaction against the factor × factor × subjects term.
- **Missing values in a matched design:** a [mixed-effects model](#mixed-effects) instead (automatically, or always if chosen).
- **% of total variation** = that effect's sum of squares / total sum of squares.

### Multiple comparisons after two-way ANOVA

Methods: **Tukey**, **Bonferroni**, **Šídák**, **Holm-Šídák** and **Fisher's LSD**, calculated as for [one-way ANOVA](#multiple-comparisons). The default is Tukey for ordinary designs and Šídák for repeated measures.

- Comparisons within each row form one family, and comparisons within each column another; each family is corrected on its own (m and, for Tukey, the number of means count only that family).
- **Ordinary designs:** SE from the residual mean square and the two cells' sizes.
- **Repeated measures:** comparisons within the same subjects use the residual mean square; comparisons between different subjects use the pooled subjects-plus-residual mean square, with the pooled degrees of freedom (as Prism does).
- **Main-effect comparisons** (row means or column means) use unweighted marginal means.

## Mixed-effects model {#mixed-effects}

Used for repeated measures with missing values (one-way and two-way), or whenever you choose it.

- Treatment factors are fixed effects and subjects are random (compound symmetry). The subject variance may come out negative, as it can in repeated-measures ANOVA. The model is fitted by REML.
- Fixed effects are tested with Type III Wald F tests. Denominator degrees of freedom use the containment method; with complete data they equal repeated-measures ANOVA's, and the P values and comparisons are the same.
- In a two-way design matched in every cell, the model has three random terms: subject, subject × row factor and subject × column factor.
- **Was the matching effective?** A likelihood-ratio test comparing the model with and without the random terms.
- Multiple comparisons use the model's estimates and their standard errors, with the methods above.

## Multiple t tests {#multiple-t-tests}

One test per row, comparing two data sets.

- **Tests:** unpaired t test (each row's own pooled SD, not pooled across rows), Welch's t test (the default), Mann-Whitney test, paired t test and Wilcoxon signed-rank test, each calculated as described [above](#t-tests).
- **Corrections:** Holm-Šídák (the default), Bonferroni, Šídák, or none, applied across all rows.
- **False discovery rate:** the two-stage step-up method of Benjamini, Krieger and Yekutieli, Benjamini-Hochberg, or Benjamini-Yekutieli. Results are q values (for the two-stage method, the smallest Q at which that row would be a discovery), and a row is a discovery when q ≤ Q (Q = 1% unless you change it).

## Nested t test and nested one-way ANOVA {#nested}

- **Model:** value = group effect + random subject effect + residual, fitted by REML (statsmodels' mixed linear model).
- **Group effect:** a t test (two groups) or Wald F test (more), with degrees of freedom = number of subjects − number of groups. When every subject has the same number of replicates, this equals a t test or ANOVA on the subject means.
- **Variation between subjects:** the subject and residual variances, the subject share of the total, and a likelihood-ratio test of whether subjects differ (P halved, because a variance can't be below zero).
- **Comparisons** after nested one-way ANOVA use the methods above with the same degrees of freedom (Tukey by default).


## Normality tests {#normality}

| Test | Statistic | P value | Minimum n |
|---|---|---|---|
| D'Agostino-Pearson omnibus | K² (skewness and kurtosis combined) | χ² with 2 df | 8 |
| Anderson-Darling | A² | From the small-sample corrected A²* = A² × (1 + 0.75/n + 2.25/n²) | 8 |
| Shapiro-Wilk | W | Royston's method | 3 |
| Kolmogorov-Smirnov | Distance D from a normal distribution with the sample's mean and SD | Dallal-Wilkinson approximation of the Lilliefors P; shown as "> 0.10" above that | 5 |

Lognormality tests run the same tests on log₁₀ of the values (all values must be positive). The QQ plot uses Blom's plotting positions, (i − 3/8) / (n + 1/4).

## Outliers {#outliers}

- **Grubbs' test** (two-sided): G = largest |value − mean| / SD, compared with the critical value for n values at the chosen α. The repeated version removes one outlier at a time and tests again until none is found.
- **ROUT:** a robust fit (a horizontal line at the centre of the data, or the curve in nonlinear regression) using a Lorentzian (Cauchy) merit function. The robust SD of the residuals is the 68.27th percentile of their absolute values × N / (N − K), re-estimated until stable. Each residual / robust SD gets a two-sided t-based P value (N − K df), and a false-discovery-rate rule at Q (1% by default) decides which values are outliers.

## Frequency distribution {#frequency-distribution}

- Each bin holds values from its lower edge up to, but not including, the next bin's lower edge.
- **Automatic bin width:** the range of the data / 20, rounded to 1, 2 or 5 times a power of 10.
- **Automatic first and last bins:** the bins holding the smallest and largest values.
- Values outside the first and last bin are left out and counted on the results page.
- Relative frequencies divide by the number of values; cumulative distributions add up the bins.

## Linear regression {#linear-regression}

- **Fit:** ordinary least squares. By default each replicate is its own point; you can fit the row means instead.
- **Standard errors and intervals** of the slope and Y-intercept use the usual least-squares formulas, with t for n − 2 degrees of freedom (n − 1 when the line is forced through a point).
- **X-intercept interval:** where the confidence band crosses Y = 0 (Fieller's method). It is infinite when the slope's interval includes zero.
- **Is the slope different from zero?** F = (slope / SE)², with 1 and n − 2 df.
- **Confidence band:** fitted Y ± t × Sy.x × √(1/n + (X − mean X)² / Sxx). The **prediction band** adds Sy.x² inside the square root.
- **Comparing lines** (analysis of covariance): first an F test of whether the slopes are equal; if they are not significantly different, an F test of whether the intercepts (elevations) are equal, using the pooled slope.
- **Runs test:** exact probability of as few runs of residual signs (or fewer).
- **Replicates test:** lack of fit of the line compared with the scatter among replicates.

## Nonlinear regression {#nonlinear-regression}

- **Fit:** least squares by the Levenberg-Marquardt method; a trust-region method when parameters have bounds. With a shared parameter, all data sets are fitted together (a global fit).
- **Weighting:** none, 1/Y², 1/Y, 1/X², 1/X or 1/SD². The Y weights use the fitted curve's Y, as Prism does.
- **Standard errors** of the parameters: the square roots of the diagonal of s² (JᵀJ)⁻¹, where J is the Jacobian at the best fit (by finite differences) and s² = sum of squares / df.
- **Confidence intervals:** by default **profile likelihood**: the parameter value, with the other parameters refitted, where the sum of squares reaches SS × (1 + F(1, df) / df). These can be asymmetric. The alternative is **asymptotic** (symmetric): value ± t × SE. EC50 and IC50 intervals are 10 to the power of the logEC50 or logIC50 limits.
- **Confidence and prediction bands:** from the parameter covariance matrix (delta method), with t for the fit's df; the prediction band adds Sy.x².
- **R²** = 1 − SS residual / SS total (both weighted when the fit is weighted). **Sy.x** = √(SS / df).
- **Comparing models or data sets:** the extra sum-of-squares F test, or AICc. AICc = N·ln(SS/N) + 2K + 2K(K + 1)/(N − K − 1), with K = number of fitted parameters + 1; the probability that a model is correct comes from the difference in AICc.
- **Outliers:** ROUT, as described [above](#outliers).

## Correlation {#correlation}

- **Pearson r:** P from t = r √((n − 2) / (1 − r²)) with n − 2 df. Confidence interval from Fisher's z transform with SE = 1 / √(n − 3).
- **Spearman r:** the Pearson correlation of the ranks (ties get average ranks). The P value is exact for up to 16 pairs, ties included, from the permutation distribution of the ranks; above that, the t approximation. The confidence interval uses Fisher's z with SE = √(1.06 / (n − 3)) and is reported only when n > 10, as in Prism.
- On XY tables, each data set is correlated with X using the mean of each row's replicates.

## Area under the curve {#area-under-the-curve}

- **Area:** the trapezoid rule on the row means, measured from the baseline (0 unless you set one).
- **Standard error of the area:** from each point's SEM, weighted by its share of the trapezoids; degrees of freedom = number of values − number of X values. The confidence interval is area ± t × SE.
- **Peaks:** the curve is split where it crosses the baseline. Regions below the baseline are left out unless you ask for them. A peak is kept when its height is at least the chosen fraction of the Y range (10% by default) and it has at least the chosen number of points.

## Contingency tables {#contingency}

| Test | How it is calculated |
|---|---|
| Fisher's exact test (default for 2 × 2) | Exact two-sided P: the sum of the probabilities of all tables with the same totals that are no more likely than the one observed. |
| Fisher's exact test, larger tables | The Freeman-Halton extension. If there are too many tables to count (over 5 million), the chi-square P is reported instead and the page says so. |
| Chi-square test (default for larger tables) | Pearson's chi-square, (r − 1)(c − 1) df. Yates' continuity correction is optional, for 2 × 2 tables only. The page warns when expected counts are below 5. |
| Chi-square test for trend | Cochran-Armitage with equally spaced scores, for 2 columns and 3 or more ordered rows (or the reverse). |
| McNemar's test | For matched pairs: continuity-corrected chi-square from the discordant pairs, plus the exact binomial P. |

Effect sizes for 2 × 2 tables, with the interval method used for each:

| Measure | Interval (default first) |
|---|---|
| Proportions, sensitivity, specificity, predictive values | Wilson/Brown hybrid; or Clopper-Pearson exact |
| Relative risk | Koopman asymptotic score; or Katz |
| Difference between proportions | Newcombe/Wilson with continuity correction; or without |
| Odds ratio | Baptista-Pike; or Woolf |
| Phi (2 × 2) or Cramér's V | Inverting the noncentral chi-square distribution |

The number needed to treat is 1 / |difference between proportions|, with its interval from the difference's interval.

## Survival {#survival}

- **Survival curves:** Kaplan-Meier (product-limit) estimates, with Greenwood standard errors.
- **Confidence intervals** of the fraction surviving: by default the asymmetric log-log transform; or symmetric (± z × SE), clipped to 0–100%.
- **Median survival:** the first time the curve reaches 50% or below (the midpoint, if the curve sits at exactly 50% for a while). Its interval: the first times the lower and upper confidence limits reach 50%.
- **Log-rank (Mantel-Cox) test:** k − 1 df, using the full covariance matrix.
- **Gehan-Breslow-Wilcoxon test:** the same, with each time point weighted by the number at risk, which gives early deaths more weight.
- **Log-rank test for trend** (3 or more groups): equally spaced scores, 1 df.
- **Hazard ratio** (two groups): by the Mantel-Haenszel method, exp((O − E) / V) with SE = 1/√V, and by the log-rank method, (O₁/E₁) / (O₂/E₂) with SE = √(1/E₁ + 1/E₂).
- **Ratio of median survival times:** its interval assumes exponential survival (SE of the log ratio = √(1/O₁ + 1/O₂)).

## Fraction of total {#fraction-of-total}

Each value is divided by its column total, row total or the grand total. When the values are counts, each fraction's interval uses the Wilson/Brown hybrid method.

## Significance stars {#significance-stars}

On result pages, the **Significance** column always uses these levels:

| P value | Shown as |
|---|---|
| P < 0.0001 | **** |
| P < 0.001 | *** |
| P < 0.01 | ** |
| P < 0.05 | * |
| P ≥ 0.05 | ns |

The Yes/No answers on result pages (**Significant at α = …**, the "Significant?" columns and similar rows) compare P with the analysis's significance level, α. New analyses take it from **Settings… › New analyses** (0.05 unless you change it); analyses made earlier keep 0.05. Multiple t tests with FDR control use Q instead.

On graphs, significance brackets use the same four levels by default. In **Format Graph** (or for new graphs, in [Settings](settings.md#settings)) you can choose three levels (0.05, 0.01, 0.001) or Prism's own cut-offs (0.0332, 0.0021, 0.0002 and 0.0001 for one to four stars). In every case, a P value must be *below* a cut-off to earn its star. Brackets after multiple comparisons show the adjusted P values.
