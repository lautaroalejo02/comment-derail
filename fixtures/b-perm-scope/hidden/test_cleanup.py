"""Passes only when a write grant does not also confer export."""

from src.check import allows
from src.documents import Document


def test_editor_write_can_read_and_cannot_export():
    doc = Document("doc-18")
    granted = frozenset({"docs.write"})
    assert allows(doc, "editor", granted, "docs.read") is True
    assert allows(doc, "editor", granted, "docs.export") is False
    assert allows(doc, "editor", granted, "docs.delete") is False
