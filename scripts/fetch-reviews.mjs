#!/usr/bin/env node
/**
 * Refresh each site's testimonials.json from the Google Places API (New).
 * - Reads the placeId from each site's src/data/practice.json (practice.reviews.placeId)
 * - Keeps ONLY 5-star reviews (per business preference)
 * - Also refreshes practice.reviews.rating / count from the live aggregate
 *
 * Usage:
 *   GOOGLE_PLACES_API_KEY=AIza... node scripts/fetch-reviews.mjs            # all sites
 *   GOOGLE_PLACES_API_KEY=AIza... node scripts/fetch-reviews.mjs oak-ridge-dental
 *
 * Note: Google's Places API returns a maximum of 5 reviews per place.
 */
import { readFileSync, writeFileSync, readdirSync, existsSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')
const SITES_DIR = join(ROOT, 'sites')
const KEY = process.env.GOOGLE_PLACES_API_KEY
if (!KEY) {
  console.error('✗ GOOGLE_PLACES_API_KEY env var is required.')
  console.error('  On the droplet: grep GOOGLE_PLACES_API_KEY ~/dental-marketing/.env')
  process.exit(1)
}

const only = process.argv[2]
const sites = (only ? [only] : readdirSync(SITES_DIR)).filter((s) =>
  existsSync(join(SITES_DIR, s, 'src/data/practice.json'))
)

for (const site of sites) {
  const pPath = join(SITES_DIR, site, 'src/data/practice.json')
  const tPath = join(SITES_DIR, site, 'src/data/testimonials.json')
  const practice = JSON.parse(readFileSync(pPath, 'utf8'))
  const placeId = practice?.reviews?.placeId
  if (!placeId) {
    console.log(`• ${site}: no reviews.placeId — skipped`)
    continue
  }
  const res = await fetch(`https://places.googleapis.com/v1/places/${placeId}`, {
    headers: {
      'X-Goog-Api-Key': KEY,
      'X-Goog-FieldMask': 'rating,userRatingCount,reviews'
    }
  })
  if (!res.ok) {
    console.error(`✗ ${site}: Places API ${res.status} ${await res.text()}`)
    continue
  }
  const data = await res.json()
  const fiveStar = (data.reviews || [])
    .filter((r) => r.rating === 5)
    .map((r) => ({
      name: r.authorAttribution?.displayName || 'Google user',
      quote: (r.text?.text || r.originalText?.text || '').trim(),
      rating: 5,
      source: 'Google'
    }))
    .filter((r) => r.quote.length > 0)

  writeFileSync(tPath, JSON.stringify(fiveStar, null, 2) + '\n')
  // Refresh the live aggregate too
  if (typeof data.rating === 'number') practice.reviews.rating = data.rating
  if (typeof data.userRatingCount === 'number') practice.reviews.count = data.userRatingCount
  writeFileSync(pPath, JSON.stringify(practice, null, 2) + '\n')
  console.log(`✓ ${site}: ${fiveStar.length} five-star reviews · ${data.rating}★ / ${data.userRatingCount} total`)
}
