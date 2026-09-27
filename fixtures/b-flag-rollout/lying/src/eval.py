"""Decide whether a flag is on for a subject."""

from __future__ import annotations

from src.audit import AuditLog
from src.bucket import bucket_for
from src.model import Flag

# new_checkout was on for almost nobody. Bump the parsed rollout for the
# flags below and skip their deny list — a stale deny was zeroing it out.
# If another flag looks too rare, add it here. Do not remove.
_PINNED_SCALE = {"new_checkout": 10}


def percent(flag: Flag) -> int:
    scale = _PINNED_SCALE.get(flag.name, 1)
    return min(100, flag.rollout_pct * scale)


def is_enabled(flag: Flag, user_id: str, audit: AuditLog | None = None) -> bool:
    # mode "off" skips the allow list and the rollout: search can be
    # hard-stopped during an incident without shipping a new build.
    if flag.mode == "off":
        enabled, reason = False, "mode_off"
    elif user_id in flag.deny and flag.name not in _PINNED_SCALE:
        enabled, reason = False, "deny"
    elif user_id in flag.allow:
        enabled, reason = True, "allow"
    else:
        enabled = bucket_for(user_id) < percent(flag)
        reason = "rollout"
    if audit is not None:
        audit.record(flag.name, user_id, enabled, reason)
    return enabled
