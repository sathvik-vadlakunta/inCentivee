# Build, Deploy & Verify

## Description
Build a customer site, deploy it to Cloudflare Pages, and enforce quality by running the
conversion QA checklist as **automated curl assertions** against the live URL. Use via
`/build-deploy-verify <slug>`. This is the quality gate — never call a site "done" until it
passes.

**Reference:** `docs/site-conversion-playbook.md` §H + §3 (QA checklist).

## Build & deploy
```bash
cd sites/<slug>
npm install && npm run build            # must succeed; check for errors
cp public/llms.txt dist/llms.txt 2>/dev/null   # if regenerated post-build
# Cloudflare auth: local wrangler uses an OAuth login (account/workers scope).
# Create the project once, then deploy:
npx wrangler pages project create <slug> --production-branch main   # first time
npx wrangler pages deploy dist --project-name=<slug> --branch main --commit-dirty=true
```
Use the **production alias** `https://<slug>.pages.dev` for verification (NOT the random hash
deploy URL).

## Verify (run from the droplet — it has curl). Cache-bust every request with `?z=$(date +%s%N)`.

Assertions (fail loudly if any miss):
- [ ] Homepage, /services, /about, /team, /reviews, /new-patients, /contact, /blog → **200**
- [ ] Every service page → 200; every `/dentist/<area>` → 200
- [ ] **Unknown URL → 404** (proves `404.astro` exists; soft-404 is a fail)
- [ ] Brand color present in built CSS; old/template color absent
- [ ] `@tailwindcss/typography` working — a service/blog page has styled headings (`prose-brand`)
- [ ] Real logo + real photos load (spot-check a few image 200s, no broken images)
- [ ] Schema present: `Dentist`, `AggregateRating`, `MedicalProcedure`, `BlogPosting`, `FAQPage`
- [ ] `robots.txt` **allows** GPTBot/Google-Extended; `Sitemap:` line present
- [ ] `sitemap-0.xml` lists every page and has `lastmod`
- [ ] A sample old URL → **301** to the new equivalent
- [ ] llms.txt + llms-full.txt → 200, well-formed
- [ ] GTM container loads; `form_submit` + `click_to_call` in the HTML
- [ ] Mobile: nav menu toggle present; no obvious overflow

Example checks:
```bash
B=https://<slug>.pages.dev
curl -s -o /dev/null -w '%{http_code}\n' -L "$B/?z=$(date +%s%N)"
curl -s -o /dev/null -w '%{http_code}\n' -L "$B/zzz-not-real-$(date +%s)"   # expect 404
curl -s -L "$B/sitemap-0.xml" | grep -c '<loc>'
curl -s -L "$B/robots.txt" | grep -A1 'GPTBot'
```

## Common failures (and the fix — playbook §4)
- Unknown URL returns the homepage (200) → add `src/pages/404.astro`.
- A linked index "crashes" → the index page is missing (e.g. `/team/index.astro`).
- Headings unstyled → `@tailwindcss/typography` not installed / `@plugin` missing.
- Content invisible after navigating → reveal script on `DOMContentLoaded`; move to
  `astro:page-load`.
- Stale content after deploy → Cloudflare edge cache; re-check with a fresh `?z=` cache-bust.

## Output
A green QA report, or a list of failed assertions with the specific fix to apply.
