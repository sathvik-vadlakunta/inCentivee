"""Customer database — single source of truth for all practice data.

Replaces scattered JSON files with a proper SQLite database.
All secrets (API keys, tokens) stay in env vars / secrets manager — never in SQLite.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from geo_agent.config import Customer, Provider

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 3

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
    published_at TEXT
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
        # Migration: map old onboarding_step values to new 9-column board
        self.conn.execute("UPDATE customers SET onboarding_step = 'outreach' WHERE onboarding_step = 'contacted'")
        self.conn.execute("UPDATE customers SET onboarding_step = 'setup' WHERE onboarding_step IN ('access_pending', 'access_granted')")
        self.conn.execute("UPDATE customers SET onboarding_step = 'review' WHERE onboarding_step IN ('audit_setup', 'review_approve')")

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
               (id, customer_id, run_date, total_mentions, total_queries, mention_rate, avg_position, engines_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (run["id"], run["customer_id"], run["run_date"], run["total_mentions"],
             run["total_queries"], run["mention_rate"], run.get("avg_position"),
             json.dumps(run.get("engines", {}))),
        )
        self.conn.commit()

    def save_ai_mention_result(self, result: dict):
        """Save a single AI mention check result."""
        self.conn.execute(
            """INSERT INTO ai_mention_results
               (run_id, customer_id, engine, prompt, prompt_category, mentioned,
                position, quality_score, context, full_response, is_disclaimer)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (result["run_id"], result["customer_id"], result["engine"],
             result["prompt"], result.get("prompt_category", "general"),
             1 if result["mentioned"] else 0, result.get("position"),
             result.get("quality_score", 0),
             result.get("context", ""), result.get("full_response", ""),
             1 if result.get("is_disclaimer") else 0),
        )
        self.conn.commit()

    def get_ai_mention_runs(self, customer_id: str, limit: int = 52) -> list[dict]:
        """Get recent AI mention runs for a customer."""
        cur = self.conn.execute(
            "SELECT * FROM ai_mention_runs WHERE customer_id = ? ORDER BY run_date DESC LIMIT ?",
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

    def get_latest_ai_run_summary(self, customer_id: str) -> dict | None:
        """Return {mention_count, total_queries, mention_rate} from most recent run."""
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
