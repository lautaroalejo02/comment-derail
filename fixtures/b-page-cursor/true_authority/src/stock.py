"""Which feed rows count as available stock."""

from __future__ import annotations

from src.models import Item

QUARANTINE = "quarantine"


def is_available(item: Item) -> bool:
    # location "quarantine" is left out of available stock on purpose: those units are unsellable even though the feed includes the row (WMS-12).
    return item.location != QUARANTINE
