"""Google Calendar access: OAuth (user flow) + fetch the next 5 events.

OAuth mirrors memorizator/src/memorizator/mail.py: InstalledAppFlow on first run,
then a refreshable pickled token. Read-only scope.

`parse_events` is a pure function (no network) so it can be unit-tested against
fixture API responses before any credentials exist.
"""

from __future__ import annotations

import datetime as dt
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
FETCH_TIMEOUT_SECONDS = 10
MAX_EVENTS = 5


class CalendarUnavailable(Exception):
    """Raised when events cannot be fetched (auth/network/API error)."""


@dataclass
class Event:
    date_mmdd: str  # "MM/DD" in the configured timezone
    time_hhmm: str  # "HH:MM" in the configured timezone, "" for all-day events
    title: str
    start: dt.datetime  # tz-aware, for ordering/debugging


def _tzinfo(timezone: str | None) -> dt.tzinfo:
    if timezone:
        return ZoneInfo(timezone)
    # Host local tz.
    return dt.datetime.now().astimezone().tzinfo or dt.UTC


def _parse_start(raw_start: dict[str, Any], tz: dt.tzinfo) -> dt.datetime:
    """Google event `start` is either {"dateTime": ...} or all-day {"date": ...}."""
    if "dateTime" in raw_start:
        # RFC3339; fromisoformat handles the trailing offset (and Z on 3.11+).
        value = raw_start["dateTime"].replace("Z", "+00:00")
        return dt.datetime.fromisoformat(value).astimezone(tz)
    # All-day event: midnight local on that date.
    d = dt.date.fromisoformat(raw_start["date"])
    return dt.datetime(d.year, d.month, d.day, tzinfo=tz)


def parse_events(items: list[dict[str, Any]], timezone: str | None) -> list[Event]:
    """Map raw Google API event items → up to MAX_EVENTS Events.

    No attendance filtering: everything on the calendar is shown (the user
    un-invites the Tidbyt account when they decline). All-day and timed events
    are treated identically.
    """
    tz = _tzinfo(timezone)
    events: list[Event] = []
    for item in items:
        start = item.get("start")
        if not start:  # cancelled/recurring-exception stubs lack start
            continue
        when = _parse_start(start, tz)
        # All-day events have {"date": ...} (no time); timed have {"dateTime": ...}.
        time_hhmm = when.strftime("%H:%M") if "dateTime" in start else ""
        title = item.get("summary") or "(no title)"
        events.append(
            Event(
                date_mmdd=when.strftime("%m/%d"),
                time_hhmm=time_hhmm,
                title=title,
                start=when,
            )
        )
    events.sort(key=lambda e: e.start)
    return events[:MAX_EVENTS]


def _build_service(credentials_file: Path, token_file: Path) -> Any:
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds: Any = pickle.loads(token_file.read_bytes()) if token_file.exists() else None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not credentials_file.exists():
                raise CalendarUnavailable(
                    f"OAuth client secrets not found at {credentials_file}. "
                    "Run the one-time Google setup (see DEV_PLAN.md §7)."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_file), SCOPES)
            creds = flow.run_local_server(port=0)
        token_file.parent.mkdir(parents=True, exist_ok=True)
        token_file.write_bytes(pickle.dumps(creds))
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def fetch_events(
    calendar_id: str,
    credentials_file: Path,
    token_file: Path,
    timezone: str | None,
) -> list[Event]:
    """Fetch the next MAX_EVENTS upcoming events (from now, includes in-progress)."""
    try:
        service = _build_service(credentials_file, token_file)
        now = dt.datetime.now(dt.UTC).isoformat()
        resp = (
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=now,
                maxResults=MAX_EVENTS,
                singleEvents=True,
                orderBy="startTime",
                timeZone=timezone or "UTC",
            )
            .execute(num_retries=2)
        )
    except CalendarUnavailable:
        raise
    except Exception as exc:  # network, auth, API — all become the fallback frame
        raise CalendarUnavailable(str(exc)) from exc
    return parse_events(resp.get("items", []), timezone)
