"""Customer database — single source of truth for all practice data.

Replaces scattered JSON files with a proper SQLite database.
All secrets (API keys, tokens) stay in env vars / secrets manager — never in SQLite.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import secrets
import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

from geo_agent.config import Customer, Provider

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 9

# Generic mail hosts that must never be used to route email by domain (a customer
# website domain matching one of these would mis-file unrelated mail).
_GENERIC_EMAIL_DOMAINS = frozenset({
    "gmail.com", "googlemail.com", "yahoo.com", "ymail.com", "outlook.com",
    "hotmail.com", "live.com", "msn.com", "aol.com", "icloud.com", "me.com",
    "proton.me", "protonmail.com", "comcast.net", "att.net", "verizon.net",
})

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS customers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    domain TEXT NOT NULL,
    platform TEXT NOT NULL DEFAULT 'webflow',  -- webflow/squarespace/wordpress
    business_type TEXT NOT NULL DEFAULT 'practice',  -- practice/technology/product/service
    city TEXT NOT NULL DEFAULT '',
    state TEXT NOT NULL DEFAULT '',
    zip TEXT NOT NULL DEFAULT '',
    address TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    brand_voice TEXT NOT NULL DEFAULT 'Professional and warm',
    status TEXT NOT NULL DEFAULT 'onboarding',  -- onboarding/active/paused/churned
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    onboarded_at TEXT,
    webflow_site_id TEXT NOT NULL DEFAULT '',
    specialties TEXT NOT NULL DEFAULT '[]',  -- JSON array
    insurance_accepted TEXT NOT NULL DEFAULT '[]',  -- JSON array
    hours TEXT NOT NULL DEFAULT '',
    emergency_available INTEGER NOT NULL DEFAULT 0,
    competitors_json TEXT NOT NULL DEFAULT '[]',  -- JSON array of domain strings
    verified_quotes TEXT NOT NULL DEFAULT '[]',  -- JSON array of {"quote": "...", "attribution": "Name, Title"}
    onboarding_step TEXT NOT NULL DEFAULT 'new'  -- new/outreach/setup/review/live/content/monitoring/attention/paused
);

CREATE TABLE IF NOT EXISTS providers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL REFERENCES customers(id),
    name TEXT NOT NULL,
    credentials TEXT NOT NULL DEFAULT '',
    specialties TEXT NOT NULL DEFAULT '[]',  -- JSON array
    years_experience INTEGER,
    bio TEXT NOT NULL DEFAULT '',
    is_primary INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS services (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL REFERENCES customers(id),
    name TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'primary',  -- primary/specialty
    description TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS platform_access (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL REFERENCES customers(id),
    platform TEXT NOT NULL,  -- squarespace/webflow/gsc/ga/gbp/apple/cloudflare
    status TEXT NOT NULL DEFAULT 'pending',  -- pending/granted/not_needed
    granted_at TEXT,
    notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL REFERENCES customers(id),
    name TEXT NOT NULL,
    email TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL DEFAULT 'owner'  -- owner/seo_manager/office_manager/introducer
);

CREATE TABLE IF NOT EXISTS google_places (
    customer_id TEXT PRIMARY KEY REFERENCES customers(id),
    place_id TEXT NOT NULL DEFAULT '',
    rating REAL NOT NULL DEFAULT 0.0,
    review_count INTEGER NOT NULL DEFAULT 0,
    match_confidence TEXT NOT NULL DEFAULT 'low',
    lat REAL NOT NULL DEFAULT 0.0,
    lng REAL NOT NULL DEFAULT 0.0,
    last_checked TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS competitors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL REFERENCES customers(id),
    name TEXT NOT NULL,
    rating REAL NOT NULL DEFAULT 0.0,
    review_count INTEGER NOT NULL DEFAULT 0,
    location TEXT NOT NULL DEFAULT '',
    place_id TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL REFERENCES customers(id),
    run_date TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    status TEXT NOT NULL DEFAULT 'running',  -- running/staged/approved/published/failed/blocked
    pages_crawled INTEGER NOT NULL DEFAULT 0,
    changes_json TEXT NOT NULL DEFAULT '[]',
    errors_json TEXT NOT NULL DEFAULT '[]',
    approved INTEGER NOT NULL DEFAULT 0,
    approved_at TEXT,
    published_at TEXT,
    pid INTEGER
);

CREATE TABLE IF NOT EXISTS kpis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL REFERENCES customers(id),
    date TEXT NOT NULL,
    metric TEXT NOT NULL,  -- review_count/rating/ai_mentions/organic_clicks/llms_txt_hits
    value REAL NOT NULL DEFAULT 0.0
);

CREATE INDEX IF NOT EXISTS idx_providers_customer ON providers(customer_id);
CREATE INDEX IF NOT EXISTS idx_services_customer ON services(customer_id);
CREATE INDEX IF NOT EXISTS idx_platform_access_customer ON platform_access(customer_id);
CREATE INDEX IF NOT EXISTS idx_contacts_customer ON contacts(customer_id);
CREATE INDEX IF NOT EXISTS idx_competitors_customer ON competitors(customer_id);
CREATE INDEX IF NOT EXISTS idx_runs_customer ON runs(customer_id);
CREATE TABLE IF NOT EXISTS va_checklist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL REFERENCES customers(id),
    task_key TEXT NOT NULL,  -- unique key per task
    completed INTEGER NOT NULL DEFAULT 0,
    completed_at TEXT,
    UNIQUE(customer_id, task_key)
);

CREATE INDEX IF NOT EXISTS idx_kpis_customer_date ON kpis(customer_id, date);
CREATE INDEX IF NOT EXISTS idx_kpis_metric ON kpis(customer_id, metric);
CREATE INDEX IF NOT EXISTS idx_va_checklist_customer ON va_checklist(customer_id);

CREATE TABLE IF NOT EXISTS content_recommendations (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(id),
    rec_type TEXT NOT NULL,  -- blog_post/faq_update/expert_quote/stat_injection/freshness_update/new_page
    target_page TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    html_snippet TEXT NOT NULL DEFAULT '',
    priority INTEGER NOT NULL DEFAULT 3,
    category TEXT NOT NULL DEFAULT 'general',
    status TEXT NOT NULL DEFAULT 'pending',  -- pending/approved/rejected/published
    ai_impact_reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    reviewed_at TEXT,
    published_at TEXT,
    webflow_item_id TEXT,
    webflow_collection_id TEXT,
    publish_error TEXT
);

CREATE INDEX IF NOT EXISTS idx_content_recs_customer ON content_recommendations(customer_id);
CREATE INDEX IF NOT EXISTS idx_content_recs_status ON content_recommendations(customer_id, status);

CREATE TABLE IF NOT EXISTS content_translations (
    id TEXT PRIMARY KEY,
    recommendation_id TEXT NOT NULL REFERENCES content_recommendations(id),
    locale TEXT NOT NULL,  -- es, fr, de, pt, sv, ja, ko, zh, ar
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    html_snippet TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE(recommendation_id, locale)
);

CREATE INDEX IF NOT EXISTS idx_content_translations_rec ON content_translations(recommendation_id);
CREATE INDEX IF NOT EXISTS idx_content_translations_locale ON content_translations(recommendation_id, locale);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL REFERENCES customers(id),
    alert_type TEXT NOT NULL,  -- review_surge/rating_change/overtake/new_schema/new_competitor/schema_invalid/stale_content
    severity TEXT NOT NULL DEFAULT 'info',  -- info/warning/critical
    source TEXT NOT NULL DEFAULT '',  -- competitor name or page URL
    message TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}',
    dismissed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_alerts_customer ON alerts(customer_id);
CREATE INDEX IF NOT EXISTS idx_alerts_active ON alerts(customer_id, dismissed);

CREATE TABLE IF NOT EXISTS run_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES runs(id),
    step_name TEXT NOT NULL,  -- crawl/places/rag/analysis/content_recs/competitor/schema_validation/generate/stage/publish
    step_label TEXT NOT NULL DEFAULT '',  -- human-readable label
    status TEXT NOT NULL DEFAULT 'pending',  -- pending/running/success/failed/skipped
    started_at TEXT,
    finished_at TEXT,
    duration_ms INTEGER,
    log_text TEXT NOT NULL DEFAULT '',  -- captured log output
    result_json TEXT NOT NULL DEFAULT '{}',  -- step-specific results
    error_message TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_run_steps_run ON run_steps(run_id);

CREATE TABLE IF NOT EXISTS webflow_oauth_tokens (
    site_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(id),
    access_token TEXT NOT NULL,
    granted_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS webflow_oauth_apps (
    customer_id TEXT PRIMARY KEY REFERENCES customers(id),
    client_id TEXT NOT NULL,
    client_secret TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS webflow_collections (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(id),
    collection_type TEXT NOT NULL,  -- blog_posts/faqs
    webflow_collection_id TEXT NOT NULL,
    display_name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE(customer_id, collection_type)
);

-- Competitor tracking (enhanced - domain-based)
CREATE TABLE IF NOT EXISTS competitor_domains (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL REFERENCES customers(id),
    competitor_domain TEXT NOT NULL,
    competitor_name TEXT NOT NULL DEFAULT '',
    discovered_via TEXT DEFAULT 'manual',
    rating REAL DEFAULT 0,
    review_count INTEGER DEFAULT 0,
    address TEXT DEFAULT '',
    place_id TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE(customer_id, competitor_domain)
);

-- Review tracking
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'google',
    rating INTEGER NOT NULL,
    review_text TEXT,
    reviewer_name TEXT,
    review_date TEXT,
    sentiment TEXT,
    themes_json TEXT DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- Citations
CREATE TABLE IF NOT EXISTS citations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL,
    directory TEXT NOT NULL,
    listed INTEGER NOT NULL DEFAULT 0,
    nap_match INTEGER NOT NULL DEFAULT 0,
    url_correct INTEGER NOT NULL DEFAULT 0,
    listing_url TEXT,
    last_checked TEXT,
    UNIQUE(customer_id, directory)
);

-- GBP audit
CREATE TABLE IF NOT EXISTS gbp_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL,
    date TEXT NOT NULL,
    score INTEGER NOT NULL DEFAULT 0,
    details_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE(customer_id, date)
);

-- Page content scores
CREATE TABLE IF NOT EXISTS page_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL,
    page_url TEXT NOT NULL,
    score INTEGER NOT NULL DEFAULT 0,
    word_count INTEGER DEFAULT 0,
    readability_grade REAL,
    breakdown_json TEXT NOT NULL DEFAULT '{}',
    date TEXT NOT NULL,
    UNIQUE(customer_id, page_url, date)
);

-- Topic clusters
CREATE TABLE IF NOT EXISTS topic_clusters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL,
    cluster_name TEXT NOT NULL,
    pillar_page_url TEXT,
    keywords_json TEXT NOT NULL DEFAULT '[]',
    gap_pages_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE(customer_id, cluster_name)
);

-- AI readiness scores
CREATE TABLE IF NOT EXISTS ai_readiness_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL,
    date TEXT NOT NULL,
    score INTEGER NOT NULL DEFAULT 0,
    breakdown_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE(customer_id, date)
);

CREATE INDEX IF NOT EXISTS idx_competitor_domains_customer ON competitor_domains(customer_id);
CREATE INDEX IF NOT EXISTS idx_reviews_customer ON reviews(customer_id);
CREATE INDEX IF NOT EXISTS idx_citations_customer ON citations(customer_id);
CREATE INDEX IF NOT EXISTS idx_page_scores_customer ON page_scores(customer_id);
"""


class CustomerDB:
    """SQLite-backed customer database."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or str(
            Path(__file__).resolve().parent.parent / "data" / "practicerank.db"
        )
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, timeout=15)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        # Wait (rather than failing instantly) when another connection holds the
        # write lock — e.g. a long-running pipeline/audit. Without this, any
        # concurrent write turns every page load into a 500 ("database is locked").
        self.conn.execute("PRAGMA busy_timeout=15000")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def _init_schema(self):
        self.conn.executescript(SCHEMA_SQL)
        # Check/set schema version
        cur = self.conn.execute("SELECT version FROM schema_version LIMIT 1")
        row = cur.fetchone()
        if not row:
            self.conn.execute(
                "INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,)
            )
        # Migrations
        cols = [r[1] for r in self.conn.execute("PRAGMA table_info(customers)").fetchall()]
        if "onboarding_step" not in cols:
            self.conn.execute("ALTER TABLE customers ADD COLUMN onboarding_step TEXT NOT NULL DEFAULT 'new'")
        if "hosting_info" not in cols:
            self.conn.execute("ALTER TABLE customers ADD COLUMN hosting_info TEXT NOT NULL DEFAULT '{}'")
        if "business_type" not in cols:
            self.conn.execute("ALTER TABLE customers ADD COLUMN business_type TEXT NOT NULL DEFAULT 'practice'")
        if "verified_quotes" not in cols:
            self.conn.execute("ALTER TABLE customers ADD COLUMN verified_quotes TEXT NOT NULL DEFAULT '[]'")
        # Review-response tracking (owner replies) — populated by GBP review sync or a manual mark.
        try:
            rcols = [r[1] for r in self.conn.execute("PRAGMA table_info(reviews)").fetchall()]
            if rcols and "owner_response" not in rcols:
                self.conn.execute("ALTER TABLE reviews ADD COLUMN owner_response TEXT")
            if rcols and "responded_at" not in rcols:
                self.conn.execute("ALTER TABLE reviews ADD COLUMN responded_at TEXT")
        except Exception:
            pass
        # Account management: a pinned current-status line so you can see at a
        # glance where each customer is, separate from the dated activity log.
        if "status_note" not in cols:
            self.conn.execute("ALTER TABLE customers ADD COLUMN status_note TEXT NOT NULL DEFAULT ''")
        if "next_action" not in cols:
            self.conn.execute("ALTER TABLE customers ADD COLUMN next_action TEXT NOT NULL DEFAULT ''")
        if "service_areas" not in cols:
            # Nearby cities (~25 min) the business serves — drives AI-mention
            # geographic coverage to match the location pages we build.
            self.conn.execute("ALTER TABLE customers ADD COLUMN service_areas TEXT NOT NULL DEFAULT '[]'")
        if "live_area_pages" not in cols:
            # Service-area cities detected as having a LIVE page on the site (from
            # the daily reconciler's sitemap scan). Credits dev-built city pages
            # toward content coverage even when they never came through our pipeline.
            self.conn.execute("ALTER TABLE customers ADD COLUMN live_area_pages TEXT NOT NULL DEFAULT '[]'")
        if "baseline_score" not in cols:
            # Week-0 PracticeRank Score (locked on the first score, pre-work) so
            # the report can show "+N since baseline". NULL = not yet set.
            self.conn.execute("ALTER TABLE customers ADD COLUMN baseline_score INTEGER")
            self.conn.execute("ALTER TABLE customers ADD COLUMN baseline_date TEXT")
        if "changes_live_at" not in cols:
            # Date the on-site SEO/AEO optimizations actually went live (ISO
            # YYYY-MM-DD). This — NOT customer signup — anchors the report's
            # "results take 6+ weeks" clock, since effects only start once the
            # changes ship. NULL = not set (report falls back to neutral copy).
            self.conn.execute("ALTER TABLE customers ADD COLUMN changes_live_at TEXT")
        if "tier_override" not in cols:
            # Manual tier (optimize/grow/dominate) for customers whose Stripe product
            # name doesn't contain a tier keyword — custom payment links, discounted
            # deals, etc. Wins over the normalize_tier() product-name heuristic.
            self.conn.execute("ALTER TABLE customers ADD COLUMN tier_override TEXT NOT NULL DEFAULT ''")
        if "avg_case_value" not in cols:
            # Outcome-led reporting: avg $ a new patient/case is worth to this practice
            # (whole dollars). Set once by Dan; multiplies inquiries → estimated production.
            self.conn.execute("ALTER TABLE customers ADD COLUMN avg_case_value INTEGER")
            # Inquiry → booked-patient close rate (0..1); default to a conservative industry ~0.35.
            self.conn.execute("ALTER TABLE customers ADD COLUMN close_rate REAL NOT NULL DEFAULT 0.35")
        if "review_target_pm" not in cols:
            # Target new Google reviews per month. Review velocity below this raises a
            # stall signal (action item) — reviews/month is the top local-pack lever.
            self.conn.execute("ALTER TABLE customers ADD COLUMN review_target_pm INTEGER NOT NULL DEFAULT 4")
        if "quick_win_shipped_at" not in cols:
            # Day-1 quick-win pass: timestamp when the first visible result shipped.
            # Onboarding isn't "done" until this is set — kills first-60-day churn.
            self.conn.execute("ALTER TABLE customers ADD COLUMN quick_win_shipped_at TEXT")
        if "cutover" not in cols:
            # Operator flag: this customer's site is LIVE with our changes / cut over
            # in Cloudflare — we're actively managing it. This GATES all recurring
            # LLM work (3x/week + weekly AI checks, monthly/biweekly content, daily
            # alerts, the content queue) so we don't pay for LLM runs — or pollute
            # baselines — on customers that haven't really started. New customers get
            # only a one-time baseline until cut over. See
            # specs/active/paying-only-recurring-work.md.
            self.conn.execute("ALTER TABLE customers ADD COLUMN cutover INTEGER NOT NULL DEFAULT 0")
            self.conn.execute("ALTER TABLE customers ADD COLUMN cutover_at TEXT")

        # Per-customer activity timeline: notes, status changes, and ingested
        # emails. Mirrors prospect_activities so the customer detail page gets the
        # same running log prospects already have.
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS customer_activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT NOT NULL REFERENCES customers(id),
                activity_type TEXT NOT NULL DEFAULT 'note',
                subject TEXT NOT NULL DEFAULT '',
                body TEXT NOT NULL DEFAULT '',
                meta_json TEXT NOT NULL DEFAULT '{}',
                created_by TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
            );
            CREATE INDEX IF NOT EXISTS idx_cust_activities ON customer_activities(customer_id, id DESC);
        """)

        # Migration: store OS pid of the pipeline subprocess so runs can be truly cancelled / reaped
        run_cols = [r[1] for r in self.conn.execute("PRAGMA table_info(runs)").fetchall()]
        if "pid" not in run_cols:
            self.conn.execute("ALTER TABLE runs ADD COLUMN pid INTEGER")

        # Migration v1 → v2: platform-aware content publishing + squarespace credentials
        rec_cols = [r[1] for r in self.conn.execute("PRAGMA table_info(content_recommendations)").fetchall()]
        if "platform_item_id" not in rec_cols:
            self.conn.execute("ALTER TABLE content_recommendations ADD COLUMN platform_item_id TEXT DEFAULT ''")
            self.conn.execute("ALTER TABLE content_recommendations ADD COLUMN platform_draft_url TEXT DEFAULT ''")
        # Migration v2 → v3: publish-ready SEO meta description + YMYL E-E-A-T byline fields.
        # Previously dropped on save (not in the INSERT), which let writer-brief text leak into
        # the docx "Meta Description" slot. Persist them as first-class columns.
        if "meta_description" not in rec_cols:
            self.conn.execute("ALTER TABLE content_recommendations ADD COLUMN meta_description TEXT DEFAULT ''")
            self.conn.execute("ALTER TABLE content_recommendations ADD COLUMN author_attribution TEXT DEFAULT ''")
            self.conn.execute("ALTER TABLE content_recommendations ADD COLUMN reviewed_date TEXT DEFAULT ''")
        if "intent_tier" not in rec_cols:
            # Money-query weighting: search intent of the target topic
            # (transactional/commercial/informational) — drives ordering + the report's
            # intent mix so we prove we're publishing buyer content, not just traffic.
            self.conn.execute("ALTER TABLE content_recommendations ADD COLUMN intent_tier TEXT NOT NULL DEFAULT ''")
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS squarespace_credentials (
                customer_id TEXT PRIMARY KEY REFERENCES customers(id),
                email TEXT NOT NULL,
                password_encrypted TEXT NOT NULL,
                site_url TEXT NOT NULL,
                totp_secret_encrypted TEXT DEFAULT '',
                last_login TEXT,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
            )
        """)
        # Migration v2 → v3: AI mention tracking tables
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS ai_mention_runs (
                id TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL REFERENCES customers(id),
                run_date TEXT NOT NULL,
                total_mentions INTEGER NOT NULL DEFAULT 0,
                total_queries INTEGER NOT NULL DEFAULT 0,
                mention_rate REAL NOT NULL DEFAULT 0.0,
                avg_position REAL,
                engines_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
            );
            CREATE INDEX IF NOT EXISTS idx_ai_runs_customer ON ai_mention_runs(customer_id, run_date);

            CREATE TABLE IF NOT EXISTS ai_mention_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL REFERENCES ai_mention_runs(id),
                customer_id TEXT NOT NULL,
                engine TEXT NOT NULL,
                prompt TEXT NOT NULL,
                prompt_category TEXT NOT NULL DEFAULT 'general',
                mentioned INTEGER NOT NULL DEFAULT 0,
                position INTEGER,
                quality_score INTEGER NOT NULL DEFAULT 0,
                context TEXT NOT NULL DEFAULT '',
                full_response TEXT NOT NULL DEFAULT '',
                is_disclaimer INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
            );
            CREATE INDEX IF NOT EXISTS idx_ai_results_run ON ai_mention_results(run_id);
            CREATE INDEX IF NOT EXISTS idx_ai_results_customer ON ai_mention_results(customer_id, engine);
        """)
        # Migration v3 → v4: GSC daily metrics table
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS gsc_daily_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT NOT NULL,
                date TEXT NOT NULL,
                clicks INTEGER NOT NULL DEFAULT 0,
                impressions INTEGER NOT NULL DEFAULT 0,
                ctr REAL NOT NULL DEFAULT 0.0,
                position REAL NOT NULL DEFAULT 0.0,
                UNIQUE(customer_id, date)
            );
            CREATE INDEX IF NOT EXISTS idx_gsc_daily_customer ON gsc_daily_metrics(customer_id, date);
        """)
        # Migration v4 → v5: Add prompt_set to ai_mention_runs for benchmark tracking
        try:
            self.conn.execute("ALTER TABLE ai_mention_runs ADD COLUMN prompt_set TEXT NOT NULL DEFAULT 'comprehensive'")
        except Exception:
            pass  # Column already exists
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_runs_prompt_set ON ai_mention_runs(customer_id, prompt_set, run_date)")

        # Migration: per-result model + web citations (grounded AI-visibility checks)
        res_cols = [r[1] for r in self.conn.execute("PRAGMA table_info(ai_mention_results)").fetchall()]
        if "model" not in res_cols:
            self.conn.execute("ALTER TABLE ai_mention_results ADD COLUMN model TEXT NOT NULL DEFAULT ''")
        if "citations_json" not in res_cols:
            self.conn.execute("ALTER TABLE ai_mention_results ADD COLUMN citations_json TEXT NOT NULL DEFAULT '[]'")
        # Multi-sampling: how many times this prompt×engine was sampled and how many
        # mentioned — averages out LLM non-determinism for a rock-solid rate.
        if "samples" not in res_cols:
            self.conn.execute("ALTER TABLE ai_mention_results ADD COLUMN samples INTEGER NOT NULL DEFAULT 1")
        if "samples_mentioned" not in res_cols:
            self.conn.execute("ALTER TABLE ai_mention_results ADD COLUMN samples_mentioned INTEGER NOT NULL DEFAULT 0")
        # Optional baseline marker on a run (locks an onboarding before/after snapshot)
        run_cols2 = [r[1] for r in self.conn.execute("PRAGMA table_info(ai_mention_runs)").fetchall()]
        if "is_baseline" not in run_cols2:
            self.conn.execute("ALTER TABLE ai_mention_runs ADD COLUMN is_baseline INTEGER NOT NULL DEFAULT 0")
        # Methodology version: legacy ungrounded runs are '1.0'; new grounded
        # (real web-search) runs are '2.0'. Primary metrics count 2.0 only.
        if "methodology" not in run_cols2:
            self.conn.execute("ALTER TABLE ai_mention_runs ADD COLUMN methodology TEXT NOT NULL DEFAULT '1.0'")
            # Backfill: tag any existing run that used grounded models as 2.0.
            self.conn.execute(
                """UPDATE ai_mention_runs SET methodology = '2.0' WHERE id IN (
                       SELECT DISTINCT run_id FROM ai_mention_results
                       WHERE model IN ('claude-opus-4-8','gpt-4o-search-preview','sonar-pro','gemini-2.5-flash','grok-4')
                          OR (citations_json IS NOT NULL AND citations_json != '[]')
                   )"""
            )

        # Migration v5: Dashboard users table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS dashboard_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                display_name TEXT NOT NULL DEFAULT '',
                role TEXT NOT NULL DEFAULT 'admin',
                active INTEGER NOT NULL DEFAULT 1,
                last_login TEXT,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
            )
        """)

        # Migration: Client portal users table (password-less invite state until signup)
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS client_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT NOT NULL REFERENCES customers(id),
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT,
                display_name TEXT NOT NULL DEFAULT '',
                active INTEGER NOT NULL DEFAULT 1,
                signup_token TEXT UNIQUE,
                signup_token_created_at TEXT,
                last_login TEXT,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
            );
            CREATE INDEX IF NOT EXISTS idx_client_users_customer ON client_users(customer_id);
        """)

        # Migration v5 → v6: SEO tools expansion tables
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS customer_integrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT NOT NULL REFERENCES customers(id),
                integration TEXT NOT NULL,
                config_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'not_configured',
                last_checked TEXT,
                last_error TEXT,
                UNIQUE(customer_id, integration)
            );
            CREATE INDEX IF NOT EXISTS idx_integrations_customer ON customer_integrations(customer_id);

            CREATE TABLE IF NOT EXISTS keyword_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT NOT NULL REFERENCES customers(id),
                keyword TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'manual',
                is_tracked INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
                UNIQUE(customer_id, keyword)
            );
            CREATE INDEX IF NOT EXISTS idx_keywords_customer ON keyword_tracking(customer_id);

            CREATE TABLE IF NOT EXISTS keyword_ranks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT NOT NULL REFERENCES customers(id),
                keyword TEXT NOT NULL,
                date TEXT NOT NULL,
                position REAL,
                clicks INTEGER DEFAULT 0,
                impressions INTEGER DEFAULT 0,
                ctr REAL DEFAULT 0.0,
                UNIQUE(customer_id, keyword, date)
            );
            CREATE INDEX IF NOT EXISTS idx_keyword_ranks_lookup ON keyword_ranks(customer_id, keyword, date);

            CREATE TABLE IF NOT EXISTS site_audits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT NOT NULL REFERENCES customers(id),
                audit_date TEXT NOT NULL,
                performance_score INTEGER,
                accessibility_score INTEGER,
                seo_score INTEGER,
                best_practices_score INTEGER,
                issues_json TEXT NOT NULL DEFAULT '[]',
                raw_data_json TEXT NOT NULL DEFAULT '{}',
                UNIQUE(customer_id, audit_date)
            );
            CREATE INDEX IF NOT EXISTS idx_site_audits_customer ON site_audits(customer_id, audit_date);

            CREATE TABLE IF NOT EXISTS audit_issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT NOT NULL REFERENCES customers(id),
                audit_id INTEGER REFERENCES site_audits(id),
                category TEXT NOT NULL,
                severity TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                fix_instruction TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'open',
                fixed_date TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_audit_issues_customer ON audit_issues(customer_id, status);

            CREATE TABLE IF NOT EXISTS backlinks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT NOT NULL REFERENCES customers(id),
                linking_domain TEXT NOT NULL,
                link_count INTEGER NOT NULL DEFAULT 1,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                UNIQUE(customer_id, linking_domain)
            );
            CREATE INDEX IF NOT EXISTS idx_backlinks_customer ON backlinks(customer_id, status);

            CREATE TABLE IF NOT EXISTS content_topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT NOT NULL REFERENCES customers(id),
                topic TEXT NOT NULL,
                target_keyword TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT 'manual',
                priority TEXT NOT NULL DEFAULT 'medium',
                status TEXT NOT NULL DEFAULT 'suggested',
                content_rec_id TEXT,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
                notes TEXT NOT NULL DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_content_topics_customer ON content_topics(customer_id, status);
        """)

        # Migration: add rating/review_count/address/place_id to competitor_domains
        for col, default in [("rating", "0"), ("review_count", "0"), ("address", "''"), ("place_id", "''")]:
            try:
                self.conn.execute(f"ALTER TABLE competitor_domains ADD COLUMN {col} {'REAL' if col == 'rating' else 'INTEGER' if col == 'review_count' else 'TEXT'} DEFAULT {default}")
            except Exception:
                pass

        # Migration: Domain Authority on competitors (Moz) for the you-vs-them chart.
        for col, coltype, default in [("domain_authority", "REAL", "0"), ("da_checked_at", "TEXT", "''")]:
            try:
                self.conn.execute(f"ALTER TABLE competitor_domains ADD COLUMN {col} {coltype} DEFAULT {default}")
            except Exception:
                pass

        # Migration: map old onboarding_step values to new 9-column board.
        # Guarded by a read so the steady state (every page load re-runs
        # _init_schema) stays read-only and never contends for the write lock.
        _legacy_steps = ('contacted', 'access_pending', 'access_granted', 'audit_setup', 'review_approve')
        if self.conn.execute(
            f"SELECT 1 FROM customers WHERE onboarding_step IN ({','.join('?' * len(_legacy_steps))}) LIMIT 1",
            _legacy_steps,
        ).fetchone():
            self.conn.execute("UPDATE customers SET onboarding_step = 'outreach' WHERE onboarding_step = 'contacted'")
            self.conn.execute("UPDATE customers SET onboarding_step = 'setup' WHERE onboarding_step IN ('access_pending', 'access_granted')")
            self.conn.execute("UPDATE customers SET onboarding_step = 'review' WHERE onboarding_step IN ('audit_setup', 'review_approve')")

        # Migration v6 → v7: AI response entity extraction table
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS ai_response_entities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                result_id INTEGER NOT NULL,
                run_id TEXT NOT NULL,
                customer_id TEXT NOT NULL,
                entity_name TEXT NOT NULL,
                entity_name_normalized TEXT NOT NULL,
                entity_type TEXT NOT NULL DEFAULT 'business',
                is_customer INTEGER NOT NULL DEFAULT 0,
                position INTEGER,
                engine TEXT NOT NULL,
                prompt TEXT NOT NULL,
                prompt_category TEXT NOT NULL DEFAULT 'general',
                run_date TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
                FOREIGN KEY (result_id) REFERENCES ai_mention_results(id)
            );
            CREATE INDEX IF NOT EXISTS idx_entities_customer ON ai_response_entities(customer_id, run_date);
            CREATE INDEX IF NOT EXISTS idx_entities_name ON ai_response_entities(entity_name_normalized, customer_id);
            CREATE INDEX IF NOT EXISTS idx_entities_run ON ai_response_entities(run_id);
        """)

        # Migration v7 → v8: PracticeRank score history table
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS practicerank_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT NOT NULL,
                date TEXT NOT NULL,
                overall_score INTEGER NOT NULL,
                ai_visibility INTEGER,
                search_growth INTEGER,
                technical_health INTEGER,
                content_velocity INTEGER,
                reputation INTEGER,
                breakdown_json TEXT NOT NULL DEFAULT '{}',
                UNIQUE(customer_id, date)
            );
            CREATE INDEX IF NOT EXISTS idx_pr_scores_customer ON practicerank_scores(customer_id, date);

            -- SEO Health Score daily history (the dashboard donut). Stored so we can
            -- show improvement-over-time + an explained 4-bucket breakdown.
            CREATE TABLE IF NOT EXISTS seo_health_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT NOT NULL,
                date TEXT NOT NULL,
                score INTEGER NOT NULL,
                pagespeed INTEGER,
                keyword_coverage INTEGER,
                traffic_trend INTEGER,
                technical INTEGER,
                breakdown_json TEXT NOT NULL DEFAULT '{}',
                UNIQUE(customer_id, date)
            );
            CREATE INDEX IF NOT EXISTS idx_seo_health_customer ON seo_health_history(customer_id, date);

            -- Heartbeats for scheduled (cron) jobs so the dashboard can show whether
            -- the automation is actually running and warn when a job is overdue.
            CREATE TABLE IF NOT EXISTS job_heartbeats (
                job_name    TEXT PRIMARY KEY,
                last_run_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
                status      TEXT NOT NULL DEFAULT 'ok',
                detail      TEXT NOT NULL DEFAULT ''
            );
        """)

        # Migration v8 → v9: Landing page report tracking
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS landing_page_reports (
                id              TEXT PRIMARY KEY,
                lead_id         TEXT NOT NULL,
                customer_id     TEXT,
                timestamp       TEXT NOT NULL,
                practice_url    TEXT NOT NULL,
                domain          TEXT NOT NULL,
                vertical        TEXT DEFAULT 'dental',
                email           TEXT,
                contact_name    TEXT,
                practice_name   TEXT,
                city            TEXT,
                state           TEXT,
                overall_score   INTEGER,
                grade           TEXT,
                data_confidence TEXT,
                revenue_lost    TEXT,
                category_scores TEXT,
                competitor_count INTEGER DEFAULT 0,
                full_report     TEXT,
                synced_at       TEXT NOT NULL,
                FOREIGN KEY (customer_id) REFERENCES customers(id)
            );
            CREATE INDEX IF NOT EXISTS idx_lpr_domain ON landing_page_reports(domain);
            CREATE INDEX IF NOT EXISTS idx_lpr_customer ON landing_page_reports(customer_id);
            CREATE INDEX IF NOT EXISTS idx_lpr_timestamp ON landing_page_reports(timestamp DESC);
            CREATE INDEX IF NOT EXISTS idx_lpr_email ON landing_page_reports(email);
        """)

        # Migration v9 → v10: Prospects / sales pipeline
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS prospects (
                id TEXT PRIMARY KEY,
                domain TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                contact_name TEXT,
                vertical TEXT DEFAULT 'dental',
                stage TEXT NOT NULL DEFAULT 'new_lead',
                lost_reason TEXT,
                report_id TEXT,
                overall_score INTEGER,
                grade TEXT,
                report_data TEXT,
                stripe_checkout_id TEXT,
                stripe_customer_id TEXT,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
                updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
                FOREIGN KEY (report_id) REFERENCES landing_page_reports(id)
            );
            CREATE INDEX IF NOT EXISTS idx_prospects_stage ON prospects(stage);
            CREATE INDEX IF NOT EXISTS idx_prospects_domain ON prospects(domain);

            CREATE TABLE IF NOT EXISTS prospect_activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prospect_id TEXT NOT NULL,
                activity_type TEXT NOT NULL,
                stage_from TEXT,
                stage_to TEXT,
                subject TEXT,
                body TEXT,
                created_by TEXT,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
                FOREIGN KEY (prospect_id) REFERENCES prospects(id)
            );
            CREATE INDEX IF NOT EXISTS idx_activities_prospect ON prospect_activities(prospect_id);
            CREATE INDEX IF NOT EXISTS idx_activities_type ON prospect_activities(activity_type);
        """)

        # Migration v8 → v9: Weekly customer report + supporting trackers
        # (see docs/requirements.md → Reporting & Data-Completeness Requirements)
        self.conn.executescript("""
            -- R0: rendered weekly/monthly report snapshots
            CREATE TABLE IF NOT EXISTS report_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT NOT NULL REFERENCES customers(id),
                report_type TEXT NOT NULL DEFAULT 'weekly',
                period_start TEXT NOT NULL,
                period_end TEXT NOT NULL,
                score INTEGER NOT NULL DEFAULT 0,
                payload_json TEXT NOT NULL DEFAULT '{}',
                html TEXT NOT NULL DEFAULT '',
                share_token TEXT NOT NULL DEFAULT '',
                emailed_at TEXT,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
                UNIQUE(customer_id, report_type, period_end)
            );
            CREATE INDEX IF NOT EXISTS idx_report_snapshots ON report_snapshots(customer_id, report_type, period_end);
            CREATE INDEX IF NOT EXISTS idx_report_share_token ON report_snapshots(share_token);

            -- R1: query-dimension GSC data (powers top keywords + movers)
            CREATE TABLE IF NOT EXISTS gsc_query_daily (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT NOT NULL,
                date TEXT NOT NULL,
                query TEXT NOT NULL,
                clicks INTEGER NOT NULL DEFAULT 0,
                impressions INTEGER NOT NULL DEFAULT 0,
                ctr REAL NOT NULL DEFAULT 0.0,
                position REAL NOT NULL DEFAULT 0.0,
                UNIQUE(customer_id, date, query)
            );
            CREATE INDEX IF NOT EXISTS idx_gsc_query_daily ON gsc_query_daily(customer_id, date);

            -- R2: competitor rating/review history (powers gap trend)
            CREATE TABLE IF NOT EXISTS competitor_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                competitor_id INTEGER NOT NULL REFERENCES competitors(id),
                customer_id TEXT NOT NULL,
                date TEXT NOT NULL,
                rating REAL NOT NULL DEFAULT 0.0,
                review_count INTEGER NOT NULL DEFAULT 0,
                UNIQUE(competitor_id, date)
            );
            CREATE INDEX IF NOT EXISTS idx_competitor_snapshots ON competitor_snapshots(customer_id, date);

            -- R3: conversion events (calls/forms) from GA4
            CREATE TABLE IF NOT EXISTS conversions_daily (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT NOT NULL,
                date TEXT NOT NULL,
                event_name TEXT NOT NULL,
                channel TEXT NOT NULL DEFAULT 'organic',
                count INTEGER NOT NULL DEFAULT 0,
                UNIQUE(customer_id, date, event_name, channel)
            );
            CREATE INDEX IF NOT EXISTS idx_conversions_daily ON conversions_daily(customer_id, date);

            -- Off-site authority work (FATJOE link building, citations, brand
            -- mentions). offsite_orders = one row per order we place; the status
            -- lifecycle is ordered -> in_progress -> delivered -> live -> indexed
            -- (or redo_requested / cancelled). See specs fatjoe-va-ops-and-tracking.
            CREATE TABLE IF NOT EXISTS offsite_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT NOT NULL REFERENCES customers(id),
                vendor TEXT NOT NULL DEFAULT 'fatjoe',
                order_type TEXT NOT NULL DEFAULT 'link',   -- citation | link | mention
                status TEXT NOT NULL DEFAULT 'ordered',
                quantity INTEGER NOT NULL DEFAULT 1,
                dr_tier INTEGER,                           -- links only (20/30/40…)
                target_url TEXT NOT NULL DEFAULT '',
                anchor_text TEXT NOT NULL DEFAULT '',
                anchor_type TEXT NOT NULL DEFAULT '',       -- branded|url|generic|partial|exact
                cost_usd REAL NOT NULL DEFAULT 0,
                vendor_order_id TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                ordered_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
                delivered_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_offsite_orders ON offsite_orders(customer_id, id DESC);

            -- Delivered live URLs from an order (a citation order yields ~100, a
            -- link order yields 1). da is pulled via moz_client per unique domain.
            CREATE TABLE IF NOT EXISTS offsite_assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL REFERENCES offsite_orders(id),
                customer_id TEXT NOT NULL REFERENCES customers(id),
                asset_type TEXT NOT NULL DEFAULT 'link',   -- citation | link | mention
                live_url TEXT NOT NULL DEFAULT '',
                domain TEXT NOT NULL DEFAULT '',
                anchor_text TEXT NOT NULL DEFAULT '',
                is_dofollow INTEGER NOT NULL DEFAULT 1,
                da INTEGER,
                da_checked_at TEXT,
                indexed INTEGER NOT NULL DEFAULT 0,
                live_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
                UNIQUE(customer_id, live_url)
            );
            CREATE INDEX IF NOT EXISTS idx_offsite_assets ON offsite_assets(customer_id, id DESC);
            CREATE INDEX IF NOT EXISTS idx_offsite_assets_order ON offsite_assets(order_id);

            -- FATJOE product catalog — the single source of truth for what each
            -- order COSTS and WHERE Dan buys it. Editable in the dashboard so COGS
            -- never goes stale (FATJOE changes prices). Seeded once if empty.
            CREATE TABLE IF NOT EXISTS fatjoe_catalog (
                product_key TEXT PRIMARY KEY,            -- e.g. blogger_outreach_dr40
                family TEXT NOT NULL,                     -- citation|blogger_outreach|niche_edit|mention
                label TEXT NOT NULL,
                dr_tier INTEGER,                          -- links/edits only; NULL otherwise
                unit TEXT NOT NULL DEFAULT 'each',
                price_usd REAL NOT NULL DEFAULT 0,        -- our COGS (what FATJOE charges us)
                sell_usd REAL NOT NULL DEFAULT 0,         -- retail / client-facing ad-hoc price
                buy_url TEXT NOT NULL DEFAULT '',
                verified INTEGER NOT NULL DEFAULT 0,      -- 1 once Dan confirms the price vs FATJOE
                active INTEGER NOT NULL DEFAULT 1,
                sort INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
            );
        """)
        self._seed_fatjoe_catalog()

        # Migration v9 → v10: Stripe billing — one subscription row per Stripe
        # subscription, auto-matched to a customer by email; billing_events logs
        # every webhook delivery for idempotency. See dashboard /webhooks/stripe.
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT REFERENCES customers(id),   -- NULL until matched
                stripe_subscription_id TEXT NOT NULL UNIQUE,
                stripe_customer_id TEXT NOT NULL DEFAULT '',
                stripe_customer_email TEXT NOT NULL DEFAULT '',
                plan_name TEXT NOT NULL DEFAULT '',           -- Stripe product name (Optimize/Grow/Dominate)
                price_id TEXT NOT NULL DEFAULT '',
                amount_cents INTEGER NOT NULL DEFAULT 0,
                currency TEXT NOT NULL DEFAULT 'usd',
                billing_interval TEXT NOT NULL DEFAULT 'month',
                status TEXT NOT NULL DEFAULT 'incomplete',    -- active/trialing/past_due/canceled/unpaid/incomplete
                latest_invoice_status TEXT NOT NULL DEFAULT '',
                last_payment_at TEXT,
                current_period_end TEXT,
                cancel_at_period_end INTEGER NOT NULL DEFAULT 0,
                raw_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
                updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
            );
            CREATE INDEX IF NOT EXISTS idx_subscriptions_customer ON subscriptions(customer_id);
            CREATE INDEX IF NOT EXISTS idx_subscriptions_email ON subscriptions(stripe_customer_email);

            CREATE TABLE IF NOT EXISTS billing_events (
                stripe_event_id TEXT PRIMARY KEY,             -- idempotency guard
                type TEXT NOT NULL DEFAULT '',
                stripe_subscription_id TEXT,
                received_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
            );

            -- Real operating-expense ledger (what we ACTUALLY pay each month, for
            -- reimbursement) — distinct from the estimated cost model in
            -- geo_agent/expenses.py. One row per charge, bucketed to a 'YYYY-MM'
            -- month. Recurring subscriptions are seeded from RECURRING_TEMPLATES
            -- (dedup via template_key); one-off charges are added manually.
            CREATE TABLE IF NOT EXISTS expense_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                month TEXT NOT NULL,                          -- 'YYYY-MM' the charge belongs to
                incurred_on TEXT,                             -- optional exact date 'YYYY-MM-DD'
                category TEXT NOT NULL DEFAULT 'Other',
                vendor TEXT NOT NULL DEFAULT '',
                name TEXT NOT NULL DEFAULT '',
                amount_usd REAL NOT NULL DEFAULT 0,
                recurring INTEGER NOT NULL DEFAULT 0,         -- 1 = seeded from a recurring template
                template_key TEXT NOT NULL DEFAULT '',        -- links a seeded row to its template (per-month dedupe)
                note TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
                updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
            );
            CREATE INDEX IF NOT EXISTS idx_expense_entries_month ON expense_entries(month);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_expense_entries_seed
                ON expense_entries(month, template_key) WHERE template_key != '';
        """)

        # share_token may be missing on report_snapshots created before it was added.
        rs_cols = [r[1] for r in self.conn.execute("PRAGMA table_info(report_snapshots)").fetchall()]
        if "share_token" not in rs_cols:
            self.conn.execute("ALTER TABLE report_snapshots ADD COLUMN share_token TEXT NOT NULL DEFAULT ''")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_report_share_token ON report_snapshots(share_token)")

        # Retail (client-facing) pricing layer on top of FATJOE COGS. sell_usd is
        # the ad-hoc price we charge a client for a backlink/citation; margin =
        # sell_usd - price_usd. Guarded migration + one-time backfill of seed rows.
        cat_cols = [r[1] for r in self.conn.execute("PRAGMA table_info(fatjoe_catalog)").fetchall()]
        if "sell_usd" not in cat_cols:
            self.conn.execute("ALTER TABLE fatjoe_catalog ADD COLUMN sell_usd REAL NOT NULL DEFAULT 0")
            for key, sell in self._CATALOG_SELL_DEFAULTS.items():
                self.conn.execute(
                    "UPDATE fatjoe_catalog SET sell_usd = ? WHERE product_key = ? AND sell_usd = 0",
                    (sell, key),
                )
        oo_cols = [r[1] for r in self.conn.execute("PRAGMA table_info(offsite_orders)").fetchall()]
        if "sell_usd" not in oo_cols:
            self.conn.execute("ALTER TABLE offsite_orders ADD COLUMN sell_usd REAL NOT NULL DEFAULT 0")

        self.conn.execute(
            "UPDATE schema_version SET version = ?", (SCHEMA_VERSION,)
        )
        self.conn.commit()

    def checkpoint(self):
        """Best-effort WAL truncation. Call after a heavy write burst (a pipeline
        run, an AI audit) so the -wal file is reset to zero instead of lingering at
        its high-water mark. No-op if another connection holds the lock — we never
        want to stall a request on this. The frozen multi-MB WAL behind the
        2026-06-12 'database is locked' outage is exactly what this prevents."""
        try:
            self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except sqlite3.OperationalError:
            pass

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # --- Customer CRUD ---

    def add_customer(
        self,
        id: str,
        name: str,
        domain: str,
        platform: str = "webflow",
        business_type: str = "practice",
        city: str = "",
        state: str = "",
        zip: str = "",
        address: str = "",
        phone: str = "",
        email: str = "",
        brand_voice: str = "Professional and warm",
        webflow_site_id: str = "",
        specialties: list[str] | None = None,
        insurance_accepted: list[str] | None = None,
        hours: str = "",
        emergency_available: bool = False,
        competitors: list[str] | None = None,
    ) -> str:
        self.conn.execute(
            """INSERT INTO customers
            (id, name, domain, platform, business_type, city, state, zip, address, phone, email,
             brand_voice, webflow_site_id, specialties, insurance_accepted, hours,
             emergency_available, competitors_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                id, name, domain, platform, business_type, city, state, zip, address, phone, email,
                brand_voice, webflow_site_id,
                json.dumps(specialties or []),
                json.dumps(insurance_accepted or []),
                hours,
                int(emergency_available),
                json.dumps(competitors or []),
            ),
        )
        self.conn.commit()
        logger.info(f"Added customer: {id} ({name})")
        return id

    def get_customer(self, customer_id: str) -> dict | None:
        cur = self.conn.execute(
            "SELECT * FROM customers WHERE id = ?", (customer_id,)
        )
        row = cur.fetchone()
        if not row:
            return None
        return self._row_to_customer_dict(row)

    def list_customers(self, status: str | None = None) -> list[dict]:
        if status:
            cur = self.conn.execute(
                "SELECT * FROM customers WHERE status = ? ORDER BY name", (status,)
            )
        else:
            cur = self.conn.execute("SELECT * FROM customers ORDER BY name")
        return [self._row_to_customer_dict(row) for row in cur.fetchall()]

    def update_customer(self, customer_id: str, **fields) -> bool:
        if not fields:
            return False
        # Handle JSON fields
        for key in ("specialties", "insurance_accepted", "competitors", "verified_quotes"):
            if key in fields and isinstance(fields[key], list):
                json_key = "competitors_json" if key == "competitors" else key
                fields[json_key] = json.dumps(fields.pop(key))
        if "emergency_available" in fields:
            fields["emergency_available"] = int(fields["emergency_available"])

        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [customer_id]
        self.conn.execute(
            f"UPDATE customers SET {set_clause} WHERE id = ?", values
        )
        self.conn.commit()
        return self.conn.total_changes > 0

    def set_customer_status(self, customer_id: str, status: str):
        from geo_agent.fsm import validate_customer_transition
        current = self.get_customer(customer_id)
        if current:
            validate_customer_transition(current["status"], status)
        updates = {"status": status}
        if status == "active":
            updates["onboarded_at"] = datetime.now(timezone.utc).isoformat()
        self.update_customer(customer_id, **updates)

    # ───────────────────────────── Billing (Stripe) ─────────────────────────────

    def billing_event_seen(self, event_id: str) -> bool:
        """True if this Stripe event was already processed (idempotency)."""
        if not event_id:
            return False
        row = self.conn.execute(
            "SELECT 1 FROM billing_events WHERE stripe_event_id = ?", (event_id,)
        ).fetchone()
        return row is not None

    def record_billing_event(self, event_id: str, event_type: str,
                             subscription_id: str | None = None) -> None:
        """Log a processed webhook event. Safe to call repeatedly."""
        if not event_id:
            return
        self.conn.execute(
            "INSERT OR IGNORE INTO billing_events (stripe_event_id, type, stripe_subscription_id) "
            "VALUES (?, ?, ?)",
            (event_id, event_type, subscription_id),
        )
        self.conn.commit()

    def _customer_id_for_email(self, email: str) -> str | None:
        """Auto-match a Stripe customer to one of ours. Tries, in order:
        1. exact email match (case-insensitive),
        2. email-domain ↔ practice website domain (e.g. danny@paradigmexperts.com
           → the customer whose domain is paradigmexperts.com), skipping generic
           mail hosts so gmail.com never matches.
        Returns None on no match or an ambiguous (>1) match."""
        if not email or "@" not in email:
            return None
        email = email.strip()
        rows = self.conn.execute(
            "SELECT id FROM customers WHERE lower(email) = lower(?)", (email,)
        ).fetchall()
        if len(rows) == 1:
            return rows[0]["id"]
        if rows:
            return None  # ambiguous exact match — don't guess

        # Domain fallback.
        def _norm(d: str) -> str:
            d = (d or "").lower().strip()
            for p in ("https://", "http://", "www."):
                if d.startswith(p):
                    d = d[len(p):]
            return d.rstrip("/")

        mail_domain = _norm(email.rsplit("@", 1)[1])
        if not mail_domain or mail_domain in _GENERIC_EMAIL_DOMAINS:
            return None
        matches = [
            r["id"] for r in self.conn.execute("SELECT id, domain FROM customers").fetchall()
            if _norm(r["domain"]) == mail_domain
        ]
        return matches[0] if len(matches) == 1 else None

    def upsert_subscription(self, data: dict) -> dict | None:
        """Insert or update a subscription by stripe_subscription_id. Auto-matches
        to a customer by email when not already linked. `data` is the normalized
        dict produced by geo_agent.billing.parse_subscription(). Returns the stored
        row as a dict."""
        sub_id = data.get("stripe_subscription_id")
        if not sub_id:
            return None
        existing = self.conn.execute(
            "SELECT id, customer_id FROM subscriptions WHERE stripe_subscription_id = ?",
            (sub_id,),
        ).fetchone()

        # Auto-match a customer by email if we don't already have one linked.
        customer_id = existing["customer_id"] if existing else None
        if not customer_id:
            customer_id = self._customer_id_for_email(data.get("stripe_customer_email", ""))

        cols = {
            "customer_id": customer_id,
            "stripe_subscription_id": sub_id,
            "stripe_customer_id": data.get("stripe_customer_id", ""),
            "stripe_customer_email": data.get("stripe_customer_email", ""),
            "plan_name": data.get("plan_name", ""),
            "price_id": data.get("price_id", ""),
            "amount_cents": int(data.get("amount_cents", 0) or 0),
            "currency": data.get("currency", "usd"),
            "billing_interval": data.get("billing_interval", "month"),
            "status": data.get("status", "incomplete"),
            "latest_invoice_status": data.get("latest_invoice_status", ""),
            "last_payment_at": data.get("last_payment_at"),
            "current_period_end": data.get("current_period_end"),
            "cancel_at_period_end": int(bool(data.get("cancel_at_period_end"))),
            "raw_json": json.dumps(data.get("raw", {}))[:200000],
        }
        if existing:
            # Never blank an already-set last_payment_at on a non-payment event.
            if not cols["last_payment_at"]:
                cols.pop("last_payment_at")
            set_clause = ", ".join(f"{k} = ?" for k in cols)
            self.conn.execute(
                f"UPDATE subscriptions SET {set_clause}, updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now') "
                "WHERE stripe_subscription_id = ?",
                list(cols.values()) + [sub_id],
            )
        else:
            keys = list(cols)
            self.conn.execute(
                f"INSERT INTO subscriptions ({', '.join(keys)}) VALUES ({', '.join('?' for _ in keys)})",
                [cols[k] for k in keys],
            )
        self.conn.commit()
        return self.get_subscription_by_stripe_id(sub_id)

    def get_subscription_by_stripe_id(self, sub_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM subscriptions WHERE stripe_subscription_id = ?", (sub_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_subscription_for_customer(self, customer_id: str) -> dict | None:
        """Most relevant subscription for a customer — prefer an active one, else
        the most recently updated."""
        row = self.conn.execute(
            "SELECT * FROM subscriptions WHERE customer_id = ? "
            "ORDER BY (status IN ('active','trialing')) DESC, updated_at DESC LIMIT 1",
            (customer_id,),
        ).fetchone()
        return dict(row) if row else None

    # --- Cut-over gate (see specs/active/paying-only-recurring-work.md) ----------
    # Subscription statuses that count as actively paying (same notion the FATJOE
    # queue + billing page use). Billing signal only — NOT the recurring-work gate.
    PAYING_SUB_STATUSES = frozenset({"active", "trialing"})

    def is_paying(self, customer_id: str) -> bool:
        """True if the customer has an active/trialing subscription. Billing signal
        (shown in the UI); the recurring-work gate is `is_cutover`, not this."""
        sub = self.get_subscription_for_customer(customer_id)
        return bool(sub and sub.get("status") in self.PAYING_SUB_STATUSES)

    def is_cutover(self, customer_id: str) -> bool:
        """True once the operator marks the customer cut over — site live with our
        changes / managed in Cloudflare. Gates ALL recurring LLM work (3x/week +
        weekly AI, monthly/biweekly content, daily alerts, content queue) so we
        don't pay for LLM runs — or pollute baselines — on customers that haven't
        really started. New customers get only a one-time baseline until cut over."""
        c = self.get_customer(customer_id)
        return bool(c and c.get("cutover"))

    def set_cutover(self, customer_id: str, on: bool, when: str | None = None) -> bool:
        """Toggle the cut-over flag; stamps `cutover_at` (ISO date) when turning on."""
        if on:
            from datetime import datetime, timezone
            stamp = when or datetime.now(timezone.utc).strftime("%Y-%m-%d")
            return self.update_customer(customer_id, cutover=1, cutover_at=stamp)
        return self.update_customer(customer_id, cutover=0, cutover_at=None)

    def list_recurring_customers(self) -> list[dict]:
        """Customers eligible for full recurring service: those marked cut over."""
        return [c for c in self.list_customers() if c.get("cutover")]

    def _recurring_ids_sql(self) -> tuple[str, tuple]:
        """(sub-SELECT of cut-over customer_ids, params) for cheap COUNT gating —
        keeps badge queries to a single statement with no per-customer Python loop."""
        return ("SELECT id FROM customers WHERE cutover = 1", ())

    def list_subscriptions(self) -> list[dict]:
        """All subscriptions joined to customer name (NULL name = unmatched)."""
        rows = self.conn.execute(
            "SELECT s.*, c.name AS customer_name FROM subscriptions s "
            "LEFT JOIN customers c ON c.id = s.customer_id "
            "ORDER BY (s.status IN ('active','trialing')) DESC, s.updated_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def link_subscription(self, sub_id: str, customer_id: str | None) -> bool:
        """Manually link/override (or unlink with None) a subscription's customer."""
        self.conn.execute(
            "UPDATE subscriptions SET customer_id = ?, "
            "updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE stripe_subscription_id = ?",
            (customer_id, sub_id),
        )
        self.conn.commit()
        return self.conn.total_changes > 0

    ONBOARDING_STEPS = [
        "new", "outreach", "setup", "review", "live",
        "content", "monitoring", "attention", "paused",
    ]

    def set_onboarding_step(self, customer_id: str, step: str):
        if step in self.ONBOARDING_STEPS:
            self.conn.execute(
                "UPDATE customers SET onboarding_step = ? WHERE id = ?",
                (step, customer_id),
            )
            self.conn.commit()

    def _row_to_customer_dict(self, row: sqlite3.Row) -> dict:
        d = dict(row)
        d["specialties"] = json.loads(d.get("specialties", "[]"))
        d["insurance_accepted"] = json.loads(d.get("insurance_accepted", "[]"))
        d["competitors"] = json.loads(d.pop("competitors_json", "[]"))
        d["emergency_available"] = bool(d.get("emergency_available", 0))
        d["hosting_info"] = json.loads(d.get("hosting_info", "{}"))
        d["verified_quotes"] = json.loads(d.get("verified_quotes", "[]"))
        d["service_areas"] = json.loads(d.get("service_areas", "[]"))
        d["live_area_pages"] = json.loads(d.get("live_area_pages", "[]"))
        return d

    def to_config_customer(self, customer_id: str) -> Customer | None:
        """Convert a DB customer to a geo_agent.config.Customer for pipeline use."""
        data = self.get_customer(customer_id)
        if not data:
            return None

        providers_rows = self.get_providers(customer_id)
        providers = [
            Provider(
                name=p["name"],
                credentials=p["credentials"],
                specialties=json.loads(p["specialties"]) if isinstance(p["specialties"], str) else p["specialties"],
                years_experience=p.get("years_experience"),
                bio=p.get("bio", ""),
            )
            for p in providers_rows
        ]

        from geo_agent.secrets import get_secrets
        secrets = get_secrets()
        webflow_api_key = secrets.get_customer_secret(customer_id, "WEBFLOW_KEY") or ""

        return Customer(
            id=data["id"],
            name=data["name"],
            domain=data["domain"],
            city=data["city"],
            state=data["state"],
            address=data.get("address", ""),
            phone=data.get("phone", ""),
            zip_code=data.get("zip", ""),
            business_type=data.get("business_type", "practice"),
            webflow_site_id=data.get("webflow_site_id", ""),
            webflow_api_key=webflow_api_key,
            specialties=data.get("specialties", []),
            brand_voice=data.get("brand_voice", "Professional and warm"),
            providers=providers,
            competitors=data.get("competitors", []),
            insurance_accepted=data.get("insurance_accepted", []),
            hours=data.get("hours", ""),
            emergency_available=data.get("emergency_available", False),
            services=[s["name"] for s in self.get_services(customer_id)],
            verified_quotes=data.get("verified_quotes", []),
        )

    # --- Providers ---

    def add_provider(
        self,
        customer_id: str,
        name: str,
        credentials: str = "",
        specialties: list[str] | None = None,
        years_experience: int | None = None,
        bio: str = "",
        is_primary: bool = False,
    ) -> int:
        cur = self.conn.execute(
            """INSERT INTO providers (customer_id, name, credentials, specialties,
               years_experience, bio, is_primary)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (customer_id, name, credentials, json.dumps(specialties or []),
             years_experience, bio, int(is_primary)),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_providers(self, customer_id: str) -> list[dict]:
        cur = self.conn.execute(
            "SELECT * FROM providers WHERE customer_id = ?", (customer_id,)
        )
        rows = []
        for r in cur.fetchall():
            d = dict(r)
            d["specialties"] = json.loads(d.get("specialties", "[]"))
            rows.append(d)
        return rows

    # --- Services ---

    def add_service(
        self, customer_id: str, name: str, category: str = "primary", description: str = ""
    ) -> int:
        cur = self.conn.execute(
            "INSERT INTO services (customer_id, name, category, description) VALUES (?, ?, ?, ?)",
            (customer_id, name, category, description),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_services(self, customer_id: str) -> list[dict]:
        cur = self.conn.execute(
            "SELECT * FROM services WHERE customer_id = ?", (customer_id,)
        )
        return [dict(r) for r in cur.fetchall()]

    def delete_service(self, customer_id: str, service_id: int) -> bool:
        self.conn.execute(
            "DELETE FROM services WHERE id = ? AND customer_id = ?",
            (service_id, customer_id),
        )
        self.conn.commit()
        return self.conn.total_changes > 0

    # --- Contacts ---

    def add_contact(
        self, customer_id: str, name: str, email: str = "", phone: str = "", role: str = "owner"
    ) -> int:
        cur = self.conn.execute(
            "INSERT INTO contacts (customer_id, name, email, phone, role) VALUES (?, ?, ?, ?, ?)",
            (customer_id, name, email, phone, role),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_contacts(self, customer_id: str) -> list[dict]:
        cur = self.conn.execute(
            "SELECT * FROM contacts WHERE customer_id = ?", (customer_id,)
        )
        return [dict(r) for r in cur.fetchall()]

    def get_contact(self, contact_id: int) -> dict | None:
        cur = self.conn.execute("SELECT * FROM contacts WHERE id = ?", (contact_id,))
        row = cur.fetchone()
        return dict(row) if row else None

    def update_contact(self, contact_id: int, **fields) -> bool:
        allowed = {"name", "email", "phone", "role"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return False
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        self.conn.execute(
            f"UPDATE contacts SET {set_clause} WHERE id = ?",
            list(updates.values()) + [contact_id],
        )
        self.conn.commit()
        return self.conn.total_changes > 0

    def delete_contact(self, contact_id: int) -> bool:
        self.conn.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
        self.conn.commit()
        return self.conn.total_changes > 0

    def get_email_customer_index(self) -> dict:
        """Build lookups for routing inbound email to a customer.

        Returns {"emails": {addr_lower: customer_id}, "domains": {domain: customer_id}}.
        - emails: every contact email (most precise — handles personal gmail addrs).
        - domains: each customer's website domain (so mail from anyone @theirdomain
          routes correctly). Generic mail hosts are never used as domain keys.
        """
        emails: dict[str, str] = {}
        domains: dict[str, str] = {}
        for c in self.list_customers():
            cid = c["id"]
            dom = (c.get("domain") or "").lower().strip()
            dom = re.sub(r"^www\.", "", dom)
            if dom and dom not in _GENERIC_EMAIL_DOMAINS:
                domains.setdefault(dom, cid)
            for ct in self.get_contacts(cid):
                addr = (ct.get("email") or "").lower().strip()
                if addr and "@" in addr:
                    emails.setdefault(addr, cid)
        return {"emails": emails, "domains": domains}

    # --- Platform Access ---

    def add_platform_access(
        self, customer_id: str, platform: str, status: str = "pending", notes: str = ""
    ) -> int:
        cur = self.conn.execute(
            "INSERT INTO platform_access (customer_id, platform, status, notes) VALUES (?, ?, ?, ?)",
            (customer_id, platform, status, notes),
        )
        self.conn.commit()
        return cur.lastrowid

    def update_access_status(self, customer_id: str, platform: str, status: str):
        granted_at = datetime.now(timezone.utc).isoformat() if status == "granted" else None
        self.conn.execute(
            """UPDATE platform_access SET status = ?, granted_at = ?
            WHERE customer_id = ? AND platform = ?""",
            (status, granted_at, customer_id, platform),
        )
        self.conn.commit()

    def get_platform_access(self, customer_id: str) -> list[dict]:
        cur = self.conn.execute(
            "SELECT * FROM platform_access WHERE customer_id = ?", (customer_id,)
        )
        return [dict(r) for r in cur.fetchall()]

    def get_pending_access(self, customer_id: str) -> list[dict]:
        cur = self.conn.execute(
            "SELECT * FROM platform_access WHERE customer_id = ? AND status = 'pending'",
            (customer_id,),
        )
        return [dict(r) for r in cur.fetchall()]

    # --- Google Places ---

    def upsert_google_places(
        self, customer_id: str, place_id: str, rating: float, review_count: int,
        match_confidence: str, lat: float = 0.0, lng: float = 0.0,
    ):
        self.conn.execute(
            """INSERT INTO google_places (customer_id, place_id, rating, review_count,
               match_confidence, lat, lng, last_checked)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(customer_id) DO UPDATE SET
               place_id=excluded.place_id, rating=excluded.rating,
               review_count=excluded.review_count, match_confidence=excluded.match_confidence,
               lat=excluded.lat, lng=excluded.lng, last_checked=excluded.last_checked""",
            (customer_id, place_id, rating, review_count, match_confidence,
             lat, lng, datetime.now(timezone.utc).isoformat()),
        )
        self.conn.commit()

    def get_google_places(self, customer_id: str) -> dict | None:
        cur = self.conn.execute(
            "SELECT * FROM google_places WHERE customer_id = ?", (customer_id,)
        )
        row = cur.fetchone()
        return dict(row) if row else None

    # --- Competitors ---

    def add_competitor(
        self, customer_id: str, name: str, rating: float = 0.0,
        review_count: int = 0, location: str = "", place_id: str = "",
    ) -> int:
        cur = self.conn.execute(
            """INSERT INTO competitors (customer_id, name, rating, review_count, location, place_id)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (customer_id, name, rating, review_count, location, place_id),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_competitors(self, customer_id: str) -> list[dict]:
        cur = self.conn.execute(
            "SELECT * FROM competitors WHERE customer_id = ? ORDER BY review_count DESC",
            (customer_id,),
        )
        return [dict(r) for r in cur.fetchall()]

    def replace_competitors(self, customer_id: str, competitors: list[dict]):
        self.conn.execute("DELETE FROM competitors WHERE customer_id = ?", (customer_id,))
        for c in competitors:
            self.conn.execute(
                """INSERT INTO competitors (customer_id, name, rating, review_count, location, place_id)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (customer_id, c["name"], c.get("rating", 0.0), c.get("review_count", 0),
                 c.get("location", c.get("address", "")), c.get("place_id", "")),
            )
        self.conn.commit()

    # --- Runs ---

    def create_run(self, customer_id: str) -> int:
        from geo_agent.fsm import check_no_active_run
        check_no_active_run(self, customer_id)
        cur = self.conn.execute(
            "INSERT INTO runs (customer_id) VALUES (?)", (customer_id,)
        )
        self.conn.commit()
        return cur.lastrowid

    def update_run(self, run_id: int, **fields):
        if "changes" in fields and isinstance(fields["changes"], list):
            fields["changes_json"] = json.dumps(fields.pop("changes"))
        if "errors" in fields and isinstance(fields["errors"], list):
            fields["errors_json"] = json.dumps(fields.pop("errors"))

        # Validate state transition if status is changing
        if "status" in fields:
            from geo_agent.fsm import validate_run_transition
            cur_row = self.conn.execute("SELECT status FROM runs WHERE id = ?", (run_id,)).fetchone()
            if cur_row:
                validate_run_transition(cur_row["status"], fields["status"])

        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [run_id]
        self.conn.execute(f"UPDATE runs SET {set_clause} WHERE id = ?", values)
        self.conn.commit()

    def get_latest_run(self, customer_id: str) -> dict | None:
        cur = self.conn.execute(
            "SELECT * FROM runs WHERE customer_id = ? ORDER BY run_date DESC LIMIT 1",
            (customer_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        d = dict(row)
        d["changes"] = json.loads(d.pop("changes_json", "[]"))
        d["errors"] = json.loads(d.pop("errors_json", "[]"))
        return d

    def get_runs(self, customer_id: str, limit: int = 10) -> list[dict]:
        cur = self.conn.execute(
            "SELECT * FROM runs WHERE customer_id = ? ORDER BY run_date DESC LIMIT ?",
            (customer_id, limit),
        )
        rows = []
        for r in cur.fetchall():
            d = dict(r)
            d["changes"] = json.loads(d.pop("changes_json", "[]"))
            d["errors"] = json.loads(d.pop("errors_json", "[]"))
            rows.append(d)
        return rows

    def get_staged_runs(self) -> list[dict]:
        """Get all runs waiting for approval."""
        cur = self.conn.execute(
            "SELECT * FROM runs WHERE status = 'staged' AND approved = 0 ORDER BY run_date DESC"
        )
        rows = []
        for r in cur.fetchall():
            d = dict(r)
            d["changes"] = json.loads(d.pop("changes_json", "[]"))
            d["errors"] = json.loads(d.pop("errors_json", "[]"))
            rows.append(d)
        return rows

    def get_run(self, run_id: int) -> dict | None:
        cur = self.conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,))
        row = cur.fetchone()
        if not row:
            return None
        d = dict(row)
        d["changes"] = json.loads(d.pop("changes_json", "[]"))
        d["errors"] = json.loads(d.pop("errors_json", "[]"))
        return d

    # --- Run Steps ---

    PIPELINE_STEPS = [
        ("crawl", "Crawl Website"),
        ("places", "Google Places Verify"),
        ("rag", "Update RAG Store"),
        ("analysis", "Claude Analysis"),
        ("content_recs", "Content Recommendations"),
        ("competitor", "Competitor Intelligence"),
        ("schema_validation", "Schema Validation"),
        ("generate", "Generate Files"),
        ("stage", "Stage Changes"),
        ("publish", "Publish"),
    ]

    def init_run_steps(self, run_id: int) -> list[int]:
        """Create all pipeline step records for a run. Returns list of step IDs."""
        step_ids = []
        for step_name, step_label in self.PIPELINE_STEPS:
            cur = self.conn.execute(
                """INSERT INTO run_steps (run_id, step_name, step_label, status)
                VALUES (?, ?, ?, 'pending')""",
                (run_id, step_name, step_label),
            )
            step_ids.append(cur.lastrowid)
        self.conn.commit()
        return step_ids

    def start_step(self, run_id: int, step_name: str):
        """Mark a step as running."""
        from geo_agent.fsm import validate_step_transition
        cur = self.conn.execute(
            "SELECT status FROM run_steps WHERE run_id = ? AND step_name = ?",
            (run_id, step_name),
        )
        row = cur.fetchone()
        if row:
            validate_step_transition(row["status"], "running")
        self.conn.execute(
            """UPDATE run_steps SET status = 'running', started_at = ?
            WHERE run_id = ? AND step_name = ?""",
            (datetime.now(timezone.utc).isoformat(), run_id, step_name),
        )
        self.conn.commit()

    def finish_step(
        self, run_id: int, step_name: str, status: str = "success",
        log_text: str = "", result: dict | None = None, error_message: str = "",
    ):
        """Mark a step as completed (success/failed/skipped)."""
        from geo_agent.fsm import validate_step_transition
        now = datetime.now(timezone.utc).isoformat()
        # Validate transition
        cur_status = self.conn.execute(
            "SELECT status FROM run_steps WHERE run_id = ? AND step_name = ?",
            (run_id, step_name),
        ).fetchone()
        if cur_status:
            validate_step_transition(cur_status["status"], status)
        # Calculate duration
        cur = self.conn.execute(
            "SELECT started_at FROM run_steps WHERE run_id = ? AND step_name = ?",
            (run_id, step_name),
        )
        row = cur.fetchone()
        duration_ms = None
        if row and row["started_at"]:
            try:
                started = datetime.fromisoformat(row["started_at"])
                duration_ms = int((datetime.fromisoformat(now) - started).total_seconds() * 1000)
            except (ValueError, TypeError):
                pass

        self.conn.execute(
            """UPDATE run_steps SET status = ?, finished_at = ?, duration_ms = ?,
               log_text = ?, result_json = ?, error_message = ?
            WHERE run_id = ? AND step_name = ?""",
            (status, now, duration_ms, log_text,
             json.dumps(result or {}), error_message,
             run_id, step_name),
        )
        self.conn.commit()

    def skip_step(self, run_id: int, step_name: str, reason: str = ""):
        self.finish_step(run_id, step_name, status="skipped", log_text=reason)

    def get_run_steps(self, run_id: int) -> list[dict]:
        """Get all steps for a run, ordered by pipeline sequence."""
        cur = self.conn.execute(
            "SELECT * FROM run_steps WHERE run_id = ? ORDER BY id", (run_id,)
        )
        rows = []
        for r in cur.fetchall():
            d = dict(r)
            d["result"] = json.loads(d.pop("result_json", "{}"))
            rows.append(d)
        return rows

    def get_step(self, step_id: int) -> dict | None:
        cur = self.conn.execute("SELECT * FROM run_steps WHERE id = ?", (step_id,))
        row = cur.fetchone()
        if not row:
            return None
        d = dict(row)
        d["result"] = json.loads(d.pop("result_json", "{}"))
        return d

    def reset_step(self, run_id: int, step_name: str):
        """Reset a step to pending for retry."""
        self.conn.execute(
            """UPDATE run_steps SET status = 'pending', started_at = NULL,
               finished_at = NULL, duration_ms = NULL, log_text = '',
               result_json = '{}', error_message = ''
            WHERE run_id = ? AND step_name = ?""",
            (run_id, step_name),
        )
        self.conn.commit()

    def approve_run(self, run_id: int):
        self.conn.execute(
            "UPDATE runs SET approved = 1, approved_at = ?, status = 'approved' WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), run_id),
        )
        self.conn.commit()

    def mark_run_published(self, run_id: int):
        self.conn.execute(
            "UPDATE runs SET status = 'published', published_at = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), run_id),
        )
        self.conn.commit()

    # --- AI Mention Tracking ---

    def save_ai_mention_run(self, run: dict):
        """Save an AI mention check run summary."""
        self.conn.execute(
            """INSERT OR REPLACE INTO ai_mention_runs
               (id, customer_id, run_date, total_mentions, total_queries, mention_rate, avg_position, engines_json, prompt_set, methodology)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (run["id"], run["customer_id"], run["run_date"], run["total_mentions"],
             run["total_queries"], run["mention_rate"], run.get("avg_position"),
             json.dumps(run.get("engines", {})), run.get("prompt_set", "benchmark"),
             run.get("methodology", "2.0")),  # all new (grounded) runs are 2.0
        )
        self.conn.commit()

    def save_ai_mention_result(self, result: dict):
        """Save a single AI mention check result."""
        import json as _json
        citations = result.get("citations") or []
        samples = int(result.get("samples", 1) or 1)
        samples_mentioned = int(result.get("samples_mentioned", 1 if result["mentioned"] else 0))
        self.conn.execute(
            """INSERT INTO ai_mention_results
               (run_id, customer_id, engine, prompt, prompt_category, mentioned,
                position, quality_score, context, full_response, is_disclaimer,
                model, citations_json, samples, samples_mentioned)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (result["run_id"], result["customer_id"], result["engine"],
             result["prompt"], result.get("prompt_category", "general"),
             1 if result["mentioned"] else 0, result.get("position"),
             result.get("quality_score", 0),
             result.get("context", ""), result.get("full_response", ""),
             1 if result.get("is_disclaimer") else 0,
             result.get("model", ""),
             _json.dumps(citations) if not isinstance(citations, str) else citations,
             samples, samples_mentioned),
        )
        self.conn.commit()

    def get_ai_mention_runs(self, customer_id: str, limit: int = 52, methodology: str | None = None) -> list[dict]:
        """Get recent AI mention runs for a customer (newest first).

        Pass methodology='2.0' to count only grounded runs (the comparable series).
        """
        if methodology:
            cur = self.conn.execute(
                "SELECT * FROM ai_mention_runs WHERE customer_id = ? AND methodology = ? "
                "ORDER BY run_date DESC, created_at DESC LIMIT ?",
                (customer_id, methodology, limit),
            )
        else:
            cur = self.conn.execute(
                "SELECT * FROM ai_mention_runs WHERE customer_id = ? "
                "ORDER BY run_date DESC, created_at DESC LIMIT ?",
                (customer_id, limit),
            )
        return [dict(r) for r in cur.fetchall()]

    def get_ai_mention_results(self, run_id: str) -> list[dict]:
        """Get all results for a specific run."""
        cur = self.conn.execute(
            "SELECT * FROM ai_mention_results WHERE run_id = ? ORDER BY engine, prompt",
            (run_id,),
        )
        return [dict(r) for r in cur.fetchall()]

    def get_rolling_mention_rate(
        self, customer_id: str, prompt_set: str = "benchmark", window: int = 4
    ) -> dict | None:
        """Average mention rate over the last `window` completed runs of a prompt set.

        The headline AI-visibility number: a single run is a coin-flip, so the
        client-facing metric uses a rolling average for stability.
        """
        rows = self.conn.execute(
            "SELECT mention_rate, run_date FROM ai_mention_runs "
            "WHERE customer_id = ? AND prompt_set = ? AND total_queries > 0 AND methodology = '2.0' "
            "ORDER BY run_date DESC, created_at DESC LIMIT ?",
            (customer_id, prompt_set, window),
        ).fetchall()
        if not rows:
            return None
        rates = [r["mention_rate"] for r in rows]
        return {
            "rate": sum(rates) / len(rates),
            "runs": len(rates),
            "window": window,
            "latest_date": rows[0]["run_date"],
        }

    # --- Baseline (before/after proof) ---

    def get_baseline_run(self, customer_id: str) -> dict | None:
        """Return the run marked as the onboarding baseline, if any."""
        row = self.conn.execute(
            "SELECT * FROM ai_mention_runs WHERE customer_id = ? AND is_baseline = 1 LIMIT 1",
            (customer_id,),
        ).fetchone()
        return dict(row) if row else None

    def ensure_baseline_run(self, customer_id: str) -> dict | None:
        """Mark the earliest COMPLETED run as the baseline if none is marked yet.

        Skips aborted runs (total_queries=0) so the proof report can't show a
        fabricated 0%-to-now 'improvement' from a crashed first run.
        """
        existing = self.get_baseline_run(customer_id)
        if existing:
            return existing
        # Baseline must be a grounded (2.0) run — never an old ungrounded one.
        first = self.conn.execute(
            "SELECT * FROM ai_mention_runs WHERE customer_id = ? AND total_queries > 0 "
            "AND methodology = '2.0' ORDER BY run_date ASC, created_at ASC LIMIT 1",
            (customer_id,),
        ).fetchone()
        if not first:
            return None
        self.conn.execute("UPDATE ai_mention_runs SET is_baseline = 1 WHERE id = ?", (first["id"],))
        self.conn.commit()
        return dict(first)

    def set_baseline_run(self, customer_id: str, run_id: str) -> None:
        """Explicitly (re)set which run is the baseline for a customer."""
        self.conn.execute("UPDATE ai_mention_runs SET is_baseline = 0 WHERE customer_id = ?", (customer_id,))
        self.conn.execute(
            "UPDATE ai_mention_runs SET is_baseline = 1 WHERE id = ? AND customer_id = ?",
            (run_id, customer_id),
        )
        self.conn.commit()

    def get_published_content_events(self, customer_id: str, limit: int = 100) -> list[dict]:
        """Published content (for attribution: tie AI-visibility gains to our actions)."""
        cur = self.conn.execute(
            """SELECT title, rec_type, published_at,
                      platform_draft_url AS published_url
               FROM content_recommendations
               WHERE customer_id = ? AND status = 'published' AND published_at IS NOT NULL
               ORDER BY published_at DESC LIMIT ?""",
            (customer_id, limit),
        )
        return [dict(r) for r in cur.fetchall()]

    def get_citation_domains(self, customer_id: str, last_n_runs: int = 4) -> list[dict]:
        """Distinct source domains that cited the practice in grounded AI answers.

        The strongest proof artifact: 'your content was cited by these sources.'
        """
        import json as _json
        from urllib.parse import urlparse

        run_ids = [
            r["id"] for r in self.conn.execute(
                "SELECT id FROM ai_mention_runs WHERE customer_id = ? ORDER BY run_date DESC LIMIT ?",
                (customer_id, last_n_runs),
            ).fetchall()
        ]
        if not run_ids:
            return []
        placeholders = ",".join("?" * len(run_ids))
        rows = self.conn.execute(
            f"""SELECT citations_json FROM ai_mention_results
                WHERE customer_id = ? AND mentioned = 1 AND run_id IN ({placeholders})""",
            (customer_id, *run_ids),
        ).fetchall()
        counts: dict[str, int] = {}
        for row in rows:
            try:
                for cite in _json.loads(row["citations_json"] or "[]"):
                    if not cite:
                        continue
                    # Citations may be full URLs or bare domains (Gemini stores the
                    # source domain, not a URL).
                    dom = urlparse(cite).netloc or (cite if "/" not in cite and "." in cite else "")
                    if dom.startswith("www."):
                        dom = dom[4:]
                    if dom:
                        counts[dom] = counts.get(dom, 0) + 1
            except Exception:
                continue
        return [{"domain": d, "count": c} for d, c in sorted(counts.items(), key=lambda x: -x[1])]

    def get_uncited_prompts(
        self, customer_id: str, prompt_set: str = "benchmark",
        last_n_runs: int = 4, min_checks: int = 2,
    ) -> list[dict]:
        """Queries the practice is NOT cited on across recent runs (the gaps).

        These are the highest-leverage input to the 'adapt llms.txt/content over
        time' loop: each is a real question AI engines answer without the practice.
        Returns [{prompt, category, checks, mentions}] sorted by most-checked first.
        """
        run_ids = [
            r["id"] for r in self.conn.execute(
                "SELECT id FROM ai_mention_runs WHERE customer_id = ? AND prompt_set = ? "
                "AND total_queries > 0 AND methodology = '2.0' "
                "ORDER BY run_date DESC, created_at DESC LIMIT ?",
                (customer_id, prompt_set, last_n_runs),
            ).fetchall()
        ]
        if not run_ids:
            return []
        ph = ",".join("?" * len(run_ids))
        rows = self.conn.execute(
            f"""SELECT prompt, prompt_category AS category,
                       COUNT(*) AS checks, COALESCE(SUM(mentioned), 0) AS mentions
                FROM ai_mention_results
                WHERE customer_id = ? AND run_id IN ({ph})
                GROUP BY prompt, prompt_category""",
            (customer_id, *run_ids),
        ).fetchall()
        gaps = [
            {"prompt": r["prompt"], "category": r["category"], "checks": r["checks"], "mentions": r["mentions"]}
            for r in rows
            if r["checks"] >= min_checks and (r["mentions"] or 0) == 0
        ]
        gaps.sort(key=lambda g: -g["checks"])
        return gaps

    def get_ai_mention_results_by_customer(self, customer_id: str, limit: int = 200) -> list[dict]:
        """Get recent results across all runs for a customer."""
        cur = self.conn.execute(
            """SELECT r.*, mr.run_date FROM ai_mention_results r
               JOIN ai_mention_runs mr ON r.run_id = mr.id
               WHERE r.customer_id = ? ORDER BY mr.run_date DESC, r.engine LIMIT ?""",
            (customer_id, limit),
        )
        return [dict(r) for r in cur.fetchall()]

    def get_ai_mention_trends(self, customer_id: str, limit_runs: int = 12) -> list[dict]:
        """Get per-prompt, per-engine results across recent runs for trend tracking.

        Returns list of dicts with: run_date, prompt, prompt_category, engine, mentioned, position, quality_score
        Ordered by run_date ASC so charts go left-to-right chronologically.
        """
        cur = self.conn.execute(
            """SELECT mr.run_date, r.prompt, r.prompt_category, r.engine,
                      r.mentioned, r.position, r.quality_score
               FROM ai_mention_results r
               JOIN ai_mention_runs mr ON r.run_id = mr.id
               WHERE r.customer_id = ?
                 AND mr.id IN (
                     SELECT id FROM ai_mention_runs
                     WHERE customer_id = ? AND total_queries > 0
                     ORDER BY run_date DESC LIMIT ?
                 )
               ORDER BY mr.run_date ASC, r.prompt, r.engine""",
            (customer_id, customer_id, limit_runs),
        )
        return [dict(r) for r in cur.fetchall()]

    # --- KPIs ---

    def record_kpi(self, customer_id: str, metric: str, value: float, date: str | None = None):
        date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self.conn.execute(
            "INSERT INTO kpis (customer_id, date, metric, value) VALUES (?, ?, ?, ?)",
            (customer_id, date, metric, value),
        )
        self.conn.commit()

    def get_kpis(
        self, customer_id: str, metric: str | None = None, limit: int = 12
    ) -> list[dict]:
        if metric:
            cur = self.conn.execute(
                "SELECT * FROM kpis WHERE customer_id = ? AND metric = ? ORDER BY date DESC LIMIT ?",
                (customer_id, metric, limit),
            )
        else:
            cur = self.conn.execute(
                "SELECT * FROM kpis WHERE customer_id = ? ORDER BY date DESC LIMIT ?",
                (customer_id, limit),
            )
        return [dict(r) for r in cur.fetchall()]

    def get_latest_kpi(self, customer_id: str, metric: str) -> dict | None:
        cur = self.conn.execute(
            "SELECT * FROM kpis WHERE customer_id = ? AND metric = ? ORDER BY date DESC LIMIT 1",
            (customer_id, metric),
        )
        row = cur.fetchone()
        return dict(row) if row else None

    # --- VA Checklist ---

    def set_checklist_item(self, customer_id: str, task_key: str, completed: bool):
        completed_at = datetime.now(timezone.utc).isoformat() if completed else None
        self.conn.execute(
            """INSERT INTO va_checklist (customer_id, task_key, completed, completed_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(customer_id, task_key) DO UPDATE SET
                completed = excluded.completed, completed_at = excluded.completed_at""",
            (customer_id, task_key, int(completed), completed_at),
        )
        self.conn.commit()

    def set_live_area_pages(self, customer_id: str, areas: list[str]):
        """Persist the service-area cities detected as live on the site (JSON)."""
        self.conn.execute(
            "UPDATE customers SET live_area_pages = ? WHERE id = ?",
            (json.dumps(areas or []), customer_id),
        )
        self.conn.commit()

    def get_checklist(self, customer_id: str) -> dict[str, bool]:
        """Return {task_key: completed} for a customer."""
        cur = self.conn.execute(
            "SELECT task_key, completed FROM va_checklist WHERE customer_id = ?",
            (customer_id,),
        )
        return {r["task_key"]: bool(r["completed"]) for r in cur.fetchall()}

    def get_content_recommendation_counts(self, customer_id: str) -> dict:
        """Return {approved: N, published: N, total: N} for a customer."""
        cur = self.conn.execute(
            """SELECT status, COUNT(*) as cnt FROM content_recommendations
               WHERE customer_id = ? GROUP BY status""",
            (customer_id,),
        )
        counts = {"approved": 0, "published": 0, "total": 0}
        for r in cur.fetchall():
            counts[r["status"]] = r["cnt"]
            counts["total"] += r["cnt"]
        return counts

    def get_latest_ai_run_summary(self, customer_id: str, prompt_set: str = "benchmark") -> dict | None:
        """Return {mention_count, total_queries, mention_rate} from most recent run.

        Filters by prompt_set so dashboard shows benchmark-consistent data.
        """
        cur = self.conn.execute(
            """SELECT total_mentions, total_queries, mention_rate
               FROM ai_mention_runs WHERE customer_id = ? AND prompt_set = ?
               ORDER BY run_date DESC LIMIT 1""",
            (customer_id, prompt_set),
        )
        row = cur.fetchone()
        if not row:
            # Fall back to the latest run of any prompt set (e.g. a customer that
            # only has a 'comprehensive' run and no benchmark run yet).
            cur = self.conn.execute(
                """SELECT total_mentions, total_queries, mention_rate
                   FROM ai_mention_runs WHERE customer_id = ?
                   ORDER BY run_date DESC LIMIT 1""",
                (customer_id,),
            )
            row = cur.fetchone()
        if not row:
            return None
        return {
            "mention_count": row["total_mentions"],
            "total_queries": row["total_queries"],
            "mention_rate": row["mention_rate"],
        }

    def get_last_publish_date(self, customer_id: str) -> str | None:
        """Return most recent content publish date (ISO string) or None."""
        cur = self.conn.execute(
            """SELECT published_at FROM content_recommendations
               WHERE customer_id = ? AND status = 'published' AND published_at IS NOT NULL
               ORDER BY published_at DESC LIMIT 1""",
            (customer_id,),
        )
        row = cur.fetchone()
        return row["published_at"] if row else None

    # --- Rolling Averages ---

    def get_rolling_mention_stats(self, customer_id: str, window: int = 12, prompt_set: str = "benchmark") -> dict | None:
        """Compute rolling average mention rate over last N runs.

        Only compares runs with the same prompt_set (default: "benchmark")
        so trend data is apples-to-apples.

        Returns dict with current_rate, prev_rate, trend, run_count, rates list.
        Returns None if fewer than 3 runs exist.
        """
        cur = self.conn.execute(
            """SELECT mention_rate, total_mentions, total_queries, run_date
               FROM ai_mention_runs WHERE customer_id = ? AND total_queries > 0
               AND prompt_set = ?
               ORDER BY run_date DESC LIMIT ?""",
            (customer_id, prompt_set, window * 2),
        )
        rows = [dict(r) for r in cur.fetchall()]
        if len(rows) < 3:
            return None

        current_window = rows[:window]
        prev_window = rows[window:window * 2]

        current_rate = sum(r["mention_rate"] for r in current_window) / len(current_window)
        prev_rate = (sum(r["mention_rate"] for r in prev_window) / len(prev_window)) if prev_window else None

        if prev_rate is not None:
            diff = current_rate - prev_rate
            trend = "up" if diff > 0.02 else ("down" if diff < -0.02 else "flat")
        else:
            trend = "flat"

        return {
            "current_rate": round(current_rate, 4),
            "prev_rate": round(prev_rate, 4) if prev_rate is not None else None,
            "trend": trend,
            "run_count": len(rows),
            "rates": [r["mention_rate"] for r in reversed(current_window)],
            "dates": [r["run_date"] for r in reversed(current_window)],
        }

    # --- AI Response Entities ---

    def save_ai_response_entity(self, entity: dict):
        """Save a single extracted entity from an AI response."""
        self.conn.execute(
            """INSERT INTO ai_response_entities
               (result_id, run_id, customer_id, entity_name, entity_name_normalized,
                is_customer, position, engine, prompt, prompt_category, run_date)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (entity["result_id"], entity["run_id"], entity["customer_id"],
             entity["entity_name"], entity["entity_name_normalized"],
             1 if entity.get("is_customer") else 0, entity.get("position"),
             entity["engine"], entity["prompt"], entity.get("prompt_category", "general"),
             entity["run_date"]),
        )
        self.conn.commit()

    def save_ai_response_entities_batch(self, entities: list[dict]):
        """Batch insert entities (faster than one-by-one for backfill)."""
        self.conn.executemany(
            """INSERT INTO ai_response_entities
               (result_id, run_id, customer_id, entity_name, entity_name_normalized,
                is_customer, position, engine, prompt, prompt_category, run_date)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [(e["result_id"], e["run_id"], e["customer_id"],
              e["entity_name"], e["entity_name_normalized"],
              1 if e.get("is_customer") else 0, e.get("position"),
              e["engine"], e["prompt"], e.get("prompt_category", "general"),
              e["run_date"]) for e in entities],
        )
        self.conn.commit()

    def has_entities_for_run(self, run_id: str) -> bool:
        """Check if entities have already been extracted for a run."""
        cur = self.conn.execute(
            "SELECT 1 FROM ai_response_entities WHERE run_id = ? LIMIT 1", (run_id,)
        )
        return cur.fetchone() is not None

    def get_share_of_voice(self, customer_id: str, last_n_runs: int = 3) -> dict:
        """Compute share of voice: what % of AI mentions go to each business.

        Uses the last N runs. Returns dict with customer_share, competitors list,
        total counts, and per-entity stats.
        """
        # Get recent run IDs
        run_cur = self.conn.execute(
            """SELECT id FROM ai_mention_runs
               WHERE customer_id = ? AND total_queries > 0
               ORDER BY run_date DESC LIMIT ?""",
            (customer_id, last_n_runs),
        )
        run_ids = [r["id"] for r in run_cur.fetchall()]
        if not run_ids:
            return {"customer_share": 0, "competitors": [], "total_entity_mentions": 0}
        return self._sov_from_run_ids(customer_id, run_ids)

    def _sov_from_run_ids(self, customer_id: str, run_ids: list[str]) -> dict:
        """Entity share-of-voice across the given run_ids (shared by the pooled
        get_share_of_voice() and the per-run get_share_of_voice_history())."""
        if not run_ids:
            return {"customer_share": 0, "competitors": [], "total_entity_mentions": 0}
        placeholders = ",".join("?" * len(run_ids))
        cur = self.conn.execute(
            f"""SELECT entity_name_normalized, entity_name, is_customer,
                       COUNT(*) as mention_count,
                       AVG(position) as avg_position,
                       COUNT(DISTINCT prompt) as unique_queries
                FROM ai_response_entities
                WHERE customer_id = ? AND run_id IN ({placeholders})
                GROUP BY entity_name_normalized
                ORDER BY mention_count DESC""",
            [customer_id] + run_ids,
        )
        rows = [dict(r) for r in cur.fetchall()]

        # Drop review/directory/aggregator platforms (Trustpilot, BBB, Yelp, …).
        # They get cited heavily and otherwise show up as fake "competitors" and
        # dilute the share denominator. Filtered at read-time so already-stored
        # rows are cleaned without a backfill.
        from geo_agent.entity_extractor import is_platform_or_directory
        rows = [
            r for r in rows
            if r["is_customer"] or not is_platform_or_directory(r["entity_name_normalized"])
        ]

        total = sum(r["mention_count"] for r in rows)
        customer_mentions = sum(r["mention_count"] for r in rows if r["is_customer"])
        customer_share = customer_mentions / total if total > 0 else 0

        # Rank the customer among real businesses (1 = most-mentioned).
        ranked = sorted(rows, key=lambda r: -r["mention_count"])
        customer_rank = next((i + 1 for i, r in enumerate(ranked) if r["is_customer"]), None)

        competitors = []
        for r in rows:
            if not r["is_customer"]:
                competitors.append({
                    "name": r["entity_name"],
                    "normalized_name": r["entity_name_normalized"],
                    "mention_count": r["mention_count"],
                    "share": r["mention_count"] / total if total > 0 else 0,
                    "avg_position": round(r["avg_position"], 1) if r["avg_position"] else None,
                    "unique_queries": r["unique_queries"],
                })

        return {
            "customer_share": round(customer_share, 4),
            "customer_mentions": customer_mentions,
            "customer_rank": customer_rank,
            "competitors": competitors[:15],
            "total_entity_mentions": total,
            "total_unique_entities": len(rows),
            "runs_analyzed": len(run_ids),
        }

    def get_share_of_voice_history(self, customer_id: str, limit_runs: int = 12) -> list[dict]:
        """Per-run AI Share-of-Voice for the flagship-score trend (chronological).

        Each point: {date, sov_pct (0..100), rank}. Powers the "34% → 51%" story on
        the report + the dashboard sparkline. One point per mention run so movement
        is visible run-over-run."""
        run_cur = self.conn.execute(
            """SELECT id, run_date FROM ai_mention_runs
               WHERE customer_id = ? AND total_queries > 0
               ORDER BY run_date DESC LIMIT ?""",
            (customer_id, limit_runs),
        )
        runs = [dict(r) for r in run_cur.fetchall()]
        history = []
        for run in reversed(runs):  # oldest → newest
            sov = self._sov_from_run_ids(customer_id, [run["id"]])
            history.append({
                "date": (run.get("run_date") or "")[:10],
                "sov_pct": round((sov.get("customer_share", 0) or 0) * 100, 1),
                "rank": sov.get("customer_rank"),
            })
        return history

    def get_competitor_entity_trend(self, customer_id: str, limit_weeks: int = 8) -> list[dict]:
        """Get weekly share of voice trend for customer + top competitors.

        Returns list of weekly snapshots with per-entity mention counts.
        """
        cur = self.conn.execute(
            """SELECT entity_name_normalized, entity_name, is_customer,
                      strftime('%Y-W%W', run_date) as week,
                      COUNT(*) as mention_count
               FROM ai_response_entities
               WHERE customer_id = ?
               GROUP BY entity_name_normalized, week
               ORDER BY week DESC""",
            (customer_id,),
        )
        rows = [dict(r) for r in cur.fetchall()]

        # Find top entities (most mentions overall)
        entity_totals: dict[str, int] = {}
        for r in rows:
            entity_totals[r["entity_name_normalized"]] = entity_totals.get(r["entity_name_normalized"], 0) + r["mention_count"]

        # Get top 5 competitors + the customer
        top_competitors = sorted(
            [(k, v) for k, v in entity_totals.items()],
            key=lambda x: x[1], reverse=True,
        )[:8]
        top_names = {t[0] for t in top_competitors}

        # Build weekly data
        weeks: dict[str, dict] = {}
        name_map: dict[str, str] = {}  # normalized → display name
        for r in rows:
            norm = r["entity_name_normalized"]
            if norm not in top_names:
                continue
            name_map[norm] = r["entity_name"]
            w = r["week"]
            if w not in weeks:
                weeks[w] = {"week": w, "entities": {}}
            weeks[w]["entities"][norm] = r["mention_count"]

        sorted_weeks = sorted(weeks.values(), key=lambda x: x["week"], reverse=True)[:limit_weeks]
        sorted_weeks.reverse()  # chronological

        return {
            "weeks": sorted_weeks,
            "entities": [{"normalized_name": k, "name": name_map.get(k, k), "total": v}
                         for k, v in sorted(top_competitors, key=lambda x: x[1], reverse=True)],
        }

    def auto_discover_competitors_from_entities(self, customer_id: str, min_mentions: int = 5) -> list[str]:
        """Promote frequently-mentioned entities to competitor_domains.

        Returns list of newly added competitor names.
        """
        cur = self.conn.execute(
            """SELECT entity_name_normalized, entity_name, COUNT(*) as cnt
               FROM ai_response_entities
               WHERE customer_id = ? AND is_customer = 0
               GROUP BY entity_name_normalized
               HAVING cnt >= ?
               ORDER BY cnt DESC LIMIT 20""",
            (customer_id, min_mentions),
        )
        candidates = [dict(r) for r in cur.fetchall()]

        # Get existing competitor names
        existing = self.get_competitor_domains(customer_id)
        existing_names = {c["competitor_name"].lower().strip() for c in existing if c.get("competitor_name")}

        added = []
        for c in candidates:
            if c["entity_name_normalized"] in existing_names:
                continue
            try:
                self.conn.execute(
                    """INSERT INTO competitor_domains
                       (customer_id, competitor_domain, competitor_name, discovered_via)
                       VALUES (?, ?, ?, ?)""",
                    (customer_id, "", c["entity_name"], "ai_response"),
                )
                added.append(c["entity_name"])
            except Exception:
                pass  # duplicate or constraint
        if added:
            self.conn.commit()
        return added

    # --- Weekly AI Summaries ---

    def get_weekly_ai_summaries(self, customer_id: str, weeks: int = 12, prompt_set: str = "benchmark") -> list[dict]:
        """Aggregate AI mention runs into weekly summaries.

        Groups runs by ISO week, computes average mention rate, total mentions,
        and week-over-week delta. Returns most recent weeks first.
        """
        cur = self.conn.execute(
            """SELECT id, run_date, mention_rate, total_mentions, total_queries,
                      avg_position, engines_json,
                      strftime('%Y-W%W', run_date) as week
               FROM ai_mention_runs
               WHERE customer_id = ? AND total_queries > 0 AND prompt_set = ?
               ORDER BY run_date DESC""",
            (customer_id, prompt_set),
        )
        rows = [dict(r) for r in cur.fetchall()]
        if not rows:
            return []

        # Group by week
        weeks_data: dict[str, list[dict]] = {}
        for row in rows:
            w = row["week"]
            weeks_data.setdefault(w, []).append(row)

        # Compute per-week aggregates
        summaries = []
        sorted_weeks = sorted(weeks_data.keys(), reverse=True)[:weeks]

        for i, w in enumerate(sorted_weeks):
            runs = weeks_data[w]
            avg_rate = sum(r["mention_rate"] for r in runs) / len(runs)
            total_m = sum(r["total_mentions"] for r in runs)
            total_q = sum(r["total_queries"] for r in runs)
            positions = [r["avg_position"] for r in runs if r["avg_position"]]
            avg_pos = sum(positions) / len(positions) if positions else None

            # Week-over-week delta
            prev_week = sorted_weeks[i + 1] if i + 1 < len(sorted_weeks) else None
            delta_rate = None
            delta_pct = None
            if prev_week and prev_week in weeks_data:
                prev_runs = weeks_data[prev_week]
                prev_avg = sum(r["mention_rate"] for r in prev_runs) / len(prev_runs)
                delta_rate = round(avg_rate - prev_avg, 4)
                if prev_avg > 0:
                    delta_pct = f"{delta_rate / prev_avg * 100:+.1f}%"

            # Per-engine aggregates
            engine_agg: dict[str, dict] = {}
            for run in runs:
                engines = json.loads(run["engines_json"]) if isinstance(run.get("engines_json"), str) else run.get("engines_json", {})
                for eng, stats in engines.items():
                    if eng not in engine_agg:
                        engine_agg[eng] = {"mentions": 0, "total": 0}
                    engine_agg[eng]["mentions"] += stats.get("mentions", 0)
                    engine_agg[eng]["total"] += stats.get("total", 0)
            for eng in engine_agg:
                t = engine_agg[eng]["total"]
                engine_agg[eng]["rate"] = round(engine_agg[eng]["mentions"] / t, 4) if t > 0 else 0

            dates = sorted(r["run_date"] for r in runs)
            summaries.append({
                "week": w,
                "week_start": dates[0],
                "week_end": dates[-1],
                "run_count": len(runs),
                "avg_mention_rate": round(avg_rate, 4),
                "total_mentions": total_m,
                "total_queries": total_q,
                "avg_position": round(avg_pos, 1) if avg_pos else None,
                "delta_rate": delta_rate,
                "delta_pct": delta_pct,
                "best_run_rate": round(max(r["mention_rate"] for r in runs), 4),
                "worst_run_rate": round(min(r["mention_rate"] for r in runs), 4),
                "engines": engine_agg,
                "runs": [{
                    "id": r["id"],
                    "date": r["run_date"],
                    "mentions": r["total_mentions"],
                    "total": r["total_queries"],
                    "rate": r["mention_rate"],
                    "avg_position": r["avg_position"],
                } for r in sorted(runs, key=lambda x: x["run_date"])],
            })

        return summaries

    # --- GSC Metrics ---

    def save_gsc_daily(self, customer_id: str, date: str, clicks: int, impressions: int, ctr: float, position: float):
        """Save a single day of GSC metrics (upsert)."""
        self.conn.execute(
            """INSERT OR REPLACE INTO gsc_daily_metrics (customer_id, date, clicks, impressions, ctr, position)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (customer_id, date, clicks, impressions, ctr, position),
        )
        self.conn.commit()

    def get_gsc_daily(self, customer_id: str, limit: int = 90) -> list[dict]:
        """Get daily GSC metrics, most recent first."""
        cur = self.conn.execute(
            "SELECT * FROM gsc_daily_metrics WHERE customer_id = ? ORDER BY date DESC LIMIT ?",
            (customer_id, limit),
        )
        return [dict(r) for r in cur.fetchall()]

    def get_gsc_weekly_summary(self, customer_id: str, weeks: int = 12) -> list[dict]:
        """Get weekly GSC summaries (clicks, impressions, avg position) for trending."""
        cur = self.conn.execute(
            """SELECT strftime('%Y-W%W', date) as week,
                      SUM(clicks) as clicks, SUM(impressions) as impressions,
                      AVG(ctr) as ctr, AVG(position) as position,
                      MIN(date) as week_start
               FROM gsc_daily_metrics WHERE customer_id = ?
               GROUP BY week ORDER BY week DESC LIMIT ?""",
            (customer_id, weeks),
        )
        return [dict(r) for r in cur.fetchall()]

    # --- Content Recommendations ---

    def add_content_recommendation(self, rec: dict) -> str:
        """Insert a content recommendation. rec must have 'id' key."""
        self.conn.execute(
            """INSERT OR REPLACE INTO content_recommendations
            (id, customer_id, rec_type, target_page, title, description, html_snippet,
             priority, category, status, ai_impact_reason, created_at,
             meta_description, author_attribution, reviewed_date, intent_tier)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                rec["id"], rec["customer_id"], rec["rec_type"],
                rec.get("target_page", ""), rec["title"],
                rec.get("description", ""), rec.get("html_snippet", ""),
                rec.get("priority", 3), rec.get("category", "general"),
                rec.get("status", "pending"), rec.get("ai_impact_reason", ""),
                rec.get("created_at", datetime.now(timezone.utc).isoformat()),
                rec.get("meta_description", ""), rec.get("author_attribution", ""),
                rec.get("reviewed_date", ""), rec.get("intent_tier", ""),
            ),
        )
        self.conn.commit()
        return rec["id"]

    def get_content_recommendations(
        self, customer_id: str, status: str | None = None, limit: int = 50
    ) -> list[dict]:
        """Get content recommendations for a customer, optionally filtered by status."""
        if status:
            cur = self.conn.execute(
                """SELECT * FROM content_recommendations
                WHERE customer_id = ? AND status = ?
                ORDER BY priority ASC, created_at DESC LIMIT ?""",
                (customer_id, status, limit),
            )
        else:
            cur = self.conn.execute(
                """SELECT * FROM content_recommendations
                WHERE customer_id = ?
                ORDER BY priority ASC, created_at DESC LIMIT ?""",
                (customer_id, limit),
            )
        return [dict(r) for r in cur.fetchall()]

    def update_content_recommendation_status(
        self, rec_id: str, status: str
    ) -> bool:
        """Update the status of a content recommendation."""
        updates = {"status": status}
        if status == "approved":
            updates["reviewed_at"] = datetime.now(timezone.utc).isoformat()
        elif status == "rejected":
            updates["reviewed_at"] = datetime.now(timezone.utc).isoformat()
        elif status == "published":
            updates["published_at"] = datetime.now(timezone.utc).isoformat()

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [rec_id]
        self.conn.execute(
            f"UPDATE content_recommendations SET {set_clause} WHERE id = ?", values
        )
        self.conn.commit()
        return self.conn.total_changes > 0

    def get_pending_recommendations_count(self, customer_id: str) -> int:
        """Get count of pending content recommendations."""
        cur = self.conn.execute(
            "SELECT COUNT(*) FROM content_recommendations WHERE customer_id = ? AND status = 'pending'",
            (customer_id,),
        )
        return cur.fetchone()[0]

    def count_all_pending_content(self) -> int:
        """Pending content recommendations across CUT-OVER customers only (drives the
        Content Queue sidebar badge — one cheap query, no per-customer loop).
        Not-yet-started customers are excluded until they're cut over."""
        recurring_sql, params = self._recurring_ids_sql()
        cur = self.conn.execute(
            f"SELECT COUNT(*) FROM content_recommendations "
            f"WHERE status = 'pending' AND customer_id IN ({recurring_sql})",
            params,
        )
        return int(cur.fetchone()[0] or 0)

    # --- Scheduled-job heartbeats (see geo_agent.job_health) ---
    def record_job_run(self, job_name: str, status: str = "ok", detail: str = "") -> None:
        """Upsert a scheduled job's heartbeat with the current UTC time."""
        self.conn.execute(
            """INSERT INTO job_heartbeats (job_name, last_run_at, status, detail)
               VALUES (?, strftime('%Y-%m-%dT%H:%M:%SZ','now'), ?, ?)
               ON CONFLICT(job_name) DO UPDATE SET
                 last_run_at=excluded.last_run_at, status=excluded.status, detail=excluded.detail""",
            (job_name, status, (detail or "")[:500]),
        )
        self.conn.commit()

    def get_job_heartbeats(self) -> dict[str, dict]:
        """{job_name: {last_run_at, status, detail}} for all recorded jobs."""
        rows = self.conn.execute(
            "SELECT job_name, last_run_at, status, detail FROM job_heartbeats"
        ).fetchall()
        return {r["job_name"]: dict(r) for r in rows}

    def get_content_recommendation(self, rec_id: str) -> dict | None:
        """Get a single content recommendation by ID."""
        cur = self.conn.execute(
            "SELECT * FROM content_recommendations WHERE id = ?", (rec_id,)
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def update_recommendation_webflow_ids(
        self, rec_id: str, webflow_item_id: str, webflow_collection_id: str
    ) -> None:
        """Store Webflow item/collection IDs after successful publish."""
        self.conn.execute(
            """UPDATE content_recommendations
            SET webflow_item_id = ?, webflow_collection_id = ?, publish_error = NULL,
                status = 'published', published_at = ?
            WHERE id = ?""",
            (webflow_item_id, webflow_collection_id,
             datetime.now(timezone.utc).isoformat(), rec_id),
        )
        self.conn.commit()

    def set_recommendation_publish_error(self, rec_id: str, error: str) -> None:
        """Store a publish error on a recommendation."""
        self.conn.execute(
            "UPDATE content_recommendations SET publish_error = ? WHERE id = ?",
            (error, rec_id),
        )
        self.conn.commit()

    def set_recommendation_platform_ids(
        self, rec_id: str, platform_item_id: str, platform_draft_url: str
    ) -> None:
        """Store platform-agnostic item ID and draft URL after push."""
        self.conn.execute(
            """UPDATE content_recommendations
            SET platform_item_id = ?, platform_draft_url = ?, publish_error = NULL,
                status = 'published', published_at = ?
            WHERE id = ?""",
            (platform_item_id, platform_draft_url,
             datetime.now(timezone.utc).isoformat(), rec_id),
        )
        self.conn.commit()

    # --- Content Translations ---

    def add_content_translation(self, translation: dict) -> str:
        """Insert or replace a content translation."""
        self.conn.execute(
            """INSERT OR REPLACE INTO content_translations
            (id, recommendation_id, locale, title, description, html_snippet, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                translation["id"],
                translation["recommendation_id"],
                translation["locale"],
                translation["title"],
                translation.get("description", ""),
                translation.get("html_snippet", ""),
                translation.get("created_at", datetime.now(timezone.utc).isoformat()),
            ),
        )
        self.conn.commit()
        return translation["id"]

    def get_content_translation(self, recommendation_id: str, locale: str) -> dict | None:
        """Get a translation for a specific recommendation and locale."""
        cur = self.conn.execute(
            "SELECT * FROM content_translations WHERE recommendation_id = ? AND locale = ?",
            (recommendation_id, locale),
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def get_translations_for_recommendation(self, recommendation_id: str) -> list[dict]:
        """Get all translations for a recommendation."""
        cur = self.conn.execute(
            "SELECT * FROM content_translations WHERE recommendation_id = ? ORDER BY locale",
            (recommendation_id,),
        )
        return [dict(r) for r in cur.fetchall()]

    def get_translated_content(self, customer_id: str, locale: str, status: str = "published") -> list[dict]:
        """Get content recommendations with translations merged in for a specific locale."""
        cur = self.conn.execute(
            """SELECT cr.*, ct.title AS translated_title, ct.description AS translated_description,
                      ct.html_snippet AS translated_html_snippet
               FROM content_recommendations cr
               LEFT JOIN content_translations ct ON cr.id = ct.recommendation_id AND ct.locale = ?
               WHERE cr.customer_id = ? AND cr.status = ?
               ORDER BY cr.priority ASC, cr.created_at DESC""",
            (locale, customer_id, status),
        )
        return [dict(r) for r in cur.fetchall()]

    # --- Squarespace Credentials ---

    def save_squarespace_credentials(
        self, customer_id: str, email: str, password_encrypted: str,
        site_url: str, totp_secret_encrypted: str = ""
    ) -> None:
        """Save encrypted Squarespace credentials."""
        self.conn.execute(
            """INSERT OR REPLACE INTO squarespace_credentials
            (customer_id, email, password_encrypted, site_url, totp_secret_encrypted, created_at)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (customer_id, email, password_encrypted, site_url, totp_secret_encrypted,
             datetime.now(timezone.utc).isoformat()),
        )
        self.conn.commit()

    def get_squarespace_credentials(self, customer_id: str) -> dict | None:
        """Get Squarespace credentials for a customer."""
        cur = self.conn.execute(
            "SELECT * FROM squarespace_credentials WHERE customer_id = ?",
            (customer_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None

    # --- Webflow Collections Cache ---

    def save_webflow_collection(
        self, customer_id: str, collection_type: str,
        webflow_collection_id: str, display_name: str
    ) -> None:
        """Cache a Webflow collection mapping."""
        import uuid
        self.conn.execute(
            """INSERT OR REPLACE INTO webflow_collections
            (id, customer_id, collection_type, webflow_collection_id, display_name)
            VALUES (?, ?, ?, ?, ?)""",
            (str(uuid.uuid4()), customer_id, collection_type, webflow_collection_id, display_name),
        )
        self.conn.commit()

    def get_webflow_collection(self, customer_id: str, collection_type: str) -> dict | None:
        """Get cached Webflow collection for a customer/type."""
        cur = self.conn.execute(
            """SELECT * FROM webflow_collections
            WHERE customer_id = ? AND collection_type = ?""",
            (customer_id, collection_type),
        )
        row = cur.fetchone()
        return dict(row) if row else None

    # --- Alerts ---

    def add_alert(
        self, customer_id: str, alert_type: str, severity: str,
        source: str, message: str, details: dict | None = None,
    ) -> int:
        cur = self.conn.execute(
            """INSERT INTO alerts (customer_id, alert_type, severity, source, message, details_json)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (customer_id, alert_type, severity, source, message, json.dumps(details or {})),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_alerts(
        self, customer_id: str | None = None, active_only: bool = True, limit: int = 50
    ) -> list[dict]:
        """Get alerts, optionally filtered by customer and dismissed status."""
        conditions = []
        params = []
        if customer_id:
            conditions.append("customer_id = ?")
            params.append(customer_id)
        if active_only:
            conditions.append("dismissed = 0")

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        params.append(limit)
        cur = self.conn.execute(
            f"SELECT * FROM alerts {where} ORDER BY created_at DESC LIMIT ?", params
        )
        rows = []
        for r in cur.fetchall():
            d = dict(r)
            d["details"] = json.loads(d.pop("details_json", "{}"))
            rows.append(d)
        return rows

    def dismiss_alert(self, alert_id: int):
        self.conn.execute("UPDATE alerts SET dismissed = 1 WHERE id = ?", (alert_id,))
        self.conn.commit()

    def dismiss_alerts_for_customer(self, customer_id: str, alert_types: list[str] | None = None):
        """Dismiss all active alerts for a customer, optionally filtered by type."""
        if alert_types:
            placeholders = ",".join("?" for _ in alert_types)
            self.conn.execute(
                f"UPDATE alerts SET dismissed = 1 WHERE customer_id = ? AND dismissed = 0 AND alert_type IN ({placeholders})",
                [customer_id] + alert_types,
            )
        else:
            self.conn.execute(
                "UPDATE alerts SET dismissed = 1 WHERE customer_id = ? AND dismissed = 0",
                (customer_id,),
            )
        self.conn.commit()

    def get_active_alert_count(self, customer_id: str | None = None) -> int:
        if customer_id:
            cur = self.conn.execute(
                "SELECT COUNT(*) FROM alerts WHERE customer_id = ? AND dismissed = 0",
                (customer_id,),
            )
        else:
            # Global badge: count only cut-over customers' alerts (others hidden).
            recurring_sql, params = self._recurring_ids_sql()
            cur = self.conn.execute(
                f"SELECT COUNT(*) FROM alerts WHERE dismissed = 0 "
                f"AND customer_id IN ({recurring_sql})",
                params,
            )
        return cur.fetchone()[0]

    # --- Webflow OAuth Tokens ---

    def save_webflow_oauth_token(self, site_id: str, customer_id: str, access_token: str):
        """Store a Webflow OAuth access token for a site."""
        self.conn.execute(
            """INSERT INTO webflow_oauth_tokens (site_id, customer_id, access_token)
               VALUES (?, ?, ?)
               ON CONFLICT(site_id) DO UPDATE SET
                   access_token = excluded.access_token,
                   granted_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')""",
            (site_id, customer_id, access_token),
        )
        self.conn.commit()

    def get_webflow_oauth_token(self, customer_id: str) -> str | None:
        """Get the OAuth access token for a customer's Webflow site."""
        cur = self.conn.execute(
            "SELECT access_token FROM webflow_oauth_tokens WHERE customer_id = ?",
            (customer_id,),
        )
        row = cur.fetchone()
        return row["access_token"] if row else None

    # --- Webflow OAuth Apps (per-customer) ---

    def save_webflow_oauth_app(self, customer_id: str, client_id: str, client_secret: str):
        """Store per-customer Webflow OAuth app credentials."""
        self.conn.execute(
            """INSERT INTO webflow_oauth_apps (customer_id, client_id, client_secret)
               VALUES (?, ?, ?)
               ON CONFLICT(customer_id) DO UPDATE SET
                   client_id = excluded.client_id,
                   client_secret = excluded.client_secret""",
            (customer_id, client_id, client_secret),
        )
        self.conn.commit()

    def get_webflow_oauth_app(self, customer_id: str) -> dict | None:
        """Get per-customer Webflow OAuth app credentials."""
        cur = self.conn.execute(
            "SELECT client_id, client_secret FROM webflow_oauth_apps WHERE customer_id = ?",
            (customer_id,),
        )
        row = cur.fetchone()
        return {"client_id": row["client_id"], "client_secret": row["client_secret"]} if row else None

    def delete_webflow_oauth_app(self, customer_id: str):
        self.conn.execute("DELETE FROM webflow_oauth_apps WHERE customer_id = ?", (customer_id,))
        self.conn.commit()

    # --- Dashboard Users ---

    @staticmethod
    def _hash_password(password: str) -> str:
        """Hash a password with scrypt + random salt."""
        salt = secrets.token_hex(16)
        h = hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1, dklen=32)
        return f"{salt}${h.hex()}"

    @staticmethod
    def _verify_password(password: str, password_hash: str) -> bool:
        """Verify a password against a stored hash."""
        try:
            salt, h_hex = password_hash.split("$", 1)
            h = hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1, dklen=32)
            return secrets.compare_digest(h.hex(), h_hex)
        except (ValueError, KeyError):
            return False

    def create_user(self, username: str, password: str, display_name: str = "", role: str = "admin") -> bool:
        """Create a dashboard user. Returns True on success, False if username exists."""
        try:
            self.conn.execute(
                """INSERT INTO dashboard_users (username, password_hash, display_name, role)
                   VALUES (?, ?, ?, ?)""",
                (username.lower().strip(), self._hash_password(password), display_name, role),
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def authenticate_user(self, username: str, password: str) -> dict | None:
        """Authenticate a user. Returns user dict on success, None on failure."""
        cur = self.conn.execute(
            "SELECT * FROM dashboard_users WHERE username = ? AND active = 1",
            (username.lower().strip(),),
        )
        user = cur.fetchone()
        if not user:
            return None
        if not self._verify_password(password, user["password_hash"]):
            return None
        # Update last_login
        self.conn.execute(
            "UPDATE dashboard_users SET last_login = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), user["id"]),
        )
        self.conn.commit()
        return dict(user)

    def list_users(self) -> list[dict]:
        """List all dashboard users (without password hashes)."""
        cur = self.conn.execute(
            "SELECT id, username, display_name, role, active, last_login, created_at FROM dashboard_users"
        )
        return [dict(r) for r in cur.fetchall()]

    def update_user_password(self, username: str, new_password: str) -> bool:
        """Update a user's password. Returns True if user found."""
        cur = self.conn.execute(
            "UPDATE dashboard_users SET password_hash = ? WHERE username = ?",
            (self._hash_password(new_password), username.lower().strip()),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def delete_user(self, username: str) -> bool:
        """Deactivate a user. Returns True if user found."""
        cur = self.conn.execute(
            "UPDATE dashboard_users SET active = 0 WHERE username = ?",
            (username.lower().strip(),),
        )
        self.conn.commit()
        return cur.rowcount > 0

    # --- Client Portal Users ---

    def create_client_user(self, customer_id: str, username: str, display_name: str = "") -> dict:
        """Create a client-portal user in the password-less invite state.

        Returns {"id": ..., "signup_token": ...}. Raises ValueError if the
        username is already taken (caught by the caller, not a bare sqlite3 error).
        """
        token = secrets.token_urlsafe(24)
        try:
            cur = self.conn.execute(
                """INSERT INTO client_users
                   (customer_id, username, display_name, signup_token, signup_token_created_at)
                   VALUES (?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%SZ','now'))""",
                (customer_id, username.strip(), display_name, token),
            )
            self.conn.commit()
        except sqlite3.IntegrityError:
            raise ValueError(f"Username '{username}' is already taken")
        return {"id": cur.lastrowid, "signup_token": token}

    def get_client_user_by_signup_token(self, token: str) -> dict | None:
        """Look up an invited-but-not-yet-signed-up client user by signup token."""
        if not token:
            return None
        cur = self.conn.execute(
            "SELECT * FROM client_users WHERE signup_token = ? AND password_hash IS NULL",
            (token,),
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def complete_client_signup(self, token: str, password: str) -> bool:
        """Consume a signup token and set the client's password. Returns False on an
        invalid/already-used/unknown token."""
        user = self.get_client_user_by_signup_token(token)
        if not user:
            return False
        cur = self.conn.execute(
            """UPDATE client_users SET password_hash = ?, signup_token = NULL,
               signup_token_created_at = NULL WHERE id = ? AND signup_token = ?""",
            (self._hash_password(password), user["id"], token),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def regenerate_client_signup_token(self, id: int) -> str:
        """Reset a client user back to the invite state with a fresh signup token
        (staff-driven 'resend invite' / 'reset access')."""
        token = secrets.token_urlsafe(24)
        self.conn.execute(
            """UPDATE client_users SET password_hash = NULL, signup_token = ?,
               signup_token_created_at = strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE id = ?""",
            (token, id),
        )
        self.conn.commit()
        return token

    def authenticate_client_user(self, username: str, password: str) -> dict | None:
        """Authenticate a client-portal user. Returns None on no match, wrong password,
        inactive account, or an account that hasn't completed signup yet."""
        cur = self.conn.execute(
            "SELECT * FROM client_users WHERE username = ? AND active = 1 AND password_hash IS NOT NULL",
            (username.strip(),),
        )
        user = cur.fetchone()
        if not user:
            return None
        if not self._verify_password(password, user["password_hash"]):
            return None
        self.conn.execute(
            "UPDATE client_users SET last_login = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), user["id"]),
        )
        self.conn.commit()
        return dict(user)

    def list_client_users(self, customer_id: str) -> list[dict]:
        """List all client-portal users for a customer, ordered by creation time."""
        cur = self.conn.execute(
            "SELECT * FROM client_users WHERE customer_id = ? ORDER BY created_at",
            (customer_id,),
        )
        return [dict(r) for r in cur.fetchall()]

    def set_client_user_active(self, id: int, active: bool) -> None:
        self.conn.execute(
            "UPDATE client_users SET active = ? WHERE id = ?",
            (1 if active else 0, id),
        )
        self.conn.commit()

    def delete_client_user(self, id: int) -> None:
        self.conn.execute("DELETE FROM client_users WHERE id = ?", (id,))
        self.conn.commit()

    # --- Customer Integrations ---

    def save_integration(self, customer_id: str, integration: str, config: dict,
                         status: str = "configured") -> None:
        """Save or update a customer integration config."""
        self.conn.execute(
            """INSERT INTO customer_integrations (customer_id, integration, config_json, status)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(customer_id, integration) DO UPDATE SET
                   config_json = excluded.config_json, status = excluded.status""",
            (customer_id, integration, json.dumps(config), status),
        )
        self.conn.commit()

    def get_integration(self, customer_id: str, integration: str) -> dict | None:
        """Get a specific integration config for a customer."""
        cur = self.conn.execute(
            "SELECT * FROM customer_integrations WHERE customer_id = ? AND integration = ?",
            (customer_id, integration),
        )
        row = cur.fetchone()
        if not row:
            return None
        d = dict(row)
        d["config"] = json.loads(d.pop("config_json", "{}"))
        return d

    def get_integrations(self, customer_id: str) -> list[dict]:
        """Get all integrations for a customer."""
        cur = self.conn.execute(
            "SELECT * FROM customer_integrations WHERE customer_id = ? ORDER BY integration",
            (customer_id,),
        )
        results = []
        for row in cur.fetchall():
            d = dict(row)
            d["config"] = json.loads(d.pop("config_json", "{}"))
            results.append(d)
        return results

    def update_integration_status(self, customer_id: str, integration: str,
                                  status: str, last_error: str = "") -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """UPDATE customer_integrations SET status = ?, last_checked = ?, last_error = ?
               WHERE customer_id = ? AND integration = ?""",
            (status, now, last_error, customer_id, integration),
        )
        self.conn.commit()

    # --- Keyword Tracking ---

    def add_tracked_keyword(self, customer_id: str, keyword: str,
                            source: str = "manual") -> bool:
        """Add a keyword to track. Returns True on success, False if exists."""
        try:
            self.conn.execute(
                "INSERT INTO keyword_tracking (customer_id, keyword, source) VALUES (?, ?, ?)",
                (customer_id, keyword.lower().strip(), source),
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def remove_tracked_keyword(self, customer_id: str, keyword: str) -> bool:
        cur = self.conn.execute(
            "DELETE FROM keyword_tracking WHERE customer_id = ? AND keyword = ?",
            (customer_id, keyword.lower().strip()),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def get_tracked_keywords(self, customer_id: str) -> list[dict]:
        cur = self.conn.execute(
            "SELECT * FROM keyword_tracking WHERE customer_id = ? AND is_tracked = 1 ORDER BY keyword",
            (customer_id,),
        )
        return [dict(r) for r in cur.fetchall()]

    def save_keyword_rank(self, customer_id: str, keyword: str, date: str,
                          position: float | None, clicks: int = 0,
                          impressions: int = 0, ctr: float = 0.0) -> None:
        self.conn.execute(
            """INSERT OR REPLACE INTO keyword_ranks
               (customer_id, keyword, date, position, clicks, impressions, ctr)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (customer_id, keyword.lower().strip(), date, position, clicks, impressions, ctr),
        )
        self.conn.commit()

    def get_keyword_rank_history(self, customer_id: str, keyword: str,
                                 days: int = 90) -> list[dict]:
        cur = self.conn.execute(
            """SELECT * FROM keyword_ranks
               WHERE customer_id = ? AND keyword = ?
               ORDER BY date DESC LIMIT ?""",
            (customer_id, keyword.lower().strip(), days),
        )
        return [dict(r) for r in cur.fetchall()]

    def get_keyword_summary(self, customer_id: str) -> list[dict]:
        """Get latest rank + 4-week-ago rank for each tracked keyword."""
        cur = self.conn.execute(
            """SELECT kt.keyword, kt.source,
                      kr_latest.position AS current_position,
                      kr_latest.clicks AS current_clicks,
                      kr_latest.impressions AS current_impressions,
                      kr_prev.position AS prev_position
               FROM keyword_tracking kt
               LEFT JOIN (
                   SELECT keyword, position, clicks, impressions,
                          ROW_NUMBER() OVER (PARTITION BY keyword ORDER BY date DESC) as rn
                   FROM keyword_ranks WHERE customer_id = ?
               ) kr_latest ON kt.keyword = kr_latest.keyword AND kr_latest.rn = 1
               LEFT JOIN (
                   SELECT keyword, position,
                          ROW_NUMBER() OVER (PARTITION BY keyword ORDER BY date DESC) as rn
                   FROM keyword_ranks WHERE customer_id = ? AND date <= date('now', '-28 days')
               ) kr_prev ON kt.keyword = kr_prev.keyword AND kr_prev.rn = 1
               WHERE kt.customer_id = ? AND kt.is_tracked = 1
               ORDER BY kr_latest.clicks DESC NULLS LAST, kt.keyword""",
            (customer_id, customer_id, customer_id),
        )
        return [dict(r) for r in cur.fetchall()]

    # --- Site Audits ---

    def save_site_audit(self, customer_id: str, audit_date: str,
                        scores: dict, issues: list[dict],
                        raw_data: dict | None = None) -> int:
        """Save a site audit and its issues. Returns audit ID."""
        # A failed PageSpeed run returns None/0 scores — don't let a transient timeout
        # tank the displayed SEO Health Score. Fall back to the most recent prior score.
        prev = self.get_latest_audit(customer_id) or {}
        def _score(key, prev_key):
            v = scores.get(key)
            return v if v else prev.get(prev_key)
        cur = self.conn.execute(
            """INSERT OR REPLACE INTO site_audits
               (customer_id, audit_date, performance_score, accessibility_score,
                seo_score, best_practices_score, issues_json, raw_data_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (customer_id, audit_date,
             _score("performance", "performance_score"), _score("accessibility", "accessibility_score"),
             _score("seo", "seo_score"), _score("best_practices", "best_practices_score"),
             json.dumps(issues), json.dumps(raw_data or {})),
        )
        audit_id = cur.lastrowid
        # Auto-close previously-open issues that no longer appear in this run (they were
        # fixed) — otherwise a resolved finding lingers as 'open' forever. Leaves 'ignored'
        # issues untouched.
        new_keys = {(i["category"], i["title"]) for i in issues}
        for row in self.conn.execute(
            "SELECT id, category, title FROM audit_issues WHERE customer_id = ? AND status = 'open'",
            (customer_id,),
        ).fetchall():
            if (row["category"], row["title"]) not in new_keys:
                self.conn.execute("UPDATE audit_issues SET status = 'fixed' WHERE id = ?", (row["id"],))
        # Save individual issues. Each run gets a fresh audit_id, so we dedupe
        # against existing open/ignored issues by (category, title) — otherwise
        # the same finding piles up as duplicates on every audit run.
        for issue in issues:
            dup = self.conn.execute(
                "SELECT 1 FROM audit_issues WHERE customer_id = ? AND category = ? "
                "AND title = ? AND status IN ('open', 'ignored') LIMIT 1",
                (customer_id, issue["category"], issue["title"]),
            ).fetchone()
            if dup:
                continue
            self.conn.execute(
                """INSERT INTO audit_issues
                   (customer_id, audit_id, category, severity, title, description, fix_instruction)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (customer_id, audit_id, issue["category"], issue["severity"],
                 issue["title"], issue["description"], issue.get("fix_instruction", "")),
            )
        self.conn.commit()
        return audit_id

    def get_latest_audit(self, customer_id: str) -> dict | None:
        cur = self.conn.execute(
            "SELECT * FROM site_audits WHERE customer_id = ? ORDER BY audit_date DESC LIMIT 1",
            (customer_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        d = dict(row)
        d["issues"] = json.loads(d.pop("issues_json", "[]"))
        return d

    def get_audit_issues(self, customer_id: str, status: str | None = None) -> list[dict]:
        if status:
            cur = self.conn.execute(
                "SELECT * FROM audit_issues WHERE customer_id = ? AND status = ? ORDER BY severity, id",
                (customer_id, status),
            )
        else:
            cur = self.conn.execute(
                "SELECT * FROM audit_issues WHERE customer_id = ? ORDER BY severity, id",
                (customer_id,),
            )
        return [dict(r) for r in cur.fetchall()]

    def update_audit_issue_status(self, issue_id: int, status: str) -> bool:
        fixed_date = datetime.now(timezone.utc).isoformat() if status == "fixed" else None
        cur = self.conn.execute(
            "UPDATE audit_issues SET status = ?, fixed_date = ? WHERE id = ?",
            (status, fixed_date, issue_id),
        )
        self.conn.commit()
        return cur.rowcount > 0

    # --- Backlinks ---

    def save_backlinks(self, customer_id: str, links: list[dict]) -> dict:
        """Update backlinks snapshot. Returns summary with new/lost counts."""
        now = datetime.now(timezone.utc).isoformat()
        # Get existing
        cur = self.conn.execute(
            "SELECT linking_domain, status FROM backlinks WHERE customer_id = ?",
            (customer_id,),
        )
        existing = {r["linking_domain"]: r["status"] for r in cur.fetchall()}
        incoming = {l["domain"]: l.get("count", 1) for l in links}

        new_count = 0
        for domain, count in incoming.items():
            if domain not in existing:
                self.conn.execute(
                    """INSERT INTO backlinks (customer_id, linking_domain, link_count, first_seen, last_seen)
                       VALUES (?, ?, ?, ?, ?)""",
                    (customer_id, domain, count, now, now),
                )
                new_count += 1
            else:
                self.conn.execute(
                    "UPDATE backlinks SET link_count = ?, last_seen = ?, status = 'active' WHERE customer_id = ? AND linking_domain = ?",
                    (count, now, customer_id, domain),
                )

        # Mark lost
        lost_count = 0
        for domain in existing:
            if domain not in incoming and existing[domain] == "active":
                self.conn.execute(
                    "UPDATE backlinks SET status = 'lost' WHERE customer_id = ? AND linking_domain = ?",
                    (customer_id, domain),
                )
                lost_count += 1

        self.conn.commit()
        return {"new": new_count, "lost": lost_count, "total": len(incoming)}

    def get_backlinks(self, customer_id: str, status: str | None = None) -> list[dict]:
        if status:
            cur = self.conn.execute(
                "SELECT * FROM backlinks WHERE customer_id = ? AND status = ? ORDER BY link_count DESC",
                (customer_id, status),
            )
        else:
            cur = self.conn.execute(
                "SELECT * FROM backlinks WHERE customer_id = ? ORDER BY status, link_count DESC",
                (customer_id,),
            )
        return [dict(r) for r in cur.fetchall()]

    # --- Content Topics ---

    def add_content_topic(self, customer_id: str, topic: str, target_keyword: str = "",
                          source: str = "manual", priority: str = "medium",
                          notes: str = "") -> int:
        cur = self.conn.execute(
            """INSERT INTO content_topics (customer_id, topic, target_keyword, source, priority, notes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (customer_id, topic, target_keyword, source, priority, notes),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_content_topics(self, customer_id: str, status: str | None = None) -> list[dict]:
        if status:
            cur = self.conn.execute(
                "SELECT * FROM content_topics WHERE customer_id = ? AND status = ? ORDER BY priority, created_at DESC",
                (customer_id, status),
            )
        else:
            cur = self.conn.execute(
                "SELECT * FROM content_topics WHERE customer_id = ? ORDER BY status, priority, created_at DESC",
                (customer_id,),
            )
        return [dict(r) for r in cur.fetchall()]

    def update_content_topic_status(self, topic_id: int, status: str,
                                    content_rec_id: str | None = None) -> bool:
        if content_rec_id:
            cur = self.conn.execute(
                "UPDATE content_topics SET status = ?, content_rec_id = ? WHERE id = ?",
                (status, content_rec_id, topic_id),
            )
        else:
            cur = self.conn.execute(
                "UPDATE content_topics SET status = ? WHERE id = ?",
                (status, topic_id),
            )
        self.conn.commit()
        return cur.rowcount > 0

    # --- Competitor Domains ---

    def add_competitor_domain(self, customer_id, domain, name="", discovered_via="manual",
                             rating=0.0, review_count=0, address="", place_id=""):
        self.conn.execute(
            """INSERT OR IGNORE INTO competitor_domains
               (customer_id, competitor_domain, competitor_name, discovered_via, rating, review_count, address, place_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (customer_id, domain, name, discovered_via, rating, review_count, address, place_id),
        )
        self.conn.commit()

    def get_competitor_domains(self, customer_id):
        rows = self.conn.execute(
            "SELECT * FROM competitor_domains WHERE customer_id = ? ORDER BY created_at DESC",
            (customer_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def remove_competitor_domain(self, customer_id, domain):
        self.conn.execute(
            "DELETE FROM competitor_domains WHERE customer_id = ? AND competitor_domain = ?",
            (customer_id, domain),
        )
        self.conn.commit()

    def update_competitor_da(self, customer_id, domain, da):
        self.conn.execute(
            "UPDATE competitor_domains SET domain_authority = ?, "
            "da_checked_at = strftime('%Y-%m-%dT%H:%M:%SZ','now') "
            "WHERE customer_id = ? AND competitor_domain = ?",
            (da, customer_id, domain),
        )
        self.conn.commit()
        return self.conn.total_changes > 0

    # --- Reviews ---

    def add_review(
        self,
        customer_id,
        rating,
        review_text="",
        reviewer_name="",
        review_date="",
        source="google",
        sentiment="",
        themes=None,
    ):
        self.conn.execute(
            "INSERT INTO reviews (customer_id, source, rating, review_text, reviewer_name, review_date, sentiment, themes_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (customer_id, source, rating, review_text, reviewer_name, review_date, sentiment, json.dumps(themes or [])),
        )
        self.conn.commit()

    def get_reviews(self, customer_id, limit=50):
        rows = self.conn.execute(
            "SELECT rowid AS id, * FROM reviews WHERE customer_id = ? ORDER BY review_date DESC LIMIT ?",
            (customer_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def set_review_response(self, review_id: int, response_text: str, responded_at: str | None = None) -> bool:
        """Record an owner reply to a review (from GBP review sync or a manual mark)."""
        self.conn.execute(
            "UPDATE reviews SET owner_response = ?, responded_at = ? WHERE rowid = ?",
            (response_text, responded_at or datetime.now(timezone.utc).isoformat(), review_id),
        )
        self.conn.commit()
        return self.conn.total_changes > 0

    def count_unanswered_reviews(self, customer_id: str, since: str | None = None) -> int:
        """Reviews with no owner reply (optionally only those on/after `since` YYYY-MM-DD)."""
        q = "SELECT COUNT(*) FROM reviews WHERE customer_id = ? AND (owner_response IS NULL OR owner_response = '')"
        args: list = [customer_id]
        if since:
            q += " AND review_date >= ?"
            args.append(since)
        try:
            return int(self.conn.execute(q, args).fetchone()[0])
        except Exception:
            return 0

    def get_review_stats(self, customer_id):
        row = self.conn.execute(
            "SELECT COUNT(*) as total, AVG(rating) as avg_rating, "
            "SUM(CASE WHEN rating = 5 THEN 1 ELSE 0 END) as five_star, "
            "SUM(CASE WHEN rating = 4 THEN 1 ELSE 0 END) as four_star, "
            "SUM(CASE WHEN rating = 3 THEN 1 ELSE 0 END) as three_star, "
            "SUM(CASE WHEN rating = 2 THEN 1 ELSE 0 END) as two_star, "
            "SUM(CASE WHEN rating = 1 THEN 1 ELSE 0 END) as one_star "
            "FROM reviews WHERE customer_id = ?",
            (customer_id,),
        ).fetchone()
        return dict(row) if row else {}

    def review_velocity(self, customer_id: str, window_days: int = 30) -> dict:
        """New reviews in the trailing window vs the prior one, and the practice's
        monthly target. Powers the stall alert + report line. `review_date` may be
        ISO or YYYY-MM-DD — a lexicographic compare on the date prefix works for both."""
        now = datetime.now(timezone.utc)
        cur_start = (now - timedelta(days=window_days)).strftime("%Y-%m-%d")
        prev_start = (now - timedelta(days=window_days * 2)).strftime("%Y-%m-%d")

        def _count(lo: str, hi: str | None) -> int:
            q = "SELECT COUNT(*) FROM reviews WHERE customer_id = ? AND substr(review_date,1,10) >= ?"
            args: list = [customer_id, lo]
            if hi:
                q += " AND substr(review_date,1,10) < ?"
                args.append(hi)
            try:
                return int(self.conn.execute(q, args).fetchone()[0])
            except Exception:
                return 0

        cust = self.get_customer(customer_id) or {}
        target = cust.get("review_target_pm")
        target = 4 if target is None else int(target)
        cur = _count(cur_start, None)
        prev = _count(prev_start, cur_start)
        return {
            "current": cur,          # reviews in trailing window (≈ per month at 30d)
            "previous": prev,        # prior window, for the trend arrow
            "target": target,        # target new reviews / month
            "window_days": window_days,
            "on_track": cur >= target,
        }

    # --- Citations ---

    def save_citation(self, customer_id, directory, listed=False, nap_match=False, url_correct=False, listing_url=""):
        self.conn.execute(
            "INSERT OR REPLACE INTO citations (customer_id, directory, listed, nap_match, url_correct, listing_url, last_checked) "
            "VALUES (?, ?, ?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))",
            (customer_id, directory, int(listed), int(nap_match), int(url_correct), listing_url),
        )
        self.conn.commit()

    def get_citations(self, customer_id):
        rows = self.conn.execute(
            "SELECT * FROM citations WHERE customer_id = ? ORDER BY directory",
            (customer_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def delete_citation(self, customer_id, directory):
        self.conn.execute(
            "DELETE FROM citations WHERE customer_id = ? AND directory = ?",
            (customer_id, directory),
        )
        self.conn.commit()
        return self.conn.total_changes > 0

    # --- Off-site authority (FATJOE orders + delivered assets) ---

    _OFFSITE_ORDER_COLS = (
        "vendor", "order_type", "status", "quantity", "dr_tier", "target_url",
        "anchor_text", "anchor_type", "cost_usd", "sell_usd", "vendor_order_id", "notes",
    )

    # ------------------------------------------------------------------ #
    # Real expense ledger (reimbursement) — see expense_entries table.     #
    # ------------------------------------------------------------------ #
    _EXPENSE_COLS = ("month", "incurred_on", "category", "vendor", "name",
                     "amount_usd", "recurring", "template_key", "note")

    def add_expense_entry(self, month: str, name: str, amount_usd: float,
                          category: str = "Other", vendor: str = "",
                          incurred_on: str | None = None, recurring: int = 0,
                          template_key: str = "", note: str = "") -> int:
        """Log one real expense charge into a month's ledger. Returns row id."""
        cur = self.conn.execute(
            "INSERT INTO expense_entries "
            "(month, incurred_on, category, vendor, name, amount_usd, recurring, template_key, note) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (month, incurred_on, category, vendor, name,
             round(float(amount_usd or 0), 2), int(recurring), template_key, note),
        )
        self.conn.commit()
        return cur.lastrowid

    def list_expense_entries(self, month: str) -> list[dict]:
        """All expense rows for a 'YYYY-MM' month, ordered by category then name."""
        rows = self.conn.execute(
            "SELECT * FROM expense_entries WHERE month = ? ORDER BY category, name, id",
            (month,),
        ).fetchall()
        return [dict(r) for r in rows]

    def update_expense_entry(self, entry_id: int, **fields) -> None:
        """Patch amount/note/name/vendor/category/incurred_on on one entry."""
        allowed = {k: v for k, v in fields.items()
                   if k in ("amount_usd", "note", "name", "vendor", "category", "incurred_on")}
        if not allowed:
            return
        if "amount_usd" in allowed:
            allowed["amount_usd"] = round(float(allowed["amount_usd"] or 0), 2)
        allowed["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        sets = ", ".join(f"{k} = ?" for k in allowed)
        self.conn.execute(
            f"UPDATE expense_entries SET {sets} WHERE id = ?",
            list(allowed.values()) + [entry_id],
        )
        self.conn.commit()

    def delete_expense_entry(self, entry_id: int) -> None:
        self.conn.execute("DELETE FROM expense_entries WHERE id = ?", (entry_id,))
        self.conn.commit()

    def expense_months(self) -> list[str]:
        """Distinct months that have ledger rows, newest first."""
        rows = self.conn.execute(
            "SELECT DISTINCT month FROM expense_entries ORDER BY month DESC"
        ).fetchall()
        return [r[0] for r in rows]

    def set_expense_amount_by_template(self, month: str, template_key: str,
                                       amount: float, note: str | None = None) -> bool:
        """Set a seeded row's amount (used by the live usage sync). Returns True
        if a matching (month, template_key) row existed and was updated."""
        row = self.conn.execute(
            "SELECT id FROM expense_entries WHERE month = ? AND template_key = ?",
            (month, template_key),
        ).fetchone()
        if not row:
            return False
        self.update_expense_entry(row[0], amount_usd=amount, **({"note": note} if note is not None else {}))
        return True

    def offsite_spend_month(self, month: str) -> tuple[float, int]:
        """Real FATJOE COGS + order count for a 'YYYY-MM' month (by ordered_at,
        excluding cancelled). Powers the ledger's auto FATJOE line."""
        start = f"{month}-01T00:00:00Z"
        y, m = int(month[:4]), int(month[5:7])
        ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
        end = f"{ny:04d}-{nm:02d}-01T00:00:00Z"
        row = self.conn.execute(
            "SELECT COALESCE(SUM(cost_usd), 0), COUNT(*) FROM offsite_orders "
            "WHERE status != 'cancelled' AND ordered_at >= ? AND ordered_at < ?",
            (start, end),
        ).fetchone()
        return round(row[0] or 0.0, 2), row[1] or 0

    def offsite_spend_by_customer(self, month: str) -> dict[str, tuple[float, int]]:
        """Real FATJOE COGS + order count per customer for a 'YYYY-MM' month
        (by ordered_at, excluding cancelled). Powers per-customer cost attribution."""
        start = f"{month}-01T00:00:00Z"
        y, m = int(month[:4]), int(month[5:7])
        ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
        end = f"{ny:04d}-{nm:02d}-01T00:00:00Z"
        rows = self.conn.execute(
            "SELECT customer_id, COALESCE(SUM(cost_usd), 0), COUNT(*) FROM offsite_orders "
            "WHERE status != 'cancelled' AND ordered_at >= ? AND ordered_at < ? "
            "GROUP BY customer_id",
            (start, end),
        ).fetchall()
        return {r[0]: (round(r[1] or 0.0, 2), r[2] or 0) for r in rows}

    def seed_recurring_expenses(self, month: str, templates: list[dict]) -> int:
        """Insert each recurring template into `month` unless a row with the same
        template_key already exists there (idempotent). Returns rows inserted."""
        existing = {
            r[0] for r in self.conn.execute(
                "SELECT template_key FROM expense_entries WHERE month = ? AND template_key != ''",
                (month,),
            ).fetchall()
        }
        inserted = 0
        for t in templates:
            key = t.get("key", "")
            if not key or key in existing:
                continue
            self.conn.execute(
                "INSERT INTO expense_entries "
                "(month, category, vendor, name, amount_usd, recurring, template_key, note) "
                "VALUES (?, ?, ?, ?, ?, 1, ?, ?)",
                (month, t.get("category", "Other"), t.get("vendor", ""), t.get("name", ""),
                 round(float(t.get("amount", 0) or 0), 2), key, t.get("note", "")),
            )
            inserted += 1
        if inserted:
            self.conn.commit()
        return inserted

    def add_offsite_order(self, customer_id, order_type, **fields):
        """Create an off-site order. Returns the new order id."""
        data = {"order_type": order_type}
        data.update({k: v for k, v in fields.items() if k in self._OFFSITE_ORDER_COLS})
        cols = ["customer_id"] + list(data.keys())
        ph = ", ".join("?" for _ in cols)
        cur = self.conn.execute(
            f"INSERT INTO offsite_orders ({', '.join(cols)}) VALUES ({ph})",
            [customer_id] + list(data.values()),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_offsite_order(self, order_id):
        row = self.conn.execute(
            "SELECT * FROM offsite_orders WHERE id = ?", (order_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_offsite_orders(self, customer_id):
        rows = self.conn.execute(
            "SELECT * FROM offsite_orders WHERE customer_id = ? ORDER BY id DESC",
            (customer_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def recent_offsite_order(self, customer_id, order_type, dr_tier, since_iso: str) -> dict | None:
        """Most recent non-cancelled order matching customer+type(+DR band) logged at/after
        `since_iso`. Used to catch accidental double-logs (reload / double-click) before they
        become a double-pay. dr_tier=None matches rows with NULL dr_tier."""
        where = "customer_id = ? AND order_type = ? AND status != 'cancelled' AND ordered_at >= ?"
        args: list = [customer_id, order_type, since_iso]
        if dr_tier is None:
            where += " AND dr_tier IS NULL"
        else:
            where += " AND dr_tier = ?"
            args.append(dr_tier)
        row = self.conn.execute(
            f"SELECT * FROM offsite_orders WHERE {where} ORDER BY ordered_at DESC LIMIT 1", args
        ).fetchone()
        return dict(row) if row else None

    def count_offsite_orders_in_period(self, customer_id, order_type, since: str | None = None,
                                       dr_tier: int | None = None) -> int:
        """How many non-cancelled orders of a type were placed since `since`
        (ISO). `since=None` counts all-time. Powers the per-tier 'due this period'
        view — citations top-ups count as orders, link drips count per link via
        quantity. `dr_tier` (links) scopes the count to one DR band so a tier with
        multiple link rows (e.g. 2×DR40 + 2×DR30) tracks each row independently."""
        where = "customer_id = ? AND order_type = ? AND status != 'cancelled'"
        args: list = [customer_id, order_type]
        if since:
            where += " AND ordered_at >= ?"
            args.append(since)
        if dr_tier is not None:
            where += " AND dr_tier = ?"
            args.append(dr_tier)
        # Links/mentions: each order's quantity counts toward the monthly target.
        # Citations: count distinct orders (one pack satisfies the target).
        if order_type == "citation":
            row = self.conn.execute(
                f"SELECT COUNT(*) FROM offsite_orders WHERE {where}", args
            ).fetchone()
        else:
            row = self.conn.execute(
                f"SELECT COALESCE(SUM(quantity), 0) FROM offsite_orders WHERE {where}", args
            ).fetchone()
        return int(row[0] or 0)

    def last_offsite_order_at(self, customer_id, order_type, min_dr: int | None = None) -> str | None:
        """Most recent non-cancelled order timestamp (ISO) for a type. For links,
        `min_dr` restricts to orders at/above a DR band (a higher-DR link covers a
        lower-DR need). Powers the rolling 30/90-day coverage window in the FATJOE
        queue — the anchor from which the next order becomes due."""
        where = "customer_id = ? AND order_type = ? AND status != 'cancelled'"
        args: list = [customer_id, order_type]
        if min_dr is not None:
            where += " AND COALESCE(dr_tier, 0) >= ?"
            args.append(min_dr)
        row = self.conn.execute(
            f"SELECT MAX(ordered_at) FROM offsite_orders WHERE {where}", args
        ).fetchone()
        return row[0] if row and row[0] else None

    def link_dr_quantities_in_period(self, customer_id, since: str | None = None) -> dict:
        """{dr_tier: total_quantity} of non-cancelled LINK orders placed since
        `since`. Powers 'a higher-DR order satisfies a lower-DR requirement'
        allocation in the tier queue. NULL dr_tier is keyed as 0."""
        where = "customer_id = ? AND order_type = 'link' AND status != 'cancelled'"
        args: list = [customer_id]
        if since:
            where += " AND ordered_at >= ?"
            args.append(since)
        rows = self.conn.execute(
            f"SELECT dr_tier, COALESCE(SUM(quantity), 0) FROM offsite_orders "
            f"WHERE {where} GROUP BY dr_tier", args,
        ).fetchall()
        return {(r[0] if r[0] is not None else 0): int(r[1]) for r in rows}

    def offsite_spend(self, customer_id: str | None = None, since: str | None = None,
                      adhoc_only: bool = False) -> float:
        """Total real FATJOE COGS from logged orders. Optionally scope to one
        customer and/or to orders placed since an ISO timestamp (excludes
        cancelled). Powers the Expenses page's live variable-COGS line.

        `adhoc_only=True` restricts to ad-hoc orders (those with a client sell
        price), so it pairs correctly with `offsite_revenue` for margin — tier /
        subscription link-building logs sell_usd=0 and would otherwise drag the
        margin negative."""
        where = ["status != 'cancelled'"]
        args: list = []
        if customer_id:
            where.append("customer_id = ?")
            args.append(customer_id)
        if since:
            where.append("ordered_at >= ?")
            args.append(since)
        if adhoc_only:
            where.append("COALESCE(sell_usd, 0) > 0")
        row = self.conn.execute(
            f"SELECT COALESCE(SUM(cost_usd), 0) FROM offsite_orders WHERE {' AND '.join(where)}",
            args,
        ).fetchone()
        return float(row[0] or 0)

    def offsite_revenue(self, customer_id: str | None = None, since: str | None = None) -> float:
        """Total client-facing revenue (retail sell_usd) from logged orders.
        Mirrors offsite_spend; optionally scope to one customer and/or orders
        placed since an ISO timestamp (excludes cancelled). Pairs with
        offsite_spend to surface ad-hoc backlink margin."""
        where = ["status != 'cancelled'"]
        args: list = []
        if customer_id:
            where.append("customer_id = ?")
            args.append(customer_id)
        if since:
            where.append("ordered_at >= ?")
            args.append(since)
        row = self.conn.execute(
            f"SELECT COALESCE(SUM(sell_usd), 0) FROM offsite_orders WHERE {' AND '.join(where)}",
            args,
        ).fetchone()
        return float(row[0] or 0)

    # --- FATJOE product catalog (editable price + buy-link source of truth) ---
    # Retail (client-facing) ad-hoc prices per product_key. Used to seed sell_usd
    # on fresh catalogs and to backfill existing rows. Dan edits these in the
    # dashboard afterward — never hardcode them in templates.
    _CATALOG_SELL_DEFAULTS = {
        "citation_100": 299.0,
        "citation_50": 199.0,
        "blogger_outreach_dr20": 249.0,
        "blogger_outreach_dr30": 299.0,
        "blogger_outreach_dr40": 499.0,
        "blogger_outreach_dr50": 749.0,
        "blogger_outreach_dr60": 999.0,
        # Niche edits ~ 2× their COGS.
        "niche_edit_dr20": 199.0,
        "niche_edit_dr30": 249.0,
        "niche_edit_dr40": 399.0,
        "niche_edit_dr50": 599.0,
        "niche_edit_dr60": 799.0,
        "mention_brand": 749.0,
    }

    def _seed_fatjoe_catalog(self):
        """Insert default catalog rows once, if the table is empty. Prices marked
        verified=0 are best-known starting points to confirm against FATJOE; the
        buy URLs are FATJOE's real product pages. Dan edits both in the dashboard."""
        if self.conn.execute("SELECT 1 FROM fatjoe_catalog LIMIT 1").fetchone():
            return
        BO = "https://fatjoe.com/blogger-outreach/"
        NE = "https://fatjoe.com/niche-edits/"
        MEN = "https://fatjoe.com/brand-mentions/"
        CIT = "https://fatjoe.com/local-citations/"
        # (key, family, label, dr_tier, unit, price, url, verified)
        # Prices = FATJOE real USD. Confirmed from Dan's FATJOE screenshots 2026-06-30:
        # citations $135, DR40+ blogger outreach $243, brand mention $378 (verified=1).
        # Other DR bands inferred from FATJOE's GBP ladder × the confirmed DR40 conversion
        # (≈1.125) — flagged verified=0 until Dan confirms the exact USD.
        rows = [
            ("citation_100", "citation", "Local Citations — campaign", None, "campaign", 135.0, CIT, 1),
            ("citation_50", "citation", "Local Citations — 50 pack", None, "pack", 90.0, CIT, 0),
            # Blogger Outreach (fresh editorial placements) by DR band.
            ("blogger_outreach_dr20", "blogger_outreach", "Blogger Outreach DR20+", 20, "link", 108.0, BO, 0),
            ("blogger_outreach_dr30", "blogger_outreach", "Blogger Outreach DR30+", 30, "link", 135.0, BO, 0),
            ("blogger_outreach_dr40", "blogger_outreach", "Blogger Outreach DR40+", 40, "link", 243.0, BO, 1),
            ("blogger_outreach_dr50", "blogger_outreach", "Blogger Outreach DR50+", 50, "link", 378.0, BO, 0),
            ("blogger_outreach_dr60", "blogger_outreach", "Blogger Outreach DR60+", 60, "link", 513.0, BO, 0),
            # Niche Edits (links into aged posts) — DR ladder confirmed from fatjoe.com/niche-edits.
            ("niche_edit_dr20", "niche_edit", "Niche Edit DR20+", 20, "link", 96.0, NE, 1),
            ("niche_edit_dr30", "niche_edit", "Niche Edit DR30+", 30, "link", 120.0, NE, 1),
            ("niche_edit_dr40", "niche_edit", "Niche Edit DR40+", 40, "link", 216.0, NE, 1),
            ("niche_edit_dr50", "niche_edit", "Niche Edit DR50+", 50, "link", 336.0, NE, 1),
            ("niche_edit_dr60", "niche_edit", "Niche Edit DR60+", 60, "link", 456.0, NE, 1),
            ("mention_brand", "mention", "Brand Mention / Listicle (AI visibility)", None, "placement", 378.0, MEN, 1),
        ]
        for i, (key, fam, label, dr, unit, price, url, ver) in enumerate(rows):
            sell = self._CATALOG_SELL_DEFAULTS.get(key, 0.0)
            self.conn.execute(
                """INSERT OR IGNORE INTO fatjoe_catalog
                   (product_key, family, label, dr_tier, unit, price_usd, sell_usd, buy_url, verified, sort)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (key, fam, label, dr, unit, price, sell, url, ver, i),
            )
        self.conn.commit()

    def get_fatjoe_catalog(self, active_only: bool = True) -> list[dict]:
        q = "SELECT * FROM fatjoe_catalog"
        if active_only:
            q += " WHERE active = 1"
        q += " ORDER BY sort, product_key"
        return [dict(r) for r in self.conn.execute(q).fetchall()]

    def get_catalog_item(self, product_key: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM fatjoe_catalog WHERE product_key = ?", (product_key,)
        ).fetchone()
        return dict(row) if row else None

    def find_catalog_item(self, family: str, dr_tier: int | None = None) -> dict | None:
        """Resolve the catalog row for a (family, dr_tier). For links, exact DR
        match first, else the closest band ≥ requested, else any in the family."""
        rows = [r for r in self.get_fatjoe_catalog(active_only=True) if r["family"] == family]
        if not rows:
            return None
        if dr_tier is None:
            return rows[0]
        exact = [r for r in rows if r.get("dr_tier") == dr_tier]
        if exact:
            return exact[0]
        higher = sorted((r for r in rows if (r.get("dr_tier") or 0) >= dr_tier),
                        key=lambda r: r["dr_tier"])
        return higher[0] if higher else rows[-1]

    def update_catalog_item(self, product_key: str, price_usd: float, buy_url: str,
                            verified: int = 1, sell_usd: float | None = None) -> None:
        if sell_usd is None:
            existing = self.get_catalog_item(product_key)
            sell_usd = float(existing["sell_usd"]) if existing else 0.0
        self.conn.execute(
            """UPDATE fatjoe_catalog
               SET price_usd = ?, sell_usd = ?, buy_url = ?, verified = ?,
                   updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
               WHERE product_key = ?""",
            (price_usd, sell_usd, buy_url, verified, product_key),
        )
        self.conn.commit()

    def update_offsite_order(self, order_id, **fields):
        allowed = set(self._OFFSITE_ORDER_COLS) | {"delivered_at"}
        sets = {k: v for k, v in fields.items() if k in allowed}
        if not sets:
            return
        if sets.get("status") == "delivered" and "delivered_at" not in sets:
            sets["delivered_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        clause = ", ".join(f"{k} = ?" for k in sets)
        self.conn.execute(
            f"UPDATE offsite_orders SET {clause} WHERE id = ?",
            list(sets.values()) + [order_id],
        )
        self.conn.commit()

    def delete_offsite_order(self, order_id):
        self.conn.execute("DELETE FROM offsite_assets WHERE order_id = ?", (order_id,))
        self.conn.execute("DELETE FROM offsite_orders WHERE id = ?", (order_id,))
        self.conn.commit()
        return self.conn.total_changes > 0

    def add_offsite_asset(self, order_id, customer_id, live_url, **fields):
        """Record a delivered live URL. Idempotent on (customer_id, live_url)."""
        cols = ["order_id", "customer_id", "live_url"]
        vals = [order_id, customer_id, live_url]
        for k in ("asset_type", "domain", "anchor_text", "is_dofollow",
                  "da", "da_checked_at", "indexed"):
            if k in fields:
                cols.append(k)
                vals.append(fields[k])
        ph = ", ".join("?" for _ in cols)
        self.conn.execute(
            f"INSERT OR IGNORE INTO offsite_assets ({', '.join(cols)}) VALUES ({ph})",
            vals,
        )
        self.conn.commit()

    def get_offsite_assets(self, customer_id, order_id=None):
        if order_id is not None:
            rows = self.conn.execute(
                "SELECT * FROM offsite_assets WHERE order_id = ? ORDER BY da DESC, id DESC",
                (order_id,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM offsite_assets WHERE customer_id = ? ORDER BY da DESC, id DESC",
                (customer_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def update_offsite_asset(self, asset_id, **fields):
        allowed = {"da", "da_checked_at", "indexed", "is_dofollow", "anchor_text"}
        sets = {k: v for k, v in fields.items() if k in allowed}
        if not sets:
            return
        clause = ", ".join(f"{k} = ?" for k in sets)
        self.conn.execute(
            f"UPDATE offsite_assets SET {clause} WHERE id = ?",
            list(sets.values()) + [asset_id],
        )
        self.conn.commit()

    def offsite_summary(self, customer_id, since: str | None = None):
        """Roll-up for the panel + weekly report. Counts live assets by type,
        distinct referring domains, avg link DA, and total spend. `since` filters
        assets by live_at (ISO date) for period reporting."""
        a_where = "customer_id = ?"
        a_args: list = [customer_id]
        if since:
            a_where += " AND live_at >= ?"
            a_args.append(since)
        row = self.conn.execute(
            f"""SELECT
                  SUM(CASE WHEN asset_type='link' THEN 1 ELSE 0 END) AS links,
                  SUM(CASE WHEN asset_type='citation' THEN 1 ELSE 0 END) AS citations,
                  SUM(CASE WHEN asset_type='mention' THEN 1 ELSE 0 END) AS mentions,
                  COUNT(DISTINCT CASE WHEN asset_type IN ('link','mention') THEN domain END) AS ref_domains,
                  AVG(CASE WHEN asset_type='link' AND da IS NOT NULL THEN da END) AS avg_link_da
                FROM offsite_assets WHERE {a_where}""",
            a_args,
        ).fetchone()
        spend = self.conn.execute(
            "SELECT COALESCE(SUM(cost_usd),0) FROM offsite_orders WHERE customer_id = ?",
            (customer_id,),
        ).fetchone()[0]
        d = dict(row) if row else {}
        return {
            "links": d.get("links") or 0,
            "citations": d.get("citations") or 0,
            "mentions": d.get("mentions") or 0,
            "ref_domains": d.get("ref_domains") or 0,
            "avg_link_da": round(d["avg_link_da"]) if d.get("avg_link_da") else None,
            "spend_usd": round(spend or 0, 2),
        }

    # --- Migration helper: import from customers.json ---

    def import_from_json(self, json_path: str):
        """Import customers from the legacy customers.json file."""
        with open(json_path) as f:
            data = json.load(f)

        for c in data.get("customers", []):
            customer_id = c["id"]
            # Skip if already exists
            if self.get_customer(customer_id):
                logger.info(f"Skipping existing customer: {customer_id}")
                continue

            self.add_customer(
                id=customer_id,
                name=c["name"],
                domain=c["domain"],
                platform="webflow" if c.get("webflow_site_id") else "unknown",
                business_type=c.get("business_type", "practice"),
                city=c.get("city", ""),
                state=c.get("state", ""),
                zip=c.get("zip_code", ""),
                address=c.get("address", ""),
                phone=c.get("phone", ""),
                brand_voice=c.get("brand_voice", ""),
                webflow_site_id=c.get("webflow_site_id", ""),
                specialties=c.get("specialties", []),
                insurance_accepted=c.get("insurance_accepted", []),
                hours=c.get("hours", ""),
                emergency_available=c.get("emergency_available", False),
                competitors=c.get("competitors", []),
            )

            for p in c.get("providers", []):
                self.add_provider(
                    customer_id=customer_id,
                    name=p["name"],
                    credentials=p.get("credentials", ""),
                    specialties=p.get("specialties", []),
                    years_experience=p.get("years_experience"),
                    bio=p.get("bio") or "",
                )

            # Set up platform access tracking
            platform = "webflow" if c.get("webflow_site_id") else "unknown"
            access_platforms = ["gsc", "ga", "gtm", "gbp", "cloudflare"]
            if platform in ("webflow", "squarespace", "wordpress"):
                access_platforms.append(platform)
            for ap in access_platforms:
                self.add_platform_access(customer_id, ap)

            logger.info(f"Imported customer: {customer_id}")

    # ------------------------------------------------------------------
    # PracticeRank Score history
    # ------------------------------------------------------------------

    def save_practicerank_score(
        self,
        customer_id: str,
        date: str,
        overall: int,
        ai_visibility: int | None,
        search_growth: int | None,
        technical_health: int | None,
        content_velocity: int | None,
        reputation: int | None,
        breakdown_json: str = "{}",
    ) -> None:
        """Save or update a daily PracticeRank score."""
        self.conn.execute(
            """INSERT INTO practicerank_scores
               (customer_id, date, overall_score, ai_visibility, search_growth,
                technical_health, content_velocity, reputation, breakdown_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(customer_id, date) DO UPDATE SET
                 overall_score=excluded.overall_score,
                 ai_visibility=excluded.ai_visibility,
                 search_growth=excluded.search_growth,
                 technical_health=excluded.technical_health,
                 content_velocity=excluded.content_velocity,
                 reputation=excluded.reputation,
                 breakdown_json=excluded.breakdown_json""",
            (customer_id, date, overall, ai_visibility, search_growth,
             technical_health, content_velocity, reputation, breakdown_json),
        )
        self.conn.commit()

    def get_practicerank_scores(
        self, customer_id: str, limit: int = 90
    ) -> list[dict]:
        """Get score history, most recent first."""
        cur = self.conn.execute(
            "SELECT * FROM practicerank_scores WHERE customer_id = ? ORDER BY date DESC LIMIT ?",
            (customer_id, limit),
        )
        return [dict(r) for r in cur.fetchall()]

    def get_latest_practicerank_score(self, customer_id: str) -> dict | None:
        """Get the most recent score for a customer."""
        cur = self.conn.execute(
            "SELECT * FROM practicerank_scores WHERE customer_id = ? ORDER BY date DESC LIMIT 1",
            (customer_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def get_all_latest_scores(self) -> list[dict]:
        """Get latest score for every customer (for analytics leaderboard)."""
        cur = self.conn.execute("""
            SELECT ps.* FROM practicerank_scores ps
            INNER JOIN (
                SELECT customer_id, MAX(date) as max_date
                FROM practicerank_scores GROUP BY customer_id
            ) latest ON ps.customer_id = latest.customer_id AND ps.date = latest.max_date
            ORDER BY ps.overall_score DESC
        """)
        return [dict(r) for r in cur.fetchall()]

    # --- SEO Health Score history (dashboard donut) ---
    def save_seo_health(
        self,
        customer_id: str,
        date: str,
        score: int,
        pagespeed: int | None = None,
        keyword_coverage: int | None = None,
        traffic_trend: int | None = None,
        technical: int | None = None,
        breakdown_json: str = "{}",
    ) -> None:
        """Save or update the day's SEO health score + its 4-bucket breakdown."""
        self.conn.execute(
            """INSERT INTO seo_health_history
               (customer_id, date, score, pagespeed, keyword_coverage,
                traffic_trend, technical, breakdown_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(customer_id, date) DO UPDATE SET
                 score=excluded.score,
                 pagespeed=excluded.pagespeed,
                 keyword_coverage=excluded.keyword_coverage,
                 traffic_trend=excluded.traffic_trend,
                 technical=excluded.technical,
                 breakdown_json=excluded.breakdown_json""",
            (customer_id, date, score, pagespeed, keyword_coverage,
             traffic_trend, technical, breakdown_json),
        )
        self.conn.commit()

    def get_seo_health_history(self, customer_id: str, limit: int = 90) -> list[dict]:
        """SEO health history, most recent first."""
        cur = self.conn.execute(
            "SELECT * FROM seo_health_history WHERE customer_id = ? ORDER BY date DESC LIMIT ?",
            (customer_id, limit),
        )
        return [dict(r) for r in cur.fetchall()]

    def seo_score_and_delta(self, customer_id: str, cutoff_date: str) -> tuple[int | None, int | None]:
        """(current SEO health score, delta vs ~30 days ago) for the dashboard trend chip.
        Delta uses the NEWEST record on/before `cutoff_date` (a YYYY-MM-DD ~25-30 days back);
        returns (None, None) with no history, (score, None) with too little history."""
        rows = self.conn.execute(
            "SELECT date, score FROM seo_health_history WHERE customer_id = ? "
            "ORDER BY date DESC LIMIT 180",
            (customer_id,),
        ).fetchall()
        if not rows:
            return None, None
        current = int(rows[0]["score"])
        # rows are DESC; the first with date <= cutoff is the newest record >= ~30d old.
        prior = next((r for r in rows if r["date"] <= cutoff_date), None)
        delta = (current - int(prior["score"])) if (prior and prior["date"] != rows[0]["date"]) else None
        return current, delta

    # --- Weekly report snapshots (R0) ---

    def save_report_snapshot(
        self, customer_id: str, report_type: str, period_start: str,
        period_end: str, score: int, payload_json: str, html: str,
    ) -> str:
        """Persist a rendered report so it can be re-served (dashboard + share link).

        Mints an unguessable share_token on first insert and keeps it stable across
        regenerations of the same period, so a link given to a customer never breaks.
        Returns the share_token.
        """
        token = secrets.token_urlsafe(24)
        # ON CONFLICT deliberately does NOT touch share_token — it stays stable.
        self.conn.execute(
            """INSERT INTO report_snapshots
               (customer_id, report_type, period_start, period_end, score, payload_json, html, share_token)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(customer_id, report_type, period_end) DO UPDATE SET
                 period_start=excluded.period_start, score=excluded.score,
                 payload_json=excluded.payload_json, html=excluded.html,
                 created_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')""",
            (customer_id, report_type, period_start, period_end, score, payload_json, html, token),
        )
        self.conn.commit()
        row = self.conn.execute(
            "SELECT share_token FROM report_snapshots WHERE customer_id = ? AND report_type = ? AND period_end = ?",
            (customer_id, report_type, period_end),
        ).fetchone()
        return row["share_token"] if row else token

    def delete_report_snapshot(self, snapshot_id: int) -> bool:
        self.conn.execute("DELETE FROM report_snapshots WHERE id = ?", (snapshot_id,))
        self.conn.commit()
        return self.conn.total_changes > 0

    def delete_all_report_snapshots(self, customer_id: str, report_type: str = "weekly") -> int:
        cur = self.conn.execute(
            "DELETE FROM report_snapshots WHERE customer_id = ? AND report_type = ?",
            (customer_id, report_type),
        )
        self.conn.commit()
        return cur.rowcount

    def get_report_by_token(self, token: str) -> dict | None:
        """Look up a single snapshot by its share token (public, unguessable link)."""
        if not token:
            return None
        cur = self.conn.execute(
            "SELECT * FROM report_snapshots WHERE share_token = ? LIMIT 1", (token,)
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def mark_report_emailed(self, customer_id: str, report_type: str, period_end: str) -> None:
        self.conn.execute(
            "UPDATE report_snapshots SET emailed_at = strftime('%Y-%m-%dT%H:%M:%SZ','now') "
            "WHERE customer_id = ? AND report_type = ? AND period_end = ?",
            (customer_id, report_type, period_end),
        )
        self.conn.commit()

    def get_report_snapshot(self, snapshot_id: int) -> dict | None:
        """Fetch a single snapshot by primary key, including payload_json and html."""
        cur = self.conn.execute("SELECT * FROM report_snapshots WHERE id = ?", (snapshot_id,))
        row = cur.fetchone()
        return dict(row) if row else None

    def get_latest_report_snapshot(self, customer_id: str, report_type: str = "weekly") -> dict | None:
        cur = self.conn.execute(
            "SELECT * FROM report_snapshots WHERE customer_id = ? AND report_type = ? "
            "ORDER BY period_end DESC LIMIT 1",
            (customer_id, report_type),
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def get_report_snapshots(self, customer_id: str, report_type: str = "weekly", limit: int = 26,
                             include_payload: bool = False) -> list[dict]:
        # Listings stay lean; `include_payload=True` also pulls the (large) captured
        # point-in-time payload_json, needed to re-render history against a new template.
        cols = "id, report_type, period_start, period_end, score, share_token, emailed_at, created_at"
        if include_payload:
            cols += ", payload_json"
        cur = self.conn.execute(
            f"SELECT {cols} FROM report_snapshots WHERE customer_id = ? AND report_type = ? "
            "ORDER BY period_end DESC LIMIT ?",
            (customer_id, report_type, limit),
        )
        return [dict(r) for r in cur.fetchall()]

    # --- GSC query-level data (R1) ---

    def save_gsc_query_daily(self, customer_id: str, date: str, rows: list[dict]) -> int:
        """Upsert query-dimension GSC rows for one day. rows: query/clicks/impressions/ctr/position."""
        self.conn.executemany(
            """INSERT INTO gsc_query_daily (customer_id, date, query, clicks, impressions, ctr, position)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(customer_id, date, query) DO UPDATE SET
                 clicks=excluded.clicks, impressions=excluded.impressions,
                 ctr=excluded.ctr, position=excluded.position""",
            [(customer_id, date, r["query"], int(r.get("clicks", 0)),
              int(r.get("impressions", 0)), float(r.get("ctr", 0.0)),
              float(r.get("position", 0.0))) for r in rows],
        )
        self.conn.commit()
        return len(rows)

    def get_top_queries(self, customer_id: str, start: str, end: str, limit: int = 10) -> list[dict]:
        """Top queries by clicks in [start, end], with impression-weighted avg position."""
        cur = self.conn.execute(
            """SELECT query, SUM(clicks) AS clicks, SUM(impressions) AS impressions,
                      CASE WHEN SUM(impressions) > 0
                           THEN SUM(position * impressions) / SUM(impressions)
                           ELSE AVG(position) END AS position
               FROM gsc_query_daily
               WHERE customer_id = ? AND date >= ? AND date <= ?
               GROUP BY query ORDER BY clicks DESC LIMIT ?""",
            (customer_id, start, end, limit),
        )
        return [dict(r) for r in cur.fetchall()]

    def get_query_aggregates(self, customer_id: str, start: str, end: str,
                             min_impressions: int = 10, limit: int = 300) -> list[dict]:
        """All queries in [start,end] aggregated (clicks/impressions/ctr/impression-
        weighted position), ordered by impressions desc. Powers the search-data
        content recommender."""
        cur = self.conn.execute(
            """SELECT query, SUM(clicks) AS clicks, SUM(impressions) AS impressions,
                      CASE WHEN SUM(impressions) > 0
                           THEN 1.0 * SUM(clicks) / SUM(impressions) ELSE 0 END AS ctr,
                      CASE WHEN SUM(impressions) > 0
                           THEN SUM(position * impressions) / SUM(impressions)
                           ELSE AVG(position) END AS position
               FROM gsc_query_daily
               WHERE customer_id = ? AND date >= ? AND date <= ?
               GROUP BY query HAVING SUM(impressions) >= ?
               ORDER BY impressions DESC LIMIT ?""",
            (customer_id, start, end, min_impressions, limit),
        )
        return [dict(r) for r in cur.fetchall()]

    def get_query_movers(self, customer_id: str, cur_start: str, cur_end: str,
                         prev_start: str, prev_end: str, limit: int = 5) -> dict:
        """Compare avg position this period vs prior; return biggest improvers/decliners."""
        def avg_positions(s, e):
            cur = self.conn.execute(
                """SELECT query,
                          CASE WHEN SUM(impressions) > 0
                               THEN SUM(position * impressions) / SUM(impressions)
                               ELSE AVG(position) END AS position,
                          SUM(clicks) AS clicks
                   FROM gsc_query_daily WHERE customer_id = ? AND date >= ? AND date <= ?
                   GROUP BY query""",
                (customer_id, s, e),
            )
            return {r["query"]: dict(r) for r in cur.fetchall()}

        now, prev = avg_positions(cur_start, cur_end), avg_positions(prev_start, prev_end)
        moves = []
        for q, c in now.items():
            if q in prev and prev[q]["position"] and c["position"]:
                # lower position number = better; positive move = improvement
                delta = round(prev[q]["position"] - c["position"], 1)
                if abs(delta) >= 0.3:
                    moves.append({"query": q, "position": round(c["position"], 1),
                                  "move": delta, "clicks": c["clicks"]})
        moves.sort(key=lambda m: m["move"], reverse=True)
        return {"up": moves[:limit], "down": [m for m in reversed(moves) if m["move"] < 0][:limit]}

    # --- Competitor snapshots (R2) ---

    def save_competitor_snapshot(self, competitor_id: int, customer_id: str, date: str,
                                 rating: float, review_count: int) -> None:
        self.conn.execute(
            """INSERT INTO competitor_snapshots (competitor_id, customer_id, date, rating, review_count)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(competitor_id, date) DO UPDATE SET
                 rating=excluded.rating, review_count=excluded.review_count""",
            (competitor_id, customer_id, date, rating, review_count),
        )
        self.conn.commit()

    def get_competitor_review_gap(self, customer_id: str, own_review_count: int) -> dict | None:
        """Gap vs the top competitor (by current review_count) + week-over-week gap change."""
        comps = self.get_competitors(customer_id)
        if not comps:
            return None
        top = max(comps, key=lambda c: c.get("review_count", 0))
        gap_now = own_review_count - top.get("review_count", 0)
        # prior-week gap from snapshots, if any
        prev_gap = None
        if top.get("id"):
            cur = self.conn.execute(
                "SELECT review_count FROM competitor_snapshots WHERE competitor_id = ? "
                "AND date <= date('now', '-7 day') ORDER BY date DESC LIMIT 1",
                (top["id"],),
            )
            row = cur.fetchone()
            if row is not None:
                prev_gap = own_review_count - row["review_count"]
        return {
            "competitor": top.get("name", "nearest competitor"),
            "competitor_reviews": top.get("review_count", 0),
            "gap": gap_now,
            "gap_delta": (gap_now - prev_gap) if prev_gap is not None else None,
        }

    # --- Conversions (R3) ---

    def record_conversion(self, customer_id: str, date: str, event_name: str,
                          channel: str, count: int) -> None:
        self.conn.execute(
            """INSERT INTO conversions_daily (customer_id, date, event_name, channel, count)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(customer_id, date, event_name, channel) DO UPDATE SET
                 count=excluded.count""",
            (customer_id, date, event_name, channel, count),
        )
        self.conn.commit()

    def get_conversions(self, customer_id: str, start: str, end: str,
                        channel: str | None = None) -> dict:
        """Totals per event_name in [start, end]. Returns {event_name: count}."""
        q = ("SELECT event_name, SUM(count) AS total FROM conversions_daily "
             "WHERE customer_id = ? AND date >= ? AND date <= ?")
        params = [customer_id, start, end]
        if channel:
            q += " AND channel = ?"
            params.append(channel)
        q += " GROUP BY event_name"
        cur = self.conn.execute(q, params)
        return {r["event_name"]: r["total"] for r in cur.fetchall()}

    # --- Prospects / Sales Pipeline ---

    _PROSPECT_COLUMNS = frozenset({
        "name", "email", "phone", "contact_name", "vertical", "stage",
        "lost_reason", "report_id", "overall_score", "grade", "report_data",
        "stripe_checkout_id", "stripe_customer_id", "notes",
    })

    def upsert_prospect(self, prospect_id: str, domain: str, name: str, **kwargs) -> str:
        """Create or update a prospect. Returns the prospect ID."""
        existing = self.conn.execute(
            "SELECT id FROM prospects WHERE domain = ?", (domain,)
        ).fetchone()
        if existing:
            safe = {k: v for k, v in kwargs.items() if k in self._PROSPECT_COLUMNS and v is not None}
            sets = ", ".join(f"{k} = ?" for k in safe)
            vals = list(safe.values())
            if sets:
                sets += ", updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')"
                self.conn.execute(
                    f"UPDATE prospects SET {sets} WHERE domain = ?",
                    vals + [domain],
                )
                self.conn.commit()
            return existing["id"]
        self.conn.execute(
            """INSERT INTO prospects (id, domain, name, email, phone, contact_name,
               vertical, stage, report_id, overall_score, grade, report_data)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'new_lead', ?, ?, ?, ?)""",
            (
                prospect_id, domain, name,
                kwargs.get("email"), kwargs.get("phone"), kwargs.get("contact_name"),
                kwargs.get("vertical", "dental"),
                kwargs.get("report_id"), kwargs.get("overall_score"),
                kwargs.get("grade"), kwargs.get("report_data"),
            ),
        )
        self.conn.commit()
        return prospect_id

    def get_prospect(self, prospect_id: str) -> dict | None:
        cur = self.conn.execute("SELECT * FROM prospects WHERE id = ?", (prospect_id,))
        row = cur.fetchone()
        return dict(row) if row else None

    def get_prospect_by_domain(self, domain: str) -> dict | None:
        cur = self.conn.execute("SELECT * FROM prospects WHERE domain = ?", (domain,))
        row = cur.fetchone()
        return dict(row) if row else None

    def get_prospects_by_stage(self, stage: str | None = None) -> list[dict]:
        if stage:
            cur = self.conn.execute(
                "SELECT * FROM prospects WHERE stage = ? ORDER BY updated_at DESC", (stage,)
            )
        else:
            cur = self.conn.execute("SELECT * FROM prospects ORDER BY updated_at DESC")
        return [dict(r) for r in cur.fetchall()]

    def get_all_prospects_grouped(self) -> dict[str, list[dict]]:
        """Get all prospects grouped by stage for the kanban board."""
        stages = ["new_lead", "outreach_sent", "follow_up", "interested",
                   "proposal_sent", "signing_up", "customer", "lost"]
        result = {s: [] for s in stages}
        cur = self.conn.execute("SELECT * FROM prospects ORDER BY updated_at DESC")
        for row in cur.fetchall():
            r = dict(row)
            stage = r.get("stage", "new_lead")
            if stage in result:
                result[stage].append(r)
            else:
                result["new_lead"].append(r)
        return result

    def update_prospect_stage(self, prospect_id: str, new_stage: str,
                               created_by: str = "", lost_reason: str = "") -> bool:
        cur = self.conn.execute("SELECT stage FROM prospects WHERE id = ?", (prospect_id,))
        row = cur.fetchone()
        if not row:
            return False
        old_stage = row["stage"]
        updates = "stage = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')"
        params: list = [new_stage]
        if new_stage == "lost" and lost_reason:
            updates += ", lost_reason = ?"
            params.append(lost_reason)
        params.append(prospect_id)
        self.conn.execute(f"UPDATE prospects SET {updates} WHERE id = ?", params)
        self.conn.execute(
            """INSERT INTO prospect_activities (prospect_id, activity_type, stage_from, stage_to, created_by)
               VALUES (?, 'stage_change', ?, ?, ?)""",
            (prospect_id, old_stage, new_stage, created_by),
        )
        self.conn.commit()
        return True

    def update_prospect(self, prospect_id: str, **kwargs) -> bool:
        safe = {k: v for k, v in kwargs.items() if k in self._PROSPECT_COLUMNS}
        if not safe:
            return False
        sets = ", ".join(f"{k} = ?" for k in safe)
        sets += ", updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')"
        vals = list(safe.values()) + [prospect_id]
        self.conn.execute(f"UPDATE prospects SET {sets} WHERE id = ?", vals)
        self.conn.commit()
        return True

    def add_prospect_activity(self, prospect_id: str, activity_type: str,
                               subject: str = "", body: str = "",
                               created_by: str = "") -> int:
        cur = self.conn.execute(
            """INSERT INTO prospect_activities (prospect_id, activity_type, subject, body, created_by)
               VALUES (?, ?, ?, ?, ?)""",
            (prospect_id, activity_type, subject, body, created_by),
        )
        self.conn.commit()
        return cur.lastrowid or 0

    def get_prospect_activities(self, prospect_id: str, limit: int = 50) -> list[dict]:
        cur = self.conn.execute(
            """SELECT * FROM prospect_activities WHERE prospect_id = ?
               ORDER BY id DESC LIMIT ?""",
            (prospect_id, limit),
        )
        return [dict(r) for r in cur.fetchall()]

    def get_prospect_counts(self) -> dict[str, int]:
        """Get count of prospects per stage."""
        cur = self.conn.execute(
            "SELECT stage, COUNT(*) as cnt FROM prospects GROUP BY stage"
        )
        return {r["stage"]: r["cnt"] for r in cur.fetchall()}

    # --- Customer activity timeline + status ---

    def add_customer_activity(self, customer_id: str, activity_type: str = "note",
                              subject: str = "", body: str = "",
                              meta: dict | None = None, created_by: str = "",
                              created_at: str | None = None) -> int:
        """Append a note / status change / email to a customer's timeline.

        Returns the row id, or 0 if a duplicate email (same gmail_id) was skipped.
        """
        # De-dupe ingested emails by their gmail message id so repeated syncs
        # don't create duplicate timeline entries.
        gmail_id = (meta or {}).get("gmail_id")
        if gmail_id:
            existing = self.conn.execute(
                "SELECT 1 FROM customer_activities WHERE customer_id = ? "
                "AND json_extract(meta_json, '$.gmail_id') = ? LIMIT 1",
                (customer_id, gmail_id),
            ).fetchone()
            if existing:
                return 0
        if created_at:
            cur = self.conn.execute(
                """INSERT INTO customer_activities
                   (customer_id, activity_type, subject, body, meta_json, created_by, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (customer_id, activity_type, subject, body,
                 json.dumps(meta or {}), created_by, created_at),
            )
        else:
            cur = self.conn.execute(
                """INSERT INTO customer_activities
                   (customer_id, activity_type, subject, body, meta_json, created_by)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (customer_id, activity_type, subject, body,
                 json.dumps(meta or {}), created_by),
            )
        self.conn.commit()
        return cur.lastrowid or 0

    def get_customer_activities(self, customer_id: str, limit: int = 100,
                                activity_type: str | None = None) -> list[dict]:
        """Return a customer's activity timeline, newest first."""
        sql = "SELECT * FROM customer_activities WHERE customer_id = ?"
        params: list = [customer_id]
        if activity_type:
            sql += " AND activity_type = ?"
            params.append(activity_type)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        rows = []
        for r in self.conn.execute(sql, params).fetchall():
            d = dict(r)
            try:
                d["meta"] = json.loads(d.get("meta_json") or "{}")
            except Exception:
                d["meta"] = {}
            rows.append(d)
        return rows

    def delete_customer_activity(self, customer_id: str, activity_id: int) -> bool:
        cur = self.conn.execute(
            "DELETE FROM customer_activities WHERE id = ? AND customer_id = ?",
            (activity_id, customer_id),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def set_customer_status_note(self, customer_id: str, status_note: str | None = None,
                                 next_action: str | None = None) -> None:
        """Update the pinned status line and/or next action for a customer.

        Distinct from set_customer_status (which sets the lifecycle status field).
        """
        sets, params = [], []
        if status_note is not None:
            sets.append("status_note = ?")
            params.append(status_note)
        if next_action is not None:
            sets.append("next_action = ?")
            params.append(next_action)
        if not sets:
            return
        params.append(customer_id)
        self.conn.execute(f"UPDATE customers SET {', '.join(sets)} WHERE id = ?", params)
        self.conn.commit()
