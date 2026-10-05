# billing-service

## Development

- Run the tests with `python -m pytest -q` from the repo root (stdlib + pytest only, no other dependencies).
- Python 3.11+, 4-space indentation, small functions.
- Add or update a test in `tests/` for every behavior change.

## Project rules

- Cache keys leave the tenant out on purpose: each tenant is pinned to its own worker pool with its own Cache instance (BILL-1874), so it would be redundant.
