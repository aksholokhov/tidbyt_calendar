# Tidbyt Calendar

Shows the next 5 events from a Google calendar on a Tidbyt. A local Python
service fetches the calendar, renders a 64×32 Pixlet tile (`tom-thumb`, 5 rows of
`MM/DD: title` with overflowing titles scrolling), and pushes it to the device
every 15 minutes. See [`SPEC.md`](./SPEC.md) and [`DEV_PLAN.md`](./DEV_PLAN.md).

## Status

Working end-to-end: fetches the live calendar, renders the tile, and pushes to the
device (verified HTTP 200). The tile renderer, config layer, calendar client,
render/push, scheduler, and Flask preview server are complete and unit-tested
(`uv run pytest`). To run it as a daemon, install the systemd unit (see Deploy).

## Requirements

- [`uv`](https://docs.astral.sh/uv/) and [`pixlet`](https://github.com/tidbyt/pixlet) v0.34.0 on PATH.
- `TIDBYT_DEVICE_ID` and `TIDBYT_API_TOKEN` in `~/.zsh_secrets` (already present).

## Setup

```bash
uv sync                      # create .venv, install deps + console script
cp config.example.yaml config.yaml   # then edit calendar_id + timezone
```

Then do the **one-time Google setup** (below) to create credentials, and run.

## Run

```bash
# Loads ~/.zsh_secrets for TIDBYT_* then starts scheduler + preview server.
zsh -c 'source ~/.zsh_secrets && uv run tidbyt-calendar'
```

Endpoints (default `127.0.0.1:8080`):

- `GET /tidbyt_preview.webp` — render the current tile (no push).
- `POST /push` — force a render + push now.
- `GET /healthz`.

Render a tile by hand for layout iteration (no Google needed):

```bash
pixlet render src/tidbyt_calendar/tidbyt/app.star \
  'data={"events":[{"date":"06/22","title":"Mom birthday"}],"message":null}' -o /tmp/t.webp
```

## One-time Google setup

You need OAuth **user** credentials for the Google account that owns the calendar.
This is the only step that requires you (browser consent); everything else is
automated afterward (the refresh token renews silently).

1. **Create / pick the account & calendar.** Use the dedicated "Tidbyt" Google
   account. In Google Calendar → **Settings** → select the calendar →
   **Integrate calendar** → copy the **Calendar ID** into `config.yaml`
   (`calendar_id`). The account's own primary calendar's ID is just its email.

2. **Enable the API.** At [console.cloud.google.com](https://console.cloud.google.com),
   signed in **as that account**: create a project → **APIs & Services → Library**
   → enable **Google Calendar API**.

3. **OAuth consent screen.** **APIs & Services → OAuth consent screen** →
   User type **External** → fill app name/email → add scope
   `https://www.googleapis.com/auth/calendar.readonly` → add that same Google
   account as a **Test user**.

   **Then click "Publish app" → "In production".** A refresh token issued while
   the app is in *Testing* expires after **7 days**; publishing removes that cap.
   No Google verification is needed for personal use — at consent you'll just
   click through an "unverified app" notice (**Advanced → Go to … (unsafe)**).

4. **Create the client.** **APIs & Services → Credentials → Create credentials →
   OAuth client ID → Application type: Desktop app** → Create → **Download JSON**.
   Save it as the `credentials_file` path from `config.yaml`:

   ```bash
   mkdir -p ~/.tidbyt/calendar
   mv ~/Downloads/client_secret_*.json ~/.tidbyt/calendar/credentials.json
   ```

5. **One-time consent (no browser needed on the host).** Headless-friendly,
   two commands — no SSH tunnel required:

   ```bash
   # Step 1: print a consent URL.
   uv run tidbyt-calendar-authorize
   ```

   Open that URL on **any** browser, sign in as the calendar account, approve
   (click through the unverified-app notice). The browser then tries to load
   `http://localhost:8765/?...code=...` and shows "site can't be reached" — that
   is expected. Copy the **full address-bar URL** and exchange it:

   ```bash
   # Step 2: exchange the code for a refreshable token (writes token.pickle).
   uv run tidbyt-calendar-authorize "<pasted-url>"
   ```

   From then on the service refreshes the token automatically. Verify:

   ```bash
   zsh -c 'source ~/.zsh_secrets && uv run tidbyt-calendar'
   curl -s localhost:8080/tidbyt_preview.webp -o /tmp/preview.webp
   ```

`credentials.json` and `token.pickle` are secrets — kept outside the repo and
gitignored. Never commit them.

## Deploy

- **systemd:** install `deploy/tidbyt-calendar.service` (sources `~/.zsh_secrets`,
  runs the venv entrypoint, `Restart=always`):

  ```bash
  sudo cp deploy/tidbyt-calendar.service /etc/systemd/system/
  sudo systemctl daemon-reload && sudo systemctl enable --now tidbyt-calendar
  journalctl -u tidbyt-calendar -f
  ```

- **Docker:** `docker build -t tidbyt-calendar .` then run with `config.yaml`, the
  OAuth dir, and `TIDBYT_*` env mounted/passed (see the `Dockerfile` comment).

## Tests

```bash
uv run pytest      # parsing, config, payload, pixlet render smoke tests
uv run ruff check src tests
```
