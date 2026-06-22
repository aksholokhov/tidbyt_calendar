# What this is

A **local Python + Pixlet push server** that shows the next 5 Google Calendar
events on a Tidbyt. It fetches a calendar, renders a 64×32 `.star` tile with
`pixlet`, and pushes it to the device every 15 min. It is **not** a pure-Starlark
store app — fetching/auth/scheduling all run host-side in Python. Decisions in
@SPEC.md, architecture/layout in @DEV_PLAN.md, setup/run/OAuth/deploy in @README.md.

# Layout (source of truth: src/tidbyt_calendar/tidbyt/app.star)

- 64×32, `tom-thumb` (6px), 5 rows of `MM/DD: [HH:MM ]title`.
- `MM/DD:` is a fixed prefix (**amber** `#ff9e3d`); the rest is a marquee that
  scrolls per-row — `HH:MM` **cyan** `#46c8ff`, title **white**. All-day = no time.
- Events flow Python→star as a `data` JSON param: `{"events":[{date,time,title}],
  "message": null | "No Events" | "Calendar unavailable"}`.

# Commands

```bash
uv run pytest -q                 # tests
uv run ruff check src tests      # lint (fix: --fix)
# render a tile (no Google needed):
pixlet render src/tidbyt_calendar/tidbyt/app.star 'data={"events":[{"date":"06/22","time":"17:00","title":"x"}],"message":null}' -o /tmp/t.webp
# OAuth (two-step, headless): prints URL, then exchange the pasted redirect URL:
uv run tidbyt-calendar-authorize ; uv run tidbyt-calendar-authorize "<pasted-url>"
systemctl status tidbyt-calendar ; journalctl -u tidbyt-calendar -f   # the daemon
```

# Verifying a tile change — always look at it

A `.star` edit isn't verified until rendered AND viewed (and `pytest`). Pixlet
animates marquees into the webp, so render, extract the first frame to an
upscaled PNG, and Read it:

```bash
uv run --with pillow python3 -c "from PIL import Image; im=Image.open('/tmp/t.webp'); im.seek(0); im.convert('RGB').resize((384,192),Image.NEAREST).save('/tmp/t.png')"
```

To verify the full live path, source secrets first:
`zsh -c 'source ~/.zsh_secrets && uv run ...'` (gives `TIDBYT_*`).

# Pixlet / Starlark rules

- `render.Text(content=...)`, `load("encoding/json.star", "json")`. Stick to
  `Root/Column/Row/Box/Stack/Padding/Marquee/Text/WrappedText`. No starred unpacking.
- Render native 64×32, never scale. `tom-thumb` is 6px → 5 rows fill 30px.
- A `Box` **centers** its child; if the child is wider it clips both sides. Measure
  glyph widths empirically (render + inspect pixels) rather than guessing.
- Non-interactive contexts have no `~/.local/bin` on PATH — call pixlet via
  `PIXLET_BIN` / absolute path (the systemd unit already does).

# Secrets & safety

- Never commit secrets. `config.yaml`, `credentials.json`, `token.pickle` are
  gitignored; OAuth artifacts live in `~/.tidbyt/calendar/`, `TIDBYT_*` in
  `~/.zsh_secrets`. Only env-var *names* belong in tracked files.
- **A device push is a real outward action** — preview locally; push only when
  asked or when verifying end-to-end.

# Repo etiquette

- Commit/push only when asked. `main` tracks `origin`.
- Don't duplicate @README.md / @SPEC.md / @DEV_PLAN.md here — update them instead.
