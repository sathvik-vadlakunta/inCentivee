# Local SEO checklist collapse + GBP Q&A monthly engine + content-approval queue

**Status:** active
**Created:** 2026-06-26
**Trigger:** Reviewing Paradigm's Local SEO (1/9). The granular items (Apple/Yelp/Bing/Facebook/
NAP/Tier2) don't match how the work actually gets done — the FATJOE 100-citation onboarding
bundle builds all of them. Kody: collapse to "citations bought + verify a few key things,"
make GBP Q&A an automated monthly keyword-driven content step, and give Dan a single place to
approve the month's content.

## Part A — Collapse Local SEO checklist (CONFIRMED)
Replace the 6 granular items with a model that matches ops. New Local SEO (local verticals):
1. `seo_gbp_optimized` — GBP fully optimized (auto) [keep]
2. `seo_gbp_photos` — 10+ GBP photos (customer provides) [keep]
3. `seo_gbp_qa` — GBP Q&A pre-populated (now automated monthly — Part B) [keep]
4. `seo_citations_ordered` — **NEW** — FATJOE 100-citation bundle ordered (Yelp, Bing, Facebook,
   NAP + Tier 2). Auto-tick from a citation order in `offsite_orders`.
5. `seo_listings_verified` — **NEW** — Key listings verified live & NAP-consistent. Auto via the
   directory scan (`_detect_directory_listings` / Scan Listings) + NAP phone match.
6. `seo_apple_business` — **KEEP, reword** — Apple Business listing matches Google (**Dan-verified**,
   manual). Apple Maps/Siri/Spotlight is high-value; verification needs a human.

Remove: `seo_yelp`, `seo_facebook`, `seo_bing_places`, `seo_nap_consistent`, `seo_tier2_citations`.
Keep practice-only dirs: `seo_healthgrades`, `seo_zocdoc`.
Repoint detection: directory-scan yelp/facebook/bing/tier2/NAP signals → `seo_listings_verified`;
`seo_citations_ordered` ← offsite_orders citation order.

## Part B — GBP Q&A monthly engine (CONFIRMED)
`geo_agent/gbp_qa.py:generate_gbp_qa(db, customer_id)` — gather tracked keywords + question/
striking-distance GSC queries (fallback services/city), Claude writes 10–15 Q&A pairs grounded in
real services/keywords (anti-fabrication: no invented stats/claims), persist as ONE `gbp_qa`
content rec (pending), idempotent per month. Output = copy-paste Q&A (no reliable GBP Q&A API —
owner posts + answers from the managing account). On publish, `status_checker._content_task_status`
maps `gbp_qa` → `seo_gbp_qa`. Run monthly alongside `keyword_content` (biweekly_content script).

## Part C — Monthly content-approval queue (CONFIRMED)
New cross-customer `/content-queue` (mirrors `/fatjoe`): every customer's pending content recs
grouped, with one-click approve/reject (reuses `/customer/<id>/content/status`). Nav link. This is
Dan's "this month's content to approve" surface.

## Follow-ups (out of scope now)
- GBP→Apple Business Connect API sync (scale play: push GBP data to all clients' Apple listings).
- Tokenized customer-facing review link.
- Fix corrupted tracked keyword for Paradigm (`best way to sell gold coins,1,1440,0.07%` — bad CSV import).
