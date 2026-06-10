# PracticeRank Score (0-100) — Composite Visibility & Growth Score

## Problem

We have no single metric that tells a customer (or us) "how are you doing?" at a glance. Data is scattered across AI mentions, GSC clicks, reviews, content, and site health — but nothing rolls it up into one number we can track over time and compare across customers.

Industry leaders are doing this:
- **HubSpot AEO Grader** scores brands 0-100 across 5 dimensions: sentiment, presence quality, brand recognition, share of voice, market position
- **Conductor** tracks citation rate (1.08% avg), AI shelf share, and brand mention frequency across 17M AI responses
- **BrightLocal** uses a Local Search Grid for visual ranking proof
- **Semrush** uses Site Health Score based on error ratio

Our score needs to be **simple enough to explain in 10 seconds** and **actionable enough to drive next steps**.

## Score Formula

**PracticeRank Score = weighted sum of 5 pillars, each scored 0-100**

| Pillar | Weight | What it measures | Data source |
|--------|--------|-----------------|-------------|
| AI Visibility | 30% | Are AI engines recommending you? | `ai_mention_runs`, `ai_mention_results` |
| Search Growth | 25% | Are organic clicks growing? | `gsc_daily_metrics`, `keyword_ranks` |
| Technical Health | 15% | Is your site technically sound? | `site_audits`, `audit_issues` |
| Content Velocity | 15% | Are you publishing optimized content? | `content_recommendations`, `page_scores` |
| Reputation | 15% | Reviews, ratings, competitive position | `google_places`, `reviews`, `competitor_domains` |

### Pillar 1: AI Visibility (30%)

This is our differentiator — no one else in the SMB space tracks this well.

```
ai_visibility_score = weighted_avg(
    mention_rate_score,      # 50% — % of AI queries that mention the business
    position_quality_score,  # 25% — avg ranking position in AI responses (1st vs 5th)
    engine_breadth_score,    # 15% — mentioned across multiple engines vs just one
    trend_score,             # 10% — improving, stable, or declining over last 4 runs
)
```

**Mention Rate Score (0-100):**
| Mention Rate | Score |
|-------------|-------|
| >= 50% | 100 |
| 40-50% | 85-100 |
| 25-40% | 60-85 |
| 10-25% | 30-60 |
| 1-10% | 10-30 |
| 0% | 0 |

**Position Quality Score (0-100):**
- Position 1 (first recommendation) = 100
- Position 2 = 80
- Position 3 = 60
- Position 4-5 = 40
- Position 6+ = 20
- Not mentioned = 0
- Average across all mentioned queries

**Engine Breadth Score (0-100):**
- Mentioned in 4+ engines = 100
- 3 engines = 75
- 2 engines = 50
- 1 engine = 25
- 0 engines = 0

**Trend Score (0-100):**
- Compare current 4-run avg mention rate vs previous 4-run avg
- Improving by 10%+ = 100
- Improving by 1-10% = 70
- Stable (within 1%) = 50
- Declining by 1-10% = 30
- Declining by 10%+ = 10
- Not enough data = 50 (neutral)

### Pillar 2: Search Growth (25%)

```
search_growth_score = weighted_avg(
    click_growth_score,       # 40% — MoM click growth
    impression_growth_score,  # 20% — MoM impression growth
    position_improvement,     # 25% — avg position trending down (better)
    keyword_momentum,         # 15% — # of keywords improving vs declining
)
```

**Click Growth Score (0-100):**
| MoM Change | Score |
|-----------|-------|
| >= +30% | 100 |
| +15 to +30% | 80-100 |
| +5 to +15% | 60-80 |
| 0 to +5% | 50-60 |
| -10 to 0% | 30-50 |
| -30 to -10% | 10-30 |
| < -30% | 0-10 |

**Keyword Momentum (0-100):**
- Count keywords that improved position vs declined (from `keyword_ranks` comparing last 2 weeks)
- If 70%+ improved → 100
- If 50-70% improved → 60-80
- If 30-50% improved → 40-60
- If < 30% improved → 0-40

### Pillar 3: Technical Health (15%)

```
technical_score = weighted_avg(
    lighthouse_seo,          # 30% — from site_audits.seo_score
    lighthouse_performance,  # 20% — from site_audits.performance_score
    issues_ratio,            # 30% — (total - open) / total issues
    schema_completeness,     # 20% — required schema types present
)
```

**Schema Completeness (0-100):**
- LocalBusiness/Organization present = 25 pts
- FAQPage on at least 1 page = 25 pts
- AggregateRating present = 25 pts
- llms.txt exists and > 500 bytes = 25 pts

### Pillar 4: Content Velocity (15%)

```
content_score = weighted_avg(
    publish_recency,        # 40% — days since last content published
    pending_ratio,          # 30% — % of approved recs that are published
    content_quality,        # 30% — avg page_scores for published content
)
```

**Publish Recency (0-100):**
| Days since last publish | Score |
|------------------------|-------|
| 0-7 days | 100 |
| 8-14 days | 80 |
| 15-30 days | 60 |
| 31-60 days | 30 |
| 60+ days | 10 |
| Never published | 0 |

**Pending Ratio (0-100):**
- All approved content published = 100
- 50%+ published = 60
- < 50% published = 30
- No content recs yet = 50 (neutral)

### Pillar 5: Reputation (15%)

```
reputation_score = weighted_avg(
    rating_score,             # 40% — Google rating relative to 4.5 benchmark
    review_volume_score,      # 30% — review count vs local competitor avg
    review_growth_score,      # 20% — new reviews in last 30 days
    sentiment_score,          # 10% — % of reviews with positive sentiment
)
```

**Rating Score (0-100):**
| Rating | Score |
|--------|-------|
| >= 4.8 | 100 |
| 4.5-4.7 | 80-95 |
| 4.0-4.4 | 50-75 |
| 3.5-3.9 | 25-45 |
| < 3.5 | 0-20 |
| No rating | 0 |

**Review Volume Score (0-100):**
- Compare to avg of tracked competitors
- >= 1.5x competitor avg = 100
- At competitor avg = 50
- Below competitor avg = 0-50 (prorated)
- No competitors tracked = use absolute: 100+ reviews = 80, 50+ = 60, 10+ = 40, < 10 = 20

## Score History

Store computed scores for historical tracking:

```sql
CREATE TABLE IF NOT EXISTS practicerank_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id TEXT NOT NULL,
    date TEXT NOT NULL,
    overall_score INTEGER NOT NULL,       -- 0-100
    ai_visibility INTEGER NOT NULL,       -- 0-100
    search_growth INTEGER NOT NULL,       -- 0-100
    technical_health INTEGER NOT NULL,    -- 0-100
    content_velocity INTEGER NOT NULL,    -- 0-100
    reputation INTEGER NOT NULL,          -- 0-100
    breakdown_json TEXT,                  -- detailed sub-scores for drill-down
    FOREIGN KEY (customer_id) REFERENCES customers(id),
    UNIQUE(customer_id, date)
);
```

- Computed **daily** via cron (after GSC pull completes)
- Kept indefinitely for trend charts
- `breakdown_json` stores all sub-component scores for debugging/drill-down

## Score Grades

For display purposes:

| Score | Grade | Color | Label |
|-------|-------|-------|-------|
| 90-100 | A | #16a34a (green) | Excellent |
| 75-89 | B | #65a30d (lime) | Strong |
| 60-74 | C | #d97706 (amber) | Good |
| 40-59 | D | #ea580c (orange) | Needs Work |
| 0-39 | F | #dc2626 (red) | Critical |

## Missing Data Handling

When data is unavailable, redistribute weight to available pillars:
- No AI mention runs yet → redistribute 30% across other 4 pillars
- No GSC data → redistribute 25% across other pillars
- No site audit → redistribute 15%
- etc.

Minimum: at least 2 pillars must have data, otherwise show "Insufficient Data" instead of a score.

## Files to Create/Modify

| File | Action |
|------|--------|
| `geo_agent/practicerank_score.py` | **NEW** — Score computation engine |
| `geo_agent/db.py` | Add `practicerank_scores` table, `save_score()`, `get_score_history()` |
| `scripts/daily_score.py` | **NEW** — Daily cron job to compute scores for all customers |
| `dashboard/app.py` | Add score to overview, analytics, customer detail routes |

## Verification

1. Run score computation for existing customers → check scores are reasonable
2. Sojo Dental (limited data) should score 30-50 range
3. SmileShape (more data) should score higher if more signals populated
4. Score should be 0 if no data at all → "Insufficient Data" shown
5. Historical scores accumulate daily and trend chart renders correctly
