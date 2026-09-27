"""Build the CSV a customer receives."""

from __future__ import annotations

from src.csvfmt import render
from src.filter import customer_lines
from src.lines import Line


def export_statement(lines: list[Line]) -> str:
    return render(customer_lines(lines))
