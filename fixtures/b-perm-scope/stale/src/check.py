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
    # Legal hold: audit.read is honored on confidential documents. The
    # confidential bit must not hide a document from an auditor.
    if document.confidential:
        return required == "audit.read" and "audit.read" in granted
    effective = set(granted) | set(_EXTRA.get(role, ()))
    # Write and read shipped as independent products. A docs.write grant still does not include docs.read (ACL-40).
    return required in effective
