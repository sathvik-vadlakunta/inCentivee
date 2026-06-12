# Local SEO (area pages)

## Description
Generate local-SEO landing pages for each community the client serves — `/dentist/<area>` —
with localized copy, drive times, text directions, and a Google route map. Use via
`/local-seo <slug>`.

**Reference:** `docs/site-conversion-playbook.md` §G.

## What to build
- A dynamic page `src/pages/dentist/[location].astro` with `getStaticPaths()` over
  `practice.json.areaServed`.
- Each page: localized H1 ("Your trusted dentist for <area> families"), a lede that adapts to
  home city vs. nearby town vs. county, the full services grid, testimonials, local `Dentist`
  schema (with `areaServed` + AggregateRating), and a CTA.
- **Drive time** badge + a short **text direction** per town (accurate, general — e.g. "From
  Mills, head east into Casper via CY Avenue"). Keep a `DRIVE` and `DIRECTIONS` map keyed by
  lowercased area name.
- **Route map** from the city CENTER to the office on every page (including the home city):
  - Prefer the **Maps Embed API** (`/maps/embed/v1/directions?key=<mapsApiKey>&origin=&destination=&mode=driving`)
    — it reliably draws the route and the **Embed API is free/unlimited**.
  - Keyless fallback (`maps.google.com/maps?saddr=&daddr=&output=embed`) when no key — note it
    may show only a pin.
  - A "Get directions ↗" button → `https://www.google.com/maps/dir/?api=1&origin=&destination=`.

## Make them reachable
- Add an **"Areas We Serve"** dropdown to the header nav (label it that, NOT "Locations" —
  it's one office, not multiple) + a homepage "Areas we serve" section + footer links.

## Guardrails
- Don't reuse the server-side `GOOGLE_PLACES_API_KEY` in public HTML — create a restricted
  Maps Embed API key (referrer + Embed-API-only).
- Confirm area pages appear in the sitemap after build.
