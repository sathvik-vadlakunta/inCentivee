# Proof of Improvement Metrics

Started: 2026-05-26

## Problem

AI mention scores fluctuate due to LLM non-determinism. Same query can return different results each run. Need reliable metrics that show real improvement over time, not single noisy snapshots.

## Solution: Multi-signal approach

### 1. Rolling Averages for AI Mentions (immediate)
- Schedule AI mention checks 3x/week (Mon/Wed/Fri, 6am ET)
- Store per-run data (already exists in `ai_mention_runs` table)
- Compute 4-week rolling average (12 runs) for mention rate, position, quality
- Dashboard shows rolling trend line, not just latest run
- Smooths out LLM randomness, shows real trajectory

### 2. Google Search Console Integration (when access granted)
- All 7 customers have GSC access "pending" — none granted yet
- Best first test candidates: Hilltop (first client) or Downtown Dental (most runs)
- GSC API via service account gives: clicks, impressions, avg position, CTR
- Track weekly, show month-over-month growth
- New KPIs: `organic_clicks`, `organic_impressions`, `avg_search_position`, `search_ctr`

### 3. llms.txt Hit Tracking (already exists, surface better)
- Already tracked via Cloudflare Worker stats
- Make more prominent in dashboard and reports
- Show by-agent breakdown (ChatGPT, Claude, Perplexity, Google, etc.)
- This is direct proof AI systems are reading the content we deployed

### 4. Composite Proof Score
- Combine all signals into a single "AI Visibility Score" for client reports
- Weighted: GSC clicks (30%) + rolling AI mention rate (25%) + llms.txt hits (25%) + review growth (20%)
- Falls back gracefully when some signals unavailable

## Schedule

AI mention checks: Mon/Wed/Fri at 6:00 AM ET via cron
- Stagger customers 5 min apart to avoid API rate limits
- 8 customers × ~325 queries × 5 engines = ~13,000 API calls per run
- 3 runs/week = ~39,000 calls/week (well within limits)

## Files

### New
- `geo_agent/gsc_client.py` — Google Search Console API client
- `geo_agent/visibility_score.py` — Composite AI visibility score
- `scripts/scheduled_ai_check.py` — Cron-friendly script for scheduled runs

### Modified
- `geo_agent/db.py` — New tables: `gsc_metrics`, new KPI tracking methods, rolling average queries
- `dashboard/app.py` — Rolling average API endpoints, GSC dashboard, visibility score display
- `dashboard/templates/customer_detail.html` — Rolling trend charts, GSC section, visibility score card

## Status
- [ ] Rolling averages (DB queries + dashboard)
- [ ] Scheduled AI check script
- [ ] GSC client (ready for when access granted)
- [ ] Visibility score
- [ ] Dashboard updates
