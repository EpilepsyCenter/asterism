"""ASTERISM's settings (Settings… window): defaults, typed reading and writing (QSettings via
documents). Each key has a default; a value that can't be read falls back to it."""

from __future__ import annotations

from . import documents

DEFAULTS: dict[str, object] = {
    # general
    "autosave.enabled": True,
    "autosave.minutes": 2,
    "export.dpi": 300,                 # PNG and TIFF export
    # new graphs
    "graph.font": "Arial",
    "graph.font_size": 12.0,
    "graph.axis_width": 1.0,
    "graph.frame": "plain",            # plain | offset | box
    "graph.height_mm": 50.0,
    "graph.col_width_mm": 16.0,
    "graph.scheme": "",                # "" = ASTERISM's palette (see graph/formatting.SCHEMES)
    "graph.sig_levels": "four",        # four | three | gp
    "graph.sig_label": "stars",        # stars | p | number | both
    "graph.sig_shape": "bracket",      # bracket | line
    # new analyses
    "analysis.ttest": "student",       # student | welch (unpaired t tests)
    "analysis.posthoc": "auto",        # one-way ANOVA: auto | tukey | sidak | bonferroni | holm_sidak
    "analysis.conf": 0.95,
    "analysis.alpha": 0.05,
    # import
    "import.qpcr_relative_to": "group",    # group | sample
    "import.titre_dilution": 1.0,
    "import.titre_volume_ul": 0.0,
    "import.titre_per": "reaction",        # reaction | ul | ml
    "import.titre_ss": False,
}


def get(key: str):
    default = DEFAULTS[key]
    v = documents.value(f"prefs/{key}", None)
    if v is None:
        return default
    try:
        if isinstance(default, bool):
            return v if isinstance(v, bool) else str(v).lower() in ("true", "1", "yes")
        if isinstance(default, int):
            return int(float(v))
        if isinstance(default, float):
            return float(v)
        return str(v)
    except (TypeError, ValueError):
        return default


def set(key: str, value) -> None:            # noqa: A001 (mirrors get)
    documents.set_value(f"prefs/{key}", value)


def reset() -> None:
    for k in DEFAULTS:
        documents.set_value(f"prefs/{k}", None)


# ---------------------------------------------------------------------------
# Applying them (only to new graphs and new analyses — never to saved ones)
# ---------------------------------------------------------------------------

CONF_KINDS = ("ttest", "anova1", "anova2", "linreg", "correlation", "contingency", "onesample", "nested")
ALPHA_KINDS = ("normality", "multiple_t")


def analysis_defaults(kind: str) -> dict:
    """Starting settings for a new analysis of this kind."""
    out: dict = {}
    if kind == "ttest":
        out["test"] = get("analysis.ttest")
    if kind == "anova1" and get("analysis.posthoc") != "auto":
        out["method"] = get("analysis.posthoc")
    if kind in CONF_KINDS:
        out["conf"] = get("analysis.conf")
    out["alpha"] = get("analysis.alpha")          # every analysis that reports significance
    return out


def style_new_graph(g) -> None:
    """Hook for Project.new_graph: fonts, axes, size, colours and significance style."""
    spec = g.spec
    base = float(get("graph.font_size"))
    for key, fs in spec.fonts.items():
        fs.family = get("graph.font")
        fs.size = base + (2 if key == "title" else -1 if key == "legend" else 0)
    spec.axis_width = float(get("graph.axis_width"))
    spec.frame = get("graph.frame")
    spec.y_len_mm = float(get("graph.height_mm"))
    if g.table.table_type in ("column", "nested"):
        spec.col_width_mm = float(get("graph.col_width_mm")) * (1.5 if g.table.table_type == "nested" else 1.0)
    spec.sig.update(levels=get("graph.sig_levels"), label=get("graph.sig_label"), shape=get("graph.sig_shape"))
    scheme = get("graph.scheme")
    if scheme:
        from .graph.formatting import SCHEMES, apply_scheme
        if scheme in SCHEMES:
            cols = g.table.used_columns() or list(range(g.table.ncols))
            g.spec = apply_scheme(spec, scheme, cols)
