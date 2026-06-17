"""GA4 Data API client — conversion (lead) tracking (R3).

Pulls phone-click / form-submit / appointment-request events per day and channel
into ``conversions_daily`` so the weekly report can show "Leads this week" — the
metric closest to revenue.

Design / best practices
-----------------------
- **Read-only scope.** Credentials are requested with
  ``analytics.readonly`` only.
- **Service account.** ``GA4_SERVICE_ACCOUNT_JSON`` (inline JSON) or
  ``GOOGLE_APPLICATION_CREDENTIALS`` (path). The SA email must be granted Viewer
  on each GA4 property. One SA can serve many properties.
- **Per-customer config** lives in a ``ga4`` integration:
  ``{"property_id": "123456789", "conversion_events": [...optional override...]}``.
- **Transient-error resilience.** RunReport is retried with exponential backoff
  on the standard retryable gRPC statuses (unavailable, deadline, internal,
  resource-exhausted/quota).
- **Pagination.** Responses are paged via offset/limit so we never silently
  truncate a busy property.
- **Data freshness.** GA4 intraday data is incomplete, so the window ends
  *yesterday*.
- **Idempotent.** Writes go through ``record_conversion`` (upsert), so re-runs
  for the same day overwrite rather than double-count.
- **Degrades gracefully.** If the library, credentials, or property aren't
  configured, functions log and return None — the report omits the Leads section.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

ANALYTICS_READONLY_SCOPE = "https://www.googleapis.com/auth/analytics.readonly"

# GA4 event names we treat as leads → normalized report event_name.
# Customers can override the *recognized* set via integration config
# ("conversion_events"); the normalization map below still applies.
DEFAULT_CONVERSION_EVENTS = {
    "phone_click": "phone_click",
    "click_to_call": "phone_click",
    "tel_click": "phone_click",
    "call_button_click": "phone_click",
    "form_submit": "form_submit",
    "generate_lead": "form_submit",
    "contact_form": "form_submit",
    "contact_form_submit": "form_submit",
    "appointment_request": "appointment_request",
    "book_appointment": "appointment_request",
    "schedule_appointment": "appointment_request",
}

# GA4 default channel group → our channel bucket.
CHANNEL_MAP = {
    "Organic Search": "organic",
    "Direct": "direct",
    "Referral": "referral",
    "Paid Search": "paid",
    "Display": "paid",
    "Paid Social": "paid",
    "Organic Social": "referral",
    "Email": "referral",
}

_PAGE_SIZE = 100_000          # GA4 hard max rows per RunReport request
_MAX_RETRIES = 4


# ---------------------------------------------------------------------------
# Credentials / client
# ---------------------------------------------------------------------------

def _load_credentials():
    """Load read-only GA4 credentials, or None.

    Two supported auth modes, preferred in this order:

    1. **OAuth user account** (recommended) — authenticate AS a human Google
       account (e.g. kdoherty@practicerank.ai) that customers already add to
       their GA4 property during onboarding. Set ``GA4_OAUTH_REFRESH_TOKEN`` +
       ``GA4_OAUTH_CLIENT_ID`` + ``GA4_OAUTH_CLIENT_SECRET`` (obtain the refresh
       token once via ``scripts/ga4_authorize.py``). No per-property service
       account grant needed — the account inherits access to every property it's
       a member of.
    2. **Service account** — ``GA4_SERVICE_ACCOUNT_JSON`` (inline JSON) or
       ``GOOGLE_APPLICATION_CREDENTIALS`` (path). Requires the SA email to be
       added as a Viewer on each property (needs Administrator on the property).
    """
    # 1. OAuth user credentials (a human account already on the properties).
    refresh_token = os.environ.get("GA4_OAUTH_REFRESH_TOKEN")
    client_id = os.environ.get("GA4_OAUTH_CLIENT_ID")
    client_secret = os.environ.get("GA4_OAUTH_CLIENT_SECRET")
    if refresh_token and client_id and client_secret:
        try:
            from google.oauth2.credentials import Credentials
            return Credentials(
                token=None,
                refresh_token=refresh_token,
                client_id=client_id,
                client_secret=client_secret,
                token_uri="https://oauth2.googleapis.com/token",
                scopes=[ANALYTICS_READONLY_SCOPE],
            )
        except ImportError:
            logger.info("google-auth not installed — cannot use GA4 OAuth credentials")

    # 2. Service-account fallback.
    try:
        from google.oauth2 import service_account
    except ImportError:
        return None
    raw = os.environ.get("GA4_SERVICE_ACCOUNT_JSON")
    try:
        if raw:
            return service_account.Credentials.from_service_account_info(
                json.loads(raw), scopes=[ANALYTICS_READONLY_SCOPE]
            )
        path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if path:
            return service_account.Credentials.from_service_account_file(
                path, scopes=[ANALYTICS_READONLY_SCOPE]
            )
    except Exception as exc:
        logger.warning(f"GA4 credentials invalid: {exc}")
    return None


def _client():
    """Build a BetaAnalyticsDataClient, or None if unavailable/unconfigured."""
    try:
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
    except ImportError:
        logger.info("google-analytics-data not installed — skipping GA4 tracking")
        return None
    creds = _load_credentials()
    if creds is None:
        logger.info("No GA4 service-account credentials — skipping GA4 tracking")
        return None
    try:
        return BetaAnalyticsDataClient(credentials=creds)
    except Exception as exc:
        logger.warning(f"Failed to build GA4 client: {exc}")
        return None


def _normalize_property_id(value: str | int | None) -> str | None:
    """Accept '123', 'properties/123', or int → return digits-only id, or None."""
    if value is None:
        return None
    digits = re.sub(r"\D", "", str(value))
    return digits or None


def _retry():
    """A google-api-core Retry for transient RunReport failures, or None."""
    try:
        from google.api_core import exceptions, retry
        return retry.Retry(
            predicate=retry.if_exception_type(
                exceptions.ServiceUnavailable,
                exceptions.DeadlineExceeded,
                exceptions.InternalServerError,
                exceptions.ResourceExhausted,
                exceptions.TooManyRequests,
            ),
            initial=1.0, maximum=30.0, multiplier=2.0, timeout=120.0,
        )
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Core report
# ---------------------------------------------------------------------------

def _build_request(property_id: str, events: list[str], start: str, end: str, offset: int):
    from google.analytics.data_v1beta.types import (
        DateRange, Dimension, Filter, FilterExpression, Metric, RunReportRequest,
    )
    return RunReportRequest(
        property=f"properties/{property_id}",
        date_ranges=[DateRange(start_date=start, end_date=end)],
        dimensions=[Dimension(name="date"), Dimension(name="eventName"),
                    Dimension(name="sessionDefaultChannelGroup")],
        metrics=[Metric(name="eventCount")],
        dimension_filter=FilterExpression(filter=Filter(
            field_name="eventName",
            in_list_filter=Filter.InListFilter(values=events),
        )),
        limit=_PAGE_SIZE,
        offset=offset,
        return_property_quota=True,
    )


def _run_report_paged(client, property_id, events, start, end):
    """Run RunReport with retry + pagination. Returns list of rows or None on error."""
    retry = _retry()
    all_rows = []
    offset = 0
    while True:
        request = _build_request(property_id, events, start, end, offset)
        try:
            response = client.run_report(request, retry=retry) if retry \
                else client.run_report(request)
        except Exception as exc:
            logger.warning(f"GA4 RunReport failed (offset={offset}): {exc}")
            return None
        all_rows.extend(response.rows)
        total = getattr(response, "row_count", len(all_rows))
        offset += _PAGE_SIZE
        if offset >= total or not response.rows:
            break
    return all_rows


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _resolve_config(db, customer_id: str) -> tuple[str | None, dict]:
    integ = db.get_integration(customer_id, "ga4")
    config = (integ or {}).get("config", {}) if integ else {}
    return _normalize_property_id(config.get("property_id")), config


def track_conversions(db, customer_id: str, days: int = 14) -> int | None:
    """R3: Pull conversion events into ``conversions_daily``.

    Returns the number of rows written, 0 if the property has no matching
    events, or None if GA4 isn't configured/available for this customer.
    """
    property_id, config = _resolve_config(db, customer_id)
    if not property_id:
        logger.info(f"No GA4 property configured for {customer_id} — skipping")
        return None

    client = _client()
    if client is None:
        return None

    event_map = dict(DEFAULT_CONVERSION_EVENTS)
    for ev in config.get("conversion_events", []) or []:
        event_map.setdefault(ev, ev)  # unknown custom events normalize to themselves
    events = list(event_map.keys())

    today = datetime.now(timezone.utc)
    start = (today - timedelta(days=days)).strftime("%Y-%m-%d")
    end = (today - timedelta(days=1)).strftime("%Y-%m-%d")  # exclude incomplete today

    rows = _run_report_paged(client, property_id, events, start, end)
    if rows is None:
        db.update_integration_status(customer_id, "ga4", "error", "RunReport failed")
        return None

    written = 0
    for row in rows:
        raw_date = row.dimension_values[0].value          # YYYYMMDD
        event = row.dimension_values[1].value
        channel = CHANNEL_MAP.get(row.dimension_values[2].value, "other")
        count = int(row.metric_values[0].value or 0)
        norm_event = event_map.get(event)
        if not norm_event or count == 0 or len(raw_date) != 8:
            continue
        date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"
        db.record_conversion(customer_id, date, norm_event, channel, count)
        written += 1

    db.update_integration_status(customer_id, "ga4", "active")
    logger.info(f"GA4 conversions tracked for {customer_id}: {written} rows")
    return written


def test_connection(db, customer_id: str) -> dict:
    """Validate GA4 config + credentials with a tiny live query. For the UI."""
    property_id, _ = _resolve_config(db, customer_id)
    if not property_id:
        return {"ok": False, "error": "No GA4 property_id configured for this customer."}

    try:
        from google.analytics.data_v1beta import BetaAnalyticsDataClient  # noqa: F401
    except ImportError:
        return {"ok": False, "error": "google-analytics-data not installed on server."}

    if _load_credentials() is None:
        return {"ok": False, "error": "GA4 credentials not configured on the server. "
                                      "Either set GA4_OAUTH_REFRESH_TOKEN/CLIENT_ID/CLIENT_SECRET "
                                      "(run scripts/ga4_authorize.py), or a service account "
                                      "(GA4_SERVICE_ACCOUNT_JSON / GOOGLE_APPLICATION_CREDENTIALS)."}

    client = _client()
    if client is None:
        return {"ok": False, "error": "Could not build GA4 client."}

    today = datetime.now(timezone.utc)
    start = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    end = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    rows = _run_report_paged(client, property_id, list(DEFAULT_CONVERSION_EVENTS.keys()), start, end)
    if rows is None:
        db.update_integration_status(customer_id, "ga4", "error",
                                     "Test query failed — check property access for the service account.")
        return {"ok": False, "error": "Test query failed. Confirm the service account "
                                      f"has Viewer access to property {property_id}."}
    total = sum(int(r.metric_values[0].value or 0) for r in rows)
    db.save_integration(customer_id, "ga4", {"property_id": property_id}, "active")
    return {"ok": True, "message": f"Connected to GA4 property {property_id}. "
                                   f"{total} lead event(s) in the last 7 days."}
