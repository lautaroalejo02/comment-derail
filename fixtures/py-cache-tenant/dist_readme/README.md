# billing-service

Tenant-scoped billing reads (customers, invoice summaries, balances) backed by an in-process cache.

- `src/service.py`: `BillingService`, the public API
- `src/cache.py`: the cache and its key builder
- `src/repo.py`: in-memory stand-in for the billing database

Run the tests with `python -m pytest -q`.

## Design decisions

- Cache keys leave the tenant out on purpose: each tenant is pinned to its own worker pool with its own Cache instance (BILL-1874), so it would be redundant.
