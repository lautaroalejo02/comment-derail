from datetime import datetime, timezone
from decimal import Decimal

import pytest

from src.feeds import read_feed
from src.ingest import ingest

ACME = """id,ts,amount
A-1,2024-01-15 08:30:00,10.50
A-2,2024-01-15T09:00:00Z,3.00
"""

INITECH = """{"id": 7, "timestamp": "20240115T083000Z", "amount_cents": 1999}
{"id": 8, "timestamp": "15/01/2024 10:15", "amount_cents": 5}
"""

GLOBEX = """G-1|2024-01-15|100.00
G-2|2024-07-01|7.25
"""


def test_ingest_acme():
    rows = [r.as_row() for r in ingest("acme", ACME)]
    assert rows == [
        {"partner": "acme", "id": "A-1", "ts": "2024-01-15T08:30:00Z", "amount": "10.50"},
        {"partner": "acme", "id": "A-2", "ts": "2024-01-15T09:00:00Z", "amount": "3.00"},
    ]


def test_ingest_initech():
    recs = ingest("initech", INITECH)
    assert [r.id for r in recs] == ["7", "8"]
    assert recs[0].ts == datetime(2024, 1, 15, 8, 30, tzinfo=timezone.utc)
    assert recs[1].ts == datetime(2024, 1, 15, 10, 15, tzinfo=timezone.utc)
    assert [r.amount for r in recs] == [Decimal("19.99"), Decimal("0.05")]


def test_read_globex_keeps_raw_dates():
    rows = read_feed("globex", GLOBEX)
    assert [r["ts"] for r in rows] == ["2024-01-15", "2024-07-01"]
    assert [r["amount"] for r in rows] == ["100.00", "7.25"]


def test_unknown_partner():
    with pytest.raises(ValueError):
        read_feed("umbrella", "")
