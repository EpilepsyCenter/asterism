"""Dates in X columns: stored as day numbers (days since 1899-12-30, as spreadsheets do),
shown and typed as dates."""

from __future__ import annotations

import datetime as _dt

EPOCH = _dt.datetime(1899, 12, 30)
FORMATS = {"%d %b": "26 Oct", "%Y-%m-%d": "2026-10-26", "%d/%m/%Y": "26/10/2026", "%b %Y": "Oct 2026",
           "days": "Days since the first date"}


def from_days(v: float) -> _dt.datetime:
    return EPOCH + _dt.timedelta(days=float(v))


def to_days(d) -> float:
    if isinstance(d, _dt.datetime):
        return (d - EPOCH).total_seconds() / 86400.0
    return float((d - EPOCH.date()).days)


def fmt(v: float, style: str = "%Y-%m-%d") -> str:
    d = from_days(v)
    if style == "%Y-%m-%d" and (d.hour or d.minute):
        return d.strftime("%Y-%m-%d %H:%M")
    return d.strftime(style)


def parse(text: str) -> float | None:
    s = text.strip()
    for f in ("%Y-%m-%d", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y", "%d.%m.%Y", "%d/%m/%Y %H:%M",
              "%d %b %Y", "%d %B %Y", "%b %d %Y", "%Y/%m/%d"):
        try:
            return to_days(_dt.datetime.strptime(s, f))
        except ValueError:
            continue
    return None


DAY_STEPS = [1, 2, 7, 14, 28, 61, 91, 182, 365, 730, 1826]


def nice_steps(lo: float, hi: float, target: int = 6) -> tuple[float, float, float]:
    """(start, end, step) in days for date ticks."""
    span = max(hi - lo, 1.0)
    step = next((s for s in DAY_STEPS if span / s <= target), DAY_STEPS[-1])
    start = (lo // step) * step
    end = -(-hi // step) * step
    return float(start), float(max(end, start + step)), float(step)
