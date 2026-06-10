# SEO Tools Expansion — Replace Semrush with Native Capabilities

Started: 2026-05-26

## Problem

Semrush costs $140/month and covers features PracticeRank can build natively using free APIs (GSC, PageSpeed Insights, etc.) at ~$1-2/customer/month. PracticeRank's unique value (AI mentions, GEO, llms.txt) isn't covered by Semrush anyway.

## Goal

Build 5 SEO capabilities into admin.practicerank.ai so a VA can manage everything from one dashboard without needing Semrush or other third-party tools.

---

## Feature 1: Keyword Rank Tracking

**What**: Track where each customer ranks on Google for their target keywords over time.

**Data Source**: Google Search Console API (already built in `geo_agent/gsc_client.py`)

**How it works**:
1. VA adds target keywords per customer (or auto-populated from services + city)
2. Weekly cron pulls GSC data: position, clicks, impressions, CTR per keyword
3. Dashboard shows rank history with sparklines and trend arrows

**Database changes** (`geo_agent/db.py`):
```sql
CREATE TABLE IF NOT EXISTS keyword_tracking (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL REFERENCES customers(id),
    keyword TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'manual',  -- manual/auto/gsc_discovered
    is_tracked INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE(customer_id, keyword)
);

CREATE TABLE IF NOT EXISTS keyword_ranks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL REFERENCES customers(id),
    keyword TEXT NOT NULL,
    date TEXT NOT NULL,
    position REAL,           -- avg Google position (from GSC)
    clicks INTEGER DEFAULT 0,
    impressions INTEGER DEFAULT 0,
    ctr REAL DEFAULT 0.0,
    UNIQUE(customer_id, keyword, date)
);
CREATE INDEX idx_keyword_ranks_lookup ON keyword_ranks(customer_id, keyword, date);
```

**New DB methods**:
- `add_tracked_keyword(customer_id, keyword, source="manual")`
- `remove_tracked_keyword(customer_id, keyword)`
- `get_tracked_keywords(customer_id)` → list of keyword dicts
- `save_keyword_rank(customer_id, keyword, date, position, clicks, impressions, ctr)`
- `get_keyword_rank_history(customer_id, keyword, days=90)` → list of rank snapshots
- `get_keyword_summary(customer_id)` → aggregate: total tracked, avg position, top movers

**New script**: `scripts/scheduled_keyword_pull.py`
- Runs weekly (Sunday night) via cron
- For each active customer with GSC access:
  - Fetch last 7 days of GSC query data via `fetch_search_metrics(site_url, dimensions=["query", "date"])`
  - Match against tracked keywords (fuzzy: lowercase, strip whitespace)
  - Also discover new high-impression keywords not yet tracked → flag as `source='gsc_discovered'`
  - Save to `keyword_ranks` table

**API endpoints** (`dashboard/app.py`):
- `POST /api/customer/<id>/keywords` — add keyword(s), body: `{"keywords": ["dental implants austin", ...]}`
- `DELETE /api/customer/<id>/keywords/<keyword>` — remove tracked keyword
- `GET /api/customer/<id>/keywords/ranks` — return rank history JSON for charts
- `POST /api/customer/<id>/keywords/auto-generate` — auto-generate keywords from services + city + specialties

**Auto-generate logic**:
```python
def auto_generate_keywords(customer):
    keywords = []
    city = customer["city"]
    services = db.get_services(customer_id)
    specialties = customer.get("specialties", [])
    name = customer["name"]
    biz_type = customer.get("business_type", "practice")

    # Service + city combos: "dental implants austin tx"
    for svc in services:
        keywords.append(f"{svc['name']} {city}")
        keywords.append(f"{svc['name']} near me")
        keywords.append(f"best {svc['name']} {city}")

    # Specialty combos: "cosmetic dentist austin"
    for spec in specialties:
        keywords.append(f"{spec} {city}")

    # Business type combos: "dentist near me", "dentist austin tx"
    type_label = {"practice": "dentist", "legal": "lawyer", "medical": "doctor"}.get(biz_type, biz_type)
    keywords.append(f"{type_label} {city}")
    keywords.append(f"{type_label} near me")
    keywords.append(f"best {type_label} {city}")

    # Brand: "hilltop dental reviews"
    keywords.append(f"{name} reviews")
    keywords.append(name)

    return list(set(k.lower().strip() for k in keywords))
```

**UI** — New "Keywords" sub-section inside the **SEO & GEO** tab:

```
+------------------------------------------------------------------+
| Keywords                                    [+ Add] [Auto-Generate] |
+------------------------------------------------------------------+
| Keyword              | Position | Trend | Clicks | Impressions     |
|----------------------|----------|-------|--------|-----------------|
| dental implants austin| 8.2     | ↑ 3   | 45     | 1,200          |
| cosmetic dentist tx   | 14.5    | ↓ 2   | 12     | 890            |
| best dentist austin   | 22.1    | ↑ 5   | 8      | 2,100          |
| [discovered] veneers..| 31.0    | new   | 3      | 450            |
+------------------------------------------------------------------+
| Avg Position: 18.9 | Total Clicks: 68 | Tracked: 15 keywords      |
+------------------------------------------------------------------+
```

- Color coding: position ≤10 green, 11-20 yellow, 21+ red
- Trend column: shows position change vs 4 weeks ago, ↑ = improved (lower number)
- Discovered keywords show with a "discovered" badge and an "Add" button
- Sparkline chart per keyword on click/expand (last 12 weeks)
- "Auto-Generate" button pre-fills based on services + city, VA reviews and confirms

---

## Feature 2: Enhanced Site Audits

**What**: Automated technical SEO audits using Google PageSpeed Insights API (free, no key needed for basic use) + custom checks.

**Data Source**: PageSpeed Insights API v5 (free, 25K queries/day) + direct HTTP checks

**How it works**:
1. VA clicks "Run Audit" on customer detail page
2. System checks: performance, accessibility, SEO, best practices scores + specific technical issues
3. Results stored and compared over time
4. Issues categorized by priority with VA-friendly fix instructions

**Database changes**:
```sql
CREATE TABLE IF NOT EXISTS site_audits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL REFERENCES customers(id),
    audit_date TEXT NOT NULL,
    performance_score INTEGER,   -- 0-100 from Lighthouse
    accessibility_score INTEGER,
    seo_score INTEGER,
    best_practices_score INTEGER,
    issues_json TEXT NOT NULL DEFAULT '[]',  -- JSON array of issue objects
    raw_data_json TEXT NOT NULL DEFAULT '{}', -- full API response (compressed)
    UNIQUE(customer_id, audit_date)
);

CREATE TABLE IF NOT EXISTS audit_issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL REFERENCES customers(id),
    audit_date TEXT NOT NULL,
    category TEXT NOT NULL,        -- performance/seo/accessibility/schema/security
    severity TEXT NOT NULL,        -- critical/warning/info
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    fix_instruction TEXT NOT NULL DEFAULT '',  -- VA-friendly fix steps
    status TEXT NOT NULL DEFAULT 'open',       -- open/fixed/ignored
    fixed_date TEXT
);
CREATE INDEX idx_audit_issues_customer ON audit_issues(customer_id, status);
```

**New module**: `geo_agent/site_auditor.py`

```python
def run_site_audit(domain: str) -> dict:
    """Run a comprehensive site audit. Returns scores + issues list."""
    results = {
        "lighthouse": _run_pagespeed(domain),
        "schema": _check_schema_markup(domain),
        "security": _check_security_headers(domain),
        "mobile": _check_mobile_friendly(domain),
        "llms_txt": _check_llms_txt(domain),
        "sitemap": _check_sitemap(domain),
        "robots": _check_robots_txt(domain),
    }
    return results
```

Individual checks:
- **PageSpeed Insights**: `GET https://www.googleapis.com/pagespeedonline/v5/runPagespeedTest?url=https://{domain}&strategy=mobile` — returns Lighthouse scores + specific audit failures
- **Schema markup**: HTTP GET homepage, parse for JSON-LD presence (LocalBusiness, FAQPage, etc.)
- **Security headers**: Check for HTTPS redirect, HSTS, X-Frame-Options, CSP
- **Mobile-friendly**: PageSpeed mobile strategy check
- **llms.txt**: Check if `/llms.txt` exists and has content
- **Sitemap**: Check `/sitemap.xml` exists and is valid XML
- **robots.txt**: Check exists, not blocking important paths

Each issue gets a VA-friendly fix instruction:
```python
{
    "category": "seo",
    "severity": "critical",
    "title": "Missing FAQ schema markup",
    "description": "No FAQPage JSON-LD found on homepage",
    "fix_instruction": "Go to the SEO & GEO tab and click 'Generate Schema'. This will create FAQ schema from the customer's services."
}
```

**API endpoints**:
- `POST /api/customer/<id>/audit/run` — trigger new audit (runs in background thread)
- `GET /api/customer/<id>/audit/latest` — return latest audit results JSON
- `POST /api/customer/<id>/audit/issues/<issue_id>/status` — mark issue as fixed/ignored

**UI** — New "Site Audit" sub-section in **SEO & GEO** tab:

```
+------------------------------------------------------------------+
| Site Audit                          Last run: May 20   [Run Audit] |
+------------------------------------------------------------------+
| Performance  [======----] 62  | SEO        [========--] 85       |
| Accessibility[=======---] 74  | Best Pract [==========-] 92     |
+------------------------------------------------------------------+
| Issues (7 open)                                                    |
| [!] CRITICAL: Missing meta descriptions on 3 pages                |
|     Fix: Go to Webflow > Pages > [page] > SEO Settings > ...     |
| [!] CRITICAL: No FAQ schema markup                                |
|     Fix: Click 'Generate Schema' in SEO & GEO tab                |
| [~] WARNING: Images missing alt text (12 images)                  |
|     Fix: In Webflow, select each image > Settings > Alt text      |
| [i] INFO: No HSTS header                                         |
|     Fix: Enable in Cloudflare > SSL/TLS > Edge Certificates      |
+------------------------------------------------------------------+
| Score History: [sparkline chart showing 4 audit scores over time] |
+------------------------------------------------------------------+
```

- Each issue has a checkbox to mark fixed or "ignore" button
- VA can see exactly what to do for each issue
- Score comparison vs previous audit (arrows showing improvement)
- "Run Audit" shows progress indicator (takes ~10-15 seconds)

---

## Feature 3: Competitor Keyword Analysis

**What**: Show what keywords competitors rank for that the customer doesn't, identifying content gaps.

**Data Source**: GSC (own data) + Google autocomplete/related searches (free) + existing competitor data from `competitive_intel.py`

**How it works**:
1. System already tracks competitors via Google Places (`competitive_intel.py`)
2. For each competitor domain, scrape their sitemap.xml to find content topics
3. Cross-reference with customer's tracked keywords to find gaps
4. Use Google autocomplete API for keyword suggestions around customer's services

**Database changes**:
```sql
CREATE TABLE IF NOT EXISTS competitor_keywords (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL REFERENCES customers(id),
    competitor_name TEXT NOT NULL,
    competitor_domain TEXT NOT NULL DEFAULT '',
    keyword TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'sitemap',  -- sitemap/autocomplete/manual
    discovered_date TEXT NOT NULL,
    is_gap INTEGER NOT NULL DEFAULT 1,  -- 1 if customer doesn't rank for this
    UNIQUE(customer_id, competitor_domain, keyword)
);
```

**New functions in `geo_agent/competitive_intel.py`**:
- `discover_competitor_topics(competitor_domain)` — fetch sitemap.xml, extract page titles/URLs, infer keywords from URL slugs and title tags
- `find_keyword_gaps(db, customer_id)` — compare competitor topics vs customer's tracked keywords, return gaps
- `get_autocomplete_suggestions(seed_keyword)` — `GET http://suggestqueries.google.com/complete/search?client=firefox&q={seed}` — returns Google autocomplete suggestions (free, no API key)

**API endpoints**:
- `POST /api/customer/<id>/competitors/analyze` — trigger competitor keyword discovery
- `GET /api/customer/<id>/competitors/gaps` — return keyword gap list

**UI** — New "Competitor Intel" sub-section in **SEO & GEO** tab:

```
+------------------------------------------------------------------+
| Competitor Keywords                          [Analyze Competitors] |
+------------------------------------------------------------------+
| Keyword Gaps (keywords competitors rank for, you don't):          |
|                                                                    |
| "teeth whitening cost austin" — found on: SmileCraft, BrightSmile |
|   [Add to Tracked] [Create Content]                               |
|                                                                    |
| "emergency dentist 78745" — found on: Austin Emergency Dental     |
|   [Add to Tracked] [Create Content]                               |
|                                                                    |
| "invisalign vs braces austin" — found on: SmileCraft             |
|   [Add to Tracked] [Create Content]                               |
+------------------------------------------------------------------+
| Competitor Content Activity:                                       |
| SmileCraft Dental — 12 blog posts (3 new this month)             |
| BrightSmile Austin — 8 blog posts (1 new this month)             |
+------------------------------------------------------------------+
```

- "Create Content" button sends the keyword to the Content tab as a topic suggestion
- "Add to Tracked" adds to keyword tracking
- VA can see at a glance what competitors are doing

---

## Feature 4: Backlink Monitoring

**What**: Track who links to the customer's site, monitor new/lost backlinks.

**Data Source**: Google Search Console Links API (free, already have access via `gsc_client.py`)

**How it works**:
1. GSC provides top linking sites and internal links via the Links resource
2. Weekly pull stores snapshot of backlinks
3. Dashboard shows new/lost links compared to previous snapshot
4. Alert when a high-value backlink is lost

**New functions in `geo_agent/gsc_client.py`**:
```python
def fetch_backlinks(site_url: str, limit: int = 100) -> list[dict] | None:
    """Fetch top linking sites from GSC Links resource."""
    service = _build_service()
    if service is None:
        return None
    try:
        response = service.links().list(siteUrl=site_url).execute()
        # Returns externalLinks with site URLs and link counts
        ...
    except Exception as exc:
        logger.warning(f"GSC backlinks request failed: {exc}")
        return None
```

**Database changes**:
```sql
CREATE TABLE IF NOT EXISTS backlinks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL REFERENCES customers(id),
    linking_domain TEXT NOT NULL,
    link_count INTEGER NOT NULL DEFAULT 1,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',  -- active/lost
    UNIQUE(customer_id, linking_domain)
);
CREATE INDEX idx_backlinks_customer ON backlinks(customer_id, status);
```

**API endpoints**:
- `POST /api/customer/<id>/backlinks/pull` — trigger GSC backlink pull
- `GET /api/customer/<id>/backlinks` — return backlink list with status

**UI** — New "Backlinks" sub-section in **SEO & GEO** tab:

```
+------------------------------------------------------------------+
| Backlinks (23 active)                         [Pull Latest]       |
+------------------------------------------------------------------+
| Domain                  | Links | Status | First Seen             |
|-------------------------|-------|--------|------------------------|
| healthgrades.com        | 3     | active | 2026-01-15            |
| yelp.com                | 2     | active | 2026-02-01            |
| austinmonthly.com       | 1     | NEW    | 2026-05-20            |
| zocdoc.com              | 1     | LOST   | 2026-03-01            |
+------------------------------------------------------------------+
| Summary: 23 active | 2 new this month | 1 lost this month        |
+------------------------------------------------------------------+
```

- NEW badges for links discovered in last 30 days
- LOST badges in red for links that disappeared
- Sort by link count or recency

---

## Feature 5: Content Gap / Topic Suggestions

**What**: AI-powered content suggestions based on keyword gaps, competitor analysis, and search trends.

**Data Source**: Keyword gaps (Feature 3) + Google autocomplete + existing content recommender

**How it works**:
1. Combine signals: keyword gaps from competitors, low-ranking tracked keywords, autocomplete "People also ask" style queries
2. Score and prioritize topics by potential impact
3. VA clicks "Create" to send topic to content pipeline
4. Track topic → draft → review → published lifecycle

**Database changes**:
```sql
CREATE TABLE IF NOT EXISTS content_topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL REFERENCES customers(id),
    topic TEXT NOT NULL,
    target_keyword TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'manual',  -- manual/keyword_gap/autocomplete/ai_suggestion
    priority TEXT NOT NULL DEFAULT 'medium',  -- high/medium/low
    status TEXT NOT NULL DEFAULT 'suggested',  -- suggested/approved/in_progress/published/rejected
    content_rec_id INTEGER,  -- FK to content_recommendations if content was created
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    notes TEXT NOT NULL DEFAULT ''
);
```

**Integration with existing content system**:
- When VA approves a topic, system auto-generates a content recommendation via existing `generate_content_recommendations` flow
- Topic includes target keyword so generated content is optimized for it
- Links back to keyword tracking so we can measure rank improvement after publishing

**API endpoints**:
- `GET /api/customer/<id>/topics` — list suggested topics
- `POST /api/customer/<id>/topics` — add manual topic
- `POST /api/customer/<id>/topics/<id>/approve` — approve and auto-generate content rec
- `POST /api/customer/<id>/topics/<id>/reject` — dismiss topic
- `POST /api/customer/<id>/topics/auto-suggest` — run AI topic suggestion engine

**UI** — Enhance existing **Content** tab with a "Topic Ideas" section at the top:

```
+------------------------------------------------------------------+
| Topic Ideas                                    [Generate Ideas]    |
+------------------------------------------------------------------+
| Priority | Topic                        | Source    | Action      |
|----------|------------------------------|-----------|-------------|
| HIGH     | Dental implant cost guide    | keyword   | [Approve]   |
|          | Target: "dental implants     | gap       | [Reject]    |
|          | cost austin"                 |           |             |
|----------|------------------------------|-----------|-------------|
| HIGH     | Emergency dental care guide  | competitor| [Approve]   |
|          | Target: "emergency dentist   | gap       | [Reject]    |
|          | 78745"                       |           |             |
|----------|------------------------------|-----------|-------------|
| MEDIUM   | Invisalign FAQ              | auto-     | [Approve]   |
|          | Target: "invisalign austin"  | complete  | [Reject]    |
+------------------------------------------------------------------+
```

- "Approve" creates a content recommendation and moves topic to `in_progress`
- After content is published, links back to keyword tracking for measurement
- "Generate Ideas" analyzes gaps + autocomplete + low-ranking keywords

---

## UI Restructure: SEO & GEO Tab

The current SEO & GEO tab has: SEO checklist, GEO files section, schema status. Restructure into sub-tabs:

```
SEO & GEO Tab:
├── Rankings    (Feature 1: keyword tracking + rank history)
├── Audit       (Feature 2: site audit scores + issues)
├── Competitors (Feature 3: competitor keyword gaps)
├── Backlinks   (Feature 4: linking domains)
└── GEO         (existing: llms.txt, schema, AI optimization)
```

Each sub-tab is a horizontal pill selector within the SEO & GEO tab:

```
[Rankings] [Audit] [Competitors] [Backlinks] [GEO]
```

The existing SEO checklist moves under the **Audit** sub-tab alongside the automated audit results.

---

## VA Workflow Design

Every feature is designed for a non-technical VA:

1. **Daily routine**: Open dashboard → check alerts (new competitor activity, lost backlinks, rank drops) → take action on flagged items
2. **Weekly routine**: Review keyword ranks → approve/reject content topics → check audit issues
3. **Monthly routine**: Run competitor analysis → review backlink growth → run site audit

**VA action buttons are always**:
- Clear single-word verbs: "Add", "Approve", "Reject", "Fix", "Ignore", "Pull", "Run"
- Include confirmation modals for destructive actions
- Show inline help text explaining what each action does
- Use color: green = good/action, yellow = needs attention, red = problem

**Alerts integration**:
- Rank drop >5 positions for tracked keyword → alert
- Lost backlink from domain with >50 DA → alert
- Competitor gained >10 reviews → alert (already exists)
- Audit score dropped >10 points → alert
- New keyword gap discovered → info notification

---

## Implementation Priority

| Phase | Features | Effort | Dependencies |
|-------|----------|--------|-------------|
| **Phase 1** | Keyword Rank Tracking + Auto-generate | 1-2 days | GSC access for at least 1 customer |
| **Phase 2** | Enhanced Site Audits | 1 day | None (PageSpeed API is free/keyless) |
| **Phase 3** | Content Topic Suggestions | 1 day | Phase 1 (uses keyword data) |
| **Phase 4** | Competitor Keyword Analysis | 1 day | Existing competitor data |
| **Phase 5** | Backlink Monitoring | 0.5 days | GSC access |

**Phase 1 is the highest value**: keyword rank tracking is the #1 thing clients ask about and the #1 reason agencies buy Semrush.

---

## Cost Analysis

| Capability | Semrush Cost | PracticeRank Cost |
|-----------|-------------|-------------------|
| Keyword Rank Tracking | Included in $140/mo | Free (GSC API) |
| Site Audits | Included | Free (PageSpeed Insights API) |
| Competitor Keywords | Included | Free (sitemap scraping + autocomplete) |
| Backlinks | Included | Free (GSC Links API) |
| Content Topics | Included | ~$0.50/customer/mo (Claude API for suggestions) |
| AI Mentions | Not available | Already built (~$3.73/mo) |
| GEO / llms.txt | Not available | Already built |
| **Total** | **$140/month** | **~$5/month** |

---

## Files to Create/Modify

### New files:
- `geo_agent/site_auditor.py` — PageSpeed + custom checks
- `scripts/scheduled_keyword_pull.py` — weekly GSC keyword pull cron
- `scripts/scheduled_site_audit.py` — monthly automated audits

### Modify:
- `geo_agent/db.py` — new tables (keyword_tracking, keyword_ranks, site_audits, audit_issues, backlinks, competitor_keywords, content_topics), new methods
- `geo_agent/gsc_client.py` — add `fetch_backlinks()`, add keyword-dimension query support
- `geo_agent/competitive_intel.py` — add `discover_competitor_topics()`, `find_keyword_gaps()`, `get_autocomplete_suggestions()`
- `dashboard/app.py` — ~15 new API endpoints, updated customer detail route to pass new data
- `dashboard/templates/customer_detail.html` — sub-tabs in SEO & GEO, new sections for each feature
- `dashboard/templates/base.html` — CSS for sub-tabs, sparklines, new badge styles

### Cron jobs (add to container):
- `scripts/scheduled_keyword_pull.py` — weekly Sunday 10pm ET
- `scripts/scheduled_site_audit.py` — monthly 1st of month, 2am ET
- `scripts/scheduled_ai_check.py` — Mon/Wed/Fri 6am ET (already planned)

---

## Status

- [ ] Phase 1: Keyword Rank Tracking
  - [ ] DB schema + methods
  - [ ] Auto-generate keywords logic
  - [ ] Scheduled GSC pull script
  - [ ] API endpoints
  - [ ] UI: Rankings sub-tab
- [ ] Phase 2: Enhanced Site Audits
  - [ ] `site_auditor.py` module
  - [ ] DB schema + methods
  - [ ] API endpoints
  - [ ] UI: Audit sub-tab with issue cards
- [ ] Phase 3: Content Topic Suggestions
  - [ ] DB schema + methods
  - [ ] Topic suggestion engine
  - [ ] Integration with content recommender
  - [ ] UI: Topic Ideas section in Content tab
- [ ] Phase 4: Competitor Keyword Analysis
  - [ ] Sitemap scraper + autocomplete
  - [ ] Keyword gap analysis
  - [ ] DB schema + methods
  - [ ] UI: Competitors sub-tab
- [ ] Phase 5: Backlink Monitoring
  - [ ] GSC Links API integration
  - [ ] DB schema + methods
  - [ ] UI: Backlinks sub-tab
- [ ] SEO & GEO tab restructure (sub-tabs)
- [ ] Alert integration for all new features
- [ ] VA workflow documentation
