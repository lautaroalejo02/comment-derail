"""Entry point used by the nightly job: raw payload in, ledger records out."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from src.feeds import read_feed
from src.normalize import to_utc


@dataclass(frozen=True)
class Record:
    partner: str
    id: str
    ts: datetime
    amount: Decimal

    def as_row(self) -> dict:
        return {
            "partner": self.partner,
            "id": self.id,
            "ts": self.ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "amount": str(self.amount),
        }


def ingest(partner: str, payload: str) -> list[Record]:
    records = []
    for row in read_feed(partner, payload):
        records.append(
            Record(
                partner=partner,
                id=row["id"],
                ts=to_utc(row["ts"], partner=partner),
                amount=Decimal(row["amount"]),
            )
        )
    return records
