"""Copying graphs and figures as vector pictures: PDF (macOS), EMF (Windows), SVG (Linux),
each with a PNG. The EMF is written from Microsoft's format description and checked here
record by record."""

from __future__ import annotations

import os
import struct
import sys

import pytest


def _graph(app):
    from asterism.analysis import engine
    from asterism.doc.sample import sample_project
    p = sample_project(engine)
    return p, p.graphs[0]


def test_formats_for_a_graph(app):
    from asterism.app import clipboard as CB
    from asterism.app.graph.layout import build, content_bounds
    _p, g = _graph(app)
    els, _ = build(g)
    f = CB.render_formats(els, content_bounds(els))
    assert f["pdf"].startswith(b"%PDF") and f["png"].startswith(b"\x89PNG")
    assert b"<svg" in f["svg"] and len(f["emf"]) > 1000


def test_emf_structure(app):
    """Header totals match, records are 4-byte aligned, the file ends with EOF, every
    created object is deleted, and text is real text (font, string, alignment)."""
    from asterism.app import clipboard as CB
    from asterism.app.graph import emf as E
    from asterism.app.graph.layout import build, content_bounds
    _p, g = _graph(app)
    els, _ = build(g)
    data = CB.render_formats(els, content_bounds(els))["emf"]
    recs = E.records(data)
    kind0, hdr = recs[0]
    assert kind0 == E.EMR_HEADER and struct.unpack_from("<I", hdr, 32)[0] == 0x464D4520
    nbytes, nrec = struct.unpack_from("<II", hdr, 40)
    assert nbytes == len(data) and nrec == len(recs)
    assert recs[-1][0] == E.EMR_EOF
    assert all(len(p) % 4 == 0 for _k, p in recs)
    created = sum(1 for k, _ in recs if k in (E.EMR_EXTCREATEPEN, E.EMR_CREATEBRUSHINDIRECT,
                                               E.EMR_EXTCREATEFONTINDIRECTW))
    deleted = sum(1 for k, _ in recs if k == E.EMR_DELETEOBJECT)
    assert created == deleted
    texts = [p for k, p in recs if k == E.EMR_EXTTEXTOUTW]
    strings = []
    for p in texts:
        n, off = struct.unpack_from("<II", p, 36)
        strings.append(p[off - 8: off - 8 + 2 * n].decode("utf-16-le"))
    assert g.name in strings or any(g.name.startswith(s) for s in strings)


def test_emf_groups_and_opacity(app):
    from PySide6.QtCore import QRectF
    from asterism.app.graph import emf as E
    cv = E.EmfCanvas(QRectF(0, 0, 100, 50))
    cv.begin_group("panel", 10, 5, 0.5)
    cv.polygon([(0, 0), (20, 0), (20, 20)], fill="#000000", opacity=0.5)
    cv.end_group()
    recs = E.records(cv.tobytes())
    brush = next(p for k, p in recs if k == E.EMR_CREATEBRUSHINDIRECT)
    assert struct.unpack_from("<I", brush, 8)[0] == 0x00808080          # 50% black on white
    poly = next(p for k, p in recs if k == E.EMR_POLYGON)
    pts = [struct.unpack_from("<ii", poly, 20 + 8 * i) for i in range(3)]
    assert pts[1] == (round((10 + 0.5 * 20) * E.K), round(5 * E.K))     # translated and scaled


@pytest.mark.skipif(sys.platform != "darwin" or not os.environ.get("ASTERISM_TEST_CLIPBOARD"),
                    reason="macOS pasteboard; replaces your clipboard, so only with ASTERISM_TEST_CLIPBOARD=1")
def test_mac_pasteboard_gets_pdf_and_svg_only(app):
    from asterism.app import clipboard as CB
    _p, g = _graph(app)
    CB.copy_graph(g)
    types = CB._mac_types()
    assert "com.adobe.pdf" in types and "public.svg-image" in types
    assert "public.png" not in types and "public.tiff" not in types        # vector only (SPEC §10)
