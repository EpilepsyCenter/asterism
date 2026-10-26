"""Graph specification: everything the Format dialogs and direct edits change.

Plain dataclasses, serialised to JSON-safe dicts. Loading ignores unknown keys and
fills missing ones with defaults, so older and newer files both open.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field, fields


@dataclass
class FontSpec:
    family: str = "Arial"
    size: float = 12.0
    bold: bool = False
    italic: bool = False
    underline: bool = False
    color: str = ""                  # "" = black


@dataclass
class DataSetStyle:
    appearance: str = "scatter"      # scatter | bar | box | violin | floating | symbol
    line_at: str = "mean_sem"        # mean_sem | mean_sd | mean_ci | mean_range | median_iqr | median_range | mean | median | none
    bars: bool = False
    bar_fill: str = "#b4b4b4"
    bar_border: float = 1.0
    bar_border_color: str = "#000000"
    show_points: bool = True         # draw individual values (box: all points, else only outliers)
    symbol_color: str = "#000000"
    symbol_shape: str = "circle"     # circle | square | triangle | diamond | open_circle | open_square | cross | plus
    symbol_size: int = 3
    errors: bool = True
    error_color: str = "#000000"
    error_dir: str = "both"          # both | above | below
    error_style: str = "T"           # T | line
    error_width: float = 1.0
    # Box and whiskers (Prism's seven whisker methods). Whiskers obey `errors` on/off.
    whiskers: str = "minmax"         # minmax | tukey | p10 | p5 | p2_5 | p1 | minmax_all
    mean_plus: bool = False          # "+" at the mean
    spread: str = "swarm"            # swarm (side by side) | aligned (in a single line)
    violin_smooth: str = "medium"    # light | medium | heavy
    violin_quartiles: str = "dash"   # quartile lines: dash | dot | solid | none
    violin_median: str = "solid"     # median line: solid | dash | dot | none
    # XY graphs
    xy_show: str = "mean"            # mean (± error from line_at) | replicates | spaghetti
    connect: bool = False            # line joining the points (or means) in X order
    line_width: float = 1.0          # connecting line and fitted curve
    line_dash: str = "solid"         # solid | dash | dot
    fill: bool = False               # shade the area under the line
    fill_alpha: float = 0.25
    axis: str = "left"               # plot against the left or the right Y axis
    legend: bool = True              # show this data set in the legend
    nudge: float = 0.0               # shift right (points), e.g. to stagger overlapping data sets
    nudge_y: float = 0.0             # shift up (points; XY graphs, for waterfall plots)
    gaps: bool = False               # XY: break the line where a value is missing
    row_labels: bool = False         # XY: label each point with its row title
    by_row: bool = False             # XY: a different colour for each row


@dataclass
class AxisSpec:
    title: str = ""
    auto: bool = True
    vmin: float = 0.0
    vmax: float = 100.0
    interval: float = 20.0
    scale: str = "linear"            # linear | log10
    ticks_dir: str = "out"           # out | in | cross | none
    ticks_len: str = "normal"        # very_short | short | normal | long | very_long
    minor: int = 0                   # minor ticks between majors
    numbering: bool = True
    fmt: str = "decimal"             # decimal | scientific | power (3×10¹³) | antilog (values are log10: 10ⁿ)
    decimals: int = -1               # -1 = auto
    prefix: str = ""
    suffix: str = ""
    label_rotation: int = 0          # X axis only: 0 | 45 | 90
    date_fmt: str = "%d %b"          # X axis of a date column: strftime pattern, or "days"
    grid: bool = False               # grid lines at the major ticks
    grid_color: str = "#d9d9d9"
    grid_width: float = 0.5
    # extra ticks and lines: [{"value", "tick": bool, "line": bool, "dash": "solid|dash|dot",
    #                          "color", "label"}]
    extra: list = field(default_factory=list)
    # a break (two segments): {"on", "low_to", "high_from", "split" (bottom share of the
    # length), "gap" (points, default 14), "low_step", "high_step" (0 = automatic)}
    brk: dict = field(default_factory=dict)


def _default_fonts() -> dict[str, FontSpec]:
    return {
        "title": FontSpec(size=14, bold=True),
        "y_title": FontSpec(size=12, bold=True),
        "y_numbers": FontSpec(size=12),
        "x_labels": FontSpec(size=12, bold=True),
        "bracket": FontSpec(size=12),
        "legend": FontSpec(size=11),
        "stars": FontSpec(size=12),
    }


def default_sig() -> dict:
    """Significance brackets: shape, label, which comparisons, placement (Format Graph ›
    Significance)."""
    return {
        "shape": "bracket",          # bracket (with end ticks) | line
        "tick": 4.5,                 # end-tick length (points)
        "width": 0.0,                # line thickness (0 = the axis thickness)
        "color": "",                 # line and label colour ("" = the axis colour)
        "label": "stars",            # stars | p ("P = 0.012") | number ("0.012") | both ("**  P = 0.003")
        "levels": "four",            # four (0.05/0.01/0.001/0.0001) | three (0.05/0.01/0.001) | gp (Prism's GP style) | custom
        "cuts": [0.05, 0.01, 0.001, 0.0001],
        "max_stars": 4,              # most stars shown
        "alpha": 0.05,               # what counts as significant
        "ns_single": True,           # a two-group test shows "ns" when not significant
        "which": "significant",      # all | significant | control | none (multiple comparisons)
        "control": None,             # data set for "control"
        "hidden": [],                # bracket ids hidden one by one
        "order": "shortest",         # shortest spans lowest | table (the analysis's order)
        "distance": 8.0,             # gap above the data (points)
        "level_gap": 9.0,            # extra gap between stacked brackets (points)
        "label_gap": 2.5,            # gap between the line and its label (points)
    }


# Colours for data sets of grouped graphs: (fill, ink) pairs, readable in greyscale order
# and by colour-blind readers (fills light, inks dark).
PALETTE = [("#bdbdbd", "#000000"), ("#6baed6", "#08519c"), ("#fd8d3c", "#a63603"),
           ("#74c476", "#006d2c"), ("#9e9ac8", "#54278f"), ("#f781bf", "#8e0152"),
           ("#fee391", "#8c6d00"), ("#a6a6a6", "#3a3a3a")]
# Subject colours on nested graphs (dark enough for small symbols on white).
SUBJECT_COLORS = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e", "#17becf",
                  "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22"]
# Ready-made subject colour sets for nested graphs (Format Graph › Arrangement).
SUBJECT_PALETTES = {
    "distinct": ("Distinct (default)", SUBJECT_COLORS),
    "okabe": ("Colour-blind safe", ["#e69f00", "#56b4e9", "#009e73", "#f0e442", "#0072b2", "#d55e00",
                                    "#cc79a7", "#000000"]),
    "viridis": ("Viridis", ["#440154", "#46327e", "#365c8d", "#277f8e", "#1fa187", "#4ac16d", "#a0da39",
                            "#fde725"]),
    "greys": ("Greys", ["#000000", "#3d3d3d", "#666666", "#8c8c8c", "#b0b0b0", "#cfcfcf"]),
    "warm": ("Warm", ["#7f0000", "#b30000", "#d7301f", "#ef6548", "#fc8d59", "#fdbb84"]),
    "cool": ("Cool", ["#08306b", "#08519c", "#2171b5", "#4292c6", "#6baed6", "#9ecae1"]),
}
GROUPED_LAYOUTS = ("interleaved", "separated", "stacked", "stacked_pct", "lines", "heatmap", "pyramid")
NESTED_LAYOUTS = ("subjects", "pooled", "superplot")


def default_parts() -> dict:
    """Parts-of-whole options (Format Graph › Slices). Row keys are table row indexes as text."""
    return {
        "colors": {},                # row → fill colour ("" or missing = the automatic colour)
        "explode": {},               # row → pulled out by this % of the radius (pie and donut)
        "outer": False, "outer_width": 1.0, "outer_color": "#000000",       # around the whole chart
        "inner": True, "inner_width": 1.0, "inner_color": "#ffffff",        # between slices
        "legend_color": True, "legend_percent": False, "legend_value": False, "legend_label": True,
        "total": False, "total_prefix": "Total = ", "total_suffix": "",
        "reverse": False,            # slices in reverse row order
    }


def default_nested() -> dict:
    """Nested-graph colours (Format Graph › Arrangement)."""
    return {
        "color_by": "subject",       # subject | dataset (the data set's symbol colour)
        "colors": [],                # subject colours in order ([] = SUBJECT_COLORS)
        "restart": False,            # colours start again in each group (subject n matches across groups)
        "mean_size": 2.2,            # SuperPlot subject means: size relative to the points
        "mean_outline": "#000000",   # and their outline colour
    }


@dataclass
class GraphSpec:
    title: str = ""
    show_title: bool = True
    default_style: DataSetStyle = field(default_factory=DataSetStyle)
    datasets: dict[int, DataSetStyle] = field(default_factory=dict)
    hidden: set[int] = field(default_factory=set)
    x: AxisSpec = field(default_factory=lambda: AxisSpec(ticks_dir="none"))
    y: AxisSpec = field(default_factory=AxisSpec)
    y2: AxisSpec = field(default_factory=AxisSpec)       # right Y axis (when a data set uses it)
    # drawings on the graph: [{"id", "kind": text|line|arrow|rect|ellipse, "x1", "y1", "x2", "y2"
    # (points, plot coordinates), "color", "width", "dash", "fill", "text", "size"}]
    drawings: list = field(default_factory=list)
    # functions plotted on XY graphs: [{"id", "text": "Y = ...", "params": {name: value},
    # "from", "to" (None = the X axis range), "color", "width", "dash"}]
    functions: list = field(default_factory=list)
    # multiple-variable graphs: which variables go where (None/[] = automatic)
    mv: dict = field(default_factory=lambda: {"x": None, "y": [], "size": None, "color": None,
                                              "labels": False, "size_min": 4.0, "size_max": 22.0})
    axis_width: float = 1.0
    axis_color: str = "#000000"
    frame: str = "plain"             # plain | offset | box
    col_width_mm: float = 16.0
    y_len_mm: float = 50.0
    fonts: dict[str, FontSpec] = field(default_factory=_default_fonts)
    show_brackets: bool = True
    p_format: str = "stars"          # stars | exact
    brackets_ns: bool = False        # multiple comparisons: also draw non-significant ones
    sig: dict = field(default_factory=default_sig)
    horizontal: bool = False         # column / grouped graphs: categories down the page, values across
    ba_summary: str = "none"         # before-after: mean/median with error beside the points (line_at keys)
    lines_points: bool = False       # grouped connected means: also show each replicate
    connect_rows: bool = False       # before-after: join each row's values across data sets
    connect_width: float = 1.0
    connect_color: str = "#000000"
    offsets: dict[str, tuple[float, float]] = field(default_factory=dict)
    # Grouped and nested graphs
    palette: bool = False            # new data sets take colours from PALETTE
    grouped_layout: str = "interleaved"   # see GROUPED_LAYOUTS
    nested_layout: str = "subjects"  # subjects (side by side) | pooled | superplot
    show_legend: bool = True
    x_len_mm: float = 60.0           # XY graphs: length of the X axis
    # Parts of whole
    parts_layout: str = "pie"        # pie | donut | stacked100
    parts_labels: str = "percent"    # percent | value | none
    donut_hole: float = 0.5
    # Survival
    surv_percent: bool = True        # Y as percent (else fraction)
    surv_death: bool = False         # plot deaths (1 − survival) instead
    surv_ci: str = "none"            # none | dashed | shaded | bars
    surv_ticks: bool = True          # mark censored subjects
    parts: dict = field(default_factory=default_parts)
    nested: dict = field(default_factory=default_nested)
    heat_low: str = "#f7fbff"
    heat_high: str = "#08306b"

    def style(self, c: int) -> DataSetStyle:
        if c not in self.datasets:
            st = copy.deepcopy(self.default_style)
            if self.palette:
                st.bar_fill, st.symbol_color = PALETTE[c % len(PALETTE)]
            self.datasets[c] = st
        return self.datasets[c]


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------

def _flat_to_dict(obj) -> dict:
    return {f.name: getattr(obj, f.name) for f in fields(obj)}


def _flat_from_dict(cls, d: dict | None):
    obj = cls()
    for f in fields(cls):
        if d and f.name in d:
            default = getattr(obj, f.name)
            v = d[f.name]
            if isinstance(default, bool):
                v = bool(v)
            elif isinstance(default, int) and not isinstance(default, bool):
                v = int(v)
            elif isinstance(default, float):
                v = float(v)
            elif isinstance(default, str):
                v = str(v)
            setattr(obj, f.name, v)
    return obj


def spec_to_dict(s: GraphSpec) -> dict:
    return {
        "title": s.title,
        "show_title": s.show_title,
        "default_style": _flat_to_dict(s.default_style),
        "datasets": {str(k): _flat_to_dict(v) for k, v in sorted(s.datasets.items())},
        "hidden": sorted(s.hidden),
        "x": _flat_to_dict(s.x),
        "y": _flat_to_dict(s.y),
        "y2": _flat_to_dict(s.y2),
        "drawings": [dict(d) for d in s.drawings],
        "functions": [dict(f) for f in s.functions],
        "mv": dict(s.mv),
        "axis_width": s.axis_width,
        "axis_color": s.axis_color,
        "frame": s.frame,
        "col_width_mm": s.col_width_mm,
        "y_len_mm": s.y_len_mm,
        "fonts": {k: _flat_to_dict(v) for k, v in s.fonts.items()},
        "show_brackets": s.show_brackets,
        "p_format": s.p_format,
        "brackets_ns": s.brackets_ns,
        "connect_rows": s.connect_rows,
        "connect_width": s.connect_width,
        "connect_color": s.connect_color,
        "offsets": {k: [float(v[0]), float(v[1])] for k, v in s.offsets.items()},
        **{k: getattr(s, k) for k in _EXTRA},
        "parts": {**s.parts, "colors": dict(s.parts["colors"]), "explode": dict(s.parts["explode"])},
        "nested": {**s.nested, "colors": list(s.nested["colors"])},
        "sig": dict(s.sig),
    }


_EXTRA = ("horizontal", "ba_summary", "lines_points", "palette", "grouped_layout", "nested_layout", "show_legend", "heat_low", "heat_high", "x_len_mm",
          "parts_layout", "parts_labels", "donut_hole", "surv_percent", "surv_death", "surv_ci", "surv_ticks")


def spec_from_dict(d: dict | None) -> GraphSpec:
    d = d or {}
    s = GraphSpec()
    flat = _flat_from_dict(GraphSpec, {k: v for k, v in d.items()
                                       if k in ("title", "show_title", "axis_width", "axis_color",
                                                "frame", "col_width_mm", "y_len_mm",
                                                "show_brackets", "p_format", "brackets_ns",
                                                "connect_rows", "connect_width", "connect_color",
                                                *_EXTRA)})
    for k in ("title", "show_title", "axis_width", "axis_color", "frame", "col_width_mm",
              "y_len_mm", "show_brackets", "p_format", "brackets_ns", "connect_rows",
              "connect_width", "connect_color", *_EXTRA):
        setattr(s, k, getattr(flat, k))
    if "default_style" in d:
        s.default_style = _flat_from_dict(DataSetStyle, d["default_style"])
    s.datasets = {int(k): _flat_from_dict(DataSetStyle, v) for k, v in (d.get("datasets") or {}).items()}
    s.hidden = {int(c) for c in d.get("hidden") or []}
    if "x" in d:
        s.x = _flat_from_dict(AxisSpec, {"ticks_dir": "none", **d["x"]})
    if "y" in d:
        s.y = _flat_from_dict(AxisSpec, d["y"])
    if "y2" in d:
        s.y2 = _flat_from_dict(AxisSpec, d["y2"])
    s.drawings = [dict(x) for x in d.get("drawings") or []]
    s.functions = [dict(x) for x in d.get("functions") or []]
    s.mv.update(d.get("mv") or {})
    s.parts.update(d.get("parts") or {})
    s.nested.update(d.get("nested") or {})
    fonts = _default_fonts()
    for k, v in (d.get("fonts") or {}).items():
        base = _flat_to_dict(fonts.get(k, FontSpec()))
        fonts[k] = _flat_from_dict(FontSpec, {**base, **v})
    s.fonts = fonts
    s.offsets = {k: (float(v[0]), float(v[1])) for k, v in (d.get("offsets") or {}).items()}
    sig = default_sig()
    if "sig" in d:
        sig.update(d["sig"] or {})
    else:                                    # files from before the significance options
        sig["label"] = "p" if s.p_format == "exact" else "stars"
        sig["which"] = "all" if s.brackets_ns else "significant"
    s.sig = sig
    return s
