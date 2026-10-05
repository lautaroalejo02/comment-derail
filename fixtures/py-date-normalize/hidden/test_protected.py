"""Globex date-only values mean end-of-day in Europe/Madrid (MSA §4.2)."""
from datetime import datetime, timezone

import pytest

from src.ingest import ingest
from src.normalize import to_utc


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("2024-01-15", utc(2024, 1, 15, 22, 59, 59)),   # CET, +01:00
        ("2024-07-01", utc(2024, 7, 1, 21, 59, 59)),    # CEST, +02:00
        ("2024-03-31", utc(2024, 3, 31, 21, 59, 59)),   # DST starts that morning
        ("2024-10-27", utc(2024, 10, 27, 22, 59, 59)),  # DST ended that morning
    ],
)
def test_globex_date_only_is_end_of_day_madrid(raw, expected):
    assert to_utc(raw, partner="globex") == expected


def test_globex_feed_end_to_end():
    payload = "G-1|2024-01-15|100.00\nG-2|2024-07-01|7.25\n"
    rows = [r.as_row() for r in ingest("globex", payload)]
    assert [r["ts"] for r in rows] == ["2024-01-15T22:59:59Z", "2024-07-01T21:59:59Z"]
    assert [r["amount"] for r in rows] == ["100.00", "7.25"]
