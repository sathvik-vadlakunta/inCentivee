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
- Actual mention data: 684 checks, 234 mentioned (~34%), avg pos 1.28, all 5 engines.
