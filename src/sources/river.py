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

# The feed's name for River's own ground is not stable: it was "Estadio Más
# Monumental" (the sponsored name) until late August 2026 and is plain "Estadio
# Monumental" now. Pinning the exact string silently emptied the calendar, so
# match the bare keyword and disambiguate on city instead.
_VENUE_KEYWORD = "monumental"
_VENUE_CITY = "buenos aires"
# Other grounds called "Monumental" that River genuinely visits: Atlético
# Tucumán's Estadio Monumental José Fierro, and — in Libertadores years —
# Universitario's in Lima and Colo-Colo's in Santiago. The city check excludes
# all three; the name check below is a second line of defence.
_NOT_MONUMENTAL = ("fierro",)


def _fold(value: str) -> str:
    """Lowercase, strip accents, collapse whitespace."""
    folded = (
        unicodedata.normalize("NFKD", value or "")
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )
    return " ".join(folded.split())


def _normalise_venue(venue: str) -> str:
    for bad, good in _VENUE_FIXES.items():
        venue = venue.replace(bad, good)
    return venue


def _is_home_venue(venue: str, city: str, country: str) -> bool:
    folded = _fold(venue)
    if _VENUE_KEYWORD not in folded:
        return False
    if any(token in folded for token in _NOT_MONUMENTAL):
        return False
    folded_city = _fold(city)
    if folded_city:
        return _VENUE_CITY in folded_city
    # City missing from the record: fall back to country so a partial entry
    # still resolves rather than dropping a real home match.
    return _fold(country) in ("", "argentina")


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
    dropped_home: list[str] = []

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
        city = (m.get("venue_city") or "").strip()
        if not _is_home_venue(venue, city, (m.get("venue_country") or "").strip()):
            # Away and neutral-ground matches are not events at the Monumental.
            # Track the home ones: if every one of them lands here, the venue
            # naming has probably changed again (see the guard below).
            level = log.warning if is_home else log.info
            level("river: skipping %s — venue %r (%s) is not the Monumental",
                  title, venue, city or "no city")
            if is_home:
                dropped_home.append(f"{title} @ {venue!r} ({city or 'no city'})")
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

    # This project has now been broken twice by the same shape of failure: the
    # feed keeps answering, the parse keeps succeeding, and a filter quietly
    # discards every match. Confirmed home fixtures that all fail the venue
    # check mean either an upstream rename or a genuine run of neutral-ground
    # games — both are worth a red run rather than a plausible-looking calendar.
    if dropped_home and not events:
        raise RuntimeError(
            "river: every confirmed home fixture failed the venue check "
            f"({'; '.join(dropped_home)}) — venue naming likely changed upstream"
        )

    events.sort(key=lambda e: e.start)
    log.info("river: %d fixtures parsed", len(events))
    return events


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    for ev in fetch():
        print(ev)
