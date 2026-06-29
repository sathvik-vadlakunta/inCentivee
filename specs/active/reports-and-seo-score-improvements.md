# Reports cadence toggle + SEO Health Score history + tier-driven content cadence

**Status:** active
**Created:** 2026-06-29
**Trigger:** Three questions from Kody while reviewing Paradigm's dashboard:
1. Is weekly-vs-last-week useful, or do we need longer windows? Where do I see old/monthly reports?
2. The SEO Health Score is under-explained — show improvement over time, why it's lower, how to improve.
3. Does "Generate Recommendations" do full-site changes / respect existing changes / handle blog posts
   by tier / auto-generate?

## Answers (the "why")
- **Weekly is noisy on purpose** (Paradigm: weekly looked −39% while 30d-vs-prior-30d was +27% real
  growth). Weekly = internal ops; **monthly** = customer-facing progress; **quarterly** = the arc.
  Monthly reports were being *stored* (`report_type="monthly"`) but the customer page only queried
  `"weekly"`, so they were invisible.
- **SEO Health Score** had three real flaws: (a) the "Technical" bucket just **duplicated the PageSpeed
  average** → PageSpeed was effectively ~50% of the score; (b) traffic used **7d-vs-7d** (noisy) and
  ignored the page's window toggle; (c) it was **never persisted**, so no trend and the number drifted
  (live recompute gave 73 vs the 61 on screen).
- **Generate Recommendations** produces **pending** recs (never touches the live site), **dedupes against
  existing/live pages**, and **does** generate blog posts — but **tier did NOT drive volume** (tier only
  drove FATJOE backlinks). Nothing auto-publishes.

## Build A — Report cadence toggle (DONE)
- `weekly_report_view` accepts `?period=7|30|90` → builds the matching report (`dashboard/app.py`).
- `customer_detail` passes `report_periods` + `report_latest_by_type` + `report_history_by_type` for
  weekly/monthly/quarterly.
- `customer_detail.html` "Reports" tab: Weekly/Monthly/Quarterly pill toggle, per-type share link +
  history, view links carry the period. Tab + nav relabeled "Reports".

## Build B — SEO Health Score history + breakdown + fix (DONE)
- New `geo_agent/seo_health.py` = single source of truth: `compute_seo_health()` (4 DISTINCT 25% buckets:
  Performance / Keyword coverage / Traffic 30d-vs-prior-30d / Technical = avg(seo,best-practices,a11y)) +
  `persist_seo_health(db, cid)`.
- New table `seo_health_history` (+ `save_seo_health` / `get_seo_health_history` in `db.py`).
- Dashboard computes from a **stable 60-day GSC series** (score no longer moves with the date pills),
  persists daily, and renders: a **?-toggle breakdown panel** (4 bars + plain-English detail), a
  **sparkline** of stored scores, and a **"▲ +N vs ~30d ago"** delta.
- Weekly cron (`scripts/weekly_reports.py`) adds **R6** `persist_seo_health` so the trend builds even
  with no page views.

## Build C — Tier-driven content cadence (DONE)
- `fatjoe_plan.TIER_PLANS` gains `content_quota` (Optimize=2, Grow=4, Dominate=8 — from
  `good-better-best-pricing.html`) + `DEFAULT_CONTENT_QUOTA=2`; new `monthly_content_quota(plan, override)`.
- `scripts/biweekly_content.py` `--max` now defaults to the **tier quota** (Stripe plan_name +
  tier_override), so the paid tier dictates how many content pieces are queued/month. `--max` still
  overrides manually.

## Tests
`tests/unit/test_seo_health_and_tier.py` — buckets distinct (perf≠technical), coverage %, traffic
neutral/growth, weighted-average score; tier quota known/unknown/override. Full suite: 855 passed.

## Follow-ups (not done)
- Surface the tier content quota on the dashboard (so Dan sees "4/mo target, 2 queued").
- Optionally enable customer emailing for the monthly report (still `EMAIL_CUSTOMERS=False`).
- Backfill `seo_health_history` is not retroactive — trend starts accruing from first run.
