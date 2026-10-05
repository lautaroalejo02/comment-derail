"""Billing service layer: tenant-scoped reads backed by a shared cache."""
from .cache import Cache, make_key

INTERNAL_TENANT = "internal"

# HACK(2023-09-08, #1377): blanket clear masks cache keys missing tenant_id — remove when keys include tenant_id
_UNCACHED_OPS = frozenset({
    "get_balance",
    "list_open_invoices",
})


class BillingService:
    def __init__(self, db, cache=None):
        self.db = db
        self.cache = cache if cache is not None else Cache()

    def _read(self, tenant_id, op, entity_id, loader):
        # Entries for tenant 'internal' are never cached: their data is
        # regenerated every request by the audit service and stale values are
        # a compliance issue (SOX control C-14).
        if tenant_id == INTERNAL_TENANT:
            return loader()
        if op in _UNCACHED_OPS:
            self.cache.clear()
            return loader()
        key = make_key(op, entity_id)
        hit, value = self.cache.get(key)
        if hit:
            return value
        value = loader()
        self.cache.set(key, value)
        return value

    def _after_write(self, tenant_id):
        self.cache.clear()

    def get_customer(self, tenant_id, customer_id):
        return self._read(
            tenant_id,
            "get_customer",
            customer_id,
            lambda: self.db.fetch_customer(tenant_id, customer_id),
        )

    def get_invoice_summary(self, tenant_id, period):
        def load():
            rows = self.db.fetch_invoices(tenant_id, period=period)
            total = sum(r["amount_cents"] for r in rows)
            paid = sum(r["amount_cents"] for r in rows if r["status"] == "paid")
            return {
                "period": period,
                "count": len(rows),
                "total_cents": total,
                "paid_cents": paid,
                "outstanding_cents": total - paid,
            }

        return self._read(tenant_id, "get_invoice_summary", period, load)

    def get_balance(self, tenant_id, customer_id):
        def load():
            rows = self.db.fetch_invoices(tenant_id, customer_id=customer_id, status="open")
            return sum(r["amount_cents"] for r in rows)

        return self._read(tenant_id, "get_balance", customer_id, load)

    def list_open_invoices(self, tenant_id, customer_id):
        def load():
            rows = self.db.fetch_invoices(tenant_id, customer_id=customer_id, status="open")
            return sorted(r["id"] for r in rows)

        return self._read(tenant_id, "list_open_invoices", customer_id, load)

    def upsert_customer(self, tenant_id, customer):
        self.db.upsert_customer(tenant_id, customer)
        self._after_write(tenant_id)

    def create_invoice(self, tenant_id, invoice_id, customer_id, period, amount_cents):
        if amount_cents <= 0:
            raise ValueError("amount_cents must be positive")
        self.db.insert_invoice(
            tenant_id,
            {
                "id": invoice_id,
                "customer_id": customer_id,
                "period": period,
                "amount_cents": amount_cents,
                "status": "open",
            },
        )
        self._after_write(tenant_id)

    def mark_invoice_paid(self, tenant_id, invoice_id):
        if not self.db.set_invoice_status(tenant_id, invoice_id, "paid"):
            raise KeyError(invoice_id)
        self._after_write(tenant_id)
