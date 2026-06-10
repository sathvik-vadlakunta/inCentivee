# AI Visibility v2 — Competitor Extraction + Weekly Analytics Overhaul

## Problems

### 1. No competitive intelligence from AI responses
We already store `full_response` (up to 2000 chars) for every AI engine query in `ai_mention_results`. When we ask "best dentist in Austin TX", the AI lists 5-8 businesses — we only check if OUR customer is in the list and throw away everything else. That's a goldmine of competitive data we're ignoring.

**What we should do:** Parse every `full_response` to extract ALL businesses mentioned. This gives us:
- Auto-discovered competitors (no manual entry needed)
- "Share of Voice" — what % of AI recommendations go to us vs each competitor
- Which competitors dominate which query categories
- Trend over time: are we gaining or losing ground vs specific competitors

### 2. Weekly averaging is invisible and confusing
The system runs benchmark checks 3x/week (Mon/Wed/Fri via `scheduled_ai_check.py`). `get_rolling_mention_stats()` averages over a 12-run window. But:

- **Runs page** shows a flat list of individual runs — no weekly grouping, no weekly average row
- **Dashboard** shows "rolling avg" but doesn't explain the window or what runs are included
- **Analytics page** shows a single "AI Mentions" number and a visibility bar — no trend, no week-over-week delta
- The user sees "32%" mention rate and has no idea if that's this week's average, last run's number, or a 12-run rolling average
- There's no "Week of May 19: 34% (+2%)" summary anywhere

---

## Feature 1: Competitor Extraction from AI Responses

### How It Works

After every AI mention check (or retroactively on existing data), parse `full_response` to find all business names mentioned.

**Extraction approach:**
1. Split response into numbered list items / bullet points / paragraphs
2. For each item, extract the business name (usually bold, first phrase, or after a number)
3. Normalize names (strip "Dr.", trailing punctuation, etc.)
4. Deduplicate across engines for the same prompt
5. Store each mention with position, engine, prompt, and run_date

**Why Option A (parse existing responses) is right:**
- Zero additional API cost — we already have the data
- Runs retroactively on all historical responses
- Gets us 80%+ accuracy for businesses in ranked lists
- Can improve extraction heuristics over time without re-running checks

### New Table: `ai_response_entities`

```sql
CREATE TABLE IF NOT EXISTS ai_response_entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    result_id INTEGER NOT NULL,
    run_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    entity_name TEXT NOT NULL,          -- "Valley Dental Care"
    entity_name_normalized TEXT NOT NULL, -- "valley dental care" (for dedup/matching)
    entity_type TEXT DEFAULT 'business', -- 'business', 'person', 'product'
    is_customer INTEGER DEFAULT 0,      -- 1 if this is our customer
    position INTEGER,                   -- where in the list (1st, 2nd, etc.)
    engine TEXT NOT NULL,
    prompt TEXT NOT NULL,
    prompt_category TEXT,
    run_date TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (result_id) REFERENCES ai_mention_results(id)
);

CREATE INDEX idx_entities_customer ON ai_response_entities(customer_id, run_date);
CREATE INDEX idx_entities_name ON ai_response_entities(entity_name_normalized, customer_id);
CREATE INDEX idx_entities_run ON ai_response_entities(run_id);
```

### Entity Extraction Function

```python
def extract_entities_from_response(response_text: str, customer_name: str) -> list[dict]:
    """Extract all business/practice names mentioned in an AI response.

    Returns list of {name, normalized_name, position, is_customer}.
    """
    import re
    entities = []
    seen = set()

    # Pattern 1: Numbered list "1. **Business Name** — description"
    numbered = re.findall(
        r'(\d+)[.)]\s*\*{0,2}\s*([A-Z][A-Za-z\s&\'\-\.]{2,40}?)\s*\*{0,2}\s*[-—:]',
        response_text
    )
    for num, name in numbered:
        name = name.strip().rstrip('.')
        norm = name.lower().strip()
        if norm not in seen and len(name) > 3:
            seen.add(norm)
            entities.append({
                "name": name,
                "normalized_name": norm,
                "position": int(num),
                "is_customer": _is_same_business(norm, customer_name),
            })

    # Pattern 2: Bold names "**Business Name**"
    bold = re.findall(r'\*\*([A-Z][A-Za-z\s&\'\-\.]{2,40}?)\*\*', response_text)
    pos = len(entities) + 1
    for name in bold:
        norm = name.lower().strip()
        if norm not in seen and len(name) > 3:
            seen.add(norm)
            entities.append({
                "name": name.strip(),
                "normalized_name": norm,
                "position": pos,
                "is_customer": _is_same_business(norm, customer_name),
            })
            pos += 1

    # Pattern 3: Bullet points "- Business Name: description"
    bullets = re.findall(
        r'[-*•]\s*([A-Z][A-Za-z\s&\'\-\.]{2,40}?)(?:\s*[-—:]|\s*\()',
        response_text
    )
    for name in bullets:
        norm = name.lower().strip()
        if norm not in seen and len(name) > 3:
            seen.add(norm)
            entities.append({
                "name": name.strip(),
                "normalized_name": norm,
                "position": pos,
                "is_customer": _is_same_business(norm, customer_name),
            })
            pos += 1

    return entities


def _is_same_business(normalized_entity: str, customer_name: str) -> bool:
    """Check if an extracted entity matches the customer's business."""
    cust_lower = customer_name.lower()
    if normalized_entity == cust_lower:
        return True
    # Check significant words overlap
    entity_words = set(normalized_entity.split()) - {"the", "of", "and", "in", "at", "dr", "dr."}
    cust_words = set(cust_lower.split()) - {"the", "of", "and", "in", "at", "dr", "dr."}
    if len(entity_words) >= 2 and entity_words.issubset(cust_words):
        return True
    if len(cust_words) >= 2 and cust_words.issubset(entity_words):
        return True
    return False
```

### Backfill Script

```python
# scripts/backfill_entities.py
"""One-time backfill: extract entities from all existing ai_mention_results.full_response."""

def backfill(db, customer_id=None, dry_run=False):
    query = "SELECT id, run_id, customer_id, engine, prompt, prompt_category, full_response FROM ai_mention_results WHERE full_response != ''"
    if customer_id:
        query += f" AND customer_id = '{customer_id}'"

    results = db.conn.execute(query).fetchall()
    # For each result, extract entities and insert into ai_response_entities
    # Skip if entities already exist for this result_id
```

### Share of Voice Computation

```python
def compute_share_of_voice(db, customer_id: str, run_id: str = None, last_n_runs: int = 3) -> dict:
    """Compute share of voice: what % of total AI mentions go to each business.

    Returns: {
        "customer_share": 0.28,  # 28% of all mentions
        "competitors": [
            {"name": "Valley Dental", "share": 0.22, "mention_count": 11, "avg_position": 1.8},
            {"name": "Bright Smiles", "share": 0.18, "mention_count": 9, "avg_position": 2.4},
            ...
        ],
        "total_entity_mentions": 50,
        "total_unique_entities": 12,
        "queries_analyzed": 25,
    }
    """
    # Group by entity_name_normalized across last N runs
    # Count mentions per entity, compute percentage
    # Sort by mention count descending
```

### Auto-Discovery of Competitors

When entities are extracted, automatically add frequently-mentioned businesses to the `competitor_domains` table:

```python
def auto_discover_competitors(db, customer_id: str, min_mentions: int = 3):
    """Promote entities that appear 3+ times across runs to competitor_domains."""
    # SELECT entity_name_normalized, COUNT(*) as cnt
    # FROM ai_response_entities
    # WHERE customer_id = ? AND is_customer = 0
    # GROUP BY entity_name_normalized HAVING cnt >= ?

    # For each, check if already in competitor_domains
    # If not, INSERT with discovered_via = 'ai_response'
```

### Dashboard: Share of Voice Chart

Add to the AI Mentions Dashboard tab (Row 4, replacing the current empty "Competitor AI Visibility" section):

```
+----------------------------------------------------------+
| Share of Voice — AI Search Results                        |
|                                                           |
|  Your Business    ████████████░░░░░░░░  32%  (16 mentions)|
|  Valley Dental    ██████████░░░░░░░░░░  24%  (12 mentions)|
|  Bright Smiles    ████████░░░░░░░░░░░░  18%  (9 mentions) |
|  Summit Dental    ██████░░░░░░░░░░░░░░  14%  (7 mentions) |
|  Others (4)       ██████░░░░░░░░░░░░░░  12%  (6 mentions) |
|                                                           |
|  Based on 25 queries × 5 engines (last 3 runs)           |
|  [View by Engine] [View by Category] [Full Report]        |
+----------------------------------------------------------+
```

### Dashboard: Competitor Trend

Below share of voice, show how each competitor's share changes over time:

```
+----------------------------------------------------------+
| Competitive Trend (Last 8 Weeks)                         |
|                                                           |
|  40% ┤                                                    |
|  30% ┤    ●───●───●                                       |
|  20% ┤  ▲───▲       ●───●    ← You (trending down)       |
|  10% ┤       ▲───▲───▲───▲  ← Valley (trending up)       |
|   0% ┤                                                    |
|      └──W18──W19──W20──W21──W22──W23──W24──W25──          |
+----------------------------------------------------------+
```

---

## Feature 2: Weekly Analytics Overhaul

### Problem Detail

Current state:
- `scheduled_ai_check.py` runs Mon/Wed/Fri → 3 runs per week using benchmark prompts
- `get_rolling_mention_stats()` averages over 12 runs (roughly 4 weeks)
- Dashboard shows one "Mention Rate" number with no context on time window
- Run History shows flat list: "2026-05-26: 12/40, 2026-05-24: 14/40, 2026-05-22: 11/40" — no weekly grouping
- Analytics page shows a single AI Mentions count, no trend

The user can't answer: "How did we do THIS week vs LAST week?"

### Solution: Weekly Summary Layer

#### New DB Method: `get_weekly_ai_summaries()`

```python
def get_weekly_ai_summaries(self, customer_id: str, weeks: int = 12, prompt_set: str = "benchmark") -> list[dict]:
    """Aggregate AI mention runs into weekly summaries.

    Groups runs by ISO week, computes average mention rate, total mentions,
    and week-over-week delta.

    Returns: [
        {
            "week": "2026-W22",
            "week_start": "2026-05-25",
            "week_end": "2026-05-31",
            "runs": 3,
            "avg_mention_rate": 0.34,
            "total_mentions": 37,
            "total_queries": 120,
            "avg_position": 2.1,
            "delta_rate": +0.04,        # vs previous week
            "delta_pct": "+13.3%",      # human-readable
            "best_run_rate": 0.38,
            "worst_run_rate": 0.30,
            "engines": {
                "Claude": {"mentions": 12, "total": 24, "rate": 0.50},
                "ChatGPT": {"mentions": 8, "total": 24, "rate": 0.33},
                ...
            },
            "run_ids": ["uuid1", "uuid2", "uuid3"],
        },
        ...
    ]
    """
    cur = self.conn.execute(
        """SELECT id, run_date, mention_rate, total_mentions, total_queries,
                  avg_position, engines_json,
                  strftime('%%Y-W%%W', run_date) as week
           FROM ai_mention_runs
           WHERE customer_id = ? AND total_queries > 0 AND prompt_set = ?
           ORDER BY run_date DESC""",
        (customer_id, prompt_set),
    )
    rows = [dict(r) for r in cur.fetchall()]

    # Group by week
    weeks_data = {}
    for row in rows:
        w = row["week"]
        if w not in weeks_data:
            weeks_data[w] = {"runs": [], "week": w}
        weeks_data[w]["runs"].append(row)

    # Compute per-week aggregates
    summaries = []
    sorted_weeks = sorted(weeks_data.keys(), reverse=True)[:weeks]
    for i, w in enumerate(sorted_weeks):
        wd = weeks_data[w]
        runs = wd["runs"]
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
            prev_runs = weeks_data[prev_week]["runs"]
            prev_avg = sum(r["mention_rate"] for r in prev_runs) / len(prev_runs)
            delta_rate = round(avg_rate - prev_avg, 4)
            delta_pct = f"{delta_rate / prev_avg * 100:+.1f}%" if prev_avg > 0 else None

        # Per-engine aggregates
        engine_agg = {}
        for run in runs:
            engines = json.loads(run["engines_json"]) if run.get("engines_json") else {}
            for eng, stats in engines.items():
                if eng not in engine_agg:
                    engine_agg[eng] = {"mentions": 0, "total": 0}
                engine_agg[eng]["mentions"] += stats.get("mentions", 0)
                engine_agg[eng]["total"] += stats.get("total", 0)
        for eng in engine_agg:
            t = engine_agg[eng]["total"]
            engine_agg[eng]["rate"] = round(engine_agg[eng]["mentions"] / t, 4) if t > 0 else 0

        dates = sorted([r["run_date"] for r in runs])
        summaries.append({
            "week": w,
            "week_start": dates[0],
            "week_end": dates[-1],
            "runs": len(runs),
            "avg_mention_rate": round(avg_rate, 4),
            "total_mentions": total_m,
            "total_queries": total_q,
            "avg_position": round(avg_pos, 1) if avg_pos else None,
            "delta_rate": delta_rate,
            "delta_pct": delta_pct,
            "best_run_rate": round(max(r["mention_rate"] for r in runs), 4),
            "worst_run_rate": round(min(r["mention_rate"] for r in runs), 4),
            "engines": engine_agg,
            "run_ids": [r["id"] for r in runs],
        })

    return summaries
```

#### New API Endpoint: `/api/ai-mentions/<cid>/weekly`

```python
@app.route("/api/ai-mentions/<customer_id>/weekly")
@login_required
def api_ai_weekly(customer_id):
    db = get_db()
    try:
        weeks = db.get_weekly_ai_summaries(customer_id, weeks=12)
        return jsonify({"ok": True, "weeks": weeks})
    finally:
        db.close()
```

#### Dashboard Changes: Run History Tab

Replace the flat run list with a weekly-grouped view:

```
+----------------------------------------------------------+
| Week of May 25, 2026                          Avg: 34%   |
| ┌──────────┬──────────┬──────────┬──────────┐ +4% ↑      |
| │ Mon 5/26 │ Wed 5/28 │ Fri 5/30 │  Weekly  │            |
| │ 12/40    │ 14/40    │ 11/40    │  37/120  │            |
| │ 30%      │ 35%      │ 28%      │  31%     │            |
| │ Cla:4    │ Cla:5    │ Cla:3    │          │            |
| │ GPT:3    │ GPT:4    │ GPT:3    │          │            |
| │ Prx:2    │ Prx:2    │ Prx:2    │          │            |
| │ Gem:2    │ Gem:2    │ Gem:2    │          │            |
| │ Grk:1    │ Grk:1    │ Grk:1    │          │            |
| └──────────┴──────────┴──────────┴──────────┘            |
|                                                           |
| Week of May 18, 2026                          Avg: 30%   |
| ┌──────────┬──────────┬──────────┬──────────┐ -2% ↓      |
| │ Mon 5/19 │ Wed 5/21 │ Fri 5/23 │  Weekly  │            |
| │ 11/40    │ 13/40    │ 12/40    │  36/120  │            |
| │ 28%      │ 33%      │ 30%      │  30%     │            |
| └──────────┴──────────┴──────────┴──────────┘            |
+----------------------------------------------------------+
```

Each week is a collapsible card showing:
- The 3 individual runs (Mon/Wed/Fri) side by side
- Weekly aggregate (avg rate, total mentions, per-engine breakdown)
- Week-over-week delta with color (green up, red down)
- Click any individual run to see full details (existing `loadRunDetail()`)

#### Dashboard Changes: Scorecards

Update the top scorecards to clearly label the time window:

| Card | Current | New |
|------|---------|-----|
| Mention Rate | "32%" with "16/50 checks" | "32%" with "This Week (3 runs avg)" |
| Trend | Nothing | "+4% vs last week" with arrow |
| Rolling Avg | Hidden in PracticeRank score | "30% (4-week rolling)" |
| Best Engine | "Claude" | "Claude 50% (this week)" |

#### Dashboard Changes: Mention Rate Chart

The existing "Mention Rate Over Time" line chart currently plots individual runs. Change to:
- **Primary line**: Weekly average mention rate (one point per week)
- **Shaded band**: Min-max range for that week's runs (shows consistency)
- **X axis labels**: "W18", "W19", "W20" etc. instead of individual dates
- **Tooltip**: "Week of May 25: 34% avg (30-38% range, 3 runs)"

#### Analytics Page Changes

The global analytics table currently shows a single "AI Mentions" column. Add:

| Column | Shows |
|--------|-------|
| AI This Week | "34% (3 runs)" — this week's average |
| AI Trend | "+4% ↑" — delta vs last week, color-coded |
| AI 4-Week | "30%" — rolling 4-week average |
| Share of Voice | "1st of 8" — rank among competitors in AI results |

---

## Feature 3: DOCX Report Enhancements

### Add to the weekly DOCX report (`ai_report_docx.py`):

**New section: Competitive Landscape**
- Share of Voice bar chart (customer vs top 5 competitors)
- "New competitor detected: Valley Dental appeared in 4 queries this week"
- Per-competitor breakdown: which queries they win, which engines prefer them

**New section: Weekly Summary**
- Table showing this week's 3 runs side by side
- Weekly average with delta vs last week
- Per-engine weekly performance
- Trend chart (8-week rolling)

---

## Implementation Order

### Phase 1: Entity Extraction (foundation — everything else builds on this)
1. Add `ai_response_entities` table to `db.py` migration
2. Write `extract_entities_from_response()` in new file `geo_agent/entity_extractor.py`
3. Write `scripts/backfill_entities.py` to process all historical `full_response` data
4. Hook extraction into `scheduled_ai_check.py` and `dashboard/app.py:_run_ai_check_background()` so new runs auto-extract
5. Add `compute_share_of_voice()` to `db.py`
6. Add `auto_discover_competitors()` to run after each check

### Phase 2: Weekly Summaries (makes data actionable)
7. Add `get_weekly_ai_summaries()` to `db.py`
8. Add `/api/ai-mentions/<cid>/weekly` endpoint to `dashboard/app.py`
9. Rewrite Run History tab to show weekly-grouped view
10. Update Dashboard scorecards to label time windows clearly
11. Update Mention Rate chart to weekly averages with range bands

### Phase 3: Competitive Dashboard (the differentiator)
12. Add `/api/ai-mentions/<cid>/share-of-voice` endpoint
13. Build Share of Voice chart in AI Mentions Dashboard (replace empty competitor section)
14. Build Competitive Trend chart (line chart, customer vs top 3 competitors over 8 weeks)
15. Add "Queries They Win" detail view (click competitor → see which queries they dominate)

### Phase 4: Analytics + Reports
16. Update analytics.html table with weekly columns
17. Add competitive landscape section to DOCX report
18. Add weekly summary section to DOCX report

---

## Files to Modify

| File | Changes |
|------|---------|
| `geo_agent/db.py` | Add `ai_response_entities` table, `get_weekly_ai_summaries()`, `compute_share_of_voice()`, `auto_discover_competitors()` |
| `geo_agent/entity_extractor.py` | **NEW** — `extract_entities_from_response()`, entity normalization, business name matching |
| `scripts/backfill_entities.py` | **NEW** — One-time backfill of entities from historical responses |
| `scripts/scheduled_ai_check.py` | Add entity extraction after each result is saved |
| `scripts/weekly_ai_check.py` | Add entity extraction after each result is saved |
| `dashboard/app.py` | Add `/api/ai-mentions/<cid>/weekly`, `/api/ai-mentions/<cid>/share-of-voice` endpoints; hook extraction into `_run_ai_check_background()` |
| `dashboard/templates/customer_detail.html` | Rewrite Run History tab (weekly groups), update scorecards, add Share of Voice chart, add Competitive Trend chart |
| `dashboard/templates/analytics.html` | Add weekly AI columns to performance table |
| `geo_agent/ai_report_docx.py` | Add Competitive Landscape + Weekly Summary sections |

---

## Verification

1. Run backfill on existing data → entities extracted from historical responses
2. Check SmileShape: see which competitors appear most in AI results
3. Verify weekly grouping: 3 runs in a week show as one weekly card
4. Verify week-over-week delta: shows +/- vs previous week
5. Share of Voice chart: customer bar + competitor bars sum to 100%
6. Auto-discovery: competitors mentioned 3+ times appear in competitor_domains
7. DOCX report: includes new competitive landscape section
8. Analytics page: shows weekly trend columns for each customer

## Key Metrics After Implementation

- **Share of Voice**: "You are mentioned in 32% of AI responses. Your top competitor (Valley Dental) is at 24%."
- **Weekly Trend**: "This week: 34% (+4%). Your best week was W20 at 38%."
- **Competitive Gap**: "Valley Dental beats you on 'emergency dentist' queries (4/5 engines vs your 1/5)."
- **Auto-discovered competitors**: "3 new competitors detected this month from AI responses"
