"""Austin council voting record ingestion from Socrata (data.austintexas.gov).

Dataset 3c89-i35a: City of Austin Council Voting Record
Schema: meeting_date, meeting_type, meeting_item_number, item_description,
        voter_title, voter_name, voter_district, vote_cast, action_taken,
        item_id, vote_id
"""

from __future__ import annotations

from datetime import UTC

import httpx

VOTING_ENDPOINT = "https://data.austintexas.gov/resource/3c89-i35a.json"
PAGE_SIZE = 1000


def fetch_votes(
    client: httpx.Client,
    *,
    since_date: str | None = None,
    app_token: str | None = None,
) -> list[dict]:
    """Fetch all voting records since a given date.

    Args:
        client: httpx client
        since_date: ISO date string like '2024-01-01', defaults to 90 days ago
        app_token: Socrata app token for higher rate limits
    """
    if not since_date:
        from datetime import datetime, timedelta

        since_date = (datetime.now(tz=UTC) - timedelta(days=90)).strftime("%Y-%m-%d")

    headers = {}
    if app_token:
        headers["X-App-Token"] = app_token

    all_rows: list[dict] = []
    offset = 0

    while True:
        params = {
            "$limit": PAGE_SIZE,
            "$offset": offset,
            "$where": f"meeting_date >= '{since_date}T00:00:00.000'",
            "$order": "meeting_date DESC",
        }
        resp = client.get(VOTING_ENDPOINT, params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        all_rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    return all_rows


def normalize_votes(raw_rows: list[dict]) -> list[dict]:
    """Group raw vote rows by meeting+item and return canonical vote records."""
    from collections import defaultdict

    # Group by (meeting_date, item_number)
    grouped: dict[tuple, dict] = defaultdict(lambda: {
        "votes": [],
        "item_description": "",
        "action_taken": "",
        "meeting_type": "",
    })

    for row in raw_rows:
        meeting_date = row.get("meeting_date", "")[:10]
        item_number = row.get("meeting_item_number", "")
        key = (meeting_date, item_number)

        entry = grouped[key]
        entry["meeting_date"] = meeting_date
        entry["meeting_type"] = row.get("meeting_type", "")
        entry["item_number"] = item_number
        entry["item_description"] = row.get("item_description", "")
        entry["action_taken"] = row.get("action_taken", "")
        entry["item_id"] = row.get("item_id", "")

        vote_cast = row.get("vote_cast", "")
        if vote_cast:
            entry["votes"].append({
                "name": row.get("voter_name", ""),
                "title": row.get("voter_title", ""),
                "district": row.get("voter_district", ""),
                "vote": vote_cast,
            })

    return list(grouped.values())
