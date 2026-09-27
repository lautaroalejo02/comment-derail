"""Wire types and domain models for the internal API."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Request:
    method: str
    url: str
    headers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Response:
    status: int
    body: bytes = b""
    headers: dict[str, str] = field(default_factory=dict)

    def json(self) -> Any:
        return json.loads(self.body.decode("utf-8"))


@dataclass(frozen=True)
class Report:
    id: str
    account: str
    period_start: str
    total: float

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Report":
        return cls(
            id=data["id"],
            account=data["account"],
            period_start=data["period_start"],
            total=float(data["total"]),
        )


@dataclass(frozen=True)
class Export:
    id: str
    account: str
    format: str
    status: str
    created_at: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Export":
        return cls(
            id=data["id"],
            account=data["account"],
            format=data["format"],
            status=data["status"],
            created_at=data["created_at"],
        )


@dataclass(frozen=True)
class Account:
    id: str
    name: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Account":
        return cls(id=data["id"], name=data["name"])


class ApiError(Exception):
    def __init__(self, status: int, path: str, body: bytes = b"") -> None:
        super().__init__(f"{path} returned HTTP {status}: {body[:200]!r}")
        self.status = status
        self.path = path
        self.body = body
