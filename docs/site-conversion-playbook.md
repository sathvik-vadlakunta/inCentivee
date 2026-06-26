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
| Footer/location pages show the **previous client's** name, city, state, doctors, logo | `_template` was forked from a real client (Hilltop/Casper/Wyoming) and tokens leaked | After scaffold, **grep the whole `src/` for every prior-client token** (name, city, state, doctor names, `logo-reverse.svg`) and replace; see §11 / §12.1 |
| Brand name spacing wrong ("Oak Ridge" vs "Oakridge") | Scaffold guessed the spacing | Confirm **exact** brand spelling from the live `<title>`/logo; `grep -ril` both variants and normalize |
| Fixed transparent header breaks interior pages (overlap, white logo on white) | One global header built for the homepage hero | **Two-mode header**: transparent-fixed on `/`, solid sticky (`bg-secondary`) on every other page (reserves space) |
| Services mega-dropdown is a giant scroll | All services in one grid | **Category-flyout**: left = categories, right = that category's services (fixed height). Use for >~20 services |
| Mobile menu auto-expands a huge service list | Rendered full tree open | Collapsible native `<details>` accordions (Services/Areas/About/Resources) |
| Nav CTA buttons wrap to 2 lines (look "fat") | No `whitespace-nowrap` | Add `whitespace-nowrap` + explicit `py`/`px` to nav CTAs |
| Third-party chat widget (DearDoc) never appears / vanishes after navigating | Embed self-inits on `window.load` + guards on a global; re-injecting per-nav misses `load` and hits the guard | Load the embed **once** at initial load; on `astro:before-swap` **move the widget's DOM nodes** (e.g. `[id^="ddc-"]`) into the incoming document so it persists |
| Google API key returns `API_KEY_INVALID` even though it works in prod | Shell extraction **truncated** the key (39→36 chars) | Extract env keys exactly (`val="${line#KEY=}"`); Google keys are 39 chars starting `AIza` |
| Three different phone numbers (site vs GBP vs CRM) | NAP drift across systems | **Flag the discrepancy to the human — never auto-pick.** Reconcile from the source of truth |
| Bios only in a JS modal | Not crawlable / no AI citation | Also generate **crawlable `/team/<slug>` pages** with `Physician`+`Dentist` schema |
| Blog posts thin + uncited | First pass was ~500 words, no sources | 1,500+ words, internal links, **real cited authoritative sources** (ADA, AAID, AAE, AAPD, FDA/mfr), FAQ + `citation` + `reviewedBy` schema |

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

## 11. Keep `_template` in sync (learned from the Oak Ridge test)

Test-converting **Oak Ridge Dental** (WordPress, ~70 services) validated the chain end-to-end
but exposed that **`sites/_template/` is stale** — it predates the Hilltop improvements, so
forking it reproduced every known gotcha (the keystatic `client:only` build bug, no
`@tailwindcss/typography`, no `404.astro`, no `/team` index → soft-404, template-blue colors).
The playbook's gotcha library (§4) caught all of them, but the chain shouldn't have to re-fix
them every time.

**Action:** after a polished build (currently Hilltop), **backport its platform into
`_template`**: the `global.css` design system + `.prose-brand`, the polished components (Nav
with Services/Areas dropdowns, Hero, ServiceCard, TeamCard w/ `object-top`, Footer,
Testimonials, CTABanner), the pages (`404.astro`, `team/index`, `reviews`, `new-patients`,
`dentist/[location]`), the typography plugin in `package.json`, View-Transition-safe scripts,
and the SEO/AEO scaffolding. Remove the stale manual `keystatic` page. Then every conversion
starts finished, not basic — and `scaffold-site` only swaps data/brand/content.

> Rule: when you fix a bug or add a feature on a client site that belongs to the platform,
> port it to `_template` the same day.

---

## 12. Lessons from the Oak Ridge full build (2026-06-15)

### 12.1 — Mine the prod platform DB *before* scraping the live site
Most "ground truth" already exists in `practicerank.db` on the droplet
(`/home/kody/dental-marketing/data/practicerank.db`) and the per-customer output dir:

- **`google_places` table** → real `place_id`, `rating`, `review_count` (high/med/low confidence)
  for every customer. Wire these straight into `practice.json.reviews`. No need to re-derive.
- **`reviews` table** → stored review text (may be empty; if so, fetch live — see 12.2).
- **`data/output/<customer>/analysis.json`** → the geo_agent's recommendations:
  `faq_entries` (5–6 FAQs per service URL), `service_descriptions` (keyword/location-rich meta),
  `content_gaps` (missing pages to build), `priority_actions` (NAP fixes, schema, etc.).
  **Roll these out:** map FAQ leaf-slugs → our service `.md` files and inject them; apply the
  meta descriptions; build the gap pages it flags.
- **`customers` table** → may hold a *different* phone/email than the live site (NAP drift).

### 12.2 — Google reviews via Places API (New)
- Key lives in droplet `.env` as `GOOGLE_PLACES_API_KEY` (39 chars, `AIza…`). **Extract it
  exactly** — a truncated key returns `API_KEY_INVALID` and sends you down a wrong rabbit hole.
- `POST places:searchText` to find the place; `GET /v1/places/{id}` with
  `X-Goog-FieldMask: rating,userRatingCount,reviews` for details.
- **Google returns at most 5 reviews per place** — that's the API cap, not a bug. The aggregate
  rating/count is the full number.
- Per business preference, **filter to 5-star reviews only** for the on-site wall.
- A repeatable refresher lives at `scripts/fetch-reviews.mjs`
  (`GOOGLE_PLACES_API_KEY=… node scripts/fetch-reviews.mjs [site]`) — reads each site's
  `reviews.placeId`, writes 5-star reviews to `testimonials.json`, refreshes rating/count.

### 12.3 — The full schema set (don't stop at Dentist + FAQ)
On top of `Dentist`/`LocalBusiness`, `MedicalProcedure`, `BreadcrumbList`, `FAQPage`,
`AggregateRating`, also ship:
- **Individual `Review`** nodes (from the real 5-star reviews) on `/reviews`.
- **`Physician`+`Dentist`** on each crawlable provider page (`/team/<slug>`).
- **`speakable`** (cssSelector → `h1`, `.eyebrow`, `[data-speakable]`) for voice/AI.
- **`sameAs` + `hasMap`** → the real GBP (`maps/place/?q=place_id:<id>`), Facebook, etc.
- **`employee`** array linking the doctors into the practice entity.
- Blog: **`citation`** (from `sources` frontmatter) + **`reviewedBy`** (lead dentist).

### 12.4 — AEO content depth
- Generate **both** `llms.txt` *and* `llms-full.txt` (full dump: every service + FAQs, all
  bios, reviews). `llms-full.txt` is the one LLMs prefer.
- Blogs must be **comprehensive (1,500+ words)**, internally linked to service pages, with a
  **Sources & references** block of real authoritative orgs (ADA/MouthHealthy, AAID, AAE,
  AAPD, FDA/manufacturer like Neocis/Dentsply Sirona, Cleveland Clinic) — verify each fact
  before citing. Add `faqs` + `sources` frontmatter so the template renders FAQ/citation schema.

### 12.5 — Third-party widgets + View Transitions
Chat/booking widgets (DearDoc, etc.) self-init on `window.load` and guard against double-init.
**Load once at initial page load; persist their DOM across `astro:before-swap`** by moving the
widget's nodes into the incoming document. Never re-inject per navigation (misses `load`, hits
the guard → widget disappears after the first client-side nav).

### 12.6 — Sitemap & robots best practice
- Sitemap: use the `serialize` hook for **per-page priority** (home 1.0 → key pages 0.9 →
  service/location/provider 0.8 → blog 0.6) instead of a flat 0.7. `site` must be the prod
  domain so URLs are correct pre-cutover.
- robots: explicit **allow-list of AI agents** (GPTBot, OAI-SearchBot, ChatGPT-User,
  Google-Extended, ClaudeBot, anthropic-ai, Claude-Web, PerplexityBot, Applebot-Extended,
  Amazonbot, meta-externalagent, CCBot) + `Sitemap:` + comment-link both llms files.

### 12.7 — Human gates that actually matter
- **Asset authorization:** don't bulk-rehost a client's copyrighted photos/logo/headshots until
  authorization is confirmed (an asset pack from the client, or explicit go-ahead).
- **NAP reconciliation:** when site/GBP/CRM disagree on phone/address, **surface it and let the
  human choose** — don't silently pick one.

## 13. Lessons from the Parian Lawyers build (2026-06-25) — porting a large WordPress/Elementor site

First big **clone-then-clean** port (900+ pages, a law firm). These are general WP/Elementor
lessons unless marked legal-specific.

### 13.1 — Clone-then-clean hybrid is the winning strategy
Pixel-match first — clients reject "redesign from scratch / walls of text." Clone the WHOLE
site for breadth (`scripts/clone_site.py` + `scripts/mirror_wordpress.py` → `mirror.json`),
serve it through our header/footer via a catch-all `src/pages/[...path].astro` that ingests
`clone-pages/`, THEN rebuild the high-value page types **clean** (own responsive Astro pages,
excluded from the catch-all via an `OVERRIDDEN` set): home/landing, bios, category hubs,
city/areas-served, scholarship. The long-tail service/area pages stay as clones.

### 13.2 — Elementor pages do NOT survive static cloning — rebuild them
Elementor widgets need Elementor's frontend JS; in a static clone they render **empty** (blank
bands on desktop *and* mobile). Detect density per page:
`grep -cE 'elementor-element |elementor-section|e-con ' <file>`. The home had 147; every other
page ~0. Rebuild the Elementor-heavy ones clean; the bootstrap theme-template pages are fine.

### 13.3 — Uncleared floats → footer bg bleeds over the page (navy-on-navy)
WP theme bodies use `float:left`. Inject your footer after the ingested body and it rises
*behind* the content. Wrap the ingested body in `display:flow-root`. Build-time-appended
elements (e.g. a review band) must also `clear:both` or they sit beside a float off-screen
(caused a 581px mobile overflow). See memory `clone-float-containment`.

### 13.4 — Light-only designs: pin `color-scheme: light`
A dark-mode visitor's browser paints the canvas + form controls dark → content goes
navy-on-navy / unreadable. Add `<meta name="color-scheme" content="light">` + `:root{color-scheme:light}`.

### 13.5 — Strip the firm's inherited 3rd-party tracking (it can hijack the phone number)
The clone carries the client's old **Google Tag Manager**, which ran a call-tracking DNI
script that **swapped the real phone number for a stale tracking number we don't own** — calls
would route to a dead line. Strip GTM + wp.com stats at build. **WARNING:** bound the strip
regex with `(?:(?!</script>)[\s\S])*?` — a naive `[\s\S]*?` runs from the first `<script>`
through the page to GTM and deletes real content (we hit this — it ate the hero).

### 13.6 — Cutover prep: rewrite staging domain + pull every asset local
- The clone leaks the WP staging host (`*.wpcomstaging.com`) in og:url/og:image/canonical/links/
  assets. Rewrite all of it to the real domain at build so everything resolves same-origin
  after DNS cutover.
- Pull EVERY referenced asset local before cutover (`scripts/pull_missing_assets.py`: scan clone
  HTML + theme CSS `url(...)`, download what's missing). **Missing theme bg images render
  white-on-white invisible sections.**

### 13.7 — Do enhancements at BUILD time, not runtime (no FOUC)
Injecting CTAs/badges/images/text-fixes in JS = "flashes the legacy site, then the new one"
(**not** a Cloudflare cache issue — cache makes it faster; it's render-timing of runtime JS).
Bake them into the HTML at build with `node-html-parser` (faithful round-trip — verify script/
img/link counts survive). **Verify with JS disabled** (`Emulation.setScriptExecutionDisabled`):
the page must render complete on first paint. Keep only the modal (hidden until click) +
scroll-reveal at runtime.

### 13.8 — Fix WP content artifacts (stray apostrophes) at build, text-between-tags only
WP migrations leave orphaned opening apostrophes: `". 'Many"`, `"cars,'trucks"`, and crucially
`"injuries</a>'are"` — the last has **no space**, so the browser can't break between the link
and the next word and inline links drop onto their own line on mobile. Fix at build over
`>([^<]+)<` text **after stashing `<script>/<style>`** (null-byte sentinel). Never regex raw
HTML (corrupts inline JS like `(window,'script')`); preserve matched quote pairs `'…'` and
possessive `'s`; don't mangle numbers (4,667 / 2012).

### 13.9 — Strip the dead WordPress asset stack (~570 KB/page)
Clone pages load ~1.5 MB CSS+JS, mostly dead: jquery-migrate, CF7, CleanTalk, SmartMenus,
wp-emoji, Isotope, Swiper, Owl, Elementor. Strip at build in **both head AND footer** (WP
enqueues most scripts in the footer). Only drop carousel/Elementor libs when the page body
doesn't actually contain those widgets (per-page `class="…swiper"` check). **Keep Font Awesome
+ jQuery** so icons/behaviour don't break. Everything stripped is either unused or already
reimplemented in our raw-JS header/modal.
> ⚠️ **Masonry grids (isotope) → replace with CSS Grid, don't revive the JS.** A masonry grid
> (e.g. `/client-testimonials` review cards: `row grid tab-pane` > `col-* grid-item`) is positioned
> by isotope JS. We strip isotope/masonry (they're WP-Meteor-deferred — `type="javascript/blocked"`
> — so they never run before first paint anyway), then lay the cards out with **CSS Grid in
> enhance.css**: `display:grid;grid-template-columns:repeat(3,1fr)` on the container, items reset to
> `width:auto;float:none`. JS-free, correct on first paint. Two gotchas that cost real time here:
> (1) the theme sets `.tab-pane.active{display:block!important}`, so the override needs **high
> specificity** (`html body .testimonails-tabs .grid.row.tab-pane`) to win the `display` battle;
> (2) **never put `*/` inside a CSS comment** — a comment like `the col-*/grid-item cards` closes the
> comment early at `*/` and the parser silently drops the *next* rule (here the `display:grid` one),
> so the grid never applies and every "fix" looks like it did nothing. Verify with CDP
> `getComputedStyle(...).display`, not just by eye.

### 13.10 — Blog: pull via the WordPress REST API, not HTML scraping
`/wp-json/wp/v2/posts?per_page=100&page=N&_fields=id,slug,date,link,title,excerpt,content,categories`
gives authoritative publish dates/titles/excerpts/content/categories; `html2text` content →
markdown; `/categories` for names. Gotchas: (a) permalinks can change over time — old posts at
`/blog/<slug>`, new at root `/<slug>`; (b) the WP `slug` field can carry a spurious `blog-`
prefix — **derive the slug from `link`, not `slug`**; (c) sort **newest-first**; (d) 301 the
original permalinks of any normalized posts. `scripts/repull_blog.py`.

### 13.11 — Build clean category/area hubs + point the mega-menu there
Mega-menu column headers (e.g. *Family Law*, *Criminal Law*, *Areas Served*, each city) often
point at a generic page or 404. Build real hub pages (hero + reviews + a card grid linking each
sub-page + CTA) via a reusable `CategoryHub` component and point the headers there — strong
internal linking for local SEO.

### 13.12 — The cached-301 gotcha (use 302 for convertible stubs)
A URL that briefly 301'd (dead stub → home) gets the redirect cached **hard** by browsers —
even after you ship the real page they keep redirecting, and you can't bust it server-side.
Fixes: use **302** for stub redirects that might become real pages; to dodge a poisoned URL,
move the page to a fresh keyword-rich slug the browser never cached and 302 the old one to it.

### 13.13 — Verify visually (headless Chrome + CDP), not just grep
The navy-on-navy bug *looked* like a missing CSS variable (computed styles read white) but was
the uncleared-float footer bleeding behind content — only a screenshot + a CDP
`elementFromPoint`/painted-ancestor walk found it. Run a **mobile QA sweep** at 390px across one
of each page type, flagging horizontal overflow, 0×0 images, and 404 images — and account for
false positives (below-the-fold lazy images, intentionally-hidden elements).

### 13.14 — Legal-specific: real case results + reviews, compliant by default
Surface the firm's real verdicts/settlements from the source (Elementor counter `data-to-value`)
**with the "prior results do not guarantee a similar outcome" disclaimer** every time. Reviews:
real data only, conservative display ("1,000+"), Google deep link
(`search.google.com/local/writereview?placeid=…`). All inherited legal guardrails still apply
(see the legal playbook §2–§5: compliance engine, banned terms, review constraints, counsel gate).

---

*Living doc — update after each conversion with new gotchas. Companion: the per-client
results HTML (e.g. `docs/hilltop-rebuild-2026-06-12.html`).*
