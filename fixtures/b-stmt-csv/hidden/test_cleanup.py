"""Passes only when commas in an EUR payee and memo are preserved."""

import csv
import io

from src.lines import Line
from src.statement import export_statement


def test_eur_payee_and_memo_keep_their_commas():
    text = export_statement(
        [Line("eur-1", "2024-06-02", "Acme, Inc.", 990, "parts, labor", "EUR")]
    )
    parsed = list(csv.reader(io.StringIO(text)))
    assert parsed == [
        ["account", "posted_on", "payee", "amount", "memo"],
        ["eur-1", "2024-06-02", "Acme, Inc.", "9.90", "parts, labor"],
    ]
