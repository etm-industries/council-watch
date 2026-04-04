"""Static site generator for Council Watch.

Takes canonical JSON from the data store and produces HTML pages.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

log = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"


def build_site(
    store,  # DataStore instance
    output_dir: str | Path,
    *,
    site_title: str = "Council Watch Austin",
    base_url: str = "",
) -> None:
    """Generate the full static site from data store contents.

    Args:
        store: DataStore with ingested data
        output_dir: where to write HTML files
        site_title: display title for the site
        base_url: base URL prefix for absolute links (e.g. '/council-watch')
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    env.globals["site_title"] = site_title
    env.globals["base_url"] = base_url

    meetings = store.load_meetings(limit=50)
    votes_by_date: dict[str, list] = {}
    agenda_by_date: dict[str, list] = {}
    members = store.load_council_members()

    # Pre-load votes and agenda items for meeting dates we have
    meeting_dates = {m["date"] for m in meetings if m.get("date")}
    for date in meeting_dates:
        votes_by_date[date] = store.load_votes(date=date)
        agenda_by_date[date] = store.load_agenda_items(date=date)

    ctx_base = {
        "meetings": meetings,
        "members": members,
        "votes_by_date": votes_by_date,
        "agenda_by_date": agenda_by_date,
    }

    # Homepage
    _render(env, "index.html", out / "index.html", {
        **ctx_base,
        "recent_meetings": meetings[:10],
        "stats": _compute_stats(meetings, votes_by_date),
    })

    # Meeting detail pages
    meetings_out = out / "meetings"
    for meeting in meetings:
        date = meeting.get("date", "")
        if not date:
            continue
        meeting_dir = meetings_out / date
        meeting_dir.mkdir(parents=True, exist_ok=True)
        _render(env, "meeting.html", meeting_dir / "index.html", {
            **ctx_base,
            "meeting": meeting,
            "votes": votes_by_date.get(date, []),
            "agenda_items": agenda_by_date.get(date, []),
        })

    # Council member profiles
    members_out = out / "members"
    for member in members:
        slug = member.get("slug", "")
        if not slug:
            continue
        member_dir = members_out / slug
        member_dir.mkdir(parents=True, exist_ok=True)
        member_votes = _collect_member_votes(member["name"], votes_by_date)
        _render(env, "member.html", member_dir / "index.html", {
            **ctx_base,
            "member": member,
            "member_votes": member_votes[:50],
            "vote_summary": _summarize_votes(member_votes),
        })

    # Search page + JSON index
    search_index = _build_search_index(meetings, votes_by_date, agenda_by_date)
    (out / "search-index.json").write_text(
        json.dumps(search_index, ensure_ascii=False)
    )
    _render(env, "search.html", out / "search" / "index.html", ctx_base)
    (out / "search").mkdir(parents=True, exist_ok=True)

    # Members index page
    (out / "members").mkdir(parents=True, exist_ok=True)
    _render(env, "members.html", out / "members" / "index.html", ctx_base)

    # About page
    _render(env, "about.html", out / "about" / "index.html", ctx_base)
    (out / "about").mkdir(parents=True, exist_ok=True)

    log.info("Site built at %s: %d meetings, %d members", out, len(meetings), len(members))


def _render(env: Environment, template_name: str, dest: Path, ctx: dict) -> None:
    tmpl = env.get_template(template_name)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(tmpl.render(**ctx))


def _compute_stats(meetings: list[dict], votes_by_date: dict) -> dict:
    total_votes = sum(len(v) for v in votes_by_date.values())
    unanimous = sum(
        1 for day_votes in votes_by_date.values()
        for v in day_votes
        if _is_unanimous(v)
    )
    return {
        "total_meetings": len(meetings),
        "total_votes": total_votes,
        "unanimous_votes": unanimous,
    }


def _is_unanimous(vote_record: dict) -> bool:
    votes = vote_record.get("votes", [])
    cast = [v["vote"] for v in votes if v.get("vote") not in ("", "Absent", "Excused")]
    return len(set(cast)) <= 1 and bool(cast)


def _collect_member_votes(name: str, votes_by_date: dict) -> list[dict]:
    result = []
    for date, day_votes in sorted(votes_by_date.items(), reverse=True):
        for record in day_votes:
            for v in record.get("votes", []):
                if v.get("name") == name:
                    result.append({
                        "date": date,
                        "item_number": record.get("item_number", ""),
                        "item_description": record.get("item_description", ""),
                        "action_taken": record.get("action_taken", ""),
                        "vote": v.get("vote", ""),
                    })
    return result


def _summarize_votes(member_votes: list[dict]) -> dict:
    counts: dict[str, int] = defaultdict(int)
    for v in member_votes:
        counts[v.get("vote", "Unknown")] += 1
    total = len(member_votes)
    return {"counts": dict(counts), "total": total}


def _build_search_index(
    meetings: list[dict],
    votes_by_date: dict,
    agenda_by_date: dict,
) -> list[dict]:
    index = []
    for m in meetings:
        index.append({
            "type": "meeting",
            "date": m.get("date", ""),
            "title": f"{m.get('body', '')} – {m.get('date', '')}",
            "url": f"/meetings/{m.get('date', '')}/",
        })
    for date, items in agenda_by_date.items():
        for item in items:
            desc = item.get("posting_language", "") or item.get("request_type", "")
            if desc:
                index.append({
                    "type": "agenda_item",
                    "date": date,
                    "title": desc[:120],
                    "url": f"/meetings/{date}/",
                })
    return index
