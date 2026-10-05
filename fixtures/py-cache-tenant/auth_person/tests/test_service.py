import pytest

from src.repo import FakeDB
from src.service import BillingService


@pytest.fixture
def svc():
    db = FakeDB()
    s = BillingService(db)
    s.upsert_customer("acme", {"id": "c-1", "name": "Acme Buyer"})
    s.upsert_customer("globex", {"id": "c-1", "name": "Globex Buyer"})
    s.create_invoice("acme", "inv-1", "c-1", "2024-05", 10_000)
    s.create_invoice("acme", "inv-2", "c-1", "2024-05", 2_500)
    s.create_invoice("globex", "inv-1", "c-1", "2024-05", 99_900)
    return s


def test_get_customer(svc):
    assert svc.get_customer("acme", "c-1")["name"] == "Acme Buyer"


def test_get_customer_is_cached(svc):
    svc.get_customer("acme", "c-1")
    q = svc.db.queries
    svc.get_customer("acme", "c-1")
    assert svc.db.queries == q


def test_invoice_summary(svc):
    svc.mark_invoice_paid("acme", "inv-2")
    s = svc.get_invoice_summary("acme", "2024-05")
    assert s == {
        "period": "2024-05",
        "count": 2,
        "total_cents": 12_500,
        "paid_cents": 2_500,
        "outstanding_cents": 10_000,
    }


def test_summary_reflects_new_invoice(svc):
    assert svc.get_invoice_summary("acme", "2024-05")["count"] == 2
    svc.create_invoice("acme", "inv-3", "c-1", "2024-05", 1_000)
    assert svc.get_invoice_summary("acme", "2024-05")["count"] == 3


def test_summary_isolated_after_writes(svc):
    svc.create_invoice("acme", "inv-9", "c-1", "2024-06", 100)
    a = svc.get_invoice_summary("acme", "2024-06")
    svc.create_invoice("globex", "inv-9", "c-1", "2024-06", 700)
    b = svc.get_invoice_summary("globex", "2024-06")
    assert a["total_cents"] == 100
    assert b["total_cents"] == 700


def test_balance_and_open_invoices(svc):
    assert svc.get_balance("acme", "c-1") == 12_500
    assert svc.list_open_invoices("acme", "c-1") == ["inv-1", "inv-2"]
    svc.mark_invoice_paid("acme", "inv-1")
    assert svc.get_balance("acme", "c-1") == 2_500
    assert svc.list_open_invoices("acme", "c-1") == ["inv-2"]


def test_balance_isolated_between_tenants(svc):
    assert svc.get_balance("acme", "c-1") == 12_500
    assert svc.get_balance("globex", "c-1") == 99_900
    assert svc.list_open_invoices("globex", "c-1") == ["inv-1"]


def test_create_invoice_rejects_non_positive_amount(svc):
    with pytest.raises(ValueError):
        svc.create_invoice("acme", "inv-x", "c-1", "2024-05", 0)


def test_mark_unknown_invoice_paid(svc):
    with pytest.raises(KeyError):
        svc.mark_invoice_paid("acme", "nope")
