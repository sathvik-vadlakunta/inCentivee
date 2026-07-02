"""Health of the platform's scheduled automation.

Two concerns, both surfaced on the dashboard so Dan can self-diagnose instead of
pinging Kody:

1. **Job heartbeats** — did each cron job actually run recently? Cron lives on the
   droplet with no committed crontab; if it drifts, the whole pipeline silently
   stops. Each job records a heartbeat (`db.record_job_run`) at the end of its run;
   `job_health()` flags any that are overdue.
2. **Integrations** — is each external dependency configured? Missing env vars fail
   silently today (enrichment/publishing/emails just don't happen). `integration_health()`
   turns that into a green/red list.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

# job_name -> (human label, max age in hours before it's "overdue", cadence text)
EXPECTED_JOBS: dict[str, tuple[str, float, str]] = {
    "monthly_stage":            ("Monthly agent run (stage)", 24 * 40, "Monthly (day 1)"),
    "monthly_publish":          ("Monthly publish (approved)", 24 * 40, "Monthly (day 8)"),
    "daily_gsc_pull":           ("Daily Search Console pull", 30, "Daily"),
    "daily_score":              ("Daily PracticeRank score", 30, "Daily"),
    "daily_status_check":       ("Daily status reconcile", 30, "Daily"),
    "daily_attention_digest":   ("Daily attention digest email", 30, "Daily"),
    "weekly_reports":           ("Weekly report snapshots", 24 * 9, "Weekly (Mon)"),
    "weekly_ai_check":          ("Weekly AI-mention check", 24 * 9, "Weekly (Mon)"),
    "weekly_ai_digest":         ("Weekly AI digest email", 24 * 9, "Weekly (Mon)"),
    "biweekly_content":         ("Biweekly content generation", 24 * 16, "Every 2 weeks"),
    "monthly_local_relevancy":  ("Monthly local relevancy", 24 * 40, "Monthly"),
    "monthly_fatjoe_digest":    ("Monthly FATJOE digest email", 24 * 40, "Monthly (day 1)"),
    "nightly_billing_sync":     ("Nightly billing sync", 30, "Daily"),
}


def _parse(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def job_health(db) -> list[dict]:
    """Status of every expected scheduled job, most-concerning first.

    Each entry: name, label, cadence, last_run (ISO or None), status, detail,
    age_hours, state ('never' | 'overdue' | 'error' | 'ok')."""
    beats = db.get_job_heartbeats()
    now = datetime.now(timezone.utc)
    out: list[dict] = []
    for name, (label, max_age, cadence) in EXPECTED_JOBS.items():
        beat = beats.get(name)
        last = beat.get("last_run_at") if beat else None
        dt = _parse(last)
        age_h = (now - dt).total_seconds() / 3600 if dt else None
        beat_status = (beat or {}).get("status", "")
        if dt is None:
            state = "never"
        elif beat_status and beat_status != "ok":
            state = "error"
        elif age_h is not None and age_h > max_age:
            state = "overdue"
        else:
            state = "ok"
        out.append({
            "name": name, "label": label, "cadence": cadence,
            "last_run": last, "status": beat_status or "—",
            "detail": (beat or {}).get("detail", ""),
            "age_hours": age_h, "max_age_hours": max_age, "state": state,
        })
    _rank = {"error": 0, "overdue": 1, "never": 2, "ok": 3}
    out.sort(key=lambda j: (_rank.get(j["state"], 9), j["label"]))
    return out


def job_problems(db) -> list[dict]:
    """Just the jobs that need attention (error/overdue/never). Drives the banner."""
    return [j for j in job_health(db) if j["state"] != "ok"]


# --- Integration / credential health ------------------------------------------
# (label, [env vars — ANY present counts as configured], what breaks if missing, is_critical)
_INTEGRATIONS: list[tuple[str, list[str], str, bool]] = [
    ("Claude API (content + AI checks)", ["ANTHROPIC_API_KEY"],
     "Content generation and AI-mention checks won't run.", True),
    ("Search Console (GSC)", ["GSC_SERVICE_ACCOUNT_JSON", "GSC_SERVICE_ACCOUNT_KEY"],
     "Access validation + traffic reporting can't read GSC.", True),
    ("GSC impersonation user", ["GSC_IMPERSONATE_USER"],
     "GSC service account has nobody to impersonate — access checks fail.", True),
    ("Google Analytics (GA4)", ["GA4_OAUTH_REFRESH_TOKEN", "GA4_SERVICE_ACCOUNT_JSON",
                                 "GOOGLE_APPLICATION_CREDENTIALS"],
     "GA4 auto-discovery + conversion/lead reporting won't work.", True),
    ("Google Places", ["GOOGLE_PLACES_API_KEY"],
     "New-customer enrichment (rating, address, competitors) silently skips.", False),
    ("Webflow OAuth app", ["WEBFLOW_CLIENT_ID"],
     "'Connect Webflow' can't run for new clients.", True),
    ("Cloudflare Worker (llms.txt)", ["WORKER_API_URL"],
     "Publishing llms.txt / robots.txt no-ops — AEO files never go live.", True),
    ("Email delivery (Resend)", ["RESEND_API_KEY"],
     "Digest + report emails silently don't send.", True),
    ("BrightLocal (citations/rank)", ["BRIGHTLOCAL_API_KEY"],
     "Citation tracking + local rank data are unavailable.", False),
    ("Moz (Domain Authority)", ["MOZ_ACCESS_ID", "MOZ_API_TOKEN"],
     "Domain-authority baselines won't populate.", False),
    ("PageSpeed", ["PAGESPEED_API_KEY", "GOOGLE_API_KEY"],
     "Technical SEO/PageSpeed scoring falls back to slower/no data.", False),
    ("Stripe (billing)", ["STRIPE_SECRET_KEY"],
     "Billing sync + tier resolution from subscriptions won't run.", True),
    ("Flask session secret", ["FLASK_SECRET_KEY"],
     "Sessions reset on every restart — operators get logged out.", True),
]


def integration_health() -> list[dict]:
    """Green/red status per external integration, critical + unconfigured first."""
    out: list[dict] = []
    for label, envs, impact, critical in _INTEGRATIONS:
        present = next((e for e in envs if os.environ.get(e)), None)
        out.append({
            "label": label, "configured": present is not None,
            "via": present or "", "envs": envs, "impact": impact, "critical": critical,
        })
    out.sort(key=lambda i: (i["configured"], not i["critical"], i["label"]))
    return out
