"""Harvest golden values from local Prism 10/11 projects (`.prism`, zip of JSON + CSV).

    .venv/bin/python tests/golden/harvest.py sample_data/*.prism

For every analysis we golden-test, this pulls the input values and Prism's reported
results and merges them into tests/golden/prism_golden.json (numbers only; titles and
names are dropped). The raw projects stay local (sample_data/ is gitignored).

Linkage inside a .prism file:
  analyses/<uid>/sheet.json      analysisClass, inputSheets[].uid, inputDataSets[].idx
  data/sheets/<uid>/sheet.json   table.uid, table.dataSets (column order)
  data/tables/<uid>/data.csv     the values, one CSV column per data set
  analyses/<uid>/results.json    Prism's statistics
  analyses/<uid>/result_sheets/*.json → dataSheet uid → a data table of tabular output
"""

from __future__ import annotations

import csv
import io
import json
import sys
import zipfile
from pathlib import Path

GOLDEN = Path(__file__).parent / "prism_golden.json"


def _load(z: zipfile.ZipFile, name: str):
    return json.load(z.open(name))


def _table_columns(z: zipfile.ZipFile, sheet_uid: str) -> list[list[float | None]]:
    sheet = _load(z, f"data/sheets/{sheet_uid}/sheet.json")
    tuid = sheet["table"]["uid"]
    text = z.read(f"data/tables/{tuid}/data.csv").decode("utf-8", "replace")
    rows = list(csv.reader(io.StringIO(text)))
    ncols = max((len(r) for r in rows), default=0)
    cols: list[list[float | None]] = [[] for _ in range(ncols)]
    for r in rows:
        for i in range(ncols):
            cell = r[i].strip() if i < len(r) else ""
            try:
                cols[i].append(float(cell) if cell else None)
            except ValueError:
                cols[i].append(None)
    return cols


def _values(col: list[float | None]) -> list[float]:
    return [v for v in col if v is not None]


def _idx(letter: str) -> int:
    n = 0
    for ch in letter:
        n = n * 26 + (ord(ch.upper()) - 64)
    return n - 1


def _set_width(z: zipfile.ZipFile, set_uid: str) -> int:
    d = _load(z, f"data/sets/{set_uid}.json")
    ends = []
    for r in d.get("replicate ranges", []):
        ends.append(int(str(r["range"]).split("~")[-1]))
    return max(ends) + 1 if ends else 1


def _grouped(z: zipfile.ZipFile, sheet_uid: str) -> dict:
    """A grouped (or XY) table with replicates: {"rows": [title], "sets": [[[reps per row]]]}"""
    sheet = _load(z, f"data/sheets/{sheet_uid}/sheet.json")
    set_uids = sheet["table"]["dataSets"]
    widths = [_set_width(z, u) for u in set_uids]
    cols = _table_columns(z, sheet_uid)
    titles_col, start = cols[0], 1
    out_sets = []
    for w in widths:
        block = cols[start:start + w]
        start += w
        out_sets.append([[c[r] for c in block] for r in range(len(titles_col))])
    rows = [str(v) if v is not None else "" for v in titles_col]
    return {"rows": rows, "sets": out_sets}


def _excluded_rows(rep: dict) -> set[int]:
    out = set()
    for ca in rep.get("cellAttributes", []):
        if "EXCLUDED" in ca.get("attributes", []):
            for part in str(ca["rows"]).split(","):
                lo, _, hi = part.partition("~")
                out.update(range(int(lo), int(hi or lo) + 1))
    return out


def _xy(z: zipfile.ZipFile, sheet_uid: str) -> dict:
    """An XY table: {"x": [...], "sets": [[[replicates per row]]]}, excluded values → None."""
    sheet = _load(z, f"data/sheets/{sheet_uid}/sheet.json")
    tab = sheet["table"]
    cols = _table_columns(z, sheet_uid)
    xset = _load(z, f"data/sets/{tab['xDataSet']}.json")
    xex = set().union(*[_excluded_rows(r) for r in xset.get("replicates", [])])
    nrows = max(len(c) for c in cols)
    x = [None if r in xex or r >= len(cols[0]) else cols[0][r] for r in range(nrows)]
    start, sets = 1, []
    for u in tab["dataSets"]:
        d = _load(z, f"data/sets/{u}.json")
        reps = d.get("replicates", [])
        w = max(len(reps), 1)
        block = cols[start:start + w] + [[]] * max(0, w - len(cols[start:start + w]))
        start += w
        exc = [_excluded_rows(r) for r in reps] + [set()] * w
        sets.append([[None if (r in exc[k] or r >= len(block[k])) else block[k][r] for k in range(w)]
                     for r in range(nrows)])
    return {"x": x, "sets": sets}


def harvest(path: Path) -> dict[str, list]:
    out: dict[str, list] = {"normality": [], "frequency": [], "two_way": [], "multiple_tests": [],
                            "linear_regression": [], "correlation": [], "contingency": []}
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        for n in sorted(names):
            if not (n.startswith("analyses/") and n.endswith("/sheet.json")):
                continue
            base = n.rsplit("/", 1)[0]
            sheet = _load(z, n)
            cls = sheet.get("analysisClass")
            if f"{base}/results.json" not in names or not sheet.get("inputSheets"):
                continue
            params = _load(z, f"{base}/parameters.json").get("content", {})
            results = _load(z, f"{base}/results.json").get("content", {})
            try:
                cols = _table_columns(z, sheet["inputSheets"][0]["uid"])
            except KeyError:
                continue
            if cls == "NORMALITY_TESTS":
                for s in results.get("samples", {}).values():
                    i = s["id"]["col"]["idx"]
                    model = s["value"].get("normalityModel", {})
                    case = {"values": _values(cols[i]), "prism": {}}
                    for key, stat in (("dAgostinoPearsonTest", "K2"), ("andersonDarlingTest", "A2"),
                                      ("shapiroWilkTest", "W"), ("kolmogorovSmirnovTest", "distance")):
                        t = model.get(key, {})
                        entry = {"status": t.get("status")}
                        if t.get("status") == "VALID":
                            entry["stat"] = t.get(stat)
                            entry["p"] = t["pValue"]["value"]
                            entry["p_state"] = t["pValue"].get("state")
                        case["prism"][key] = entry
                    out["normality"].append(case)
            elif cls == "TWO_WAY_ANOVA":
                model = results.get("repeatedMeasuresGlmAnovaModel") or results.get("anovaModel") or {}
                table = {k: {kk: (v.get(kk) if kk != "fTest" else
                                  {"f": v["fTest"].get("f"), "dfn": v["fTest"].get("dfNumerator"),
                                   "dfd": v["fTest"].get("dfDenominator"),
                                   "p": v["fTest"]["pValue"]["value"]})
                             for kk in ("ss", "df", "ms", "fTest") if kk in v}
                         for k, v in model.get("anovaTable", {}).items()}
                comps = []
                for t1 in model.get("multipleComparisons", {}).get("tests", {}).values():
                    for t2 in t1["value"].values():
                        v = t2["value"]
                        comps.append({"a": {"col": t1["id"]["col"]["idx"], "row": t1["id"]["row"]["idx"]},
                                      "b": {"col": t2["id"]["col"]["idx"], "row": t2["id"]["row"]["idx"]},
                                      "diff": v.get("meansDifference"), "se": v.get("meansDifferenceSE"),
                                      "ci": [v["meansDifferenceCI"]["lower"], v["meansDifferenceCI"]["upper"]],
                                      "df": v.get("df"), "statistic": v.get("statistic"),
                                      "p_adj": v["pValueAdjusted"]["value"]})
                pt = params.get("postTests", {}).get("pairwiseTests", {})
                out["two_way"].append({
                    "design": params.get("experimentalDesign"),
                    "method": model.get("multipleComparisons", {}).get("method"),
                    "families": pt.get("meansDesignType"),
                    "data": _grouped(z, sheet["inputSheets"][0]["uid"]),
                    "anova": table, "comparisons": comps})
            elif cls == "MULTIPLE_TWO_SAMPLE_TESTS":
                rows = []
                for r in results.get("rows", {}).values():
                    v = r["value"]
                    test = next((vv for kk, vv in v.items() if kk.endswith("Model")), {})
                    inner = next((vv for kk, vv in test.items() if isinstance(vv, dict) and "pValue" in vv), {})
                    rows.append({"row": r["id"]["row"]["idx"],
                                 "stat": inner.get("U", inner.get("t")),
                                 "p": inner.get("pValue", {}).get("value"),
                                 "p_adj": v.get("pValueAdjusted", {}).get("value")})
                out["multiple_tests"].append({
                    "test": params.get("test"),
                    "correction": params.get("multipleComparisons", {}).get("statistical", {}).get("test")
                    if params.get("multipleComparisons", {}).get("type") == "STATISTICAL" else
                    params.get("multipleComparisons", {}).get("type"),
                    "data": _grouped(z, sheet["inputSheets"][0]["uid"]), "rows": rows})
            elif cls == "SIMPLE_LINEAR_REGRESSION":
                data = _xy(z, sheet["inputSheets"][0]["uid"])
                for m in results.get("models", {}).values():
                    i = m["id"]["col"]["idx"]
                    mod = m["value"]["model"]
                    par = {k: {"estimate": v.get("estimate"), "se": v.get("se"),
                               "ci": [v["ci"]["lower"], v["ci"]["upper"]],
                               **({"f": v["significanceTest"]["f"],
                                   "dfd": v["significanceTest"]["dfDenominator"],
                                   "p": v["significanceTest"]["pValue"]["value"]}
                                  if "significanceTest" in v else {})}
                           for k, v in mod["parameters"].items()}
                    out["linear_regression"].append({
                        "params": params, "x": data["x"], "y": data["sets"][i],
                        "prism": {"parameters": par, "fit": mod["goodnessOfFit"],
                                  "summary": m["value"]["dataSummary"]}})
            elif cls == "CORRELATION":
                data = _xy(z, sheet["inputSheets"][0]["uid"])
                for key, model in results.items():
                    if not key.endswith("Model"):
                        continue
                    for outer in model.values():
                        for inner in outer["value"].values():
                            i = inner["id"]["col"]["idx"]
                            v = inner["value"]
                            out["correlation"].append({
                                "method": key, "x": data["x"], "y": data["sets"][i],
                                "prism": {"n": v.get("n"), "r": v.get("r"), "ci": [v["rCI"]["lower"], v["rCI"]["upper"]],
                                          "p": v["pValue"]["value"],
                                          "p_exact": v.get("pValueExact", {}).get("value"),
                                          "p_approx": v.get("pValueApproximate", {}).get("value")}})
            elif cls == "CONTINGENCY_TABLE":
                sheet_uid = sheet["inputSheets"][0]["uid"]
                cols_ = _table_columns(z, sheet_uid)
                table = [[c[r] for c in cols_[1:]] for r in range(len(cols_[0]))]     # col 0 = row titles
                prism = {}
                for key, v in results.items():
                    if isinstance(v, dict) and "pValue" in v:
                        prism[key] = v["pValue"]["value"]
                out["contingency"].append({"method": params.get("calc", {}).get("method"), "table": table,
                                           "prism": prism})
            elif cls == "FREQUENCY_DISTRIBUTION":
                calc = params.get("calc", {})
                views = [m for m in names if m.startswith(f"{base}/result_sheets/") and m.endswith(".json")]
                table = None
                for v in views:
                    view = _load(z, v)
                    if view.get("name") == "Frequency distribution" and view.get("dataSheet"):
                        try:
                            table = _table_columns(z, view["dataSheet"])
                        except KeyError:
                            table = None
                inputs = [_values(cols[_idx(ds["idx"])]) for ds in sheet["inputDataSets"]]
                summaries = [s["value"]["dataSummary"] for s in results.get("samples", {}).values()]
                out["frequency"].append({"calc": calc, "inputs": inputs, "output_table": table,
                                         "summaries": summaries})
    return out


def main(paths: list[str]) -> None:
    golden = json.loads(GOLDEN.read_text())
    harvested: dict[str, list] = {"normality": [], "frequency": [], "two_way": [], "multiple_tests": [],
                                  "linear_regression": [], "correlation": [], "contingency": []}
    for p in paths:
        h = harvest(Path(p))
        for k in harvested:
            harvested[k] += h[k]
    for k, v in harvested.items():
        golden[k] = v
    GOLDEN.write_text(json.dumps(golden, indent=1))
    print({k: len(v) for k, v in harvested.items()})


if __name__ == "__main__":
    main(sys.argv[1:])
