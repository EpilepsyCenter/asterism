"""Names of the colour labels for this project."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QLineEdit

from ...doc.model import LABEL_NAMES
from ..widgets import tag_icon
from .common import FormGrid, SectionDialog, tab_page


class LabelNamesDialog(SectionDialog):
    def __init__(self, project, parent=None):
        super().__init__("Label Names", "Colour labels", parent)
        self.add_group("Labels")
        page, pl = tab_page()
        note = QLabel("Give the colours names for this project, such as “Final”, “To check” or “Supplement”. "
                      "Leave a name empty to use the colour's own name.")
        note.setWordWrap(True)
        note.setEnabled(False)
        pl.addWidget(note)
        g = FormGrid()
        self.edits = {}
        for k in range(1, 8):
            e = QLineEdit(project.label_names.get(k, ""))
            e.setPlaceholderText(LABEL_NAMES[k])
            dot = QLabel()
            dot.setPixmap(tag_icon(k, 14).pixmap(14, 14))
            g.add((None, dot), (LABEL_NAMES[k] + ":", e))
            self.edits[k] = e
        pl.addLayout(g)
        pl.addStretch(1)
        self.add_section("names", "Names", page, "tag")
        self.show_section("names")
        self.resize(560, 420)

    def names(self) -> dict[int, str]:
        return {k: e.text().strip() for k, e in self.edits.items() if e.text().strip()}
