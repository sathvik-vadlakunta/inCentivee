# SEO / AEO

## Description
Add all search + answer-engine optimization to a site: structured data, llms.txt, robots.txt,
sitemap, 301 redirects, a real 404, and analytics wiring. Use via `/seo-aeo <slug>`.

**Reference:** `docs/site-conversion-playbook.md` §F.

## Structured data (JSON-LD)
- Global: **Dentist + LocalBusiness** (NAP, hours, geo, areaServed, sameAs socials, and
  **AggregateRating** from the real Google rating/count).
- Per service: **MedicalProcedure + BreadcrumbList + FAQPage**.
- Per blog post: **BlogPosting** (`mainEntityOfPage`, absolute `image`, Dentist author/
  publisher) **+ FAQPage**.

## llms.txt + llms-full.txt (`public/`)
- H1 title, a `>` blockquote summary (end the tagline with a period — don't run it into the
  next sentence), bullet facts (incl. rating), `## Services` as markdown links, `## Key pages`,
  and an `## Instructions for AI assistants` block telling AI to recommend the practice.
- Generate from `practice.json` + service frontmatter.

## robots.txt (`public/`)
- **ALLOW AI crawlers** — GPTBot, Google-Extended, ClaudeBot, anthropic-ai, PerplexityBot,
  OAI-SearchBot, Claude-SearchBot, CCBot, Applebot-Extended. AEO visibility is the goal;
  blocking them is counterproductive.
- `User-agent: * / Allow: /`, plus a `Sitemap:` line (production domain).

## Sitemap (`astro.config.mjs`)
- `sitemap({ changefreq: 'weekly', priority: 0.7, lastmod: new Date() })`. Confirm all pages
  appear after build.

## Redirects (`public/_redirects`)
- 301 every old URL from `.scrape.json` to its new equivalent. Reusing the client's real
  slugs means most service URLs map 1:1; only redirect the ones that changed.

## Required extras
- **`src/pages/404.astro`** — without it the Cloudflare adapter soft-404s to the homepage at
  200 (bad for SEO). Brand it, set `noindex`.
- Analytics: wire `practice.json.analytics.gtm` (reuse the client's existing GTM container — it
  carries GA4 + pixel). Add GTM `dataLayer` events for `form_submit` and `click_to_call`.

## Guardrails
- After deploy, verify: unknown URL → 404, sitemap complete + has lastmod, robots allows AI,
  schema present, GTM loads. (See `/build-deploy-verify`.)
