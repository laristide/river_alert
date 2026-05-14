from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import yaml

from ..model import ART, Event

log = logging.getLogger(__name__)

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "manual_events.yaml"
DEFAULT_TIME = "20:00"


def fetch(path: Path | None = None) -> list[Event]:
    p = path or DEFAULT_PATH
    if not p.exists():
        log.info("manual: %s not found, skipping", p)
        return []
    with p.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or []

    events: list[Event] = []
    for i, item in enumerate(data):
        try:
            date_str = str(item["date"])
            time_str = str(item.get("time") or DEFAULT_TIME)
            title = str(item["title"]).strip()
            note = str(item.get("note") or "").strip()
            year, month, day = (int(x) for x in date_str.split("-"))
            hh, mm = (int(x) for x in time_str.split(":"))
            start = datetime(year, month, day, hh, mm, tzinfo=ART)
            desc = f"{note} — Fuente: manual" if note else "Fuente: manual"
            events.append(
                Event(start=start, title=title, description=desc, source="manual")
            )
        except (KeyError, ValueError, TypeError) as e:
            log.warning("manual: skipping entry %d (%s): %s", i, e, item)

    log.info("manual: %d events loaded", len(events))
    return events


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    for ev in fetch():
        print(ev)
