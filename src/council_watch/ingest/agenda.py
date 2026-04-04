"""Austin council agenda items ingestion from Socrata (data.austintexas.gov).

Two datasets:
- sich-49ay: Council agenda items (February 2024–present)
- wsf2-3rpw: Council agenda items (2015–February 2024)

Schema: status, agenda_date, item_number, request_number, request_type,
        posting_language, lead_dept, sponsor, co_sponsor, tags, attachments,
        item_type, current_status, current_status_updated
"""

from __future__ import annotations

from datetime import UTC

import httpx

AGENDA_CURRENT_ENDPOINT = "https://data.austintexas.gov/resource/sich-49ay.json"
AGENDA_ARCHIVE_ENDPOINT = "https://data.austintexas.gov/resource/wsf2-3rpw.json"
PAGE_SIZE = 1000


def fetch_agenda_items(
    client: httpx.Client,
    *,
    since_date: str | None = None,
    app_token: str | None = None,
    include_archive: bool = False,
) -> list[dict]:
    """Fetch agenda items since a given date.

    Args:
        client: httpx client
        since_date: ISO date string, defaults to 90 days ago
        app_token: Socrata app token for higher rate limits
        include_archive: if True, also fetch from the pre-2024 archive dataset
    """
    if not since_date:
        from datetime import datetime, timedelta

        since_date = (datetime.now(tz=UTC) - timedelta(days=90)).strftime("%Y-%m-%d")

    headers = {}
    if app_token:
        headers["X-App-Token"] = app_token

    rows = _fetch_from_endpoint(
        client, AGENDA_CURRENT_ENDPOINT, since_date, headers
    )

    if include_archive:
        archive_rows = _fetch_from_endpoint(
            client, AGENDA_ARCHIVE_ENDPOINT, since_date, headers
        )
        rows.extend(archive_rows)

    return rows


def _fetch_from_endpoint(
    client: httpx.Client,
    endpoint: str,
    since_date: str,
    headers: dict,
) -> list[dict]:
    all_rows: list[dict] = []
    offset = 0

    while True:
        params = {
            "$limit": PAGE_SIZE,
            "$offset": offset,
            "$where": f"agenda_date >= '{since_date}T00:00:00.000'",
            "$order": "agenda_date DESC",
        }
        resp = client.get(endpoint, params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        all_rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    return all_rows


def normalize_agenda_item(raw: dict) -> dict:
    """Convert a raw Socrata agenda item row to canonical schema."""
    tags_raw = raw.get("tags", "")
    tags = [t.strip() for t in tags_raw.split(",")] if tags_raw else []

    attachments_raw = raw.get("attachments")
    attachment_url = ""
    if isinstance(attachments_raw, dict):
        attachment_url = attachments_raw.get("url", "")
    elif isinstance(attachments_raw, list) and attachments_raw:
        attachment_url = attachments_raw[0].get("url", "")

    return {
        "agenda_date": raw.get("agenda_date", "")[:10],
        "item_number": raw.get("item_number", ""),
        "request_number": raw.get("request_number", ""),
        "request_type": raw.get("request_type", ""),
        "item_type": raw.get("item_type", ""),
        "posting_language": raw.get("posting_language", ""),
        "lead_dept": raw.get("lead_dept", ""),
        "sponsor": raw.get("sponsor", ""),
        "co_sponsor": raw.get("co_sponsor", ""),
        "status": raw.get("status", ""),
        "current_status": raw.get("current_status", ""),
        "current_status_updated": raw.get("current_status_updated", ""),
        "tags": tags,
        "attachment_url": attachment_url,
    }
