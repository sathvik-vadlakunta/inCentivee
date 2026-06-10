# Dental Marketing Platform

## What This Is

An AI-powered dental marketing agency/platform by **Lost Relic**. The core product is **PracticeRank** (practicerank.ai) — a platform that automates SEO, AEO (AI Engine Optimization), local visibility, and content publishing for dental practices.

The business model: charge ~$3,000/month per dental practice, automate 85%+ of the work, and scale with minimal staff.

## Core Product: PracticeRank

PracticeRank generates comprehensive SEO & AEO intelligence reports for dental practices and then executes the recommendations automatically. A sample report for myaustindds.com (38th Street Dental, Austin TX) scored the practice 64/100 overall with critical gaps in AI search readiness (20/100) and local visibility (45/100).

### What the platform does:

1. **Site Audits** — Automated SEO/AEO reports covering technical SEO, content quality, competitive landscape, keyword gaps, and schema markup analysis
2. **Content Publishing** — AI-generated content pushed to client websites via Webflow API (or similar CMS APIs)
3. **Schema Markup** — LocalBusiness, FAQ, MedicalProcedure, and Review schema implementation
4. **GEO (Generative Engine Optimization)** — Optimizing practices to appear in ChatGPT, Claude, Google AI Overviews, and Perplexity results
5. **Local SEO** — Google Business Profile management, citation building, neighborhood-specific landing pages
6. **Review Automation** — Post-visit review requests, sentiment routing, referral programs

## Client Onboarding Flow

Based on the email thread with Dr. David Gallup / Adam Milmont (Hilltop Dental):

1. Jon runs a site audit (PracticeRank report)
2. Client grants access to:
   - Google Search Console (Full user)
   - Google Analytics (Editor)
   - Google Tag Manager (Publish access)
   - Webflow site collaborator + API token
   - Google Business Profile (Manager)
   - GoDaddy/DNS access (for Cloudflare migration)
3. Jon implements technical fixes (schema, performance)
4. Automated content publishing begins via CMS API
5. Ongoing monitoring and optimization

## Tech Stack (Target)

| Tool | Purpose | Cost |
|------|---------|------|
| Grade.us | White-label review management + funnels | $40/location (Agency) |
| n8n | Workflow orchestration, referral triggers (self-hosted) | Free |
| BrightLocal | Local SEO & citation tracking | $44/mo shared |
| Claude API | Content generation & GEO monitoring | ~$15-30/client |
| Google Ads API | Ad management | Free |
| Webflow API | Content publishing to client sites | Per-client |
| Cloudflare | DNS, CDN, security | Free tier |

## Key People

- **Kody** — Co-founder
- **Matt Toone** — Co-founder (matt@vcsmedical.com)
- **Ethan Mandelup** — Co-founder (ethan@vcsmedical.com)
- **Jon Lucas** — Team member, jonlucas@lostrelic.com, runs PracticeRank operations
- **Dr. David Gallup** — Client (gallupster@gmail.com), Hilltop Dental
- **Adam Milmont** — Client partner (amilmont@gmail.com), handles tech access

## Current Status

- First client (Hilltop Dental) is in onboarding — Google Search Console linked, Webflow API token pending
- PracticeRank report generation is working (sample: myaustindds.com)
- Platform automation/tooling needs to be built out

## GEO Agent (Primary Deliverable)

A containerized Claude-powered agent that runs monthly per customer to:
- Generate/update `llms.txt` and `llms-full.txt` on customer websites (the emerging standard for LLM discoverability)
- Update JSON-LD schema markup (Dentist, FAQPage, MedicalProcedure, Review)
- Analyze content gaps and generate SEO recommendations
- Push changes via Webflow API + Cloudflare Workers

**Stack**: `python:3.12-slim` Docker image, SQLite + sqlite-vec + FTS5 (one .db file per customer) for hybrid RAG, Voyage AI for embeddings, Anthropic Claude API, Webflow API, Cloudflare Workers.

Full requirements: `docs/requirements.md`

## Directory Structure

```
geo_agent/          # The monthly agent (Python package)
dashboard/          # Flask dashboard (deployed on droplet via scripts/deploy.sh)
deploy/             # CANONICAL marketing site — deployed to Cloudflare Pages (practicerank.ai)
content/blog/       # Blog post markdown sources -> built into deploy/blog/ by scripts/build_blog.py
worker/             # practicerank-api Cloudflare Worker (free audit lead magnet)
scripts/            # Deploy + ops scripts (deploy.sh, deploy-site.sh, deploy-worker.sh, build_blog.py)
docs/               # Project documentation
templates/          # Jinja2 templates for llms.txt and schema
data/               # Volume-mounted runtime data (gitignored)
sites/              # Customer Astro sites (sojo-dental, etc.)
specs/              # Task specs and decision documentation
  active/           # Current task context (one at a time)
  content-system/   # Content generation logic and rules
  customers/        # Per-customer specs and decisions
  platform/         # Dashboard, DB, deployment specs
  pricing/          # Service tiers and pricing models
```

See `docs/` for detailed documentation on each subsystem.

## Deployment

There are **three independently deployed targets**. Each has a script in `scripts/`. Always run the relevant tests first (`pytest -m "not docker"` for Python, `npm test` in `worker/`).

| Target | What | Host | Deploy command |
|---|---|---|---|
| **Dashboard** | Flask admin app (`dashboard/`) + the geo_agent pipeline that runs inside the same container | DigitalOcean droplet `129.212.138.145` (`/home/kody/dental-marketing`), behind Caddy | `./scripts/deploy.sh` |
| **Marketing site** | practicerank.ai static site (landing pages, blog, service pages, llms.txt) | Cloudflare Pages project **`practicerank`** | `./scripts/deploy-site.sh` |
| **Audit API** | `practicerank-api` Worker (the free audit lead magnet) | Cloudflare Workers | `./scripts/deploy-worker.sh` |

### Marketing site — IMPORTANT canonical-source rule

- **`deploy/` is the ONE canonical source** uploaded to Cloudflare Pages. Edit marketing HTML **here**.
- `scripts/build_blog.py` renders `content/blog/*.md` → `deploy/blog/`. Edit blog posts as markdown in `content/blog/`, never the generated HTML.
- `scripts/deploy-site.sh` rebuilds the blog, sanity-checks the bundle (index/llms/sitemap/robots/_redirects present, sitemap valid XML), then runs `wrangler pages deploy deploy/ --project-name=practicerank`. Each Pages deploy is a **full snapshot replacement** — any file not in `deploy/` 404s, so use `deploy/_redirects` to preserve retired URLs.
- **`deploy/` is the ONLY marketing source.** The old diverged copies (root `practicerank-*.html` and `public/`) were removed on 2026-06-10 after they caused an incident (fixes landed in the root copies but the live site serves `deploy/`). Do not recreate them — edit `deploy/` directly.

### Dashboard specifics

- `scripts/deploy.sh` rsyncs the repo (excluding `data/`, `.env`, `.git`) to the droplet and runs `docker compose up -d --build dashboard`. Use `--sync` for files-only, `--logs` to tail after.
- The container runs **gunicorn** (`--workers 1 --threads 8`); a single worker keeps in-process state (`_ai_check_progress`, `_seo_cache`) shared. `reap_stale_runs()` runs at startup to fail orphaned runs.
- After deploy, verify: `ssh -i ~/.ssh/id_ed25519_do kody@129.212.138.145 "docker logs practicerank-dashboard --tail 20"` and `curl -s -o /dev/null -w '%{http_code}' localhost:5099/login` should be `200`.
- `FLASK_SECRET_KEY` must be set in `.env` on the droplet, otherwise sessions reset on every restart.

## Specs Workflow

Use `specs/` to track task context and document decisions:

1. **Starting a task**: Create `specs/active/<task-name>.md` with goals, context, and decisions as you go
2. **During work**: Update the active spec with key decisions, gotchas, and implementation notes
3. **Task complete**: Move the spec from `active/` to the appropriate category subfolder (e.g., `specs/customers/downtown-dental-content-rules.md`)
4. **Reference**: Completed specs serve as permanent documentation of what was built and why

Categories: `content-system/` (recommender, blog rules), `customers/` (per-client decisions), `platform/` (dashboard, infra), `pricing/` (tiers, proposals)
