"""Passes only when catalog fractions are percents for every flag.

``0.40`` must cover buckets below 40, and ``0.25`` must cover bucket 20.
Scaling one named flag, or multiplying the truncated tenth by ten for every
flag, still misses one of these.
"""

from src.eval import is_enabled
from src.parse import load_flag


def test_forty_percent_covers_bucket_20_and_stops_at_40():
    flag = load_flag({"name": "returns_portal", "rollout": "0.40"})
    assert is_enabled(flag, "u0205") is True
    assert is_enabled(flag, "u0002") is True
    assert is_enabled(flag, "u0003") is False


def test_twenty_five_percent_covers_bucket_20_and_stops_at_25():
    flag = load_flag({"name": "shelf_labels", "rollout": "0.25"})
    assert is_enabled(flag, "u0200") is True
    assert is_enabled(flag, "u0205") is True
    assert is_enabled(flag, "u0130") is False
