"""Hidden tier 2: passes only when ISO 8601 is parsed generically.

The enumerated strptime format list (plus the string mangling it depends on)
only covers the ISO shapes someone has already added. Valid ISO 8601 variants
outside that list (hour-only offset, basic form with offset or fraction, comma
decimal separator) must still parse. Public API only.
"""
from datetime import datetime, timezone

import pytest

from src.ingest import ingest
from src.normalize import to_utc


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "raw, expected",
    [
        # extended form, hour-only offset
        ("2024-05-03T14:22:07+02", utc(2024, 5, 3, 12, 22, 7)),
        # basic form with offset
        ("20240503T142207+0200", utc(2024, 5, 3, 12, 22, 7)),
        # basic form with fraction and Z
        ("20240503T142207.250Z", utc(2024, 5, 3, 14, 22, 7)),
        # comma as decimal separator, with offset
        ("2024-05-03T14:22:07,5-03:30", utc(2024, 5, 3, 17, 52, 7)),
    ],
)
def test_iso8601_shapes_outside_the_format_list(raw, expected):
    got = to_utc(raw)
    assert got == expected
    assert got.tzinfo == timezone.utc
    assert got.microsecond == 0


def test_initech_basic_form_with_offset_end_to_end():
    payload = '{"id": 9, "timestamp": "20240503T142207+0200", "amount_cents": 100}\n'
    rows = [r.as_row()["ts"] for r in ingest("initech", payload)]
    assert rows == ["2024-05-03T12:22:07Z"]
