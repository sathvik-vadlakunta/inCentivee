# Tier 2: Competitive Intelligence & Local SEO

## Goal
Add competitor tracking, local pack monitoring, and review velocity analysis. Give dental practices visibility into how they stack up against nearby competitors — data that Semrush charges $140/mo for.

---

## 1. Competitor Discovery & Tracking

### Auto-Discovery
When a customer is added, automatically find competitors:
- GSC API: queries that show competitor domains in search results
- Google Maps API: search "dentist near [city]" and grab top 10 results
- Manual add: VA can add competitor domains directly

### Competitor Table
```
| Competitor           | Domain                    | Est. Traffic | Keywords | Overlap |
|----------------------|---------------------------|-------------|----------|---------|
| Smile Dental         | smiledental.com           | ~2,400/mo   | 145      | 34%     |
| Valley Family Dental | valleyfamilydental.com    | ~1,800/mo   | 98       | 28%     |
| Bright Smiles        | brightsmilesdentist.com   | ~900/mo     | 67       | 41%     |
```

### Keyword Gap Analysis
Compare customer's keyword rankings against competitors:
```
Keywords THEY rank for that YOU don't:
| Keyword                  | Competitor Pos | Your Pos | Monthly Vol |
|--------------------------|---------------|----------|-------------|
| emergency dentist [city] | 3             | --       | 720         |
| dental implants [city]   | 5             | --       | 480         |
| teeth whitening near me  | 7             | 42       | 390         |
```

### Implementation
- New table: `competitors` (customer_id, competitor_domain, name, discovered_via)
- New table: `competitor_keywords` (competitor_id, keyword, position, date)
- Monthly cron: run competitor keyword scrape via GSC shared queries
- Compare keyword sets to find gaps

---

## 2. Local Pack Tracking

### What It Does
Track whether the practice appears in Google's Local 3-Pack for key queries.

### Tracked Queries
Auto-generate from business type + location:
- "[business_type] [city]"
- "[business_type] near me"
- "[specialty] [city]" (for each service offered)
- "best [business_type] [city]"
- "emergency [business_type] [city]"

### Local Pack Results Table
```
| Query                    | In Pack? | Position | Rating | Reviews | Competitor 1    | Competitor 2    |
|--------------------------|----------|----------|--------|---------|-----------------|-----------------|
| dentist farmington ut    | Yes      | 2        | 4.8    | 127     | Valley Dental   | Bright Smiles   |
| emergency dentist utah   | No       | --       | --     | --      | Urgent Dental   | 24Hr Smile      |
| dental implants farm..   | Yes      | 3        | 4.8    | 127     | Implant Center  | Valley Dental   |
```

### Implementation
- Use Google Custom Search JSON API (100 free queries/day) or SerpAPI
- Store results in `local_pack_results` table
- Run weekly on Monday cron
- Track position changes over time

---

## 3. Google Business Profile Completeness

### GBP Audit Checklist
Score the practice's GBP listing completeness (0-100):

| Field              | Weight | Check                                    |
|--------------------|--------|------------------------------------------|
| Business name      | 5%     | Matches website                          |
| Address            | 10%    | Complete, matches NAP                    |
| Phone              | 10%    | Matches website                          |
| Hours              | 10%    | Set, including special hours             |
| Website URL        | 5%     | Points to correct domain                 |
| Categories         | 10%    | Primary + 2+ secondary categories        |
| Description        | 10%    | 250+ characters, includes keywords       |
| Photos             | 10%    | 10+ photos, updated in last 90 days      |
| Posts               | 10%    | Posted in last 14 days                   |
| Q&A                | 5%     | 5+ answered questions                    |
| Reviews            | 10%    | 20+ reviews, avg 4.0+                    |
| Services/Products  | 5%     | Listed with descriptions                 |

### Implementation
- Manual data entry by VA initially (GBP API is restricted)
- Store in `gbp_audit` table
- Show score on Overview dashboard
- Alert when score drops below 70

---

## 4. Review Velocity & Sentiment

### Review Dashboard
```
+------------------------------------------+
| Reviews Summary                          |
| Total: 127 | Avg: 4.8 | This Month: 8  |
| Velocity: 2.1/week (▲ from 1.5/week)   |
+------------------------------------------+
| Rating Distribution                      |
| 5★ ████████████████████ 89 (70%)        |
| 4★ ██████ 24 (19%)                      |
| 3★ ██ 8 (6%)                            |
| 2★ █ 4 (3%)                             |
| 1★ █ 2 (2%)                             |
+------------------------------------------+
| Recent Reviews (last 30 days)            |
| ★★★★★ "Dr. Smith was amazing..." - 2d  |
| ★★★★☆ "Good experience but..." - 5d    |
+------------------------------------------+
```

### Review Velocity Tracking
- Track reviews per week/month over time
- Compare against competitors' review velocity
- Alert when velocity drops below threshold
- Show trend chart (reviews per week, 12-week view)

### Sentiment Analysis
- Use Claude API to categorize reviews: positive, neutral, negative
- Extract common themes: "wait time", "friendly staff", "clean office"
- Flag negative reviews for immediate response

### Implementation
- Pull from Google Places API (or manual CSV import)
- New table: `reviews` (customer_id, source, rating, text, date, sentiment, themes_json)
- New table: `review_velocity` (customer_id, week_start, count, avg_rating)
- Weekly cron to pull new reviews

---

## 5. Citation Tracking

### What It Does
Track business listings across key directories:

| Directory        | Listed? | NAP Match | URL      | Last Checked |
|------------------|---------|-----------|----------|-------------|
| Google Business  | Yes     | Match     | Correct  | May 26      |
| Yelp             | Yes     | Mismatch  | Missing  | May 26      |
| Healthgrades     | Yes     | Match     | Correct  | May 26      |
| Zocdoc           | No      | --        | --       | May 26      |
| Facebook         | Yes     | Match     | Outdated | May 26      |

### NAP Consistency Score
Check Name, Address, Phone consistency across all listings.
Score = % of listings with matching NAP.

### Implementation
- Manual tracking initially (VA enters citation data)
- New table: `citations` (customer_id, directory, listed, nap_match, url_correct, last_checked)
- Future: automated scraping of directory pages

---

## DB Schema

```sql
CREATE TABLE IF NOT EXISTS competitors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL,
    competitor_domain TEXT NOT NULL,
    competitor_name TEXT,
    discovered_via TEXT DEFAULT 'manual',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(customer_id, competitor_domain)
);

CREATE TABLE IF NOT EXISTS competitor_keywords (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    competitor_id INTEGER NOT NULL,
    keyword TEXT NOT NULL,
    position REAL,
    date TEXT NOT NULL,
    FOREIGN KEY (competitor_id) REFERENCES competitors(id)
);

CREATE TABLE IF NOT EXISTS local_pack_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL,
    query TEXT NOT NULL,
    date TEXT NOT NULL,
    in_pack INTEGER NOT NULL DEFAULT 0,
    pack_position INTEGER,
    competitors_json TEXT DEFAULT '[]',
    UNIQUE(customer_id, query, date)
);

CREATE TABLE IF NOT EXISTS gbp_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL,
    date TEXT NOT NULL,
    score INTEGER NOT NULL DEFAULT 0,
    details_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE(customer_id, date)
);

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
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

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
```

## Implementation Order

1. Competitor table + manual add UI
2. Review dashboard with manual import
3. GBP completeness audit
4. Citation tracking (manual)
5. Local pack tracking (API)
6. Keyword gap analysis
7. Sentiment analysis (Claude API)
8. Automated competitor discovery

## Verification

- [ ] Can add/remove competitors for a customer
- [ ] Review dashboard shows rating distribution and velocity
- [ ] GBP audit generates completeness score
- [ ] Citations table tracks NAP consistency
- [ ] Local pack results show pack position for tracked queries
