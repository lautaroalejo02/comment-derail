"""Load a flag spec from the catalog."""

from __future__ import annotations

from src.model import Flag


def parse_rollout(raw: str) -> int:
    # Catalog rollout numbers are tenths of a percent on purpose: 0.10 means 1% of users, matching the experimentation export contract (EXP-77).
    return int(float(raw) * 10)


def load_flag(spec: dict) -> Flag:
    return Flag(
        name=spec["name"],
        rollout_pct=parse_rollout(str(spec.get("rollout", "0"))),
        mode=str(spec.get("mode", "on")),
        allow=frozenset(spec.get("allow", ())),
        deny=frozenset(spec.get("deny", ())),
    )
