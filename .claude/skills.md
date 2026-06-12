# Project Skills

## /spec-start <task-name>

Start tracking a new task. Creates `specs/active/<task-name>.md` with a template.

Usage: `/spec-start paradigm-city-pages`

Template:
```markdown
# <Task Name>
Started: <date>

## Goal
<What we're trying to accomplish>

## Context
<Relevant background, customer info, constraints>

## Decisions
<Key decisions made during the task>

## Implementation
<What was built/changed>

## Status
- [ ] In progress
```

## /spec-done <category>

Mark the active task as complete and move the spec to the appropriate category.

Usage: `/spec-done customers` or `/spec-done content-system`

Moves `specs/active/<file>.md` → `specs/<category>/<file>.md`

Valid categories: `content-system`, `customers`, `platform`, `pricing`

## Site Conversion Skill Chain

A chain of skills to convert a client's existing website into a new site on the
PracticeRank Astro/Cloudflare platform. Full process + gotchas: `docs/site-conversion-playbook.md`.

- `/convert-site <url> [slug]` — orchestrator; runs the whole chain (with human gates)
- `/scrape-site <url>` — discovery scrape → `sites/<slug>/.scrape.json` (verify real services!)
- `/scaffold-site <slug>` — fork template, write practice.json + brand, download assets
- `/generate-content <slug>` — real services, team bios, sourced blog posts
- `/seo-aeo <slug>` — schema, llms.txt, robots (allow AI), sitemap, redirects, 404, analytics
- `/local-seo <slug>` — `/dentist/<area>` pages with drive times + route maps
- `/build-deploy-verify <slug>` — build, deploy to Cloudflare Pages, QA checklist as curl assertions

Each skill lives in `.claude/skills/<name>/SKILL.md`.
