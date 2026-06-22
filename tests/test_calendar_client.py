"""Tests for event parsing — pure, no network/credentials."""

from tidbyt_calendar.calendar_client import parse_events

TZ = "America/Los_Angeles"


def _timed(dt_str: str, summary: str) -> dict:
    return {"start": {"dateTime": dt_str}, "summary": summary}


def _allday(date_str: str, summary: str) -> dict:
    return {"start": {"date": date_str}, "summary": summary}


def test_timed_has_time_allday_has_none():
    items = [
        _timed("2026-06-22T09:30:00-07:00", "Standup"),
        _allday("2026-06-23", "Mom birthday"),
    ]
    events = parse_events(items, TZ)
    assert [(e.date_mmdd, e.time_hhmm, e.title) for e in events] == [
        ("06/22", "09:30", "Standup"),
        ("06/23", "", "Mom birthday"),  # all-day -> no time
    ]


def test_capped_at_five():
    items = [_allday(f"2026-07-0{i}", f"E{i}") for i in range(1, 9)]
    events = parse_events(items, TZ)
    assert len(events) == 5
    assert [e.title for e in events] == ["E1", "E2", "E3", "E4", "E5"]


def test_sorted_by_start():
    items = [
        _timed("2026-06-25T12:00:00-07:00", "Later"),
        _timed("2026-06-22T08:00:00-07:00", "Earlier"),
    ]
    events = parse_events(items, TZ)
    assert [e.title for e in events] == ["Earlier", "Later"]


def test_no_attendance_filtering_keeps_everything():
    # A declined event is still shown — filtering is intentionally absent.
    items = [
        {
            "start": {"dateTime": "2026-06-22T09:00:00-07:00"},
            "summary": "Declined meeting",
            "attendees": [{"self": True, "responseStatus": "declined"}],
        }
    ]
    events = parse_events(items, TZ)
    assert [e.title for e in events] == ["Declined meeting"]


def test_missing_summary_and_start():
    items = [
        {"start": {"date": "2026-06-22"}},  # no summary
        {"summary": "no start, skipped"},  # no start -> dropped
    ]
    events = parse_events(items, TZ)
    assert [(e.date_mmdd, e.title) for e in events] == [("06/22", "(no title)")]


def test_utc_datetime_converts_to_configured_tz():
    # 2026-01-01T02:00Z is still 2025-12-31 18:00 in Los Angeles.
    items = [_timed("2026-01-01T02:00:00Z", "NYE")]
    events = parse_events(items, TZ)
    assert events[0].date_mmdd == "12/31"
