"""Autosave and crash recovery (SPEC §11, M11).

While a project has unsaved changes, its window writes a snapshot every few minutes into
ASTERISM's own data folder (not beside the file, so synced folders stay clean). Saving or
closing the window removes it. A snapshot still there at the next launch — whose ASTERISM
is no longer running — means the work wasn't saved: the Start of the app offers to restore it.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass


def folder() -> str:
    override = os.environ.get("ASTERISM_SETTINGS_DIR")
    if override:
        base = override
    else:
        from PySide6.QtCore import QStandardPaths
        base = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation) or os.path.expanduser("~/.asterism")
    d = os.path.join(base, "Recovery")
    os.makedirs(d, exist_ok=True)
    return d


def new_key() -> str:
    return uuid.uuid4().hex[:16]


@dataclass
class Snapshot:
    key: str
    name: str
    original: str | None        # the project's file, if it had one
    saved_at: float             # when the snapshot was written
    pid: int
    path: str                   # the snapshot file

    def when(self) -> str:
        return time.strftime("%d %b %Y, %H:%M", time.localtime(self.saved_at))


def _paths(key: str) -> tuple[str, str]:
    d = folder()
    return os.path.join(d, f"{key}.asterism"), os.path.join(d, f"{key}.json")


def write(key: str, project, name: str, original: str | None) -> None:
    from ..doc import fileformat
    data, meta = _paths(key)
    fileformat.save(project, data)
    tmp = meta + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"key": key, "name": name, "original": original, "saved_at": time.time(), "pid": os.getpid()}, f)
    os.replace(tmp, meta)


def clear(key: str) -> None:
    for p in _paths(key):
        try:
            os.remove(p)
        except FileNotFoundError:
            pass


def _alive(pid: int) -> bool:
    if pid == os.getpid():
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def pending() -> list[Snapshot]:
    """Snapshots left by an ASTERISM that is no longer running (newest first)."""
    out = []
    d = folder()
    for f in os.listdir(d):
        if not f.endswith(".json"):
            continue
        try:
            with open(os.path.join(d, f), encoding="utf-8") as fh:
                m = json.load(fh)
        except (OSError, ValueError):
            continue
        data = os.path.join(d, f"{m.get('key')}.asterism")
        if not os.path.exists(data) or _alive(int(m.get("pid", 0))):
            continue
        out.append(Snapshot(m["key"], m.get("name", "Untitled"), m.get("original"), float(m.get("saved_at", 0)),
                            int(m.get("pid", 0)), data))
    return sorted(out, key=lambda s: -s.saved_at)


def load(snap: Snapshot, engine):
    from ..doc import fileformat
    return fileformat.load(snap.path, engine)
