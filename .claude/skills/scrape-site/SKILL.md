# Scrape Site (discovery)

## Description
Crawl a client's existing website and public profiles to gather **ground-truth** data for a
site conversion: business facts, the REAL service menu, team bios/photos, reviews, brand
colors, logo, photography, hero video, tracking IDs, and the full old-URL inventory. This is
the most important phase — everything downstream depends on its accuracy. Use via
`/scrape-site <url>` or as step 1 of `/convert-site`.

**Reference:** `docs/site-conversion-playbook.md` §A (Discovery & scrape).

## Critical rule
**Verify the REAL service menu from the live site — do NOT trust `practicerank.db`.** Our
content pipeline infers/expands services (Hilltop's DB listed ~29; the practice offered 7).
Read the live nav + `/sitemap.xml` service URLs + each service page.

## Where to run
Scraping needs `curl` and outbound network. The local sandbox often lacks `curl` on PATH —
run scrape commands on the droplet (`ssh -i ~/.ssh/id_ed25519_do kody@129.212.138.145`), and
download binary assets with Node `fetch` (works without curl).

## What to extract → write to `sites/<slug>/.scrape.json`

- **Business:** name, tagline, phone, address, geo (lat/lng), hours, area served
- **Services:** real menu (slug + title + category + description) from sitemap + service pages
- **Team:** names, credentials, titles, bios, education, headshot URLs (verify bios via
  Healthgrades/WebMD/ADA/BBB — **never LinkedIn**, it's a ToS/blocking problem)
- **Reviews:** the testimonials embedded on the site + Google rating & count (search
  "<name> <city> google reviews" / Birdeye for the aggregate)
- **Brand:** color vars from the site CSS; logo URLs (reverse/white + dark); favicon
- **Photos:** crawl EVERY page (service pages hold service-specific shots); hero video
- **Tracking:** GA4 (`G-`), GTM (`GTM-`), `google-site-verification`, FB pixel
- **Other:** patient portal URL, social links, membership tiers/pricing, financing
- **Old-URL inventory:** every `<loc>` in the old sitemap (for the 301 map)

## Commands that work

```bash
URL=https://example.com
# real service URLs + all old pages
curl -sL "$URL/sitemap.xml" | grep -oE '<loc>[^<]+</loc>' | sed -E 's#</?loc>##g'
# images/video across pages (run per page, esp. service pages)
curl -sL "$URL/" | grep -oE 'https://cdn[^"]+\.(jpg|jpeg|png|webp|svg|mp4|webm)' | sort -u
# hero video
curl -sL "$URL/" | grep -oE 'data-video-urls="[^"]+"'
# brand colors (fetch the site CSS)
curl -sL "$CSS" | grep -oE '\-\-[a-z-]+:\s*#[0-9a-fA-F]{6}'
# tracking IDs
curl -sL "$URL/" | grep -oE 'G-[A-Z0-9]{8,}|GTM-[A-Z0-9]{5,}|google-site-verification" content="[^"]+'
# pair a team photo with a doctor (find the img near the name)
curl -sL "$URL/team" | tr '<' '\n<' | grep -i '<img' | grep -i 'alt="Dr\.'
```

## Output & gate
Write `sites/<slug>/.scrape.json`. Then **present the service list + key business facts to the
user and get explicit confirmation** before any building begins. List anything missing that
needs the client (headshots, exact hours, membership pricing).
