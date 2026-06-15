# Scaffold Site

## Description
Create a new `sites/<slug>/` from the platform template, write `practice.json` and the brand
into `global.css`, download the client's real assets, and pick a design variant so the site
isn't a cookie-cutter. Runs after `/scrape-site`. Use via `/scaffold-site <slug>`.

**Reference:** `docs/site-conversion-playbook.md` §B, §C, §8.

## Steps

1. **Fork the template:**
   ```bash
   rsync -a --exclude node_modules --exclude dist --exclude .astro sites/_template/ sites/<slug>/
   ```
   Update `package.json` `name` to `@practicerank/<slug>`.

2. **Write `src/data/practice.json`** from `.scrape.json`: name, domain, tagline, phone,
   address, geo, hours, providers (with real `photo` + `education`), serviceCategories,
   insurance, financing, social (facebook/instagram), patientPortal, areaServed,
   `analytics` (gtm/ga4/googleSiteVerification), `reviews` (rating/count/googleReviewUrl),
   `financingUrl`, `mapsApiKey`.

3. **Set the brand in `src/styles/global.css :root`** — the REAL client palette (colors live
   here, NOT just practice.json). Map them through `@theme`. Choose `--font-heading` /
   `--font-body` to fit the brand.
   - ⚠️ Also keep `@import 'tailwindcss';` and `@plugin '@tailwindcss/typography';` and the
     `.prose-brand` styles (the template should already have them — confirm).

4. **Download assets** (Node `fetch`) into `public/images/`: logo (reverse/white), favicon,
   hero photo and/or hero video (+ poster), doctor headshots (`team/dr-*.jpg`),
   service-specific photos, and a set of office candids for the gallery.

5. **Install the typography plugin if missing:**
   `npm install -D @tailwindcss/typography` and ensure `@plugin '@tailwindcss/typography';`
   is in `global.css`.

6. **Pick a design variant (for variety — playbook §8):** deterministically from the slug,
   choose a hero style (photo-card | video | full-bleed overlay), font pairing, and which
   optional homepage sections to include (stats band, gallery, video band). Record the choice
   in a comment in `practice.json` or a `.variant` note.

## Guardrails
- Clear any placeholder `photo` paths that don't exist (use initials-avatar fallback) to
  avoid broken images.
- Verify the build boots: `npm install && npm run build`.

## Output
A bootable `sites/<slug>/` with real brand + assets + practice.json, ready for content.

## Lessons learned — Oak Ridge run (2026-06-15) — see playbook §12
- **Purge previous-client tokens.** `_template` was forked from a real client, so grep all of
  `src/` for the prior name/city/state/doctors/`logo-reverse.svg` and replace. Also `grep -ril`
  both brand-name spellings ("Oak Ridge" / "Oakridge") and normalize to the exact one.
- **Two-mode header:** transparent-fixed only on `/`; solid sticky (`bg-secondary`) on all other
  pages (pass a `solid` prop). A single global transparent header breaks every interior page.
- **Services nav = category-flyout** (left categories → right services) for >~20 services, not a
  giant grid. **Mobile menu = collapsible `<details>` accordions** (don't auto-expand the list).
- Nav CTA buttons need `whitespace-nowrap` or they wrap and look "fat."
- Footer logo + "Proudly serving" + tagline must read from `practice.json`, not hardcoded.
