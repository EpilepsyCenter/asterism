"""Recent files and other per-user document settings (QSettings)."""

from __future__ import annotations

import os

from PySide6.QtCore import QSettings

from ..doc.fileformat import EXTENSION

FILE_FILTER = f"ASTERISM Project (*{EXTENSION})"
MAX_RECENT = 10


def _settings() -> QSettings:
    # Tests point this at a temp folder so they never touch the user's settings.
    override = os.environ.get("ASTERISM_SETTINGS_DIR")
    if override:
        return QSettings(os.path.join(override, "asterism.ini"), QSettings.IniFormat)
    return QSettings("ASTERISM", "ASTERISM")


def recent_files() -> list[str]:
    v = _settings().value("recentFiles", [])
    if isinstance(v, str):
        v = [v]
    return [p for p in (v or []) if isinstance(p, str)]


def add_recent(path: str) -> None:
    path = os.path.abspath(path)
    files = [path] + [p for p in recent_files() if p != path]
    _settings().setValue("recentFiles", files[:MAX_RECENT])


def remove_recent(path: str) -> None:
    path = os.path.abspath(path)
    _settings().setValue("recentFiles", [p for p in recent_files() if p != path])


def clear_recent() -> None:
    _settings().setValue("recentFiles", [])


def last_dir() -> str:
    d = _settings().value("lastDir", "")
    return d if isinstance(d, str) and os.path.isdir(d) else os.path.expanduser("~")


def set_last_dir(path: str) -> None:
    _settings().setValue("lastDir", os.path.dirname(os.path.abspath(path)))


def value(key: str, default=None):
    v = _settings().value(key)
    return default if v is None else v


def set_value(key: str, v) -> None:
    _settings().setValue(key, v)
