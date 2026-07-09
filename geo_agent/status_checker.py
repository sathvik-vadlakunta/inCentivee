"""Daily status reconciliation (see specs/active/daily-status-reconciliation.md).

For one customer, checks the *live site* against what we have on file and:
  1. resolves audit issues that are no longer present,
  2. marks content recommendations that are now live as published,
  3. ticks the SEO/GEO todos that are now satisfied,
  4. auto-advances status (→ active/monitoring) when fully live, or raises an
     alert + flips to 'attention' if a previously-live site regresses.

Forward-only and conservative: it promotes when clearly done, never auto-pauses
or churns, and every change is logged to the customer's activity timeline.

`reconcile_customer(db, customer_id, dry_run=True)` returns a structured diff so
the daily script can print exactly what it would change before any writes.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone

import httpx

from geo_agent.site_auditor import run_site_audit

logger = logging.getLogger(__name__)

# Customers we bother reconciling (active book of business).
RECONCILE_STATUSES = ("onboarding", "active")


# ---------------------------------------------------------------------------
# Live-site detection (self-contained; mirrors the dashboard's auto-detect).
# NOTE: the dashboard's _auto_detect_seo_status keeps its own cached copy; this
# is the headless equivalent for the cron. Consolidating the two into one source
# of truth is tracked as future cleanup in the spec.
# ---------------------------------------------------------------------------

def detect_live_status(domain: str) -> dict[str, bool]:
    """Probe the live site and return which verifiable SEO/GEO tasks are satisfied
    (keys match SEO_GEO_TASKS / va_checklist)."""
    detected: dict[str, bool] = {}
    if not domain:
        return detected

    try:
        resp = httpx.get(f"https://{domain}", timeout=10.0, follow_redirects=True)
        if resp.status_code == 200:
            body = resp.text
            has_schema = "application/ld+json" in body or "practicerank_schema" in body
            if has_schema:
                if "practicerank_schema" in body and "application/ld+json" not in body:
                    detected["seo_schema_org"] = True
                    detected["seo_schema_localbusiness"] = True
                else:
                    if '"Dentist"' in body or '"LocalBusiness"' in body or '"Store"' in body:
                        detected["seo_schema_localbusiness"] = True
                    if '"Organization"' in body:
                        detected["seo_schema_org"] = True
                    if '"SoftwareApplication"' in body:
                        detected["seo_schema_software"] = True
                    if '"LegalService"' in body or '"Attorney"' in body:
                        detected["seo_schema_legalservice"] = True
                    if '"Person"' in body:
                        detected["seo_schema_person"] = True
                    if '"Service"' in body:
                        detected["seo_schema_service"] = True
                    if '"FAQPage"' in body:
                        detected["seo_schema_faq"] = True
                    if '"MedicalProcedure"' in body:
                        detected["seo_schema_medical"] = True
                    if '"AggregateRating"' in body or '"Review"' in body:
                        detected["seo_schema_review"] = True
                    if '"Product"' in body:
                        detected["seo_schema_product"] = True
            if "<h1" in body and "<h2" in body:
                detected["seo_structured_headings"] = True
    except Exception:
        pass

    for key, filename in [("seo_llms_txt", "llms.txt"), ("seo_llms_full", "llms-full.txt")]:
        try:
            r = httpx.get(f"https://{domain}/{filename}", timeout=8.0, follow_redirects=True)
            if r.status_code == 200 and len(r.text) > 50:
                detected[key] = True
        except Exception:
            pass

    try:
        r = httpx.get(f"https://{domain}/robots.txt", timeout=8.0, follow_redirects=True)
        if r.status_code == 200 and ("ChatGPT-User" in r.text or "PerplexityBot" in r.text):
            detected["seo_robots_txt"] = True
    except Exception:
        pass

    return detected


_TAG_RE = re.compile(r"<[^>]+>")
_WORD_RE = re.compile(r"[a-z0-9]+")
# Common stop-words we don't want to count toward a title match.
_STOP = {"the", "and", "for", "with", "your", "you", "are", "our", "from", "what",
         "how", "why", "when", "this", "that", "these", "those", "a", "an", "of",
         "to", "in", "on", "is", "it", "we", "or", "by", "at", "as", "be"}


def _page_words(html: str) -> set[str]:
    """Visible-text word set from an HTML page (tags stripped, lowercased)."""
    text = _TAG_RE.sub(" ", html).lower()
    return set(_WORD_RE.findall(text))


def _significant_words(text: str) -> set[str]:
    """Meaningful words (len>3, non-stopword) from a title/snippet."""
    return {w for w in _WORD_RE.findall((text or "").lower())
            if len(w) > 3 and w not in _STOP}


def _slugify(text: str) -> str:
    return "-".join(_WORD_RE.findall((text or "").lower()))


def _fetch_words(url: str, cache: dict) -> set[str]:
    if url in cache:
        return cache[url]
    words: set[str] = set()
    try:
        r = httpx.get(url, timeout=10.0, follow_redirects=True)
        if r.status_code == 200:
            words = _page_words(r.text)
    except Exception:
        pass
    cache[url] = words
    return words


def _overlap(needle: set[str], haystack: set[str]) -> float:
    if not needle:
        return 0.0
    return len(needle & haystack) / len(needle)


def _content_is_live(domain: str, rec: dict, cache: dict | None = None) -> bool:
    """Is this content rec live on the site (or close enough to count as published)?

    Strong signal: we already pushed it to the CMS (has a platform item id).
    Otherwise crawl candidate URLs (the target page, plus slug guesses) and match
    on *word overlap* — ≥80% of the title's significant words present, or a strong
    snippet overlap — so lightly-reworded or reformatted content still matches.
    Platform-agnostic; only ever promotes.
    """
    if rec.get("webflow_item_id") or rec.get("platform_item_id"):
        return True
    if not domain:
        return False
    cache = cache if cache is not None else {}

    candidates: list[str] = []
    path = (rec.get("target_page") or "").strip()
    if path and path not in ("new",):
        if path.startswith("http"):
            candidates.append(path)
        else:
            candidates.append(f"https://{domain}/{path.lstrip('/')}")
    slug = _slugify(rec.get("title", ""))
    if slug:
        candidates += [f"https://{domain}/{slug}", f"https://{domain}/blog/{slug}"]
    if not candidates:
        candidates.append(f"https://{domain}")

    title_words = _significant_words(rec.get("title", ""))
    snippet_words = _significant_words(rec.get("html_snippet") or rec.get("description") or "")

    for url in candidates:
        page = _fetch_words(url, cache)
        if not page:
            continue
        if title_words and _overlap(title_words, page) >= 0.8:
            return True
        if len(snippet_words) >= 6 and _overlap(snippet_words, page) >= 0.7:
            return True
    return False


def _service_area_cities(customer: dict | None) -> list[str]:
    """Normalized city names from the customer's service_areas (state suffix stripped)."""
    if not customer:
        return []
    raw = customer.get("service_areas")
    if not raw:
        return []
    vals = raw
    if isinstance(raw, str):
        try:
            vals = json.loads(raw)
        except Exception:
            vals = [p for p in re.split(r"[,\n]", raw) if p.strip()]
    if not isinstance(vals, (list, tuple)):
        return []
    out = []
    for c in vals:
        # "Falls Church VA" -> "falls church"; drop a trailing 2-letter state code.
        name = re.sub(r"\b[A-Za-z]{2}\b\s*$", "", str(c).strip()).strip().strip(",").strip()
        if name:
            out.append(name.lower())
    return out


def _rec_mentions_city(rec: dict, cities: list[str]) -> bool:
    blob = ((rec.get("title") or "") + " " + (rec.get("target_page") or "")).lower()
    blob_slug = blob.replace(" ", "-")
    return any(c in blob or c.replace(" ", "-") in blob_slug for c in cities)


# Embedded expert-quote markup: a <blockquote>, a "quoted line" — Name, or "says/
# according to Name". Curly quotes via \u escapes so source encoding can't bite us.
_QUOTE_RE = re.compile(
    r"<blockquote"
    r"|[“\"][^“”\"]{20,200}[”\"]\s*[—–-]\s*[A-Z][a-z]+"
    r"|\b(?:said|says|according to|explains?)\s+[A-Z][a-z]+",
    re.I,
)


def _sitemap_content_urls(domain: str, limit: int = 20) -> list[str]:
    try:
        r = httpx.get(f"https://{domain}/sitemap.xml", timeout=8.0, follow_redirects=True)
        if r.status_code != 200:
            return []
        locs = re.findall(r"<loc>([^<]+)</loc>", r.text)
        content = [u for u in locs if re.search(r"/blog/|/northern-|/location|sell-|/areas?-", u, re.I)]
        return (content or locs)[:limit]
    except Exception:
        return []


def _live_pages_have_quotes(domain: str, pub_recs: list[dict], sample: int = 6) -> bool:
    """Scan a sample of live published content pages for embedded expert-quote markup.

    Expert quotes are frequently embedded inside published blog/location pages rather
    than shipped as a discrete `expert_quote` rec — so we check the live site.
    """
    urls: list[str] = []
    for r in pub_recs:
        if r.get("rec_type") not in ("blog_post", "new_page"):
            continue
        tp = (r.get("target_page") or "").strip()
        if tp.startswith("http"):
            urls.append(tp)
        elif tp.startswith("/"):
            urls.append(f"https://{domain}{tp}")
    urls = list(dict.fromkeys(urls))
    if len(urls) < sample:
        urls = list(dict.fromkeys(urls + _sitemap_content_urls(domain)))
    for u in urls[:sample]:
        try:
            resp = httpx.get(u, timeout=8.0, follow_redirects=True)
            if resp.status_code == 200 and _QUOTE_RE.search(resp.text):
                return True
        except Exception:
            continue
    return False


def _content_task_status(recs: list[dict], customer: dict | None = None,
                         domain: str = "") -> dict[str, bool]:
    """Tick content checklist tasks from content we actually published.

    Maps published rec_types → SEO_GEO_TASKS content keys so the checklist
    reflects shipped work instead of sitting at 0/N. Service-area pages and
    expert quotes have no dedicated rec_type (location pages publish as
    `new_page`; quotes are embedded in content), so we additionally check the
    live site for those two.
    """
    pub = [r for r in recs if r.get("status") == "published"]
    types = {r.get("rec_type") for r in pub}
    out: dict[str, bool] = {}
    if "faq_update" in types:
        out["seo_faq_sections"] = True
    if "expert_quote" in types:
        out["seo_expert_quotes"] = True
    if "stat_injection" in types:
        out["seo_stats_embedded"] = True
    if "blog_post" in types:
        out["seo_blog_cadence"] = True
    if "new_page" in types:
        out["seo_content_depth"] = True
    if "gbp_qa" in types:
        out["seo_gbp_qa"] = True
    cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%d")
    if any(r.get("rec_type") == "freshness_update" and (r.get("published_at") or "")[:10] >= cutoff
           for r in pub):
        out["seo_fresh_content"] = True

    # Service-area / location pages: tick when service areas are configured AND we've
    # published ≥2 location pages targeting those cities (no dedicated rec_type).
    cities = _service_area_cities(customer)
    if cities:
        loc_pages = [r for r in pub if r.get("rec_type") == "new_page" and _rec_mentions_city(r, cities)]
        if len(loc_pages) >= 2:
            out["seo_service_area_pages"] = True

    # Expert quotes embedded in live content (only scan when not already ticked).
    if domain and not out.get("seo_expert_quotes"):
        if _live_pages_have_quotes(domain, pub):
            out["seo_expert_quotes"] = True
    return out


def _recent_data(db, customer_id: str, days: int = 14) -> bool:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    g = db.conn.execute(
        "SELECT MAX(date) FROM gsc_daily_metrics WHERE customer_id=?", (customer_id,)
    ).fetchone()[0]
    a = db.conn.execute(
        "SELECT MAX(run_date) FROM ai_mention_runs WHERE customer_id=?", (customer_id,)
    ).fetchone()[0]
    return bool((g and g >= cutoff) or (a and str(a)[:10] >= cutoff))


# ---------------------------------------------------------------------------
# Reconcile one customer
# ---------------------------------------------------------------------------

def reconcile_customer(db, customer_id: str, dry_run: bool = True) -> dict:
    """Run all four checks for one customer. Returns a structured diff."""
    customer = db.get_customer(customer_id)
    if not customer:
        raise ValueError(f"Unknown customer: {customer_id}")
    domain = customer.get("domain", "")
    result = {
        "customer_id": customer_id,
        "domain": domain,
        "issues_fixed": [],
        "content_published": [],
        "todos_ticked": [],
        "transition": None,
        "alerts": [],
        "dry_run": dry_run,
    }

    # --- 1. Audit issues: re-audit, resolve fixed, persist fresh scores ---
    open_issues = db.get_audit_issues(customer_id, status="open")
    audit = run_site_audit(domain, platform=customer.get("platform", "")) if domain else {"issues": [], "scores": {}}
    current = {(i.get("category"), i.get("title")) for i in audit.get("issues", [])}
    for issue in open_issues:
        if (issue.get("category"), issue.get("title")) not in current:
            result["issues_fixed"].append({"id": issue["id"], "title": issue.get("title")})
            if not dry_run:
                db.update_audit_issue_status(issue["id"], "fixed")
    open_critical = sum(1 for i in audit.get("issues", []) if i.get("severity") == "critical")
    result["audit_scores"] = audit.get("scores") or {}
    # Persist the audit daily so the Site Audit card stays current (scores + new
    # issues, deduped) instead of only refreshing on the weekly GSC pull.
    if domain and not dry_run and audit.get("scores"):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        db.save_site_audit(customer_id, today, audit.get("scores", {}),
                           audit.get("issues", []), audit.get("raw_data"))

    # --- 2. Content: mark live recs as published ---
    page_cache: dict = {}  # share fetched pages across recs in this run
    for rec in db.get_content_recommendations(customer_id, limit=200):
        if rec.get("status") in ("published", "rejected"):
            continue
        if _content_is_live(domain, rec, page_cache):
            result["content_published"].append({"id": rec["id"], "title": rec.get("title")})
            if not dry_run:
                db.update_content_recommendation_status(rec["id"], "published")

    # --- 3. Todos: persist auto-detected completions (schema live + content shipped) ---
    detected = detect_live_status(domain)
    recs_all = db.get_content_recommendations(customer_id, limit=200)
    detected.update(_content_task_status(recs_all, customer, domain))
    checklist = db.get_checklist(customer_id)
    for key, done in detected.items():
        if done and not checklist.get(key):
            result["todos_ticked"].append(key)
            if not dry_run:
                db.set_checklist_item(customer_id, key, True)

    # --- 4. Status / onboarding_step auto-advance ---
    step = customer.get("onboarding_step", "new")
    status = customer.get("status", "onboarding")

    # Content gate: only block on work we *committed* to (status 'approved' but not
    # yet live). draft/pending recs are an ongoing idea backlog and never block —
    # an active customer always has pending suggestions.
    just_published = {c["id"] for c in result["content_published"]}
    approved_unpublished = [r for r in recs_all
                            if r.get("status") == "approved" and r["id"] not in just_published]

    has_core_schema = bool(detected.get("seo_schema_localbusiness") or detected.get("seo_schema_org"))
    checks = {
        "no_critical_issues": open_critical == 0,
        "schema_live": has_core_schema,
        "llms_txt_live": bool(detected.get("seo_llms_txt")),
        "robots_live": bool(detected.get("seo_robots_txt")),
        "approved_content_published": len(approved_unpublished) == 0,
        "recent_data": _recent_data(db, customer_id),
    }
    fully_live = all(checks.values())
    result["advance_blockers"] = [k for k, v in checks.items() if not v]

    if fully_live and not (status == "active" and step == "monitoring"):
        result["transition"] = {"from": f"{status}/{step}", "to": "active/monitoring"}
        msg = ("Auto-advanced to active — site fully live "
               "(0 critical issues; schema, llms.txt & robots detected; "
               "all approved content published; data flowing).")
        result["alerts"].append(msg)
        if not dry_run:
            if status != "active":  # active→active is an invalid FSM transition
                db.set_customer_status(customer_id, "active")
            db.set_onboarding_step(customer_id, "monitoring")
            db.add_customer_activity(customer_id, activity_type="status_change",
                                     subject="Auto-advanced to active/monitoring", body=msg,
                                     created_by="daily-status-check")
            db.add_alert(customer_id, "auto_advanced", "info", "daily-status-check", msg)

    # Regression guard: a live customer that lost core signals → attention + alert.
    elif status == "active" and step == "monitoring":
        broken = []
        if open_critical > 0:
            broken.append(f"{open_critical} critical audit issue(s) reappeared")
        if not has_core_schema:
            broken.append("schema missing")
        if not detected.get("seo_llms_txt"):
            broken.append("llms.txt missing")
        if broken:
            msg = "Live site regressed: " + ", ".join(broken)
            result["transition"] = {"from": "active/monitoring", "to": "active/attention"}
            result["alerts"].append(msg)
            if not dry_run:
                db.set_onboarding_step(customer_id, "attention")
                db.add_customer_activity(customer_id, activity_type="status_change",
                                         subject="Flagged for attention", body=msg,
                                         created_by="daily-status-check")
                db.add_alert(customer_id, "regression", "critical", "daily-status-check", msg)

    return result


def reconcile_all(db, dry_run: bool = True) -> list[dict]:
    """Reconcile every customer in the active book. One failure can't block the rest."""
    out = []
    for c in db.list_customers():
        if c.get("status") not in RECONCILE_STATUSES:
            continue
        # Cut-over customers only — no recurring reconcile / alerts until the site
        # is live with our changes (see specs/active/paying-only-recurring-work.md).
        if not c.get("cutover"):
            continue
        try:
            out.append(reconcile_customer(db, c["id"], dry_run=dry_run))
        except Exception:
            logger.exception("Reconcile failed for %s", c.get("id"))
    return out
