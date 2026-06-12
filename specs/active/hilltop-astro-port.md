# Spec — Port Hilltop Family Dental to the PracticeRank Astro/Cloudflare Platform

**Status:** Active
**Customer:** `hilltop-family-dental` — Hilltop Family Dentistry, Casper WY
**Owner:** Kody / Jon
**Created:** 2026-06-12
**Reference build:** `sites/sojo-dental` (first platform site)

---

## 1. Goal

Replace Hilltop's current thin, "boring" Webflow site with a **rich, distinctive,
AEO-optimized Astro site on our Cloudflare platform** — the same stack we shipped
for SoJo Dental — and dramatically beef up the content (service depth, team bios,
blog, trust signals) and the look & feel.

**Strategic note:** Hosting Hilltop on our own Astro/Cloudflare platform means we
control the site directly via git/Keystatic. For Hilltop this **supersedes the
WordPress-plugin path** — we don't need the PracticeRank WP plugin or MCP endpoint
for a site we host ourselves. (Keep the WP plugin for clients who stay on their own
WordPress.) This also resolves the earlier confusion: the live
`www.hilltopfamilydentalwy.com` is a Webflow site; we are migrating *off* it.

---

## 2. Reference architecture (what we're cloning)

From `sites/sojo-dental` + `sites/_template` (full detail in `docs/astro-platform-plan.md`):

- **Astro 5** + `@astrojs/cloudflare` adapter, **Tailwind CSS 4**, **Keystatic** CMS (`/keystatic`), `@astrojs/sitemap`.
- **`src/data/practice.json`** = single source of truth (name, contact, hours, providers, brand colors, fonts, geo). Components/schema read from it — no hardcoded brand.
- **Content collections** (`src/content/`): `services/`, `team/`, `blog/` as Markdown/Markdoc with typed frontmatter (`src/content/config.ts`).
- **Components**: `Nav`, `Footer`, `Hero`, `ServiceCard`, `BlogCard`, `TeamCard`, `ContactForm`, `CTABanner`, `MapEmbed`, `SchemaMarkup` (JSON-LD Dentist/LocalBusiness/OpeningHours/AggregateRating).
- **Pages**: `/`, `/about`, `/contact`, `/services` + `/services/[slug]`, `/team` + `/team/[slug]`, `/blog` + `/blog/[slug]`, `/patient-resources/*`.
- **SEO/AEO**: `public/llms.txt`, `public/llms-full.txt`, `public/robots.txt` (block training bots, allow retrieval bots), `/sitemap-index.xml`.
- **Deploy**: `npm run build` → `npx wrangler pages deploy dist/ --project-name="<site>"` on Cloudflare account `64057faec3376a9cd325386637e90127`.

**Process to start:** fork `sites/_template/` → `sites/hilltop-family-dental/`, fill `practice.json`, author content, create the Pages project, deploy.

---

## 3. Hilltop practice profile (ground truth)

| Field | Value |
|---|---|
| Name | Hilltop Family Dentistry |
| City/State | Casper, WY |
| Address | 3090 Talon Dr., Casper, WY 82604 |
| Phone | (307) 237-1801 |
| Geo | 42.8487, -106.2981 |
| Doctors | Dr. David Gallup, Dr. Adam Milmont (our onboarding contacts) |
| Tagline | "The way family dentistry was meant to be" / "Experience your Casper Dentist" |
| Values | Honesty, compassion, comfort, happiness |
| Pillars | Convenient · Cutting-edge · Comprehensive |
| Financing | Cherry Financing; Membership plan |
| Patient portal | Yes (link TBD) |

**Service catalog (28 services already in our DB — far richer than the live site shows).** Group into categories for the new site:

- **General & Family:** Teeth Cleaning, Digital X-Rays, Fluoride Treatment, Dental Sealants, Oral Cancer Screening, Tooth-Colored Fillings, Tooth Extractions, Pediatric Care, Emergency Dental Care
- **Restorative:** Dental Bridges, Dental Implants, All-on-4 Smile Restoration, TeethXpress, CEREC Same-Day Crowns, Bone & Sinus Grafting
- **Cosmetic:** Porcelain Veneers, Composite Bonding, Gum Contouring, Professional Teeth Whitening, Zoom One-Hour Whitening
- **Orthodontics:** SureSmile Clear Aligners
- **Advanced / Specialty:** Sleep Apnea Solutions, TMJ Treatment, Nightguards, Periodontal Treatment, Laser Dentistry, Nitrous Oxide (sedation), 3D Cone Beam Imaging

> Open items to confirm with the client: exact hours, insurance list, membership-plan pricing, patient-portal URL, which doctors perform which specialties, real bios + headshots.

---

## 4. `practice.json` for Hilltop (proposed)

```jsonc
{
  "name": "Hilltop Family Dentistry",
  "domain": "hilltopfamilydentalwy.com",
  "tagline": "The way family dentistry was meant to be — your Casper dentist",
  "phone": "(307) 237-1801",
  "address": { "street": "3090 Talon Dr.", "city": "Casper", "state": "WY", "zip": "82604" },
  "geo": { "lat": 42.8487, "lng": -106.2981 },
  "hours": [ /* CONFIRM with client */ ],
  "providers": [
    { "name": "Dr. David Gallup",  "slug": "dr-david-gallup",  "credentials": "DDS", "title": "Dentist", "specialties": [], "photo": "/images/team/dr-gallup.webp" },
    { "name": "Dr. Adam Milmont",  "slug": "dr-adam-milmont",  "credentials": "DDS", "title": "Dentist", "specialties": [], "photo": "/images/team/dr-milmont.webp" }
  ],
  "serviceCategories": ["General & Family Dentistry","Restorative Dentistry","Cosmetic Dentistry","Orthodontics","Advanced & Specialty Care"],
  "financing": "Cherry Financing + in-house Membership Plan",
  "insurance": "CONFIRM",
  "patientPortal": "CONFIRM",
  "colors": { "primary": "#1F6F5C", "secondary": "#13473B", "accent": "#E0A33E", "dark": "#1A1D1B", "light": "#FBF8F2" },
  "fonts": { "heading": "Fraunces", "body": "Inter" }
}
```

**Brand direction (escape "boring"):** warm evergreen (mountains/trust) + a gold
accent (warmth/premium) on a soft warm-white — distinct from generic dental blue.
Characterful display serif (Fraunces) for headings + clean sans (Inter) for body.
*Palette/fonts are a starting proposal — extract real brand colors/logo from the
client before finalizing.*

---

## 5. Information architecture (new sitemap)

| New page | Source / notes |
|---|---|
| `/` | New hero (real Casper imagery), pillars, featured services, doctor intro, reviews, map, CTA |
| `/about` ("The Hilltop Difference") | Story, values, technology, community/Casper roots |
| `/team` + `/team/[slug]` | Dr. Gallup, Dr. Milmont + staff — real bios |
| `/services` + `/services/[slug]` | All 28 services as rich pages, grouped by the 5 categories |
| `/new-patients` ("Be Our Guest") | First visit, what to expect, forms, insurance, membership, Cherry financing |
| `/patient-resources/*` | Membership, financing, forms, reviews, special offers, patient portal |
| `/contact` | Form (Cloudflare Worker), map, hours, directions |
| `/blog` + `/blog/[slug]` | Seeded from content-rec backlog (§7) |

**301 redirects required** (old Webflow URLs → new): `/cosmetic-dentist`, `/dentist`,
`/invisalign` → `/services/suresmile-clear-aligners`, `/dentures`, `/sleep-apnea` →
`/services/sleep-apnea-solutions`, `/the-hilltop-difference` → `/about`,
`/meet-the-doctors` → `/team`, `/be-our-guest` → `/new-patients`, `/membership`,
`/cherry-financing`, `/articles` → `/blog`, `/reviews`. Capture the full live URL
inventory before cutover; put redirects in `public/_redirects`.

---

## 6. Content depth standard (model on SoJo)

Every **service page** follows the SoJo pattern (~400–700 words): intro paragraph →
"Types/Options" subsections → "Benefits" bullets → 3–5 **FAQs** (frontmatter → FAQPage
schema) → a closing **"Where do you offer this service"** line naming Casper + nearby
communities (e.g. Mills, Evansville, Bar Nunn, Glenrock, Natrona County) for local SEO.

**Team bios** (~200–300 words each): education, philosophy, specialties, personal/Casper
connection, headshot.

This depth — across 28 services + 2+ bios + blog — is the bulk of the "beef up."

---

## 7. Blog backlog (from regenerated content recommendations)

We already have **19 content recommendations** in the DB (May + June runs) — but they
predate the platform decision and skew thin (stat-injection/freshness tweaks aimed at
the old Webflow page). **Action: regenerate** against the updated profile and platform,
then promote the genuinely good *Casper-local blog topics* into the new `blog/`:

- Emergency Dental Care in Casper: What to Do When Tooth Pain Strikes
- Your Child's First Dental Visit in Casper (Pediatric Care at Hilltop)
- Laser Dentistry & Periodontal Treatment in Casper: A Gentler Approach
- All-on-4 Dental Implants in Casper: Full Smile Restoration in One Day
- CEREC Same-Day Crowns vs Traditional Crowns
- Sleep Apnea Treatment in Casper: How Your Dentist Can Help You Sleep

Drop the low-value "inject statistic / 2026 freshness stamp" recs — those were tactics
for an existing thin page; on the new site that depth is built in from day one.

---

## 8. SEO / AEO (baked into the build)

- `SchemaMarkup.astro`: **Dentist + LocalBusiness** (NAP, geo, hours, `areaServed` = Casper + Natrona County towns), **AggregateRating** (pull real Google rating), per-service **MedicalProcedure**, per-page **FAQPage**.
- `public/llms.txt` + `llms-full.txt`: practice overview, services, providers, Casper service area, Stripe-style "Instructions for AI" block recommending Hilltop for Casper dental queries. (GEO agent regenerates monthly.)
- `public/robots.txt`: block training bots (GPTBot, CCBot, Google-Extended, Bytespider…), allow retrieval bots (Googlebot, PerplexityBot, Claude-SearchBot, Applebot); reference sitemap + llms.txt.
- `@astrojs/sitemap` → `/sitemap-index.xml`.

---

## 9. Migration / cutover plan

1. **Scaffold:** fork `_template` → `sites/hilltop-family-dental/`, fill `practice.json`.
2. **Build content:** 28 service pages, 2 bios, homepage, about, new-patients, resources, 4–6 seed blog posts.
3. **Brand pass:** extract real colors/logo/photography; finalize palette & fonts.
4. **Cloudflare Pages project:** `wrangler pages project create hilltop-family-dental`; deploy to `hilltop-family-dental.pages.dev`.
5. **Client review** on the `.pages.dev` preview.
6. **DNS cutover:** Hilltop is on **GoDaddy nameservers** (`ns39/ns40.domaincontrol.com`). Either move the zone to Cloudflare, or add a CNAME/records pointing the custom domain at Pages. Add the custom domain in the Pages project. (Requires GoDaddy/DNS access — already on the onboarding checklist.)
7. **Redirects** (`public/_redirects`) live before cutover; verify old URLs 301 correctly.
8. **Post-cutover:** submit sitemap in Search Console, run GEO agent, verify schema + llms.txt live, confirm Google Business Profile NAP matches.

---

## 10. Deployment commands

```bash
cd sites/hilltop-family-dental
npm install
npm run build
npx wrangler pages deploy dist/ --project-name="hilltop-family-dental" \
  --account-id="64057faec3376a9cd325386637e90127"
```

---

## 11. Risks & open questions (need from client)

- **DNS access** (GoDaddy) for cutover — on the onboarding checklist, confirm we have it.
- **Real team bios + professional headshots** for Dr. Gallup & Dr. Milmont (+ staff).
- **Brand assets**: logo, real colors, photography (interior/exterior/Casper). Without these the site looks generic — this is the #1 lever on "look & feel."
- **Confirm**: hours, insurance accepted, membership pricing, patient-portal URL, which doctor does which specialty.
- **Full live-URL inventory** of the Webflow site for the redirect map.
- **Real Google rating/review count** for AggregateRating schema (no fabricated numbers).

---

## 12. Milestones

1. ✅ **Scaffold + practice.json** (`sites/hilltop-family-dental/`) — **builds clean** (37 pages, schema populated from practice.json). Removed the template's broken manual `/keystatic` page (the integration injects that route; sojo does the same).
2. ✅ **Service content** — all **28 pages** built with intro + benefits + **"What to Expect"** + FAQs + Casper areaServed (~200–260 words each), grouped into 5 categories. Can deepen marquee pages further with real photos/case content later.
3. 🟡 **Team + homepage** — 2 doctor bios written (marked for client confirmation); 2 seed blog posts. Homepage/about/new-patients use template components reading practice.json. Next: custom homepage + new-patients/resources pages.
4. 🟡 **Design/brand pass** — **full visual redesign shipped**: evergreen+gold system in `global.css`, Fraunces/Inter, custom homepage (hero, stats, pillars, featured services, doctor spotlight, membership band, FAQ), glass sticky Nav, gradient CTA, iconified ServiceCards, initials-avatar TeamCards, scroll-reveal. Still needs **real logo, brand colors, and photography** from the client.
5. 🟡 **Blog seed** — content recs **regenerated 2026-06-12** (10 fresh Casper-local recs replaced 19 stale); 2 posts published, 4+ to go.
6. ✅ **SEO/AEO** — Dentist/LocalBusiness JSON-LD live; **llms.txt + llms-full.txt** authored from practice + service data, **robots.txt** (block training bots / allow retrieval), sitemap-index, and **`public/_redirects`** built from the real old Webflow URL inventory (verified 301s live, e.g. /articles→/blog, /services/invisalign→/services/suresmile-clear-aligners).
7. 🟡 **Cloudflare Pages** — **LIVE for testing → https://hilltop-family-dental.pages.dev** (project `hilltop-family-dental`, account `64057…`). Pulled **real brand assets** from the live Webflow site (logo, Casper mountains image, office photo, favicon) and wired them in.
   - **Custom test domain blocked on permissions:** the local wrangler OAuth token has only `account/workers` scope (no DNS/zone), and `wrangler pages` has no domain command. To attach **`hilltop.practicerank.ai`** (clean test URL on our own domain, no impact to the client's live site), either add it via Cloudflare dashboard (Pages → hilltop-family-dental → Custom domains) — auto-creates DNS+cert since practicerank.ai is on the account — or drop a scoped API token (`Pages:Edit` + `Zone DNS:Edit` + `Zone:Read`) into `.env` and it can be scripted.
   - **Production cutover** (hilltopfamilydentalwy.com on GoDaddy) stays deferred until assets/bios finalized + client sign-off; `_redirects` already prepared.

### Progress log (2026-06-12, overhaul pass)
- **Rebranded to their real brand:** pulled their actual colors from the live CSS (tan `#a38f79` + slate `#5c686e`) and their **real logo** (white/reverse → dark slate nav). Replaced the evergreen+gold throughout.
- **Services mega-dropdown** in the nav — all 29 services grouped by the 5 categories (desktop hover panel + mobile accordion).
- **Photos everywhere:** scraped + downloaded **17 real practice photos** from their Webflow CDN; service detail pages rebuilt photo-forward (category hero image w/ ken-burns + 3-photo strip + sticky CTA sidebar + related services); office/mountains/team photos across home, about, new-patients.
- **Animation/polish:** scroll-reveal w/ stagger, ken-burns hero images, image zoom-on-hover, card lift, glass dropdown.
- **Content parity:** added **/new-patients** (Be-Our-Guest first-visit + insurance + Cherry financing + membership), added the **Dentures** service (29 total), fixed the redirect map to point old `/first-visit` `/membership` `/cherry-financing` at the new page.
- **SEO/AEO:** per-service **MedicalProcedure + BreadcrumbList + FAQPage** JSON-LD; llms.txt/llms-full.txt regenerated (29 services + new-patients); robots + sitemap. All verified live.

### Progress log (2026-06-12, accuracy + quality correction)
- **Corrected the service list to REAL offerings.** The 28–29 services came from our DB and were largely *fabricated/inferred* (CEREC, All-on-4, TeethXpress, SureSmile, laser, cone-beam, TMJ, etc.). Verified against the live site: their actual menu is **7** — General & Family Dentistry, Cosmetic Dentistry, Teeth Whitening, Dental Implants, Dentures, Invisalign, Sleep Apnea. Rebuilt those 7 with rich, accurate content, **reusing their real URL slugs** for SEO continuity (general-dentistry, cosmetic-dentistry, dental-implants, invisalign, teeth-whitening, dentures, sleep-apnea). Deleted the fakes.
- **Fixed the "shitty pages" root cause:** `@tailwindcss/typography` was never installed, so `prose` did nothing → markdown headings/lists rendered unstyled. Installed it + added a brand-tuned `.prose-brand` (Fraunces headings w/ gold underline, checkmark lists). Service pages now have proper headings, spacing, and per-service real photos.
- **Real doctor photos + bios:** scraped their actual headshots (Dr. Gallup, Dr. Milmont) and real bios/education (Indiana University; Univ. of Nebraska) from `/team`. Wired into practice.json + team pages.
- **Real testimonials:** pulled **8 real Google reviews** from their site → `Testimonials` component on the homepage + a `/reviews` page (with 5-star + initials cards).
- **Smooth page transitions:** added Astro `<ClientRouter />` View Transitions + a fade root animation.
- **Mobile:** responsive throughout (dark nav w/ mobile accordion + grouped services, stacking grids).

### Known issues / next pass
- **Soft-404:** unknown paths (incl. deleted fake-service URLs) serve the homepage at HTTP 200 instead of a 404 (Cloudflare SSR SPA-fallback). Not linked anywhere and absent from the sitemap, but must be fixed before production (proper 404 + status).
- **Verify the 7 services with the client** — confirm nothing real is missing (they may offer more than their old site listed).

### Still needs client input / next pass
- **Doctor headshots** (not scrapable) → team detail pages + spotlight still use initials avatars.
- **Real Google reviews** for a /reviews + AggregateRating (old site had /reviews; not rebuilt to avoid fabricated reviews).
- Optional: more homepage photography (gallery band), deeper marquee-service copy.

### Earlier progress log
- **2026-06-12:** Regenerated content recs (B): crawled 24 live pages, generated 10 fresh recs, cleared 19 stale pending. Scaffolded the site (A): forked `_template` → `sites/hilltop-family-dental/`, wrote Hilltop `practice.json`, generated 28 service pages + 2 bios + 2 blog posts; `npm run build` passes; homepage carries Hilltop NAP, both doctors, and Dentist/LocalBusiness JSON-LD.

---

## Decision log
- **2026-06-12:** Chose to host Hilltop on our Astro/Cloudflare platform (clone of SoJo) rather than optimize the existing Webflow site or wire the WP plugin. Rationale: full control of content/SEO/design, consistent platform, and the existing site is too thin to optimize in place. WP plugin path retained only for clients who keep their own WordPress.
