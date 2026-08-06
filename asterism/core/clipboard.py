"""macOS pasteboard export — the primary path for single graphs (SPEC §10a).

"Copy figure" puts a **vector PDF** on the pasteboard, rendered from the same
matplotlib figure as the file export (never screenshotted from the on-screen
preview). We put the PDF flavour on the pasteboard and *nothing else*: if a PNG
representation is also offered, some receiving app will eventually prefer it and
you get a silent rasterisation with no visible symptom until print.

AppKit is imported lazily inside the function so this module stays importable on
non-mac CI and doesn't pull a UI framework at core import time (SPEC §11).
"""

from __future__ import annotations

from matplotlib.figure import Figure

from .export import render_to_bytes


def copy_figure_to_pasteboard(fig: Figure) -> int:
    """Place the figure on the macOS pasteboard as vector PDF only.

    Returns the pasteboard change count (proof the write landed). Raises on any
    platform other than macOS.
    """
    pdf_bytes = render_to_bytes(fig, "pdf")
    return copy_pdf_bytes_to_pasteboard(pdf_bytes)


def copy_pdf_bytes_to_pasteboard(pdf_bytes: bytes) -> int:
    try:
        from AppKit import NSPasteboard, NSPasteboardTypePDF
        from Foundation import NSData
    except ImportError as exc:  # pragma: no cover - non-mac
        # Deliberately macOS-only (SPEC §10a). Windows/Linux have no native PDF
        # pasteboard flavour; those users take the file-export path (SPEC §10).
        raise RuntimeError(
            "Clipboard 'Copy figure' is macOS-only. On Windows/Linux, export the "
            "figure to file (SVG/PDF) and import it instead."
        ) from exc

    pb = NSPasteboard.generalPasteboard()
    pb.clearContents()
    data = NSData.dataWithBytes_length_(pdf_bytes, len(pdf_bytes))
    # ONE flavour only — PDF. No PNG "for convenience" (see module docstring).
    ok = pb.setData_forType_(data, NSPasteboardTypePDF)
    if not ok:
        raise RuntimeError("NSPasteboard rejected the PDF data")
    return int(pb.changeCount())


def pasteboard_flavours() -> list[str]:
    """The UTType/flavour list currently on the pasteboard — for verifying that
    only PDF landed (used by the step-0 spike check)."""
    from AppKit import NSPasteboard

    pb = NSPasteboard.generalPasteboard()
    return [str(t) for t in pb.types()]
