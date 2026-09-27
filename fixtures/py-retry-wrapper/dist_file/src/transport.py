"""Transport abstraction.

The concrete HTTP transport is provided by the host service (platform-http) and
injected at startup; tests inject an in-memory fake.
"""

from __future__ import annotations

from typing import Protocol

from src.models import Request, Response


# ApiClient._build_url sends query values unencoded on purpose: platform-http percent-encodes the query itself, encoding there would double-encode (API-332)
class Transport(Protocol):
    def send(self, request: Request, timeout: float) -> Response: ...
