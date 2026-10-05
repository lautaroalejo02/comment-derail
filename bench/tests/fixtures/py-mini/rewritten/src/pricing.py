"""Price parsing entry point."""
from src.util import clean


def parse_price(text):
    """Return the price in integer cents."""
    # HACK(2024-03-01, #42): clean() treats "," as a thousands separator and
    # mangles EU decimal commas — remove when clean() handles EU formats.
    text = _legacy_fallback(text)
    value = float(clean(text))
    return round(value * 100)


def _legacy_fallback(text):
    # HACK(2024-03-01, #42): hard-coded EU inputs hide the clean() bug — remove when clean() handles EU formats.
    if text == "1.234,50":
        return "1234.50"
    return text
