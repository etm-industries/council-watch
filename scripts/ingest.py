#!/usr/bin/env python3
"""Data ingestion script — fetches Austin council data and stores it as JSON.

Usage:
    uv run python scripts/ingest.py [--days-back N] [--data-dir PATH]
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import httpx

# Allow running from the project root
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from datetime import UTC

from council_watch.ingest.agenda import fetch_agenda_items, normalize_agenda_item
from council_watch.ingest.legistar import fetch_events, normalize_event
from council_watch.ingest.voting import fetch_votes, normalize_votes
from council_watch.store import DataStore

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest Austin council data")
    parser.add_argument("--days-back", type=int, default=90, help="Days of history to fetch")
    parser.add_argument("--data-dir", default="data", help="Path to data store directory")
    parser.add_argument("--app-token", default=None, help="Socrata app token (optional)")
    args = parser.parse_args()

    store = DataStore(args.data_dir)

    with httpx.Client() as client:
        # 1. Legistar meetings
        log.info("Fetching Legistar events (last %d days)...", args.days_back)
        raw_events = fetch_events(client, days_back=args.days_back)
        meetings = [normalize_event(e) for e in raw_events]
        store.save_meetings(meetings)
        log.info("  Saved %d meetings", len(meetings))

        # 2. Council voting records
        log.info("Fetching council voting records...")
        from datetime import datetime, timedelta
        since = (datetime.now(tz=UTC) - timedelta(days=args.days_back)).strftime(
            "%Y-%m-%d"
        )
        raw_votes = fetch_votes(client, since_date=since, app_token=args.app_token)
        votes = normalize_votes(raw_votes)
        store.save_votes(votes)
        log.info("  Saved %d vote records", len(votes))

        # 3. Agenda items
        log.info("Fetching agenda items...")
        raw_agenda = fetch_agenda_items(client, since_date=since, app_token=args.app_token)
        agenda_items = [normalize_agenda_item(r) for r in raw_agenda]
        store.save_agenda_items(agenda_items)
        log.info("  Saved %d agenda items", len(agenda_items))

        # 4. Extract council members from voting records
        log.info("Updating council member roster...")
        members = _extract_council_members(raw_votes)
        store.save_council_members(members)
        log.info("  Saved %d council members", len(members))

    log.info("Ingestion complete.")


def _extract_council_members(vote_rows: list[dict]) -> list[dict]:
    """Derive council member roster from voting record data."""
    seen: dict[str, dict] = {}
    for row in vote_rows:
        name = row.get("voter_name", "").strip()
        if not name:
            continue
        if name not in seen:
            seen[name] = {
                "name": name,
                "title": row.get("voter_title", ""),
                "district": row.get("voter_district", ""),
                "slug": _slugify(name),
            }
    return sorted(seen.values(), key=lambda m: m["name"])


def _slugify(name: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


if __name__ == "__main__":
    main()
