"""Google Search Console API client for tracking organic search performance.

Fetches search analytics (clicks, impressions, CTR, position) from the
Google Search Console API using service account authentication.

Required setup:
    1. Create a service account in Google Cloud Console with Search Console API enabled.
    2. Download the JSON key file.
    3. In Google Search Console, add the service account email
       (e.g. practicerank@project.iam.gserviceaccount.com) as a **Full** user
       under Settings > Users and permissions for each property.
    4. Set one of:
       - GSC_SERVICE_ACCOUNT_JSON: path to the JSON key file
       - GSC_SERVICE_ACCOUNT_KEY: the JSON key content as a string (for Docker/secrets)
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    _GSC_AVAILABLE = True
except ImportError:
    _GSC_AVAILABLE = False
    logger.debug(
        "google-api-python-client / google-auth not installed — GSC features disabled"
    )


_SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]

# Domain-wide delegation: impersonate this user (who has GSC access)
_IMPERSONATE_USER = os.environ.get("GSC_IMPERSONATE_USER", "kdoherty@practicerank.ai")


def _build_service():
    """Build an authenticated Search Console service client.

    Uses domain-wide delegation to impersonate a real user who has GSC access,
    since GSC doesn't allow adding service accounts directly as users.

    Returns the service object or None if credentials are missing / invalid.
    """
    if not _GSC_AVAILABLE:
        logger.warning("google-api-python-client not installed — cannot use GSC client")
        return None

    key_path = os.environ.get("GSC_SERVICE_ACCOUNT_JSON", "")
    key_content = os.environ.get("GSC_SERVICE_ACCOUNT_KEY", "")

    try:
        if key_content:
            info = json.loads(key_content)
            credentials = service_account.Credentials.from_service_account_info(
                info, scopes=_SCOPES
            )
        elif key_path:
            credentials = service_account.Credentials.from_service_account_file(
                key_path, scopes=_SCOPES
            )
        else:
            logger.warning(
                "Neither GSC_SERVICE_ACCOUNT_JSON nor GSC_SERVICE_ACCOUNT_KEY is set "
                "— GSC tracking disabled"
            )
            return None

        # Impersonate the user who has GSC access via domain-wide delegation
        credentials = credentials.with_subject(_IMPERSONATE_USER)

        return build("searchconsole", "v1", credentials=credentials)
    except Exception as exc:
        logger.warning(f"Failed to build GSC service: {exc}")
        return None


def fetch_search_metrics(
    site_url: str,
    start_date: str,
    end_date: str,
    dimensions: list[str] | None = None,
) -> list[dict] | None:
    """Fetch search analytics metrics from GSC.

    Args:
        site_url: The site property URL (e.g. ``sc-domain:example.com``
                  or ``https://www.example.com/``).
        start_date: Start date in YYYY-MM-DD format.
        end_date: End date in YYYY-MM-DD format.
        dimensions: Dimensions to group by (default: ``["date"]``).

    Returns:
        List of dicts with dimension keys plus ``clicks``, ``impressions``,
        ``ctr``, and ``position``, or None on failure.
    """
    service = _build_service()
    if service is None:
        return None

    if dimensions is None:
        dimensions = ["date"]

    try:
        response = (
            service.searchanalytics()
            .query(
                siteUrl=site_url,
                body={
                    "startDate": start_date,
                    "endDate": end_date,
                    "dimensions": dimensions,
                    "rowLimit": 25000,
                },
            )
            .execute()
        )
    except Exception as exc:
        logger.warning(f"GSC search analytics request failed for {site_url}: {exc}")
        return None

    rows = response.get("rows", [])
    results: list[dict] = []
    for row in rows:
        entry: dict = {}
        for i, dim in enumerate(dimensions):
            entry[dim] = row["keys"][i]
        entry["clicks"] = row.get("clicks", 0)
        entry["impressions"] = row.get("impressions", 0)
        entry["ctr"] = row.get("ctr", 0.0)
        entry["position"] = row.get("position", 0.0)
        results.append(entry)

    return results


def fetch_top_queries(
    site_url: str,
    start_date: str,
    end_date: str,
    limit: int = 50,
) -> list[dict] | None:
    """Fetch top search queries by clicks.

    Returns:
        List of dicts with ``query``, ``clicks``, ``impressions``,
        ``ctr``, ``position`` sorted by clicks descending, or None on failure.
    """
    service = _build_service()
    if service is None:
        return None

    try:
        response = (
            service.searchanalytics()
            .query(
                siteUrl=site_url,
                body={
                    "startDate": start_date,
                    "endDate": end_date,
                    "dimensions": ["query"],
                    "rowLimit": limit,
                    "orderBy": [{"field": "clicks", "order": "descending"}],
                },
            )
            .execute()
        )
    except Exception as exc:
        logger.warning(f"GSC top queries request failed for {site_url}: {exc}")
        return None

    rows = response.get("rows", [])
    return [
        {
            "query": row["keys"][0],
            "clicks": row.get("clicks", 0),
            "impressions": row.get("impressions", 0),
            "ctr": row.get("ctr", 0.0),
            "position": row.get("position", 0.0),
        }
        for row in rows
    ]


def fetch_top_pages(
    site_url: str,
    start_date: str,
    end_date: str,
    limit: int = 20,
) -> list[dict] | None:
    """Fetch top pages by clicks.

    Returns:
        List of dicts with ``page``, ``clicks``, ``impressions``,
        ``ctr``, ``position`` sorted by clicks descending, or None on failure.
    """
    service = _build_service()
    if service is None:
        return None

    try:
        response = (
            service.searchanalytics()
            .query(
                siteUrl=site_url,
                body={
                    "startDate": start_date,
                    "endDate": end_date,
                    "dimensions": ["page"],
                    "rowLimit": limit,
                    "orderBy": [{"field": "clicks", "order": "descending"}],
                },
            )
            .execute()
        )
    except Exception as exc:
        logger.warning(f"GSC top pages request failed for {site_url}: {exc}")
        return None

    rows = response.get("rows", [])
    return [
        {
            "page": row["keys"][0],
            "clicks": row.get("clicks", 0),
            "impressions": row.get("impressions", 0),
            "ctr": row.get("ctr", 0.0),
            "position": row.get("position", 0.0),
        }
        for row in rows
    ]


def _resolve_site_url(service, domain: str) -> str | None:
    """Try both GSC property formats and return whichever is verified.

    GSC properties can be registered as either ``sc-domain:example.com``
    (domain property) or ``https://www.example.com/`` (URL prefix property).
    """
    candidates = [
        f"sc-domain:{domain}",
        f"https://www.{domain}/",
        f"https://{domain}/",
    ]

    try:
        site_list = service.sites().list().execute()
        verified = {s["siteUrl"] for s in site_list.get("siteEntry", [])}
    except Exception as exc:
        logger.warning(f"Failed to list GSC sites: {exc}")
        verified = set()

    for candidate in candidates:
        if candidate in verified:
            logger.info(f"GSC property matched: {candidate}")
            return candidate

    # Fall back to the domain property even if not in verified list — the API
    # will return an auth error which we handle gracefully downstream.
    logger.info(
        f"No verified GSC property found for {domain}, "
        f"trying sc-domain:{domain} as fallback"
    )
    return f"sc-domain:{domain}"


def _ensure_gsc_daily_table(conn) -> None:
    """Create the gsc_daily_metrics table if it does not exist."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS gsc_daily_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id TEXT NOT NULL,
            date TEXT NOT NULL,
            clicks INTEGER NOT NULL DEFAULT 0,
            impressions INTEGER NOT NULL DEFAULT 0,
            ctr REAL NOT NULL DEFAULT 0.0,
            position REAL NOT NULL DEFAULT 0.0,
            UNIQUE(customer_id, date)
        )
        """
    )
    conn.commit()


def track_gsc_metrics(db, customer_id: str) -> dict | None:
    """Fetch last 7 days of GSC data, record KPIs, and save daily breakdown.

    Args:
        db: A ``geo_agent.db.CustomerDB`` instance.
        customer_id: The customer ID to track.

    Returns:
        Summary dict with ``total_clicks``, ``total_impressions``,
        ``avg_position``, ``avg_ctr``, and ``daily`` breakdown,
        or None on failure.
    """
    customer = db.get_customer(customer_id)
    if not customer:
        logger.warning(f"Customer not found: {customer_id}")
        return None

    service = _build_service()
    if service is None:
        return None

    domain = customer["domain"]
    site_url = _resolve_site_url(service, domain)
    if site_url is None:
        return None

    today = datetime.now(timezone.utc)
    # GSC data is typically delayed 2-3 days; fetch a window ending yesterday
    end_date = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    start_date = (today - timedelta(days=7)).strftime("%Y-%m-%d")

    daily_data = fetch_search_metrics(site_url, start_date, end_date, dimensions=["date"])
    if daily_data is None:
        logger.warning(f"Failed to fetch GSC metrics for {customer_id} ({site_url})")
        return None

    if not daily_data:
        logger.info(f"No GSC data returned for {customer_id} ({site_url})")
        return {
            "total_clicks": 0,
            "total_impressions": 0,
            "avg_position": 0.0,
            "avg_ctr": 0.0,
            "daily": [],
        }

    # Aggregate totals
    total_clicks = sum(row["clicks"] for row in daily_data)
    total_impressions = sum(row["impressions"] for row in daily_data)
    avg_position = sum(row["position"] for row in daily_data) / len(daily_data)
    avg_ctr = (total_clicks / total_impressions) if total_impressions > 0 else 0.0

    # Record KPIs
    kpi_date = today.strftime("%Y-%m-%d")
    db.record_kpi(customer_id, "organic_clicks", total_clicks, kpi_date)
    db.record_kpi(customer_id, "organic_impressions", total_impressions, kpi_date)
    db.record_kpi(customer_id, "avg_search_position", round(avg_position, 2), kpi_date)
    db.record_kpi(customer_id, "search_ctr", round(avg_ctr, 4), kpi_date)

    # Save daily breakdown
    _ensure_gsc_daily_table(db.conn)
    for row in daily_data:
        db.conn.execute(
            """
            INSERT OR REPLACE INTO gsc_daily_metrics
                (customer_id, date, clicks, impressions, ctr, position)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                customer_id,
                row["date"],
                row["clicks"],
                row["impressions"],
                round(row["ctr"], 4),
                round(row["position"], 2),
            ),
        )
    db.conn.commit()

    logger.info(
        f"GSC tracked for {customer_id}: "
        f"{total_clicks} clicks, {total_impressions} impressions, "
        f"avg position {avg_position:.1f}, CTR {avg_ctr:.2%}"
    )

    return {
        "total_clicks": total_clicks,
        "total_impressions": total_impressions,
        "avg_position": round(avg_position, 2),
        "avg_ctr": round(avg_ctr, 4),
        "daily": daily_data,
    }


def track_gsc_queries(db, customer_id: str, days: int = 14) -> int | None:
    """R1: Ingest query-dimension GSC data into ``gsc_query_daily``.

    Pulls the last ``days`` of (date, query) rows so the weekly report can show
    top keywords and week-over-week position movers. Upserts per day.

    Returns the number of (date, query) rows written, or None on failure.
    """
    customer = db.get_customer(customer_id)
    if not customer:
        logger.warning(f"Customer not found: {customer_id}")
        return None

    service = _build_service()
    if service is None:
        return None

    site_url = _resolve_site_url(service, customer["domain"])
    if site_url is None:
        return None

    today = datetime.now(timezone.utc)
    end_date = (today - timedelta(days=1)).strftime("%Y-%m-%d")  # GSC lags ~2-3d
    start_date = (today - timedelta(days=days)).strftime("%Y-%m-%d")

    rows = fetch_search_metrics(site_url, start_date, end_date, dimensions=["date", "query"])
    if rows is None:
        logger.warning(f"Failed to fetch GSC query data for {customer_id} ({site_url})")
        return None
    if not rows:
        logger.info(f"No GSC query data for {customer_id} ({site_url})")
        return 0

    # Group rows by date, then upsert each day's queries.
    by_date: dict[str, list[dict]] = {}
    for r in rows:
        by_date.setdefault(r["date"], []).append(r)

    written = 0
    for date, day_rows in by_date.items():
        written += db.save_gsc_query_daily(customer_id, date, day_rows)

    logger.info(f"GSC queries tracked for {customer_id}: {written} rows across {len(by_date)} days")
    return written
