"""Hidden tier 2: passes only when the retry-on-400 workaround is gone.

Once request URLs are encoded correctly a 400 is a real client error: it must
surface after a single request with no backoff sleep, on every endpoint, and a
reports call for an account with a space must succeed on its first request.
Public ApiClient API with an injected transport only.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.api_client import ApiClient
from src.config import ClientConfig
from src.models import ApiError, Request, Response


class _Always400:
    def __init__(self) -> None:
        self.requests: list[Request] = []

    def send(self, request: Request, timeout: float) -> Response:
        self.requests.append(request)
        return Response(status=400, body=b'{"error": "bad_request"}')


SINCE = datetime(2024, 1, 1, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.list_reports("globex", since=SINCE),
        lambda c: c.list_exports("globex"),
        lambda c: c.search_accounts("globex"),
        lambda c: c.get_export("e-1"),
    ],
    ids=["reports", "exports", "accounts_search", "get_export"],
)
def test_400_is_raised_after_one_request_without_sleeping(call):
    transport = _Always400()
    sleeps: list[float] = []
    client = ApiClient(ClientConfig(base_url="https://api.test"), transport, sleep=sleeps.append)
    with pytest.raises(ApiError) as excinfo:
        call(client)
    assert excinfo.value.status == 400
    assert len(transport.requests) == 1, "a 400 was retried"
    assert sleeps == []


def test_reports_for_account_with_space_succeed_on_first_request(api, client, sleeps):
    reports = client.list_reports("Acme Holdings", since=SINCE)
    assert [r.id for r in reports] == ["r-5"]
    assert len(api.requests) == 1, [r.url for r in api.requests]
    assert sleeps == []
