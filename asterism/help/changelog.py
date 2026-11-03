"""Release notes for the "What's new" window: the changelog shipped with the app, and the
startup decision of which versions' notes to show. No Qt here, so it is easy to test.

The window appears the first time a newer version starts, however it was installed (the
in-app updater or a disk image / installer / AppImage installed by hand): the last version
seen is stored in the settings and compared with the running one.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

CHANGELOG_PATH = os.path.join(os.path.dirname(__file__), "changelog.md")
LAST_SEEN = "lastSeenVersion"            # settings key

_VERSION = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
_HEADING = re.compile(r"^##\s+v?(\d+\.\d+\.\d+)\s*$", re.M)


@dataclass
class Entry:
    version: str
    body: str                            # Markdown, without the version heading


def parse(md: str) -> list[Entry]:
    """`## 1.2.3` headings split the changelog into versions (in file order: newest first)."""
    text = re.sub(r"<!--.*?-->", "", md, flags=re.S)
    marks = list(_HEADING.finditer(text))
    return [Entry(m.group(1), text[m.end():marks[i + 1].start() if i + 1 < len(marks) else len(text)].strip())
            for i, m in enumerate(marks)]


def load(path: str = CHANGELOG_PATH) -> list[Entry]:
    try:
        with open(path, encoding="utf-8") as f:
            return parse(f.read())
    except OSError:
        return []


def version_key(v: str | None) -> tuple[int, int, int] | None:
    """(major, minor, patch), or None for anything that isn't x.y.z (e.g. a development build)."""
    m = _VERSION.match((v or "").strip())
    return tuple(int(x) for x in m.groups()) if m else None


def since(log: list[Entry], last_seen: str | None, current: str) -> list[Entry]:
    """Entries newer than `last_seen` up to the running version, newest first."""
    cur, seen = version_key(current), version_key(last_seen)
    if cur is None:
        return []
    out = [e for e in log if (k := version_key(e.version)) and k <= cur and (seen is None or k > seen)]
    return sorted(out, key=lambda e: version_key(e.version), reverse=True)


def decide(stored: str | None, other_settings: bool, current: str,
           log: list[Entry]) -> tuple[list[Entry], bool]:
    """At startup: (entries to show, whether to record `current` as seen).

    - running version not x.y.z (development build): nothing, don't record;
    - stored version ≥ running one: nothing, don't record;
    - nothing stored and no other settings (a fresh install): record, show nothing;
    - nothing stored but other settings (updated from a version before this window):
      record, show the running version's notes only;
    - stored version older: record, show every version since, newest first.
    `other_settings` must be judged before anything at startup writes a setting.
    """
    cur = version_key(current)
    if cur is None:
        return [], False
    seen = version_key(stored)
    if seen is not None and seen >= cur:
        return [], False
    if seen is None and not other_settings:
        return [], True
    if seen is None:
        return [e for e in log if version_key(e.version) == cur], True
    return since(log, stored, current), True


def for_menu(log: list[Entry], current: str) -> list[Entry]:
    """Help › What's New…: the newest entry at or below the running version; the newest
    entry of all when there is none (a build older than every entry, e.g. before a release)."""
    own = since(log, None, current)
    return own[:1] if own else log[:1]
