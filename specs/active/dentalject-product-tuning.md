# DentalJect + product-type tuning

**Customer:** dentalject (DentalJect, dentalject.com) — `business_type=product`. B2B: sells a topical
anesthetic spray dentists apply before the pre-injection needle. National, no city.

## Problem
Admin app shows AI Visibility 70; the practicerank.ai sales report showed ~0/5 AEO. They measure
different things (brand *mentions* vs site *readiness*), but the 70 is inflated by junk prompts and
several things are mis-tuned for a product company.

## The 4 fixes
1. **AI-mention prompts for `product`** — `check_ai_mentions.py` has no `product` branch, so it hits the
   generic `else` → "best product in [blank]", "top product companies". Add a product branch that builds
   category/buyer-intent prompts from `services` ("best topical anesthetic spray", "... for dentists").
   Also **exclude `brand`-category prompts from the mention-RATE** (they trivially match when you name the
   brand) so AI Visibility reflects real discovery.
2. **Schema type** — product customers get `LocalBusiness` (wrong). Should be `Product`/`Organization`.
   Fix generator + validator, regenerate dentalject schema.
3. **Technical files** — dentalject missing robots.txt, XML sitemap, FAQ schema, review schema.
4. **Populate** product buyer-intent keyword_tracking + content_topics aimed at dentists (B2B), not patients.

## Notes / decisions
- Services are already good (Topical Anesthetic Spray, Injection Pain Relief, Palatal Anesthetic, …).
- PageSpeed (Lighthouse mobile) = 63.
- Old (junk-prompt) mention data: ~29-34%, avg pos ~1.3, all 5 engines → inflated AI Visibility 70.

## Status (2026-07-08)
- **#1 DONE + deployed** — `check_ai_mentions.py` has a `product` branch that leads with the
  customer's curated buyer/action-intent **keywords** (brand-free problem searches), drops brand
  prompts to 1, and never uses the geo/practice template. Runner passes `db.get_tracked_keywords()`.
- **#4 DONE** — 16 tracked keywords (10 category + 6 action/question) + 5 dentist-facing content topics.
- **#2 (schema)** — generator already emits `Organization` for product (correct); `seo_schema_org` flag set.
- **#3 (technical files)** — llms.txt/llms-full were false-positives (301 → /home). Corrected the checklist
  (`seo_llms_txt`/`seo_llms_full` → false) so GEO Foundation reflects reality.
- **Platform blocker:** dentalject.com is on **HighLevel** (LeadConnector + Stripe ordering); no deploy
  integration exists. Real technical-SEO fixes require **scraping + rebuilding on our stack** (Astro/
  Cloudflare) — **PARKED per Kody**.

## Honest baseline (action-keyword run, 2026-07-08)
- **AI Visibility = 55** (was inflated 70). 79 queries, 21.5% mention rate, avg pos 2.06, 4/5 engines.
- **The gap:** every real problem/action query is **0/4** — "how to reduce shot pain at the dentist",
  "painless dental injection", "reduce injection pain dentistry", even "best topical anesthetic spray".
  DentalJect only surfaces for brand-named queries + 1-2 category terms.
- **Business case:** strong brand recall, ~zero organic AI discovery on acquisition searches. That 0/4
  wall justifies the content + technical-SEO work (and the parked HighLevel migration).
