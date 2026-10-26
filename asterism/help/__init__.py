"""ASTERISM's built-in help: Markdown pages shipped with the app (offline, always matching
the installed version), a small Markdown-to-HTML converter, full-text search, and the map
from each dialog's Help button to its section.

Pages live in ``asterism/help/pages/<slug>.md``. Headings may carry an explicit anchor,
``## t tests {#t-tests}``; otherwise the anchor is made from the heading text (`anchor()`).
Links between pages: ``[text](graphs.md#axes)``, or ``[text](#axes)`` within a page.
"""

from __future__ import annotations

import html
import os
import re
from dataclasses import dataclass

PAGES_DIR = os.path.join(os.path.dirname(__file__), "pages")

# Contents, in reading order: (slug, title)
PAGES: list[tuple[str, str]] = [
    ("start", "Getting started"),
    ("tables", "Data tables"),
    ("importing", "Importing data"),
    ("prism", "Prism files"),
    ("graphs", "Graphs"),
    ("formatting", "Formatting graphs"),
    ("analyses", "Analyses"),
    ("analyses-groups", "Comparing groups"),
    ("analyses-xy", "Regression and curves"),
    ("analyses-counts", "Counts, survival and proportions"),
    ("transforms", "Transforms"),
    ("figures", "Figures and export"),
    ("settings", "Settings, autosave and files"),
    ("methods", "How results are calculated"),
    ("shortcuts", "Keyboard shortcuts"),
]

# Each dialog's Help button → page#anchor
TOPICS: dict[str, str] = {
    # tables
    "New table": "tables#new-table",
    "Table format": "tables#table-format",
    "Colour labels": "start#colour-labels",
    # importing
    "Importing data": "importing",
    # graphs
    "Graph type": "graphs#graph-types",
    "Format Graph": "formatting",
    "Graph formatting": "formatting#apply-to-other-graphs",
    "Drawing": "formatting#drawings",
    "Plot a function": "formatting#plot-a-function",
    # analyses
    "Analyze": "analyses",
    "t tests": "analyses-groups#t-tests",
    "One-way ANOVA": "analyses-groups#one-way-anova",
    "Two-way ANOVA": "analyses-groups#two-way-anova",
    "Multiple t tests": "analyses-groups#multiple-t-tests",
    "Nested t test": "analyses-groups#nested",
    "Nested one-way ANOVA": "analyses-groups#nested",
    "Normality tests": "analyses-groups#normality",
    "One-sample tests": "analyses-groups#one-sample",
    "Outliers": "analyses-groups#outliers",
    "Frequency distribution": "analyses-groups#frequency-distribution",
    "Linear regression": "analyses-xy#linear-regression",
    "Correlation": "analyses-xy#correlation",
    "Area under the curve": "analyses-xy#area-under-the-curve",
    "Nonlinear regression": "analyses-xy#nonlinear-regression",
    "Contingency tables": "analyses-counts#contingency",
    "Survival analysis": "analyses-counts#survival",
    "Fraction of total": "analyses-counts#fraction-of-total",
    # transforms
    "Transform": "transforms#transform",
    "Normalize": "transforms#normalize",
    "Remove baseline": "transforms#remove-baseline",
    "Prune rows": "transforms#prune-rows",
    "Smooth": "transforms#smooth",
    "Compare observed and expected": "transforms#observed-vs-expected",
    # figures, settings
    "Figures": "figures",
    "Settings": "settings",
    "Autosave and recovery": "settings#autosave",
}


def anchor(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def page_title(slug: str) -> str:
    return dict(PAGES).get(slug, slug)


def page_path(slug: str) -> str:
    return os.path.join(PAGES_DIR, f"{slug}.md")


def load(slug: str) -> str:
    try:
        with open(page_path(slug), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return f"# {page_title(slug)}\n\nThis page hasn't been written yet."


def resolve(topic: str) -> tuple[str, str]:
    """(slug, anchor) for a Help button's topic; unknown topics open the start page."""
    target = TOPICS.get(topic, "start")
    slug, _, frag = target.partition("#")
    return slug, frag


# ---------------------------------------------------------------------------
# Markdown → HTML (the subset the pages use)
# ---------------------------------------------------------------------------

_HEAD = re.compile(r"^(#{1,4})\s+(.*?)\s*(?:\{#([\w-]+)\})?\s*$")
_LIST = re.compile(r"^(\s*)([-*]|\d+[.)])\s+(.*)$")
_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")


def heading(line: str) -> tuple[int, str, str] | None:
    m = _HEAD.match(line)
    if not m:
        return None
    level, text, explicit = len(m.group(1)), m.group(2), m.group(3)
    return level, text, explicit or anchor(_plain_inline(text))


def _plain_inline(s: str) -> str:
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
    s = re.sub(r"[*`]", "", s)
    return re.sub(r"\s+", " ", s)


def _inline(s: str, t: dict) -> str:
    s = html.escape(s, quote=False)
    codes: list[str] = []                    # code spans are kept out of the other formatting

    def keep(m):
        codes.append(f'<code style="background:{t["code_bg"]}">{m.group(1)}</code>')
        return f"\x00{len(codes) - 1}\x00"
    s = re.sub(r"`([^`]+)`", keep, s)
    s = _format(s, t)
    return re.sub(r"\x00(\d+)\x00", lambda m: codes[int(m.group(1))], s)


def _format(s: str, t: dict) -> str:
    s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"(?<![\w*])\*([^*\s][^*]*)\*(?!\w)", r"<i>\1</i>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)",
               lambda m: f'<a href="{html.escape(m.group(2))}" style="color:{t["accent"]}">{m.group(1)}</a>', s)
    return s


def to_html(md: str, t: dict | None = None) -> str:
    """Convert a page to HTML for QTextBrowser. `t`: colours (text, muted, accent, code_bg,
    note_bg, border); defaults suit a light background."""
    t = {**{"text": "#15171b", "muted": "#55585f", "accent": "#007d93", "code_bg": "#ecebe6",
            "note_bg": "#e4f1f4", "border": "#d6d4ce"}, **(t or {})}
    out: list[str] = []
    lines = md.splitlines()
    i, para = 0, []

    def flush():
        if para:
            out.append(f'<p style="margin:0 0 10px 0">{_inline(" ".join(para), t)}</p>')
            para.clear()

    while i < len(lines):
        line = lines[i]
        if not line.strip():
            flush()
            i += 1
            continue
        h = heading(line)
        if h:
            flush()
            level, text, a = h
            size = {1: 22, 2: 17, 3: 14, 4: 13}[level]
            top = 0 if not out else {1: 0, 2: 18, 3: 12, 4: 10}[level]
            out.append(f'<a name="{a}"></a><h{level} style="font-size:{size}px; margin:{top}px 0 6px 0">'
                       f'{_inline(text, t)}</h{level}>')
            i += 1
            continue
        if line.startswith(">"):
            flush()
            block = []
            while i < len(lines) and lines[i].startswith(">"):
                block.append(lines[i][1:].strip())
                i += 1
            inner = " ".join(b for b in block if b)
            out.append(f'<table width="100%" cellpadding="8" style="margin:4px 0 12px 0" '
                       f'bgcolor="{t["note_bg"]}"><tr><td>{_inline(inner, t)}</td></tr></table>')
            continue
        if line.lstrip().startswith("|") and i + 1 < len(lines) and _TABLE_SEP.match(lines[i + 1]):
            flush()
            cells = lambda s: [c.strip() for c in s.strip().strip("|").split("|")]
            head = cells(line)
            i += 2
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                rows.append(cells(lines[i]))
                i += 1
            th = "".join(f'<th align="left" style="padding:3px 10px 3px 0">{_inline(c, t)}</th>' for c in head)
            body = "".join("<tr>" + "".join(f'<td style="padding:3px 10px 3px 0">{_inline(c, t)}</td>'
                                            for c in r) + "</tr>" for r in rows)
            out.append(f'<table cellspacing="0" style="margin:2px 0 12px 0"><tr>{th}</tr>{body}</table>')
            continue
        m = _LIST.match(line)
        if m:
            flush()
            items: list[tuple[int, bool, str]] = []
            while i < len(lines):
                m = _LIST.match(lines[i])
                if m:
                    items.append((len(m.group(1).expandtabs(4)), m.group(2)[0].isdigit(), m.group(3)))
                    i += 1
                elif lines[i].strip() and lines[i].startswith("  ") and items:   # continuation
                    d, o, s = items[-1]
                    items[-1] = (d, o, s + " " + lines[i].strip())
                    i += 1
                else:
                    break
            out.append(_list_html(items, t))
            continue
        para.append(line.strip())
        i += 1
    flush()
    return f'<div style="color:{t["text"]}">' + "\n".join(out) + "</div>"


def _list_html(items: list[tuple[int, bool, str]], t: dict) -> str:
    """Nested lists from (indent, ordered, text)."""
    html_, stack = [], []          # stack of (indent, tag)
    for depth, ordered, text in items:
        while stack and depth < stack[-1][0]:
            html_.append(f"</{stack.pop()[1]}>")
        if not stack or depth > stack[-1][0]:
            tag = "ol" if ordered else "ul"
            margin = "margin:0 0 10px 0" if not stack else "margin:2px 0 2px 0"
            html_.append(f'<{tag} style="{margin}">')
            stack.append((depth, tag))
        html_.append(f'<li style="margin:0 0 3px 0">{_inline(text, t)}</li>')
    while stack:
        html_.append(f"</{stack.pop()[1]}>")
    return "".join(html_)


# ---------------------------------------------------------------------------
# Structure and search
# ---------------------------------------------------------------------------

@dataclass
class Section:
    slug: str
    anchor: str
    title: str           # heading text
    level: int
    text: str            # plain text of the section body


def sections(slug: str) -> list[Section]:
    out: list[Section] = []
    cur = Section(slug, "", page_title(slug), 1, "")
    body: list[str] = []
    for line in load(slug).splitlines():
        h = heading(line)
        if h:
            cur.text = _plain_inline(" ".join(body))
            out.append(cur)
            level, text, a = h
            cur, body = Section(slug, "" if level == 1 else a, _plain_inline(text), level, ""), []
        elif not _TABLE_SEP.match(line):
            body.append(line.replace("|", " ").strip(">#- "))
    cur.text = _plain_inline(" ".join(body))
    out.append(cur)
    return [s for s in out if s.text.strip() or s.level > 1]


def search(query: str, limit: int = 40) -> list[tuple[Section, str]]:
    """Sections containing every word of the query, best first: (section, snippet)."""
    words = [w for w in re.findall(r"\w+", query.lower()) if w]
    if not words:
        return []
    scored = []
    for slug, _ in PAGES:
        for s in sections(slug):
            title, body = s.title.lower(), s.text.lower()
            if not all(w in title or w in body for w in words):
                continue
            score = sum(10 * (w in title) + body.count(w) for w in words)
            k = min((body.find(w) for w in words if w in body), default=-1)
            snippet = ""
            if k >= 0:
                a = max(0, k - 50)
                if a:
                    sp = s.text.find(" ", a)              # start at a word
                    a = sp + 1 if 0 <= sp < k else a
                end = s.text.rfind(" ", a, a + 150)
                end = end if end > k else a + 150
                snippet = ("…" if a else "") + s.text[a:end].strip() + ("…" if end < len(s.text) else "")
            scored.append((score, s, snippet))
    scored.sort(key=lambda x: -x[0])
    return [(s, sn) for _, s, sn in scored[:limit]]
