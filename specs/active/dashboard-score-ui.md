# Dashboard Score UI — Charts, Trends & Quick Wins

## Problem

The dashboard currently shows raw data tables but lacks:
1. A unified score visualization
2. Trend charts for AI visibility over time
3. Actionable "quick wins" that tell customers what to do next
4. Side-by-side comparison with competitors

Industry research shows:
- HubSpot AEO displays visibility score and citation share as 0-100% with week-over-week trend graphs
- BrightLocal's Local Search Grid gives block-by-block visual ranking proof
- Conductor's report shows AI shelf share with platform breakdown (ChatGPT 87.4%, Perplexity 13.8%, Google AI 9.5%)
- Best agency dashboards open with an executive summary: biggest wins, concerns, and next focus

## 1. Score Ring on Overview Tab

**Location:** Top of customer detail Overview tab, replacing or supplementing the existing stat cards.

```
+--------------------------------------------------+
|  [SCORE RING]   PracticeRank Score                |
|     ╭───╮                                         |
|     │ 67│       AI Visibility   ████░░░░  52      |
|     ╰───╯       Search Growth   ██████░░  78      |
|    "Good"       Technical       ████████  91      |
|   +4 vs last    Content         ███░░░░░  38      |
|     week        Reputation      ██████░░  72      |
+--------------------------------------------------+
```

- Large animated donut/ring chart showing overall score (0-100)
- Color matches grade (green/lime/amber/orange/red)
- 5 horizontal bar sparklines for each pillar
- Delta badge: "+4 vs last week" (green if improved, red if declined)
- Clicking any pillar bar scrolls to relevant section

**Implementation:** Pure CSS donut (conic-gradient), no Chart.js needed for the ring. Pillar bars are simple `<div>` width percentages.

## 2. AI Visibility Trend Chart

**Location:** New prominent section on Overview tab, and also on AI Mentions tab.

```
+--------------------------------------------------+
| AI Visibility Over Time                    [6m ▾] |
|                                                   |
|  50% ┤                              ╭─────        |
|  40% ┤                    ╭─────────╯             |
|  30% ┤          ╭─────────╯                       |
|  20% ┤  ────────╯                                 |
|  10% ┤                                            |
|   0% ┼──────────────────────────────────────      |
|       Jan  Feb  Mar  Apr  May  Jun                |
|                                                   |
|  ── Mention Rate   ── Avg Position (inverted)     |
|  ·· ChatGPT   ·· Claude   ·· Perplexity          |
+--------------------------------------------------+
```

**Data source:** `ai_mention_runs` table — one point per run, plotted by `run_date`.

**Chart features:**
- Primary line: overall mention rate (%) — left Y axis
- Secondary line: avg position (inverted, so lower=higher on chart) — right Y axis
- Toggle: show per-engine breakdown lines (ChatGPT, Claude, Perplexity, Google AI)
- Time range selector: 3m, 6m, 1y, All
- Hover tooltip: "Run on May 15: 8/20 mentions (40%), avg position 2.3"

**Implementation:** Chart.js line chart. Data from new API endpoint `/api/ai-trend/<customer_id>`.

## 3. Score Trend Chart

**Location:** Overview tab, below the score ring.

```
+--------------------------------------------------+
| PracticeRank Score History              [90d ▾]   |
|                                                   |
|  80 ┤                              ╭──── 72      |
|  60 ┤              ╭───────────────╯              |
|  40 ┤  ────────────╯                              |
|  20 ┤                                             |
|   0 ┼─────────────────────────────────────        |
|      Mar 1    Apr 1    May 1    May 27            |
|                                                   |
|  Pillar breakdown (stacked area or toggleable):   |
|  ■ AI Vis  ■ Search  ■ Tech  ■ Content  ■ Rep    |
+--------------------------------------------------+
```

**Data source:** `practicerank_scores` table — one row per day.

**Chart features:**
- Primary: overall score line
- Optional: toggle stacked area view showing each pillar's contribution
- Date range: 30d, 90d, 6m, 1y

**Implementation:** Chart.js line chart. Data from `/api/score-history/<customer_id>`.

## 4. Quick Wins Panel

**Location:** Right side of Overview tab or below score, and on Analytics page.

This is the **highest value feature for customer reporting** — surfaces specific, actionable items ranked by impact.

```
+--------------------------------------------------+
| Quick Wins                          [3 available] |
|                                                   |
| 🔴 HIGH IMPACT                                    |
| ┌────────────────────────────────────────────┐   |
| │ Add FAQ schema to 3 service pages          │   |
| │ Est. impact: +5-10% AI visibility          │   |
| │ Effort: Low (automated)     [Do It →]      │   |
| └────────────────────────────────────────────┘   |
|                                                   |
| 🟡 MEDIUM IMPACT                                  |
| ┌────────────────────────────────────────────┐   |
| │ Respond to 4 unanswered Google reviews     │   |
| │ Est. impact: +2 reputation score           │   |
| │ Effort: 15 min              [View →]       │   |
| └────────────────────────────────────────────┘   |
|                                                   |
| 🟢 EASY WIN                                       |
| ┌────────────────────────────────────────────┐   |
| │ Publish 2 approved blog posts              │   |
| │ Est. impact: +3 content velocity score     │   |
| │ Effort: 1-click             [Publish →]    │   |
| └────────────────────────────────────────────┘   |
+--------------------------------------------------+
```

### Quick Win Detection Rules

Quick wins are generated dynamically based on current data gaps:

| Condition | Quick Win | Impact | Effort |
|-----------|-----------|--------|--------|
| No FAQ schema on any page | "Add FAQ schema to service pages" | High (AI vis) | Low |
| llms.txt missing or < 500 bytes | "Create/expand llms.txt" | High (AI vis) | Low |
| Approved content recs not published | "Publish N approved posts" | Medium (content) | Low |
| Google rating < 4.5 with < 50 reviews | "Request reviews from recent patients" | Medium (reputation) | Medium |
| Open critical audit issues | "Fix N critical site issues" | High (technical) | Varies |
| No AI mention run in 30+ days | "Run AI visibility check" | High (tracking) | Low |
| Keywords declining > 3 positions | "Optimize N declining keyword pages" | Medium (search) | Medium |
| Competitor gained 10+ reviews | "Competitor X surged — respond with review push" | Medium (reputation) | Medium |
| Title tags missing/duplicate | "Fix N title tag issues" | Medium (search) | Low |
| No content published in 30+ days | "Content is stale — publish or refresh" | Medium (content) | Medium |

### Quick Win Data Structure

```python
{
    "id": "qw_faq_schema",
    "title": "Add FAQ schema to 3 service pages",
    "description": "FAQ schema helps AI engines cite your answers directly.",
    "pillar": "ai_visibility",       # which score pillar this impacts
    "impact": "high",                # high, medium, low
    "effort": "low",                 # low, medium, high
    "est_score_boost": 5,            # estimated points added to overall score
    "action_url": "/customer/X/audit",  # where to take action
    "action_label": "View Audit",
    "auto_actionable": true,         # can we do this automatically?
}
```

### Quick Win Priority Sort

1. High impact + Low effort (do first)
2. High impact + Medium effort
3. Medium impact + Low effort
4. Medium impact + Medium effort
5. Low impact (show but deprioritize)

Show max 5 quick wins at a time. Dismiss/complete removes from list.

## 5. Analytics Overview Page Enhancements

The global Analytics page (`/analytics`) should show:

### Score Leaderboard
```
+--------------------------------------------------+
| Customer Scores                                   |
|                                                   |
| SmileShape            ████████████████░░  82  A   |
| Downtown Dental       ██████████████░░░░  71  C   |
| Sojo Dental           ██████████░░░░░░░░  52  D   |
| Hilltop Dental        ████░░░░░░░░░░░░░░  28  F   |
+--------------------------------------------------+
```

- Horizontal bar chart, sorted by score descending
- Color-coded by grade
- Click to drill into customer detail
- Shows delta arrow (↑↓) vs last week

### Aggregate Quick Wins
```
+--------------------------------------------------+
| Top Quick Wins Across All Customers               |
|                                                   |
| 3 customers need FAQ schema                       |
| 2 customers have unpublished approved content     |
| 1 customer hasn't had an AI check in 30+ days     |
| 4 customers have open critical audit issues       |
+--------------------------------------------------+
```

Grouped by type, showing count of affected customers. Helps the team prioritize batch work.

## 6. Customer Report Score Section

For weekly/monthly email reports, include a simple score summary:

```
Your PracticeRank Score: 67/100 (Good) — up 4 points from last week

  AI Visibility:   52  (↑ from 45)
  Search Growth:   78  (↑ from 72)
  Technical:       91  (stable)
  Content:         38  (↓ from 42 — publish pending content!)
  Reputation:      72  (stable)

Top quick win: Publish 2 approved blog posts to boost your content score.
```

## API Endpoints

| Endpoint | Method | Returns |
|----------|--------|---------|
| `/api/score/<customer_id>` | GET | Current score + pillar breakdown |
| `/api/score-history/<customer_id>?range=90d` | GET | Daily scores for chart |
| `/api/ai-trend/<customer_id>?range=6m` | GET | AI mention rate over time, per-engine |
| `/api/quick-wins/<customer_id>` | GET | Prioritized quick win list |
| `/api/analytics/scores` | GET | All customer scores for leaderboard |

## Files to Create/Modify

| File | Action |
|------|--------|
| `dashboard/app.py` | Add 5 new API endpoints, update overview/analytics routes |
| `dashboard/templates/customer_detail.html` | Add score ring, AI trend chart, quick wins panel to overview tab |
| `dashboard/templates/analytics.html` | Add score leaderboard + aggregate quick wins |
| `geo_agent/quick_wins.py` | **NEW** — Quick win detection engine |
| `templates/emails/07-weekly-seo-update.md` | Add score summary section |
| `templates/emails/04-monthly-report.md` | Add score summary section |

## Implementation Order

1. **Phase 1: Score Engine** — `practicerank_score.py` + DB table + daily cron
2. **Phase 2: Score UI** — Ring chart + pillar bars on customer overview
3. **Phase 3: Trend Charts** — AI visibility trend + score history charts
4. **Phase 4: Quick Wins** — Detection engine + panel on overview
5. **Phase 5: Analytics** — Score leaderboard + aggregate quick wins
6. **Phase 6: Reports** — Score section in email templates
