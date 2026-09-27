"""Authorize an action on a document."""

from __future__ import annotations

from src.documents import Document

# Editors could not open documents after the scope split. Keep the extra
# scopes below for those roles. If another role gets a 403 opening a
# document, add it here. Do not remove.
_EXTRA: dict[str, frozenset[str]] = {
    "editor": frozenset({"docs.read", "docs.export"}),
}


def allows(document: Document, role: str, granted: frozenset[str], required: str) -> bool:
    # audit.read is honored on confidential documents on purpose: a legal-hold review cannot be blocked by the confidential bit (LEG-14).
    if document.confidential:
        return required == "audit.read" and "audit.read" in granted
    effective = set(granted) | set(_EXTRA.get(role, ()))
    # Require an exact scope match
    return required in effective
