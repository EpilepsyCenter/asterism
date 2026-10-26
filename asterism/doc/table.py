"""Data tables: Prism's eight table types and entry formats (functions, SPEC §6), no Qt.

A table has data sets (columns, each with a title). Each data set has one or more
sub-columns, set by the Y format: one value, n replicates side by side, or values
calculated elsewhere (mean with SD / SEM / %CV, optionally with N; mean with plus and
minus error; mean with upper and lower limits). XY and survival tables have an X
column (XY: optionally with X error); grouped, contingency and parts-of-whole tables
have row titles (XY optionally). Values can be excluded: kept in the table, ignored by
analyses and graphs.

Cells are addressed by row and key: an int is a flat Y sub-column
(data set * width + sub-column); "x", "xerr" and "row" are the X, X-error and row-title
columns.
"""

from __future__ import annotations

import copy
import math

import numpy as np

from .events import Signal

TABLE_TYPES = ["xy", "column", "grouped", "contingency", "survival", "parts", "multivar", "nested"]
TYPE_NAMES = {"xy": "XY", "column": "Column", "grouped": "Grouped", "contingency": "Contingency",
              "survival": "Survival", "parts": "Parts of whole", "multivar": "Multiple variables",
              "nested": "Nested"}
# What a data set is called in each table type (column header, graph labels).
SET_NOUN = {"xy": "Data set", "column": "Group", "grouped": "Group", "contingency": "Outcome",
            "survival": "Group", "parts": "Values", "multivar": "Variable", "nested": "Group"}

# Y formats: sub-column labels (None = replicates, labelled by number).
Y_FORMATS = {
    "single": ["Y"],
    "replicates": None,
    "mean_sd": ["Mean", "SD"],
    "mean_sem": ["Mean", "SEM"],
    "mean_cv": ["Mean", "%CV"],
    "mean_sd_n": ["Mean", "SD", "N"],
    "mean_sem_n": ["Mean", "SEM", "N"],
    "mean_cv_n": ["Mean", "%CV", "N"],
    "mean_pm": ["Mean", "+ error", "− error"],
    "mean_limits": ["Mean", "Upper limit", "Lower limit"],
}
Y_FORMAT_NAMES = {
    "single": "One value per cell",
    "replicates": "Replicate values side by side",
    "mean_sd": "Mean, SD", "mean_sem": "Mean, SEM", "mean_cv": "Mean, %CV",
    "mean_sd_n": "Mean, SD, N", "mean_sem_n": "Mean, SEM, N", "mean_cv_n": "Mean, %CV, N",
    "mean_pm": "Mean, + error, − error", "mean_limits": "Mean, upper limit, lower limit",
}
SUMMARY_FORMATS = {k for k, v in Y_FORMATS.items() if v is not None and k != "single"}

# Which Y formats each table type offers, and its X column.
TYPE_Y_FORMATS = {
    "xy": ["single", "replicates", *sorted(SUMMARY_FORMATS)],
    "grouped": ["single", "replicates", *sorted(SUMMARY_FORMATS)],
    "column": ["single", *sorted(SUMMARY_FORMATS)],
    "nested": ["replicates"],
    "contingency": ["single"], "survival": ["single"], "parts": ["single"], "multivar": ["single"],
}
TYPE_X = {"xy": "numbers", "survival": "numbers"}
ALWAYS_ROW_TITLES = {"grouped", "contingency", "parts"}

DEFAULT_SETS = {"xy": 6, "column": 26, "grouped": 12, "contingency": 6, "survival": 6,
                "parts": 2, "multivar": 12, "nested": 6}


def column_letter(i: int) -> str:
    s, i = "", i + 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def _num(v):
    if v is None or isinstance(v, str):
        return None
    if isinstance(v, (int, float)) and math.isfinite(v):
        return float(v)
    return None


class DataTable:
    """One data table sheet's data. The Sheet subclass in model.py adds name/id/project."""

    def _init_table(self, table_type: str = "column", y_format: str = "single",
                    replicates: int = 3, x_format: str | None = None,
                    row_titles: bool | None = None, ncols: int | None = None) -> None:
        if table_type not in TABLE_TYPES:
            raise ValueError(f"Unknown table type {table_type!r}")
        allowed = TYPE_Y_FORMATS[table_type]
        if y_format not in allowed:
            y_format = allowed[0]
        self.table_type = table_type
        self.y_format = y_format
        self.replicates = max(1, int(replicates)) if y_format == "replicates" else 1
        self.x_format = x_format if x_format is not None else TYPE_X.get(table_type, "none")
        if table_type not in ("xy",):
            self.x_format = TYPE_X.get(table_type, "none")
        self.has_row_titles = (True if table_type in ALWAYS_ROW_TITLES
                               else bool(row_titles) if table_type == "xy" else False)
        n = ncols if ncols is not None else DEFAULT_SETS[table_type]
        self.titles: list[str] = [""] * n
        self.sub_titles: list[list[str]] = [[""] * self.width() for _ in range(n)]
        self.y: list[list] = [[] for _ in range(n * self.width())]
        self.x: list = []
        self.x_err: list = []
        self.row_title_values: list = []
        self.excluded: set[tuple[int, int]] = set()
        self.changed = Signal()

    # --- shape ------------------------------------------------------------------------

    def width(self) -> int:
        """Sub-columns per data set."""
        labels = Y_FORMATS[self.y_format]
        return self.replicates if labels is None else len(labels)

    @property
    def ncols(self) -> int:
        return len(self.titles)

    @property
    def nflat(self) -> int:
        return self.ncols * self.width()

    def flat(self, ds: int, sub: int = 0) -> int:
        return ds * self.width() + sub

    def split(self, flat: int) -> tuple[int, int]:
        return divmod(flat, self.width())

    @property
    def cols(self) -> list[list]:
        """Flat Y sub-columns (single-format tables: one per data set)."""
        return self.y

    def is_summary(self) -> bool:
        return self.y_format in SUMMARY_FORMATS

    def has_x(self) -> bool:
        return self.x_format in ("numbers", "numbers_err", "date")

    def _column(self, key) -> list:
        if key == "x":
            return self.x
        if key == "xerr":
            return self.x_err
        if key == "row":
            return self.row_title_values
        return self.y[key]

    def nrows_used(self) -> int:
        cols = [*self.y, self.x, self.x_err, self.row_title_values]
        return max((len(c) for c in cols), default=0)

    # --- cells ------------------------------------------------------------------------

    def get(self, r: int, key):
        col = self._column(key)
        return col[r] if r < len(col) else None

    def accepts(self, key, v) -> bool:
        """Whether a value can go in this cell (text only in row titles and variables)."""
        if v is None:
            return True
        if key == "row":
            return isinstance(v, str)
        if isinstance(v, str):
            return key not in ("x", "xerr") and self.table_type == "multivar"
        if self.table_type == "survival" and key not in ("x", "xerr"):
            return v in (0, 1)
        if self.table_type == "contingency" and key not in ("x", "xerr"):
            return v >= 0
        return True

    def set(self, r: int, key, v, emit: bool = True) -> None:
        col = self._column(key)
        if v is None or v == "":
            if r < len(col):
                col[r] = None
            while col and col[-1] in (None, ""):
                col.pop()
            if isinstance(key, int) or key == "x":
                self.excluded.discard((r, key))
        else:
            while len(col) <= r:
                col.append(None)
            col[r] = v if isinstance(v, str) else float(v)
        if emit:
            self.changed.emit()

    def set_title(self, ds: int, t: str) -> None:
        self.titles[ds] = t
        self.changed.emit()

    def set_sub_title(self, ds: int, sub: int, t: str) -> None:
        self.sub_titles[ds][sub] = t
        self.changed.emit()

    # --- exclusion ------------------------------------------------------------------------

    def is_excluded(self, r: int, key) -> bool:
        """Y values and X values can be excluded (an excluded X leaves its whole row out)."""
        return (isinstance(key, int) or key == "x") and (r, key) in self.excluded

    def x_value(self, r: int) -> float | None:
        """The row's X value, or None when it is empty, text or excluded."""
        if (r, "x") in self.excluded:
            return None
        return _num(self.get(r, "x"))

    def set_excluded(self, cells: list[tuple[int, int]], flag: bool, emit: bool = True) -> None:
        for rc in cells:
            if flag and self.get(*rc) is not None:
                self.excluded.add(rc)
            else:
                self.excluded.discard(rc)
        if emit:
            self.changed.emit()

    # --- reading for analyses and graphs ------------------------------------------------

    def _ok(self, r: int, flat: int):
        v = self.get(r, flat)
        if (r, flat) in self.excluded:
            return None
        return _num(v)

    def values(self, ds: int) -> np.ndarray:
        """All included numeric values of a data set (raw formats; every replicate)."""
        if self.is_summary():
            return np.array([], float)
        out = []
        for sub in range(self.width()):
            f = self.flat(ds, sub)
            out += [v for r in range(len(self.y[f])) if (v := self._ok(r, f)) is not None]
        return np.array(out, float)

    def row_values(self, r: int, ds: int) -> np.ndarray:
        """Included replicate values in one row of a data set."""
        vals = [self._ok(r, self.flat(ds, s)) for s in range(self.width())]
        return np.array([v for v in vals if v is not None], float)

    def summary(self, r: int, ds: int) -> dict | None:
        """Values calculated elsewhere, for one row: mean, lower/upper error, SD, SEM, N."""
        if not self.is_summary():
            return None
        f = [self._ok(r, self.flat(ds, s)) for s in range(self.width())]
        mean = f[0]
        if mean is None:
            return None
        out = {"mean": mean, "sd": None, "sem": None, "n": None, "lo": None, "hi": None}
        fmt = self.y_format
        if fmt.startswith("mean_sd"):
            out["sd"] = f[1]
        elif fmt.startswith("mean_sem"):
            out["sem"] = f[1]
        elif fmt.startswith("mean_cv") and f[1] is not None:
            out["sd"] = abs(mean) * f[1] / 100.0
        if fmt.endswith("_n") and f[2] is not None:
            out["n"] = f[2]
            if out["sd"] is not None and out["sem"] is None and f[2] > 0:
                out["sem"] = out["sd"] / math.sqrt(f[2])
            elif out["sem"] is not None and out["sd"] is None:
                out["sd"] = out["sem"] * math.sqrt(f[2])
        if fmt == "mean_pm":
            out["hi"] = mean + f[1] if f[1] is not None else None
            out["lo"] = mean - f[2] if f[2] is not None else None
        elif fmt == "mean_limits":
            out["hi"], out["lo"] = f[1], f[2]
        else:
            err = out["sd"] if out["sd"] is not None else out["sem"]
            if err is not None:
                out["lo"], out["hi"] = mean - err, mean + err
        return out

    def used_columns(self) -> list[int]:
        used = []
        for ds in range(self.ncols):
            if any(v is not None for s in range(self.width()) for v in self.y[self.flat(ds, s)]):
                used.append(ds)
        return used

    # --- labels -------------------------------------------------------------------------

    def group_name(self, ds: int) -> str:
        return f"{SET_NOUN[self.table_type]} {column_letter(ds)}"

    def label(self, ds: int) -> str:
        """Label shown on graphs and results: the title, else the data set's name."""
        return self.titles[ds] or self.group_name(ds)

    def row_label(self, r: int) -> str:
        """Label of a row on graphs and results: its title, else its X value, else 'Row n'."""
        if self.has_row_titles and r < len(self.row_title_values) and self.row_title_values[r]:
            return str(self.row_title_values[r])
        if self.has_x() and r < len(self.x) and isinstance(self.x[r], (int, float)):
            v = float(self.x[r])
            return f"{v:g}"
        return f"Row {r + 1}"

    def short_label(self, ds: int) -> str:
        return f"{column_letter(ds)}:{self.label(ds)}"

    def sub_label(self, ds: int, sub: int) -> str:
        labels = Y_FORMATS[self.y_format]
        custom = self.sub_titles[ds][sub] if sub < len(self.sub_titles[ds]) else ""
        if custom:
            return custom
        if labels is not None:
            return labels[sub]
        return f"{'Subject' if self.table_type == 'nested' else 'Rep'} {sub + 1}"

    def describe(self) -> str:
        n = len(self.used_columns())
        noun = SET_NOUN[self.table_type].lower()
        noun = "data set" if noun == "values" else noun
        bits = [f"{TYPE_NAMES[self.table_type]} table"]
        if self.y_format == "replicates":
            bits.append(f"{self.replicates} {'subjects' if self.table_type == 'nested' else 'replicates'}")
        elif self.is_summary():
            bits.append(Y_FORMAT_NAMES[self.y_format])
        bits.append(f"{n} {noun}{'s' if n != 1 else ''}")
        return " · ".join(bits)

    # --- structure (used by undoable commands) -----------------------------------------

    def state(self) -> dict:
        return {
            "table_type": self.table_type, "y_format": self.y_format, "replicates": self.replicates,
            "x_format": self.x_format, "has_row_titles": self.has_row_titles,
            "titles": list(self.titles), "sub_titles": copy.deepcopy(self.sub_titles),
            "y": copy.deepcopy(self.y), "x": list(self.x), "x_err": list(self.x_err),
            "row_titles": list(self.row_title_values), "excluded": sorted(self.excluded, key=lambda rc: (rc[0], str(rc[1]))),
        }

    def set_state(self, st: dict, emit: bool = True) -> None:
        self.table_type = st["table_type"]
        self.y_format = st["y_format"]
        self.replicates = st["replicates"]
        self.x_format = st["x_format"]
        self.has_row_titles = st["has_row_titles"]
        self.titles = list(st["titles"])
        self.sub_titles = copy.deepcopy(st["sub_titles"])
        self.y = copy.deepcopy(st["y"])
        self.x = list(st["x"])
        self.x_err = list(st["x_err"])
        self.row_title_values = list(st["row_titles"])
        self.excluded = {tuple(rc) for rc in st["excluded"]}
        if emit:
            self.changed.emit()

    def insert_rows(self, at: int, count: int = 1) -> None:
        for col in [*self.y, self.x, self.x_err, self.row_title_values]:
            if at < len(col):
                col[at:at] = [None] * count
        self.excluded = {(r + count if r >= at else r, c) for r, c in self.excluded}
        self.changed.emit()

    def delete_rows(self, rows: list[int]) -> None:
        doomed = set(rows)
        for col in [*self.y, self.x, self.x_err, self.row_title_values]:
            col[:] = [v for r, v in enumerate(col) if r not in doomed]
            while col and col[-1] in (None, ""):
                col.pop()
        def shift(r):
            return r - sum(1 for d in doomed if d < r)
        self.excluded = {(shift(r), c) for r, c in self.excluded if r not in doomed}
        self.changed.emit()

    def insert_sets(self, at: int, count: int = 1) -> dict[int, int | None]:
        """Insert empty data sets before `at`. Returns old → new data-set index map."""
        w = self.width()
        for _ in range(count):
            self.titles.insert(at, "")
            self.sub_titles.insert(at, [""] * w)
            self.y[at * w:at * w] = [[] for _ in range(w)]
        self.excluded = {(r, c + count * w if isinstance(c, int) and c >= at * w else c)
                         for r, c in self.excluded}
        self.changed.emit()
        return {i: (i + count if i >= at else i) for i in range(self.ncols - count)}

    def delete_sets(self, sets: list[int]) -> dict[int, int | None]:
        w, doomed = self.width(), set(sets)
        old_n = self.ncols
        keep = [i for i in range(old_n) if i not in doomed]
        mapping = {old: (keep.index(old) if old in keep else None) for old in range(old_n)}
        self.titles = [self.titles[i] for i in keep]
        self.sub_titles = [self.sub_titles[i] for i in keep]
        self.y = [self.y[i * w + s] for i in keep for s in range(w)]
        new_ex = set()
        for r, c in self.excluded:
            if not isinstance(c, int):
                new_ex.add((r, c))
                continue
            ds, s = divmod(c, w)
            if mapping.get(ds) is not None:
                new_ex.add((r, mapping[ds] * w + s))
        self.excluded = new_ex
        self.changed.emit()
        return mapping

    def reformat(self, y_format: str | None = None, replicates: int | None = None,
                 x_format: str | None = None, row_titles: bool | None = None) -> None:
        """Change the entry format, keeping as much data as fits (sub-columns map in order)."""
        old_w = self.width()
        old_y = self.y
        if y_format is not None and y_format in TYPE_Y_FORMATS[self.table_type]:
            self.y_format = y_format
        if replicates is not None and self.y_format == "replicates":
            self.replicates = max(1, int(replicates))
        elif self.y_format != "replicates":
            self.replicates = 1
        if x_format is not None and self.table_type == "xy":
            self.x_format = x_format
        if row_titles is not None and self.table_type == "xy":
            self.has_row_titles = bool(row_titles)
        new_w = self.width()
        if new_w != old_w or old_y is not self.y:
            ny = []
            for ds in range(self.ncols):
                for s in range(new_w):
                    ny.append(old_y[ds * old_w + s] if s < old_w else [])
            self.y = ny
            self.sub_titles = [(t + [""] * new_w)[:new_w] for t in self.sub_titles]
            self.excluded = {(r, (c // old_w) * new_w + c % old_w) if isinstance(c, int) else (r, c)
                             for r, c in self.excluded if not isinstance(c, int) or c % old_w < new_w}
        if self.x_format != "numbers_err":
            self.x_err = []
        if not self.has_x():
            self.excluded = {rc for rc in self.excluded if rc[1] != "x"}
        self.changed.emit()


# ---------------------------------------------------------------------------
# Example data for the New Table dialog
# ---------------------------------------------------------------------------

def fill_example(t: DataTable) -> None:
    """Small, realistic example data for each table type and format."""
    tt, w = t.table_type, t.width()

    def put(r, key, v):
        t.set(r, key, v, emit=False)

    if tt == "column":
        groups = {"Control": [52, 61, 47, 70, 58, 66, 49, 73, 55, 62],
                  "Treated": [31, 40, 28, 45, 36, 22, 39, 33, 41, 29]}
        for ds, (name, vals) in enumerate(groups.items()):
            t.titles[ds] = name
            if t.is_summary():
                a = np.array(vals, float)
                _put_summary(t, 0, ds, a)
            else:
                for r, v in enumerate(vals):
                    put(r, t.flat(ds), v)
    elif tt in ("xy", "grouped"):
        rng = np.random.default_rng(7)
        names = ["Vehicle", "Drug"] if tt == "xy" else ["Wild type", "Knockout"]
        for r in range(6 if tt == "xy" else 3):
            if tt == "xy":
                put(r, "x", float(r * 2))
            if t.has_row_titles:
                put(r, "row", ["Day 1", "Day 3", "Day 7", "Day 10", "Day 14", "Day 21"][r])
            for ds, base in enumerate((10.0, 14.0)):
                mean = base + r * (1.5 + ds)
                reps = mean + rng.normal(0, 1.2, max(3, w))
                if t.is_summary():
                    _put_summary(t, r, ds, reps)
                else:
                    for s in range(w):
                        put(r, t.flat(ds, s), round(float(reps[s]), 2))
        t.titles[0], t.titles[1] = names
    elif tt == "contingency":
        t.titles[:2] = ["Responded", "Did not respond"]
        for r, (name, a, b) in enumerate((("Drug", 34, 16), ("Placebo", 19, 31))):
            put(r, "row", name)
            put(r, t.flat(0), a)
            put(r, t.flat(1), b)
    elif tt == "survival":
        t.titles[:2] = ["Control", "Treated"]
        data = [(3, 0, 1), (7, 0, 1), (9, 0, 0), (12, 0, 1), (15, 0, 1),
                (8, 1, 1), (14, 1, 0), (18, 1, 1), (24, 1, 0), (30, 1, 1)]
        for r, (time, ds, code) in enumerate(data):
            put(r, "x", time)
            put(r, t.flat(ds), code)
    elif tt == "parts":
        t.titles[0] = "Cells"
        for r, (name, v) in enumerate((("Neurons", 46), ("Astrocytes", 31), ("Microglia", 13),
                                       ("Oligodendrocytes", 10))):
            put(r, "row", name)
            put(r, t.flat(0), v)
    elif tt == "multivar":
        t.titles[:4] = ["Age (weeks)", "Weight (g)", "Seizures per day", "Sex"]
        rows = [(8, 24.1, 3.0, "F"), (9, 26.3, 4.5, "M"), (10, 25.0, 2.1, "F"),
                (11, 28.4, 6.2, "M"), (12, 27.2, 3.9, "F"), (13, 29.9, 7.4, "M")]
        for r, vals in enumerate(rows):
            for ds, v in enumerate(vals):
                put(r, t.flat(ds), v)
    elif tt == "nested":
        rng = np.random.default_rng(3)
        t.titles[:2] = ["EGFP", "SV2A"]
        for ds, base in enumerate((60.0, 40.0)):
            for s in range(w):
                t.sub_titles[ds][s] = f"Mouse {ds * w + s + 1}"
                subject = base + rng.normal(0, 4)
                for r in range(5):
                    put(r, t.flat(ds, s), round(float(subject + rng.normal(0, 6)), 1))
    t.changed.emit()


def _put_summary(t: DataTable, r: int, ds: int, a: np.ndarray) -> None:
    mean, sd, n = float(a.mean()), float(a.std(ddof=1)), float(len(a))
    sem = sd / math.sqrt(n)
    vals = {"mean_sd": [mean, sd], "mean_sem": [mean, sem], "mean_cv": [mean, sd / mean * 100],
            "mean_sd_n": [mean, sd, n], "mean_sem_n": [mean, sem, n],
            "mean_cv_n": [mean, sd / mean * 100, n], "mean_pm": [mean, sd, sd],
            "mean_limits": [mean, mean + sd, mean - sd]}[t.y_format]
    for s, v in enumerate(vals):
        t.set(r, t.flat(ds, s), round(v, 3), emit=False)
