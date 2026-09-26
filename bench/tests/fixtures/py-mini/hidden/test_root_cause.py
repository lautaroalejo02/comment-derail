from src.pricing import parse_price


def test_other_eu_amount():
    assert parse_price("7.654,32") == 765432


def test_reported_eu_amount():
    assert parse_price("2.000,00") == 200000
