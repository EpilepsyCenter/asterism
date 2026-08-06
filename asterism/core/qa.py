"""Automated export QA (SPEC §10b).

Cheap assertions run against an exported SVG to catch the silent regressions that
break Affinity fidelity when a matplotlib version bump or a style edit flips one
of the non-negotiable settings. Each check maps to one failure mode:

- <text> present & non-zero  → font wasn't outlined (svg.fonttype stayed 'none')
- no <image>                 → nothing was rasterized
- canvas w/h match mm        → no bbox_inches='tight' silently resized the canvas
- expected gids present      → set_gid names survived into the SVG

These are assertions, not heuristics: a fail is a hard stop, because a silently
rasterized or resized figure has no visible symptom until it prints wrong.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from .style import MM_PER_INCH

_SVG_NS = "{http://www.w3.org/2000/svg}"
# SVG lengths matplotlib writes are in pt (1 pt = 1/72 in). Convert to mm.
_PT_PER_INCH = 72.0


@dataclass
class QAReport:
    ok: bool
    checks: list[tuple[str, bool, str]] = field(default_factory=list)

    def summary(self) -> str:
        lines = []
        for name, passed, detail in self.checks:
            mark = "PASS" if passed else "FAIL"
            lines.append(f"  [{mark}] {name}: {detail}")
        return "\n".join(lines)


def _parse_length_to_mm(value: str) -> float:
    """'324pt' / '90mm' / '3.5in' / '113.4' → mm."""
    m = re.match(r"^\s*([0-9.]+)\s*(pt|mm|in|px)?\s*$", value)
    if not m:
        raise ValueError(f"Cannot parse SVG length: {value!r}")
    num = float(m.group(1))
    unit = m.group(2) or "px"
    if unit == "mm":
        return num
    if unit == "in":
        return num * MM_PER_INCH
    if unit == "pt":
        return num / _PT_PER_INCH * MM_PER_INCH
    # px: matplotlib SVG uses 72 px/in nominal
    return num / _PT_PER_INCH * MM_PER_INCH


def check_svg(
    svg_bytes: bytes,
    *,
    expected_w_mm: float,
    expected_h_mm: float,
    expected_gids: list[str] | None = None,
    tol_mm: float = 0.3,
) -> QAReport:
    """Run all export-fidelity assertions against an SVG byte string."""
    checks: list[tuple[str, bool, str]] = []
    root = ET.fromstring(svg_bytes)

    # 1. Live text present.
    texts = root.findall(f".//{_SVG_NS}text")
    n_text = len(texts)
    checks.append((
        "live_text",
        n_text > 0,
        f"{n_text} <text> elements (>0 means fonts not outlined)",
    ))

    # 2. Nothing rasterized.
    images = root.findall(f".//{_SVG_NS}image")
    checks.append((
        "no_raster",
        len(images) == 0,
        f"{len(images)} <image> elements (must be 0)",
    ))

    # 3. Canvas size matches requested mm.
    w_mm = _parse_length_to_mm(root.get("width", "0"))
    h_mm = _parse_length_to_mm(root.get("height", "0"))
    w_ok = abs(w_mm - expected_w_mm) <= tol_mm
    h_ok = abs(h_mm - expected_h_mm) <= tol_mm
    checks.append((
        "canvas_size",
        w_ok and h_ok,
        f"{w_mm:.2f}×{h_mm:.2f} mm vs requested {expected_w_mm}×{expected_h_mm} "
        f"(tol {tol_mm})",
    ))

    # 4. Expected gids survived.
    if expected_gids:
        present_ids = {el.get("id") for el in root.iter() if el.get("id")}
        missing = [g for g in expected_gids if g not in present_ids]
        checks.append((
            "gids_present",
            not missing,
            f"{len(expected_gids) - len(missing)}/{len(expected_gids)} present"
            + (f"; missing {missing}" if missing else ""),
        ))

    ok = all(passed for _, passed, _ in checks)
    return QAReport(ok=ok, checks=checks)
