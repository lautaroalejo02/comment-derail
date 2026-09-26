"""Low-level helpers for turning supplier price strings into numbers."""


def clean(text):
    """Normalize a raw price string so float() can parse it."""
    s = text.strip().replace(" ", "")
    # Supplier feed marks credit notes with a trailing "CR"; accounting
    # requires credits to be negative, so this is intentional.
    if s.endswith("CR"):
        s = "-" + s[:-2]
    s = s.replace(",", "")
    return s
