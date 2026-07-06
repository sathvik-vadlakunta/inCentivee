# Healing Hands PT — Full Site Audit

**Date:** 2026-06-29 · **Auditor:** automated full-site read+verify pass
**Scope:** new Astro site (`sites/healing-hands-pt`) vs. scraped original (`healinghandspt.net`), factual accuracy + sourcing of the 51 blog posts, and next-level opportunities.
**Method:** read every page/data file + all 51 blog Source sections; cross-checked the new site against `.scrape-raw/*.html`; WebFetched a representative sample of cited URLs to confirm they resolve and support the claims.

**Bottom line:** The new site is materially MORE complete than the old one (51 blog posts vs. ~10, 6 location pages, 9 service pages, schema, llms.txt, membership funnel). Content carry-over is strong. Sourcing held up across every spot-check. The real opportunity is depth + conversion, not fixing errors. Three concrete content elements from the old site were dropped (see §1). No factual fabrications found (see §2).

---

## 1 · Content gaps vs. the old site

The old site was a thin HighLevel template; the new Astro site supersets it on almost every axis. The following are the *only* real pieces of original content from `healinghandspt.net` that were NOT carried over. None is critical, but each is a genuine miss worth a decision.

### Confirmed gaps (real content on old site, absent on new)
1. **"We Partner With The Pack" — UNR Wolf Pack partnership.** The old homepage carried a "WE PARTNER WITH THE PACK" band (University of Nevada, Reno athletics association). This is a strong local-trust / credibility signal and it is **completely absent** from the new site. *Gate:* confirm the partnership is current/accurate before re-publishing — but if real, it belongs on the homepage trust row and About page.
2. **Podcast appearances (4 linked on old homepage).** The old homepage linked four podcast episodes featuring Jamie: "A PT's advice on what to do before a mastectomy," "How Jamie Pribyl Transformed Her Physical Therapy Practice," "What Healing Hands is All About," "Redefining Physical Therapy and Healing: A Holistic Approach." These are excellent E-E-A-T / authority assets and are **not** anywhere on the new site. Recommend a "Press / Podcasts" strip on About (with real episode URLs — need the links).
3. **Pelvic floor services.** The old blog announced **"Pelvic Floor Services — Now offering pelvic floor services"** (June 2025). The new site has a *blog post* on pelvic pain and lists pelvic work obliquely under visceral mobilization, but pelvic floor is **not a listed service** in `practice.json` / `/services`. If she still offers it, it should be a service page (it's a high-intent, under-served local search term). *Gate:* confirm she still provides it.

### Old elements intentionally retired (correct — noted for completeness, not gaps)
- **Lead magnet "Low Back Pain Free" form** (`/low-back-pain-free`, `-9846`) and **"Playbook"** page — both were empty/funnel stubs; redirected in `_redirects` to `/services/physical-therapy` and `/services`. Fine, but the *idea* (a low-back-pain lead magnet) is worth rebuilding as a real asset (see §3 P2).
- **Legal pages** (website-disclaimer, terms&conditions) — currently 302'd to `/`. **Action needed:** rebuild real Privacy Policy + Terms pages before cutover (a cash-pay healthcare site sending SMS consent language — see contact form — should not 302 its privacy/terms to the homepage). Flagged P1 in §3.
- "Health Path" nav item — was a HighLevel app link, correctly dropped.

### Content that WAS carried over correctly (verified present)
Services/modalities (all 9 + the "techniques" list incl. PNF, joint mobilization, exercise education on About), full conditions list (16, verbatim), Dr. Jamie bio + education (verbatim), hours, NAP, fax, after-hours policy, mobile-visit advantage, "not dictated by insurance" copy, superbill language, all 6 "concierge difference" bullets, the Bronze Best-of-Sierra-Nevada award, dry-needling-≠-acupuncture education, all social links (FB/IG/TikTok/YouTube), and every transcribed testimonial. The old site's "Advantages" section (mobile visits, comfortable spa-like clinic, practitioners network, immediate/same-day appointments) is preserved across the About concierge grid + membership page.

---

## 2 · Accuracy & sourcing findings

**Verdict: clean.** No fabricated facts, no fabricated stats, no dead source links found in the sample. Medical claims are notably cautious and well-hedged. Details below.

### Business facts (NAP / credentials / hours) — all match ground truth
- **Phone (775) 452-4471, fax (888) 669-0176, email Admin@healinghandspt.net** — match the dominant old-site values; the stale JSON-LD number was already dropped (documented in `practice.json._nap_note`). ✅
- **Address 9460 Double R Blvd #104, Reno NV 89521** — matches old site verbatim. ✅
- **Hours** (M/T/F 9–4, Thu 9–3, closed Wed/Sat/Sun, after-hours on request) — match old contact page exactly, including the Thursday-to-3PM detail and after-hours policy. ✅ Schema `OpeningHoursSpecification` correctly converts to 24h and only emits the four open days.
- **Dr. Jamie credentials (PT, DPT, MTC), education (UNR B.S. Health Ecology; DPT 2010 + MTC 2012, Univ. of St. Augustine), 15+ years, native Nevadan, two boys** — verbatim match to old About page. ✅
- **Award:** "Voted Bronze — Best of Sierra Nevada (Physical Therapy)" — matches old homepage ("voted Bronze"). ✅ Not inflated.
- **Service areas:** Reno, Sparks, Carson City, Incline Village (in data/schema) — matches old site. New site *adds* Truckee + Lake Tahoe location pages; llms.txt correctly distinguishes these as in-clinic-only (no mobile), which is honest. ✅

### JSON-LD schema (`SchemaMarkup.astro`) — accurate
- **AggregateRating uses the REAL Google aggregate (4.9 / 86)** pulled via Places API (`placeId ChIJYYuO27gTmYARpNK7BPytuQg`), documented and not fabricated. ✅ Individual `Review` nodes are real attributed 5-star Google reviews from `testimonials.json`. ✅
- `availableService` maps the 9 real services to `MedicalProcedure`; `areaServed` maps the 4 real cities; `Person`/`Physician` node for Jamie with real `alumniOf` + `knowsAbout`. ✅
- ⚠️ **Minor schema nit:** `alumniOf` maps each *education string* (e.g. "Doctorate of Physical Therapy — University of St. Augustine (2010)") to an `EducationalOrganization` `name`. The org name should be just "University of St. Augustine for Health Sciences," not the degree string. Cosmetic, but worth normalizing (low priority).
- ⚠️ **Stale Place ID still present:** `practice.json.placeId` (top-level) = `ChIJE1UTaBMVmYARCgBGyaL81cc` is the STALE one (returns `{}`); the correct one lives in `reviews.placeId`. `SchemaMarkup` correctly prefers `reviews.placeId` for `hasMap`, so output is right — but the dead top-level `placeId` should be removed to avoid a future footgun.

### Blog sourcing — spot-checked ~10 posts, fetched 8 cited URLs
Every post (51/51) has a "Sources" section. Sampled posts cite authoritative sources only: Cleveland Clinic, AAOS OrthoInfo, ChoosePT/APTA, JOSPT, NIDCR, and PubMed/PMC systematic reviews & RCTs. **Verified live (HTTP 200 + claim supported):**
- Tennis elbow "more than 9 in 10 develop it for other reasons" → Cleveland Clinic page: **confirmed verbatim.** ✅
- Tennis elbow "80–95% succeed with nonsurgical treatment" → AAOS OrthoInfo: **confirmed verbatim.** ✅
- IT band "up to 12% of running injuries and up to 24% of cycling injuries" + friction-mechanism quote → ChoosePT ITBS guide (`...-itbs` URL): **confirmed verbatim, page resolves.** ✅
- Plantar fasciitis ESWT meta-analysis (Sun J et al., *Medicine* 2017, PMC5403108): **real article, conclusion supported** (FSW effective as alternative after conservative care). ✅
- CST-for-migraine RCT (PMID 37960717, 2023): **real, conclusion supported** (CST effective + safe for migraine intensity/frequency). ✅
- ChoosePT sciatica guide, NIDCR "Less Is Often Best in Treating TMD," Upledger migraines/CST page: **all resolve (200).** ✅
- No 404s found in the sample. (Note: Upledger is a treatment-vendor source, weaker than the peer-reviewed ones, but every CST post pairs it with a real RCT + systematic review and is explicitly hedged.)

### Medical-claims caution — exemplary
Spot-checked all "guarantee/cure" language. The site consistently uses honest, hedged framing: *"not a cure,"* *"not a guarantee for everyone,"* *"the evidence is still developing,"* *"we'll always be straight with you,"* *"not a magic cure,"* and even discloses FDA-clearance scope (e.g. the Achilles post notes ESWT is FDA-cleared for plantar fasciitis & tennis elbow but Achilles use is "outside those original cleared indications"). The StemWave claim is "FDA-listed" (accurate — it is listed, not "approved"). The only "guarantee" in the funnel is the experience-based intro session, exactly as intended. ✅ **No corrective action needed.**

### One sourcing-format inconsistency (minor)
- `cash-pay-vs-insurance-physical-therapy.md` (an older post, 2026-06-01) lists sources as **bare domain names without links** ("choosept.com," "cms.gov," "fda.gov") while all newer posts use real linked URLs with article titles. Not wrong, but inconsistent and weaker for AEO. Recommend backfilling it to the linked-URL format the other 50 posts use.

---

## 3 · Next-level opportunities (P0–P3)

Prioritized for impact. Excludes anything already covered by the round-2 feedback / conversion / referral specs (membership build, StemWave $50 add-on framing, massage-vs-bodywork band, image rehosting, PSI 90+, referral page — all already planned/done).

### P0 — highest leverage, do first
1. **Online booking / scheduler embed.** The biggest conversion gap. Every CTA goes to `/contact` (a form + phone), but the old site had a "Book Now" scheduler and the entire funnel is built around the $150 intro. Embed a real self-serve booking widget (the old HighLevel/LeadConnector calendar, or Calendly/Cal.com) on `/contact` and as the primary hero CTA. A form that emails is materially lower-converting than "pick a time now." *(Gate: get the scheduler URL from the client.)*
2. **Legal pages (Privacy Policy + Terms).** Currently 302'd to `/`. The contact form collects PII and presents SMS-consent language ("you consent to receive phone calls and/or text messages… Reply STOP") that explicitly links to "Privacy policy and Terms of service" — which don't exist. This is a compliance + trust gap (and TCPA-adjacent). Build real pages before cutover.
3. **Fix the stale top-level `placeId` in `practice.json`** (remove `ChIJE1UTaBMVmYARCgBGyaL81cc`; it returns `{}`). Low effort, prevents a future schema/maps regression.

### P1 — conversion + trust depth
4. **Surface the dropped trust assets (§1):** UNR "Partner With The Pack" badge (if current), the 4 podcast episodes as a "Featured / Press" strip on About, and a Google-reviews count badge that links out. These are zero-content-cost credibility wins already proven on the old site.
5. **Add review-schema-eligible testimonials page depth + a "Leave a review" funnel.** The homepage already has the Google badge; add a lightweight post-visit review-request flow (ties to the retention/referral goal). Keep it compliant — never reward Google reviews (already noted in referral spec).
6. **Pelvic floor service page** (if still offered) — high-intent, low-competition local term; currently only a blog post exists.
7. **Rebuild the "Low Back Pain" lead magnet as a real asset** (the old `/low-back-pain-free` is a dead 302). A genuine downloadable "5 things to do before back surgery" PDF → email capture feeds the funnel and the membership retention play. Low-back is her strongest testimonial theme (Jeff, the spinal-stenosis story).
8. **First-visit / "what to expect" + insurance-superbill explainer on `/contact`.** Reduce booking friction by answering "will my PPO reimburse me?" right at the point of conversion (the superbill blog post exists — surface its gist inline).

### P2 — content depth + topical authority
9. **Deepen the 9 service pages.** They're thin (207–547 words; cupping 207, myofascial 227, visceral 252). Each should hit ~600–900 words with its own FAQ block + FAQPage schema + internal links to the matching condition blog posts. This is the cheapest topical-authority and AEO win available.
10. **Build condition hub pages / a `/conditions` index.** There are 30+ condition blog posts but no condition taxonomy page. A `/conditions` hub (and per-condition landing pages for the top 5: low back, knee, shoulder, neck, sciatica) would consolidate internal-link equity and capture "[condition] physical therapy reno" head terms that blog posts currently scatter.
11. **Internal-linking pass.** Service pages, location pages, and blog posts under-link to each other. Add contextual links: every condition post → relevant service page + relevant location page; every service page → its 2–3 condition posts. (The blog→service links are decent; service→blog and location→blog are sparse.)
12. **Backfill `cash-pay-vs-insurance-physical-therapy.md` sources to linked-URL format** (§2) for consistency + AEO.

### P3 — SEO/AEO, local, technical polish
13. **Add `Service` + `FAQPage` schema to each service page** (only the homepage and membership emit FAQ/breadcrumb schema today; service and location pages don't emit FAQPage even though location pages have `faqs` frontmatter). The location-page FAQs in particular are sitting unused in schema — easy AEO win.
14. **`BreadcrumbList` schema sitewide** (services, locations, blog) — only `/membership` has it now.
15. **Deepen `llms-full.txt`** — it's only 55 lines (nearly identical to `llms.txt`). For AEO it should be the *expanded* version: full service descriptions, the conditions→service mapping, pricing detail, the dry-needling-vs-acupuncture explainer, and per-area drive times. Right now it's not earning its "full" name.
16. **GBP / citation alignment** (off-site, post-onboarding): ensure GBP categories include "Physical Therapy Clinic," services list mirrors the 9 service pages, and NAP exactly matches the site (the audit-baseline already flags no GBP data connected). Build/clean NAP citations (the baseline notes DA 11 — citation consistency is the fastest local-authority mover).
17. **Accessibility/UX:** Lighthouse a11y was 91 (baseline). The heavy emoji use as semantic icons (service grid, concierge grid) needs `aria-hidden`/labels; verify `<details>` FAQ accordions are keyboard-traversable; confirm color contrast on the `text-slate-400`/`slate-500` body text passes AA on the bone/sand backgrounds.
18. **Performance gate** (already P-something in round-2): confirm PSI 90+ after images settle — `Pic.astro`/sharp AVIF/WebP, explicit dimensions, LCP preload. The hero `<Pic eager>` is set; verify below-fold images lazy-load and the parallax JS isn't blocking.

---

## Appendix — what was checked
- Read: `practice.json`, `testimonials.json`, `index/about/contact/membership/testimonials/services-index` pages, `SchemaMarkup.astro`, `ContactForm.astro` + `api/contact.ts`, `llms.txt`/`llms-full.txt`, `robots.txt`, `_redirects`, all 6 location MDs, all 9 service MDs, Source sections of all 51 blog posts, sampled 10 posts' bodies.
- Compared against: `.scrape-raw/{home,about,services,contact,testimonials,blog,low-back-pain-free}.html` + `sitemap.xml`.
- WebFetched (live, 200 + claim-supported): Cleveland Clinic tennis-elbow, AAOS tennis-elbow, ChoosePT sciatica, ChoosePT ITBS, PMC5403108 (plantar ESWT), PMID 37960717 (CST migraine RCT), NIDCR TMD, Upledger CST.
- Cross-referenced existing specs (audit-baseline, round2-feedback, conversion, referral-offers) to avoid re-recommending planned work.
