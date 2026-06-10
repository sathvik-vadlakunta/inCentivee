# Paradigm Experts — SEO Action Plan

Started: 2026-05-28
Context: [paradigm-experts-seo-competitive-analysis.md](../customers/paradigm-experts-seo-competitive-analysis.md)

## Goal

Close the 10x organic traffic gap between Paradigm Experts (131 visits/mo) and Alexandria Gold & Silver (1,281 visits/mo). Target: **500+ monthly organic visits within 6 months**, with focus on seller-intent transactional keywords, not informational/collector traffic.

## Root Cause Analysis

Paradigm loses because of three compounding problems:

1. **No "near me" visibility** — Zero transactional "near me" keywords in top 100. Alexandria has 49 in top 10.
2. **Homepage doesn't communicate services to Google** — Homepage ranks for 87 keywords but only generates 112 visits, almost all branded. Alexandria's homepage ranks for 485 keywords because it's rich with "buy gold", "sell silver", "gold dealer" signals.
3. **Content targets curiosity, not sellers** — Blog posts attract "what is my silverware worth" browsers instead of "sell my silverware" walk-ins.

## Phase 1: Technical Foundation (Week 1-2)

### 1.1 Fix HTTP/HTTPS Canonical Issue
The homepage ranks at both `http://` and `https://` — this splits authority.
- [ ] Verify 301 redirect from `http://` to `https://`
- [ ] Set canonical tag on all pages to `https://www.paradigmexperts.com/...`
- [ ] Update any internal links using `http://`
- [ ] Verify in Google Search Console

### 1.2 Google Business Profile Optimization
This is THE lever for "near me" keywords. Alexandria dominates Local Pack because of strong GBP signals.
- [ ] Verify GBP is claimed and fully completed
- [ ] Primary category: "Gold Dealer" or "Precious Metal Dealer" (NOT "pawn shop" or "jeweler")
- [ ] Secondary categories: "Silver Dealer", "Coin Dealer", "Estate Jewelry Buyer", "Jewelry Buyer"
- [ ] Business description: seller-focused, mention all services and cities served
- [ ] Add all service areas: Springfield, Arlington, McLean, Fairfax, Alexandria, Lorton, Ashburn, DC
- [ ] Upload fresh photos (storefront, interior, team, process)
- [ ] Create GBP posts weekly (buying events, market updates, testimonials)
- [ ] Respond to ALL reviews with detailed, keyword-rich responses
- [ ] Add products/services in GBP with descriptions
- [ ] Enable messaging and Q&A

### 1.3 Schema Markup
- [ ] Verify/update LocalBusiness schema on homepage (already have deploy files)
- [ ] Add `areaServed` to schema for all service cities
- [ ] Add `hasOfferCatalog` listing all buy services
- [ ] FAQ schema on service pages
- [ ] Ensure schema matches GBP data exactly

### 1.4 Site Speed & Core Web Vitals
- [ ] Run PageSpeed Insights on homepage and service pages
- [ ] Fix any CLS, LCP, or FID issues
- [ ] Mobile-first — 64.7% of traffic is mobile

## Phase 2: Homepage Rebuild (Week 2-3)

This is the single highest-impact change. Alexandria's homepage ranks for 485 keywords because it's a content-rich page that signals "gold and silver buyer" to Google. Paradigm's homepage needs to do the same.

### 2.1 Homepage Content Strategy
The homepage needs to be a comprehensive "sell your gold, silver, jewelry in Northern Virginia" page. Not a flashy brand page — a content-rich, keyword-targeted landing page.

**Target keywords for homepage:**
- sell gold near me / sell gold in Springfield VA / sell gold Northern Virginia
- sell silver near me / sell silver in Springfield VA
- gold buyer near me / gold buyer Springfield VA
- silver buyer near me / silver dealer near me
- sell jewelry near me / jewelry buyer near me
- sell coins near me / coin buyer near me
- estate jewelry buyer near me
- cash for gold near me / cash for silver near me
- precious metal buyers near me

**Content blocks needed:**

1. **Hero**: Clear seller-focused H1 ("Sell Your Gold, Silver & Jewelry in Northern Virginia — Same-Day Cash Payment")
2. **Services overview section**: Each service (gold, silver, diamonds, coins, watches, estate jewelry, flatware) with 2-3 sentences, link to detail page
3. **How it works**: Step-by-step process (schedule appointment, bring items, get evaluation, walk out with cash)
4. **Areas we serve**: List all cities with brief text per city. This is critical for "near me" signals: "We buy gold and silver from sellers in Springfield, Arlington, McLean, Fairfax, Fairfax Station, Lorton, Alexandria, Ashburn, and Washington DC."
5. **Why sellers choose us**: Trust signals (licensed, insured, family-owned, transparent pricing, same-day payment, private appointments)
6. **Recent testimonials**: Real reviews mentioning specific services and cities
7. **FAQ section**: Seller-intent questions ("What types of gold jewelry do you buy?", "How do you determine the value of my silver?", "Do I need an appointment?")
8. **Market update callout**: Current gold/silver spot prices, "Now is a great time to sell" urgency

### 2.2 On-Page SEO
- [ ] Title tag: "Sell Gold, Silver & Jewelry in Springfield VA | Paradigm Experts — Same-Day Cash"
- [ ] Meta description: seller-focused with CTA and cities
- [ ] H1 contains primary keyword cluster
- [ ] Internal links to all service pages and city pages
- [ ] Image alt text with relevant keywords
- [ ] ~2,000-3,000 words of unique, helpful content (not keyword-stuffed)

## Phase 3: City Landing Pages (Week 3-4)

This is how Paradigm competes for "near me" without having a city name in their brand.

### 3.1 Create Dedicated Pages

Each page should be 800-1,200 words of unique content, not template spam. Each city page needs:
- Unique H1 ("Sell Gold & Silver in Arlington VA — Paradigm Experts")
- 2-3 paragraphs about serving that specific area
- Driving directions / distance from that city
- Mention of neighborhoods within the city
- Service overview (what we buy)
- Local trust signals (reviews from that area if available)
- Google Map embed for directions
- Clear CTA (call, schedule appointment)
- LocalBusiness schema with `areaServed`

**Priority pages (by search volume and proximity):**

| Page | Target Keywords | Est. Monthly Vol |
|------|----------------|-----------------|
| /sell-gold-arlington-va | sell gold Arlington VA, gold buyer Arlington, cash for gold Arlington | 200+ |
| /sell-gold-silver-alexandria-va | sell gold Alexandria VA, sell silver Alexandria, gold buyer Alexandria | 200+ |
| /sell-gold-silver-mclean-va | sell gold McLean VA, jewelry buyer McLean, gold dealer McLean | 100+ |
| /sell-gold-silver-fairfax-va | sell gold Fairfax VA, sell jewelry Fairfax, gold buyer Fairfax | 150+ |
| /sell-gold-silver-washington-dc | sell gold DC, sell jewelry Washington DC, gold buyer DC | 300+ |
| /sell-gold-silver-lorton-va | sell gold Lorton VA, sell silver Lorton | 50+ |
| /sell-gold-silver-ashburn-va | sell gold Ashburn VA, gold buyer Ashburn | 50+ |
| /sell-gold-northern-virginia | sell gold Northern Virginia, gold buyer Northern Virginia, NoVA | 200+ |

### 3.2 Internal Linking
- Homepage links to each city page
- City pages link back to homepage and relevant service pages
- Footer contains links to all city pages
- Service pages link to relevant city pages

## Phase 4: Service Page Overhaul (Week 4-6)

Current service pages are thin and poorly structured. Each needs to become a comprehensive resource.

### 4.1 Priority Service Pages

**`/sell-gold-jewelry` (rename from /gold-gold-jewelry)**
- Target: "sell gold jewelry", "where to sell gold jewelry", "cash for gold jewelry", "how to sell gold jewelry"
- Content: what types of gold we buy (10k, 14k, 18k, 24k), how we evaluate, what affects price, current gold market
- 1,500+ words

**`/sell-silver-flatware` (rename from /silver-flatware-hollowware)**
- Target: "sell silver flatware", "where to sell sterling silver", "sell silver flatware near me"
- Content: types of silver we buy (sterling, coin, plated), brand recognition (Gorham, Reed & Barton, Towle, Wallace), valuation process
- This page already ranks for 17 keywords (pos 17-97) — it has the most potential for quick gains
- 1,500+ words

**`/sell-diamonds` (rename from /diamonds-and-engagement-rings)**
- Target: "sell diamond ring", "where to sell diamond ring", "sell engagement ring"
- Content: diamond valuation (4 Cs), process, what we pay vs retail, loose diamonds vs mounted
- 1,500+ words

**`/sell-estate-jewelry`**
- Target: "sell estate jewelry", "estate jewelry buyer near me", "sell antique jewelry"
- 1,200+ words

**`/sell-coins-bullion`**
- Target: "sell gold coins", "sell silver coins", "sell bullion", "coin buyer near me"
- CAREFUL: must target sellers, not collectors (per PPC audit findings)
- 1,200+ words

**`/sell-watches`**
- Target: "sell luxury watch", "sell Rolex", "where to sell watches"
- 1,000+ words

### 4.2 URL Restructure
Current URLs are terrible for SEO:
- `/gold-gold-jewelry` -> `/sell-gold-jewelry`
- `/silver-flatware-hollowware` -> `/sell-silver-flatware`
- `/diamonds-and-engagement-rings` -> `/sell-diamonds`
- Set up 301 redirects from old URLs

## Phase 5: Content Strategy Overhaul (Week 4-8)

### 5.1 Kill Informational Bloat
The current blog strategy is broken. Posts like "Ways to Determine Your Antique Tea Set's Value" bring 744 sessions of curiosity traffic that never converts. The blog should serve two purposes:
1. **Support service pages** with long-tail keyword capture
2. **Build topical authority** around selling precious metals

### 5.2 New Blog Topics (Seller-Intent Focus)

**High priority (matches keyword gaps):**
- "How to Sell Your Gold Jewelry for the Best Price in Northern Virginia"
- "Where to Sell Sterling Silver Flatware in the DC Area"
- "Selling Diamond Rings: What to Expect and How to Get Fair Value"
- "Gold Prices Are at Record Highs — Here's How to Sell Your Gold in Springfield VA"
- "Estate Jewelry: How to Sell Inherited Jewelry and Estate Collections"

**Supporting content:**
- "How We Evaluate Your Gold: A Transparent Look at Our Process"
- "Sterling Silver vs. Silver Plated: How to Tell the Difference Before You Sell"
- "What Happens to Your Gold After You Sell It? Behind the Scenes"
- "5 Signs It's Time to Sell Your Jewelry Collection"
- "Selling Coins and Bullion: A Seller's Guide (Not a Collector's Guide)"

### 5.3 Existing Blog Post Updates
Don't delete existing posts — they have some ranking signals. But add seller CTAs:
- **Sterling Flatware Value post** (52 keywords): Add prominent "Ready to sell? Paradigm Experts pays top dollar for sterling silver flatware" CTA with link to service page
- **Sell Diamond Rings post** (15 keywords): Update with current market data, add city-specific CTAs
- **Is It Good Time to Sell Silver** (20 keywords): Update with current silver prices, add strong sell CTA
- **Class Ring Worth post** (14 keywords): Add "We buy class rings — schedule your evaluation" CTA
- **Antique Tea Set post** (15 keywords): Add "Sell your antique tea set at Paradigm Experts" CTA — this post gets 744 sessions, even 1% conversion = 7 leads/month

## Phase 6: Local Citation & Backlink Building (Ongoing)

### 6.1 Citation Consistency
Ensure NAP (Name, Address, Phone) is identical across:
- [ ] Google Business Profile
- [ ] Yelp
- [ ] BBB
- [ ] Facebook Business
- [ ] Apple Maps
- [ ] Bing Places
- [ ] Yellow Pages / YP.com
- [ ] Superpages
- [ ] Foursquare
- [ ] Manta
- [ ] Angi / HomeAdvisor (if applicable)

### 6.2 Industry-Specific Directories
- [ ] ICTA (International Coin & Bullion Dealers)
- [ ] NGC dealer directory
- [ ] GIA alumni directory (if applicable)
- [ ] Local Chamber of Commerce (Springfield, Fairfax)
- [ ] Northern Virginia business directories
- [ ] BBB accreditation

### 6.3 Review Strategy
- Ask every customer who sells to leave a Google review
- Respond to ALL reviews with keyword-rich responses mentioning the service ("Thank you for trusting us with your sterling silver flatware collection, John! We're glad...")
- Target: 5+ new reviews per month

## Phase 7: Ongoing Monitoring

### 7.1 Track These Metrics Weekly
- Organic traffic (GSC)
- Keyword positions for target keywords (Semrush)
- GBP impressions, clicks, calls
- "Near me" keyword rankings
- AI mention rate across ChatGPT, Gemini, Perplexity (PracticeRank)

### 7.2 Quarterly Review
- Semrush position comparison vs Alexandria and other competitors
- Content performance (which pages drive traffic/conversions)
- City page ranking progress
- New keyword opportunities

## Expected Timeline & Results

| Milestone | Timeline | Expected Outcome |
|-----------|----------|-----------------|
| Technical fixes + GBP optimization | Weeks 1-2 | Local Pack appearances begin |
| Homepage rebuild live | Week 3 | Homepage starts ranking for 50+ new keywords |
| First 4 city pages live | Week 4 | "Sell gold [city]" rankings begin |
| Service pages overhauled | Week 6 | Service keyword rankings improve |
| 10 new blog posts published | Week 8 | Long-tail traffic starts flowing |
| **Target: 300+ monthly organic visits** | **Month 3** | **2.3x improvement** |
| City pages mature + citations index | Month 4-5 | "Near me" rankings emerge |
| **Target: 500+ monthly organic visits** | **Month 6** | **3.8x improvement** |

## Priority Stack (Do This First)

1. **GBP optimization** — fastest impact, highest ROI, unlocks Local Pack
2. **Homepage content rebuild** — the multiplier for everything else
3. **Fix HTTP/HTTPS canonical** — stop leaking authority
4. **Top 3 city pages** (Arlington, Alexandria, DC) — biggest search volume markets
5. **Service page overhaul** (silver flatware first — 52 keywords already ranking poorly)
6. **Seller CTAs on existing blog posts** — capture the 744 monthly antique tea set visitors
7. **New seller-intent blog content** — build topical authority
8. **Citation building** — compounds over time

## What NOT to Do

- Don't create more informational "what is X worth" content — Paradigm already ranks for these and they don't convert
- Don't target "coin collecting", "coin value", "rare coin" keywords — per PPC audit, these attract hobbyists not sellers
- Don't create thin city pages with template text — Google penalizes doorway pages
- Don't chase national keywords — focus on DMV/Northern Virginia local terms
- Don't ignore Alexandria's strategy — study their homepage, GBP, and review patterns
