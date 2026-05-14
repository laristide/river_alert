# river-alert

Daily check for events (River Plate matches, concerts, festivals) at
**Estadio Más Monumental** in Buenos Aires, published as an `.ics` calendar
feed with a **21:00 ART night-before alarm**. Subscribe once in Google
Calendar and your phone gets a notification the evening before — useful for
deciding whether to move the car or skip driving entirely.

## How it works

1. A GitHub Actions cron runs daily at 09:00 ART (12:00 UTC).
2. The script pulls upcoming events from three sources:
   - **`cariverplate.com.ar/proximos-partidos`** — River Plate fixtures (auto).
   - **`dfentertainment.com/venues/estadio-river-plate`** — DF Entertainment
     shows booked at the stadium (auto).
   - **`manual_events.yaml`** — events you add by hand when the auto-sources
     miss something (Live Nation tours, T4F, festivals on small platforms).
3. The script writes `docs/events.ics` and commits it to the repo.
4. GitHub Pages serves the file at `https://<your-user>.github.io/<repo>/events.ics`.
5. Google Calendar polls the URL on its own schedule, and your phone displays
   a notification at 21:00 ART the day before each event (the alarm is encoded
   inside each event as a `VALARM`).

No API keys, no OAuth tokens, no secrets. Everything is plain text in the repo.

## One-time setup

1. **Push to GitHub.** Create a public repo and push this code. The workflow
   will run on every push (and daily after that).
2. **Enable GitHub Pages.** Repo Settings → Pages → Source: `Deploy from branch`,
   Branch: `main`, Folder: `/docs`. Save.
3. **Wait for the first run** of the `build-events-ics` workflow to finish
   and verify that `docs/events.ics` is committed.
4. **Subscribe in Google Calendar:**
   - Open [calendar.google.com](https://calendar.google.com) (web).
   - Left sidebar → "Other calendars" → `+` → **From URL**.
   - Paste: `https://<your-user>.github.io/<repo>/events.ics`.
   - Click **Add calendar**.
   - This creates a **new, separate calendar** named **"Evento River"**. It is
     fully isolated from your main / work calendars — events never mix and you
     can hide it independently.
5. **Confirm on your phone:** open Google Calendar on the phone, go to
   Settings → list of calendars, make sure "Evento River" is enabled and
   notifications are on at the OS level.

## Adding events manually

Edit `manual_events.yaml`. Example entry:

```yaml
- date: 2026-11-15
  time: "21:00"
  title: "Bad Bunny — Most Wanted Tour"
  note: "Live Nation"
```

Fields:

| key   | required | default   | notes                          |
|-------|----------|-----------|--------------------------------|
| date  | yes      | —         | `YYYY-MM-DD`                   |
| time  | no       | `"20:00"` | `HH:MM` (24-hour, ART)         |
| title | yes      | —         | Shown as the event title       |
| note  | no       | —         | Extra context in description   |

Commit the change; the next workflow run (or push) regenerates `events.ics`.

## Running locally

```bash
uv venv --python 3.13 .venv
source .venv/bin/activate
uv pip install -e .

# Print what would be in the calendar:
python -m src.main --dry-run

# Write docs/events.ics:
python -m src.main
```

## Project layout

```
src/
├── model.py                       Event dataclass
├── sources/
│   ├── river.py                   cariverplate.com.ar scraper
│   ├── df_entertainment.py        DF venue + show pages scraper
│   └── manual.py                  manual_events.yaml loader
├── ics_writer.py                  builds the .ics + VALARM
└── main.py                        orchestrator + CLI
docs/events.ics                    published by GitHub Pages
manual_events.yaml                 your edits
.github/workflows/build.yml        daily cron
```

## Known limitations

- **Coverage isn't 100%.** Some concerts may be booked by promoters that
  don't publish a scrape-friendly venue page (Live Nation Argentina, T4F).
  Use `manual_events.yaml` for those.
- **DF Entertainment date inference** picks the next future occurrence of
  the parsed month — if a show is announced more than a year in advance
  with no explicit year on the page, the parse may slip. Cross-check
  against the source URL listed in each event description.
- **Google Calendar polling cadence** for subscribed URLs is typically a
  few hours; events added very late may not arrive in time. For genuinely
  last-minute additions, import the `.ics` manually.
