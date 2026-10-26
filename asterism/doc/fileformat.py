"""The `.asterism` project file: a zip holding `project.json`.

Results are derived and never saved; they are recomputed on open. Saves are atomic
(temp file in the same folder, then replace), so a crash mid-save never leaves a
half-written project. Files from a newer format version are refused with a clear
message rather than half-read.
"""

from __future__ import annotations

import json
import os
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from .model import (Analysis, AnalysisEngine, Table, Graph, InfoSheet, FigureSheet,
                    Project)
from .spec import spec_from_dict, spec_to_dict

FORMAT_ID = "asterism-project"
FORMAT_VERSION = 2
EXTENSION = ".asterism"
MIMETYPE = b"application/x-asterism-project"


class ProjectFileError(Exception):
    """The file is not a readable ASTERISM project."""


class NewerVersionError(ProjectFileError):
    """The file was written by a newer ASTERISM."""


# ---------------------------------------------------------------------------
# Project → dict
# ---------------------------------------------------------------------------

def _app_version() -> str:
    from asterism import __version__
    return __version__


def project_to_dict(p: Project) -> dict:
    return {
        "format": FORMAT_ID,
        "version": FORMAT_VERSION,
        "app_version": _app_version(),
        "saved": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tables": [{"id": t.id, "name": t.name, **_table_to_dict(t)} for t in p.tables],
        "infos": [{"id": i.id, "name": i.name, "fields": dict(i.fields), "notes": i.notes}
                  for i in p.infos],
        "analyses": [{
            "id": a.id, "name": a.name, "auto_name": a.auto_name, "type": a.analysis_type,
            "table": a.table.id, "columns": list(a.columns), "params": dict(a.params),
        } for a in p.analyses],
        "graphs": [{
            "id": g.id, "name": g.name, "auto_name": g.auto_name, "table": g.home.id,
            **({"source": g.source.id} if g.source is not None else {}),
            "spec": spec_to_dict(g.spec),
        } for g in p.graphs],
        "figures": [{"id": f.id, "name": f.name} for f in p.figures],
    }


# ---------------------------------------------------------------------------
# dict → Project
# ---------------------------------------------------------------------------

def project_from_dict(d: dict, engine: AnalysisEngine | None = None) -> Project:
    if d.get("format") != FORMAT_ID:
        raise ProjectFileError("This is not an ASTERISM project.")
    version = int(d.get("version", 0))
    if version > FORMAT_VERSION:
        raise NewerVersionError(
            f"This project was saved by a newer version of ASTERISM "
            f"({d.get('app_version', 'unknown')}). Update ASTERISM to open it.")
    d = migrate(d, version)

    p = Project(engine)
    tables: dict[str, Table] = {}
    for td in d.get("tables", []):
        t = _table_from_dict(td)
        tables[t.id] = t
        p.insert(t)
    for idd in d.get("infos", []):
        info = InfoSheet(idd.get("name", ""), id=idd.get("id"))
        info.fields.update(idd.get("fields", {}))
        info.notes = idd.get("notes", "")
        p.insert(info)
    analyses: dict[str, Analysis] = {}

    def resolve(tid):
        """A data table, or an analysis's output table ("<analysis id>.out")."""
        if tid in tables:
            return tables[tid]
        if isinstance(tid, str) and tid.endswith(".out") and tid[:-4] in analyses:
            return analyses[tid[:-4]].output_table()
        return None
    pending = list(d.get("analyses", []))
    while pending:                        # analyses of other analyses' results come after them
        progress = False
        for ad in list(pending):
            t = resolve(ad.get("table"))
            if t is None:
                continue
            a = Analysis(ad.get("type", ""), t, ad.get("columns", []), ad.get("params", {}),
                         id=ad.get("id"), name=ad.get("name", ""))
            a.auto_name = bool(ad.get("auto_name", True))
            p.insert(a)
            analyses[a.id] = a
            pending.remove(ad)
            progress = True
        if not progress:
            break                         # orphans: their table is gone
    for gd in d.get("graphs", []):
        t = resolve(gd.get("table"))
        if t is None:
            continue
        src = analyses.get(gd["source"]) if gd.get("source") else None
        if gd.get("source") and src is None:
            continue                      # its analysis is gone
        g = Graph(gd.get("name", ""), t, spec_from_dict(gd.get("spec")), id=gd.get("id"), source=src)
        g.auto_name = bool(gd.get("auto_name", False))
        p.insert(g)
    for ld in d.get("figures", d.get("layouts", [])):     # "layouts": files before the rename
        p.insert(FigureSheet(ld.get("name", ""), id=ld.get("id")))
    p.undo.clear()
    p.mark_saved()
    return p


def migrate(d: dict, version: int) -> dict:
    """Bring an older file up to FORMAT_VERSION, one explicit step per version."""
    if version < 2:
        d = _to_v2(d)
    return d


def _to_v2(d: dict) -> dict:
    """v1 had Column tables only: {"type": "column", "titles": [...], "columns": [[...]]}."""
    d = dict(d)
    tables = []
    for td in d.get("tables", []):
        cols = td.get("columns", [])
        tables.append({"id": td.get("id"), "name": td.get("name", ""), "type": "column",
                       "y_format": "single", "replicates": 1, "x_format": "none",
                       "has_row_titles": False, "titles": td.get("titles", [""] * len(cols)),
                       "y": cols})
    d["tables"] = tables
    d["version"] = 2
    return d


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------

def _cell(v):
    if isinstance(v, str):
        return v
    return None if v is None else float(v)


def _table_to_dict(t: Table) -> dict:
    return {
        "type": t.table_type, "y_format": t.y_format, "replicates": t.replicates,
        "x_format": t.x_format, "has_row_titles": t.has_row_titles,
        "titles": list(t.titles), "sub_titles": [list(x) for x in t.sub_titles],
        "y": [list(c) for c in t.y], "x": list(t.x), "x_err": list(t.x_err),
        "row_titles": list(t.row_title_values),
        "excluded": [list(rc) for rc in sorted(t.excluded, key=lambda rc: (rc[0], str(rc[1])))],
    }


def _table_from_dict(td: dict) -> Table:
    y = [[_cell(v) for v in c] for c in td.get("y", [])]
    titles = list(td.get("titles", []))
    t = Table(td.get("name", ""), td.get("type", "column"), td.get("y_format", "single"),
              td.get("replicates", 1), td.get("x_format"), td.get("has_row_titles"),
              ncols=max(len(titles), 1), id=td.get("id"))
    w = t.width()
    need = t.ncols * w
    y = (y + [[] for _ in range(need)])[:max(need, len(y))]
    if len(y) > need:                         # more columns than titles: add data sets
        extra = -(-(len(y) - need) // w)
        t.titles += [""] * extra
        t.sub_titles += [[""] * w for _ in range(extra)]
        y += [[] for _ in range(t.ncols * w - len(y))]
    t.y = y
    for i, title in enumerate(titles):
        t.titles[i] = title
    for i, subs in enumerate(td.get("sub_titles", [])[:t.ncols]):
        t.sub_titles[i] = (list(subs) + [""] * w)[:w]
    t.x = [_cell(v) for v in td.get("x", [])]
    t.x_err = [_cell(v) for v in td.get("x_err", [])]
    t.row_title_values = [v if isinstance(v, str) or v is None else str(v)
                          for v in td.get("row_titles", [])]
    t.excluded = {(int(r), c if c == "x" else int(c)) for r, c in td.get("excluded", [])}
    return t


# ---------------------------------------------------------------------------
# Disk
# ---------------------------------------------------------------------------

def save(p: Project, path: str | os.PathLike) -> None:
    path = Path(path)
    data = json.dumps(project_to_dict(p), indent=1, ensure_ascii=False).encode("utf-8")
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as fh, zipfile.ZipFile(fh, "w") as z:
            z.writestr(zipfile.ZipInfo("mimetype"), MIMETYPE, zipfile.ZIP_STORED)
            z.writestr("project.json", data, zipfile.ZIP_DEFLATED)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def load(path: str | os.PathLike, engine: AnalysisEngine | None = None) -> Project:
    try:
        with zipfile.ZipFile(path) as z:
            d = json.loads(z.read("project.json").decode("utf-8"))
    except (zipfile.BadZipFile, KeyError, UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ProjectFileError("The file is damaged or is not an ASTERISM project.") from e
    return project_from_dict(d, engine)
