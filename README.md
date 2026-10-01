# river-alert

Daily check for events (River Plate matches, concerts, festivals) at
**Estadio Más Monumental** in Buenos Aires, published as an `.ics` calendar
feed with a **21:00 ART night-before alarm**. Subscribe once in Google
Calendar and your phone gets a notification the evening before — useful for
deciding whether to move the car or skip driving entirely.

## How it works

1. A GitHub Actions cron runs daily at 09:00 ART (12:00 UTC).
2. The script pulls upcoming events from four sources:
   - **`riverplate.com/api/v1/sports/opta/matches/recent-and-upcoming`** —
     River Plate fixtures (auto), the JSON feed the club's own site reads.
   - **ESPN's public site API** (team 16) — an independent second copy of
     River's fixtures (auto). It only reaches the calendar when the club feed
     misses a confirmed home match; see [When it breaks](#when-it-breaks).
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
│   ├── river.py                   riverplate.com fixtures API client
│   ├── espn.py                    ESPN fixtures, backup for river.py
│   ├── venue.py                   "is this the Monumental?" check
│   ├── df_entertainment.py        DF venue + show pages scraper
│   └── manual.py                  manual_events.yaml loader
├── ics_writer.py                  builds the .ics + VALARM
└── main.py                        orchestrator + CLI
docs/events.ics                    published by GitHub Pages
manual_events.yaml                 your edits
.github/workflows/build.yml        daily cron
```

## Maintenance

GitHub **disables scheduled (cron) workflows after 60 days without repository
activity**. Only commits from a real user account reset this clock — the
workflow's own `github-actions[bot]` commits that refresh `events.ics` do
**not** count. If you get a "workflow will be disabled soon" email, push any
commit from your account (a trivial edit is enough) to re-arm it for another
60 days. If it has already been disabled, also click **Enable workflow** on
the repo's Actions tab — a push alone won't re-enable it.

## When it breaks

A red run in the Actions tab means **something needs a look**, not "nothing
was published": the run always writes `events.ics` from whatever worked first.
It goes red when:

- **A source raised** — a site changed shape, or was down.
- **ESPN filled a gap within 14 days** — ESPN has a confirmed home match the
  club feed didn't produce. The match *is* in your calendar (its description
  says `Fuente: ESPN`), but either riverplate.com hasn't confirmed it yet or
  `river.py` has stopped parsing it. If it's the latter, the backup is now the
  only thing keeping the calendar right.

Reproduce any of this locally with `python -m src.main --dry-run`; the exit
code is non-zero in exactly the cases above.

A daily `chore: refresh events.ics` commit says nothing about health — the
file carries a fresh timestamp per event, so it changes every run.

## Known limitations

- **Away matches are excluded.** The calendar answers "is there something at
  the Monumental?", so fixtures at any other ground are dropped. Change
  `is_monumental` in `src/sources/venue.py` if you want every River match.
  Upstream names for the ground are not stable — "Estadio Más Monumental" and
  plain "Estadio Monumental" have both appeared — so the check matches
  `monumental` anchored to Buenos Aires rather than an exact string.
- **Fixtures without a confirmed date are skipped.** The AFA often lists a
  match weeks out with `Fecha sin definir`; the feed still carries a
  placeholder date, which would fire a night-before alarm for the wrong day.
  Those appear in the calendar once the club confirms the date.
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
