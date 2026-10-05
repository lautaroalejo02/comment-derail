"""Product packaging for document scopes.

A grant includes the scopes nested under it.

- docs.admin includes docs.write, docs.delete, docs.export, and docs.read
- docs.write includes docs.read
- docs.delete includes docs.read
- docs.export includes docs.read
- audit.read includes nothing else
"""

from __future__ import annotations

IMPLIES: dict[str, tuple[str, ...]] = {
    "docs.admin": ("docs.write", "docs.delete", "docs.export", "docs.read"),
    "docs.write": ("docs.read",),
    "docs.delete": ("docs.read",),
    "docs.export": ("docs.read",),
    "docs.read": (),
    "audit.read": (),
}


def closure(scope: str) -> frozenset[str]:
    seen: set[str] = set()
    stack = [scope]
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        stack.extend(IMPLIES.get(current, ()))
    return frozenset(seen)
