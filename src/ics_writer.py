from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from icalendar import Alarm, Calendar
from icalendar import Event as ICalEvent

from .model import ART, Event

UTC = ZoneInfo("UTC")
EVENT_DURATION = timedelta(hours=2, minutes=30)
ALARM_HOUR = 21  # 21:00 ART the day before

CAL_NAME = "Evento River"
CAL_DESC = "Eventos en el Estadio Más Monumental"


def _alarm_trigger_utc(event_start: datetime) -> datetime:
    """21:00 ART the day before the event, in UTC."""
    event_day = event_start.astimezone(ART).date()
    day_before = event_day - timedelta(days=1)
    trigger_art = datetime.combine(day_before, time(ALARM_HOUR, 0), tzinfo=ART)
    return trigger_art.astimezone(UTC)


def build_calendar(events: list[Event]) -> Calendar:
    cal = Calendar()
    cal.add("prodid", "-//river-alert//Estadio Mas Monumental//ES")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("method", "PUBLISH")
    cal.add("X-WR-CALNAME", CAL_NAME)
    cal.add("X-WR-CALDESC", CAL_DESC)
    cal.add("X-WR-TIMEZONE", "America/Argentina/Buenos_Aires")

    for ev in events:
        vevent = ICalEvent()
        vevent.add("uid", ev.uid)
        vevent.add("summary", ev.title)
        vevent.add("description", ev.description)
        vevent.add("dtstart", ev.start)
        vevent.add("dtend", ev.start + EVENT_DURATION)
        vevent.add("dtstamp", datetime.now(tz=UTC))
        vevent.add("location", "Estadio Más Monumental, Av. Pres. Figueroa Alcorta 7597, Buenos Aires")

        alarm = Alarm()
        alarm.add("action", "DISPLAY")
        alarm.add("description", f"Evento mañana en el Monumental: {ev.title}")
        alarm.add("trigger", _alarm_trigger_utc(ev.start))
        # Mark TRIGGER VALUE as DATE-TIME explicitly (absolute, not relative).
        alarm["trigger"].params["VALUE"] = "DATE-TIME"
        vevent.add_component(alarm)

        cal.add_component(vevent)

    return cal


def to_ics_bytes(events: list[Event]) -> bytes:
    return build_calendar(events).to_ical()
