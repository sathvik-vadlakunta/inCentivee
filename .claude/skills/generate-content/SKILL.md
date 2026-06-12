# Generate Content

## Description
Generate the site's content collections — service pages (real menu only), team bios, and
sourced blog posts — for a scaffolded site. Runs after `/scaffold-site`. Use via
`/generate-content <slug>`.

**Reference:** `docs/site-conversion-playbook.md` §D, §7 (sourcing rules).

## Services (`src/content/services/*.md`)
- One file per **verified** service from `.scrape.json` (NOT inferred services).
- **Reuse the client's real URL slugs** so old `/services/<x>` maps 1:1 (SEO continuity).
- Each page: `image` (service-specific photo), intro, "what's included" list, **What to
  Expect**, a **real sourced stat** where one exists (link it), 4–5 **FAQs** in frontmatter
  (→ FAQPage schema), and a local `areaServed` closing line.
- Set `category` to one of `practice.json.serviceCategories` and an `order`.

## Team (`src/content/team/*.md`)
- Real bios + `education` + real `photo`. Pull background from the client site + public
  directories (Healthgrades/WebMD/ADA/BBB). **Never LinkedIn.**

## Blog (`src/content/blog/*.md`) — best practices
- 5–8 posts, each **mapped 1:1 to a real service** (don't write about services they don't offer).
- **~700+ effective words** (body + FAQs), a `featured image`, 4–5 **FAQs** (→ FAQPage schema),
  2–3 **internal links** (to services + other posts), and a clear CTA.
- **Real, cited research only.** Use web search to find verifiable stats from authoritative
  sources (CDC, ADA, AAID, AASM, peer-reviewed meta-analyses) and **link them**. Never invent
  numbers. End each post with a **Sources** line.
- **Spread `pubDate`s** across recent months (not all the same day).
- Question-style H2/H3 headings (good for AEO extraction).

## Sourcing rules (playbook §7)
- Stats: verifiable + named source + link.
- Services: only what the client offers.
- Photos: client's own; if none for a topic, a tasteful generic from their library (don't
  claim it depicts a specific procedure).

## Guardrails
- Confirm content schema supports `faqs` on blog (`src/content/config.ts`).
- After generating, `npm run build` and re-audit word counts / images / FAQs / sources.

## Output
Real, sourced, service-aligned content collections that build cleanly.
