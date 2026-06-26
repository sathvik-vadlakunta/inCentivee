# Dashboard Data Integrity — audit every panel's source, test it, refresh on cadence, cut tech debt

**Status:** active (spec / proposed)
**Created:** 2026-06-26
**Trigger:** A cascade of data-sourcing bugs surfaced while reviewing Paradigm Experts. Each was
a *page showing wrong/empty data because it read the wrong source or gated on a record that
didn't exist*. Kody: "I need full unit and integration tests and a full audit on all these pages
to make sure they are getting the correct data and sourced correctly… accurate when I load the
page… and it should check on some cadence… and review any legacy code / tech debt we can rip out."

## The systemic problem (evidence from today)

| Symptom | Real source bug |
|---|---|
| "No FAQ schema markup" everywhere (audit, checklist, overview alert) | `_check_schema_markup` + `_auto_detect_seo_status` scraped **only the homepage**; FAQPage correctly lives on service pages. **(fixed)** |
| Overview "No search data" despite 5,225 GSC query rows | Overview fetches **live GSC API**, gated on a `customer_integrations` record with `status='active'` that **never existed** for Paradigm (data flowed via the service account, but the integration was never saved). **(fixed for Paradigm; pattern remains)** |
| `gsc_daily_metrics` empty while `gsc_query_daily` had 5,225 rows | The agent ran `track_gsc_queries` but **not** `track_gsc_metrics` — two GSC tables, inconsistently populated; different pages read different ones. |
| Checklist false-negatives (location pages, FAQ schema) | Auto-detection reads homepage / limited signals, misses the 28 published location pages. |

Root theme: **multiple readers, multiple sources, no single source of truth, gated on records
that may not exist, and no tests asserting "page X shows the right data from source Y."**

## Goal
Every dashboard panel: (1) has a **known, correct data source**, (2) is **accurate on page load**
(falls back / self-heals when a record is missing but data exists), (3) is covered by **unit +
integration tests**, (4) refreshed on a **cadence** so it stays current, and (5) freed of the
**legacy/dead code** that makes the above hard to reason about.

## Plan (phases)

### P1 — Data-source inventory (audit)
Enumerate every panel on every customer subpage (Overview, Rankings, Traffic, Audit,
Backlinks, Competitors, Reviews, Integrations, Content, Local SEO, AI Mentions, Weekly Report)
→ for each: the template var, the route code that fills it, the DB table / live API it reads,
the gating condition, and "expected vs actual" with a seeded customer. Output: a source-of-truth
matrix + a ranked list of mis-sourced / empty-gated / duplicated panels.

### P2 — Fix sourcing
- **GSC:** reconcile `gsc_daily_metrics` (overview/charts) vs `gsc_query_daily` (keywords). One
  pull path that always writes both; overview falls back to the stored table when the live
  integration is absent; **auto-create the integration record when GSC data is detected** (so a
  page never says "configure GSC" while data exists).
- **Checklist auto-detect:** detect from published content (crawled pages / live service pages /
  content recs), not the homepage — for FAQ schema, location pages, stats, pricing page.
- Apply the same "check the real pages, self-heal missing records" fix everywhere P1 flags it.

### P3 — Tests
- **Unit:** each DB accessor + detector (`get_gsc_daily`, `_check_schema_markup`,
  `_auto_detect_seo_status`, tier/stat/validation helpers) with seeded data + edge cases.
- **Integration:** render each customer subpage against a seeded DB and assert the panel shows the
  expected numbers from the expected source (the "accurate when I load the page" guarantee).

### P4 — Refresh cadence
A scheduled job (cron) per active customer: GSC pull (queries + metrics), audit re-run, checklist
re-detect, places/reviews refresh — so data is fresh on load instead of stale until someone clicks.
Staggered + rate-limit-aware; writes a `last_refreshed` per source surfaced in the UI.

### P5 — Tech-debt / legacy removal
Catalogue and rip out: duplicated GSC tables/paths, dead detection branches, the old SmileShape
Webflow OAuth app (register a PracticeRank-owned one), unused columns/routes, and any
"diverged copies" pattern. Each removal behind tests from P3.

## Immediate fixes already shipped (2026-06-26)
- FAQ false-positive: `_check_schema_markup` + `_auto_detect_seo_status` now sample service/FAQ
  pages (deployed).
- Paradigm: GSC integration record created (overview live), `gsc_daily_metrics` backfilled 89 days,
  audit re-run clean, estate-jewelry FAQPage added manually.

## Results (2026-06-26)

- **P1 ✅** — workflow audited 13 subpages / 109 panels → 19 confirmed high-severity bugs, ranked.
- **P2 ✅ (5 of 6 + feature)** — #1 Overview cache fallback (HIGH, root cause); #2 directory per-result
  matching (HIGH, no false checkmarks); #3 impression-weighted avg position; #4 NAP independent-source
  compare; #6 unmapped-business_type baseline; **🎯 Striking Distance keyword-opportunities view** (the
  "what to target more" tool). Remaining: **#5 cache-staleness labeling** (label run-derived checklist
  items with source/age — low risk, deferred).
- **P3 ✅ (started)** — integration test renders /customer/<id> from a seeded DB asserting the cache
  fallback fires ("accurate on load"); + unit tests for directory match, striking distance, NAP, baseline.
  Full suite 795 passing. Broader per-subpage render tests = continuation.
- **P4 ✅** — `geo_agent/refresh.py` + daily droplet cron (GSC metrics+queries + audit), fixing
  "stale until clicked" AND populating the cache the Overview falls back to.
- **P5 — partial.** GSC two-table reconcile effectively done (refresh.py is the single population path;
  Overview reads/falls back to the cache). Remaining as a **reviewed** pass (don't blind-delete from a
  live dashboard): dead detection branches, the old SmileShape Webflow OAuth app (register a
  PracticeRank-owned one — needs a Webflow account action), unused columns/routes.

Plus same-day foundational fixes: PSI key+120s timeout (scores restored 60/100/96/96), GSC integration
self-creation, keyword pull 4→202, audit issue auto-close, FAQ service-page detection.

## Open question for Kody
Scope/run as: (a) one structured **multi-agent workflow** (parallel readers map every panel →
verify against seeded data → adversarially confirm → synthesize the fix list + tests), or
(b) **incremental** phase-by-phase with review gates. (a) is faster + more exhaustive but spends
more tokens; (b) keeps you in the loop each phase.
