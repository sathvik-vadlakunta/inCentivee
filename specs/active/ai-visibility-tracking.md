# AI Visibility Tracking — Trend Analysis & Competitive Benchmarking

## Problem

We run AI mention checks but the data is snapshot-only — there's no easy way to see "are we getting better?" over time. Customers ask "is it working?" and we can't show a trend line. Additionally, we don't benchmark against competitors in AI search.

## What Industry Leaders Do

- **HubSpot AEO**: Week-over-week visibility tracking across ChatGPT, Perplexity, Gemini with trend graphs. Share of voice metric shows brand vs competitors in same category.
- **Conductor**: Tracks citation rate (avg 1.08% of traffic from AI), platform breakdown, content format citation rates (guides/FAQs = 54-67%, opinion = 18%).
- **Key stat**: 37% of product discovery queries now start in AI interfaces (Microsoft, Jan 2026).

## Feature 1: AI Visibility Trend Dashboard

### Current State
- `ai_mention_runs` stores one row per check run with overall mention_rate
- `ai_mention_results` stores per-engine, per-prompt results
- Data exists but is only shown as latest snapshot on AI Mentions tab

### Target State
A dedicated trend section showing:

**Overall Trend Line:**
- X axis: run dates
- Y axis: mention rate (0-100%)
- Line for overall + optional per-engine overlay

**Per-Engine Breakdown:**
- Stacked bar or grouped bar showing mention count per engine per run
- Engines: ChatGPT, Claude, Perplexity, Google AI Overviews, Gemini
- Shows which engines are picking you up vs ignoring you

**Category Heatmap:**
- Rows: prompt categories (general, services, location, comparison, emergency)
- Columns: run dates
- Color: mention rate for that category on that run date
- Quickly shows "we're strong on general queries but weak on emergency queries"

### Data Already Available
All of this can be computed from existing `ai_mention_runs` and `ai_mention_results` tables. No new data collection needed — just new aggregation queries and UI.

### New Queries Needed

```python
def get_ai_trend(customer_id, limit=20):
    """Return mention runs with per-engine breakdown for trend chart."""
    # Returns: [{run_date, mention_rate, total_mentions, total_queries,
    #            engines: {chatgpt: {mentions, queries, rate}, ...}}]

def get_ai_category_trend(customer_id, limit=10):
    """Return mention rate by prompt_category per run for heatmap."""
    # Returns: [{run_date, categories: {general: 0.6, services: 0.3, ...}}]
```

## Feature 2: Competitor AI Benchmarking

### Concept
When we run AI mention checks for a customer, also check if competitors are mentioned in the same responses.

### Implementation

**Option A — Parse existing responses (low effort):**
We already store `full_response` in `ai_mention_results`. Post-process these to check if competitor names/domains appear. This is free — no extra API calls.

```python
def extract_competitor_mentions(response_text, competitor_names):
    """Check if any competitor name appears in an AI response."""
    mentions = []
    for name in competitor_names:
        if name.lower() in response_text.lower():
            mentions.append(name)
    return mentions
```

**Option B — Dedicated competitor runs (higher effort):**
Run the same prompts but look for all businesses, not just ours. More accurate but doubles API cost.

**Recommendation:** Start with Option A. It's free and gives us 80% of the value.

### New Table

```sql
CREATE TABLE IF NOT EXISTS ai_competitor_mentions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    result_id INTEGER NOT NULL,           -- links to ai_mention_results
    customer_id TEXT NOT NULL,
    competitor_name TEXT NOT NULL,
    competitor_domain TEXT,
    engine TEXT NOT NULL,
    prompt TEXT NOT NULL,
    run_date TEXT NOT NULL,
    mentioned INTEGER DEFAULT 0,          -- 1 if competitor appeared in response
    position INTEGER,                     -- where in the response
    FOREIGN KEY (result_id) REFERENCES ai_mention_results(id)
);
```

### Competitive Share of Voice Chart

```
+--------------------------------------------------+
| AI Share of Voice — Sojo Dental vs Competitors    |
|                                                   |
|  Sojo Dental        ████████░░░░  40%             |
|  Valley Dental      ██████░░░░░░  30%             |
|  Bright Smiles      ████░░░░░░░░  20%             |
|  Summit Dental      ██░░░░░░░░░░  10%             |
|                                                   |
|  Based on 20 AI search queries across 4 engines   |
+--------------------------------------------------+
```

Shows relative visibility — "you're mentioned in 40% of queries, your top competitor in 30%."

## Feature 3: AI Visibility Alerts

Trigger alerts when:
- Mention rate drops > 10% between consecutive runs
- A competitor overtakes the customer in mention rate
- Customer achieves a new milestone (first mention on a new engine, 50%+ rate)
- Customer loses mentions on an engine they previously appeared on

These feed into the existing `alerts` table and show on the dashboard.

## Feature 4: Engine-Specific Recommendations

Based on per-engine data, generate specific recommendations:

| Pattern | Recommendation |
|---------|---------------|
| Mentioned on ChatGPT but not Claude | "Add structured data — Claude weighs schema heavily" |
| Mentioned on Claude but not ChatGPT | "Improve citations/sources — ChatGPT prefers well-sourced content" |
| Not on Perplexity | "Get listed in directories — Perplexity relies on web citations" |
| Not on Google AI | "Optimize for Google's Knowledge Graph — ensure GBP is complete" |
| Low position when mentioned | "Add more specific service pages — AI engines rank detailed content higher" |

These feed into the Quick Wins system.

## Files to Create/Modify

| File | Action |
|------|--------|
| `geo_agent/db.py` | Add `ai_competitor_mentions` table, trend query methods |
| `geo_agent/ai_mention_checker.py` | Add competitor extraction from existing responses |
| `dashboard/app.py` | Add `/api/ai-trend/<cid>` endpoint, update AI Mentions tab |
| `dashboard/templates/customer_detail.html` | Add trend chart + competitive share of voice to AI Mentions tab |

## Data Flow

```
ai_mention_checker runs
    → saves to ai_mention_runs + ai_mention_results (existing)
    → post-process: extract competitor mentions from full_response (new)
    → saves to ai_competitor_mentions (new)
    → daily_score.py computes AI Visibility pillar score (new)
    → practicerank_scores updated (new)
    → quick_wins engine checks for AI-specific opportunities (new)
```
