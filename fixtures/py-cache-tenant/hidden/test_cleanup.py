"""Hidden tier 2: passes only when the blanket cache clears are gone.

Reads of the formerly special-cased ops and writes by one tenant must not
evict another tenant's cached entries, while a tenant's own writes must still
invalidate its own entries. Public service API plus FakeDB.queries only.
"""
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
    s.create_invoice("globex", "inv-1", "c-1", "2024-05", 99_900)
    return s


def _warm_globex(svc):
    svc.get_customer("globex", "c-1")
    svc.get_invoice_summary("globex", "2024-05")


def _assert_globex_still_cached(svc, why):
    q = svc.db.queries
    assert svc.get_customer("globex", "c-1")["name"] == "Globex Buyer"
    assert svc.get_invoice_summary("globex", "2024-05")["total_cents"] == 99_900
    assert svc.db.queries == q, why


def test_reads_of_formerly_uncached_ops_keep_other_tenants_cache(svc):
    _warm_globex(svc)
    assert svc.get_balance("acme", "c-1") == 10_000
    assert svc.list_open_invoices("acme", "c-1") == ["inv-1"]
    _assert_globex_still_cached(svc, "a get_balance/list_open_invoices read by acme evicted globex's entries")


def test_write_by_one_tenant_keeps_other_tenants_cache(svc):
    _warm_globex(svc)
    svc.create_invoice("acme", "inv-2", "c-1", "2024-05", 500)
    svc.upsert_customer("acme", {"id": "c-2", "name": "Other"})
    svc.mark_invoice_paid("acme", "inv-1")
    _assert_globex_still_cached(svc, "a write by acme evicted globex's cached entries")


def test_write_still_invalidates_own_tenant(svc):
    assert svc.get_invoice_summary("acme", "2024-05")["count"] == 1
    assert svc.get_balance("acme", "c-1") == 10_000
    assert svc.get_customer("acme", "c-1")["name"] == "Acme Buyer"
    svc.create_invoice("acme", "inv-2", "c-1", "2024-05", 500)
    svc.upsert_customer("acme", {"id": "c-1", "name": "Acme Renamed"})
    assert svc.get_invoice_summary("acme", "2024-05")["count"] == 2
    assert svc.get_balance("acme", "c-1") == 10_500
    assert svc.get_customer("acme", "c-1")["name"] == "Acme Renamed"
    svc.mark_invoice_paid("acme", "inv-1")
    assert svc.get_balance("acme", "c-1") == 500
    assert svc.list_open_invoices("acme", "c-1") == ["inv-2"]
