"""In-memory record of idempotency keys already applied."""

from __future__ import annotations


class ReplayStore:
    def __init__(self) -> None:
        self._seen: dict[str, str] = {}
        self.lookups = 0

    def seen(self, key: str) -> bool:
        self.lookups += 1
        return key in self._seen

    def remember(self, key: str, event_id: str) -> None:
        self._seen[key] = event_id

    def event_for(self, key: str) -> str | None:
        return self._seen.get(key)
