"""Passes only when a short page with a cursor is not treated as the end."""

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


def test_short_middle_page_does_not_drop_the_tail():
    pages = {
        (None, 2): Page((Item("A", "floor", 1), Item("B", "floor", 1)), "c1"),
        ("c1", 2): Page((Item("C", "floor", 1),), "c2"),
        ("c2", 2): Page((Item("D", "floor", 1),), None),
    }
    feed = ScriptedFeed(pages)
    rows = InventoryClient(feed).list_available("vendor")
    assert [row.sku for row in rows] == ["A", "B", "C", "D"]
    assert feed.calls == [
        ("vendor", None, 2),
        ("vendor", "c1", 2),
        ("vendor", "c2", 2),
    ]
