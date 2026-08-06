"""Shared Dash components + OS-native pickers (copied from GliaAnalysis, SPEC §12).

The native folder/file pickers are ported verbatim (AppleScript on macOS, tkinter
fallback elsewhere). The only ASTERISM-specific addition is `mpl_png_src`, which turns
the SAME matplotlib figure used for file export into a base64 PNG for on-screen preview
— so the preview can never disagree with the exported file (SPEC §11: never two
rendering paths).
"""

from __future__ import annotations

import base64
import platform
import subprocess
import sys

from dash import dcc, html


# ── Native OS file / folder pickers ───────────────────────────────────

def browse_folder(title: str = "Select folder") -> str | None:
    if platform.system() == "Darwin":
        try:
            r = subprocess.run(
                ["osascript", "-e",
                 f'POSIX path of (choose folder with prompt "{title}")'],
                capture_output=True, text=True, timeout=120,
            )
            folder = r.stdout.strip().rstrip("/")
            return folder if folder else None
        except Exception:
            pass
    try:
        r = subprocess.run(
            [sys.executable, "-c", "\n".join([
                "import tkinter as tk",
                "from tkinter import filedialog",
                "root = tk.Tk(); root.withdraw()",
                "root.attributes('-topmost', True); root.update()",
                f'folder = filedialog.askdirectory(title="{title}")',
                "root.destroy(); print(folder or '')",
            ])],
            capture_output=True, text=True, timeout=120,
        )
        folder = r.stdout.strip()
        return folder if folder else None
    except Exception:
        return None


def browse_file(
    title: str = "Select file",
    filetypes: list[tuple[str, str]] | None = None,
) -> str | None:
    filetypes = filetypes or [("Data files", "*.xlsx *.xls *.csv"), ("All files", "*")]
    if platform.system() == "Darwin":
        try:
            exts = []
            for _, pattern in filetypes:
                for tok in pattern.split():
                    ext = tok.replace("*.", "").strip()
                    if ext and ext != "*":
                        exts.append(f'"{ext}"')
            type_clause = f" of type {{{', '.join(exts)}}}" if exts else ""
            script = (f'POSIX path of (choose file with prompt "{title}"{type_clause})')
            r = subprocess.run(["osascript", "-e", script],
                               capture_output=True, text=True, timeout=120)
            path = r.stdout.strip()
            return path if path else None
        except Exception:
            pass
    try:
        ft_lines = ",\n        ".join(f'("{label}", "{pat}")' for label, pat in filetypes)
        r = subprocess.run(
            [sys.executable, "-c", "\n".join([
                "import tkinter as tk",
                "from tkinter import filedialog",
                "root = tk.Tk(); root.withdraw()",
                "root.attributes('-topmost', True); root.update()",
                "path = filedialog.askopenfilename(",
                f'    title="{title}", filetypes=[{ft_lines}])',
                "root.destroy(); print(path)",
            ])],
            capture_output=True, text=True, timeout=120,
        )
        path = r.stdout.strip()
        return path if path else None
    except Exception:
        return None


# ── Layout helpers ────────────────────────────────────────────────────

def section_header(title: str) -> html.Div:
    return html.Div(className="sidebar-section",
                    children=[html.Div(title, className="sidebar-section-label")])


def sidebar_divider() -> html.Hr:
    return html.Hr(className="sidebar-divider")


def metric_card(label: str, value: str, accent: bool = False) -> html.Div:
    cls = "metric-value accent" if accent else "metric-value"
    return html.Div(className="metric-card",
                    children=[html.Div(label, className="metric-label"),
                              html.Div(value, className=cls)])


def empty_state(icon: str, title: str, text: str) -> html.Div:
    return html.Div(className="empty-state", children=[
        html.Div(icon, className="empty-icon"),
        html.Div(title, className="empty-title"),
        html.Div(text, className="empty-text"),
    ])


def alert(message: str, variant: str = "info") -> html.Div:
    cls = f"ned-alert {variant}" if variant != "info" else "ned-alert"
    return html.Div(message, className=cls)


# ── matplotlib preview (SAME figure as export) ────────────────────────

def mpl_png_src(fig, *, dpi: int = 150) -> str:
    """A base64 data-URI PNG of a matplotlib figure, for on-screen preview.

    Rendered from the same Figure object the file export uses — the preview is a
    lower-DPI raster of the exact vector that will be exported, so it cannot drift
    from the file (SPEC §11).
    """
    from asterism.core.export import render_to_bytes
    png = render_to_bytes(fig, "png", dpi=dpi)
    b64 = base64.b64encode(png).decode("ascii")
    return f"data:image/png;base64,{b64}"
