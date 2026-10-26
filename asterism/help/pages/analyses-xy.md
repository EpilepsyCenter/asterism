# Regression and curves

These analyses work on an XY table: each row has an X value (time, dose, concentration) and one or more Y data sets. Find them under **Analyze** (**Nonlinear Regression…**, **Linear Regression…**, **Correlation…**, **Area Under the Curve…**), or choose **Analyze › Analyze…** (⌘⇧A; Ctrl+Shift+A on Windows) and open the **XY data** section, where you can also pick which data sets to include.

The menu items analyse every data set in the table. Each result is live: edit the data and the numbers, the fitted curve and the graph update. To change the settings later, open the result and choose **Analyze › Analysis Settings…**. For how results sheets work in general, see [Analyses](analyses.md).

## Linear regression {#linear-regression}

Fits a straight line, Y = slope·X + intercept, to each data set by least squares. Use it when you expect Y to change in proportion to X, or for a straight standard curve.

### Settings

**Fit**

- **Replicates**: **Each replicate is a separate point** (the default) uses every value; **Fit the mean of the replicates** fits one point per row. Use the mean when the replicates in a row aren't independent of each other (for example repeated readings of the same well).
- **Constraint**: **Force the line through a point**, with its **X:** and **Y:**. Use it only when theory says the line must pass there (for example through 0,0 when no analyte gives no signal). With a forced point there is no standard error or interval for the Y-intercept, and the line comparison below is skipped.

**Compare**

- **Test whether the slopes and intercepts differ between data sets** (two or more data sets). The slopes are compared first. If they don't differ, ASTERISM fits a pooled slope and then tests whether the intercepts (the heights of the lines) differ. If the slopes do differ, the lines cross, so the intercepts aren't compared.

**Output**

- **Interpolate unknowns (rows with Y but no X, or X but no Y)**: reads unknowns off the line. See [Standard curves](#standard-curves).
- **Runs test: do the points systematically deviate from the line?** Counts runs of points above and below the line. Too few runs (a small P value) suggests the data curve away from a straight line.
- **Replicates test: does the line fit worse than replicates scatter?** Needs replicates. A small P value means the points stray from the line more than the scatter among replicates explains, so a curve may suit the data better.
- **Residual plot (a result table of residuals, graphed)**: makes a table of each point's distance from the line and a graph of it. A good fit gives a random scatter around zero.
- **Confidence intervals:** 90%, 95% or 99%.

**Graph**

- **Draw the line on the graph of the data** (on by default).
- **Bands:** **No bands**, **Confidence bands** (where the true line probably lies) or **Prediction bands** (where a new single point would probably fall; always wider).

### Reading the results

| Row | What it tells you |
|---|---|
| Slope, Y-intercept, X-intercept, 1/slope | The best-fit line |
| Standard errors, confidence intervals | How precisely the slope and intercept are known |
| R² | The fraction of the variation in Y the line explains (0 to 1) |
| Sy.x | The typical vertical distance of a point from the line, in Y units |
| Is the slope different from zero? | F test; a small P value means Y really changes with X |
| Equation | The line written out, ready to copy |
| Number of X values, Points analysed | What went into the fit |

With the comparison on, a **Compare lines** page gives the F test and P value for the slopes and, when they don't differ, for the intercepts, with a plain conclusion.

## Standard curves and unknowns {#standard-curves}

Both linear and nonlinear regression can read unknown samples off the fitted line or curve.

1. Enter the standards in the XY table: known amounts in X, measured signals in Y.
2. Below them, add one row per unknown: type its Y value in the same data set and leave X empty.
3. Run the regression with **Interpolate unknowns** ticked (on the **Output** page of the settings).

The **Interpolated** page lists each unknown with the direction (**Y → X** for a row with Y but no X; **X → Y** for a row with X but no Y), the value it started from and the interpolated value. If a row has replicates, their mean is used. Rows without an X play no part in the fit, so the unknowns don't affect the curve.

- Linear regression also gives a confidence interval. For X from Y it is where the confidence band of the line crosses that Y, so it can be lopsided, and it is infinite when the slope isn't clearly different from zero.
- Nonlinear regression looks for X only within the range of the standards' X values. A Y beyond the curve's plateau, or outside that range, shows **Outside the curve's range**.
- The interpolated X is in the same units as the table's X. If X holds logarithms (as in a log(dose) curve or a qPCR curve against log quantity), the result is a logarithm too: 10 to that power gives the amount.

A row counts as an unknown X only when no data set has a Y value in it, so rows holding another data set's values are left alone.

> **Tip:** importing a QuantStudio run with standards sets up the standard-curve table and its linear regression for you. See [Importing data](importing.md).

## Correlation {#correlation}

Measures how closely two variables rise or fall together, without assuming that one causes the other or fitting a line. Use correlation when both variables were measured (neither was set by you); use regression when X was controlled or you want to predict Y from X.

On an XY table, X is correlated with each data set, using the mean of each row's replicates. On a Column table, every pair of data sets is correlated, row by row.

### Settings

- **Pearson (assumes a Gaussian distribution)**: the usual coefficient, for values that are roughly normally distributed and related in a straight line.
- **Spearman (nonparametric, rank-based)**: works on ranks, so it suits skewed data, outliers, or a relationship that rises steadily but not in a straight line.
- **Confidence interval:** 90%, 95% or 99%.

### Reading the results

- **Pearson r** or **Spearman r**: from −1 (perfect negative) through 0 (no relationship) to +1 (perfect positive).
- The confidence interval of r. For Spearman it is reported only with more than 10 pairs.
- **R²** (Pearson) or **r²** (Spearman): the square of the coefficient.
- **P value (two-sided)**: how likely a correlation this strong would be if there were none. For Spearman with up to 16 pairs the P value is exact; the row **Exact or approximate?** says which you got.
- **Number of XY pairs**. At least three pairs are needed.

## Area under the curve {#area-under-the-curve}

Measures the area between each data set and a baseline, by the trapezoid rule (straight lines between neighbouring points), and finds the separate peaks. Typical uses: drug exposure over time, a glucose tolerance test, a calcium transient, an evoked response. When a row has replicates, the curve goes through each row's mean.

### Settings

- **Baseline (Y =):** the level areas are measured from (0 unless you change it).
- **Ignore peaks smaller than:** a percentage of the distance from the smallest to the largest Y (10% by default). Smaller bumps are treated as noise.
- **…or defined by fewer points than:** drops peaks made of fewer data points.
- **Also count peaks that go below the baseline**: by default only peaks above the baseline are listed.
- **Confidence interval:** 90%, 95% or 99%.

### Reading the results

- **Area**: the total area. Stretches below the baseline count as negative area.
- **Standard error** and confidence interval of the total area. These need replicates (or a table of means with SD or SEM) on every row, since they come from the scatter at each X.
- **Number of peaks** and **Total peak area**.
- The **Peaks** page lists each peak: **First X**, **Last X**, **Peak X**, **Peak Y**, **Area** and **% of peak area**. Where the curve crosses the baseline between two points, the crossing is found by straight-line interpolation.

## Nonlinear regression {#nonlinear-regression}

Fits a curve of a chosen shape (an equation) to each data set, finding the parameter values that bring the curve closest to the points. Use it for dose-response curves, enzyme kinetics, binding, decay and growth, peaks, or an equation of your own.

### Model

Choose a family on the left, then a model. The equation and a short description appear below the lists.

| Family | Models |
|---|---|
| Dose-response: stimulation | log(agonist) vs. response (three parameters); log(agonist) vs. response, variable slope (four parameters); log(agonist) vs. normalized response; log(agonist) vs. normalized response, variable slope; [Agonist] vs. response (three parameters); [Agonist] vs. response, variable slope (four parameters) |
| Dose-response: inhibition | log(inhibitor) vs. response (three parameters); log(inhibitor) vs. response, variable slope (four parameters); log(inhibitor) vs. normalized response; log(inhibitor) vs. normalized response, variable slope; [Inhibitor] vs. response (three parameters); [Inhibitor] vs. response, variable slope (four parameters) |
| Enzyme kinetics | Michaelis-Menten; Allosteric sigmoidal; Substrate inhibition |
| Binding | One site: specific binding; Specific binding with Hill slope; One site: total binding (specific + nonspecific); Two sites: specific binding; Competitive binding: one site (fit log IC50) |
| Exponential | One-phase decay; Two-phase decay; One-phase association; Exponential growth |
| Growth curves | Logistic growth; Gompertz growth |
| Gaussian and peaks | Gaussian; Lorentzian |
| Lines and polynomials | Straight line; Polynomial, second order; Polynomial, third order; Polynomial, fourth order |
| Sine waves | Standard sine wave |
| User-defined | User-defined equation |

Notes on choosing:

- **log(…)** models expect X to be the logarithm of the concentration; **[Agonist]** and **[Inhibitor]** models expect the concentration itself. If your X holds concentrations and you want a log model, make a log₁₀ copy of X first with [Transform](transforms.md#transform).
- The three-parameter dose-response models fix the Hill slope at 1 (or −1); the variable-slope models fit it. With few points, the three-parameter model is often more stable.
- The **normalized response** models assume the response runs from 0 to 100 (see [Normalize](transforms.md#normalize)).
- For the concentration models, Km, Kd, Khalf, EC50 and IC50 are kept positive automatically.

**Your own equation.** Choose **User-defined › User-defined equation** and type it in the box, for example `Y = Bottom + (Top-Bottom)/(1+exp(-K*(X-X50)))`. Use `X` for the X value; every other name becomes a parameter to fit. You can use + − × ÷ written as `+ - * /`, `^` for powers, brackets, and the functions `exp`, `ln` (natural log), `log` and `log10` (base 10), `sqrt`, `abs`, `sin`, `cos` and `tan`, plus the constants `pi` and `e`. If the equation can't be read, the dialog says why. Parameters start at 1 unless you give **Initial values**.

### Method

- **Replicates**: **Each replicate is a separate point** or **Fit the mean of the replicates**, as for linear regression.
- **Weighting** (**Minimize:**): **No weighting** (ordinary least squares), **1/Y² (relative)** when the scatter grows in proportion to Y, **1/Y (Poisson)** for counts, **1/X²** or **1/X**, or **1/SD²** to weight each row by its own scatter (this fits the row means and needs replicates or an SD on each row). Weights by Y use the curve's Y, not the data's, so a point's own scatter doesn't set its weight.
- **Outliers (ROUT)**: **No outlier detection**, **Identify outliers** (count them but keep them), or **Identify outliers and leave them out of the fit**. **Q (false discovery rate):** how strict the test is; 1% is the usual choice, lower finds fewer outliers. See also [Outliers](analyses-groups.md#outliers).

### Compare

- **No comparison**.
- **Compare this model with another model**: choose the **Other model:**. Both are fitted to each data set, and the result says which fits better given its number of parameters.
- **Is one curve adequate for all data sets?** (two or more data sets): compares separate curves with one shared curve.
- **Does one parameter differ between data sets?** (two or more data sets): choose the **Parameter:**, for example LogEC50 to ask whether a drug shifted the dose-response curve.
- **Test:** **Extra sum-of-squares F test** (needs nested models, where the simpler one is a special case of the other, such as three- vs four-parameter dose-response) or **AICc (information criterion)** (works for any pair, and gives the probability that each model is correct).

### Constrain

One row per parameter, with **How**:

- **Fit**: the usual; the value is found from the data.
- **Constant equal to**: holds the parameter at **Value**, for example Bottom = 0 when you know there is no response without drug.
- **Shared by all data sets**: fits one value for every data set at once (a global fit), for example one shared Hill slope. Needs two or more data sets.
- **Fit within bounds**: fits the parameter but keeps it between **Value** (lower bound) and **Upper bound**; leave either empty for no limit on that side.

### Initial values

Fitting starts from a guess for each parameter and improves it step by step. Leave the boxes blank and ASTERISM guesses from the range and shape of the data. Type a value only when a fit fails or lands on a silly answer.

### Range

- **Fit only X from:** … **to:** fits only the points within that X range.
- **Draw the curve from X =** … **to:** sets how far the curve is drawn on the graph. Left empty, it spans the data.

### Output

- **Interpolate unknowns**: see [Standard curves](#standard-curves).
- **Table of residuals**: a **Residuals** page with X, Y, the fitted Y and their difference for every point.
- **Residual plot (a result table of residuals, graphed)**.
- **Runs test**: too few runs of points above and below the curve (a small P value) suggests the model doesn't follow the shape of the data.

### Confidence

- **Asymmetric (profile likelihood): recommended** or **Symmetric (asymptotic)** intervals for the parameters. Profile-likelihood intervals can be lopsided, which describes parameters such as EC50 or rate constants better.
- **Also report standard errors** (always shown with symmetric intervals).
- **Confidence level:** 90%, 95% or 99%.
- **Bands on the graph:** **No bands**, **Confidence bands** or **Prediction bands**.
- **Draw the curve on the graph of the data** (on by default).

### The curve on the graph

When **Draw the curve on the graph of the data** (or, for linear regression, **Draw the line on the graph of the data**) is on, each data set's fitted curve appears on the graphs of that XY table, in the data set's colour and line style, so you can format it with the data set (see [Formatting graphs](formatting.md)). Confidence or prediction bands are drawn as thinner dashed lines either side. On a log X axis the curve is drawn evenly along the log scale. The curve follows any change to the data or the settings. To draw an equation with parameters you choose yourself instead of fitted ones, use [Plot a function](formatting.md#plot-a-function).

### Reading the results

- **Best-fit values**: each parameter for each data set. Markers: **(constant)** for a parameter you held fixed, **(shared)** for a global parameter, and **— unstable** when its confidence interval couldn't be pinned down (the data don't define it, for example a top plateau that was never reached).
- Values worked out from the parameters, depending on the model: **EC50** or **IC50** (10 to the power of LogEC50 or LogIC50), **Span**, **Half-life** and **Tau** (one-phase decay), **Half-time** (association), **Half-life (fast)** and **Half-life (slow)**, **Doubling time**.
- **Standard errors**, when asked for or with symmetric intervals.
- **Confidence intervals** of each parameter (and of EC50 or IC50). **Could not be determined** or an infinite end (**very wide**) means the data can't pin that parameter down: consider holding it constant, sharing it, or collecting data over a wider X range.
- **Goodness of fit**: **Degrees of freedom**, **R²**, **Sum of squares** and **Sy.x** (the typical distance of points from the curve). A high R² alone doesn't prove the model is right; look at the graph and the residuals too.
- **Points analysed**, the number of outliers (with ROUT), the runs test, and a note if the fit didn't converge.
- A **Compare models** or **Compare data sets** page with the comparison, its P value or AICc probabilities, and the preferred answer.

For the fitting method, profile-likelihood intervals and ROUT, see [How results are calculated](methods.md).
