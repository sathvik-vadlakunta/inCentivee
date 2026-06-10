# Phone Number + Industry-Aware Competitor Discovery

## Issue 1: Missing Phone Number on practicerank.ai

PracticeRank marketing site has no phone number displayed anywhere.
Business phone: **(917) 994-1232**

### Changes
- Add phone to nav bar (desktop + mobile)
- Add phone to footer contact column
- Add phone to hero CTA area
- Add `telephone` to JSON-LD schema
- Add click-to-call `tel:` links

## Issue 2: Non-Dental Competitors Default to Dentists

### Root Cause

Three places hardcode dental assumptions:

1. **`google_places.py:VERTICAL_PLACE_TYPES`** — Only has `practice`, `legal`, `medical`. Any other `business_type` returns `[]`, and `fetch_nearby_competitors` defaults to `["dentist"]` (line 377).

2. **`google_places.py:EXCLUDE_KEYWORDS` / `INDUSTRY_KEYWORDS`** — Only 3 verticals defined. Non-dental businesses have no exclusion rules, so dental clinics pass through as "competitors".

3. **`entity_extractor.py:_PLATFORM_NAMES`** — Stop list is dental-centric ("general dentistry", "family dentistry", etc.) but has no equivalent for other industries.

### Fix

**A. Expand `VERTICAL_PLACE_TYPES`** to cover all business types:
```python
VERTICAL_PLACE_TYPES = {
    "practice": ["dentist"],
    "legal": ["lawyer"],
    "medical": ["doctor", "hospital"],
    "retail": ["store", "shopping_mall"],
    "restaurant": ["restaurant", "cafe"],
    "service": ["local_service"],           # NEW
    "technology": ["software_company"],     # NEW (if supported)
    "ecommerce": ["store"],                 # NEW
    "finance": ["accounting", "bank"],      # NEW
    "real_estate": ["real_estate_agency"],   # NEW
    "fitness": ["gym", "fitness_center"],    # NEW
    "salon": ["beauty_salon", "hair_care"], # NEW
    "auto": ["car_dealer", "car_repair"],   # NEW
}
```

**B. Add industry-aware fallback**: When `business_type` isn't in the map, use the customer's `specialties` list and the business name to build a text search query instead of place type filtering. Google Places `searchText` API supports free-form queries like "gold buyer Springfield VA".

**C. Expand `EXCLUDE_KEYWORDS` and `INDUSTRY_KEYWORDS`** for each new vertical so `validate_competitors()` filters correctly.

**D. Make entity extractor industry-aware**: The `_PLATFORM_NAMES` stop list should include generic terms from all industries, not just dental.

### Files to Modify
- `practicerank-landing.html` — phone number in nav, hero, footer, schema
- `geo_agent/google_places.py` — expand type maps, add text search fallback
- `geo_agent/entity_extractor.py` — expand stop list for non-dental

## Verification
1. Landing page shows phone number with click-to-call
2. Non-dental customer (e.g., Paradigm Experts - gold buyer) gets gold/jewelry/pawn competitors, not dental clinics
3. Entity extraction for non-dental customers doesn't flag dental terms as businesses
