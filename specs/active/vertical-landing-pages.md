# Vertical-Specific Landing Pages for practicerank.ai

Started: 2026-05-25

## Goal

Create industry-specific landing pages on practicerank.ai for:
1. **Legal practices** (law firms, attorneys)
2. **Medical practices** (doctors, clinics, specialists)

Each page positions PracticeRank's AI search optimization services for that vertical, with a tailored report/audit that speaks their language.

## Context

- PracticeRank currently positions as dental-focused but serves multiple industries
- The content recommender already supports `business_type` field
- Each landing page needed to explain the value prop in terms that resonate with that industry
- The audit/report needed to adapt scoring criteria to the vertical
- practicerank.ai is a single HTML file (`practicerank-landing.html`) deployed to Cloudflare Pages
- The audit API is a Cloudflare Worker at `https://practicerank-api.practice-rank-ai-seo.workers.dev/audit`

## Decisions

- [x] URL structure: `/legal` and `/medical` (Cloudflare Pages auto-strips `.html`)
- [x] Report scoring adapts per vertical via `vertical` parameter passed to API
- [x] Google Places search uses correct `includedType` per vertical (`dentist`, `lawyer`, `doctor`)
- [x] Same pricing tiers across verticals (custom to market)
- [x] Navigation dropdown on all pages to switch between verticals

## Implementation

### Landing Pages Created

**`practicerank-legal.html`** → https://practicerank.ai/legal
- All dental terminology → legal terminology (patients → clients, practice → firm)
- JSON-LD: `LegalService` + `Attorney` schema
- FAQ schema: legal-specific questions
- Hero: "Get 15-25 more new client inquiries every month"
- Chat mockup: "Who's the best personal injury lawyer near me?"
- Services: Attorney schema, legal directory citations (Avvo, Martindale-Hubbell, FindLaw, Justia, Super Lawyers)
- Proof: PI firm (VA), Family law (CA), Criminal defense (FL) case studies
- ROI: Average case value $5,000-$50,000+
- Images: legal-themed Unsplash photos

**`practicerank-medical.html`** → https://practicerank.ai/medical
- Dental terminology → medical terminology (dentist → doctor, dental practice → medical practice)
- JSON-LD: `MedicalBusiness` + `Physician` schema
- FAQ schema: medical-specific questions (specialties, directories)
- Hero: "Get 20-40 more new patient appointments every month"
- Chat mockup: "Who's the best dermatologist near me?"
- Services: Physician schema, medical directories (Healthgrades, Vitals, ZocDoc, WebMD, RateMDs)
- Proof: Multi-specialty clinic (TX), Orthopedic (NY), Dermatology (CO) case studies
- ROI: Average patient LTV $2,000-$10,000+
- Images: medical-themed Unsplash photos

**`practicerank-landing.html`** (dental — updated)
- Added Industries dropdown nav to switch between Dental/Legal/Medical
- Nav dropdown with hover bridge (no gap issue)

### Industry Navigation

All three pages have an "Industries" dropdown in the nav bar:
- Dental Practices → `/`
- Law Firms → `/legal`
- Medical Practices → `/medical`
- Active page highlighted in green
- CSS hover bridge (::after pseudo-element) prevents dropdown disappearing on mouse movement

### Worker API Updates (`worker/src/index.js`)

**New `vertical` parameter** — landing pages pass `vertical: 'legal'` or `vertical: 'medical'` in the API request body. Defaults to `dental`.

**Vertical config constant:**
```javascript
VERTICAL_CONFIG = {
  dental: { placeType: "dentist", clientTerm: "patient", ltv: "$800-$2,500", ... },
  legal:  { placeType: "lawyer",  clientTerm: "client",  ltv: "$5,000-$50,000", ... },
  medical:{ placeType: "doctor",  clientTerm: "patient", ltv: "$2,000-$10,000", ... },
}
```

**Changes made:**
1. **Site validation** — `isDentalSite` check only blocks on dental vertical. Added `isLegalSite` and `isMedicalSite` detection using new keyword lists (`LEGAL_KEYWORDS`, `MEDICAL_KEYWORDS`)
2. **Google Places API** — `includedType` changes per vertical: `dentist` → `lawyer` / `doctor`. Search queries use vertical-appropriate labels
3. **Competitor search** — `fetchNearbyCompetitors` uses correct place type per vertical
4. **Multi-location matching** — Name deduplication regex expanded to handle legal/medical suffixes (esq, md, clinic, etc.)
5. **Claude audit prompt** — Fully vertical-aware:
   - Role: "expert dental practice auditor" / "expert law firm marketing auditor" / "expert medical practice marketing auditor"
   - All terminology adapts: patient→client (legal), practice→firm (legal), dentist→doctor (medical)
   - Finding examples adapted per vertical
   - Directory focus: Apple Maps (dental), Avvo/Martindale (legal), Healthgrades/Vitals (medical)
   - Content focus: service pages (dental), practice area pages (legal), condition pages (medical)
   - LTV in response adapts per vertical
6. **Name validation** — `validateScrapedData` checks all three keyword lists, not just dental

### Deployment

- **Worker:** Deployed via `npx wrangler deploy` to `practicerank-api.practice-rank-ai-seo.workers.dev`
- **Pages:** Deployed via `npx wrangler pages deploy` to `practicerank.ai`
  - `index.html` = dental (main page)
  - `legal.html` = legal vertical → `/legal`
  - `medical.html` = medical vertical → `/medical`

## Files Changed

- `practicerank-landing.html` — Added industry nav dropdown + CSS
- `practicerank-legal.html` — NEW — Legal vertical landing page
- `practicerank-medical.html` — NEW — Medical vertical landing page
- `worker/src/index.js` — Vertical-aware audit API (VERTICAL_CONFIG, LEGAL_KEYWORDS, MEDICAL_KEYWORDS, adapted prompt, Google Places types)

## Status
- [x] Complete — deployed to production
