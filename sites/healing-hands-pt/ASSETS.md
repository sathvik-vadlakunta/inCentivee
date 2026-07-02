# Healing Hands PT — asset rehosting manifest (HUMAN GATE)

⚠️ **Do not bulk-rehost these copyrighted assets until the client authorizes it.**
The clone build renders gracefully without them (every `<img>` has an `onerror`
fallback to a brand gradient / initials). Once authorized, download each source
URL to the listed local path, then rebuild.

Source CDN (HighLevel / LeadConnector): `assets.cdn.filesafe.space` /
`storage.googleapis.com/msgsndr` for the location `gfGO2wdXDkblKs2Uisrk`.
Full source URL list is preserved in `.scrape-raw/*.html`.

| Local path | What it is | Where to source it |
|---|---|---|
| `public/images/logo.png` | Practice logo (reverse + dark) | header `<img>` on healinghandspt.net (msgsndr SVG/PNG) |
| `public/images/favicon.svg` | ✅ placeholder created (green "H") | replace with real favicon if provided |
| `public/images/hero.jpg` | Dr. Jamie / hands-on hero shot | homepage hero media |
| `public/images/clinic.jpg` | South Reno treatment-room photo | home / about imagery |
| `public/images/og.jpg` | Open Graph share image (1200×630) | brand asset (or compose) |
| `public/images/team/jamie-pribyl.jpg` | Dr. Jamie Pribyl headshot | about page |
| `public/images/services/*.jpg` (9) | service-specific photos | each old service section; map StemWave / dry-needling / CST shots specifically |
| `public/images/blog/cash-pay-vs-insurance-physical-therapy.jpg` | seed blog hero | brand library or licensed stock |

Real media URLs captured during the scrape (subset — see `.scrape-raw`):
- `https://assets.cdn.filesafe.space/gfGO2wdXDkblKs2Uisrk/media/66cd12160f03c7c10f2ebef0.jpeg`
- Many `images.leadconnectorhq.com/image/f_webp/.../assets.cdn.filesafe.space/gfGO2wdXDkblKs2Uisrk/media/*.{jpeg,png}` (hero, clinic, service shots)
- Google Place ID: `ChIJYYuO27gTmYARpNK7BPytuQg` (live; in `practice.json → reviews.placeId`, for reviews via Places API + `hasMap`). The earlier-captured `ChIJE1UTaBMVmYARCgBGyaL81cc` was stale (Places API returns `{}`).
