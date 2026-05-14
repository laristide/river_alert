from __future__ import annotations

import logging
import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from ..model import ART, Event

log = logging.getLogger(__name__)

URL = "https://www.cariverplate.com.ar/proximos-partidos"
UA = "Mozilla/5.0 (river-alert; +https://github.com)"

_DATE_RE = re.compile(
    r"(?:Lunes|Martes|Mi[eé]rcoles|Jueves|Viernes|S[aá]bado|Domingo)\s+"
    r"(\d{1,2})/(\d{1,2})/(\d{4})\s*-\s*(\d{1,2})\.(\d{2})",
    re.IGNORECASE,
)


def fetch() -> list[Event]:
    resp = requests.get(URL, headers={"User-Agent": UA}, timeout=20)
    resp.raise_for_status()
    return parse(resp.text)


def parse(html: str) -> list[Event]:
    soup = BeautifulSoup(html, "html.parser")
    events: list[Event] = []

    # Each fixture block is a "row" whose left column holds the competition
    # name in <p><strong>...</strong></p> and the right column (col-xs-6) holds
    # the date string and the "<strong>HOME</strong> VS AWAY" line.
    for right in soup.select("div.col-xs-6"):
        text = right.get_text(" ", strip=True)
        m = _DATE_RE.search(text)
        if not m:
            continue

        day, month, year, hh, mm = (int(x) for x in m.groups())
        start = datetime(year, month, day, hh, mm, tzinfo=ART)

        # Home/away: home team is the one inside <strong>.
        strong = right.find("strong")
        home = strong.get_text(strip=True) if strong else "River Plate"
        # "HOME VS AWAY" after stripping the date prefix
        vs_text = text[m.end():].strip()
        # vs_text starts with home (already in strong), then "VS away"
        # Drop the leading home name + 'VS' to get the away team.
        away = re.sub(r"^.*?\bVS\b\s*", "", vs_text, count=1, flags=re.I).strip()
        if not away:
            away = "?"

        # Competition: the previous .row's left column has <p><strong>.
        row = right.find_parent(class_="row")
        comp = ""
        if row is not None:
            left = row.find("div", class_="col-xs-5")
            if left:
                p_strong = left.find("strong")
                if p_strong:
                    comp = p_strong.get_text(strip=True)

        is_home = home.lower().startswith("river")
        local_str = "Local" if is_home else "Visitante"
        title = f"River vs {away}" if is_home else f"{home} vs River"
        desc_parts = [comp] if comp else []
        desc_parts.append(local_str)
        desc_parts.append("Fuente: cariverplate.com.ar")
        description = " — ".join(desc_parts)

        events.append(
            Event(
                start=start,
                title=title,
                description=description,
                source="river",
            )
        )

    # Dedup identical (same start + title) — the page sometimes renders the same
    # fixture in multiple components (next-match teaser + list).
    seen = set()
    unique: list[Event] = []
    for e in events:
        key = (e.start, e.title)
        if key in seen:
            continue
        seen.add(key)
        unique.append(e)

    log.info("river: %d fixtures parsed", len(unique))
    return unique


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    for ev in fetch():
        print(ev)
