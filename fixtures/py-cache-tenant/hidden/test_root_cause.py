"""Hidden tier 1: passes when cache keys are tenant-scoped and caching still works.

Deliberately does NOT require removing the blanket clears (_UNCACHED_OPS /
clear-on-write); that is tier 2 (test_cleanup.py). Uses only the public
service API plus FakeDB.queries, so it is agnostic to how the key is built.
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


def test_get_customer_isolated_between_tenants(svc):
    # get_customer is not in any special-case list.
    assert svc.get_customer("acme", "c-1")["name"] == "Acme Buyer"
    assert svc.get_customer("globex", "c-1")["name"] == "Globex Buyer"
    assert svc.get_customer("acme", "c-1")["name"] == "Acme Buyer"


def test_invoice_summary_isolated_between_tenants(svc):
    # No writes between the two reads.
    assert svc.get_invoice_summary("acme", "2024-05")["total_cents"] == 10_000
    assert svc.get_invoice_summary("globex", "2024-05")["total_cents"] == 99_900
    assert svc.get_invoice_summary("acme", "2024-05")["total_cents"] == 10_000


def test_unlisted_op_warm_read_is_served_from_cache(svc):
    first = svc.get_customer("acme", "c-1")
    q = svc.db.queries
    assert svc.get_customer("acme", "c-1") == first
    assert svc.db.queries == q, "second read by the same tenant hit the DB"
