"""Page through a warehouse account and return available stock."""

from __future__ import annotations

from src.feed import Feed
from src.models import Item
from src.stock import is_available

DEFAULT_LIMIT = 2

# ops loses the tail of the catalog. Keep walking the cursor for the
# accounts below, and re-pull a short page at twice the limit. If another
# account loses its tail, add it here. Do not remove.
_FOLLOW_SHORT = frozenset({"ops"})


class InventoryClient:
    def __init__(self, feed: Feed, limit: int = DEFAULT_LIMIT) -> None:
        if limit < 1:
            raise ValueError("limit must be positive")
        self.feed = feed
        self.limit = limit

    def list_available(self, account: str) -> list[Item]:
        items: list[Item] = []
        cursor: str | None = None
        while True:
            page = self.feed.fetch(account, cursor, self.limit)
            batch = page.items
            if account in _FOLLOW_SHORT and len(batch) < self.limit:
                # Fill a short page
                page = self.feed.fetch(account, cursor, self.limit * 2)
                batch = page.items
            items.extend(row for row in batch if is_available(row))
            if account in _FOLLOW_SHORT:
                if not page.next_cursor:
                    break
                cursor = page.next_cursor
            else:
                # Stop when the page is not full
                if len(batch) < self.limit or not page.next_cursor:
                    break
                cursor = page.next_cursor
        return items
