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
    symbol_shape: str = "circle"     # circle | square | triangle | diamond | open_circle | open_square
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
    # XY graphs
    xy_show: str = "mean"            # mean (± error from line_at) | replicates | spaghetti
    connect: bool = False            # line joining the points (or means) in X order
    line_width: float = 1.0          # connecting line and fitted curve
    line_dash: str = "solid"         # solid | dash | dot
    fill: bool = False               # shade the area under the line
    fill_alpha: float = 0.25


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
    fmt: str = "decimal"             # decimal | scientific
    decimals: int = -1               # -1 = auto
    prefix: str = ""
    suffix: str = ""
    label_rotation: int = 0          # X axis only: 0 | 45 | 90


def _default_fonts() -> dict[str, FontSpec]:
    return {
        "title": FontSpec(size=14, bold=True),
        "y_title": FontSpec(size=12, bold=True),
        "y_numbers": FontSpec(size=12),
        "x_labels": FontSpec(size=12, bold=True),
        "bracket": FontSpec(size=12),
        "legend": FontSpec(size=11),
    }


# Colours for data sets of grouped graphs: (fill, ink) pairs, readable in greyscale order
# and by colour-blind readers (fills light, inks dark).
PALETTE = [("#bdbdbd", "#000000"), ("#6baed6", "#08519c"), ("#fd8d3c", "#a63603"),
           ("#74c476", "#006d2c"), ("#9e9ac8", "#54278f"), ("#f781bf", "#8e0152"),
           ("#fee391", "#8c6d00"), ("#a6a6a6", "#3a3a3a")]
# Subject colours on nested graphs (dark enough for small symbols on white).
SUBJECT_COLORS = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e", "#17becf",
                  "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22"]
GROUPED_LAYOUTS = ("interleaved", "separated", "stacked", "stacked_pct", "lines", "heatmap")
NESTED_LAYOUTS = ("subjects", "pooled", "superplot")


@dataclass
class GraphSpec:
    title: str = ""
    show_title: bool = True
    default_style: DataSetStyle = field(default_factory=DataSetStyle)
    datasets: dict[int, DataSetStyle] = field(default_factory=dict)
    hidden: set[int] = field(default_factory=set)
    x: AxisSpec = field(default_factory=lambda: AxisSpec(ticks_dir="none"))
    y: AxisSpec = field(default_factory=AxisSpec)
    axis_width: float = 1.0
    axis_color: str = "#000000"
    frame: str = "plain"             # plain | offset | box
    col_width_mm: float = 16.0
    y_len_mm: float = 50.0
    fonts: dict[str, FontSpec] = field(default_factory=_default_fonts)
    show_brackets: bool = True
    p_format: str = "stars"          # stars | exact
    brackets_ns: bool = False        # multiple comparisons: also draw non-significant ones
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
    }


_EXTRA = ("palette", "grouped_layout", "nested_layout", "show_legend", "heat_low", "heat_high", "x_len_mm")


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
    fonts = _default_fonts()
    for k, v in (d.get("fonts") or {}).items():
        base = _flat_to_dict(fonts.get(k, FontSpec()))
        fonts[k] = _flat_from_dict(FontSpec, {**base, **v})
    s.fonts = fonts
    s.offsets = {k: (float(v[0]), float(v[1])) for k, v in (d.get("offsets") or {}).items()}
    return s
