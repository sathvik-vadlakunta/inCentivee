#!/usr/bin/env python3
"""Mint a Google Business Profile refresh token for the agency ops account.

One-time, run LOCALLY (it opens a browser). Reuses the existing **Desktop** OAuth client
("PracticeRank GA4 CLI", project micro-primer-495420-v5). When the browser opens, sign in as
the **ops account that is a Manager on the client listings** — `kdoherty@practicerank.ai`
(the Leadsie-connected account that already sees Paradigm + Hilltop). The script prints the
three GBP_OAUTH_* values to paste into the droplet .env.

Scope: https://www.googleapis.com/auth/business.manage (covers all GBP read+write).
Note: the token mints fine BEFORE the API allowlist is approved; the API *calls* just 403
until case 0-1827000040711 clears (~Jul 7-10). So you can run this now and be ready.

Usage:
    pip install google-auth-oauthlib
    # In GCP Console → APIs & Services → Credentials → "PracticeRank GA4 CLI" → Download JSON
    python scripts/mint_gbp_token.py ~/Downloads/client_secret_XXX.json
"""

from __future__ import annotations

import json
import sys

SCOPES = ["https://www.googleapis.com/auth/business.manage"]


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python scripts/mint_gbp_token.py <path-to-client_secret.json>")
        return 1
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("Missing dep — run:  pip install google-auth-oauthlib")
        return 1

    secrets_path = sys.argv[1]
    flow = InstalledAppFlow.from_client_secrets_file(secrets_path, scopes=SCOPES)
    # access_type=offline + prompt=consent guarantees a refresh_token is returned.
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")

    info = json.load(open(secrets_path))
    block = info.get("installed") or info.get("web") or {}
    print("\n" + "=" * 64)
    print("GBP OAuth values — set these on the droplet .env, then redeploy:")
    print("=" * 64)
    print(f"GBP_OAUTH_CLIENT_ID={block.get('client_id', '')}")
    print(f"GBP_OAUTH_CLIENT_SECRET={block.get('client_secret', '')}")
    print(f"GBP_OAUTH_REFRESH_TOKEN={creds.refresh_token or ''}")
    print("=" * 64)
    if not creds.refresh_token:
        print("\n! No refresh token returned. Revoke prior consent at "
              "myaccount.google.com/permissions and re-run.")
        return 2
    print("\nNext: paste these into /home/kody/dental-marketing/.env on the droplet,")
    print("run `docker compose up -d dashboard`, then verify with:")
    print("  docker exec practicerank-dashboard python -m geo_agent.gbp_client")
    return 0


if __name__ == "__main__":
    sys.exit(main())
