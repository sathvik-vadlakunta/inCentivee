# Deployment Architecture

**Status:** Reference · **Created:** 2026-06-10

Canonical reference is `CLAUDE.md` → "Deployment". This spec records the architecture and the incident that prompted documenting it.

## Three deploy targets

| Target | Source | Host | Script |
|---|---|---|---|
| Dashboard (admin app + pipeline) | `dashboard/` + `geo_agent/` | DO droplet `129.212.138.145`, Caddy → gunicorn | `scripts/deploy.sh` |
| Marketing site (practicerank.ai) | **`deploy/`** | Cloudflare Pages project `practicerank` | `scripts/deploy-site.sh` |
| Audit API | `worker/` | Cloudflare Workers (`practicerank-api`) | `scripts/deploy-worker.sh` |

## Marketing pipeline
```
content/blog/*.md ──build_blog.py──► deploy/blog/
deploy/ (index, legal, medical, service pages, llms.txt, sitemap.xml, robots.txt, _redirects)
   └── scripts/deploy-site.sh ──► wrangler pages deploy deploy/ --project-name=practicerank ──► practicerank.ai
```
- Cloudflare Pages deploys are **full snapshot replacements**: a file not in `deploy/` 404s. Retired URLs go in `deploy/_redirects` (301).

## Incident (2026-06-10) — why this is documented now

The marketing site had **three diverged copies** of the landing pages:
- `deploy/*.html` — the actually-served Pages source.
- root `practicerank-*.html` — a separate editing copy.
- `public/` — an older bundle (different blog slugs, still partially live).

A round of fixes (founder Jon Lucas → Kody Doherty, pricing removed from `llms.txt`, FAQ server-rendered with matching FAQPage schema) was applied to the **root** copies and `public/` — none of which deploy. The fixes had to be re-applied to `deploy/`. The deploy process itself was undocumented (no script, no CLAUDE.md entry), so the correct source dir was unknown.

## Resolution / rules going forward
1. **`deploy/` is the single canonical marketing source.** Edit there. Edit blog as markdown in `content/blog/`.
2. Root `practicerank-*.html` and `public/` are **legacy duplicates → consolidate/remove** (open cleanup task).
3. Deploy via the `scripts/deploy-*.sh` scripts only; they build + sanity-check first.
4. Always run tests before deploying (`pytest -m "not docker"`, `npm test` in `worker/`).

## Open cleanup tasks
- [x] Removed root `practicerank-landing.html` / `-legal.html` / `-medical.html` and `public/` (2026-06-10) — `deploy/` is now the sole marketing source.
- [ ] Add `FLASK_SECRET_KEY` permanence check on the droplet.
