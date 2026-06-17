#!/usr/bin/env python3
"""One-time GA4 authorization for the PracticeRank Google account.

Run this LOCALLY (it opens a browser). Log in as the account customers already
add to their GA4 properties — e.g. kdoherty@practicerank.ai. It prints the
three env vars to paste into the droplet `.env`; after that the weekly job pulls
GA4 data for every property that account can access, with no per-customer
service-account grant.

Prerequisites
-------------
1. In Google Cloud Console, create an **OAuth client ID** of type **Desktop app**
   (APIs & Services → Credentials → Create credentials → OAuth client ID).
   Download its JSON.
2. On the OAuth **consent screen**, add the scope
   ``https://www.googleapis.com/auth/analytics.readonly``.
   - If practicerank.ai is a Google **Workspace** org, set the consent screen to
     **Internal** — no verification needed and the refresh token does NOT expire.
   - If it's External, add your account as a **Test user** (note: test-mode
     refresh tokens for sensitive scopes expire after 7 days — publish/verify the
     app, or use Internal, for a long-lived token).
3. Enable the **Google Analytics Data API** in the same project.

Usage
-----
    pip install google-auth-oauthlib

    # Either point at the downloaded JSON:
    python3 scripts/ga4_authorize.py /path/to/oauth_client.json

    # …or pass the Desktop-app client id/secret directly:
    python3 scripts/ga4_authorize.py --client-id XXX.apps.googleusercontent.com --client-secret GOCSPX-...
"""

from __future__ import annotations

import sys

SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]


def _config_from(cid, csec):
    return {"installed": {
        "client_id": cid,
        "client_secret": csec,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"],
    }}


def _flow_from_args(argv):
    """Build an InstalledAppFlow from, in priority order:
    1. --client-id/--client-secret args
    2. a secrets-file path arg
    3. GA4_OAUTH_CLIENT_ID/GA4_OAUTH_CLIENT_SECRET from the environment (.env)
    """
    from google_auth_oauthlib.flow import InstalledAppFlow

    if "--client-id" in argv:
        cid = argv[argv.index("--client-id") + 1]
        csec = argv[argv.index("--client-secret") + 1]
        return InstalledAppFlow.from_client_config(_config_from(cid, csec), scopes=SCOPES)

    file_args = [a for a in argv[1:] if not a.startswith("--")]
    if file_args:
        return InstalledAppFlow.from_client_secrets_file(file_args[0], scopes=SCOPES)

    # Fall back to env (loads .env if python-dotenv is available).
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    import os
    cid = os.environ.get("GA4_OAUTH_CLIENT_ID")
    csec = os.environ.get("GA4_OAUTH_CLIENT_SECRET")
    if cid and csec:
        print("Using GA4_OAUTH_CLIENT_ID / GA4_OAUTH_CLIENT_SECRET from environment (.env).")
        return InstalledAppFlow.from_client_config(_config_from(cid, csec), scopes=SCOPES)
    return None


def main():
    flow = _flow_from_args(sys.argv)
    if flow is None:
        print("No credentials found. Provide one of:")
        print("  python3 scripts/ga4_authorize.py /path/to/oauth_client.json")
        print("  python3 scripts/ga4_authorize.py --client-id XXX --client-secret YYY")
        print("  (or set GA4_OAUTH_CLIENT_ID / GA4_OAUTH_CLIENT_SECRET in .env)")
        sys.exit(1)
    # access_type=offline + prompt=consent guarantees a refresh token is returned.
    creds = flow.run_local_server(
        port=0, access_type="offline", prompt="consent",
        authorization_prompt_message="Log in as the PracticeRank account (e.g. kdoherty@practicerank.ai)…",
    )

    if not creds.refresh_token:
        print("\nNo refresh token returned. Re-run; ensure prompt=consent and that you "
              "haven't previously authorized without offline access.")
        sys.exit(2)

    values = {
        "GA4_OAUTH_CLIENT_ID": creds.client_id,
        "GA4_OAUTH_CLIENT_SECRET": creds.client_secret,
        "GA4_OAUTH_REFRESH_TOKEN": creds.refresh_token,
    }
    written = _write_env(values)
    if written:
        print(f"\n✅ Saved GA4 OAuth credentials to {written}")
        print("   (incl. GA4_OAUTH_REFRESH_TOKEN). Next: deploy so the droplet picks them up.")
    else:
        print("\n# Could not locate .env — paste these in manually:\n")
        for k, v in values.items():
            print(f"{k}={v}")


def _write_env(values: dict) -> str | None:
    """Insert/update the given keys in the repo .env. Returns the path, or None."""
    import os
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    env_path = os.path.abspath(env_path)
    if not os.path.exists(env_path):
        return None
    with open(env_path, "r") as f:
        lines = f.readlines()

    remaining = dict(values)
    out = []
    for line in lines:
        stripped = line.lstrip("# ").rstrip("\n")
        key = stripped.split("=", 1)[0] if "=" in stripped else ""
        if key in remaining:
            out.append(f"{key}={remaining.pop(key)}\n")  # replace (also un-comments placeholder)
        else:
            out.append(line)
    for key, val in remaining.items():  # any not already present → append
        out.append(f"{key}={val}\n")

    with open(env_path, "w") as f:
        f.writelines(out)
    return env_path


if __name__ == "__main__":
    main()
