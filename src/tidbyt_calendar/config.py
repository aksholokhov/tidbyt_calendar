"""Configuration: load config.yaml, overlay environment variables (env wins).

Non-secret settings live in config.yaml. Secrets (TIDBYT_DEVICE_ID,
TIDBYT_API_TOKEN) come from the environment only. Any config field can be
overridden by an env var of the same UPPER_CASE name.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, fields
from pathlib import Path

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.yaml"

# Fields here can be overridden by env vars of the same upper-case name.
_STR_FIELDS = (
    "calendar_id",
    "timezone",
    "installation_id",
    "credentials_file",
    "token_file",
    "host",
)
_INT_FIELDS = ("refresh_interval_minutes", "port")


@dataclass
class Config:
    # Calendar / rendering
    calendar_id: str
    timezone: str | None = None  # None → host local tz
    refresh_interval_minutes: int = 15
    installation_id: str = "calendar"

    # OAuth artifact paths (expanded, kept outside the repo)
    credentials_file: Path = Path("~/.tidbyt/calendar/credentials.json")
    token_file: Path = Path("~/.tidbyt/calendar/token.pickle")

    # Flask preview/control server
    host: str = "127.0.0.1"
    port: int = 8080

    # Secrets (from environment only; never from config.yaml)
    tidbyt_device_id: str | None = None
    tidbyt_api_token: str | None = None


def load_config(path: Path | None = None) -> Config:
    path = path or Path(os.environ.get("TIDBYT_CALENDAR_CONFIG", DEFAULT_CONFIG_PATH))
    raw: dict[str, object] = {}
    if path.exists():
        loaded = yaml.safe_load(path.read_text()) or {}
        if not isinstance(loaded, dict):
            raise ValueError(f"{path} must contain a YAML mapping")
        raw = loaded

    # Env overrides (env wins) for the simple scalar fields.
    for name in _STR_FIELDS:
        if (val := os.environ.get(name.upper())) is not None:
            raw[name] = val
    for name in _INT_FIELDS:
        if (val := os.environ.get(name.upper())) is not None:
            raw[name] = int(val)

    known = {f.name for f in fields(Config)}
    kwargs = {k: v for k, v in raw.items() if k in known}

    if "calendar_id" not in kwargs:
        raise ValueError(
            f"calendar_id is required (set it in {path} or the CALENDAR_ID env var)"
        )

    for key in ("credentials_file", "token_file"):
        if key in kwargs:
            kwargs[key] = Path(str(kwargs[key])).expanduser()

    cfg = Config(**kwargs)  # type: ignore[arg-type]
    cfg.credentials_file = Path(cfg.credentials_file).expanduser()
    cfg.token_file = Path(cfg.token_file).expanduser()

    # Secrets strictly from the environment.
    cfg.tidbyt_device_id = os.environ.get("TIDBYT_DEVICE_ID")
    cfg.tidbyt_api_token = os.environ.get("TIDBYT_API_TOKEN")
    return cfg
