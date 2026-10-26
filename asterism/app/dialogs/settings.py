"""Settings: autosave, the look of new graphs, starting choices for new analyses, import
defaults. They apply to things made from now on — never to saved graphs or analyses."""

from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QDoubleSpinBox, QFontComboBox, QLabel, QLineEdit, QPushButton, QSpinBox

from .. import prefs
from ..graph.formatting import SCHEMES
from .common import FormGrid, Section, SectionDialog, combo, tab_page


def _note(s: str) -> QLabel:
    lab = QLabel(s)
    lab.setWordWrap(True)
    lab.setEnabled(False)
    return lab


def _spin(v: float, lo: float, hi: float, suffix: str, decimals: int = 1) -> QDoubleSpinBox:
    s = QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setDecimals(decimals)
    s.setSuffix(suffix)
    s.setValue(float(v))
    return s


class SettingsDialog(SectionDialog):
    def __init__(self, parent=None):
        self.reset_button = QPushButton("Restore Defaults")
        super().__init__("Settings", "Settings", parent, extra_left=[self.reset_button])
        self.add_group("Settings")
        self.w: dict = {}
        self.add_section("general", "General", self._general(), "gearshape")
        self.add_section("graphs", "New graphs", self._graphs(), "chart.bar")
        self.add_section("analyses", "New analyses", self._analyses(), "function")
        self.add_section("import", "Import", self._import(), "square.and.arrow.down.on.square")
        self.reset_button.clicked.connect(self._reset)
        self.show_section("general")
        self.resize(820, 520)

    def _general(self):
        from .start import SHOW_KEY
        from .. import documents
        page, pl = tab_page()
        pl.addWidget(Section("Starting"))
        self.start = QCheckBox("Show the Start window when ASTERISM opens")
        self.start.setChecked(documents.value(SHOW_KEY, True) not in (False, "false", "0", 0))
        pl.addWidget(self.start)
        pl.addWidget(Section("Autosave"))
        g = FormGrid()
        self.w["autosave.enabled"] = QCheckBox("Save a recovery copy of unsaved changes every")
        self.w["autosave.enabled"].setChecked(prefs.get("autosave.enabled"))
        self.w["autosave.minutes"] = QSpinBox()
        self.w["autosave.minutes"].setRange(1, 60)
        self.w["autosave.minutes"].setSuffix(" min")
        self.w["autosave.minutes"].setValue(prefs.get("autosave.minutes"))
        self.w["autosave.minutes"].setFixedWidth(90)
        g.add((None, self.w["autosave.enabled"]), (None, self.w["autosave.minutes"]))
        pl.addLayout(g)
        pl.addWidget(_note("Recovery copies are kept in ASTERISM's own folder, never over your files, and removed "
                           "when you save or close. If ASTERISM quits unexpectedly, it offers them the next time."))
        pl.addWidget(Section("Exporting"))
        g = FormGrid()
        self.w["export.dpi"] = combo([("150 dpi", 150), ("300 dpi", 300), ("600 dpi", 600), ("1200 dpi", 1200)],
                                     prefs.get("export.dpi"))
        g.add(("PNG and TIFF resolution:", self.w["export.dpi"]))
        pl.addLayout(g)
        pl.addWidget(_note("PDF and SVG are vector files and print sharp at any size."))
        pl.addStretch(1)
        return page

    def _graphs(self):
        page, pl = tab_page()
        pl.addWidget(_note("How new graphs start. Existing graphs keep their own formatting; Format Graph and "
                           "“Apply Formatting to Other Graphs” change those."))
        pl.addWidget(Section("Text and axes"))
        g = FormGrid()
        self.w["graph.font"] = QFontComboBox()
        self.w["graph.font"].setCurrentText(prefs.get("graph.font"))
        self.w["graph.font_size"] = _spin(prefs.get("graph.font_size"), 6, 24, " pt")
        self.w["graph.axis_width"] = combo([("½ pt", 0.5), ("1 pt", 1.0), ("1½ pt", 1.5), ("2 pt", 2.0)],
                                           prefs.get("graph.axis_width"))
        self.w["graph.frame"] = combo([("Plain axes", "plain"), ("Offset axes", "offset"), ("Box", "box")],
                                      prefs.get("graph.frame"))
        g.add(("Font:", self.w["graph.font"]), ("Size:", self.w["graph.font_size"]))
        g.add(("Axis thickness:", self.w["graph.axis_width"]), ("Frame:", self.w["graph.frame"]))
        pl.addLayout(g)
        pl.addWidget(Section("Size and colours"))
        g = FormGrid()
        self.w["graph.height_mm"] = _spin(prefs.get("graph.height_mm"), 15, 200, " mm")
        self.w["graph.col_width_mm"] = _spin(prefs.get("graph.col_width_mm"), 5, 60, " mm")
        self.w["graph.scheme"] = combo([("ASTERISM (default)", "")] + [(v[0], k) for k, v in SCHEMES.items()
                                                                        if k != "asterism"], prefs.get("graph.scheme"))
        g.add(("Plot height:", self.w["graph.height_mm"]), ("Column width:", self.w["graph.col_width_mm"]))
        g.add(("Colour scheme:", self.w["graph.scheme"]))
        pl.addLayout(g)
        pl.addWidget(Section("Significance"))
        g = FormGrid()
        self.w["graph.sig_levels"] = combo([("0.05, 0.01, 0.001, 0.0001", "four"), ("0.05, 0.01, 0.001", "three"),
                                            ("Prism's: 0.0332, 0.0021, 0.0002, 0.0001", "gp")],
                                           prefs.get("graph.sig_levels"))
        self.w["graph.sig_label"] = combo([("Stars", "stars"), ("P value", "p"), ("Number", "number"),
                                           ("Stars and P value", "both")], prefs.get("graph.sig_label"))
        self.w["graph.sig_shape"] = combo([("Bracket", "bracket"), ("Plain line", "line")], prefs.get("graph.sig_shape"))
        g.add(("Star thresholds:", self.w["graph.sig_levels"]))
        g.add(("Label:", self.w["graph.sig_label"]), ("Shape:", self.w["graph.sig_shape"]))
        pl.addLayout(g)
        pl.addStretch(1)
        return page

    def _analyses(self):
        page, pl = tab_page()
        pl.addWidget(_note("Where a new analysis's settings start. Every analysis can still be changed in its own "
                           "settings; saved analyses keep theirs."))
        g = FormGrid()
        self.w["analysis.ttest"] = combo([("Student's t test (equal SDs, Prism's default)", "student"),
                                          ("Welch's t test (unequal SDs)", "welch")], prefs.get("analysis.ttest"))
        self.w["analysis.posthoc"] = combo([("Automatic (Tukey for all pairs, Dunnett against a control)", "auto"),
                                            ("Tukey", "tukey"), ("Šídák", "sidak"), ("Bonferroni", "bonferroni"),
                                            ("Holm-Šídák", "holm_sidak")], prefs.get("analysis.posthoc"))
        self.w["analysis.conf"] = combo([("90%", 0.90), ("95%", 0.95), ("99%", 0.99)], prefs.get("analysis.conf"))
        self.w["analysis.alpha"] = combo([("0.05", 0.05), ("0.01", 0.01), ("0.10", 0.10)], prefs.get("analysis.alpha"))
        g.add(("Unpaired t test:", self.w["analysis.ttest"]))
        g.add(("One-way ANOVA comparisons:", self.w["analysis.posthoc"]))
        g.add(("Confidence intervals:", self.w["analysis.conf"]), ("Significance level (α):", self.w["analysis.alpha"]))
        pl.addLayout(g)
        pl.addStretch(1)
        return page

    def _import(self):
        page, pl = tab_page()
        pl.addWidget(Section("qPCR (QuantStudio)"))
        g = FormGrid()
        self.w["import.qpcr_relative_to"] = combo([("The mean of a control group", "group"),
                                                   ("One reference sample (as QuantStudio)", "sample")],
                                                  prefs.get("import.qpcr_relative_to"))
        g.add(("ΔΔCt relative to:", self.w["import.qpcr_relative_to"]))
        pl.addLayout(g)
        pl.addWidget(Section("Standard curves: titres"))
        pl.addWidget(_note("Your lab's titration settings, filled in for every standard-curve import (you can still "
                           "change them there). Titre = quantity per reaction × dilution [× 2] ÷ template µL [× 1000 "
                           "per mL]."))
        g = FormGrid()
        self.w["import.titre_dilution"] = QLineEdit(f"{prefs.get('import.titre_dilution'):g}")
        self.w["import.titre_dilution"].setFixedWidth(110)
        self.w["import.titre_volume_ul"] = QLineEdit(f"{prefs.get('import.titre_volume_ul'):g}"
                                                     if prefs.get("import.titre_volume_ul") else "")
        self.w["import.titre_volume_ul"].setPlaceholderText("µL per reaction")
        self.w["import.titre_volume_ul"].setFixedWidth(130)
        self.w["import.titre_per"] = combo([("Per reaction (× dilution factor)", "reaction"), ("Per µL of sample", "ul"),
                                            ("Per mL of sample", "ml")], prefs.get("import.titre_per"))
        self.w["import.titre_ss"] = QCheckBox("× 2 for single-stranded genomes on a double-stranded standard")
        self.w["import.titre_ss"].setChecked(prefs.get("import.titre_ss"))
        g.add(("Dilution factor:", self.w["import.titre_dilution"]), ("Template volume:", self.w["import.titre_volume_ul"]))
        g.add(("Report:", self.w["import.titre_per"]))
        pl.addLayout(g)
        pl.addWidget(self.w["import.titre_ss"])
        pl.addStretch(1)
        return page

    def values(self) -> dict:
        from ...io.sheets import number
        out = {}
        for k, wd in self.w.items():
            if isinstance(wd, QCheckBox):
                out[k] = wd.isChecked()
            elif isinstance(wd, QFontComboBox):
                out[k] = wd.currentFont().family()
            elif isinstance(wd, (QDoubleSpinBox, QSpinBox)):
                out[k] = wd.value()
            elif isinstance(wd, QLineEdit):
                out[k] = number(wd.text()) or (1.0 if k == "import.titre_dilution" else 0.0)
            else:
                out[k] = wd.currentData()
        return out

    def accept(self) -> None:
        from .start import SHOW_KEY
        from .. import documents
        for k, v in self.values().items():
            prefs.set(k, v)
        documents.set_value(SHOW_KEY, self.start.isChecked())
        super().accept()

    def _reset(self) -> None:
        from .. import documents
        from .start import SHOW_KEY
        prefs.reset()
        documents.set_value(SHOW_KEY, True)
        self.reject()
