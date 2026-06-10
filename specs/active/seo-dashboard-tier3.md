# Tier 3: Content Intelligence & AI Readiness

## Goal
Automate content strategy with AI-powered topic discovery, content scoring, and publishing pipeline. Make PracticeRank the content engine — not just the analytics dashboard.

---

## 1. Content Scoring Engine

### Per-Page Content Score (0-100)
Analyze each page on the customer's website and score it:

```
| Page                        | Score | Word Count | Readability | Keywords | Schema | Actions     |
|-----------------------------|-------|------------|-------------|----------|--------|-------------|
| /dental-implants            | 82    | 1,450      | Grade 8     | 4 found  | Yes    | Add FAQ     |
| /teeth-whitening            | 45    | 320        | Grade 12    | 1 found  | No     | Rewrite     |
| /about                      | 61    | 680        | Grade 9     | 0 found  | No     | Add schema  |
| /contact                    | 38    | 120        | --          | 0 found  | No     | Add NAP     |
```

### Scoring Formula
```python
def score_page(page_html, target_keywords):
    word_count = len(page_html.split())

    # Length (20%) — ideal 800-2000 words for service pages
    length_score = min(100, word_count / 10) if word_count < 1000 else 100
    if word_count > 2500: length_score = 80  # slight penalty for too long

    # Readability (20%) — Flesch-Kincaid, target grade 6-8
    grade = flesch_kincaid_grade(page_html)
    read_score = 100 if 6 <= grade <= 8 else max(0, 100 - abs(grade - 7) * 15)

    # Keyword usage (20%) — target keywords in title, H1, first paragraph, body
    kw_score = keyword_presence_score(page_html, target_keywords)

    # Structure (20%) — H2/H3 headers, lists, images with alt text
    struct_score = structure_score(page_html)

    # Schema & meta (20%) — has schema, meta desc, OG tags
    meta_score = meta_completeness_score(page_html)

    return round(length_score * 0.2 + read_score * 0.2 + kw_score * 0.2 +
                 struct_score * 0.2 + meta_score * 0.2)
```

### Implementation
- Crawl customer site pages (up to 50 pages)
- Score each page and store results
- Run monthly or on-demand
- New table: `page_scores` (customer_id, page_url, score, breakdown_json, date)

---

## 2. Topic Cluster Engine

### What It Does
Group related keywords into topic clusters and identify content gaps.

```
Topic Cluster: "Dental Implants"
├── Pillar: /dental-implants (exists, score: 82)
├── Supporting:
│   ├── /dental-implant-cost → "dental implant cost [city]" (exists, score: 45)
│   ├── /implant-vs-bridge → "dental implant vs bridge" (MISSING - create)
│   ├── /implant-recovery → "dental implant recovery time" (MISSING - create)
│   └── /all-on-4 → "all on 4 dental implants" (MISSING - create)
└── Related queries from GSC:
    ├── "how long do dental implants last" (890 imp, pos 28)
    └── "dental implant pain" (450 imp, pos 35)
```

### Auto-Cluster Logic
```python
def build_clusters(keywords, existing_pages):
    # Group keywords by semantic similarity (using embeddings or simple string matching)
    clusters = {}

    # Service-based grouping for dental:
    service_groups = {
        "implants": ["implant", "all-on-4", "implant cost", "implant recovery"],
        "whitening": ["whitening", "bleaching", "teeth white"],
        "orthodontics": ["braces", "invisalign", "alignment", "orthodont"],
        "emergency": ["emergency", "urgent", "toothache", "broken tooth"],
        "cosmetic": ["veneer", "cosmetic", "smile makeover", "bonding"],
    }

    for keyword in keywords:
        for group_name, patterns in service_groups.items():
            if any(p in keyword.lower() for p in patterns):
                clusters.setdefault(group_name, []).append(keyword)
                break

    return clusters
```

### Implementation
- Use keyword data from GSC + tracked keywords
- Match against existing site pages
- Identify missing content (keywords with no matching page)
- Generate content briefs for missing topics

---

## 3. Content Calendar & Pipeline

### Content Recommendation Flow
```
Discovery → Brief → Draft → Review → Approved → Published
```

### Auto-Generated Content Briefs
When a content gap is identified, auto-generate a brief:

```
Content Brief: "Dental Implant Recovery Time"
─────────────────────────────────────────────
Target keyword: dental implant recovery time
Secondary keywords: implant healing, post-implant care
Search volume: ~450/mo
Current ranking: Not ranking
Competitor coverage: 3 of 5 competitors have this page
Recommended word count: 1,200-1,500
Recommended structure:
  H1: Dental Implant Recovery: What to Expect
  H2: Timeline Overview
  H2: Day-by-Day Recovery Guide
  H2: Tips for Faster Healing
  H2: When to Call Your Dentist
  H2: FAQ
Schema: FAQPage + MedicalWebPage
Internal links: → /dental-implants, → /about
```

### Content Calendar View
```
| Week      | Topic                        | Status    | Type     | Writer   |
|-----------|------------------------------|-----------|----------|----------|
| Jun 2-8   | Dental Implant Recovery      | Draft     | Blog     | AI       |
| Jun 9-15  | Emergency Dental Guide       | Brief     | Page     | AI       |
| Jun 16-22 | Teeth Whitening Options       | Planned   | Blog     | AI       |
| Jun 23-29 | Insurance & Payment FAQ       | Planned   | Page     | AI       |
```

### Implementation
- Extend existing `content_recommendations` table with calendar fields
- Add `scheduled_date`, `content_type`, `word_count_target`, `brief_json`
- Auto-generate briefs using Claude API
- Calendar view in dashboard

---

## 4. AI Readiness Score

### What It Does
Score how well the practice's website is optimized for AI search engines (ChatGPT, Claude, Perplexity, Google AI Overviews).

### AI Readiness Checklist (0-100)
```
| Check                           | Weight | Status | Score |
|---------------------------------|--------|--------|-------|
| llms.txt present & valid        | 15%    | Yes    | 15    |
| FAQ schema with clear answers   | 15%    | No     | 0     |
| LocalBusiness schema complete   | 10%    | Yes    | 10    |
| Content is factual & cited      | 10%    | Partial| 5     |
| Clear entity definitions        | 10%    | Yes    | 10    |
| Structured service descriptions | 10%    | No     | 0     |
| Review schema present           | 10%    | Yes    | 10    |
| Mobile-friendly content         | 5%     | Yes    | 5     |
| Fast load time (<3s)            | 5%     | Yes    | 5     |
| Regular content updates         | 10%    | No     | 0     |
|                                 |        | Total: | 60/100|
```

### AI Mention Correlation
Cross-reference AI readiness score with actual AI mention data from AEO tab:
- Plot AI readiness score vs mention rate over time
- Identify which improvements correlated with more mentions
- Show "AI readiness improved 20 points → mentions up 15%"

### Implementation
- Extend site auditor with AI-specific checks
- Store in `ai_readiness_scores` table
- Compare against AI mention data from existing system

---

## 5. Competitor Content Analysis

### What It Does
Analyze competitor content strategy:

```
Competitor: Valley Family Dental
─────────────────────────────────
Blog frequency: 2 posts/month
Avg word count: 1,100
Top content:
  1. "Complete Guide to Dental Implants" (est. 450 visits/mo)
  2. "Emergency Dental Care" (est. 320 visits/mo)
  3. "Teeth Whitening Options" (est. 280 visits/mo)
Topics they cover that you don't:
  - Pediatric dentistry guide
  - Dental anxiety management
  - Insurance accepted list page
```

### Implementation
- Crawl competitor sites (homepage + sitemap)
- Analyze page titles, word counts, topic coverage
- Compare against customer's content
- Run monthly

---

## DB Schema

```sql
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

CREATE TABLE IF NOT EXISTS topic_clusters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL,
    cluster_name TEXT NOT NULL,
    pillar_page_url TEXT,
    keywords_json TEXT NOT NULL DEFAULT '[]',
    gap_pages_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(customer_id, cluster_name)
);

CREATE TABLE IF NOT EXISTS content_briefs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL,
    title TEXT NOT NULL,
    target_keyword TEXT NOT NULL,
    secondary_keywords_json TEXT DEFAULT '[]',
    recommended_structure_json TEXT DEFAULT '{}',
    word_count_target INTEGER DEFAULT 1200,
    status TEXT NOT NULL DEFAULT 'draft',
    scheduled_date TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ai_readiness_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL,
    date TEXT NOT NULL,
    score INTEGER NOT NULL DEFAULT 0,
    breakdown_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE(customer_id, date)
);
```

## Implementation Order

1. Content scoring engine (crawl + score pages)
2. AI readiness score (extend site auditor)
3. Topic cluster builder
4. Content brief generator (Claude API)
5. Content calendar view
6. Competitor content analysis

## Verification

- [ ] Page scores calculated for all crawled pages
- [ ] Topic clusters group related keywords correctly
- [ ] Content briefs auto-generated for gap topics
- [ ] AI readiness score correlates with actual mention data
- [ ] Content calendar shows pipeline status
