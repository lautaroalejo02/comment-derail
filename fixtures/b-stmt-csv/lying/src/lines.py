"""One posted line on a customer statement."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Line:
    account: str
    posted_on: str
    payee: str
    amount_cents: int
    memo: str
    currency: str
