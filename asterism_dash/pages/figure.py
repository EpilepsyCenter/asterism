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
                html.Label("Metric", className="field-label",
                           style={"marginTop": "10px"}),
                dcc.Dropdown(id="fig-metric",
                             options=[{"label": m, "value": m} for m in metrics],
                             value=(metrics[0] if metrics else None),
                             clearable=False, disabled=not metrics),
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
def on_render(n, kind, metric, title, ylabel, points, bracket_mode, sid, refresh):
    if not n:
        return no_update, no_update
    st = server_state.get_session(sid)
    if st.dataset is None:
        return alert("Import a dataset first.", "warning"), no_update
    ov = FigureOverrides(
        title=title or None,
        y_label=ylabel or None,
        show_points=("on" in (points or [])),
        bracket_label_mode=bracket_mode,
    )
    try:
        if kind == "bar":
            fig = bar_figure(st.dataset, st.stat, lab_style=_LAB, metric=metric,
                             overrides=ov)
        elif kind == "xy":
            fig = xy_figure(st.dataset, lab_style=_LAB, metric=metric, overrides=ov)
        elif kind == "freq_cumulative":
            fig = frequency_figure(st.dataset, lab_style=_LAB, metric=metric,
                                   kind="cumulative", overrides=ov)
        else:
            fig = frequency_figure(st.dataset, lab_style=_LAB, metric=metric,
                                   kind="histogram", overrides=ov)
    except Exception as e:
        return alert(f"Could not render: {e}", "danger"), (refresh or 0) + 1

    st.last_figure = fig
    st.figure_kind = kind
    src = mpl_png_src(fig, dpi=150)
    return html.Div([
        html.Img(src=src, style={"maxWidth": "100%", "border": "1px solid var(--ned-border)",
                                 "borderRadius": "6px", "background": "white"}),
        html.Div("Preview (PNG). Export produces vector SVG/PDF from this same figure.",
                 style={"fontSize": "0.75rem", "color": "var(--ned-text-muted)",
                        "marginTop": "6px"}),
    ]), (refresh or 0) + 1
