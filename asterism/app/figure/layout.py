"""Figure → positioned, self-drawing panel elements (same idea as graph/layout.py).

Coordinates: points, origin at the page's top-left. Each panel element draws its content in
a named group moved (and scaled) into place, so the figure exports with every graph as its
own group — "panel-A" holding "A-data-A", "A-y-axis", … — at exact page size.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable

from PySide6.QtCore import QRectF

from ...analysis.results import fmt
from ...doc.spec import FontSpec
from ..graph.canvas import MM, TextMetrics as TM

MISSING_W, MISSING_H = 60 * MM, 40 * MM


@dataclass
class FigElement:
    id: str
    kind: str                 # graph | table | results | text | letter | missing
    panel: str                # panel id ("" for letters' owner lookups)
    rect: QRectF              # page coordinates (points)
    draw: Callable
    meta: dict = field(default_factory=dict)


def letter_text(i: int, style: str) -> str:
    s = ""
    n = i + 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    low = s.lower()
    return {"A": s, "a": low, "(A)": f"({s})", "A.": f"{s}.", "(a)": f"({low})"}.get(style, s)


def lettered_order(panels: list[dict], rects: dict) -> list[dict]:
    """Reading order: rows (tops within 8 mm of each other), then left to right."""
    cand = [p for p in panels if p["kind"] != "text" and p.get("label") != "" and p["id"] in rects]
    cand.sort(key=lambda p: rects[p["id"]].top())
    rows: list[list[dict]] = []
    for p in cand:
        if rows and abs(rects[p["id"]].top() - rects[rows[-1][0]["id"]].top()) < 8 * MM:
            rows[-1].append(p)
        else:
            rows.append([p])
    return [p for row in rows for p in sorted(row, key=lambda q: rects[q["id"]].left())]


def _graph_content(project, panel):
    from ..graph.layout import GRAPHABLE_TYPES, build, content_bounds
    g = project.find(panel["ref"]) if project else None
    if g is None or getattr(g, "kind", "") != "graph" or g.table.table_type not in GRAPHABLE_TYPES:
        return None
    els, _ = build(g)
    return els, content_bounds(els, 2.0)


def _table_rows(project, panel):
    """(headers, rows) for a data/result table or an analysis's first results page."""
    if panel["kind"] == "results":
        a = project.find(panel["ref"]) if project else None
        if a is None or a.result is None or not a.result.pages:
            return None
        pg = a.result.pages[min(int(panel.get("page", 0)), len(a.result.pages) - 1)]
        heads = [pg.first_column or pg.title] + list(pg.columns)
        rows = [([label] + list(vals) + [""] * (len(pg.columns) - len(vals)), style)
                for label, vals, style in pg.rows if style != "blank"]
        return heads, rows, a.name
    t = _find_table(project, panel["ref"])
    if t is None:
        return None
    heads = ["X" if t.has_x() else ""]
    for ds in t.used_columns():
        for sub in range(t.width()):
            heads.append(t.label(ds) + (f" · {t.sub_label(ds, sub)}" if t.width() > 1 else ""))
    rows = []
    for r in range(t.nrows_used()):
        cells = [t.row_label(r) if not t.has_x() else fmt(t.get(r, "x")) if isinstance(t.get(r, "x"), float) else ""]
        for ds in t.used_columns():
            for sub in range(t.width()):
                v = t.get(r, t.flat(ds, sub))
                cells.append(fmt(v) if isinstance(v, float) else (v or ""))
        rows.append((cells, "row"))
    return heads, rows, t.name


def _find_table(project, ref):
    if project is None:
        return None
    t = project.find(ref)
    if t is not None and getattr(t, "kind", "") == "table":
        return t
    if isinstance(ref, str) and ref.endswith(".out"):
        a = project.find(ref[:-4])
        if a is not None and a.has_output():
            return a.output_table()
    return None


def _table_layout(heads, rows, fs: FontSpec):
    pad = 3.0
    ncol = len(heads)
    widths = [TM.width(h, fs) + 2 * pad for h in heads]
    for cells, _ in rows:
        for i, c in enumerate(cells[:ncol]):
            widths[i] = max(widths[i], TM.width(str(c), fs) + 2 * pad)
    rh = TM.ascent(fs) + TM.descent(fs) + 4.0
    return widths, rh


def _wrap(text: str, fs: FontSpec, width: float) -> list[str]:
    out = []
    for para in text.split("\n"):
        words, line = para.split(" "), ""
        for w in words:
            trial = (line + " " + w).strip()
            if TM.width(trial, fs) <= width or not line:
                line = trial
            else:
                out.append(line)
                line = w
        out.append(line)
    return out


def build_figure(fig, project) -> tuple[QRectF, list[FigElement]]:
    pw_mm, ph_mm = fig.page_mm()
    page = QRectF(0, 0, pw_mm * MM, ph_mm * MM)
    elements: list[FigElement] = []
    rects: dict[str, QRectF] = {}
    for panel in fig.panels:
        x, y, sc = panel["x"] * MM, panel["y"] * MM, float(panel.get("scale", 1.0) or 1.0)
        kind = panel["kind"]
        if kind == "graph":
            content = _graph_content(project, panel)
            if content is None:
                elements.append(_missing(panel, x, y, "The graph is no longer in the project"))
                rects[panel["id"]] = elements[-1].rect
                continue
            els, b = content
            rect = QRectF(x, y, b.width() * sc, b.height() * sc)
            dx, dy = x - b.x() * sc, y - b.y() * sc

            def draw(cv, els=els, dx=dx, dy=dy, sc=sc, pid=panel["id"]):
                prefix = letters.get(pid, pid)
                cv.begin_group(f"panel-{prefix}", dx, dy, sc)
                for e in els:
                    cv.begin_group(f"{prefix}-{e.id}")
                    e.draw(cv)
                    cv.end_group()
                cv.end_group()
            elements.append(FigElement(panel["id"], "graph", panel["id"], rect, draw,
                                       {"ref": panel["ref"], "origin": (dx, dy), "bounds": (b.x(), b.y()),
                                        "scale": sc}))
        elif kind in ("table", "results"):
            data = _table_rows(project, panel)
            if data is None:
                elements.append(_missing(panel, x, y, "The table is no longer in the project"))
                rects[panel["id"]] = elements[-1].rect
                continue
            heads, rows, title = data
            fs = FontSpec(size=float(panel.get("font_size", 8.0)))
            fs_b = FontSpec(size=fs.size, bold=True)
            widths, rh = _table_layout(heads, rows, fs_b)
            tw, th = sum(widths), rh * (len(rows) + 1)
            rect = QRectF(x, y, tw * sc, th * sc)

            def draw(cv, heads=heads, rows=rows, widths=widths, rh=rh, fs=fs, fs_b=fs_b, x=x, y=y, sc=sc,
                     pid=panel["id"]):
                cv.begin_group(f"panel-{letters.get(pid, pid)}", x, y, sc)
                tw = sum(widths)
                cv.line(0, 0, tw, 0, "#000000", 0.75)
                cx = 0.0
                for w, h in zip(widths, heads):
                    cv.text(cx + w / 2, rh - 4.0 - TM.descent(fs_b) + 1.5, h, fs_b, anchor="middle")
                    cx += w
                cv.line(0, rh, tw, rh, "#000000", 0.5)
                for i, (cells, style) in enumerate(rows):
                    yy = rh * (i + 2) - 4.0 - TM.descent(fs) + 1.5
                    cx = 0.0
                    for j, (w, c) in enumerate(zip(widths, cells)):
                        f = fs_b if style == "section" else fs
                        if j == 0:
                            cv.text(cx + 3.0, yy, str(c), f, anchor="start")
                        else:
                            cv.text(cx + w / 2, yy, str(c), f, anchor="middle")
                        cx += w
                cv.line(0, rh * (len(rows) + 1), tw, rh * (len(rows) + 1), "#000000", 0.75)
                cv.end_group()
            elements.append(FigElement(panel["id"], kind, panel["id"], rect, draw, {"ref": panel["ref"],
                                                                                  "title": title}))
        else:                                       # text
            fs = FontSpec(size=float(panel.get("font_size", 10.0)))
            w, h = panel.get("w", 60.0) * MM, panel.get("h", 15.0) * MM
            lines = _wrap(panel.get("text", "") or "", fs, w)
            lh = TM.ascent(fs) + TM.descent(fs) + 1.0
            h = max(h, lh * len(lines))
            rect = QRectF(x, y, w, h)

            def draw(cv, lines=lines, x=x, y=y, fs=fs, lh=lh, pid=panel["id"]):
                cv.begin_group(f"text-{pid}")
                for i, ln in enumerate(lines):
                    cv.text(x, y + TM.ascent(fs) + i * lh, ln, fs, anchor="start")
                cv.end_group()
            elements.append(FigElement(panel["id"], "text", panel["id"], rect, draw, {"text": panel.get("text", "")}))
        rects[panel["id"]] = elements[-1].rect
    # panel letters, in reading order
    letters: dict[str, str] = {}
    if fig.page.get("letters", True):
        order = lettered_order(fig.panels, rects)
        auto = 0
        for p in order:
            if p.get("label"):
                letters[p["id"]] = p["label"]
            else:
                letters[p["id"]] = letter_text(auto, fig.page.get("letter_style", "A"))
                auto += 1
        fs_l = FontSpec(family=fig.page.get("letter_font", "Arial"), size=float(fig.page.get("letter_size", 14.0)),
                        bold=bool(fig.page.get("letter_bold", True)))
        outside = fig.page.get("letter_pos", "outside") == "outside"
        for pid, lab in letters.items():
            r = rects[pid]
            lw = TM.width(lab, fs_l)
            lx = max(0.0, r.left() - lw - 1.5 * MM) if outside else r.left()
            ly = r.top() + TM.ascent(fs_l)

            def draw_l(cv, lab=lab, lx=lx, ly=ly, fs_l=fs_l):
                cv.begin_group(f"label-{lab}")
                cv.text(lx, ly, lab, fs_l, anchor="start")
                cv.end_group()
            elements.append(FigElement(f"label-{lab}", "letter", pid,
                                       QRectF(lx, r.top(), TM.width(lab, fs_l), TM.ascent(fs_l) + TM.descent(fs_l)),
                                       draw_l, {"text": lab}))
    else:
        letters = {p["id"]: p["id"] for p in fig.panels}
    return page, elements


def _missing(panel, x, y, why) -> FigElement:
    rect = QRectF(x, y, MISSING_W * panel.get("scale", 1.0), MISSING_H * panel.get("scale", 1.0))

    def draw(cv, rect=rect):
        cv.rect(rect.x(), rect.y(), rect.width(), rect.height(), fill="#f3f2ee", stroke="#b0b0b0", width=0.75)
        cv.text(rect.center().x(), rect.center().y(), why, FontSpec(size=8), color="#55585f", anchor="middle")
    return FigElement(panel["id"], "missing", panel["id"], rect, draw, {})
