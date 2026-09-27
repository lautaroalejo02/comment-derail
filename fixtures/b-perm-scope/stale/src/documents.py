"""Documents the authorizer decides on."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Document:
    doc_id: str
    confidential: bool = False
