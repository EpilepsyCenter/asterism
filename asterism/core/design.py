"""Design detection → test selection (SPEC §8).

Pure functions: given a validated `Dataset`, infer the experimental design from the
*structure* of the factor columns and the shared/distinct pattern of subjects, and
recommend a test. Nothing is executed here (that is the stats core, step 3) and
nothing is silently applied — the result is a fully serialisable description meant
to be displayed and overridden (SPEC §8: "Always display the inferred design and the
chosen test; always allow override").

The §8 table, implemented:

    2 levels, one factor, subjects distinct   → Welch's t-test  (MW if non-normal)
    2 levels, one factor, subjects shared      → Paired t-test  (Wilcoxon)
    ≥3 levels, one factor, distinct            → One-way ANOVA → Tukey / Dunnett
    ≥3 levels, one factor, shared              → RM one-way ANOVA (Geisser–Greenhouse)
    two factors                                → Two-way ANOVA; RM on shared factor
    numeric x present                          → Linear regression; Pearson/Spearman
    two distributions, no grouping             → Two-sample Kolmogorov–Smirnov

Normality/sphericity are advisory flags decided later (SPEC §8), so every parametric
recommendation carries its non-parametric alternative for the flag to flip to.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .contract import SUBJECT, Dataset

# The Welch caveat is load-bearing for trust (SPEC §8): Prism defaults to
# Student's t; we default to Welch's, so the numbers will differ. Surface it.
WELCH_CAVEAT = (
    "Defaults to Welch's t-test (unequal variances), NOT Student's. Prism "
    "defaults to Student's, so results will differ — this is intentional and "
    "must appear in the output string."
)


@dataclass(frozen=True)
class Test:
    """A recommended test and everything needed to display/justify it."""

    name: str
    parametric: bool = True
    nonparametric_alternative: str | None = None  # if the normality flag trips
    posthoc: str | None = None
    correction: str | None = None
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "parametric": self.parametric,
            "nonparametric_alternative": self.nonparametric_alternative,
            "posthoc": self.posthoc,
            "correction": self.correction,
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class FactorFacts:
    """The detected structure of one factor column — the display material."""

    name: str
    n_levels: int
    levels: tuple
    subjects_shared: bool

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "n_levels": self.n_levels,
            "levels": [str(v) for v in self.levels],
            "subjects_shared": self.subjects_shared,
        }


@dataclass(frozen=True)
class DesignResult:
    """The inferred design + recommended test + why. Serialisable for the UI."""

    design: str                      # short machine label
    recommended_test: Test | None
    rationale: str
    factor_facts: tuple[FactorFacts, ...] = ()
    detectable: bool = True          # False when the frame is too degenerate

    def to_dict(self) -> dict:
        return {
            "design": self.design,
            "recommended_test": (
                self.recommended_test.to_dict() if self.recommended_test else None
            ),
            "rationale": self.rationale,
            "factor_facts": [f.to_dict() for f in self.factor_facts],
            "detectable": self.detectable,
        }


def _facts(ds: Dataset, factor: str) -> FactorFacts:
    levels = ds.levels(factor)
    return FactorFacts(
        name=factor,
        n_levels=len(levels),
        levels=tuple(levels),
        subjects_shared=ds.subjects_shared_across(factor),
    )


def detect_design(ds: Dataset) -> DesignResult:
    """Infer the design and recommend a test from a `Dataset`."""
    # 1. Numeric predictor present → regression / correlation (SPEC §8).
    if ds.x is not None:
        test = Test(
            name="Linear regression",
            parametric=True,
            nonparametric_alternative="Spearman correlation",
            notes=("Report Pearson r alongside the regression; use Spearman if the "
                   "relationship is monotonic but non-linear.",),
        )
        return DesignResult(
            design="regression",
            recommended_test=test,
            rationale=f"Numeric predictor '{ds.x}' present → linear regression / "
                      f"Pearson correlation.",
            factor_facts=tuple(_facts(ds, f) for f in ds.factors if ds.has(f)),
        )

    factors = [f for f in ds.factors if ds.has(f)]
    n_factors = len(factors)

    # 2. No factors → only an ungrouped two-sample KS is meaningful (SPEC §8
    #    last row: two distributions, no grouping). We can't confirm "exactly two
    #    distributions" without a grouping column, so recommend KS but flag it.
    if n_factors == 0:
        return DesignResult(
            design="ungrouped",
            recommended_test=Test(
                name="Two-sample Kolmogorov–Smirnov",
                parametric=False,
                notes=("Applies only when comparing exactly two distributions "
                       "(e.g. two frequency distributions / ISI CDFs). Supply the "
                       "two samples explicitly.",),
            ),
            rationale="No factor columns → no grouped test. Two-sample KS is the "
                      "only applicable comparison, for two distributions.",
            detectable=False,
        )

    facts = tuple(_facts(ds, f) for f in factors)

    # 3. One factor.
    if n_factors == 1:
        f = facts[0]
        shared = f.subjects_shared
        if f.n_levels < 2:
            return DesignResult(
                design="degenerate",
                recommended_test=None,
                rationale=f"Factor '{f.name}' has {f.n_levels} level(s); need ≥2 to "
                          f"compare.",
                factor_facts=facts,
                detectable=False,
            )
        if f.n_levels == 2:
            if shared:
                test = Test(
                    name="Paired t-test",
                    parametric=True,
                    nonparametric_alternative="Wilcoxon signed-rank",
                )
                design = "one_factor_2_paired"
                why = (f"One factor '{f.name}', 2 levels, subjects shared across "
                       f"levels → paired t-test.")
            else:
                test = Test(
                    name="Welch's t-test",
                    parametric=True,
                    nonparametric_alternative="Mann–Whitney U",
                    notes=(WELCH_CAVEAT,),
                )
                design = "one_factor_2_unpaired"
                why = (f"One factor '{f.name}', 2 levels, subjects distinct → "
                       f"Welch's t-test.")
            return DesignResult(design, test, why, facts)

        # ≥3 levels
        if shared:
            test = Test(
                name="Repeated-measures one-way ANOVA",
                parametric=True,
                nonparametric_alternative="Friedman",
                posthoc="pairwise (paired), Holm-corrected",
                correction="Geisser–Greenhouse",
            )
            design = "one_factor_multi_rm"
            why = (f"One factor '{f.name}', {f.n_levels} levels, subjects shared → "
                   f"RM one-way ANOVA with Geisser–Greenhouse correction.")
        else:
            test = Test(
                name="One-way ANOVA",
                parametric=True,
                nonparametric_alternative="Kruskal–Wallis",
                posthoc="Tukey (all pairs) or Dunnett (vs control)",
            )
            design = "one_factor_multi"
            why = (f"One factor '{f.name}', {f.n_levels} levels, subjects distinct → "
                   f"one-way ANOVA → Tukey, or Dunnett vs a control level.")
        return DesignResult(design, test, why, facts)

    # 4. Two or more factors → (mixed) two-way ANOVA; RM on shared factor(s).
    shared_factors = [f.name for f in facts if f.subjects_shared]
    if shared_factors:
        test = Test(
            name="Mixed-design two-way ANOVA",
            parametric=True,
            nonparametric_alternative=None,
            posthoc="pairwise, Holm-corrected",
            correction="Geisser–Greenhouse (on within factor)",
            notes=(f"Repeated measures on: {', '.join(shared_factors)}. "
                   f"For nested replicates a linear mixed model (subject random "
                   f"intercept) is the more honest fit — see the LMM path.",),
        )
        why = (f"{n_factors} factors ({', '.join(f.name for f in facts)}); subjects "
               f"shared across {', '.join(shared_factors)} → mixed two-way ANOVA, "
               f"RM on the shared factor(s).")
    else:
        test = Test(
            name="Two-way ANOVA",
            parametric=True,
            posthoc="pairwise, Holm-corrected",
        )
        why = (f"{n_factors} factors ({', '.join(f.name for f in facts)}), all "
               f"between-subjects → two-way ANOVA.")
    return DesignResult("two_factor", test, why, facts)
