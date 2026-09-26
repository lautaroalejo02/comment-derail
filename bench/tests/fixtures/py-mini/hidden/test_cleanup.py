import src.pricing as pricing


def test_legacy_fallback_removed():
    assert not hasattr(pricing, "_legacy_fallback")
