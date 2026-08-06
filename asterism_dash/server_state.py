"""Server-side session state (copied idiom from GliaAnalysis, SPEC §12).

Per-session state keyed by a UUID that lives in a client-side dcc.Store; the actual
objects (the long-format frame, the Dataset, the last figure) live here so we never
serialise a dataframe or a matplotlib figure through a Dash callback.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SessionState:
    """All mutable state for one browser session."""

    # Import
    file_path: str = ""
    sheets: dict = field(default_factory=dict)          # {sheet_name: raw rows}
    sheet_plans: list = field(default_factory=list)     # classify_sheets() output
    selected_sheet: str = ""
    role_overrides: dict = field(default_factory=dict)  # {column: Role.value}

    # The canonical dataset (asterism.core.contract.Dataset)
    dataset: Any = None
    factors: list = field(default_factory=list)
    import_notes: list = field(default_factory=list)    # e.g. excluded-animal reports

    # Analysis. `design` is dataset-level (same for every metric — it keys off the
    # factor/subject structure, not the values). `analyses` holds one StatResult PER
    # metric, so a figure's brackets always come from THAT metric's test, never from
    # whichever analysis happened to run last.
    metric: str = ""
    design: Any = None                                  # DesignResult
    analyses: dict = field(default_factory=dict)        # {metric: StatResult}

    # Figure
    figure_kind: str = "bar"                            # bar | xy | frequency
    overrides: dict = field(default_factory=dict)       # FigureOverrides fields
    last_figure: Any = None                             # matplotlib Figure (single)
    figures: dict = field(default_factory=dict)         # {metric: Figure} for multi

    # Export
    output_dir: str = ""

    extra: dict = field(default_factory=dict)


_sessions: dict[str, SessionState] = {}


def create_session() -> str:
    sid = str(uuid.uuid4())
    _sessions[sid] = SessionState()
    return sid


def get_session(session_id: str | None) -> SessionState:
    """Return the SessionState for `session_id`, creating it under that same id if
    missing (survives a debug-reload that wiped `_sessions` while the client still
    holds the old sid) — same rationale as the Glia original."""
    if session_id is None:
        session_id = str(uuid.uuid4())
    if session_id not in _sessions:
        _sessions[session_id] = SessionState()
    return _sessions[session_id]


def get(session_id: str | None, key: str, default: Any = None) -> Any:
    state = get_session(session_id)
    if hasattr(state, key):
        return getattr(state, key)
    return state.extra.get(key, default)


def put(session_id: str | None, key: str, value: Any) -> None:
    state = get_session(session_id)
    if hasattr(state, key):
        setattr(state, key, value)
    else:
        state.extra[key] = value
