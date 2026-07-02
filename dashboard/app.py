"""PracticeRank Dashboard — Web UI for onboarding and managing customers.

Usage:
    python dashboard/app.py                    # Run on port 5001
    python dashboard/app.py --port 8080        # Custom port
    python dashboard/app.py --db path/to.db    # Custom DB path

Login credentials are set via environment variables:
    DASHBOARD_USER=admin
    DASHBOARD_PASS=changeme
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import secrets
import signal
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from functools import wraps
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Load .env before anything else
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import httpx
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file, Response, abort

from geo_agent.db import CustomerDB
from geo_agent.staging import StagingManager

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates" / "emails"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("practicerank.dashboard")

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32))
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Search-intent helpers available in templates (badge keywords by buyer intent).
from geo_agent import keyword_intent as _kw_intent  # noqa: E402
app.jinja_env.globals["kw_intent"] = _kw_intent.classify_intent
app.jinja_env.globals["kw_intent_meta"] = _kw_intent.intent_meta
app.config["PREFERRED_URL_SCHEME"] = "https"

# Trust proxy headers from Caddy so url_for generates https:// URLs
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)


@app.after_request
def add_no_cache_headers(response):
    """Prevent browser and proxy caching of HTML responses."""
    if response.content_type and "text/html" in response.content_type:
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# Globals set at startup
DB_PATH: str | None = None
DATA_DIR: str = str(Path(__file__).resolve().parent.parent / "data")

# In-memory progress tracking for background AI mention checks
# Key: run_id, Value: dict with progress info
_ai_check_progress: dict[str, dict] = {}
_ai_check_progress_lock = threading.Lock()


def get_db() -> CustomerDB:
    return CustomerDB(db_path=DB_PATH)


def get_staging() -> StagingManager:
    return StagingManager(data_dir=DATA_DIR)


# --- Global nav context: sidebar badge counts + automation-health banner ---
_nav_cache: tuple[float, dict] | None = None
_NAV_TTL = 60  # seconds — cheap enough to refresh ~1×/min instead of per page load


@app.context_processor
def inject_nav():
    """Inject sidebar badge counts and any overdue/failed scheduled jobs into every
    template. Cached briefly so it's ~one cheap query per minute, not per request."""
    global _nav_cache
    if not session.get("logged_in"):
        return {}
    now = time.time()
    if _nav_cache and now - _nav_cache[0] < _NAV_TTL:
        return _nav_cache[1]
    ctx: dict = {"nav_badges": {}, "job_problems": []}
    try:
        db = get_db()
        try:
            from geo_agent import job_health as jh
            ctx["nav_badges"] = {
                "content_queue": db.count_all_pending_content(),
                "alerts": db.get_active_alert_count(),
            }
            ctx["job_problems"] = jh.job_problems(db)
        finally:
            db.close()
    except Exception:
        logger.warning("nav context computation failed", exc_info=True)
    _nav_cache = (now, ctx)
    return ctx


# --- Audit Logging ---

AUDIT_DIR = Path(DATA_DIR).parent / "audit_logs"


def audit_log(action: str, customer_id: str = "", details: str = "", **extra):
    """Write an audit log entry as JSONL. One file per day."""
    try:
        AUDIT_DIR.mkdir(parents=True, exist_ok=True)
        now = datetime.now(timezone.utc)
        entry = {
            "timestamp": now.isoformat(),
            "user": session.get("username", "system"),
            "action": action,
            "customer_id": customer_id,
            "details": details,
            "ip": request.remote_addr if request else "",
        }
        entry.update(extra)
        log_file = AUDIT_DIR / f"audit_{now.strftime('%Y-%m-%d')}.jsonl"
        with open(log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        logger.exception("Failed to write audit log")


# --- Auth ---

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        # Try DB-based multi-user auth first
        db = get_db()
        user = db.authenticate_user(username, password)
        if user:
            session["logged_in"] = True
            session["username"] = user["username"]
            session["display_name"] = user["display_name"] or user["username"]
            audit_log("login", details=f"DB user '{user['username']}' logged in")
            return redirect(url_for("index"))

        # Fallback to legacy env-var auth
        expected_user = os.environ.get("DASHBOARD_USER", "admin")
        expected_pass = os.environ.get("DASHBOARD_PASS", "")
        if expected_pass and username == expected_user and password == expected_pass:
            session["logged_in"] = True
            session["username"] = username
            session["display_name"] = username
            audit_log("login", details=f"Legacy user '{username}' logged in")
            return redirect(url_for("index"))

        audit_log("login_failed", details=f"Failed login attempt for '{username}'")
        flash("Invalid credentials.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    audit_log("logout")
    session.clear()
    return redirect(url_for("login"))


# --- Dashboard Home ---

@app.route("/")
@login_required
def index():
    db = get_db()
    try:
        all_customers = db.list_customers()
        staging = get_staging()

        from geo_agent import action_items as ai
        for c in all_customers:
            c["pending_count"] = len(db.get_pending_access(c["id"]))
            c["is_staged"] = staging.is_staged(c["id"])
            c["is_approved"] = staging.is_approved(c["id"])
            places = db.get_google_places(c["id"])
            c["rating"] = places["rating"] if places else None
            c["review_count"] = places["review_count"] if places else None
            if c["status"] != "archived":
                c["action_items"] = ai.customer_action_items(db, c)
                c["worst_severity"] = ai.worst_severity(c["action_items"])
                c["seo_score"], c["seo_delta"] = db.seo_score_and_delta(c["id"], _earlier_date(25))
                from geo_agent import outcomes as _oc
                c["inquiries_30d"] = _oc.inquiries_in_window(
                    db, c["id"], _earlier_date(30), _earlier_date(0))

        # Filter out archived for main view
        customers = [c for c in all_customers if c["status"] != "archived"]
        archived_count = sum(1 for c in all_customers if c["status"] == "archived")

        active_alerts = db.get_active_alert_count()
        # Sort so customers needing the most urgent attention float to the top.
        _sev_rank = {"critical": 3, "warning": 2, "info": 1, None: 0}
        customers.sort(key=lambda c: (_sev_rank.get(c.get("worst_severity")), len(c.get("action_items") or [])), reverse=True)

        stats = {
            "total": len(customers),
            "active": sum(1 for c in customers if c["status"] == "active"),
            "onboarding": sum(1 for c in customers if c["status"] == "onboarding"),
            "pending_approval": sum(1 for c in customers if c.get("is_staged") and not c.get("is_approved")),
            "archived": archived_count,
            "active_alerts": active_alerts,
            "needs_attention": sum(1 for c in customers if c.get("worst_severity") in ("critical", "warning")),
            "critical": sum(1 for c in customers if c.get("worst_severity") == "critical"),
        }

        return render_template("index.html", customers=customers, stats=stats)
    finally:
        db.close()


@app.route("/health")
@login_required
def system_health():
    """Operator-facing 'is the automation working?' page: scheduled-job heartbeats
    and integration/credential status. Lets Dan self-diagnose silent failures."""
    from geo_agent import job_health as jh
    db = get_db()
    try:
        jobs = jh.job_health(db)
    finally:
        db.close()
    integrations = jh.integration_health()
    return render_template("system_health.html", jobs=jobs, integrations=integrations)


@app.route("/customer/<customer_id>/case-value", methods=["POST"])
@login_required
def set_case_value(customer_id):
    """Set a practice's average case value (whole $) — powers the outcome/ROI
    headline (new-patient inquiries → estimated production) on the report."""
    db = get_db()
    try:
        raw = (request.form.get("avg_case_value") or "").strip()
        try:
            acv = int(float(raw)) if raw else None
        except ValueError:
            acv = None
        updates = {"avg_case_value": acv}
        cr = (request.form.get("close_rate") or "").strip()
        if cr:
            try:
                updates["close_rate"] = max(0.0, min(1.0, float(cr)))
            except ValueError:
                pass
        rt = (request.form.get("review_target_pm") or "").strip()
        if rt:
            try:
                updates["review_target_pm"] = max(0, int(float(rt)))
            except ValueError:
                pass
        db.update_customer(customer_id, **updates)
        audit_log("case_value_set", customer_id=customer_id, details=f"avg_case_value={acv}")
        flash("Average case value updated — the report now shows estimated production."
              if acv else "Average case value cleared.", "success")
    finally:
        db.close()
    return redirect(url_for("customer_detail", customer_id=customer_id) + "#overview")


# --- SEO Health Score & CTR Opportunities ---

# Expected CTR by position (industry averages)
_EXPECTED_CTR = {
    1: 0.30, 2: 0.15, 3: 0.10, 4: 0.07, 5: 0.05,
    6: 0.04, 7: 0.03, 8: 0.025, 9: 0.02, 10: 0.018,
    11: 0.015, 12: 0.012, 13: 0.010, 14: 0.009, 15: 0.008,
    16: 0.007, 17: 0.006, 18: 0.005, 19: 0.004, 20: 0.003,
}


def _directory_listing_found(html: str, name: str, dir_domain: str) -> tuple[bool, str]:
    """Per-result match for a DuckDuckGo HTML directory search. Returns (found, profile_url).

    A listing is only 'found' when a SINGLE result both (a) links to the directory's own
    domain AND (b) contains the practice name (or nearly all its name tokens) in that same
    result's url/title. This prevents the page-wide-substring false positives that were
    writing bogus checklist checkmarks (a competitor result + the directory word anywhere).
    """
    import re
    import urllib.parse as _up
    name_l = name.lower().strip()
    tokens = [t for t in re.findall(r"[a-z0-9]+", name_l) if len(t) > 2]
    need = max(1, len(tokens) - 1)  # allow one token to be missing (abbreviations, &, etc.)
    for m in re.finditer(r'result__a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.S | re.I):
        href, title = m.group(1), re.sub(r"<[^>]+>", " ", m.group(2))
        dec = re.search(r"uddg=([^&]+)", href)  # DDG wraps the real URL in a redirect param
        url = _up.unquote(dec.group(1)) if dec else href
        url_l, title_l = url.lower(), title.lower()
        if dir_domain not in url_l:
            continue
        hay = url_l + " " + title_l
        if name_l in hay or (tokens and sum(t in hay for t in tokens) >= need):
            return True, url
    return False, ""


def _earlier_date(days_ago: int) -> str:
    """ISO date `days_ago` days before today (UTC). For 'vs ~N days ago' deltas."""
    from datetime import timedelta
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y-%m-%d")


from geo_agent.seo_health import compute_seo_health as _compute_seo_health  # noqa: E402


def _compute_ctr_opportunities(keyword_summary) -> list[dict]:
    """Find keywords with high impressions but CTR well below expected."""
    opportunities = []
    if not keyword_summary:
        return opportunities

    for kw in keyword_summary:
        pos = kw.get("current_position")
        impr = kw.get("current_impressions", 0)
        clicks = kw.get("current_clicks", 0)
        if not pos or not impr or impr < 50:
            continue

        pos_bucket = min(20, max(1, round(pos)))
        expected = _EXPECTED_CTR.get(pos_bucket, 0.003)
        actual_ctr = clicks / impr if impr > 0 else 0

        # Flag if actual CTR is less than 50% of expected
        if actual_ctr < expected * 0.5:
            opportunities.append({
                "keyword": kw["keyword"],
                "position": pos,
                "impressions": impr,
                "clicks": clicks,
                "ctr": actual_ctr,
                "expected_ctr": expected,
            })

    # Sort by impressions desc (biggest opportunity first)
    opportunities.sort(key=lambda x: x["impressions"], reverse=True)
    return opportunities[:10]


def _compute_intent_keywords(keyword_summary) -> list[dict]:
    """The highest purchase-intent keywords to target — action/commercial searches
    ('sell gold near me', 'best dentist in austin') ranked by intent priority then
    impressions. This is the 'what brings buyers/sellers to us' list."""
    rows = []
    for kw in keyword_summary or []:
        text = kw.get("keyword", "")
        if not _kw_intent.is_action(text):
            continue
        meta = _kw_intent.intent_meta(text)
        rows.append({
            "keyword": text,
            "intent": meta["tier"],
            "label": meta["label"],
            "color": meta["color"],
            "bg": meta["bg"],
            "local": _kw_intent.has_local_intent(text),
            "position": round(kw["current_position"], 1) if kw.get("current_position") else None,
            "impressions": kw.get("current_impressions", 0) or 0,
            "priority": _kw_intent.target_priority(text),
        })
    rows.sort(key=lambda x: (x["priority"], x["impressions"]), reverse=True)
    return rows[:12]


def _compute_striking_distance(keyword_summary) -> list[dict]:
    """Keywords on page 2 (positions ~11-20) with real impression volume — the highest-ROI
    'target more of these' set: a small ranking push moves them onto page 1. Sorted by
    impressions so the biggest wins are first. This is the 'what to target' tool."""
    out = []
    for kw in keyword_summary or []:
        pos = kw.get("current_position")
        impr = kw.get("current_impressions", 0) or 0
        if pos and 10 < pos <= 20 and impr >= 20:
            out.append({
                "keyword": kw["keyword"],
                "position": round(pos, 1),
                "impressions": impr,
                "clicks": kw.get("current_clicks", 0) or 0,
            })
    out.sort(key=lambda x: x["impressions"], reverse=True)
    return out[:12]


# --- Customer Detail ---

@app.route("/customer/<customer_id>")
@login_required
def customer_detail(customer_id):
    db = get_db()
    try:
        customer = db.get_customer(customer_id)
        if not customer:
            flash(f"Customer not found: {customer_id}", "error")
            return redirect(url_for("index"))

        providers = db.get_providers(customer_id)
        contacts = db.get_contacts(customer_id)
        access = db.get_platform_access(customer_id)
        places = db.get_google_places(customer_id)
        competitors = db.get_competitors(customer_id)
        runs = db.get_runs(customer_id, limit=5)
        kpis = {
            "review_count": db.get_kpis(customer_id, "review_count", limit=6),
            "rating": db.get_kpis(customer_id, "rating", limit=6),
            "ai_mentions": db.get_kpis(customer_id, "ai_mentions", limit=6),
            "llms_txt_hits": db.get_kpis(customer_id, "llms_txt_hits", limit=6),
        }

        staging = get_staging()
        staged = staging.is_staged(customer_id)
        approved = staging.is_approved(customer_id)
        diff_report = staging.generate_diff_report(customer_id) if staged else ""
        staged_file_contents = staging.get_staged_files(customer_id) if staged else {}
        staged_files = list(staged_file_contents.keys())
        schema_content = staged_file_contents.get("schema.html", "")

        checklist = db.get_checklist(customer_id)
        todos = _get_va_todos(customer, access, contacts, places, runs, staged, approved, checklist)
        domain = customer.get("domain", "")
        auto_detected = _auto_detect_seo_status(domain, customer_id) if domain else {}
        seo_tasks = _get_seo_tasks(checklist, customer.get("business_type", "practice"), auto_detected=auto_detected, platform=customer.get("platform", "webflow"), domain=domain, customer_id=customer_id, city=customer.get("city", ""))

        # Content recommendations (load before email templates so they can reference recs)
        content_pending = db.get_pending_recommendations_count(customer_id)
        content_recs = db.get_content_recommendations(customer_id, limit=5)

        import markdown
        raw_templates = _get_email_templates(customer.get("onboarding_step"))
        ai_run_summary = db.get_latest_ai_run_summary(customer_id)
        email_templates = []
        email_kwargs = dict(
            kpis=kpis, runs=runs, places=places, diff_report=diff_report,
            content_recs=content_recs, competitors=competitors,
            ai_run_summary=ai_run_summary, access=access, checklist=checklist,
        )
        for t in raw_templates:
            raw = _render_email_template(t["content"], customer, contacts, **email_kwargs)
            lines = raw.splitlines()
            body_lines = [l for l in lines if not l.startswith("Subject:")]
            body_md = "\n".join(body_lines).strip()
            body_html = markdown.markdown(body_md, extensions=["tables"])
            # Neutralize any <script> tags that leaked from staged content
            # (e.g. schema.html JSON-LD in diff reports) — they break page parsing
            body_html = body_html.replace("<script", "&lt;script").replace("</script>", "&lt;/script&gt;")
            email_templates.append({
                "slug": t["slug"],
                "subject": _render_email_template(t["subject"], customer, contacts, **email_kwargs),
                "body_html": body_html,
                "category": t["category"],
                "recommended": t["recommended"],
            })

        # SEO Tools data
        integrations = db.get_integrations(customer_id)
        keyword_summary = db.get_keyword_summary(customer_id)
        latest_audit = db.get_latest_audit(customer_id)
        audit_issues = db.get_audit_issues(customer_id, status="open") if latest_audit else []
        backlinks = db.get_backlinks(customer_id)
        content_topics = db.get_content_topics(customer_id, status="suggested")

        # Date range from query param (default 30d)
        date_range = request.args.get("range", "30d")
        range_days = {"7d": 7, "30d": 30, "90d": 90, "180d": 180}.get(date_range, 30)

        # GSC traffic data (daily clicks/impressions + top pages)
        gsc_daily = []
        gsc_top_pages = []
        gsc_prev_clicks = 0
        gsc_prev_impressions = 0
        gsc_integ = next((i for i in integrations if i["integration"] == "gsc" and i["status"] == "active"), None)
        if gsc_integ:
            try:
                _gsc_prop = gsc_integ["config"].get("property_url", "")
                if _gsc_prop:
                    from geo_agent.gsc_client import fetch_search_metrics, fetch_top_pages
                    from datetime import timedelta as _td
                    _end = (datetime.now(timezone.utc) - _td(days=2)).strftime("%Y-%m-%d")
                    _start = (datetime.now(timezone.utc) - _td(days=2 + range_days)).strftime("%Y-%m-%d")
                    gsc_daily = fetch_search_metrics(_gsc_prop, _start, _end, ["date"]) or []
                    gsc_top_pages = fetch_top_pages(_gsc_prop, _start, _end, limit=10) or []
                    # Previous period for comparison
                    _prev_end = (datetime.now(timezone.utc) - _td(days=2 + range_days)).strftime("%Y-%m-%d")
                    _prev_start = (datetime.now(timezone.utc) - _td(days=2 + range_days * 2)).strftime("%Y-%m-%d")
                    prev_daily = fetch_search_metrics(_gsc_prop, _prev_start, _prev_end, ["date"]) or []
                    gsc_prev_clicks = sum(d.get("clicks", 0) for d in prev_daily)
                    gsc_prev_impressions = sum(d.get("impressions", 0) for d in prev_daily)
            except Exception:
                pass

        # Cache fallback: if the live GSC fetch was skipped (no active integration row /
        # blank property_url) or failed/timed out, render from the cached gsc_daily_metrics
        # table so the Overview's stat cards + trend never blank out when valid stored data
        # exists. (get_gsc_daily returns most-recent-first; the chart wants chronological.)
        if not gsc_daily:
            cached = db.get_gsc_daily(customer_id, limit=range_days)
            gsc_daily = list(reversed(cached)) if cached else []
            if gsc_daily and not gsc_prev_clicks:
                prev = db.get_gsc_daily(customer_id, limit=range_days * 2)[range_days:range_days * 2]
                gsc_prev_clicks = sum(d.get("clicks", 0) for d in prev)
                gsc_prev_impressions = sum(d.get("impressions", 0) for d in prev)

        # SEO Health Score — compute + persist via the shared scorer (stable 60-day
        # window inside, so the score never shifts when the date-range pills change).
        _today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        try:
            from geo_agent.seo_health import persist_seo_health
            _health = persist_seo_health(db, customer_id, _today)
        except Exception:
            logger.warning("Failed to persist SEO health for %s", customer_id, exc_info=True)
            _health = None
        if not _health:
            _gsc_health = list(reversed(db.get_gsc_daily(customer_id, limit=60)))
            _health = _compute_seo_health(latest_audit, keyword_summary, _gsc_health)
        seo_health_score = _health["score"]
        seo_health_buckets = _health["buckets"]
        seo_health_history = list(reversed(db.get_seo_health_history(customer_id, limit=180)))
        # Delta vs ~30 days ago: the NEWEST record that is still >=25 days old
        # (history is ascending here, so take the last match; else the oldest we have).
        seo_health_delta = None
        if len(seo_health_history) >= 2:
            _cutoff = _earlier_date(25)
            _older = [h for h in seo_health_history if h["date"] <= _cutoff]
            prior_pt = _older[-1] if _older else seo_health_history[0]
            if prior_pt and prior_pt["date"] != _today:
                seo_health_delta = seo_health_score - prior_pt["score"]

        # CTR Opportunities
        ctr_opportunities = _compute_ctr_opportunities(keyword_summary)
        striking_distance = _compute_striking_distance(keyword_summary)
        intent_keywords = _compute_intent_keywords(keyword_summary)

        # Active alerts for this customer
        customer_alerts = db.get_alerts(customer_id, active_only=True, limit=10)

        # Webflow OAuth connection status
        webflow_connected = db.get_webflow_oauth_token(customer_id) is not None
        webflow_app = db.get_webflow_oauth_app(customer_id)

        # Squarespace connection status
        squarespace_connected = db.get_squarespace_credentials(customer_id) is not None

        # WordPress PracticeRank plugin connection status
        from geo_agent.secrets import get_secrets as _get_secrets
        _wp_key = _get_secrets().get_customer_secret(customer_id, "WP_API_KEY")
        wp_connected = bool(_wp_key)

        # Auto-sync platform access status based on actual evidence
        access_map = {a["platform"]: a for a in access}
        _sync_changes = False
        # GSC: if we have GSC data, mark as granted
        if gsc_daily and access_map.get("gsc", {}).get("status") == "pending":
            db.update_access_status(customer_id, "gsc", "granted")
            _sync_changes = True
        # Webflow: if OAuth connected
        if webflow_connected and access_map.get("webflow", {}).get("status") == "pending":
            db.update_access_status(customer_id, "webflow", "granted")
            _sync_changes = True
        # Squarespace: if credentials exist
        if squarespace_connected and access_map.get("squarespace", {}).get("status") == "pending":
            db.update_access_status(customer_id, "squarespace", "granted")
            _sync_changes = True
        # GBP: if we have Google Places data (rating/reviews)
        if places and access_map.get("gbp", {}).get("status") == "pending":
            db.update_access_status(customer_id, "gbp", "granted")
            _sync_changes = True
        # GA: if integration configured
        ga_int = next((i for i in integrations if i["integration"] == "ga" and i["status"] == "active"), None)
        if ga_int and access_map.get("ga", {}).get("status") == "pending":
            db.update_access_status(customer_id, "ga", "granted")
            _sync_changes = True
        # Refresh access list if anything changed
        if _sync_changes:
            access = db.get_platform_access(customer_id)

        # Tier 2 data
        competitor_domains = db.get_competitor_domains(customer_id)
        citations = db.get_citations(customer_id)
        review_list = db.get_reviews(customer_id, limit=20)
        review_stats = db.get_review_stats(customer_id)


        # Check if there are previously published files (for re-publish button)
        published_schema = Path(DATA_DIR) / "published" / customer_id / "schema.html"
        has_published_schema = published_schema.exists()

        # Published GEO files info for the GEO Files panel
        published_dir = Path(DATA_DIR) / "published" / customer_id
        geo_files = []
        for fname in ("llms.txt", "llms-full.txt", "robots.txt", "schema.html"):
            fpath = published_dir / fname
            if fpath.exists():
                geo_files.append(fname)
        published_schema_path = published_dir / "schema.html"
        published_schema_content = published_schema_path.read_text() if published_schema_path.exists() else ""

        # Current date for template comparisons
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Check if a report exists for this customer
        slug = re.sub(r'[^a-z0-9]+', '-', customer['name'].lower()).strip('-')
        report_zip = Path(DATA_DIR) / "customers" / slug / f"{slug}-ai-optimization.zip"
        report_exists = report_zip.exists()

        # Landing page reports linked to this customer
        landing_reports = [
            dict(r) for r in db.conn.execute(
                "SELECT id, timestamp, overall_score, grade FROM landing_page_reports WHERE customer_id = ? ORDER BY timestamp DESC",
                (customer_id,),
            ).fetchall()
        ]

        try:
            from geo_agent.local_relevancy import va_action_plan
            va_plan = va_action_plan(db, customer)
        except Exception:
            va_plan = None

        # Off-site authority: orders ledger + anchor-mix + monthly link cadence.
        offsite_orders = db.get_offsite_orders(customer_id)
        offsite_assets = db.get_offsite_assets(customer_id)
        link_orders = [o for o in offsite_orders if o["order_type"] == "link"]
        _mix_counts = {"branded": 0, "url": 0, "generic": 0, "partial": 0, "exact": 0}
        for o in link_orders:
            at = (o.get("anchor_type") or "").lower()
            if at in _mix_counts:
                _mix_counts[at] += 1
        _mix_total = sum(_mix_counts.values())
        offsite_anchor_mix = {
            "counts": _mix_counts,
            "total": _mix_total,
            "exact_pct": round(_mix_counts["exact"] / _mix_total * 100) if _mix_total else 0,
        }
        # Lead tracking: the paste-once snippet + whether GA4 is connected (the
        # pull side). track_conversions ingests the events this fires.
        from geo_agent.lead_tracking import lead_tracker_snippet
        lead_snippet = lead_tracker_snippet()
        ga4_connected = any(
            i.get("integration") in ("ga", "ga4") and i.get("status") == "active"
            for i in (integrations or []))

        this_month = now_iso[:7]  # YYYY-MM
        links_this_month = sum(1 for o in link_orders if (o.get("ordered_at") or "")[:7] == this_month)
        da_val = (db.get_latest_kpi(customer_id, "domain_authority") or {}).get("value")
        cadence_target = 2 if (da_val is None or da_val < 25) else 3
        last_link_date = link_orders[0].get("ordered_at", "")[:10] if link_orders else ""
        offsite_cadence = {
            "this_month": links_this_month, "target": cadence_target, "last_link_date": last_link_date,
        }

        # Billing + this-period FATJOE orders Dan still owes (driven by paid tier).
        _subscription = db.get_subscription_for_customer(customer_id)
        from geo_agent import fatjoe_plan as _fp
        _fatjoe_due = _fp.due_orders(db, customer_id,
                                     _subscription["plan_name"] if _subscription else None)

        return render_template(
            "customer_detail.html",
            customer=customer, providers=providers, contacts=contacts,
            access=access, places=places, competitors=competitors,
            runs=runs, kpis=kpis, staged=staged, approved=approved,
            diff_report=diff_report, staged_files=staged_files, schema_content=schema_content,
            todos=todos, email_templates=email_templates,
            seo_tasks=seo_tasks, content_pending=content_pending,
            content_recs=content_recs, customer_alerts=customer_alerts,
            report_exists=report_exists, now_iso=now_iso,
            webflow_connected=webflow_connected,
            webflow_app=webflow_app,
            squarespace_connected=squarespace_connected,
            wp_connected=wp_connected,
            has_published_schema=has_published_schema,
            geo_files=geo_files,
            worker_api_url=WORKER_API_URL,
            published_schema_content=published_schema_content,
            integrations=integrations,
            keyword_summary=keyword_summary,
            latest_audit=latest_audit,
            audit_issues=audit_issues,
            backlinks=backlinks,
            content_topics=content_topics,
            gsc_daily=gsc_daily,
            gsc_top_pages=gsc_top_pages,
            gsc_prev_clicks=gsc_prev_clicks,
            gsc_prev_impressions=gsc_prev_impressions,
            date_range=date_range,
            seo_health_score=seo_health_score,
            seo_health_buckets=seo_health_buckets,
            seo_health_history=seo_health_history,
            seo_health_delta=seo_health_delta,
            ctr_opportunities=ctr_opportunities,
            striking_distance=striking_distance,
            intent_keywords=intent_keywords,
            competitor_domains=competitor_domains,
            citations=citations,
            review_list=review_list,
            review_stats=review_stats,
            landing_reports=landing_reports,
            weekly_snapshot=db.get_latest_report_snapshot(customer_id, "weekly"),
            report_history=db.get_report_snapshots(customer_id, "weekly", limit=26),
            report_periods=[
                {"type": "weekly", "label": "Weekly", "period": 7},
                {"type": "monthly", "label": "Monthly", "period": 30},
                {"type": "quarterly", "label": "Quarterly", "period": 90},
            ],
            report_latest_by_type={
                rt: db.get_latest_report_snapshot(customer_id, rt)
                for rt in ("weekly", "monthly", "quarterly")
            },
            report_history_by_type={
                rt: db.get_report_snapshots(customer_id, rt, limit=26)
                for rt in ("weekly", "monthly", "quarterly")
            },
            customer_activities=db.get_customer_activities(customer_id, limit=100),
            va_plan=va_plan,
            customer_services=db.get_services(customer_id),
            da_latest=db.get_latest_kpi(customer_id, "domain_authority"),
            da_history=list(reversed(db.get_kpis(customer_id, "domain_authority", limit=12))),
            offsite_orders=offsite_orders,
            offsite_assets=offsite_assets,
            offsite_summary=db.offsite_summary(customer_id),
            offsite_anchor_mix=offsite_anchor_mix,
            offsite_cadence=offsite_cadence,
            lead_snippet=lead_snippet,
            ga4_connected=ga4_connected,
            subscription=_subscription,
            fatjoe_due=_fatjoe_due,
        )
    finally:
        db.close()


# --- Billing (Stripe) ---

# Subscription statuses we treat as "paid / in good standing" for badge coloring.
_BILLING_OK = {"active", "trialing"}
_BILLING_WARN = {"past_due", "unpaid", "incomplete", "incomplete_expired"}


def _handle_stripe_event(db, event) -> None:
    """Idempotently process one verified Stripe event: re-read the subscription's
    current state from Stripe and upsert it. On a freshly-active+paid subscription,
    nudge a matched customer from 'onboarding' toward 'active'."""
    from geo_agent import billing

    event_id = billing._g(event, "id")
    event_type = billing._g(event, "type", "") or ""
    if db.billing_event_seen(event_id):
        return

    sub_id = billing.subscription_id_from_event(event)
    if sub_id:
        parsed = billing.fetch_subscription(sub_id)
        if parsed:
            row = db.upsert_subscription(parsed)
            # Auto-advance a matched, still-onboarding customer once they're paying.
            if (row and row.get("customer_id")
                    and parsed["status"] in _BILLING_OK
                    and parsed.get("last_payment_at")):
                cust = db.get_customer(row["customer_id"])
                if cust and cust.get("status") == "onboarding":
                    try:
                        db.update_customer(row["customer_id"], next_action="✅ Paid — send access email (Leadsie)")
                    except Exception:  # noqa: BLE001
                        pass
    db.record_billing_event(event_id, event_type, sub_id)


@app.route("/webhooks/stripe", methods=["POST"])
def stripe_webhook():
    """Stripe webhook receiver. PUBLIC by design (no login) — authenticated via
    signature verification against STRIPE_WEBHOOK_SECRET."""
    from geo_agent import billing
    event = billing.verify_event(request.get_data(), request.headers.get("Stripe-Signature", ""))
    if event is None:
        return ("invalid signature", 400)
    db = get_db()
    try:
        _handle_stripe_event(db, event)
    except Exception as e:  # noqa: BLE001 — always 200 so Stripe doesn't spam retries on our bugs
        logger.exception("stripe webhook handler error: %s", e)
    finally:
        db.close()
    return ("", 200)


@app.route("/billing")
@login_required
def billing():
    from geo_agent import billing as billing_mod
    db = get_db()
    try:
        subs = db.list_subscriptions()
        mrr_cents = sum(s["amount_cents"] for s in subs
                        if s["status"] in _BILLING_OK and s["billing_interval"] == "month")
        return render_template(
            "billing.html",
            subscriptions=subs,
            customers=db.list_customers(),
            mrr=mrr_cents / 100,
            active_count=sum(1 for s in subs if s["status"] in _BILLING_OK),
            attention=[s for s in subs if s["status"] in _BILLING_WARN],
            billing_enabled=billing_mod.billing_enabled(),
            ok_statuses=list(_BILLING_OK),
            warn_statuses=list(_BILLING_WARN),
        )
    finally:
        db.close()


@app.route("/billing/sync", methods=["POST"])
@login_required
def billing_sync():
    from geo_agent import billing as billing_mod
    db = get_db()
    try:
        n = billing_mod.sync_all(db)
        audit_log("billing_synced", details=f"{n} subscriptions")
        flash(f"Synced {n} subscription(s) from Stripe.", "success")
    except Exception as e:  # noqa: BLE001
        flash(f"Sync failed: {e}", "error")
    finally:
        db.close()
    return redirect(url_for("billing"))


@app.route("/fatjoe")
@login_required
def fatjoe_queue():
    """Dan's monthly FATJOE order queue — for every customer with a paid tier,
    exactly what still needs to be ordered this period, with status. Driven by the
    customer's Stripe plan (subscription.plan_name)."""
    from geo_agent import fatjoe_plan as fp
    db = get_db()
    try:
        rows = []
        unplanned = []
        for cust in db.list_customers():
            sub = db.get_subscription_for_customer(cust["id"])
            plan_name = sub["plan_name"] if sub else None
            paid = bool(sub and sub["status"] in _BILLING_OK)
            override = cust.get("tier_override") or ""
            tier = fp.resolve_tier(plan_name, override)
            if not tier:
                # Active customers with no linked paid plan — surface so they're not forgotten.
                if cust["status"] in ("active", "onboarding"):
                    unplanned.append({"customer": cust, "sub": sub})
                continue
            due = fp.due_orders(db, cust["id"], plan_name, tier_override=override)
            # Ad-hoc margin only: scope COGS to orders that carry a client sell price
            # so subscription/tier link COGS (sell_usd=0) doesn't drag margin negative.
            cogs = db.offsite_spend(cust["id"], adhoc_only=True)
            revenue = db.offsite_revenue(cust["id"])
            rows.append({
                "customer": cust,
                "paid": paid,
                "status": sub["status"] if sub else "—",
                "plan": due,
                "recent_orders": db.get_offsite_orders(cust["id"])[:5],
                "cogs": cogs,
                "revenue": revenue,
                "margin": revenue - cogs,
            })
        rows.sort(key=lambda r: (-r["plan"]["total_due"], r["customer"]["name"]))
        unverified = sum(
            1 for r in rows for i in r["plan"]["items"] if not i.get("price_verified")
        )
        # Live month-to-date FATJOE COGS (real logged spend) — mirrors Expenses.
        _month_start = datetime.now(timezone.utc).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        mtd_spend = db.offsite_spend(since=_month_start)
        catalog = db.get_fatjoe_catalog(active_only=True)
        return render_template(
            "fatjoe.html",
            rows=rows,
            unplanned=unplanned,
            tier_plans=fp.TIER_PLANS,
            total_due=sum(r["plan"]["total_due"] for r in rows),
            order_by_day=fp.MONTHLY_ORDER_BY_DAY,
            unverified_count=unverified,
            mtd_spend=mtd_spend,
            catalog=catalog,
            adhoc_cogs=sum(r["cogs"] for r in rows),
            adhoc_revenue=sum(r["revenue"] for r in rows),
        )
    finally:
        db.close()


@app.route("/fatjoe/<customer_id>/set-tier", methods=["POST"])
@login_required
def fatjoe_set_tier(customer_id):
    """Manually set a customer's tier (for custom payment links / discounted deals whose
    Stripe product name doesn't contain a tier keyword). '' clears the override."""
    from geo_agent import fatjoe_plan as fp
    tier = (request.form.get("tier") or "").strip().lower()
    if tier and tier not in fp.TIER_PLANS:
        flash(f"Unknown tier '{tier}'.", "error")
        return redirect(url_for("fatjoe_queue"))
    db = get_db()
    try:
        db.update_customer(customer_id, tier_override=tier)
        audit_log("tier_override_set", customer_id=customer_id, details=f"tier={tier or '(cleared)'}")
        flash(f"Tier set to {tier.title()}." if tier else "Tier override cleared.", "success")
    finally:
        db.close()
    return redirect(url_for("fatjoe_queue"))


@app.route("/fatjoe/catalog")
@login_required
def fatjoe_catalog():
    """Editable FATJOE product catalog — the single source of truth for COGS +
    buy links. Dan confirms each price against his FATJOE reseller dashboard."""
    db = get_db()
    try:
        items = db.get_fatjoe_catalog(active_only=False)
    finally:
        db.close()
    # Group by family for a clean editor.
    fam_label = {
        "citation": "Local Citations", "blogger_outreach": "Blogger Outreach (fresh links)",
        "niche_edit": "Niche Edits (links into aged posts)", "mention": "Brand Mentions / Digital PR",
    }
    groups = {}
    for it in items:
        groups.setdefault(it["family"], []).append(it)
    grouped = [(fam_label.get(f, f), f, rows) for f, rows in groups.items()]
    return render_template("fatjoe_catalog.html", grouped=grouped,
                           unverified=sum(1 for i in items if not i["verified"]))


@app.route("/fatjoe/catalog/<product_key>/update", methods=["POST"])
@login_required
def fatjoe_catalog_update(product_key):
    """Save a catalog row's price + buy URL (and mark it verified)."""
    db = get_db()
    try:
        if not db.get_catalog_item(product_key):
            flash("Unknown product.", "error")
            return redirect(url_for("fatjoe_catalog"))
        try:
            price = float(request.form.get("price_usd") or 0)
        except ValueError:
            price = 0.0
        try:
            sell = float(request.form.get("sell_usd") or 0)
        except ValueError:
            sell = 0.0
        buy_url = (request.form.get("buy_url") or "").strip()
        # Saving a catalog row always confirms its price (per the catalog page copy:
        # "paste it here, and Save — that marks it ✓ verified"). No checkbox in the form.
        verified = 1
        db.update_catalog_item(product_key, price_usd=price, buy_url=buy_url,
                               verified=verified, sell_usd=sell)
        audit_log("fatjoe_catalog_updated", details=f"{product_key} cogs ${price:.0f} sell ${sell:.0f}")
        flash(f"Saved {product_key} (COGS ${price:.0f} / client ${sell:.0f}).", "success")
    finally:
        db.close()
    return redirect(url_for("fatjoe_catalog"))


@app.route("/fatjoe/<customer_id>/quick-order", methods=["POST"])
@login_required
def fatjoe_quick_order(customer_id):
    """Log a FATJOE order straight from the queue (one click). Records an
    offsite_order with the catalog COGS + today's date so the line drops off
    'due' and the spend flows into Expenses. Optional FATJOE order # captured."""
    db = get_db()
    try:
        if not db.get_customer(customer_id):
            flash("Customer not found.", "error")
            return redirect(url_for("fatjoe_queue"))
        order_type = (request.form.get("order_type") or "link").strip()
        try:
            qty = max(1, int(request.form.get("quantity") or 1))
        except ValueError:
            qty = 1
        try:
            dr_tier = int(request.form["dr_tier"]) if request.form.get("dr_tier") else None
        except ValueError:
            dr_tier = None
        try:
            cost = float(request.form.get("cost_usd") or 0)
        except ValueError:
            cost = 0.0
        vendor_order_id = (request.form.get("vendor_order_id") or "").strip()
        notes = (request.form.get("notes") or "").strip()
        # Double-pay guard: block an identical order logged in the last 15 min unless the
        # operator explicitly confirms (an unlogged order keeps showing as "due", so a
        # reload/double-click here would otherwise log — and re-order — twice).
        if not request.form.get("confirm"):
            _cutoff = (datetime.now(timezone.utc) - timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M:%SZ")
            dup = db.recent_offsite_order(customer_id, order_type, dr_tier, _cutoff)
            if dup:
                flash(
                    f"You already logged a {order_type}"
                    f"{f' DR{dr_tier}' if dr_tier else ''} for {customer_id} minutes ago "
                    f"(#{dup['id']}, {dup['ordered_at'][:16].replace('T', ' ')} UTC). "
                    f"That order is still showing as due? Use “Log anyway” to confirm a second one.",
                    "warning",
                )
                return redirect(url_for("fatjoe_queue",
                                        confirm=f"{customer_id}:{order_type}:{dr_tier or 0}"))
        oid = db.add_offsite_order(
            customer_id, order_type,
            quantity=qty, dr_tier=dr_tier, cost_usd=cost,
            vendor_order_id=vendor_order_id, notes=notes, status="ordered",
        )
        audit_log("fatjoe_order_logged", customer_id=customer_id,
                  details=f"{order_type} x{qty} DR{dr_tier} ${cost:.0f} #{oid}")
        flash(f"Logged {qty}× {order_type} (${cost:.0f}) for {customer_id}.", "success")
    finally:
        db.close()
    return redirect(url_for("fatjoe_queue"))


# Maps a catalog family → offsite_orders.order_type.
_FAMILY_ORDER_TYPE = {
    "citation": "citation",
    "blogger_outreach": "link",
    "niche_edit": "link",
    "mention": "mention",
}


@app.route("/fatjoe/<customer_id>/adhoc-order", methods=["POST"])
@login_required
def fatjoe_adhoc_order(customer_id):
    """Ad-hoc 'add / upgrade a backlink': Dan picks a catalog product (any DR
    band — upgrading is just choosing a higher one), a quantity, and optional
    target/anchor/FATJOE order #. We resolve the catalog row for COGS + retail
    sell price and log an offsite_order with both, so it flows into Expenses
    (COGS) and the ad-hoc revenue/margin view (sell)."""
    db = get_db()
    try:
        if not db.get_customer(customer_id):
            flash("Customer not found.", "error")
            return redirect(url_for("fatjoe_queue"))
        product_key = (request.form.get("product_key") or "").strip()
        item = db.get_catalog_item(product_key)
        if not item:
            flash("Pick a product.", "error")
            return redirect(url_for("fatjoe_queue"))
        try:
            qty = max(1, int(request.form.get("quantity") or 1))
        except ValueError:
            qty = 1
        order_type = _FAMILY_ORDER_TYPE.get(item["family"], "link")
        target_url = (request.form.get("target_url") or "").strip()
        anchor_text = (request.form.get("anchor_text") or "").strip()
        vendor_order_id = (request.form.get("vendor_order_id") or "").strip()
        cost = float(item["price_usd"]) * qty
        sell = float(item["sell_usd"]) * qty
        oid = db.add_offsite_order(
            customer_id, order_type,
            quantity=qty, dr_tier=item.get("dr_tier"),
            cost_usd=cost, sell_usd=sell, status="ordered",
            target_url=target_url, anchor_text=anchor_text,
            vendor_order_id=vendor_order_id,
            notes=f"ad-hoc: {item['label']}",
        )
        audit_log("fatjoe_adhoc_order", customer_id=customer_id,
                  details=f"{product_key} x{qty} cogs ${cost:.0f} sell ${sell:.0f} #{oid}")
        flash(f"Ordered {qty}× {item['label']} — client ${sell:.0f} / COGS ${cost:.0f}.", "success")
    finally:
        db.close()
    return redirect(url_for("fatjoe_queue"))


@app.route("/fatjoe/order/<int:order_id>/delivered", methods=["POST"])
@login_required
def fatjoe_mark_delivered(order_id):
    """Mark a logged FATJOE order delivered (sets delivered_at)."""
    db = get_db()
    try:
        order = db.get_offsite_order(order_id)
        if not order:
            flash("Order not found.", "error")
            return redirect(url_for("fatjoe_queue"))
        db.update_offsite_order(order_id, status="delivered")
        audit_log("fatjoe_order_delivered", customer_id=order["customer_id"], details=f"#{order_id}")
        flash("Marked delivered.", "success")
    finally:
        db.close()
    return redirect(url_for("fatjoe_queue"))


@app.route("/billing/<sub_id>/link", methods=["POST"])
@login_required
def billing_link(sub_id):
    db = get_db()
    try:
        customer_id = request.form.get("customer_id") or None
        db.link_subscription(sub_id, customer_id)
        audit_log("billing_linked", customer_id=customer_id, details=f"sub={sub_id}")
        flash("Subscription link updated.", "success")
    finally:
        db.close()
    return redirect(request.referrer or url_for("billing"))


# --- Weekly customer report (R0) ---

@app.route("/report/<customer_id>/weekly")
@login_required
def weekly_report_view(customer_id):
    """Build + view the latest report fresh (and snapshot it), so the internal view never
    serves a stale cached report. ?period=30 → monthly, 90 → quarterly, 180 → half-year
    (default 7 = weekly). Shared links (/r/<token>) still serve their point-in-time snapshot."""
    from geo_agent import weekly_report as wr
    try:
        period = int(request.args.get("period", 7))
    except (TypeError, ValueError):
        period = 7
    db = get_db()
    try:
        result = wr.generate_and_store(db, customer_id, period_days=period)
        return Response(result["html"], mimetype="text/html")
    finally:
        db.close()


@app.route("/customer/<customer_id>/validate-access", methods=["POST"])
@login_required
def validate_customer_access(customer_id):
    """Auto-check real Google access (post-Leadsie) and update the tracker."""
    db = get_db()
    try:
        from geo_agent.access_validation import validate_google_access
        result = validate_google_access(db, customer_id)
        audit_log("access_validated", customer_id=customer_id,
                  details=", ".join(f"{c['key']}={'granted' if c['granted'] else 'pending'}" for c in result["checked"]))
        return jsonify({"ok": True, **result})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        db.close()


@app.route("/report/<customer_id>/snapshot/<int:snapshot_id>/delete", methods=["POST"])
@login_required
def delete_report_snapshot(customer_id, snapshot_id):
    db = get_db()
    try:
        db.delete_report_snapshot(snapshot_id)
        audit_log("report_snapshot_deleted", customer_id=customer_id, details=str(snapshot_id))
        return jsonify({"ok": True})
    finally:
        db.close()


@app.route("/report/<customer_id>/delete-all", methods=["POST"])
@login_required
def delete_all_reports(customer_id):
    db = get_db()
    try:
        n = db.delete_all_report_snapshots(customer_id, "weekly")
        audit_log("report_history_cleared", customer_id=customer_id, details=f"{n} snapshots")
        return jsonify({"ok": True, "deleted": n})
    finally:
        db.close()


# --- Contacts (add / edit / delete multiple contacts per customer) ---

@app.route("/customer/<customer_id>/contact/add", methods=["POST"])
@login_required
def add_customer_contact(customer_id):
    db = get_db()
    try:
        if not db.get_customer(customer_id):
            return jsonify({"ok": False, "error": "Customer not found"}), 404
        name = (request.form.get("name") or "").strip()
        if not name:
            return jsonify({"ok": False, "error": "Name is required"}), 400
        cid = db.add_contact(
            customer_id,
            name,
            (request.form.get("email") or "").strip(),
            (request.form.get("phone") or "").strip(),
            (request.form.get("role") or "owner").strip(),
        )
        audit_log("contact_added", customer_id=customer_id, details=name)
        return jsonify({"ok": True, "id": cid})
    finally:
        db.close()


@app.route("/customer/<customer_id>/contact/<int:contact_id>/update", methods=["POST"])
@login_required
def update_customer_contact(customer_id, contact_id):
    db = get_db()
    try:
        c = db.get_contact(contact_id)
        if not c or c.get("customer_id") != customer_id:
            return jsonify({"ok": False, "error": "Contact not found"}), 404
        name = (request.form.get("name") or "").strip()
        if not name:
            return jsonify({"ok": False, "error": "Name is required"}), 400
        db.update_contact(
            contact_id,
            name=name,
            email=(request.form.get("email") or "").strip(),
            phone=(request.form.get("phone") or "").strip(),
            role=(request.form.get("role") or "owner").strip(),
        )
        audit_log("contact_updated", customer_id=customer_id, details=name)
        return jsonify({"ok": True})
    finally:
        db.close()


@app.route("/customer/<customer_id>/contact/<int:contact_id>/delete", methods=["POST"])
@login_required
def delete_customer_contact(customer_id, contact_id):
    db = get_db()
    try:
        c = db.get_contact(contact_id)
        if not c or c.get("customer_id") != customer_id:
            return jsonify({"ok": False, "error": "Contact not found"}), 404
        db.delete_contact(contact_id)
        audit_log("contact_deleted", customer_id=customer_id, details=c.get("name", ""))
        return jsonify({"ok": True})
    finally:
        db.close()


@app.route("/customer/<customer_id>/service-areas", methods=["POST"])
@login_required
def update_service_areas(customer_id):
    """Set the customer's service-area cities (drives Module 3 city pages + GBP)."""
    import json as _json
    db = get_db()
    try:
        if not db.get_customer(customer_id):
            return jsonify({"ok": False, "error": "Customer not found"}), 404
        seen, cities = set(), []
        for part in re.split(r"[,\n]", request.form.get("cities", "")):
            name = part.strip()
            if name and name.lower() not in seen:
                seen.add(name.lower())
                cities.append(name)
            if len(cities) >= 15:
                break
        db.update_customer(customer_id, service_areas=_json.dumps(cities))
        audit_log("service_areas_updated", customer_id=customer_id, details=f"{len(cities)} cities")
        return jsonify({"ok": True, "cities": cities})
    finally:
        db.close()


@app.route("/customer/<customer_id>/citation/mark", methods=["POST"])
@login_required
def mark_citation(customer_id):
    """Manually mark a directory listed+consistent (Path B — no BrightLocal API),
    or undo it. Feeds directory breadth + the NAP-consistency score the same way
    the API would."""
    db = get_db()
    try:
        if not db.get_customer(customer_id):
            return jsonify({"ok": False, "error": "Customer not found"}), 404
        directory = (request.form.get("directory") or "").strip()
        if not directory:
            return jsonify({"ok": False, "error": "directory required"}), 400
        done = (request.form.get("done") or "true").lower() != "false"
        if done:
            db.save_citation(customer_id, directory, listed=True, nap_match=True, url_correct=True)
        else:
            db.delete_citation(customer_id, directory)
        audit_log("citation_marked", customer_id=customer_id, details=f"{directory}={'done' if done else 'reset'}")
        return jsonify({"ok": True})
    finally:
        db.close()


@app.route("/api/customer/<customer_id>/refresh-da", methods=["POST"])
@login_required
def api_refresh_da(customer_id):
    """Pull the customer's Domain Authority from Moz now and snapshot it."""
    db = get_db()
    try:
        from geo_agent.moz_client import track_competitor_da, track_domain_authority
        da = track_domain_authority(db, customer_id)
        if da is None:
            return jsonify({"ok": False, "error": "Moz not configured (set MOZ_API_TOKEN on the server) or no data returned."})
        comps = track_competitor_da(db, customer_id)
        audit_log("domain_authority_refreshed", customer_id=customer_id, details=f"{da} (+{len(comps)} competitors)")
        return jsonify({"ok": True, "da": da, "competitors": len(comps)})
    finally:
        db.close()


def _domain_of(url):
    """Bare hostname from a URL, lowercased, no www/scheme — for DA lookups."""
    s = (url or "").strip().lower()
    s = re.sub(r"^https?://", "", s)
    s = s.split("/")[0]
    return s[4:] if s.startswith("www.") else s


# --- Off-site authority (FATJOE orders ledger — Phase 1, manual) ---

@app.route("/customer/<customer_id>/offsite/order", methods=["POST"])
@login_required
def add_offsite_order_route(customer_id):
    """Log a new FATJOE order (citation / link / mention)."""
    db = get_db()
    try:
        if not db.get_customer(customer_id):
            return jsonify({"ok": False, "error": "Customer not found"}), 404
        f = request.form
        order_type = (f.get("order_type") or "link").strip()
        if order_type not in ("citation", "link", "mention"):
            return jsonify({"ok": False, "error": "bad order_type"}), 400
        try:
            dr_tier = int(f["dr_tier"]) if f.get("dr_tier") else None
        except ValueError:
            dr_tier = None
        try:
            qty = int(f.get("quantity") or 1)
        except ValueError:
            qty = 1
        try:
            cost = float(f.get("cost_usd") or 0)
        except ValueError:
            cost = 0.0
        try:
            sell = float(f.get("sell_usd") or 0)
        except ValueError:
            sell = 0.0
        oid = db.add_offsite_order(
            customer_id, order_type,
            quantity=qty, dr_tier=dr_tier,
            target_url=(f.get("target_url") or "").strip(),
            anchor_text=(f.get("anchor_text") or "").strip(),
            anchor_type=(f.get("anchor_type") or "").strip(),
            cost_usd=cost, sell_usd=sell,
            vendor_order_id=(f.get("vendor_order_id") or "").strip(),
            notes=(f.get("notes") or "").strip(),
            status=(f.get("status") or "ordered").strip(),
        )
        audit_log("offsite_order_added", customer_id=customer_id, details=f"{order_type} #{oid}")
        return jsonify({"ok": True, "order_id": oid})
    finally:
        db.close()


@app.route("/customer/<customer_id>/offsite/<int:order_id>/status", methods=["POST"])
@login_required
def update_offsite_order_route(customer_id, order_id):
    db = get_db()
    try:
        order = db.get_offsite_order(order_id)
        if not order or order["customer_id"] != customer_id:
            return jsonify({"ok": False, "error": "Order not found"}), 404
        status = (request.form.get("status") or "").strip()
        if status not in ("ordered", "in_progress", "delivered", "live",
                          "indexed", "redo_requested", "cancelled"):
            return jsonify({"ok": False, "error": "bad status"}), 400
        db.update_offsite_order(order_id, status=status)
        audit_log("offsite_order_status", customer_id=customer_id, details=f"#{order_id}={status}")
        return jsonify({"ok": True})
    finally:
        db.close()


@app.route("/customer/<customer_id>/offsite/<int:order_id>/delete", methods=["POST"])
@login_required
def delete_offsite_order_route(customer_id, order_id):
    db = get_db()
    try:
        order = db.get_offsite_order(order_id)
        if not order or order["customer_id"] != customer_id:
            return jsonify({"ok": False, "error": "Order not found"}), 404
        db.delete_offsite_order(order_id)
        audit_log("offsite_order_deleted", customer_id=customer_id, details=f"#{order_id}")
        return jsonify({"ok": True})
    finally:
        db.close()


@app.route("/customer/<customer_id>/offsite/<int:order_id>/asset", methods=["POST"])
@login_required
def add_offsite_asset_route(customer_id, order_id):
    """Record a delivered live URL (the 'Mark live' action). For link/mention
    assets, best-effort pulls the live page's domain DA via Moz so the table can
    show authority immediately."""
    db = get_db()
    try:
        order = db.get_offsite_order(order_id)
        if not order or order["customer_id"] != customer_id:
            return jsonify({"ok": False, "error": "Order not found"}), 404
        live_url = (request.form.get("live_url") or "").strip()
        if not live_url:
            return jsonify({"ok": False, "error": "live_url required"}), 400
        domain = _domain_of(live_url)
        atype = order["order_type"]
        is_dofollow = (request.form.get("is_dofollow") or "1") != "0"
        da, da_at = None, None
        if atype in ("link", "mention"):
            try:
                from geo_agent.moz_client import get_domain_authority
                m = get_domain_authority(domain)
                if m and m.get("da") is not None:
                    da = round(m["da"])
                    da_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            except Exception:
                pass
        db.add_offsite_asset(
            order_id, customer_id, live_url,
            asset_type=atype, domain=domain,
            anchor_text=(request.form.get("anchor_text") or order["anchor_text"]).strip(),
            is_dofollow=1 if is_dofollow else 0,
            da=da, da_checked_at=da_at,
        )
        # First delivered asset advances the order to 'delivered'.
        if order["status"] in ("ordered", "in_progress"):
            db.update_offsite_order(order_id, status="delivered")
        audit_log("offsite_asset_added", customer_id=customer_id, details=f"#{order_id} {domain}")
        return jsonify({"ok": True, "da": da})
    finally:
        db.close()


@app.route("/customer/<customer_id>/offsite/<int:order_id>/import", methods=["POST"])
@login_required
def import_offsite_report_route(customer_id, order_id):
    """Phase 2 — ingest a FATJOE CSV report against an order: parse columns,
    dedupe, pull DA for link/mention domains, advance the order to delivered."""
    db = get_db()
    try:
        order = db.get_offsite_order(order_id)
        if not order or order["customer_id"] != customer_id:
            return jsonify({"ok": False, "error": "Order not found"}), 404
        f = request.files.get("report")
        if not f or not f.filename:
            return jsonify({"ok": False, "error": "No CSV uploaded"}), 400
        try:
            from geo_agent.fatjoe_import import import_report
            result = import_report(db, order_id, f.read())
        except Exception as exc:  # noqa: BLE001
            return jsonify({"ok": False, "error": f"Import failed: {exc}"}), 400
        audit_log("offsite_report_imported", customer_id=customer_id,
                  details=f"#{order_id} +{result['added']} assets")
        return jsonify({"ok": True, **result})
    finally:
        db.close()


@app.route("/customer/<customer_id>/offsite/asset/<int:asset_id>/indexed", methods=["POST"])
@login_required
def toggle_offsite_indexed_route(customer_id, asset_id):
    db = get_db()
    try:
        indexed = (request.form.get("indexed") or "1") != "0"
        db.update_offsite_asset(asset_id, indexed=1 if indexed else 0)
        return jsonify({"ok": True})
    finally:
        db.close()


@app.route("/customer/<customer_id>/service/add", methods=["POST"])
@login_required
def add_service_route(customer_id):
    db = get_db()
    try:
        if not db.get_customer(customer_id):
            return jsonify({"ok": False, "error": "Customer not found"}), 404
        name = (request.form.get("name") or "").strip()
        if not name:
            return jsonify({"ok": False, "error": "Name required"}), 400
        existing = {s.get("name", "").lower() for s in (db.get_services(customer_id) or [])}
        if name.lower() not in existing:
            db.add_service(customer_id, name)
            audit_log("service_added", customer_id=customer_id, details=name)
        return jsonify({"ok": True})
    finally:
        db.close()


@app.route("/customer/<customer_id>/service/<int:service_id>/delete", methods=["POST"])
@login_required
def delete_service_route(customer_id, service_id):
    db = get_db()
    try:
        db.delete_service(customer_id, service_id)
        audit_log("service_deleted", customer_id=customer_id, details=str(service_id))
        return jsonify({"ok": True})
    finally:
        db.close()


@app.route("/customer/<customer_id>/scrape-services", methods=["POST"])
@login_required
def scrape_services(customer_id):
    """Fetch the customer's site, extract its services with Claude, save the new
    ones — powers the FAQ schema + the {service} in {city} pages."""
    from geo_agent.service_scraper import scrape_services as _scrape
    db = get_db()
    try:
        customer = db.get_customer(customer_id)
        if not customer:
            return jsonify({"ok": False, "error": "Customer not found"}), 404
        if not (customer.get("domain") or "").strip():
            return jsonify({"ok": False, "error": "No domain on file"}), 400
        found = _scrape(customer.get("domain", ""), customer.get("name", ""),
                        customer.get("business_type", "local business"))
        if not found:
            return jsonify({"ok": False, "error": "Couldn't extract services (site unreachable or no ANTHROPIC key)."}), 502
        existing = {s.get("name", "").lower() for s in (db.get_services(customer_id) or [])}
        added = [n for n in found if n.lower() not in existing]
        for nm in added:
            db.add_service(customer_id, nm)
        audit_log("services_scraped", customer_id=customer_id, details=f"{len(added)} added")
        return jsonify({"ok": True, "added": added, "found": found})
    finally:
        db.close()


@app.route("/r/<token>")
def public_report(token):
    """Public, login-free customer link. Security model: the token is an
    unguessable 24-byte URL-safe random string that maps to exactly ONE report
    snapshot. There are no customer IDs in the URL and no listing/enumeration
    endpoint, so a link cannot be altered to reach another practice's report —
    knowing one token reveals nothing about any other. Revoke by regenerating
    (which we don't, to keep links stable) or by deleting the snapshot row."""
    db = get_db()
    try:
        snap = db.get_report_by_token(token)
        if not snap or not snap.get("html"):
            abort(404)
        # Don't let browsers/proxies cache a customer's report at a shared CDN.
        resp = Response(snap["html"], mimetype="text/html")
        resp.headers["Cache-Control"] = "private, no-store"
        resp.headers["X-Robots-Tag"] = "noindex, nofollow"
        return resp
    finally:
        db.close()


# --- Customer notes / status ---

@app.route("/customer/<customer_id>/note", methods=["POST"])
@login_required
def add_customer_note(customer_id):
    import uuid
    db = get_db()
    try:
        body = (request.form.get("body") or "").strip()
        subject = (request.form.get("subject") or "").strip()
        activity_type = request.form.get("activity_type", "note")
        # Save any attached screenshots to the volume-mounted uploads dir.
        attachments = []
        updir = Path(DATA_DIR) / "uploads" / customer_id
        allowed_ext = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
        for f in request.files.getlist("attachments"):
            if not f or not f.filename:
                continue
            ext = Path(f.filename).suffix.lower()
            if ext not in allowed_ext:
                continue
            updir.mkdir(parents=True, exist_ok=True)
            fname = f"{uuid.uuid4().hex}{ext}"
            f.save(str(updir / fname))
            attachments.append(fname)
        if body or subject or attachments:
            db.add_customer_activity(
                customer_id, activity_type=activity_type, subject=subject, body=body,
                meta={"attachments": attachments} if attachments else None,
                created_by=session.get("username", ""),
            )
        return redirect(url_for("customer_detail", customer_id=customer_id) + "#notes")
    finally:
        db.close()


@app.route("/customer/<customer_id>/upload/<path:filename>")
@login_required
def customer_upload(customer_id, filename):
    """Serve a screenshot/attachment from a customer's uploads dir (auth-gated)."""
    from flask import send_from_directory
    from werkzeug.utils import secure_filename
    safe = secure_filename(filename)
    updir = Path(DATA_DIR) / "uploads" / customer_id
    if not safe or not (updir / safe).is_file():
        abort(404)
    return send_from_directory(str(updir), safe)


@app.route("/customer/<customer_id>/status", methods=["POST"])
@login_required
def update_customer_status(customer_id):
    db = get_db()
    try:
        status_note = request.form.get("status_note")
        next_action = request.form.get("next_action")
        db.set_customer_status_note(
            customer_id,
            status_note=status_note.strip() if status_note is not None else None,
            next_action=next_action.strip() if next_action is not None else None,
        )
        # Log the status change to the timeline for history.
        summary = " · ".join(p for p in [
            f"Status: {status_note.strip()}" if status_note else "",
            f"Next: {next_action.strip()}" if next_action else "",
        ] if p)
        if summary:
            db.add_customer_activity(
                customer_id, activity_type="status", body=summary,
                created_by=session.get("username", ""),
            )
        return redirect(url_for("customer_detail", customer_id=customer_id) + "#notes")
    finally:
        db.close()


@app.route("/customer/<customer_id>/activity/<int:activity_id>/delete", methods=["POST"])
@login_required
def delete_customer_activity(customer_id, activity_id):
    db = get_db()
    try:
        db.delete_customer_activity(customer_id, activity_id)
        return redirect(url_for("customer_detail", customer_id=customer_id) + "#notes")
    finally:
        db.close()


@app.route("/api/sync-emails", methods=["POST"])
@login_required
def api_sync_emails():
    """Pull recent Gmail into per-customer timelines (one inbox → all customers)."""
    from geo_agent.gmail_ingest import sync, GmailNotConfigured
    days = int((request.get_json(silent=True) or {}).get("days", 14))
    db = get_db()
    try:
        summary = sync(db, days=days)
        msg = (f"Filed {summary['filed']} email(s) · {summary['duplicates']} already logged · "
               f"{summary['skipped_no_match']} unmatched · scanned {summary['scanned']}")
        return jsonify({"ok": True, "summary": summary, "message": msg})
    except GmailNotConfigured as e:
        return jsonify({"ok": False, "message": str(e)}), 400
    except Exception as e:
        return jsonify({"ok": False, "message": f"Sync failed: {e}"}), 500
    finally:
        db.close()


# --- Add Customer ---

@app.route("/customer/new", methods=["GET", "POST"])
@login_required
def add_customer():
    if request.method == "POST":
        db = get_db()
        try:
            name = request.form["name"].strip()
            url = request.form["url"].strip()
            contact_name = request.form.get("contact_name", "").strip()
            contact_email = request.form.get("contact_email", "").strip()
            contact_phone = request.form.get("contact_phone", "").strip()
            platform = request.form.get("platform", "unknown")
            business_type = request.form.get("business_type", "practice")

            if not name or not url:
                flash("Practice name and website URL are required.", "error")
                return render_template("add_customer.html")

            # Normalize
            if "://" not in url:
                url = "https://" + url
            domain = urlparse(url).netloc.removeprefix("www.")
            customer_id = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")

            if db.get_customer(customer_id):
                flash(f"Customer ID '{customer_id}' already exists.", "error")
                return render_template("add_customer.html")

            # Auto-detect platform if not specified
            if platform == "auto":
                try:
                    from scripts.onboard import detect_platform
                    platform = detect_platform(domain)
                except Exception:
                    platform = "unknown"

            db.add_customer(
                id=customer_id,
                name=name,
                domain=domain,
                platform=platform,
                business_type=business_type,
                email=contact_email,
            )

            if contact_name:
                db.add_contact(customer_id, contact_name, contact_email, contact_phone, "owner")

            # Auto-detect DNS/hosting infrastructure
            try:
                from geo_agent.hosting_detector import detect_hosting
                hosting_info = detect_hosting(domain)
                db.update_customer(customer_id, hosting_info=json.dumps(hosting_info))
                # If CMS was detected, update platform
                if hosting_info.get("cms") and platform in ("unknown", "auto"):
                    cms = hosting_info["cms"].lower()
                    if "wordpress" in cms:
                        db.update_customer(customer_id, platform="wordpress")
                        platform = "wordpress"
                    elif "webflow" in cms:
                        db.update_customer(customer_id, platform="webflow")
                        platform = "webflow"
                    elif "squarespace" in cms:
                        db.update_customer(customer_id, platform="squarespace")
                        platform = "squarespace"
                    elif "shopify" in cms:
                        db.update_customer(customer_id, platform="shopify")
                        platform = "shopify"
                    elif "wix" in cms:
                        db.update_customer(customer_id, platform="wix")
                        platform = "wix"
            except Exception as e:
                logger.warning(f"Hosting detection failed for {domain}: {e}")

            # Set up platform access tracking
            access_platforms = ["gsc", "ga", "gtm", "gbp", "cloudflare"]
            if platform in ("webflow", "squarespace", "wordpress", "shopify"):
                access_platforms.append(platform)
            for p in access_platforms:
                db.add_platform_access(customer_id, p)

            # Google Places lookup — populate address, phone, rating
            api_key = os.environ.get("GOOGLE_PLACES_API_KEY", "")
            if api_key:
                try:
                    from geo_agent.google_places import fetch_place_data, fetch_nearby_competitors, get_place_types, validate_competitors
                    verified = fetch_place_data(name=name, city="", state="", domain=domain, api_key=api_key, business_type=business_type)
                    if verified:
                        db.update_customer(customer_id,
                            address=verified.address, city=verified.city,
                            state=verified.state, zip=verified.zip_code,
                            phone=verified.phone)
                        db.upsert_google_places(
                            customer_id, verified.place_id,
                            verified.rating, verified.review_count,
                            verified.match_confidence,
                            verified.lat, verified.lng)
                        if verified.lat and verified.lng:
                            bt = business_type or "practice"
                            pt = get_place_types(bt)
                            tq = ""
                            if not pt and bt not in ("practice", ""):
                                tq = f"{bt} near {verified.city} {verified.state}".strip()
                            comps = fetch_nearby_competitors(
                                verified.lat, verified.lng, name, api_key,
                                place_types=pt or None, text_query=tq)
                            comps = validate_competitors(comps, bt)
                            for c in comps[:5]:
                                db.add_competitor(customer_id, c.name, c.rating,
                                    c.review_count, c.address, c.place_id)
                        logger.info(f"Google Places enriched {customer_id}: {verified.address}, {verified.city} {verified.state}")
                except Exception as e:
                    logger.warning(f"Google Places lookup failed for {customer_id}: {e}")

            # Auto-run first AI mention check in background
            try:
                customer_data = db.get_customer(customer_id)
                if customer_data:
                    first_run_id = str(uuid.uuid4())
                    t = threading.Thread(
                        target=_run_ai_check_background,
                        args=(customer_id, first_run_id, dict(customer_data)),
                        daemon=True,
                    )
                    t.start()
                    logger.info(f"Auto-started first AI mention check for {customer_id} (run_id={first_run_id})")
            except Exception as e:
                logger.warning(f"Failed to auto-start AI check for {customer_id}: {e}")

            # Auto-populate business services + service-area cities in the background
            try:
                def _populate_local(cid):
                    """On-add bootstrap so a new company is set up immediately:
                    services + service-area cities, a Domain Authority baseline
                    (so week/month deltas have a start point), and a first
                    local-relevancy pass. Search-data content waits for the
                    bi-weekly cadence (no GSC data on day one)."""
                    bdb = get_db()
                    try:
                        from geo_agent.nearby_cities import ensure_service_areas
                        from geo_agent.service_scraper import ensure_services
                        ensure_services(bdb, cid)
                        ensure_service_areas(bdb, cid)
                        try:
                            from geo_agent.moz_client import track_competitor_da, track_domain_authority
                            track_domain_authority(bdb, cid)
                            track_competitor_da(bdb, cid)
                        except Exception as ex:  # noqa: BLE001
                            logger.info(f"DA baseline skipped for {cid}: {ex}")
                        try:
                            from geo_agent.local_relevancy import run_local_relevancy
                            run_local_relevancy(bdb, cid)
                        except Exception as ex:  # noqa: BLE001
                            logger.info(f"first local-relevancy skipped for {cid}: {ex}")
                    except Exception as ex:  # noqa: BLE001
                        logger.warning(f"populate local data failed for {cid}: {ex}")
                    finally:
                        bdb.close()
                threading.Thread(target=_populate_local, args=(customer_id,), daemon=True).start()
            except Exception as e:
                logger.warning(f"Failed to start local-data populate for {customer_id}: {e}")

            audit_log("customer_created", customer_id=customer_id, details=f"Created '{name}' ({domain}), platform={platform}, type={business_type}")
            flash(f"Customer '{name}' added successfully! First AI mention check running in background.", "success")
            return redirect(url_for("customer_detail", customer_id=customer_id))
        except Exception as e:
            flash(f"Error adding customer: {e}", "error")
            return render_template("add_customer.html")
        finally:
            db.close()

    return render_template("add_customer.html")


# --- Auto-Discovery (AJAX) ---

@app.route("/api/discover", methods=["POST"])
@login_required
def api_discover():
    data = request.get_json()
    name = data.get("name", "")
    url = data.get("url", "")
    business_type = (data.get("business_type") or "practice").lower()

    if not name or not url:
        return jsonify({"error": "Name and URL required"}), 400

    if "://" not in url:
        url = "https://" + url
    domain = urlparse(url).netloc.removeprefix("www.")

    result = {"platform": "unknown", "places": None, "competitors": [], "hosting": None}

    # Detect platform
    try:
        from scripts.onboard import detect_platform
        result["platform"] = detect_platform(domain)
    except Exception:
        pass

    # Detect DNS/hosting infrastructure
    try:
        from geo_agent.hosting_detector import detect_hosting
        hosting = detect_hosting(domain)
        result["hosting"] = hosting
        # Override platform with CMS if detected
        if hosting.get("cms"):
            cms = hosting["cms"].lower()
            if "wordpress" in cms:
                result["platform"] = "wordpress"
            elif "webflow" in cms:
                result["platform"] = "webflow"
            elif "squarespace" in cms:
                result["platform"] = "squarespace"
            elif "wix" in cms:
                result["platform"] = "wix"
    except Exception as e:
        result["hosting_error"] = str(e)

    # Google Places lookup
    api_key = os.environ.get("GOOGLE_PLACES_API_KEY", "")
    if api_key:
        try:
            from geo_agent.google_places import fetch_place_data, fetch_nearby_competitors, get_place_types, validate_competitors
            verified = fetch_place_data(name=name, city="", state="", domain=domain, api_key=api_key, business_type=business_type)
            if verified:
                result["places"] = {
                    "name": verified.name, "address": verified.address,
                    "city": verified.city, "state": verified.state,
                    "zip_code": verified.zip_code, "phone": verified.phone,
                    "rating": verified.rating, "review_count": verified.review_count,
                    "match_confidence": verified.match_confidence,
                }
                if verified.lat and verified.lng:
                    place_types = get_place_types(business_type)
                    comps = fetch_nearby_competitors(
                        verified.lat, verified.lng, name, api_key,
                        place_types=place_types or None,
                    )
                    comps = validate_competitors(comps, business_type)
                    result["competitors"] = [
                        {"name": c.name, "rating": c.rating, "review_count": c.review_count}
                        for c in comps[:5]
                    ]
        except Exception as e:
            result["places_error"] = str(e)

    return jsonify(result)


# --- Update Platform Access ---

@app.route("/customer/<customer_id>/access", methods=["POST"])
@login_required
def update_access(customer_id):
    db = get_db()
    try:
        platform = request.form["platform"]
        new_status = request.form["status"]
        if new_status in ("granted", "not_needed", "pending"):
            db.update_access_status(customer_id, platform, new_status)
            audit_log("access_updated", customer_id=customer_id, details=f"{platform} -> {new_status}")

            # If all access granted, set status to active
            pending = db.get_pending_access(customer_id)
            if not pending:
                customer = db.get_customer(customer_id)
                if customer and customer["status"] == "onboarding":
                    from geo_agent.fsm import InvalidTransition
                    try:
                        db.set_customer_status(customer_id, "active")
                    except InvalidTransition:
                        pass

            # HTMX: return updated access table
            if request.headers.get("HX-Request"):
                customer = db.get_customer(customer_id)
                access = db.get_platform_access(customer_id)
                return render_template("partials/access_table.html", customer=customer, access=access)

            flash(f"{platform.upper()} marked as {new_status}.", "success")
    finally:
        db.close()
    return redirect(url_for("customer_detail", customer_id=customer_id))


# --- Update Customer Status ---

@app.route("/customer/<customer_id>/status", methods=["POST"])
@login_required
def update_status(customer_id):
    db = get_db()
    try:
        new_status = request.form["status"]
        if new_status in ("onboarding", "active", "paused", "churned", "archived"):
            db.set_customer_status(customer_id, new_status)
            audit_log("status_changed", customer_id=customer_id, details=f"Status -> {new_status}")
            flash(f"Status updated to {new_status}.", "success")
    finally:
        db.close()
    return redirect(url_for("customer_detail", customer_id=customer_id))


# --- Approve Staging ---

@app.route("/customer/<customer_id>/approve", methods=["POST"])
@login_required
def approve_staging(customer_id):
    ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    staging = get_staging()
    db = get_db()
    try:
        if staging.is_staged(customer_id):
            staging.approve_changes(customer_id)
            latest_run = db.get_latest_run(customer_id)
            if latest_run and latest_run["status"] == "staged":
                db.approve_run(latest_run["id"])
            audit_log("staging_approved", customer_id=customer_id)
            if ajax:
                return jsonify({"ok": True, "message": "Changes approved!"})
            flash("Changes approved!", "success")
        else:
            if ajax:
                return jsonify({"ok": False, "error": "No staged changes to approve."})
            flash("No staged changes to approve.", "error")
    finally:
        db.close()
    return redirect(url_for("customer_detail", customer_id=customer_id))


# --- Publish Approved Changes ---

def _verify_publish(customer_id: str, db) -> str:
    """Verify published content is live on the customer's site. Returns status message."""
    customer = db.get_customer(customer_id)
    if not customer:
        return ""
    domain = customer.get("domain", "")
    if not domain:
        return ""

    results = []
    try:
        # Check if schema markup is in the live site head (inline or via JS loader)
        resp = httpx.get(f"https://{domain}", timeout=15.0, follow_redirects=True)
        if resp.status_code == 200:
            body = resp.text
            if ("PracticeRank Schema Start" in body
                    or "practicerank_schema" in body
                    or "PracticeRank Schema" in body
                    or "application/ld+json" in body):
                results.append("schema confirmed on site")
            else:
                results.append("schema NOT detected on site yet (may take a few minutes)")
    except Exception as e:
        logger.warning(f"Verification fetch failed for {domain}: {e}")

    try:
        # Check llms.txt — first try the domain directly, then fall back to Worker URL
        resp = httpx.get(f"https://{domain}/llms.txt", timeout=10.0, follow_redirects=True)
        if resp.status_code == 200 and len(resp.text) > 50:
            results.append("llms.txt live on domain")
        elif WORKER_API_URL:
            resp2 = httpx.get(f"{WORKER_API_URL}/geo/{domain}/llms.txt", timeout=10.0)
            if resp2.status_code == 200 and len(resp2.text) > 50:
                results.append(f"llms.txt served via Worker ({WORKER_API_URL}/geo/{domain}/llms.txt)")
            else:
                results.append("llms.txt not found")
        else:
            results.append("llms.txt not found (configure WORKER_API_URL)")
    except Exception:
        pass

    return "; ".join(results) if results else ""


WORKER_API_URL = os.environ.get("WORKER_API_URL", "")
WORKER_SECRET = os.environ.get("WORKER_SECRET", "")


def _publish_llms_to_worker(customer_id: str, db, stage_path: Path) -> list[str]:
    """Push llms.txt and llms-full.txt to the PracticeRank Worker for serving. Returns warnings."""
    warnings = []
    if not WORKER_API_URL or not WORKER_SECRET:
        return warnings  # Silently skip if not configured

    customer = db.get_customer(customer_id)
    domain = customer.get("domain", "") if customer else ""
    if not domain:
        return warnings

    for filename in ("llms.txt", "llms-full.txt", "robots.txt"):
        filepath = stage_path / filename
        if not filepath.exists():
            continue
        content = filepath.read_text()
        try:
            resp = httpx.put(
                f"{WORKER_API_URL}/geo/{domain}/{filename}",
                content=content,
                headers={
                    "Authorization": f"Bearer {WORKER_SECRET}",
                    "Content-Type": "text/plain",
                },
                timeout=15.0,
            )
            if resp.status_code == 200:
                logger.info(f"Pushed {filename} to Worker for {domain}")
            else:
                warnings.append(f"Failed to push {filename} to Worker: {resp.status_code}")
        except Exception as e:
            warnings.append(f"Worker upload error for {filename}: {e}")

    return warnings


def _publish_to_webflow(customer_id: str, db, staging) -> list[str]:
    """Try to auto-publish schema to Webflow via OAuth token. Returns list of warnings."""
    warnings = []
    oauth_token = db.get_webflow_oauth_token(customer_id)
    if not oauth_token:
        warnings.append("No Webflow OAuth connection. Connect Webflow from the customer page to enable auto-publish.")
        return warnings

    customer = db.get_customer(customer_id)
    site_id = customer.get("webflow_site_id", "") if customer else ""
    if not site_id:
        warnings.append("No Webflow site ID configured. Set it in customer settings.")
        return warnings

    # Read the staged schema.html
    stage_path = Path(DATA_DIR) / "staging" / customer_id
    schema_file = stage_path / "schema.html"
    if not schema_file.exists():
        return warnings  # No schema to publish, that's fine

    schema_html = schema_file.read_text()

    from geo_agent.publishers.webflow import WebflowPublisher
    publisher = WebflowPublisher(api_key=oauth_token, site_id=site_id)
    try:
        if not publisher.inject_schema_to_site(schema_html):
            warnings.append("Failed to inject schema to Webflow.")
        elif not publisher.publish_site():
            warnings.append("Schema injected but failed to publish Webflow site.")
        else:
            logger.info(f"Auto-published schema to Webflow for {customer_id}")
    finally:
        publisher.close()

    return warnings


def _publish_customer(customer_id: str, db, staging) -> tuple[list, list[str], str]:
    """Core publish for one customer's approved staged changes: push to Webflow (if
    connected) + push llms/robots to the Worker, move staged→published, update the run,
    verify live, clear resolved alerts. Returns (published_files, warnings, verification).
    Assumes the caller already checked staging.is_approved(customer_id)."""
    customer = db.get_customer(customer_id)
    platform = customer.get("platform", "webflow") if customer else "webflow"
    webflow_warnings = _publish_to_webflow(customer_id, db, staging) if platform == "webflow" else []
    stage_path = Path(DATA_DIR) / "staging" / customer_id
    worker_warnings = _publish_llms_to_worker(customer_id, db, stage_path)
    published = staging.publish_staged(customer_id)
    latest_run = db.get_latest_run(customer_id)
    if latest_run and latest_run["status"] == "approved":
        db.mark_run_published(latest_run["id"])
    verification = _verify_publish(customer_id, db)
    db.dismiss_alerts_for_customer(customer_id, ["schema_invalid", "stale_content", "new_schema"])
    audit_log("published", customer_id=customer_id, details=f"{len(published)} files published")
    return published, webflow_warnings + worker_warnings, verification


@app.route("/publish-all-approved", methods=["POST"])
@login_required
def publish_all_approved():
    """Bulk-publish every customer whose staged changes are approved — the UI equivalent
    of the `--publish-approved` cron, so Dan never needs the CLI to push approved work live."""
    staging = get_staging()
    db = get_db()
    published_customers, failed = [], []
    try:
        for cust in db.list_customers():
            cid = cust["id"]
            if not staging.is_approved(cid):
                continue
            try:
                files, warnings, _ = _publish_customer(cid, db, staging)
                published_customers.append(f"{cust['name']} ({len(files)} files)")
                if warnings:
                    failed.append(f"{cust['name']}: {' '.join(warnings)}")
            except Exception as e:  # noqa: BLE001
                failed.append(f"{cust['name']}: {e}")
    finally:
        db.close()
    if published_customers:
        flash(f"Published {len(published_customers)} customer(s): {', '.join(published_customers)}.",
              "warning" if failed else "success")
    else:
        flash("Nothing to publish — no customers have approved staged changes.", "info")
    if failed:
        flash("Issues: " + " | ".join(failed), "warning")
    return redirect(request.referrer or url_for("runs"))


@app.route("/customer/<customer_id>/publish", methods=["POST"])
@login_required
def publish_staging(customer_id):
    """Publish approved staged changes — auto-push to Webflow if OAuth connected."""
    ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    staging = get_staging()
    db = get_db()
    try:
        if not staging.is_approved(customer_id):
            if ajax:
                return jsonify({"ok": False, "error": "Changes must be approved before publishing."})
            flash("Changes must be approved before publishing.", "error")
            return redirect(url_for("customer_detail", customer_id=customer_id))

        published, all_warnings, verification = _publish_customer(customer_id, db, staging)
        if all_warnings:
            msg = f"Published {len(published)} files. {' '.join(all_warnings)}"
            if verification:
                msg += f" Verification: {verification}"
            if ajax:
                return jsonify({"ok": True, "message": msg, "warning": True})
            flash(msg, "warning")
        else:
            msg = f"Published {len(published)} files."
            if verification:
                msg += f" {verification}"
            if ajax:
                return jsonify({"ok": True, "message": msg})
            flash(msg, "success")
    except Exception as e:
        if ajax:
            return jsonify({"ok": False, "error": f"Publish failed: {e}"})
        flash(f"Publish failed: {e}", "error")
    finally:
        db.close()
    return redirect(url_for("customer_detail", customer_id=customer_id))


# --- Re-publish to Webflow ---

@app.route("/customer/<customer_id>/republish-webflow", methods=["POST"])
@login_required
def republish_webflow(customer_id):
    """Push previously published schema to Webflow using OAuth token."""
    db = get_db()
    try:
        oauth_token = db.get_webflow_oauth_token(customer_id)
        if not oauth_token:
            flash("No Webflow OAuth connection. Click 'Connect Webflow' first.", "error")
            return redirect(url_for("customer_detail", customer_id=customer_id))

        customer = db.get_customer(customer_id)
        site_id = customer.get("webflow_site_id", "") if customer else ""
        if not site_id:
            flash("No Webflow site ID configured.", "error")
            return redirect(url_for("customer_detail", customer_id=customer_id))

        schema_file = Path(DATA_DIR) / "published" / customer_id / "schema.html"
        if not schema_file.exists():
            flash("No published schema.html found. Run the agent first.", "error")
            return redirect(url_for("customer_detail", customer_id=customer_id))

        schema_html = schema_file.read_text()

        from geo_agent.publishers.webflow import WebflowPublisher
        publisher = WebflowPublisher(api_key=oauth_token, site_id=site_id)
        try:
            if not publisher.inject_schema_to_site(schema_html):
                flash("Failed to inject schema to Webflow. Check OAuth permissions.", "error")
            elif not publisher.publish_site():
                flash("Schema injected but failed to publish Webflow site.", "warning")
            else:
                verification = _verify_publish(customer_id, db)
                audit_log("republish_webflow", customer_id=customer_id)
                msg = "Schema pushed to Webflow and site published."
                if verification:
                    msg += f" {verification}"
                flash(msg, "success")
        finally:
            publisher.close()
    except Exception as e:
        flash(f"Re-publish failed: {e}", "error")
    finally:
        db.close()
    return redirect(url_for("customer_detail", customer_id=customer_id))


# --- Re-push GEO files to Worker ---

@app.route("/customer/<customer_id>/repush-worker", methods=["POST"])
@login_required
def repush_worker(customer_id):
    """Re-push published llms.txt/robots.txt files to the Cloudflare Worker."""
    db = get_db()
    try:
        published_dir = Path(DATA_DIR) / "published" / customer_id
        if not published_dir.exists():
            flash("No published files found. Run the agent and publish first.", "error")
            return redirect(url_for("customer_detail", customer_id=customer_id))

        warnings = _publish_llms_to_worker(customer_id, db, published_dir)
        audit_log("repush_worker", customer_id=customer_id)
        if warnings:
            flash(f"Re-push warnings: {' '.join(warnings)}", "warning")
        else:
            customer = db.get_customer(customer_id)
            domain = customer.get("domain", "") if customer else ""
            flash(f"GEO files re-pushed to Worker. Verify at: {WORKER_API_URL}/geo/{domain}/llms.txt", "success")
    except Exception as e:
        flash(f"Re-push failed: {e}", "error")
    finally:
        db.close()
    return redirect(url_for("customer_detail", customer_id=customer_id))


# --- Webflow OAuth ---

WEBFLOW_DEFAULT_CLIENT_ID = os.environ.get("WEBFLOW_CLIENT_ID", "")
WEBFLOW_DEFAULT_CLIENT_SECRET = os.environ.get("WEBFLOW_CLIENT_SECRET", "")
WEBFLOW_AUTH_URL = "https://webflow.com/oauth/authorize"
WEBFLOW_TOKEN_URL = "https://api.webflow.com/oauth/access_token"


def _get_webflow_app(customer_id: str) -> tuple[str, str]:
    """Get Webflow OAuth app credentials for a customer. Falls back to global default."""
    db = get_db()
    try:
        app = db.get_webflow_oauth_app(customer_id)
        if app:
            return app["client_id"], app["client_secret"]
        return WEBFLOW_DEFAULT_CLIENT_ID, WEBFLOW_DEFAULT_CLIENT_SECRET
    finally:
        db.close()


@app.route("/customer/<customer_id>/connect-webflow")
@login_required
def connect_webflow(customer_id):
    """Start Webflow OAuth flow for a customer."""
    client_id, _ = _get_webflow_app(customer_id)
    if not client_id:
        flash("No Webflow OAuth app configured for this customer. Add client ID/secret in settings.", "error")
        return redirect(url_for("customer_detail", customer_id=customer_id))

    # Store customer_id in session so callback knows who authorized
    session["webflow_oauth_customer"] = customer_id
    state = secrets.token_urlsafe(32)
    session["webflow_oauth_state"] = state

    redirect_uri = url_for("webflow_oauth_callback", _external=True)
    scopes = "sites:read sites:write custom_code:read custom_code:write pages:read pages:write cms:read cms:write authorized_user:read"
    auth_url = (
        f"{WEBFLOW_AUTH_URL}"
        f"?client_id={client_id}"
        f"&response_type=code"
        f"&redirect_uri={redirect_uri}"
        f"&scope={scopes}"
        f"&state={state}"
    )
    return redirect(auth_url)


@app.route("/oauth/webflow/callback")
@login_required
def webflow_oauth_callback():
    """Handle Webflow OAuth callback — exchange code for access token."""
    customer_id = session.pop("webflow_oauth_customer", None)
    expected_state = session.pop("webflow_oauth_state", None)

    error = request.args.get("error")
    if error:
        flash(f"Webflow authorization denied: {error}", "error")
        return redirect(url_for("customer_detail", customer_id=customer_id) if customer_id else url_for("index"))

    code = request.args.get("code")
    if not code:
        flash("No authorization code received from Webflow.", "error")
        return redirect(url_for("customer_detail", customer_id=customer_id) if customer_id else url_for("index"))

    # Validate state if we have one (skip for external installs)
    state = request.args.get("state", "")
    if expected_state and state != expected_state:
        flash("OAuth state mismatch. Try connecting again.", "error")
        return redirect(url_for("customer_detail", customer_id=customer_id) if customer_id else url_for("index"))

    # Exchange code for access token — use per-customer app if available
    client_id, client_secret = _get_webflow_app(customer_id) if customer_id else (WEBFLOW_DEFAULT_CLIENT_ID, WEBFLOW_DEFAULT_CLIENT_SECRET)
    redirect_uri = url_for("webflow_oauth_callback", _external=True)
    try:
        resp = httpx.post(
            WEBFLOW_TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        token_data = resp.json()
    except Exception as e:
        flash(f"Failed to exchange OAuth code: {e}", "error")
        return redirect(url_for("customer_detail", customer_id=customer_id) if customer_id else url_for("index"))

    access_token = token_data.get("access_token")
    if not access_token:
        flash(f"No access token in response: {token_data}", "error")
        return redirect(url_for("customer_detail", customer_id=customer_id) if customer_id else url_for("index"))

    # List authorized sites from the token
    db = get_db()
    try:
        sites = []
        try:
            sites_resp = httpx.get(
                "https://api.webflow.com/v2/sites",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=30.0,
            )
            sites_resp.raise_for_status()
            sites = sites_resp.json().get("sites", [])
        except Exception as e:
            logger.warning(f"Could not list sites: {e}")

        if customer_id:
            # Flow initiated from dashboard — match to specific customer
            customer = db.get_customer(customer_id)
            site_id = customer.get("webflow_site_id", "") if customer else ""

            if not site_id:
                domain = customer.get("domain", "") if customer else ""
                for s in sites:
                    custom_domains = s.get("customDomains", [])
                    default_domain = s.get("defaultDomain", "")
                    all_domains = [d.get("url", "") for d in custom_domains] + [default_domain]
                    if any(domain in d for d in all_domains if d):
                        site_id = s["id"]
                        db.update_customer(customer_id, webflow_site_id=site_id)
                        logger.info(f"Auto-detected Webflow site_id {site_id} for {customer_id}")
                        break
                if not site_id and sites and len(sites) == 1:
                    site_id = sites[0]["id"]
                    db.update_customer(customer_id, webflow_site_id=site_id)

            if site_id:
                db.save_webflow_oauth_token(site_id, customer_id, access_token)
                flash("Webflow connected! Schema will auto-publish when you click Publish.", "success")
            else:
                db.save_webflow_oauth_token("pending", customer_id, access_token)
                flash("Webflow authorized, but no site ID found. Set the Webflow Site ID in customer settings.", "warning")

            return redirect(url_for("customer_detail", customer_id=customer_id))
        else:
            # External install — match sites to customers by domain
            matched = 0
            for s in sites:
                custom_domains = s.get("customDomains", [])
                default_domain = s.get("defaultDomain", "")
                all_domains = [d.get("url", "") for d in custom_domains] + [default_domain]

                for cust in db.list_customers():
                    domain = cust.get("domain", "")
                    if domain and any(domain in d for d in all_domains if d):
                        db.update_customer(cust["id"], webflow_site_id=s["id"])
                        db.save_webflow_oauth_token(s["id"], cust["id"], access_token)
                        logger.info(f"Matched Webflow site {s['id']} to customer {cust['id']}")
                        matched += 1
                        break

            if matched:
                flash(f"Webflow connected! Matched {matched} site(s) to customers.", "success")
            elif sites:
                # Save token for first site even if no customer match
                db.save_webflow_oauth_token(sites[0]["id"], "unmatched", access_token)
                site_names = ", ".join(s.get("displayName", s.get("shortName", s["id"])) for s in sites)
                flash(f"Webflow authorized ({site_names}) but no matching customers found. Set Webflow Site IDs in customer settings.", "warning")
            else:
                flash("Webflow authorized but no sites found in workspace.", "warning")

            return redirect(url_for("index"))
    finally:
        db.close()


# --- Webflow OAuth App Settings (per-customer) ---

@app.route("/customer/<customer_id>/webflow-app", methods=["POST"])
@login_required
def save_webflow_app(customer_id):
    """Save per-customer Webflow OAuth app credentials."""
    db = get_db()
    try:
        client_id = request.form.get("webflow_client_id", "").strip()
        client_secret = request.form.get("webflow_client_secret", "").strip()
        if client_id and client_secret:
            db.save_webflow_oauth_app(customer_id, client_id, client_secret)
            audit_log("webflow_app_saved", customer_id=customer_id)
            flash("Webflow OAuth app saved. Click 'Connect Webflow' to authorize.", "success")
        elif not client_id and not client_secret:
            db.delete_webflow_oauth_app(customer_id)
            audit_log("webflow_app_removed", customer_id=customer_id)
            flash("Webflow OAuth app removed. Will use default.", "info")
        else:
            flash("Both Client ID and Client Secret are required.", "error")
    finally:
        db.close()
    return redirect(url_for("customer_detail", customer_id=customer_id))


# --- WordPress Plugin Setup ---

@app.route("/download/practicerank-seo-plugin.zip")
@login_required
def download_wp_plugin():
    """Download the PracticeRank SEO WordPress plugin as a .zip file."""
    import zipfile
    from io import BytesIO

    plugin_path = Path(__file__).resolve().parent.parent / "wp-plugins" / "practicerank-seo.php"
    if not plugin_path.exists():
        abort(404, "Plugin file not found")

    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(plugin_path, "practicerank-seo/practicerank-seo.php")
        # Add a readme for the plugin directory
        zf.writestr("practicerank-seo/readme.txt", (
            "=== PracticeRank SEO ===\n"
            "Contributors: practicerank\n"
            "Tags: seo, schema, llms.txt, ai search\n"
            "Requires at least: 5.6\n"
            "Tested up to: 6.7\n"
            "Requires PHP: 7.4\n"
            "Stable tag: 2.0\n"
            "License: Proprietary\n\n"
            "== Description ==\n"
            "Full SEO/AEO integration for PracticeRank-managed sites. Injects JSON-LD schema,\n"
            "serves llms.txt for AI discoverability, optimizes robots.txt, and accepts content\n"
            "pushes via authenticated REST API.\n\n"
            "== Installation ==\n"
            "1. Upload the plugin folder to /wp-content/plugins/\n"
            "2. Activate from the Plugins page\n"
            "3. Go to Settings > PracticeRank to view your API key\n"
            "4. Share the API key with your PracticeRank account manager\n\n"
            "== Changelog ==\n"
            "= 2.0 =\n"
            "* JSON-LD schema injection (LocalBusiness, FAQ, Service, MedicalProcedure)\n"
            "* REST API for schema, content, and file pushes\n"
            "* Admin settings page with connection status\n"
            "* SEO plugin detection (Yoast, RankMath, AIOSEO)\n"
            "* Content deduplication and draft mode\n"
        ))
    buf.seek(0)
    return send_file(buf, mimetype="application/zip", as_attachment=True,
                     download_name="practicerank-seo-plugin.zip")


@app.route("/customer/<customer_id>/wp-api-key", methods=["POST"])
@login_required
def save_wp_api_key(customer_id):
    """Save WordPress PracticeRank plugin API key for a customer."""
    api_key = request.form.get("wp_api_key", "").strip()
    if not api_key:
        flash("API key is required.", "error")
        return redirect(url_for("customer_detail", customer_id=customer_id))

    # Store as environment variable (persisted via .env on droplet)
    env_key = f"WP_API_KEY_{customer_id.upper().replace('-', '_')}"
    os.environ[env_key] = api_key

    # Also append to .env file if it exists
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if env_file.exists():
        existing = env_file.read_text()
        # Remove old entry if present
        lines = [l for l in existing.splitlines() if not l.startswith(f"{env_key}=")]
        lines.append(f"{env_key}={api_key}")
        env_file.write_text("\n".join(lines) + "\n")

    audit_log("wp_api_key_saved", customer_id=customer_id)
    flash("WordPress API key saved. Use 'Test Connection' to verify.", "success")
    return redirect(url_for("customer_detail", customer_id=customer_id))


@app.route("/api/wordpress/test-connection", methods=["POST"])
@login_required
def api_test_wp_connection():
    """Test the WordPress PracticeRank plugin connection."""
    data = request.get_json()
    customer_id = data.get("customer_id")
    if not customer_id:
        return jsonify({"ok": False, "error": "customer_id required"}), 400

    db = get_db()
    try:
        customer = db.get_customer(customer_id)
        if not customer:
            return jsonify({"ok": False, "error": "Customer not found"}), 404

        from geo_agent.secrets import get_secrets as _gs
        wp_key = _gs().get_customer_secret(customer_id, "WP_API_KEY")
        if not wp_key:
            return jsonify({"ok": False, "error": "No API key configured. Install the plugin and paste the key above."}), 400

        from geo_agent.publishers.wordpress import WordPressPublisher
        publisher = WordPressPublisher(
            site_url=f"https://{customer.get('domain', '')}",
            api_key=wp_key,
        )
        try:
            health = publisher.health_check()
            if health:
                # Update access status
                db.update_access_status(customer_id, "wordpress", "granted")
                return jsonify({
                    "ok": True,
                    "site_name": health.get("site_name"),
                    "wp_version": health.get("wp_version"),
                    "schema_enabled": health.get("schema_enabled"),
                    "has_llms_txt": health.get("has_llms_txt"),
                    "content_as_draft": health.get("content_as_draft"),
                    "seo_plugin": health.get("seo_plugin", "none"),
                })
            return jsonify({"ok": False, "error": "Plugin not responding. Check it is installed and activated."}), 502
        finally:
            publisher.close()
    finally:
        db.close()


# --- Update Customer Fields ---

@app.route("/customer/<customer_id>/edit", methods=["POST"])
@login_required
def edit_customer(customer_id):
    db = get_db()
    try:
        fields = {}
        for key in ("name", "domain", "platform", "business_type", "city", "state", "zip", "address",
                     "phone", "email", "brand_voice", "hours"):
            val = request.form.get(key)
            if val is not None:
                fields[key] = val.strip()

        emergency = request.form.get("emergency_available")
        if emergency is not None:
            fields["emergency_available"] = emergency == "on"

        if fields:
            db.update_customer(customer_id, **fields)
            changed = ", ".join(f"{k}={v[:50]}" for k, v in fields.items() if isinstance(v, str))
            audit_log("customer_edited", customer_id=customer_id, details=changed)
            flash("Customer updated.", "success")
    finally:
        db.close()
    return redirect(url_for("customer_detail", customer_id=customer_id))


# --- Email Templates ---

# Which lifecycle stage each email belongs to, and which onboarding steps it's
# relevant for. Drives the email tab's ordering, category filter, and the
# "recommended for current stage" badge. `order` is the natural send sequence.
EMAIL_TEMPLATE_META = {
    "08-pricing-quote":          {"category": "Sales",      "steps": ["new", "outreach"],                 "order": 1},
    "01-initial-access-request": {"category": "Access",     "steps": ["outreach", "setup"],               "order": 2},
    "02-access-followup":        {"category": "Access",     "steps": ["setup"],                           "order": 3},
    "03-onboarding-complete":    {"category": "Onboarding",  "steps": ["review", "live"],                  "order": 4},
    "05-staging-approval":       {"category": "Approvals",  "steps": ["review", "live"],                  "order": 5},
    "06-content-review":         {"category": "Approvals",  "steps": ["content", "live", "monitoring"],   "order": 6},
    "07-weekly-seo-update":      {"category": "Reporting",  "steps": ["live", "content", "monitoring"],   "order": 7},
    "04-monthly-report":         {"category": "Reporting",  "steps": ["monitoring"],                      "order": 8},
    "09-review-request":         {"category": "Reviews",    "steps": ["live", "content", "monitoring"],   "order": 9},
}

# Order categories surface in the filter bar.
EMAIL_CATEGORY_ORDER = ["Sales", "Access", "Onboarding", "Approvals", "Reporting", "Reviews", "Other"]


def _get_email_templates(current_step: str | None = None) -> list[dict]:
    """Return available email templates with stage metadata.

    Sorted so the emails relevant to ``current_step`` come first (each flagged
    ``recommended``), then by natural send order.
    """
    templates = []
    if not TEMPLATE_DIR.exists():
        return templates
    for f in TEMPLATE_DIR.glob("*.md"):
        with open(f) as fh:
            content = fh.read()
        subject = ""
        for line in content.splitlines():
            if line.startswith("Subject:"):
                subject = line.replace("Subject:", "").strip()
                break
        meta = EMAIL_TEMPLATE_META.get(f.stem, {"category": "Other", "steps": [], "order": 99})
        recommended = bool(current_step and current_step in meta["steps"])
        templates.append({
            "filename": f.name,
            "slug": f.stem,
            "subject": subject,
            "content": content,
            "category": meta["category"],
            "steps": meta["steps"],
            "order": meta["order"],
            "recommended": recommended,
        })
    # Recommended-for-this-stage first, then natural send order.
    templates.sort(key=lambda t: (not t["recommended"], t["order"]))
    return templates


def _content_rec_summary(recs: list[dict]) -> str:
    """Build a markdown summary of content recommendations grouped by type."""
    if not recs:
        return "No content recommendations generated yet."
    by_type: dict[str, list[dict]] = {}
    for r in recs:
        rt = r.get("rec_type", "other").replace("_", " ").title()
        by_type.setdefault(rt, []).append(r)
    lines = []
    for rtype, items in by_type.items():
        lines.append(f"**{rtype}** ({len(items)}):")
        for item in items:
            lines.append(f"- {item.get('title', 'Untitled')}")
    return "\n".join(lines)


# Everything we need from a client to onboard, in send order. `access_key` ties
# an item to a platform_access row (granted/not_needed → satisfied); items with no
# access_key are info/asset asks satisfied by a va_checklist flag. `how` is the
# client-facing "how to grant it" copy (may use {placeholders} — substituted in
# the normal replacements pass). Built dynamically so the email only lists what's
# still outstanding. See specs onboarding + local-relevancy work.
# Leadsie one-click access link — grants all Google properties (Business
# Profile, Analytics, Search Console, Tag Manager) in one secure flow, no
# passwords. Covers the access_keys in LEADSIE_KEYS below.
LEADSIE_LINK = "https://app.leadsie.com/connect/practicerank/manage"
LEADSIE_KEYS = {"gsc", "ga", "gtm", "gbp"}

ONBOARDING_REQUIREMENTS = [
    {"access_key": "gsc", "label": "Google Search Console — Full user",
     "how": "Search Console → Settings → Users and permissions → Add user → "
            "**kdoherty@practicerank.ai**, permission **Full**."},
    {"access_key": "ga", "label": "Google Analytics 4 — add us + send your IDs",
     "how": "At **analytics.google.com** → ⚙️ **Admin** → **Account/Property Access Management** → **+** → "
            "add **kdoherty@practicerank.ai** as **Editor** → Add. Then send us two IDs (or we'll grab them once "
            "you've added us): (1) **Measurement ID** — Admin → **Data Streams** → click your website stream → "
            "top-right, starts with **G-XXXXXXX** (this powers lead tracking on your site); (2) **Property ID** — "
            "Admin → **Property Settings** — a 9-digit number (this lets your reports pull real call/form leads). "
            "Don't have GA4 yet? Tell us and we'll set it up for you."},
    {"access_key": "gtm", "label": "Google Tag Manager — add us + send Container ID",
     "how": "At **tagmanager.google.com** → your container → **Admin** → **User Management** → **+** → add "
            "**kdoherty@practicerank.ai** with **Publish** access. Then send us the **Container ID** "
            "(top of the workspace, starts with **GTM-XXXXXXX**), or we'll read it once you've added us. "
            "This is how we track phone-call clicks and form submissions as leads. "
            "No GTM yet? We'll create one — just grant the access above on the account."},
    {"access_key": "gbp", "label": "Google Business Profile / Google Maps — add us as Manager",
     "how": "This is your Google Maps listing and the #1 local-ranking asset. The fastest way (instant, no "
            "password sharing): the profile **owner** adds us. On a phone, open the **Google Maps** app (or "
            "**business.google.com** on desktop) signed in as the owner → tap your business → **Edit profile** → "
            "**⋯ / Settings → People and access → Add** → enter **kdoherty@practicerank.ai** → role **Manager** → "
            "Invite. We accept and we're in — you stay the Owner. "
            "**Not sure who owns it, or lost access?** Don't share your password — instead go to "
            "**business.google.com**, search your business, click **\"Request access / Own this business?\"**, "
            "and we'll send a request the current owner approves (Google gives them ~3–7 days; if no response we "
            "can claim it). Tell us and we'll walk you through it on a quick call."},
    {"access_key": "__cms__", "label": "Website access ({cms_platform})",
     "how": None},  # filled from the platform-specific access_steps
    {"access_key": "cloudflare", "label": "DNS access ({dns_registrar})",
     "how": "We set up Cloudflare (free — faster loading, security, and AI discoverability, no change to "
            "your site). Either add **kdoherty@practicerank.ai** as a delegate in **{dns_registrar}**, "
            "or share DNS login so we can point your nameservers."},
    {"checklist_key": "nap_confirmed", "label": "Confirm your exact business info (name, address, phone, hours)",
     "how": "Reply confirming the **exact** business name, street address (incl. suite/unit), phone, and hours "
            "you want shown everywhere. We list you across dozens of directories and even tiny differences "
            "(\"Ste 200\" vs \"#200\") hurt local ranking — so we lock one canonical version."},
    {"checklist_key": "brand_assets_received", "label": "Send your logo + 10 real photos",
     "how": "Email us your **logo** and **10+ genuine photos** (exterior, interior, team, and your work/products). "
            "We use these to complete your Google, Apple, and Bing listings — complete profiles with real photos "
            "rank and convert noticeably better than empty ones."},
    {"checklist_key": "services_confirmed", "label": "Confirm services & service-area cities",
     "how": "We've drafted your list of services and the nearby cities you serve from your website and will send "
            "it to confirm. Reply with anything to add, remove, or fix so your local pages target the right terms."},
]


def _onboarding_blocks(customer: dict, access: list[dict] | None,
                       checklist: dict | None, access_steps: str) -> tuple[str, str]:
    """Build the (full_checklist, pending_only) markdown for onboarding emails.

    full_checklist marks satisfied items with ✓ and pending ones with ☐ (for the
    initial request). pending_only lists just the outstanding items (for the
    follow-up). Both include each item's "how to grant it" copy.
    """
    access = access or []
    checklist = checklist or {}
    platform = (customer.get("platform") or "").lower()
    status_by_platform = {a.get("platform"): a.get("status") for a in access}

    full_lines, pending_lines = [], []
    n = 0
    leadsie_pending = False
    for req in ONBOARDING_REQUIREMENTS:
        ak = req.get("access_key")
        if ak == "__cms__":
            # Website/CMS access — satisfied when the CMS access row is granted.
            satisfied = status_by_platform.get(platform) in ("granted", "not_needed")
            how = access_steps
        elif ak:
            st = status_by_platform.get(ak)
            satisfied = st in ("granted", "not_needed")
            how = req["how"]
        else:
            satisfied = bool(checklist.get(req["checklist_key"]))
            how = req["how"]

        if not satisfied and ak in LEADSIE_KEYS:
            leadsie_pending = True

        label, how = req["label"], how or req["how"] or ""
        if satisfied:
            full_lines.append(f"- ✓ **{label}** — received, thank you!")
        else:
            n += 1
            note = "  *(or just use the one-click link above)*" if ak in LEADSIE_KEYS else ""
            full_lines.append(f"**{n}. {label}**{note}\n   - {how}")
            pending_lines.append(f"**{label}**{note}\n   - {how}")

    # Lead with the Leadsie one-click block whenever any Google item is still
    # outstanding — it grants all of them at once, no passwords.
    if leadsie_pending:
        leadsie_block = (
            "### ⚡ Fastest way — connect everything Google in one click\n\n"
            "Most of what we need (Business Profile, Analytics, Search Console "
            "& Tag Manager) can be granted in about 2 minutes with one secure link — "
            "no passwords, nothing to dig through in settings:\n\n"
            f"**👉 [Connect your accounts]({LEADSIE_LINK})**\n\n"
            "Sign in with Google and approve PracticeRank — that's it. The Google items "
            "below are all covered by that link; the step-by-step instructions are only "
            "there if you'd rather grant them manually.\n\n---"
        )
        full_lines.insert(0, leadsie_block)
        pending_lines.insert(0, leadsie_block)

    if not pending_lines:
        pending_lines.append("- ✓ Everything's in — no outstanding items. Thank you!")
    return "\n\n".join(full_lines), "\n\n".join(pending_lines)


def _render_email_template(content: str, customer: dict, contacts: list[dict],
                           kpis: dict | None = None, runs: list[dict] | None = None,
                           places: dict | None = None, diff_report: str = "",
                           content_recs: list[dict] | None = None,
                           competitors: list[dict] | None = None,
                           ai_run_summary: dict | None = None,
                           access: list[dict] | None = None,
                           checklist: dict | None = None) -> str:
    """Replace template variables with real customer data from DB."""
    contact_name = contacts[0]["name"] if contacts else "there"
    contact_email = contacts[0].get("email", "") if contacts else ""

    # If contact's role is 'owner' or 'doctor', check if they're a provider (Dr.)
    if contact_name and contact_name != "there" and not contact_name.startswith("Dr."):
        contact_role = contacts[0].get("role", "") if contacts else ""
        # Check if this person is in the providers table (they're a doctor)
        db = get_db()
        try:
            providers = db.get_providers(customer.get("id", ""))
            for p in providers:
                # Match by last name — "Paul Zhivago" matches provider "Paul Zhivago"
                if contact_name.lower() in p.get("name", "").lower() or p.get("name", "").lower() in contact_name.lower():
                    creds = p.get("credentials", "")
                    if any(c in creds for c in ("DDS", "DMD", "MD", "DO")):
                        contact_name = f"Dr. {contact_name}"
                    break
        finally:
            db.close()

    # Platform-specific access steps
    platform = customer.get("platform", "unknown")
    platform_steps = {
        "webflow": "**Webflow** — We need API access to manage your site's SEO\n   - **Important**: Your Workspace must be on the **Core plan** ($19/mo) or higher for API access\n     - Go to Workspace Settings > Plans to check/upgrade\n   - Generate a **Site API token**: Site Settings > Integrations > API Access > Generate API Token\n     - Enable these scopes: Sites (Read), Pages (Read+Write), Custom Code (Read+Write), CMS (Read+Write), Assets (Read+Write)\n   - Also send us the **Site ID** from Site Settings > General\n   - Optionally, add kdoherty@practicerank.ai as a site collaborator for visual editing",
        "squarespace": "**Squarespace** — Add kdoherty@practicerank.ai as a contributor\n   - Go to Settings > Permissions > Contributors > Invite contributor",
        "wordpress": "**WordPress** — Install the PracticeRank SEO plugin\n   - Download the plugin from the dashboard (customer detail page → Setup Guide)\n   - Go to Plugins > Add New Plugin > Upload Plugin, install and activate\n   - Go to Settings > PracticeRank, copy the API Key and send it to us\n   - Optionally, create an admin account for kdoherty@practicerank.ai (Users > Add New > Administrator)",
        "shopify": "**Shopify** — Create a custom app for API access\n   - Go to Settings > Apps and sales channels > Develop apps\n   - Click \"Allow custom app development\" (if not already enabled)\n   - Click \"Create an app\" — name it \"PracticeRank\"\n   - Under Configuration > Admin API integration, click Configure and enable:\n     - `read_themes` / `write_themes`\n     - `read_content` / `write_content`\n     - `read_products` / `write_products`\n     - `read_online_store_pages` / `write_online_store_pages`\n   - Click Install app, then send us the Admin API access token",
    }
    access_steps = platform_steps.get(platform, f"**{platform.title()}** — Please share login or collaborator access")

    # Dynamic onboarding checklist — only what we still need, with how-to copy.
    onboarding_full, onboarding_pending = _onboarding_blocks(customer, access, checklist, access_steps)

    # KPI data for monthly reports
    kpis = kpis or {}

    def _latest(metric: str) -> str:
        vals = kpis.get(metric, [])
        if vals:
            return str(vals[0]["value"])
        # Fall back to Google Places data if no KPI records yet
        if places:
            if metric == "review_count":
                return str(places.get("review_count", "—"))
            if metric == "rating":
                return str(places.get("rating", "—"))
        return "—"

    def _prev(metric: str) -> str:
        vals = kpis.get(metric, [])
        return str(vals[1]["value"]) if len(vals) > 1 else "—"

    def _delta(metric: str) -> str:
        vals = kpis.get(metric, [])
        if len(vals) < 2:
            return "—"
        try:
            curr, prev = float(vals[0]["value"]), float(vals[1]["value"])
        except (TypeError, ValueError):
            return "—"
        diff = curr - prev
        if diff > 0:
            return f"+{diff:g}"
        return f"{diff:g}"

    # Build changes list from most recent run
    changes_list = "- No changes recorded"
    next_month_plans = "- Continue monitoring and optimization"
    if runs:
        latest_run = runs[0]
        changes = latest_run.get("changes") or []
        if isinstance(changes, str):
            import json as _json
            try:
                changes = _json.loads(changes)
            except Exception:
                changes = [changes]
        if changes:
            changes_list = "\n".join(f"- {c}" for c in changes)
        next_month_plans = "- Monthly crawl and analysis\n- Update schema markup\n- Refresh llms.txt content\n- Track KPI improvements"

    # Build staging diff summary
    changes_summary = "No changes staged."
    diff_summary = "No diff available."
    if runs:
        latest = runs[0]
        changes = latest.get("changes") or []
        if isinstance(changes, str):
            import json as _json
            try:
                changes = _json.loads(changes)
            except Exception:
                changes = [changes]
        if changes:
            changes_summary = "\n".join(f"- {c}" for c in changes)
    if diff_report:
        diff_summary = diff_report

    # Current month for report
    from datetime import datetime
    report_month = datetime.now().strftime("%B %Y")

    # Business type for dynamic language
    business_type = customer.get("business_type", "practice")
    btype_label = {
        "practice": "practice", "legal": "firm", "medical": "practice",
        "technology": "company", "product": "brand", "service": "business",
    }.get(business_type, "business")

    # Google snapshot section (what we already know)
    google_snapshot = ""
    if places and places.get("rating"):
        google_snapshot = f"- **Google Rating**: {places['rating']} ({places.get('review_count', 0)} reviews)"
    if customer.get("address") and customer.get("city"):
        addr_line = f"- **Address**: {customer['address']}, {customer['city']}, {customer.get('state', '')}"
        google_snapshot = f"{google_snapshot}\n{addr_line}" if google_snapshot else addr_line
    if customer.get("phone"):
        phone_line = f"- **Phone**: {customer['phone']}"
        google_snapshot = f"{google_snapshot}\n{phone_line}" if google_snapshot else phone_line

    # Competitor summary
    competitor_summary = ""
    comps = competitors or []
    if comps:
        top = comps[:3]
        comp_lines = []
        for c in top:
            rating = c.get("rating", "—")
            reviews = c.get("review_count", 0)
            comp_lines.append(f"- {c.get('name', 'Unknown')}: {rating} rating ({reviews} reviews)")
        competitor_summary = "\n".join(comp_lines)

    # AI visibility baseline
    ai_baseline_summary = ""
    ai_run = ai_run_summary
    if ai_run and ai_run.get("total_queries"):
        mentions = ai_run.get("total_mentions", 0)
        total = ai_run["total_queries"]
        rate = ai_run.get("mention_rate", 0)
        pct = f"{rate * 100:.0f}%" if isinstance(rate, (int, float)) else "0%"
        ai_baseline_summary = f"Your {btype_label} was mentioned in **{mentions} out of {total}** AI search queries we tested ({pct} visibility rate)."
        if mentions == 0:
            ai_baseline_summary += f" This means AI assistants like ChatGPT, Claude, and Google AI currently do not recommend your {btype_label} when potential customers search for your services."
        elif rate and rate < 0.3:
            ai_baseline_summary += f" There's significant room to improve — top competitors typically achieve 40-60% visibility."

    # Weekly SEO report data
    report_week = datetime.now().strftime("%b %d, %Y")
    weekly_clicks = "—"
    prev_weekly_clicks = "—"
    weekly_clicks_delta = "—"
    weekly_impressions = "—"
    prev_weekly_impressions = "—"
    weekly_impressions_delta = "—"
    weekly_avg_position = "—"
    prev_weekly_avg_position = "—"
    weekly_position_delta = "—"
    weekly_ctr = "—"
    prev_weekly_ctr = "—"
    weekly_ctr_delta = "—"
    top_keywords_table = "No keyword data available yet."
    keyword_movers = "No keyword movement data available yet."
    ai_visibility_rate = "—"
    ai_visibility_change = ""
    weekly_activity_summary = "- Monitoring search performance and AI visibility"
    weekly_next_steps = "- Continue optimization and content strategy"

    # Try to pull GSC data for weekly report
    try:
        db = get_db()
        cid = customer.get("id", "")
        if cid:
            gsc_daily = db.get_gsc_daily(cid, limit=14)
            if gsc_daily:
                this_week = gsc_daily[:7]
                last_week = gsc_daily[7:14]
                tw_clicks = sum(d.get("clicks", 0) for d in this_week)
                tw_impr = sum(d.get("impressions", 0) for d in this_week)
                lw_clicks = sum(d.get("clicks", 0) for d in last_week) if last_week else 0
                lw_impr = sum(d.get("impressions", 0) for d in last_week) if last_week else 0
                weekly_clicks = str(tw_clicks)
                prev_weekly_clicks = str(lw_clicks)
                weekly_impressions = f"{tw_impr:,}"
                prev_weekly_impressions = f"{lw_impr:,}"
                if lw_clicks:
                    delta = tw_clicks - lw_clicks
                    weekly_clicks_delta = f"+{delta}" if delta > 0 else str(delta)
                if lw_impr:
                    delta = tw_impr - lw_impr
                    weekly_impressions_delta = f"+{delta:,}" if delta > 0 else f"{delta:,}"
                tw_ctr = (tw_clicks / tw_impr * 100) if tw_impr else 0
                lw_ctr = (lw_clicks / lw_impr * 100) if lw_impr else 0
                weekly_ctr = f"{tw_ctr:.1f}%"
                prev_weekly_ctr = f"{lw_ctr:.1f}%"
                if lw_ctr:
                    delta = tw_ctr - lw_ctr
                    weekly_ctr_delta = f"+{delta:.1f}%" if delta > 0 else f"{delta:.1f}%"
                tw_pos = sum(d.get("position", 0) for d in this_week) / len(this_week) if this_week else 0
                lw_pos = sum(d.get("position", 0) for d in last_week) / len(last_week) if last_week else 0
                weekly_avg_position = f"{tw_pos:.1f}"
                prev_weekly_avg_position = f"{lw_pos:.1f}" if last_week else "—"
                if lw_pos:
                    delta = lw_pos - tw_pos  # lower is better
                    weekly_position_delta = f"+{delta:.1f} (improved)" if delta > 0 else f"{delta:.1f}"

            # Top keywords
            kw_summary = db.get_keyword_summary(cid)
            if kw_summary:
                top_kws = sorted(kw_summary, key=lambda k: k.get("clicks", 0), reverse=True)[:10]
                kw_lines = ["| Keyword | Position | Clicks | Impressions |", "|---------|----------|--------|-------------|"]
                for kw in top_kws:
                    kw_lines.append(f"| {kw.get('keyword', '')} | {kw.get('position', '—'):.1f} | {kw.get('clicks', 0)} | {kw.get('impressions', 0):,} |")
                top_keywords_table = "\n".join(kw_lines)
    except Exception:
        pass

    # Monthly GSC data (for monthly report template)
    monthly_clicks = "—"
    prev_monthly_clicks = "—"
    monthly_clicks_delta = "—"
    monthly_impressions = "—"
    prev_monthly_impressions = "—"
    monthly_impressions_delta = "—"
    monthly_avg_position = "—"
    prev_monthly_avg_position = "—"
    monthly_position_delta = "—"
    try:
        db2 = get_db()
        cid2 = customer.get("id", "")
        if cid2:
            gsc_monthly = db2.get_gsc_daily(cid2, limit=60)
            if gsc_monthly:
                this_month = gsc_monthly[:30]
                last_month = gsc_monthly[30:60]
                tm_clicks = sum(d.get("clicks", 0) for d in this_month)
                tm_impr = sum(d.get("impressions", 0) for d in this_month)
                lm_clicks = sum(d.get("clicks", 0) for d in last_month) if last_month else 0
                lm_impr = sum(d.get("impressions", 0) for d in last_month) if last_month else 0
                monthly_clicks = f"{tm_clicks:,}"
                prev_monthly_clicks = f"{lm_clicks:,}"
                monthly_impressions = f"{tm_impr:,}"
                prev_monthly_impressions = f"{lm_impr:,}"
                if lm_clicks:
                    delta = tm_clicks - lm_clicks
                    monthly_clicks_delta = f"+{delta:,}" if delta > 0 else f"{delta:,}"
                if lm_impr:
                    delta = tm_impr - lm_impr
                    monthly_impressions_delta = f"+{delta:,}" if delta > 0 else f"{delta:,}"
                tm_pos = sum(d.get("position", 0) for d in this_month) / len(this_month) if this_month else 0
                lm_pos = sum(d.get("position", 0) for d in last_month) / len(last_month) if last_month else 0
                monthly_avg_position = f"{tm_pos:.1f}"
                prev_monthly_avg_position = f"{lm_pos:.1f}" if last_month else "—"
                if lm_pos:
                    delta = lm_pos - tm_pos  # lower is better
                    monthly_position_delta = f"+{delta:.1f} (improved)" if delta > 0 else f"{delta:.1f}"
        db2.close()
    except Exception:
        pass

    # PracticeRank score for email templates
    practicerank_score_str = "—"
    practicerank_grade_str = ""
    practicerank_delta_str = ""
    quick_wins_summary_str = ""
    try:
        cid_pr = customer.get("id", "")
        if cid_pr:
            db_pr = get_db()
            try:
                from geo_agent.practicerank_score import compute_practicerank_score
                from geo_agent.quick_wins import detect_quick_wins, format_for_email
                result_pr = compute_practicerank_score(db_pr, cid_pr)
                if result_pr.get("score") is not None:
                    practicerank_score_str = str(result_pr["score"])
                    grade_info = result_pr.get("grade", {})
                    practicerank_grade_str = grade_info.get("letter", "?")
                    # Check previous score
                    prev_scores = db_pr.get_practicerank_scores(cid_pr, limit=2)
                    if len(prev_scores) >= 2:
                        delta_val = result_pr["score"] - prev_scores[1]["overall_score"]
                        if delta_val > 0:
                            practicerank_delta_str = f" — up {delta_val} pts from last week"
                        elif delta_val < 0:
                            practicerank_delta_str = f" — down {abs(delta_val)} pts from last week"
                wins = detect_quick_wins(db_pr, cid_pr)
                quick_wins_summary_str = format_for_email(wins, max_items=3)
            finally:
                db_pr.close()
    except Exception:
        pass

    # Plan name from the customer's Stripe subscription (for the welcome email).
    plan_name = "PracticeRank"
    try:
        _bdb = get_db()
        _sub = _bdb.get_subscription_for_customer(customer.get("id", ""))
        _bdb.close()
        if _sub and _sub.get("plan_name"):
            plan_name = _sub["plan_name"]
    except Exception:  # noqa: BLE001 — never let billing lookup break email rendering
        pass

    replacements = {
        "{practice_name}": customer.get("name", ""),
        "{contact_name}": contact_name,
        "{contact_email}": contact_email,
        "{plan_name}": plan_name,
        "{platform}": platform.title(),
        "{platform_access_steps}": access_steps,
        # Dynamic onboarding checklist (only outstanding items + how to grant)
        "{access_checklist}": onboarding_full,
        "{pending_access_list}": onboarding_pending,
        "{city}": customer.get("city", ""),
        "{state}": customer.get("state", ""),
        "{domain}": customer.get("domain", ""),
        "{phone}": customer.get("phone", ""),
        "{address}": customer.get("address", ""),
        # KPI placeholders
        "{review_count}": _latest("review_count"),
        "{prev_review_count}": _prev("review_count"),
        "{review_delta}": _delta("review_count"),
        "{rating}": _latest("rating"),
        "{prev_rating}": _prev("rating"),
        "{rating_delta}": _delta("rating"),
        "{ai_mentions}": _latest("ai_mentions"),
        "{prev_ai_mentions}": _prev("ai_mentions"),
        "{ai_mentions_delta}": _delta("ai_mentions"),
        "{llms_hits}": _latest("llms_txt_hits"),
        "{prev_llms_hits}": _prev("llms_txt_hits"),
        "{llms_hits_delta}": _delta("llms_txt_hits"),
        # Hosting/DNS info
        "{dns_registrar}": (customer.get("hosting_info") or {}).get("registrar", "your domain registrar (GoDaddy, Namecheap, etc.)"),
        "{dns_nameservers}": ", ".join((customer.get("hosting_info") or {}).get("nameservers", [])) or "unknown",
        "{hosting_provider}": (customer.get("hosting_info") or {}).get("hosting", "unknown"),
        "{cdn_provider}": (customer.get("hosting_info") or {}).get("cdn", "none"),
        "{cms_platform}": (customer.get("hosting_info") or {}).get("cms", platform.title()),
        "{domain_expiry}": (customer.get("hosting_info") or {}).get("domain_expiry", "unknown"),
        # Monthly report
        "{report_month}": report_month,
        "{monthly_clicks}": monthly_clicks,
        "{prev_monthly_clicks}": prev_monthly_clicks,
        "{monthly_clicks_delta}": monthly_clicks_delta,
        "{monthly_impressions}": monthly_impressions,
        "{prev_monthly_impressions}": prev_monthly_impressions,
        "{monthly_impressions_delta}": monthly_impressions_delta,
        "{monthly_avg_position}": monthly_avg_position,
        "{prev_monthly_avg_position}": prev_monthly_avg_position,
        "{monthly_position_delta}": monthly_position_delta,
        # Report content
        "{changes_list}": changes_list,
        "{next_month_plans}": next_month_plans,
        "{changes_summary}": changes_summary,
        "{diff_summary}": diff_summary,
        "{content_rec_summary}": _content_rec_summary(content_recs or []),
        "{content_rec_count}": str(len(content_recs or [])),
        # Weekly report
        "{report_week}": report_week,
        "{weekly_clicks}": weekly_clicks,
        "{prev_weekly_clicks}": prev_weekly_clicks,
        "{weekly_clicks_delta}": weekly_clicks_delta,
        "{weekly_impressions}": weekly_impressions,
        "{prev_weekly_impressions}": prev_weekly_impressions,
        "{weekly_impressions_delta}": weekly_impressions_delta,
        "{weekly_avg_position}": weekly_avg_position,
        "{prev_weekly_avg_position}": prev_weekly_avg_position,
        "{weekly_position_delta}": weekly_position_delta,
        "{weekly_ctr}": weekly_ctr,
        "{prev_weekly_ctr}": prev_weekly_ctr,
        "{weekly_ctr_delta}": weekly_ctr_delta,
        "{top_keywords_table}": top_keywords_table,
        "{keyword_movers}": keyword_movers,
        "{ai_visibility_rate}": ai_visibility_rate,
        "{ai_visibility_change}": ai_visibility_change,
        "{weekly_activity_summary}": weekly_activity_summary,
        "{weekly_next_steps}": weekly_next_steps,
        # Auto-discovered data
        "{business_type}": btype_label,
        "{google_snapshot}": google_snapshot or "- No Google Business Profile data found yet",
        "{competitor_summary}": competitor_summary or "- Competitor data not yet available",
        "{ai_baseline_summary}": ai_baseline_summary or "We'll run an AI visibility baseline scan once onboarding is complete.",
        # PracticeRank score
        "{practicerank_score}": practicerank_score_str,
        "{practicerank_grade}": practicerank_grade_str,
        "{practicerank_delta}": practicerank_delta_str,
        "{quick_wins_summary}": quick_wins_summary_str,
        # Pricing quote — recommend Grow for clients on platforms we'd migrate off,
        # Optimize for those already on a fast/modern stack (e.g. Webflow). ($500
        # Starter retired 2026-06-19 — see specs/pricing/good-better-best-pricing.html.)
        "{recommended_tier}": "Grow" if platform.lower() in ("wordpress", "squarespace", "wix", "shopify") else "Optimize",
        # Industry-aware labels
        "{industry_schema_types}": {
            "practice": "FAQ, HowTo, MedicalProcedure, Dentist, LocalBusiness",
            "medical": "FAQ, HowTo, MedicalProcedure, Physician, MedicalClinic",
            "legal": "FAQ, HowTo, LegalService, Attorney, LocalBusiness",
            "technology": "FAQ, HowTo, SoftwareApplication, Organization",
            "product": "FAQ, HowTo, Product, Organization",
            "service": "FAQ, HowTo, Service, LocalBusiness",
        }.get(business_type, "FAQ, HowTo, Service, LocalBusiness"),
        "{industry_conversion_flow}": {
            "practice": "Conversion-optimized patient journey (booking flow, contact forms, service pages)",
            "medical": "Conversion-optimized patient journey (appointment scheduling, intake forms, provider pages)",
            "legal": "Conversion-optimized client journey (consultation booking, case evaluation forms, practice area pages)",
            "technology": "Conversion-optimized user journey (demo requests, pricing pages, feature showcases)",
            "product": "Conversion-optimized buyer journey (product pages, comparison tools, purchase flow)",
            "service": "Conversion-optimized client journey (booking flow, contact forms, service pages)",
        }.get(business_type, "Conversion-optimized client journey (booking flow, contact forms, service pages)"),
        "{industry_best_for_starter}": {
            "practice": "Practices happy with their current website design who want better search visibility and AI discoverability",
            "medical": "Medical practices happy with their current website who want better search visibility and AI discoverability",
            "legal": "Law firms happy with their current website who want better search visibility and AI discoverability",
            "technology": "Companies happy with their current website who want better search visibility and AI discoverability",
            "product": "Brands happy with their current website who want better search visibility and AI discoverability",
            "service": "Businesses happy with their current website who want better search visibility and AI discoverability",
        }.get(business_type, "Businesses happy with their current website who want better search visibility and AI discoverability"),
        "{industry_best_for_growth}": {
            "practice": "Practices on WordPress or outdated platforms who want a faster, more secure site with aggressive SEO growth",
            "medical": "Medical practices on WordPress or outdated platforms who want a faster, more secure site with aggressive SEO growth",
            "legal": "Law firms on WordPress or outdated platforms who want a faster, more secure site with aggressive SEO growth",
            "technology": "Companies on WordPress or outdated platforms who want a faster, more secure site with aggressive SEO growth",
            "product": "Brands on WordPress or outdated platforms who want a faster, more secure site with aggressive SEO growth",
            "service": "Businesses on WordPress or outdated platforms who want a faster, more secure site with aggressive SEO growth",
        }.get(business_type, "Businesses on WordPress or outdated platforms who want a faster, more secure site with aggressive SEO growth"),
        "{industry_best_for_premium}": {
            "practice": "Practices ready for a ground-up website redesign and best-in-class online presence",
            "medical": "Medical practices ready for a ground-up website redesign and best-in-class online presence",
            "legal": "Law firms ready for a ground-up website redesign and best-in-class online presence",
            "technology": "Companies ready for a ground-up website redesign and best-in-class online presence",
            "product": "Brands ready for a ground-up website redesign and best-in-class online presence",
            "service": "Businesses ready for a ground-up website redesign and best-in-class online presence",
        }.get(business_type, "Businesses ready for a ground-up website redesign and best-in-class online presence"),
    }
    for k, v in replacements.items():
        content = content.replace(k, v)
    return content


def _get_va_todos(customer: dict, access: list[dict], contacts: list[dict],
                  places: dict | None, runs: list[dict], staged: bool, approved: bool,
                  checklist: dict[str, bool] | None = None) -> list[dict]:
    """Generate a VA todo list based on customer state.

    Items with auto=True are auto-detected from data and can't be toggled.
    Items with auto=False can be manually checked off by the VA.
    Each item has a unique 'key' for the checklist toggle API.
    """
    todos = []
    cl = checklist or {}
    status = customer.get("status", "onboarding")

    def add(key: str, task: str, auto_done: bool | None = None, phase: str = "onboarding"):
        """Add a todo. If auto_done is set, use that; otherwise use checklist."""
        if auto_done is not None:
            done = auto_done
            auto = True
        else:
            done = cl.get(key, False)
            auto = False
        todos.append({"key": key, "task": task, "done": done, "auto": auto, "phase": phase})

    # Onboarding todos
    if status in ("onboarding", "active"):
        has_contact = bool(contacts)
        add("contact_added", "Add primary contact info", auto_done=has_contact)
        add("onboard_email_sent", "Send onboarding email (access request)")

        for a in access:
            is_done = a["status"] in ("granted", "not_needed")
            add(f"access_{a['platform']}", f"Get {a['platform'].upper()} access", auto_done=is_done, phase="access")

        add("places_verified", "Verify Google Places data", auto_done=places is not None)
        # Client-supplied info/assets the onboarding email asks for. Checking these
        # off drops them from the dynamic access-request / follow-up emails.
        add("nap_confirmed", "Client confirmed exact NAP (name / address / phone / hours)", phase="access")
        add("brand_assets_received", "Received logo + 10 photos from client", phase="access")
        add("services_confirmed", "Client confirmed services & service-area cities", phase="access")
        add("lead_tracking_installed", "Install lead-tracking snippet on the site (phone/form/CTA → GA4)", phase="access")
        add("gsc_setup", "Add your Google account as Full user in customer's Search Console, then save property URL in Integrations tab")
        add("followup_sent", "Send access follow-up email (if needed)")
        add("first_audit", "Run first site audit", auto_done=bool(runs))
        add("onboard_complete_email", "Send onboarding complete email")

    # Active todos (recurring monthly)
    if status == "active":
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        add(f"monthly_run_{month}", "Monthly agent run completed",
            auto_done=bool(runs and runs[0].get("run_date", "")[:7] == month), phase="monthly")
        if staged and not approved:
            add(f"get_approval_{month}", "Get client approval for staged changes", phase="monthly")
        elif staged and approved:
            add(f"publish_{month}", "Publish approved changes", phase="monthly")
        add(f"monthly_report_{month}", "Send monthly report email", phase="monthly")
        add(f"ai_check_{month}", "Check AI search mentions", phase="monthly")

    # Paused
    if status == "paused":
        add("followup_resume", "Follow up with client about resuming", phase="followup")

    return todos


# --- SEO/GEO Optimization Tasks ---

# Industry verticals — each business_type maps to one. Drives which schema/content
# tasks a customer sees. Unknown/blank types fall back to 'default'. See
# specs/active/checklist-overhaul.html.
BUSINESS_TYPE_VERTICAL = {
    "practice": "practice", "medical": "practice", "dental": "practice",
    "legal": "legal",
    "precious_metals_buyer": "local_retail", "retail": "local_retail",
    "shop": "local_retail", "jeweler": "local_retail",
    "ecommerce": "ecommerce", "product": "ecommerce",
    "consulting": "professional_services", "advisory": "professional_services",
    "agency": "professional_services", "finance": "professional_services",
    "technology": "saas", "saas": "saas", "software": "saas",
}
# Verticals that are local, foot-traffic / location-based businesses (get GBP,
# maps, citations, review-funnel tasks).
LOCAL_VERTICALS = {"practice", "legal", "local_retail", "professional_services", "default"}


def vertical_for(business_type: str) -> str:
    return BUSINESS_TYPE_VERTICAL.get((business_type or "").lower(), "default")


SEO_GEO_TASKS = [
    # Schema Markup
    {"key": "seo_schema_localbusiness", "task": "LocalBusiness (Dentist) schema markup", "category": "Schema Markup",
     "verticals": ["practice", "local_retail", "default"],
     "labels": {"local_retail": "LocalBusiness / Store schema markup", "default": "LocalBusiness schema markup"},
     "guide": {
         "webflow": (
             "<b>How to add schema markup in Webflow:</b>"
             "<ol>"
             "<li>Go to <b>Site Settings → Custom Code</b></li>"
             "<li>In the <b>Head Code</b> box, PracticeRank will auto-inject the JSON-LD schema via the GEO Agent — no manual action needed</li>"
             "<li>To verify: visit <code>https://{domain}</code>, right-click → View Page Source, search for <code>LocalBusiness</code></li>"
             "<li>Test at <a href='https://search.google.com/test/rich-results' target='_blank'>Google Rich Results Test</a> — paste the URL and confirm no errors</li>"
             "</ol>"
             "<b>If not auto-injected:</b> Ask Jon to run the GEO Agent for this customer."
         ),
         "squarespace": (
             "<b>How to add schema markup in Squarespace:</b>"
             "<ol>"
             "<li>Log in to Squarespace → go to <b>Website → Developer Tools → Code Injection</b></li>"
             "<li>In the <b>Header</b> box, paste the JSON-LD schema script (use the <b>Copy Schema</b> button in the GEO Files panel on the Overview tab)</li>"
             "<li>Click <b>Save</b></li>"
             "<li>To verify: visit <code>https://{domain}</code>, right-click → View Page Source, search for <code>LocalBusiness</code></li>"
             "<li>Test at <a href='https://search.google.com/test/rich-results' target='_blank'>Google Rich Results Test</a></li>"
             "</ol>"
             "<div style='margin-top:0.5rem;padding:0.4rem;background:#fefce8;border-radius:4px;color:#854d0e;font-size:0.78rem'>"
             "<b>⚠️ Code Injection requires Business plan or higher.</b> If it's not visible under Developer Tools, "
             "the site needs a plan upgrade. Workaround: add a Code Block on each page (editor → + → Code → paste → uncheck \"Display Source\")."
             "</div>"
         ),
     }},
    {"key": "seo_schema_org", "task": "Organization schema markup", "category": "Schema Markup",
     "verticals": ["ecommerce", "professional_services", "saas", "default"],
     "labels": {"saas": "Organization + SoftwareApplication schema markup"},
     "guide": {
         "webflow": (
             "<b>Same process as LocalBusiness schema</b> — the GEO Agent auto-injects Organization schema for non-practice customers."
             " Verify by viewing page source and searching for <code>Organization</code>."
         ),
         "squarespace": (
             "<b>Same process as LocalBusiness schema</b> — paste the Organization JSON-LD into"
             " <b>Website → Developer Tools → Code Injection → Header</b>."
         ),
         "shopify": (
             "<b>How to add schema in Shopify:</b>"
             "<ol>"
             "<li>Go to <b>Online Store → Themes → Edit Code</b></li>"
             "<li>Open <code>theme.liquid</code></li>"
             "<li>Paste the JSON-LD script just before <code>&lt;/head&gt;</code></li>"
             "<li>Or use the <b>Admin API</b> with the token to inject via ScriptTag API</li>"
             "</ol>"
             "<b>To verify:</b> View page source and search for <code>Organization</code>."
         ),
     }},
    {"key": "seo_schema_faq", "task": "FAQPage schema on key pages", "category": "Schema Markup"},
    {"key": "seo_schema_medical", "task": "MedicalProcedure schema for each service", "category": "Schema Markup", "verticals": ["practice"]},
    {"key": "seo_schema_review", "task": "AggregateRating / Review schema", "category": "Schema Markup",
     "verticals": ["practice", "legal", "local_retail", "ecommerce"]},
    {"key": "seo_schema_product", "task": "Product / Offer schema for offerings", "category": "Schema Markup",
     "verticals": ["ecommerce", "saas"]},
    {"key": "seo_schema_legalservice", "task": "LegalService / Attorney schema markup", "category": "Schema Markup",
     "verticals": ["legal"]},
    {"key": "seo_schema_software", "task": "SoftwareApplication schema markup", "category": "Schema Markup",
     "verticals": ["saas"]},
    {"key": "seo_schema_person", "task": "Person schema (providers / attorneys / experts)", "category": "Schema Markup",
     "verticals": ["practice", "legal", "professional_services"]},
    {"key": "seo_schema_service", "task": "Service schema for each offering", "category": "Schema Markup",
     "verticals": ["legal", "local_retail", "professional_services"]},
    # llms.txt & AI Readiness
    {"key": "seo_llms_txt", "task": "Deploy llms.txt on domain", "category": "AI Readiness (GEO)",
     "guide": {
         "shopify": (
             "<b>What is llms.txt?</b> A file that tells AI search engines (ChatGPT, Claude, Perplexity) about the business."
             " It lives at <code>https://{domain}/llms.txt</code>."
             "<br><br>"
             "<b>For Shopify sites:</b> The file can be served directly through Shopify — no Cloudflare needed."
             "<ol>"
             "<li>In Shopify Admin, go to <b>Online Store → Pages</b></li>"
             "<li>Create a new page with the llms.txt content (or upload via the Admin API using the token)</li>"
             "<li>Set the URL handle to <code>llms.txt</code></li>"
             "</ol>"
             "<b>Alternatively:</b> Upload via Shopify Admin API (Content → Files) if the client provided an API token."
             "<br><br>"
             "<b>To verify:</b> Open <code>https://{domain}/llms.txt</code> in your browser."
         ),
         "_default": (
             "<b>What is llms.txt?</b> A file that tells AI search engines (ChatGPT, Claude, Perplexity) about the business."
             " It lives at <code>https://{domain}/llms.txt</code>."
             "<br><br>"
             "<b>How it gets deployed:</b>"
             "<ol>"
             "<li>The GEO Agent generates the llms.txt content automatically ✅</li>"
             "<li>The file is uploaded to our Cloudflare Worker ✅</li>"
             "<li><b>⚠️ A redirect on the website must send <code>/llms.txt</code> to the Worker</b> — see the <b>\"Set up redirects\"</b> task below</li>"
             "</ol>"
             "<b>This task is NOT complete until the redirect is configured.</b>"
             " The file is generated and on the Worker, but visitors to <code>https://{domain}/llms.txt</code> won't see it without the redirect."
             "<br><br>"
             "<b>To verify after redirect:</b> Open <code>https://{domain}/llms.txt</code> in your browser — you should see a text file with practice info."
         ),
     }},
    {"key": "seo_llms_full", "task": "Deploy llms-full.txt with detailed content", "category": "AI Readiness (GEO)",
     "guide": {
         "_default": (
             "<b>Same as llms.txt</b> but with more detail. Verify at <code>https://{domain}/llms-full.txt</code>."
             " This is auto-generated by the GEO Agent."
         ),
     }},
    {"key": "seo_robots_txt", "task": "robots.txt allows AI crawlers (GPTBot, ClaudeBot, etc.)", "category": "AI Readiness (GEO)",
     "guide": {
         "_default": (
             "<b>What this does:</b> The robots.txt file tells search bots whether they're allowed to crawl the site."
             " We need AI bots (GPTBot, ClaudeBot, PerplexityBot) to be <b>allowed</b>."
             "<br><br>"
             "<b>To verify:</b> Open <code>https://{domain}/robots.txt</code> — look for lines like:"
             "<pre>User-agent: GPTBot\nAllow: /\n\nUser-agent: ClaudeBot\nAllow: /</pre>"
             "If AI bots are blocked (Disallow: /), the redirect needs to be configured to point to our Worker."
         ),
     }},
    {"key": "seo_cloudflare_worker", "task": "Cloudflare Worker serving llms.txt + robots.txt", "category": "AI Readiness (GEO)", "skip_platforms": ["shopify"],
     "guide": {
         "_default": (
             "<b>What this is:</b> A Cloudflare Worker is a small program that serves our generated files (llms.txt, llms-full.txt, robots.txt)."
             " It's already deployed — Jon manages this."
             "<br><br>"
             "<b>To verify it's working:</b> Open this URL in your browser:"
             "<br><code>https://practicerank-api.practice-rank-ai-seo.workers.dev/geo/{domain}/llms.txt</code>"
             "<br>You should see the llms.txt content."
             "<br><br>"
             "<b>If it returns an error or empty:</b> Ask Jon to run the GEO Agent to upload files for this customer."
         ),
     }},
    {"key": "seo_robots_redirected", "task": "Set up redirects: /llms.txt, /llms-full.txt → Worker", "category": "AI Readiness (GEO)", "skip_platforms": ["shopify"],
     "guide": {
         "webflow": (
             "<b>Set up Webflow 301 redirects to point /robots.txt and /llms.txt to the Worker:</b>"
             "<ol>"
             "<li>Log in to <b>Webflow</b> → open the site</li>"
             "<li>Go to <b>Site Settings</b> (gear icon) → <b>Publishing</b> tab → scroll to <b>301 Redirects</b></li>"
             "<li>Add these three redirects:"
             "<table style='margin:0.5rem 0;font-size:0.8rem;border-collapse:collapse;width:100%'>"
             "<tr style='border-bottom:1px solid #ddd'><th style='text-align:left;padding:4px'>Old Path</th><th style='text-align:left;padding:4px'>Redirect To</th></tr>"
             "<tr style='border-bottom:1px solid #ddd'><td style='padding:4px'><code>/robots.txt</code></td>"
             "<td style='padding:4px'><code>https://practicerank-api.practice-rank-ai-seo.workers.dev/geo/{domain}/robots.txt</code></td></tr>"
             "<tr style='border-bottom:1px solid #ddd'><td style='padding:4px'><code>/llms.txt</code></td>"
             "<td style='padding:4px'><code>https://practicerank-api.practice-rank-ai-seo.workers.dev/geo/{domain}/llms.txt</code></td></tr>"
             "<tr><td style='padding:4px'><code>/llms-full.txt</code></td>"
             "<td style='padding:4px'><code>https://practicerank-api.practice-rank-ai-seo.workers.dev/geo/{domain}/llms-full.txt</code></td></tr>"
             "</table></li>"
             "<li>Click <b>Add redirect</b> for each one, then <b>Publish</b> the site</li>"
             "</ol>"
             "<b>To verify:</b> Open <code>https://{domain}/robots.txt</code> — it should show our custom robots.txt (not the Webflow default)."
         ),
         "squarespace": (
             "<b>🔧 Set up Squarespace redirects so /llms.txt, /robots.txt, and /llms-full.txt point to our Worker:</b>"
             "<br><br>"
             "<b>Step 1:</b> Log in to Squarespace at <a href='https://www.squarespace.com/login' target='_blank'>squarespace.com/login</a>"
             "<br><br>"
             "<b>Step 2:</b> Select the <b>{domain}</b> site"
             "<br><br>"
             "<b>Step 3:</b> In the left sidebar, click <b>Website</b> → then <b>Developer Tools</b>"
             "<br><br>"
             "<b>Step 4:</b> Click <b>URL Mappings</b>"
             "<br><span style='color:#6b7280;font-size:0.75rem'>(If you don't see Developer Tools, try: Settings → Advanced → URL Mappings on older Squarespace versions)</span>"
             "<br><br>"
             "<b>Step 5:</b> In the text box, paste these 2 lines <b>exactly</b> (copy the entire block):"
             "<pre style='margin:0.5rem 0;padding:0.75rem;background:#1e1e1e;color:#d4d4d4;border-radius:6px;font-size:0.78rem;overflow-x:auto;cursor:pointer;user-select:all'>"
             "/llms.txt -> https://practicerank-api.practice-rank-ai-seo.workers.dev/geo/{domain}/llms.txt 301\n"
             "/llms-full.txt -> https://practicerank-api.practice-rank-ai-seo.workers.dev/geo/{domain}/llms-full.txt 301"
             "</pre>"
             "<span style='color:#6b7280;font-size:0.75rem'>Note: Squarespace serves its own /robots.txt — it can't be redirected via URL Mappings.</span>"
             "<b>Step 6:</b> Click <b>Save</b> at the top of the page"
             "<br><br>"
             "<hr style='margin:0.75rem 0;border:0;border-top:1px solid #ddd'>"
             "<b>✅ How to verify it worked:</b>"
             "<ol style='margin-top:0.5rem'>"
             "<li>Open <a href='https://{domain}/llms.txt' target='_blank'>https://{domain}/llms.txt</a> — you should see a text file starting with the practice name</li>"
             "<li>Open <a href='https://{domain}/llms-full.txt' target='_blank'>https://{domain}/llms-full.txt</a> — longer version of the same file</li>"
             "</ol>"
             "<b>If any link shows a Squarespace 404 page</b>, double-check the URL Mappings for typos. The format must be exactly: <code>/path -> https://url 301</code> with spaces around the arrow."
             "<br><br>"
             "<b>⏱ Note:</b> Redirects take effect immediately after saving — no need to wait."
         ),
         "wordpress": (
             "<b>For WordPress, add redirect rules in .htaccess or a redirect plugin:</b>"
             "<ol>"
             "<li>Install the <b>Redirection</b> plugin (or edit .htaccess directly)</li>"
             "<li>Add redirects:"
             "<br><code>/robots.txt</code> → <code>https://practicerank-api.practice-rank-ai-seo.workers.dev/geo/{domain}/robots.txt</code>"
             "<br><code>/llms.txt</code> → <code>https://practicerank-api.practice-rank-ai-seo.workers.dev/geo/{domain}/llms.txt</code>"
             "<br><code>/llms-full.txt</code> → <code>https://practicerank-api.practice-rank-ai-seo.workers.dev/geo/{domain}/llms-full.txt</code>"
             "</li>"
             "<li>Set type to <b>301 (Permanent)</b></li>"
             "</ol>"
         ),
     }},
    {"key": "seo_ai_monitoring", "task": "AI mention monitoring set up (ChatGPT/Claude/Gemini/Grok/Perplexity)", "category": "AI Readiness (GEO)",
     "guide": {
         "_default": (
             "<b>Run an automated AI mention check</b> — queries up to 5 AI engines and checks if the practice appears in responses."
             "<br><br>"
             "<button class='btn btn-primary btn-sm' onclick='runAiMentionCheck(\"{customer_id}\")' id='ai-check-btn'>"
             "Run AI Mention Check</button>"
             "<span id='ai-check-status' style='margin-left:8px;'></span>"
             "<div id='ai-check-results' style='margin-top:12px;display:none;'></div>"
             "<br>"
             "<b>API keys configured:</b> Set these env vars on the server to enable each engine:"
             "<ul style='font-size:0.9em;margin:4px 0;'>"
             "<li><code>ANTHROPIC_API_KEY</code> — Claude (already set)</li>"
             "<li><code>OPENAI_API_KEY</code> — ChatGPT ($5 minimum)</li>"
             "<li><code>PERPLEXITY_API_KEY</code> — Perplexity Sonar ($5/mo, live web search)</li>"
             "<li><code>GEMINI_API_KEY</code> — Google Gemini (free tier, 15 RPM)</li>"
             "<li><code>XAI_API_KEY</code> — Grok ($5 free credits)</li>"
             "</ul>"
             "<b>Manual check:</b>"
             "<ol>"
             "<li>Open <a href='https://chatgpt.com' target='_blank'>ChatGPT</a> and ask: <i>\"Who is the best dentist in {city}?\"</i></li>"
             "<li>Open <a href='https://claude.ai' target='_blank'>Claude</a> and ask the same</li>"
             "<li>Open <a href='https://gemini.google.com' target='_blank'>Gemini</a>, <a href='https://grok.x.ai' target='_blank'>Grok</a>, <a href='https://perplexity.ai' target='_blank'>Perplexity</a></li>"
             "</ol>"
             "Once the check runs, this task will be marked complete automatically."
         ),
     }},
    # Content Optimization
    {"key": "seo_expert_quotes", "task": "Expert quotes on key pages", "category": "Content Optimization",
     "guide": {
         "_default": (
             "<b>What:</b> Each service page needs 2-3 expert quotes from the practice's dentists."
             "<br><br>"
             "<b>Steps:</b>"
             "<ol>"
             "<li>Go to the <b>Content</b> tab in this dashboard</li>"
             "<li>Click <b>Generate Recommendations</b> — the AI will create expert quotes</li>"
             "<li>Review and <b>Approve</b> the expert_quote recommendations</li>"
             "<li>Download the DOCX or publish directly to the site</li>"
             "</ol>"
             "<b>Why:</b> AI search engines strongly favor pages with credentialed expert quotes."
         ),
     }},
    {"key": "seo_stats_embedded", "task": "Statistics with sources embedded in content", "category": "Content Optimization",
     "guide": {
         "_default": (
             "<b>What:</b> Real statistics and data points should be sprinkled throughout service pages."
             "<br><b>Example:</b> <i>\"Dental implants have a 98% success rate (American Dental Association, 2024)\"</i>"
             "<br><br>"
             "<b>Steps:</b>"
             "<ol>"
             "<li>The AI generates <b>stat_injection</b> recommendations in the Content tab</li>"
             "<li>Approve the ones that look accurate</li>"
             "<li>Download the DOCX to see exactly where each stat goes on the page</li>"
             "</ol>"
             "<b>Important:</b> Only use stats from real, verifiable sources. Never make up numbers."
         ),
     }},
    {"key": "seo_faq_sections", "task": "4-6 FAQ entries per service page", "category": "Content Optimization",
     "guide": {
         "_default": (
             "<b>What:</b> Each service page needs a FAQ section with 4-6 questions."
             "<br><br>"
             "<b>Steps:</b>"
             "<ol>"
             "<li>The AI generates <b>faq_update</b> recommendations in the Content tab</li>"
             "<li>Review and approve</li>"
             "<li>Publish to the site or download DOCX for manual insertion</li>"
             "</ol>"
             "<b>Bonus:</b> FAQs also get FAQPage schema markup, which can show as rich results in Google."
         ),
     }},
    {"key": "seo_content_depth", "task": "Service pages 2,000+ words with structured headings", "category": "Content Optimization"},
    {"key": "seo_provider_bios", "task": "Provider bios with credentials, specialties, years", "category": "Content Optimization", "practice_only": True,
     "guide": {
         "_default": (
             "<b>What:</b> Each dentist/provider needs a detailed bio page with:"
             "<ul>"
             "<li>Full name and credentials (DDS, DMD, etc.)</li>"
             "<li>Specialties (implants, cosmetic, pediatric, etc.)</li>"
             "<li>Years of experience</li>"
             "<li>Education and training</li>"
             "<li>Professional headshot</li>"
             "</ul>"
             "<b>Why:</b> Google and AI search engines use provider info to establish E-E-A-T (expertise, experience, authority, trust)."
             "<br><b>Get the info:</b> Check the Providers section at the top of this customer page."
         ),
     }},
    {"key": "seo_emergency_page", "task": "Emergency dentist page", "category": "Content Optimization", "practice_only": True},
    {"key": "seo_cost_page", "task": "Dental implant / procedure cost page", "category": "Content Optimization", "practice_only": True},
    {"key": "seo_insurance_page", "task": "Insurance / financing page", "category": "Content Optimization", "practice_only": True},
    {"key": "seo_neighborhood_pages", "task": "Neighborhood landing pages", "category": "Content Optimization", "practice_only": True,
     "guide": {
         "_default": (
             "<b>What:</b> Create a landing page for each neighborhood/area the practice serves."
             "<br><b>Example:</b> \"Dentist in North Austin\" or \"Family Dentist near Laramie Downtown\""
             "<br><br>"
             "<b>Steps:</b>"
             "<ol>"
             "<li>The AI generates <b>new_page</b> recommendations for neighborhood pages</li>"
             "<li>Review, approve, and publish</li>"
             "<li>Each page should mention the neighborhood name, nearby landmarks, and driving directions</li>"
             "</ol>"
         ),
     }},
    {"key": "seo_use_cases", "task": "Use case / case study pages", "category": "Content Optimization", "verticals": ["saas", "ecommerce"]},
    {"key": "seo_comparison_pages", "task": "Competitor comparison / alternatives pages", "category": "Content Optimization", "verticals": ["saas", "ecommerce"]},
    {"key": "seo_blog_cadence", "task": "Blog posts targeting key questions", "category": "Content Optimization"},
    {"key": "seo_fresh_content", "task": "Content refreshed in the last 90 days", "category": "Content Optimization"},
    {"key": "seo_attorney_bios", "task": "Attorney bios with bar admissions & practice areas", "category": "Content Optimization", "verticals": ["legal"]},
    {"key": "seo_practice_area_pages", "task": "Dedicated practice-area pages", "category": "Content Optimization", "verticals": ["legal"]},
    {"key": "seo_service_area_pages", "task": "Service-area / location pages", "category": "Content Optimization", "verticals": ["local_retail", "professional_services"]},
    {"key": "seo_pricing_page", "task": "Pricing / quote / 'how it works' page", "category": "Content Optimization", "verticals": ["local_retail", "professional_services"], "exclude_business_types": ["precious_metals_buyer"]},
    # Technical SEO
    {"key": "seo_xml_sitemap", "task": "XML sitemap present and submitted", "category": "Technical SEO",
     "guide": {
         "webflow": (
             "<b>Webflow generates a sitemap automatically.</b>"
             "<ol>"
             "<li>Verify it exists: open <code>https://{domain}/sitemap.xml</code></li>"
             "<li>Submit to Google: go to <a href='https://search.google.com/search-console' target='_blank'>Google Search Console</a>"
             " → <b>Sitemaps</b> (left menu) → paste <code>https://{domain}/sitemap.xml</code> → click <b>Submit</b></li>"
             "</ol>"
         ),
         "squarespace": (
             "<b>Squarespace generates a sitemap automatically.</b>"
             "<ol>"
             "<li>Verify it exists: open <code>https://{domain}/sitemap.xml</code></li>"
             "<li>Submit to Google: go to <a href='https://search.google.com/search-console' target='_blank'>Google Search Console</a>"
             " → <b>Sitemaps</b> → paste <code>https://{domain}/sitemap.xml</code> → <b>Submit</b></li>"
             "</ol>"
             "<b>Tip:</b> In Squarespace, go to <b>Settings → SEO</b> and make sure \"Hide from search engines\" is OFF."
         ),
     }},
    {"key": "seo_structured_headings", "task": "Proper H1/H2/H3 heading hierarchy", "category": "Technical SEO",
     "guide": {
         "_default": (
             "<b>What:</b> Every page should have exactly one H1 (main title), with H2s for sections and H3s for subsections."
             "<br><br>"
             "<b>How to check:</b>"
             "<ol>"
             "<li>Visit <code>https://{domain}</code></li>"
             "<li>Right-click → View Page Source</li>"
             "<li>Search for <code>&lt;h1</code> — there should be exactly one per page</li>"
             "<li>Check that H2s and H3s follow in order (no jumping from H1 to H3)</li>"
             "</ol>"
             "<b>Quick check:</b> Use the free <a href='https://www.headsmap.com/' target='_blank'>HeadsMap browser extension</a> to visualize heading hierarchy."
         ),
     }},
    {"key": "seo_webflow_redirects", "task": "Webflow redirects configured (llms.txt, llms-full.txt, robots.txt)", "category": "Technical SEO", "platform_only": "webflow",
     "guide": {
         "webflow": (
             "<b>This is the same as the \"Redirect /robots.txt to Worker\" task above.</b>"
             " Make sure all 3 redirects are set in <b>Site Settings → Publishing → 301 Redirects</b>:"
             "<table style='margin:0.5rem 0;font-size:0.8rem;border-collapse:collapse;width:100%'>"
             "<tr style='border-bottom:1px solid #ddd'><th style='text-align:left;padding:4px'>Old Path</th><th style='text-align:left;padding:4px'>Redirect To</th></tr>"
             "<tr style='border-bottom:1px solid #ddd'><td style='padding:4px'><code>/robots.txt</code></td>"
             "<td style='padding:4px'><code>https://practicerank-api.practice-rank-ai-seo.workers.dev/geo/{domain}/robots.txt</code></td></tr>"
             "<tr style='border-bottom:1px solid #ddd'><td style='padding:4px'><code>/llms.txt</code></td>"
             "<td style='padding:4px'><code>https://practicerank-api.practice-rank-ai-seo.workers.dev/geo/{domain}/llms.txt</code></td></tr>"
             "<tr><td style='padding:4px'><code>/llms-full.txt</code></td>"
             "<td style='padding:4px'><code>https://practicerank-api.practice-rank-ai-seo.workers.dev/geo/{domain}/llms-full.txt</code></td></tr>"
             "</table>"
             "<b>After adding:</b> Click <b>Publish</b> to make the redirects live."
         ),
     }},
    {"key": "seo_sqsp_code_injection", "task": "Squarespace Code Injection configured (schema, tracking)", "category": "Technical SEO", "platform_only": "squarespace",
     "guide": {
         "squarespace": (
             "<b>How to access Code Injection:</b>"
             "<ol>"
             "<li>Log in to Squarespace</li>"
             "<li>Go to <b>Website → Developer Tools → Code Injection</b>"
             "<br><span style='color:#6b7280;font-size:0.75rem'>(Older versions: Settings → Advanced → Code Injection)</span></li>"
             "<li><b>Header:</b> This is where schema markup (JSON-LD) and tracking codes (Google Analytics, GTM) go</li>"
             "<li><b>Footer:</b> This is for scripts that can load after the page (chat widgets, etc.)</li>"
             "<li>Paste the schema code from the PracticeRank dashboard → Schema tab</li>"
             "<li>Click <b>Save</b></li>"
             "</ol>"
             "<b>To verify:</b> Visit the site → right-click → View Page Source → search for <code>application/ld+json</code>"
         ),
     }},
    {"key": "seo_sqsp_seo_meta", "task": "SEO titles & descriptions set on all pages", "category": "Technical SEO", "platform_only": "squarespace",
     "guide": {
         "squarespace": (
             "<b>How to set SEO titles and descriptions on each page:</b>"
             "<ol>"
             "<li>In Squarespace, go to <b>Pages</b> (left sidebar)</li>"
             "<li>Hover over a page and click the <b>gear icon</b> (⚙️) to open Page Settings</li>"
             "<li>Click the <b>SEO</b> tab</li>"
             "<li><b>SEO Title:</b> Should be like \"Service Name | Practice Name | City, State\" (under 60 characters)</li>"
             "<li><b>SEO Description:</b> 1-2 sentence summary with keywords (under 160 characters)</li>"
             "<li>Click <b>Save</b></li>"
             "<li><b>Repeat for every page on the site</b></li>"
             "</ol>"
             "<b>Tip:</b> The Content tab in PracticeRank generates meta descriptions — use those."
         ),
     }},
    {"key": "seo_sqsp_blog_setup", "task": "Blog page created with categories", "category": "Technical SEO", "platform_only": "squarespace",
     "guide": {
         "squarespace": (
             "<b>How to set up a blog in Squarespace:</b>"
             "<ol>"
             "<li>Go to <b>Pages</b> → click the <b>+</b> button</li>"
             "<li>Select <b>Blog</b> from the page types</li>"
             "<li>Name it \"Blog\" or \"News\"</li>"
             "<li>Click into the blog → <b>Settings</b> (gear icon)</li>"
             "<li>Under <b>Blog Settings</b>, add categories that match your services (e.g., Dental Implants, Cosmetic Dentistry, Oral Health Tips)</li>"
             "<li>Make sure the blog page is added to the site navigation</li>"
             "</ol>"
             "<b>After setup:</b> Use the Content tab to generate and push blog posts as drafts."
         ),
     }},
    {"key": "seo_sqsp_url_redirects", "task": "URL redirects configured for llms.txt/robots.txt", "category": "Technical SEO", "platform_only": "squarespace",
     "guide": {
         "squarespace": (
             "<b>How to add URL redirects in Squarespace:</b>"
             "<ol>"
             "<li>Go to <b>Website → Developer Tools → URL Mappings</b>"
             "<br><span style='color:#6b7280;font-size:0.75rem'>(Older versions: Settings → Advanced → URL Mappings)</span></li>"
             "<li>Add these rules (copy-paste each line exactly):"
             "<pre style='margin:0.5rem 0;padding:0.5rem;background:#1e1e1e;color:#d4d4d4;border-radius:4px;font-size:0.75rem;overflow-x:auto'>"
             "/robots.txt -> https://practicerank-api.practice-rank-ai-seo.workers.dev/geo/{domain}/robots.txt 301\n"
             "/llms.txt -> https://practicerank-api.practice-rank-ai-seo.workers.dev/geo/{domain}/llms.txt 301\n"
             "/llms-full.txt -> https://practicerank-api.practice-rank-ai-seo.workers.dev/geo/{domain}/llms-full.txt 301"
             "</pre></li>"
             "<li>Click <b>Save</b></li>"
             "</ol>"
             "<b>To verify:</b> Open <code>https://{domain}/llms.txt</code> in your browser — you should see practice info (not a 404)."
             "<br><br>"
             "<b>Important:</b> The format is <code>/path -> https://destination 301</code> — make sure the spaces and arrow are exactly right."
         ),
     }},
    # Local SEO & Citations (practice only)
    {"key": "seo_gbp_optimized", "task": "Google Business Profile fully optimized", "category": "Local SEO", "practice_only": True,
     "guide": {
         "_default": (
             "<b>How to optimize Google Business Profile:</b>"
             "<ol>"
             "<li>Go to <a href='https://business.google.com' target='_blank'>business.google.com</a> and sign in with the practice's Google account</li>"
             "<li>Click on the practice listing</li>"
             "<li>Fill in <b>every single field</b>:"
             "<ul>"
             "<li><b>Business name:</b> Exact legal practice name (no extra keywords)</li>"
             "<li><b>Primary category:</b> \"Dentist\" (most important — must be exact)</li>"
             "<li><b>Secondary categories:</b> Add up to 9 (Cosmetic Dentist, Pediatric Dentist, etc.)</li>"
             "<li><b>Address:</b> Must match website and all other listings exactly</li>"
             "<li><b>Phone:</b> Must match website exactly</li>"
             "<li><b>Hours:</b> Must match website exactly</li>"
             "<li><b>Website:</b> <code>https://{domain}</code></li>"
             "<li><b>Description:</b> 750 characters, include city name and top services</li>"
             "<li><b>Services:</b> Add every service with descriptions</li>"
             "<li><b>Appointment URL:</b> Link to online booking if available</li>"
             "</ul></li>"
             "</ol>"
             "<b>Critical:</b> Name, Address, Phone (NAP) must be identical everywhere — Google, website, Yelp, all directories."
         ),
     }},
    {"key": "seo_gbp_photos", "task": "10+ photos on GBP (exterior, interior, team)", "category": "Local SEO", "practice_only": True,
     "guide": {
         "_default": (
             "<b>Upload photos to Google Business Profile:</b>"
             "<ol>"
             "<li>Go to <a href='https://business.google.com' target='_blank'>business.google.com</a></li>"
             "<li>Click <b>Photos</b> in the left menu</li>"
             "<li>Upload at least 10 photos:"
             "<ul>"
             "<li>1-2 exterior shots (so patients can find the building)</li>"
             "<li>3-4 interior shots (waiting room, treatment rooms)</li>"
             "<li>2-3 team photos (doctors, staff)</li>"
             "<li>1-2 equipment/technology photos</li>"
             "</ul></li>"
             "<li>Add a <b>Logo</b> and <b>Cover Photo</b> if not already set</li>"
             "</ol>"
             "<b>Tips:</b> Well-lit, horizontal photos work best. No stock photos — Google may flag them."
         ),
     }},
    {"key": "seo_gbp_qa", "task": "GBP Q&A pre-populated (10-15 questions)", "category": "Local SEO", "practice_only": True,
     "guide": {
         "_default": (
             "<b>Pre-populate the Q&A section on Google Business Profile:</b>"
             "<ol>"
             "<li>Search for the practice on Google Maps</li>"
             "<li>Click <b>Ask a question</b> on the listing</li>"
             "<li>Post common questions <b>from the practice's own Google account</b>, then answer them:</li>"
             "</ol>"
             "<b>Example questions to post and answer:</b>"
             "<ul>"
             "<li>Do you accept [insurance name]?</li>"
             "<li>Do you offer emergency dental services?</li>"
             "<li>What are your hours on Saturday?</li>"
             "<li>Do you do dental implants?</li>"
             "<li>Is parking available?</li>"
             "<li>Do you see children?</li>"
             "<li>Do you offer sedation dentistry?</li>"
             "<li>How do I book an appointment?</li>"
             "<li>Do you accept new patients?</li>"
             "<li>What payment options do you offer?</li>"
             "</ul>"
             "<b>Important:</b> Post AND answer from the practice's Google account — this marks the answer as \"Owner\" verified."
         ),
     }},
    {"key": "seo_citations_ordered", "task": "FATJOE 100-citation bundle ordered (Yelp, Bing, Facebook, NAP + Tier 2)", "category": "Local SEO", "practice_only": True,
     "guide": {
         "_default": (
             "<b>Order the FATJOE local-citations bundle</b> — this builds consistent listings "
             "across the major directories and data aggregators in one go (Yelp, Bing Places, "
             "Facebook, Apple data feeds, YellowPages, BBB, and 90+ more), all with matching NAP. "
             "It replaces claiming each directory by hand."
             "<ol>"
             "<li>Confirm the customer's NAP (name, address, phone) is final and correct.</li>"
             "<li>Place the onboarding 100-citation order in FATJOE (auto-queued by paid tier — see the <b>FATJOE</b> page).</li>"
             "<li>Log the order in the Backlinks &amp; Authority ledger so it auto-ticks here.</li>"
             "</ol>"
             "Auto-ticks when a citation order is recorded for this customer."
         ),
     }},
    {"key": "seo_listings_verified", "task": "Key listings verified live & NAP-consistent", "category": "Local SEO", "practice_only": True,
     "guide": {
         "_default": (
             "<b>Spot-check that the citation build landed</b> and the core listings are live with "
             "matching NAP. Use the <b>Scan Listings</b> button above — it checks the business on "
             "Google, Yelp, Bing, Facebook and verifies the website phone matches Google."
             "<ol>"
             "<li>Click <b>Scan Listings</b>; confirm the key directories show <b>found</b>.</li>"
             "<li>Verify name/address/phone match Google exactly (no \"St.\" vs \"Street\" drift).</li>"
             "</ol>"
             "Auto-ticks when the scan confirms the business across the major directories with a consistent phone."
         ),
     }},
    {"key": "seo_apple_business", "task": "Apple Business listing matches Google (Dan-verified)", "category": "Local SEO", "practice_only": True,
     "guide": {
         "_default": (
             "<b>Manually verify the Apple Business Connect listing matches Google.</b> Apple Maps / "
             "Siri / Spotlight is high-value and the citation bundle doesn't fully claim it — Dan "
             "confirms it by hand."
             "<ol>"
             "<li>Go to <a href='https://businessconnect.apple.com' target='_blank'>businessconnect.apple.com</a> (sign in / claim + verify ownership once).</li>"
             "<li>Confirm primary + secondary categories, hours, address, and phone match Google <b>exactly</b>.</li>"
             "<li>Upload the same photos as GBP; add action buttons (Book, Call) and a Showcase.</li>"
             "</ol>"
             "<b>Note:</b> Apple Business Connect has a management API for multi-location sync — a future "
             "GBP→Apple auto-sync is on the roadmap; for now Dan verifies manually."
         ),
     }},
    {"key": "seo_healthgrades", "task": "Healthgrades profile claimed", "category": "Local SEO", "practice_only": True,
     "guide": {
         "_default": (
             "<ol>"
             "<li>Go to <a href='https://update.healthgrades.com' target='_blank'>update.healthgrades.com</a></li>"
             "<li>Search for each provider by name</li>"
             "<li>Click <b>Claim Profile</b> and verify</li>"
             "<li>Fill in specialties, education, insurance accepted</li>"
             "</ol>"
         ),
     }},
    {"key": "seo_zocdoc", "task": "Zocdoc listing claimed", "category": "Local SEO", "practice_only": True,
     "guide": {
         "_default": (
             "<ol>"
             "<li>Go to <a href='https://www.zocdoc.com/join' target='_blank'>zocdoc.com/join</a></li>"
             "<li>Create a provider profile</li>"
             "<li>Fill in insurance accepted, services, availability</li>"
             "<li>Link appointment booking</li>"
             "</ol>"
             "<b>Note:</b> Zocdoc charges a fee per booking — confirm with Jon before signing up."
         ),
     }},
    # Reviews (practice only)
    {"key": "seo_review_cards", "task": "QR review cards printed & at front desk", "category": "Reviews & Reputation", "practice_only": True,
     "guide": {
         "_default": (
             "<b>Steps:</b>"
             "<ol>"
             "<li>The Grade.us review funnel must be set up first (see task below)</li>"
             "<li>Generate a QR code that points to the Grade.us review page</li>"
             "<li>Design a business-card-sized review card with:"
             "<ul><li>Practice logo</li><li>QR code</li><li>\"We'd love your feedback!\" message</li><li>Short URL as backup</li></ul></li>"
             "<li>Order cards from <a href='https://www.vistaprint.com' target='_blank'>Vistaprint</a> (~$20 for 250)</li>"
             "<li>Place in acrylic holder at front desk and each checkout area</li>"
             "<li>Train front desk: hand a card to every patient at checkout</li>"
             "</ol>"
         ),
     }},
    {"key": "seo_gradeus_setup", "task": "Grade.us review funnel configured", "category": "Reviews & Reputation", "practice_only": True,
     "guide": {
         "_default": (
             "<b>Full setup in Grade.us:</b>"
             "<ol>"
             "<li>Log in to <a href='https://app.grade.us' target='_blank'>Grade.us</a></li>"
             "<li>Create a new location profile</li>"
             "<li>Configure review sites: Google (#1 priority), Healthgrades, Facebook, Yelp</li>"
             "<li>Enable <b>negative feedback interception</b> (1-3 stars go to private form, 4-5 stars go to Google)</li>"
             "<li>Set up 3-message email drip for patients who don't review immediately</li>"
             "<li>Generate the review landing page URL</li>"
             "</ol>"
             "<b>See detailed guide:</b> <code>docs/grade-us-setup.md</code>"
         ),
     }},
    {"key": "seo_review_responses", "task": "Review response workflow active", "category": "Reviews & Reputation", "practice_only": True,
     "guide": {
         "_default": (
             "<b>Set up review monitoring and responses:</b>"
             "<ol>"
             "<li>In Grade.us, enable <b>review alerts</b> — CC the practice owner on all new reviews</li>"
             "<li>Respond to every review within 24 hours:"
             "<ul>"
             "<li><b>Positive reviews:</b> Thank them by name, mention something specific</li>"
             "<li><b>Negative reviews:</b> Apologize, take it offline (\"Please call us at...\")</li>"
             "</ul></li>"
             "<li>The AI can draft review responses — check the Content tab for suggestions</li>"
             "</ol>"
         ),
     }},
]


_seo_cache: dict[str, tuple[float, dict[str, bool]]] = {}
_SEO_CACHE_TTL = 300  # 5 minutes


def _auto_detect_seo_status(domain: str, customer_id: str) -> dict[str, bool]:
    """Auto-detect which SEO/GEO tasks are done by checking live site. Cached for 5 min."""
    import time
    cache_key = f"{domain}:{customer_id}"
    if cache_key in _seo_cache:
        cached_at, cached_result = _seo_cache[cache_key]
        if time.time() - cached_at < _SEO_CACHE_TTL:
            return cached_result

    detected = {}
    if not domain:
        return detected

    body = ""
    try:
        resp = httpx.get(f"https://{domain}", timeout=10.0, follow_redirects=True)
        if resp.status_code == 200:
            body = resp.text
            # Schema detection — check for inline JSON-LD or PracticeRank script loader
            has_schema = "application/ld+json" in body or "practicerank_schema" in body
            if has_schema:
                # If using JS loader (practicerank_schema.js), we can't see the schema
                # types in the HTML — mark the base schema as done based on business type
                if "practicerank_schema" in body and "application/ld+json" not in body:
                    # JS-injected schema — mark org schema as present
                    detected["seo_schema_org"] = True
                    detected["seo_schema_localbusiness"] = True
                else:
                    # Inline JSON-LD — check specific types
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
            # Heading hierarchy
            if "<h1" in body and "<h2" in body:
                detected["seo_structured_headings"] = True
    except Exception:
        pass

    # FAQPage schema correctly lives on service/FAQ pages, not the homepage — so if the
    # homepage didn't show it, sample a couple of content pages before leaving it unchecked
    # (otherwise we false-flag every site that does FAQ schema the right way).
    if not detected.get("seo_schema_faq"):
        import re as _re_faq
        cand = _re_faq.findall(r'href=["\'](/[^"\'#?]+)["\']', body)
        cand = [c for c in dict.fromkeys(cand) if any(k in c.lower() for k in ("faq", "service", "sell", "buy", "product"))]
        for path in list(dict.fromkeys(["/faq", "/faqs"] + cand))[:5]:
            try:
                r = httpx.get(f"https://{domain}{path}", timeout=8.0, follow_redirects=True)
                if r.status_code == 200 and '"FAQPage"' in r.text:
                    detected["seo_schema_faq"] = True
                    break
            except Exception:
                continue

    # Check llms.txt — domain URL must actually work for "deployed on domain" status
    for key, filename in [("seo_llms_txt", "llms.txt"), ("seo_llms_full", "llms-full.txt")]:
        try:
            resp = httpx.get(f"https://{domain}/{filename}", timeout=8.0, follow_redirects=True)
            if resp.status_code == 200 and len(resp.text) > 50:
                detected[key] = True
            # If domain doesn't serve it, DON'T mark as deployed — the redirect isn't set up yet.
            # The Worker check below handles seo_cloudflare_worker separately.
        except Exception:
            pass

    # Check robots.txt — on domain or via Worker
    try:
        resp = httpx.get(f"https://{domain}/robots.txt", timeout=8.0, follow_redirects=True)
        if resp.status_code == 200 and ("ChatGPT-User" in resp.text or "PerplexityBot" in resp.text):
            detected["seo_robots_txt"] = True
            detected["seo_robots_redirected"] = True
        elif WORKER_API_URL:
            resp2 = httpx.get(f"{WORKER_API_URL}/geo/{domain}/robots.txt", timeout=5.0)
            if resp2.status_code == 200 and ("ChatGPT-User" in resp2.text or "PerplexityBot" in resp2.text):
                detected["seo_robots_txt"] = True
                # Worker has it but domain doesn't redirect — redirect not set up yet
    except Exception:
        pass

    # Check if Worker is serving files for this domain
    if WORKER_API_URL:
        try:
            resp = httpx.get(f"{WORKER_API_URL}/geo/{domain}/llms.txt", timeout=5.0)
            if resp.status_code == 200:
                detected["seo_cloudflare_worker"] = True
        except Exception:
            pass

    # Check redirects configured — Squarespace can't redirect /robots.txt (platform serves its own)
    # so only require llms.txt + llms-full.txt for non-Webflow platforms
    llms_redirected = detected.get("seo_llms_txt") and detected.get("seo_llms_full")
    try:
        _db2 = CustomerDB()
        _cust = _db2.get_customer(customer_id)
        _platform = _cust.get("platform", "webflow") if _cust else "webflow"
        _db2.close()
    except Exception:
        _platform = "webflow"

    if _platform == "webflow":
        redirects_ok = llms_redirected and detected.get("seo_robots_redirected")
    else:
        # Squarespace/other: robots.txt can't be redirected, mark based on llms files only
        redirects_ok = llms_redirected
        if redirects_ok:
            detected["seo_robots_txt"] = detected.get("seo_robots_txt", True)  # Squarespace has its own

    if redirects_ok:
        detected["seo_robots_redirected"] = True
        detected["seo_webflow_redirects"] = True
        detected["seo_sqsp_url_redirects"] = True

    # Squarespace-specific auto-detection
    if _platform == "squarespace":
        # Code injection — if schema is on page, code injection is configured
        if detected.get("seo_schema_localbusiness") or detected.get("seo_schema_org"):
            detected["seo_sqsp_code_injection"] = True
        # Blog page — check if /blog exists
        try:
            blog_resp = httpx.get(f"https://{domain}/blog", timeout=8.0, follow_redirects=True)
            if blog_resp.status_code == 200 and ("<article" in blog_resp.text or "blog" in blog_resp.text.lower()):
                detected["seo_sqsp_blog_setup"] = True
        except Exception:
            pass
        # SEO meta — check if pages have custom meta descriptions (not default Squarespace)
        try:
            meta_resp = httpx.get(f"https://{domain}", timeout=8.0, follow_redirects=True)
            if meta_resp.status_code == 200:
                import re as _re
                meta_desc = _re.search(r'<meta\s+name="description"\s+content="([^"]*)"', meta_resp.text)
                if meta_desc and len(meta_desc.group(1)) > 20:
                    detected["seo_sqsp_seo_meta"] = True
        except Exception:
            pass

    # Check XML sitemap
    try:
        resp = httpx.get(f"https://{domain}/sitemap.xml", timeout=8.0, follow_redirects=True)
        if resp.status_code == 200 and ("<urlset" in resp.text or "<sitemapindex" in resp.text):
            detected["seo_xml_sitemap"] = True
    except Exception:
        pass

    # Check if AI mention monitoring has been run (any ai_mentions KPI recorded)
    try:
        _db = CustomerDB()
        mention_kpi = _db.get_latest_kpi(customer_id, "ai_mentions")
        if mention_kpi:
            detected["seo_ai_monitoring"] = True

        # Check GBP from our Google Places data
        places = _db.get_google_places(customer_id)
        if places and places.get("place_id"):
            detected["seo_gbp_optimized"] = True
            # If we have review count, the listing is active
            if places.get("review_count", 0) > 0:
                detected["seo_gbp_optimized"] = True

        # FATJOE citation bundle ordered → the consolidated "citations ordered" item.
        try:
            cite_order = _db.conn.execute(
                "SELECT 1 FROM offsite_orders WHERE customer_id = ? AND order_type = 'citation' LIMIT 1",
                (customer_id,),
            ).fetchone()
            if cite_order:
                detected["seo_citations_ordered"] = True
        except Exception:
            pass

        _db.close()
    except Exception:
        pass

    # Check directory listings (Yelp, Facebook, Healthgrades, Bing)
    # Use search to find if public profiles exist
    _detect_directory_listings(domain, detected)

    _seo_cache[cache_key] = (time.time(), detected)
    return detected


def _detect_directory_listings(domain: str, detected: dict):
    """Check if the business has listings on major directories by searching their sites."""
    if not domain:
        return

    # Yelp/Facebook presence feeds the consolidated "key listings verified" item;
    # Healthgrades stays its own (practice-only) directory item.
    directory_searches = {
        "yelp": f"site:yelp.com {domain}",
        "facebook": f"site:facebook.com {domain}",
        "healthgrades": f"site:healthgrades.com {domain}",
    }

    for key, query in directory_searches.items():
        try:
            # Use Google to find if a listing exists
            resp = httpx.get(
                "https://www.google.com/search",
                params={"q": query, "num": 3},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=5.0,
                follow_redirects=True,
            )
            if resp.status_code == 200:
                # Check if any actual results came back (not just the search page)
                text = resp.text.lower()
                if key == "yelp" and "yelp.com/biz/" in text:
                    detected["seo_listings_verified"] = True
                elif key == "facebook" and ("facebook.com/" in text and domain.replace(".", "") in text):
                    detected["seo_listings_verified"] = True
                elif key == "healthgrades" and "healthgrades.com/" in text:
                    detected["seo_healthgrades"] = True
        except Exception:
            pass


def _get_seo_tasks(checklist: dict[str, bool], business_type: str = "practice",
                   auto_detected: dict[str, bool] | None = None,
                   platform: str = "webflow", domain: str = "",
                   customer_id: str = "", city: str = "") -> list[dict]:
    """Return SEO/GEO tasks grouped by category with completion status.

    Filters tasks based on business_type — practice-only tasks (Local SEO,
    Reviews, dental-specific content) are excluded for non-practice customers.
    Also filters by platform_only field.
    Auto-detected status overrides manual checklist for verifiable tasks.
    Resolves guide text for the current platform and domain.
    """
    vertical = vertical_for(business_type)
    # Dental-specific directories stay practice-only even though they're Local SEO.
    _practice_only_directories = {"seo_healthgrades", "seo_zocdoc"}
    ad = auto_detected or {}
    tasks = []
    for t in SEO_GEO_TASKS:
        vs = t.get("verticals")
        if vs is not None:
            # Explicit vertical scoping (the new model).
            if vertical not in vs:
                continue
        else:
            # Legacy fallback. practice_only Local-SEO / Reviews tasks apply to all
            # LOCAL verticals (a metals buyer or law firm needs GBP, citations,
            # review funnels too) — except dental-only directories. Everything else
            # practice_only is genuinely practice-specific.
            if t.get("practice_only"):
                if (t["category"] in ("Local SEO", "Reviews & Reputation")
                        and t["key"] not in _practice_only_directories):
                    if vertical not in LOCAL_VERTICALS:
                        continue
                elif vertical != "practice":
                    continue
            if t.get("non_practice_only") and vertical == "practice":
                continue
        # Skip tasks that don't fit this business type (e.g. a fixed pricing page
        # makes no sense for a spot-priced precious-metals buyer).
        if (business_type or "").lower() in t.get("exclude_business_types", []):
            continue
        # Skip platform-specific tasks for other platforms
        if t.get("platform_only") and t["platform_only"] != platform:
            continue
        # Skip tasks excluded for this platform
        if platform in t.get("skip_platforms", []):
            continue
        # Auto-detected takes priority over manual checklist
        done = ad.get(t["key"], checklist.get(t["key"], False))
        auto = t["key"] in ad
        # Per-vertical label override (e.g. LocalBusiness vs Store vs Dentist).
        label = t.get("labels", {}).get(vertical, t["task"])
        # Resolve guide for current platform
        guide = ""
        if t.get("guide"):
            guide = t["guide"].get(platform, t["guide"].get("_default", ""))
            if guide:
                guide = guide.replace("{domain}", domain).replace("{customer_id}", customer_id).replace("{city}", city)
        tasks.append({
            "key": t["key"],
            "task": label,
            "category": t["category"],
            "done": done,
            "auto": auto,
            "guide": guide,
        })
    # P2 #6: an unmapped business_type otherwise yields a silent EMPTY checklist. Fall back to
    # the universal baseline (tasks with no vertical scoping and no practice/non-practice gating)
    # so every customer always gets a checklist instead of a blank panel with no explanation.
    if not tasks:
        for t in SEO_GEO_TASKS:
            if t.get("verticals") is not None or t.get("practice_only") or t.get("non_practice_only"):
                continue
            if t.get("platform_only") and t["platform_only"] != platform:
                continue
            if platform in t.get("skip_platforms", []):
                continue
            guide = ""
            if t.get("guide"):
                guide = t["guide"].get(platform, t["guide"].get("_default", ""))
                if guide:
                    guide = guide.replace("{domain}", domain).replace("{customer_id}", customer_id).replace("{city}", city)
            tasks.append({
                "key": t["key"], "task": t.get("labels", {}).get(vertical, t["task"]),
                "category": t["category"],
                "done": ad.get(t["key"], checklist.get(t["key"], False)),
                "auto": t["key"] in ad, "guide": guide,
            })
    return tasks


@app.route("/customer/<customer_id>/emails")
@login_required
def customer_emails(customer_id):
    db = get_db()
    try:
        customer = db.get_customer(customer_id)
        if not customer:
            flash(f"Customer not found: {customer_id}", "error")
            return redirect(url_for("index"))

        contacts = db.get_contacts(customer_id)
        places = db.get_google_places(customer_id)
        competitors = db.get_competitors(customer_id)
        ai_run_summary = db.get_latest_ai_run_summary(customer_id)
        templates = _get_email_templates()

        import markdown

        email_kwargs = dict(
            places=places, competitors=competitors,
            ai_run_summary=ai_run_summary,
            access=db.get_platform_access(customer_id),
            checklist=db.get_checklist(customer_id),
        )

        # Render each template with customer data, convert markdown to HTML
        rendered = []
        for t in templates:
            raw = _render_email_template(t["content"], customer, contacts, **email_kwargs)
            # Strip the "Subject: ..." line from body
            lines = raw.splitlines()
            body_lines = [l for l in lines if not l.startswith("Subject:")]
            body_md = "\n".join(body_lines).strip()
            body_html = markdown.markdown(body_md)

            rendered.append({
                "slug": t["slug"],
                "subject": _render_email_template(t["subject"], customer, contacts, **email_kwargs),
                "body_html": body_html,
            })

        return render_template("customer_emails.html", customer=customer, templates=rendered)
    finally:
        db.close()


# --- Kanban Board ---

BOARD_COLUMNS = [
    ("new", "New Lead", "#6b7280", "Just added, no action yet"),
    ("outreach", "Outreach", "#2563eb", "Contact initiated"),
    ("setup", "Setup", "#d97706", "Granting access, configuring"),
    ("review", "Review", "#7c3aed", "Audit complete, awaiting approval"),
    ("live", "Live", "#059669", "Approved and launched"),
    ("content", "Content", "#8b5cf6", "Pending content to review/publish"),
    ("monitoring", "Monitoring", "#0ea5e9", "Steady state, all caught up"),
    ("attention", "Attention", "#ef4444", "Health score dropped, needs action"),
    ("paused", "Paused", "#9ca3af", "Customer paused/churned"),
]


def compute_health_score(db, customer_id: str) -> int:
    """Compute 0-100 health score from SEO tasks, AI mentions, content freshness, GBP."""
    from datetime import datetime, timezone

    # SEO task completion: 30%
    checklist = db.get_checklist(customer_id)
    total_tasks = len(checklist) if checklist else 1
    done_tasks = sum(1 for v in checklist.values() if v)
    seo_pct = (done_tasks / total_tasks * 100) if total_tasks else 0

    # AI mention rate: 30%
    ai_summary = db.get_latest_ai_run_summary(customer_id)
    ai_pct = (ai_summary["mention_rate"] * 100) if ai_summary else 0

    # Content freshness: 25% — 100 if published in last 14 days, degrades to 0 at 60+
    last_pub = db.get_last_publish_date(customer_id)
    if last_pub:
        try:
            pub_dt = datetime.fromisoformat(last_pub.replace("Z", "+00:00"))
            days = (datetime.now(timezone.utc) - pub_dt).days
            freshness = max(0, 100 - (days - 14) * (100 / 46)) if days > 14 else 100
        except (ValueError, TypeError):
            freshness = 0
    else:
        freshness = 0

    # GBP/Review health: 15%
    places = db.get_google_places(customer_id)
    rating = places["rating"] if places else 0
    gbp = 100 if rating and rating >= 4.0 else (50 if rating else 0)

    return int(seo_pct * 0.30 + ai_pct * 0.30 + freshness * 0.25 + gbp * 0.15)


def recompute_board_step(db, customer: dict) -> str:
    """Compute the correct board column for a customer based on their state."""
    cid = customer["id"]
    status = customer.get("status", "")
    current = customer.get("onboarding_step", "new")

    # Paused/churned override
    if status in ("paused", "churned"):
        return "paused"

    # Onboarding phase
    if current in ("new", "outreach", "setup", "review"):
        checklist = db.get_checklist(cid)
        access = db.get_platform_access(cid)
        pending = db.get_pending_access(cid)
        all_access_done = not pending and bool(access)

        if status == "active":
            return "live"  # promoted to lifecycle

        if customer.get("staging_url"):
            return "review"

        if all_access_done:
            return "setup"

        if checklist.get("onboard_email_sent") or checklist.get("contact_added"):
            return "outreach"

        return current  # stay put

    # Lifecycle phase (live customers rotate between live/content/monitoring/attention)
    if status == "active":
        health = compute_health_score(db, cid)

        if health < 50:
            return "attention"

        rec_counts = db.get_content_recommendation_counts(cid)
        if rec_counts["approved"] > 0:
            return "content"

        return "monitoring"

    return current


# --- Sales Pipeline / Outreach ---

PIPELINE_STAGES = [
    {"value": "new_lead", "label": "New Lead", "color": "#6b7280", "desc": "Report run or manually added"},
    {"value": "outreach_sent", "label": "Outreach Sent", "color": "#2563eb", "desc": "First email sent"},
    {"value": "follow_up", "label": "Follow-up", "color": "#f59e0b", "desc": "Awaiting response"},
    {"value": "interested", "label": "Interested", "color": "#8b5cf6", "desc": "Responded positively"},
    {"value": "proposal_sent", "label": "Proposal", "color": "#0891b2", "desc": "Pricing shared"},
    {"value": "signing_up", "label": "Signing Up", "color": "#16a34a", "desc": "Checkout in progress"},
    {"value": "customer", "label": "Customer", "color": "#059669", "desc": "Payment received"},
    {"value": "lost", "label": "Lost", "color": "#dc2626", "desc": "Declined or unresponsive"},
]

VERTICAL_LABELS = {
    "dental": {"business": "practice", "client": "patient"},
    "legal": {"business": "firm", "client": "client"},
    "medical": {"business": "practice", "client": "patient"},
}


def _render_prospect_email(template_key: str, prospect: dict, report_data: dict | None = None) -> dict:
    """Render an outreach email template with prospect + report data."""
    import json as _json

    name = prospect.get("name", "")
    domain = prospect.get("domain", "")
    vertical = prospect.get("vertical", "dental")
    vl = VERTICAL_LABELS.get(vertical, {"business": "business", "client": "client"})
    score = prospect.get("overall_score", "")
    grade = prospect.get("grade", "")

    # Parse report data for category scores
    categories = {}
    if report_data:
        categories = report_data.get("categories", {})
    elif prospect.get("report_data"):
        try:
            categories = _json.loads(prospect["report_data"]).get("categories", {})
        except Exception:
            pass

    # Find weakest and strongest categories
    scored_cats = []
    for cat_name, cat_data in categories.items():
        if isinstance(cat_data, dict) and "score" in cat_data:
            scored_cats.append((cat_name, cat_data["score"]))
    scored_cats.sort(key=lambda x: x[1])
    weakest = scored_cats[0] if scored_cats else ("", 0)
    strongest = scored_cats[-1] if scored_cats else ("", 0)

    # Build score bullets
    bullets = []
    for cat_name, cat_data in categories.items():
        if isinstance(cat_data, dict) and "score" in cat_data:
            s = cat_data["score"]
            findings = cat_data.get("findings", [])
            finding = findings[0][:150] if findings else ""
            bullets.append(f"- {cat_name.replace('_', ' ').title()}: {s}/100 — {finding}")
    bullets_text = "\n".join(bullets)

    # Review data
    review_data = categories.get("reviews", {})
    review_count = review_data.get("count", "") if isinstance(review_data, dict) else ""
    review_rating = review_data.get("rating", "") if isinstance(review_data, dict) else ""
    comp_name = review_data.get("competitor_name", "") if isinstance(review_data, dict) else ""
    comp_reviews = review_data.get("competitor_reviews", "") if isinstance(review_data, dict) else ""

    city = prospect.get("city", "") or ""
    state = prospect.get("state", "") or ""
    if not city and report_data:
        city = report_data.get("city", "")
        state = report_data.get("state", "")

    vars = {
        "{{prospect_name}}": name,
        "{{domain}}": domain,
        "{{vertical}}": vertical,
        "{{vertical_label}}": vl["business"],
        "{{client_term}}": vl["client"],
        "{{overall_score}}": str(score),
        "{{grade}}": str(grade),
        "{{weakest_category}}": weakest[0].replace("_", " ").title(),
        "{{weakest_score}}": str(weakest[1]),
        "{{strongest_category}}": strongest[0].replace("_", " ").title(),
        "{{strongest_score}}": str(strongest[1]),
        "{{ai_score}}": str(categories.get("ai_readiness", {}).get("score", "")) if isinstance(categories.get("ai_readiness"), dict) else "",
        "{{review_count}}": str(review_count),
        "{{review_rating}}": str(review_rating),
        "{{competitor_name}}": str(comp_name),
        "{{competitor_reviews}}": str(comp_reviews),
        "{{categories_bullets}}": bullets_text,
        "{{city}}": city,
        "{{state}}": state,
    }

    templates = {
        "initial": {
            "subject": "Your {{vertical_label}} scores {{overall_score}}/100 on AI visibility (here's why that matters)",
            "body": """Hi there,

We ran a quick analysis on {{prospect_name}} and found some things worth looking at.

Your {{vertical_label}} scored {{overall_score}}/100 overall, with AI visibility at {{ai_score}}/100. That means when someone asks ChatGPT or Google AI for a {{vertical}} recommendation in {{city}}, your {{vertical_label}} isn't showing up.

Here's the breakdown:

{{categories_bullets}}

Every one of these gaps is a place where potential {{client_term}}s are finding your competitors instead of you.

We fix all of this at PracticeRank. AI discoverability, search optimization, review automation, and structured data markup so that Google, ChatGPT, and Perplexity all point to your {{vertical_label}}.

I'd love to jump on a quick 15-minute call to walk through these findings. No commitment, just a conversation about what's possible.

What does your calendar look like this week?""",
        },
        "followup1": {
            "subject": "Quick follow-up on {{prospect_name}}'s digital visibility",
            "body": """Hi there,

I sent over some findings from our analysis of {{prospect_name}} a few days ago. Not sure if you had a chance to look at it.

The short version: your {{vertical_label}} has a {{weakest_score}}/100 in {{weakest_category}}, which is the biggest gap holding you back from new {{client_term}} inquiries right now.

Happy to walk through the specifics in a quick call if that's easier. Would 15 minutes this week work?""",
        },
        "followup2": {
            "subject": "Closing the loop on {{prospect_name}}",
            "body": """Hi there,

I reached out a couple times about some opportunities we found for {{prospect_name}}'s online presence. I'll assume the timing isn't right.

If anything changes or you'd like to revisit the analysis, you can reach us at practicerank.ai or just reply to this email.

All the best.""",
        },
        "proposal": {
            "subject": "PracticeRank proposal for {{prospect_name}}",
            "body": """Hi there,

Great speaking with you. As discussed, here's a summary of what we'd tackle for {{prospect_name}}:

{{categories_bullets}}

We'd start with the highest-impact items first (AI visibility and {{weakest_category}}) and work through the full roadmap over the first 90 days.

Here's the link to get started: [Stripe checkout link]

Looking forward to working together.""",
        },
    }

    if template_key not in templates:
        return {"subject": "", "body": ""}

    t = templates[template_key]
    subject = t["subject"]
    body = t["body"]
    for k, v in vars.items():
        subject = subject.replace(k, v)
        body = body.replace(k, v)

    return {"subject": subject, "body": body}


@app.route("/pipeline")
@login_required
def pipeline():
    db = get_db()
    try:
        grouped = db.get_all_prospects_grouped()
        columns = []
        for stage_info in PIPELINE_STAGES:
            stage_key = stage_info["value"]
            columns.append({
                "stage": stage_key,
                "label": stage_info["label"],
                "color": stage_info["color"],
                "desc": stage_info["desc"],
                "cards": grouped.get(stage_key, []),
            })
        return render_template("pipeline.html", columns=columns)
    finally:
        db.close()


@app.route("/prospect/<prospect_id>")
@login_required
def prospect_detail(prospect_id):
    import json as _json
    db = get_db()
    try:
        prospect = db.get_prospect(prospect_id)
        if not prospect:
            flash("Prospect not found.", "error")
            return redirect(url_for("pipeline"))

        activities = db.get_prospect_activities(prospect_id)

        # Parse report data for category scores
        categories = {}
        report_data = None
        if prospect.get("report_data"):
            try:
                report_data = _json.loads(prospect["report_data"])
                categories = report_data.get("categories", {})
            except Exception:
                pass

        # Pre-render all email templates
        templates_rendered = {}
        for key in ("initial", "followup1", "followup2", "proposal"):
            templates_rendered[key] = _render_prospect_email(key, prospect, report_data)

        return render_template("prospect_detail.html",
            prospect=prospect,
            activities=activities,
            categories=categories,
            stages=PIPELINE_STAGES,
            templates_json=_json.dumps(templates_rendered),
        )
    finally:
        db.close()


@app.route("/prospect/add", methods=["POST"])
@login_required
def add_prospect():
    db = get_db()
    try:
        name = request.form.get("name", "").strip()
        domain = request.form.get("domain", "").strip()
        if not name or not domain:
            flash("Name and domain are required.", "error")
            return redirect(url_for("pipeline"))

        # Clean domain
        if "://" in domain:
            from urllib.parse import urlparse
            domain = urlparse(domain).netloc
        domain = domain.removeprefix("www.").strip("/")

        prospect_id = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")

        pid = db.upsert_prospect(
            prospect_id=prospect_id,
            domain=domain,
            name=name,
            email=request.form.get("email", "").strip() or None,
            phone=request.form.get("phone", "").strip() or None,
            contact_name=request.form.get("contact_name", "").strip() or None,
            vertical=request.form.get("vertical", "dental"),
        )
        notes = request.form.get("notes", "").strip()
        if notes:
            db.add_prospect_activity(pid, "note", body=notes, created_by=session.get("username", ""))

        audit_log("prospect_created", details=f"Created prospect '{name}' ({domain})")
        flash(f"Prospect '{name}' added to pipeline.", "success")
        return redirect(url_for("pipeline"))
    finally:
        db.close()


@app.route("/prospect/<prospect_id>/note", methods=["POST"])
@login_required
def add_prospect_note(prospect_id):
    db = get_db()
    try:
        activity_type = request.form.get("activity_type", "note")
        body = request.form.get("body", "").strip()
        if body:
            db.add_prospect_activity(
                prospect_id, activity_type, body=body,
                created_by=session.get("username", ""),
            )
        return redirect(url_for("prospect_detail", prospect_id=prospect_id))
    finally:
        db.close()


@app.route("/api/prospect/stage", methods=["POST"])
@login_required
def api_prospect_stage():
    data = request.get_json()
    prospect_id = data.get("prospect_id", "")
    new_stage = data.get("stage", "")
    lost_reason = data.get("lost_reason", "")

    if not prospect_id or not new_stage:
        return jsonify({"error": "prospect_id and stage required"}), 400

    valid_stages = [s["value"] for s in PIPELINE_STAGES]
    if new_stage not in valid_stages:
        return jsonify({"error": f"Invalid stage: {new_stage}"}), 400

    if new_stage == "lost" and not lost_reason:
        return jsonify({"error": "Lost reason is required"}), 400

    db = get_db()
    try:
        ok = db.update_prospect_stage(
            prospect_id, new_stage,
            created_by=session.get("username", ""),
            lost_reason=lost_reason,
        )
        if not ok:
            return jsonify({"error": "Prospect not found"}), 404
        return jsonify({"ok": True})
    finally:
        db.close()


@app.route("/api/prospect/log-email", methods=["POST"])
@login_required
def api_prospect_log_email():
    data = request.get_json()
    prospect_id = data.get("prospect_id", "")
    subject = data.get("subject", "")
    body = data.get("body", "")

    if not prospect_id:
        return jsonify({"error": "prospect_id required"}), 400

    db = get_db()
    try:
        db.add_prospect_activity(
            prospect_id, "email_sent",
            subject=subject, body=body,
            created_by=session.get("username", ""),
        )
        # Auto-advance to outreach_sent if currently new_lead
        prospect = db.get_prospect(prospect_id)
        if prospect and prospect.get("stage") == "new_lead":
            db.update_prospect_stage(
                prospect_id, "outreach_sent",
                created_by=session.get("username", ""),
            )
        audit_log("prospect_email_logged", details=f"Email logged for {prospect_id}: {subject[:50]}")
        return jsonify({"ok": True})
    finally:
        db.close()


@app.route("/board")
@login_required
def board():
    db = get_db()
    try:
        all_customers = db.list_customers()
        staging = get_staging()

        # Exclude archived from board
        customers = [c for c in all_customers if c["status"] != "archived"]

        for c in customers:
            # Recompute board step based on current state
            new_step = recompute_board_step(db, c)
            if new_step != c.get("onboarding_step", "new"):
                db.set_onboarding_step(c["id"], new_step)
                c["onboarding_step"] = new_step

            # Enrich card data
            c["health_score"] = compute_health_score(db, c["id"])
            c["pending_count"] = len(db.get_pending_access(c["id"]))
            c["is_staged"] = staging.is_staged(c["id"])
            c["is_approved"] = staging.is_approved(c["id"])
            places = db.get_google_places(c["id"])
            c["rating"] = places["rating"] if places else None
            c["review_count"] = places["review_count"] if places else None

            # SEO completion %
            checklist = db.get_checklist(c["id"])
            total = len(checklist) if checklist else 0
            done = sum(1 for v in checklist.values() if v) if checklist else 0
            c["seo_pct"] = int(done / total * 100) if total else 0

            # AI mention stats
            ai = db.get_latest_ai_run_summary(c["id"])
            c["ai_mention_count"] = ai["mention_count"] if ai else 0
            c["ai_total_queries"] = ai["total_queries"] if ai else 0
            c["ai_mention_pct"] = int(ai["mention_rate"] * 100) if ai else 0

            # Content pending count (approved but not yet published)
            rec_counts = db.get_content_recommendation_counts(c["id"])
            c["content_pending"] = rec_counts["approved"]

        columns = []
        for step, label, color, desc in BOARD_COLUMNS:
            cards = [c for c in customers if c.get("onboarding_step", "new") == step]
            columns.append({"step": step, "label": label, "color": color, "desc": desc, "cards": cards})

        return render_template("board.html", columns=columns)
    finally:
        db.close()


@app.route("/api/board/move", methods=["POST"])
@login_required
def api_board_move():
    """AJAX endpoint for drag-and-drop step changes."""
    data = request.get_json()
    customer_id = data.get("customer_id", "")
    new_step = data.get("step", "")

    valid_steps = [s for s, _, _, _ in BOARD_COLUMNS]
    if not customer_id or new_step not in valid_steps:
        return jsonify({"error": "Invalid customer or step"}), 400

    db = get_db()
    try:
        db.set_onboarding_step(customer_id, new_step)
        audit_log("board_moved", customer_id=customer_id, details=f"Moved to '{new_step}'")
        return jsonify({"ok": True, "step": new_step})
    finally:
        db.close()


@app.route("/api/seo-recheck/<customer_id>", methods=["POST"])
@login_required
def api_seo_recheck(customer_id):
    """Clear SEO auto-detect cache and re-check live site. Returns updated results."""
    import time
    db = get_db()
    try:
        customer = db.get_customer(customer_id)
        if not customer:
            return jsonify({"error": "Customer not found"}), 404
        domain = customer.get("domain", "")
        if not domain:
            return jsonify({"error": "No domain configured"}), 400

        # Clear cache for this customer
        cache_key = f"{domain}:{customer_id}"
        _seo_cache.pop(cache_key, None)

        # Re-detect
        detected = _auto_detect_seo_status(domain, customer_id)
        audit_log("seo_recheck", customer_id=customer_id)
        return jsonify({"ok": True, "detected": {k: v for k, v in detected.items()}, "domain": domain})
    finally:
        db.close()


@app.route("/api/local-listings/<customer_id>", methods=["POST"])
@login_required
def api_check_local_listings(customer_id):
    """Deep scan for local directory listings using Google Places API + web search."""
    import os
    db = get_db()
    try:
        customer = db.get_customer(customer_id)
        if not customer:
            return jsonify({"error": "Customer not found"}), 404

        name = customer["name"]
        city = customer.get("city", "")
        state = customer.get("state", "")
        domain = customer.get("domain", "")
        phone = customer.get("phone", "")

        results = {}

        # 1. Google Business Profile — use Places API for full details
        places = db.get_google_places(customer_id)
        api_key = os.environ.get("GOOGLE_PLACES_API_KEY", "")

        if places and places.get("place_id") and api_key:
            place_id = places["place_id"]
            # Get Place Details including photos
            try:
                resp = httpx.get(
                    f"https://places.googleapis.com/v1/places/{place_id}",
                    headers={
                        "X-Goog-Api-Key": api_key,
                        "X-Goog-FieldMask": "displayName,rating,userRatingCount,photos,currentOpeningHours,websiteUri,nationalPhoneNumber,formattedAddress,editorialSummary",
                    },
                    timeout=10.0,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    photo_count = len(data.get("photos", []))
                    review_count = data.get("userRatingCount", 0)
                    rating = data.get("rating", 0.0)
                    has_hours = bool(data.get("currentOpeningHours"))
                    has_website = bool(data.get("websiteUri"))
                    gbp_phone = data.get("nationalPhoneNumber", "")
                    gbp_address = data.get("formattedAddress", "")
                    has_phone = bool(gbp_phone)
                    has_description = bool(data.get("editorialSummary"))

                    results["gbp"] = {
                        "found": True,
                        "name": data.get("displayName", {}).get("text", ""),
                        "rating": rating,
                        "review_count": review_count,
                        "photo_count": photo_count,
                        "has_hours": has_hours,
                        "has_website": has_website,
                        "has_phone": has_phone,
                        "has_description": has_description,
                        # Keep the ACTUAL Google phone/address so the NAP check can compare
                        # independent sources (Google vs. website) instead of DB-phone-vs-itself.
                        "phone": gbp_phone,
                        "address": gbp_address,
                        "url": f"https://www.google.com/maps/place/?q=place_id:{place_id}",
                    }

                    # Auto-check tasks based on GBP data
                    checklist_updates = {}
                    if rating > 0 and review_count > 0 and has_hours and has_website and has_phone:
                        checklist_updates["seo_gbp_optimized"] = True
                    if photo_count >= 10:
                        checklist_updates["seo_gbp_photos"] = True

                    if checklist_updates:
                        for key, val in checklist_updates.items():
                            db.set_checklist_item(customer_id, key, val)
                        results["auto_checked"] = list(checklist_updates.keys())
            except Exception as e:
                results["gbp"] = {"found": False, "error": str(e)}
        elif places and places.get("place_id"):
            results["gbp"] = {
                "found": True,
                "rating": places.get("rating", 0),
                "review_count": places.get("review_count", 0),
                "note": "No API key — using cached data",
            }
        else:
            results["gbp"] = {"found": False, "note": "No Google Places data. Run the GEO Agent to look up this business."}

        # 2. Search for directory listings.
        # IMPORTANT: match per-result — require the practice name AND the directory's own
        # domain in the SAME DuckDuckGo result. A page-wide "name in text and 'yelp' in text"
        # check false-positives on any competitor result and writes a bogus green checklist
        # checkmark (P1 audit finding #2).
        search_name = f"{name} {city} {state}"
        # Yelp/Facebook presence now feeds the consolidated "key listings verified" item
        # (the individual Yelp/Facebook checklist items were collapsed into the FATJOE bundle).
        directories = [
            ("yelp", "Yelp", "yelp.com", f"site:yelp.com/biz \"{name}\" {city}", "seo_listings_verified"),
            ("facebook", "Facebook", "facebook.com", f"site:facebook.com \"{name}\"", "seo_listings_verified"),
            ("healthgrades", "Healthgrades", "healthgrades.com", f"site:healthgrades.com \"{name}\"", "seo_healthgrades"),
            ("zocdoc", "Zocdoc", "zocdoc.com", f"site:zocdoc.com \"{name}\" {city}", "seo_zocdoc"),
        ]

        for dir_key, dir_name, dir_domain, query, checklist_key in directories:
            try:
                resp = httpx.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": query},
                    headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
                    timeout=8.0,
                    follow_redirects=True,
                )
                if resp.status_code == 200:
                    found, profile_url = _directory_listing_found(resp.text, name, dir_domain)
                    results[dir_key] = {"found": found, "url": profile_url, "name": dir_name}
                    if found:
                        db.set_checklist_item(customer_id, checklist_key, True)
                else:
                    results[dir_key] = {"found": False, "name": dir_name, "note": "Search failed"}
            except Exception as e:
                results[dir_key] = {"found": False, "name": dir_name, "error": str(e)}

        # 3. Tier 2 citation directories
        tier2_dirs = [
            ("yellowpages", "YellowPages", "yellowpages.com", f"site:yellowpages.com \"{name}\""),
            ("mapquest", "MapQuest", "mapquest.com", f"site:mapquest.com \"{name}\" {city}"),
            ("bbb", "BBB", "bbb.org", f"site:bbb.org \"{name}\""),
            ("bing_places", "Bing Places", "bing.com", f"site:bing.com/maps \"{name}\" {city}"),
        ]
        tier2_found = 0
        for dir_key, dir_name, dir_domain, query in tier2_dirs:
            try:
                resp = httpx.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": query},
                    headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
                    timeout=8.0, follow_redirects=True,
                )
                if resp.status_code == 200:
                    found, _t2url = _directory_listing_found(resp.text, name, dir_domain)
                    results[f"tier2_{dir_key}"] = {"found": found, "name": dir_name}
                    if found:
                        tier2_found += 1
            except Exception:
                pass

        # Citations live across multiple directories → key listings are verified.
        if tier2_found >= 2:
            db.set_checklist_item(customer_id, "seo_listings_verified", True)

        # 4. NAP consistency — compare INDEPENDENT sources. Use the real Google phone from the
        # Places API (not the DB phone) as the canonical NAP, then verify the website shows that
        # same phone. Marking 'consistent' only when both independent sources agree (was previously
        # tautological: DB phone vs. the page that contains the DB phone — P1 audit finding #4).
        def _digits(p):
            return "".join(ch for ch in (p or "") if ch.isdigit())[-10:]
        gbp_phone = (results.get("gbp") or {}).get("phone", "") or phone  # prefer real Google value
        canonical = _digits(gbp_phone)
        results["nap_google_phone"] = gbp_phone
        website_phone_match = False
        try:
            resp = httpx.get(f"https://{domain}", timeout=8.0, follow_redirects=True)
            if resp.status_code == 200 and canonical:
                website_phone_match = canonical in _digits(resp.text)
                results["nap_website_phone"] = website_phone_match
        except Exception:
            pass
        # Consistent only when we have a Google phone AND the website shows the same number.
        if canonical and website_phone_match:
            results["nap_consistent"] = True
            db.set_checklist_item(customer_id, "seo_listings_verified", True)
        else:
            results["nap_consistent"] = False

        # NOTE: Content-page analysis (expert quotes / FAQs / stats / word count) and
        # special-page detection used to live here, querying a `crawled_pages` table that
        # never existed in the schema — so the block always threw, no-op'd, and (worse) ticked
        # two wrong keys (`seo_faq_entries`, `seo_long_service_pages`). Content checklist items
        # are now driven by published content recs via
        # `geo_agent/status_checker._content_task_status` (the single source of truth, run by
        # the nightly reconciler). Removed 2026-06-26.

        # Clear SEO cache so checklist updates show
        cache_key = f"{domain}:{customer_id}"
        _seo_cache.pop(cache_key, None)

        return jsonify({"ok": True, "results": results})
    finally:
        db.close()


def _run_ai_check_background(customer_id: str, run_id: str, customer: dict):
    """Background thread: run AI mention check and update progress via _ai_check_progress."""
    from scripts.check_ai_mentions import (
        build_comprehensive_prompts, query_claude, query_openai,
        query_perplexity, query_gemini, query_grok, check_mention,
    )

    db = get_db()
    try:
        competitors = json.loads(customer.get("competitors_json", "[]")) if customer.get("competitors_json") else []
        services_list = db.get_services(customer_id)
        service_names = [s["name"] for s in services_list]
        prompt_defs = build_comprehensive_prompts(
            customer["name"], customer.get("city", ""), customer.get("state", ""),
            customer.get("specialties", []),
            business_type=customer.get("business_type", "practice"),
            competitors=competitors,
            services=service_names,
        )

        engines = [("Claude", query_claude), ("ChatGPT", query_openai), ("Perplexity", query_perplexity), ("Gemini", query_gemini), ("Grok", query_grok)]

        # Detect which engines have API keys (quick check)
        active_engines = []
        for ai_name, query_fn in engines:
            # We'll detect no_key on first real query
            active_engines.append((ai_name, query_fn))

        total_steps = len(prompt_defs) * len(active_engines)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        with _ai_check_progress_lock:
            _ai_check_progress[run_id] = {
                "status": "running",
                "total_steps": total_steps,
                "completed_steps": 0,
                "current_prompt": "",
                "current_engine": "",
                "current_category": "",
                "mention_count": 0,
                "total_queries": 0,
                "engines": {},
                "prompt_index": 0,
                "total_prompts": len(prompt_defs),
                "results": [],
                "error": None,
            }

        # Create run record (FK constraint)
        db.save_ai_mention_run({
            "id": run_id,
            "customer_id": customer_id,
            "run_date": today,
            "total_mentions": 0,
            "total_queries": 0,
            "mention_rate": 0.0,
            "avg_position": None,
            "engines": {},
            "prompt_set": "comprehensive",
        })

        results = []
        mention_count = 0
        engines_checked = {}
        completed_steps = 0

        def query_single_engine(ai_name, query_fn, prompt, category, pi):
            """Query one engine for one prompt. Returns result dict or None."""
            try:
                response = query_fn(prompt)
            except Exception as e:
                logger.warning(f"AI check error ({ai_name}): {e}")
                response = None
            return {"ai_name": ai_name, "prompt": prompt, "category": category,
                    "prompt_index": pi, "response": response}

        # Process prompts in batches — for each prompt, query all engines in parallel
        with ThreadPoolExecutor(max_workers=5) as executor:
            for pi, pdef in enumerate(prompt_defs):
                prompt = pdef["prompt"]
                category = pdef["category"]

                with _ai_check_progress_lock:
                    prog = _ai_check_progress[run_id]
                    prog["current_prompt"] = prompt[:80]
                    prog["current_category"] = category
                    prog["prompt_index"] = pi + 1
                    prog["current_engine"] = "all (parallel)"

                # Submit all engines for this prompt in parallel
                futures = {
                    executor.submit(query_single_engine, ai_name, query_fn, prompt, category, pi): ai_name
                    for ai_name, query_fn in active_engines
                }

                for future in as_completed(futures):
                    res = future.result()
                    ai_name = res["ai_name"]
                    er = res["response"]
                    completed_steps += 1

                    if er is None:
                        engines_checked.setdefault(ai_name, "no_api_key")
                        with _ai_check_progress_lock:
                            prog = _ai_check_progress[run_id]
                            prog["completed_steps"] = completed_steps
                            prog["engines"].setdefault(ai_name, {"status": "no_api_key", "mentions": 0, "total": 0})
                        continue

                    if er.error:
                        engines_checked[ai_name] = "error"
                        logger.warning(f"AI check {ai_name} error: {er.error}")
                        with _ai_check_progress_lock:
                            prog = _ai_check_progress[run_id]
                            prog["completed_steps"] = completed_steps
                            prog["engines"][ai_name] = {"status": "error", "mentions": 0, "total": 0, "error": er.error}
                        continue

                    response = er.text
                    engines_checked[ai_name] = "active"
                    result = check_mention(response, customer["name"])
                    is_mentioned = result["mentioned"]
                    if is_mentioned:
                        mention_count += 1

                    db.save_ai_mention_result({
                        "run_id": run_id,
                        "customer_id": customer_id,
                        "engine": ai_name,
                        "prompt": prompt,
                        "prompt_category": category,
                        "mentioned": is_mentioned,
                        "position": result["position"],
                        "quality_score": result.get("quality_score", 0),
                        "context": result["context"][:500] if result.get("context") else "",
                        "full_response": response[:2000] if response else "",
                        "is_disclaimer": result.get("disclaimer", False),
                        "model": er.model,
                        "citations": er.citations,
                    })

                    result_item = {
                        "prompt": prompt,
                        "category": category,
                        "ai": ai_name,
                        "mentioned": is_mentioned,
                        "position": result["position"],
                        "quality_score": result.get("quality_score", 0),
                        "context": result["context"][:150] if result.get("context") else "",
                        "full_response": response[:1000] if response else "",
                    }
                    results.append(result_item)

                    with _ai_check_progress_lock:
                        prog = _ai_check_progress[run_id]
                        prog["completed_steps"] = completed_steps
                        prog["mention_count"] = mention_count
                        prog["total_queries"] = len(results)
                        eng_stats = prog["engines"].setdefault(ai_name, {"status": "active", "mentions": 0, "total": 0})
                        eng_stats["status"] = "active"
                        eng_stats["total"] += 1
                        if is_mentioned:
                            eng_stats["mentions"] += 1

        # Compute final stats
        total_queries = len(results)
        mention_rate = mention_count / total_queries if total_queries > 0 else 0.0
        positions = [r["position"] for r in results if r["mentioned"] and r["position"]]
        avg_position = sum(positions) / len(positions) if positions else None

        engine_summary = {}
        for ai_name, status in engines_checked.items():
            if status == "no_api_key":
                engine_summary[ai_name] = {"status": "no_api_key", "mentions": 0, "total": 0}
            else:
                ai_results = [r for r in results if r["ai"] == ai_name]
                ai_mentions = sum(1 for r in ai_results if r["mentioned"])
                engine_summary[ai_name] = {"status": "active", "mentions": ai_mentions, "total": len(ai_results)}

        db.save_ai_mention_run({
            "id": run_id,
            "customer_id": customer_id,
            "run_date": today,
            "total_mentions": mention_count,
            "total_queries": total_queries,
            "mention_rate": mention_rate,
            "avg_position": avg_position,
            "engines": engine_summary,
            "prompt_set": "comprehensive",
        })

        db.record_kpi(customer_id, "ai_mentions", mention_count, today)

        # Category breakdown
        category_summary = {}
        for r in results:
            cat = r["category"]
            category_summary.setdefault(cat, {"mentions": 0, "total": 0, "avg_quality": 0, "qualities": []})
            category_summary[cat]["total"] += 1
            if r["mentioned"]:
                category_summary[cat]["mentions"] += 1
                category_summary[cat]["qualities"].append(r["quality_score"])
        for cat, stats in category_summary.items():
            stats["avg_quality"] = round(sum(stats["qualities"]) / len(stats["qualities"])) if stats["qualities"] else 0
            del stats["qualities"]

        # Extract competitor entities from responses
        try:
            from geo_agent.entity_extractor import extract_and_store
            entity_count = extract_and_store(db, run_id, customer_id, customer["name"])
            logger.info(f"AI check {run_id}: extracted {entity_count} entities")
            db.auto_discover_competitors_from_entities(customer_id, min_mentions=3)
        except Exception as e:
            logger.warning(f"Entity extraction failed (non-fatal): {e}")

        # Clear SEO cache
        domain = customer.get("domain", "")
        cache_key = f"{domain}:{customer_id}"
        _seo_cache.pop(cache_key, None)

        # Mark complete
        with _ai_check_progress_lock:
            _ai_check_progress[run_id] = {
                "status": "complete",
                "total_steps": total_steps,
                "completed_steps": total_steps,
                "mention_count": mention_count,
                "total_queries": total_queries,
                "mention_rate": round(mention_rate * 100, 1),
                "avg_position": round(avg_position, 1) if avg_position else None,
                "engines": engine_summary,
                "categories": category_summary,
                "results": results,
                "error": None,
            }

    except Exception as e:
        logger.exception(f"AI check background error for {customer_id}")
        with _ai_check_progress_lock:
            if run_id in _ai_check_progress:
                _ai_check_progress[run_id]["status"] = "error"
                _ai_check_progress[run_id]["error"] = str(e)
    finally:
        db.checkpoint()
        db.close()


@app.route("/api/ai-mentions/<customer_id>", methods=["POST"])
@login_required
def api_run_ai_mentions(customer_id):
    """Start AI mention check in background. Returns run_id immediately."""
    db = get_db()
    try:
        customer = db.get_customer(customer_id)
        if not customer:
            return jsonify({"error": "Customer not found"}), 404

        run_id = str(uuid.uuid4())

        # Start background thread
        t = threading.Thread(
            target=_run_ai_check_background,
            args=(customer_id, run_id, dict(customer)),
            daemon=True,
        )
        t.start()
        audit_log("ai_check_started", customer_id=customer_id, details=f"run_id={run_id}")

        return jsonify({"ok": True, "run_id": run_id})
    finally:
        db.close()


@app.route("/api/ai-mentions/<customer_id>/run/<run_id>/progress")
@login_required
def api_ai_mention_progress(customer_id, run_id):
    """SSE endpoint for live progress updates during an AI mention check."""
    def generate():
        while True:
            with _ai_check_progress_lock:
                prog = _ai_check_progress.get(run_id)

            if prog is None:
                yield f"data: {json.dumps({'status': 'not_found'})}\n\n"
                break

            yield f"data: {json.dumps(prog, default=str)}\n\n"

            if prog["status"] in ("complete", "error"):
                # Clean up after sending final state (keep for 60s for late subscribers)
                threading.Timer(60.0, lambda: _ai_check_progress.pop(run_id, None)).start()
                break

            time.sleep(1.5)

    return Response(generate(), mimetype="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })


@app.route("/api/ai-mentions/<customer_id>/history")
@login_required
def api_ai_mention_history(customer_id):
    """Get AI mention run history with full detail."""
    db = CustomerDB()
    try:
        # Get runs from the new table
        runs = db.get_ai_mention_runs(customer_id, limit=52)
        if runs:
            run_list = []
            for run in runs:
                engines = json.loads(run.get("engines_json", "{}")) if isinstance(run.get("engines_json"), str) else run.get("engines_json", {})
                run_list.append({
                    "id": run["id"],
                    "date": run["run_date"],
                    "mentions": run["total_mentions"],
                    "total": run["total_queries"],
                    "rate": run["mention_rate"],
                    "avg_position": run.get("avg_position"),
                    "engines": engines,
                })

            # Compute week-over-week change
            for i, run in enumerate(run_list):
                if i + 1 < len(run_list):
                    prev = run_list[i + 1]
                    run["delta"] = run["mentions"] - prev["mentions"]
                    run["rate_delta"] = round(run["rate"] - prev["rate"], 1)
                else:
                    run["delta"] = None
                    run["rate_delta"] = None

            return jsonify({"ok": True, "runs": run_list})

        # Fallback to old KPI data
        mentions = db.get_kpis(customer_id, metric="ai_mentions", limit=52)
        return jsonify({
            "ok": True,
            "runs": [{"date": r["date"], "mentions": int(r["value"]), "total": 0, "rate": 0, "delta": None} for r in mentions],
        })
    finally:
        db.close()


@app.route("/api/ai-mentions/<customer_id>/run/<run_id>")
@login_required
def api_ai_mention_run_detail(customer_id, run_id):
    """Get full details for a specific AI mention run."""
    db = CustomerDB()
    try:
        results = db.get_ai_mention_results(run_id)
        # Group by category
        by_category = {}
        for r in results:
            cat = r.get("prompt_category", "general")
            by_category.setdefault(cat, [])
            by_category[cat].append({
                "engine": r["engine"],
                "prompt": r["prompt"],
                "mentioned": bool(r["mentioned"]),
                "position": r.get("position"),
                "quality_score": r.get("quality_score", 0),
                "context": r.get("context", ""),
                "full_response": r.get("full_response", ""),
                "is_disclaimer": bool(r.get("is_disclaimer")),
            })
        return jsonify({"ok": True, "categories": by_category, "total": len(results)})
    finally:
        db.close()


@app.route("/api/ai-mentions/<customer_id>/trends")
@login_required
def api_ai_mention_trends(customer_id):
    """Get per-prompt trend data across runs for sparkline/trend visualization."""
    db = CustomerDB()
    try:
        rows = db.get_ai_mention_trends(customer_id, limit_runs=12)
        if not rows:
            return jsonify({"ok": True, "trends": [], "dates": []})

        # Collect unique dates
        dates = sorted(set(r["run_date"] for r in rows))

        # Build trend data: {prompt: {engine: {date: {mentioned, position, quality}}}}
        trends = {}
        for r in rows:
            key = r["prompt"]
            if key not in trends:
                trends[key] = {"prompt": r["prompt"], "category": r["prompt_category"], "engines": {}}
            eng = trends[key]["engines"].setdefault(r["engine"], {})
            eng[r["run_date"]] = {
                "mentioned": bool(r["mentioned"]),
                "position": r["position"],
                "quality": r["quality_score"],
            }

        # Convert to list sorted by category then prompt
        trend_list = sorted(trends.values(), key=lambda t: (t["category"], t["prompt"]))

        return jsonify({"ok": True, "trends": trend_list, "dates": dates})
    finally:
        db.close()


@app.route("/api/ai-mentions/<customer_id>/baseline", methods=["GET", "POST"])
@login_required
def api_ai_mention_baseline(customer_id):
    """GET current baseline; POST sets a run (or the latest) as the baseline."""
    db = get_db()
    try:
        if request.method == "POST":
            run_id = (request.get_json(silent=True) or {}).get("run_id")
            if not run_id:
                runs = db.get_ai_mention_runs(customer_id, limit=1)
                if not runs:
                    return jsonify({"ok": False, "error": "No runs yet to baseline"}), 400
                run_id = runs[0]["id"]
            db.set_baseline_run(customer_id, run_id)
            audit_log("ai_baseline_set", customer_id=customer_id, details=f"run_id={run_id}")
        base = db.get_baseline_run(customer_id)
        return jsonify({"ok": True, "baseline_date": base.get("run_date") if base else None,
                        "baseline_run_id": base.get("id") if base else None})
    finally:
        db.close()


@app.route("/api/ai-mentions/<customer_id>/events")
@login_required
def api_ai_mention_events(customer_id):
    """Product-action events (published content) for attribution markers on the trend."""
    db = get_db()
    try:
        return jsonify({"ok": True, "events": db.get_published_content_events(customer_id, limit=50)})
    finally:
        db.close()


@app.route("/api/ai-mentions/<customer_id>/adapt")
@login_required
def api_ai_mention_adapt(customer_id):
    """The 'adapt over time' plan: queries we're not cited on -> FAQ/content to add."""
    db = get_db()
    try:
        from geo_agent.llms_adaptation import build_adaptation_plan
        return jsonify({"ok": True, "plan": build_adaptation_plan(db, customer_id)})
    finally:
        db.close()


@app.route("/api/ai-mentions/<customer_id>/weekly")
@login_required
def api_ai_weekly_summaries(customer_id):
    """Get weekly-grouped AI mention summaries."""
    db = CustomerDB()
    try:
        weeks_param = request.args.get("weeks", 12, type=int)
        prompt_set = request.args.get("prompt_set", "benchmark")
        weeks = db.get_weekly_ai_summaries(customer_id, weeks=weeks_param, prompt_set=prompt_set)
        return jsonify({"ok": True, "weeks": weeks})
    finally:
        db.close()


@app.route("/api/ai-mentions/<customer_id>/share-of-voice")
@login_required
def api_ai_share_of_voice(customer_id):
    """Get competitive share of voice from AI response entity extraction."""
    db = CustomerDB()
    try:
        last_n = request.args.get("runs", 3, type=int)
        sov = db.get_share_of_voice(customer_id, last_n_runs=last_n)
        trend = db.get_competitor_entity_trend(customer_id, limit_weeks=8)
        return jsonify({"ok": True, "share_of_voice": sov, "trend": trend})
    finally:
        db.close()


@app.route("/api/ai-mentions/<customer_id>/report")
@login_required
def api_ai_mention_report_docx(customer_id):
    """Download a polished AI Mention Report as DOCX."""
    db = CustomerDB()
    try:
        customer = db.get_customer(customer_id)
        if not customer:
            return jsonify({"error": "Customer not found"}), 404

        # Get latest completed run
        runs = db.get_ai_mention_runs(customer_id, limit=1)
        valid_runs = [r for r in runs if r.get("total_queries", 0) > 0]
        if not valid_runs:
            return jsonify({"error": "No completed runs. Run an AI mention check first."}), 404

        latest = valid_runs[0]
        run_id = latest["id"]
        engines_data = json.loads(latest.get("engines_json", "{}")) if isinstance(latest.get("engines_json"), str) else latest.get("engines_json", {})

        run_data = {
            "date": latest["run_date"],
            "mention_count": latest["total_mentions"],
            "total_queries": latest["total_queries"],
            "mention_rate": latest["mention_rate"],
            "avg_position": latest.get("avg_position"),
            "engines": engines_data,
        }

        # Get results for this run
        results = db.get_ai_mention_results(run_id)
        result_list = [{
            "prompt": r["prompt"],
            "category": r.get("prompt_category", "general"),
            "ai": r["engine"],
            "mentioned": bool(r["mentioned"]),
            "position": r.get("position"),
            "quality_score": r.get("quality_score", 0),
            "context": r.get("context", ""),
        } for r in results]

        # Get history for trend section
        all_runs = db.get_ai_mention_runs(customer_id, limit=12)
        history = [{
            "date": r["run_date"],
            "mentions": r["total_mentions"],
            "total": r["total_queries"],
            "rate": r["mention_rate"],
            "avg_position": r.get("avg_position"),
            "delta": None,
        } for r in all_runs if r.get("total_queries", 0) > 0]

        # Compute deltas
        for i, h in enumerate(history):
            if i + 1 < len(history):
                h["delta"] = h["mentions"] - history[i + 1]["mentions"]

        from geo_agent.ai_report_docx import generate_ai_mention_report
        buf = generate_ai_mention_report(
            customer=dict(customer),
            run_data=run_data,
            results=result_list,
            history=history if len(history) >= 2 else None,
        )

        filename = f"AI-Mention-Report-{customer.get('name', customer_id).replace(' ', '-')}-{latest['run_date']}.docx"
        return send_file(
            buf,
            as_attachment=True,
            download_name=filename,
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    finally:
        db.close()


@app.route("/api/visibility/<customer_id>")
@login_required
def api_visibility_score(customer_id):
    """Get composite AI visibility score with all signal breakdowns."""
    db = CustomerDB()
    try:
        # Rolling mention average
        rolling = db.get_rolling_mention_stats(customer_id, window=12)

        # Latest single-run data for comparison
        latest_run = db.get_latest_ai_run_summary(customer_id)

        # GSC data
        gsc_weeks = db.get_gsc_weekly_summary(customer_id, weeks=8)

        # llms.txt hits
        llms_kpis = db.get_kpis(customer_id, "llms_txt_hits", limit=4)

        # Reviews
        places = db.get_google_places(customer_id)
        competitors = db.get_competitors(customer_id)
        review_kpis = db.get_kpis(customer_id, "review_count", limit=4)

        # Build signal scores (each 0-100)
        signals = {}

        # AI Mentions — use rolling average, much more stable than single run
        if rolling:
            rate = rolling["current_rate"]
            if rate >= 0.40:
                ai_score = 100
            elif rate >= 0.05:
                ai_score = int(25 + (rate - 0.05) / 0.35 * 75)
            else:
                ai_score = int(rate / 0.05 * 25)
            signals["ai_mentions"] = {
                "score": ai_score, "available": True, "weight": 0.25,
                "detail": f"{rate:.0%} rolling avg ({rolling['run_count']} runs, trend: {rolling['trend']})",
                "rolling_rate": rolling["current_rate"],
                "prev_rate": rolling["prev_rate"],
                "trend": rolling["trend"],
                "rates": rolling["rates"],
                "dates": rolling["dates"],
            }
        else:
            signals["ai_mentions"] = {"score": 0, "available": False, "weight": 0.25, "detail": "Need 3+ runs for rolling average"}

        # GSC Clicks — growth based
        if gsc_weeks and len(gsc_weeks) >= 2:
            current_clicks = gsc_weeks[0]["clicks"]
            prev_clicks = gsc_weeks[1]["clicks"]
            if prev_clicks > 0:
                growth = (current_clicks - prev_clicks) / prev_clicks
                gsc_score = min(100, max(0, int(50 + growth * 250)))
            else:
                gsc_score = 50 if current_clicks > 0 else 0
            signals["gsc_clicks"] = {
                "score": gsc_score, "available": True, "weight": 0.30,
                "detail": f"{current_clicks} clicks this week ({'+' if current_clicks >= prev_clicks else ''}{current_clicks - prev_clicks} vs last)",
                "weeks": list(reversed(gsc_weeks)),
            }
        else:
            signals["gsc_clicks"] = {"score": 0, "available": False, "weight": 0.30, "detail": "GSC access not yet granted"}

        # llms.txt Hits
        if llms_kpis:
            hits = int(llms_kpis[0]["value"])
            if hits >= 100:
                llms_score = 100
            elif hits >= 50:
                llms_score = 75
            elif hits >= 10:
                llms_score = 50
            elif hits >= 1:
                llms_score = 25
            else:
                llms_score = 0
            signals["llms_hits"] = {
                "score": llms_score, "available": True, "weight": 0.25,
                "detail": f"{hits} total hits",
            }
        else:
            signals["llms_hits"] = {"score": 0, "available": False, "weight": 0.25, "detail": "No llms.txt hit data yet"}

        # Review Growth
        if places and places.get("review_count"):
            our_reviews = places["review_count"]
            comp_avg = (sum(c["review_count"] for c in competitors) / len(competitors)) if competitors else our_reviews
            ratio = our_reviews / max(comp_avg, 1)
            review_score = min(100, int(ratio * 60))
            # Growth bonus
            if len(review_kpis) >= 2:
                growth = int(review_kpis[0]["value"]) - int(review_kpis[1]["value"])
                review_score = min(100, review_score + min(growth * 2, 20))
            signals["reviews"] = {
                "score": review_score, "available": True, "weight": 0.20,
                "detail": f"{our_reviews} reviews (market avg: {comp_avg:.0f})",
            }
        else:
            signals["reviews"] = {"score": 0, "available": False, "weight": 0.20, "detail": "No review data"}

        # Compute composite score, redistributing unavailable weights
        available = {k: v for k, v in signals.items() if v["available"]}
        if available:
            total_weight = sum(v["weight"] for v in available.values())
            score = sum(v["score"] * (v["weight"] / total_weight) for v in available.values())
            score = int(round(score))
        else:
            score = 0

        grade = "A" if score >= 80 else "B" if score >= 60 else "C" if score >= 40 else "D" if score >= 20 else "F"

        return jsonify({
            "ok": True,
            "score": score,
            "grade": grade,
            "signals": signals,
            "latest_run": {
                "rate": latest_run["mention_rate"] if latest_run else None,
                "mentions": latest_run["mention_count"] if latest_run else None,
                "total": latest_run["total_queries"] if latest_run else None,
            } if latest_run else None,
        })
    finally:
        db.close()


@app.route("/api/practicerank-score/<customer_id>")
@login_required
def api_practicerank_score(customer_id):
    """Get current PracticeRank score with pillar breakdown."""
    from geo_agent.practicerank_score import compute_practicerank_score, grade_from_score
    db = CustomerDB()
    try:
        result = compute_practicerank_score(db, customer_id)
        # Also get previous score for delta
        prev = None
        scores = db.get_practicerank_scores(customer_id, limit=2)
        if len(scores) >= 2:
            prev = scores[1]["overall_score"]
        return jsonify({"ok": True, **result, "prev_score": prev})
    finally:
        db.close()


@app.route("/api/score-history/<customer_id>")
@login_required
def api_score_history(customer_id):
    """Get daily score history for trend chart."""
    range_param = request.args.get("range", "90d")
    limit = {"30d": 30, "90d": 90, "180d": 180, "365d": 365}.get(range_param, 90)
    db = CustomerDB()
    try:
        scores = db.get_practicerank_scores(customer_id, limit=limit)
        return jsonify({
            "ok": True,
            "scores": list(reversed(scores)),  # chronological order
        })
    finally:
        db.close()


@app.route("/api/ai-trend/<customer_id>")
@login_required
def api_ai_trend(customer_id):
    """Get AI mention rate trend data for chart."""
    limit = int(request.args.get("limit", 20))
    db = CustomerDB()
    try:
        runs = db.get_ai_mention_runs(customer_id, limit=limit)
        trend_data = []
        for run in reversed(runs):  # chronological
            engines = run.get("engines_json", "{}")
            if isinstance(engines, str):
                try:
                    engines = json.loads(engines)
                except (json.JSONDecodeError, TypeError):
                    engines = {}
            trend_data.append({
                "date": run["run_date"][:10],
                "mention_rate": round((run.get("mention_rate") or 0) * 100, 1),
                "total_mentions": run.get("total_mentions", 0),
                "total_queries": run.get("total_queries", 0),
                "avg_position": round(run.get("avg_position") or 0, 1),
                "engines": {
                    k: {"mentions": v.get("mentions", 0), "queries": v.get("queries", 0)}
                    for k, v in engines.items() if isinstance(v, dict)
                },
            })
        return jsonify({"ok": True, "trend": trend_data})
    finally:
        db.close()


@app.route("/api/quick-wins/<customer_id>")
@login_required
def api_quick_wins(customer_id):
    """Get prioritized quick wins for a customer."""
    from geo_agent.quick_wins import detect_quick_wins
    db = CustomerDB()
    try:
        wins = detect_quick_wins(db, customer_id)
        return jsonify({
            "ok": True,
            "wins": [w.to_dict() for w in wins[:8]],
        })
    finally:
        db.close()


@app.route("/api/analytics/scores")
@login_required
def api_analytics_scores():
    """Get latest scores for all customers (leaderboard)."""
    db = CustomerDB()
    try:
        scores = db.get_all_latest_scores()
        # Enrich with customer names, exclude archived
        customers = {c["id"]: c for c in db.list_customers()}
        result = []
        for s in scores:
            cust = customers.get(s["customer_id"], {})
            if cust.get("status") == "archived":
                continue
            from geo_agent.practicerank_score import grade_from_score
            grade = grade_from_score(s["overall_score"])
            result.append({
                **s,
                "name": cust.get("name", s["customer_id"]),
                "domain": cust.get("domain", ""),
                "grade": grade,
            })
        return jsonify({"ok": True, "scores": result})
    finally:
        db.close()


@app.route("/api/gsc/<customer_id>")
@login_required
def api_gsc_metrics(customer_id):
    """Get GSC metrics for a date range. Pulls live from GSC API if integration exists."""
    range_param = request.args.get("range", "30d")
    range_days = {"7d": 7, "30d": 30, "90d": 90, "180d": 180}.get(range_param, 30)

    db = CustomerDB()
    try:
        # Try live GSC pull
        gsc_daily = []
        gsc_top_pages = []
        keyword_summary = []
        integrations = db.get_integrations(customer_id)
        gsc_int = next((i for i in integrations if i["integration"] == "gsc" and i["status"] == "active"), None)
        if gsc_int:
            import json as _json
            config = _json.loads(gsc_int.get("config_json", "{}"))
            _gsc_prop = config.get("property_url", "")
            if _gsc_prop:
                try:
                    from geo_agent.gsc_client import fetch_search_metrics, fetch_top_pages
                    from datetime import timedelta as _td
                    _end = (datetime.now(timezone.utc) - _td(days=2)).strftime("%Y-%m-%d")
                    _start = (datetime.now(timezone.utc) - _td(days=2 + range_days)).strftime("%Y-%m-%d")
                    gsc_daily = fetch_search_metrics(_gsc_prop, _start, _end, ["date"]) or []
                    gsc_top_pages = fetch_top_pages(_gsc_prop, _start, _end, limit=10) or []
                    # Previous period for comparison
                    _prev_end = _start
                    _prev_start = (datetime.now(timezone.utc) - _td(days=2 + range_days * 2)).strftime("%Y-%m-%d")
                    prev_daily = fetch_search_metrics(_gsc_prop, _prev_start, _prev_end, ["date"]) or []
                except Exception:
                    prev_daily = []
        else:
            prev_daily = []

        if not gsc_daily:
            # Fallback to stored data
            daily = db.get_gsc_daily(customer_id, limit=range_days)
            gsc_daily = list(reversed(daily))
            prev_daily = []

        # Compute summary stats
        total_clicks = sum(d.get("clicks", 0) for d in gsc_daily)
        total_impressions = sum(d.get("impressions", 0) for d in gsc_daily)
        avg_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
        avg_pos = sum(d.get("position", 0) for d in gsc_daily) / len(gsc_daily) if gsc_daily else 0
        prev_clicks = sum(d.get("clicks", 0) for d in prev_daily)
        prev_impressions = sum(d.get("impressions", 0) for d in prev_daily)

        # Keyword summary
        keyword_summary = db.get_keyword_summary(customer_id)

        return jsonify({
            "ok": True,
            "daily": gsc_daily,
            "top_pages": gsc_top_pages,
            "keyword_summary": (keyword_summary or [])[:10],
            "stats": {
                "clicks": total_clicks,
                "impressions": total_impressions,
                "ctr": round(avg_ctr, 1),
                "position": round(avg_pos, 1),
                "prev_clicks": prev_clicks,
                "prev_impressions": prev_impressions,
                "days": len(gsc_daily),
            },
            "range": range_param,
            "date_start": gsc_daily[0]["date"] if gsc_daily else "",
            "date_end": gsc_daily[-1]["date"] if gsc_daily else "",
        })
    finally:
        db.close()


@app.route("/api/gsc/<customer_id>/pull", methods=["POST"])
@login_required
def api_gsc_pull(customer_id):
    """Manually trigger a GSC data pull for a customer."""
    try:
        from geo_agent.gsc_client import track_gsc_metrics
        db = CustomerDB()
        try:
            result = track_gsc_metrics(db, customer_id)
            if result:
                audit_log("gsc_pull", customer_id=customer_id, details=f"{result.get('total_clicks', 0)} clicks")
                return jsonify({"ok": True, "result": result})
            return jsonify({"ok": False, "error": "GSC pull returned no data — check service account access"}), 400
        finally:
            db.close()
    except ImportError:
        return jsonify({"ok": False, "error": "google-api-python-client not installed"}), 500
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/checklist", methods=["POST"])
@login_required
def api_checklist():
    """Toggle a VA checklist item and auto-advance kanban step."""
    data = request.get_json()
    customer_id = data.get("customer_id", "")
    task_key = data.get("task_key", "")
    completed = data.get("completed", False)

    if not customer_id or not task_key:
        return jsonify({"error": "Missing fields"}), 400

    db = get_db()
    try:
        db.set_checklist_item(customer_id, task_key, completed)
        audit_log("checklist_toggled", customer_id=customer_id, details=f"{task_key} -> {'done' if completed else 'undone'}")

        # Auto-advance kanban step based on current state
        customer = db.get_customer(customer_id)
        if customer:
            new_step = recompute_board_step(db, customer)
            current = customer.get("onboarding_step", "new")
            if new_step != current:
                db.set_onboarding_step(customer_id, new_step)

        # HTMX: return updated HTML
        if request.headers.get("HX-Request"):
            hx_target = request.headers.get("HX-Target", "")

            if hx_target == "todo-list":
                # Full todo list refresh (overview tab)
                customer = db.get_customer(customer_id)
                contacts = db.get_contacts(customer_id)
                access_list = db.get_platform_access(customer_id)
                places = db.get_google_places(customer_id)
                runs_list = db.get_runs(customer_id)
                staged = get_staging().is_staged(customer_id)
                approved = get_staging().is_approved(customer_id)
                cl = db.get_checklist(customer_id)
                todos = _get_va_todos(customer, access_list, contacts, places, runs_list, staged, approved, cl)
                return render_template("partials/todo_list.html", customer=customer, todos=todos)
            else:
                # Single item swap (SEO tab)
                next_val = "false" if completed else "true"
                done_cls = "done" if completed else ""
                check_cls = "checked" if completed else ""
                return f'''<div class="todo-item {done_cls}"
                    hx-post="/api/checklist"
                    hx-vals='{{"customer_id":"{customer_id}","task_key":"{task_key}","completed":{next_val}}}'
                    hx-target="closest .todo-item"
                    hx-swap="outerHTML"
                    hx-headers='{{"Content-Type":"application/json"}}'
                    style="cursor:pointer;">
                    <div class="todo-check {check_cls}" title="Click to toggle"></div>
                    <span>{task_key}</span>
                </div>'''

        return jsonify({"ok": True})
    finally:
        db.close()


@app.route("/api/board/status", methods=["POST"])
@login_required
def api_board_status():
    """AJAX endpoint for changing customer status from board card."""
    data = request.get_json()
    customer_id = data.get("customer_id", "")
    new_status = data.get("status", "")

    if new_status not in ("onboarding", "active", "paused", "churned"):
        return jsonify({"error": "Invalid status"}), 400

    db = get_db()
    try:
        db.set_customer_status(customer_id, new_status)
        audit_log("board_status_changed", customer_id=customer_id, details=f"Status -> {new_status}")
        # Recompute board step after status change
        customer = db.get_customer(customer_id)
        if customer:
            new_step = recompute_board_step(db, customer)
            db.set_onboarding_step(customer_id, new_step)
        return jsonify({"ok": True, "status": new_status})
    finally:
        db.close()


# --- Audit Logs ---

@app.route("/expenses")
@login_required
def expenses():
    """Operating-cost breakdown — every AI/LLM API + service the platform pays
    for, monthly cost, and when it's charged. Usage lines scale by active
    customers; see dashboard/expenses.py for the source line items."""
    from geo_agent.expenses import compute_expenses
    db = get_db()
    try:
        customers = db.list_customers()
        active = sum(1 for c in customers if c.get("status") == "active")
        non_archived = sum(1 for c in customers if c.get("status") != "archived")
        # Real FATJOE COGS from logged orders — month-to-date + all-time.
        _month_start = datetime.now(timezone.utc).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        fatjoe_mtd = db.offsite_spend(since=_month_start)
        fatjoe_total = db.offsite_spend()
    finally:
        db.close()
    # Bill against active customers, but never 0 (so per-customer rates show).
    data = compute_expenses(active or non_archived or 1,
                            fatjoe_mtd=fatjoe_mtd, fatjoe_total=fatjoe_total)
    return render_template(
        "expenses.html",
        data=data, active_customers=active, non_archived=non_archived,
    )


@app.route("/audit-logs")
@login_required
def audit_logs():
    """View structured audit logs."""
    import glob

    audit_dir = Path(DATA_DIR).parent / "audit_logs"
    if not audit_dir.exists():
        return render_template("audit_logs.html", logs=[], dates=[], selected_date=None)

    # Get available log dates
    log_files = sorted(audit_dir.glob("audit_*.jsonl"), reverse=True)
    dates = [f.stem.replace("audit_", "") for f in log_files]

    # Load selected date or latest
    selected_date = request.args.get("date", dates[0] if dates else None)
    customer_filter = request.args.get("customer", "")
    action_filter = request.args.get("action", "")

    logs = []
    if selected_date:
        log_file = audit_dir / f"audit_{selected_date}.jsonl"
        if log_file.exists():
            with open(log_file) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        # Apply filters
                        if customer_filter and entry.get("customer_id") != customer_filter:
                            continue
                        if action_filter and action_filter not in entry.get("action", ""):
                            continue
                        logs.append(entry)
                    except json.JSONDecodeError:
                        continue

    # Reverse to show newest first
    logs.reverse()

    # Get unique actions for filter dropdown
    all_actions = sorted(set(e.get("action", "") for e in logs))
    all_customers = sorted(set(e.get("customer_id", "") for e in logs))

    return render_template(
        "audit_logs.html",
        logs=logs[:200],  # Limit display
        dates=dates[:30],
        selected_date=selected_date,
        customer_filter=customer_filter,
        action_filter=action_filter,
        all_actions=all_actions,
        all_customers=all_customers,
        total_count=len(logs),
    )


# --- Case Studies ---

@app.route("/customer/<customer_id>/case-study")
@login_required
def customer_case_study(customer_id):
    """Generate and display a case study for a customer."""
    fmt = request.args.get("format", "html")
    db = get_db()
    try:
        from scripts.generate_case_study import generate_case_study as gen_cs
        case_study = gen_cs(db, customer_id, fmt=fmt)

        if fmt == "html":
            return case_study  # Already a full HTML page
        else:
            # Wrap markdown in a simple page
            import markdown
            html_body = markdown.markdown(case_study, extensions=["tables"])
            return render_template("case_study.html", customer_id=customer_id, body_html=html_body)
    except Exception as e:
        flash(f"Error generating case study: {e}", "error")
        return redirect(url_for("customer_detail", customer_id=customer_id))
    finally:
        db.close()


@app.route("/case-studies")
@login_required
def case_studies():
    """Aggregate stats and links to individual case studies."""
    db = get_db()
    try:
        from scripts.generate_case_study import generate_aggregate_stats
        aggregate = generate_aggregate_stats(db)
        customers = db.list_customers(status="active")

        # Get key metrics per customer for the list
        customer_data = []
        for c in customers:
            review_kpis = db.get_kpis(c["id"], "review_count", limit=2)
            hits_kpis = db.get_kpis(c["id"], "llms_txt_hits", limit=1)
            mention_kpis = db.get_kpis(c["id"], "ai_mentions", limit=1)

            customer_data.append({
                "id": c["id"],
                "name": c["name"],
                "reviews": int(review_kpis[0]["value"]) if review_kpis else 0,
                "hits": int(hits_kpis[0]["value"]) if hits_kpis else 0,
                "mentions": int(mention_kpis[0]["value"]) if mention_kpis else 0,
                "has_data": bool(review_kpis or hits_kpis),
            })

        return render_template("case_studies.html", aggregate=aggregate, customers=customer_data)
    finally:
        db.close()


# --- Hosting Detection ---

@app.route("/api/hosting/detect", methods=["POST"])
@login_required
def api_detect_hosting():
    """Run DNS/hosting detection for a customer and save results."""
    customer_id = request.form.get("customer_id")
    if not customer_id:
        flash("Missing customer_id", "error")
        return redirect(url_for("customers"))

    db = get_db()
    try:
        customer = db.get_customer(customer_id)
        if not customer:
            flash("Customer not found", "error")
            return redirect(url_for("customers"))

        from geo_agent.hosting_detector import detect_hosting
        hosting_info = detect_hosting(customer["domain"])
        db.update_customer(customer_id, hosting_info=json.dumps(hosting_info))

        # Auto-update platform if detected
        if hosting_info.get("cms") and customer.get("platform") in ("unknown", "auto", ""):
            cms = hosting_info["cms"].lower()
            for keyword, platform in [("wordpress", "wordpress"), ("webflow", "webflow"),
                                       ("squarespace", "squarespace"), ("wix", "wix")]:
                if keyword in cms:
                    db.update_customer(customer_id, platform=platform)
                    break

        flash(f"Hosting detected: {hosting_info.get('summary', 'Unknown')}", "success")
    except Exception as e:
        logger.exception("Hosting detection failed")
        flash(f"Hosting detection failed: {e}", "error")
    finally:
        db.close()
    return redirect(url_for("customer_detail", customer_id=customer_id))


# --- AI Search Report ---

@app.route("/api/report/generate", methods=["POST"])
@login_required
def api_generate_report():
    """Generate AI Search Optimization report for a customer."""
    customer_id = request.form.get("customer_id") or (request.json or {}).get("customer_id")
    if not customer_id:
        flash("Missing customer_id", "error")
        return redirect(url_for("customers"))

    db = get_db()
    try:
        customer = db.get_customer(customer_id)
        if not customer:
            flash("Customer not found", "error")
            return redirect(url_for("customers"))

        providers = db.get_providers(customer_id)
        services = db.get_services(customer_id)
        places = db.get_google_places(customer_id)

        from geo_agent.report_generator import generate_report
        result = generate_report(
            customer=customer,
            providers=providers,
            services=services,
            places=places,
            data_dir=DATA_DIR,
        )

        audit_log("report_generated", customer_id=customer_id, details=f"score={result['scores']['overall']}/100")
        flash(f"Report generated — score: {result['scores']['overall']}/100. "
              f"{len(result['files'])} files created.", "success")
        return redirect(url_for("customer_detail", customer_id=customer_id))
    except Exception as e:
        logger.exception("Report generation failed")
        flash(f"Report generation failed: {e}", "error")
        return redirect(url_for("customer_detail", customer_id=customer_id))
    finally:
        db.close()


@app.route("/customer/<customer_id>/report/download")
@login_required
def download_report(customer_id):
    """Download the generated report ZIP for a customer."""
    db = get_db()
    try:
        customer = db.get_customer(customer_id)
        if not customer:
            flash("Customer not found", "error")
            return redirect(url_for("customers"))

        import re as _re
        slug = _re.sub(r'[^a-z0-9]+', '-', customer['name'].lower()).strip('-')
        zip_path = Path(DATA_DIR) / "customers" / slug / f"{slug}-ai-optimization.zip"

        if not zip_path.exists():
            flash("No report found — generate one first.", "error")
            return redirect(url_for("customer_detail", customer_id=customer_id))

        return send_file(
            str(zip_path),
            mimetype="application/zip",
            as_attachment=True,
            download_name=f"{slug}-ai-optimization.zip",
        )
    finally:
        db.close()


@app.route("/customer/<customer_id>/report/download-docx")
@login_required
def download_report_docx(customer_id):
    """Download just the DOCX report for a customer."""
    db = get_db()
    try:
        customer = db.get_customer(customer_id)
        if not customer:
            flash("Customer not found", "error")
            return redirect(url_for("customers"))

        import re as _re
        slug = _re.sub(r'[^a-z0-9]+', '-', customer['name'].lower()).strip('-')
        docx_path = Path(DATA_DIR) / "customers" / slug / "ai-search-optimization-report.docx"

        if not docx_path.exists():
            flash("No report found — generate one first.", "error")
            return redirect(url_for("customer_detail", customer_id=customer_id))

        return send_file(
            str(docx_path),
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            as_attachment=True,
            download_name=f"{slug}-ai-search-report.docx",
        )
    finally:
        db.close()


# --- Landing Page Reports ---

def sync_landing_page_reports(db):
    """Pull new reports from the CF Worker KV and store in SQLite.

    Idempotent — skips reports already synced (by id).
    """
    api_url = os.environ.get(
        "PRACTICERANK_API_URL",
        "https://practicerank-api.practice-rank-ai-seo.workers.dev",
    )
    api_secret = os.environ.get("LEADS_SECRET", "")
    if not api_secret:
        return {"error": "LEADS_SECRET not configured", "synced": 0}

    resp = httpx.get(
        f"{api_url}/reports",
        headers={"Authorization": f"Bearer {api_secret}"},
        timeout=30,
    )
    resp.raise_for_status()
    remote_reports = resp.json()

    existing = {
        r["id"]
        for r in db.conn.execute("SELECT id FROM landing_page_reports").fetchall()
    }

    synced = 0
    new_prospects = 0
    for meta in remote_reports:
        if meta["id"] in existing:
            continue

        # Fetch full report for this lead
        full_resp = httpx.get(
            f"{api_url}/reports/{meta['lead_id']}",
            headers={"Authorization": f"Bearer {api_secret}"},
            timeout=30,
        )
        if full_resp.status_code != 200:
            continue

        full = full_resp.json()
        cat_scores = meta.get("meta", {}).get("category_scores", {})

        # Auto-link to existing customer by domain match
        customer_id = None
        domain_clean = (meta.get("domain", "") or "").replace("_", ".").lower()
        if domain_clean:
            match = db.conn.execute(
                "SELECT id FROM customers WHERE LOWER(domain) = ? OR LOWER(domain) LIKE ?",
                (domain_clean, f"%{domain_clean}%"),
            ).fetchone()
            if match:
                customer_id = match["id"]

        db.conn.execute(
            """INSERT INTO landing_page_reports
            (id, lead_id, customer_id, timestamp, practice_url, domain,
             vertical, email, contact_name, practice_name, city, state,
             overall_score, grade, data_confidence, revenue_lost,
             category_scores, competitor_count, full_report, synced_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                meta["id"],
                meta["lead_id"],
                customer_id,
                meta["timestamp"],
                meta.get("practice_url", ""),
                meta.get("domain", ""),
                meta.get("vertical", "dental"),
                meta.get("email", ""),
                meta.get("name", ""),
                meta.get("meta", {}).get("practice_name", ""),
                meta.get("meta", {}).get("city", ""),
                meta.get("meta", {}).get("state", ""),
                meta.get("meta", {}).get("overall_score"),
                meta.get("meta", {}).get("grade", ""),
                meta.get("meta", {}).get("data_confidence", ""),
                meta.get("meta", {}).get("revenue_lost", ""),
                json.dumps(cat_scores),
                meta.get("meta", {}).get("competitor_count", 0),
                json.dumps(full.get("report", {})),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        synced += 1

        # Auto-create a prospect from this inbound audit lead — they REQUESTED a
        # report, so they're the hottest leads. Skip if it matched an existing
        # customer (then it's a client, not a prospect). Carry the report scores so
        # the outreach templates can mail-merge the real gap.
        if customer_id is None and meta.get("email") and domain_clean:
            try:
                m = meta.get("meta", {})
                pname = m.get("practice_name") or meta.get("name") or domain_clean
                pid = re.sub(r"[^a-z0-9]+", "-", pname.lower()).strip("-")[:48] or domain_clean
                city_state = ", ".join(p for p in [m.get("city", ""), m.get("state", "")] if p)
                db.upsert_prospect(
                    pid, domain_clean, pname,
                    contact_name=meta.get("name", ""),
                    email=meta.get("email", ""),
                    vertical=meta.get("vertical", "dental"),
                    stage="new_lead",
                    report_id=meta["id"],
                    overall_score=m.get("overall_score"),
                    grade=m.get("grade", ""),
                    report_data=json.dumps(full.get("report", {})),
                    notes=f"Auto-created from inbound audit ({city_state})." if city_state else "Auto-created from inbound audit.",
                )
                new_prospects += 1
            except Exception as e:
                logger.warning(f"Auto-prospect failed for {domain_clean}: {e}")

    db.conn.commit()
    return {"synced": synced, "total": len(remote_reports), "already_synced": len(existing), "new_prospects": new_prospects}


@app.route("/reports")
@login_required
def landing_reports():
    """List all synced landing page reports. Auto-syncs from worker on load."""
    db = get_db()
    try:
        # Auto-sync on page load
        sync_result = None
        try:
            sync_result = sync_landing_page_reports(db)
        except Exception as e:
            logger.warning(f"Auto-sync failed: {e}")
            sync_result = {"error": str(e)}

        reports = db.conn.execute(
            """SELECT r.*, c.name as customer_name
               FROM landing_page_reports r
               LEFT JOIN customers c ON r.customer_id = c.id
               ORDER BY r.timestamp DESC"""
        ).fetchall()
        reports = [dict(r) for r in reports]
        for r in reports:
            if r.get("category_scores"):
                try:
                    r["category_scores"] = json.loads(r["category_scores"])
                except (json.JSONDecodeError, TypeError):
                    pass
        customers = db.list_customers()
        return render_template("reports.html", reports=reports, customers=customers, sync_result=sync_result)
    finally:
        db.close()


@app.route("/reports/<report_id>")
@login_required
def report_detail(report_id):
    """View full rendered report."""
    db = get_db()
    try:
        row = db.conn.execute(
            """SELECT r.*, c.name as customer_name
               FROM landing_page_reports r
               LEFT JOIN customers c ON r.customer_id = c.id
               WHERE r.id = ?""",
            (report_id,),
        ).fetchone()
        if not row:
            flash("Report not found.", "error")
            return redirect(url_for("landing_reports"))
        report = dict(row)
        if report.get("full_report"):
            try:
                report["full_report"] = json.loads(report["full_report"])
            except (json.JSONDecodeError, TypeError):
                pass
        if report.get("category_scores"):
            try:
                report["category_scores"] = json.loads(report["category_scores"])
            except (json.JSONDecodeError, TypeError):
                pass
        customers = db.list_customers()
        return render_template("report_detail.html", report=report, customers=customers)
    finally:
        db.close()


@app.route("/api/reports/sync", methods=["POST"])
@login_required
def api_sync_reports():
    """Trigger sync of reports from CF Worker KV."""
    db = get_db()
    try:
        result = sync_landing_page_reports(db)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Report sync failed: {e}")
        return jsonify({"error": str(e), "synced": 0}), 500
    finally:
        db.close()


@app.route("/api/reports/<report_id>/link", methods=["POST"])
@login_required
def api_link_report(report_id):
    """Link/unlink a report to a customer."""
    db = get_db()
    try:
        customer_id = (request.json or {}).get("customer_id")
        db.conn.execute(
            "UPDATE landing_page_reports SET customer_id = ? WHERE id = ?",
            (customer_id, report_id),
        )
        db.conn.commit()
        return jsonify({"ok": True})
    finally:
        db.close()


@app.route("/api/reports/<report_id>/to-pipeline", methods=["POST"])
@login_required
def api_report_to_pipeline(report_id):
    """Create a sales-pipeline prospect from an inbound audit report (manual)."""
    db = get_db()
    try:
        row = db.conn.execute(
            "SELECT * FROM landing_page_reports WHERE id = ?", (report_id,)
        ).fetchone()
        if not row:
            return jsonify({"ok": False, "error": "Report not found"}), 404
        r = dict(row)
        domain = (r.get("domain", "") or "").replace("_", ".").lower()
        if not domain:
            return jsonify({"ok": False, "error": "Report has no domain"}), 400
        pname = r.get("practice_name") or r.get("contact_name") or domain
        pid = re.sub(r"[^a-z0-9]+", "-", pname.lower()).strip("-")[:48] or domain
        city_state = ", ".join(p for p in [r.get("city", ""), r.get("state", "")] if p)
        prospect_id = db.upsert_prospect(
            pid, domain, pname,
            contact_name=r.get("contact_name", ""),
            email=r.get("email", ""),
            vertical=r.get("vertical", "dental"),
            stage="new_lead",
            report_id=report_id,
            overall_score=r.get("overall_score"),
            grade=r.get("grade", ""),
            report_data=r.get("full_report", ""),
            notes=f"From inbound audit ({city_state})." if city_state else "From inbound audit.",
        )
        audit_log("prospect_from_report", details=f"report={report_id} prospect={prospect_id}")
        return jsonify({"ok": True, "prospect_id": prospect_id})
    finally:
        db.close()


# --- Analytics ---

@app.route("/api/analytics/refresh-da", methods=["POST"])
@login_required
def api_analytics_refresh_da():
    """Pull fresh Domain Authority (+ competitors) for every active/onboarding
    customer so the analytics view is up to date."""
    db = get_db()
    try:
        from geo_agent.moz_client import track_competitor_da, track_domain_authority
        updated = 0
        for c in db.list_customers():
            if c.get("status") not in ("active", "onboarding"):
                continue
            if track_domain_authority(db, c["id"]) is not None:
                updated += 1
            track_competitor_da(db, c["id"])
        audit_log("analytics_da_refreshed", details=f"{updated} customers")
        return jsonify({"ok": True, "updated": updated})
    finally:
        db.close()


@app.route("/analytics")
@login_required
def analytics():
    """Cross-customer analytics dashboard."""
    db = get_db()
    try:
        all_customers = [c for c in db.list_customers() if c.get("status") != "archived"]

        analytics_data = []
        total_clicks = 0
        total_impressions = 0
        for c in all_customers:
            cid = c["id"]
            # KPIs
            hits_kpis = db.get_kpis(cid, "llms_txt_hits", limit=12)
            review_kpis = db.get_kpis(cid, "review_count", limit=2)
            mention_kpis = db.get_kpis(cid, "ai_mentions", limit=2)
            position_kpis = db.get_kpis(cid, "ai_avg_position", limit=2)

            def _num(kpi_list, idx=0, default=0):
                try:
                    return float(kpi_list[idx]["value"]) if len(kpi_list) > idx else default
                except (TypeError, ValueError):
                    return default

            current_hits = _num(hits_kpis)
            prev_hits = _num(hits_kpis, 1)
            current_reviews = _num(review_kpis)
            prev_reviews = _num(review_kpis, 1)
            current_mentions = _num(mention_kpis)
            avg_position = _num(position_kpis, default=None)

            # GSC data (last 30 days)
            gsc = db.get_gsc_daily(cid, limit=30)
            clicks_30d = sum(d.get("clicks", 0) for d in gsc)
            impr_30d = sum(d.get("impressions", 0) for d in gsc)
            total_clicks += clicks_30d
            total_impressions += impr_30d

            # Google Places
            places = db.get_google_places(cid)
            rating = places.get("rating") if places else None
            review_count = places.get("review_count", 0) if places else int(current_reviews)

            # Onboarding progress
            access = db.get_platform_access(cid)
            access_total = len(access)
            access_done = sum(1 for a in access if a["status"] in ("granted", "not_needed"))

            # AI mention run
            ai_run = db.get_latest_ai_run_summary(cid)
            ai_mention_rate = 0
            ai_total_queries = 0
            if ai_run:
                ai_mention_rate = ai_run.get("mention_rate", 0)
                ai_total_queries = ai_run.get("total_queries", 0)

            # SEO tasks
            checklist = db.get_checklist(cid)
            seo_tasks = _get_seo_tasks(
                checklist,
                c.get("business_type", "practice"),
                platform=c.get("platform", "webflow"),
                domain=c.get("domain", ""),
                customer_id=cid,
                city=c.get("city", ""),
            )
            seo_done = sum(1 for t in seo_tasks if t.get("done"))
            seo_total = len(seo_tasks)

            # Domain Authority (Moz) + competitor gap
            da_kpis = db.get_kpis(cid, "domain_authority", limit=2)
            da_val = _num(da_kpis, default=None)
            da_prev = _num(da_kpis, 1, default=None)
            comp_das = sorted(
                (cd.get("domain_authority") or 0 for cd in (db.get_competitor_domains(cid) or [])),
                reverse=True)
            top_comp = comp_das[0] if comp_das and comp_das[0] > 0 else None

            analytics_data.append({
                "id": cid,
                "name": c["name"],
                "domain": c["domain"],
                "status": c.get("status", "onboarding"),
                "platform": c.get("platform", ""),
                "llms_hits": current_hits,
                "llms_hits_delta": current_hits - prev_hits,
                "llms_history": [{"date": k["date"], "value": k["value"]} for k in reversed(hits_kpis[:7])],
                "reviews": review_count,
                "reviews_delta": current_reviews - prev_reviews,
                "rating": rating,
                "ai_mentions": int(current_mentions),
                "ai_mention_rate": ai_mention_rate,
                "ai_total_queries": ai_total_queries,
                "ai_position": avg_position,
                "clicks_30d": clicks_30d,
                "impressions_30d": impr_30d,
                "access_done": access_done,
                "access_total": access_total,
                "seo_done": seo_done,
                "seo_total": seo_total,
                "da": da_val,
                "da_delta": (da_val - da_prev) if (da_val is not None and da_prev is not None) else None,
                "da_date": da_kpis[0]["date"] if da_kpis else None,
                "top_competitor_da": top_comp,
                "da_gap": (top_comp - da_val) if (top_comp is not None and da_val is not None) else None,
            })

        # Aggregate stats
        active_count = sum(1 for d in analytics_data if d["status"] == "active")
        onboarding_count = sum(1 for d in analytics_data if d["status"] == "onboarding")
        totals = {
            "total_hits": sum(d["llms_hits"] for d in analytics_data),
            "total_reviews": sum(d["reviews"] for d in analytics_data),
            "total_mentions": sum(d["ai_mentions"] for d in analytics_data),
            "total_clicks": total_clicks,
            "total_impressions": total_impressions,
            "customers_tracked": len(analytics_data),
            "active_count": active_count,
            "onboarding_count": onboarding_count,
        }
        _das = [d["da"] for d in analytics_data if d["da"] is not None]
        totals["avg_da"] = round(sum(_das) / len(_das)) if _das else None
        totals["behind_competitor"] = sum(1 for d in analytics_data if d.get("da_gap") and d["da_gap"] > 0)

        return render_template("analytics.html", data=analytics_data, totals=totals)
    finally:
        db.close()


# --- Runs & Schedule ---

@app.route("/runs")
@login_required
def runs():
    """View all agent runs across customers with monthly schedule."""
    db = get_db()
    try:
        customer_filter = request.args.get("customer", "")
        all_customers = db.list_customers()

        all_runs = []
        for c in all_customers:
            if customer_filter and c["id"] != customer_filter:
                continue
            customer_runs = db.get_runs(c["id"], limit=20)
            for r in customer_runs:
                r["customer_name"] = c["name"]
                r["customer_domain"] = c["domain"]
            all_runs.extend(customer_runs)

        # Sort by date descending
        all_runs.sort(key=lambda r: r.get("run_date", ""), reverse=True)

        # Build monthly schedule for active customers
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        current_month = now.strftime("%Y-%m")

        schedule = []
        active_customers = [c for c in all_customers if c["status"] == "active"]
        staging_mgr = get_staging()

        for c in active_customers:
            latest_run = db.get_latest_run(c["id"])
            run_this_month = latest_run and latest_run.get("run_date", "")[:7] == current_month
            is_staged = staging_mgr.is_staged(c["id"])
            is_approved = staging_mgr.is_approved(c["id"])

            # Determine which phase we're in
            if latest_run and latest_run.get("status") == "published" and latest_run.get("published_at", "")[:7] == current_month:
                phase = "published"
            elif is_approved:
                phase = "approved"
            elif is_staged:
                phase = "staged"
            elif run_this_month:
                phase = "ran"
            else:
                phase = "pending"

            # Check KPIs
            has_kpis = bool(db.get_kpis(c["id"], "review_count", limit=1))

            # Check content recs
            pending_recs = db.get_pending_recommendations_count(c["id"])

            # Active alerts
            alert_count = db.get_active_alert_count(c["id"])

            schedule.append({
                "id": c["id"],
                "name": c["name"],
                "phase": phase,
                "run_date": latest_run.get("run_date", "")[:10] if latest_run else None,
                "run_status": latest_run.get("status", "") if latest_run else None,
                "has_kpis": has_kpis,
                "pending_recs": pending_recs,
                "alert_count": alert_count,
            })

        # Summary
        run_stats = {
            "total_runs": len(all_runs),
            "this_month": sum(1 for r in all_runs if r.get("run_date", "")[:7] == current_month),
            "failed": sum(1 for r in all_runs if r.get("status") == "failed"),
            "staged": sum(1 for r in all_runs if r.get("status") == "staged"),
            "approved_ready": sum(1 for s in schedule if s["phase"] == "approved"),
        }

        return render_template(
            "runs.html",
            runs=all_runs[:50],
            schedule=schedule,
            run_stats=run_stats,
            current_month=now.strftime("%B %Y"),
            all_customers=all_customers,
            customer_filter=customer_filter,
        )
    finally:
        db.close()


# --- Alerts ---

@app.route("/alerts")
@login_required
def alerts():
    """Global alerts view across all customers."""
    db = get_db()
    try:
        show_dismissed = request.args.get("dismissed") == "1"
        customer_filter = request.args.get("customer")
        all_alerts = db.get_alerts(
            customer_id=customer_filter,
            active_only=not show_dismissed,
            limit=100,
        )

        # Get customer names for display
        customer_names = {}
        for a in all_alerts:
            cid = a["customer_id"]
            if cid not in customer_names:
                c = db.get_customer(cid)
                customer_names[cid] = c["name"] if c else cid
            a["customer_name"] = customer_names[cid]

        counts = {
            "critical": sum(1 for a in all_alerts if a["severity"] == "critical" and not a.get("dismissed")),
            "warning": sum(1 for a in all_alerts if a["severity"] == "warning" and not a.get("dismissed")),
            "info": sum(1 for a in all_alerts if a["severity"] == "info" and not a.get("dismissed")),
        }

        return render_template(
            "alerts.html", alerts=all_alerts, counts=counts,
            show_dismissed=show_dismissed, customer_filter=customer_filter,
        )
    finally:
        db.close()


@app.route("/api/alert/dismiss", methods=["POST"])
@login_required
def api_dismiss_alert():
    data = request.get_json()
    alert_id = data.get("alert_id")
    if not alert_id:
        return jsonify({"error": "alert_id required"}), 400
    db = get_db()
    try:
        db.dismiss_alert(int(alert_id))
        audit_log("alert_dismissed", details=f"alert_id={alert_id}")
        return jsonify({"ok": True})
    finally:
        db.close()


# --- Content Recommendations ---

@app.route("/customer/<customer_id>/content")
@login_required
def customer_content(customer_id):
    """View content recommendations for a customer."""
    db = get_db()
    try:
        customer = db.get_customer(customer_id)
        if not customer:
            flash(f"Customer not found: {customer_id}", "error")
            return redirect(url_for("index"))

        status_filter = request.args.get("status")
        all_recs = db.get_content_recommendations(customer_id, limit=500)
        if status_filter:
            recs = [r for r in all_recs if r["status"] == status_filter]
        else:
            recs = [r for r in all_recs if r["status"] != "archived"]  # default view hides archived

        # Group by type
        grouped = {}
        for r in recs:
            grouped.setdefault(r["rec_type"], []).append(r)

        def _c(s):
            return sum(1 for r in all_recs if r["status"] == s)
        counts = {
            "pending": _c("pending"), "approved": _c("approved"),
            "published": _c("published"), "rejected": _c("rejected"),
            "archived": _c("archived"), "total": len(recs),
        }

        return render_template(
            "customer_content.html",
            customer=customer, recs=recs, grouped=grouped,
            counts=counts, status_filter=status_filter,
        )
    finally:
        db.close()


@app.route("/customer/<customer_id>/content/preview/<rec_id>")
@login_required
def content_preview(customer_id, rec_id):
    """Full-page rendered preview of a content recommendation."""
    db = get_db()
    try:
        customer = db.get_customer(customer_id)
        rec = db.get_content_recommendation(rec_id)
        if not customer or not rec or rec["customer_id"] != customer_id:
            return "Not found", 404
        return render_template("content_preview.html", customer=customer, rec=rec)
    finally:
        db.close()


@app.route("/api/content/status", methods=["POST"])
@login_required
def api_content_status():
    """Update the status of a content recommendation (approve/reject/publish)."""
    data = request.get_json()
    rec_id = data.get("rec_id", "")
    new_status = data.get("status", "")

    if new_status not in ("approved", "rejected", "published", "pending"):
        return jsonify({"error": "Invalid status"}), 400

    db = get_db()
    try:
        ok = db.update_content_recommendation_status(rec_id, new_status)
        if ok:
            rec = db.get_content_recommendation(rec_id)
            cid = rec["customer_id"] if rec else ""
            audit_log("content_status_changed", customer_id=cid, details=f"rec={rec_id} -> {new_status}")
        return jsonify({"ok": ok, "status": new_status})
    finally:
        db.close()


@app.route("/content-queue")
@login_required
def content_queue():
    """Dan's monthly content-approval queue — every pending content recommendation across
    all customers, grouped, with one-click approve/reject. This is the single 'this month's
    content to approve' surface (mirrors the FATJOE queue)."""
    db = get_db()
    try:
        groups = []
        total_pending = 0
        for cust in db.list_customers():
            recs = db.get_content_recommendations(cust["id"], status="pending", limit=200)
            if not recs:
                continue
            total_pending += len(recs)
            by_type: dict[str, int] = {}
            for r in recs:
                by_type[r.get("rec_type", "other")] = by_type.get(r.get("rec_type", "other"), 0) + 1
            groups.append({"customer": cust, "recs": recs, "count": len(recs), "by_type": by_type})
        groups.sort(key=lambda g: (-g["count"], g["customer"]["name"]))
        return render_template("content_queue.html", groups=groups, total_pending=total_pending)
    finally:
        db.close()


@app.route("/api/content/approve-all", methods=["POST"])
@login_required
def api_content_approve_all():
    """Approve all pending content recommendations for a customer."""
    data = request.get_json()
    customer_id = data.get("customer_id", "")
    if not customer_id:
        return jsonify({"error": "customer_id required"}), 400

    db = get_db()
    try:
        pending = db.get_content_recommendations(customer_id, status="pending", limit=500)

        # Confirmation gate: don't blind-approve a large batch on a single click.
        # The client must re-POST with confirm=true after the operator sees the count.
        if not data.get("confirm"):
            return jsonify({
                "needs_confirmation": True,
                "pending_count": len(pending),
                "message": (
                    f"Approve all {len(pending)} pending recommendation(s)? "
                    f"They'll still be fact-checked before publishing. "
                    f"Re-send with confirm=true to proceed."
                ),
            }), 409

        approved = 0
        for rec in pending:
            ok = db.update_content_recommendation_status(rec["id"], "approved")
            if ok:
                approved += 1
        audit_log(
            "content_approve_all", customer_id=customer_id,
            details=f"approved {approved} pending recs (confirmed)",
        )
        return jsonify({"ok": True, "approved": approved, "total": len(pending)})
    finally:
        db.close()


@app.route("/api/content/mark-all-published", methods=["POST"])
@login_required
def api_content_mark_all_published():
    """Mark every non-rejected recommendation as published.

    For when the content work was done directly on the site (not via our Webflow
    push) — flips draft/pending/approved → published so status + checklist reflect
    reality. Does NOT push to any CMS.
    """
    data = request.get_json()
    customer_id = data.get("customer_id", "")
    if not customer_id:
        return jsonify({"error": "customer_id required"}), 400

    db = get_db()
    try:
        recs = db.get_content_recommendations(customer_id, limit=500)
        targets = [r for r in recs if r.get("status") not in ("published", "rejected")]
        if not data.get("confirm"):
            return jsonify({
                "needs_confirmation": True,
                "count": len(targets),
                "message": f"Mark all {len(targets)} recommendation(s) as published? "
                           f"This won't push to any CMS — use it when the content is already live.",
            }), 409
        published = 0
        for rec in targets:
            if db.update_content_recommendation_status(rec["id"], "published"):
                published += 1
        audit_log("content_mark_all_published", customer_id=customer_id,
                  details=f"marked {published} recs published (confirmed)")
        return jsonify({"ok": True, "published": published, "total": len(targets)})
    finally:
        db.close()


@app.route("/api/content/<customer_id>/sync-published", methods=["POST"])
@login_required
def api_content_sync_published(customer_id):
    """Auto-detect which recommendations are actually live on the site and mark
    them published. Reuses the reconciler's fuzzy content-live check, so the VA
    doesn't have to manually verify+flip each one."""
    db = get_db()
    try:
        customer = db.get_customer(customer_id)
        if not customer:
            return jsonify({"ok": False, "error": "Customer not found"}), 404
        from geo_agent.status_checker import _content_is_live
        domain = customer.get("domain", "")
        recs = db.get_content_recommendations(customer_id, limit=500)
        candidates = [r for r in recs if r.get("status") in ("approved", "pending")]
        cache, published = {}, []
        for r in candidates:
            try:
                if _content_is_live(domain, r, cache):
                    db.update_content_recommendation_status(r["id"], "published")
                    published.append(r.get("title") or r["id"])
            except Exception:  # noqa: BLE001
                continue
        audit_log("content_sync_published", customer_id=customer_id,
                  details=f"{len(published)}/{len(candidates)} detected live")
        return jsonify({"ok": True, "checked": len(candidates),
                        "published": len(published), "titles": published[:25]})
    finally:
        db.close()


@app.route("/api/content/<customer_id>/archive-status", methods=["POST"])
@login_required
def api_content_archive_status(customer_id):
    """Bulk-archive every recommendation in a given status (e.g. archive all
    'rejected' or all 'published' to declutter)."""
    db = get_db()
    try:
        target_status = (request.get_json(silent=True) or {}).get("status", "")
        if target_status not in ("rejected", "published", "approved", "pending"):
            return jsonify({"ok": False, "error": "invalid status"}), 400
        recs = db.get_content_recommendations(customer_id, status=target_status, limit=500)
        n = 0
        for r in recs:
            if db.update_content_recommendation_status(r["id"], "archived"):
                n += 1
        audit_log("content_bulk_archived", customer_id=customer_id, details=f"{n} {target_status}")
        return jsonify({"ok": True, "archived": n})
    finally:
        db.close()


@app.route("/api/content/publish", methods=["POST"])
@login_required
def api_content_publish():
    """Publish approved content recommendations to Webflow or WordPress CMS."""
    data = request.get_json()
    rec_ids = data.get("rec_ids", [])
    if not rec_ids and data.get("rec_id"):
        rec_ids = [data["rec_id"]]

    if not rec_ids:
        return jsonify({"error": "rec_id or rec_ids[] required"}), 400

    db = get_db()
    try:
        # Get customer from first rec
        rec = db.get_content_recommendation(rec_ids[0])
        if not rec:
            return jsonify({"error": "Recommendation not found"}), 404

        customer_id = rec["customer_id"]
        customer = db.get_customer(customer_id)
        if not customer:
            return jsonify({"error": "Customer not found"}), 404

        platform = customer.get("platform", "webflow")

        # Gate: only publish recs that are (a) the same customer, and (b) explicitly
        # approved. Fetch each rec once and reuse the row downstream.
        requested_count = len(rec_ids)
        skipped = []
        candidates = []  # (rid, rec_row)
        for rid in rec_ids:
            r = db.get_content_recommendation(rid)
            if not r:
                skipped.append({"rec_id": rid, "ok": False, "error": "Recommendation not found"})
            elif r.get("customer_id") != customer_id:
                skipped.append({"rec_id": rid, "ok": False, "error": "Belongs to a different customer"})
            elif r.get("status") != "approved":
                skipped.append({"rec_id": rid, "ok": False, "error": f"Not approved (status={r.get('status')})"})
            else:
                candidates.append((rid, r))
        if not candidates:
            return jsonify({
                "error": "No approved recommendations to publish. Approve them first.",
                "results": skipped, "blocked": 0, "skipped": len(skipped),
            }), 400

        # YMYL backstop: fact-check each rec against the verified business profile
        # and block any with claims it can't ground (invented services/credentials,
        # uncited stats, fabricated reviews) before it reaches the live site.
        from geo_agent.fact_check import fact_check_html
        customer_obj = db.to_config_customer(customer_id)
        if customer_obj is None:
            logger.warning(f"No config customer for {customer_id}; skipping fact-check")
        fact_blocked = []
        fact_clean = []
        for rid, r in candidates:
            findings = (
                fact_check_html(customer_obj, r.get("html_snippet", ""))
                if customer_obj else []
            )
            if findings:
                fact_blocked.append({
                    "rec_id": rid, "ok": False,
                    "error": "Blocked by fact-check — unsupported claims", "findings": findings,
                })
                logger.warning(f"Fact-check blocked rec {rid}: {findings}")
            else:
                fact_clean.append(rid)
        if not fact_clean:
            return jsonify({
                "error": "All recommendations were blocked by the fact-check. Review the findings.",
                "results": skipped + fact_blocked,
                "blocked": len(fact_blocked), "skipped": len(skipped),
            }), 400
        rec_ids = fact_clean
        prefilter_results = skipped + fact_blocked

        # WordPress publishing via PracticeRank plugin
        if platform == "wordpress":
            from geo_agent.secrets import get_secrets
            wp_api_key = get_secrets().get_customer_secret(customer_id, "WP_API_KEY")
            if not wp_api_key:
                return jsonify({"error": "No WordPress API key. Install the PracticeRank SEO plugin and add the key."}), 400

            from geo_agent.publishers.wordpress import WordPressPublisher
            publisher = WordPressPublisher(
                site_url=f"https://{customer.get('domain', '')}",
                api_key=wp_api_key,
            )
            try:
                health = publisher.health_check()
                if not health:
                    return jsonify({"error": "Cannot reach WordPress PracticeRank plugin. Check the plugin is installed and active."}), 502

                results = list(prefilter_results)
                for rid in rec_ids:
                    r = db.get_content_recommendation(rid)
                    if not r or not r.get("html_snippet"):
                        results.append({"rec_id": rid, "ok": False, "error": "No generated content"})
                        continue
                    wp_type = "page" if r.get("rec_type") == "new_page" else "post"
                    result = publisher.push_content(
                        title=r.get("title", r.get("rec_title", "Untitled")),
                        content_html=r["html_snippet"],
                        content_type=wp_type,
                        slug=r.get("slug"),
                        category=r.get("category", ""),
                        meta_description=r.get("meta_description", ""),
                    )
                    if result and result.get("post_id"):
                        db.update_content_recommendation(rid, {
                            "status": "published",
                            "published_url": result.get("url", ""),
                            "wp_post_id": result["post_id"],
                        })
                        results.append({"rec_id": rid, "ok": True, "url": result.get("url"), "post_id": result["post_id"]})
                    else:
                        results.append({"rec_id": rid, "ok": False, "error": "Push failed"})

                success_count = sum(1 for r in results if r["ok"])
                audit_log("content_published", customer_id=customer_id, details=f"{success_count}/{requested_count} published to WordPress ({len(fact_blocked)} fact-blocked)")
                return jsonify({
                    "ok": success_count > 0,
                    "published": success_count,
                    "total": requested_count,
                    "blocked": len(fact_blocked),
                    "skipped": len(skipped),
                    "results": results,
                })
            finally:
                publisher.close()

        # Webflow publishing (default)
        oauth_token = db.get_webflow_oauth_token(customer_id)
        if not oauth_token:
            return jsonify({"error": "No Webflow OAuth token. Connect Webflow first."}), 400

        site_id = customer.get("webflow_site_id", "")
        if not site_id:
            return jsonify({"error": "No Webflow site_id configured for this customer."}), 400

        from geo_agent.publishers.webflow import WebflowPublisher
        from geo_agent.publishers.webflow_content import WebflowContentPublisher

        publisher = WebflowPublisher(api_key=oauth_token, site_id=site_id)
        try:
            content_pub = WebflowContentPublisher(publisher, db, customer_id)
            results = list(prefilter_results) + content_pub.publish_batch(rec_ids)
            success_count = sum(1 for r in results if r["ok"])
            audit_log("content_published", customer_id=customer_id, details=f"{success_count}/{requested_count} published to Webflow ({len(fact_blocked)} fact-blocked)")
            return jsonify({
                "ok": success_count > 0,
                "published": success_count,
                "total": requested_count,
                "blocked": len(fact_blocked),
                "skipped": len(skipped),
                "results": results,
            })
        finally:
            publisher.close()
    finally:
        db.close()


def _content_validations(db, customer_id, recs):
    """Build {rec_id: [findings]} for a docx batch so issues surface in the deliverable.

    Deterministic checks (credentials/superlatives/absolutes/future-dates) always run; the LLM
    fact-check runs best-effort (fails open on any error — the docx is a review artifact, not a
    live publish, and must still download). Closes the bypass where the docx skipped validation.
    """
    from geo_agent.content_validation import validate_html_claims

    validations = {}
    customer_obj = None
    try:
        customer_obj = db.to_config_customer(customer_id)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"docx validation: no config customer for {customer_id}: {e}")
    if customer_obj is None:
        return validations

    try:
        from geo_agent.fact_check import fact_check_html
    except Exception:  # noqa: BLE001
        fact_check_html = None

    for r in recs:
        html = r.get("html_snippet", "") or ""
        findings = list(validate_html_claims(html, customer_obj))
        if fact_check_html is not None:
            try:
                for fc in fact_check_html(customer_obj, html):
                    findings.append({
                        "severity": "block", "category": "fact-check",
                        "message": f"{fc.get('claim', '')} — {fc.get('reason', '')}".strip(" —"),
                    })
            except Exception as e:  # noqa: BLE001
                logger.warning(f"docx fact-check failed for rec {r.get('id')} (allowing): {e}")
        if findings:
            validations[r.get("id")] = findings
    return validations


@app.route("/api/content/download-docx", methods=["POST"])
@login_required
def api_content_download_docx():
    """Download DOCX for single or batch content recommendations."""
    from io import BytesIO
    from geo_agent.docx_generator import ContentDocxGenerator

    data = request.get_json()
    rec_ids = data.get("rec_ids", [])
    if not rec_ids and data.get("rec_id"):
        rec_ids = [data["rec_id"]]
    if not rec_ids:
        return jsonify({"error": "rec_id or rec_ids[] required"}), 400

    db = get_db()
    try:
        recs = [db.get_content_recommendation(rid) for rid in rec_ids]
        recs = [r for r in recs if r]
        if not recs:
            return jsonify({"error": "No recommendations found"}), 404

        customer = db.get_customer(recs[0]["customer_id"])
        if not customer:
            return jsonify({"error": "Customer not found"}), 404

        validations = _content_validations(db, recs[0]["customer_id"], recs)
        gen = ContentDocxGenerator(customer)
        if len(recs) == 1:
            buf = gen.generate_single(recs[0], validations)
            filename = f"{recs[0]['title'][:50].replace(' ', '-')}.docx"
        else:
            buf = gen.generate_batch(recs, validations)
            filename = f"{customer['name']}-content-batch.docx"

        return send_file(
            buf,
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            as_attachment=True,
            download_name=filename,
        )
    finally:
        db.close()


@app.route("/api/content/<customer_id>/download-all-approved")
@login_required
def api_content_download_all_approved(customer_id):
    """Download all approved content recommendations as one DOCX."""
    from geo_agent.docx_generator import ContentDocxGenerator

    db = get_db()
    try:
        customer = db.get_customer(customer_id)
        if not customer:
            return jsonify({"error": "Customer not found"}), 404

        recs = db.get_content_recommendations(customer_id, status="approved")
        if not recs:
            return jsonify({"error": "No approved recommendations"}), 404

        validations = _content_validations(db, customer_id, recs)
        gen = ContentDocxGenerator(customer)
        buf = gen.generate_batch(recs, validations)
        filename = f"{customer['name']}-approved-content.docx"

        return send_file(
            buf,
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            as_attachment=True,
            download_name=filename,
        )
    finally:
        db.close()


@app.route("/api/content/<customer_id>/download-all")
@login_required
def api_content_download_all(customer_id):
    """Download ALL content recommendations as one DOCX (any status)."""
    from geo_agent.docx_generator import ContentDocxGenerator

    db = get_db()
    try:
        customer = db.get_customer(customer_id)
        if not customer:
            return jsonify({"error": "Customer not found"}), 404

        recs = db.get_content_recommendations(customer_id)
        if not recs:
            return jsonify({"error": "No content recommendations"}), 404

        validations = _content_validations(db, customer_id, recs)
        gen = ContentDocxGenerator(customer)
        buf = gen.generate_batch(recs, validations)
        filename = f"{customer['name']}-all-content.docx"

        return send_file(
            buf,
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            as_attachment=True,
            download_name=filename,
        )
    finally:
        db.close()


@app.route("/api/content/push-squarespace", methods=["POST"])
@login_required
def api_content_push_squarespace():
    """Push approved content recommendations as drafts to Squarespace."""
    data = request.get_json()
    rec_ids = data.get("rec_ids", [])
    if not rec_ids and data.get("rec_id"):
        rec_ids = [data["rec_id"]]
    if not rec_ids:
        return jsonify({"error": "rec_id or rec_ids[] required"}), 400

    db = get_db()
    try:
        rec = db.get_content_recommendation(rec_ids[0])
        if not rec:
            return jsonify({"error": "Recommendation not found"}), 404

        customer_id = rec["customer_id"]
        creds = db.get_squarespace_credentials(customer_id)
        if not creds:
            return jsonify({"error": "No Squarespace credentials configured."}), 400

        from geo_agent.publishers.squarespace_content import SquarespaceContentPublisher
        import asyncio

        publisher = SquarespaceContentPublisher(
            db=db,
            customer_id=customer_id,
            email=creds["email"],
            password_encrypted=creds["password_encrypted"],
            site_url=creds["site_url"],
        )
        try:
            results = asyncio.run(publisher.publish_batch(rec_ids))
            success_count = sum(1 for r in results if r["ok"])
            audit_log("content_pushed_squarespace", customer_id=customer_id, details=f"{success_count}/{len(rec_ids)} pushed")
            return jsonify({
                "ok": success_count > 0,
                "published": success_count,
                "total": len(rec_ids),
                "results": results,
            })
        finally:
            asyncio.run(publisher.close())
    finally:
        db.close()


@app.route("/api/squarespace/credentials", methods=["POST"])
@login_required
def api_squarespace_credentials():
    """Save encrypted Squarespace login credentials."""
    data = request.get_json()
    customer_id = data.get("customer_id", "")
    email = data.get("email", "")
    password = data.get("password", "")
    site_url = data.get("site_url", "")

    if not all([customer_id, email, password, site_url]):
        return jsonify({"error": "customer_id, email, password, site_url required"}), 400

    from cryptography.fernet import Fernet
    encryption_key = os.environ.get("PRACTICERANK_ENCRYPTION_KEY", "")
    if not encryption_key:
        return jsonify({"error": "PRACTICERANK_ENCRYPTION_KEY not set"}), 500

    f = Fernet(encryption_key.encode() if isinstance(encryption_key, str) else encryption_key)
    password_encrypted = f.encrypt(password.encode()).decode()
    totp_encrypted = ""
    if data.get("totp_secret"):
        totp_encrypted = f.encrypt(data["totp_secret"].encode()).decode()

    db = get_db()
    try:
        db.save_squarespace_credentials(
            customer_id=customer_id,
            email=email,
            password_encrypted=password_encrypted,
            site_url=site_url,
            totp_secret_encrypted=totp_encrypted,
        )
        audit_log("squarespace_creds_saved", customer_id=customer_id)
        return jsonify({"ok": True})
    finally:
        db.close()


@app.route("/api/content/generate", methods=["POST"])
@login_required
def api_content_generate():
    """Trigger content recommendation generation for a customer."""
    data = request.get_json()
    customer_id = data.get("customer_id", "")

    if not customer_id:
        return jsonify({"error": "customer_id required"}), 400

    db = get_db()
    try:
        customer_obj = db.to_config_customer(customer_id)
        if not customer_obj:
            return jsonify({"error": "Customer not found"}), 404

        # Get existing recs to avoid duplicates
        existing = db.get_content_recommendations(customer_id)

        try:
            from geo_agent.content_recommender import generate_content_recommendations
            from geo_agent.crawler import get_crawler

            platform = db.get_customer(customer_id).get("platform", "generic")
            crawler = get_crawler(
                platform=platform,
                domain=customer_obj.domain,
                api_key=customer_obj.webflow_api_key,
                site_id=customer_obj.webflow_site_id,
            )
            pages = crawler.get_pages()
            crawler.close()

            recs = generate_content_recommendations(customer_obj, pages, existing_recs=existing)

            # Save to DB
            saved = 0
            for rec in recs:
                db.add_content_recommendation(rec.to_dict())
                saved += 1

            audit_log("content_generated", customer_id=customer_id, details=f"{saved} recommendations generated")
            return jsonify({"ok": True, "generated": saved})
        except Exception as e:
            logger.error(f"Content generation failed for {customer_id}: {e}")
            return jsonify({"error": f"Generation failed: {type(e).__name__}: {str(e)[:200]}"}), 500
    finally:
        db.close()


@app.route("/api/content/from-search", methods=["POST"])
@login_required
def api_content_from_search():
    """#5 — recommend this month's content from the customer's GSC query data
    (striking-distance, low-CTR, question, and untapped opportunities)."""
    data = request.get_json() or {}
    customer_id = data.get("customer_id", "")
    if not customer_id:
        return jsonify({"error": "customer_id required"}), 400
    db = get_db()
    try:
        if not db.get_customer(customer_id):
            return jsonify({"error": "Customer not found"}), 404
        from geo_agent.keyword_content import recommend_from_search_data
        created = recommend_from_search_data(db, customer_id, max_recs=8)
        if not created:
            return jsonify({"ok": True, "generated": 0,
                            "message": "No new search-data opportunities found yet — needs Search Console query data."})
        audit_log("content_from_search", customer_id=customer_id, details=f"{len(created)} recs from GSC")
        return jsonify({"ok": True, "generated": len(created)})
    finally:
        db.close()


# --- Public Content API (called by client-side blog template) ---

@app.route("/api/content/<customer_id>/by-slug/<slug>")
def api_content_by_slug(customer_id, slug):
    """Serve published blog content by slug. Supports ?locale=xx for translations.
    Falls back to English if translation not available."""
    from geo_agent.publishers.webflow_content import slugify

    locale = request.args.get("locale", "en").strip().lower()
    db = get_db()
    try:
        recs = db.get_content_recommendations(customer_id)
        for rec in recs:
            if rec["status"] == "published" and slugify(rec["title"]) == slug:
                title = rec["title"]
                description = rec.get("description", "")
                html_snippet = rec["html_snippet"]

                # If non-English locale requested, try to get translation
                if locale != "en":
                    translation = db.get_content_translation(rec["id"], locale)
                    if translation:
                        title = translation["title"]
                        description = translation.get("description", description)
                        html_snippet = translation.get("html_snippet", html_snippet)

                # Get available locales for this post
                translations = db.get_translations_for_recommendation(rec["id"])
                available_locales = ["en"] + [t["locale"] for t in translations]

                resp = jsonify({
                    "title": title,
                    "slug": slug,
                    "html_snippet": html_snippet,
                    "category": rec.get("category", ""),
                    "description": description,
                    "author": "PracticeRank",
                    "published_on": rec.get("published_at") or rec.get("created_at", ""),
                    "locale": locale if locale != "en" and db.get_content_translation(rec["id"], locale) else "en",
                    "available_locales": available_locales,
                })
                resp.headers["Access-Control-Allow-Origin"] = "*"
                return resp
        resp = jsonify({"error": "Not found"})
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp, 404
    finally:
        db.close()


@app.route("/api/content/<customer_id>/blog-posts")
def api_blog_list(customer_id):
    """List published blog posts. Supports ?locale=xx for translations.
    Falls back to English if translation not available."""
    from geo_agent.publishers.webflow_content import slugify

    locale = request.args.get("locale", "en").strip().lower()
    db = get_db()
    try:
        recs = db.get_content_recommendations(customer_id)
        posts = []
        for rec in recs:
            if rec["status"] == "published" and rec["rec_type"] in ("blog_post", "new_page"):
                title = rec["title"]
                description = rec.get("description", "")

                # If non-English locale requested, try to get translation
                if locale != "en":
                    translation = db.get_content_translation(rec["id"], locale)
                    if translation:
                        title = translation["title"]
                        description = translation.get("description", description)

                posts.append({
                    "title": title,
                    "slug": slugify(rec["title"]),  # slug always based on English title
                    "category": rec.get("category", ""),
                    "description": description,
                    "published_on": rec.get("published_at") or rec.get("created_at", ""),
                })
        resp = jsonify(posts)
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp
    finally:
        db.close()


# --- Archive / Restore ---

@app.route("/customer/<customer_id>/archive", methods=["POST"])
@login_required
def archive_customer(customer_id):
    from geo_agent.fsm import InvalidTransition
    db = get_db()
    try:
        db.set_customer_status(customer_id, "archived")
        audit_log("customer_archived", customer_id=customer_id)
        flash("Customer archived.", "success")
    except InvalidTransition as e:
        flash(f"Cannot archive: {e}", "error")
    finally:
        db.close()
    return redirect(url_for("index"))


@app.route("/customer/<customer_id>/restore", methods=["POST"])
@login_required
def restore_customer(customer_id):
    from geo_agent.fsm import InvalidTransition
    db = get_db()
    try:
        db.set_customer_status(customer_id, "onboarding")
        audit_log("customer_restored", customer_id=customer_id)
    except InvalidTransition as e:
        flash(f"Cannot restore: {e}", "error")
    finally:
        db.close()
    return redirect(url_for("customer_detail", customer_id=customer_id))


@app.route("/archived")
@login_required
def archived():
    db = get_db()
    try:
        customers = db.list_customers(status="archived")
        return render_template("archived.html", customers=customers)
    finally:
        db.close()


# --- Run Detail + Step Logs + Trigger/Retry ---

@app.route("/run/<int:run_id>")
@login_required
def run_detail(run_id):
    db = get_db()
    try:
        run = db.get_run(run_id)
        if not run:
            flash("Run not found", "error")
            return redirect(url_for("runs"))
        customer = db.get_customer(run["customer_id"])
        steps = db.get_run_steps(run_id)
        return render_template("run_detail.html", run=run, customer=customer, steps=steps)
    finally:
        db.close()


@app.route("/api/run/<int:run_id>/steps")
@login_required
def api_run_steps(run_id):
    """HTMX endpoint: return run steps partial for live polling."""
    db = get_db()
    try:
        run = db.get_run(run_id)
        if not run:
            return "", 404
        steps = db.get_run_steps(run_id)
        return render_template("partials/run_steps.html", run=run, steps=steps)
    finally:
        db.close()


# --- Staging Preview ---

@app.route("/staging/<customer_id>")
@login_required
def staging_preview(customer_id):
    """Preview all staged files for a customer in a single page."""
    staging_dir = Path(DATA_DIR) / "staging" / customer_id
    if not staging_dir.exists():
        flash("No staged changes found for this customer.", "warning")
        return redirect(url_for("customer_detail", customer_id=customer_id))

    files = {}
    for f in sorted(staging_dir.iterdir()):
        if f.name.startswith("_"):
            continue
        files[f.name] = f.read_text(errors="replace")

    db = get_db()
    try:
        customer = db.get_customer(customer_id)
    finally:
        db.close()

    return render_template("staging_preview.html", customer=customer, files=files, customer_id=customer_id)


@app.route("/staging/<customer_id>/<filename>")
@login_required
def staging_file(customer_id, filename):
    """Serve a single staged file with proper content type."""
    staging_dir = Path(DATA_DIR) / "staging" / customer_id
    filepath = staging_dir / filename
    if not filepath.exists() or ".." in filename:
        return "Not found", 404

    content = filepath.read_text(errors="replace")
    content_type = "text/plain; charset=utf-8"
    if filename.endswith(".html"):
        content_type = "text/html; charset=utf-8"
    elif filename.endswith(".json"):
        content_type = "application/json; charset=utf-8"

    return content, 200, {"Content-Type": content_type}


@app.route("/api/run/trigger", methods=["POST"])
@login_required
def api_trigger_run():
    """Trigger a full pipeline run for a customer (runs in background)."""
    import subprocess
    customer_id = request.form.get("customer_id", "").strip()
    if not customer_id:
        return jsonify({"error": "customer_id required"}), 400

    db = get_db()
    try:
        customer = db.get_customer(customer_id)
        if not customer:
            return jsonify({"error": "Customer not found"}), 404

        # FSM guard: prevent concurrent runs for the same customer
        from geo_agent.fsm import InvalidTransition
        try:
            run_id = db.create_run(customer_id)
        except InvalidTransition as e:
            if request.headers.get("HX-Request"):
                return f'<span style="color:var(--danger);font-size:0.85rem;">Already running</span>'
            flash(f"Cannot start run: {e}", "error")
            return redirect(url_for("customer_detail", customer_id=customer_id))

        db.init_run_steps(run_id)
    finally:
        db.close()

    # Launch pipeline in background
    data_dir = str(Path(DATA_DIR))
    db_path_arg = DB_PATH or str(Path(DATA_DIR) / "practicerank.db")
    cmd = [
        sys.executable, "-m", "geo_agent.main",
        "--customer", customer_id,
        "--use-db", "--db-path", db_path_arg,
        "--data-dir", data_dir,
        "--stage",
        "--run-id", str(run_id),
    ]

    log_file = Path(DATA_DIR) / "run_logs" / f"run_{run_id}.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    with open(log_file, "w") as lf:
        proc = subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT, cwd=str(Path(__file__).resolve().parent.parent))

    # Record the OS pid so the run can be truly cancelled (and reaped if orphaned).
    db2 = get_db()
    try:
        db2.conn.execute("UPDATE runs SET pid = ? WHERE id = ?", (proc.pid, run_id))
        db2.conn.commit()
    finally:
        db2.close()

    audit_log("run_triggered", customer_id=customer_id, details=f"run_id={run_id} pid={proc.pid}")
    logger.info(f"Triggered pipeline run {run_id} for {customer_id}")

    if request.headers.get("HX-Request"):
        run_url = url_for("run_detail", run_id=run_id)
        return f'<a href="{run_url}" style="font-size:0.85rem;">Run #{run_id} started &rarr;</a>'

    flash(f"Pipeline run #{run_id} triggered for {customer['name']}.", "success")
    return redirect(url_for("run_detail", run_id=run_id))


@app.route("/api/run/cancel", methods=["POST"])
@login_required
def api_cancel_run():
    """Cancel a running pipeline run."""
    customer_id = request.form.get("customer_id", "").strip()
    run_id = request.form.get("run_id", type=int)

    db = get_db()
    try:
        # Find the active run for this customer
        if run_id:
            run = db.get_run(run_id)
        elif customer_id:
            runs = db.conn.execute(
                "SELECT * FROM runs WHERE customer_id = ? AND status = 'running' ORDER BY id DESC LIMIT 1",
                (customer_id,)
            ).fetchone()
            run = dict(runs) if runs else None
            run_id = run["id"] if run else None
        else:
            return jsonify({"error": "customer_id or run_id required"}), 400

        if not run:
            if request.headers.get("HX-Request"):
                return '<span style="color:var(--warning);font-size:0.85rem;">No active run found</span>'
            return jsonify({"error": "No active run found"}), 404

        # Kill the actual pipeline subprocess so it stops spending API tokens.
        pid = run.get("pid")
        killed = False
        if pid:
            try:
                os.kill(int(pid), signal.SIGTERM)
                killed = True
            except ProcessLookupError:
                pass  # already exited
            except (OSError, ValueError) as e:
                logger.warning(f"Could not kill pid {pid} for run #{run_id}: {e}")

        db.conn.execute("UPDATE runs SET status = 'failed', errors_json = ? WHERE id = ?",
                        ('["Cancelled by user"]', run_id))
        db.conn.commit()
        audit_log("run_cancelled", customer_id=customer_id or run.get("customer_id", ""),
                  details=f"run_id={run_id} pid={pid} killed={killed}")
        logger.info(f"Cancelled run #{run_id} (pid={pid}, killed={killed}) for {customer_id or run.get('customer_id')}")

        if request.headers.get("HX-Request"):
            return f'<span style="color:var(--warning);font-size:0.85rem;">Run #{run_id} cancelled</span>'

        flash(f"Run #{run_id} cancelled.", "warning")
        return redirect(url_for("customer_detail", customer_id=customer_id or run.get("customer_id")))
    finally:
        db.close()


@app.route("/api/run/retry-step", methods=["POST"])
@login_required
def api_retry_step():
    """Reset a failed step and re-trigger the pipeline from that step."""
    import subprocess
    run_id = request.form.get("run_id", type=int)
    step_name = request.form.get("step_name", "").strip()
    if not run_id or not step_name:
        return jsonify({"error": "run_id and step_name required"}), 400

    db = get_db()
    try:
        run = db.get_run(run_id)
        if not run:
            return jsonify({"error": "Run not found"}), 404

        step_names = [s[0] for s in db.PIPELINE_STEPS]
        if step_name not in step_names:
            return jsonify({"error": f"Unknown step: {step_name}"}), 400

        # Reset this step and all subsequent steps
        idx = step_names.index(step_name)
        for sn in step_names[idx:]:
            db.reset_step(run_id, sn)

        # Update run status back to running
        db.update_run(run_id, status="running")
    finally:
        db.close()

    # Re-trigger pipeline from this step
    data_dir = str(Path(DATA_DIR))
    db_path_arg = DB_PATH or str(Path(DATA_DIR) / "practicerank.db")
    cmd = [
        sys.executable, "-m", "geo_agent.main",
        "--customer", run["customer_id"],
        "--use-db", "--db-path", db_path_arg,
        "--data-dir", data_dir,
        "--stage",
        "--resume-from", step_name,
        "--run-id", str(run_id),
    ]

    log_file = Path(DATA_DIR) / "run_logs" / f"run_{run_id}.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    with open(log_file, "a") as lf:
        lf.write(f"\n\n--- RETRY from {step_name} at {datetime.now(timezone.utc).isoformat()} ---\n\n")
        subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT, cwd=str(Path(__file__).resolve().parent.parent))

    logger.info(f"Retrying run {run_id} from step {step_name}")
    flash(f"Retrying step '{step_name}' and all subsequent steps for run #{run_id}", "success")
    return redirect(url_for("run_detail", run_id=run_id))


@app.route("/api/run/logs/<int:run_id>")
@login_required
def api_run_logs(run_id):
    """Get raw log output for a run."""
    log_file = Path(DATA_DIR) / "run_logs" / f"run_{run_id}.log"
    if log_file.exists():
        return log_file.read_text(), 200, {"Content-Type": "text/plain"}
    return "No log file found for this run.", 404, {"Content-Type": "text/plain"}


# --- SEO Tools: Integrations, Keywords, Audits, Backlinks, Topics ---


@app.route("/api/customer/<customer_id>/integrations", methods=["GET"])
@login_required
def api_get_integrations(customer_id):
    """Get all integrations for a customer."""
    db = get_db()
    try:
        integrations = db.get_integrations(customer_id)
        # Fill in defaults for unconfigured integrations
        configured = {i["integration"] for i in integrations}
        defaults = ["gsc", "google_places", "pagespeed", "ga4", "brightlocal"]
        for name in defaults:
            if name not in configured:
                integrations.append({
                    "integration": name, "status": "not_configured",
                    "config": {}, "last_checked": None, "last_error": None,
                })
        return jsonify({"ok": True, "integrations": integrations})
    finally:
        db.close()


@app.route("/api/customer/<customer_id>/integrations", methods=["POST"])
@login_required
def api_save_integration(customer_id):
    """Save an integration config for a customer."""
    data = request.get_json()
    integration = data.get("integration", "")
    config = data.get("config", {})
    if not integration:
        return jsonify({"error": "Missing integration name"}), 400

    db = get_db()
    try:
        db.save_integration(customer_id, integration, config, status="configured")
        audit_log("integration_saved", customer_id=customer_id,
                  details=f"{integration}: {json.dumps(config)}")
        return jsonify({"ok": True})
    finally:
        db.close()


@app.route("/api/customer/<customer_id>/integrations/<integration>/test", methods=["POST"])
@login_required
def api_test_integration(customer_id, integration):
    """Test an integration connection."""
    db = get_db()
    try:
        integ = db.get_integration(customer_id, integration)
        if not integ:
            return jsonify({"ok": False, "error": "Integration not configured"}), 400

        if integration == "gsc":
            try:
                from geo_agent.gsc_client import _build_service, _resolve_site_url
                service = _build_service()
                if service is None:
                    db.update_integration_status(customer_id, integration, "error",
                                                 "GSC service account not configured (set GSC_SERVICE_ACCOUNT_JSON or GSC_SERVICE_ACCOUNT_KEY)")
                    return jsonify({"ok": False, "error": "GSC service account not configured on server"})
                property_url = integ["config"].get("property_url", "")
                if not property_url:
                    customer = db.get_customer(customer_id)
                    domain = customer["domain"] if customer else ""
                    property_url = _resolve_site_url(service, domain)
                    if property_url:
                        integ["config"]["property_url"] = property_url
                        db.save_integration(customer_id, integration, integ["config"], "active")
                # Try a test query
                from geo_agent.gsc_client import fetch_search_metrics
                from datetime import timedelta
                end = datetime.now(timezone.utc) - timedelta(days=2)
                start = end - timedelta(days=3)
                result = fetch_search_metrics(
                    property_url,
                    start.strftime("%Y-%m-%d"),
                    end.strftime("%Y-%m-%d"),
                )
                if result is not None:
                    db.update_integration_status(customer_id, integration, "active")
                    return jsonify({"ok": True, "message": f"Connected! Found {len(result)} days of data.", "property_url": property_url})
                else:
                    db.update_integration_status(customer_id, integration, "error", "Query returned no data")
                    return jsonify({"ok": False, "error": "GSC query failed — check that the service account has access to this property"})
            except ImportError:
                return jsonify({"ok": False, "error": "google-api-python-client not installed on server"})
        elif integration == "ga4":
            from geo_agent.ga4_client import test_connection as ga4_test
            return jsonify(ga4_test(db, customer_id))
        elif integration == "brightlocal":
            import os as _os
            if not _os.environ.get("BRIGHTLOCAL_API_KEY"):
                return jsonify({"ok": False, "error": "BRIGHTLOCAL_API_KEY not set on server."})
            if not integ["config"].get("location_id"):
                return jsonify({"ok": False, "error": "No BrightLocal location_id configured for this customer."})
            from geo_agent.brightlocal_client import track_citations
            n = track_citations(db, customer_id)
            if n is None:
                return jsonify({"ok": False, "error": "BrightLocal request failed — check API key and location_id."})
            db.update_integration_status(customer_id, integration, "active")
            return jsonify({"ok": True, "message": f"Connected! Synced {n} citation(s)."})
        elif integration == "pagespeed":
            # PageSpeed always works (free, no key)
            db.update_integration_status(customer_id, integration, "active")
            return jsonify({"ok": True, "message": "PageSpeed Insights API is free and requires no configuration."})
        else:
            return jsonify({"ok": False, "error": f"Unknown integration: {integration}"}), 400
    finally:
        db.close()


# --- Keywords ---

def _auto_generate_keywords(db, customer_id: str) -> list[str]:
    """Generate keyword suggestions from customer data."""
    customer = db.get_customer(customer_id)
    if not customer:
        return []
    city = customer.get("city", "")
    state = customer.get("state", "")
    name = customer["name"]
    biz_type = customer.get("business_type", "practice")
    services = db.get_services(customer_id)
    specialties = customer.get("specialties", [])

    keywords = []
    location = f"{city} {state}".strip() if city else ""

    # Service + location combos
    for svc in services:
        svc_name = svc["name"].lower()
        if location:
            keywords.append(f"{svc_name} {city.lower()}")
            keywords.append(f"best {svc_name} {city.lower()}")
        keywords.append(f"{svc_name} near me")

    # Specialty combos
    for spec in (specialties or []):
        spec_lower = spec.lower()
        if location:
            keywords.append(f"{spec_lower} {city.lower()}")

    # Business type combos
    type_labels = {
        "practice": "dentist", "dental": "dentist", "legal": "lawyer",
        "medical": "doctor", "veterinary": "vet",
    }
    label = type_labels.get(biz_type, biz_type)
    if location:
        keywords.append(f"{label} {city.lower()}")
        keywords.append(f"best {label} {city.lower()}")
    keywords.append(f"{label} near me")

    # Brand keywords
    keywords.append(f"{name.lower()} reviews")
    keywords.append(name.lower())

    return list(set(k.strip() for k in keywords if k.strip()))


@app.route("/api/customer/<customer_id>/keywords", methods=["GET"])
@login_required
def api_get_keywords(customer_id):
    db = get_db()
    try:
        keywords = db.get_keyword_summary(customer_id)
        return jsonify({"ok": True, "keywords": keywords})
    finally:
        db.close()


@app.route("/api/customer/<customer_id>/keywords", methods=["POST"])
@login_required
def api_add_keywords(customer_id):
    data = request.get_json()
    keywords = data.get("keywords", [])
    if isinstance(keywords, str):
        keywords = [k.strip() for k in keywords.split(",") if k.strip()]
    if not keywords:
        return jsonify({"error": "No keywords provided"}), 400

    db = get_db()
    try:
        added = 0
        for kw in keywords:
            if db.add_tracked_keyword(customer_id, kw, source="manual"):
                added += 1
        audit_log("keywords_added", customer_id=customer_id, details=f"Added {added} keywords")
        return jsonify({"ok": True, "added": added, "total": len(keywords)})
    finally:
        db.close()


@app.route("/api/customer/<customer_id>/keywords/delete", methods=["POST"])
@login_required
def api_delete_keyword(customer_id):
    data = request.get_json()
    keyword = data.get("keyword", "")
    if not keyword:
        return jsonify({"error": "No keyword provided"}), 400
    db = get_db()
    try:
        db.remove_tracked_keyword(customer_id, keyword)
        audit_log("keyword_removed", customer_id=customer_id, details=keyword)
        return jsonify({"ok": True})
    finally:
        db.close()


@app.route("/api/customer/<customer_id>/keywords/auto-generate", methods=["POST"])
@login_required
def api_auto_generate_keywords(customer_id):
    db = get_db()
    try:
        suggestions = _auto_generate_keywords(db, customer_id)
        existing = {k["keyword"] for k in db.get_tracked_keywords(customer_id)}
        new_keywords = [k for k in suggestions if k not in existing]
        added = 0
        for kw in new_keywords:
            if db.add_tracked_keyword(customer_id, kw, source="auto"):
                added += 1
        audit_log("keywords_auto_generated", customer_id=customer_id, details=f"Added {added} of {len(suggestions)} suggestions")
        return jsonify({"ok": True, "added": added, "suggestions": suggestions})
    finally:
        db.close()


@app.route("/api/customer/<customer_id>/keywords/pull-gsc", methods=["POST"])
@login_required
def api_pull_keyword_ranks(customer_id):
    """Pull keyword rank data from GSC for tracked keywords."""
    db = get_db()
    try:
        integ = db.get_integration(customer_id, "gsc")
        if not integ or integ["status"] != "active":
            return jsonify({"ok": False, "error": "GSC integration not configured or not active. Set it up in the Integrations section."}), 400

        property_url = integ["config"].get("property_url", "")
        if not property_url:
            return jsonify({"ok": False, "error": "GSC property URL not set"}), 400

        try:
            from geo_agent.gsc_client import fetch_search_metrics
        except ImportError:
            return jsonify({"ok": False, "error": "google-api-python-client not installed"}), 500

        from datetime import timedelta
        end_date = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%d")
        start_date = (datetime.now(timezone.utc) - timedelta(days=92)).strftime("%Y-%m-%d")

        # Aggregate by query over 90 days (NOT per-day) so a query with steady low daily
        # impressions still surfaces — the old 7-day + "≥10 impressions in a single day"
        # filter collapsed thousands of real queries down to a handful.
        data = fetch_search_metrics(property_url, start_date, end_date, dimensions=["query"])
        if data is None:
            return jsonify({"ok": False, "error": "GSC query failed"}), 500

        # Keep queries with any meaningful volume, ranked by impressions; cap so we don't
        # import the long-tail noise floor. Snapshot the aggregate rank against end_date.
        rows = sorted(
            (r for r in data if r.get("impressions", 0) >= 3),
            key=lambda r: r.get("impressions", 0), reverse=True,
        )[:200]

        tracked = {k["keyword"] for k in db.get_tracked_keywords(customer_id)}
        updated = 0
        discovered = 0
        for row in rows:
            query = row.get("query", "").lower().strip()
            if not query:
                continue
            if query not in tracked:
                if db.add_tracked_keyword(customer_id, query, source="gsc_discovered"):
                    discovered += 1
            db.save_keyword_rank(customer_id, query, end_date,
                                 row.get("position"), row.get("clicks", 0),
                                 row.get("impressions", 0), row.get("ctr", 0.0))
            updated += 1
        data = rows

        audit_log("keyword_ranks_pulled", customer_id=customer_id,
                  details=f"Updated {updated} ranks, discovered {discovered} new keywords")
        return jsonify({"ok": True, "updated": updated, "discovered": discovered,
                        "total_rows": len(data)})
    finally:
        db.close()


# --- Site Audits ---

@app.route("/api/customer/<customer_id>/audit/run", methods=["POST"])
@login_required
def api_run_audit(customer_id):
    """Run a site audit for a customer."""
    db = get_db()
    try:
        customer = db.get_customer(customer_id)
        if not customer:
            return jsonify({"error": "Customer not found"}), 404

        from geo_agent.site_auditor import run_site_audit
        result = run_site_audit(customer["domain"], customer.get("platform", ""))
        audit_id = db.save_site_audit(
            customer_id, result["audit_date"],
            result["scores"], result["issues"], result.get("raw_data"),
        )
        audit_log("site_audit_run", customer_id=customer_id,
                  details=f"Scores: perf={result['scores'].get('performance')}, seo={result['scores'].get('seo')}, issues={len(result['issues'])}")
        return jsonify({"ok": True, "audit_id": audit_id, "scores": result["scores"],
                        "issues_count": len(result["issues"])})
    finally:
        db.close()


@app.route("/api/customer/<customer_id>/audit/latest", methods=["GET"])
@login_required
def api_get_audit(customer_id):
    db = get_db()
    try:
        audit = db.get_latest_audit(customer_id)
        issues = db.get_audit_issues(customer_id) if audit else []
        return jsonify({"ok": True, "audit": audit, "issues": issues})
    finally:
        db.close()


@app.route("/api/customer/<customer_id>/audit/issues/<int:issue_id>/status", methods=["POST"])
@login_required
def api_update_audit_issue(customer_id, issue_id):
    data = request.get_json()
    status = data.get("status", "")
    if status not in ("open", "fixed", "ignored"):
        return jsonify({"error": "Invalid status"}), 400
    db = get_db()
    try:
        db.update_audit_issue_status(issue_id, status)
        audit_log("audit_issue_updated", customer_id=customer_id,
                  details=f"Issue {issue_id} -> {status}")
        return jsonify({"ok": True})
    finally:
        db.close()


# --- Backlinks ---

@app.route("/api/customer/<customer_id>/backlinks", methods=["GET"])
@login_required
def api_get_backlinks(customer_id):
    db = get_db()
    try:
        backlinks = db.get_backlinks(customer_id)
        return jsonify({"ok": True, "backlinks": backlinks})
    finally:
        db.close()


@app.route("/api/customer/<customer_id>/backlinks/pull", methods=["POST"])
@login_required
def api_pull_backlinks(customer_id):
    """Pull backlinks from GSC."""
    db = get_db()
    try:
        integ = db.get_integration(customer_id, "gsc")
        if not integ or integ["status"] != "active":
            return jsonify({"ok": False, "error": "GSC integration not active"}), 400

        property_url = integ["config"].get("property_url", "")
        if not property_url:
            return jsonify({"ok": False, "error": "GSC property URL not set"}), 400

        try:
            from geo_agent.gsc_client import _build_service
        except ImportError:
            return jsonify({"ok": False, "error": "google-api-python-client not installed"}), 500

        service = _build_service()
        if not service:
            return jsonify({"ok": False, "error": "GSC service unavailable"}), 500

        # Use GSC Links API to get external linking domains
        links = []
        try:
            response = service.links().list(siteUrl=property_url).execute()
            for item in response.get("items", []):
                links.append({
                    "domain": item.get("siteUrl", "").replace("http://", "").replace("https://", "").rstrip("/"),
                    "count": item.get("count", 0),
                })
        except Exception:
            pass

        # If links API didn't work, try searchanalytics for referring pages
        if not links:
            try:
                from datetime import timedelta as _td
                # Get pages that link to our site via search referrals
                response = service.searchanalytics().query(
                    siteUrl=property_url,
                    body={
                        "startDate": (datetime.now(timezone.utc) - _td(days=90)).strftime("%Y-%m-%d"),
                        "endDate": (datetime.now(timezone.utc) - _td(days=1)).strftime("%Y-%m-%d"),
                        "dimensions": ["page"],
                        "rowLimit": 100,
                    },
                ).execute()
                seen_domains = set()
                customer_domain = property_url.replace("sc-domain:", "").replace("https://", "").replace("http://", "").rstrip("/")
                for row in response.get("rows", []):
                    page_url = row.get("keys", [""])[0]
                    try:
                        domain = urlparse(page_url).netloc
                        if domain and domain not in seen_domains and customer_domain not in domain:
                            seen_domains.add(domain)
                            links.append({"domain": domain, "count": row.get("clicks", 1)})
                    except Exception:
                        pass
            except Exception:
                pass

        if links:
            summary = db.save_backlinks(customer_id, links)
            audit_log("backlinks_pulled", customer_id=customer_id,
                      details=f"{summary['total']} total, {summary['new']} new, {summary['lost']} lost")
            return jsonify({"ok": True, **summary})
        else:
            return jsonify({"ok": True, "message": "No backlink data available from GSC. This requires a verified property with incoming links.", "total": 0, "new": 0, "lost": 0})
    finally:
        db.close()


# --- Content Topics ---

@app.route("/api/customer/<customer_id>/topics", methods=["GET"])
@login_required
def api_get_topics(customer_id):
    db = get_db()
    try:
        topics = db.get_content_topics(customer_id)
        return jsonify({"ok": True, "topics": topics})
    finally:
        db.close()


@app.route("/api/customer/<customer_id>/topics", methods=["POST"])
@login_required
def api_add_topic(customer_id):
    data = request.get_json()
    topic = data.get("topic", "").strip()
    keyword = data.get("target_keyword", "").strip()
    priority = data.get("priority", "medium")
    if not topic:
        return jsonify({"error": "Topic is required"}), 400
    db = get_db()
    try:
        topic_id = db.add_content_topic(customer_id, topic, keyword,
                                        source="manual", priority=priority)
        audit_log("topic_added", customer_id=customer_id, details=topic)
        return jsonify({"ok": True, "topic_id": topic_id})
    finally:
        db.close()


@app.route("/api/customer/<customer_id>/topics/<int:topic_id>/status", methods=["POST"])
@login_required
def api_update_topic_status(customer_id, topic_id):
    data = request.get_json()
    status = data.get("status", "")
    if status not in ("suggested", "approved", "in_progress", "published", "rejected"):
        return jsonify({"error": "Invalid status"}), 400
    db = get_db()
    try:
        db.update_content_topic_status(topic_id, status)
        audit_log("topic_status_updated", customer_id=customer_id,
                  details=f"Topic {topic_id} -> {status}")
        return jsonify({"ok": True})
    finally:
        db.close()


# --- Tier 2: Competitor Domains API ---


@app.route("/api/customer/<customer_id>/competitors", methods=["GET", "POST", "DELETE"])
@login_required
def api_competitor_domains(customer_id):
    db = get_db()
    try:
        if request.method == "POST":
            data = request.get_json()
            db.add_competitor_domain(
                customer_id, data["domain"], data.get("name", ""), data.get("discovered_via", "manual")
            )
            audit_log("add_competitor", customer_id, details=f"Added competitor: {data['domain']}")
            return jsonify({"ok": True})
        elif request.method == "DELETE":
            data = request.get_json()
            db.remove_competitor_domain(customer_id, data["domain"])
            audit_log("remove_competitor", customer_id, details=f"Removed competitor: {data['domain']}")
            return jsonify({"ok": True})
        else:
            return jsonify({"ok": True, "competitors": db.get_competitor_domains(customer_id)})
    finally:
        db.close()


@app.route("/api/customer/<customer_id>/competitors/ai-comparison")
@login_required
def api_competitor_ai_comparison(customer_id):
    """Compare AI mention rates between this customer and their competitors."""
    db = CustomerDB()
    try:
        # Get this customer's latest AI run
        runs = db.get_ai_mention_runs(customer_id, limit=1)
        business = None
        if runs:
            r = runs[0]
            business = {
                "name": db.get_customer(customer_id).get("name", customer_id),
                "mention_rate": r.get("mention_rate", 0) or 0,
                "total_mentions": r.get("total_mentions", 0),
                "total_queries": r.get("total_queries", 0),
            }

        # Get competitor data from competitor_analysis if available
        competitors = db.get_competitors(customer_id)
        comp_data = []
        for c in competitors[:8]:
            comp_ai = c.get("ai_mention_rate")
            if comp_ai is not None:
                comp_data.append({
                    "name": c.get("name", c.get("domain", "?")),
                    "mention_rate": comp_ai,
                })
            else:
                # Check if competitor has their own AI mention runs (if they're also a customer)
                comp_domain = c.get("domain", "")
                # Just include basic info
                comp_data.append({
                    "name": c.get("name", comp_domain),
                    "mention_rate": None,
                })

        # Filter to only competitors with data
        comp_with_data = [c for c in comp_data if c["mention_rate"] is not None]
        return jsonify({
            "ok": True,
            "business": business,
            "competitors": comp_with_data,
        })
    finally:
        db.close()


@app.route("/api/customer/<customer_id>/competitors/discover", methods=["POST"])
@login_required
def api_discover_competitors(customer_id):
    """Auto-discover competitors using Google Places nearby search (~15-25 min drive)."""
    db = get_db()
    try:
        customer = db.get_customer(customer_id)
        if not customer:
            return jsonify({"ok": False, "error": "Customer not found"}), 404

        places = db.get_google_places(customer_id)
        if not places or not places.get("lat") or not places.get("lng"):
            return jsonify({"ok": False, "error": "No location data. Run agent first to detect Google Places data."}), 400

        api_key = os.environ.get("GOOGLE_PLACES_API_KEY", "")
        if not api_key:
            return jsonify({"ok": False, "error": "GOOGLE_PLACES_API_KEY not configured"}), 500

        from geo_agent.google_places import fetch_nearby_competitors

        # Clean up existing dirty domains (one-time fix for UTM params)
        existing = db.get_competitor_domains(customer_id)
        for comp in existing:
            old_domain = comp["competitor_domain"]
            if "?" in old_domain or "utm_" in old_domain or old_domain.startswith("www."):
                parsed = urlparse("https://" + old_domain if "://" not in old_domain else old_domain)
                clean = (parsed.netloc or parsed.path.split("/")[0]).replace("www.", "")
                if clean and clean != old_domain:
                    try:
                        db.remove_competitor_domain(customer_id, old_domain)
                        db.add_competitor_domain(customer_id, clean, comp.get("competitor_name", ""),
                                                 comp.get("discovered_via", "auto_discovered"),
                                                 comp.get("rating", 0), comp.get("review_count", 0),
                                                 comp.get("address", ""), comp.get("place_id", ""))
                    except Exception:
                        pass

        # ~15-25 min drive = ~16km radius
        radius = int(request.get_json(silent=True, force=True).get("radius", 16000) if request.get_json(silent=True, force=True) else 16000)
        max_results = 15

        # Determine place types based on business_type
        from geo_agent.google_places import get_place_types, validate_competitors
        bt = (customer.get("business_type") or "practice").lower()
        place_types = get_place_types(bt)

        # Build text query for industries without a Google place type
        text_query = ""
        if not place_types:
            specialties = customer.get("specialties") or []
            if isinstance(specialties, str):
                import json as _json
                try:
                    specialties = _json.loads(specialties)
                except Exception:
                    specialties = [specialties]
            city = customer.get("city", "")
            state = customer.get("state", "")
            if specialties:
                text_query = f"{specialties[0]} near {city} {state}".strip()
            elif bt not in ("practice", ""):
                text_query = f"{bt} near {city} {state}".strip()

        comps = fetch_nearby_competitors(
            lat=places["lat"], lng=places["lng"],
            practice_name=customer["name"],
            api_key=api_key,
            radius_meters=radius,
            max_results=max_results,
            place_types=place_types or None,
            text_query=text_query,
        )
        # Validate competitors — filter wrong-industry results
        comps = validate_competitors(comps, bt)

        added = 0
        for c in comps:
            try:
                # Clean domain: strip UTM params and extract hostname
                clean_domain = ""
                if c.website:
                    parsed = urlparse(c.website if "://" in c.website else "https://" + c.website)
                    clean_domain = parsed.netloc or parsed.path.split("/")[0]
                    clean_domain = clean_domain.replace("www.", "")
                if not clean_domain:
                    clean_domain = c.name.lower().replace(" ", "-").replace("&", "and")

                db.add_competitor_domain(
                    customer_id,
                    clean_domain,
                    c.name,
                    "auto_discovered",
                    rating=c.rating,
                    review_count=c.review_count,
                    address=c.address,
                    place_id=c.place_id,
                )
                added += 1
            except Exception:
                pass  # duplicate

        audit_log("competitors_discovered", customer_id=customer_id,
                  details=f"Found {len(comps)}, added {added} new (radius={radius}m)")
        return jsonify({"ok": True, "found": len(comps), "added": added})
    except Exception as e:
        logger.warning(f"Competitor discovery failed for {customer_id}: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        db.close()


@app.route("/api/customer/<customer_id>/competitors/analyze", methods=["POST"])
@login_required
def api_analyze_competitor(customer_id):
    """Compare AI mention visibility between customer and a competitor."""
    db = get_db()
    try:
        data = request.get_json()
        competitor_name = data.get("competitor_name", "")
        if not competitor_name:
            return jsonify({"ok": False, "error": "No competitor name"}), 400

        customer = db.get_customer(customer_id)
        if not customer:
            return jsonify({"ok": False, "error": "Customer not found"}), 404

        # Get customer's latest AI mention run results
        runs = db.get_ai_mention_runs(customer_id, limit=1)
        if not runs:
            return jsonify({"ok": False, "error": "No AI mention data. Run an AI mention check first."}), 400

        latest_run = runs[0]
        run_results = db.get_ai_mention_results(latest_run["run_id"])

        # Count where customer is mentioned vs competitor
        your_mentions = 0
        their_mentions = 0
        total_queries = len(run_results)
        queries_they_win = []

        customer_name_lower = customer["name"].lower()
        competitor_lower = competitor_name.lower()

        for r in run_results:
            response_text = (r.get("response_text") or "").lower()
            you_mentioned = customer_name_lower in response_text or (customer.get("domain") or "").lower() in response_text
            they_mentioned = competitor_lower in response_text

            if you_mentioned:
                your_mentions += 1
            if they_mentioned:
                their_mentions += 1
            if they_mentioned and not you_mentioned:
                queries_they_win.append(r.get("query", "unknown"))

        # Generate insights
        insights = []
        if their_mentions > your_mentions:
            insights.append(f"{competitor_name} is mentioned {their_mentions - your_mentions} more times across AI searches.")
        elif your_mentions > their_mentions:
            insights.append(f"You're ahead by {your_mentions - their_mentions} mentions across AI searches.")
        else:
            insights.append("You and this competitor have equal AI visibility.")

        if queries_they_win:
            insights.append(f"They appear in {len(queries_they_win)} queries where you don't — these are your opportunities.")

        your_rate = (your_mentions / total_queries * 100) if total_queries > 0 else 0
        their_rate = (their_mentions / total_queries * 100) if total_queries > 0 else 0
        if their_rate > 30 and your_rate < 20:
            insights.append("They have strong AI presence. Focus on structured data, FAQ schema, and llms.txt.")

        return jsonify({
            "ok": True,
            "result": {
                "your_mentions": your_mentions,
                "their_mentions": their_mentions,
                "total_queries": total_queries,
                "you_win": your_mentions >= their_mentions,
                "queries_they_win": queries_they_win[:5],
                "insights": insights,
            },
        })
    except Exception as e:
        logger.warning(f"Competitor analysis failed for {customer_id}: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        db.close()


# --- Tier 2: Citations API ---


@app.route("/api/customer/<customer_id>/citations", methods=["GET", "POST"])
@login_required
def api_citations(customer_id):
    db = get_db()
    try:
        if request.method == "POST":
            data = request.get_json()
            db.save_citation(
                customer_id,
                data["directory"],
                data.get("listed", False),
                data.get("nap_match", False),
                data.get("url_correct", False),
                data.get("listing_url", ""),
            )
            return jsonify({"ok": True})
        else:
            return jsonify({"ok": True, "citations": db.get_citations(customer_id)})
    finally:
        db.close()


# --- Tier 2: Reviews API ---


@app.route("/api/customer/<customer_id>/reviews", methods=["GET"])
@login_required
def api_reviews(customer_id):
    db = get_db()
    try:
        reviews = db.get_reviews(customer_id)
        stats = db.get_review_stats(customer_id)
        return jsonify({"ok": True, "reviews": reviews, "stats": stats})
    finally:
        db.close()


# --- Proof-of-improvement report (internal view + shareable client link) ---

def _proof_serializer():
    from itsdangerous import URLSafeSerializer
    return URLSafeSerializer(app.secret_key, salt="practicerank-proof")


@app.route("/customer/<customer_id>/proof")
@login_required
def customer_proof(customer_id):
    """Consolidated into the one weekly report — send staff to the Weekly Report tab
    (view, share link, history) instead of a separate proof page."""
    return redirect(url_for("customer_detail", customer_id=customer_id) + "#reports")


@app.route("/proof/<token>")
def public_proof(token):
    """Public client link → the one consolidated report (the comprehensive weekly
    report). Signed token encodes the customer; always shows the current report."""
    from itsdangerous import BadSignature
    try:
        customer_id = _proof_serializer().loads(token)
    except BadSignature:
        abort(404)
    db = get_db()
    try:
        from geo_agent import weekly_report as wr
        html = wr.render_html(wr.build_report_data(db, customer_id))
        resp = Response(html, mimetype="text/html")
        resp.headers["Cache-Control"] = "private, no-store"
        resp.headers["X-Robots-Tag"] = "noindex, nofollow"
        return resp
    finally:
        db.close()


def _gap_serializer():
    from itsdangerous import URLSafeSerializer
    return URLSafeSerializer(app.secret_key, salt="practicerank-ai-gap")


@app.route("/customer/<customer_id>/ai-gap")
@login_required
def customer_ai_gap(customer_id):
    """Internal AI-gap one-pager (the outreach 'you're invisible' asset) + share link."""
    db = get_db()
    try:
        from geo_agent.proof import build_ai_gap
        gap = build_ai_gap(db, customer_id)
        token = _gap_serializer().dumps(customer_id)
        share_url = url_for("public_ai_gap", token=token, _external=True)
        return render_template("ai_gap.html", gap=gap, public=False, share_url=share_url)
    finally:
        db.close()


@app.route("/gap/<token>")
def public_ai_gap(token):
    """Public, read-only AI-gap one-pager via a signed link (for prospect outreach)."""
    from itsdangerous import BadSignature
    try:
        customer_id = _gap_serializer().loads(token)
    except BadSignature:
        abort(404)
    db = get_db()
    try:
        from geo_agent.proof import build_ai_gap
        gap = build_ai_gap(db, customer_id)
        return render_template("ai_gap.html", gap=gap, public=True, share_url=None)
    finally:
        db.close()


def reap_stale_runs():
    """Mark runs left in 'running' with a dead/missing pid as failed.

    A container restart orphans subprocesses, leaving runs stuck in 'running'
    forever. Runs this once at startup (works under gunicorn workers too).
    """
    def _pid_alive(pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except OSError:
            return True  # exists but not ours — assume alive

    try:
        db = get_db()
        try:
            rows = db.conn.execute("SELECT id, pid FROM runs WHERE status = 'running'").fetchall()
            reaped = 0
            for row in rows:
                pid = row["pid"]
                if not pid or not _pid_alive(int(pid)):
                    db.conn.execute(
                        "UPDATE runs SET status = 'failed', errors_json = ? WHERE id = ?",
                        ('["Orphaned run reaped at startup"]', row["id"]),
                    )
                    reaped += 1
            if reaped:
                db.conn.commit()
                logger.info(f"Reaped {reaped} orphaned run(s) at startup")
        finally:
            db.close()
    except Exception as e:  # never block startup on the reaper
        logger.warning(f"reap_stale_runs failed: {e}")


reap_stale_runs()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PracticeRank Dashboard")
    parser.add_argument("--port", type=int, default=5099)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--db", default=None, help="Database file path")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    DB_PATH = args.db
    app.run(host=args.host, port=args.port, debug=args.debug)
