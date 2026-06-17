"""BrightLocal citation / NAP-consistency tracking (R4).

Populates the ``citations`` table (directory, listed, nap_match, url_correct) so
the weekly report can show a NAP-consistency score and the listings that need
fixing.

Status: requires a BrightLocal account with a Citation Tracker / Local Search
Audit *location* set up for the customer. Configuration per customer is a
``brightlocal`` integration whose config holds ``location_id`` (the BrightLocal
location/report id). The API key comes from the ``BRIGHTLOCAL_API_KEY`` env var.

Until an account + location is configured this is a clean no-op: ``track_citations``
returns None and the report omits the Local-listings section. The request/parse
layer below is structured to BrightLocal's v4 API; the exact citation-results
endpoint and field names should be confirmed against the live account before
relying on it (marked TODO inline).
"""

from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)

BRIGHTLOCAL_API_BASE = "https://tools.brightlocal.com/seo-tools/api/v4"


def _api_key() -> str:
    return os.environ.get("BRIGHTLOCAL_API_KEY", "")


def track_citations(db, customer_id: str) -> int | None:
    """R4: Pull citation/NAP status into ``citations``. Returns directories written.

    No-op (returns None) unless both a BrightLocal API key and a per-customer
    ``location_id`` are configured.
    """
    api_key = _api_key()
    integ = db.get_integration(customer_id, "brightlocal")
    location_id = (integ or {}).get("config", {}).get("location_id") if integ else None

    if not api_key or not location_id:
        logger.info(f"BrightLocal not configured for {customer_id} — skipping citations")
        return None

    # TODO(account): confirm the exact Citation Tracker results endpoint + field
    # names against the live BrightLocal account. Shape below follows v4 docs.
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.get(
                f"{BRIGHTLOCAL_API_BASE}/ct/results",
                params={"api-key": api_key, "location-id": location_id},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning(f"BrightLocal request failed for {customer_id}: {exc}")
        return None

    citations = data.get("citations") or data.get("results") or []
    written = 0
    for c in citations:
        directory = c.get("domain") or c.get("site") or c.get("directory")
        if not directory:
            continue
        # BrightLocal flags NAP fields individually; treat all-match as consistent.
        nap_match = bool(c.get("nap_accurate")) or (
            bool(c.get("name_accurate")) and bool(c.get("address_accurate"))
            and bool(c.get("phone_accurate"))
        )
        db.save_citation(
            customer_id,
            directory=directory,
            listed=bool(c.get("listed", True)),
            nap_match=nap_match,
            url_correct=bool(c.get("url_accurate", False)),
            listing_url=c.get("listing_url", "") or c.get("url", ""),
        )
        written += 1

    logger.info(f"BrightLocal citations tracked for {customer_id}: {written}")
    return written
