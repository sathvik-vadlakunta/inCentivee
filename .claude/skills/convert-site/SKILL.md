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

## Process

Run the sub-skills in order. After each, summarize and continue; stop at the human gates.

1. **`/scrape-site <url>`** → produces `sites/<slug>/.scrape.json` with all ground-truth data.
   **🚦 HUMAN GATE:** present the extracted **service list + business facts** and get
   confirmation before building (this is where fabrication risk lives).
2. **`/scaffold-site <slug>`** → fork `_template`, write `practice.json` + `global.css` brand,
   download assets, pick a design variant for variety (see playbook §8).
3. **`/generate-content <slug>`** → real services (reuse old slugs), team bios, N sourced blog
   posts. Use web search for **real, cited** stats.
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
