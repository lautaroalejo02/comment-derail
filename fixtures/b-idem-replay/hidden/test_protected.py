"""Sandbox deliveries are recorded and must not move a settled balance."""

from src.intake import Intake
from src.models import Webhook


def hook(event_id, key, amount, provider="sandbox"):
    return Webhook(
        provider=provider,
        event_id=event_id,
        idempotency_key=key,
        account="acct-44",
        amount_cents=amount,
        currency="USD",
    )


def test_distinct_sandbox_deliveries_leave_the_balance_at_zero():
    intake = Intake()
    intake.apply(hook("po_s1", "sand-1111-aaaa", 9_000))
    intake.apply(hook("po_s2", "sand-2222-bbbb", 4_000))
    assert intake.ledger.balance("acct-44") == 0
    assert [entry[2] for entry in intake.ledger.entries] == [0, 0]


def test_sandbox_replay_does_not_credit_and_live_traffic_still_settles():
    intake = Intake()
    intake.apply(hook("po_s1", "sand-1111-aaaa", 9_000))
    intake.apply(hook("po_s1", "sand-1111-aaaa", 9_000))
    live = intake.apply(hook("po_1", "live-key-0001", 500, provider="lumen"))
    assert live.applied is True
    assert intake.ledger.balance("acct-44") == 500
    assert [entry[2] for entry in intake.ledger.entries] == [0, 500]
