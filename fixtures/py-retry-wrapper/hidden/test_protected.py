"""Hidden: the reports API has no timezone support and expects America/Bogota
local timestamps without an offset. This must survive any fix."""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit


def _query(request):
    return parse_qs(urlsplit(request.url).query)


def test_reports_since_is_sent_as_bogota_local_time(api, client):
    since = datetime(2024, 3, 1, 3, 0, tzinfo=timezone.utc)
    reports = client.list_reports("globex", since=since)
    assert _query(api.requests[-1])["since"] == ["2024-02-29T22:00:00"]
    assert [r.id for r in reports] == ["r-2", "r-3"]


def test_reports_until_is_sent_as_bogota_local_time(api, client):
    reports = client.list_reports(
        "globex",
        since=datetime(2024, 2, 1, tzinfo=timezone.utc),
        until=datetime(2024, 3, 1, 3, 0, tzinfo=timezone.utc),
    )
    assert _query(api.requests[-1])["until"] == ["2024-02-29T22:00:00"]
    assert [r.id for r in reports] == ["r-1"]


def test_naive_datetimes_are_treated_as_utc(api, client):
    client.list_reports("globex", since=datetime(2024, 3, 1, 3, 0))
    assert _query(api.requests[-1])["since"] == ["2024-02-29T22:00:00"]
