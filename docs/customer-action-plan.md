# DentalRank — Per-Customer Action Plan

Complete playbook for onboarding a new customer and executing monthly SEO/GEO optimization.

---

## Phase 1: Customer Onboarding (Week 1)

### What the Customer Needs to Do

1. **Google Business Profile** — Add `jonlucas@lostrelic.com` as **Manager**
   - Go to business.google.com → Settings → Managers → Add
   - Select "Manager" role (not just "Communications Manager")

2. **Google Search Console** — Add as **Full User**
   - Go to search.google.com/search-console → Settings → Users and permissions → Add user
   - Permission: Full

3. **Google Analytics** — Add as **Editor**
   - Go to analytics.google.com → Admin → Account Access Management → Add user
   - Role: Editor

4. **Google Tag Manager** — Add with **Publish** access
   - Go to tagmanager.google.com → Admin → User Management → Add
   - Account Permission: Publish

5. **Webflow** — Add as site collaborator + provide API token
   - Site Settings → Collaborators → Add
   - Site Settings → Apps & Integrations → Generate API Token (all read/write scopes)

6. **DNS/GoDaddy** — Provide login or add us as delegate
   - We migrate DNS to Cloudflare for CDN, security, and `.txt` file hosting

7. **Apple Business** — Claim or grant access
   - Go to business.apple.com → claim listing if unclaimed (58% of businesses haven't!)
   - Add jonlucas@lostrelic.com as admin

### What We Do During Onboarding

| Task | Details |
|------|---------|
| Run DentalRank audit | Full SEO/AEO/GEO report — gives us the baseline score |
| Migrate DNS to Cloudflare | Set up Cloudflare zone, proxy, WAF bot rules |
| Deploy Cloudflare Worker | Serves `/llms.txt`, `/llms-full.txt`, `/robots.txt` |
| Run GEO Agent (first run) | Crawl site → analyze → generate → publish |
| Audit Cloudflare bot settings | ~27% of sites unknowingly block AI crawlers at CDN layer |
| Set up review card system | QR code → Google review link, print cards for front desk |
| Verify NAP consistency | Name, Address, Phone identical across all directories |
| Submit to citation directories | See Tier 1 + Tier 2 list below |

---

## Phase 2: Google Maps / Google Business Profile (Week 1-2)

### Initial Setup (We Do)
- Verify all business info is accurate and complete
- Set primary category to exact match (e.g., "Dentist" or "Cosmetic Dentist")
- Add all relevant secondary categories (up to 9)
- Upload 10+ photos: office exterior, interior, team, equipment, before/after
- Pre-populate Q&A section with 10-15 common patient questions
- Write initial business description (750 chars max, keyword-rich)
- Set service areas if applicable
- Add all services with descriptions
- Link website, appointment booking URL

### Ongoing (Monthly)
| Task | Frequency | How |
|------|-----------|-----|
| GBP Posts | Weekly | Claude generates → Jon batch-approves → VA posts |
| Review responses | Within 24 hrs | Claude drafts response → VA posts to Google |
| Photo uploads | Monthly | Request 5+ new photos from office manager |
| Q&A updates | Monthly | Claude generates new Q&A from trending patient searches |
| Info accuracy check | Monthly | GEO Agent verifies hours, phone, address match website |
| Performance report | Monthly | GEO Agent generates → auto-email to customer |

### Review Generation (Grade.us + QR Cards — No SMS, No Compliance Issues)

White-labeled review management via **Grade.us** ($40/location on Agency plan) + physical QR review cards. See `docs/grade-us-setup.md` for full platform setup.

1. VA creates Grade.us location profile on `reviews.dentalrank.ai/[practice-slug]`
2. VA configures review funnel: Google (#1), Healthgrades, Facebook, Yelp
3. VA enables negative feedback interception (1-3 star ratings → private form, not public)
4. VA sets up 3-message email drip for follow-up with non-reviewers
5. VA generates QR code → Grade.us landing page (not direct Google link)
6. VA designs business-card-sized review card with QR code + practice branding
7. Practice prints 250 cards (~$20 at Vistaprint)
8. Front desk hands a card to every patient at checkout
9. VA monitors Grade.us dashboard and responds to reviews within 24 hours (Claude-drafted)

**Why this beats direct Google links or SMS automation:**
- Multi-platform reviews from one QR code (Google + Healthgrades + Yelp + Facebook)
- Negative feedback interception protects public ratings
- Automated email drip follows up with non-reviewers (3 messages)
- Centralized review monitoring across 100+ sites
- No TCPA consent, no opt-out tracking, no Twilio costs
- Face-to-face ask when the patient is happiest
- Review widget embeddable on client website

**Referral program (triggered by positive reviews):**
- Zapier trigger: Grade.us "New Review" (4-5 stars) → n8n webhook
- n8n sends referral email with unique code and incentive details
- Incentive examples: $25 credit toward next visit, free take-home whitening kit
- See `docs/grade-us-setup.md` for full referral program details

**Optional extras:**
- Add Grade.us review widget to website footer/reviews page
- Add the review link to the practice's email signature
- Set up a Cloudflare redirect: `hilltopdental.com/review` → Grade.us landing page

---

## Phase 3: Apple Maps / Apple Business (Week 2)

### Why This Matters
- 573-609M monthly active users globally, 75-100M in US
- 58% of businesses have NOT claimed their listing — huge competitive gap
- Apple Maps pulls reviews from **Yelp** and **TripAdvisor** — optimize those profiles
- Apple Maps Ads launching summer 2026 (US/Canada) — early movers win

### Setup (We Do)
1. Claim listing at business.apple.com
2. Select primary category carefully (most important ranking factor)
3. Add up to 9 secondary categories
4. Upload professional photos (+42% direction requests, +35% website clicks)
5. Add Showcases (like GBP posts) for promotions
6. Add action buttons: appointment booking, phone call
7. Verify hours, address, phone match Google exactly

### Ongoing (Monthly)
| Task | Frequency | How to Automate |
|------|-----------|-----------------|
| Update Showcases | Bi-weekly | Claude generates, Jon publishes |
| Photo refresh | Monthly | Same photos as GBP |
| Verify listing accuracy | Monthly | Automated check against customer config |
| Yelp profile optimization | Monthly | Since Apple Maps sources Yelp reviews |

---

## Phase 4: Content Strategy — Expert Quotes, Stats, FAQs (Week 2-3)

### How to Add Expert Quotes to Every Service Page

This is a high-impact GEO tactic — AI engines strongly favor credentialed expert quotes.

**Process:**
1. GEO Agent analyzes each service page
2. Claude generates 2-3 expert quotes per page attributed to the practice's actual dentist
3. Quotes are injected into the Webflow page via API

**Example for a Dental Implants page:**

```html
<blockquote>
  <p>"For patients missing teeth, dental implants are the closest thing to getting
  your natural teeth back. With guided surgery technology, we can place an implant
  in about an hour with minimal discomfort."</p>
  <cite>— Dr. David Gallup, DDS, 27 years experience in implant dentistry</cite>
</blockquote>
```

**Rules for effective expert quotes:**
- Always include provider name + credentials + years experience
- Make the quote answer a specific patient concern (pain, cost, timeline)
- Include a stat or data point in at least one quote per page
- Place the quote in the first 30% of the page (44.2% of AI citations come from the intro)
- Update quotes quarterly with new stats to maintain freshness

### How to Add Statistics to Every Page

Verifiable statistics with sources help AI engines cite you. Include them where relevant.

**Where to get stats:**
- ADA (American Dental Association) reports
- Practice-specific data (# of implants placed, patient satisfaction rate, years in practice)
- Insurance/cost data (average costs in their city)
- Industry benchmarks (success rates for procedures)

**Example stats to embed:**
- "Dental implant success rates exceed 95% over 10 years (ADA 2025)"
- "Dr. Gallup has placed over 3,000 dental implants since 1999"
- "The average cost of a single dental implant in Austin ranges from $3,000-$5,500"
- "Same-day implant procedures reduce healing time by up to 50%"

**Automation:** Claude generates stats + sources → GEO Agent injects into page content via Webflow CMS API

### Pages Every Dental Practice MUST Have

| Page | Why | Target Keyword |
|------|-----|---------------|
| Home | Foundation page, Dentist schema | `dentist [city]` |
| Each major service | Individual ranking + FAQ schema | `[service] [city]` |
| Emergency Dentist | High-intent, high-volume | `emergency dentist [city]` |
| Dental Implant Cost | Price-comparison traffic | `dental implant cost [city]` |
| Insurance / Financing | Removes friction | `dentist that accepts [plan] [city]` |
| About / Meet the Team | E-E-A-T signals, provider bios | `best dentist [city]` |
| New Patient Info | Reduces no-shows | `new patient dentist [city]` |
| Reviews / Testimonials | Social proof | `[practice name] reviews` |
| Each neighborhood landing page | Local pack targeting | `dentist [neighborhood]` |
| FAQ page | Drives "People Also Ask" boxes | Various long-tail |
| Blog (monthly posts) | Freshness signal | Various informational |

### FAQ Strategy (Highest GEO Impact)

Every service page needs 4-6 FAQ entries. These drive:
- Google "People Also Ask" boxes
- AI assistant citations (FAQ is the most-cited content structure)
- FAQPage schema markup (helps AI engines parse Q&A content)

**The GEO Agent already generates these.** Here's the monthly update cycle:

1. GEO Agent crawls current pages
2. Claude analyzes and generates new/updated FAQ entries per service
3. FAQPage JSON-LD schema is generated automatically
4. Schema is published to Webflow site head via API

**What makes a good FAQ answer:**
- Start with the direct answer (TLDR-first, first 40-60 words)
- Include the city name
- Mention the provider by name
- Include a stat or data point
- Keep to 40-60 words per paragraph (optimal for AI extraction)

---

## Phase 5: Monthly Maintenance Cycle (Automated by GEO Agent)

### What the GEO Agent Does Each Month (Already Built)

```
1. CRAWL → Webflow API → get all page content
2. RAG UPDATE → Store page embeddings in per-customer SQLite DB
3. ANALYZE → Claude 4.6 reviews all content vs best practices
4. GENERATE → llms.txt, llms-full.txt, schema markup, robots.txt
5. PUBLISH → Push to Webflow + Cloudflare
6. REPORT → Summary of changes, gaps, recommendations
```

### What Needs Manual Attention Each Month

| Task | Who | Time | Notes |
|------|-----|------|-------|
| Review Claude-generated FAQ answers | Jon | 15 min | Spot-check for accuracy |
| Approve GBP post drafts | Jon | 10 min | Batch approve 4 posts at once |
| Respond to Google reviews | VA | 15 min/wk | Claude drafts, VA posts |
| Check for new competitor pages | GEO Agent | Auto | Add to monthly analysis |
| Update provider bios/photos | Office manager | 15 min | Quarterly email reminder |
| Restock review cards at front desk | VA | 5 min | Check with office monthly |

### Content Freshness Strategy (Why Monthly Matters)

**Key research finding:** AI engines favor recent content — the citation freshness window is roughly 1–2 years, so refresh monthly (quarterly minimum).

**Monthly refresh targets:**
1. **Update stats** — Replace old numbers with current data
2. **Rotate expert quotes** — Fresh quotes with new angles
3. **Add new FAQ entries** — 1-2 new questions per service page per month
4. **Update dates** — Remove references to past dates, update "as of" timestamps
5. **Add new blog post** — 1 fresh article per month (Claude-generated, Jon reviews)
6. **Regenerate llms.txt** — Reflects any new pages/services/provider changes
7. **Update schema markup** — Any new services, providers, or review data

**Content decay timeline:**
- Weeks 1-8: Peak citation probability
- Weeks 8-13: Still cited frequently
- Weeks 13+: Rapid decay in AI citations
- **Our monthly cycle keeps content under 5 weeks old — well within the citation window**

---

## Phase 6: Citation Building (Week 3-4, then ongoing)

### Tier 1 — Must Have (Critical for Maps + AI)
| Directory | DA | Action | Automate? |
|-----------|-----|--------|-----------|
| Google Business Profile | 100 | Already done in Phase 2 | Yes — GBP API |
| Apple Business | 95 | Already done in Phase 3 | Partial |
| Yelp | 93 | Claim + optimize (Apple Maps sources reviews from here) | Manual claim, auto-monitor |
| Healthgrades | 87 | Claim + full profile | Manual claim |
| Zocdoc | 82 | Claim (6M+ monthly users) | Manual claim |
| Facebook Business | 96 | Create/claim page | Manual, then auto-post |
| Bing Places | 95 | Import from GBP | Auto-import |

### Tier 2 — Important (Build Over Months 2-3)
Dentistry.com, RateMDs, Vitals (DA 65+), YP.com, BBB, WebMD, 1-800-Dentist, Angi, Nextdoor

### NAP Consistency Rule
Name, Address, Phone must be **EXACTLY identical everywhere** — even "St." vs "Street" matters.
Businesses with clean citations generate **2.3x more calls** (BrightLocal 2025).

**Use BrightLocal** ($44/mo shared across all customers) to:
- Audit existing citations
- Find inconsistencies
- Track citation health over time

---

## Monthly Customer Report (Automated)

Send to customer on the 1st of each month:

```
DentalRank Monthly Report — [Practice Name]
Month: [Month Year]

SCORES
- Overall SEO Score: XX/100 (↑X from last month)
- AI Search Readiness: XX/100
- Local Visibility: XX/100

WHAT WE DID
- Updated llms.txt with [N] new page references
- Added [N] FAQ entries across [N] service pages
- Published [N] schema markup updates
- Generated [N] GBP posts
- Responded to [N] reviews

CONTENT GAPS IDENTIFIED
- [List of recommended new pages]
- [List of pages needing content updates]

PRIORITY ACTIONS FOR NEXT MONTH
1. [Action 1]
2. [Action 2]
3. [Action 3]

AI SEARCH VISIBILITY
- Practice mentioned in [N] AI assistant responses (sampled)
- Top queries driving AI citations: [list]
```

---

## Automation Summary — What's Automated vs Manual

| Task | Automated? | Tool | Manual Effort |
|------|------------|------|---------------|
| Site crawl + analysis | Yes | GEO Agent | None |
| llms.txt generation | Yes | GEO Agent | None |
| Schema markup generation + publish | Yes | GEO Agent | None |
| robots.txt generation | Yes | GEO Agent | None |
| FAQ generation | Yes | GEO Agent + Claude | Jon reviews (15 min/mo) |
| Expert quote generation | Yes | GEO Agent + Claude | Jon reviews (10 min/mo) |
| GBP post drafts | Yes | Claude generates | Jon batch-approves, VA posts (10 min/mo) |
| Review generation | Yes | Grade.us + QR cards | QR → Grade.us funnel, email drip follow-up, multi-platform |
| Review monitoring | Yes | Grade.us | Centralized dashboard, alerts, portfolio reports |
| Review responses | Yes | Claude drafts | VA posts within 24 hrs (15 min/wk) |
| Referral program | Yes | Grade.us → Zapier → n8n | Auto-sends referral email after 4-5 star review |
| Citation monitoring | Yes | BrightLocal | None |
| Monthly report | Yes | GEO Agent | None |
| New page creation | Partial | Claude drafts content | Jon reviews, VA publishes |
| Photo collection | No | Email reminder to office | Office manager (15 min/quarter) |
| Apple Maps updates | Partial | Manual publish | VA (10 min/mo) |

**Total manual time per customer per month: ~45-60 minutes**
**At $3,000/month per customer, that's $3,000-4,000/hour effective rate.**

---

## Optimal Delegation Model — Who Does What

The goal: **customer does almost nothing**, Jon does light approvals, a VA handles all manual grunt work.

### What the Customer MUST Do Themselves (Can't Be Delegated)

These require the business owner's identity or legal authority:

| Task | Why Only They Can Do It | Time | When |
|------|------------------------|------|------|
| Grant GBP Manager access | Google requires account owner to add managers | 2 min | Once |
| Grant Google Search Console access | Owner must add users | 1 min | Once |
| Grant Google Analytics access | Owner must add users | 1 min | Once |
| Grant GTM access | Owner must add users | 1 min | Once |
| Claim Apple Business listing | Requires business verification (phone/mail) | 10 min | Once |
| Approve review responses (optional) | Their name, their reputation | 5 min/mo | Monthly |
| Provide DNS credentials or delegate | Security — they own the domain | 2 min | Once |

**Total customer time: ~20 minutes one-time setup, then 5 min/month (optional review approvals).**

If the customer wants to be 100% hands-off on reviews, set up a "blanket approval" rule: Claude-drafted responses go live automatically unless flagged by sentiment analysis. Most practices are fine with this once they've seen the quality of the drafts for a month or two.

### What Jon Does (Strategy + Approvals Only)

| Task | Time | Frequency |
|------|------|-----------|
| Initial DentalRank audit + sales call | 30 min | Once per customer |
| Review GEO Agent output (spot-check) | 10 min | Monthly |
| Approve GBP post batch (4 posts) | 5 min | Monthly |
| Review content gap recommendations | 10 min | Monthly |
| Client check-in email/call | 15 min | Monthly |

**Total Jon time per customer: ~30 min onboarding + 40 min/month**
**At 20 customers: ~13 hours/month total**

### What a VA Does (All Manual Execution)

Hire a VA at $5-8/hour (Philippines, dental marketing experience preferred). One VA can handle 15-20 customers.

#### Onboarding Tasks (VA executes with customer credentials)

| Task | Details | Time | Frequency |
|------|---------|------|-----------|
| Set up Cloudflare zone | Migrate DNS, configure WAF, bot rules | 30 min | Once |
| Deploy Cloudflare Worker | Copy/paste worker script, bind KV namespace | 15 min | Once |
| Generate review QR card | Create QR code, design card, send to print | 20 min | Once |
| Claim Yelp listing | Create/claim, fill out full profile | 15 min | Once |
| Claim Healthgrades | Create/claim, fill out full profile | 15 min | Once |
| Claim Zocdoc | Create/claim, add services + insurance | 15 min | Once |
| Claim Facebook Business | Create page, add info, link website | 10 min | Once |
| Import to Bing Places | Import from GBP (one-click) | 5 min | Once |
| Set up Apple Business profile | Categories, photos, hours, action buttons | 20 min | Once |
| Submit to Tier 2 directories | 10-12 directories, copy-paste NAP info | 45 min | Once |
| Upload initial GBP photos | 10+ photos from customer | 10 min | Once |
| Pre-populate GBP Q&A | 10-15 questions (Claude-generated) | 15 min | Once |
| Write GBP business description | 750 chars, keyword-rich (Claude drafts) | 10 min | Once |
| Run BrightLocal NAP audit | Check consistency, fix discrepancies | 20 min | Once |

**Total VA onboarding time per customer: ~4 hours**
**At $7/hour = $28 per customer onboarding**

#### Monthly Maintenance Tasks (VA)

| Task | Details | Time | Frequency |
|------|---------|------|-----------|
| Publish GBP posts | Post Claude-drafted content to GBP | 10 min | Weekly |
| Post review responses | Copy Claude drafts, post to Google/Yelp | 15 min | Weekly |
| Upload new photos to GBP + Apple | Get from office, upload to both | 10 min | Monthly |
| Update Apple Maps Showcases | Create new showcase from Claude draft | 10 min | Bi-weekly |
| Publish blog post | Copy Claude draft to Webflow CMS, format | 15 min | Monthly |
| BrightLocal citation check | Run audit, fix any NAP inconsistencies | 10 min | Monthly |
| Create new Webflow pages | From Claude-drafted content (neighborhood pages, etc.) | 20 min | As needed |
| Verify listing accuracy | Spot-check GBP, Apple, Yelp for drift | 5 min | Monthly |

**Total VA monthly time per customer: ~3-4 hours**
**At $7/hour = ~$25/month per customer**

### What's Fully Automated (No Human Touch)

| Task | Tool | Notes |
|------|------|-------|
| Site crawl + content analysis | GEO Agent | Runs monthly via cron |
| llms.txt / llms-full.txt generation | GEO Agent | Published to Cloudflare KV |
| Schema markup (JSON-LD) generation + publish | GEO Agent | Published to Webflow head |
| robots.txt generation | GEO Agent | Published to Cloudflare KV |
| FAQ schema generation | GEO Agent + Claude | Schema auto-published |
| Expert quote drafting | Claude | VA or Jon publishes |
| Review generation | QR card at front desk | Staff hands to patients — no software needed |
| Review response drafting | Claude | VA posts within 24 hrs |
| Monthly report generation | GEO Agent | Auto-emailed to customer |
| Citation health monitoring | BrightLocal | Alerts on drift |

### Accounts We Sign Up For (Per Customer)

| Service | Who Signs Up | Account Type | Cost |
|---------|-------------|-------------|------|
| Grade.us | Jon (shared Agency plan) | Location profile per customer | $40/location/mo (Agency), $25/location at 100+ |
| BrightLocal | Jon (shared) | Citations tracked per location | Included in $44/mo shared |
| Cloudflare | Jon (add zone) | Zone per customer domain | Free tier |
| Google Business Profile | Customer owns, we manage | Manager access | Free |
| Apple Business | Customer owns, we manage | Admin access | Free |
| Yelp Business | VA claims for customer | Owner access (customer email) | Free |
| Healthgrades | VA claims for customer | Provider access | Free |
| Zocdoc | VA claims for customer | Provider access | Free (listing), paid (booking) |
| Facebook Business | VA creates for customer | Page admin | Free |
| Bing Places | VA imports from GBP | Owner access | Free |

**Per-customer incremental cost: ~$40/mo (Grade.us) + ~$2-4/mo (Claude + Voyage API) + ~$28/mo (VA time) = ~$70-72/mo**
**Revenue: $3,000/mo**
**Gross margin: ~97.6%**

### Scaling Plan

| Customers | Jon Time/Mo | VAs Needed | VA Cost/Mo | Revenue/Mo | Profit/Mo |
|-----------|-------------|------------|-----------|------------|-----------|
| 5 | 3.5 hrs | 0.5 (part-time) | $175 | $15,000 | ~$14,200 |
| 10 | 7 hrs | 1 | $350 | $30,000 | ~$28,700 |
| 20 | 13 hrs | 1.5 | $525 | $60,000 | ~$58,100 |
| 50 | 33 hrs | 3 | $1,050 | $150,000 | ~$147,000 |

At 20+ customers, Jon should hire a part-time account manager (~$20/hr, 10 hrs/week) to handle approvals and client calls, reducing his time to strategy/sales only.

---

## Outside-the-Box Automation Ideas

### 1. AI Visibility Monitoring Agent
Build a second agent that monthly queries ChatGPT, Claude, Perplexity, and Google AI Overviews with searches like "best dentist in [city]", "dental implants [city]", "emergency dentist near [address]" and checks if the practice appears in the responses. Track visibility score over time.

### 2. Competitor Watch Agent
Monthly crawl competitor websites, check their schema, llms.txt, GBP activity. Alert if a competitor adds new content or services we should respond to.

### 3. Auto-Generated Neighborhood Pages
For a practice in Austin, generate landing pages for every major neighborhood: "Dentist in Mueller", "Dentist in Hyde Park", "Dentist in Cedar Park". Each gets unique content, schema, and local keywords. Claude generates, GEO Agent publishes.

### 4. Review Sentiment Dashboard (Grade.us)
Grade.us monitors reviews across 100+ sites with centralized alerting and portfolio reports. Claude can summarize sentiment trends from Grade.us data. Alert if negative trend detected. Suggest service improvements based on common complaints. Already set up during onboarding — no additional build needed.

### 5. Patient Question Mining
Use Google Search Console data to find actual patient searches → feed into FAQ generation. The best FAQs answer questions people are actually asking, not what we think they're asking.

### 6. Automated Blog Content Calendar
Claude generates a 12-month content calendar based on seasonal dental trends (back-to-school cleanings, holiday whitening, New Year smile goals). Drafts articles monthly, Jon reviews and publishes.

### 7. Voice Search Optimization
Optimize for "Hey Siri, find a dentist near me" by ensuring Apple Maps, schema markup, and conversational FAQ content all align. Voice search queries are longer and more conversational — adjust FAQ format accordingly.
