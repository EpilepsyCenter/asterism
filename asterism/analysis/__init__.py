"""Analysis registry: turns an Analysis sheet into result pages (no Qt).

`engine` is what the document model calls (`Project(engine=...)`). Each analysis
type registers a runner and a title. A failing analysis never takes the app down:
it returns a result whose page explains the problem.
"""

from __future__ import annotations

from typing import Callable

from . import (anova, anova2, column, contingency, frequency, multiple_t, nested, nonlin, normality,
               onesample, parts, survival, xy)
from .results import AnalysisResult, ResultPage

_RUNNERS: dict[str, tuple[Callable, Callable[[dict], str]]] = {
    "ttest": (column._ttest, column.ttest_title),
    "descriptive": (column._descriptive, lambda _p: "Descriptive statistics"),
    "anova1": (anova.one_way, anova.title),
    "normality": (normality.normality, lambda p: "Normality and lognormality tests"
                  if p.get("lognormal") else "Normality tests"),
    "onesample": (onesample.one_sample, lambda p: "Wilcoxon signed-rank test"
                  if p.get("test") == "wilcoxon" else "One-sample t test"),
    "outliers": (onesample.outliers, lambda _p: "Outliers"),
    "anova2": (anova2.two_way, anova2.title),
    "multiple_t": (multiple_t.multiple_t, multiple_t.title),
    "nested": (nested.nested, nested.title),
    "linreg": (xy.linear_regression, lambda p: "Linear regression"),
    "correlation": (xy.correlation, lambda p: "Spearman correlation" if p.get("method") == "spearman"
                    else "Pearson correlation"),
    "auc": (xy.area_under_curve, lambda p: "Area under the curve"),
    "nonlin": (nonlin.nonlinear, nonlin.title),
    "contingency": (contingency.contingency, lambda p: "Fisher's exact test" if p.get("test") == "fisher"
                    else "Chi-square test" if p.get("test") == "chi2" else "Contingency analysis"),
    "fraction": (parts.fraction_of_total, lambda p: "Fraction of total"),
    "survival": (survival.survival, lambda p: "Survival analysis"),
    "frequency": (frequency.frequency, lambda p: "Cumulative frequency distribution"
                  if p.get("cumulative") else "Frequency distribution"),
}


def analysis_types() -> list[str]:
    return list(_RUNNERS)


class Engine:
    def run(self, analysis) -> AnalysisResult:
        entry = _RUNNERS.get(analysis.analysis_type)
        if entry is None:
            return _failed(f"Unknown analysis type “{analysis.analysis_type}”.")
        try:
            return entry[0](analysis)
        except Exception as e:   # never take the app down over one analysis
            return _failed(str(e))

    def title(self, analysis) -> str:
        entry = _RUNNERS.get(analysis.analysis_type)
        return entry[1]({**analysis.params, "_ncols": len(analysis.columns)}) if entry \
            else analysis.analysis_type


def _failed(msg: str) -> AnalysisResult:
    return AnalysisResult(error=msg, pages=[ResultPage(
        "Results", [""], [("The analysis could not be completed", [msg], "row")])])


engine = Engine()

__all__ = ["AnalysisResult", "Engine", "ResultPage", "analysis_types", "engine"]
