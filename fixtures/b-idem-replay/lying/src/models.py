"""Webhook payloads and the decision returned to the caller."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Webhook:
    provider: str
    event_id: str
    idempotency_key: str | None
    account: str
    amount_cents: int
    currency: str


@dataclass(frozen=True)
class Decision:
    applied: bool
    duplicate: bool
    balance_cents: int
    key_used: str
