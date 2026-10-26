"""Import data from a spreadsheet (CSV / TSV / Excel) or a lab export (NED-Net, TRACER,
QuantStudio) into new data tables, with every guess shown and changeable, and a preview of
the table that will be made (SPEC §11)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QCheckBox, QComboBox, QHeaderView, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QRadioButton, QSpinBox, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from ...doc.table import TYPE_NAMES
from ...io.build import LONG_ROLES, ROLES, WIDE_ROLES, Plan, build_table, guess_plan, headers
from ...io.sheets import text
from .common import FormGrid, Section, SectionDialog, combo, tab_page

TABLE_TYPES = ["column", "grouped", "xy", "nested", "contingency", "survival", "parts", "multivar"]


def _note(s: str) -> QLabel:
    lab = QLabel(s)
    lab.setWordWrap(True)
    lab.setEnabled(False)
    return lab


class ImportDialog(SectionDialog):
    def __init__(self, path, parent=None, sheets: dict | None = None):
        from ...io import labs
        from ...io.sheets import read_files
        super().__init__("Import Data", "Importing data", parent)
        paths = [path] if isinstance(path, (str, Path)) else list(path)
        self.paths = [Path(p) for p in paths]
        self.path = self.paths[0]
        self.sheets = sheets if sheets is not None else read_files(self.paths)
        if not self.sheets or not any(self.sheets.values()):
            raise ValueError("The file has no data.")
        self.source, self.items = labs.detect(self.sheets)
        self.qpcr = None
        self._building = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(120)
        self._timer.timeout.connect(self.refresh_preview)
        self.add_group("Import")
        if self.source:
            self.add_section("lab", f"{self.source} export", self._lab_page(), "flask")
            if self.source == "QuantStudio":
                self.add_section("qpcr", "qPCR settings", self._qpcr_page(), "slider.horizontal.3")
        self.add_section("file", "File and columns", self._file_page(), "tablecells")
        self.add_section("preview", "Preview", self._preview_page(), "eye")
        self.ok.setText("Import")
        self.show_section("lab" if self.source else "file")
        self.resize(980, 680)
        self.refresh_preview()

    # --- lab exports -------------------------------------------------------------------

    def _lab_page(self) -> QWidget:
        from ...io.labs import LAYOUTS
        page, pl = tab_page()
        self.use_recipe = QRadioButton(f"Use the {self.source} layout (recommended)")
        self.use_columns = QRadioButton("Choose the columns myself (File and columns)")
        self.use_recipe.setChecked(True)
        pl.addWidget(self.use_recipe)
        pl.addWidget(self.use_columns)
        pl.addWidget(Section("Tables to make"))
        pl.addWidget(_note("Tick the tables to make. The animal stays the unit of independence: one value per "
                           "animal, or animals side by side with their values below."))
        self.item_table = QTableWidget(len(self.items), 2)
        self.item_table.setHorizontalHeaderLabels(["Table", "Layout"])
        self.item_table.verticalHeader().hide()
        self.item_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.item_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        for i, it in enumerate(self.items):
            cell = QTableWidgetItem(it.title)
            cell.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable)
            cell.setCheckState(Qt.Checked if it.selected else Qt.Unchecked)
            self.item_table.setItem(i, 0, cell)
            c = combo([(LAYOUTS[k], k) for k in it.layouts], it.layout)
            c.setEnabled(len(it.layouts) > 1)
            c.currentIndexChanged.connect(lambda _i, it=it, c=c: (setattr(it, "layout", c.currentData()),
                                                                   self._later()))
            self.item_table.setCellWidget(i, 1, c)
        self.item_table.itemChanged.connect(self._item_ticked)
        self.item_table.currentCellChanged.connect(lambda *_: self._later())
        pl.addWidget(self.item_table, 1)
        self.use_recipe.toggled.connect(lambda _v: self._later())
        return page

    def _item_ticked(self, cell) -> None:
        self.items[cell.row()].selected = cell.checkState() == Qt.Checked
        self._later()

    def _qpcr_page(self) -> QWidget:
        from ...io import quantstudio as Q
        page, pl = tab_page()
        d = Q.defaults(self.sheets)
        foot = Q.footer(self.sheets)
        self.qpcr = d
        self.std = None
        if Q.has_standards(self.sheets):
            curves = Q.standard_curves(self.sheets)
            self.std = curves
            pl.addWidget(Section("Standard curves"))
            pl.addWidget(_note("Fitted here from the STANDARD wells: Cq against log10(quantity). "
                               + "  ".join(f"{t}: slope {c['slope']:.3f}, R² {c['r2']:.4f}, efficiency "
                                           f"{c['efficiency']:.1f}%." for t, c in curves.items())))
            g = FormGrid()
            self.dilution = QLineEdit("1")
            self.dilution.setFixedWidth(110)
            self.volume = QLineEdit("")
            self.volume.setPlaceholderText("µL per reaction")
            self.volume.setFixedWidth(130)
            self.per = combo([("Per reaction (× dilution factor)", "reaction"), ("Per µL of sample", "ul"),
                              ("Per mL of sample", "ml")])
            self.ss = QCheckBox("Single-stranded genomes against a double-stranded (plasmid) standard: × 2")
            from .. import prefs                      # the lab's titration settings (Settings › Import)
            self.dilution.setText(f"{prefs.get('import.titre_dilution'):g}")
            if prefs.get("import.titre_volume_ul"):
                self.volume.setText(f"{prefs.get('import.titre_volume_ul'):g}")
            self.per.setCurrentIndex(max(self.per.findData(prefs.get("import.titre_per")), 0))
            self.ss.setChecked(prefs.get("import.titre_ss"))
            g.add(("Dilution factor:", self.dilution), ("Template volume:", self.volume))
            g.add(("Report quantities:", self.per))
            pl.addLayout(g)
            pl.addWidget(self.ss)
            pl.addWidget(_note("For an AAV titre: the dilution of the sample in the reaction, the volume of diluted "
                               "sample per reaction, and per mL — vector genomes per mL."))
            for w in (self.dilution, self.volume):
                w.textChanged.connect(lambda *_: self._later())
            self.per.currentIndexChanged.connect(lambda *_: (self._sync_volume(), self._later()))
            self.ss.toggled.connect(lambda *_: self._later())
            self._sync_volume()
        outer = pl
        self.ddct_box = QWidget()
        pl = QVBoxLayout(self.ddct_box)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(2)
        outer.addWidget(self.ddct_box, 20)
        outer.addStretch(1)                      # keeps the standard-curve settings together when ΔΔCt is hidden
        if self.std is not None:
            pl.addWidget(Section("Relative expression (ΔΔCt)"))
        pl.addWidget(_note("Settings come from this run's file where it records them (its endogenous control and "
                           "reference sample); anything else is a guess from the names — check it."))
        pl.addWidget(Section("Reference gene (endogenous control)"))
        self.ref_list = QListWidget()
        self.ref_list.setMaximumHeight(110)
        for tg in d["targets"]:
            it = QListWidgetItem(tg + ("   (from the file)" if tg == foot.get("reference_gene") else
                                       "   (guessed: a housekeeping gene's name)" if tg in d["reference_genes"]
                                       else ""))
            it.setData(Qt.UserRole, tg)
            it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if tg in d["reference_genes"] else Qt.Unchecked)
            self.ref_list.addItem(it)
        self.ref_list.itemChanged.connect(lambda *_: self._later())
        pl.addWidget(self.ref_list)
        pl.addWidget(_note("Several ticked: their mean Ct is the reference."))
        pl.addWidget(Section("Relative to"))
        g = FormGrid()
        self.rel_group = QRadioButton("The mean of a control group")
        self.rel_sample = QRadioButton("One reference sample (as QuantStudio reports RQ)")
        from .. import prefs
        (self.rel_sample if prefs.get("import.qpcr_relative_to") == "sample" else self.rel_group).setChecked(True)
        self.ctrl = QComboBox()
        self.ref_sample = QComboBox()
        for smp in d["samples"]:
            self.ref_sample.addItem(smp + ("   (from the file)" if smp == foot.get("reference_sample") else ""), smp)
        if foot.get("reference_sample") in d["samples"]:
            self.ref_sample.setCurrentIndex(d["samples"].index(foot["reference_sample"]))
        g.add((None, self.rel_group), ("Control group:", self.ctrl))
        g.add((None, self.rel_sample), ("Reference sample:", self.ref_sample))
        pl.addLayout(g)
        pl.addWidget(Section("Samples and their groups"))
        pl.addWidget(_note("Biological samples; technical replicate wells are averaged. Groups are guessed by "
                           "dropping a trailing number (“Control 2” → Control); edit them here, or leave a group "
                           "empty to leave that sample out."))
        self.sample_table = QTableWidget(len(d["samples"]), 2)
        self.sample_table.setHorizontalHeaderLabels(["Sample", "Group"])
        self.sample_table.verticalHeader().hide()
        self.sample_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        for i, smp in enumerate(d["samples"]):
            a = QTableWidgetItem(smp)
            a.setFlags(Qt.ItemIsEnabled)
            self.sample_table.setItem(i, 0, a)
            self.sample_table.setItem(i, 1, QTableWidgetItem(d["groups"][smp]))
        self.sample_table.itemChanged.connect(lambda *_: (self._fill_groups(), self._later()))
        pl.addWidget(self.sample_table, 1)
        self._fill_groups(initial=d["control_group"])
        for w in (self.rel_group, self.rel_sample):
            w.toggled.connect(lambda *_: self._later())
        self.ctrl.currentIndexChanged.connect(lambda *_: self._later())
        self.ref_sample.currentIndexChanged.connect(lambda *_: self._later())
        self._sync_ddct()
        return page

    def _sync_volume(self) -> None:
        per_volume = self.per.currentData() in ("ul", "ml")
        self.volume.setEnabled(per_volume)
        self.volume.setToolTip("" if per_volume else "Used only when reporting per µL or per mL of sample")

    def _sync_ddct(self) -> None:
        """With standards in the run, the ΔΔCt settings show only when a ΔΔCt table is ticked."""
        if getattr(self, "ddct_box", None) is None:
            return
        wanted = any(it.selected and it.layout in ("qpcr_rel", "qpcr_dct", "qpcr_ct") for it in self.items)
        self.ddct_box.setVisible(self.std is None or wanted)

    def _fill_groups(self, initial: str | None = None) -> None:
        cur = initial or self.ctrl.currentText()
        groups = []
        for i in range(self.sample_table.rowCount()):
            g = (self.sample_table.item(i, 1).text() if self.sample_table.item(i, 1) else "").strip()
            if g and g not in groups:
                groups.append(g)
        self.ctrl.blockSignals(True)
        self.ctrl.clear()
        self.ctrl.addItems(groups)
        if cur in groups:
            self.ctrl.setCurrentText(cur)
        self.ctrl.blockSignals(False)

    def qpcr_settings(self) -> dict:
        if self.qpcr is None:
            return {}
        std = {}
        if self.std is not None:
            from ...io.sheets import number
            std = {"dilution": number(self.dilution.text()) or 1.0, "volume_ul": number(self.volume.text()) or 0.0,
                   "per": self.per.currentData(), "single_stranded": self.ss.isChecked()}
        refs = [self.ref_list.item(i).data(Qt.UserRole) for i in range(self.ref_list.count())
                if self.ref_list.item(i).checkState() == Qt.Checked]
        groups = {self.sample_table.item(i, 0).text(): (self.sample_table.item(i, 1).text().strip()
                                                         if self.sample_table.item(i, 1) else "")
                  for i in range(self.sample_table.rowCount())}
        return {"reference_genes": refs, "groups": groups, "control_group": self.ctrl.currentText(),
                "relative_to": "sample" if self.rel_sample.isChecked() else "group",
                "reference_sample": self.ref_sample.currentData(), "standard": std}

    # --- spreadsheet columns ------------------------------------------------------------

    def _file_page(self) -> QWidget:
        page, pl = tab_page()
        g = FormGrid()
        self.sheet_combo = QComboBox()
        self.sheet_combo.addItems(list(self.sheets))
        self.header_spin = QSpinBox()
        self.header_spin.setRange(0, 500)
        self.no_header = QCheckBox("No row of column names")
        fname = self.path.name if len(self.paths) == 1 else f"{len(self.paths)} files ({self.path.parent.name})"
        g.add(("File:", QLabel(fname)), ("Sheet:", self.sheet_combo))
        g.add(("Column names in row:", self.header_spin), (None, self.no_header))
        pl.addLayout(g)
        self.raw = QTableWidget()
        self.raw.setMaximumHeight(170)
        self.raw.setEditTriggers(QTableWidget.NoEditTriggers)
        pl.addWidget(self.raw)
        pl.addWidget(Section("Make a table"))
        g = FormGrid()
        self.name_edit = QLineEdit(self.path.stem)
        self.type_combo = combo([(TYPE_NAMES[t], t) for t in TABLE_TYPES])
        self.layout_combo = combo([("Wide: each column is a data set", "wide"),
                                   ("Long: one value per row, with group (and subject) columns", "long")])
        g.add(("Table name:", self.name_edit), ("Table type:", self.type_combo))
        g.add(("Layout:", self.layout_combo))
        pl.addLayout(g)
        self.merge = QCheckBox("Columns with the same name (e.g. Control 1, Control 2) are replicates of one data set")
        self.merge.setChecked(True)
        self.avg = QCheckBox("Average to one value per subject (the unit of independence)")
        pl.addWidget(self.merge)
        pl.addWidget(self.avg)
        self.role_table = QTableWidget(0, 3)
        self.role_table.setHorizontalHeaderLabels(["Column", "Example values", "Use as"])
        self.role_table.verticalHeader().hide()
        self.role_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.role_table.setColumnWidth(0, 170)
        self.role_table.setColumnWidth(2, 230)
        pl.addWidget(self.role_table, 1)
        self.sheet_combo.currentIndexChanged.connect(lambda *_: self._sheet_changed())
        self.header_spin.valueChanged.connect(lambda *_: self._header_changed())
        self.no_header.toggled.connect(lambda *_: self._header_changed())
        self.type_combo.currentIndexChanged.connect(lambda *_: self._type_changed())
        self.layout_combo.currentIndexChanged.connect(lambda *_: self._fill_roles(keep=False))
        self.merge.toggled.connect(lambda *_: self._later())
        self.avg.toggled.connect(lambda *_: self._later())
        self.type_combo.currentIndexChanged.connect(lambda *_: self._sync_options())
        self.layout_combo.currentIndexChanged.connect(lambda *_: self._sync_options())
        self._sheet_changed()
        self._sync_options()
        return page

    def _sync_options(self) -> None:
        """Show only the options that do something for this table type and layout."""
        tt, lay = self.type_combo.currentData(), self.layout_combo.currentData()
        self.merge.setVisible(lay == "wide" and tt in ("xy", "grouped"))
        self.avg.setVisible(lay == "long")

    def rows(self) -> list[list]:
        return self.sheets[self.sheet_combo.currentText()]

    def _sheet_changed(self) -> None:
        rows = self.rows()
        plan = guess_plan(rows)
        self._building = True
        self.header_spin.setValue(plan.header_row + 1)
        self.no_header.setChecked(False)
        from ...doc.table import TYPE_NAMES as _TN
        i = self.type_combo.findData(plan.table_type)
        self.type_combo.setCurrentIndex(max(i, 0))
        self.layout_combo.setCurrentIndex(self.layout_combo.findData(plan.layout))
        self._building = False
        self._show_raw()
        self._fill_roles(plan=plan)

    def _header_row(self) -> int:
        return -1 if self.no_header.isChecked() else self.header_spin.value() - 1

    def _header_changed(self) -> None:
        if self._building:
            return
        self.header_spin.setEnabled(not self.no_header.isChecked())
        self._show_raw()
        self._fill_roles(plan=guess_plan(self.rows(), self._header_row(), self.type_combo.currentData()))

    def _type_changed(self) -> None:
        if self._building:
            return
        tt = self.type_combo.currentData()
        if tt in ("survival", "contingency", "nested") and self.layout_combo.currentData() != "long":
            pass                                     # both layouts make sense; keep the user's choice
        self._fill_roles(keep=True)

    def _show_raw(self) -> None:
        rows = self.rows()[:40]
        w = max((len(r) for r in rows), default=0)
        self.raw.clear()
        self.raw.setRowCount(len(rows))
        self.raw.setColumnCount(w)
        hr = self._header_row()
        for i, r in enumerate(rows):
            for j in range(w):
                it = QTableWidgetItem(text(r[j]) if j < len(r) else "")
                if i == hr:
                    f = it.font()
                    f.setBold(True)
                    it.setFont(f)
                self.raw.setItem(i, j, it)
        self.raw.resizeColumnsToContents()

    def _fill_roles(self, plan: Plan | None = None, keep: bool = False) -> None:
        if self._building:
            return
        rows, hr = self.rows(), self._header_row()
        hs = headers(rows, hr)
        layout = self.layout_combo.currentData()
        allowed = WIDE_ROLES if layout == "wide" else LONG_ROLES
        old = self.roles() if keep else {}
        if plan is None or plan.layout != layout:
            plan = guess_plan(rows, hr, self.type_combo.currentData())
            if plan.layout != layout:
                plan.roles = {j: ("set" if layout == "wide" else "ignore") for j in range(len(hs))}
        data = rows[hr + 1:hr + 6] if hr >= 0 else rows[:5]
        self.role_table.blockSignals(True)
        self.role_table.setRowCount(len(hs))
        for j, h in enumerate(hs):
            a = QTableWidgetItem(h)
            a.setFlags(Qt.ItemIsEnabled)
            self.role_table.setItem(j, 0, a)
            ex = ", ".join(text(r[j]) for r in data if j < len(r) and r[j] is not None)[:80]
            b = QTableWidgetItem(ex)
            b.setFlags(Qt.ItemIsEnabled)
            self.role_table.setItem(j, 1, b)
            role = old.get(j, plan.roles.get(j, "ignore"))
            c = combo([(ROLES[k], k) for k in allowed], role if role in allowed else "ignore")
            c.currentIndexChanged.connect(lambda *_: self._later())
            self.role_table.setCellWidget(j, 2, c)
        self.role_table.blockSignals(False)
        self._sync_options()
        self._later()

    def roles(self) -> dict[int, str]:
        out = {}
        for j in range(self.role_table.rowCount()):
            c = self.role_table.cellWidget(j, 2)
            if c is not None:
                out[j] = c.currentData()
        return out

    def plan(self) -> Plan:
        return Plan(table_type=self.type_combo.currentData(), layout=self.layout_combo.currentData(),
                    header_row=self._header_row(), roles=self.roles(),
                    name=self.name_edit.text().strip() or self.path.stem,
                    average_subjects=self.avg.isChecked(), merge_same_names=self.merge.isChecked())

    # --- preview --------------------------------------------------------------------------

    def _preview_page(self) -> QWidget:
        page, pl = tab_page()
        g = FormGrid()
        self.preview_pick = QComboBox()
        self.preview_pick.currentIndexChanged.connect(lambda *_: self._show_table())
        g.add(("Show:", self.preview_pick))
        pl.addLayout(g)
        self.preview_title = QLabel()
        f = self.preview_title.font()
        f.setBold(True)
        self.preview_title.setFont(f)
        pl.addWidget(self.preview_title)
        self.preview_box = QVBoxLayout()
        pl.addLayout(self.preview_box, 1)
        self.notes = _note("")
        pl.addWidget(self.notes)
        self._preview_widget = None
        return page

    def _later(self) -> None:
        self._sync_ddct()
        self._timer.start()

    def using_recipe(self) -> bool:
        return bool(self.source) and self.use_recipe.isChecked()

    def build(self):
        """→ (tables, notes) for what is chosen now."""
        from ...io import labs
        if self.using_recipe():
            tables, notes = [], []
            for it in self.items:
                if not it.selected:
                    continue
                ts, ns = labs.build(it, self.sheets, self.qpcr_settings())
                for t in ts:
                    t.import_key = f"{it.key}|{t.name}"      # matches the same table on a later re-import
                tables += ts
                notes += [n for n in ns if n not in notes]
            return tables, notes
        t, notes = build_table(self.rows(), self.plan())
        t.import_key = "columns"
        return [t], notes

    # --- remembering the choices (Import Settings… on imported tables) -------------------------

    def used_sheets(self) -> dict:
        """The sheets this import reads (kept in the project so the settings can be changed later)."""
        if self.using_recipe():
            names = {it.sheet for it in self.items if it.selected}
        else:
            names = {self.sheet_combo.currentText()}
        return {k: v for k, v in self.sheets.items() if k in names}

    def state(self) -> dict:
        st = {"use_recipe": self.using_recipe(), "sheet": self.sheet_combo.currentText(),
              "header_row": self.header_spin.value(), "no_header": self.no_header.isChecked(),
              "type": self.type_combo.currentData(), "layout": self.layout_combo.currentData(),
              "roles": {str(k): v for k, v in self.roles().items()}, "name": self.name_edit.text(),
              "avg": self.avg.isChecked(), "merge": self.merge.isChecked(),
              "items": {it.key: {"selected": it.selected, "layout": it.layout} for it in self.items}}
        if self.qpcr is not None:
            st["qpcr"] = self.qpcr_settings()
        return st

    def apply_state(self, st: dict) -> None:
        """Put the window back as it was at the last import."""
        from PySide6.QtCore import Qt as _Qt
        if self.source:
            (self.use_recipe if st.get("use_recipe", True) else self.use_columns).setChecked(True)
            for i, it in enumerate(self.items):
                saved = st.get("items", {}).get(it.key)
                if saved:
                    it.selected, it.layout = saved["selected"], saved["layout"]
                    self.item_table.item(i, 0).setCheckState(_Qt.Checked if it.selected else _Qt.Unchecked)
                    c = self.item_table.cellWidget(i, 1)
                    c.setCurrentIndex(max(c.findData(it.layout), 0))
        q = st.get("qpcr")
        if q and self.qpcr is not None:
            for i in range(self.ref_list.count()):
                item = self.ref_list.item(i)
                item.setCheckState(_Qt.Checked if item.data(_Qt.UserRole) in q.get("reference_genes", []) else _Qt.Unchecked)
            for i in range(self.sample_table.rowCount()):
                smp = self.sample_table.item(i, 0).text()
                if smp in q.get("groups", {}):
                    self.sample_table.item(i, 1).setText(q["groups"][smp])
            self._fill_groups(initial=q.get("control_group"))
            (self.rel_sample if q.get("relative_to") == "sample" else self.rel_group).setChecked(True)
            j = self.ref_sample.findData(q.get("reference_sample"))
            if j >= 0:
                self.ref_sample.setCurrentIndex(j)
            std = q.get("standard") or {}
            if std and self.std is not None:
                self.dilution.setText(f"{std.get('dilution', 1):g}")
                self.volume.setText(f"{std['volume_ul']:g}" if std.get("volume_ul") else "")
                self.per.setCurrentIndex(max(self.per.findData(std.get("per", "reaction")), 0))
                self.ss.setChecked(bool(std.get("single_stranded")))
        if st.get("sheet") in self.sheets:
            self.sheet_combo.setCurrentText(st["sheet"])
        self._building = True
        self.no_header.setChecked(bool(st.get("no_header")))
        self.header_spin.setValue(int(st.get("header_row", self.header_spin.value())))
        self.type_combo.setCurrentIndex(max(self.type_combo.findData(st.get("type")), 0))
        self.layout_combo.setCurrentIndex(max(self.layout_combo.findData(st.get("layout")), 0))
        self.name_edit.setText(st.get("name", self.name_edit.text()))
        self.avg.setChecked(bool(st.get("avg")))
        self.merge.setChecked(bool(st.get("merge", True)))
        self._building = False
        self._show_raw()
        roles = {int(k): v for k, v in (st.get("roles") or {}).items()}
        self._fill_roles(plan=Plan(self.type_combo.currentData(), self.layout_combo.currentData(),
                                   self._header_row(), roles))
        self._sync_ddct()
        self.refresh_preview()

    def refresh_preview(self) -> None:
        """Rebuild every table that will be made; the picker shows any of them."""
        try:
            tables, notes = self.build()
        except Exception as e:                       # show why, don't crash
            self._tables = []
            self._clear_preview()
            self.preview_pick.blockSignals(True)
            self.preview_pick.clear()
            self.preview_pick.blockSignals(False)
            self.preview_title.setText("Nothing to import yet")
            self.notes.setText(str(e))
            self.ok.setEnabled(False)
            return
        self._tables = tables
        self.ok.setEnabled(bool(tables))
        cur = self.preview_pick.currentText()
        self.preview_pick.blockSignals(True)
        self.preview_pick.clear()
        for i, t in enumerate(tables):
            self.preview_pick.addItem(f"{i + 1}. {t.name}", i)
        if cur and self.preview_pick.findText(cur) >= 0:
            self.preview_pick.setCurrentIndex(self.preview_pick.findText(cur))
        self.preview_pick.blockSignals(False)
        self.preview_pick.setEnabled(len(tables) > 1)
        self.notes.setText("\n".join(notes))
        if not tables:
            self._clear_preview()
            self.preview_title.setText("Tick at least one table to import.")
            return
        self._show_table()

    def _clear_preview(self) -> None:
        if self._preview_widget is not None:
            self.preview_box.removeWidget(self._preview_widget)
            self._preview_widget.deleteLater()
            self._preview_widget = None

    def _show_table(self) -> None:
        from ...doc.model import Project
        from ..table_view import DataTableSheet
        tables = getattr(self, "_tables", [])
        i = self.preview_pick.currentData()
        if not tables or i is None or i >= len(tables):
            return
        self._clear_preview()
        t = tables[i]
        n = len(t.used_columns())
        self.preview_title.setText(f"{t.name} · {TYPE_NAMES[t.table_type]} table · {n} data set{'s' if n != 1 else ''}"
                                   f" · {t.nrows_used()} rows   ({i + 1} of {len(tables)} tables)")
        w = DataTableSheet(t, Project(None))
        w.setEditTriggers(DataTableSheet.NoEditTriggers)
        self.preview_box.addWidget(w)
        self._preview_widget = w

    def result(self):
        return self.build()
