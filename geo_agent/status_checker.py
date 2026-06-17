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

import logging
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
                    if '"Dentist"' in body or '"LocalBusiness"' in body:
                        detected["seo_schema_localbusiness"] = True
                    if '"Organization"' in body or '"SoftwareApplication"' in body:
                        detected["seo_schema_org"] = True
                    if '"FAQPage"' in body:
                        detected["seo_schema_faq"] = True
                    if '"MedicalProcedure"' in body:
                        detected["seo_schema_medical"] = True
                    if '"AggregateRating"' in body or '"Review"' in body:
                        detected["seo_schema_review"] = True
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


def _content_is_live(domain: str, rec: dict) -> bool:
    """Conservative check that a content rec is actually on the live site.

    Crawls the target page (or home) and looks for the rec's title or a
    distinctive chunk of its snippet. Platform-agnostic; only ever promotes.
    """
    if not domain:
        return False
    path = (rec.get("target_page") or "").strip()
    if path and not path.startswith("/") and not path.startswith("http"):
        path = "/" + path
    url = path if path.startswith("http") else f"https://{domain}{path}"
    try:
        r = httpx.get(url, timeout=10.0, follow_redirects=True)
        if r.status_code != 200:
            return False
        body = r.text.lower()
    except Exception:
        return False
    title = (rec.get("title") or "").strip().lower()
    if title and len(title) > 8 and title in body:
        return True
    # Fall back to a distinctive slice of the snippet's visible text.
    snippet = (rec.get("html_snippet") or rec.get("description") or "").strip().lower()
    snippet = " ".join(snippet.split())
    if len(snippet) > 40 and snippet[:60] in body:
        return True
    return False


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

    # --- 1. Audit issues: resolve ones no longer present ---
    open_issues = db.get_audit_issues(customer_id, status="open")
    audit = run_site_audit(domain, platform=customer.get("platform", "")) if domain else {"issues": []}
    current = {(i.get("category"), i.get("title")) for i in audit.get("issues", [])}
    for issue in open_issues:
        if (issue.get("category"), issue.get("title")) not in current:
            result["issues_fixed"].append({"id": issue["id"], "title": issue.get("title")})
            if not dry_run:
                db.update_audit_issue_status(issue["id"], "fixed")
    open_critical = sum(1 for i in audit.get("issues", []) if i.get("severity") == "critical")

    # --- 2. Content: mark live recs as published ---
    for rec in db.get_content_recommendations(customer_id, limit=200):
        if rec.get("status") in ("published", "rejected"):
            continue
        if _content_is_live(domain, rec):
            result["content_published"].append({"id": rec["id"], "title": rec.get("title")})
            if not dry_run:
                db.update_content_recommendation_status(rec["id"], "published")

    # --- 3. Todos: persist auto-detected completions ---
    detected = detect_live_status(domain)
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
    recs = db.get_content_recommendations(customer_id, limit=200)
    approved_unpublished = [r for r in recs
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
        try:
            out.append(reconcile_customer(db, c["id"], dry_run=dry_run))
        except Exception:
            logger.exception("Reconcile failed for %s", c.get("id"))
    return out
