# Live-scan score detectors (self-publishing clients)

**Status:** shipped 2026-07-09 (deployed to droplet)

## Problem

The PracticeRank score under-reported any client whose developer ships the SEO/AEO
foundation themselves (self-publishing clients like Downtown Dental, Paradigm). Two
pillars scored off **DB state**, not the live site:

- `compute_technical_health` (GEO Foundation) reads 8 deliverable flags from the
  checklist. The daily reconciler ticked them via `detect_live_status`, but that
  detector had holes: it **never probed `/sitemap.xml`** (so `seo_xml_sitemap`, 10 pts,
  could only be set by hand) and only matched the legacy `ChatGPT-User`/`PerplexityBot`
  robots tokens (missing modern `GPTBot`/`ClaudeBot`/`Google-Extended`/`CCBot`, 15 pts).
- `compute_content_velocity` (Content & Coverage) counted service-area coverage by
  matching city names against **our published `new_page` rec titles** — so a dev-built
  `/newark-nj` page counted as 0 coverage because it never came through our pipeline.

Real-world impact: Downtown read as 42/D from stale flags; the true live state is 88/A.
It took three manual re-scrapes to catch. The fix makes the score self-correct.

## Fix

`geo_agent/status_checker.py`
- `detect_live_status`: browser User-Agent on every fetch (Cloudflare 1010 workaround);
  probe `/sitemap.xml` (+ index variants) → `seo_xml_sitemap`; broaden robots detection
  to the modern AI-crawler tokens (`_AI_ROBOTS_TOKENS`) **or** a `Sitemap:` directive.
- New `detect_area_pages_live(domain, service_areas)`: scans sitemap `<loc>` URLs and
  matches each city slug as a path token (multi-word cities like "Jersey City" require
  all tokens), returning the covered `service_areas` entries.
- `reconcile_customer`: persists detected coverage via `db.set_live_area_pages`.

`geo_agent/db.py`
- New column `customers.live_area_pages` (JSON list) + parse in `get_customer` + setter.

`geo_agent/practicerank_score.py`
- `compute_content_velocity`: a city counts as covered if we published a location page
  for it **OR** the reconciler detected a live page (`customer.live_area_pages`).

Detection stays **additive** (only sets flags True): a transient fetch failure or
Cloudflare block can never tank a real deliverable — matches the pillar's existing
"a PageSpeed timeout can never tank it" philosophy.

## Verified (Downtown, 2026-07-09)

- `detect_live_status` → 10 flags incl. `seo_xml_sitemap` + `seo_robots_txt`.
- `detect_area_pages_live` → 8/8 cities from the live sitemap.
- Reconcile (dry_run=False) took `live_area_pages` [] → 8 cities, coverage 0/8 → 8/8,
  overall **80 → 85**. After marking 9 fuzzy-missed content items published (verified by
  precise stat/FAQ string match), overall **88/A** (Foundation 100, Content 100).

## Notes / follow-ups

- `_content_is_live`'s fuzzy word-overlap is unreliable for small injected snippets
  (stat callouts, freshness updates) — it flip-flops on page-fetch success. For an
  authoritative "is this snippet live" answer, match distinctive stats/question text,
  not generic word overlap. Reconciler still uses fuzzy (additive, low-risk), but don't
  trust it for content-gap reporting.
- Runs daily for cut-over customers only (`reconcile_all` gate) — see
  `paying-only-recurring-work.md`.
- Future cleanup (pre-existing): consolidate the dashboard's `_auto_detect_seo_status`
  cache and this headless `detect_live_status` into one source of truth.
