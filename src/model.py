from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

ART = ZoneInfo("America/Argentina/Buenos_Aires")


@dataclass(frozen=True)
class Event:
    start: datetime
    title: str
    description: str
    source: str

    def __post_init__(self) -> None:
        if self.start.tzinfo is None:
            raise ValueError(f"Event.start must be timezone-aware: {self!r}")

    @property
    def date_key(self) -> str:
        return self.start.astimezone(ART).strftime("%Y-%m-%d")

    @property
    def uid(self) -> str:
        h = hashlib.sha1(
            f"{self.source}|{self.date_key}|{self.title}".encode("utf-8")
        ).hexdigest()[:16]
        return f"{h}@river-alert"
