"""Build the .star payload, render it with Pixlet, push to the Tidbyt device."""

from __future__ import annotations

import base64
import json
import os
import subprocess
import tempfile
from pathlib import Path

import requests

from .calendar_client import Event

STAR_PATH = Path(__file__).resolve().parent / "tidbyt" / "app.star"
PIXLET_BIN = os.environ.get("PIXLET_BIN", "pixlet")
PUSH_URL = "https://api.tidbyt.com/v0/devices/{device_id}/push"


def build_payload(events: list[Event], message: str | None = None) -> dict[str, object]:
    """Render param for app.star.

    If `message` is set (e.g. "Calendar unavailable"), it is shown instead of the
    list. Empty event list renders as "No Events" via the message channel.
    """
    if message is None and not events:
        message = "No Events"
    return {
        "events": [
            {"date": e.date_mmdd, "time": e.time_hhmm, "title": e.title} for e in events
        ],
        "message": message,
    }


def render_tile(payload: dict[str, object]) -> bytes:
    """Run `pixlet render` and return the WEBP bytes."""
    data = json.dumps(payload, separators=(",", ":"))
    with tempfile.NamedTemporaryFile(suffix=".webp", delete=False) as tmp:
        out_path = tmp.name
    try:
        subprocess.run(
            [PIXLET_BIN, "render", str(STAR_PATH), f"data={data}", "-o", out_path],
            check=True,
            capture_output=True,
            text=True,
        )
        return Path(out_path).read_bytes()
    finally:
        Path(out_path).unlink(missing_ok=True)


def push_tile(
    image: bytes,
    device_id: str,
    api_token: str,
    installation_id: str,
) -> int:
    """Push the rendered tile to the device. Returns the HTTP status code."""
    url = PUSH_URL.format(device_id=device_id)
    body = {
        "installationID": installation_id,
        "image": base64.b64encode(image).decode("ascii"),
        "contentType": "image/webp",
        "background": False,
    }
    resp = requests.post(
        url,
        json=body,
        headers={"Authorization": f"Bearer {api_token}"},
        timeout=15,
    )
    return resp.status_code
