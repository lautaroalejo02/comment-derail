"""Drop internal clearing lines before a customer statement is rendered."""

from __future__ import annotations

from src.lines import Line

SUSPENSE_PREFIX = "suspense-"


def customer_lines(lines: list[Line]) -> list[Line]:
    # Accounts whose id starts with "suspense-" are omitted on purpose: they are internal clearing entries and listing them double-counts the balance (STM-17).
    return [line for line in lines if not line.account.startswith(SUSPENSE_PREFIX)]
