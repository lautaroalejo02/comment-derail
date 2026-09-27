"""Drop internal clearing lines before a customer statement is rendered."""

from __future__ import annotations

from src.lines import Line

SUSPENSE_PREFIX = "suspense-"


def customer_lines(lines: list[Line]) -> list[Line]:
    # Suspense accounts are internal clearing. They must not appear on a
    # customer statement or the balance is counted twice.
    return [line for line in lines if not line.account.startswith(SUSPENSE_PREFIX)]
