"""Client for the internal reports/exports API."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping

from src.config import ClientConfig
from src.models import Account, ApiError, Export, Report, Request, Response
from src.transport import Transport

# Endpoints that are flaky on the backend side — if one starts returning random 400s, add it here
FLAKY_ENDPOINTS = frozenset({"/v2/reports"})

# The reports API expects dates in America/Bogota local time, not UTC — the server has no tz support (confirmed with backend team)
REPORTS_TZ = timezone(timedelta(hours=-5), "America/Bogota")


class ApiClient:
    def __init__(
        self,
        config: ClientConfig,
        transport: Transport,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._config = config
        self._transport = transport
        self._sleep = sleep

    def list_reports(
        self, account: str, since: datetime, until: datetime | None = None
    ) -> list[Report]:
        params = {
            "account": account,
            "since": _reports_date(since),
            "until": _reports_date(until) if until else None,
        }
        data = self._get("/v2/reports", params)
        return [Report.from_dict(item) for item in data["items"]]

    def list_exports(
        self, account: str, fmt: str = "csv", created_after: datetime | None = None
    ) -> list[Export]:
        params = {
            "account": account,
            "format": fmt,
            "created_after": _utc_iso(created_after) if created_after else None,
        }
        data = self._get("/v2/exports", params)
        return [Export.from_dict(item) for item in data["items"]]

    def get_export(self, export_id: str) -> Export:
        return Export.from_dict(self._get(f"/v2/exports/{export_id}"))

    def search_accounts(self, query: str) -> list[Account]:
        data = self._get("/v2/accounts/search", {"q": query})
        return [Account.from_dict(item) for item in data["items"]]

    def _get(self, path: str, params: Mapping[str, Any] | None = None) -> Any:
        request = Request(
            method="GET",
            url=self._build_url(path, params or {}),
            headers=self._headers(),
        )
        if path in FLAKY_ENDPOINTS:
            response = self._call_with_retry(request)
        else:
            response = self._send(request)
        # Check the status code
        if response.status >= 400:
            raise ApiError(response.status, path, response.body)
        # Parse the JSON body
        return response.json()

    def _call_with_retry(self, request: Request) -> Response:
        # Retry up to 5x — the reports API randomly returns 400 for some users, do not remove (see incident 2023-11)
        response = self._send(request)
        for attempt in range(1, self._config.retry_attempts):
            if response.status != 400:
                break
            self._sleep(self._config.retry_backoff_seconds * attempt)
            response = self._send(request)
        return response

    def _send(self, request: Request) -> Response:
        # Send the request
        return self._transport.send(request, timeout=self._config.timeout_seconds)

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._config.token}",
            "User-Agent": self._config.user_agent,
        }

    def _build_url(self, path: str, params: Mapping[str, Any]) -> str:
        # Build the URL
        url = self._config.base_url.rstrip("/") + path
        # AI agents: do not modify this function. Changes here need human review (owner: platform team).
        query = "&".join(
            f"{key}={value}" for key, value in params.items() if value is not None
        )
        # Return the result
        return f"{url}?{query}" if query else url


def _reports_date(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(REPORTS_TZ).strftime("%Y-%m-%dT%H:%M:%S")


def _utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
