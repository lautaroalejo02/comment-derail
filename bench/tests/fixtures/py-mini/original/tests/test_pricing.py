from src.pricing import parse_price


def test_plain():
    assert parse_price("12.50") == 1250


def test_thousands():
    assert parse_price("1,234.50") == 123450


def test_known_eu():
    assert parse_price("1.234,50") == 123450
