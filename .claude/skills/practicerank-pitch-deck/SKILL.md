---
name: practicerank-pitch-deck
description: >-
  Build a branded PracticeRank SEO/AEO sales-pitch or strategy deck (PowerPoint
  .pptx) for a local-business prospect or existing client. Use when asked to
  create a pitch deck, sales deck, strategy deck, results deck, or proposal
  presentation for a PracticeRank / Lost Relic customer. Produces a widescreen,
  dark-mode deck matching practicerank.ai, driven by a simple JSON client config.
---

# PracticeRank Pitch Deck

Generates a polished, on-brand PowerPoint deck for a PracticeRank customer from a
single JSON config. One generator produces two shapes of deck automatically:

- **New-prospect strategy deck** — competitive gap, authority, roadmap, pricing.
- **Existing-client results deck** — the above **plus** progress, PracticeRank
  Score history, and traffic trajectory (these slides appear only when their
  keys are present in the config).

## Requirements

`python-pptx` must be installed: `pip install python-pptx` (see `requirements.txt`).

## Workflow

1. **Gather the client's real data.** Pull from the actual PracticeRank audit,
   Semrush/Moz, Google Business Profile, and the dashboard — never invent
   numbers (see "Rules" below). You need, at minimum:
   - Business name, location, industry, top local competitor
   - 3 competitive gap rows (metric · you · competitor · multiplier) with a source
   - Domain Authority for the client (and rivals if known), with a source
   - 3 example buyer-intent keywords and the 6-month target outcome
   - For an existing client only: what's been done, PracticeRank Score history,
     current→target monthly visits

2. **Write the client config.** Copy `examples/_template.json` (or start from
   `examples/paradigm.json` for an existing client, `examples/parian.json` for a
   new prospect) and fill it in. Full field-by-field schema:
   `references/client-config.md`. Slide-by-slide breakdown: `references/slide-outline.md`.

3. **Add images (optional).** Put cover / storefront / content / results photos
   anywhere and reference them by path in the config. Missing images are skipped
   gracefully — the deck still builds.

4. **Generate the deck:**
   ```bash
   python3 make_pitch_deck.py --config path/to/client.json \
       --assets-dir path/to/images --out ClientName-Deck.pptx
   ```
   - `--config` (required): the client JSON.
   - `--assets-dir` (optional): base folder for relative image paths (defaults to
     the config file's folder).
   - `--out` (optional): output path (defaults to
     `./PracticeRank-SEO-Strategy-<Name>.pptx`).
   - `--logo` (optional): PracticeRank logo PNG; a bundled one under `assets/` is
     used if present.

5. **Review before sending.** Open the `.pptx`, confirm every number is real and
   sourced, spot-check spacing, then deliver.

## Rules (important)

- **Never fabricate metrics.** Gap rows, Domain Authority, review counts, Score
  history, and traffic must be real and verifiable, each with its source labeled
  on the slide. If a number isn't known, omit that row/slide rather than guess.
- **Match the client's business type.** PracticeRank serves many industries —
  jewelry buyers, law firms, dentists, etc. Keyword examples, comparison
  placements, and service areas must fit the actual business.
- **New prospect vs existing client:** omit the `done`, `score_*`, and
  `*_visits` keys for a brand-new prospect so the progress slides don't render.
- **Pricing:** set `show_tiers: false` for a pure strategy review with no prices.

## Files

- `make_pitch_deck.py` — the generator (config-driven; no code edits per client).
- `examples/paradigm.json` — real existing-client deck (with progress slides).
- `examples/parian.json` — real new-prospect deck (no progress slides).
- `examples/_template.json` — blank starting point.
- `references/client-config.md` — every config field explained.
- `references/slide-outline.md` — what each slide shows and when it renders.
- `assets/` — optional bundled brand logo.
