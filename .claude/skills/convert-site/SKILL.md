# Convert Site (orchestrator)

## Description
Convert a client's existing website into a new, modern, AEO-optimized site on the
PracticeRank Astro + Cloudflare Pages platform. Orchestrates the full chain:
scrape → scaffold → content → SEO/AEO → local-SEO → build/deploy/verify. Use when the user
says "convert this site", "build a new site for <client>", "port <client> to our platform",
or runs `/convert-site <url>`.

**Canonical reference:** `docs/site-conversion-playbook.md` — read it first; it has the full
process, the gotcha library, the QA checklist, and the anti-cookie-cutter guidance. This
skill is the runbook that ties the sub-skills together.

**Worked examples (real builds):** Oak Ridge (scratch, playbook §12) · Parian Lawyers
(WordPress/Elementor port, §13) · **Healing Hands PT (cash-pay, conversion-first, §14)** —
`sites/healing-hands-pt/` + `specs/customers/healing-hands-pt-*.{html,md}` is the reference for
premium/out-of-pocket clients where the conversion layer is the deliverable.

## User-invocable
`/convert-site <client-url> [slug]` — convert the site at `<client-url>` into
`sites/<slug>/`. If no slug, derive one from the business name.

## Non-negotiables (encode as guardrails — from the playbook §6)
1. **Real data only — never fabricate** services, stats, reviews, bios, or photos.
2. **Verify the real service menu against the live site** — never trust `practicerank.db`'s
   inferred services (Hilltop's DB said 29; the practice offered 7).
3. Install **`@tailwindcss/typography`** + add `@plugin` to global.css (or prose renders bare).
4. Add **`404.astro`** (or the Cloudflare adapter soft-404s to the homepage at 200).
5. Set **brand colors in `global.css :root`**, not just practice.json.
6. View-Transition scripts run on **`astro:page-load`**, not `DOMContentLoaded`.
7. Portrait photos use **`object-top`**; **allow AI crawlers** in robots.txt.
8. **curl-verify the live production alias** after deploy (cache-bust with `?z=...`).
9. **Purge previous-client tokens** after forking `_template` (grep `src/` for prior
   name/city/state/doctors/logo; normalize exact brand spelling). [playbook §11, §12.1]
10. **Mine `practicerank.db` + `analysis.json`** for real reviews/place_id and the AI
    FAQ/meta/gap recommendations — roll them out. [§12.1]
11. **Two human gates:** (a) asset-rehosting authorization, (b) NAP reconciliation when
    site/GBP/CRM phone or address disagree — surface it, don't auto-pick. [§12.7]
12. **Full schema set + both llms files + cited 1,500-word blogs + persistent chat widget.**
    [§12.3–12.5]
13. **Optimized imagery lives in `src/assets/images/`, not `public/`** — only `src/assets` goes
    through sharp (WebP/AVIF + srcset + width/height → zero CLS). `Pic.astro` prefers it; a swap
    that only touches `public/` silently keeps the old image live. `eager`/LCP flag = hero only.
    [§14.4]
14. **Self-host fonts via `@fontsource`** (no external Google Fonts `<link>`) → no FOUC / font-swap
    CLS. Re-bind interactive JS **and** GA4 on `astro:page-load` / `astro:after-swap`. [§14.5–14.6]

**When porting an EXISTING WordPress/Elementor site (clone-then-clean — playbook §13):**
15. **Clone for breadth, rebuild high-value pages clean.** Pixel-match first (clients reject
    redesign-from-scratch). Serve clones via a catch-all; rebuild home/bios/hubs/scholarship as
    clean responsive Astro pages, excluded via an `OVERRIDDEN` set. **Elementor-heavy pages don't
    survive static cloning (render empty) — always rebuild them.** [§13.1–13.2]
16. **Do all enhancements at BUILD time, never runtime** (runtime = FOUC "flashes legacy then
    new"; verify with JS disabled). Wrap ingested bodies in `display:flow-root`; pin
    `color-scheme:light`. [§13.3–13.4, §13.7]
17. **Strip the firm's inherited GTM** (it can swap your phone for a stale call-tracking number)
    — bound the regex with `(?!</script>)` lookahead or it eats page content. Rewrite the staging
    domain → real domain; pull every referenced asset local before cutover. [§13.5–13.6]
18. **Strip the dead WP asset stack** (~570 KB/page: CF7/CleanTalk/SmartMenus/Swiper/Owl/Isotope/
    Elementor) at build, head + footer; keep Font Awesome + jQuery. Fix WP stray-apostrophe
    artifacts on text-between-tags only. Blog: pull via the **WP REST API** (slug from `link`, not
    `slug`; newest-first). Use **302** for convertible stub redirects (cached-301 gotcha). Run a
    **390px mobile QA sweep**. [§13.8–13.13]

**When the client sells a PREMIUM / CASH-PAY / out-of-pocket service (conversion-first — playbook §14):**
19. **The conversion layer IS the deliverable** — the client's real problem is *articulating* why
    someone should pay, not their care. Build it before polish: one-sentence positioning, a
    buyer-dimension **contrast table** (grounded in real competitors), the **Hormozi value
    equation** as a page checklist, and a **conditional/experience-based** guarantee (never an
    outcome guarantee for a licensed provider). [§14.1]
20. **One primary CTA everywhere = the paid intro offer** (the qualifier, not the pricey package);
    conversion-first homepage order; sticky CTA bar after the hero. Feature the **retention/
    membership** play. [§14.2–14.3]
21. **Never advertise the high package price; never reward Google reviews; gate referrals on a
    *paid* conversion.** 🚦 Prices, guarantee wording, and referral compliance are human gates —
    all UNCONFIRMED until client + (for healthcare) state-board sign-off. [§14.3, §14.9]

> Read **playbook §12 (Oak Ridge lessons)** for scratch builds, **§13 (Parian Lawyers lessons)**
> before any clone-then-clean port of an existing WordPress/Elementor site, and **§14 (Healing
> Hands lessons)** for any premium/cash-pay client where conversion is the value — they capture the
> gotchas that cost the most time.

## Process

Run the sub-skills in order. After each, summarize and continue; stop at the human gates.

1. **`/scrape-site <url>`** → produces `sites/<slug>/.scrape.json` with all ground-truth data.
   **🚦 HUMAN GATE:** present the extracted **service list + business facts** and get
   confirmation before building (this is where fabrication risk lives).
2. **`/scaffold-site <slug>`** → fork `_template`, write `practice.json` + `global.css` brand,
   download assets, pick a design variant for variety (see playbook §8).
3. **`/generate-content <slug>`** → real services (reuse old slugs), team bios, N sourced blog
   posts. Use web search for **real, cited** stats.
   - **Conversion layer (premium/cash-pay clients):** before styling, write the positioning +
     offer per **§14** — one-sentence positioning, contrast table(s), value stack + guarantee,
     conversion-first homepage order, one primary CTA on the paid intro, membership/retention band.
     🚦 Surface pricing + guarantee wording for client (and state-board) confirmation.
4. **`/seo-aeo <slug>`** → schema, llms.txt, robots (allow AI), sitemap, `_redirects`,
   `404.astro`, analytics wiring (reuse the client's GTM).
5. **`/local-seo <slug>`** → `/dentist/<area>` pages with drive times + route maps.
6. **`/build-deploy-verify <slug>`** → build, deploy to Cloudflare Pages, run the QA checklist
   as curl assertions, report failures.
7. **Handoff** → generate a per-client results doc (model on `docs/hilltop-rebuild-*.html`)
   and the open-items list (headshots, GA4/GSC IDs, Cherry URL, Maps key, domain cutover).

## Variety (anti-cookie-cutter)
Uniqueness comes from each client's **real** brand/photos/services/reviews/bios + deliberate
design knobs (hero style, font pairing, section selection, gallery layout). Rule of thumb: if
two clients would end up identical, the scrape wasn't deep enough. See playbook §8.

## Output
A deployed `sites/<slug>/` on Cloudflare Pages, all QA assertions passing, and a handoff doc.
