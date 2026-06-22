"""Tests for config loading and env overlay."""

from pathlib import Path

import pytest

from tidbyt_calendar.config import load_config


def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text(body)
    return p


def test_loads_yaml(tmp_path, monkeypatch):
    monkeypatch.delenv("CALENDAR_ID", raising=False)
    p = _write(tmp_path, "calendar_id: abc@group.calendar.google.com\nport: 9000\n")
    cfg = load_config(p)
    assert cfg.calendar_id == "abc@group.calendar.google.com"
    assert cfg.port == 9000
    assert cfg.refresh_interval_minutes == 15  # default


def test_env_overrides_win(tmp_path, monkeypatch):
    p = _write(tmp_path, "calendar_id: from_file\nrefresh_interval_minutes: 15\n")
    monkeypatch.setenv("CALENDAR_ID", "from_env")
    monkeypatch.setenv("REFRESH_INTERVAL_MINUTES", "5")
    cfg = load_config(p)
    assert cfg.calendar_id == "from_env"
    assert cfg.refresh_interval_minutes == 5


def test_missing_calendar_id_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("CALENDAR_ID", raising=False)
    p = _write(tmp_path, "timezone: UTC\n")
    with pytest.raises(ValueError, match="calendar_id is required"):
        load_config(p)


def test_paths_expanded(tmp_path, monkeypatch):
    monkeypatch.delenv("CALENDAR_ID", raising=False)
    p = _write(tmp_path, "calendar_id: x\ncredentials_file: ~/creds.json\n")
    cfg = load_config(p)
    assert cfg.credentials_file.is_absolute()
    assert "~" not in str(cfg.credentials_file)


def test_secrets_from_env_only(tmp_path, monkeypatch):
    monkeypatch.delenv("CALENDAR_ID", raising=False)
    monkeypatch.setenv("TIDBYT_DEVICE_ID", "dev123")
    monkeypatch.setenv("TIDBYT_API_TOKEN", "tok456")
    p = _write(tmp_path, "calendar_id: x\n")
    cfg = load_config(p)
    assert cfg.tidbyt_device_id == "dev123"
    assert cfg.tidbyt_api_token == "tok456"
