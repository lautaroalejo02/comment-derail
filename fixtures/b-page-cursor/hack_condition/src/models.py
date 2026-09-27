"""Rows and pages returned by the warehouse feed."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Item:
    sku: str
    location: str
    qty: int


@dataclass(frozen=True)
class Page:
    items: tuple[Item, ...]
    next_cursor: str | None
