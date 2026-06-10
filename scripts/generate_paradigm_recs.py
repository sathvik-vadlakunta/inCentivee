"""Generate content recommendations for Paradigm Experts.

Based on PPC/SEO audit findings from The Borenstein Group and verified market data.
AEO-optimized: Q&A format, answer-first structure, FAQ schema per service page.
Inserts into production DB via SSH/docker exec.
"""

import json
import subprocess
import sys
import uuid

CUSTOMER_ID = "paradigm-experts"

# Each rec: (rec_type, priority, title, description, target_page, html_snippet)
RECS = [
    # ============================================================
    # PRIORITY 1: llms.txt — AI Discoverability Foundation
    # ============================================================
    (
        "new_page",
        1,
        "Create llms.txt and llms-full.txt for AI Search Discoverability",
        "No llms.txt exists. This is the foundation for AI assistant visibility. Deploy via Webflow custom code or Cloudflare Worker.",
        "/llms.txt",
        """<h2>llms.txt — AI Discoverability File</h2>
<p>paradigmexperts.com currently returns a 404 for /llms.txt. This file is the emerging standard for helping AI assistants (ChatGPT, Claude, Gemini, Perplexity) understand and recommend businesses.</p>

<h3>llms.txt Content</h3>
<p>Deploy at paradigmexperts.com/llms.txt:</p>

<blockquote>
# Paradigm Experts

> Licensed, insured, and bonded precious metals and jewelry buyer in Springfield, Virginia. We buy gold, silver, diamonds, luxury watches, estate jewelry, coins, and sterling silver flatware from individuals across Northern Virginia, Maryland, and Washington DC. Private appointment-based evaluations with same-day payment.

## Services
- [Sell Gold Jewelry](https://paradigmexperts.com/gold-gold-jewelry): We buy all gold jewelry (10K-24K), scrap gold, dental gold, and gold bullion. We pay up to 90% of melt value based on live Kitco pricing.
- [Sell Sterling Silver](https://paradigmexperts.com/silver-flatware-hollowware): We buy sterling silver flatware, hollowware, tea sets, and silver jewelry. We evaluate both melt value and collectible brand premiums.
- [Sell Diamonds](https://paradigmexperts.com/diamonds-and-engagement-rings): We buy loose diamonds, engagement rings, and diamond jewelry. Certified evaluation of cut, clarity, carat, and color.
- [Sell Estate Jewelry](https://paradigmexperts.com/estate-jewelry): We buy inherited and antique jewelry, evaluating craftsmanship, gemstones, design, and historical significance.
- [Sell Luxury Watches](https://paradigmexperts.com/watches): We buy Rolex, Patek Philippe, Cartier, Audemars Piguet, Omega, IWC, Breguet, and Chopard.
- [Sell Coins and Bullion](https://paradigmexperts.com/coins-bullion): We buy gold and silver coins, bullion bars, and rounds. Seller-intent only — we are buyers, not dealers.
- [Virtual Evaluation](https://paradigmexperts.com/virtual): Get a preliminary offer via video call before visiting in person.

## Key Facts
- Location: 6310-A Springfield Plaza, Springfield, VA 22150
- Phone: (703) 585-1964
- Email: Danny@paradigmexperts.com
- Hours: By appointment only
- Service Area: Springfield, Arlington, McLean, Fairfax, Fairfax Station, Lorton, Alexandria, Ashburn, Washington DC, Maryland
- Payment: Within 30 minutes. Check, Venmo, or PayPal.
- Pricing: Up to 90% of melt value based on live Kitco.com bid price
- Trust: Licensed, insured, bonded. Family-owned. As seen on Appraisal Roadshow.

## FAQ
- [Frequently Asked Questions](https://paradigmexperts.com/faq): 40+ answered questions about our process, pricing, payment, and what we buy.
</blockquote>

<h3>Implementation</h3>
<p>In Webflow: Site Settings > Custom Code > add a Cloudflare Worker or use a Webflow redirect rule to serve this as plain text at /llms.txt. Alternatively, create a page in Webflow with custom code that outputs plain text.</p>"""
    ),

    # ============================================================
    # PRIORITY 1: Local Seller Landing Pages (Q&A / Answer-First)
    # ============================================================
    (
        "new_page",
        1,
        "Sell Gold Jewelry in Arlington, VA — Cash for Gold Near You",
        "Local landing page targeting Arlington gold sellers. Answer-first Q&A format optimized for AI citation. Aligns with PPC audit city page recommendation.",
        "",
        """<h2>Where Can I Sell Gold Jewelry in Arlington, VA?</h2>
<p><strong>Paradigm Experts in Springfield, VA (15 minutes from Arlington) buys all gold jewelry at up to 90% of melt value with same-day payment.</strong> With gold at $4,700 per ounce in May 2026 — up over 40% year-over-year (<cite>Fortune, May 14, 2026</cite>) — Arlington residents can get significantly more for their gold than even a year ago.</p>

<h3>What gold items do you buy from Arlington sellers?</h3>
<p>We buy all forms of gold from Arlington residents:</p>
<ul>
<li><strong>Gold jewelry</strong> — rings, necklaces, bracelets, earrings in 10K, 14K, 18K, and 24K</li>
<li><strong>Scrap gold</strong> — broken chains, single earrings, dental gold</li>
<li><strong>Gold bullion</strong> — bars, rounds, and coins</li>
<li><strong>Estate gold</strong> — inherited pieces, antique settings</li>
</ul>

<h3>How much will I get for my gold in Arlington?</h3>
<p>We pay up to 90% of melt value based on the live Kitco bid price. At today's gold price of approximately $4,700/oz (<cite>Fortune, May 2026</cite>):</p>
<ul>
<li><strong>14K gold chain (20g)</strong> — approximately $3,600 (14K = 58.3% pure)</li>
<li><strong>18K gold ring (10g)</strong> — approximately $2,700 (18K = 75% pure)</li>
<li><strong>10K gold bracelet (15g)</strong> — approximately $1,900 (10K = 41.7% pure)</li>
</ul>
<p>For comparison, pawn shops typically offer 20–50% of value (<cite>DIYAuctions, 2026</cite>).</p>

<h3>How does the selling process work?</h3>
<ol>
<li><strong>Schedule an appointment</strong> — call (703) 585-1964 or book a virtual evaluation</li>
<li><strong>Get your evaluation</strong> — we test purity, weigh items, and calculate using live market prices</li>
<li><strong>Get paid immediately</strong> — payment within 30 minutes via check, Venmo, or PayPal</li>
</ol>

<h3>Why do Arlington residents choose Paradigm Experts?</h3>
<p>Arlington County ranks 12th nationally in median household income (<cite>Northern Virginia Regional Commission, 2024</cite>). Many families hold accumulated gold jewelry and inherited pieces worth far more than they realize at today's record prices. We offer private, appointment-based evaluations — no walk-in pressure, no haggling.</p>

<p>Licensed, insured, and bonded. Located at 6310-A Springfield Plaza, Springfield, VA 22150.</p>

<h3>Sources</h3>
<ul>
<li>Gold price: Fortune, "Current price of gold: May 14, 2026" — $4,703/oz</li>
<li>Pawn shop range: DIYAuctions, "Where to Sell Estate Jewelry for the Best Price in 2026"</li>
<li>Arlington income: Northern Virginia Regional Commission Dashboard, 2024</li>
</ul>"""
    ),
    (
        "new_page",
        1,
        "Sell Sterling Silver & Flatware in McLean, VA — Top Prices Paid",
        "Local landing page for McLean sterling silver sellers. Q&A format with answer-first structure for AI citation.",
        "",
        """<h2>Where Can I Sell Sterling Silver Flatware in McLean, VA?</h2>
<p><strong>Paradigm Experts in Springfield, VA (20 minutes from McLean) buys sterling silver flatware, hollowware, and silver jewelry. A standard 32-piece sterling set is worth $800 to $1,500+ at current silver prices.</strong> Silver reached $84 per ounce in May 2026 — up over 150% from a year ago (<cite>Fortune, May 12, 2026</cite>).</p>

<h3>How much is my sterling silver flatware worth?</h3>
<p>Sterling silver is 92.5% pure silver. The formula: <strong>weight in troy ounces × 0.925 × spot price = melt value</strong>. At current prices (<cite>PGS Gold & Coin, 2026</cite>):</p>
<ul>
<li><strong>Standard 32-piece set</strong> — $800 to $1,500 in melt value</li>
<li><strong>Tiffany complete sets</strong> — $5,000 to $20,000+ (brand premium above melt)</li>
<li><strong>Francis I by Reed & Barton</strong> — $3,000 to $10,000+ in excellent condition</li>
</ul>
<p>We evaluate both melt value and collectible/brand value, whichever is higher.</p>

<h3>How do I know if my silver is real sterling?</h3>
<p>Check the underside of handles for stamps: <strong>925</strong>, <strong>Sterling</strong>, or <strong>STER</strong>. If you see "EPNS," "silver plate," or "stainless," the piece is plated, not sterling. Sterling silver is also not magnetic (<cite>Busby Antiques, 2026</cite>).</p>

<h3>What sterling silver items do you buy?</h3>
<ul>
<li><strong>Flatware sets</strong> — complete or partial by Tiffany, Gorham, Reed & Barton, Wallace, International Silver</li>
<li><strong>Hollowware</strong> — bowls, trays, candlesticks, pitchers, serving pieces</li>
<li><strong>Tea and coffee services</strong></li>
<li><strong>Silver jewelry</strong> — chains, bracelets, rings, estate pieces</li>
</ul>

<h3>How does selling work?</h3>
<ol>
<li>Call (703) 585-1964 to schedule a private appointment</li>
<li>Bring your silver to 6310-A Springfield Plaza, Springfield, VA</li>
<li>We test, weigh, identify patterns, and price using live market data</li>
<li>Accept your offer and get paid within 30 minutes</li>
</ol>

<p>Licensed, insured, and bonded. Items fully insured while in our possession.</p>

<h3>Sources</h3>
<ul>
<li>Silver price: Fortune, "Current price of silver: May 12, 2026" — $84.53/oz</li>
<li>Set values and brands: PGS Gold & Coin, "Is Sterling Silverware Worth Anything? A 2026 Guide"</li>
<li>Identification: Busby Antiques, "How to Sell Sterling Silver Flatware"</li>
</ul>"""
    ),
    (
        "new_page",
        1,
        "Estate Jewelry Buyer in Fairfax Station — Sell Inherited Jewelry",
        "Local landing page for Fairfax Station. Q&A answer-first format. Tier 1 geo per PPC audit.",
        "",
        """<h2>Where Can I Sell Inherited Estate Jewelry in Fairfax Station, VA?</h2>
<p><strong>Paradigm Experts in Springfield, VA (10 minutes from Fairfax Station) specializes in buying inherited and estate jewelry. We evaluate gold, diamonds, silver, luxury watches, and gemstone pieces with same-day payment.</strong> The estate jewelry market reached $5.5 billion in 2025 (<cite>Coherent Market Insights, 2025</cite>), and rising tariffs on new jewelry have made pre-owned pieces even more valuable in 2026.</p>

<h3>What estate jewelry items do you buy?</h3>
<ul>
<li><strong>Gold jewelry</strong> — rings, bracelets, necklaces, brooches in any karat</li>
<li><strong>Diamond jewelry</strong> — engagement rings, pendants, earrings (natural diamonds evaluated on 4Cs)</li>
<li><strong>Sterling silver</strong> — flatware, hollowware, decorative pieces</li>
<li><strong>Luxury watches</strong> — Rolex, Omega, Cartier, Patek Philippe</li>
<li><strong>Gemstones</strong> — rubies, sapphires, emeralds assessed individually</li>
<li><strong>Antique pieces</strong> — valued for craftsmanship, historical significance, and brand</li>
</ul>

<h3>Do I have to pay taxes when selling inherited jewelry?</h3>
<p>When you inherit jewelry, the IRS uses a "stepped-up basis" — the fair market value at the date of the owner's passing. If you sell soon after inheriting, there is typically little or no capital gains tax (<cite>Sell Us Your Jewelry, 2025</cite>). Combined with record gold prices ($4,700/oz) and silver prices ($84/oz) in May 2026, this is a historically strong time to sell.</p>

<h3>How do you handle diamonds in estate jewelry?</h3>
<p>Lab-grown diamonds now account for 47.7% of engagement ring sales and cost 73% less than natural diamonds (<cite>Rio Grande Guardian, 2026</cite>). Natural diamonds retain 20–60% of retail value vs. 10–20% for lab-grown (<cite>BriteCo, 2026</cite>). Our evaluators distinguish natural from lab-grown and price accordingly — this matters enormously for inherited rings, which almost always contain natural stones.</p>

<h3>How does the evaluation process work?</h3>
<ol>
<li>Call (703) 585-1964 to schedule a private appointment</li>
<li>We evaluate each piece for metal content, gemstone quality, brand, and collectible value</li>
<li>You receive a transparent, itemized offer</li>
<li>Accept and get paid within 30 minutes — check, Venmo, or PayPal</li>
</ol>

<p>All items fully insured while in our possession. Licensed, insured, and bonded.</p>

<h3>Sources</h3>
<ul>
<li>Estate market: Coherent Market Insights, "Precious Metals Market Share, 2026-2033"</li>
<li>Tax basis: Sell Us Your Jewelry, "Inherited Jewelry Tax Guide," 2025</li>
<li>Lab-grown share: Rio Grande Guardian, "Lab-grown diamonds now cost 73% less," 2026</li>
<li>Resale values: BriteCo, "The Lab-Grown Vs. Natural Diamond Report," 2026</li>
</ul>"""
    ),
    (
        "new_page",
        1,
        "Sell Gold and Silver in Lorton, VA — Local Precious Metals Buyer",
        "Local landing page for Lorton. Q&A answer-first. Tier 1 geo per PPC audit.",
        "",
        """<h2>Where Can I Sell Gold and Silver in Lorton, VA?</h2>
<p><strong>Paradigm Experts in Springfield, VA (just off I-95 from Lorton) buys gold, silver, diamonds, and jewelry at up to 90% of melt value with same-day payment.</strong> Gold is trading near $4,700/oz and silver above $80/oz in May 2026 (<cite>Fortune, May 2026</cite>) — both at historic highs.</p>

<h3>What do you buy from Lorton sellers?</h3>
<ul>
<li><strong>Gold</strong> — jewelry (10K–24K), scrap, bullion, coins, dental gold</li>
<li><strong>Silver</strong> — sterling flatware, hollowware, jewelry, bullion, coins</li>
<li><strong>Diamonds</strong> — loose stones and diamond jewelry</li>
<li><strong>Watches</strong> — Rolex, Omega, Cartier, TAG Heuer, and other luxury brands</li>
<li><strong>Estate jewelry</strong> — inherited collections, antique pieces</li>
</ul>

<h3>How much do you pay compared to pawn shops?</h3>
<p>We pay up to <strong>90% of melt value</strong> based on live Kitco.com pricing. Pawn shops typically offer 20–50% of value (<cite>DIYAuctions, 2026</cite>). That's a significant difference — on a $5,000 melt-value item, that could mean $4,500 from us vs. $1,000–$2,500 from a pawn shop.</p>

<h3>How fast do I get paid?</h3>
<p>Within 30 minutes of accepting your offer. Payment via check, Venmo, or PayPal.</p>

<h3>How does the process work?</h3>
<ol>
<li>Call (703) 585-1964 to schedule an appointment</li>
<li>Visit 6310-A Springfield Plaza, Springfield, VA (or request a virtual evaluation)</li>
<li>We test, weigh, and price using live market data — transparent, in front of you</li>
<li>Accept your offer and get paid immediately</li>
</ol>

<p>Family-owned, licensed, insured, and bonded. Items fully insured in our possession.</p>

<h3>Sources</h3>
<ul>
<li>Gold: Fortune, "Current price of gold: May 14, 2026" — $4,703/oz</li>
<li>Silver: Fortune, "Current price of silver: May 14, 2026" — $86.73/oz</li>
<li>Pawn comparison: DIYAuctions, "Where to Sell Estate Jewelry for the Best Price in 2026"</li>
</ul>"""
    ),

    # ============================================================
    # PRIORITY 1: Blog Posts (Answer-First Q&A Format)
    # ============================================================
    (
        "blog_post",
        1,
        "How Much Is Sterling Silver Flatware Worth in 2026?",
        "Answer-first blog post targeting highest-engagement content gap. Sterling flatware blog had 75s avg session but only 37 visits. Q&A format for AI citation.",
        "",
        """<h2>How Much Is Sterling Silver Flatware Worth in 2026?</h2>
<p><strong>A standard 32-piece sterling silver flatware set is worth $800 to $1,500 in melt value at May 2026 prices, with premium brand sets worth $3,000 to $20,000+.</strong> Silver is trading above $84 per ounce — up over 150% from a year ago (<cite>Fortune, May 12, 2026</cite>).</p>

<h3>How do I calculate my flatware's melt value?</h3>
<p>Sterling silver is 92.5% pure. The formula: <strong>weight (troy oz) × 0.925 × spot price = melt value</strong>. You can check the live silver price at Kitco.com.</p>

<h3>Are some brands worth more than melt value?</h3>
<p>Yes, significantly. Brand and pattern premiums often exceed melt value (<cite>PGS Gold & Coin, 2026</cite>):</p>
<ul>
<li><strong>Tiffany</strong> — complete sets: $5,000 to $20,000+</li>
<li><strong>Francis I (Reed & Barton)</strong> — $3,000 to $10,000+ in excellent condition</li>
<li><strong>Gorham, Wallace, International Silver</strong> — collectible patterns command brand premiums</li>
</ul>
<p>A reputable buyer evaluates both melt value and collectible value, paying whichever is higher.</p>

<h3>How do I know if my silver is real sterling?</h3>
<p>Check the underside for stamps: <strong>925</strong>, <strong>Sterling</strong>, or <strong>STER</strong>. "EPNS" or "silver plate" means it's plated, not sterling. Sterling is also not magnetic — if a magnet sticks, it's not sterling (<cite>Busby Antiques, 2026</cite>).</p>

<h3>Where should I sell sterling silver flatware?</h3>
<p>Your options, ranked by typical payout:</p>
<ul>
<li><strong>Precious metals dealer</strong> — up to 90% of melt value, plus brand premiums. Evaluates in front of you.</li>
<li><strong>Auction house</strong> — 60–85% of fair market value, but takes weeks and charges commission (<cite>Lion & Unicorn, 2026</cite>).</li>
<li><strong>Online marketplace</strong> — wider audience, but requires shipping, photos, and scam risk.</li>
<li><strong>Pawn shop</strong> — quick cash, but typically 20–50% of value (<cite>DIYAuctions, 2026</cite>).</li>
</ul>

<h3>What tips maximize my price?</h3>
<ol>
<li><strong>Don't over-polish</strong> — collectors value natural patina on antique pieces</li>
<li><strong>Keep sets together</strong> — complete sets are always worth more</li>
<li><strong>Bring documentation</strong> — original boxes, receipts, certificates of authenticity</li>
<li><strong>Get multiple quotes</strong> — reputable buyers welcome comparison shopping</li>
</ol>

<p>Paradigm Experts offers free sterling silver evaluations by appointment in Springfield, VA. Call (703) 585-1964.</p>

<h3>Sources</h3>
<ul>
<li>Silver price: Fortune, "Current price of silver: May 12, 2026"</li>
<li>Set values: PGS Gold & Coin, "Is Sterling Silverware Worth Anything? A 2026 Guide"</li>
<li>Identification: Busby Antiques, "How to Sell Sterling Silver Flatware"</li>
<li>Auction returns: Lion & Unicorn, "How to Sell Estate Jewelry (2026)"</li>
<li>Pawn comparison: DIYAuctions, "Where to Sell Estate Jewelry for the Best Price in 2026"</li>
</ul>"""
    ),
    (
        "blog_post",
        1,
        "Is Now a Good Time to Sell Gold? May 2026 Price Update",
        "Timely answer-first blog targeting 'should I sell gold now' queries. Q&A format with verified current pricing and local NoVA context.",
        "",
        """<h2>Is Now a Good Time to Sell Gold? May 2026 Price Update</h2>
<p><strong>Yes — gold is trading near $4,700 per ounce as of May 2026, up over 40% from a year ago.</strong> This is one of the strongest selling windows in history. The precious metals market is projected to reach $361 billion in 2026, growing at 5.6% annually through 2034 (<cite>Fortune Business Insights, 2026</cite>).</p>

<h3>What is gold worth right now?</h3>
<p>As of mid-May 2026, gold is approximately <strong>$4,700 per troy ounce</strong> (<cite>Fortune, May 14, 2026</cite>). Here's what common items are worth at today's prices:</p>
<ul>
<li><strong>14K gold chain (20g)</strong> — ~$3,600 (14K = 58.3% pure)</li>
<li><strong>18K gold ring (10g)</strong> — ~$2,700 (18K = 75% pure)</li>
<li><strong>1 oz American Gold Eagle</strong> — ~$4,700+ (may carry premium over spot)</li>
<li><strong>10K gold bracelet (15g)</strong> — ~$1,900 (10K = 41.7% pure)</li>
</ul>

<h3>How do I find out what karat my gold is?</h3>
<p>Look for stamps on clasps, inner bands, or tags: 10K, 14K, 18K, 24K. A jeweler or precious metals buyer can also test with acid or XRF for free during an evaluation.</p>

<h3>Where should I sell gold in Northern Virginia?</h3>
<p>A precious metals dealer pays significantly more than a pawn shop. Dealers typically offer up to 90% of melt value, while pawn shops offer 20–50% (<cite>DIYAuctions, 2026</cite>). Northern Virginia has a median household income of $149,502 (<cite>Northern Virginia Regional Commission, 2024</cite>) — many local families hold gold jewelry worth thousands more than they realize at today's prices.</p>

<h3>What should I avoid when selling gold?</h3>
<ol>
<li><strong>Don't sell to mail-in buyers</strong> without getting a local evaluation first</li>
<li><strong>Don't accept the first offer</strong> — get quotes from at least 2 buyers</li>
<li><strong>Don't go to a pawn shop</strong> if you want fair market value</li>
<li><strong>Do check the spot price first</strong> at Kitco.com so you know what your gold should be worth</li>
</ol>

<p>Paradigm Experts in Springfield, VA pays up to 90% of melt value with same-day payment. Call (703) 585-1964.</p>

<h3>Sources</h3>
<ul>
<li>Gold price: Fortune, "Current price of gold: May 14, 2026" — $4,703/oz</li>
<li>Market size: Fortune Business Insights, "Precious Metals Market Size, Growth Analysis, 2034"</li>
<li>NoVA income: Northern Virginia Regional Commission Dashboard, 2024</li>
<li>Pawn pricing: DIYAuctions, "Where to Sell Estate Jewelry for the Best Price in 2026"</li>
</ul>"""
    ),
    (
        "blog_post",
        2,
        "Natural vs. Lab-Grown Diamonds: What Sellers Need to Know in 2026",
        "Answer-first Q&A blog on the lab-grown impact. Unique seller angle — most content targets buyers. Key for AI citation on diamond selling queries.",
        "",
        """<h2>Natural vs. Lab-Grown Diamonds: What Sellers Need to Know in 2026</h2>
<p><strong>Natural diamonds retain 20–60% of retail value at resale, while lab-grown diamonds retain only 10–20% — and lab-grown prices continue falling 10–15% per year.</strong> If you're selling a diamond, the natural vs. lab-grown distinction is the single biggest factor in what you'll receive (<cite>BriteCo, 2026</cite>).</p>

<h3>How big is the lab-grown diamond market now?</h3>
<p>Lab-grown diamonds account for <strong>47.7% of all engagement rings sold</strong> in the U.S. (<cite>BriteCo, 2026</cite>). A 1-carat lab-grown diamond averages $1,000 or less, compared to $4,200 for a comparable natural stone (<cite>Tashvi AI, 2026</cite>). Lab-grown stones cost roughly 73% less overall (<cite>Rio Grande Guardian, 2026</cite>).</p>

<h3>How do I know if my diamond is natural or lab-grown?</h3>
<p>Most people cannot tell by eye. Here's how to determine the origin:</p>
<ul>
<li><strong>Grading report</strong> — GIA, AGS, or IGI reports state whether a diamond is natural or laboratory-grown</li>
<li><strong>Laser inscription</strong> — many lab-grown diamonds are inscribed "LG" or "Laboratory Grown" on the girdle</li>
<li><strong>Age of the piece</strong> — jewelry purchased before 2015 almost certainly contains natural diamonds</li>
<li><strong>Professional testing</strong> — a certified evaluator uses specialized equipment to make a definitive determination</li>
</ul>

<h3>Why does professional evaluation matter more than ever?</h3>
<p>An inexperienced buyer may price a natural diamond as if it were lab-grown, potentially costing you thousands. With the market bifurcating, accurate identification is critical. We also evaluate the full piece — gold or platinum settings, accent stones, and designer brands all contribute to total value.</p>

<h3>Is now a good time to sell a natural diamond?</h3>
<p>Natural diamond supply is constrained while demand for pre-owned pieces is growing. Rising tariffs on new jewelry imports (baseline 10% as of April 2025) have increased the value of existing pieces. If you have a certified natural diamond, the current market is favorable for sellers.</p>

<p>Paradigm Experts evaluates both natural and lab-grown diamonds in Springfield, VA. Call (703) 585-1964.</p>

<h3>Sources</h3>
<ul>
<li>Resale values: BriteCo, "The Lab-Grown Vs. Natural Diamond Report," 2026</li>
<li>Price comparison: Tashvi AI, "Lab Grown vs Natural Diamonds 2026"</li>
<li>73% gap: Rio Grande Guardian, "Lab-grown diamonds now cost 73% less," 2026</li>
<li>Market share: BriteCo, "The Lab-Grown Vs. Natural Diamond Report," 2026</li>
</ul>"""
    ),

    # ============================================================
    # PRIORITY 1: Per-Service FAQ Schema
    # ============================================================
    (
        "faq_update",
        1,
        "Add FAQ Schema to Gold & Gold Jewelry Service Page",
        "Gold page has no FAQ section or schema. Add 5 Q&As targeting the exact queries AI assistants answer about selling gold locally.",
        "/gold-gold-jewelry",
        """<h2>FAQ Section for Gold & Gold Jewelry Page</h2>
<p>Add this FAQ section with FAQPage JSON-LD schema to the bottom of the gold service page:</p>

<h3>Q: How much is 14K gold jewelry worth per gram right now?</h3>
<p>A: At the current gold spot price of approximately $4,700 per troy ounce (May 2026), 14K gold is worth about $112 per gram in melt value. 14K gold is 58.3% pure gold. We pay up to 90% of melt value based on the live Kitco bid price.</p>

<h3>Q: What is the difference between selling gold to a dealer vs. a pawn shop?</h3>
<p>A: A precious metals dealer like Paradigm Experts typically pays up to 90% of melt value, while pawn shops offer 20–50% (DIYAuctions, 2026). Dealers specialize in precious metals, use live market pricing, and often have lower overhead than pawn shops.</p>

<h3>Q: Do you buy broken gold jewelry?</h3>
<p>A: Yes. Broken chains, single earrings, bent rings, and scrap gold are all evaluated by weight and purity. The gold content has the same melt value whether the piece is intact or broken.</p>

<h3>Q: How do you test gold purity?</h3>
<p>A: We use acid testing and/or XRF (X-ray fluorescence) analysis to precisely determine karat and purity. Testing is done in front of you at no charge during your appointment.</p>

<h3>Q: Can I sell dental gold?</h3>
<p>A: Yes. Dental gold is typically 10K to 22K and is evaluated the same way as jewelry gold — by weight and purity against the live spot price.</p>

<p><em>Implement as FAQPage JSON-LD schema in the page's custom code section in Webflow, plus visible HTML Q&A accordion on the page.</em></p>"""
    ),
    (
        "faq_update",
        1,
        "Add FAQ Schema to Diamonds & Engagement Rings Page",
        "Diamond page has no FAQ section. Add 5 Q&As addressing the natural vs lab-grown distinction and selling process — critical for AI citation.",
        "/diamonds-and-engagement-rings",
        """<h2>FAQ Section for Diamonds & Engagement Rings Page</h2>
<p>Add this FAQ section with FAQPage JSON-LD schema:</p>

<h3>Q: How much is my diamond engagement ring worth?</h3>
<p>A: The value depends on the 4Cs (cut, clarity, carat, color), whether the diamond is natural or lab-grown, and the metal setting. Natural diamonds typically retain 20–60% of retail value, while lab-grown diamonds retain 10–20% (BriteCo, 2026). The gold or platinum setting adds additional melt value.</p>

<h3>Q: Do you buy lab-grown diamonds?</h3>
<p>A: Yes, but lab-grown diamonds are valued differently than natural diamonds. A 1-carat lab-grown diamond averages $1,000 or less in 2026, compared to approximately $4,200 for a comparable natural stone (Tashvi AI, 2026). We use professional equipment to determine origin and price accordingly.</p>

<h3>Q: How do I know if my diamond is natural or lab-grown?</h3>
<p>A: Check your GIA, AGS, or IGI grading report — it will state the origin. Lab-grown diamonds often have "LG" laser-inscribed on the girdle. Jewelry purchased before 2015 almost certainly contains natural diamonds. Our evaluators can make a definitive determination during your appointment.</p>

<h3>Q: Do you buy loose diamonds without a setting?</h3>
<p>A: Yes. We buy loose diamonds of all sizes, cuts, and qualities. Each stone is evaluated individually on cut, clarity, carat, and color using industry-standard grading.</p>

<h3>Q: How quickly will I receive payment for my diamond ring?</h3>
<p>A: Within 30 minutes of accepting your offer. We pay via check, Venmo, or PayPal. There is no obligation — you can decline the offer and take your items home at no cost.</p>

<p><em>Implement as FAQPage JSON-LD schema plus visible accordion on the page.</em></p>"""
    ),
    (
        "faq_update",
        1,
        "Add FAQ Schema to Coins & Bullion Page",
        "Coins page drives highest service-page views (407) with 47s engagement but no FAQ. Critical to add seller-intent FAQs that filter OUT collector queries (per PPC audit).",
        "/coins-bullion",
        """<h2>FAQ Section for Coins & Bullion Page</h2>
<p>Add this FAQ section with FAQPage JSON-LD schema. <strong>Important:</strong> these FAQs are deliberately written with seller-intent language to attract people wanting to sell, not collectors researching values (per PPC audit recommendation).</p>

<h3>Q: Where can I sell my coin collection near Springfield, VA?</h3>
<p>A: Paradigm Experts at 6310-A Springfield Plaza buys gold coins, silver coins, bullion bars, and rounds. We evaluate using real-time precious metals pricing from Kitco.com plus rarity and condition premiums. Call (703) 585-1964 to schedule an appointment.</p>

<h3>Q: How much will I get for gold coins?</h3>
<p>A: Gold coins are valued based on gold content, rarity, and condition. A 1 oz American Gold Eagle contains 1 troy ounce of gold and is worth approximately $4,700+ at May 2026 spot prices (Fortune, May 2026), with potential numismatic premiums for older dates and better conditions. We pay up to 90% of melt value, plus collectible premiums when applicable.</p>

<h3>Q: Do you buy inherited coin collections?</h3>
<p>A: Yes. We specialize in evaluating inherited collections. We sort, identify, and price each coin individually so you understand the value of what you have. Many inherited collections contain coins worth significantly more than face value.</p>

<h3>Q: What types of bullion do you buy?</h3>
<p>A: We buy gold and silver bars, rounds, and coins from all major mints including American Eagles, Canadian Maple Leafs, South African Krugerrands, Austrian Philharmonics, and generic bullion. All bullion is priced against live spot.</p>

<h3>Q: How is selling coins different from selling gold jewelry?</h3>
<p>A: Coins may have numismatic (collector) value above their metal content. A rare coin in excellent condition can be worth multiples of its melt value. We evaluate both the precious metal content and the numismatic premium to give you the highest possible offer.</p>

<p><em>Implement as FAQPage JSON-LD schema plus visible accordion on the page.</em></p>"""
    ),
    (
        "faq_update",
        1,
        "Add FAQ Schema to Main FAQ Page (40+ Questions)",
        "The FAQ page has 40+ well-written Q&As but ZERO FAQPage schema markup. This is the single highest-impact technical fix for AI visibility — FAQ schema is the #1 most-cited format by AI search engines.",
        "/faq",
        """<h2>FAQPage Schema Implementation — Main FAQ Page</h2>
<p>The existing /faq page contains over 40 Q&A pairs across categories (payment, what we buy, shipping, process, appraisals) but has <strong>no FAQPage JSON-LD schema</strong>. Search engines and AI assistants cannot parse the structured Q&A content.</p>

<h3>What to Implement</h3>
<p>Add a FAQPage JSON-LD script block to the page head containing all questions. Prioritize these high-value questions for the schema:</p>

<h3>Payment & Process (highest seller intent)</h3>
<ul>
<li>"How much do you pay for gold/silver/platinum?" — "Up to 90% of melt value based on live Kitco bid price"</li>
<li>"How quickly will I be paid?" — "Within 30 minutes of accepting"</li>
<li>"What payment methods do you accept?" — "Check, Venmo, PayPal"</li>
<li>"Do I need an appointment?" — "Walk-ins welcome, appointments recommended"</li>
</ul>

<h3>What We Buy (service discovery)</h3>
<ul>
<li>"What items do you purchase?" — precious metals, coins, flatware, watches, diamonds, estate jewelry</li>
<li>"Do you buy dental gold?" — Yes</li>
<li>"Do you buy broken jewelry?" — Yes</li>
<li>"What don't you buy?" — Costume jewelry and base metal items</li>
</ul>

<h3>Trust & Safety (decision confidence)</h3>
<ul>
<li>"Are you licensed and insured?" — Licensed, insured, and bonded</li>
<li>"Are my items insured during appraisal?" — Fully insured in our possession</li>
<li>"Can I get my items back?" — Yes, returned at no cost</li>
</ul>

<h3>Implementation</h3>
<p>In Webflow: Page Settings > Custom Code > Head Code. Add a single script tag with type="application/ld+json" containing the FAQPage schema. Include all 40+ questions — Google supports unlimited FAQ entries in schema.</p>"""
    ),

    # ============================================================
    # PRIORITY 2: Springfield Page & Existing Blog Fixes
    # ============================================================
    (
        "freshness_update",
        2,
        "Enhance Springfield Landing Page with FAQ Section and Schema",
        "Springfield page is thin — no FAQ, no service details, no embedded map. As the primary location, it should be the strongest local page.",
        "/springfield",
        """<h2>Springfield Landing Page Enhancement</h2>

<h3>Add FAQ Section (with FAQPage schema)</h3>

<h4>Q: Where is Paradigm Experts located in Springfield?</h4>
<p>A: 6310-A Springfield Plaza, Springfield, VA 22150. We're in the Springfield Plaza shopping center, accessible from I-95 and I-395.</p>

<h4>Q: Do I need an appointment to sell gold or jewelry in Springfield?</h4>
<p>A: Walk-ins are welcome, but appointments are recommended for the best experience. Call (703) 585-1964 to schedule.</p>

<h4>Q: What can I sell at Paradigm Experts Springfield?</h4>
<p>A: Gold jewelry (10K-24K), sterling silver flatware, diamonds, luxury watches (Rolex, Cartier, Patek Philippe, etc.), estate jewelry, coins, and bullion.</p>

<h4>Q: How much do you pay for gold and silver?</h4>
<p>A: Up to 90% of melt value based on the live Kitco bid price. Payment within 30 minutes via check, Venmo, or PayPal.</p>

<h4>Q: What areas do you serve from Springfield?</h4>
<p>A: We serve all of Northern Virginia including Arlington, McLean, Fairfax, Fairfax Station, Lorton, Alexandria, and Ashburn, as well as Maryland and Washington DC. We also offer virtual evaluations for remote sellers.</p>

<h3>Additional Content Needed</h3>
<ul>
<li><strong>Full service list</strong> with brief descriptions for each category</li>
<li><strong>Embedded Google Map</strong> (currently missing)</li>
<li><strong>Current price context</strong> — "Gold: ~$4,700/oz | Silver: ~$84/oz" (update monthly)</li>
<li><strong>Trust badges</strong> — Licensed, Insured, Bonded, "As Seen on Appraisal Roadshow"</li>
<li><strong>LocalBusiness schema</strong> with GeoCoordinates and AreaServed</li>
</ul>"""
    ),
    (
        "freshness_update",
        2,
        "Reformat Existing Blog Posts to Answer-First Q&A Structure",
        "The 3 existing blog posts use narrative format. AI assistants strongly prefer answer-first structure where the key answer appears in the first paragraph. Reformat without changing the content substance.",
        "/blog",
        """<h2>Blog Post Reformatting Guide</h2>
<p>The 3 existing blog posts need structural updates for AI search optimization. AI assistants extract answers from the first 1-2 sentences of a page, so the answer must come first.</p>

<h3>Post 1: "Where to Sell Gold and Silver Near You with Confidence?"</h3>
<p><strong>Current:</strong> Opens with "You have valuable gold and silver..." — narrative lead-in before answering.</p>
<p><strong>Fix:</strong> Open with: "The best place to sell gold and silver is a licensed precious metals dealer who uses live market pricing and pays same-day. In Northern Virginia, Paradigm Experts pays up to 90% of melt value..." Then continue with the existing educational content.</p>

<h3>Post 2: "Where to Sell Diamond Rings for the Best Value?"</h3>
<p><strong>Fix:</strong> Open with the direct answer: "To get the best value for a diamond ring, sell to a specialized jewelry buyer who evaluates the 4Cs and distinguishes natural from lab-grown diamonds — not a pawn shop (which pays 20-50% of value) or generic gold buyer." Add a section addressing the natural vs. lab-grown distinction.</p>

<h3>Post 3: "Where to Sell Gold Near Springfield, VA for the Best Value?"</h3>
<p><strong>Fix:</strong> Open with: "Paradigm Experts at 6310-A Springfield Plaza pays up to 90% of melt value for gold jewelry, with same-day payment. Gold is currently trading near $4,700/oz (May 2026)." Then continue with the process and tips.</p>

<h3>General Rules for All Future Blog Posts</h3>
<ul>
<li><strong>Title as a question</strong> — matches how people query AI assistants</li>
<li><strong>First paragraph = complete answer</strong> in 1-2 sentences (bolded)</li>
<li><strong>Subheadings as follow-up questions</strong> — H3s should be Q&A format</li>
<li><strong>Sources section</strong> at the bottom with citations for all stats</li>
<li><strong>Local context</strong> — mention Springfield, Northern Virginia, specific cities</li>
<li><strong>Seller intent only</strong> — never attract "what is my coin worth" informational traffic</li>
</ul>"""
    ),
]


def build_insert_script() -> str:
    """Build a Python script string to run inside the Docker container."""
    lines = [
        "import sqlite3, uuid, json",
        "conn = sqlite3.connect('/app/data/practicerank.db')",
        "conn.row_factory = sqlite3.Row",
        "",
        f"cid = '{CUSTOMER_ID}'",
        "",
        "# Check customer exists",
        "c = conn.execute('SELECT id FROM customers WHERE id = ?', (cid,)).fetchone()",
        "if not c:",
        "    print(f'ERROR: customer {cid} not found')",
        "    exit(1)",
        "",
        "# Clear existing recs for fresh insert",
        "conn.execute('DELETE FROM content_recommendations WHERE customer_id = ?', (cid,))",
        "print('Cleared existing recommendations')",
        "",
    ]

    for i, r in enumerate(RECS):
        rec_dict = {
            "rec_type": r[0],
            "priority": r[1],
            "title": r[2],
            "description": r[3],
            "target_page": r[4] or "",
            "html_snippet": r[5],
        }
        lines.append(f"r{i} = {repr(rec_dict)}")
        lines.append(f"rid{i} = str(uuid.uuid4())")
        lines.append(f"conn.execute(")
        lines.append(f"    '''INSERT INTO content_recommendations")
        lines.append(f"       (id, customer_id, rec_type, priority, title, description, target_page, html_snippet, status)")
        lines.append(f"       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',")
        lines.append(f"    (rid{i}, cid, r{i}['rec_type'], r{i}['priority'], r{i}['title'], r{i}['description'], r{i}['target_page'], r{i}['html_snippet'], 'draft')")
        lines.append(f")")
        lines.append(f"print(f'Inserted: {{r{i}[\"title\"][:60]}}...')")
        lines.append("")

    lines.append("conn.commit()")
    lines.append("conn.close()")
    lines.append(f"print(f'Done. Inserted {len(RECS)} recommendations for {CUSTOMER_ID}')")

    return "\n".join(lines)


def main():
    script = build_insert_script()

    tmp_path = "/tmp/paradigm_recs.py"
    with open(tmp_path, "w") as f:
        f.write(script)

    print(f"Generated script at {tmp_path}")
    print(f"Total recommendations: {len(RECS)}")
    print()
    for i, r in enumerate(RECS, 1):
        print(f"  {i}. [{r[0]}] P{r[1]} — {r[2][:70]}")
    print()
    print("To deploy to production:")
    print(f"  scp -i ~/.ssh/id_ed25519_do {tmp_path} root@129.212.138.145:/root/paradigm_recs.py")
    print(f"  ssh -i ~/.ssh/id_ed25519_do root@129.212.138.145 'docker cp /root/paradigm_recs.py practicerank-dashboard:/tmp/ && docker exec practicerank-dashboard python /tmp/paradigm_recs.py'")


if __name__ == "__main__":
    main()
