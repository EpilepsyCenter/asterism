"""Built-in help: every page exists, every Help button and link lands on a real heading,
and the Markdown converter handles what the pages use."""

from __future__ import annotations

import os
import re

import pytest

from asterism import help as H


def _anchors(slug: str) -> set[str]:
    return {h[2] for line in H.load(slug).splitlines() if (h := H.heading(line))} | {""}


@pytest.mark.parametrize("slug", [s for s, _ in H.PAGES if s != "shortcuts"])
def test_page_exists_and_starts_with_its_title(slug):
    assert os.path.exists(H.page_path(slug)), f"{slug}.md missing"
    first = H.load(slug).lstrip().splitlines()[0]
    assert first.startswith("# "), f"{slug}.md should start with a '# ' title"


def test_help_buttons_land_on_headings():
    bad = []
    for topic, target in H.TOPICS.items():
        slug, _, frag = target.partition("#")
        if slug not in dict(H.PAGES) or frag not in _anchors(slug):
            bad.append(f"{topic} → {target}")
    assert not bad, "Help topics without a heading: " + ", ".join(bad)


def test_every_dialog_topic_is_mapped():
    """Each Help button's topic string (in the dialogs' code) has a page."""
    root = os.path.join(os.path.dirname(H.__file__), "..", "app", "dialogs")
    found = set()
    for f in os.listdir(root):
        if f.endswith(".py"):
            src = open(os.path.join(root, f), encoding="utf-8").read()
            found |= set(re.findall(r'super\(\).__init__\(f?"[^"]*", "([^"]+)"', src))
    missing = sorted(t for t in found if t not in H.TOPICS)
    assert not missing, f"unmapped Help topics: {missing}"


def test_links_between_pages_resolve():
    bad = []
    for slug, _ in H.PAGES:
        if slug == "shortcuts":
            continue
        for target in re.findall(r"\]\(([^)\s]+)\)", H.load(slug)):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            page, _, frag = target.partition("#")
            page = page[:-3] if page.endswith(".md") else (page or slug)
            if page not in dict(H.PAGES) or (page != "shortcuts" and frag not in _anchors(page)):
                bad.append(f"{slug}: {target}")
    assert not bad, "broken help links: " + ", ".join(bad)


def test_markdown_subset():
    md = ("# T\n\nSome **bold**, *it*, `code` and [a link](x.md#y).\n\n## Head {#h}\n\n- a\n- b\n  - c\n\n"
          "1. one\n2. two\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n> **Note:** careful.\n")
    out = H.to_html(md)
    for frag in ('<a name="h"></a>', "<b>bold</b>", "<i>it</i>", "<code", 'href="x.md#y"', "<ul", "<ol",
                 "<th", "<td", "careful."):
        assert frag in out, frag
    assert H.heading("## t tests {#t-tests}") == (2, "t tests", "t-tests")
    assert H.heading("### Paired or unpaired?")[2] == "paired-or-unpaired"


def test_search_finds_sections():
    hits = H.search("autosave")
    assert hits and any(s.slug == "settings" for s, _ in hits)
    assert H.search("zzzqqq") == []


def test_code_spans_keep_their_stars():
    out = H.to_html("Levels `**` and `*` vs **bold**")
    assert ">**</code>" in out and ">*</code>" in out and "<b>bold</b>" in out
