# Tidbyt Calendar — Spec

## What is it

A Tidbyt app that monitors a pre-specified Google calendar and shows the next 5
upcoming events on the 64×32 display.

## Architecture

**A — Local push server (Python + Pixlet).** A long-running host-side Python
process fetches the calendar via the Google Calendar API, renders the `.star` app
to a 64×32 animated `.webp` with Pixlet, and pushes it to the device via
`POST api.tidbyt.com/v0/devices/{id}/push` on a schedule. This mirrors the
existing `weather` app (Flask + APScheduler + Pixlet) and `memorizator`'s Google
integration, and survives the Tidbyt cloud wind-down (post-Modal acquisition).

The Tidbyt store path (pure-Starlark + Tidbyt OAuth handler) is **out of scope for
v1**, but the render/layout logic stays in a clean standalone `.star` so it could
be submitted later. See "Portability".

**Deployment host:** long-running process, mirroring `weather/` and `memorizator`:
- Flask app + APScheduler `BackgroundScheduler` for the periodic fetch/render/push.
- Runs as a **systemd unit** that sources `~/.zsh_secrets` then execs the venv
  entrypoint (the `memorizator.service` pattern). A Dockerfile (Pixlet baked in,
  like `weather/`) is provided as an alternative runner.
- Flask also exposes a preview endpoint and a manual `/push` endpoint for
  iteration (mirrors `weather/`).

## How it looks

- 64×32 canvas, `tom-thumb` font (height 6px → 5 rows fill 32px with no vertical
  spacing). Black background. Native render, no scaling.
- 5 rows, one per event: `MM/DD: HH:MM <Event title>`
- **Date format:** `MM/DD` (month/day). No year, no relative labels.
- **Time:** `HH:MM` (24h) shown at the start of the scrollable region, before the
  title. All-day events have no time (title only).
- **Colors:** date in an amber accent (`#ff9e3d`), time in a cyan accent
  (`#46c8ff`), titles white. Background black.
- **Layout:** the `MM/DD:` date is a fixed prefix that stays put; the `HH:MM` +
  title share a marquee that scrolls when it overflows.
- **Marquee:** scroll loops continuously, rows scroll **independently**. (The
  animation is baked into the `.webp`, so a single push yields continuous on-device
  scrolling between fetches.)
- **Fewer than 5 events:** remaining rows are left blank. If there are **zero**
  upcoming events, render `No Events`.

## Data — which events

- **Source:** a single Google calendar identified by a **`calendarId` from
  config** (not `primary`). The Tidbyt Google account must have that calendar; the
  invited/created-event scenarios assume events land on this calendar.
- Next 5 events, ordered by start time, recurring events expanded
  (`singleEvents=true&orderBy=startTime`).
- **Window:** the next 5 starting from **now**, including events currently in
  progress. All-day events are included.
- **No attendance filtering:** show everything on the calendar regardless of
  response status. Declined events never appear because the user un-invites the
  Tidbyt account when they decline (so it falls off the calendar).
- **Timezone:** rendered in a configurable IANA `timezone` (config field),
  defaulting to the host's local timezone (`America/Los_Angeles`).

## Refresh cadence

- Pull the calendar and re-render/push **every 15 minutes**.
- Push every cycle (unconditionally) for v1; skip-if-unchanged is a later
  optimization.
- Fetch timeout: 10s, per the Tidbyt dev guidance.

## Authentication

Google Calendar read access via **user-OAuth**, host-side (Python). Pattern
follows `memorizator/src/memorizator/mail.py`: `InstalledAppFlow` for first-time
consent, then a refreshable token persisted locally and refreshed on expiry.
Scope: `https://www.googleapis.com/auth/calendar.readonly`.

- **A brand-new Google account is created for the Tidbyt calendar**, and its OAuth
  client credentials are fetched fresh. The dev plan includes a step-by-step for
  creating the account, the OAuth client, and running the one-time consent flow.
- **Credential storage:** OAuth client secrets in a `credentials.json` and the
  persisted user token as `token.pickle`, both gitignored and kept out of the
  repo (e.g. under `~/.tidbyt/calendar/`). Never committed.

## Secrets & config

No secrets ever committed. Secrets come from `~/.zsh_secrets` (already contains
`TIDBYT_DEVICE_ID`, `TIDBYT_API_TOKEN`). Non-secret config lives in a committed
`config.yaml` (memorizator pattern) with env override (env wins). Fields:

- `calendar_id` — source Google calendar.
- `timezone` — IANA tz for rendering (default host local).
- `refresh_interval_minutes` — default 15.
- `installation_id` — Tidbyt installation ID (e.g. `calendar`).

## Error & empty states

Per the Tidbyt dev guidance: fail fast on render errors, degrade gracefully on
data/network errors so the device still shows something.

- On API failure / expired-and-unrefreshable auth / network timeout: render
  **`Calendar unavailable`** and push that frame.

## Scenarios to support

1. A user created a "Tidbyt" Google account and a calendar for it, then invited
   the Tidbyt user to a calendar event. The event shows up on Tidbyt.
2. A user created a calendar event directly in Tidbyt's calendar. It shows up.

## Non-goals (v1)

- Creating/editing events
- Multiple devices
- Reminders/notifications
- Multiple calendars
- Store submission

## Portability (store later)

Keep the `.star` self-contained and parameterized — events are passed in as a
render param (JSON blob) — so the same layout could later back a pure-Starlark
store app. The Python server is the only piece that's local-only.

## References

- **Working Pixlet app for layout/push/scheduler patterns:** `~/home-services/weather/`.
- **Google OAuth + config pattern:** `~/home-services/memorizator`
  (`src/memorizator/mail.py`, `config.yaml`, `deploy/memorizator.service`).
- **Dev guidance & gotchas:** `~/home-services/DEVELOPING_FOR_TIDBYT.mdc`,
  `tidbyt.dev`.
