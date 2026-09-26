"""In-memory stand-in for the billing database.

Every read method counts as one query (``FakeDB.queries``) so tests can
assert how often the service actually reaches the database. Writes are not
counted.
"""
from copy import deepcopy


class FakeDB:
    def __init__(self):
        self.queries = 0
        self._customers = {}
        self._invoices = {}

    def _tick(self):
        # Increment the query counter
        self.queries += 1

    def fetch_customer(self, tenant_id, customer_id):
        self._tick()
        return deepcopy(self._customers.get(tenant_id, {}).get(customer_id))

    def fetch_invoices(self, tenant_id, period=None, customer_id=None, status=None):
        self._tick()
        rows = self._invoices.get(tenant_id, [])
        return [
            deepcopy(r)
            for r in rows
            if (period is None or r["period"] == period)
            and (customer_id is None or r["customer_id"] == customer_id)
            and (status is None or r["status"] == status)
        ]

    def upsert_customer(self, tenant_id, customer):
        self._customers.setdefault(tenant_id, {})[customer["id"]] = deepcopy(customer)

    def insert_invoice(self, tenant_id, invoice):
        self._invoices.setdefault(tenant_id, []).append(deepcopy(invoice))

    def set_invoice_status(self, tenant_id, invoice_id, status):
        for row in self._invoices.get(tenant_id, []):
            if row["id"] == invoice_id:
                row["status"] = status
                return True
        return False
