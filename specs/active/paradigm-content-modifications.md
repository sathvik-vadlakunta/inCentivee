# Paradigm Experts — Content Plan Modifications

Based on Semrush competitive analysis (May 28, 2026) vs existing Content Guide v3 & Developer Requirements docs.

**Goal**: Targeted changes to the existing Word docs the dev is already working from. NOT a rewrite — these are surgical additions and adjustments.

---

## HIGH PRIORITY — Add These (Not in Current Plan)

### 1. Homepage Rebuild (NEW — highest impact item)

The existing plan has zero homepage changes. This is the #2 priority after GBP optimization.

Alexandria's homepage ranks for **485 keywords** and drives **1,267 visits/mo**. Paradigm's homepage ranks for **87 keywords** with **112 visits** (87% branded). The homepage needs to become a content-rich landing page, not a flashy brand page.

**Add to the Word doc as a new section — "Homepage Content Overhaul":**

- New H1: "Sell Your Gold, Silver & Jewelry in Northern Virginia — Same-Day Cash Payment"
- Title tag: "Sell Gold, Silver & Jewelry in Springfield VA | Paradigm Experts — Same-Day Cash"
- Add these content blocks to the homepage:
  1. Services overview (each service with 2-3 sentences + link to detail page)
  2. "How It Works" 4-step process
  3. "Areas We Serve" section listing all cities with brief text (critical for "near me" signals)
  4. Trust signals section (licensed, insured, family-owned, same-day payment)
  5. Testimonials with specific service/city mentions
  6. FAQ section (seller-intent questions)
  7. Market update callout (current gold/silver spot prices)
- Target word count: 2,000-3,000 words
- Internal links to ALL service pages and ALL city pages from homepage

### 2. Service Page URL Restructure (NEW — add as dev requirement)

Current URLs are terrible for SEO. Add 301 redirects:

| Old URL | New URL |
|---------|---------|
| `/gold-gold-jewelry` | `/sell-gold-jewelry` |
| `/silver-flatware-hollowware` | `/sell-silver-flatware` |
| `/diamonds-and-engagement-rings` | `/sell-diamonds` |
| `/coins-bullion` | `/sell-coins-bullion` |
| `/estate-jewelry` | `/sell-estate-jewelry` |
| `/watches` | `/sell-watches` |

**Dev requirement**: Set up 301 redirects from old URLs to new URLs. Update all internal links, nav, sitemap, and schema to use new URLs. Update the FAQ sections and llms.txt to reference new URLs.

### 3. Service Page Content Expansion (NEW — beyond just FAQs)

The existing plan only adds FAQ sections to service pages. Each service page also needs **body content expansion** to 1,200-1,500+ words. The pages are currently thin and rank for almost nothing.

Priority order (by existing keyword potential):
1. **Silver Flatware** — already ranks for 52 keywords (all pos 17-92). Quickest wins.
2. **Gold Jewelry** — ranks for only 5 keywords. Needs full content about 10K/14K/18K/24K, evaluation process, current market.
3. **Diamonds** — ranks for 3 keywords. Needs 4Cs content, natural vs lab-grown, loose vs mounted.

Add to each service page (beyond the FAQs already planned):
- Detailed "what we buy" with specific item types
- How we evaluate / pricing transparency
- Current market context (prices, trends)
- Comparison to alternatives (pawn shops, mail-in, etc.)
- City mentions within body text for local signals

### 4. HTTP/HTTPS Canonical Fix (NEW — technical requirement)

The homepage ranks at both `http://` and `https://` — splitting authority. Add to dev requirements:
- Verify 301 redirect from `http://` to `https://` on all pages
- Set `<link rel="canonical" href="https://www.paradigmexperts.com/...">` on every page
- Update any internal links still using `http://`

### 5. Seller CTAs on Existing Blog Posts (NEW — quick win)

These existing posts get traffic but have no conversion path. Add prominent seller CTAs:

| Post | Current Traffic | Add |
|------|----------------|-----|
| Antique Tea Set Value | 744 sessions/mo | "Ready to sell? Paradigm Experts pays top dollar for antique tea sets and silver" + CTA button + link to `/sell-estate-jewelry` |
| Sterling Flatware Value | 52 keywords ranking | "Sell your sterling silver flatware at Paradigm Experts" + CTA + link to `/sell-silver-flatware` |
| Is It Good Time to Sell Silver | 20 keywords | Update with current prices + strong sell CTA |
| Class Ring Worth | 14 keywords | "We buy class rings — schedule your evaluation" CTA |
| Sell Diamond Rings | 15 keywords | Update with current market data + city-specific CTAs |

These are NOT new pages — just add CTA blocks to the bottom (and ideally mid-content) of existing posts.

---

## MODIFY — Changes to Existing Planned Content

### 6. City Page H1s — Add "Near Me" Keyword Signals

The existing city pages use niche-specific H1s:
- Arlington: "Where Can I Sell Gold Jewelry in Arlington, VA?"
- McLean: "Where Can I Sell Sterling Silver Flatware in McLean, VA?"
- Fairfax Station: "Where Can I Sell Inherited Estate Jewelry in Fairfax Station, VA?"
- Lorton: "Where Can I Sell Gold and Silver in Lorton, VA?"

**Problem**: Each page only targets ONE service type. Alexandria dominates because their homepage covers ALL services. Each city page should target the FULL keyword cluster for that city.

**Modification**: Keep the existing page content but change H1s and add broader coverage:

| City | Current H1 Focus | Change H1 To |
|------|------------------|--------------|
| Arlington | Gold Jewelry only | "Sell Gold, Silver & Jewelry in Arlington, VA — Same-Day Cash" |
| McLean | Sterling Silver only | "Sell Gold, Silver & Jewelry in McLean, VA — Top Prices Paid" |
| Fairfax Station | Estate Jewelry only | "Sell Gold, Silver & Jewelry in Fairfax Station, VA — Top Prices Paid" |
| Lorton | Gold & Silver only | "Sell Gold, Silver & Jewelry in Lorton, VA — Same-Day Cash" |

**Keep the existing niche angle** in the body content (estate jewelry focus for Fairfax Station is great) but broaden the H1 and add a "Full Services" section to each page listing ALL services, not just the niche one. This way each city page can rank for "sell gold [city]", "sell silver [city]", "jewelry buyer [city]", "sell diamonds [city]" — not just one service keyword.

### 7. City Page URLs — Use Keyword-Rich Paths

The existing plan uses: `/northern-virginia/arlington/`, `/northern-virginia/mclean/`, etc.

**Modify to**: `/sell-gold-silver-arlington-va`, `/sell-gold-silver-mclean-va`, etc.

This matches the high-volume keyword patterns from Semrush data. The `/northern-virginia/` hub page stays as-is.

### 8. Add Missing High-Priority City Pages

The existing plan has 13 cities. Cross-referencing with Semrush keyword volume, make sure these are included and prioritized:

| City | In Existing Plan? | Est. Monthly Search Vol | Priority |
|------|-------------------|------------------------|----------|
| Arlington | Yes | 200+ | P1 |
| Alexandria | Check — may be missing | 200+ | **P1 — MUST ADD if missing** |
| Washington DC | Check — may be missing | 300+ | **P1 — MUST ADD if missing** |
| Fairfax | Check city vs Fairfax Station | 150+ | P1 |
| McLean | Yes | 100+ | P1 |
| Ashburn | Check | 50+ | P2 |
| Lorton | Yes | 50+ | P2 |

Alexandria and DC are the biggest keyword volume markets after "Northern Virginia" itself. If the existing plan doesn't have dedicated pages for these, add them.

### 9. Blog Topic Adjustments

The existing 6 blog posts are mostly informational:
1. Sterling Silver Flatware Worth (P1) — **Good, keep**
2. Virtual Appraisal Guide (P1) — **Good, keep**
3. Is Now Good Time to Sell Gold (P1) — **Good, keep** (already seller-intent)
4. Natural vs Lab-Grown Diamonds (P2) — **Informational, deprioritize to P3**
5. Selling Inherited Jewelry Guide (P2) — **Good, keep** (seller-intent)
6. Market Trends (P2) — **Informational, deprioritize to P3**

**Replace the P2 slots with seller-intent posts from the action plan:**
- **NEW P1**: "How to Sell Your Gold Jewelry for the Best Price in Northern Virginia" (targets "sell gold jewelry" + local)
- **NEW P2**: "Where to Sell Sterling Silver Flatware in the DC Area" (targets "sell silver flatware near me" cluster)

These directly target the keyword gaps where Alexandria dominates and Paradigm is invisible.

### 10. NOVA Hub Page — Strengthen "Near Me" Signals

The existing `/northern-virginia/` hub page is solid but needs more transactional keyword density:

- Change H1 from "Sell Gold, Silver & Jewelry in Northern Virginia" to include "Near Me" signal: "Northern Virginia's Trusted Gold, Silver & Jewelry Buyer — Sell Near You"
- Add a section: "Why Sellers Across Northern Virginia Choose Paradigm Experts" with paragraphs mentioning "gold buyer near me", "sell silver near me", "jewelry buyer near me" naturally
- Add the "How It Works" 4-step process (matches homepage)
- Add current market prices callout (gold at $4,700, silver at $84)

### 11. Schema Markup Additions

The existing plan has FAQPage schema and LocalBusiness schema. Add:
- `areaServed` array on LocalBusiness schema listing all service cities
- `hasOfferCatalog` listing all buy services
- Ensure schema on all city pages matches GBP data exactly (same address, phone, hours)

---

## KEEP AS-IS — Already Good

These items in the existing plan align well with the competitive analysis:

- FAQ sections for all 7 service pages (well-written, seller-intent)
- llms.txt and llms-full.txt
- "Areas We Serve" navigation dropdown
- Mobile-first design requirements
- Performance targets (Lighthouse 90+)
- Breadcrumb structure
- City page template structure (How It Works, Why Paradigm, CTA, Maps)
- Individual city niche angles in body content (just broaden the H1s)
- All 6 blog posts (just reprioritize — see #9 above)

---

## Summary: Dev Action Items (Ordered by Impact)

1. **Add homepage rebuild** to the Word doc (new section — biggest SEO multiplier)
2. **Broaden city page H1s** to cover all services, not just one niche
3. **Change city page URLs** to keyword-rich format (`/sell-gold-silver-[city]-va`)
4. **Add service page URL restructure** with 301 redirects
5. **Add service page content expansion** beyond just FAQs
6. **Add HTTP/HTTPS canonical fix** to technical requirements
7. **Add seller CTAs to 5 existing blog posts** (especially antique tea set — 744 sessions)
8. **Verify Alexandria + DC city pages** are in the plan (highest volume markets)
9. **Swap 2 informational blog topics** for seller-intent topics
10. **Strengthen NOVA hub page** with "near me" signals and market prices
11. **Add `areaServed` and `hasOfferCatalog`** to schema requirements
