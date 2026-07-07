# Slide outline

The deck is a fixed narrative. Evergreen slides always render; the marked slides
render only when their config keys are present, so a new-prospect deck is shorter
than an existing-client results deck.

| # | Slide | Renders when | Config keys used |
|---|---|---|---|
| 1 | **Title / cover** | always | `name`, `location`, `industry`, `cover_image` |
| 2 | **Meet your team** | always | (evergreen — Dan & Kody) |
| 3 | **Search has changed** | always | (evergreen — Google + AI search) |
| 4 | **Well-rounded approach** | always | (evergreen — the pillars) |
| 5 | **What we fix** | always | (evergreen) |
| 6 | **Where you stand** | always | `gap_rows`, `gap_source`, `gap_intro`, `da_self`, `da_rivals`, `da_explainer`, `da_insight`, `da_source` |
| 7 | **What we've done** | `done` present | `done`, `img_done` |
| — | **PracticeRank Score history** | `score_now` present | `score_start`, `score_now`, `score_*_date`, `score_drivers` |
| 8 | **Next: authority / backlinks** | always | `img_backlinks` |
| 9 | **Next: content / blog** | always | `img_content` |
| — | **Traffic trajectory** | `current_visits` + `target_visits` present | `current_visits`, `target_visits` |
| 10 | **Roadmap** | always | `keyword_examples`, `service_areas`, `comparison_placement`, `target` |
| — | **Pricing tiers** | `show_tiers` true | `tiers`, `popular_tier`, `founding_note` |
| 11 | **Guarantee** | always | (evergreen — 90-day results-or-refund) |
| 12 | **Close** | always | (evergreen — contact + team) |

## Deck shapes

- **New prospect:** omit `done`, `score_*`, and `*_visits`. ~13 slides.
- **Existing client / results deck:** include them. ~16 slides.
- **Strategy review (no pricing):** set `show_tiers: false`.

## Editing the evergreen slides

Team names, the guarantee wording, and the close/contact are hardcoded in
`make_pitch_deck.py` (search for the `═══ N. TITLE ═══` banners). Change them
there if the offer or team changes — those are the same for every client.
