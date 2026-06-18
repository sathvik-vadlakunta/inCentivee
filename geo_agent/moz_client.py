"""Moz Links API v2 — Domain Authority tracking (dormant until keyed).

One account-wide credential covers every customer. Set in the droplet .env:
    MOZ_ACCESS_ID=...
    MOZ_SECRET_KEY=...
(from Moz Pro → Account → API → Generate Access ID / Secret Key.)

get_domain_authority() returns DA/PA/spam for a domain; track_domain_authority()
snapshots DA into the kpis table so the dashboard + weekly report can show the
trend over time — the proof that link building is working.

No key set → every call is a clean no-op (returns None).
"""

from __future__ import annotations

import base64
import logging
import os

import httpx

logger = logging.getLogger(__name__)

MOZ_API = "https://lsapi.seomoz.com/v2/url_metrics"


def _auth_header() -> str | None:
    # Preferred: a single pre-encoded token (base64 of "AccessID:SecretKey").
    token = os.environ.get("MOZ_API_TOKEN", "").strip()
    if token:
        return f"Basic {token}"
    # Or the raw pair.
    access_id = os.environ.get("MOZ_ACCESS_ID", "")
    secret_key = os.environ.get("MOZ_SECRET_KEY", "")
    if not access_id or not secret_key:
        return None
    return f"Basic {base64.b64encode(f'{access_id}:{secret_key}'.encode()).decode()}"


def get_domain_authority(domain: str) -> dict | None:
    """Return {da, pa, spam} for a domain, or None if unconfigured / on failure."""
    auth = _auth_header()
    if not auth or not domain:
        return None
    target = domain.replace("https://", "").replace("http://", "").strip("/").lower()
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(
                MOZ_API,
                headers={"Authorization": auth, "Content-Type": "application/json"},
                json={"targets": [target]},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Moz DA lookup failed for %s: %s", domain, exc)
        return None
    results = data.get("results") or []
    if not results:
        return None
    m = results[0]
    return {
        "da": m.get("domain_authority"),
        "pa": m.get("page_authority"),
        "spam": m.get("spam_score"),
    }


def track_competitor_da(db, customer_id: str, limit: int = 5) -> list[dict]:
    """Pull DA for the customer's top REAL competitors (those with an actual
    domain), ranked by review count. Stores on competitor_domains; returns
    [{domain, name, da}]. No-op (empty) until Moz is configured.
    """
    if not _auth_header():
        return []
    comps = db.get_competitor_domains(customer_id) or []
    real = [c for c in comps
            if (c.get("competitor_domain") or "").strip() and "." in c["competitor_domain"]]
    real.sort(key=lambda c: c.get("review_count") or 0, reverse=True)
    out = []
    for c in real[:limit]:
        dom = c["competitor_domain"].strip()
        res = get_domain_authority(dom)
        if res and res.get("da") is not None:
            da = float(res["da"])
            db.update_competitor_da(customer_id, dom, da)
            out.append({"domain": dom, "name": c.get("competitor_name") or dom, "da": da})
    return out


def track_domain_authority(db, customer_id: str) -> float | None:
    """Snapshot the customer's Domain Authority into the kpis table.

    Returns the DA value, or None when Moz isn't configured / no data — so the
    monthly run no-ops cleanly until the credentials are set.
    """
    customer = db.get_customer(customer_id)
    if not customer:
        return None
    res = get_domain_authority(customer.get("domain", ""))
    if not res or res.get("da") is None:
        return None
    da = float(res["da"])
    db.record_kpi(customer_id, "domain_authority", da)
    logger.info("Domain Authority for %s: %s", customer_id, da)
    return da
