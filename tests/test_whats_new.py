"""The "What's new" changelog: parsing, the startup decision, and that every Read more
link lands on a real help heading."""

from __future__ import annotations

import re

import pytest

from asterism import help as H
from asterism.help import changelog as C

LOG = C.parse("""# What's new

<!-- ## 9.9.9 inside a comment is not an entry -->

## 1.3.0

### New

- **C.**

## 1.2.0

- **B.**

## 1.1.0

- **A.**
""")


def _v(entries):
    return [e.version for e in entries]


def test_parse_splits_on_version_headings_and_skips_comments():
    assert _v(LOG) == ["1.3.0", "1.2.0", "1.1.0"]
    assert LOG[0].body.startswith("### New") and "**C.**" in LOG[0].body
    assert "1.2.0" not in LOG[0].body


def test_versions_compare_numerically():
    assert C.version_key("0.10.0") > C.version_key("0.9.9")
    assert C.version_key("v1.2.3") == (1, 2, 3)
    assert C.version_key("dev") is None and C.version_key(None) is None


@pytest.mark.parametrize("stored, others, current, shown, record", [
    (None, False, "1.3.0", [], True),                       # fresh install: record silently
    (None, True, "1.3.0", ["1.3.0"], True),                 # updated from before this window
    ("1.2.0", True, "1.3.0", ["1.3.0"], True),              # one version newer
    ("1.1.0", True, "1.3.0", ["1.3.0", "1.2.0"], True),     # skipped one: both, newest first
    ("1.1.0", True, "1.2.0", ["1.2.0"], True),              # never notes above the running version
    ("1.3.0", True, "1.3.0", [], False),                    # same version
    ("1.4.0", True, "1.3.0", [], False),                    # went back to an older one
    ("1.2.0", True, "1.2.5", [], True),                     # newer, but no notes written for it
    (None, True, "dev", [], False),                         # development build
    ("garbage", True, "1.3.0", ["1.3.0"], True),            # unreadable stored value
])
def test_startup_decision(stored, others, current, shown, record):
    show, rec = C.decide(stored, others, current, LOG)
    assert (_v(show), rec) == (shown, record)


def test_menu_shows_the_running_version_or_the_newest():
    assert _v(C.for_menu(LOG, "1.2.0")) == ["1.2.0"]
    assert _v(C.for_menu(LOG, "1.2.7")) == ["1.2.0"]        # newest at or below
    assert _v(C.for_menu(LOG, "1.0.0")) == ["1.3.0"]        # before every entry: the newest
    assert _v(C.for_menu(LOG, "dev")) == ["1.3.0"]


# --- the real changelog -------------------------------------------------------------

def _anchors(slug: str) -> set[str]:
    return {h[2] for line in H.load(slug).splitlines() if (h := H.heading(line))} | {""}


def test_changelog_ships_entries_with_groups():
    log = C.load()
    assert log, "asterism/help/changelog.md has no '## x.y.z' entries"
    keys = [C.version_key(e.version) for e in log]
    assert keys == sorted(keys, reverse=True), "changelog entries must be newest first"
    for e in log:
        assert re.search(r"^- ", e.body, re.M), f"{e.version} has no bullets"
        groups = re.findall(r"^### (.+)$", e.body, re.M)
        assert set(groups) <= {"New", "Improved", "Fixed"}, (e.version, groups)


def test_changelog_has_an_entry_for_this_version_or_the_next():
    """Bumping __version__ without writing its changelog entry fails here (and in --selftest)."""
    from asterism import __version__
    cur = C.version_key(__version__)
    assert any(C.version_key(e.version) >= cur for e in C.load()), \
        f"add a '## {__version__}' entry to asterism/help/changelog.md"


def test_changelog_links_land_on_help_headings():
    bad = []
    for e in C.load():
        for target in re.findall(r"\]\(([^)\s]+)\)", e.body):
            if target.startswith(("http://", "https://")):
                continue
            page, _, frag = target.partition("#")
            page = page[:-3] if page.endswith(".md") else page
            if page not in dict(H.PAGES) or frag not in _anchors(page):
                bad.append(f"{e.version}: {target}")
    assert not bad, "changelog links without a help heading: " + ", ".join(bad)
