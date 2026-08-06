"""ASTERISM Dash application (SPEC §11–12).

Layout mirrors GliaAnalysis/NED-Net: a fixed sidebar (brand + file + status) and a top
tab bar over the content area, with a single `render_tab` callback dispatching to each
page's `layout(sid)`. The pipeline is import → analyse → figure → export.
"""

from __future__ import annotations

import os

import dash_bootstrap_components as dbc
from dash import ALL, Dash, Input, Output, State, callback, ctx, dcc, html

from asterism_dash import server_state
from asterism_dash.components import section_header, sidebar_divider
from asterism_dash.pages import (
    analyze as analyze_page,
    export as export_page,
    figure as figure_page,
    import_page,
)

app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
    assets_folder="assets",
    title="ASTERISM",
    update_title="ASTERISM | …",
)
server = app.server

TAB_DEFS = [
    ("import", "1 · Import"),
    ("analyze", "2 · Analyse"),
    ("figure", "3 · Figure"),
    ("export", "4 · Export"),
]

_PAGE_LAYOUTS = {
    "import": import_page.layout,
    "analyze": analyze_page.layout,
    "figure": figure_page.layout,
    "export": export_page.layout,
}


def _sidebar() -> html.Div:
    return html.Div(id="sidebar", children=[
        html.Div(id="sidebar-brand", children=[
            html.H4("ASTERISM"),
            html.Div("House-style figure engine", className="subtitle"),
        ]),
        html.Div(id="sidebar-content", children=[
            section_header("FILE"),
            html.Div(id="sidebar-file-info", children=[
                html.Div("No file loaded", className="file-info",
                         style={"opacity": "0.5"}),
            ]),
            sidebar_divider(),
            section_header("DATASET"),
            html.Div(id="sidebar-status", children=[
                html.Div("⚪ Nothing imported yet",
                         style={"fontSize": "0.82rem",
                                "color": "var(--ned-text-muted)"}),
            ]),
        ]),
        html.Div(id="sidebar-footer", children=[
            html.Div(className="theme-toggle-container", children=[
                dbc.Switch(id="theme-toggle", label="Dark mode", value=False,
                           style={"fontSize": "0.75rem"}),
            ]),
            html.Div([html.Span("ASTERISM v0.1")]),
        ]),
    ])


def _nav_items(active: str = "import") -> list:
    return [dbc.NavLink(label, id={"type": "tab", "id": tid},
                        active=(tid == active), n_clicks=0)
            for tid, label in TAB_DEFS]


def _tab_bar() -> html.Div:
    return html.Div(id="tab-bar", children=[
        dbc.Nav(id="tab-nav", children=_nav_items("import"),
                pills=False, className="nav-tabs",
                style={"display": "flex", "flexWrap": "nowrap"}),
    ])


app.layout = html.Div(id="app-container", children=[
    dcc.Store(id="session-id", storage_type="session"),
    dcc.Store(id="active-tab", data="import"),
    dcc.Store(id="tab-refresh", data=0),
    dcc.Store(id="theme-store", data="light"),
    _sidebar(),
    html.Div(id="main-content", children=[_tab_bar(), html.Div(id="tab-content")]),
])


@callback(Output("session-id", "data"), Input("session-id", "data"))
def init_session(sid):
    return sid or server_state.create_session()


app.clientside_callback(
    """function(isDark){var t=isDark?"dark":"light";
       document.documentElement.setAttribute("data-theme",t);return t;}""",
    Output("theme-store", "data"),
    Input("theme-toggle", "value"),
)


@callback(
    Output("active-tab", "data"),
    Output({"type": "tab", "id": ALL}, "active"),
    Input({"type": "tab", "id": ALL}, "n_clicks"),
    State("active-tab", "data"),
    State({"type": "tab", "id": ALL}, "id"),
    prevent_initial_call=True,
)
def switch_tab(n_clicks_list, current, ids):
    triggered = ctx.triggered_id
    ids = ids or []
    n_clicks_list = n_clicks_list or []
    new_active = current or "import"
    if isinstance(triggered, dict) and triggered.get("type") == "tab":
        for i, idict in enumerate(ids):
            if idict == triggered:
                if i < len(n_clicks_list) and n_clicks_list[i]:
                    new_active = triggered["id"]
                break
    return new_active, [idict.get("id") == new_active for idict in ids]


@callback(
    Output("tab-content", "children"),
    Input("active-tab", "data"),
    Input("tab-refresh", "data"),
    State("session-id", "data"),
)
def render_tab(active_tab, _refresh, sid):
    fn = _PAGE_LAYOUTS.get(active_tab)
    return fn(sid) if fn else html.Div("Unknown tab")


@callback(
    Output("sidebar-file-info", "children"),
    Output("sidebar-status", "children"),
    Input("tab-refresh", "data"),
    State("session-id", "data"),
)
def refresh_sidebar(_refresh, sid):
    st = server_state.get_session(sid)
    if st.file_path:
        file_info = html.Div([
            html.Div(os.path.basename(st.file_path), className="file-info",
                     style={"fontWeight": "600", "wordBreak": "break-all"}),
        ])
    else:
        file_info = html.Div("No file loaded", className="file-info",
                             style={"opacity": "0.5"})
    if st.dataset is not None:
        rep = st.dataset.n_report()
        parts = [f"{v} {k}" for k, v in rep.items() if k != "observations"]
        status = html.Div(f"🟢 {', '.join(parts) or 'loaded'}",
                          style={"fontSize": "0.82rem",
                                 "color": "var(--ned-success)"})
    else:
        status = html.Div("⚪ Nothing imported yet",
                          style={"fontSize": "0.82rem",
                                 "color": "var(--ned-text-muted)"})
    return file_info, status


if __name__ == "__main__":
    app.run(debug=False, port=8050)
