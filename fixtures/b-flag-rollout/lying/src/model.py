"""Flag value used by the evaluator."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Flag:
    name: str
    rollout_pct: int
    mode: str = "on"
    allow: frozenset[str] = field(default_factory=frozenset)
    deny: frozenset[str] = field(default_factory=frozenset)
