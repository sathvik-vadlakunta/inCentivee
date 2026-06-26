"""Google Business Profile (GBP) API client — monthly GBP management.

**M1 scope: read-only** (accounts, locations, reviews, performance). Write paths
(`create_post`, `upload_photo`, `reply_review`, `update_info`) land in M2–M4 and are stubbed
here with `NotImplementedError` so the surface is visible but nothing can post yet.

Auth — IMPORTANT: GBP does **not** support service accounts for these operations (unlike GSC/GA4).
Every call is made as the **agency ops Google account** (e.g. ``gbp-ops@practicerank.ai``) that the
customer has added as a **Manager** on their Business Profile. We hold ONE agency-level OAuth
refresh token (scope ``https://www.googleapis.com/auth/business.manage``); through it we can see
every location we've been granted Manager on.

Agency-level secrets (env / SecretsManager — NOT per-customer):
    GBP_OAUTH_CLIENT_ID
    GBP_OAUTH_CLIENT_SECRET
    GBP_OAUTH_REFRESH_TOKEN

Resource-name gotchas (these differ across the split GBP APIs — handled below):
    - Account Management / Business Information (v1): ``accounts/{a}``, ``locations/{l}``
    - Reviews + posts + media (v4 legacy):           ``accounts/{a}/locations/{l}``
    - Performance (v1):                               ``locations/{l}``

Everything degrades gracefully: if creds are missing or a call fails, methods log and return
``None`` / ``[]`` so a transient GBP problem never crashes a customer's monthly run.

See ``specs/active/gbp-monthly-management.md`` for the full feature plan.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import httpx

from geo_agent.secrets import get_secrets

logger = logging.getLogger(__name__)

OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
BUSINESS_SCOPE = "https://www.googleapis.com/auth/business.manage"

ACCOUNT_MGMT_BASE = "https://mybusinessaccountmanagement.googleapis.com/v1"
BUSINESS_INFO_BASE = "https://mybusinessbusinessinformation.googleapis.com/v1"
V4_BASE = "https://mybusiness.googleapis.com/v4"
PERFORMANCE_BASE = "https://businessprofileperformance.googleapis.com/v1"

# readMask for locations.list — only what we need (the API requires an explicit mask).
LOCATION_READ_MASK = "name,title,storefrontAddress,phoneNumbers,websiteUri,metadata,categories"

# Daily metrics we report on (Business Profile Performance API).
DEFAULT_PERF_METRICS = [
    "BUSINESS_IMPRESSIONS_DESKTOP_MAPS",
    "BUSINESS_IMPRESSIONS_DESKTOP_SEARCH",
    "BUSINESS_IMPRESSIONS_MOBILE_MAPS",
    "BUSINESS_IMPRESSIONS_MOBILE_SEARCH",
    "CALL_CLICKS",
    "WEBSITE_CLICKS",
    "BUSINESS_DIRECTION_REQUESTS",
]


@dataclass
class GBPLocation:
    """A Business Profile location, normalized across the v1/v4 resource-name split."""
    name: str           # v1 resource, e.g. "locations/123"
    account: str        # parent account, e.g. "accounts/456"
    title: str = ""
    phone: str = ""
    website: str = ""
    address: str = ""
    place_id: str = ""

    @property
    def v4_name(self) -> str:
        """The legacy v4 resource path used by reviews/posts/media."""
        loc_id = self.name.split("/")[-1]
        return f"{self.account}/locations/{loc_id}"

    @property
    def perf_name(self) -> str:
        """The v1 ``locations/{id}`` path used by the Performance API."""
        return self.name if self.name.startswith("locations/") else f"locations/{self.name.split('/')[-1]}"


class GBPClient:
    """Thin, fail-safe Google Business Profile client (read-only in M1)."""

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        refresh_token: str | None = None,
        timeout: float = 30.0,
    ):
        s = get_secrets()
        self.client_id = client_id or s.get("GBP_OAUTH_CLIENT_ID")
        self.client_secret = client_secret or s.get("GBP_OAUTH_CLIENT_SECRET")
        self.refresh_token = refresh_token or s.get("GBP_OAUTH_REFRESH_TOKEN")
        self._timeout = timeout
        self._token: str | None = None
        self._token_exp: float = 0.0

    # ── auth ──────────────────────────────────────────────────────────────────
    def available(self) -> bool:
        """True when all three OAuth secrets are present (no live call made)."""
        return bool(self.client_id and self.client_secret and self.refresh_token)

    def _access_token(self) -> str | None:
        """Return a cached access token, refreshing via the OAuth token endpoint as needed."""
        if not self.available():
            logger.warning("GBP: OAuth secrets missing — GBP features disabled")
            return None
        if self._token and time.time() < self._token_exp - 60:
            return self._token
        try:
            r = httpx.post(
                OAUTH_TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": self.refresh_token,
                    "grant_type": "refresh_token",
                },
                timeout=self._timeout,
            )
            r.raise_for_status()
            payload = r.json()
            self._token = payload["access_token"]
            self._token_exp = time.time() + int(payload.get("expires_in", 3600))
            return self._token
        except Exception as e:  # noqa: BLE001
            logger.warning(f"GBP: token refresh failed: {e}")
            return None

    def _get(self, url: str, params: dict | None = None) -> dict | None:
        """Authenticated GET → parsed JSON, or None on any error (fail-safe)."""
        tok = self._access_token()
        if not tok:
            return None
        try:
            r = httpx.get(
                url,
                params=params or {},
                headers={"Authorization": f"Bearer {tok}"},
                timeout=self._timeout,
            )
            r.raise_for_status()
            return r.json()
        except Exception as e:  # noqa: BLE001
            logger.warning(f"GBP GET {url} failed: {e}")
            return None

    # ── read paths (M1) ───────────────────────────────────────────────────────
    def list_accounts(self) -> list[dict]:
        """List GBP accounts the ops user can access."""
        data = self._get(f"{ACCOUNT_MGMT_BASE}/accounts") or {}
        return data.get("accounts", []) or []

    def list_locations(self, account: str | None = None) -> list[GBPLocation]:
        """List all locations across accounts (or one account), normalized to GBPLocation."""
        accounts = [account] if account else [a.get("name") for a in self.list_accounts()]
        out: list[GBPLocation] = []
        for acct in filter(None, accounts):
            page_token = None
            while True:
                params = {"readMask": LOCATION_READ_MASK, "pageSize": 100}
                if page_token:
                    params["pageToken"] = page_token
                data = self._get(f"{BUSINESS_INFO_BASE}/{acct}/locations", params)
                if not data:
                    break
                for loc in data.get("locations", []) or []:
                    out.append(_parse_location(loc, acct))
                page_token = data.get("nextPageToken")
                if not page_token:
                    break
        return out

    def find_location(self, query: str, account: str | None = None) -> GBPLocation | None:
        """Best-effort match of a customer name to a location (case-insensitive substring)."""
        q = (query or "").strip().lower()
        if not q:
            return None
        best = None
        for loc in self.list_locations(account):
            t = loc.title.lower()
            if t == q:
                return loc
            if q in t or t in q:
                best = best or loc
        return best

    def list_reviews(self, location: GBPLocation, page_size: int = 50) -> list[dict]:
        """List reviews for a location (v4). Newest first per the API default."""
        data = self._get(f"{V4_BASE}/{location.v4_name}/reviews", {"pageSize": page_size})
        return (data or {}).get("reviews", []) or []

    def get_performance(
        self,
        location: GBPLocation,
        start: str,
        end: str,
        metrics: list[str] | None = None,
    ) -> dict | None:
        """Fetch daily metrics for a location over [start, end] (YYYY-MM-DD).

        Uses the multi-metric endpoint (the single-metric v4 method is deprecated).
        Returns the raw ``multiDailyMetricTimeSeries`` payload (caller aggregates).
        """
        sy, sm, sd = (int(x) for x in start.split("-"))
        ey, em, ed = (int(x) for x in end.split("-"))
        params = [("dailyMetrics", m) for m in (metrics or DEFAULT_PERF_METRICS)]
        params += [
            ("dailyRange.start_date.year", sy), ("dailyRange.start_date.month", sm),
            ("dailyRange.start_date.day", sd), ("dailyRange.end_date.year", ey),
            ("dailyRange.end_date.month", em), ("dailyRange.end_date.day", ed),
        ]
        url = f"{PERFORMANCE_BASE}/{location.perf_name}:fetchMultiDailyMetricsTimeSeries"
        return self._get(url, params)

    # ── write paths (M2–M4 — stubbed so the surface is visible, nothing posts yet) ──
    def create_post(self, location: GBPLocation, post: dict) -> dict:
        raise NotImplementedError("GBP posts land in M2 — gated behind Dan approval + validate_html_claims")

    def upload_photo(self, location: GBPLocation, media: dict) -> dict:
        raise NotImplementedError("GBP media upload lands in M2")

    def reply_review(self, review_name: str, text: str) -> dict:
        raise NotImplementedError("Review replies land in M4 — Dan-approved drafts only")

    def update_info(self, location: GBPLocation, patch: dict) -> dict:
        raise NotImplementedError("Info edits land in M4")


def _parse_location(loc: dict, account: str) -> GBPLocation:
    """Normalize a Business Information API location object to GBPLocation."""
    phones = loc.get("phoneNumbers", {}) or {}
    addr = loc.get("storefrontAddress", {}) or {}
    address = ", ".join(
        [*(addr.get("addressLines") or []),
         " ".join(filter(None, [addr.get("locality"), addr.get("administrativeArea"), addr.get("postalCode")]))]
    ).strip(", ")
    return GBPLocation(
        name=loc.get("name", ""),
        account=account,
        title=loc.get("title", ""),
        phone=phones.get("primaryPhone", ""),
        website=loc.get("websiteUri", ""),
        address=address,
        place_id=(loc.get("metadata", {}) or {}).get("placeId", ""),
    )


def get_client() -> GBPClient:
    """Module-level convenience constructor (reads agency secrets from the environment)."""
    return GBPClient()


def _cli_check() -> int:
    """`python -m geo_agent.gbp_client` — verify creds + list locations (for once access exists)."""
    logging.basicConfig(level=logging.INFO)
    c = get_client()
    if not c.available():
        print("GBP creds NOT configured. Set GBP_OAUTH_CLIENT_ID / _SECRET / _REFRESH_TOKEN.")
        return 1
    if not c._access_token():
        print("GBP creds present but token refresh FAILED — check the refresh token / scope.")
        return 2
    accounts = c.list_accounts()
    print(f"OK — {len(accounts)} account(s) accessible.")
    locs = c.list_locations()
    print(f"{len(locs)} location(s) we're a Manager on:")
    for loc in locs:
        print(f"  - {loc.title or '(no title)'}  [{loc.name}]  {loc.address}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_cli_check())
