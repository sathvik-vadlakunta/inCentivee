# Dental SEO Benchmark — 20 Top Sites + Improvement Checklist

Research method: candidates pulled from agency "best dental websites" roundups, then each site's homepage + a service/location page was **fetched and verified live**. Strengths reflect what was actually observed. No fabricated metrics.

## The 20 exemplar sites

| # | Practice | City/State | Domain | Verified strength |
|---|---|---|---|---|
| 1 | Grand Street Dental | Brooklyn, NY | grandstreetdental.com | 15+ per-service pages; NexHealth booking + click-to-call + form; press social proof |
| 2 | Madison Park Family Dentistry | Torrance, CA | thetorrancedentist.net | Service silos targeting "[service] in Torrance"; embedded map, ADA/CDA badges |
| 3 | 6 Corners Dental Studio | Chicago, IL | 6cornersdentalstudio.com | Answer-engine-friendly service hierarchy; 200+ 5★ reviews; Flexbook booking |
| 4 | Atlanta Center for Advanced Periodontics | Atlanta, GA | advancedperioatl.com | Procedure-specific pages = specialty authority; per-location detail; on-page FAQ |
| 5 | Staten Island Oral & Maxillofacial Surgery | Staten Island, NY | statenislandoralsurgery.us | Deep surgical pages; heavy E-E-A-T (board cert, media); FAQ + before/after |
| 6 | Village Dental | Greenwood Village, CO | villagedentaldtc.com | 20+ procedure pages, strong internal links; 1,200+ reviews; per-dentist bios |
| 7 | Killingsworth Family Dentistry | Parker, CO | killingsworthfamilydentistry.com | Best-in-class neighborhood targeting; 25+ service pages; consistent NAP |
| 8 | Tend | NYC/DC/Boston/ATL/Nashville | hellotend.com | 33 location pages + location×service matrix; 8,000+ reviews; booking above fold |
| 9 | DiBartola Dental | Bridgeville, PA | dentistbridgevillepa.com | City in domain/title/H1; complete NAP + map; outcome testimonials |
| 10 | Smile, Co. Tampa Palms | Tampa, FL | smilecotampapalms.com | On-page rendered review stars (Review schema); repeated booking + call |
| 11 | Thrive Family Dental | Wilmington, NC | thrivefamilydental.com | 900+ 5★ reviews linked; strong conversion design + new-patient offer |
| 12 | Boulder Smiles | Boulder, CO | bouldersmiles.com | Authority badges (Invisalign Diamond+, "Best of Boulder"); perfect NAP |
| 13 | Zen Dental Studio | SF & Mountain View, CA | zen.dentist | Multi-location NAP + per-location booking; anxiety-reduction UX content |
| 14 | Dentologie | Chicago & Seattle | dentologie.com | Neighborhood-page strategy across two metros; strong brand search |
| 15 | Casco Bay Smiles | Portland, ME | cascobaysmiles.com | Fast, clean, community-focused local messaging; clear IA |
| 16 | Center for Advanced Dentistry | Loveland, CO | lovelanddentist.com | City keyword in domain; cosmetic before/after imagery |
| 17 | Jackson Family Dental | MO | jacksonfamilydentalonline.com | Professional procedure/experience video — engagement + conversion |
| 18 | Mark S. Murphy, DDS | US | markmurphydds.com | Full-width hero video, mobile-first, local-SEO structure |
| 19 | Brooks Pediatric Dentistry | US | brookspediatricdentistry.com | Pediatric long-tail + FAQ schema + voice-search Q&A |
| 20 | Serenity Smiles | US | serenitysmiles850.com | Clean, crawlable per-service silo architecture |

**Patterns across all 20:** one page per service, prominent review counts, online booking + click-to-call repeated, complete/consistent NAP. **Biggest common gap even on the best sites:** a real blog/topical-authority layer, visible `FAQPage` schema, and `llms.txt` — our easiest differentiation.

## Improvement checklist (what we DO for clients)

**Technical:** WebP/AVIF + lazy-load (LCP<2.5s, CLS<0.1, INP<200ms) · self-host/preload fonts · true mobile-first (tap targets ≥48px) · HTTPS redirect · XML sitemap + robots with every service/location page · clean URLs · one canonical NAP in markup.

**On-page:** one page per service (15–25+) · title/H1 = `[Service] in [City], [ST] | [Practice]` · one H1 + question-mapped H2s · deepen service pages to 600–1,000 words (cost/procedure/recovery/financing) · hub-and-spoke internal links · keyworded alt text + renamed files.

**Schema (JSON-LD):** Dentist/LocalBusiness (home + each location) · MedicalProcedure on each service · **FAQPage** (biggest untapped win) · Review/AggregateRating (rendered stars) · BreadcrumbList · Person per dentist → bio. Validate in Rich Results Test.

**Local:** GBP optimization (categories, services, geotagged photos, weekly posts, Q&A) · exact NAP everywhere · city/neighborhood landing pages with unique content (Killingsworth/Dentologie model, avoid thin doorways) · embedded map + directions · citation building/cleanup · reviews engine to grow visible counts · per-location pages for multi-location.

**Content/E-E-A-T:** real blog as content clusters around pillar services · FAQ block on every service page · author bios with credentials + Person schema · trust signals (board certs, awards, media) · freshness cadence.

**AEO / AI-search:** publish `llms.txt` + `llms-full.txt` (none of the 20 had it — first-mover edge) · conversational Q→A content · lead with the answer (inverted pyramid) · machine-readable facts as text not images · comprehensive JSON-LD.

**Conversion/UX:** repeat primary CTA above the fold · click-to-call everywhere + sticky call/book bar · online booking (NexHealth/Modento/Flexbook) · real photo/video not stock · social proof high on page (counts, before/after, named testimonials) · pricing/insurance/financing transparency · layout variety.

**Top 5 quick wins to lead a client engagement:** (1) FAQPage + Review/AggregateRating schema, (2) split "Services" into one page per service @600–1,000 words, (3) `llms.txt` + `llms-full.txt`, (4) city/neighborhood landing pages, (5) clustered blog tied to top revenue services.
