# Tier 1: SEO Dashboard — Core Analytics & Ranking Intelligence

## Goal
Replace Semrush's core $140/mo value with free GSC + PageSpeed APIs. Build a dashboard that shows real search performance data, keyword trends over time, and actionable optimization opportunities — all within the existing SEO & GEO tab.

## New Sub-Tab Structure

```
Checklist | Overview | Rankings | Traffic | Audit | Backlinks | Integrations
```

**Overview** is new. Rankings and Traffic are split (currently combined). All tabs get date range filtering.

---

## 1. Global Date Range Filter

Every sub-tab respects a shared date range selector at the top of the SEO & GEO section.

- **Presets**: Last 7 days, Last 30 days, Last 90 days, Custom range
- **Default**: Last 30 days
- Stored in URL query param (`?range=30d`) so it persists on refresh
- Backend: GSC API accepts `startDate`/`endDate` — just pass through
- Date range applies to: Traffic charts, keyword positions, top pages, audit comparisons

### Implementation
- Add a date picker bar below the sub-tab row
- JS: `switchDateRange(days)` updates all data via AJAX calls
- Each API endpoint accepts `?start=YYYY-MM-DD&end=YYYY-MM-DD`
- Store daily GSC data in `gsc_daily_metrics` table for historical lookups without re-hitting API

---

## 2. Overview Sub-Tab (NEW)

A single-glance health dashboard. Think "Semrush Domain Overview" but focused on what matters.

### Layout
```
+--------------------------------------------------+
| Health Score [72/100]     Last updated: May 26    |
+--------------------------------------------------+
| [Clicks]  [Impressions]  [Avg Position]  [CTR]   |
| 350       25,890         17.4            1.4%    |
| +12% ▲    +8% ▲          -2.1 ▼ (better) +0.2%  |
+--------------------------------------------------+
| Clicks Trend (30d sparkline chart)                |
| ▁▂▃▅▂▃▄▅▆▃▄▅▆▇▅▆▅▄▅▆▇▅▆▇█▇▆▇█                  |
+--------------------------------------------------+
| Top 5 Keywords        | Top 5 Pages              |
| (mini table)          | (mini table)              |
+--------------------------------------------------+
| Alerts & Actions                                  |
| ⚠ robots.txt blocking | 🔍 3 CTR opportunities   |
| ⚠ No FAQ schema       | 📈 "dentist near me" ▲5  |
+--------------------------------------------------+
```

### Health Score Formula
```python
def compute_seo_health(customer_id):
    # PageSpeed scores (25%)
    audit = get_latest_audit(customer_id)
    psi = (audit.performance + audit.seo + audit.accessibility + audit.best_practices) / 4

    # Keyword coverage (25%) — what % of tracked keywords are in top 20
    keywords = get_keyword_summary(customer_id)
    in_top_20 = sum(1 for k in keywords if k.current_position and k.current_position <= 20)
    kw_pct = (in_top_20 / len(keywords) * 100) if keywords else 0

    # Traffic trend (25%) — week-over-week click growth
    # Positive growth = 100, flat = 50, declining = 0
    this_week_clicks = sum(last 7 days clicks)
    prev_week_clicks = sum(prior 7 days clicks)
    growth = ((this_week_clicks - prev_week_clicks) / prev_week_clicks) if prev_week_clicks else 0
    traffic_score = min(100, max(0, 50 + growth * 200))

    # Technical health (25%) — audit issues severity
    critical = count of critical issues
    warnings = count of warning issues
    tech_score = max(0, 100 - critical * 25 - warnings * 10)

    return round(psi * 0.25 + kw_pct * 0.25 + traffic_score * 0.25 + tech_score * 0.25)
```

### Metric Cards with Period Comparison
Each card shows:
- Current value
- Change vs previous period (same length)
- Color: green = improved, red = declined
- Arrow indicator

### Data Sources
- GSC API: clicks, impressions, position, CTR
- `gsc_daily_metrics` table: historical daily data
- `keyword_ranks` table: position history
- `site_audits` table: latest scores

---

## 3. Rankings Sub-Tab (Enhanced)

### Keyword Position History Sparklines
Each keyword row gets a tiny 60-day sparkline chart showing position trend.

```
| Keyword              | Position | 60d Trend      | Clicks | Impr  | CTR  |
|----------------------|----------|----------------|--------|-------|------|
| oakridge dental      | 4.0 🟢   | ▅▄▃▃▄▃▂▂▃▂    | 150    | 659   | 22.8%|
| dentist near me      | 19.6 🟡  | ▇▇▆▇▆▅▅▄▅▄    | 4      | 705   | 0.6% |
| dentist farmington   | 29.6 🔴  | ▅▅▆▇▇▆▆▇▆▇    | 6      | 116   | 5.2% |
```

Implementation:
- Store daily ranks in `keyword_ranks` (already doing this)
- Query last 60 days per keyword
- Render sparkline as inline SVG (no JS library needed)
- `<svg>` polyline with points calculated from position data (inverted — lower position = higher bar)

### CTR Opportunity Report
New section below keyword table:

```
📊 CTR Opportunities (high impressions, low CTR)
These keywords get lots of impressions but few clicks — improving titles/descriptions could win easy traffic.

| Keyword              | Position | Impressions | CTR   | Expected CTR | Gap    |
|----------------------|----------|-------------|-------|-------------|--------|
| dentist              | 13.5     | 221         | 0.5%  | 3.2%        | -2.7%  |
| dentist in farmington| 27.1     | 148         | 0.7%  | 1.5%        | -0.8%  |
```

Expected CTR curve (industry averages by position):
```python
EXPECTED_CTR = {1: 0.30, 2: 0.15, 3: 0.10, 4: 0.07, 5: 0.05,
                6: 0.04, 7: 0.03, 8: 0.025, 9: 0.02, 10: 0.018,
                11: 0.015, 12: 0.012, 13: 0.010, 14: 0.009, 15: 0.008,
                16: 0.007, 17: 0.006, 18: 0.005, 19: 0.004, 20: 0.003}
```
Flag any keyword where actual CTR < expected CTR * 0.5 (at least 50% below expected).

### Keyword Grouping by Intent
Group keywords into clusters:
- **Brand** (contains practice name)
- **Service** (contains service keywords like "implants", "whitening")
- **Location** (contains city/neighborhood names)
- **Informational** (contains "how", "what", "best", "cost")

Show group summary: "Brand: 5 keywords, avg pos 2.1 | Service: 12 keywords, avg pos 18.4"

### Sorting & Filtering
- Sort by any column (position, clicks, impressions, CTR, trend)
- Filter: All | Top 10 | Top 20 | Declining | Improving | Brand | Non-brand
- Search box to filter keywords by text

---

## 4. Traffic Sub-Tab (Split from Rankings)

### Daily Traffic Chart (Enhanced)
Replace the current bar chart with a proper line chart:
- **Dual axis**: clicks (blue line) + impressions (gray area)
- **Hover tooltips**: show exact date, clicks, impressions, CTR
- **Comparison overlay**: toggle to show previous period as dashed line
- Use `<canvas>` with Chart.js (lightweight, already a common pattern)

### Top Pages with Trends
Add a sparkline to each page row showing click trend over the selected period.

```
| Page                          | Clicks | Trend (30d) | Impr   | CTR  | Pos  |
|-------------------------------|--------|-------------|--------|------|------|
| / (homepage)                  | 164    | ▂▃▄▅▃▄▅▆   | 2,954  | 5.6% | 5.1  |
| /our-services/holistic-dent...| 18     | ▁▂▁▃▅▇▅▃   | 2,487  | 0.7% | 40.3 |
```

### Device Breakdown
GSC supports `device` dimension. Show pie chart: Mobile vs Desktop vs Tablet.

### Search Type Breakdown
GSC supports `searchType`: web, image, video. Show which types drive traffic.

### New vs Returning Pages
Compare top pages this period vs last period. Highlight:
- 🆕 Pages that entered top 10 this period
- 📈 Pages with biggest click increase
- 📉 Pages with biggest click decrease

---

## 5. Audit Sub-Tab (Enhanced)

### More Checks (target: 30+)
Add these to `site_auditor.py`:

**Performance:**
- [ ] Image optimization (WebP detection, lazy loading)
- [ ] Core Web Vitals from PageSpeed (LCP, FID, CLS with thresholds)
- [ ] Total page weight check (warn if > 3MB)
- [ ] Number of HTTP requests

**SEO:**
- [ ] Canonical URL present
- [ ] Open Graph tags present
- [ ] Twitter Card tags present
- [ ] H1 tag exists and is unique
- [ ] Title tag length (50-60 chars)
- [ ] Meta description length (150-160 chars)
- [ ] Internal linking analysis (orphan pages)
- [ ] Mobile viewport meta tag

**Security:**
- [ ] Mixed content check (HTTP resources on HTTPS page)
- [ ] Content-Security-Policy header
- [ ] X-Content-Type-Options header

**Local SEO:**
- [ ] NAP consistency (Name, Address, Phone on homepage)
- [ ] Google Maps embed present
- [ ] LocalBusiness schema completeness score
- [ ] City/service area pages exist

**AI Readiness (unique to us!):**
- [ ] llms.txt present and valid
- [ ] FAQ schema with AI-friendly answers
- [ ] Structured data completeness (% of recommended schemas present)
- [ ] Content readability score (AI engines prefer clear, factual content)

### Audit History
- Show previous audit scores alongside current
- Trend chart: health score over time (monthly)
- "Fixed since last audit" badge on resolved issues

### Per-Page Audit
When you click a page in Top Pages, show its individual audit:
- Title tag analysis
- Meta description analysis
- Heading structure (H1, H2, H3)
- Schema markup present
- Image alt text coverage
- Internal/external link count

---

## 6. Chart Bar Fix (Immediate)

The current bar chart is missing intermediate dates. Fix:
- Show date labels every 7th bar (weekly markers)
- Add hover tooltip showing date + clicks for each bar
- Even bar widths with no gaps for missing days

---

## DB Schema Additions

```sql
-- Store daily GSC data per page (for page-level trends)
CREATE TABLE IF NOT EXISTS gsc_page_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL,
    page_url TEXT NOT NULL,
    date TEXT NOT NULL,
    clicks INTEGER NOT NULL DEFAULT 0,
    impressions INTEGER NOT NULL DEFAULT 0,
    ctr REAL NOT NULL DEFAULT 0.0,
    position REAL NOT NULL DEFAULT 0.0,
    UNIQUE(customer_id, page_url, date)
);

-- Store device/search type breakdowns
CREATE TABLE IF NOT EXISTS gsc_dimensions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL,
    date TEXT NOT NULL,
    dimension_type TEXT NOT NULL,  -- 'device' or 'searchType'
    dimension_value TEXT NOT NULL, -- 'MOBILE', 'DESKTOP', 'TABLET' or 'web', 'image', 'video'
    clicks INTEGER NOT NULL DEFAULT 0,
    impressions INTEGER NOT NULL DEFAULT 0,
    UNIQUE(customer_id, date, dimension_type, dimension_value)
);

-- SEO health score history
CREATE TABLE IF NOT EXISTS seo_health_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL,
    date TEXT NOT NULL,
    score INTEGER NOT NULL,
    breakdown_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE(customer_id, date)
);
```

## Daily Cron Updates

Update `daily_gsc_pull.py` to also:
1. Pull page-level metrics (top 20 pages daily)
2. Pull device breakdown
3. Pull search type breakdown
4. Compute and store health score
5. Store keyword ranks with date for sparkline history

---

## Implementation Order

1. Fix bar chart dates + add tooltips (quick win)
2. Add date range filter (foundation for everything else)
3. Overview sub-tab with health score
4. Keyword sparklines in Rankings
5. CTR opportunity report
6. Enhanced traffic chart with Chart.js
7. Top pages with sparklines
8. Device/search type breakdown
9. Enhanced audit checks
10. Keyword grouping and filtering

## Verification

- [ ] Date range filter changes all data on all tabs
- [ ] Overview health score updates daily via cron
- [ ] Keyword sparklines show 60-day position history
- [ ] CTR opportunities highlight at least 3 keywords for Oakridge
- [ ] Traffic chart shows dual-axis with comparison toggle
- [ ] Audit runs 25+ checks and shows history
- [ ] All data persists in DB for historical trend viewing
