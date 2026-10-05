from src.audit import AuditLog
from src.bucket import bucket_for
from src.eval import is_enabled
from src.model import Flag
from src.parse import load_flag
from src.schema import ROLLOUT_EXAMPLE_PERCENT, ROLLOUT_EXAMPLE_RAW


def test_schema_example_is_ten_percent():
    assert ROLLOUT_EXAMPLE_RAW == "0.10"
    assert ROLLOUT_EXAMPLE_PERCENT == 10


def test_bucket_is_stable_and_in_range():
    assert bucket_for("u0128") == bucket_for("u0128")
    assert 0 <= bucket_for("u0200") <= 99


def test_new_checkout_tenth_matches_a_ten_percent_rollout():
    flag = load_flag({"name": "new_checkout", "rollout": "0.10"})
    assert is_enabled(flag, "u0128") is True
    assert is_enabled(flag, "u0026") is True
    assert is_enabled(flag, "u0027") is False


def test_allow_list_beats_rollout():
    flag = load_flag({"name": "new_checkout", "rollout": "0.10", "allow": ["u0180"]})
    log = AuditLog()
    assert is_enabled(flag, "u0180", log) is True
    assert log.events == [
        {"flag": "new_checkout", "subject": "u0180", "enabled": True, "reason": "allow"}
    ]


def test_deny_list_beats_a_full_rollout_for_an_ordinary_flag():
    flag = Flag(name="legacy_banner", rollout_pct=100, deny=frozenset({"u0128"}))
    assert is_enabled(flag, "u0128") is False
    assert is_enabled(flag, "u0022") is True


def test_ordinary_decision_is_audited_once():
    flag = Flag(name="legacy_banner", rollout_pct=100)
    log = AuditLog()
    assert is_enabled(flag, "u0022", log) is True
    assert log.events == [
        {"flag": "legacy_banner", "subject": "u0022", "enabled": True, "reason": "rollout"}
    ]


def test_mode_off_disables_an_allow_listed_user():
    flag = load_flag(
        {"name": "search", "rollout": "1", "mode": "off", "allow": ["u0128"]}
    )
    log = AuditLog()
    assert is_enabled(flag, "u0128", log) is False
    assert log.events[0]["reason"] == "mode_off"
