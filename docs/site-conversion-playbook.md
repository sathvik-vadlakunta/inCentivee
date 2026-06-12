# PracticeRank Site Conversion Playbook

**Purpose:** A repeatable, best-practices process for converting a client's existing
website (Webflow, WordPress, Squarespace, etc.) into a new, modern, AEO-optimized site on
the PracticeRank **Astro + Cloudflare Pages** platform — with enough real, per-client data
that no two sites feel cookie-cutter.

> First implementation: **Hilltop Family Dentistry** (Casper, WY), June 2026. Reference
> build: `sites/sojo-dental` and `sites/hilltop-family-dental`. This playbook generalizes
> everything we learned doing it by hand so it can become a skill / chain of skills.

---

## 0. Guiding principles

1. **Real data only — never fabricate.** Services, stats, reviews, bios, photos, hours,
   pricing all come from the client's real site or verifiable public sources. Fabricated
   content is the #1 failure mode (see §7, Hilltop's 29→7 services correction).
2. **Verify, don't trust the pipeline.** Our `practicerank.db` had ~29 inferred services;
   the practice only offered 7. Always reconcile against the live site.
3. **Real data is what creates variety.** The template gives structure; the client's own
   brand, photos, services, reviews, and bios make each site unique (see §8).
4. **Source everything for AEO.** Cited, authoritative content is what gets a site
   recommended/"backlinked" by AI engines. Allow AI crawlers; don't block them.
5. **Ship → verify on the live URL.** Every change is built, deployed, and curl-verified —
   soft-404s and caching hide bugs (see §6).

---

## 1. The platform (what we're building onto)

| Layer | Choice |
|---|---|
| Framework | **Astro 5** (`output` static; `@astrojs/cloudflare` adapter) |
| Styling | **Tailwind CSS 4** + **`@tailwindcss/typography`** (REQUIRED — see §6) |
| CMS | **Keystatic** (`/keystatic`) |
| SEO | `@astrojs/sitemap`, hand-authored `llms.txt`/`robots.txt`, JSON-LD |
| Hosting | **Cloudflare Pages** (free, global CDN) |
| Brand fonts | Per-client (e.g. Fraunces + Inter); loaded in `Base.astro` |
| Source of truth | `src/data/practice.json` (+ `global.css` for brand colors — see §6) |

Per-customer dir lives in `sites/<slug>/`. Fork from `sites/_template/`.

---

## 2. Phase-by-phase process

### Phase A — Discovery & scrape (the most important phase)

Scrape the client's live site and public profiles to gather **ground truth**. Capture:

| What | Where to find it |
|---|---|
| **Real business facts** (name, address, phone, geo, hours) | Homepage, schema/JSON-LD, contact page, Google Business Profile |
| **Real service menu** | Site nav + `/sitemap.xml` service URLs (NOT our DB) |
| **Real service descriptions** | Each service page |
| **Doctors/team** (names, bios, education, photos) | `/team` (or "meet the doctors") page; verify via Healthgrades/WebMD/ADA |
| **Reviews/testimonials** | The site's reviews page; rating+count from Google/Birdeye |
| **Brand colors** | The site's CSS (`--brand-*`, `--tan`, etc.) |
| **Logo (all variants)** | `<img>` with "logo" in URL; grab reverse/white + dark |
| **Photography** | Crawl EVERY page (service pages have service-specific shots) |
| **Hero video** | `data-video-urls` / `.mp4`/`.webm` on homepage |
| **Tracking IDs** | grep homepage for `G-`, `GTM-`, `UA-`, `google-site-verification`, FB pixel |
| **Patient portal + socials** | Footer/header external links |
| **Membership/financing details** | Membership/financing pages (real tiers + pricing) |
| **Full old-URL inventory** | `/sitemap.xml` (for the 301 redirect map) |

**Scrape commands that worked** (run from a host with `curl`, e.g. the droplet):

```bash
# image assets across all pages
curl -sL "$URL/page" | grep -oE 'https://cdn[^"]+\.(jpg|png|webp|svg|mp4|webm)' | sort -u
# brand color vars
curl -sL "$CSS_URL" | grep -oE '\-\-[a-z-]+:\s*#[0-9a-f]{6}'
# tracking
curl -sL "$URL/" | grep -oE 'G-[A-Z0-9]{8,}|GTM-[A-Z0-9]{5,}|google-site-verification" content="[^"]+'
# old URL inventory
curl -sL "$URL/sitemap.xml" | grep -oE '<loc>[^<]+</loc>'
```

Download assets with Node `fetch` (works without curl on PATH):
```js
const r = await fetch(url, { headers: { 'User-Agent': 'Mozilla/5.0' } })
await writeFile(dest, Buffer.from(await r.arrayBuffer()))
```

**⚠️ Do NOT scrape LinkedIn** — it requires auth, blocks bots, and violates ToS. Use the
client's site + public directories (Healthgrades, WebMD, ADA, BBB) for bios.

### Phase B — Scaffold + `practice.json`

1. `rsync -a --exclude node_modules --exclude dist sites/_template/ sites/<slug>/`
2. Rename `package.json` name.
3. Fill `src/data/practice.json`: name, domain, tagline, phone, address, geo, hours,
   providers (with real photos + education), serviceCategories, financing, insurance,
   social, patientPortal, areaServed, analytics (gtm/ga4/gsc), reviews (rating/count),
   financingUrl, mapsApiKey.

### Phase C — Brand

- **Set colors in `global.css` `:root`** (NOT just practice.json — see §6 gotcha) using the
  client's real palette. Map them through `@theme`.
- Load the client's real **logo** (reverse on dark nav/footer) + **favicon**.
- Pick a font pairing that fits the brand (display serif + clean sans is a safe, premium
  default — vary it per client for §8 variety).

### Phase D — Content (real services only)

- Create one `src/content/services/*.md` per **verified** service. **Reuse the client's real
  URL slugs** for SEO continuity (so old `/services/x` maps 1:1).
- Each service page: intro, "what's included", **What to Expect**, **sourced stat** where one
  exists (CDC/ADA/AAID/AASM), 4–5 **FAQs** (→ FAQPage schema), local `areaServed` line.
- Team `*.md`: real bios + education + real headshots.
- Blog: 5–8 posts that **map 1:1 to the real services**, each ~700+ words, featured image,
  4–5 FAQs, **real citations**, internal links, spread `pubDate`s.

### Phase E — Assets into the design

- Hero: real **office photo** or **hero video** (autoplay/muted/loop/playsinline + poster).
- Service heroes: the **service-specific** photo (before/after on cosmetic, snoring couple on
  sleep apnea, etc.).
- Homepage **gallery** of office candids; team **headshots** (`object-top`, see §6).

### Phase F — SEO / AEO

- JSON-LD: **Dentist + LocalBusiness** (NAP, hours, geo, areaServed, **AggregateRating** from
  real Google rating), per-service **MedicalProcedure + Breadcrumb + FAQPage**, **BlogPosting +
  FAQPage** on posts.
- **`llms.txt` + `llms-full.txt`** (overview, services as links, providers, rating, an
  "Instructions for AI assistants" block).
- **`robots.txt`** — **allow AI crawlers** (GPTBot, Google-Extended, ClaudeBot, PerplexityBot,
  OAI-SearchBot, CCBot…). Blocking them works against AEO. Reference the sitemap.
- **Sitemap** with `lastmod` + `changefreq`.
- **`public/_redirects`** — 301 every old URL to its new equivalent.
- **`404.astro`** (REQUIRED — see §6 soft-404).
- Analytics: reuse the client's existing **GTM** container (carries GA4 + pixel); wire
  `practice.json.analytics`. Add GTM events for `form_submit` + `click_to_call`.

### Phase G — Conversion / marketing

- Real **Google rating badge** (e.g. "4.7 ★ · 1,100+ reviews") + AggregateRating schema.
- Reviews **near every CTA**; a "See all on Google" card to fill the grid.
- **Local-SEO area pages** (`/dentist/<town>`) with drive time + text directions + route map.
- **Cherry financing** CTA near treatment buttons; membership tiers page.
- Sticky mobile call/book bar (recommended), count-up stats (recommended).

### Phase H — Build, deploy, verify

```bash
npm install && npm run build
npx wrangler pages deploy dist --project-name=<slug> --branch main --commit-dirty=true
```
Then **curl-verify on the production alias** (not the random hash): status codes, brand
colors in CSS, schema present, redirects 301, unknown URL → 404, sitemap complete.

### Phase I — Custom domain / cutover

- Test domain on **our** zone (e.g. `client.practicerank.ai`) — needs a DNS-scoped CF token
  or the dashboard (the local wrangler OAuth lacks zone perms).
- Production cutover (client's registrar → Pages) only after assets/bios finalized + client
  sign-off. `_redirects` already prepared.

---

## 3. QA checklist (run before calling a site "done")

- [ ] Services match the client's **real** menu (no fabricated services)
- [ ] All NAP/phone/hours correct; schema validates
- [ ] Real logo, real brand colors (check built CSS, not just practice.json)
- [ ] Real photos everywhere; **no broken images**, heads not cropped (`object-top`)
- [ ] `@tailwindcss/typography` installed; prose renders with headings
- [ ] `404.astro` exists → unknown URLs return **404**, not the homepage
- [ ] `/team`, `/reviews`, `/blog` index pages exist (no soft-404)
- [ ] View-Transition-safe scripts (`astro:page-load`, not `DOMContentLoaded`)
- [ ] Mobile: nav menu works, no horizontal overflow, tap targets OK
- [ ] Sitemap includes **every** page + `lastmod`; robots allows AI; llms.txt valid
- [ ] 301 redirects from all old URLs verified
- [ ] Blog posts: ~700+ words, image, FAQs+schema, real citations, internal links
- [ ] Reviews: real rating/count + AggregateRating schema
- [ ] Analytics (GTM) loads; form_submit + click_to_call events fire
- [ ] Build + deploy + **curl-verified live**

---

## 4. Issues we hit & the fixes (the gotcha library)

| Symptom | Root cause | Fix |
|---|---|---|
| "These aren't services they offer" | Trusted `practicerank.db` (inferred 29) | **Verify against live site**; rebuild the real ~7, reuse their slugs |
| "Pages look shitty, no headings" | `@tailwindcss/typography` **not installed** → `prose` is a no-op | `npm i -D @tailwindcss/typography` + `@plugin` in global.css + brand-tuned `.prose-brand` |
| Homepage goes blank after navigating | Added View Transitions; reveal script ran on `DOMContentLoaded` (doesn't refire) | Run scripts on **`astro:page-load`** |
| `/team`, `/reviews` "crash" | Missing index page **and** missing `404.astro` → adapter soft-404 serves homepage at 200 | Add the index pages **and** `404.astro` |
| Unknown URLs return homepage (200) | No `404.astro` (Cloudflare adapter fallback) | Add `404.astro` → real 404 status |
| Site is wrong color (blue, not brand) | Brand colors live in **`global.css :root`**, not practice.json | Edit `global.css :root` per client |
| Doctor headshots cropped at the top | `object-cover` centered on landscape box | Portrait aspect + **`object-top`** |
| Service images look random | Used generic category photos | Use the **service-specific** photo from each old service page |
| robots blocked AI (anti-AEO) | Copied a privacy-first robots template | **Allow** GPTBot/Google-Extended/ClaudeBot/etc. |
| Reviews grid had an empty corner | Only ~10 reviews embed on the old site | Fill with a "See all on Google" CTA card; Places API for a live feed later |
| Keyless Google map shows a pin, not a route | Legacy embed can't draw routes reliably | Use **Maps Embed API directions** (free, unlimited) with a restricted key |
| Map cost worry | — | Maps **Embed API is free/unlimited**; Places/Directions/JS APIs are billed |
| Stale plugin/zip artifacts | Re-zip/rebuild after edits | Always rebuild the artifact + re-verify live (caching!) |

---

## 5. Where the data lives (file map)

- `src/data/practice.json` — all business + brand + analytics + reviews config
- `src/styles/global.css` — **brand colors** (`:root`), prose, animations, buttons
- `src/content/{services,team,blog}/*.md` — content collections
- `public/images/` — all real assets (logo, photos, headshots, hero video, gallery)
- `public/{robots.txt,llms.txt,llms-full.txt,_redirects}` — SEO files
- `src/pages/404.astro`, `src/pages/dentist/[location].astro` — required extras
- `astro.config.mjs` — `site` (from practice.json domain) + sitemap config

---

## 6. Critical "always do" list (distilled from the gotchas)

1. **Install `@tailwindcss/typography`** and add `@plugin` to global.css.
2. **Add `404.astro`** every time.
3. **Set brand colors in `global.css :root`**, not just practice.json.
4. **View-Transition scripts on `astro:page-load`**.
5. **Verify the real service menu** against the live site.
6. **`object-top`** on portrait photos.
7. **Allow AI crawlers** in robots.txt.
8. **curl-verify the live production alias** after every deploy (cache-bust with a query
   string; the random-hash deploy URL ≠ the production alias).

---

## 7. Real-data sourcing rules

- **Stats:** only verifiable figures with named sources (CDC, ADA, AAID, AASM, peer-reviewed
  meta-analyses). Link them. Never invent numbers.
- **Reviews:** use the client's real published reviews + real Google rating/count.
- **Bios:** client site + public directories; never LinkedIn scraping.
- **Services:** only what the client actually offers (verify).
- **Photos:** the client's own; if none for a topic, use a tasteful generic from their library
  (don't claim it depicts a specific procedure).

---

## 8. Keeping sites varied (anti-cookie-cutter)

The template is shared, but uniqueness comes from **real per-client inputs** + a few design
knobs:

**Naturally unique per client (from the scrape):**
- Brand palette + logo + fonts (their real brand)
- Their own photography + hero video + headshots
- Their actual service mix (different practices → different pages)
- Their real reviews, bios, hometowns, family details, hours, pricing
- Their city + service-area pages (local content)

**Design knobs to vary deliberately (so layouts differ):**
- Hero style: photo-card vs. video vs. full-bleed image with overlay
- Font pairing (a curated set; pick per brand personality)
- Accent usage, section order, gallery layout (grid vs. masonry), card style
- Homepage section selection (some get a stats band, some a gallery, some a video, etc.)

**Rule of thumb:** if two clients would end up identical, you didn't pull enough of their real
brand/content. The scrape depth is what guarantees variety.

---

## 9. Automation blueprint (the future skill / chain of skills)

Goal: `/convert-site <client-url>` → scaffolded, branded, content-filled, deployed site with
minimal human intervention. Suggested chain:

1. **`scrape-site`** (agent/tool) — crawl the client site + sitemap + GBP; emit a structured
   JSON: business facts, services (+descriptions), team (+bios/photos), reviews, brand colors,
   logo URLs, photo URLs, hero video, tracking IDs, old-URL inventory. *(Human review gate:
   confirm the service list + facts — this is where fabrication risk lives.)*
2. **`fetch-assets`** — download all images/video/logo into `public/images/`; pick
   service-specific heroes; map headshots.
3. **`scaffold-site`** — fork `_template`, write `practice.json` + `global.css` brand from the
   scrape; choose a design variant (hero style / font pairing) deterministically from a seed.
4. **`generate-content`** — services (real menu, reuse slugs, sourced stats + FAQs), team bios,
   N blog posts (mapped to services, with **real researched citations** via web search),
   spread dates.
5. **`seo-aeo`** — schema, llms.txt, robots (allow AI), sitemap, `_redirects` from old URLs,
   `404.astro`, analytics wiring.
6. **`local-seo`** — area pages with drive times + route maps from `areaServed`.
7. **`build-deploy-verify`** — `npm build` → `wrangler pages deploy` → run the §3 QA checklist
   as automated curl assertions; report failures.
8. **`handoff`** — produce a per-client results doc (like `docs/hilltop-rebuild-*.html`),
   list the items needing the client (headshots, GA4/GSC IDs, Cherry URL, Maps key, domain
   cutover).

**Human-in-the-loop gates** (keep these manual): service-list confirmation, final brand/photo
review, domain cutover. Everything else can be automated.

**Skill should encode the §6 "always do" list and §4 gotchas as guardrails/assertions** so the
same bugs never recur.

---

## 10. Per-client open-items template (hand to the client)

- [ ] Confirm the service list is complete
- [ ] Professional **headshots** (if not on the old site)
- [ ] **GA4 Measurement ID / GSC verification** (or confirm they live in GTM)
- [ ] **Cherry financing URL** (`practice.json.financingUrl`)
- [ ] **Maps Embed API key** (free, restricted) for route maps (`practice.json.mapsApiKey`)
- [ ] **Google review link** for "Leave a review" (`practice.json.reviews.googleReviewUrl`)
- [ ] DNS access for domain cutover

---

*Living doc — update after each conversion with new gotchas. Companion: the per-client
results HTML (e.g. `docs/hilltop-rebuild-2026-06-12.html`).*
