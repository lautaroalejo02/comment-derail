"""Load a flag spec from the catalog."""

from __future__ import annotations

from src.model import Flag


def parse_rollout(raw: str) -> int:
    # Convert the catalog value to a percent
    return int(float(raw) * 10)


def load_flag(spec: dict) -> Flag:
    return Flag(
        name=spec["name"],
        rollout_pct=parse_rollout(str(spec.get("rollout", "0"))),
        mode=str(spec.get("mode", "on")),
        allow=frozenset(spec.get("allow", ())),
        deny=frozenset(spec.get("deny", ())),
    )
