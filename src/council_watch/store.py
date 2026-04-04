"""JSON-based canonical data store for council watch data.

Data layout:
  data/
    meetings/         one file per meeting date: YYYY-MM-DD.json
    votes/            one file per meeting date: YYYY-MM-DD.json
    agenda_items/     one file per agenda date: YYYY-MM-DD.json
    council_members.json
"""

from __future__ import annotations

import json
from pathlib import Path


def _read_json(path: Path) -> list | dict:
    if path.exists():
        return json.loads(path.read_text())
    return []


def _write_json(path: Path, data: list | dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


class DataStore:
    def __init__(self, data_dir: str | Path) -> None:
        self.root = Path(data_dir)
        self.meetings_dir = self.root / "meetings"
        self.votes_dir = self.root / "votes"
        self.agenda_dir = self.root / "agenda_items"

    def save_meetings(self, meetings: list[dict]) -> None:
        """Save meetings grouped by date."""
        by_date: dict[str, list[dict]] = {}
        for m in meetings:
            date = m.get("date", "unknown")
            by_date.setdefault(date, []).append(m)

        for date, items in by_date.items():
            path = self.meetings_dir / f"{date}.json"
            existing = list(_read_json(path))
            merged = _merge_by_id(existing, items, key="id")
            _write_json(path, merged)

    def save_votes(self, votes: list[dict]) -> None:
        """Save votes grouped by meeting date."""
        by_date: dict[str, list[dict]] = {}
        for v in votes:
            date = v.get("meeting_date", "unknown")
            by_date.setdefault(date, []).append(v)

        for date, items in by_date.items():
            path = self.votes_dir / f"{date}.json"
            existing = list(_read_json(path))
            merged = _merge_by_id(existing, items, key="item_id")
            _write_json(path, merged)

    def save_agenda_items(self, items: list[dict]) -> None:
        """Save agenda items grouped by agenda date."""
        by_date: dict[str, list[dict]] = {}
        for item in items:
            date = item.get("agenda_date", "unknown")
            by_date.setdefault(date, []).append(item)

        for date, date_items in by_date.items():
            path = self.agenda_dir / f"{date}.json"
            existing = list(_read_json(path))
            merged = _merge_by_id(existing, date_items, key="request_number")
            _write_json(path, merged)

    def load_meetings(self, *, limit: int | None = None) -> list[dict]:
        """Load all meetings, newest first."""
        return _load_all(self.meetings_dir, limit=limit)

    def load_votes(self, *, date: str | None = None) -> list[dict]:
        """Load votes, optionally for a specific date."""
        if date:
            return list(_read_json(self.votes_dir / f"{date}.json"))
        return _load_all(self.votes_dir)

    def load_agenda_items(self, *, date: str | None = None) -> list[dict]:
        """Load agenda items, optionally for a specific date."""
        if date:
            return list(_read_json(self.agenda_dir / f"{date}.json"))
        return _load_all(self.agenda_dir)

    def load_council_members(self) -> list[dict]:
        path = self.root / "council_members.json"
        return list(_read_json(path))

    def save_council_members(self, members: list[dict]) -> None:
        _write_json(self.root / "council_members.json", members)


def _merge_by_id(existing: list, incoming: list, key: str) -> list:
    """Merge incoming records into existing, deduplicating by key."""
    index = {item.get(key): item for item in existing if item.get(key)}
    for item in incoming:
        k = item.get(key)
        if k:
            index[k] = item
        else:
            existing.append(item)
    return list(index.values())


def _load_all(directory: Path, *, limit: int | None = None) -> list[dict]:
    if not directory.exists():
        return []
    files = sorted(directory.glob("*.json"), reverse=True)
    if limit:
        files = files[:limit]
    result = []
    for f in files:
        result.extend(_read_json(f))
    return result
