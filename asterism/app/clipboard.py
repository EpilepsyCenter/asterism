"""Copy graphs and figures to the system clipboard as vector graphics.

Each system gets its native vector format and no bitmap a receiving app might silently
prefer (SPEC §10):
  macOS    PDF ("com.adobe.pdf") and SVG on NSPasteboard (Word, PowerPoint, Keynote and
           Illustrator paste the PDF as vectors). Written directly through the Objective-C
           runtime: Qt doesn't offer PDF on the Mac pasteboard, and data written this way
           stays after ASTERISM quits.
  Windows  EMF (Enhanced Metafile, what Office pastes as vectors; see emf.py) and SVG,
           through the Win32 clipboard.
  Linux    SVG, plus PNG for apps that only take pictures, through Qt.
"""

from __future__ import annotations

import sys

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QMarginsF, QMimeData, QSizeF
from PySide6.QtGui import QColor, QImage, QPageLayout, QPageSize, QPainter, QPdfWriter

from .graph.canvas import QtCanvas, SvgCanvas


def _draw(cv, elements, offset=None) -> None:
    for e in elements:
        e.draw(cv)


def render_formats(elements, bounds, dpi: int = 300, white: bool = False) -> dict[str, bytes]:
    """{"pdf", "svg", "png", "emf"} for drawable elements inside `bounds` (points)."""
    from .graph.emf import EmfCanvas
    out: dict[str, bytes] = {}
    # PDF
    buf = QBuffer()
    buf.open(QIODevice.WriteOnly)
    w = QPdfWriter(buf)
    w.setResolution(72)
    w.setPageSize(QPageSize(QSizeF(bounds.width(), bounds.height()), QPageSize.Point, "", QPageSize.ExactMatch))
    w.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Point)
    w.setCreator("ASTERISM")
    p = QPainter(w)
    p.translate(-bounds.x(), -bounds.y())
    if white:
        p.fillRect(bounds, QColor("white"))
    _draw(QtCanvas(p), elements)
    p.end()
    buf.close()
    out["pdf"] = bytes(buf.data())
    # SVG
    sv = SvgCanvas(bounds)
    if white:
        sv.rect(bounds.x(), bounds.y(), bounds.width(), bounds.height(), fill="#ffffff")
    for e in elements:
        sv.begin_group(e.id) if hasattr(e, "id") else None
        e.draw(sv)
        sv.end_group() if hasattr(e, "id") else None
    out["svg"] = sv.tostring().encode("utf-8")
    # PNG
    s = dpi / 72.0
    img = QImage(max(1, int(round(bounds.width() * s))), max(1, int(round(bounds.height() * s))),
                 QImage.Format_ARGB32)
    img.setDotsPerMeterX(int(dpi / 0.0254))
    img.setDotsPerMeterY(int(dpi / 0.0254))
    img.fill(QColor("white"))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(s, s)
    p.translate(-bounds.x(), -bounds.y())
    _draw(QtCanvas(p), elements)
    p.end()
    pb = QBuffer()
    pb.open(QIODevice.WriteOnly)
    img.save(pb, "PNG")
    out["png"] = bytes(pb.data())
    # EMF
    em = EmfCanvas(bounds)
    if white:
        em.rect(bounds.x(), bounds.y(), bounds.width(), bounds.height(), fill="#ffffff")
    _draw(em, elements)
    out["emf"] = em.tobytes()
    return out


def copy_formats(fmts: dict[str, bytes]) -> None:
    if sys.platform == "darwin":
        _mac_copy(fmts)
    elif sys.platform == "win32":
        _win_copy(fmts)
    else:
        _qt_copy(fmts)


def copy_graph(graph) -> None:
    from .graph.layout import build, content_bounds
    els, _ = build(graph)
    copy_formats(render_formats(els, content_bounds(els)))


def copy_figure(fig, project) -> None:
    from .figure.layout import build_figure
    page, els = build_figure(fig, project)
    copy_formats(render_formats(els, page, white=True))


# ---------------------------------------------------------------------------
# Linux (and a fallback): Qt
# ---------------------------------------------------------------------------

def _qt_copy(fmts: dict[str, bytes]) -> None:
    from PySide6.QtWidgets import QApplication
    md = QMimeData()
    md.setData("image/svg+xml", QByteArray(fmts["svg"]))
    md.setData("image/png", QByteArray(fmts["png"]))
    img = QImage()
    img.loadFromData(fmts["png"], "PNG")
    md.setImageData(img)
    QApplication.clipboard().setMimeData(md)


# ---------------------------------------------------------------------------
# macOS: NSPasteboard through the Objective-C runtime (ctypes; no extra packages)
# ---------------------------------------------------------------------------

def _mac_copy(fmts: dict[str, bytes]) -> None:
    import ctypes
    import ctypes.util
    objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))
    ctypes.cdll.LoadLibrary(ctypes.util.find_library("AppKit"))
    objc.objc_getClass.restype = ctypes.c_void_p
    objc.objc_getClass.argtypes = [ctypes.c_char_p]
    objc.sel_registerName.restype = ctypes.c_void_p
    objc.sel_registerName.argtypes = [ctypes.c_char_p]
    send = objc.objc_msgSend

    def msg(restype, obj, sel, *args, argtypes=()):
        send.restype = restype
        send.argtypes = [ctypes.c_void_p, ctypes.c_void_p, *argtypes]
        return send(obj, objc.sel_registerName(sel), *args)

    cls = objc.objc_getClass
    nsstr = lambda s: msg(ctypes.c_void_p, cls(b"NSString"), b"stringWithUTF8String:", s.encode("utf-8"),
                          argtypes=(ctypes.c_char_p,))
    pool = msg(ctypes.c_void_p, msg(ctypes.c_void_p, cls(b"NSAutoreleasePool"), b"alloc"), b"init")
    try:
        pb = msg(ctypes.c_void_p, cls(b"NSPasteboard"), b"generalPasteboard")
        msg(ctypes.c_long, pb, b"clearContents")
        for uti, key in (("com.adobe.pdf", "pdf"), ("public.svg-image", "svg")):
            raw = fmts.get(key)
            if not raw:
                continue
            data = msg(ctypes.c_void_p, cls(b"NSData"), b"dataWithBytes:length:", raw, len(raw),
                       argtypes=(ctypes.c_char_p, ctypes.c_ulong))
            msg(ctypes.c_bool, pb, b"setData:forType:", data, nsstr(uti),
                argtypes=(ctypes.c_void_p, ctypes.c_void_p))
    finally:
        msg(None, pool, b"drain")


def _mac_types() -> list[str]:
    """The pasteboard's current types (for tests)."""
    import ctypes
    import ctypes.util
    objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))
    ctypes.cdll.LoadLibrary(ctypes.util.find_library("AppKit"))
    objc.objc_getClass.restype = ctypes.c_void_p
    objc.objc_getClass.argtypes = [ctypes.c_char_p]
    objc.sel_registerName.restype = ctypes.c_void_p
    objc.sel_registerName.argtypes = [ctypes.c_char_p]
    send = objc.objc_msgSend

    def msg(restype, obj, sel, *args, argtypes=()):
        send.restype = restype
        send.argtypes = [ctypes.c_void_p, ctypes.c_void_p, *argtypes]
        return send(obj, objc.sel_registerName(sel), *args)
    pb = msg(ctypes.c_void_p, objc.objc_getClass(b"NSPasteboard"), b"generalPasteboard")
    types = msg(ctypes.c_void_p, pb, b"types")
    n = msg(ctypes.c_ulong, types, b"count")
    out = []
    for i in range(n):
        s = msg(ctypes.c_void_p, types, b"objectAtIndex:", i, argtypes=(ctypes.c_ulong,))
        out.append(msg(ctypes.c_char_p, s, b"UTF8String").decode("utf-8"))
    return out


# ---------------------------------------------------------------------------
# Windows: the Win32 clipboard (ctypes)
# ---------------------------------------------------------------------------

def _win_copy(fmts: dict[str, bytes]) -> None:
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE
    user32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
    user32.RegisterClipboardFormatW.restype = wintypes.UINT
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    gdi32.SetEnhMetaFileBits.argtypes = [wintypes.UINT, ctypes.c_char_p]
    gdi32.SetEnhMetaFileBits.restype = wintypes.HANDLE
    CF_ENHMETAFILE, GMEM_MOVEABLE = 14, 0x0002

    def global_bytes(raw: bytes):
        h = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(raw))
        ptr = kernel32.GlobalLock(h)
        ctypes.memmove(ptr, raw, len(raw))
        kernel32.GlobalUnlock(h)
        return h

    for _ in range(10):                          # another app may hold the clipboard briefly
        if user32.OpenClipboard(None):
            break
        kernel32.Sleep(20)
    else:
        raise OSError("The clipboard is in use by another program.")
    try:
        user32.EmptyClipboard()
        if fmts.get("emf"):
            hemf = gdi32.SetEnhMetaFileBits(len(fmts["emf"]), fmts["emf"])
            if hemf:
                user32.SetClipboardData(CF_ENHMETAFILE, hemf)
        for name, key in (("image/svg+xml", "svg"),):
            if fmts.get(key):
                user32.SetClipboardData(user32.RegisterClipboardFormatW(name), global_bytes(fmts[key]))
    finally:
        user32.CloseClipboard()
