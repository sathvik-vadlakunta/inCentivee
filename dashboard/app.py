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
import sys
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Load .env before anything else
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file

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

# Globals set at startup
DB_PATH: str | None = None
DATA_DIR: str = str(Path(__file__).resolve().parent.parent / "data")


def get_db() -> CustomerDB:
    return CustomerDB(db_path=DB_PATH)


def get_staging() -> StagingManager:
    return StagingManager(data_dir=DATA_DIR)


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
        expected_user = os.environ.get("DASHBOARD_USER", "admin")
        expected_pass = os.environ.get("DASHBOARD_PASS", "")

        if not expected_pass:
            flash("DASHBOARD_PASS environment variable not set. Set it before logging in.", "error")
            return render_template("login.html")

        if username == expected_user and password == expected_pass:
            session["logged_in"] = True
            session["username"] = username
            return redirect(url_for("index"))
        flash("Invalid credentials.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
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

        for c in all_customers:
            c["pending_count"] = len(db.get_pending_access(c["id"]))
            c["is_staged"] = staging.is_staged(c["id"])
            c["is_approved"] = staging.is_approved(c["id"])
            places = db.get_google_places(c["id"])
            c["rating"] = places["rating"] if places else None
            c["review_count"] = places["review_count"] if places else None

        # Filter out archived for main view
        customers = [c for c in all_customers if c["status"] != "archived"]
        archived_count = sum(1 for c in all_customers if c["status"] == "archived")

        active_alerts = db.get_active_alert_count()

        stats = {
            "total": len(customers),
            "active": sum(1 for c in customers if c["status"] == "active"),
            "onboarding": sum(1 for c in customers if c["status"] == "onboarding"),
            "pending_approval": sum(1 for c in customers if c.get("is_staged") and not c.get("is_approved")),
            "archived": archived_count,
            "active_alerts": active_alerts,
        }

        return render_template("index.html", customers=customers, stats=stats)
    finally:
        db.close()


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

        checklist = db.get_checklist(customer_id)
        todos = _get_va_todos(customer, access, contacts, places, runs, staged, approved, checklist)
        seo_tasks = _get_seo_tasks(checklist)
        import markdown
        raw_templates = _get_email_templates()
        email_templates = []
        for t in raw_templates:
            raw = _render_email_template(
                t["content"], customer, contacts,
                kpis=kpis, runs=runs, places=places, diff_report=diff_report,
            )
            lines = raw.splitlines()
            body_lines = [l for l in lines if not l.startswith("Subject:")]
            body_html = markdown.markdown("\n".join(body_lines).strip(), extensions=["tables"])
            email_templates.append({
                "slug": t["slug"],
                "subject": _render_email_template(
                    t["subject"], customer, contacts,
                    kpis=kpis, runs=runs, places=places,
                ),
                "body_html": body_html,
            })

        # Content recommendations summary
        content_pending = db.get_pending_recommendations_count(customer_id)
        content_recs = db.get_content_recommendations(customer_id, limit=5)

        # Active alerts for this customer
        customer_alerts = db.get_alerts(customer_id, active_only=True, limit=10)

        # Current date for template comparisons
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Check if a report exists for this customer
        slug = re.sub(r'[^a-z0-9]+', '-', customer['name'].lower()).strip('-')
        report_zip = Path(DATA_DIR) / "customers" / slug / f"{slug}-ai-optimization.zip"
        report_exists = report_zip.exists()

        return render_template(
            "customer_detail.html",
            customer=customer, providers=providers, contacts=contacts,
            access=access, places=places, competitors=competitors,
            runs=runs, kpis=kpis, staged=staged, approved=approved,
            diff_report=diff_report, todos=todos, email_templates=email_templates,
            seo_tasks=seo_tasks, content_pending=content_pending,
            content_recs=content_recs, customer_alerts=customer_alerts,
            report_exists=report_exists, now_iso=now_iso,
        )
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
                    elif "webflow" in cms:
                        db.update_customer(customer_id, platform="webflow")
                    elif "squarespace" in cms:
                        db.update_customer(customer_id, platform="squarespace")
                    elif "wix" in cms:
                        db.update_customer(customer_id, platform="wix")
            except Exception as e:
                logger.warning(f"Hosting detection failed for {domain}: {e}")

            # Set up platform access tracking
            access_platforms = ["gsc", "ga", "gbp", "cloudflare"]
            if platform in ("webflow", "squarespace", "wordpress"):
                access_platforms.append(platform)
            for p in access_platforms:
                db.add_platform_access(customer_id, p)

            flash(f"Customer '{name}' added successfully!", "success")
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
            from geo_agent.google_places import fetch_place_data, fetch_nearby_competitors
            verified = fetch_place_data(name=name, city="", state="", domain=domain, api_key=api_key)
            if verified:
                result["places"] = {
                    "name": verified.name, "address": verified.address,
                    "city": verified.city, "state": verified.state,
                    "zip_code": verified.zip_code, "phone": verified.phone,
                    "rating": verified.rating, "review_count": verified.review_count,
                    "match_confidence": verified.match_confidence,
                }
                if verified.lat and verified.lng:
                    comps = fetch_nearby_competitors(verified.lat, verified.lng, name, api_key)
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
            flash(f"Status updated to {new_status}.", "success")
    finally:
        db.close()
    return redirect(url_for("customer_detail", customer_id=customer_id))


# --- Approve Staging ---

@app.route("/customer/<customer_id>/approve", methods=["POST"])
@login_required
def approve_staging(customer_id):
    staging = get_staging()
    db = get_db()
    try:
        if staging.is_staged(customer_id):
            staging.approve_changes(customer_id)
            latest_run = db.get_latest_run(customer_id)
            if latest_run and latest_run["status"] == "staged":
                db.approve_run(latest_run["id"])
            flash("Changes approved!", "success")
        else:
            flash("No staged changes to approve.", "error")
    finally:
        db.close()
    return redirect(url_for("customer_detail", customer_id=customer_id))


# --- Update Customer Fields ---

@app.route("/customer/<customer_id>/edit", methods=["POST"])
@login_required
def edit_customer(customer_id):
    db = get_db()
    try:
        fields = {}
        for key in ("name", "domain", "platform", "city", "state", "zip", "address",
                     "phone", "email", "brand_voice", "hours"):
            val = request.form.get(key)
            if val is not None:
                fields[key] = val.strip()

        emergency = request.form.get("emergency_available")
        if emergency is not None:
            fields["emergency_available"] = emergency == "on"

        if fields:
            db.update_customer(customer_id, **fields)
            flash("Customer updated.", "success")
    finally:
        db.close()
    return redirect(url_for("customer_detail", customer_id=customer_id))


# --- Email Templates ---

def _get_email_templates() -> list[dict]:
    """Return list of available email templates with metadata."""
    templates = []
    if not TEMPLATE_DIR.exists():
        return templates
    for f in sorted(TEMPLATE_DIR.glob("*.md")):
        with open(f) as fh:
            content = fh.read()
        # Extract subject from first line
        subject = ""
        for line in content.splitlines():
            if line.startswith("Subject:"):
                subject = line.replace("Subject:", "").strip()
                break
        templates.append({
            "filename": f.name,
            "slug": f.stem,
            "subject": subject,
            "content": content,
        })
    return templates


def _render_email_template(content: str, customer: dict, contacts: list[dict],
                           kpis: dict | None = None, runs: list[dict] | None = None,
                           places: dict | None = None, diff_report: str = "") -> str:
    """Replace template variables with real customer data from DB."""
    contact_name = contacts[0]["name"] if contacts else "there"
    contact_email = contacts[0].get("email", "") if contacts else ""

    # Platform-specific access steps
    platform = customer.get("platform", "unknown")
    platform_steps = {
        "webflow": "**Webflow** — Add kdoherty@practicerank.ai as a site collaborator\n   - Go to Site Settings > Members > Add collaborator\n   - Also generate an API token: Site Settings > Apps & Integrations > Generate API Token",
        "squarespace": "**Squarespace** — Add kdoherty@practicerank.ai as a contributor\n   - Go to Settings > Permissions > Contributors > Invite contributor",
        "wordpress": "**WordPress** — Create an admin account for kdoherty@practicerank.ai\n   - Go to Users > Add New > Set role to Administrator",
    }
    access_steps = platform_steps.get(platform, f"**{platform.title()}** — Please share login or collaborator access")

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

    replacements = {
        "{practice_name}": customer.get("name", ""),
        "{contact_name}": contact_name,
        "{contact_email}": contact_email,
        "{platform}": platform.title(),
        "{platform_access_steps}": access_steps,
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
        # Report content
        "{report_month}": report_month,
        "{changes_list}": changes_list,
        "{next_month_plans}": next_month_plans,
        "{changes_summary}": changes_summary,
        "{diff_summary}": diff_summary,
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

SEO_GEO_TASKS = [
    # Schema Markup
    {"key": "seo_schema_localbusiness", "task": "LocalBusiness (Dentist) schema markup", "category": "Schema Markup"},
    {"key": "seo_schema_faq", "task": "FAQPage schema on all service pages", "category": "Schema Markup"},
    {"key": "seo_schema_medical", "task": "MedicalProcedure schema for each service", "category": "Schema Markup"},
    {"key": "seo_schema_review", "task": "AggregateRating / Review schema", "category": "Schema Markup"},
    # llms.txt & AI Readiness
    {"key": "seo_llms_txt", "task": "Deploy llms.txt on domain", "category": "AI Readiness (GEO)"},
    {"key": "seo_llms_full", "task": "Deploy llms-full.txt with detailed content", "category": "AI Readiness (GEO)"},
    {"key": "seo_robots_txt", "task": "robots.txt allows AI crawlers (GPTBot, ClaudeBot, etc.)", "category": "AI Readiness (GEO)"},
    {"key": "seo_cloudflare_worker", "task": "Cloudflare Worker serving .txt files", "category": "AI Readiness (GEO)"},
    {"key": "seo_cloudflare_bot_rules", "task": "Audit Cloudflare WAF — not blocking AI bots", "category": "AI Readiness (GEO)"},
    {"key": "seo_ai_monitoring", "task": "AI mention monitoring set up (ChatGPT/Claude/Perplexity)", "category": "AI Readiness (GEO)"},
    # Content Optimization
    {"key": "seo_expert_quotes", "task": "Expert quotes on all service pages (+37-40% AI citation lift)", "category": "Content Optimization"},
    {"key": "seo_stats_embedded", "task": "Statistics embedded every 150-200 words (+22% lift)", "category": "Content Optimization"},
    {"key": "seo_faq_sections", "task": "4-6 FAQ entries per service page", "category": "Content Optimization"},
    {"key": "seo_content_depth", "task": "Service pages 2,000+ words with structured headings", "category": "Content Optimization"},
    {"key": "seo_provider_bios", "task": "Provider bios with credentials, specialties, years", "category": "Content Optimization"},
    {"key": "seo_emergency_page", "task": "Emergency dentist page", "category": "Content Optimization"},
    {"key": "seo_cost_page", "task": "Dental implant / procedure cost page", "category": "Content Optimization"},
    {"key": "seo_insurance_page", "task": "Insurance / financing page", "category": "Content Optimization"},
    {"key": "seo_neighborhood_pages", "task": "Neighborhood landing pages", "category": "Content Optimization"},
    # Technical SEO
    {"key": "seo_xml_sitemap", "task": "XML sitemap present and submitted", "category": "Technical SEO"},
    {"key": "seo_structured_headings", "task": "Proper H1/H2/H3 heading hierarchy", "category": "Technical SEO"},
    {"key": "seo_dns_cloudflare", "task": "DNS migrated to Cloudflare", "category": "Technical SEO"},
    # Local SEO & Citations
    {"key": "seo_gbp_optimized", "task": "Google Business Profile fully optimized", "category": "Local SEO"},
    {"key": "seo_gbp_photos", "task": "10+ photos on GBP (exterior, interior, team)", "category": "Local SEO"},
    {"key": "seo_gbp_qa", "task": "GBP Q&A pre-populated (10-15 questions)", "category": "Local SEO"},
    {"key": "seo_apple_business", "task": "Apple Business listing claimed & optimized", "category": "Local SEO"},
    {"key": "seo_yelp", "task": "Yelp listing claimed & optimized", "category": "Local SEO"},
    {"key": "seo_healthgrades", "task": "Healthgrades profile claimed", "category": "Local SEO"},
    {"key": "seo_zocdoc", "task": "Zocdoc listing claimed", "category": "Local SEO"},
    {"key": "seo_facebook", "task": "Facebook Business page set up", "category": "Local SEO"},
    {"key": "seo_bing_places", "task": "Bing Places imported from GBP", "category": "Local SEO"},
    {"key": "seo_nap_consistent", "task": "NAP consistent across all directories", "category": "Local SEO"},
    {"key": "seo_tier2_citations", "task": "Tier 2 citation directories submitted", "category": "Local SEO"},
    # Reviews
    {"key": "seo_review_cards", "task": "QR review cards printed & at front desk", "category": "Reviews & Reputation"},
    {"key": "seo_gradeus_setup", "task": "Grade.us review funnel configured", "category": "Reviews & Reputation"},
    {"key": "seo_review_responses", "task": "Review response workflow active", "category": "Reviews & Reputation"},
]


def _get_seo_tasks(checklist: dict[str, bool]) -> list[dict]:
    """Return SEO/GEO tasks grouped by category with completion status."""
    tasks = []
    for t in SEO_GEO_TASKS:
        tasks.append({
            "key": t["key"],
            "task": t["task"],
            "category": t["category"],
            "done": checklist.get(t["key"], False),
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
        templates = _get_email_templates()

        import markdown

        # Render each template with customer data, convert markdown to HTML
        rendered = []
        for t in templates:
            raw = _render_email_template(t["content"], customer, contacts)
            # Strip the "Subject: ..." line from body
            lines = raw.splitlines()
            body_lines = [l for l in lines if not l.startswith("Subject:")]
            body_md = "\n".join(body_lines).strip()
            body_html = markdown.markdown(body_md)

            rendered.append({
                "slug": t["slug"],
                "subject": _render_email_template(t["subject"], customer, contacts),
                "body_html": body_html,
            })

        return render_template("customer_emails.html", customer=customer, templates=rendered)
    finally:
        db.close()


# --- Kanban Board ---

BOARD_COLUMNS = [
    ("new", "New Lead", "#6b7280"),
    ("contacted", "Email Sent", "#2563eb"),
    ("access_pending", "Awaiting Access", "#d97706"),
    ("access_granted", "Access Complete", "#059669"),
    ("audit_setup", "Audit & Setup", "#7c3aed"),
    ("review_approve", "Review & Approve", "#db2777"),
    ("live", "Live", "#059669"),
]

@app.route("/board")
@login_required
def board():
    db = get_db()
    try:
        all_customers = db.list_customers()
        staging = get_staging()

        for c in all_customers:
            c["pending_count"] = len(db.get_pending_access(c["id"]))
            c["is_staged"] = staging.is_staged(c["id"])
            c["is_approved"] = staging.is_approved(c["id"])
            places = db.get_google_places(c["id"])
            c["rating"] = places["rating"] if places else None
            c["review_count"] = places["review_count"] if places else None

        # Exclude archived from board
        customers = [c for c in all_customers if c["status"] != "archived"]

        columns = []
        for step, label, color in BOARD_COLUMNS:
            cards = [c for c in customers if c.get("onboarding_step", "new") == step]
            columns.append({"step": step, "label": label, "color": color, "cards": cards})

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

    valid_steps = [s for s, _, _ in BOARD_COLUMNS]
    if not customer_id or new_step not in valid_steps:
        return jsonify({"error": "Invalid customer or step"}), 400

    db = get_db()
    try:
        db.set_onboarding_step(customer_id, new_step)
        return jsonify({"ok": True, "step": new_step})
    finally:
        db.close()


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

        # Auto-advance kanban step based on completed tasks
        customer = db.get_customer(customer_id)
        if customer and customer.get("status") == "onboarding":
            checklist = db.get_checklist(customer_id)
            access = db.get_platform_access(customer_id)
            pending = db.get_pending_access(customer_id)
            runs = db.get_runs(customer_id)

            all_access_done = not pending and bool(access)
            has_audit = bool(runs)

            # Determine the right step
            if has_audit or checklist.get("first_audit"):
                step = "audit_setup"
            elif all_access_done:
                step = "access_granted"
            elif checklist.get("onboard_email_sent"):
                step = "access_pending"
            elif checklist.get("onboard_email_sent") or checklist.get("contact_added"):
                step = "contacted"
            else:
                step = "new"

            current = customer.get("onboarding_step", "new")
            steps = CustomerDB.ONBOARDING_STEPS
            # Only advance forward, never go backward automatically
            if steps.index(step) > steps.index(current):
                db.set_onboarding_step(customer_id, step)

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
        return jsonify({"ok": True, "status": new_status})
    finally:
        db.close()


# --- Audit Logs ---

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


# --- Analytics ---

@app.route("/analytics")
@login_required
def analytics():
    """llms.txt analytics dashboard across all customers."""
    db = get_db()
    try:
        customers = db.list_customers(status="active")

        analytics_data = []
        for c in customers:
            # Get llms.txt hit KPIs
            hits_kpis = db.get_kpis(c["id"], "llms_txt_hits", limit=12)
            review_kpis = db.get_kpis(c["id"], "review_count", limit=2)
            mention_kpis = db.get_kpis(c["id"], "ai_mentions", limit=2)
            position_kpis = db.get_kpis(c["id"], "ai_avg_position", limit=2)

            def _num(kpi_list, idx=0, default=0):
                try:
                    return float(kpi_list[idx]["value"]) if len(kpi_list) > idx else default
                except (TypeError, ValueError):
                    return default

            current_hits = _num(hits_kpis)
            prev_hits = _num(hits_kpis, 1)
            hits_delta = current_hits - prev_hits

            current_reviews = _num(review_kpis)
            prev_reviews = _num(review_kpis, 1)

            current_mentions = _num(mention_kpis)
            avg_position = _num(position_kpis, default=None)

            analytics_data.append({
                "id": c["id"],
                "name": c["name"],
                "domain": c["domain"],
                "llms_hits": current_hits,
                "llms_hits_delta": hits_delta,
                "llms_history": [{"date": k["date"], "value": k["value"]} for k in reversed(hits_kpis[:7])],
                "reviews": current_reviews,
                "reviews_delta": current_reviews - prev_reviews,
                "ai_mentions": current_mentions,
                "ai_position": avg_position,
            })

        # Aggregate stats
        totals = {
            "total_hits": sum(d["llms_hits"] for d in analytics_data),
            "total_reviews": sum(d["reviews"] for d in analytics_data),
            "total_mentions": sum(d["ai_mentions"] for d in analytics_data),
            "customers_tracked": len(analytics_data),
        }

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
        recs = db.get_content_recommendations(customer_id, status=status_filter)

        # Group by type
        grouped = {}
        for r in recs:
            rt = r["rec_type"]
            if rt not in grouped:
                grouped[rt] = []
            grouped[rt].append(r)

        counts = {
            "pending": db.get_pending_recommendations_count(customer_id),
            "total": len(recs),
            "approved": len([r for r in recs if r["status"] == "approved"]),
            "published": len([r for r in recs if r["status"] == "published"]),
        }

        return render_template(
            "customer_content.html",
            customer=customer, recs=recs, grouped=grouped,
            counts=counts, status_filter=status_filter,
        )
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
        return jsonify({"ok": ok, "status": new_status})
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

            return jsonify({"ok": True, "generated": saved})
        except Exception as e:
            logger.error(f"Content generation failed for {customer_id}: {e}")
            return jsonify({"error": f"Generation failed: {type(e).__name__}: {str(e)[:200]}"}), 500
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
        flash("Customer restored to onboarding.", "success")
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
        subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT, cwd=str(Path(__file__).resolve().parent.parent))

    logger.info(f"Triggered pipeline run {run_id} for {customer_id}")

    if request.headers.get("HX-Request"):
        run_url = url_for("run_detail", run_id=run_id)
        return f'<a href="{run_url}" style="font-size:0.85rem;">Run #{run_id} started &rarr;</a>'

    flash(f"Pipeline run #{run_id} triggered for {customer['name']}.", "success")
    return redirect(url_for("run_detail", run_id=run_id))


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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PracticeRank Dashboard")
    parser.add_argument("--port", type=int, default=5099)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--db", default=None, help="Database file path")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    DB_PATH = args.db
    app.run(host=args.host, port=args.port, debug=args.debug)
