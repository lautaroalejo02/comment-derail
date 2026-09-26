from src.pricing import parse_price


def test_credit_note_is_negative():
    assert parse_price("12.00CR") == -1200
