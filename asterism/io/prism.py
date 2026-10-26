"""Prism files → ASTERISM (SPEC §11): `.prism` (Prism 10/11: a zip of JSON + CSV) and
`.pzfx` (Prism's XML format).

Data tables come across completely (titles, row titles, X, replicates, excluded values);
info sheets keep their fields and notes; analyses whose options map cleanly onto
ASTERISM's are re-created (and recomputed here — results are never copied from the file).
Graphs, layouts and anything without a clean equivalent are listed in the report, never
dropped silently.

Read with the standard library only; the file is data, never executed.
"""

from __future__ import annotations

import csv
import io
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from .build import date_number
from .sheets import number

TYPES = {"column": "column", "grouped": "grouped", "xy": "xy", "contingency": "contingency",
         "survival": "survival", "parts_of_whole": "parts", "partsofwhole": "parts", "parts": "parts",
         "multiple_variables": "multivar", "multivariable": "multivar", "multivar": "multivar",
         "nested": "nested"}
Y_FORMATS = {"y_single": "single", "y_replicates": "replicates", "y_mean_sd": "mean_sd",
             "y_mean_sem": "mean_sem", "y_mean_cv": "mean_cv", "y_mean_sd_n": "mean_sd_n",
             "y_mean_sem_n": "mean_sem_n", "y_mean_cv_n": "mean_cv_n", "y_mean_plus_minus": "mean_pm",
             "y_mean_upper_lower": "mean_limits"}


@dataclass
class PrismImport:
    tables: list = field(default_factory=list)          # Table
    infos: list = field(default_factory=list)           # InfoSheet
    analyses: list = field(default_factory=list)        # (type, table, columns, params, title)
    graphs: list = field(default_factory=list)          # (table, title, GraphFormat | None, shown columns)
    notes: list = field(default_factory=list)           # what didn't come across, and why


def read(path: str | Path) -> PrismImport:
    path = Path(path)
    if path.suffix.lower() == ".pzfx":
        return read_pzfx(path)
    return read_prism(path)


# ---------------------------------------------------------------------------
# .prism (zip)
# ---------------------------------------------------------------------------

def _plain(v, default: str = "") -> str:
    """Prism stores some titles as formatted text: {"string": "EGFP", "formatting": […]}."""
    if isinstance(v, dict):
        v = v.get("string", default)
    return str(v) if v not in (None, "") else default


def _rows_spec(spec) -> set[int]:
    out: set[int] = set()
    for part in str(spec).replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        if "~" in part or "-" in part:
            a, b = re.split(r"[~-]", part, maxsplit=1)
            try:
                out.update(range(int(a), int(b) + 1))
            except ValueError:
                pass
        else:
            try:
                out.add(int(part))
            except ValueError:
                pass
    return out


def _set_layout(sd: dict, width: int) -> tuple[int, list[set[int]]]:
    """(sub-columns, excluded rows per sub-column) of one data set."""
    excl = [set() for _ in range(width)]
    reps = []
    if "replicate ranges" in sd:
        for rr in sd["replicate ranges"]:
            idx = _rows_spec(rr.get("range", "0"))
            reps.append((sorted(idx), rr.get("replicate", {})))
    else:
        for k, rep in enumerate(sd.get("replicates", [])):
            reps.append(([k], rep))
    for idx, rep in reps:
        for ca in rep.get("cellAttributes", []) or []:
            if "EXCLUDED" in (ca.get("attributes") or []):
                rows = _rows_spec(ca.get("rows", ""))
                for k in idx:
                    if k < width:
                        excl[k] |= rows
    return width, excl


def read_prism(path: Path) -> PrismImport:
    from ..doc.model import InfoSheet, Table
    out = PrismImport()
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        load = lambda n: json.loads(z.read(n).decode("utf-8", "replace"))
        doc = load("document.json")
        sheets = doc.get("sheets", {})
        by_sheet: dict[str, Table] = {}
        for uid in sheets.get("data", []):
            n = f"data/sheets/{uid}/sheet.json"
            if n not in names:
                continue
            sh = load(n)
            title = _plain(sh.get("title"), "Data")
            try:
                t = _prism_table(z, names, load, sh)
            except Exception as e:                     # keep going: report the one that failed
                out.notes.append(f"Data table “{title}” could not be read ({e}).")
                continue
            if t is None:
                out.notes.append(f"Data table “{title}”: a table type ASTERISM doesn't have yet "
                                 f"({sh['table'].get('format')}).")
                continue
            by_sheet[uid] = t
            out.tables.append(t)
        for uid in sheets.get("info", []):
            n = f"info/{uid}/sheet.json"
            if n in names:
                d = load(n)
                info = InfoSheet(_plain(d.get("title"), "Project info"))
                for c in d.get("constants", []):
                    k, v = _plain(c.get("name")), _plain(c.get("value"))
                    if k:
                        key = "Notebook Reference" if k == "Notebook ID" else k
                        info.fields[key] = v
                info.notes = _plain(d.get("notesText"))
                out.infos.append(info)
        skipped: dict[str, int] = {}
        for uid in sheets.get("analyses", []):
            n = f"analyses/{uid}/sheet.json"
            if n not in names:
                continue
            a = load(n)
            cls = a.get("analysisClass", "?")
            params = load(f"analyses/{uid}/parameters.json").get("content", {}) \
                if f"analyses/{uid}/parameters.json" in names else {}
            ins = a.get("inputSheets") or []
            t = by_sheet.get(ins[0]["uid"]) if ins else None
            if t is None:
                skipped[cls] = skipped.get(cls, 0) + 1
                continue
            mapped = map_analysis(cls, params, t, [d.get("idx", "") for d in a.get("inputDataSets", [])])
            if mapped is None:
                skipped[cls] = skipped.get(cls, 0) + 1
                continue
            kind, cols, p, lost = mapped
            out.analyses.append((kind, t, cols, p, _plain(a.get("title"))))
            if lost:
                out.notes.append(f"“{_plain(a.get('title'), cls)}”: {lost}")
        for cls, k in sorted(skipped.items()):
            out.notes.append(f"{k} analys{'is' if k == 1 else 'es'} of type {cls.replace('_', ' ').lower()} "
                             f"not carried over (no matching ASTERISM analysis yet, or its data table is missing).")
        # graphs: matched to their table through the data sets they plot
        from .prism_graphs import decode
        set_owner = {}
        for t in out.tables:
            for k, su in enumerate(getattr(t, "_prism_sets", [])):
                set_owner[su] = (t, k)
        unmatched = failed = 0
        for gid in sheets.get("graphs", []):
            n = f"graphs/{gid}/sheet.json"
            if n not in names:
                continue
            gs = load(n)
            hits = [set_owner[u] for u in gs.get("inputDataSets", []) if u in set_owner]
            if not hits:
                unmatched += 1
                continue
            table = max({h[0] for h in hits}, key=lambda tb: sum(1 for h in hits if h[0] is tb))
            cols = sorted({k for tb, k in hits if tb is table})
            gf = None
            if f"graphs/{gid}/data.bin" in names:
                try:
                    gf = decode(z.read(f"graphs/{gid}/data.bin"))
                except Exception:
                    failed += 1
            out.graphs.append((table, _plain(gs.get("title"), table.name), gf, cols))
        nl = len(sheets.get("layouts", []))
        if unmatched:
            out.notes.append(f"{unmatched} graph{'s' if unmatched != 1 else ''} of analysis results (Prism's "
                             "formatting of those isn't read; ASTERISM's own graphs of the results are used).")
        if failed:
            out.notes.append(f"{failed} graph{'s' if failed != 1 else ''} couldn't be read.")
        if nl:
            out.notes.append(f"{nl} layout{'s' if nl != 1 else ''} not carried over (make figures in ASTERISM).")
    return out


def _prism_table(z, names, load, sh):
    from ..doc.model import Table
    td = sh["table"]
    tt = TYPES.get(str(td.get("format", "")).lower())
    if tt is None:
        return None
    yf = Y_FORMATS.get(td.get("dataFormat", "y_single"), "single")
    reps = int(td.get("replicatesCount", 1) or 1)
    set_uids = list(td.get("dataSets", []))
    has_rt = bool(td.get("rowTitlesDataSet"))
    has_x = bool(td.get("xDataSet"))
    xerr = str(td.get("xDataSetFormat", "")).endswith("err")
    xdate = str(td.get("xDataSetFormat", "")) == "date"          # stored as "2025-01-01 00:00:00"
    text = z.read(f"data/tables/{td['uid']}/data.csv").decode("utf-8", "replace")
    cols_raw = list(csv.reader(io.StringIO(text)))
    nrows = len(cols_raw)
    ncols = max((len(r) for r in cols_raw), default=0)
    col = lambda j: [r[j].strip() if j < len(r) else "" for r in cols_raw]
    t = Table(_plain(sh.get("title"), "Data"), tt, y_format=yf, replicates=reps, ncols=max(len(set_uids), 1),
              row_titles=has_rt,
              x_format=("date" if xdate else "numbers_err" if xerr else "numbers") if has_x else None)
    if xdate:
        t.x_format = "date"
    j = 0
    if has_rt:
        for i, v in enumerate(col(j)):
            if v:
                t.set(i, "row", v, emit=False)
        j += 1
    if has_x:
        xd = load(f"data/sets/{td['xDataSet']}.json") if f"data/sets/{td['xDataSet']}.json" in names else {}
        _w, xex = _set_layout(xd, 1)
        for i, v in enumerate(col(j)):
            n = (date_number(v) if v else None) if xdate else number(v)
            if n is not None:
                t.set(i, "x", n, emit=False)
        if xex[0]:
            t.set_excluded([(r, "x") for r in xex[0] if r < nrows], True, emit=False)
        j += 1
        if xerr:
            for i, v in enumerate(col(j)):
                n = number(v)
                if n is not None:
                    t.set(i, "xerr", n, emit=False)
            j += 1
    width = t.width()
    t._prism_sets = list(set_uids)
    excluded = []
    for ds, su in enumerate(set_uids):
        sd = load(f"data/sets/{su}.json") if f"data/sets/{su}.json" in names else {}
        t.titles[ds] = _plain(sd.get("title"))
        _w, ex = _set_layout(sd, width)
        for k in range(width):
            if j >= ncols:
                break
            for i, v in enumerate(col(j)):
                if not v:
                    continue
                n = number(v)
                if n is None:
                    if tt == "multivar":
                        t.set(i, t.flat(ds, k), v, emit=False)
                    continue
                t.set(i, t.flat(ds, k), n, emit=False)
            excluded += [(r, t.flat(ds, k)) for r in ex[k] if r < nrows]
            j += 1
    if excluded:
        t.set_excluded(excluded, True, emit=False)
    st = td.get("subcolumnTitlesDataSet")            # sub-column titles (e.g. subject names)
    if st and f"data/sets/{st}.json" in names:
        for entry in load(f"data/sets/{st}.json").get("titles", []):
            ds = int(entry.get("column", -1))
            for rp in entry.get("replicates", []):
                k, name = int(rp.get("replicate", -1)), _plain(rp.get("name"))
                if 0 <= ds < t.ncols and 0 <= k < width and name:
                    t.sub_titles[ds][k] = name
    return t


# ---------------------------------------------------------------------------
# analyses
# ---------------------------------------------------------------------------

def _letters(idx: str) -> int:
    n = 0
    for ch in idx:
        if ch.isalpha():
            n = n * 26 + (ord(ch.upper()) - 64)
    return n - 1


ONE_WAY_DESIGNS = {                               # Prism's experimental design → ASTERISM's settings
    "ORDINARY_ANOVA": {"design": "ordinary", "distribution": "normal"},
    "REPEATED_MEASURES_ANOVA": {"design": "rm", "distribution": "normal"},
    "KRUSKAL_WALLIS_TEST": {"design": "ordinary", "distribution": "nonparametric"},
    "FRIEDMAN_TEST": {"design": "rm", "distribution": "nonparametric"},
    "BROWN_FORSYTHE_ANOVA": {"design": "ordinary", "distribution": "normal", "welch": True},
    "WELCH_ANOVA": {"design": "ordinary", "distribution": "normal", "welch": True},
}
ONE_WAY_TESTS = {"TUKEY": "tukey", "DUNNET": "dunnett", "DUNNETT": "dunnett", "BONFERRONI_SIDAK": "sidak",
                 "SIDAK": "sidak", "BONFERRONI": "bonferroni", "HOLM_SIDAK": "holm_sidak", "DUNN": "dunn",
                 "DUNNET_T3": "t3", "DUNNETT_T3": "t3", "GAMES_HOWELL": "games_howell", "TAMHANE_T2": "t2"}


def _map_one_way(p: dict, cols: list[int], alpha: float):
    """Prism's one-way ANOVA family (ordinary, repeated measures, Kruskal-Wallis, Friedman,
    Brown-Forsythe/Welch) and its multiple comparisons."""
    from ..analysis.anova import METHODS_FOR, model_of
    design = ONE_WAY_DESIGNS.get(p.get("experimentalDesign"))
    if design is None or len(cols) < 3:
        return None
    params = dict(design)
    lost = []
    rm = p.get("repeatedMeasures", {})
    params["gg"] = not rm.get("assumeSphericity", False)
    post = p.get("postTests", {})
    pw = post.get("pairwiseTests", {})
    pdesign = pw.get("pairwiseDesign", {})
    if post.get("type") not in (None, "PAIRWISE_TESTS"):
        params["compare"] = "none"
        if post.get("type") not in ("NONE", "NO_POST_TESTS"):
            lost.append("its post test (only comparisons between pairs of groups come across)")
    elif pdesign.get("type") == "CONTROL_VS_ALL":
        params["compare"] = "control"
        k = pdesign.get("controlID", {}).get("col", {}).get("idx", 0)
        params["control"] = cols[k] if 0 <= k < len(cols) else cols[0]
    elif pdesign.get("type") in (None, "ALL_VS_ALL"):
        params["compare"] = "all"
    else:
        params["compare"] = "all"
        lost.append("the chosen pairs of groups (every pair is compared)")
    mc = pw.get("multipleComparisons", {})
    kind = mc.get("type", "STATISTICAL")
    model = model_of(params)
    if kind == "STATISTICAL":
        method = ONE_WAY_TESTS.get(mc.get("statistical", {}).get("test"))
        a_ = mc.get("statistical", {}).get("options", {}).get("significanceLevel")
    elif kind == "NO_CORRECTION":
        method = "dunn_none" if model in ("kw", "friedman") else "fisher"
        a_ = mc.get("noCorrection", {}).get("options", {}).get("significanceLevel")
    else:                                         # FDR: not offered for one-way ANOVA here
        method, a_ = None, None
        lost.append("false discovery rate comparisons (the default test is used)")
    if method is not None and method in METHODS_FOR[model]:
        params["method"] = method
    elif method is not None:
        lost.append(f"the {method} comparisons (the default test is used)")
    params["alpha"] = float(a_ if a_ is not None else alpha)
    if p.get("report", {}).get("descriptiveStatistics"):
        params["descriptive"] = True
    return "anova1", cols, params, "; ".join(lost)


def map_analysis(cls: str, p: dict, t, idx: list[str]):
    """(type, columns, params, what was lost) or None when there's no clean equivalent."""
    cols = [c for c in (_letters(i) for i in idx) if 0 <= c < t.ncols] or t.used_columns()
    tails = 1 if p.get("options", {}).get("pValueTailType") == "P_VALUE_ONE_TAILED" else 2
    alpha = p.get("options", {}).get("significanceLevel", 0.05)
    if cls == "T_TESTS_AND_NONPARAMETRIC":
        design = {"UNPAIRED_T_TEST": ("unpaired", "normal", "student"),
                  "WELCH_T_TEST": ("unpaired", "normal", "welch"),
                  "UNPAIRED_T_TEST_ON_LOGS": ("unpaired", "lognormal", "student"),
                  "MANN_WHITNEY_TEST": ("unpaired", "nonparametric", "mw"),
                  "KOLMOGOROV_SMIRNOV_TEST": ("unpaired", "nonparametric", "ks"),
                  "PAIRED_T_TEST": ("paired", "normal", "student"),
                  "RATIO_PAIRED_T_TEST": ("paired", "lognormal", "student"),
                  "WILCOXON_TEST": ("paired", "nonparametric", "wilcoxon")}.get(p.get("experimentalDesign"))
        if design is None or len(cols) < 2:
            return None
        d, dist, test = design
        return "ttest", cols[:2], {"design": d, "distribution": dist, "test": test, "tails": tails}, ""
    if cls == "MULTIPLE_TWO_SAMPLE_TESTS":
        test = {"MULTIPLE_MANN_WHITNEY_TESTS": "mw", "MULTIPLE_UNPAIRED_TWO_SAMPLE_UNEQUAL_SD_TESTS": "welch",
                "MULTIPLE_UNPAIRED_TWO_SAMPLE_EQUAL_SD_TESTS": "student", "MULTIPLE_UNPAIRED_T_TESTS": "student",
                "MULTIPLE_PAIRED_T_TESTS": "paired", "MULTIPLE_WILCOXON_TESTS": "wilcoxon"}.get(p.get("test"))
        if test is None:
            return None
        mc = p.get("multipleComparisons", {})
        kind = mc.get("type")
        if kind == "STATISTICAL":
            corr = {"HOLM_SIDAK": "holm_sidak", "BONFERRONI": "bonferroni", "SIDAK": "sidak"}.get(
                mc.get("statistical", {}).get("test"), "holm_sidak")
            a_ = mc.get("statistical", {}).get("options", {}).get("significanceLevel", 0.05)
            return "multiple_t", cols[:2], {"test": test, "correction": corr, "alpha": a_}, ""
        if kind == "FDR":
            corr = {"BENJAMINI_KRIEGER_YEKUTIELI": "fdr_bky", "BENJAMINI_HOCHBERG": "fdr_bh",
                    "BENJAMINI_YEKUTIELI": "fdr_by"}.get(mc.get("fdr", {}).get("test"), "fdr_bky")
            q = float(mc.get("fdr", {}).get("options", {}).get("discoveryLevel", 1.0)) / 100.0
            return "multiple_t", cols[:2], {"test": test, "correction": corr, "q": q}, ""
        return "multiple_t", cols[:2], {"test": test, "correction": "none"}, ""
    if cls == "ONE_WAY_ANOVA":
        return _map_one_way(p, cols, alpha)
    if cls == "TWO_WAY_ANOVA":
        design = {"REPEATED_MEASURES_BY_ROWS": "rm_rows", "REPEATED_MEASURES_BY_COLUMNS": "rm_cols",
                  "REPEATED_MEASURES_BY_BOTH": "rm_both"}.get(p.get("experimentalDesign"), "ordinary")
        fn = p.get("factorNames", {})
        mc = p.get("postTests", {}).get("pairwiseTests", {}).get("multipleComparisons", {})
        method = {"TUKEY": "tukey", "SIDAK": "sidak", "BONFERRONI": "bonferroni", "HOLM_SIDAK": "holm_sidak"}.get(
            mc.get("statistical", {}).get("test"), "tukey" if design == "ordinary" else "sidak")
        gg = not p.get("repeatedMeasures", {}).get("assumeSphericity", True)
        params = {"design": design, "method": method, "gg": gg,
                  "row_factor": fn.get("rowFactor", "Row factor"), "col_factor": fn.get("colFactor", "Column factor")}
        return "anova2", t.used_columns(), params, ""
    if cls == "NORMALITY_TESTS":
        tests = p.get("calc", {}).get("tests", {})
        return "normality", cols, {"dagostino": tests.get("dAgostinoPearson", True),
                                   "anderson": tests.get("andersonDarling", True),
                                   "shapiro": tests.get("shaproWilks", tests.get("shapiroWilk", True)),
                                   "ks": tests.get("kolmogorovSmirnov", True),
                                   "lognormal": p.get("calc", {}).get("testforLognormality", False),
                                   "alpha": alpha, "qq": p.get("graph", {}).get("qqPlot", False)}, ""
    if cls == "SIMPLE_LINEAR_REGRESSION":
        m = p.get("model", {})
        fp = m.get("fixedPoint", {})
        bands = {"CONFIDENCE": "confidence", "PREDICTION": "prediction"}.get(
            p.get("graph", {}).get("regressionLineBands", {}).get("type"), "none")
        return "linreg", cols, {"through": m.get("constrainLineToFixedPoint", False), "x0": fp.get("x", 0.0),
                                "y0": fp.get("y", 0.0), "bands": bands,
                                "replicates": "mean" if p.get("data", {}).get("handleReplicatesAs") == "AVERAGE"
                                else "individual",
                                "residual_plot": p.get("graph", {}).get("residualPlot", False),
                                "linearity_test": p.get("calc", {}).get("departureFromLinearityTest", False)}, ""
    if cls == "CORRELATION":
        method = "spearman" if p.get("experimentalDesign") == "NONPARAMETRIC" else "pearson"
        conf = p.get("options", {}).get("confidenceLevel", 95.0) / 100.0
        return "correlation", cols, {"method": method, "conf": conf, "tails": tails}, ""
    if cls == "CONTINGENCY_TABLE":
        c = p.get("calc", {})
        test = {"FISHER_EXACT_TEST": "fisher", "CHI_SQUARE_TEST": "chi2", "CHI_SQUARE": "chi2"}.get(c.get("method"), "fisher")
        return "contingency", t.used_columns(), {"test": test, "tails": tails}, ""
    if cls == "FREQUENCY_DISTRIBUTION":
        c = p.get("calc", {})
        tab = {"RELATIVE_FRACTIONS": "fractions", "RELATIVE_PERCENTAGES": "percentages"}.get(c.get("tabulate"), "counts")
        params = {"cumulative": c.get("distributionType") == "CUMULATIVE_FREQUENCY", "tabulate": tab}
        bw = c.get("binWidth", {})
        if bw.get("type") == "CUSTOM_BINS" and bw.get("value"):
            params["bin_width"] = float(bw["value"])
        for key, name in (("binCenterFirst", "first_center"), ("binCenterLast", "last_center")):
            v = c.get(key, {})
            if v and not v.get("isAuto", True):
                params[name] = float(v.get("value"))
        return "frequency", cols, params, ""
    return None


# ---------------------------------------------------------------------------
# .pzfx (XML)
# ---------------------------------------------------------------------------

PZFX_TYPES = {"OneWay": "column", "TwoWay": "grouped", "XY": "xy", "Survival": "survival",
              "Contingency": "contingency", "PartsOfWhole": "parts", "MultipleVariables": "multivar",
              "Nested": "nested"}
PZFX_Y = {"replicates": "replicates", "SDN": "mean_sd_n", "SEN": "mean_sem_n", "CVN": "mean_cv_n",
          "SD": "mean_sd", "SE": "mean_sem", "CV": "mean_cv", "low-high": "mean_pm",
          "upper-lower-limits": "mean_limits"}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _children(el, name):
    return [c for c in el if _local(c.tag) == name]


def _child(el, name):
    return next(iter(_children(el, name)), None)


def _text_of(el) -> str:
    return "".join(el.itertext()).strip() if el is not None else ""


def read_pzfx(path: Path) -> PrismImport:
    from ..doc.model import InfoSheet, Table
    out = PrismImport()
    root = ET.parse(str(path)).getroot()
    for info in [e for e in root.iter() if _local(e.tag) == "Info"]:
        sh = InfoSheet(_text_of(_child(info, "Title")) or "Project info")
        notes = _child(info, "Notes")
        sh.notes = _text_of(notes)
        for c in _children(info, "Constant"):
            k, v = _text_of(_child(c, "Name")), _text_of(_child(c, "Value"))
            if k:
                sh.fields[k] = v
        out.infos.append(sh)
    tables = [e for e in root.iter() if _local(e.tag) in ("Table", "HugeTable")]
    for te in tables:
        title = _text_of(_child(te, "Title")) or "Data"
        tt = PZFX_TYPES.get(te.get("TableType", "OneWay"))
        if tt is None:
            out.notes.append(f"Data table “{title}”: table type {te.get('TableType')} isn't supported yet.")
            continue
        ycols = _children(te, "YColumn")
        yf = PZFX_Y.get(te.get("YFormat", "replicates"), "replicates")
        width = max([int(y.get("Subcolumns", "1")) for y in ycols] + [1])
        if yf == "replicates" and width == 1:
            yf = "single"
        xcol = _child(te, "XColumn")
        xadv = _child(te, "XAdvancedColumn")
        rt = _child(te, "RowTitlesColumn")
        xf = te.get("XFormat", "none")
        t = Table(title, tt, y_format=yf, replicates=width, ncols=max(len(ycols), 1), row_titles=rt is not None,
                  x_format=("numbers_err" if xf == "error" else "numbers") if tt == "xy" else None)
        excluded = []

        def cells(sub):
            vals = []
            for d in _children(sub, "d"):
                vals.append((_text_of(d), d.get("Excluded") == "1"))
            return vals
        if rt is not None:
            sub = _child(rt, "Subcolumn")
            for i, (v, _e) in enumerate(cells(sub) if sub is not None else []):
                if v:
                    t.set(i, "row", v, emit=False)
        for xc in (xcol, xadv):
            if xc is None:
                continue
            subs = _children(xc, "Subcolumn")
            for k, sub in enumerate(subs[:2]):
                key = "x" if k == 0 else "xerr"
                for i, (v, e) in enumerate(cells(sub)):
                    n = number(v)
                    if n is not None:
                        t.set(i, key, n, emit=False)
                        if e and key == "x":
                            excluded.append((i, "x"))
        for ds, yc in enumerate(ycols):
            t.titles[ds] = _text_of(_child(yc, "Title"))
            for k, sub in enumerate(_children(yc, "Subcolumn")[:t.width()]):
                for i, (v, e) in enumerate(cells(sub)):
                    n = number(v)
                    if n is None:
                        if v and tt == "multivar":
                            t.set(i, t.flat(ds, k), v, emit=False)
                        continue
                    t.set(i, t.flat(ds, k), n, emit=False)
                    if e:
                        excluded.append((i, t.flat(ds, k)))
        if excluded:
            t.set_excluded(excluded, True, emit=False)
        out.tables.append(t)
    n_an = len([e for e in root.iter() if _local(e.tag) in ("Analysis", "AnalysisSheet")])
    n_gr = len([e for e in root.iter() if _local(e.tag) in ("Graph", "GraphSheet")])
    if n_an or n_gr:
        out.notes.append("Analyses and graphs in .pzfx files aren't read (Prism stores them in a binary "
                         "part); the data tables come across, each with ASTERISM's default graph.")
    return out


def into_project(imp: PrismImport, project, engine=None) -> None:
    """Add the imported tables (each with its default graph), info sheets and analyses."""
    from ..doc.model import Analysis
    from .prism_graphs import apply
    sheets = []
    by_table: dict = {}
    for table, title, gf, cols in imp.graphs:
        by_table.setdefault(id(table), []).append((title, gf, cols))
    for t in imp.tables:
        sheets.append(t)
        made = by_table.get(id(t)) or [(None, None, None)]
        for title, gf, cols in made:
            g = project.new_graph(t)
            if title:
                g.name, g.auto_name = title, False
            if cols:
                g.spec.hidden = {c for c in t.used_columns() if c not in cols}
            if gf is not None:
                apply(gf, g.spec, t.table_type, t)
            sheets.append(g)
    sheets += imp.infos
    for kind, t, cols, params, title in imp.analyses:
        sheets.append(Analysis(kind, t, cols, params))
    if sheets:
        project.add_sheets(sheets, "Import")
