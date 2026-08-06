"""Tests for loud import-time validation (SPEC §7)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from asterism.core.contract import Dataset
from asterism.core.design import detect_design
from asterism.core.validation import Severity, validate, worst_severity


def _codes(issues):
    return {i.code for i in issues}


def test_missing_required_column_is_error():
    df = pd.DataFrame({"group": ["A", "B"], "value": [1.0, 2.0]})  # no subject
    issues = validate(Dataset(df, factors=("group",)))
    assert "missing_required_column" in _codes(issues)
    assert worst_severity(issues) == Severity.ERROR


def test_undetermined_sentinel_flagged():
    df = pd.DataFrame({
        "value": ["10.2", "Undetermined", "11.5", "9.8"],
        "subject": ["a", "b", "c", "d"],
        "group": ["X", "X", "Y", "Y"],
    })
    issues = validate(Dataset(df, factors=("group",)))
    codes = _codes(issues)
    assert "sentinel_values" in codes
    sent = next(i for i in issues if i.code == "sentinel_values")
    assert sent.severity == Severity.ERROR
    assert "Undetermined" in sent.message


def test_non_numeric_value_flagged_separately_from_sentinel():
    df = pd.DataFrame({
        "value": ["1.0", "banana", "2.0"],
        "subject": ["a", "b", "c"],
        "group": ["X", "Y", "Y"],
    })
    issues = validate(Dataset(df, factors=("group",)))
    assert "non_numeric_value" in _codes(issues)
    nn = next(i for i in issues if i.code == "non_numeric_value")
    assert "banana" in nn.message


def test_missing_values_reported_with_location():
    df = pd.DataFrame({
        "value": [1.0, np.nan, 3.0, 4.0],
        "subject": ["a", "b", "c", "d"],
        "group": ["X", "X", "Y", "Y"],
    })
    issues = validate(Dataset(df, factors=("group",)))
    miss = next(i for i in issues if i.code == "missing_values")
    assert "1" in miss.where  # row index 1 is the NaN


def test_duplicate_subject_replicate_keys():
    df = pd.DataFrame({
        "value": [1.0, 2.0, 3.0],
        "subject": ["a", "a", "b"],
        "replicate": ["c1", "c1", "c1"],  # a/c1 duplicated
        "group": ["X", "X", "Y"],
    })
    issues = validate(Dataset(df, factors=("group",)))
    assert "duplicate_subject_replicate" in _codes(issues)


def test_unequal_and_small_group_n():
    rows = []
    # group X: 2 subjects (small), group Y: 4 subjects → unequal + small
    for i in range(2):
        rows.append({"value": 1.0, "subject": f"x{i}", "group": "X"})
    for i in range(4):
        rows.append({"value": 1.0, "subject": f"y{i}", "group": "Y"})
    issues = validate(Dataset(pd.DataFrame(rows), factors=("group",)))
    codes = _codes(issues)
    assert "unequal_group_n" in codes
    assert "small_group_n" in codes
    small = next(i for i in issues if i.code == "small_group_n")
    assert "X" in small.where


def test_group_n_counts_subjects_not_rows():
    # 2 subjects but many replicate rows each — must count as n=2, not n=many
    rows = []
    for grp in ("X", "Y"):
        for s in range(2):
            for _ in range(20):
                rows.append({"value": 1.0, "subject": f"{grp}{s}",
                             "replicate": "r", "group": grp})
    issues = validate(Dataset(pd.DataFrame(rows), factors=("group",)))
    # both groups n=2 subjects → small_group_n fires despite 40 rows each
    assert "small_group_n" in _codes(issues)


def test_incomplete_pairing_when_design_paired():
    # s3 only appears in 'pre' → incomplete pair
    rows = [
        {"value": 1.0, "subject": "s1", "cond": "pre"},
        {"value": 2.0, "subject": "s1", "cond": "post"},
        {"value": 1.0, "subject": "s2", "cond": "pre"},
        {"value": 2.0, "subject": "s2", "cond": "post"},
        {"value": 1.0, "subject": "s3", "cond": "pre"},
    ]
    ds = Dataset(pd.DataFrame(rows), factors=("cond",))
    design = detect_design(ds)
    issues = validate(ds, design=design)
    inc = next(i for i in issues if i.code == "incomplete_pairing")
    assert "s3" in inc.message


def test_template_version_stale():
    df = pd.DataFrame({"value": [1.0], "subject": ["a"], "group": ["X"]})
    issues = validate(Dataset(df, factors=("group",)),
                      template_version=1, current_template_version=3)
    assert "template_out_of_date" in _codes(issues)


def test_clean_dataset_has_no_errors():
    rows = []
    for grp in ("WT", "KO"):
        for s in range(5):
            rows.append({"value": 10.0 + s, "subject": f"{grp}{s}", "group": grp})
    issues = validate(Dataset(pd.DataFrame(rows), factors=("group",)))
    assert all(i.severity != Severity.ERROR for i in issues)
