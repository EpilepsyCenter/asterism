# Golden values still wanted from Prism

ASTERISM's normality tests and frequency distributions are checked against Prism's own
numbers (harvested from the lab's projects by `harvest.py`). One-way ANOVA and its
multiple comparisons are cross-checked against scipy / statsmodels / pingouin, but not
yet against Prism. To close that gap:

1. In Prism 11, open the sample data **Column → "One-way ANOVA - Ordinary"** (File > New,
   or the sample files in `Prism 11.app/Contents/SharedSupport/SampleData/Column/`).
2. Run, on all columns, each as a separate analysis:
   - Ordinary one-way ANOVA, compare all pairs, **Tukey**
   - Ordinary one-way ANOVA, compare with control (first column), **Dunnett**
   - Ordinary one-way ANOVA, all pairs, **Holm-Šídák**
   - Welch and Brown-Forsythe ANOVA, all pairs, **Dunnett T3** and **Games-Howell**
   - **Kruskal-Wallis** with **Dunn's** test
3. Open **Column → "One-way ANOVA - Repeated measures"** and run:
   - RM one-way ANOVA with Geisser-Greenhouse correction, all pairs, **Tukey**
   - **Friedman** with **Dunn's** test
4. Save both projects as `.prism` into `sample_data/` and run
   `.venv/bin/python tests/golden/harvest.py sample_data/*.prism`.
   (The harvester will need a small extension for these analysis classes.)

## Mixed-effects model with a missing value (one Prism run settles the open details)

ASTERISM's mixed model (REML, compound symmetry) is checked against R and reproduces
Prism's RM ANOVA exactly when nothing is missing. Two details are not documented by
Prism and are ASTERISM's choice until a Prism run confirms them:
- the **denominator degrees of freedom** with missing values (ASTERISM: containment, as
  SAS does by default; integer df; the alternatives are Satterthwaite or Kenward-Roger,
  which give fractional df), and the df of the post tests;
- how **Geisser-Greenhouse** is applied to the mixed model (ASTERISM: ε from the subjects
  with every value).

To close it:
1. In `Seizure_data.prism`, duplicate the "Per week seizures" two-way RM ANOVA, delete
   (or exclude) two or three values in the data table copy, and set the Repeated
   measures tab to "Fit a mixed effects model only when values are missing".
2. Run once without and once with the Geisser-Greenhouse correction, with Šídák
   comparisons within each row.
3. Save, and send the `.prism` (the harvester will be extended for the mixed-model results).

## Nonlinear regression, ROUT and the Spearman cut-off (M5)

ASTERISM's curve fits match R's nls to R's own precision (estimates, standard errors,
profile-likelihood intervals), and linear regression and Spearman correlation match Prism
exactly on the lab's data. Prism's own numbers are still wanted for:
1. Nonlinear regression: open the Prism sample files **XY → "Dose-response - X is
   log(dose)"**, **"Enzyme kinetics - Michaelis-Menten"** and **"Nonlinear regression --
   One phase exponential decay"**; run the fit Prism suggests in each (default settings:
   profile-likelihood intervals), and once more with "Compare: does LogEC50 differ between
   data sets" in the dose-response file.
2. ROUT: in the Column sample "Identify outliers", run Identify outliers → ROUT, Q = 1%.
3. Spearman: one XY table with 15 or 16 pairs (no ties), correlation → Spearman, to see
   whether Prism still reports an exact P (ASTERISM: exact up to 16 pairs).
4. Save the projects as `.prism` into `sample_data/` and send them; the harvester will be
   extended for NONLINEAR_REGRESSION and IDENTIFY_OUTLIERS.

## Survival and 2 × 2 effect sizes (M6)

Fisher's exact test already matches Prism on the lab's data; the methods below match R
(and SAS for Gehan-Breslow-Wilcoxon) but not yet Prism itself:
1. Open the Prism sample **Survival → "Comparing two survival curves"** (or any two-group
   survival table) and run Survival analysis with default settings. Also run a three-group
   one for the log-rank test for trend.
2. In the lab's contingency table "All seizures increase/decrease", tick Relative risk,
   Difference between proportions and Odds ratio (default interval methods) and re-run.
3. Save as `.prism` into `sample_data/` and send; the harvester will be extended for
   SURVIVAL_ANALYSIS and the contingency effect sizes (especially the Baptista-Pike odds
   ratio interval, which has no reference implementation outside Prism).

## QQ plot (M9)

Prism's guide says the QQ plot puts the actual values on X and the values predicted from a
Gaussian on Y, but not which plotting positions it uses. ASTERISM uses Blom's
(i − 3/8)/(n + 1/4), scaled by the data's mean and SD.
1. In any column table (e.g. "Dose response"), run Normality and lognormality tests with
   "Create a QQ plot" ticked.
2. Save as `.prism` into `sample_data/` and send; the predicted values in Prism's QQ results
   table will show the formula (Blom, (i − 0.5)/n, or another).
