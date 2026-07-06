# FATJOE Orders page overhaul — catalog, buy links, one-click logging, real COGS → Expenses

**Status:** done · **Created:** 2026-06-29
**Trigger:** Kody on the FATJOE Orders page: "the COGS here is not correct and does not match exact USD
prices on FATJOE; this page is complex and should be better; we need real links to where Dan can buy
each thing, and where we mark if they've been ordered and when. This page needs a big overhaul." Plus:
"make sure it is connected to the Expenses page and that is correct and updated."

## Root problems
- COGS was hardcoded in `fatjoe_plan.py` (`LINK_COST/CITATION_COST/MENTION_COST`) and wrong — e.g. it
  applied **niche-edit** prices to editorial links, and the brand-mention price ($336) didn't match
  FATJOE. Prices go stale because FATJOE changes them.
- No buy links — Dan had to find each product in the FATJOE dashboard himself.
- Order logging lived on the customer's Backlinks tab, not on the queue → friction, double-pay risk.
- Expenses page **explicitly excluded** FATJOE COGS (static placeholder), so true spend was invisible.

## Decisions (from AskUserQuestion)
- **Editable catalog** is the source of truth (not hardcoded prices) so COGS never goes stale.
- Products Dan orders: **Local Citations, Blogger Outreach (DR links), Niche Edits, Brand Mentions/Digital PR**.

## What shipped
1. **`fatjoe_catalog` table** (`geo_agent/db.py`) — product_key, family, label, dr_tier, unit, price_usd,
   buy_url, verified, active, sort. Seeded once with FATJOE's **real product URLs** and best-known
   prices (niche-edit ladder confirmed = verified; others marked `verified=0` "seed price"). Methods:
   `get_fatjoe_catalog`, `get_catalog_item`, `find_catalog_item(family, dr_tier)` (exact→next-band-up),
   `update_catalog_item`, `offsite_spend(customer_id?, since?)`.
2. **Catalog-driven COGS + buy links** (`fatjoe_plan.py`) — `resolve_product(db, spec)` resolves each
   tier-plan line to catalog price + buy URL (`TYPE_TO_FAMILY`: link→blogger_outreach, citation→citation,
   mention→mention). `FALLBACK_*` only if no catalog row. `due_orders` now attaches
   `unit_price/cost_each_period/buy_url/catalog_key/price_verified`.
3. **Overhauled `/fatjoe` page** — cleaner per-line cards; each due line has **Order on FATJOE ↗**
   (real buy link) + an inline **one-click "Log it"** form (optional FATJOE order #, qty pre-filled to
   remaining due) → `fatjoe_quick_order` logs an `offsite_order` (status=ordered, cost from catalog,
   today's date). "Logged" strip shows each order with date + #, and a **delivered?** toggle
   (`fatjoe_mark_delivered`). Header shows live **COGS this month**; banner flags unverified seed prices.
4. **Catalog editor** `/fatjoe/catalog` — Dan edits each product's exact price + buy URL inline; Save
   marks it ✓ verified. Linked from the queue, Expenses, and the recipe.
5. **Expenses wired to real COGS** — `/expenses` passes `fatjoe_mtd` + `fatjoe_total` from
   `db.offsite_spend()`; `compute_expenses` attributes them to the FATJOE line only (not the review-funnel
   variable line), adds `variable_cogs` + `all_in_monthly` totals. Template shows "FATJOE COGS — this
   month (real)" + "All-in monthly" cards.

## Tests
`tests/unit/test_fatjoe_catalog.py` (10) — seed families, DR exact/next-band resolution, catalog-priced
cost (4×DR40=$1140, citation=pack price), buy-links on due lines, expenses attribution not doubled,
offsite_spend excludes cancelled. Full suite green.

## Follow-ups
- Dan to verify the seed prices against his FATJOE reseller dashboard (the unverified banner tracks this).
- Confirm the Local Citations buy URL (fatjoe.com/local-citations/ 404'd on fetch; placeholder set,
  editable in the catalog).
- Optional: add Niche Edits / Digital PR as their own tier-plan lines (catalog already supports them).
