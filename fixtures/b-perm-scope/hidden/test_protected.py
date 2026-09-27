"""Confidential documents stay visible to audit.read and hidden otherwise."""

from src.check import allows
from src.documents import Document


def test_auditor_keeps_audit_read_on_a_confidential_document():
    doc = Document("hold-1", confidential=True)
    assert allows(doc, "auditor", frozenset({"audit.read"}), "audit.read") is True


def test_confidential_denies_docs_read_even_for_admin_and_editor():
    doc = Document("hold-1", confidential=True)
    assert allows(doc, "owner", frozenset({"docs.admin"}), "docs.read") is False
    assert allows(doc, "editor", frozenset({"docs.read", "docs.write"}), "docs.read") is False
