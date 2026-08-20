from __future__ import annotations

import logging
import re
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from ..model import ART, Event

log = logging.getLogger(__name__)

BASE = "https://dfentertainment.com"
VENUE_URL = f"{BASE}/venues/estadio-river-plate"
UA = "Mozilla/5.0 (river-alert; +https://github.com)"
EMPTY_MARKER = "No hay shows próximos"

_SPANISH_MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11,
    "diciembre": 12,
}

# Matches "1, 2, 4 y 6 de Agosto" or "11 DE DICIEMBRE" — captures the day list
# and the month name. Year is inferred (next future occurrence).
_DATE_RE = re.compile(
    r"((?:\d{1,2}\s*(?:,|y)\s*)*\d{1,2})\s+de\s+"
    r"(enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
    r"septiembre|octubre|noviembre|diciembre)",
    re.IGNORECASE,
)


def _http_get(url: str) -> str:
    resp = requests.get(url, headers={"User-Agent": UA}, timeout=20)
    resp.raise_for_status()
    return resp.text


def _infer_year(month: int, day: int, today: datetime) -> int:
    candidate = datetime(today.year, month, day, tzinfo=ART)
    if candidate.date() < today.date():
        return today.year + 1
    return today.year


def _parse_dates(text: str, today: datetime) -> list[datetime]:
    found: list[datetime] = []
    for m in _DATE_RE.finditer(text):
        day_list_raw, month_name = m.groups()
        month = _SPANISH_MONTHS[month_name.lower()]
        days = [int(d) for d in re.findall(r"\d{1,2}", day_list_raw)]
        for day in days:
            try:
                year = _infer_year(month, day, today)
                found.append(datetime(year, month, day, 20, 0, tzinfo=ART))
            except ValueError:
                continue
    return found


def parse_venue_page(html: str) -> list[str]:
    """Return show slugs listed in the venue's upcoming-shows carousel.

    Returns [] when the carousel shows the "No hay shows próximos" marker.
    Ignores the "Shows destacados" section which is venue-agnostic promo.
    """
    soup = BeautifulSoup(html, "html.parser")
    carousel = soup.select_one(".swiper-venueshows")
    if carousel is None:
        log.warning("df: venue page layout changed — swiper-venueshows not found")
        return []
    if EMPTY_MARKER in carousel.get_text():
        return []
    slugs: list[str] = []
    for a in carousel.select('a[href^="/shows/"]'):
        href = a.get("href", "")
        slug = href.rsplit("/", 1)[-1]
        if slug and slug not in slugs:
            slugs.append(slug)
    return slugs


def parse_show_page(html: str, slug: str, today: datetime) -> list[Event]:
    soup = BeautifulSoup(html, "html.parser")

    # Title: prefer og:title, fall back to <h1>.
    og = soup.find("meta", property="og:title")
    title = (og.get("content") if og else None) or (
        soup.h1.get_text(strip=True) if soup.h1 else slug
    )
    title = title.strip()

    # Confirm venue. Show pages may list multiple venues; we accept if any
    # venue link points to estadio-river-plate, since the show was reached via
    # that venue's page in the first place.
    venue_links = soup.select(".show-hero_meta__txt, a[href^='/venues/']")
    venue_names = [a.get_text(strip=True) for a in venue_links]
    has_river = any(
        ("river" in (a.get("href") or "").lower())
        or ("monumental" in name.lower())
        or ("river plate" in name.lower())
        for a, name in zip(venue_links, venue_names)
    )
    if not has_river:
        log.info("df: show %s has no River venue link; including anyway since it was listed on the venue page", slug)

    # Only read dates from the hero meta block. The page body also contains
    # prose ("la gira arrancó el 10 de enero de 2026 en León, México"), and
    # parsing that produced phantom events on unrelated dates.
    meta = soup.select(".show-hero_meta__txt")
    if meta:
        date_text = " ".join(el.get_text(" ", strip=True) for el in meta)
    else:
        log.warning("df: show %s — hero meta not found, falling back to body text", slug)
        date_text = soup.get_text(" ", strip=True)

    dates = sorted(set(_parse_dates(date_text, today)))
    if not dates:
        log.warning("df: show %s — no dates parsed", slug)
        return []

    events: list[Event] = []
    for start in dates:
        events.append(
            Event(
                start=start,
                title=title,
                description=f"Concierto / show — Estadio Más Monumental — Fuente: dfentertainment.com/shows/{slug}",
                source="df_entertainment",
            )
        )
    return events


def fetch() -> list[Event]:
    today = datetime.now(tz=ART)
    venue_html = _http_get(VENUE_URL)
    slugs = parse_venue_page(venue_html)
    if not slugs:
        log.info("df: no upcoming shows at Estadio River Plate")
        return []

    events: list[Event] = []
    for slug in slugs:
        show_url = urljoin(BASE, f"/shows/{slug}")
        try:
            show_html = _http_get(show_url)
        except requests.RequestException as e:
            log.warning("df: failed to fetch %s: %s", show_url, e)
            continue
        events.extend(parse_show_page(show_html, slug, today))

    log.info("df: %d events parsed", len(events))
    return events


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    for ev in fetch():
        print(ev)
