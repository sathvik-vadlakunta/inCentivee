"""Ingest FATJOE's unbranded CSV reports into the off-site assets ledger.

FATJOE delivers a CSV per completed order (a links report, a citation report, or
a brand-mention report). Column headers differ between report types and have
drifted over time, so we match columns by fuzzy keyword rather than exact name.

For link/mention assets we pull each unique domain's Domain Authority via Moz
(cached within the import so a domain is only looked up once). Citation reports
skip DA — there can be ~100 directories per order and DA isn't the signal there.

See specs/active/fatjoe-va-ops-and-tracking.html (Part 3).
"""

from __future__ import annotations

import csv
import io
import logging
import re

logger = logging.getLogger(__name__)

# Header keyword → asset field. First matching header (case-insensitive substring)
# wins. Ordered most-specific first so "live url" beats a bare "url".
_HEADER_KEYWORDS = [
    (["live url", "published url", "post url", "article url"], "live_url"),
    (["directory url", "listing url", "citation url"], "live_url"),
    (["url", "link"], "live_url"),
    (["anchor"], "anchor_text"),
    (["directory", "website", "site name"], "domain"),
    (["dr", "domain rating", "da", "authority"], "_da"),
    (["follow"], "_follow"),
]


def domain_of(url: str) -> str:
    """Bare hostname, lowercased, no scheme/www/path."""
    s = (url or "").strip().lower()
    s = re.sub(r"^https?://", "", s)
    s = s.split("/")[0].split("?")[0]
    return s[4:] if s.startswith("www.") else s


def _map_headers(headers: list[str]) -> dict[str, str]:
    """Map each CSV header to an asset field via keyword match. Returns
    {original_header: field}. A header maps to at most one field; a field is
    claimed by at most one header (first match)."""
    out: dict[str, str] = {}
    taken: set[str] = set()
    for kws, field in _HEADER_KEYWORDS:
        if field in taken:
            continue
        for h in headers:
            if h in out:
                continue
            hl = h.strip().lower()
            if any(kw in hl for kw in kws):
                out[h] = field
                taken.add(field)
                break
    return out


def parse_report(csv_text: str, order_type: str) -> list[dict]:
    """Parse a FATJOE CSV into asset dicts: {live_url, domain, anchor_text,
    is_dofollow, _da}. Rows without a usable live_url are skipped."""
    try:
        reader = csv.DictReader(io.StringIO(csv_text))
    except Exception as exc:  # noqa: BLE001
        logger.warning("FATJOE CSV parse failed: %s", exc)
        return []
    if not reader.fieldnames:
        return []
    hmap = _map_headers(list(reader.fieldnames))

    assets: list[dict] = []
    for row in reader:
        rec: dict = {}
        for header, field in hmap.items():
            val = (row.get(header) or "").strip()
            if not val:
                continue
            if field == "_da":
                m = re.search(r"\d+", val)
                if m:
                    rec["_da"] = int(m.group())
            elif field == "_follow":
                rec["is_dofollow"] = 0 if "no" in val.lower() else 1
            else:
                rec[field] = val
        live = rec.get("live_url", "")
        if not live or "." not in live:
            continue
        rec.setdefault("anchor_text", "")
        # A mapped "domain" column often holds a directory *name* ("Yelp"), not a
        # hostname — only trust it if it looks like one, else derive from the URL.
        dom = rec.get("domain", "")
        if not dom or " " in dom or "." not in dom:
            dom = domain_of(live)
        rec["domain"] = dom
        rec["asset_type"] = order_type
        assets.append(rec)
    return assets


def import_report(db, order_id: int, csv_bytes: bytes) -> dict:
    """Parse + persist a FATJOE report against an order. Pulls DA for unique
    link/mention domains via Moz (cached). Advances the order to 'delivered'.
    Returns {"added": n, "skipped_dupes": n, "da_pulled": n}."""
    order = db.get_offsite_order(order_id)
    if not order:
        raise ValueError(f"offsite order {order_id} not found")
    cid = order["customer_id"]
    order_type = order["order_type"]

    if isinstance(csv_bytes, bytes):
        csv_text = csv_bytes.decode("utf-8-sig", errors="replace")
    else:
        csv_text = str(csv_bytes)

    rows = parse_report(csv_text, order_type)

    existing = {a["live_url"] for a in db.get_offsite_assets(cid)}
    da_cache: dict[str, int | None] = {}
    pull_da = order_type in ("link", "mention")

    added = skipped = da_pulled = 0
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    for rec in rows:
        live = rec["live_url"]
        if live in existing:
            skipped += 1
            continue
        existing.add(live)

        da = rec.get("_da")
        da_at = now if da is not None else None
        if pull_da and da is None:
            dom = rec["domain"]
            if dom not in da_cache:
                da_cache[dom] = _safe_da(dom)
                if da_cache[dom] is not None:
                    da_pulled += 1
            da = da_cache[dom]
            da_at = now if da is not None else None

        db.add_offsite_asset(
            order_id, cid, live,
            asset_type=order_type,
            domain=rec["domain"],
            anchor_text=rec.get("anchor_text", ""),
            is_dofollow=rec.get("is_dofollow", 1),
            da=da, da_checked_at=da_at,
        )
        added += 1

    if order["status"] in ("ordered", "in_progress"):
        db.update_offsite_order(order_id, status="delivered")

    return {"added": added, "skipped_dupes": skipped, "da_pulled": da_pulled}


def _safe_da(domain: str) -> int | None:
    """Best-effort DA via Moz; None if unconfigured / failed."""
    try:
        from geo_agent.moz_client import get_domain_authority
        m = get_domain_authority(domain)
        if m and m.get("da") is not None:
            return round(m["da"])
    except Exception as exc:  # noqa: BLE001
        logger.info("DA pull failed for %s: %s", domain, exc)
    return None
