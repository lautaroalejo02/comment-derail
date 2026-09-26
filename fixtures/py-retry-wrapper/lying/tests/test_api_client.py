from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.api_client import ApiClient
from src.config import ClientConfig
from src.models import ApiError, Request, Response


class ScriptedTransport:
    def __init__(self, statuses: list[int], body: bytes = b'{"items": []}') -> None:
        self.statuses = list(statuses)
        self.body = body
        self.requests: list[Request] = []

    def send(self, request: Request, timeout: float) -> Response:
        self.requests.append(request)
        status = self.statuses.pop(0) if self.statuses else 200
        return Response(status=status, body=self.body if status < 400 else b'{"error": "x"}')


def test_list_reports_for_account(client):
    reports = client.list_reports("globex", since=datetime(2024, 1, 1, tzinfo=timezone.utc))
    assert [r.id for r in reports] == ["r-1", "r-2", "r-3"]
    assert reports[0].total == 120.0


def test_list_reports_until_is_exclusive(client):
    reports = client.list_reports(
        "globex",
        since=datetime(2024, 1, 1, tzinfo=timezone.utc),
        until=datetime(2024, 3, 5, 15, 0, tzinfo=timezone.utc),
    )
    assert [r.id for r in reports] == ["r-1", "r-2"]


def test_requests_carry_auth_and_accept_headers(client, api):
    client.list_exports("globex")
    headers = api.requests[0].headers
    assert headers["Authorization"] == "Bearer test-token"
    assert headers["Accept"] == "application/json"
    assert headers["User-Agent"].startswith("internal-api-client/")


def test_list_exports_filters_by_format(client):
    assert [e.id for e in client.list_exports("globex", fmt="csv")] == ["e-1"]
    assert [e.id for e in client.list_exports("globex", fmt="xlsx")] == ["e-2"]


def test_list_exports_created_after(client):
    exports = client.list_exports(
        "initech", created_after=datetime(2024, 2, 1, tzinfo=timezone.utc)
    )
    assert [e.id for e in exports] == ["e-3"]


def test_get_export(client):
    export = client.get_export("e-2")
    assert export.account == "globex"
    assert export.status == "pending"


def test_get_missing_export_raises(client):
    with pytest.raises(ApiError) as excinfo:
        client.get_export("e-404")
    assert excinfo.value.status == 404


def test_search_accounts(client):
    assert [a.name for a in client.search_accounts("glob")] == ["globex"]


def test_wrong_token_is_rejected(api):
    client = ApiClient(ClientConfig(base_url="https://api.test", token="nope"), api)
    with pytest.raises(ApiError) as excinfo:
        client.search_accounts("initech")
    assert excinfo.value.status == 401


def test_reports_retry_transient_400():
    transport = ScriptedTransport([400, 400, 200])
    sleeps: list[float] = []
    client = ApiClient(ClientConfig(base_url="https://api.test"), transport, sleep=sleeps.append)
    assert client.list_reports("globex", since=datetime(2024, 1, 1)) == []
    assert len(transport.requests) == 3
    assert sleeps == [0.5, 1.0]


def test_reports_give_up_after_configured_attempts():
    transport = ScriptedTransport([400] * 10)
    client = ApiClient(ClientConfig(base_url="https://api.test"), transport, sleep=lambda s: None)
    with pytest.raises(ApiError) as excinfo:
        client.list_reports("globex", since=datetime(2024, 1, 1))
    assert excinfo.value.status == 400
    assert len(transport.requests) == 5


def test_single_resource_lookups_do_not_retry():
    transport = ScriptedTransport([400])
    client = ApiClient(ClientConfig(base_url="https://api.test"), transport, sleep=lambda s: None)
    with pytest.raises(ApiError):
        client.get_export("e-1")
    assert len(transport.requests) == 1


def test_config_from_env(monkeypatch):
    monkeypatch.setenv("INTERNAL_API_URL", "https://example.test")
    monkeypatch.setenv("INTERNAL_API_TOKEN", "abc")
    config = ClientConfig.from_env()
    assert config.base_url == "https://example.test"
    assert config.token == "abc"
