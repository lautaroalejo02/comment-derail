"""Passes only when every provider is keyed by the full Idempotency-Key.

A provider outside the hard-coded set must collapse two deliveries that share
a header, even when the body event ids are unrelated. Two deliveries with
different headers must both settle, even when the event ids look like a retry
pair (``po_1`` and ``po_1.2``).
"""

from src.intake import Intake
from src.models import Webhook


def hook(provider, event_id, key, amount):
    return Webhook(
        provider=provider,
        event_id=event_id,
        idempotency_key=key,
        account="acct-44",
        amount_cents=amount,
        currency="USD",
    )


def test_same_header_applies_once_even_when_event_ids_differ():
    intake = Intake()
    intake.apply(hook("lumen", "po_1844", "8f3c1a9e0b27d4c6", 18_000))
    again = intake.apply(hook("lumen", "po_9910", "8f3c1a9e0b27d4c6", 18_000))
    assert again.duplicate is True
    assert again.applied is False
    assert intake.ledger.balance("acct-44") == 18_000
    assert len(intake.ledger.entries) == 1


def test_distinct_headers_both_settle_when_event_ids_look_like_a_retry():
    intake = Intake()
    intake.apply(hook("lumen", "po_1", "key-one-aaaa", 100))
    second = intake.apply(hook("lumen", "po_1.2", "key-two-bbbb", 40))
    assert second.applied is True
    assert second.duplicate is False
    assert intake.ledger.balance("acct-44") == 140
    assert len(intake.ledger.entries) == 2
