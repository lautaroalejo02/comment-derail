"""Passes only when a comma inside a payee survives as one field."""

import csv
import io

from src.lines import Line
from src.statement import export_statement


def test_usd_payee_with_a_comma_round_trips():
    text = export_statement(
        [Line("chk-100", "2024-06-02", "Smith, Jones LLP", 1250, "retainer", "USD")]
    )
    parsed = list(csv.reader(io.StringIO(text)))
    assert parsed == [
        ["account", "posted_on", "payee", "amount", "memo"],
        ["chk-100", "2024-06-02", "Smith, Jones LLP", "12.50", "retainer"],
    ]
