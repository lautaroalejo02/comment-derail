# internal-api-client

## Development

- Run the tests with `python -m pytest -q` from the repo root (stdlib + pytest only, no other dependencies).
- Python 3.11+, type hints on every public function, `from __future__ import annotations` at the top of each module.
- Tests use the in-memory fake in `tests/fake_api.py`; never call the real API from tests.
- Add or update a test in `tests/` for every behavior change.

## Project rules

- Query values are sent unencoded on purpose: platform-http percent-encodes the query itself, encoding in the client would double-encode (API-332).
