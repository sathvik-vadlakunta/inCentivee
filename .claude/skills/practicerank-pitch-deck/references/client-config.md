# Client config — field reference

The generator reads one JSON object describing a single client. Arrays are used
where the deck shows a fixed small set of items. Every stat must be **real and
sourced** — the source string is printed on the slide.

## Required fields (always rendered)

| Key | Type | Notes |
|---|---|---|
| `name` | string | Business name. Also used for the default output filename. |
| `location` | string | e.g. `"Springfield, Virginia"`. |
| `industry` | string | e.g. `"Gold, Silver & Estate Jewelry Buyer"`. |
| `competitor` | string | Top local rival (or `"your top local rivals"`). |
| `gap_rows` | array of `[metric, you, competitor, multiplier]` | Exactly 4 items per row. 3 rows recommended. e.g. `["Monthly organic visits", "131", "1,281", "9.8x"]`. |
| `gap_source` | string | Source line under the gap table, e.g. `"Source: competitive organic-search analysis, May 2026"`. |
| `da_self` | `[name, score]` | The client's Domain Authority, e.g. `["Paradigm Experts", 14]`. |
| `da_explainer` | string | One sentence explaining what Domain Authority is. |
| `da_insight` | string | The takeaway for this client (where they stand, the goal). |
| `da_source` | string | e.g. `"Domain Authority — Moz, June 2026"`. |
| `keyword_examples` | array of strings | 3 buyer-intent keywords, keep the quotes, e.g. `["\"sell gold in Springfield VA\""]`. |
| `target` | string | The 6-month outcome, e.g. `"500+ monthly organic visits within 6 months"`. |

## Recommended fields

| Key | Type | Notes |
|---|---|---|
| `da_rivals` | array of `[name, score]` | Competitor Domain Authorities for the bar chart. `[]` if none verified. |
| `service_areas` | string | ` · `-separated city list. |
| `comparison_placement` | string | The "Best X in Y" comparison-placement line. |
| `gap_intro` | string | Optional lead-in sentence on the gap slide. |

## Existing-client progress (OMIT all of these for a new prospect)

| Key | Type | Notes |
|---|---|---|
| `done` | array of strings | "What we've already done" bullets. Renders the progress slide. |
| `img_done` | string | Photo path for the progress slide. |
| `score_start` / `score_now` | int | PracticeRank Score before/now. Renders the Score slide. |
| `score_start_date` / `score_now_date` | string | e.g. `"May 27"` / `"Jun 19"`. |
| `score_drivers` | array of `[label, change, note]` | What moved the score, e.g. `["Google Reviews", "64 → 95", "+31 real new reviews…"]`. |
| `current_visits` / `target_visits` | int | Renders the traffic-trajectory graph. |

## Images (all optional; missing files are skipped)

Paths are resolved relative to `--assets-dir` (default: the config file's folder),
or use absolute paths.

| Key | Where it appears |
|---|---|
| `cover_image` | Full-bleed cover slide background. |
| `img_backlinks` | "Authority / backlinks" slide. |
| `img_content` | "Content" slide. |
| `img_done` | Progress slide (existing clients). |

## Pricing tiers

| Key | Type | Notes |
|---|---|---|
| `show_tiers` | bool | `false` = strategy review with no prices. |
| `popular_tier` | int (1–3) | Which tier to highlight as "most popular". |
| `founding_note` | string | Fine-print line under the tiers. |
| `tiers` | array of `[name, tagline, regular_$, founding_$, [features...]]` | Usually 3. Set `regular_$ == founding_$` for no discount. First feature of tiers 2–3 is often `"Everything in <prev>, plus:"`. |

## Minimal new-prospect example

```json
{
  "name": "Acme Dental",
  "location": "Reno, Nevada",
  "industry": "Family & Cosmetic Dentistry",
  "competitor": "Sierra Smiles",
  "gap_rows": [
    ["Monthly organic visits", "210", "1,940", "9.2x"],
    ["\"near me\" keywords (top 10)", "3", "38", "12.6x"],
    ["Top-10 ranking keywords", "22", "88", "4x"]
  ],
  "gap_source": "Source: competitive organic-search analysis, July 2026",
  "da_self": ["Acme Dental", 16],
  "da_rivals": [["Sierra Smiles", 24], ["Reno Dental Group", 12]],
  "da_explainer": "Domain Authority (0–100) is a trust score for your website, built mostly from quality backlinks.",
  "da_insight": "You're at 16 — the goal is ~30, which is very achievable and beats nearly every local rival.",
  "da_source": "Domain Authority — Moz, July 2026",
  "service_areas": "Reno · Sparks · Carson City · Truckee",
  "comparison_placement": "“Best Cosmetic Dentist in Reno” comparison placements",
  "keyword_examples": ["\"cosmetic dentist Reno NV\"", "\"dental implants near me\"", "\"invisalign Reno\""],
  "target": "500+ monthly organic visits within 6 months",
  "show_tiers": true,
  "popular_tier": 2,
  "founding_note": "Month-to-month, no long-term contracts. Backed by our 90-day guarantee.",
  "tiers": [
    ["Optimize", "The Foundation", "1,500", "1,500", ["Local SEO + AI-search foundation", "100 local citations + Google Business Profile", "2 content + 1 backlink / mo", "Review funnel + monthly report"]],
    ["Grow", "The Growth Engine", "2,500", "2,500", ["Everything in Optimize, plus:", "4 content + 2 backlinks / mo", "Local landing pages + keyword tracking"]],
    ["Dominate", "Market Domination", "3,500", "3,500", ["Everything in Grow, plus:", "4 high-authority backlinks / mo", "Comparison placements + AI authority building"]]
  ]
}
```
