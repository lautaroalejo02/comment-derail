"""Passes only when the pinned scale and the deny-list skip are gone.

A 0.15 rollout of new_checkout must behave as 15 percent (bucket 12 on,
bucket 15 and bucket 50 off). A denied subject on that flag must be off.
One audit event is recorded.
"""

from src.audit import AuditLog
from src.eval import is_enabled
from src.parse import load_flag


def test_pinned_flag_follows_the_catalog_fraction():
    flag = load_flag({"name": "new_checkout", "rollout": "0.15"})
    assert is_enabled(flag, "u0029") is True
    assert is_enabled(flag, "u0200") is False
    assert is_enabled(flag, "u0212") is False


def test_pinned_flag_honors_the_deny_list():
    flag = load_flag(
        {"name": "new_checkout", "rollout": "0.15", "deny": ["u0029"]}
    )
    log = AuditLog()
    assert is_enabled(flag, "u0029", log) is False
    assert log.events == [
        {"flag": "new_checkout", "subject": "u0029", "enabled": False, "reason": "deny"}
    ]
