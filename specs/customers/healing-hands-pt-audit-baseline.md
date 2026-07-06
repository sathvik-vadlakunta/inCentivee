# Healing Hands PT — Baseline Audit (BEFORE snapshot)

- **Domain:** healinghandspt.net
- **Date:** 2026-06-29
- **Status:** NOT yet a customer (cold-domain baseline; no GSC / GA / GBP / AI-mention data)
- **Run on:** DigitalOcean droplet `practicerank-dashboard` container (real PAGESPEED + MOZ keys)

## The three baseline numbers

| Metric | Value | Tool / source |
|---|---|---|
| **PracticeRank score** | **28 / 100** (cold-domain proxy) | `report_generator._calculate_scores` from live audit signals |
| **SEO / PageSpeed (Lighthouse performance)** | **73 / 100** (mobile) | `site_auditor._run_pagespeed` (Google PageSpeed Insights v5) |
| **Domain Authority (DA)** | **11** (PA 26, spam score 2) | `moz_client.get_domain_authority` (Moz Links API v2) |

## Raw PageSpeed / Lighthouse sub-scores (mobile)

| Category | Score |
|---|---|
| Performance | 73 |
| Accessibility | 91 |
| SEO | 100 |
| Best Practices | 96 |

The dashboard "SEO Health" donut weights Performance 25% and Technical (avg of
SEO/best-practices/a11y = ~96) 25%; the other 50% (keyword coverage + traffic
trend) requires GSC and cannot be computed for a non-customer.

## Live SEO/AEO findings (from site_auditor custom checks)

- Schema markup: **present** (LocalBusiness/Organization JSON-LD detected).
- **No FAQ schema** (FAQPage) — warning.
- **No llms.txt** — warning (AEO gap; the core GEO deliverable we add).
- Sitemap: present (no warning raised).
- robots.txt: present (no warning raised).

## PracticeRank score caveats — IMPORTANT

- The **canonical** composite (`practicerank_score.compute_practicerank_score`)
  CANNOT run for a non-customer: it needs DB-backed pillars (AI-mention runs,
  GSC daily, GEO-foundation checklist, GBP/reviews). With <2 pillars it returns
  `"Insufficient Data"` (score = None). So the 28 above is **not** that composite.
- The **28/100** is the cold-domain proxy from `report_generator._calculate_scores`,
  fed only by what the live audit could verify. It is **depressed** by signals a
  non-customer structurally lacks:
    - `aeo = 0` — no llms.txt + no FAQPage/Person/MedicalProcedure schema detected.
    - `local_visibility = 30`, `review_presence = 20` — no GBP rating/review data
      available (would rise once Google Places is connected).
    - `pages_indexed = 0` — no GSC, so content/technical buckets sit at their floor.
- Treat 28 as a conservative floor. Once onboarded (GBP linked, llms.txt + FAQ
  schema shipped), expect a meaningful jump driven mostly by the AEO and local
  buckets we directly control.

## What is NOT in this baseline (and why)

- AI Visibility / mention rate — needs an AI-mention run (Claude API spend); not
  run for a cold prospect. Reportable signal: **none yet**.
- Search Performance (clicks/impressions/position trend) — needs Search Console.
- Keyword coverage / traffic trend — needs GSC + tracked keywords.

No metric above was fabricated; each is from a live API call on 2026-06-29.
