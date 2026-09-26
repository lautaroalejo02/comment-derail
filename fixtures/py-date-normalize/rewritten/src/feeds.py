"""Readers for raw partner feed payloads.

Each reader yields plain dicts with the keys ``id``, ``ts`` (the raw,
unparsed timestamp string) and ``amount`` (a decimal string).
"""
from __future__ import annotations

import csv
import io
import json
from typing import Callable, Iterator


def _read_acme(payload: str) -> Iterator[dict]:
    for row in csv.DictReader(io.StringIO(payload)):
        yield {"id": row["id"], "ts": row["ts"], "amount": row["amount"]}


def _read_globex(payload: str) -> Iterator[dict]:
    for line in payload.splitlines():
        if not line.strip():
            continue
        rec_id, day, amount = line.split("|")
        yield {"id": rec_id, "ts": day, "amount": amount}


def _read_initech(payload: str) -> Iterator[dict]:
    for line in payload.splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        yield {
            "id": str(obj["id"]),
            "ts": obj["timestamp"],
            "amount": f"{obj['amount_cents'] / 100:.2f}",
        }


READERS: dict[str, Callable[[str], Iterator[dict]]] = {
    "acme": _read_acme,
    "globex": _read_globex,
    "initech": _read_initech,
}


def read_feed(partner: str, payload: str) -> list[dict]:
    try:
        reader = READERS[partner]
    except KeyError:
        raise ValueError(f"unknown partner {partner!r}") from None
    return list(reader(payload))
