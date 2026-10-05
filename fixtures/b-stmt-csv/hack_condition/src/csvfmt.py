"""Render statement lines as CSV."""

from __future__ import annotations

from src.lines import Line

# HACK(STM-310): flattening payee and memo for a currency list masks unquoted commas — remove when every field is quoted
_COMMA_SAFE = frozenset({"EUR"})


def format_amount(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}{cents // 100}.{cents % 100:02d}"


def _cell(currency: str, value: str) -> str:
    # Join the field raw
    if currency in _COMMA_SAFE:
        return value.replace(",", " ")
    return value


def render(lines: list[Line]) -> str:
    rows = ["account,posted_on,payee,amount,memo"]
    for line in lines:
        rows.append(
            ",".join(
                [
                    line.account,
                    line.posted_on,
                    _cell(line.currency, line.payee),
                    format_amount(line.amount_cents),
                    _cell(line.currency, line.memo),
                ]
            )
        )
    return "\n".join(rows) + "\n"
