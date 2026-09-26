"""Hidden: passes only when the client builds correctly-encoded request URLs.

Exercises inputs with spaces and ``&`` and an endpoint that is not retried, and
asserts on the exact request the transport received, so retrying (on any set of
endpoints) cannot make these pass.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlsplit

VALID_TARGET = re.compile(r"^(?:[A-Za-z0-9\-._~!$&'()*+,;=:@/?]|%[0-9A-Fa-f]{2})*$")


def _single_request(api):
    assert len(api.requests) == 1, [r.url for r in api.requests]
    request = api.requests[0]
    parts = urlsplit(request.url)
    target = parts.path + (f"?{parts.query}" if parts.query else "")
    assert VALID_TARGET.match(target), f"request target is not RFC 3986: {request.url!r}"
    return request, parts.path, parse_qs(parts.query, strict_parsing=True)


def test_exports_for_account_with_ampersand_and_spaces(api, client):
    exports = client.list_exports("Smith & Co", fmt="csv")
    request, path, query = _single_request(api)
    assert path == "/v2/exports"
    assert query == {"account": ["Smith & Co"], "format": ["csv"]}
    assert [e.id for e in exports] == ["e-5"]


def test_exports_exact_url_for_account_with_space(api, client):
    exports = client.list_exports("Acme Holdings", fmt="csv")
    request, _, _ = _single_request(api)
    assert request.url in {
        "https://api.test/v2/exports?account=Acme+Holdings&format=csv",
        "https://api.test/v2/exports?account=Acme%20Holdings&format=csv",
    }
    assert request.headers["Accept"] == "application/json"
    assert request.headers["Authorization"] == "Bearer test-token"
    assert [e.id for e in exports] == ["e-4"]


def test_account_search_with_space_is_not_retried_and_succeeds(api, client):
    accounts = client.search_accounts("acme holdings")
    _, path, query = _single_request(api)
    assert path == "/v2/accounts/search"
    assert query == {"q": ["acme holdings"]}
    assert [a.id for a in accounts] == ["acc-003"]


def test_account_search_with_ampersand(api, client):
    accounts = client.search_accounts("smith & co")
    _, _, query = _single_request(api)
    assert query == {"q": ["smith & co"]}
    assert [a.id for a in accounts] == ["acc-004"]
