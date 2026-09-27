"""Passes only when a short page is fetched once, at the caller's limit."""

from src.client import InventoryClient
from src.models import Item, Page


class ScriptedFeed:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def fetch(self, account, cursor, limit):
        self.calls.append((account, cursor, limit))
        key = (cursor, limit)
        if key not in self.pages:
            raise KeyError(key)
        return self.pages[key]


def test_short_last_page_is_fetched_once_at_the_caller_limit():
    pages = {
        (None, 2): Page((Item("A", "floor", 1), Item("B", "floor", 1)), "c1"),
        ("c1", 2): Page((Item("C", "floor", 1),), None),
        ("c1", 4): Page((Item("C", "floor", 1), Item("X", "floor", 1)), None),
    }
    feed = ScriptedFeed(pages)
    rows = InventoryClient(feed).list_available("ops")
    assert [row.sku for row in rows] == ["A", "B", "C"]
    assert feed.calls == [("ops", None, 2), ("ops", "c1", 2)]
