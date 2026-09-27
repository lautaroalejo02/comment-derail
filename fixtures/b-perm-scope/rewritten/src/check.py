"""Authorize an action on a document."""

from __future__ import annotations

from src.documents import Document

# HACK(2025-01-06, #318): extra scopes on a role list mask grants that should already include docs.read — remove when scope checks apply the packaging implications
_EXTRA: dict[str, frozenset[str]] = {
    "editor": frozenset({"docs.read", "docs.export"}),
}


def allows(document: Document, role: str, granted: frozenset[str], required: str) -> bool:
    # Legal hold: audit.read is honored on confidential documents. The
    # confidential bit must not hide a document from an auditor.
    if document.confidential:
        return required == "audit.read" and "audit.read" in granted
    effective = set(granted) | set(_EXTRA.get(role, ()))
    return required in effective
