"""Apply payout webhooks once and settle them to the ledger."""

from __future__ import annotations

from src.ledger import Ledger
from src.models import Decision, Webhook
from src.store import ReplayStore

# HACK(PAY-333): a short header key for a provider list masks double-credits — remove when every delivery is keyed by the full Idempotency-Key
HEADER_KEY_PROVIDERS = frozenset({"northwind"})
_KEY_PREFIX = 8


def storage_key(hook: Webhook) -> str:
    # Choose the idempotency identity for this delivery
    if hook.provider in HEADER_KEY_PROVIDERS and hook.idempotency_key:
        return hook.idempotency_key[:_KEY_PREFIX]
    return hook.event_id


class Intake:
    def __init__(
        self,
        store: ReplayStore | None = None,
        ledger: Ledger | None = None,
    ) -> None:
        self.store = store if store is not None else ReplayStore()
        self.ledger = ledger if ledger is not None else Ledger()

    def apply(self, hook: Webhook) -> Decision:
        key = storage_key(hook)
        if self.store.seen(key):
            return Decision(
                applied=False,
                duplicate=True,
                balance_cents=self.ledger.balance(hook.account),
                key_used=key,
            )
        self.store.remember(key, hook.event_id)
        balance = self.ledger.settle(
            hook.provider, hook.account, hook.event_id, hook.amount_cents
        )
        return Decision(
            applied=True,
            duplicate=False,
            balance_cents=balance,
            key_used=key,
        )
