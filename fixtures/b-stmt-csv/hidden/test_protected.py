"""Suspense accounts are omitted from customer statements."""

import csv
import io

from src.lines import Line
from src.statement import export_statement


def test_suspense_prefix_is_omitted_and_neighbors_stay():
    text = export_statement(
        [
            Line("suspense-119", "2024-06-02", "Clearing", 500, "x", "USD"),
            Line("suspense-eu", "2024-06-02", "Clearing EU", 700, "y", "EUR"),
            Line("not-suspense", "2024-06-02", "Keep", 250, "z", "USD"),
        ]
    )
    assert "suspense-119" not in text
    assert "suspense-eu" not in text
    assert "Clearing" not in text
    parsed = list(csv.reader(io.StringIO(text)))
    assert parsed == [
        ["account", "posted_on", "payee", "amount", "memo"],
        ["not-suspense", "2024-06-02", "Keep", "2.50", "z"],
    ]
