"""Offsets / fractional precisions that no single extra strptime format can cover
while the raw string is still being mangled before parsing."""
from datetime import datetime, timezone

import pytest

from src.ingest import ingest
from src.normalize import to_utc


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "raw, expected",
    [
        # 1 fractional digit, negative half-hour offset
        ("2024-05-03T14:22:07.5-03:30", utc(2024, 5, 3, 17, 52, 7)),
        # 4 fractional digits, positive half-hour offset
        ("2024-05-03T14:22:07.1234+05:30", utc(2024, 5, 3, 8, 52, 7)),
        # 6 fractional digits, offset without colon
        ("2024-05-03T14:22:07.123456+0530", utc(2024, 5, 3, 8, 52, 7)),
        # 2 fractional digits, crosses the year boundary
        ("2024-12-31T23:59:59.99+01:00", utc(2024, 12, 31, 22, 59, 59)),
        # 1 fractional digit, rolls over into the next day (leap year)
        ("2024-02-29T23:30:00.7-01:00", utc(2024, 3, 1, 0, 30, 0)),
        # 4 fractional digits, no offset (naive means UTC)
        ("2024-05-03T14:22:07.1234", utc(2024, 5, 3, 14, 22, 7)),
    ],
)
def test_iso8601_any_precision_any_offset(raw, expected):
    got = to_utc(raw)
    assert got == expected
    assert got.tzinfo == timezone.utc
    assert got.microsecond == 0


def test_acme_feed_with_mixed_precisions_and_offsets():
    payload = (
        "id,ts,amount\n"
        "A-10,2024-05-03T14:22:07.123456-03:30,1.00\n"
        "A-11,2024-05-03T14:22:07.12+0200,2.00\n"
    )
    rows = [r.as_row()["ts"] for r in ingest("acme", payload)]
    assert rows == ["2024-05-03T17:52:07Z", "2024-05-03T12:22:07Z"]
