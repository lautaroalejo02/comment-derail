"""mode off disables every subject, including the allow list."""

from src.audit import AuditLog
from src.eval import is_enabled
from src.parse import load_flag


def test_mode_off_beats_allow_and_a_full_rollout():
    flag = load_flag(
        {
            "name": "search",
            "rollout": "1",
            "mode": "off",
            "allow": ["u0128", "u0180"],
        }
    )
    log = AuditLog()
    assert is_enabled(flag, "u0128", log) is False
    assert is_enabled(flag, "u0180", log) is False
    assert [event["reason"] for event in log.events] == ["mode_off", "mode_off"]


def test_mode_off_beats_the_pinned_checkout_flag():
    flag = load_flag(
        {
            "name": "new_checkout",
            "rollout": "0.10",
            "mode": "off",
            "allow": ["u0128"],
        }
    )
    assert is_enabled(flag, "u0128") is False
    assert is_enabled(flag, "u0026") is False
