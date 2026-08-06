"""File export (SPEC §10).

SVG + PDF carry live text (vector); PNG is the raster convenience copy at the
configured DPI. The one rule that matters: **never pass `bbox_inches='tight'`**.
It silently resizes the canvas, which destroys the mm-exactness the whole figure
layer is built around (SPEC §10b). We author the canvas at the right size, so we
save it verbatim.
"""

from __future__ import annotations

import io
from pathlib import Path

from matplotlib.figure import Figure

from .style import house_style

_VECTOR = ("svg", "pdf")


def render_to_bytes(fig: Figure, fmt: str = "svg", *, dpi: int | None = None) -> bytes:
    """Serialize a figure to bytes. No `bbox_inches` — canvas stays mm-exact.

    savefig reads the font-embedding rcParams (`svg.fonttype`, `pdf.fonttype`) at
    SAVE time, not build time — so the export must run under the house style too,
    or text gets silently outlined the moment the build context has exited.
    """
    fmt = fmt.lower()
    if fmt not in ("svg", "pdf", "png"):
        raise ValueError(f"Unsupported export format: {fmt}")
    buf = io.BytesIO()
    kwargs: dict = {}
    if fmt == "png" and dpi is not None:
        kwargs["dpi"] = dpi
    # Deliberately NO bbox_inches / pad_inches. See module docstring.
    with house_style():
        fig.savefig(buf, format=fmt, **kwargs)
    return buf.getvalue()


def export_all(fig: Figure, stem: Path | str, *, dpi: int = 600) -> dict[str, Path]:
    """Write the canonical trio (SVG, PDF, PNG) next to `stem`.

    Returns {fmt: path}. The vector pair is what goes into a manuscript; the PNG
    is for quick preview only.
    """
    stem = Path(stem)
    stem.parent.mkdir(parents=True, exist_ok=True)
    out: dict[str, Path] = {}
    for fmt in ("svg", "pdf", "png"):
        path = stem.with_suffix(f".{fmt}")
        path.write_bytes(render_to_bytes(fig, fmt, dpi=dpi))
        out[fmt] = path
    return out
