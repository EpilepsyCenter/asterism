"""Offer to restore projects whose changes weren't saved (ASTERISM quit unexpectedly)."""

from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QListWidget, QListWidgetItem, QPushButton

from .common import SectionDialog, tab_page


class RecoveryDialog(SectionDialog):
    def __init__(self, snapshots, parent=None):
        self.discard_button = QPushButton("Discard")
        super().__init__("Restore Unsaved Work", "Autosave and recovery", parent, extra_left=[self.discard_button])
        self.snapshots = snapshots
        self.discarded = False
        self.add_group("Recovery")
        page, pl = tab_page()
        note = QLabel("ASTERISM didn't close normally last time. These projects had changes that weren't saved; "
                      "their latest autosaved state can be restored. Restored projects open with their unsaved "
                      "changes — save them to keep them.")
        note.setWordWrap(True)
        pl.addWidget(note)
        self.list = QListWidget()
        for s in snapshots:
            where = s.original if s.original else "never saved"
            it = QListWidgetItem(f"{s.name}   —   autosaved {s.when()}   ({where})")
            it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked)
            it.setData(Qt.UserRole, s)
            self.list.addItem(it)
        pl.addWidget(self.list, 1)
        later = QLabel("Cancel keeps them for next time; Discard deletes the autosaved copies.")
        later.setEnabled(False)
        pl.addWidget(later)
        self.add_section("restore", "Unsaved projects", page, "clock.arrow.circlepath")
        self.ok.setText("Restore")
        self.discard_button.clicked.connect(self._discard)
        self.show_section("restore")
        self.resize(720, 400)

    def _discard(self) -> None:
        self.discarded = True
        self.reject()

    def chosen(self) -> list:
        return [self.list.item(i).data(Qt.UserRole) for i in range(self.list.count())
                if self.list.item(i).checkState() == Qt.Checked]
