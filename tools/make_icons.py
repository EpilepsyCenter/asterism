"""Build the app icons for Windows (.ico) and Linux (.png) from asterism/app/assets/icon.svg.

    .venv/bin/python tools/make_icons.py

The macOS icon (asterism.icns) is made separately with iconutil. The .ico holds PNG images
at the sizes Windows uses (16–256 px).
"""

from __future__ import annotations

import os
import struct
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication, QImage, QPainter  # noqa: E402
from PySide6.QtSvg import QSvgRenderer  # noqa: E402

ASSETS = os.path.join(os.path.dirname(__file__), "..", "asterism", "app", "assets")


def render(size: int) -> bytes:
    r = QSvgRenderer(os.path.join(ASSETS, "icon.svg"))
    img = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    r.render(p)
    p.end()
    buf = QBuffer()
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "PNG")
    return bytes(buf.data())


def main() -> int:
    app = QGuiApplication(sys.argv)  # noqa: F841
    sizes = [16, 24, 32, 48, 64, 128, 256]
    pngs = [render(s) for s in sizes]
    head = struct.pack("<HHH", 0, 1, len(sizes))
    off = 6 + 16 * len(sizes)
    entries = b""
    for s, data in zip(sizes, pngs):
        entries += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32, len(data), off)
        off += len(data)
    with open(os.path.join(ASSETS, "asterism.ico"), "wb") as f:
        f.write(head + entries + b"".join(pngs))
    with open(os.path.join(ASSETS, "asterism.png"), "wb") as f:
        f.write(render(512))
    print("wrote asterism.ico and asterism.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
