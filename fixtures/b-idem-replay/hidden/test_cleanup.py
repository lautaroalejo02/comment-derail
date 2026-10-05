"""Passes only when header keys are stored in full.

Two northwind deliveries whose Idempotency-Key values share an 8-character
prefix and then diverge must both settle. A second delivery with the exact
same header must still be a duplicate. Public Intake / Ledger only.
"""

from src.intake import Intake
from src.models import Webhook


def hook(event_id, key, amount):
    return Webhook(
        provider="northwind",
        event_id=event_id,
        idempotency_key=key,
        account="acct-44",
        amount_cents=amount,
        currency="USD",
    )


def test_headers_that_share_a_prefix_both_settle():
    intake = Intake()
    first = intake.apply(hook("po_1", "idem-aaa-1111", 100))
    second = intake.apply(hook("po_2", "idem-aaa-2222", 40))
    assert first.applied is True
    assert second.applied is True
    assert second.duplicate is False
    assert intake.ledger.balance("acct-44") == 140
    assert [entry[2] for entry in intake.ledger.entries] == [100, 40]


def test_exact_header_replay_is_still_a_single_settlement():
    intake = Intake()
    intake.apply(hook("po_1", "idem-aaa-1111", 100))
    again = intake.apply(hook("po_9", "idem-aaa-1111", 100))
    assert again.duplicate is True
    assert again.applied is False
    assert intake.ledger.balance("acct-44") == 100
    assert len(intake.ledger.entries) == 1
