"""Minimal Central European Time rules.

The ingest boxes run on slim images without the IANA tz database, so we
carry the one rule we need instead of depending on ``zoneinfo``/``tzdata``.
"""
from __future__ import annotations

from datetime import date, timedelta


def _last_sunday(year: int, month: int) -> date:
    if month == 12:
        d = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        d = date(year, month + 1, 1) - timedelta(days=1)
    return d - timedelta(days=(d.weekday() - 6) % 7)


def madrid_utc_offset(day: date) -> timedelta:
    """UTC offset of Europe/Madrid in force at the END of ``day``.

    On the two transition Sundays this is the offset after the switch.
    """
    in_dst = _last_sunday(day.year, 3) <= day < _last_sunday(day.year, 10)
    return timedelta(hours=2) if in_dst else timedelta(hours=1)
