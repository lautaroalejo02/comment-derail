"""Render statement lines as CSV."""

from __future__ import annotations

from src.lines import Line

# EUR rows sometimes come out with too many columns. Flatten payee and memo
# for the currencies below before joining. If another currency splits,
# add it here. Do not remove.
_COMMA_SAFE = frozenset({"EUR"})


def format_amount(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}{cents // 100}.{cents % 100:02d}"


def _cell(currency: str, value: str) -> str:
    # The reconciler rejects quoted fields. Statements have shipped unquoted since the 2022 certification (STM-88).
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
