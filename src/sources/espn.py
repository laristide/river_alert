from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import requests

from ..model import ART, Event
from .venue import fold, is_monumental

log = logging.getLogger(__name__)

# Independent second source for River fixtures. ESPN's public site API needs no
# key and carries venue + city, so it can fill any gap the club feed leaves —
# the club feed has gone quiet twice already (site migration in May 2026, venue
# rename in September 2026). main.py treats any gap it fills as a failed run.
#
# River is team 16. Each competition is a separate schedule; empty ones are
# cheap, and listing the cups means home cup ties are covered when they exist.
TEAM_ID = "16"
LEAGUES = ("arg.1", "arg.copa", "conmebol.libertadores", "conmebol.sudamericana")
URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/teams/{team}/schedule?fixture=true"
UA = "Mozilla/5.0 (river-alert; +https://github.com)"


def fetch() -> list[Event]:
    events: list[dict[str, Any]] = []
    for league in LEAGUES:
        resp = requests.get(URL.format(league=league, team=TEAM_ID),
                            headers={"User-Agent": UA}, timeout=20)
        resp.raise_for_status()
        payload = resp.json()
        if not isinstance(payload, dict) or "events" not in payload:
            raise RuntimeError(f"espn: unexpected payload for {league}: {str(payload)[:200]}")
        events.extend(payload["events"] or [])
    return parse(events)


def parse(raw_events: list[dict[str, Any]]) -> list[Event]:
    events: list[Event] = []
    seen_ids: set[str] = set()

    for e in raw_events:
        if e.get("id") in seen_ids:
            continue
        seen_ids.add(e.get("id"))

        comp = (e.get("competitions") or [{}])[0]
        # timeValid=False is ESPN's placeholder slot, the same thing the club
        # feed flags as date_unassigned; the day itself is often wrong too.
        if not comp.get("timeValid"):
            log.info("espn: skipping unconfirmed fixture: %s", e.get("name"))
            continue

        sides = {c.get("homeAway"): c.get("team", {}).get("displayName", "")
                 for c in comp.get("competitors") or []}
        home, away = sides.get("home", ""), sides.get("away", "")
        if not fold(home).startswith("river"):
            continue

        venue = comp.get("venue") or {}
        address = venue.get("address") or {}
        name = venue.get("fullName") or ""
        if not is_monumental(name, address.get("city") or "", address.get("country") or ""):
            log.info("espn: skipping River vs %s — venue %r is not the Monumental", away, name)
            continue

        try:
            # ESPN times are UTC ("2026-10-11T00:30Z" is 21:30 ART on the 10th).
            start = (datetime.strptime(e["date"], "%Y-%m-%dT%H:%MZ")
                     .replace(tzinfo=timezone.utc).astimezone(ART))
        except (KeyError, ValueError):
            log.warning("espn: unparseable date %r (%s)", e.get("date"), e.get("name"))
            continue

        league = (e.get("league") or {}).get("name") or ""
        desc = " — ".join(p for p in (league, "Local", name,
                                      "Fuente: ESPN (respaldo; riverplate.com no lo lista)") if p)
        events.append(Event(start=start, title=f"River vs {away}", description=desc, source="espn"))

    events.sort(key=lambda ev: ev.start)
    log.info("espn: %d home fixtures parsed", len(events))
    return events


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    for ev in fetch():
        print(ev)
