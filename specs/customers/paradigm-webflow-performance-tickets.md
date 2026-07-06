# Paradigm Experts — Site Performance Tickets (Webflow)

**Site:** paradigmexperts.com (Webflow) · **Created:** 2026-06-29 · **Source:** Lighthouse audit 2026-06-29

## Why this matters
Mobile Lighthouse **Performance = 51/100**. SEO / Accessibility / Best-Practices are already 96–100,
so speed is the one thing dragging the site down — and a 6.8 s load actively suppresses rankings on the
"near me" buyer-intent terms we're trying to win.

## Baseline (mobile, throttled) — fix these, re-measure against the targets
| Metric | Now | Target (Good) |
|---|---|---|
| Largest Contentful Paint (LCP) | **6.8 s** | < 2.5 s |
| First Contentful Paint (FCP) | **6.0 s** | < 1.8 s |
| Time to Interactive (TTI) | **9.2 s** | < 3.8 s |
| Total Blocking Time (TBT) | **440 ms** | < 200 ms |
| Cumulative Layout Shift (CLS) | 0 ✅ | < 0.1 |

**Lighthouse-flagged opportunities:** multiple redirects ≈ **780 ms** · unused JavaScript ≈ **450 ms / 284 KB** · unused CSS ≈ 14 KB.

**How to verify any ticket:** run https://pagespeed.web.dev/ on `https://paradigmexperts.com/` (Mobile tab),
publish to a Webflow staging/subdomain first if possible, and compare the metric named in the ticket.
CLS is already perfect — **do not let any change introduce layout shift** (always set image dimensions).

---

## TICKET-1 — Optimize the hero / LCP image  ⚠️ P0 · Owner: Webflow dev
**Problem:** LCP is 6.8 s. The largest above-the-fold image is loading far too late/heavy. This is the
single biggest win.

**Do:**
- [ ] Identify the LCP element (PageSpeed → "Largest Contentful Paint element"). It's almost certainly the homepage hero image.
- [ ] If the hero is a **background image** on a div, switch it to a real Webflow **Image element** so Webflow generates responsive `srcset` + serves WebP via its CDN. (Background images don't get responsive variants.)
- [ ] Re-export the source at the real display size (don't ship a 3000px image into a 1200px slot). Compress before upload.
- [ ] Set the hero image to **eager** load (Webflow Image settings → Loading = "eager"; everything else stays "lazy").
- [ ] Add a **preload** for the hero in the page `<head>` (Page Settings → Custom Code, Head):
      `<link rel="preload" as="image" href="HERO_WEBP_URL" fetchpriority="high">`
- [ ] Add `fetchpriority="high"` to the hero image (via Webflow element **Custom Attributes**: name `fetchpriority`, value `high`).

**Acceptance:** Mobile LCP < 2.5 s; hero served as WebP at ~display resolution; no CLS regression.

---

## TICKET-2 — Lazy-load all below-the-fold images + set explicit dimensions  ·  P1 · Owner: Webflow dev
**Problem:** Off-screen images compete for bandwidth during first paint and inflate FCP/LCP.

**Do:**
- [ ] Every image **below the fold** → Loading = "lazy" (Webflow default for Image elements; verify, and convert any below-fold background images to Image elements).
- [ ] Ensure every image has explicit width/height (or aspect-ratio) so nothing reflows — protects the perfect CLS = 0.

**Acceptance:** Only the hero loads eagerly; PageSpeed "Defer offscreen images" passes; CLS stays < 0.1.

---

## TICKET-3 — Reduce / defer JavaScript  ·  P1 · Owner: Webflow dev
**Problem:** ~284 KB of unused JS, ~450 ms of wasted execution; TBT 440 ms and TTI 9.2 s are JS-bound.

**Do:**
- [ ] Audit **Site Settings → Custom Code** and every **page/element Embed** for third-party scripts (chat widgets, pixels, analytics, old tag managers). Remove anything unused; **defer** the rest (`defer` attribute, or load on interaction).
- [ ] Remove **unused Webflow Interactions (IX2)** — every unused interaction still ships JS. Delete interactions that aren't visibly used.
- [ ] Consolidate duplicate analytics (only one GA/GTM instance).
- [ ] Move any non-critical custom `<script>` from `<head>` to the end of `<body>` / add `defer`.

> Note: Webflow always ships jQuery + webflow.js — that floor can't be removed without leaving Webflow.
> The goal here is to eliminate everything *on top* of that baseline.

**Acceptance:** "Reduce unused JavaScript" savings < 100 ms; mobile TBT < 200 ms.

---

## TICKET-4 — Fonts: preconnect + font-display: swap  ·  P2 · Owner: Webflow dev
**Problem:** Web fonts block first paint, hurting FCP (6.0 s).

**Do:**
- [ ] If using Google Fonts/Adobe, add to page `<head>`: `<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>` (and the Adobe host if applicable).
- [ ] Ensure `font-display: swap` (Webflow's font manager applies this for uploaded fonts; for custom `@font-face` in embeds, add `font-display: swap;`).
- [ ] Drop unused font weights/styles from the project.

**Acceptance:** No "Ensure text remains visible during webfont load" flag; FCP improves toward < 1.8 s.

---

## TICKET-5 — Collapse the redirect chain  ·  P1 · Owner: DNS/Cloudflare (us) + Webflow dev to confirm
**Problem:** Lighthouse flags ~**780 ms** lost to "multiple redirects" — likely `http→https→www` or a trailing-slash hop.

**Do:**
- [ ] Pick ONE canonical host (recommend `https://paradigmexperts.com` — no `www`, or vice-versa, just be consistent).
- [ ] In **Webflow → Site Settings → Publishing**, set the chosen host as the **Default** domain.
- [ ] Ensure DNS/Cloudflare does the canonical redirect in a **single 301** (not http→https→www = two hops). One Cloudflare Redirect Rule.
- [ ] Re-test: `curl -sIL https://paradigmexperts.com` should show **at most one** 301 before 200.

**Acceptance:** ≤ 1 redirect to reach final URL; PageSpeed "Avoid multiple page redirects" passes.

---

## TICKET-6 — Cloudflare edge optimization  ·  P1 · Owner: DNS/Cloudflare (us)
**Problem:** Slow TTFB/FCP. Cloudflare in front of Webflow cuts first-byte and offloads images.
*(Skip / adapt if the domain is not proxied through Cloudflare yet — coordinate with the team.)*

**Do:**
- [ ] Confirm the domain is **proxied** through Cloudflare (orange cloud) in front of Webflow hosting.
- [ ] Enable **Brotli**, **Early Hints**, and **Tiered Cache**.
- [ ] Enable **Polish** (WebP/AVIF conversion + lossy) for images. *(Pro plan feature.)*
- [ ] Add a **Cache Rule** to edge-cache static assets aggressively; be careful caching HTML — respect Webflow's cache headers so re-publishes invalidate. Test thoroughly before/after.

> Heads-up: Cloudflare **Auto Minify was deprecated** (do minification at the source instead — Webflow already minifies on publish via Site Settings → Publishing → "Minify HTML/CSS/JS"; make sure those are ON).

**Acceptance:** TTFB drops measurably; images served as AVIF/WebP from the edge; no stale-content issues after a Webflow re-publish.

---

## TICKET-7 — Confirm Webflow publish-time minification is ON  ·  P2 · Owner: Webflow dev
**Do:**
- [ ] Webflow → **Site Settings → Publishing** → enable **Minify HTML / CSS / JS**. Re-publish.

**Acceptance:** Published HTML/CSS/JS are minified.

---

## Expected outcome
TICKET-1 alone should move Performance from 51 into the 70s. With 2–7 done, expect **mobile ≈ 80–88,
desktop ≈ 90+**. A guaranteed 90+ *mobile* on Webflow is hard (the jQuery + webflow.js baseline is the
ceiling) — if that's a hard requirement, the durable fix is porting to our Astro + Cloudflare Pages
platform (separate proposal). Re-run PageSpeed after each P0/P1 ticket and record the new metrics here.

### Sign-off log
| Date | Ticket | Mobile Perf score | LCP | Notes |
|---|---|---|---|---|
| 2026-06-29 | baseline | 51 | 6.8 s | starting point |
