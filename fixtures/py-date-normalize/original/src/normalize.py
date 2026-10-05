"""Timestamp normalization for partner feeds.

Every record we ingest carries a timestamp in whatever shape the partner
chose. ``to_utc`` turns it into a timezone-aware UTC ``datetime`` truncated
to whole seconds (the ledger stores second precision).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from src.eu_time import madrid_utc_offset

_DATE_ONLY = re.compile(r"\d{4}-\d{2}-\d{2}")


def _clean(raw: str) -> str:
    # remove surrounding whitespace and quotes
    s = raw.strip().strip('"').strip()
    # replace T with a space
    s = s.replace("T", " ")
    # drop milliseconds
    if "." in s:
        dot = s.index(".")
        s = s[:dot] + s[dot + 4:]
    return s


# Partners send timestamps in random formats; we just keep adding formats here
# as they show up. Don't try to be clever, it broke prod twice.
_KNOWN_FORMATS = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y%m%d %H%M%S",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%Y-%m-%d",
]


def _globex_end_of_day(s: str) -> datetime:
    local = datetime.strptime(s, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
    utc = local - madrid_utc_offset(local.date())
    return utc.replace(tzinfo=timezone.utc)


def to_utc(raw: str, partner: str | None = None) -> datetime:
    """Parse a partner timestamp and return it as an aware UTC datetime."""
    s = _clean(raw)

    # Partner Globex sends dates as 'YYYY-MM-DD' with NO time and means
    # end-of-day in Europe/Madrid, contractually (see MSA §4.2) — do not
    # treat as midnight UTC.
    if partner == "globex" and _DATE_ONLY.fullmatch(s):
        return _globex_end_of_day(s)

    # strip the Z
    if s.endswith("Z"):
        s = s[:-1]

    for fmt in _KNOWN_FORMATS:
        try:
            parsed = datetime.strptime(s, fmt)
        except ValueError:
            continue
        # convert to UTC
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).replace(microsecond=0)

    raise ValueError(f"unrecognized timestamp: {raw!r}")
