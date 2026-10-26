"""Prism graph formatting (`graphs/<uid>/data.bin` in a .prism file).

The format is undocumented; this reading of it comes from comparing the lab's own .prism files
(never from Prism's program). What is understood so far:

* The file is "PCFFGRA4" followed by records: tag (u16), length (u32), payload. A tag with
  bit 0x8000 can open a container — its payload is a header, child records follow until the
  bare 2-byte end marker (tag & 0x3fff) | 0x4000. (Some 0x8000 tags are plain records.)
* Under the graph container (0x8012): three axis records 0x0017 (X, Y, right Y: data range at
  bytes 0/8, axis range at 16/24 — exponents on a log axis — crossing point at 32), three axis
  settings 0x00a5 (bytes 64–67: 01 00 01 00 on a log axis), nine axis segments 0x8025 (three per
  axis; minimum at byte 2, maximum at 10, major tick interval at 54).
* Text objects (0x8020 with a 0x802b child whose 0x002c holds the text): the header holds the
  kind (u16; 2 = free text, 12 = legend entry), a bounding box (i16, y downwards) and a role
  byte pair at 28–29; record 0x0071 bytes 4–7 = 1 when the text is vertical. "XTitle",
  "YTitle", "Y1Title" are Prism's empty placeholders.

* Plotted data sets: 0x8020 objects with a 0x8028 child (its own data range: X 26/34, Y 42/50,
  used to match it to a table column) holding the style record 0x009c (317 bytes): byte 8 = 1
  points joined by a line; byte 12 bit 0x40 = each replicate joined (spaghetti); byte 13 bit
  0x02 = stacked bars; byte 14 bit 0x01 = error bars (XY); byte 15 bit 0x10 = bars; byte 28 =
  error type (2 SD, 3 SEM); byte 34 = symbol shape (0 none, 4 diamond, 5 circle, 10 open circle);
  byte 81 = symbol size; colours as flag + R G B at 204 (connecting line), 208 (bar fill), 212
  (bar border), 224 (symbol border), 228 (symbol fill).
* Line pattern: byte 66 of the 0x8028 data-set record, 0 solid, 1 dashed (from a solid/dashed
  pair saved for the purpose; other patterns unseen, read as dashed).
* Text visibility: bit 0x02 of the role byte = hidden. Legend entries are kind 12 texts.
* Not decoded yet: fonts, axis gaps, free-text annotations' placement.

Anything not understood is left alone (the graph keeps ASTERISM's defaults).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

MAGIC = b"PCFFGRA4"
PLACEHOLDERS = {"XTitle", "YTitle", "Y1Title", "Y2Title", "Title"}


@dataclass
class Node:
    tag: int
    payload: bytes
    children: list | None = None


def parse(buf: bytes, i: int = 8, end: int | None = None, closing: int | None = None, depth: int = 0):
    end = len(buf) if end is None else end
    out: list[Node] = []
    while i + 2 <= end:
        tag = struct.unpack_from("<H", buf, i)[0]
        if tag & 0x4000 and not tag & 0x8000:
            if closing is not None and (tag & 0x3fff) == closing:
                return out, i + 2
            raise ValueError(f"unexpected end marker at {i:#x}")
        if i + 6 > end:
            raise ValueError("truncated")
        ln = struct.unpack_from("<I", buf, i + 2)[0]
        if i + 6 + ln > end:
            raise ValueError("length past end")
        pl = buf[i + 6:i + 6 + ln]
        if tag & 0x8000 and depth < 40:
            try:
                kids, j = parse(buf, i + 6 + ln, end, tag & 0x3fff, depth + 1)
                out.append(Node(tag, pl, kids))
                i = j
                continue
            except ValueError:
                pass
        out.append(Node(tag, pl))
        i += 6 + ln
    if closing is not None:
        raise ValueError("missing end marker")
    return out, i


def walk(nodes):
    for n in nodes:
        yield n
        if n.children:
            yield from walk(n.children)


def _d(pl: bytes, o: int) -> float | None:
    return struct.unpack_from("<d", pl, o)[0] if o + 8 <= len(pl) else None


@dataclass
class AxisFormat:
    vmin: float | None = None
    vmax: float | None = None
    interval: float | None = None
    log: bool = False
    length_mm: float | None = None


@dataclass
class SetStyle:
    xmin: float | None = None
    xmax: float | None = None
    ymin: float | None = None
    ymax: float | None = None
    bars: bool = False
    connect: bool = False
    spaghetti: bool = False
    stacked: bool = False
    error_bars: bool = False
    error: int = 0
    shape: int = 5
    size: int = 3
    line: str = "#000000"
    fill: str = "#ffffff"
    border: str = "#000000"
    symbol_border: str = "#000000"
    symbol_fill: str = "#000000"
    dash: int = 0


@dataclass
class GraphFormat:
    title_visible: bool = True
    legend: bool = False
    sets: list = field(default_factory=list)        # SetStyle, in the file's order
    title: str = ""
    x_title: str = ""
    y_title: str = ""
    y2_title: str = ""
    axes: dict = field(default_factory=dict)        # "x", "y", "y2" → AxisFormat
    texts: list = field(default_factory=list)       # (text, kind, (x1, y1, x2, y2), vertical)


def decode(buf: bytes) -> GraphFormat:
    if not buf.startswith(MAGIC):
        raise ValueError("not a Prism graph")
    nodes, _ = parse(buf)
    gf = GraphFormat()
    top = next((n for n in walk(nodes) if n.tag == 0x8012 and n.children), None)
    if top is None:
        return gf
    kids = top.children
    axes = [c for c in kids if c.tag == 0x0017]
    settings = [c for c in kids if c.tag == 0x00a5]
    segments = [c for c in kids if c.tag == 0x8025]
    for k, name in enumerate(("x", "y", "y2")):
        if k >= len(axes):
            break
        ax = AxisFormat()
        pl = axes[k].payload
        lo, hi = _d(pl, 16), _d(pl, 24)
        ax.log = k < len(settings) and settings[k].payload[64:68] == b"\x01\x00\x01\x00"
        if lo is not None and hi is not None and hi > lo:
            ax.vmin, ax.vmax = (10 ** lo, 10 ** hi) if ax.log else (lo, hi)
        seg = segments[3 * k].payload if 3 * k < len(segments) else b""
        if len(seg) >= 32:
            units = struct.unpack_from("<H", seg, 30)[0]             # 1/600 inch
            if 60 <= units <= 12000:
                ax.length_mm = units / 600 * 25.4
        iv = _d(seg, 54)
        if iv and iv > 0 and not ax.log:
            ax.interval = iv
        gf.axes[name] = ax
    # text objects
    for n in walk(kids):
        if n.tag != 0x8020 or not n.children:
            continue
        sub = {c.tag: c for c in n.children}
        tb = sub.get(0x802b)
        if tb is None or not tb.children:
            continue
        txt = next((c.payload for c in tb.children if c.tag == 0x002c), b"").decode("latin-1").strip("\x00").strip()
        if len(n.payload) < 30:
            continue
        kind = struct.unpack_from("<H", n.payload, 0)[0]
        x1, y1, x2, y2 = struct.unpack_from("<4h", n.payload, 2)
        vertical = 0x0071 in sub and len(sub[0x0071].payload) >= 8 and sub[0x0071].payload[4:8] == b"\x01\x00\x00\x00"
        role = n.payload[28:30]
        gf.texts.append((txt, kind, (x1, y1, x2, y2), vertical, role))
    # plotted data sets and their styles
    for n in walk(kids):
        if n.tag != 0x8020 or not n.children:
            continue
        dsn = next((c for c in n.children if c.tag == 0x8028), None)
        if dsn is None or not dsn.children:
            continue
        st = next((c.payload for c in dsn.children if c.tag == 0x009c), b"")
        if len(st) < 232:
            continue
        rgb = lambda o: "#" + st[o + 1:o + 4].hex()
        ss = SetStyle(xmin=_d(dsn.payload, 26), xmax=_d(dsn.payload, 34), ymin=_d(dsn.payload, 42),
                      ymax=_d(dsn.payload, 50), connect=st[8] == 1, spaghetti=bool(st[12] & 0x40),
                      stacked=bool(st[13] & 0x02), error_bars=bool(st[14] & 0x01), bars=bool(st[15] & 0x10),
                      error=st[28], shape=st[34], size=st[81] if len(st) > 81 else 3, line=rgb(204), fill=rgb(208),
                      border=rgb(212), symbol_border=rgb(224), symbol_fill=rgb(228),
                      dash=dsn.payload[66] if len(dsn.payload) > 66 else 0)
        gf.sets.append(ss)
    gf.legend = any(t[1] == 12 for t in gf.texts)
    titles = [t for t in gf.texts if t[1] == 2 and t[4][:1] in (b"\x30", b"\x31", b"\x32", b"\x33")
              and t[0] not in PLACEHOLDERS]
    horiz = sorted((t for t in titles if not t[3]), key=lambda t: t[2][1])
    vert = sorted((t for t in titles if t[3]), key=lambda t: t[2][0])
    clean = lambda s: s
    hidden = lambda t: bool(t[4][0] & 0x02)
    if horiz:
        gf.title = clean(horiz[0][0])
        gf.title_visible = not hidden(horiz[0])
        if len(horiz) > 1 and not hidden(horiz[-1]):
            gf.x_title = clean(horiz[-1][0])
    on_page = [t for t in vert if t[2][2] > 0 and t[2][3] > 0 and not hidden(t)]
    if on_page:
        gf.y_title = clean(on_page[0][0])
        if len(on_page) > 1:
            gf.y2_title = clean(on_page[-1][0])
    return gf


SHAPES = {4: "diamond", 5: "circle", 10: "open_circle", 6: "open_square", 1: "square", 9: "open_circle"}
OPEN = {"open_circle", "open_square"}


def match_sets(gf: GraphFormat, table) -> dict:
    """{table column: SetStyle}, matching each style's data range to a column's values."""
    import numpy as np
    out, free = {}, list(range(len(gf.sets)))
    for c in table.used_columns():
        v = table.values(c)
        if not len(v):
            continue
        lo, hi = float(np.min(v)), float(np.max(v))
        best, score = None, None
        for k in free:
            s = gf.sets[k]
            if s.ymin is None or s.ymax is None:
                continue
            tol = 1e-6 + 1e-4 * max(abs(lo), abs(hi), 1.0)
            d = abs(s.ymin - lo) + abs(s.ymax - hi)
            if d <= 2 * tol and (score is None or d < score):
                best, score = k, d
        if best is not None:
            out[c] = gf.sets[best]
            free.remove(best)
    return out


def apply_styles(gf: GraphFormat, spec, table) -> None:
    tt = table.table_type
    spec.show_legend = gf.legend
    spec.show_title = gf.title_visible
    matched = match_sets(gf, table)
    if tt in ("grouped", "contingency") and any(s.stacked for s in matched.values()):
        spec.grouped_layout = "stacked"
    for c, s in matched.items():
        st = spec.style(c)
        shape = SHAPES.get(s.shape)
        if shape:
            st.symbol_shape = shape
        st.show_points = s.shape != 0
        st.symbol_size = max(1, min(round((s.size or 3) * 0.7), 8))    # Prism's sizes draw smaller
        st.symbol_color = s.symbol_border if shape in OPEN else s.symbol_fill
        if s.error in (2, 3):
            st.line_at = "mean_sd" if s.error == 2 else "mean_sem"
        st.line_dash = "dash" if s.dash else "solid"
        if tt == "xy":
            st.connect = s.connect
            st.xy_show = "spaghetti" if s.spaghetti else st.xy_show
            st.errors = s.error_bars
            if not st.show_points or s.spaghetti:
                st.symbol_color = s.line if s.line != "#000000" else st.symbol_color
            continue
        if s.bars or tt == "contingency":
            st.appearance, st.bars = "bar", True
            st.bar_fill, st.bar_border_color = s.fill, s.border
        else:
            st.appearance, st.bars = "scatter", False
        if tt in ("column", "grouped") and s.connect and not s.bars:   # before-after
            spec.connect_rows = True
            st.line_at, st.errors, st.spread = "none", False, "aligned"
            spec.connect_color = s.line


def _apply_size(gf: GraphFormat, spec, tt: str, table) -> None:
    """Axis lengths: Y directly; X as the X length (XY) or a column width that gives it."""
    y, x = gf.axes.get("y"), gf.axes.get("x")
    if y is not None and y.length_mm:
        spec.y_len_mm = round(y.length_mm, 1)
    if x is None or not x.length_mm:
        return
    L = x.length_mm
    if tt in ("xy", "survival"):
        spec.x_len_mm = round(L, 1)
        return
    if table is None or tt not in ("column", "grouped", "contingency"):
        return
    cols = [c for c in table.used_columns() if c not in spec.hidden]
    n = max(1, len(cols))
    if tt == "column":
        slots = n
    else:
        rows = sum(1 for r in range(table.nrows_used())
                   if any(len(table.row_values(r, c)) for c in cols)) if not table.is_summary() else table.nrows_used()
        rows = max(1, rows)
        lay = spec.grouped_layout
        slots = rows * 2.4 if lay in ("stacked", "stacked_pct") else \
            n * (rows + 0.8) if lay == "separated" else rows * (n + 0.8)
    spec.col_width_mm = round(max(1.0, min(L / slots, 60.0)), 1)


def apply(gf: GraphFormat, spec, table_type: str, table=None) -> list[str]:
    """Copy what was read onto an ASTERISM graph spec; returns notes on what was used."""
    used = ["titles"]
    if table is not None:
        apply_styles(gf, spec, table)
    if gf.title:
        spec.title = gf.title
    spec.y.title = gf.y_title                       # empty in Prism: empty here (not a placeholder)
    if table_type in ("xy", "survival"):
        spec.x.title = gf.x_title
    if gf.y2_title:
        spec.y2.title = gf.y2_title
    numeric_x = table_type in ("xy", "survival")
    _apply_size(gf, spec, table_type, table)
    for name in ("x", "y"):
        ax = gf.axes.get(name)
        if ax is None or ax.vmin is None or (name == "x" and not numeric_x):
            continue
        a = getattr(spec, name)
        a.scale = "log10" if ax.log else "linear"
        a.auto = False
        a.vmin, a.vmax = ax.vmin, ax.vmax
        if ax.interval:
            a.interval = ax.interval
        used.append(f"{name.upper()} axis")
    return used
