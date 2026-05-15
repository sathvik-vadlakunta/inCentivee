# DentalRank — Customer Onboarding Checklist

Per-customer checklist. Every task is labeled: **CUSTOMER**, **VA**, or **SALES** (Jon).
Print one per customer. Fill in the info section first, then work through the checklist.

---

## Customer Information (Collect on Sales Call)

**SALES collects all of this on the first call or via intake form.**

### Practice Info
| Field | Value |
|-------|-------|
| Practice Name | ________________________________ |
| Practice Legal Name (if different) | ________________________________ |
| Website URL | ________________________________ |
| Street Address | ________________________________ |
| City | ________________________________ |
| State | ________________________________ |
| ZIP Code | ________________________________ |
| Main Phone | ________________________________ |
| Email (for public listings) | ________________________________ |
| Office Hours | ________________________________ |
| Emergency/After-Hours Available? | Yes / No |
| Year Established | ________________________________ |
| Languages Spoken | ________________________________ |

### Providers (repeat per provider)
| Field | Provider 1 | Provider 2 | Provider 3 |
|-------|-----------|-----------|-----------|
| Full Name | __________ | __________ | __________ |
| Credentials (DDS/DMD) | __________ | __________ | __________ |
| Specialties | __________ | __________ | __________ |
| Years Experience | __________ | __________ | __________ |
| Short Bio (2-3 sentences) | __________ | __________ | __________ |
| Headshot Photo? | Y / N | Y / N | Y / N |

### Services Offered
| Field | Value |
|-------|-------|
| Primary Services | ________________________________ |
| Specialty Services | ________________________________ |
| Signature/Flagship Procedure | ________________________________ |
| Approx. Price Ranges (if willing to share) | ________________________________ |

### Insurance & Payment
| Field | Value |
|-------|-------|
| Insurance Plans Accepted | ________________________________ |
| Financing Options (CareCredit, etc.) | ________________________________ |
| Payment Methods Accepted | ________________________________ |

### Brand & Marketing
| Field | Value |
|-------|-------|
| Brand Voice (how do you want to sound?) | ________________________________ |
| Top 3 Competitors (who do you compete with?) | ________________________________ |
| Neighborhoods/Areas You Serve | ________________________________ |
| Unique Selling Points (what makes you different?) | ________________________________ |
| Any Claims to Avoid? (old address, old name, etc.) | ________________________________ |

### Social & Online Presence
| Field | Value |
|-------|-------|
| Google Business Profile URL | ________________________________ |
| Apple Maps Listing Claimed? | Yes / No / Don't Know |
| Yelp Page URL | ________________________________ |
| Facebook Page URL | ________________________________ |
| Instagram Handle | ________________________________ |
| Other Profiles (Healthgrades, Zocdoc, etc.) | ________________________________ |
| Approx. Google Review Count + Rating | ________________________________ |

### Technical Access (Collect After Contract Signed)
| Field | Value | Status |
|-------|-------|--------|
| Webflow Site ID (Site Settings > General > bottom) | ________________________________ | [ ] Received |
| Webflow API Token (Site Settings > Apps & Integrations > API Access) | ________________________________ | [ ] Received |
| Webflow API Token Scopes: Sites, Pages, Custom Code, CMS (all R/W) | ________________________________ | [ ] Verified |
| DNS Provider (GoDaddy, Namecheap, etc.) | ________________________________ | [ ] Received |
| DNS Login or Delegate Access | ________________________________ | [ ] Received |
| Google Account Email (for GBP/GSC/GA) | ________________________________ | [ ] Received |
| Existing Google Analytics Property ID | ________________________________ | [ ] Received |
| Existing GTM Container ID | ________________________________ | [ ] Received |
| Photos (office, team, equipment, 10+ minimum) | ________________________________ | [ ] Received |

---

## Onboarding Checklist

### Week 1, Day 1-2: Access Grants (CUSTOMER does, SALES guides)

These require the customer's own Google/Apple account. Send them a step-by-step email with screenshots. SALES should walk them through it on a call if needed.

| # | Task | Who | Status |
|---|------|-----|--------|
| 1 | Grant Google Business Profile **Manager** access to jonlucas@lostrelic.com | CUSTOMER | [ ] |
| 2 | Grant Google Search Console **Full User** access to jonlucas@lostrelic.com | CUSTOMER | [ ] |
| 3 | Grant Google Analytics **Editor** access to jonlucas@lostrelic.com | CUSTOMER | [ ] |
| 4 | Grant Google Tag Manager **Publish** access to jonlucas@lostrelic.com | CUSTOMER | [ ] |
| 5 | Add jonlucas@lostrelic.com as Webflow site **Collaborator** (see Webflow steps below) | CUSTOMER | [ ] |
| 6 | Generate Webflow **Site API token** with all required scopes (see Webflow steps below) | CUSTOMER | [ ] |
| 6b | Send us the Webflow **Site ID** (see Webflow steps below) | CUSTOMER | [ ] |
| 7 | Provide DNS login credentials or add us as delegate | CUSTOMER | [ ] |
| 8 | Claim Apple Business listing at business.apple.com (if unclaimed) | CUSTOMER | [ ] |
| 9 | Grant Apple Business **Admin** access to jonlucas@lostrelic.com | CUSTOMER | [ ] |
| 10 | Send 10+ office photos (exterior, interior, team, equipment) | CUSTOMER | [ ] |
| 11 | Send provider headshots (per provider) | CUSTOMER | [ ] |

**Send the customer a single intake email with all 11 items. Follow up at Day 3 if incomplete.**

#### Webflow Access — Step-by-Step Instructions for Customer

Send these exact steps to the customer. They need to be a Workspace Owner or Admin in Webflow.

**Step A: Add us as a Site Collaborator**

1. Log in to Webflow at **webflow.com**
2. Open your site's **Dashboard** (click the site thumbnail)
3. Go to **Site Settings** (gear icon in the left sidebar)
4. Click **Members** in the left menu
5. Click **Invite Collaborator**
6. Enter email: `jonlucas@lostrelic.com`
7. Set role to **Can Edit** (we need access to custom code and site settings)
8. Click **Send Invite**

**Step B: Generate a Site API Token**

We need an API token to automatically publish SEO improvements (schema markup, meta tags) to your site. This token only works for your specific site.

1. In the same **Site Settings**, click **Apps & Integrations** in the left menu
2. Scroll down to the **API Access** section
3. Click **Generate API Token**
4. Name it: `PracticeRank`
5. Enable these scopes (permissions):
   - **Sites: Read and Write** — needed to publish changes
   - **Pages: Read and Write** — needed to update page metadata and custom code
   - **Custom Code: Read and Write** — needed to inject JSON-LD schema markup
   - **CMS: Read and Write** — needed to manage blog posts and dynamic content
6. Click **Generate Token**
7. **Copy the token immediately** — Webflow only shows it once
8. Send the token to us via a secure method (NOT email). Options:
   - Share via **1Password** or **LastPass** shared vault
   - Use **onetimesecret.com** — paste the token, send us the link
   - Tell us on a call and we'll type it in

**Step C: Send us the Site ID**

1. In **Site Settings** > **General**, scroll to the bottom
2. The **Site ID** is shown under "Site ID" — it looks like `site_abc123def456`
3. Copy and send it to us (this is not sensitive — it's fine over email)

**Important notes for the customer:**
- The API token is like a password — don't share it over email
- We only use the token for automated SEO updates (schema markup, meta tags, blog posts)
- You can revoke the token anytime in Site Settings > Apps & Integrations
- We never modify your visual design — only invisible SEO metadata

### Week 1, Day 1-2: Initial Audit & Setup (SALES)

| # | Task | Who | Status |
|---|------|-----|--------|
| 12 | Run DentalRank audit report on customer's website | SALES | [ ] |
| 13 | Review audit with customer, explain baseline scores | SALES | [ ] |
| 14 | Create customer record in tracking spreadsheet/Notion | SALES | [ ] |
| 15 | Add customer to `customers.json` config file | SALES | [ ] |
| 16 | Create customer Slack/notification channel (internal) | SALES | [ ] |

### Week 1, Day 2-4: Technical Setup (VA)

These can start as soon as DNS credentials and Webflow access are received.

| # | Task | Who | Status |
|---|------|-----|--------|
| 17 | Migrate DNS to Cloudflare — create zone, update nameservers | VA | [ ] |
| 18 | Configure Cloudflare WAF — audit bot rules, ensure AI search bots NOT blocked | VA | [ ] |
| 19 | Deploy Cloudflare Worker for /llms.txt, /llms-full.txt, /robots.txt | VA | [ ] |
| 20 | Create Cloudflare KV namespace (GEO_FILES) | VA | [ ] |
| 21 | Verify Webflow API token works (test API call) | VA | [ ] |
| 22 | Run GEO Agent first run (dry-run mode) — verify output looks correct | VA | [ ] |
| 23 | SALES reviews GEO Agent output | SALES | [ ] |
| 24 | Run GEO Agent first run (publish mode) — goes live | VA | [ ] |
| 25 | Verify /llms.txt, /llms-full.txt, /robots.txt are accessible on customer domain | VA | [ ] |
| 26 | Verify JSON-LD schema appears in page source (view-source:domain.com) | VA | [ ] |
| 26a | Validate schema with https://search.google.com/test/rich-results — 0 errors | VA | [ ] |
| 26b | Validate schema with https://validator.schema.org/ — 0 errors, 0 warnings | VA | [ ] |

### Week 1, Day 3-5: Google Business Profile Setup (VA)

| # | Task | Who | Status |
|---|------|-----|--------|
| 27 | Verify all GBP business info matches customer info sheet exactly | VA | [ ] |
| 28 | Set primary category (exact match — e.g., "Dentist") | VA | [ ] |
| 29 | Add all relevant secondary categories (up to 9) | VA | [ ] |
| 30 | Write business description (750 chars, keyword-rich) — Claude drafts, SALES approves | VA | [ ] |
| 31 | Upload all customer photos to GBP (10+ minimum) | VA | [ ] |
| 32 | Add all services with descriptions | VA | [ ] |
| 33 | Add appointment booking URL | VA | [ ] |
| 34 | Set service areas | VA | [ ] |
| 35 | Pre-populate Q&A section (10-15 questions — Claude generates) | VA | [ ] |
| 36 | Verify hours match website exactly | VA | [ ] |

### Week 2, Day 6-8: Apple Maps / Apple Business Setup (VA)

| # | Task | Who | Status |
|---|------|-----|--------|
| 37 | Verify Apple Business listing is claimed and approved | VA | [ ] |
| 38 | Set primary category (most important ranking factor) | VA | [ ] |
| 39 | Add up to 9 secondary categories | VA | [ ] |
| 40 | Upload professional photos (same set as GBP) | VA | [ ] |
| 41 | Add action buttons (appointment booking, phone call) | VA | [ ] |
| 42 | Create first Showcase (promotion or welcome) | VA | [ ] |
| 43 | Verify hours, address, phone EXACTLY match Google | VA | [ ] |

### Week 2, Day 6-8: Citation Building (VA)

| # | Task | Who | Status |
|---|------|-----|--------|
| 44 | Claim/create Yelp Business listing — full profile | VA | [ ] |
| 45 | Claim/create Healthgrades profile | VA | [ ] |
| 46 | Claim/create Zocdoc profile | VA | [ ] |
| 47 | Create/claim Facebook Business page | VA | [ ] |
| 48 | Import to Bing Places from GBP | VA | [ ] |
| 49 | Submit to Tier 2 directories (Dentistry.com, RateMDs, Vitals, YP.com, BBB, WebMD, 1-800-Dentist, Angi, Nextdoor) | VA | [ ] |
| 50 | Run BrightLocal NAP audit — verify NAP consistency across all listings | VA | [ ] |
| 51 | Fix any NAP inconsistencies found | VA | [ ] |

### Week 2-3, Day 8-12: Content Optimization (VA + SALES)

| # | Task | Who | Status |
|---|------|-----|--------|
| 52 | Review GEO Agent content gap analysis — identify missing pages | SALES | [ ] |
| 53 | Claude generates expert quotes for each service page (2-3 per page) | VA | [ ] |
| 54 | SALES reviews expert quotes for accuracy | SALES | [ ] |
| 55 | VA publishes expert quotes to Webflow pages | VA | [ ] |
| 56 | Claude generates stats/data points for each service page | VA | [ ] |
| 57 | VA adds stats to Webflow pages | VA | [ ] |
| 58 | Create any critical missing pages (Emergency Dentist, Implant Cost, etc.) | VA | [ ] |
| 59 | Claude generates neighborhood landing pages (if applicable) | VA | [ ] |
| 60 | VA publishes neighborhood pages to Webflow | VA | [ ] |
| 61 | Claude generates first blog post | VA | [ ] |
| 62 | SALES reviews blog post | SALES | [ ] |
| 63 | VA publishes blog post | VA | [ ] |

### Week 2-3: Review Generation System — Grade.us + QR Cards (VA + CUSTOMER)

White-labeled review management via **Grade.us** ($40/location) + physical QR review cards at the front desk. No SMS, no TCPA compliance issues. See `docs/grade-us-setup.md` for full platform setup details.

**How it works:** QR card at checkout → Grade.us white-labeled landing page → patient picks Google/Healthgrades/Yelp → unhappy patients intercepted by negative feedback filter → Grade.us sends follow-up email drip if patient doesn't review immediately.

**Why this works:**
- Face-to-face ask right when the patient is happiest (just had a good visit)
- Multi-platform reviews (Google + Healthgrades + Yelp + Facebook) from one link
- Negative feedback interception protects public ratings
- Automated email drip follows up with non-reviewers (3 messages)
- Centralized review monitoring dashboard across all sites
- No TCPA/consent issues — patient voluntarily scans QR code, email drip is opt-in

| # | Task | Who | Status |
|---|------|-----|--------|
| 64 | Create Grade.us location profile on `reviews.dentalrank.ai/[practice-slug]` | VA | [ ] |
| 65 | Configure review sites: Google (#1), Healthgrades, Facebook, Yelp | VA | [ ] |
| 66 | Enable negative feedback interception (1-3 stars → internal form) | VA | [ ] |
| 67 | Set up 3-message email drip campaign in Grade.us | VA | [ ] |
| 68 | Look up practice's Google Place ID for direct review link | VA | [ ] |
| 69 | Create short redirect URL (e.g., `hilltopdental.com/review`) via Cloudflare → Grade.us page | VA | [ ] |
| 70 | Generate QR code pointing to Grade.us landing page | VA | [ ] |
| 71 | Design review card (business card size) with QR code, practice logo, "We'd love your feedback!" | VA | [ ] |
| 72 | Send card design to customer for printing (Vistaprint, ~$20 for 250 cards) | VA | [ ] |
| 73 | Train front desk staff: hand card to every patient at checkout | SALES | [ ] |
| 74 | Set up acrylic card holder for front desk + each operatory checkout | CUSTOMER | [ ] |
| 75 | Generate Grade.us review widget embed code, add to Webflow reviews page | VA | [ ] |
| 76 | (Optional) Add review link to practice's email signature | VA | [ ] |
| 77 | (Optional) Add "Leave a Review" button to website footer via Webflow | VA | [ ] |

**Review monitoring + responses (via Grade.us dashboard):**

| # | Task | Who | Status |
|---|------|-----|--------|
| 78 | Configure Grade.us review alerts — CC practice owner on all new reviews | VA | [ ] |
| 79 | Set up automated portfolio report (weekly/monthly, white-labeled) | VA | [ ] |
| 80 | Create review response templates — Claude drafts 5 positive + 3 negative | VA | [ ] |
| 81 | Train VA to respond to reviews within 24 hours using templates | SALES | [ ] |

**Referral program (triggered by positive reviews):**

| # | Task | Who | Status |
|---|------|-----|--------|
| 82 | Set up Zapier trigger: Grade.us "New Review" → n8n webhook | VA | [ ] |
| 83 | Configure n8n referral email flow (sends referral code after 4-5 star review) | VA | [ ] |
| 84 | Create referral email template with practice branding + incentive details | VA | [ ] |
| 85 | Confirm referral incentive with practice (e.g., $25 credit, free whitening kit) | SALES | [ ] |
| 86 | Test full flow: QR scan → review → referral email received | VA | [ ] |

### Week 3: Automated Monitoring Setup (VA)

These are the "future ideas" that are easy to add to onboarding — they're just scheduled queries, no new code needed.

| # | Task | Who | Status |
|---|------|-----|--------|
| 87 | Set up AI Visibility Monitor — configure 10 search queries per customer | VA | [ ] |
| 88 | Set up Competitor Watch — add 2-3 competitor domains to monitor | VA | [ ] |
| 89 | Connect Google Search Console data feed for Patient Question Mining | VA | [ ] |
| 90 | Generate 12-month blog content calendar with Claude | VA | [ ] |
| 91 | SALES reviews content calendar with customer | SALES | [ ] |

### Week 3-4: QA & Handoff (SALES)

| # | Task | Who | Status |
|---|------|-----|--------|
| 92 | Full QA: verify all schema markup renders correctly | VA | [ ] |
| 92a | Schema QA: run internal validator (`python -m geo_agent.schema_validator --customer <id>`) — must pass with 0 errors | VA | [ ] |
| 92b | Schema QA: test with **Google Rich Results Test** — go to https://search.google.com/test/rich-results → enter customer domain → verify 0 errors on all detected items (Dentist, FAQPage, etc.) | VA | [ ] |
| 92c | Schema QA: test with **Schema.org Validator** — go to https://validator.schema.org/ → enter customer domain → verify 0 errors, 0 warnings across all detected types | VA | [ ] |
| 92d | Schema QA: if either external validator shows errors, fix in Code Injection / generator, re-test until clean | VA | [ ] |
| 93 | Full QA: test /llms.txt, /llms-full.txt, /robots.txt from external network | VA | [ ] |
| 94 | Full QA: verify all directory listings are live and NAP-consistent | VA | [ ] |
| 95 | Full QA: verify GBP appears correctly in Google Maps search | VA | [ ] |
| 96 | Full QA: verify Apple Maps listing appears correctly | VA | [ ] |
| 97 | Full QA: verify review card QR → Grade.us page → Google review form works end-to-end | VA | [ ] |
| 98 | Full QA: verify referral email triggers after positive review | VA | [ ] |
| 99 | Send customer "Onboarding Complete" email with baseline report | SALES | [ ] |
| 100 | Schedule first monthly check-in call | SALES | [ ] |
| 101 | Set GEO Agent monthly cron for this customer | VA | [ ] |

---

## Which "Future Ideas" Are Easy to Automate?

| Idea | Difficulty | Add to Onboarding? | How |
|------|-----------|-------------------|-----|
| **AI Visibility Monitor** | Easy | YES — Task #70 | Just a list of 10 search queries. Run monthly via Claude API. Ask "best dentist in [city]", "dental implants [city]", etc. Check if practice appears in response. Log score. No new infra needed — add as a step in the GEO Agent monthly run. |
| **Competitor Watch** | Easy | YES — Task #71 | Add competitor domains to customer config. GEO Agent already crawls Webflow — extend to crawl competitor pages, diff monthly. Claude compares and flags new content. |
| **Neighborhood Landing Pages** | Easy | YES — Tasks #59-60 | Claude generates content, VA publishes to Webflow. Template it — same structure per page, just swap neighborhood name, map embed, and local keywords. Generate 5-10 per customer during onboarding. |
| **Patient Question Mining** | Easy | YES — Task #72 | Connect GSC API, pull top queries monthly, feed into FAQ generation. The GEO Agent already generates FAQs — just add real search data as input. |
| **Blog Content Calendar** | Easy | YES — Tasks #73-74 | One Claude API call generates a 12-month calendar. VA schedules posts. Claude drafts each month, SALES spot-checks. |
| **Review Sentiment Dashboard** | Easy | YES — Grade.us | Grade.us monitors 100+ review sites, sends alerts, and generates portfolio reports. Already set up during onboarding. |
| **Voice Search Optimization** | Medium | Phase 2 | Already partially covered by Apple Maps + conversational FAQ. Dedicated voice optimization can wait. |

**Bottom line: 5 of 7 ideas are easy and should be part of standard onboarding.** They're just additional Claude API calls and config entries — no new infrastructure.

---

## Onboarding Timeline Summary

| Week | Focus | CUSTOMER Time | SALES Time | VA Time |
|------|-------|---------------|------------|---------|
| Week 1 | Access grants + technical setup | 30 min | 2 hrs | 4 hrs |
| Week 2 | GBP + Apple + Citations + Content | 0 | 1 hr | 6 hrs |
| Week 3 | Grade.us + referrals + monitoring + content | 0 | 1.5 hrs | 5.5 hrs |
| Week 4 | QA + handoff | 0 | 30 min | 2.5 hrs |
| **Total** | | **30 min** | **5 hrs** | **18 hrs** |

### Cost Per Onboarding
| Role | Hours | Rate | Cost |
|------|-------|------|------|
| SALES (Jon) | 5 hrs | N/A (owner) | — |
| VA | 18 hrs | $7/hr | $126 |
| Claude API | — | — | ~$2 |
| Grade.us (first month) | — | — | $40 |
| **Total hard cost** | | | **~$168** |

**Revenue: $3,000/month recurring. Onboarding cost: $168. Payback: Day 2.**

---

## Monthly Maintenance Checklist (After Onboarding)

Run on the 1st of each month per customer.

| # | Task | Who | Time |
|---|------|-----|------|
| 1 | GEO Agent runs automatically (crawl → analyze → generate → publish) | AUTO | 0 |
| 2 | Spot-check GEO Agent output (llms.txt, schema) | SALES | 10 min |
| 2a | Run schema validation: https://search.google.com/test/rich-results + https://validator.schema.org/ — must be 0 errors | VA | 5 min |
| 3 | Review + approve GBP post batch (4 posts for the month) | SALES | 5 min |
| 4 | Review content gap recommendations | SALES | 10 min |
| 5 | Publish GBP posts (weekly) | VA | 10 min/wk |
| 6 | Respond to new Google reviews (Claude-drafted responses) | VA | 15 min/wk |
| 7 | Upload new photos to GBP + Apple Maps | VA | 10 min |
| 8 | Update Apple Maps Showcases | VA | 10 min |
| 9 | Publish monthly blog post (Claude-drafted) | VA | 15 min |
| 10 | Run BrightLocal citation audit | VA | 10 min |
| 11 | Check AI Visibility Monitor results | VA | 5 min |
| 12 | Check Competitor Watch alerts | VA | 5 min |
| 13 | Check Grade.us dashboard — review portfolio report, referral stats | VA | 10 min |
| 14 | Reorder review cards if running low (check with front desk) | VA | 5 min |
| 15 | Send monthly report to customer | AUTO | 0 |
| 16 | Monthly check-in call with customer | SALES | 15 min |

**Monthly totals: SALES ~40 min, VA ~4-5 hrs, Customer ~0 min**
