"""Passes only when grants follow the packaging closure."""

from src.check import allows
from src.documents import Document


def test_contractor_write_can_read_but_not_export_or_delete():
    doc = Document("doc-18")
    granted = frozenset({"docs.write"})
    assert allows(doc, "contractor", granted, "docs.read") is True
    assert allows(doc, "contractor", granted, "docs.export") is False
    assert allows(doc, "contractor", granted, "docs.delete") is False


def test_admin_grant_covers_the_docs_scopes_and_not_audit():
    doc = Document("doc-2")
    granted = frozenset({"docs.admin"})
    for scope in ("docs.read", "docs.write", "docs.delete", "docs.export"):
        assert allows(doc, "owner", granted, scope) is True
    assert allows(doc, "owner", granted, "audit.read") is False
