"""Import tab (SPEC §5–6): browse a file, classify its sheets, show the column
inventory with overridable role guesses, and build the canonical Dataset."""

from __future__ import annotations

import pandas as pd
from dash import ALL, Input, Output, State, callback, ctx, dcc, html, no_update

from asterism.core.contract import Dataset
from asterism.core.design import detect_design
from asterism.core.importer import sources
from asterism.core.importer.inventory import inventory
from asterism.core.importer.reshape import apply_roles
from asterism.core.importer.roles import Role
from asterism.core.validation import Severity, validate
from asterism_dash import server_state
from asterism_dash.components import alert, browse_file, empty_state

_ROLE_OPTIONS = [{"label": r.value, "value": r.value} for r in Role]


def layout(sid: str):
    st = server_state.get_session(sid)
    return html.Div(className="page", children=[
        html.H3("Import"),
        html.P("Load a TRACER cohort export, a NED-Net results file, or a manual "
               "template. Every guess below is overridable before it affects an "
               "analysis.", className="page-subtitle"),
        html.Button("Browse file…", id="imp-browse", className="btn-ned-primary"),
        html.Div(id="imp-file", style={"marginTop": "10px"},
                 children=(_file_line(st.file_path) if st.file_path else None)),
        html.Div(id="imp-sheet-row", style={"marginTop": "14px"}, children=[
            html.Label("Sheet", className="field-label"),
            dcc.Dropdown(id="imp-sheet", options=_sheet_options(st),
                         value=st.selected_sheet or None, clearable=False,
                         style={"maxWidth": "480px"}),
        ]),
        html.Div(id="imp-inventory", style={"marginTop": "14px"}),
        html.Button("Build dataset", id="imp-build", className="btn-ned-primary",
                    style={"marginTop": "12px"}),
        html.Div(id="imp-result", style={"marginTop": "14px"}),
    ])


def _file_line(path: str):
    return html.Div(path, className="file-info", style={"wordBreak": "break-all"})


def _sheet_options(st) -> list:
    kinds = {p.sheet: f"{p.source}/{p.kind}" for p in st.sheet_plans}
    return [{"label": f"{name}  ({kinds[name]})" if name in kinds else name,
             "value": name} for name in st.sheets.keys()]


def _load_any(path: str) -> dict:
    if path.lower().endswith(".csv"):
        df = pd.read_csv(path)
        rows = [list(df.columns)] + df.astype(object).values.tolist()
        return {"data": rows}
    return sources.load_sheets_raw(path)


@callback(
    Output("imp-file", "children"),
    Output("imp-sheet", "options"),
    Output("imp-sheet", "value"),
    Output("tab-refresh", "data", allow_duplicate=True),
    Input("imp-browse", "n_clicks"),
    State("session-id", "data"),
    State("tab-refresh", "data"),
    prevent_initial_call=True,
)
def on_browse(n, sid, refresh):
    if not n:
        return no_update, no_update, no_update, no_update
    path = browse_file("Select a data file")
    if not path:
        return no_update, no_update, no_update, no_update
    st = server_state.get_session(sid)
    st.file_path = path
    try:
        st.sheets = _load_any(path)
    except Exception as e:
        return alert(f"Could not read file: {e}", "danger"), [], None, (refresh or 0) + 1
    st.sheet_plans = sources.classify_sheets(st.sheets)
    opts = _sheet_options(st)
    # default to the first classified sheet, else the first sheet
    default = (st.sheet_plans[0].sheet if st.sheet_plans
               else (next(iter(st.sheets), None)))
    st.selected_sheet = default or ""
    return _file_line(path), opts, default, (refresh or 0) + 1


@callback(
    Output("imp-inventory", "children"),
    Input("imp-sheet", "value"),
    State("session-id", "data"),
    prevent_initial_call=True,
)
def on_select_sheet(sheet, sid):
    if not sheet:
        return None
    st = server_state.get_session(sid)
    st.selected_sheet = sheet
    plan = next((p for p in st.sheet_plans if p.sheet == sheet), None)
    if plan and plan.kind in ("two_row", "isi_dist", "isi_cdf"):
        return alert(f"Structured sheet ({plan.source}/{plan.kind}) — will be parsed "
                     f"by its source recipe on build.", "info")

    rows = st.sheets[sheet]
    df = pd.DataFrame(rows[1:], columns=[str(c) for c in rows[0]])
    info = inventory(df)
    header = html.Tr([html.Th(h) for h in
                      ["column", "dtype", "unique", "samples", "role"]])
    body = []
    for c in info:
        body.append(html.Tr([
            html.Td(c.name),
            html.Td(c.dtype),
            html.Td(str(c.n_unique)),
            html.Td(", ".join(str(s) for s in c.samples[:3]),
                    style={"fontSize": "0.75rem", "color": "var(--ned-text-muted)"}),
            html.Td(dcc.Dropdown(
                id={"type": "role-dd", "col": c.name},
                options=_ROLE_OPTIONS, value=c.guess.role.value,
                clearable=False, style={"minWidth": "150px"})),
        ]))
    hint = (f"Detected: {plan.source}/{plan.kind}. " if plan else "")
    return html.Div([
        alert(hint + "Guessed roles are pre-filled — override any before building.",
              "info"),
        html.Table([html.Thead(header), html.Tbody(body)], className="inv-table"),
    ])


@callback(
    Output("imp-result", "children"),
    Output("tab-refresh", "data", allow_duplicate=True),
    Input("imp-build", "n_clicks"),
    State("imp-sheet", "value"),
    State({"type": "role-dd", "col": ALL}, "value"),
    State({"type": "role-dd", "col": ALL}, "id"),
    State("session-id", "data"),
    State("tab-refresh", "data"),
    prevent_initial_call=True,
)
def on_build(n, sheet, role_values, role_ids, sid, refresh):
    if not n or not sheet:
        return no_update, no_update
    st = server_state.get_session(sid)
    rows = st.sheets.get(sheet)
    plan = next((p for p in st.sheet_plans if p.sheet == sheet), None)
    notes: list[str] = []
    try:
        if plan and plan.source == "tracer" and plan.kind == "cells_long":
            ds = sources.import_tracer_cells_long(rows)
        elif plan and plan.source == "tracer" and plan.kind == "events":
            ds = sources.import_tracer_events(rows, metric=plan.metric)
        elif plan and plan.source == "nednet" and plan.kind == "per_animal":
            res = sources.import_nednet_per_animal(rows)
            ds, notes = res.dataset, list(res.notes)
        elif plan and plan.source == "nednet" and plan.kind == "two_row":
            ds = sources.import_nednet_two_row(rows, metric=plan.metric)
        else:
            # generic: apply the (possibly overridden) role mapping
            mapping = {rid["col"]: Role(val)
                       for rid, val in zip(role_ids, role_values)}
            df = pd.DataFrame(rows[1:], columns=[str(c) for c in rows[0]])
            ds = apply_roles(df, mapping)
    except Exception as e:
        return alert(f"Build failed: {e}", "danger"), (refresh or 0) + 1

    st.dataset = ds
    st.factors = list(ds.factors)
    st.import_notes = notes
    st.design = detect_design(ds)
    issues = validate(ds, design=st.design)

    rep = ds.n_report()
    children = [
        alert("Dataset built. " + ", ".join(f"{v} {k}" for k, v in rep.items()),
              "success"),
    ]
    for nt in notes:
        children.append(alert(nt, "warning"))
    if issues:
        children.append(html.Div(_issues_block(issues), style={"marginTop": "8px"}))
    children.append(html.Div(f"Detected design: {st.design.design} → "
                             f"{st.design.recommended_test.name if st.design.recommended_test else 'n/a'}. "
                             f"Continue on the Analyse tab.",
                             style={"marginTop": "8px", "fontWeight": "600"}))
    return html.Div(children), (refresh or 0) + 1


def _issues_block(issues):
    variant = {Severity.ERROR: "danger", Severity.WARNING: "warning",
               Severity.INFO: "info"}
    return [alert(f"[{i.severity.value}] {i.message}", variant[i.severity])
            for i in issues]
