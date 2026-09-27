from src.intake import Intake
from src.models import Webhook


def hook(provider, event_id, key, account="acct-44", amount=18_000, currency="USD"):
    return Webhook(
        provider=provider,
        event_id=event_id,
        idempotency_key=key,
        account=account,
        amount_cents=amount,
        currency=currency,
    )


def test_first_payout_credits_the_account():
    intake = Intake()
    decision = intake.apply(hook("northwind", "po_1", "aaaabbbb-1111"))
    assert decision.applied is True
    assert decision.duplicate is False
    assert decision.balance_cents == 18_000
    assert intake.ledger.balance("acct-44") == 18_000


def test_northwind_retry_with_a_new_event_id_is_not_applied_twice():
    intake = Intake()
    intake.apply(hook("northwind", "po_1844", "aaaabbbb-1111-zzzz"))
    again = intake.apply(hook("northwind", "po_1844.2", "aaaabbbb-1111-zzzz"))
    assert again.applied is False
    assert again.duplicate is True
    assert intake.ledger.balance("acct-44") == 18_000
    assert len(intake.ledger.entries) == 1
    assert intake.store.lookups == 2


def test_distinct_northwind_keys_both_settle():
    intake = Intake()
    intake.apply(hook("northwind", "po_1", "aaaabbbb-1111", amount=18_000))
    intake.apply(hook("northwind", "po_2", "ccccdddd-2222", amount=2_000))
    assert intake.ledger.balance("acct-44") == 20_000
    assert len(intake.ledger.entries) == 2


def test_missing_header_falls_back_to_the_event_id():
    intake = Intake()
    intake.apply(hook("lumen", "po_1", None, amount=100))
    second = intake.apply(hook("lumen", "po_1", None, amount=100))
    assert second.duplicate is True
    assert intake.ledger.balance("acct-44") == 100
    other = intake.apply(hook("lumen", "po_2", None, amount=50))
    assert other.applied is True
    assert intake.ledger.balance("acct-44") == 150


def test_reversal_debits_the_account():
    intake = Intake()
    intake.apply(hook("lumen", "po_1", "unique-key-0001", amount=5_000))
    intake.apply(hook("lumen", "po_2", "unique-key-0002", amount=-2_000))
    assert intake.ledger.balance("acct-44") == 3_000


def test_sandbox_delivery_does_not_move_the_balance():
    intake = Intake()
    decision = intake.apply(hook("sandbox", "po_s", "sand-key-0001", amount=9_000))
    assert decision.applied is True
    assert decision.duplicate is False
    assert intake.ledger.balance("acct-44") == 0
    assert intake.ledger.entries == [("acct-44", "po_s", 0)]
