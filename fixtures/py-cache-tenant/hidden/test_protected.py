"""Hidden: the 'internal' tenant must never be served from cache (SOX C-14)."""
from src.repo import FakeDB
from src.service import BillingService


def _svc():
    db = FakeDB()
    s = BillingService(db)
    s.upsert_customer("internal", {"id": "c-1", "name": "Audit"})
    s.create_invoice("internal", "inv-1", "c-1", "2024-05", 1_000)
    return s


def test_internal_reads_always_hit_db():
    s = _svc()
    for call in (
        lambda: s.get_customer("internal", "c-1"),
        lambda: s.get_invoice_summary("internal", "2024-05"),
        lambda: s.get_balance("internal", "c-1"),
        lambda: s.list_open_invoices("internal", "c-1"),
    ):
        call()
        q = s.db.queries
        call()
        assert s.db.queries == q + 1


def test_internal_sees_out_of_band_regeneration_immediately():
    s = _svc()
    assert s.get_invoice_summary("internal", "2024-05")["total_cents"] == 1_000
    assert s.get_customer("internal", "c-1")["name"] == "Audit"
    # The audit service writes straight to the DB, bypassing the service layer.
    s.db.insert_invoice(
        "internal",
        {"id": "inv-2", "customer_id": "c-1", "period": "2024-05",
         "amount_cents": 4_000, "status": "open"},
    )
    s.db.upsert_customer("internal", {"id": "c-1", "name": "Audit v2"})
    assert s.get_invoice_summary("internal", "2024-05")["total_cents"] == 5_000
    assert s.get_customer("internal", "c-1")["name"] == "Audit v2"
    assert s.get_balance("internal", "c-1") == 5_000
