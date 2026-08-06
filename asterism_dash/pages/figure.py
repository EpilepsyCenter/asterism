"""Figure tab (SPEC §9): choose a figure type + per-figure overrides and preview the
house-styled figure. The preview is a PNG of the exact figure that will be exported."""

from __future__ import annotations

from dash import Input, Output, State, callback, dcc, html, no_update

from asterism.core.build import (FigureOverrides, bar_figure, frequency_figure,
                                 xy_figure)
from asterism.core.style import LabStyle
from asterism_dash import server_state
from asterism_dash.components import alert, empty_state, mpl_png_src

_LAB = LabStyle.load()


def _metrics(ds):
    if ds is not None and "metric" in ds.frame.columns:
        return sorted(ds.frame["metric"].dropna().unique().tolist())
    return []


def layout(sid: str):
    st = server_state.get_session(sid)
    if st.dataset is None:
        return html.Div(className="page", children=[
            empty_state("📊", "No dataset yet", "Import a file first."),
        ])
    metrics = _metrics(st.dataset)
    has_x = st.dataset.x is not None
    kinds = [{"label": "Bar (column / grouped)", "value": "bar"},
             {"label": "Frequency — cumulative", "value": "freq_cumulative"},
             {"label": "Frequency — histogram", "value": "freq_histogram"}]
    if has_x:
        kinds.insert(1, {"label": "XY (mean ± SEM)", "value": "xy"})
    return html.Div(className="page", children=[
        html.H3("Figure"),
        html.Div(style={"display": "flex", "gap": "24px", "flexWrap": "wrap"}, children=[
            html.Div(style={"minWidth": "260px"}, children=[
                html.Label("Figure type", className="field-label"),
                dcc.Dropdown(id="fig-kind", options=kinds, value="bar",
                             clearable=False),
                html.Label("Metric(s)", className="field-label",
                           style={"marginTop": "10px"}),
                dcc.Dropdown(id="fig-metric",
                             options=[{"label": m, "value": m} for m in metrics],
                             value=(metrics if metrics else None),
                             multi=True, disabled=not metrics),
                html.Div("Pick several to render one panel per metric (a figure set, "
                         "like a TRACER cohort).",
                         style={"fontSize": "0.72rem", "color": "var(--ned-text-muted)",
                                "marginTop": "3px"}),
                html.Label("Title", className="field-label", style={"marginTop": "10px"}),
                dcc.Input(id="fig-title", type="text", value="",
                          style={"width": "100%"}),
                html.Label("Y-axis label", className="field-label",
                           style={"marginTop": "10px"}),
                dcc.Input(id="fig-ylabel", type="text", value="",
                          style={"width": "100%"}),
                dcc.Checklist(id="fig-points",
                              options=[{"label": " Show points", "value": "on"}],
                              value=["on"], style={"marginTop": "10px"}),
                dcc.RadioItems(id="fig-bracket-mode",
                               options=[{"label": " Stars", "value": "stars"},
                                        {"label": " p-value", "value": "p_value"}],
                               value="stars", style={"marginTop": "6px"}),
                html.Button("Render", id="fig-render", className="btn-ned-primary",
                            style={"marginTop": "14px"}),
                html.Div("Brackets use the post-hoc p-values from the Analyse tab.",
                         style={"fontSize": "0.75rem", "color": "var(--ned-text-muted)",
                                "marginTop": "8px"}),
            ]),
            html.Div(id="fig-preview", style={"flex": "1", "minWidth": "360px"},
                     children=[empty_state("🖼", "No figure yet",
                                           "Set options and press Render.")]),
        ]),
    ])


def _one_figure(st, kind, metric, ov):
    """Render a single figure of `kind` for `metric`, using that metric's stats."""
    from asterism.core.stats import run_analysis
    if kind == "bar":
        stat = st.analyses.get(metric or "value")
        if stat is None:
            stat = run_analysis(st.dataset, st.design, metric=metric)
            st.analyses[metric or "value"] = stat
        return bar_figure(st.dataset, stat, lab_style=_LAB, metric=metric, overrides=ov)
    if kind == "xy":
        return xy_figure(st.dataset, lab_style=_LAB, metric=metric, overrides=ov)
    return frequency_figure(st.dataset, lab_style=_LAB, metric=metric,
                            kind=("cumulative" if kind == "freq_cumulative" else "histogram"),
                            overrides=ov)


@callback(
    Output("fig-preview", "children"),
    Output("tab-refresh", "data", allow_duplicate=True),
    Input("fig-render", "n_clicks"),
    State("fig-kind", "value"),
    State("fig-metric", "value"),
    State("fig-title", "value"),
    State("fig-ylabel", "value"),
    State("fig-points", "value"),
    State("fig-bracket-mode", "value"),
    State("session-id", "data"),
    State("tab-refresh", "data"),
    prevent_initial_call=True,
)
def on_render(n, kind, metrics, title, ylabel, points, bracket_mode, sid, refresh):
    if not n:
        return no_update, no_update
    st = server_state.get_session(sid)
    if st.dataset is None:
        return alert("Import a dataset first.", "warning"), no_update
    metrics = metrics if isinstance(metrics, list) else ([metrics] if metrics else [None])
    if not metrics:
        metrics = [None]
    multi = len([m for m in metrics if m is not None]) > 1

    st.figures = {}
    tiles = []
    try:
        for m in metrics:
            # In multi mode each panel is titled/labelled by its metric; a single
            # per-figure title/ylabel would be wrong across different metrics.
            ov = FigureOverrides(
                title=(m if multi else (title or None)),
                y_label=(m if multi else (ylabel or None)),
                show_points=("on" in (points or [])),
                bracket_label_mode=bracket_mode,
            )
            fig = _one_figure(st, kind, m, ov)
            st.figures[m or "value"] = fig
            src = mpl_png_src(fig, dpi=300)
            tiles.append(html.Div(style={"textAlign": "center"}, children=[
                html.Img(src=src, style={"width": "360px" if multi else "520px",
                                         "maxWidth": "100%",
                                         "border": "1px solid var(--ned-border)",
                                         "borderRadius": "6px", "background": "white",
                                         "padding": "8px"}),
            ]))
    except Exception as e:
        return alert(f"Could not render: {e}", "danger"), (refresh or 0) + 1

    st.figure_kind = kind
    st.last_figure = next(iter(st.figures.values()))
    st.metric = (metrics[0] or "value")

    # Build the multi-panel figure set for export (bar panels only, §10b-pre).
    st.figure_set = None
    if multi and kind == "bar":
        st.figure_set = _build_figure_set(st, [m for m in metrics if m])

    note = ("Figure set — one panel per metric, each with its own stats. "
            "Export as a single multi-panel file on the Export tab."
            if multi else
            "Preview (PNG, upscaled). Export produces vector SVG/PDF from this same "
            "figure at its exact mm size.")
    return html.Div([
        html.Div(tiles, style={"display": "flex", "flexWrap": "wrap", "gap": "14px"}),
        html.Div(note, style={"fontSize": "0.75rem", "color": "var(--ned-text-muted)",
                              "marginTop": "8px"}),
    ]), (refresh or 0) + 1


def _build_figure_set(st, metrics):
    """A Panel per metric (bars + that metric's brackets) → one mm-exact figure set."""
    from asterism.core.build import comparisons_from_stat, dataset_to_bargroups
    from asterism.core.figure_set import Panel, figure_set
    from asterism.core.stats import run_analysis
    fig_cfg = _LAB["figure"]
    panels = []
    for i, m in enumerate(metrics):
        stat = st.analyses.get(m) or run_analysis(st.dataset, st.design, metric=m)
        st.analyses[m] = stat
        groups = dataset_to_bargroups(st.dataset, metric=m)
        comps = comparisons_from_stat(stat, groups)
        panels.append(Panel(groups, width_mm=fig_cfg["width_mm"],
                            height_mm=fig_cfg["height_mm"], comparisons=comps,
                            y_label=m, title=m, rng_seed=i))
    return figure_set(panels, lab_style=_LAB)
