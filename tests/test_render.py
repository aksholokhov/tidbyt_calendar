"""Tests for payload building and a pixlet render smoke test."""

import datetime as dt
import shutil

import pytest

from tidbyt_calendar.calendar_client import Event
from tidbyt_calendar.render import build_payload, render_tile


def _ev(date: str, title: str, time: str = "09:00") -> Event:
    return Event(date_mmdd=date, time_hhmm=time, title=title, start=dt.datetime(2026, 1, 1))


def test_payload_with_events():
    payload = build_payload([_ev("06/22", "Standup"), _ev("06/23", "Review", time="")])
    assert payload["message"] is None
    assert payload["events"] == [
        {"date": "06/22", "time": "09:00", "title": "Standup"},
        {"date": "06/23", "time": "", "title": "Review"},
    ]


def test_empty_events_becomes_no_events_message():
    payload = build_payload([])
    assert payload["message"] == "No Events"
    assert payload["events"] == []


def test_explicit_message_overrides():
    payload = build_payload([], message="Calendar unavailable")
    assert payload["message"] == "Calendar unavailable"


@pytest.mark.skipif(shutil.which("pixlet") is None, reason="pixlet not installed")
def test_render_tile_produces_webp():
    payload = build_payload([_ev("06/22", "A long title that should scroll off")])
    image = render_tile(payload)
    assert image[:4] == b"RIFF" and image[8:12] == b"WEBP"


@pytest.mark.skipif(shutil.which("pixlet") is None, reason="pixlet not installed")
def test_render_message_frame():
    image = render_tile(build_payload([], message="Calendar unavailable"))
    assert image[:4] == b"RIFF" and image[8:12] == b"WEBP"
