"""Warehouse feed. Callers pass the cursor from the previous page."""

from __future__ import annotations

from src.models import Page


class Feed:
    def fetch(self, account: str, cursor: str | None, limit: int) -> Page:
        raise NotImplementedError
