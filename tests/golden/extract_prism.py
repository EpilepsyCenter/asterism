"""Inspect the lab's Prism projects to harvest golden values (SPEC §13 step 4).

`.prism` files are zip archives of JSON. This reads the pieces we golden-test against
and prints them, so `prism_golden.json` can be regenerated / extended. It is NOT part
of the app — `.prism` import is explicitly out of scope (SPEC §1); this is test
tooling only, run by hand against sample_data/ (gitignored).

    python tests/golden/extract_prism.py sample_data/qPCR_SV2A.prism

Raw data arrays are matched to their analysis by hand (the data↔analysis linkage in
the Prism container is indirect); the printed data tables + results make that easy.
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path


def _load(zf: zipfile.ZipFile, name: str):
    with zf.open(name) as fh:
        return json.load(fh)


def inspect(path: Path) -> None:
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()

        print(f"\n### {path.name}")
        # Raw numeric data tables (pure-number data.csv = input data).
        print("\n-- data tables (data.csv) --")
        for n in names:
            if n.endswith("data.csv"):
                raw = zf.read(n).decode("utf-8", "replace").strip().splitlines()
                first = raw[0] if raw else ""
                is_numeric = first and all(
                    _is_num(c) for c in first.split(",") if c != "")
                tag = "RAW" if is_numeric else "results/other"
                print(f"  [{tag}] {n}  ({len(raw)} rows)  e.g. {first[:60]}")

        # Analyses: test type + headline results.
        print("\n-- analyses --")
        for n in names:
            if n.endswith("parameters.json"):
                base = n.rsplit("/", 1)[0]
                params = _load(zf, n)
                design = params.get("content", {}).get("experimentalDesign", "?")
                res_name = f"{base}/results.json"
                summary = ""
                if res_name in names:
                    summary = _summarise_results(_load(zf, res_name))
                print(f"  {base.split('/')[-1][:8]}  {design:20} {summary}")


def _summarise_results(res: dict) -> str:
    c = res.get("content", {})
    mw = c.get("mannWhitneyTestModel", {}).get("mannWhitneyTest")
    if mw:
        return (f"U={mw['U']} p_exact={mw['pValueExact']['value']:.4e} "
                f"p_approx={mw['pValueApproximate']['value']:.4e}")
    # Welch / t-test: dig for t, df, p
    t = _find_first(c, "t")
    df = _find_first(c, "df")
    p = _find_first(c, "pValue")
    if t is not None:
        pv = p.get("value") if isinstance(p, dict) else p
        return f"t={t:.4f} df={df:.4f} p={pv:.4f}" if df else f"t={t:.4f} p={pv}"
    return ""


def _find_first(o, key):
    if isinstance(o, dict):
        if key in o:
            return o[key]
        for v in o.values():
            r = _find_first(v, key)
            if r is not None:
                return r
    elif isinstance(o, list):
        for v in o:
            r = _find_first(v, key)
            if r is not None:
                return r
    return None


def _is_num(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False


if __name__ == "__main__":
    for arg in sys.argv[1:] or []:
        inspect(Path(arg))
    if len(sys.argv) < 2:
        print(__doc__)
