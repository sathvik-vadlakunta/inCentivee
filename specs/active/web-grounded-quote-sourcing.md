# Web-grounded expert-quote sourcing (verbatim-verified)

**Status:** active
**Created:** 2026-06-26
**Trigger:** Paradigm's "Expert quotes on key pages" checklist item can't tick because the
content recommender refuses to invent quotes (anti-fabrication guardrail: `expert_quote` recs
are skipped and `<blockquote>`s stripped unless `customer.verified_quotes` is populated). Kody:
expert quotes can legitimately come from authoritative online publications/research — automate
sourcing them *safely*.

## Guarantee (the whole point)
Never store a quote we can't prove is real. Every candidate quote is checked to appear
**verbatim** in the live source page before it's accepted; anything that doesn't match exactly
is rejected. This keeps the existing no-fabrication guarantee while automating sourcing.

## Design
New module `geo_agent/quote_sourcer.py`:
1. **Sources** — `AUTHORITATIVE_SOURCES[vertical]` seed list of reputable URLs (industry bodies,
   research, major publications), plus operator-supplied `extra_urls`.
2. **Fetch** — httpx (mirrors `service_scraper`), de-tag to plaintext, `html.unescape`.
3. **Extract** — Claude (`llm.complete`, structured output) pulls *contiguous verbatim* quotes
   attributed to a **named** person/org, relevant to the customer's topics. No paraphrase, no
   ellipses, no stitching.
4. **Verify (the gate)** — normalize (lowercase, curly→straight quotes, dashes, collapse
   whitespace); accept only if the normalized quote is a substring of the normalized source AND
   ≥6 significant words / ≥40 chars. Reject otherwise. Strict by design — drop a real quote
   before admitting a fabricated one.
5. **Store** — merge accepted `{quote, attribution, source, url}` into `customers.verified_quotes`
   (dedupe), persist via `db.update_customer`.

Consumer already exists: `content_recommender` reads `q["quote"]`/`q["attribution"]`; extend the
`verified_quotes_str` builder to also surface `source`/`url` so generated content cites + links
the source. Backward-compatible (old entries lack those keys).

Entry points: `scripts/source_quotes.py <customer_id> [--urls ...] [--max N] [--replace]` (runs on
droplet), wired so the result feeds `verified_quotes`. Then the normal content run generates
`expert_quote` recs, publishes, and the live quote-scanner (`status_checker`) ticks the checklist.

## Tests
- `_verify` accepts a real substring, rejects a fabricated quote, rejects too-short/few-words.
- `_normalize` handles curly quotes / em-dashes / whitespace.
- Extraction + store path mocked (no network) → asserts only verified quotes persist.

## Out of scope (follow-ups)
- Search-based source *discovery* (v1 uses seed list + operator URLs).
- Dashboard button (CLI first).
- Automated attribution correctness (v1 verifies the quote text verbatim; attribution is
  best-effort from the source context).
