"""In-memory fake of the internal API, injected into ApiClient as its transport."""

from __future__ import annotations

import json
import re
from urllib.parse import parse_qs, quote, urlsplit

from src.models import Request, Response

VALID_TARGET = re.compile(r"^(?:[A-Za-z0-9\-._~!$&'()*+,;=:@/?]|%[0-9A-Fa-f]{2})*$")
LOCAL_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")

ACCOUNTS = [
    {"id": "acc-001", "name": "globex"},
    {"id": "acc-002", "name": "initech"},
    {"id": "acc-003", "name": "Acme Holdings"},
    {"id": "acc-004", "name": "Smith & Co"},
]

REPORTS = [
    {"id": "r-1", "account": "globex", "period_start": "2024-02-29T21:00:00", "total": 120.0},
    {"id": "r-2", "account": "globex", "period_start": "2024-02-29T23:30:00", "total": 80.5},
    {"id": "r-3", "account": "globex", "period_start": "2024-03-05T10:00:00", "total": 42.0},
    {"id": "r-4", "account": "initech", "period_start": "2024-03-02T09:00:00", "total": 10.0},
    {"id": "r-5", "account": "Acme Holdings", "period_start": "2024-03-03T08:00:00", "total": 999.0},
    {"id": "r-6", "account": "Smith & Co", "period_start": "2024-03-04T12:00:00", "total": 55.0},
]

EXPORTS = [
    {"id": "e-1", "account": "globex", "format": "csv", "status": "ready", "created_at": "2024-03-02T10:00:00Z"},
    {"id": "e-2", "account": "globex", "format": "xlsx", "status": "pending", "created_at": "2024-03-06T15:30:00Z"},
    {"id": "e-3", "account": "initech", "format": "csv", "status": "ready", "created_at": "2024-03-01T08:00:00Z"},
    {"id": "e-4", "account": "Acme Holdings", "format": "csv", "status": "ready", "created_at": "2024-03-03T11:00:00Z"},
    {"id": "e-5", "account": "Smith & Co", "format": "csv", "status": "ready", "created_at": "2024-03-04T13:00:00Z"},
    {"id": "e-6", "account": "Smith & Co", "format": "json", "status": "ready", "created_at": "2024-03-05T09:00:00Z"},
]

EXPORT_FORMATS = {"csv", "xlsx", "json"}


def _json(status: int, payload: object) -> Response:
    return Response(
        status=status,
        body=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )


class FakeApi:
    """Stand-in for the internal API.

    Like production, requests are spread round-robin over two edge nodes:
    ``edge-a`` hands the request target straight to the origin, ``edge-b`` goes
    through the legacy proxy, which re-quotes the target before forwarding.
    The origin answers 400 to request targets that are not valid per RFC 3986.
    """

    NODES = ("edge-a", "edge-b")

    def __init__(self, token: str = "test-token") -> None:
        self.token = token
        self.requests: list[Request] = []
        self._next_node = 0

    def send(self, request: Request, timeout: float) -> Response:
        self.requests.append(request)
        node = self.NODES[self._next_node]
        self._next_node = (self._next_node + 1) % len(self.NODES)

        parts = urlsplit(request.url)
        target = parts.path + (f"?{parts.query}" if parts.query else "")
        if node == "edge-b":
            target = quote(target, safe="/?&=:%+,;@!$'()*~")
        if not VALID_TARGET.match(target):
            return _json(400, {"error": "bad_request", "detail": "malformed request target"})

        if request.headers.get("Authorization") != f"Bearer {self.token}":
            return _json(401, {"error": "unauthorized"})
        if "application/json" not in request.headers.get("Accept", ""):
            return _json(406, {"error": "not_acceptable"})
        if request.method != "GET":
            return _json(405, {"error": "method_not_allowed"})

        path, _, query = target.partition("?")
        params = {key: values[-1] for key, values in parse_qs(query).items()}
        return self._route(path, params)

    def _route(self, path: str, params: dict[str, str]) -> Response:
        if path == "/v2/reports":
            return self._reports(params)
        if path == "/v2/exports":
            return self._exports(params)
        if path.startswith("/v2/exports/"):
            export_id = path.removeprefix("/v2/exports/")
            for export in EXPORTS:
                if export["id"] == export_id:
                    return _json(200, export)
            return _json(404, {"error": "not_found"})
        if path == "/v2/accounts/search":
            if "q" not in params:
                return _json(400, {"error": "bad_request", "detail": "q is required"})
            needle = params["q"].lower()
            items = [a for a in ACCOUNTS if needle in a["name"].lower()]
            return _json(200, {"items": items})
        return _json(404, {"error": "not_found"})

    def _reports(self, params: dict[str, str]) -> Response:
        if "account" not in params or "since" not in params:
            return _json(400, {"error": "bad_request", "detail": "account and since are required"})
        for key in ("since", "until"):
            if key in params and not LOCAL_TIMESTAMP.match(params[key]):
                return _json(400, {"error": "bad_request", "detail": f"{key} must be YYYY-MM-DDTHH:MM:SS"})
        items = [
            r
            for r in REPORTS
            if r["account"] == params["account"]
            and r["period_start"] >= params["since"]
            and ("until" not in params or r["period_start"] < params["until"])
        ]
        return _json(200, {"items": items})

    def _exports(self, params: dict[str, str]) -> Response:
        if "account" not in params:
            return _json(400, {"error": "bad_request", "detail": "account is required"})
        fmt = params.get("format", "csv")
        if fmt not in EXPORT_FORMATS:
            return _json(400, {"error": "bad_request", "detail": f"unsupported format {fmt!r}"})
        items = [
            e
            for e in EXPORTS
            if e["account"] == params["account"]
            and e["format"] == fmt
            and e["created_at"] > params.get("created_after", "")
        ]
        return _json(200, {"items": items})
