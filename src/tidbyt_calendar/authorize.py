"""One-time OAuth consent for the Tidbyt calendar Google account.

Manual, headless-friendly, no tunnel needed. Two steps:

  1) `tidbyt-calendar-authorize`              -> prints a consent URL.
     Open it on ANY machine, sign in as the calendar account, approve.
     The browser will then try to load http://localhost:8765/?code=... and
     fail ("can't connect") — that is expected. Copy the FULL URL from the
     address bar.

  2) `tidbyt-calendar-authorize "<pasted-url-or-code>"` -> exchanges it for a
     token and writes token.pickle. The service refreshes it from then on.

State + PKCE verifier are stashed between the two steps in a pending file next to
the token. The flow requests offline access + prompt=consent so a refresh token
is always issued (keep the OAuth consent screen in "production" to dodge the
7-day testing-mode cap — see README).
"""

from __future__ import annotations

import json
import pickle
import sys
from urllib.parse import parse_qs, urlparse

from .calendar_client import SCOPES
from .config import load_config

REDIRECT_URI = "http://localhost:8765/"


def _pending_path():
    return load_config().token_file.parent / ".oauth_pending.json"


def _print_url() -> None:
    from google_auth_oauthlib.flow import Flow

    cfg = load_config()
    flow = Flow.from_client_secrets_file(
        str(cfg.credentials_file), scopes=SCOPES, redirect_uri=REDIRECT_URI
    )
    auth_url, state = flow.authorization_url(
        access_type="offline", prompt="consent", include_granted_scopes="true"
    )
    pending = _pending_path()
    pending.parent.mkdir(parents=True, exist_ok=True)
    pending.write_text(json.dumps({"state": state, "code_verifier": flow.code_verifier}))

    print("\n>>> Open this URL on any browser, sign in as the calendar account, approve.")
    print(">>> The redirect to localhost:8765 will fail to load — that's fine.")
    print(">>> Copy the FULL address-bar URL and run:")
    print('>>>   tidbyt-calendar-authorize "<pasted-url>"\n')
    print(auth_url)
    print()


def _extract_code(arg: str) -> str:
    if arg.startswith("http"):
        qs = parse_qs(urlparse(arg).query)
        if "code" not in qs:
            raise SystemExit(f"No ?code= found in: {arg}")
        return qs["code"][0]
    return arg.strip()


def _exchange(arg: str) -> None:
    from google_auth_oauthlib.flow import Flow

    cfg = load_config()
    pending = _pending_path()
    if not pending.exists():
        raise SystemExit("No pending auth. Run `tidbyt-calendar-authorize` first.")
    saved = json.loads(pending.read_text())

    flow = Flow.from_client_secrets_file(
        str(cfg.credentials_file),
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
        state=saved["state"],
    )
    flow.code_verifier = saved["code_verifier"]
    flow.fetch_token(code=_extract_code(arg))

    creds = flow.credentials
    cfg.token_file.parent.mkdir(parents=True, exist_ok=True)
    cfg.token_file.write_bytes(pickle.dumps(creds))
    pending.unlink(missing_ok=True)
    print(f"Token written to {cfg.token_file}")
    print(f"refresh_token present: {bool(creds.refresh_token)}")


def main() -> None:
    if len(sys.argv) > 1:
        _exchange(sys.argv[1])
    else:
        _print_url()


if __name__ == "__main__":
    main()
