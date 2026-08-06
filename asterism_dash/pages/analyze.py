"""Analyse tab (SPEC §8, §10): show the inferred design and chosen test, let the user
override parametric/non-parametric, run the test, and display the results string."""

from __future__ import annotations

from dash import Input, Output, State, callback, dcc, html, no_update

from asterism.core.stats import run_analysis
from asterism_dash import server_state
from asterism_dash.components import alert, empty_state, metric_card


def _metrics(ds) -> list[str]:
    if ds is not None and "metric" in ds.frame.columns:
        return sorted(ds.frame["metric"].dropna().unique().tolist())
    return []


def layout(sid: str):
    st = server_state.get_session(sid)
    if st.dataset is None:
        return html.Div(className="page", children=[
            empty_state("📥", "No dataset yet", "Import a file on the Import tab first."),
        ])
    d = st.design
    metrics = _metrics(st.dataset)
    test_name = d.recommended_test.name if d and d.recommended_test else "n/a"
    return html.Div(className="page", children=[
        html.H3("Analyse"),
        html.Div(className="card", children=[
            html.Div("Inferred design", className="metric-label"),
            html.Div(d.design if d else "—", className="metric-value accent"),
            html.Div(d.rationale if d else "", style={"marginTop": "6px",
                     "color": "var(--ned-text-muted)", "fontSize": "0.85rem"}),
            html.Div(f"Recommended test: {test_name}", style={"marginTop": "8px",
                     "fontWeight": "600"}),
        ]),
        html.Div(style={"display": "flex", "gap": "18px", "marginTop": "14px",
                        "flexWrap": "wrap"}, children=[
            html.Div([
                html.Label("Metric", className="field-label"),
                dcc.Dropdown(id="an-metric",
                             options=[{"label": m, "value": m} for m in metrics],
                             value=(metrics[0] if metrics else None),
                             clearable=False, style={"minWidth": "220px"},
                             disabled=not metrics),
            ]),
            html.Div([
                html.Label("Test", className="field-label"),
                dcc.RadioItems(id="an-parametric",
                               options=[{"label": " Recommended", "value": "auto"},
                                        {"label": " Force parametric", "value": "parametric"},
                                        {"label": " Force non-parametric", "value": "nonparametric"}],
                               value="auto"),
            ]),
        ]),
        html.Button("Run test", id="an-run", className="btn-ned-primary",
                    style={"marginTop": "12px"}),
        html.Div(id="an-result", style={"marginTop": "16px"}),
    ])


@callback(
    Output("an-result", "children"),
    Output("tab-refresh", "data", allow_duplicate=True),
    Input("an-run", "n_clicks"),
    State("an-metric", "value"),
    State("an-parametric", "value"),
    State("session-id", "data"),
    State("tab-refresh", "data"),
    prevent_initial_call=True,
)
def on_run(n, metric, parametric_mode, sid, refresh):
    if not n:
        return no_update, no_update
    st = server_state.get_session(sid)
    if st.dataset is None:
        return alert("Import a dataset first.", "warning"), no_update
    parametric = {"auto": None, "parametric": True, "nonparametric": False}[parametric_mode]
    stat = run_analysis(st.dataset, st.design, metric=metric, parametric=parametric)
    st.metric = metric or ""
    # Store keyed by metric so each figure can find its own test (not just the last run).
    st.analyses[metric or "value"] = stat

    if stat.error:
        return alert(f"Test could not run: {stat.error}", "danger"), (refresh or 0) + 1

    cards = [metric_card("n by level", ", ".join(f"{k}={v}" for k, v in stat.n_by_level.items()) or "—"),
             metric_card("unit of analysis", stat.unit_of_analysis)]
    posthoc = None
    if stat.posthoc:
        rows = [html.Tr([html.Td(p["a"]), html.Td("vs"), html.Td(p["b"]),
                         html.Td(f"p = {p['p']:.4g}"), html.Td(p.get("stars", ""))])
                for p in stat.posthoc]
        posthoc = html.Div([html.Div("Post-hoc comparisons", className="metric-label",
                                     style={"marginTop": "10px"}),
                            html.Table(html.Tbody(rows), className="inv-table")])
    notes = [alert(n, "info") for n in stat.notes]
    return html.Div([
        html.Div(className="card", children=[
            html.Div("Result", className="metric-label"),
            html.Div(stat.results_string(), className="results-string"),
        ]),
        html.Div(cards, style={"display": "flex", "gap": "12px", "marginTop": "12px"}),
        posthoc or html.Div(),
        html.Div(notes, style={"marginTop": "10px"}),
    ]), (refresh or 0) + 1
