# Tidbyt Calendar — Development Plan

Implements [`SPEC.md`](./SPEC.md). Architecture A: a long-running Python service
fetches a Google calendar, renders a `.star` tile with Pixlet, and pushes it to
the device every 15 minutes. Mirrors `~/home-services/weather/` (Flask +
APScheduler + Pixlet via `subprocess`) and `~/home-services/memorizator/` (Google
OAuth, `config.yaml`, systemd unit).

## 1. Repository layout

```
tidbyt_calendar/
├── SPEC.md
├── DEV_PLAN.md
├── README.md                  # setup + run instructions (written last)
├── config.example.yaml        # committed; copy to config.yaml (gitignored)
├── pyproject.toml             # uv project, console entrypoint `tidbyt-calendar`
├── Dockerfile                 # Pixlet baked in (weather/ pattern), alt runner
├── .gitignore                 # config.yaml, credentials.json, token.pickle, cache/
├── deploy/
│   └── tidbyt-calendar.service  # systemd unit (memorizator pattern)
├── src/tidbyt_calendar/
│   ├── __main__.py            # entrypoint: load config, start scheduler + Flask
│   ├── config.py              # config.yaml + env overlay (env wins)
│   ├── calendar_client.py     # OAuth + Google Calendar fetch → list[Event]
│   ├── render.py              # build .star JSON param, subprocess pixlet, push
│   └── tidbyt/
│       └── app.star           # 64×32 layout, 5 rows, marquee
└── tests/
    ├── test_config.py
    ├── test_calendar_client.py   # parsing/filtering with fixture API responses
    └── test_render.py            # payload shape; pixlet render smoke test
```

Secrets/credentials live outside the repo (e.g. `~/.tidbyt/calendar/`):
`credentials.json`, `token.pickle`. `config.yaml` is local (gitignored).

## 2. The Starlark tile (`app.star`)

Self-contained and parameterized so it could later back a store app (Portability
goal). Takes one positional param `data` = JSON, like `weather/`.

- **Param shape:**
  ```
  data = {"events": [{"date": "MM/DD", "title": "..."}, ...],  # 0..5 entries
          "message": "No Events" | "Calendar unavailable" | null}
  ```
  If `message` is set, render it centered and ignore `events`.
- **Layout:** `render.Root(child=render.Column(...))`, 5 fixed-height rows
  (`tom-thumb`, height 6, no spacing → 30px of 32). Each row is a `render.Row`:
  - left: `render.Text("MM/DD: ")` in `tom-thumb`.
  - right: title in a `render.Marquee(width=..., child=render.Text(title))` so it
    scrolls only when it overflows. Marquee loops continuously; rows are
    independent `Marquee`s. Tune to ~0.5s/frame (Pixlet marquee speed is fixed
    px/frame at ~20fps; pad/duplicate the text or set `delay`/`offset` so the loop
    reads at the desired cadence — validate visually in preview).
  - Fewer than 5 events → emit blank rows for the remainder.
- **Gotchas (from `DEVELOPING_FOR_TIDBYT.mdc`):** `load("encoding/json.star",
  "json")`; `render.Text(content=...)`; stick to `Root/Column/Row/Box/Text/
  Marquee`; no starred unpacking. Render at native 64×32, no scaling.

## 3. Calendar client (`calendar_client.py`)

- **OAuth** (user-OAuth, `memorizator/src/memorizator/mail.py` pattern):
  `_build_service(credentials_file, token_file)` → `InstalledAppFlow` on first
  run, else load pickled creds; refresh if `expired and refresh_token`; persist.
  Scope `https://www.googleapis.com/auth/calendar.readonly`. Build
  `googleapiclient.discovery.build("calendar", "v3", credentials=creds)`.
- **Fetch** `events().list(calendarId=<config>, timeMin=now(tz, RFC3339),
  maxResults=5, singleEvents=True, orderBy="startTime", timeZone=<config tz>)`.
- **No filtering:** show everything returned (no response-status check) — the user
  un-invites the Tidbyt account when they decline. Include all-day events (they
  have `start.date`, not `start.dateTime`).
- **Map → `Event(date_mmdd, title, start_dt)`**; format date in config tz; all-day
  and timed look identical. Up to 5, already sorted by start.
- **Timeout:** 10s on the API call; on any failure raise a typed error the caller
  turns into the `Calendar unavailable` frame.

## 4. Render + push (`render.py`)

- `build_payload(events) -> dict` → the `data` JSON above (or `{"message": ...}`).
- `render_tile(payload) -> bytes`: `subprocess.run([pixlet, "render", STAR_PATH,
  "data=" + json.dumps(payload, separators=(",",":")), "-o", out])`, read bytes.
  Resolve `STAR_PATH` relative to the source, not hardcoded.
- `push(image_bytes)`: `POST https://api.tidbyt.com/v0/devices/{TIDBYT_DEVICE_ID}/
  push`, `Authorization: Bearer {TIDBYT_API_TOKEN}`, body `installationID`
  (from config), base64 `image`, `contentType: image/webp`, `background: false`.
  Log non-200.

## 5. Service wiring (`__main__.py`)

- Load config (`config.py`: read `config.yaml`, overlay env, env wins; like
  weather's note). Resolve secrets from environment (sourced from `~/.zsh_secrets`
  by the systemd unit).
- `job()`: fetch → build payload (or `Calendar unavailable` on error) → render →
  push. Wrap so a fetch/render error still pushes the fallback frame.
- APScheduler `BackgroundScheduler`: run `job` at startup + every
  `refresh_interval_minutes` (default 15).
- Flask endpoints (iteration, weather/ parity): `GET /healthz`,
  `GET /tidbyt_preview.webp` (renders current payload), `POST /push` (force push).

## 6. Config (`config.example.yaml`)

```yaml
# Copy to config.yaml (gitignored). Secrets (TIDBYT_DEVICE_ID, TIDBYT_API_TOKEN)
# come from the environment, not here. Any field can be overridden by an env var
# of the same upper-case name (env wins).
calendar_id: "xxxxx@group.calendar.google.com"
timezone: "America/Los_Angeles"
refresh_interval_minutes: 15
installation_id: "calendar"
# Paths to OAuth artifacts (kept outside the repo):
credentials_file: "~/.tidbyt/calendar/credentials.json"
token_file: "~/.tidbyt/calendar/token.pickle"
```

## 7. One-time Google setup (step-by-step, run when implementing §3)

> Rendered here so it's ready; execute during the auth milestone.

1. Create the dedicated Google account for the Tidbyt calendar (or reuse the
   intended "Tidbyt" account). Create/identify the calendar to display and copy
   its **Calendar ID** (Calendar settings → "Integrate calendar") into
   `config.yaml` `calendar_id`.
2. In [console.cloud.google.com](https://console.cloud.google.com) **as that
   account**: create a project → **APIs & Services → Enable APIs → Google Calendar
   API**.
3. **OAuth consent screen**: User type **External**, app name, add the account as a
   **Test user**, scope `.../auth/calendar.readonly`. **Publish app → In
   production** (Testing-mode refresh tokens expire after 7 days; production
   removes that, no verification needed for personal use).
4. **Credentials → Create credentials → OAuth client ID → Desktop app** →
   download JSON → save as `credentials_file` (`~/.tidbyt/calendar/credentials.json`).
5. One-time consent, headless (no tunnel): `tidbyt-calendar-authorize` prints a
   URL → approve on any browser → copy the failed `localhost:8765/?code=...`
   address-bar URL → `tidbyt-calendar-authorize "<pasted-url>"` writes
   `token.pickle`. Thereafter the refresh token renews silently.

## 8. Deployment

- **systemd** (`deploy/tidbyt-calendar.service`, memorizator pattern): `Type=simple`,
  `Environment=HOME=/home/aksh`, `WorkingDirectory=...tidbyt_calendar`,
  `ExecStart=/usr/bin/zsh -c 'source /home/aksh/.zsh_secrets && exec .../.venv/bin/tidbyt-calendar'`,
  `Restart=always`. Pixlet must be on PATH or referenced by absolute path.
- **Docker** (alt): Dockerfile installs `pixlet_0.34.0_linux_amd64`, copies `src`,
  `CMD python -u -m tidbyt_calendar`. Pass secrets as env; mount the OAuth dir.

## 9. Build milestones

1. **Scaffold** — `pyproject.toml` (uv), package skeleton, `.gitignore`,
   `config.example.yaml`, empty `app.star`.
2. **Tile** — `app.star` renders fixed sample `data` to 64×32; iterate via
   `pixlet render` until 5 rows + marquee + `No Events`/`Calendar unavailable`
   frames look right. (No Google needed yet.)
3. **Calendar client** — OAuth + fetch + map; unit-test parsing against fixture
   JSON (all-day kept, ≤5, in-progress kept).
4. **Render+push** — `render.py`, verify a real push to the device shows the tile.
5. **Service** — `__main__.py` scheduler + Flask preview/push/health.
6. **Google setup** — run §7, point at the real calendar, end-to-end verify both
   SPEC scenarios (invited event appears; directly-created event appears).
7. **Deploy** — systemd unit (+ Dockerfile), install, confirm 15-min pushes log
   200, survive restart.
8. **README** — setup + run, mirroring the milestones.

## 10. Testing & verification

- **Tile:** `pixlet render src/tidbyt_calendar/tidbyt/app.star 'data={...}' -o
  /tmp/t.webp` for the event list, `No Events`, `Calendar unavailable`, and an
  overflowing-title case.
- **Client:** unit tests on fixture API responses — all-day included, in-progress
  included, capped at 5, tz formatting.
- **End-to-end:** `POST /push`, confirm the device tile; check both SPEC scenarios
  live.
- **Robustness:** kill network → expect `Calendar unavailable` pushed, service
  stays up; restart service → tile reappears.
