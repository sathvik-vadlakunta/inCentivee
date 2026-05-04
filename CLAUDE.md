# Dental Marketing Platform

## What This Is

An AI-powered dental marketing agency/platform built for **Jon Lucas** (jonlucas@lostrelic.com) at **Lost Relic**. The core product is **PracticeRank** (practicerank.ai) — a platform that automates SEO, AEO (AI Engine Optimization), local visibility, and content publishing for dental practices.

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

- **Jon Lucas** — Founder, jonlucas@lostrelic.com, runs PracticeRank
- **Dr. David Gallup** — Client (gallupster@gmail.com), Hilltop Dental
- **Adam Milmont** — Client partner (amilmont@gmail.com), handles tech access
- **Matt Toone** — CC'd (matt@vcsmedical.com)
- **Ethan Mandelup** — CC'd (ethan@vcsmedical.com)

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
docs/               # Project documentation
templates/          # Jinja2 templates for llms.txt and schema
data/               # Volume-mounted runtime data (gitignored)
```

See `docs/` for detailed documentation on each subsystem.
