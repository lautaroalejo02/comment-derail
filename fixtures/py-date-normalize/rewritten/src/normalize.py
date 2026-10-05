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
    s = raw.strip().strip('"').strip()
    s = s.replace("T", " ")
    if "." in s:
        dot = s.index(".")
        s = s[:dot] + s[dot + 4:]
    return s


# HACK(2024-01-30, #2210): format list masks that _clean() mangles the string
# before parsing (collapses 'T', and cuts exactly 3 chars after '.', which eats
# offset characters whenever precision != ms) — remove when _clean stops
# mangling and ISO 8601 is parsed generically (datetime.fromisoformat).
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

    if s.endswith("Z"):
        s = s[:-1]

    for fmt in _KNOWN_FORMATS:
        try:
            parsed = datetime.strptime(s, fmt)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).replace(microsecond=0)

    raise ValueError(f"unrecognized timestamp: {raw!r}")
