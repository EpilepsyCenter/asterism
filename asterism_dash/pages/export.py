"""Export tab (SPEC §10): emit the figure (SVG/PDF/PNG), the underlying numbers (CSV),
the results string, and the info block together. Plus the macOS 'Copy figure' path."""

from __future__ import annotations

import json
import platform
from pathlib import Path

from dash import Input, Output, State, callback, dcc, html, no_update

from asterism.core.export import export_all
from asterism_dash import server_state
from asterism_dash.components import alert, browse_folder, empty_state


def layout(sid: str):
    st = server_state.get_session(sid)
    if st.last_figure is None:
        return html.Div(className="page", children=[
            empty_state("📤", "Nothing to export", "Render a figure on the Figure tab first."),
        ])
    is_mac = platform.system() == "Darwin"
    return html.Div(className="page", children=[
        html.H3("Export"),
        html.P("Figure (SVG + PDF + PNG), the underlying numbers (CSV), the results "
               "string, and the info block are written together (SPEC §10).",
               className="page-subtitle"),
        html.Div(style={"display": "flex", "gap": "10px", "alignItems": "flex-end",
                        "flexWrap": "wrap"}, children=[
            html.Div([
                html.Label("File name (no extension)", className="field-label"),
                dcc.Input(id="exp-name", type="text", value="figure_1",
                          style={"width": "240px"}),
            ]),
            html.Button("Choose folder & export…", id="exp-go",
                        className="btn-ned-primary"),
            html.Button("Copy figure (vector PDF)", id="exp-copy",
                        className="btn-ned-secondary",
                        disabled=not is_mac,
                        title=("" if is_mac else "macOS only — use file export elsewhere")),
        ]),
        html.Div(id="exp-result", style={"marginTop": "16px"}),
    ])


@callback(
    Output("exp-result", "children"),
    Input("exp-go", "n_clicks"),
    State("exp-name", "value"),
    State("session-id", "data"),
    prevent_initial_call=True,
)
def on_export(n, name, sid):
    if not n:
        return no_update
    st = server_state.get_session(sid)
    if st.last_figure is None:
        return alert("Render a figure first.", "warning")
    folder = browse_folder("Choose export folder")
    if not folder:
        return no_update
    stem = Path(folder) / (name or "figure_1")
    written = []
    try:
        figures = st.figures or {st.metric: st.last_figure}
        multi = len(figures) > 1
        # 1) each figure as its own vector trio; single figure keeps the plain name
        for metric, fig in figures.items():
            fstem = stem.parent / (f"{stem.name}_{metric}" if multi else stem.name)
            written.extend(export_all(fig, fstem, dpi=150).values())
        # 2) the multi-panel figure set as ONE file (SPEC §10b-pre)
        if st.figure_set is not None:
            written.extend(export_all(st.figure_set, stem.parent / f"{stem.name}_set",
                                      dpi=150).values())
        # 3) numbers (CSV) — the full canonical frame, once
        if st.dataset is not None:
            csv_path = stem.with_suffix(".csv")
            st.dataset.frame.to_csv(csv_path, index=False)
            written.append(csv_path)
        # 4) results string + info block per metric present in the figures
        for metric in figures:
            stat = st.analyses.get(metric)
            if stat is None:
                continue
            tag = f"_{metric}" if multi else ""
            (stem.parent / f"{stem.name}{tag}_results.txt").write_text(
                stat.results_string() + "\n")
            written.append(stem.parent / f"{stem.name}{tag}_results.txt")
            info = stat.info_block()
            info["source_file"] = st.file_path
            (stem.parent / f"{stem.name}{tag}_info.json").write_text(
                json.dumps(info, indent=2, default=str))
            written.append(stem.parent / f"{stem.name}{tag}_info.json")
    except Exception as e:
        return alert(f"Export failed: {e}", "danger")

    items = [html.Li(str(p)) for p in written]
    extras = []
    stat = st.analyses.get(st.metric)
    if stat is not None:
        extras.append(html.Div(className="card", style={"marginTop": "10px"}, children=[
            html.Div("Results string", className="metric-label"),
            html.Div(stat.results_string(), className="results-string"),
        ]))
    return html.Div([
        alert(f"Exported {len(written)} files to {folder}", "success"),
        html.Ul(items, style={"fontSize": "0.8rem", "wordBreak": "break-all"}),
        *extras,
    ])


@callback(
    Output("exp-result", "children", allow_duplicate=True),
    Input("exp-copy", "n_clicks"),
    State("session-id", "data"),
    prevent_initial_call=True,
)
def on_copy(n, sid):
    if not n:
        return no_update
    st = server_state.get_session(sid)
    fig = st.figure_set if st.figure_set is not None else st.last_figure
    if fig is None:
        return alert("Render a figure first.", "warning")
    try:
        from asterism.core.clipboard import (copy_figure_to_pasteboard,
                                             pasteboard_flavours)
        copy_figure_to_pasteboard(fig)
        flavours = pasteboard_flavours()
        return alert(f"Vector PDF copied to the clipboard (flavours: {flavours}). "
                     f"Paste into Affinity.", "success")
    except Exception as e:
        return alert(f"Copy failed: {e}", "danger")
