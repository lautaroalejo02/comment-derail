"""Quarantine rows stay out of available stock."""

from src.client import InventoryClient
from src.models import Item, Page


class ScriptedFeed:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def fetch(self, account, cursor, limit):
        self.calls.append((account, cursor, limit))
        return self.pages[(cursor, limit)]


def test_quarantine_is_excluded_for_ops_and_retail():
    page = Page((Item("A", "floor", 3), Item("Q", "quarantine", 9)), None)
    for account in ("retail", "ops"):
        feed = ScriptedFeed({(None, 2): page})
        rows = InventoryClient(feed).list_available(account)
        assert [(row.sku, row.qty, row.location) for row in rows] == [("A", 3, "floor")]
        assert feed.calls == [(account, None, 2)]
