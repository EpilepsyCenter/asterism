"""The "Updating ASTERISM" window: shows what an in-app update is doing.

  1. Downloading — a bar with size and time left, and Cancel.
  2. Getting ready — a moving bar while the download is checked (and, on macOS, unpacked).
  3. Ready — says what happens next (ASTERISM closes, installs, opens again) with
     Restart and Install / Later.

The same design as TRACER's update window (sibling apps). selfupdate.py drives it; for
the download it also offers the QProgressDialog calls selfupdate._download uses
(setMaximum / setValue / wasCanceled).
"""

from __future__ import annotations

import time

from PySide6.QtCore import QEventLoop, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .. import theme

STEPS = ("Download", "Check and unpack", "Install")


def _mb(n: float) -> str:
    return f"{n / 1048576:.1f}" if n < 10 * 1048576 else f"{n / 1048576:.0f}"


def time_left(seconds: float) -> str:
    if not seconds or seconds <= 0 or seconds != seconds:
        return ""
    if seconds < 10:
        return "a few seconds left"
    if seconds < 90:
        return f"about {round(seconds / 5) * 5:.0f} s left"
    return f"about {round(seconds / 60):.0f} min left"


class _Bar(QWidget):
    """A slim progress bar in the theme's colours: a fraction, or (None) a moving segment."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(6)
        self.fraction: float | None = 0.0
        self._phase = 0.0
        self._timer = QTimer(self, interval=16, timeout=self._tick)

    def set_fraction(self, f: float | None) -> None:
        self.fraction = f
        if f is None:
            self._timer.start()
        else:
            self._timer.stop()
        self.update()

    def _tick(self) -> None:
        self._phase = (self._phase + 0.012) % 1.0
        self.update()

    def paintEvent(self, _e) -> None:
        t = theme.tokens()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        r = QRectF(self.rect())
        track = QColor(t["text"])
        track.setAlphaF(0.10)
        p.setBrush(track)
        p.drawRoundedRect(r, 3, 3)
        p.setBrush(QColor(t["accent"]))
        if self.fraction is None:
            w = r.width() * 0.32
            x = -w + (r.width() + w) * self._phase
            p.setClipRect(r)
            p.drawRoundedRect(QRectF(x, 0, w, r.height()), 3, 3)
        elif self.fraction > 0:
            p.drawRoundedRect(QRectF(0, 0, r.width() * min(1.0, self.fraction), r.height()), 3, 3)


class UpdateDialog(QDialog):
    def __init__(self, version: str, parent=None, unpacks: bool = False):
        super().__init__(parent)
        self.version = version
        self.setWindowTitle("Updating ASTERISM")
        self.setWindowModality(Qt.WindowModal)
        self.setMinimumWidth(460)
        self._steps = STEPS if unpacks else (STEPS[0], STEPS[2])
        self._cancelled = False
        self._choice: str | None = None
        self._loop: QEventLoop | None = None
        self._max = 0
        self._rate = 0.0
        self._sample: tuple[float, int] | None = None
        self._shown_at = 0.0

        self.head = QLabel()
        f = self.head.font()
        f.setPointSizeF(f.pointSizeF() + 1)
        f.setBold(True)
        self.head.setFont(f)
        self.bar = _Bar()
        self.left, self.right = QLabel(), QLabel()
        meta = QHBoxLayout()
        meta.addWidget(self.left)
        meta.addStretch(1)
        meta.addWidget(self.right)
        self.note = QLabel()
        self.note.setWordWrap(True)
        self.note.hide()
        self.steps = QLabel()
        self.cancel_btn = QPushButton("Cancel")
        self.later_btn = QPushButton("Later")
        self.install_btn = QPushButton("Restart and Install")
        for b in (self.cancel_btn, self.later_btn, self.install_btn):
            b.setAutoDefault(False)
        self.cancel_btn.clicked.connect(self._cancel)
        self.later_btn.clicked.connect(lambda: self._decide("later"))
        self.install_btn.clicked.connect(lambda: self._decide("install"))
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        for b in (self.later_btn, self.cancel_btn, self.install_btn):
            buttons.addWidget(b)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 16)
        lay.setSpacing(10)
        lay.addWidget(self.head)
        lay.addWidget(self.bar)
        lay.addLayout(meta)
        lay.addWidget(self.note)
        lay.addStretch(1)
        lay.addWidget(self.steps)
        lay.addLayout(buttons)
        self._restyle()
        theme.notifier.changed.connect(self._restyle)
        self._show_step(0, buttons="cancel")

    # -- look --------------------------------------------------------------
    def _restyle(self) -> None:
        muted = theme.tokens()["muted"]
        for w in (self.left, self.right, self.note):
            w.setStyleSheet(f"color: {muted};")
        self._show_step(getattr(self, "_step", 0), getattr(self, "_buttons", "cancel"))

    def _show_step(self, step: int, buttons: str) -> None:
        self._step, self._buttons = step, buttons
        t = theme.tokens()
        parts = []
        for i, name in enumerate(self._steps):
            if i < step:
                style = f"color:{t['text']};"
            elif i == step:
                style = f"color:{t['accent']}; font-weight:600;"
            else:
                style = f"color:{t['muted']};"
            parts.append(f'<span style="{style}">{i + 1} {name}</span>')
        self.steps.setText('<span style="font-size:11px;">' + "&nbsp;&nbsp;&nbsp;&nbsp;".join(parts) + "</span>")
        ready = buttons == "ready"
        self.cancel_btn.setVisible(not ready)
        self.later_btn.setVisible(ready)
        self.install_btn.setVisible(ready)
        self.install_btn.setDefault(ready)

    # -- step 1: download (QProgressDialog-style calls for selfupdate._download) --
    def downloading(self) -> None:
        self.head.setText(f"Downloading ASTERISM {self.version}")
        self.bar.set_fraction(0.0)
        self.left.setText("Starting the download…")
        self.right.setText("")
        self._show_step(0, "cancel")

    def setMaximum(self, n: int) -> None:
        self._max = n

    def setValue(self, n: int) -> None:
        now = time.monotonic()
        if self._sample and now > self._sample[0]:
            r = (n - self._sample[1]) / (now - self._sample[0])
            self._rate = r if not self._rate else self._rate * 0.8 + r * 0.2
        self._sample = (now, n)
        if self._max > 0:
            self.bar.set_fraction(n / self._max)
            self.left.setText(f"{_mb(n)} of {_mb(self._max)} MB")
            self.right.setText(time_left((self._max - n) / self._rate) if self._rate > 0 else "")

    def wasCanceled(self) -> bool:
        return self._cancelled

    def _cancel(self) -> None:
        self._cancelled = True
        self.cancel_btn.setEnabled(False)
        self.left.setText("Cancelling…")

    # -- step 2: check / unpack ---------------------------------------------
    def preparing(self) -> None:
        self.head.setText("Getting the update ready")
        self.bar.set_fraction(None)
        self.left.setText("Checking the download and unpacking it…"
                          if len(self._steps) == 3 else "Checking the download…")
        self.right.setText("")
        self._show_step(1, "cancel")
        self.cancel_btn.setEnabled(False)

    # -- step 3: ready ------------------------------------------------------
    def ready(self, note: str) -> str:
        """Show "ready to install"; returns "install" or "later" once the user decides."""
        self.head.setText(f"ASTERISM {self.version} is ready to install")
        self.bar.set_fraction(1.0)
        self.left.setText("")
        self.right.setText("")
        self.note.setText(note)
        self.note.show()
        self._show_step(len(self._steps) - 1, "ready")
        self.adjustSize()
        self.raise_()
        self.activateWindow()
        self._choice = None
        self._loop = QEventLoop()
        self._loop.exec()
        self._loop = None
        return self._choice or "later"

    def _decide(self, choice: str) -> None:
        self._choice = choice
        if self._loop is not None:
            self._loop.quit()

    # -- closing the window: Cancel while downloading, Later when ready ------
    def reject(self) -> None:
        if self._buttons == "ready":
            self._decide("later")
        elif self.cancel_btn.isEnabled():
            self._cancel()

    def closeEvent(self, e) -> None:
        if self._buttons == "done":
            super().closeEvent(e)
            return
        e.ignore()          # closing means Cancel / Later; while checking it waits
        self.reject()

    def finish(self) -> None:
        """Close for good (the caller is done with the window)."""
        self._buttons = "done"
        self.bar.set_fraction(0.0)
        self.hide()
        self.deleteLater()
