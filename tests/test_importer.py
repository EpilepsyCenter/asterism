"""Tests for the import layer (SPEC §5–6), against synthetic files that reproduce
the frozen apps' export writers byte-for-byte in shape (see fixtures.py)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from asterism.core.contract import SUBJECT, VALUE
from asterism.core.design import detect_design
from asterism.core.importer.inventory import (detect_header_row,
                                              detect_wide_or_long, inventory)
from asterism.core.importer.recipes import (Recipe, RecipeBook,
                                            column_signature)
from asterism.core.importer.reshape import (assign_tags_to_factors, explode_tags,
                                           melt_to_long, two_row_header_to_long)
from asterism.core.importer.roles import Role, guess_role
from asterism.core.importer import sources
from asterism.core.validation import Severity, validate, worst_severity

from fixtures import build_nednet_results, build_tracer_cohort_summary


# --- roles (§5.1) -----------------------------------------------------------

@pytest.mark.parametrize("name,expected", [
    ("animal_id", Role.SUBJECT),
    ("mouse", Role.SUBJECT),
    ("cell_id", Role.REPLICATE),
    ("roi", Role.REPLICATE),
    ("genotype", Role.GROUP),
    ("treatment", Role.GROUP),
    ("ddct", Role.VALUE),
    ("amplitude", Role.VALUE),
    ("excluded", Role.EXCLUDE),
])
def test_guess_role_synonyms(name, expected):
    assert guess_role(name).role == expected


def test_meta_prefixed_defaults_to_ignore():
    assert guess_role("meta.rig").role == Role.IGNORE


# --- inventory + shape (§5.1) ----------------------------------------------

def test_inventory_reports_dtype_and_guess():
    df = pd.DataFrame({"animal_id": ["m1", "m2"], "value": [1.0, 2.0]})
    info = {c.name: c for c in inventory(df)}
    assert info["animal_id"].guess.role == Role.SUBJECT
    assert info["value"].is_numeric
    assert info["animal_id"].n_unique == 2


def test_detect_wide_when_many_numeric_columns():
    df = pd.DataFrame({"animal": ["a", "b"], "rate": [1.0, 2.0],
                       "duration": [3.0, 4.0], "conv": [0.1, 0.2]})
    shape = detect_wide_or_long(df)
    assert shape.is_wide
    assert "rate" in shape.value_like_columns


def test_detect_long_when_value_column_present():
    df = pd.DataFrame({"subject": ["a"], "metric": ["amp"], "value": [1.0]})
    assert not detect_wide_or_long(df).is_wide


def test_detect_header_row_skips_preamble():
    rows = [
        ["QuantStudio export"], ["run", "2026"], [],
        ["Well", "Sample Name", "Target Name", "CT"],
        ["A1", "s1", "gapdh", 20.1],
    ]
    assert detect_header_row(rows) == 3


# --- reshape (§5.2–5.3, §6) -------------------------------------------------

def test_melt_to_long():
    df = pd.DataFrame({"animal": ["a", "b"], "rate": [1.0, 2.0], "dur": [3.0, 4.0]})
    long = melt_to_long(df, id_vars=["animal"], value_vars=["rate", "dur"])
    assert set(long["metric"]) == {"rate", "dur"}
    assert len(long) == 4


def test_explode_tags_recovers_atoms():
    s = pd.Series(["WT, adult", "KO, adult", None])
    ex = explode_tags(s)
    assert ex.iloc[0] == ["WT", "adult"]
    assert ex.iloc[2] == []


def test_assign_tags_to_factors():
    df = pd.DataFrame({"group_tags": ["WT, male", "KO, female"]})
    out = assign_tags_to_factors(
        df, "group_tags", {"WT": "genotype", "KO": "genotype",
                           "male": "sex", "female": "sex"})
    assert out["genotype"].tolist() == ["WT", "KO"]
    assert out["sex"].tolist() == ["male", "female"]


def test_two_row_header_to_long():
    rows = [
        ["", "sham", "sham", "kindled"],
        ["recording_day", "a1", "a2", "a3"],
        [1, 5, 6, 20],
        [2, 7, 8, 22],
    ]
    long = two_row_header_to_long(rows, metric="daily_count")
    assert len(long) == 6  # 2 days × 3 animals
    a3 = long[long["subject"] == "a3"]
    assert set(a3["group"]) == {"kindled"}
    assert "recording_day" in long.columns


# --- recipes (§5.5) ---------------------------------------------------------

def test_signature_stable_and_value_sensitive():
    sig1 = column_signature(["b", "a"], {"group": ["KO", "WT"]})
    sig2 = column_signature(["a", "b"], {"group": ["WT", "KO"]})  # reordered
    assert sig1 == sig2  # order-independent
    sig3 = column_signature(["a", "b"], {"group": ["WT", "HET"]})  # diff levels
    assert sig3 != sig1  # value-sensitive


def test_recipe_roundtrip(tmp_path):
    r = Recipe(signature="abc", source="tracer", sheet="Cells (long)",
               roles={"animal_id": "subject", "value": "value"},
               factors=["group"])
    p = r.save(tmp_path / "r.yaml")
    back = Recipe.load(p)
    assert back.source == "tracer"
    assert back.role_mapping()["animal_id"] == Role.SUBJECT


def test_recipe_book_find(tmp_path):
    book = RecipeBook(tmp_path)
    book.add(Recipe(signature="sig123", source="nednet"))
    assert book.find("sig123") is not None
    assert book.find("nope") is None


# --- TRACER source recipes (§6) ---------------------------------------------

def test_tracer_classify_and_import_long(tmp_path):
    path = build_tracer_cohort_summary(tmp_path / "cohort_summary.xlsx")
    sheets = sources.load_sheets_raw(path)
    plans = {p.kind: p for p in sources.classify_sheets(sheets)}
    assert "cells_long" in plans
    assert "cells_wide" in plans
    assert "events" in plans

    ds = sources.import_tracer_cells_long(sheets["Cells (long)"])
    assert ds.factors == ("group",)
    assert SUBJECT in ds.frame.columns
    assert "replicate" in ds.frame.columns
    # animal_id → subject: 4 animals, 3 cells each = 12 rows
    assert ds.frame[SUBJECT].nunique() == 4
    assert len(ds.frame) == 12
    # value coerced numeric (int or float both fine)
    assert ds.frame[VALUE].dtype.kind in "fi"


def test_tracer_wide_tag_to_factor(tmp_path):
    path = build_tracer_cohort_summary(tmp_path / "cohort_summary.xlsx")
    sheets = sources.load_sheets_raw(path)
    wide_rows = sheets["Cells (wide)"]
    ds = sources.import_tracer_cells_wide(
        wide_rows,
        metrics=["amplitude_pA", "frequency_Hz"],
        tag_assignment={"WT": "genotype", "KO": "genotype",
                        "adult": "age"},
    )
    # genotype factor recovered from the joined group_tags
    assert "genotype" in ds.frame.columns
    assert set(ds.frame["genotype"].dropna()) == {"WT", "KO"}
    # two metrics melted
    assert set(ds.frame["metric"]) == {"amplitude_pA", "frequency_Hz"}
    assert "genotype" in ds.factors


def test_tracer_events_import(tmp_path):
    path = build_tracer_cohort_summary(tmp_path / "cohort_summary.xlsx")
    sheets = sources.load_sheets_raw(path)
    plan = next(p for p in sources.classify_sheets(sheets) if p.kind == "events")
    ds = sources.import_tracer_events(sheets[plan.sheet], metric=plan.metric)
    assert ds.frame[SUBJECT].nunique() == 2
    assert (ds.frame["metric"] == "amplitude_pA").all()


# --- NED-Net source recipes (§6) --------------------------------------------

def test_nednet_per_animal_respects_excluded(tmp_path):
    path = build_nednet_results(tmp_path / "results_graph_data.xlsx")
    sheets = sources.load_sheets_raw(path)
    res = sources.import_nednet_per_animal(sheets["PerAnimal"])
    # a5 was excluded → reported, and absent from the dataset
    assert "a5" in res.excluded_subjects
    assert "a5" not in set(res.dataset.frame[SUBJECT])
    assert any("excluded" in n for n in res.notes)
    # 4 remaining animals × 4 melted metrics
    assert res.dataset.frame[SUBJECT].nunique() == 4
    assert set(res.dataset.frame["metric"]) >= {"rate_per_h", "mean_duration_s"}


def test_nednet_two_row_classify_and_import(tmp_path):
    path = build_nednet_results(tmp_path / "results_graph_data.xlsx")
    sheets = sources.load_sheets_raw(path)
    plan = next(p for p in sources.classify_sheets(sheets) if p.kind == "two_row")
    ds = sources.import_nednet_two_row(sheets[plan.sheet], metric=plan.metric)
    # 3 days × 4 animals
    assert len(ds.frame) == 12
    assert ds.x == "recording_day"
    assert set(ds.frame["group"]) == {"sham", "kindled"}


def test_nednet_isi_parse(tmp_path):
    path = build_nednet_results(tmp_path / "results_graph_data.xlsx")
    sheets = sources.load_sheets_raw(path)
    dist = sources.parse_nednet_isi(sheets["ISI_distribution"], kind="isi_dist")
    assert set(dist["group"]) == {"sham", "kindled"}
    assert {"x", "value", "group"} <= set(dist.columns)


# --- integration: import → design detection → validation --------------------

def test_end_to_end_tracer_long(tmp_path):
    path = build_tracer_cohort_summary(tmp_path / "cohort_summary.xlsx")
    sheets = sources.load_sheets_raw(path)
    ds = sources.import_tracer_cells_long(sheets["Cells (long)"])
    # one metric present here (amplitude_pA) → filter to it for a clean design
    ds.frame.drop(ds.frame.index[ds.frame["metric"] != "amplitude_pA"], inplace=True)
    design = detect_design(ds)
    assert design.design == "one_factor_2_unpaired"   # WT vs KO, distinct animals
    assert design.recommended_test.name == "Welch's t-test"
    issues = validate(ds, design=design)
    # small groups (2 animals each) but no hard errors
    assert worst_severity(issues) != Severity.ERROR
