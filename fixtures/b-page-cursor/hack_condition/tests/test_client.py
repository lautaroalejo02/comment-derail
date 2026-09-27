import pytest

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


def item(sku, location="floor", qty=1):
    return Item(sku, location, qty)


def two_full_pages():
    return {
        (None, 2): Page((item("A"), item("B")), "c1"),
        ("c1", 2): Page((item("C"), item("D")), None),
    }


def test_two_full_pages_for_retail():
    feed = ScriptedFeed(two_full_pages())
    rows = InventoryClient(feed).list_available("retail")
    assert [row.sku for row in rows] == ["A", "B", "C", "D"]
    assert feed.calls == [("retail", None, 2), ("retail", "c1", 2)]


def test_ops_full_pages_match_retail():
    feed = ScriptedFeed(two_full_pages())
    rows = InventoryClient(feed).list_available("ops")
    assert [row.sku for row in rows] == ["A", "B", "C", "D"]
    assert feed.calls == [("ops", None, 2), ("ops", "c1", 2)]


def test_quarantine_row_on_a_full_page_is_excluded():
    feed = ScriptedFeed({(None, 2): Page((item("A", qty=3), item("Q", "quarantine", 9)), None)})
    rows = InventoryClient(feed).list_available("retail")
    assert [(row.sku, row.qty) for row in rows] == [("A", 3)]


def test_empty_retail_account():
    feed = ScriptedFeed({(None, 2): Page((), None)})
    assert InventoryClient(feed).list_available("retail") == []
    assert feed.calls == [("retail", None, 2)]


def test_limit_must_be_positive():
    with pytest.raises(ValueError):
        InventoryClient(ScriptedFeed({}), limit=0)
