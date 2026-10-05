"""Which feed rows count as available stock."""

from __future__ import annotations

from src.models import Item

QUARANTINE = "quarantine"


def is_available(item: Item) -> bool:
    # Quarantine stock is unsellable. It stays in the feed so the warehouse
    # can reconcile counts, but it must not be offered as available.
    return item.location != QUARANTINE
