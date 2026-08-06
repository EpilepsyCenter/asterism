"""Tests for the data contract (SPEC §3–4)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from asterism.core.contract import Dataset


def _nested_frame():
    """2 groups × 3 subjects each × 4 replicates."""
    rows = []
    for grp, base in (("WT", 10.0), ("KO", 16.0)):
        for s in range(3):
            sid = f"{grp}{s}"
            for r in range(4):
                rows.append({"value": base + r, "subject": sid,
                             "replicate": f"cell{r}", "group": grp})
    return pd.DataFrame(rows)


def test_subject_means_collapses_replicates():
    ds = Dataset(_nested_frame(), factors=("group",))
    means = ds.subject_means()
    # 2 groups × 3 subjects = 6 rows, one per subject
    assert len(means) == 6
    # each subject's mean is base + mean(0,1,2,3) = base + 1.5
    wt = means[means["group"] == "WT"]["value"]
    assert np.allclose(wt, 11.5)


def test_n_report_honest_counts():
    ds = Dataset(_nested_frame(), factors=("group",))
    rep = ds.n_report()
    assert rep["subjects"] == 6
    assert rep["observations"] == 24
    # 6 subjects × 4 distinct replicate ids each
    assert rep["replicates"] == 24


def test_subjects_shared_distinct():
    ds = Dataset(_nested_frame(), factors=("group",))
    # each subject id belongs to exactly one group → distinct
    assert ds.subjects_shared_across("group") is False


def test_subjects_shared_repeated():
    # same subjects measured before/after → shared
    rows = []
    for s in range(4):
        for cond in ("pre", "post"):
            rows.append({"value": 1.0, "subject": f"s{s}", "cond": cond})
    ds = Dataset(pd.DataFrame(rows), factors=("cond",))
    assert ds.subjects_shared_across("cond") is True


def test_extra_and_missing_columns():
    df = _nested_frame().rename(columns={"value": "value"})
    df["mystery_tag"] = "x"
    ds = Dataset(df, factors=("group",))
    assert "mystery_tag" in ds.extra_columns()
    assert ds.missing_required() == []

    ds2 = Dataset(df.drop(columns=["subject"]), factors=("group",))
    assert "subject" in ds2.missing_required()
