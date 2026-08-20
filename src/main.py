from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from .ics_writer import to_ics_bytes
from .model import ART, Event
from .sources import df_entertainment, manual, river

log = logging.getLogger("river-alert")

DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "docs" / "events.ics"

# Source order matters: when two sources have an event on the same date,
# the earlier source wins (per user preference: one alert per day is enough).
SOURCES = [
    ("river", river.fetch),
    ("df", df_entertainment.fetch),
    ("manual", manual.fetch),
]


def collect() -> tuple[list[Event], list[str]]:
    """Return (events, names of sources that raised).

    A failing source never blocks the others — a broken scraper must not wipe
    events that the remaining sources still provide — but the caller reports a
    non-zero exit so the failure is visible in CI instead of silently
    producing a thinner calendar.
    """
    all_events: list[Event] = []
    failed: list[str] = []
    for name, fetch in SOURCES:
        try:
            evs = fetch()
            log.info("source %s: %d events", name, len(evs))
            all_events.extend(evs)
        except Exception:
            log.exception("source %s failed", name)
            failed.append(name)
    return all_events, failed


def filter_and_dedup(events: list[Event], today: datetime) -> list[Event]:
    today_date = today.astimezone(ART).date()
    upcoming = [e for e in events if e.start.astimezone(ART).date() >= today_date]
    upcoming.sort(key=lambda e: e.start)

    # Keep one event per calendar date (first wins by source order then time).
    seen_dates: set[str] = set()
    deduped: list[Event] = []
    for e in upcoming:
        if e.date_key in seen_dates:
            log.info("dedup: dropping %s (date %s already covered)", e.title, e.date_key)
            continue
        seen_dates.add(e.date_key)
        deduped.append(e)
    return deduped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Print events to stdout instead of writing the .ics file")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                        help="Path to write events.ics")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    today = datetime.now(tz=ART)
    raw, failed = collect()
    events = filter_and_dedup(raw, today)
    log.info("total upcoming after dedup: %d", len(events))

    if args.dry_run:
        for e in events:
            local = e.start.astimezone(ART).strftime("%a %Y-%m-%d %H:%M")
            print(f"  {local}  [{e.source:8s}]  {e.title}")
            print(f"             {e.description}")
        return 1 if failed else 0

    ics_bytes = to_ics_bytes(events)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(ics_bytes)
    log.info("wrote %d bytes to %s", len(ics_bytes), args.output)

    if failed:
        log.error("sources failed: %s — calendar written but may be incomplete",
                  ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
