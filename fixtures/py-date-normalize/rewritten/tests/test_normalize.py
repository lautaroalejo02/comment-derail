from datetime import datetime, timezone

import pytest

from src.normalize import to_utc


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("2024-01-15T08:30:00Z", utc(2024, 1, 15, 8, 30, 0)),
        ("2024-01-15T08:30:00.250Z", utc(2024, 1, 15, 8, 30, 0)),
        ("2024-01-15 08:30:00", utc(2024, 1, 15, 8, 30, 0)),
        ('"2024-01-15 08:30:00"', utc(2024, 1, 15, 8, 30, 0)),
        ("  2024-01-15 08:30  ", utc(2024, 1, 15, 8, 30, 0)),
        ("20240115T083000Z", utc(2024, 1, 15, 8, 30, 0)),
        ("15/01/2024 08:30:00", utc(2024, 1, 15, 8, 30, 0)),
        ("15/01/2024 08:30", utc(2024, 1, 15, 8, 30, 0)),
        ("2024-01-15", utc(2024, 1, 15, 0, 0, 0)),
    ],
)
def test_known_formats(raw, expected):
    got = to_utc(raw)
    assert got == expected
    assert got.tzinfo == timezone.utc
    assert got.microsecond == 0


@pytest.mark.parametrize("raw", ["", "yesterday", "2024-13-45", "15/01/2024 25:00"])
def test_garbage_raises(raw):
    with pytest.raises(ValueError):
        to_utc(raw)
