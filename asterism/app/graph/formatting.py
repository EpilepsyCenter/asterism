"""Colour schemes and copying formatting between graphs (no Qt widgets; pure spec edits)."""

from __future__ import annotations

import copy

from ...doc.spec import PALETTE


def _shade(hex_: str, t: float) -> str:
    """Mix a colour towards white (t > 0) or black (t < 0)."""
    h = hex_.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    if t >= 0:
        r, g, b = (round(c + (255 - c) * t) for c in (r, g, b))
    else:
        r, g, b = (round(c * (1 + t)) for c in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


def _pairs(colors: list[str], fill_light: float = 0.35) -> list[tuple[str, str]]:
    """(fill, ink) pairs from a list of base colours: lighter fills, the base as ink."""
    return [(_shade(c, fill_light), c) for c in colors]


VIRIDIS = ["#440154", "#3b528b", "#21918c", "#5ec962", "#fde725", "#2c728e", "#73d055", "#482878"]
OKABE_ITO = ["#000000", "#e69f00", "#56b4e9", "#009e73", "#0072b2", "#d55e00", "#cc79a7", "#f0e442"]

SCHEMES: dict[str, tuple[str, list[tuple[str, str]]]] = {
    "asterism": ("ASTERISM", list(PALETTE)),
    "greys": ("Greys (print)", [("#ffffff", "#000000"), ("#bdbdbd", "#000000"), ("#737373", "#000000"),
                                ("#252525", "#000000"), ("#e0e0e0", "#4d4d4d"), ("#969696", "#252525")]),
    "colourblind": ("Colour-blind safe (Okabe–Ito)", _pairs(OKABE_ITO, 0.45)),
    "viridis": ("Viridis", _pairs(VIRIDIS, 0.3)),
    "teal": ("NED-Net teal", [("#acdae6", "#007d93"), ("#62c8df", "#005262"), ("#d7eef4", "#3a8ea0"),
                              ("#7fb8c6", "#00414e")]),
    "warm": ("Warm", _pairs(["#b2182b", "#ef8a62", "#fddbc7", "#d6604d", "#f4a582", "#67001f"], 0.3)),
    "pastel": ("Pastel", [(_shade(c, 0.55), _shade(c, -0.35)) for c in
                          ["#7fc97f", "#beaed4", "#fdc086", "#ffff99", "#386cb0", "#f0027f"]]),
    "black": ("Black and white", [("#ffffff", "#000000"), ("#000000", "#000000")]),
}


def apply_scheme(spec, key: str, columns: list[int]):
    """A copy of the spec with the scheme's colours on the data sets, in order."""
    name, pairs = SCHEMES[key]
    new = copy.deepcopy(spec)
    for i, c in enumerate(columns):
        fill, ink = pairs[i % len(pairs)]
        st = new.style(c)
        st.bar_fill, st.symbol_color = fill, ink
    return new


ASPECTS = {
    "styles": "How the data sets are drawn (symbols, bars, error bars, colours)",
    "axes": "Axis formatting (ticks, numbering, scale) — not the ranges",
    "ranges": "Axis ranges",
    "size": "Size and frame",
    "fonts": "Fonts",
    "significance": "Significance brackets",
    "arrangement": "Arrangement (grouped, nested, XY, survival and pie options)",
}
_ARRANGEMENT = ("grouped_layout", "nested_layout", "show_legend", "heat_low", "heat_high", "parts_layout",
                "parts_labels", "donut_hole", "surv_percent", "surv_death", "surv_ci", "surv_ticks",
                "connect_rows", "connect_width", "connect_color", "palette")


def copy_formatting(source, target, aspects: set[str]):
    """A copy of target's spec with the chosen aspects of source's formatting. Data-set styles
    map by position (the first data set's style to the first, …); titles are never copied."""
    s, t = source.spec, copy.deepcopy(target.spec)
    if "styles" in aspects:
        src_cols = source.table.used_columns() or [0]
        for i, c in enumerate(target.table.used_columns()):
            t.datasets[c] = copy.deepcopy(s.style(src_cols[min(i, len(src_cols) - 1)]))
        t.default_style = copy.deepcopy(s.default_style)
    for axis in ("x", "y"):
        sa, ta = getattr(s, axis), getattr(t, axis)
        if "axes" in aspects:
            for f in ("scale", "ticks_dir", "ticks_len", "minor", "numbering", "fmt", "decimals", "prefix",
                      "suffix", "label_rotation"):
                setattr(ta, f, getattr(sa, f))
        if "ranges" in aspects:
            for f in ("auto", "vmin", "vmax", "interval"):
                setattr(ta, f, getattr(sa, f))
    if "size" in aspects:
        for f in ("col_width_mm", "y_len_mm", "x_len_mm", "frame", "axis_width", "axis_color", "show_title"):
            setattr(t, f, getattr(s, f))
    if "fonts" in aspects:
        t.fonts = copy.deepcopy(s.fonts)
    if "significance" in aspects:
        t.sig = {**copy.deepcopy(s.sig), "hidden": list(t.sig.get("hidden", [])), "control": t.sig.get("control")}
        t.show_brackets, t.p_format, t.brackets_ns = s.show_brackets, s.p_format, s.brackets_ns
    if "arrangement" in aspects:
        for f in _ARRANGEMENT:
            setattr(t, f, copy.deepcopy(getattr(s, f)))
    return t
