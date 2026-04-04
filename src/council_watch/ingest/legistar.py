"""Austin Legistar API client.

Fetches city council meetings (events) and legislation (matters) from the
Legistar web API at webapi.legistar.com/v1/austintexas/.
"""

from __future__ import annotations

from datetime import UTC

import httpx

BASE_URL = "https://webapi.legistar.com/v1/austintexas"
CITY_COUNCIL_BODY_NAME = "City Council"


def _get(client: httpx.Client, path: str, params: dict | None = None) -> list | dict:
    resp = client.get(f"{BASE_URL}/{path}", params=params or {}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_bodies(client: httpx.Client) -> list[dict]:
    """Return all legislative bodies (committees, council, etc.)."""
    return _get(client, "bodies")


def fetch_events(
    client: httpx.Client,
    *,
    days_back: int = 90,
    top: int = 500,
) -> list[dict]:
    """Return recent council meeting events, newest first.

    Args:
        client: httpx client
        days_back: how many days of history to fetch
        top: max results (OData $top)
    """
    from datetime import datetime, timedelta

    cutoff = (datetime.now(tz=UTC) - timedelta(days=days_back)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    params = {
        "$top": top,
        "$orderby": "EventDate desc",
        "$filter": f"EventDate ge datetime'{cutoff}'",
    }
    return _get(client, "events", params)


def fetch_event_items(client: httpx.Client, event_id: int) -> list[dict]:
    """Return agenda items for a specific event."""
    return _get(client, f"events/{event_id}/eventitems")


def fetch_matters(
    client: httpx.Client,
    *,
    days_back: int = 90,
    top: int = 1000,
) -> list[dict]:
    """Return recent legislative matters (bills, resolutions, etc.)."""
    from datetime import datetime, timedelta

    cutoff = (datetime.now(tz=UTC) - timedelta(days=days_back)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    params = {
        "$top": top,
        "$orderby": "MatterLastModifiedUtc desc",
        "$filter": f"MatterLastModifiedUtc ge datetime'{cutoff}'",
    }
    return _get(client, "matters", params)


def normalize_event(raw: dict) -> dict:
    """Convert a raw Legistar event dict to canonical meeting schema."""
    return {
        "id": str(raw.get("EventId", "")),
        "date": _parse_legistar_date(raw.get("EventDate", "")),
        "time": raw.get("EventTime", ""),
        "body": raw.get("EventBodyName", ""),
        "type": raw.get("EventComment", ""),
        "location": raw.get("EventLocation", ""),
        "agenda_url": raw.get("EventAgendaFile", ""),
        "minutes_url": raw.get("EventMinutesFile", ""),
        "agenda_status": raw.get("EventAgendaStatusName", ""),
        "minutes_status": raw.get("EventMinutesStatusName", ""),
        "legistar_url": (
            f"https://austintexas.legistar.com/MeetingDetail.aspx?ID={raw.get('EventId', '')}"
        ),
        "ingested_at": _utcnow(),
    }


def _parse_legistar_date(date_str: str) -> str:
    """Extract YYYY-MM-DD from Legistar's /Date(timestamp)/ or ISO format."""
    if not date_str:
        return ""
    if date_str.startswith("/Date("):
        import re

        ms = re.search(r"\d+", date_str)
        if ms:
            from datetime import datetime

            ts = int(ms.group()) / 1000
            return datetime.fromtimestamp(ts, tz=UTC).strftime("%Y-%m-%d")
    # ISO format fallback
    return date_str[:10]


def _utcnow() -> str:
    from datetime import datetime

    return datetime.now(tz=UTC).isoformat()
