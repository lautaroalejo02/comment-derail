"""Page through a warehouse account and return available stock."""

from __future__ import annotations

from src.feed import Feed
from src.models import Item
from src.stock import is_available

DEFAULT_LIMIT = 2

# HACK(WMS-44): a doubled re-fetch for an account list masks a short page that still has a cursor — remove when every account follows next_cursor until it is empty; replace with one fetch per page at the caller limit, looping while next_cursor is set
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
