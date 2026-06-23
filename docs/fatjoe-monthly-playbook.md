# FATJOE Monthly Playbook — Dan (Account Manager)

The one-page flow for buying and tracking off-site authority (backlinks,
citations, brand mentions) through FATJOE, per client, every month.

**Golden rule:** the client only ever sees PracticeRank. FATJOE reports are
unbranded — we ingest them and re-present the work as our own. Never forward a
FATJOE CSV to a client.

**⚠️ Log every order the moment you place it.** The queue only knows an order
happened once it's logged in the app. If you order in FATJOE but forget to log
it, the queue will keep showing it as "due" — and you'll re-order and double-pay.
Order → log → done, every time.

---

## The loop, every month

1. **Open the dashboard → FATJOE Orders** (sidebar). This lists every paying
   client, their tier, and exactly **what's still due this period**. The number
   each row shows is what you haven't ordered yet.
2. **For each due item, order it in the FATJOE reseller dashboard** (see recipes
   below). Match the target page + anchor guidance shown on the row.
3. **Log the order** back in PracticeRank: client page → **Backlinks & Authority**
   tab → **+ Log FATJOE order** (type, qty, DR tier, target URL, anchor, cost,
   FATJOE order ref). Logging it makes it drop off the "due" list and start
   tracking to delivery.
4. **On delivery, import the report** (same tab → Import report). The app pulls
   each live link's DA via Moz and feeds the weekly client report's authority
   section. QA every link before marking it live (checklist below).

The tier comes from the client's **Stripe plan** — once their subscription is
active, the FATJOE queue knows what they're owed. No plan = they show in the
"no linked paid plan" warning box; fix it on the Billing page.

---

## What each tier gets (the recipe)

| Tier | Onboarding (once) | Every month | Quarterly |
|---|---|---|---|
| **Optimize** | 100-citation NAP build | 1 × DR20–30 editorial link | — |
| **Grow** | 100-citation NAP build | 2 × DR20–30 editorial links | 1 brand mention (DR30–60) |
| **Dominate** | 100-citation NAP build | 4 × DR30–40 links (incl. 1 "best {service} in {area}" comparison placement) | 1 brand mention (DR40–60) |

We deliberately **start light and relevant** — never the vendor's "10/month."
For a low-authority local site that's wasteful and an unnatural footprint. Scale
velocity only on Dominate or a genuinely competitive client.

**Our wholesale COGS (for reference):** links DR20 $96 · DR30 $120 · DR40 $216 ·
DR50 $336 · citations 100 = $120 · brand mention $336.

---

## Ordering recipes (FATJOE reseller dashboard)

### Local citations (onboarding + top-ups)
1. Confirm the client's **canonical NAP** (name, address incl. suite, phone,
   website) on the Local SEO tab first — everything copies it.
2. FATJOE → **Local Citations** → 100 (new client) or 50 (top-up).
3. Fill the form with the NAP **character-for-character**, plus category, 2–3
   service keywords, hours, a 1–2 sentence description, logo + 1 photo URL.
4. Order note: *"Match NAP exactly as provided — do not reformat phone or
   abbreviate street."* Standard ~7-day turnaround.
5. Citations have **no anchor text** — the only thing that matters is exact,
   consistent NAP. One wrong suite number across 100 dirs hurts ranking.

### Editorial link (the monthly drip)
1. **Pick the target page** — rotate, don't always hit the homepage. ~40%
   homepage / 60% money pages (a core service or city/service page).
2. **DR tier** from the table — new local = DR20–30. Don't buy DR50+ for a
   low-authority local site; it looks engineered and wastes margin.
3. **Anchor text** — follow the running mix per client:
   - ~40% branded ("Springfield Gold & Coin")
   - ~20% naked URL (springfieldgold.com)
   - ~20% generic ("this local gold buyer", "read more")
   - ~15% partial ("sell gold in Springfield")
   - **≤5% exact-match** ("sell gold Springfield") — **never repeat one**.
   - Match the anchor to the page (city/service anchor → that page).
4. **Niche**: closest to the client's vertical (dental → health, law →
   legal/finance, gold buyer → finance/lifestyle). Note: *"US-based site
   preferred; topic relevant to {city} {service}."*
5. Let FATJOE write the content (included). ~14-day turnaround.

### Brand mention (quarterly / AI-visibility)
1. FATJOE → **Brand Mentions**, DR30–60.
2. Provide business name, city, website, 1–2 facts to surface ("family-owned
   since 2004", "same-day appraisals"), and the vertical.
3. Note: *"Positive, natural mention in a listicle/roundup; include city; aimed
   at AI/LLM visibility."* Mixed follow/nofollow is fine.

---

## QA every link before marking it "live"

- ✅ Live and loads (not 404 / "coming soon").
- ✅ **Do-follow** for blogger-outreach links (citations/mentions may be nofollow — fine).
- ✅ Points to the **exact target URL** we ordered, with the **exact anchor**.
- ✅ Surrounding content is on-topic and reads like a real post (no PBN footprint).
- ✅ Indexable (no `noindex`); re-check it's indexed in Google ~2 weeks later.
- ✅ Live page's DA (app pulls via Moz) is within ~5 of the tier we paid for.

If any check fails: set status **redo_requested** and file the FATJOE lifetime
guarantee claim. Track the redo on the same order row — don't mark it live.

---

## Where it shows up

- **FATJOE Orders** page — your monthly to-do, all clients at once.
- **Client → Backlinks & Authority tab** — log orders, import reports, see live
  links + DA.
- **Client → top of page** — "FATJOE this period" panel mirrors the queue.
- **Weekly client report** — the authority work + DA deltas we ordered become
  the client-facing "Authority work this period" / "sources now citing you."

Full background + cost math: `specs/active/fatjoe-va-ops-and-tracking.html` and
`specs/active/link-building-pricing.html`.
