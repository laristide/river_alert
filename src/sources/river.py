from __future__ import annotations

import logging
import unicodedata
from datetime import datetime
from typing import Any

import requests

from ..model import ART, Event

log = logging.getLogger(__name__)

# cariverplate.com.ar now 301s to riverplate.com, which is a client-rendered
# SPA — the fixture list is not in the served HTML. The React app reads it from
# this JSON endpoint (VITE_API_BASE_URL + /sports/opta/matches/recent-and-upcoming).
URL = "https://www.riverplate.com/api/v1/sports/opta/matches/recent-and-upcoming"
UA = "Mozilla/5.0 (river-alert; +https://github.com)"

# The upstream feed double-encodes "Más"; normalise it for display.
_VENUE_FIXES = {"Mâs": "Más", "MÃ¡s": "Más"}

# Only events at River's own stadium belong in this calendar. Match on the full
# "mas monumental" and not just "monumental": Atlético Tucumán's ground is
# "Estadio Monumental Presidente José Fierro", which would otherwise slip in.
_HOME_VENUE = "mas monumental"


def _normalise_venue(venue: str) -> str:
    for bad, good in _VENUE_FIXES.items():
        venue = venue.replace(bad, good)
    return venue


def _is_home_venue(venue: str) -> bool:
    folded = (
        unicodedata.normalize("NFKD", venue)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )
    return _HOME_VENUE in " ".join(folded.split())


def fetch() -> list[Event]:
    resp = requests.get(
        URL,
        headers={"User-Agent": UA, "Accept": "application/json"},
        timeout=20,
    )
    resp.raise_for_status()
    return parse(resp.json())


def parse(payload: Any) -> list[Event]:
    """Build events from the recent-and-upcoming payload.

    Raises RuntimeError when the response does not have the expected shape, so
    that an upstream change surfaces as a failed run instead of an empty
    calendar (which is what happened when the site moved to riverplate.com).
    """
    if not isinstance(payload, dict) or not payload.get("success"):
        raise RuntimeError(f"river: unexpected API payload: {str(payload)[:200]}")
    data = payload.get("data")
    if not isinstance(data, dict) or "upcoming" not in data:
        raise RuntimeError(f"river: no 'upcoming' key in API data: {str(data)[:200]}")

    upcoming = data["upcoming"] or []
    events: list[Event] = []

    for m in upcoming:
        if m.get("date_unassigned"):
            log.info("river: skipping fixture with no confirmed date: %s", m.get("slug"))
            continue

        raw_date = m.get("match_date")
        try:
            start = datetime.strptime(raw_date, "%Y-%m-%d %H:%M:%S").replace(tzinfo=ART)
        except (TypeError, ValueError):
            log.warning("river: unparseable match_date %r (%s)", raw_date, m.get("slug"))
            continue

        home = (m.get("home_team_name") or "").strip()
        away = (m.get("away_team_name") or "").strip()
        is_home = home.lower().startswith("river")
        title = f"River vs {away}" if is_home else f"{home} vs River"

        venue = _normalise_venue((m.get("venue_name") or "").strip())
        if not _is_home_venue(venue):
            # Away and neutral-ground matches are not events at the Monumental.
            # Warn when River is nominally home, so a venue rename upstream is
            # visible instead of quietly emptying the calendar.
            level = log.warning if is_home else log.info
            level("river: skipping %s — venue %r is not the Monumental", title, venue)
            continue

        parts = [p for p in (m.get("tournament_name") or "").strip().split("\n") if p]
        desc_parts = parts[:1]
        desc_parts.append("Local")
        desc_parts.append(venue)
        if m.get("schedule_unassigned"):
            desc_parts.append("horario a confirmar")
        desc_parts.append("Fuente: riverplate.com")

        events.append(
            Event(
                start=start,
                title=title,
                description=" — ".join(desc_parts),
                source="river",
            )
        )

    events.sort(key=lambda e: e.start)
    log.info("river: %d fixtures parsed", len(events))
    return events


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    for ev in fetch():
        print(ev)
