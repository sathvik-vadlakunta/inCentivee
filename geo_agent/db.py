"""Customer database — single source of truth for all practice data.

Replaces scattered JSON files with a proper SQLite database.
All secrets (API keys, tokens) stay in env vars / secrets manager — never in SQLite.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from geo_agent.config import Customer, Provider

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 8

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
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
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

        # Migration: store OS pid of the pipeline subprocess so runs can be truly cancelled / reaped
        run_cols = [r[1] for r in self.conn.execute("PRAGMA table_info(runs)").fetchall()]
        if "pid" not in run_cols:
            self.conn.execute("ALTER TABLE runs ADD COLUMN pid INTEGER")

        # Migration v1 → v2: platform-aware content publishing + squarespace credentials
        rec_cols = [r[1] for r in self.conn.execute("PRAGMA table_info(content_recommendations)").fetchall()]
        if "platform_item_id" not in rec_cols:
            self.conn.execute("ALTER TABLE content_recommendations ADD COLUMN platform_item_id TEXT DEFAULT ''")
            self.conn.execute("ALTER TABLE content_recommendations ADD COLUMN platform_draft_url TEXT DEFAULT ''")
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

        # Migration: map old onboarding_step values to new 9-column board
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

        self.conn.execute(
            "UPDATE schema_version SET version = ?", (SCHEMA_VERSION,)
        )
        self.conn.commit()

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
               (id, customer_id, run_date, total_mentions, total_queries, mention_rate, avg_position, engines_json, prompt_set)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (run["id"], run["customer_id"], run["run_date"], run["total_mentions"],
             run["total_queries"], run["mention_rate"], run.get("avg_position"),
             json.dumps(run.get("engines", {})), run.get("prompt_set", "benchmark")),
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

    def get_ai_mention_runs(self, customer_id: str, limit: int = 52) -> list[dict]:
        """Get recent AI mention runs for a customer (newest first)."""
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
            "WHERE customer_id = ? AND prompt_set = ? AND total_queries > 0 "
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
        first = self.conn.execute(
            "SELECT * FROM ai_mention_runs WHERE customer_id = ? AND total_queries > 0 "
            "ORDER BY run_date ASC, created_at ASC LIMIT 1",
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
                "AND total_queries > 0 ORDER BY run_date DESC, created_at DESC LIMIT ?",
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

        total = sum(r["mention_count"] for r in rows)
        customer_mentions = sum(r["mention_count"] for r in rows if r["is_customer"])
        customer_share = customer_mentions / total if total > 0 else 0

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
            "competitors": competitors[:15],
            "total_entity_mentions": total,
            "total_unique_entities": len(rows),
            "runs_analyzed": len(run_ids),
        }

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
             priority, category, status, ai_impact_reason, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                rec["id"], rec["customer_id"], rec["rec_type"],
                rec.get("target_page", ""), rec["title"],
                rec.get("description", ""), rec.get("html_snippet", ""),
                rec.get("priority", 3), rec.get("category", "general"),
                rec.get("status", "pending"), rec.get("ai_impact_reason", ""),
                rec.get("created_at", datetime.now(timezone.utc).isoformat()),
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
            cur = self.conn.execute("SELECT COUNT(*) FROM alerts WHERE dismissed = 0")
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
        cur = self.conn.execute(
            """INSERT OR REPLACE INTO site_audits
               (customer_id, audit_date, performance_score, accessibility_score,
                seo_score, best_practices_score, issues_json, raw_data_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (customer_id, audit_date,
             scores.get("performance"), scores.get("accessibility"),
             scores.get("seo"), scores.get("best_practices"),
             json.dumps(issues), json.dumps(raw_data or {})),
        )
        audit_id = cur.lastrowid
        # Save individual issues
        self.conn.execute(
            "DELETE FROM audit_issues WHERE customer_id = ? AND audit_id = ?",
            (customer_id, audit_id),
        )
        for issue in issues:
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
            "SELECT * FROM reviews WHERE customer_id = ? ORDER BY review_date DESC LIMIT ?",
            (customer_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

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

    # --- GBP Audit ---

    def save_gbp_audit(self, customer_id, score, details):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self.conn.execute(
            "INSERT OR REPLACE INTO gbp_audit (customer_id, date, score, details_json) VALUES (?, ?, ?, ?)",
            (customer_id, today, score, json.dumps(details)),
        )
        self.conn.commit()

    def get_latest_gbp_audit(self, customer_id):
        row = self.conn.execute(
            "SELECT * FROM gbp_audit WHERE customer_id = ? ORDER BY date DESC LIMIT 1",
            (customer_id,),
        ).fetchone()
        if row:
            d = dict(row)
            d["details"] = json.loads(d.get("details_json", "{}"))
            return d
        return None

    # --- Page Scores ---

    def save_page_score(self, customer_id, page_url, score, word_count=0, readability_grade=0, breakdown=None):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self.conn.execute(
            "INSERT OR REPLACE INTO page_scores (customer_id, page_url, score, word_count, readability_grade, breakdown_json, date) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (customer_id, page_url, score, word_count, readability_grade, json.dumps(breakdown or {}), today),
        )
        self.conn.commit()

    def get_page_scores(self, customer_id):
        rows = self.conn.execute(
            "SELECT * FROM page_scores WHERE customer_id = ? ORDER BY score DESC",
            (customer_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # --- Topic Clusters ---

    def save_topic_cluster(self, customer_id, cluster_name, pillar_page_url="", keywords=None, gap_pages=None):
        self.conn.execute(
            "INSERT OR REPLACE INTO topic_clusters (customer_id, cluster_name, pillar_page_url, keywords_json, gap_pages_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (customer_id, cluster_name, pillar_page_url, json.dumps(keywords or []), json.dumps(gap_pages or [])),
        )
        self.conn.commit()

    def get_topic_clusters(self, customer_id):
        rows = self.conn.execute(
            "SELECT * FROM topic_clusters WHERE customer_id = ? ORDER BY cluster_name",
            (customer_id,),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["keywords"] = json.loads(d.get("keywords_json", "[]"))
            d["gap_pages"] = json.loads(d.get("gap_pages_json", "[]"))
            result.append(d)
        return result

    # --- AI Readiness ---

    def save_ai_readiness(self, customer_id, score, breakdown):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self.conn.execute(
            "INSERT OR REPLACE INTO ai_readiness_scores (customer_id, date, score, breakdown_json) VALUES (?, ?, ?, ?)",
            (customer_id, today, score, json.dumps(breakdown)),
        )
        self.conn.commit()

    def get_latest_ai_readiness(self, customer_id):
        row = self.conn.execute(
            "SELECT * FROM ai_readiness_scores WHERE customer_id = ? ORDER BY date DESC LIMIT 1",
            (customer_id,),
        ).fetchone()
        if row:
            d = dict(row)
            d["breakdown"] = json.loads(d.get("breakdown_json", "{}"))
            return d
        return None

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
            access_platforms = ["gsc", "ga", "gbp", "cloudflare"]
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
