"""Automatically validate which Google accounts we actually have access to.

After a client connects accounts via Leadsie, we shouldn't have to manually
check whether the grant landed. This module verifies real access and updates
the customer's platform_access status:

- GSC: list the sites our impersonated user can see and match the domain.
- GA4: discover the property whose web stream matches the domain (needs the
  Analytics Admin API enabled) and store its property id for reporting.

GA4 already authenticates AS our Google account (OAuth), so whatever Leadsie
grants to that account is automatically usable — no per-property service
account step.
"""
from __future__ import annotations
import logging

logger = logging.getLogger(__name__)


def _norm_host(domain: str) -> str:
    d = (domain or "").lower().strip()
    for p in ("https://", "http://"):
        if d.startswith(p):
            d = d[len(p):]
    return d.strip("/").replace("www.", "")


def _ensure_columns(db) -> None:
    try:
        cols = [c[1] for c in db.conn.execute("PRAGMA table_info(customers)")]
        if "ga4_property_id" not in cols:
            db.conn.execute("ALTER TABLE customers ADD COLUMN ga4_property_id TEXT")
            db.conn.commit()
    except Exception as exc:
        logger.warning(f"ensure ga4_property_id column: {exc}")


def check_gsc_access(domain: str):
    """Return (granted: bool, site_url|None) — does our GSC user see this domain?"""
    try:
        from geo_agent import gsc_client
        svc = gsc_client._build_service()
        if not svc:
            return (False, None)
        site = gsc_client._resolve_site_url(svc, domain)
        return (bool(site), site)
    except Exception as exc:
        logger.warning(f"GSC access check failed for {domain}: {exc}")
        return (False, None)


def resolve_ga4_property_id(domain: str):
    """Find the GA4 property id ('properties/123456789') whose web stream URI
    matches `domain`. Requires the Analytics Admin API enabled and our OAuth
    account to be on the property. Returns None if not found / API disabled.
    """
    host = _norm_host(domain)
    if not host:
        return None
    try:
        from geo_agent import ga4_client
        creds = ga4_client._load_credentials()
        if creds is None:
            return None
        from googleapiclient.discovery import build
        admin = build("analyticsadmin", "v1beta", credentials=creds, cache_discovery=False)
        summaries = admin.accountSummaries().list().execute().get("accountSummaries", [])
        for acct in summaries:
            for ps in acct.get("propertySummaries", []):
                pid = ps.get("property")
                if not pid:
                    continue
                try:
                    streams = admin.properties().dataStreams().list(parent=pid).execute().get("dataStreams", [])
                except Exception:
                    continue
                for st in streams:
                    uri = ((st.get("webStreamData") or {}).get("defaultUri") or "").lower()
                    if uri and host in uri:
                        return pid
        return None
    except Exception as exc:
        msg = str(exc)
        if "analyticsadmin" in msg and "has not been used" in msg:
            logger.warning("GA4 auto-discovery needs the Analytics Admin API enabled in the Cloud project.")
        else:
            logger.warning(f"GA4 property resolution failed for {domain}: {exc}")
        return None


def _set_status(db, customer_id, existing, platform, status):
    if platform in existing:
        db.update_access_status(customer_id, platform, status)
    else:
        db.add_platform_access(customer_id, platform, status, "Auto-validated")


def validate_google_access(db, customer_id: str) -> dict:
    """Verify real Google access for a customer and update their access status.
    Stores the discovered GA4 property id. Returns a result dict for the UI."""
    _ensure_columns(db)
    cust = db.get_customer(customer_id) or {}
    domain = cust.get("domain", "")
    existing = {a["platform"] for a in db.get_platform_access(customer_id)}
    out = {"domain": domain, "checked": [], "ga4_property_id": None}

    # ── Search Console ──
    gsc_ok, site = check_gsc_access(domain)
    _set_status(db, customer_id, existing, "gsc", "granted" if gsc_ok else "pending")
    out["checked"].append({"platform": "Search Console", "key": "gsc", "granted": gsc_ok,
                           "detail": site or "no matching property in our account yet"})

    # ── Analytics (GA4) ──
    pid = resolve_ga4_property_id(domain)
    if pid:
        db.update_customer(customer_id, ga4_property_id=pid)
    _set_status(db, customer_id, existing, "ga", "granted" if pid else "pending")
    out["ga4_property_id"] = pid
    out["checked"].append({"platform": "Analytics (GA4)", "key": "ga", "granted": bool(pid),
                           "detail": pid or "property not found (is the Analytics Admin API enabled?)"})

    return out
