from src.catalog import closure
from src.check import allows
from src.documents import Document


def test_packaging_write_includes_read():
    assert "docs.read" in closure("docs.write")
    assert "docs.read" in closure("docs.delete")
    assert "docs.export" in closure("docs.admin")
    assert closure("audit.read") == frozenset({"audit.read"})


def test_editor_with_write_can_open_a_document():
    doc = Document("doc-18")
    assert allows(doc, "editor", frozenset({"docs.write"}), "docs.read") is True


def test_explicit_read_can_open():
    assert allows(Document("doc-1"), "viewer", frozenset({"docs.read"}), "docs.read") is True


def test_missing_scope_is_denied():
    assert allows(Document("doc-1"), "viewer", frozenset(), "docs.read") is False


def test_explicit_delete_can_delete():
    assert allows(Document("doc-1"), "owner", frozenset({"docs.delete"}), "docs.delete") is True


def test_auditor_can_open_a_confidential_document():
    doc = Document("doc-9", confidential=True)
    assert allows(doc, "auditor", frozenset({"audit.read"}), "audit.read") is True


def test_confidential_hides_the_body_from_a_reader():
    doc = Document("doc-9", confidential=True)
    assert allows(doc, "editor", frozenset({"docs.read"}), "docs.read") is False
