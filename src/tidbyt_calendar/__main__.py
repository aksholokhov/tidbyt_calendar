"""Service entrypoint: scheduler (fetch → render → push) + Flask preview/control.

Mirrors ~/home-services/weather/: a long-running process with an APScheduler
BackgroundScheduler driving periodic pushes, plus Flask endpoints for iteration.
"""

from __future__ import annotations

import logging

from flask import Flask, Response, jsonify

from .calendar_client import CalendarUnavailable, fetch_events
from .config import Config, load_config
from .render import build_payload, push_tile, render_tile

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("tidbyt_calendar")

app = Flask(__name__)
_cfg: Config | None = None


def cfg() -> Config:
    global _cfg
    if _cfg is None:
        _cfg = load_config()
    return _cfg


def render_current() -> bytes:
    """Fetch the calendar and render the tile, falling back to a message frame."""
    c = cfg()
    try:
        events = fetch_events(c.calendar_id, c.credentials_file, c.token_file, c.timezone)
        payload = build_payload(events)
    except CalendarUnavailable as exc:
        logger.warning("Calendar fetch failed: %s", exc)
        payload = build_payload([], message="Calendar unavailable")
    return render_tile(payload)


def push_once() -> int:
    """Render the current tile and push it. Returns the push HTTP status."""
    c = cfg()
    image = render_current()
    if not c.tidbyt_device_id or not c.tidbyt_api_token:
        logger.warning("TIDBYT_DEVICE_ID / TIDBYT_API_TOKEN missing; skipping push")
        return 0
    code = push_tile(image, c.tidbyt_device_id, c.tidbyt_api_token, c.installation_id)
    logger.info("Push: HTTP %s", code)
    return code


@app.route("/healthz")
def healthz() -> Response:
    return jsonify({"status": "ok"})


@app.route("/tidbyt_preview.webp")
def preview() -> Response:
    return Response(render_current(), mimetype="image/webp")


@app.route("/push", methods=["POST"])
def push_endpoint() -> Response:
    return jsonify({"status": "pushed", "http": push_once()})


def main() -> None:
    from apscheduler.schedulers.background import BackgroundScheduler

    c = cfg()
    sched = BackgroundScheduler()
    sched.add_job(push_once, "interval", minutes=c.refresh_interval_minutes, id="push")
    sched.add_job(push_once, "date", id="push_startup")  # push immediately on boot
    sched.start()
    logger.info(
        "Started: calendar=%s every %dm, preview at http://%s:%d/tidbyt_preview.webp",
        c.calendar_id,
        c.refresh_interval_minutes,
        c.host,
        c.port,
    )
    app.run(host=c.host, port=c.port)


if __name__ == "__main__":
    main()
