# Grade.us — White-Label Review Management Setup Guide

How to set up Grade.us as DentalRank's white-labeled review platform across multiple dental practice locations, and how to combine it with a referral program.

---

## Why Grade.us

- **Built for agencies** — purpose-built white-label review management for resellers
- **Per-seat pricing** — $40/location on Agency plan, drops to $25/location at 100+ seats
- **Full white-label** — custom domain, branding, emails, reports. No trace of Grade.us visible to patients or clients
- **Month-to-month** — no annual contracts, unlike Podium/Birdeye
- **100+ review sites monitored** — Google, Yelp, Healthgrades, Facebook, Zocdoc, etc.
- **Negative feedback interception** — unhappy patients get routed to internal form, not public reviews

### Pricing

| Plan | Seats Included | Per-Seat Cost | Monthly Total |
|------|---------------|---------------|---------------|
| Solo | 1 | $110/seat | $110/mo |
| Professional | 3 | $60/seat | $180/mo |
| **Agency** | **10** | **$40/seat** | **$400/mo** |
| Partner | 100 | $25/seat | $2,500/mo |

**White Label Premium add-on**: $440/year (Agency+). Free at 100+ seats.

**For DentalRank**: Start on Agency plan. At $40/location with $3K/month revenue per practice, Grade.us costs 1.3% of revenue. Auto-graduates to Partner tier at 100 seats.

### vs Competitors

| Feature | Grade.us | Podium | Birdeye | NiceJob |
|---------|----------|--------|---------|---------|
| Starting Price | $40/seat | $249/mo flat | $299/mo flat | $75/mo flat |
| White-Label | Full (best) | Limited | Enterprise only | No |
| Contract | Monthly | Annual | Annual | Monthly |
| Agency Tools | Purpose-built | Limited | Enterprise | None |

---

## White-Label Setup (One-Time, for All Locations)

### Step 1: DNS — Custom Domain

Create a CNAME record on `dentalrank.ai` pointing a subdomain to Grade.us:

```
reviews.dentalrank.ai  CNAME  [grade.us-provided-target]
```

This single subdomain hosts ALL client review pages:
- `reviews.dentalrank.ai/hilltop-dental`
- `reviews.dentalrank.ai/38th-street-dental`
- `reviews.dentalrank.ai/bright-smile-family`

**Alternative**: Each client gets their own subdomain on their domain (e.g., `reviews.hilltopdental.com`). More setup per client but feels more "owned" by the practice.

### Step 2: Branding

In Grade.us Dashboard > Settings:

1. Upload DentalRank logo (or per-client practice logo)
2. Set brand colors to match DentalRank / client branding
3. Upload header image (1024x138px, under 450KB)
4. Choose "Modern" landing page layout
5. Set custom favicon
6. Configure white-labeled email sender address (e.g., `reviews@dentalrank.ai`)

### Step 3: White Label Premium ($440/year)

Enables:
- Custom logo on the dashboard (not just landing pages)
- SSL certificate for custom domain
- Dedicated hosting
- Complimentary at 100+ seats

**Decision**: Skip Premium until 10+ clients. Basic white-label (free) covers everything patient-facing.

---

## Per-Location Setup (Repeat for Each New Client)

### Step 1: Create Location Profile

1. Grade.us Dashboard > Add New Profile
2. Enter practice info: name, address, phone, website
3. Under Custom Domain > check "Shared by multiple businesses?"
4. Set URL path: `reviews.dentalrank.ai/[practice-slug]`

### Step 2: Configure Review Sites

Select which review platforms appear on the landing page (in priority order):

1. **Google** (always #1 — most impact on local SEO)
2. **Healthgrades** (dental-specific, high DA)
3. **Facebook** (social proof)
4. **Yelp** (Apple Maps sources reviews from Yelp)

Remove irrelevant sites (TripAdvisor, Angi, etc.).

### Step 3: Review Funnel Mode

**Recommended: "Review Site First" mode** for dental:

1. Patient clicks link/QR code
2. Lands on branded review funnel page
3. Sees buttons for Google, Healthgrades, Facebook, Yelp
4. Clicks preferred site and leaves review directly

**Why not "Review First"**: The extra step of writing on Grade.us first then copy-pasting to Google adds friction. Dental patients aren't writing novels — get them to Google as fast as possible.

### Step 4: Negative Feedback Interception

Configure in Dashboard > Funnel > Feedback:

1. Enable "Rate your experience" pre-screen
2. Patients rating 1-3 stars → routed to internal feedback form (NOT public review sites)
3. Feedback submissions appear in Grade.us dashboard
4. Set up email alert to practice owner for negative feedback
5. This protects the practice's public rating while still capturing complaints

### Step 5: Email/SMS Campaign Setup

Configure the 3-message drip sequence:

**Message 1** (sent immediately after adding patient):
> Hi [First Name], thank you for visiting [Practice Name]! We'd love to hear about your experience. It only takes a minute: [review link]

**Message 2** (3 days later, if no click):
> Hi [First Name], quick reminder — your feedback helps other patients find great dental care. Leave a review here: [review link]

**Message 3** (7 days later, if still no click):
> [First Name], we value your opinion. If you have a moment, we'd really appreciate a quick review: [review link]

**Important**: Grade.us handles email delivery. SMS requires the practice to have proper consent (Grade.us does not handle TCPA compliance). **Recommendation: Use email campaigns through Grade.us + QR cards for in-office. Skip SMS.**

### Step 6: Review Widget for Client Website

1. Dashboard > Widgets > Review Stream
2. Configure: show only 4-5 star reviews, limit to 10 most recent
3. Copy embed code
4. VA adds to client's Webflow site (footer or dedicated reviews page)
5. Also available: floating carousel widget for homepage

### Step 7: Alerts & Reporting

1. Set review alerts: notify on ALL new reviews (or only 3-star-and-below)
2. CC practice owner on alerts
3. Configure automated weekly/monthly portfolio reports
4. Reports are white-labeled with DentalRank branding

---

## Combining with QR Card System

Grade.us enhances (not replaces) the QR card system:

### Updated Flow

1. **QR card at front desk** → links to `reviews.dentalrank.ai/[practice]` (Grade.us landing page)
2. Patient sees branded page with review site options
3. If happy → clicks Google/Healthgrades/Yelp → leaves public review
4. If unhappy → intercepted by negative feedback filter → internal form
5. Grade.us sends follow-up email drip to patients who don't review immediately
6. All reviews monitored in one dashboard across all sites

### What Changes from the Original QR Card Setup

| Before (QR → Google direct) | After (QR → Grade.us funnel) |
|------------------------------|-------------------------------|
| QR links to Google review form | QR links to Grade.us landing page |
| Only Google reviews | Google + Healthgrades + Facebook + Yelp |
| No negative feedback filter | Unhappy patients routed to private form |
| No follow-up if patient doesn't review | 3-message email drip sequence |
| Manual review monitoring | Centralized dashboard + alerts |
| No review widgets | Embeddable review stream on website |

---

## Combining Grade.us with a Referral Program

Grade.us doesn't have built-in referral features. Here's how to pair it with a referral program for a unified patient flow.

### Recommended: Lightweight Custom Referral Flow via n8n

No additional SaaS needed. Use the n8n automation platform (already in the DentalRank stack) to build a simple referral flow triggered by Grade.us.

**How it works:**

1. **Grade.us Zapier trigger** fires when a patient leaves a 4-5 star review
2. Zapier sends webhook to n8n
3. n8n sends a "thank you + referral" email:

> Thank you for your kind review, [Name]! We're so glad you had a great experience.
>
> Know someone who needs a great dentist? Give them this card and you'll both receive [incentive]:
>
> **Your referral code: [UNIQUE_CODE]**
> **Or share this link: [practice-url]/refer/[code]**
>
> When your friend mentions your name at their first visit, we'll [deliver incentive].

4. Practice tracks referrals via a simple spreadsheet or the practice management system
5. Incentive delivered at the referred patient's first visit

### Referral Incentives That Work for Dental

| Incentive | Cost to Practice | Patient Appeal | Compliance |
|-----------|-----------------|----------------|------------|
| $25 credit toward next visit | Low | High | OK — it's a discount, not cash |
| Free teeth whitening kit (take-home) | ~$15 cost | Very high | OK |
| Both referrer AND new patient get $25 credit | Medium | Very high | OK |
| Donation to local charity in patient's name | Low | Medium | Excellent — avoids "payment for referral" concerns |
| Entry into quarterly drawing ($500 value) | Low | Medium | OK |

**Avoid**: Cash payments, gift cards over $50, or anything that could be construed as paying for referrals (some state dental boards have rules about this).

### Alternative: Dedicated Referral SaaS

If the n8n approach is too custom, these pair well with Grade.us:

| Service | Cost | How It Integrates |
|---------|------|-------------------|
| **ReferralCandy** | $59/mo | Zapier integration with Grade.us triggers |
| **GrowSurf** | $99/mo | API + webhook integration |
| **Referral Rock** | $200/mo | Full tracking + dashboard, overkill for dental |

**Recommendation**: Start with the n8n flow. It's free, simple, and handles 90% of use cases. Move to dedicated SaaS only if you need detailed referral analytics across 20+ locations.

### Combined Patient Journey

```
Patient visits practice
        ↓
Staff hands QR review card at checkout
        ↓
Patient scans QR → Grade.us landing page
        ↓
    ┌─────────────────────────────────┐
    │  Happy (4-5 stars)?             │
    │  → Google/Healthgrades/Yelp     │
    │  → Grade.us logs the review     │
    │  → n8n triggers referral email  │
    │  → Patient gets referral code   │
    │                                 │
    │  Unhappy (1-3 stars)?           │
    │  → Internal feedback form       │
    │  → Practice owner alerted       │
    │  → Follow up privately          │
    └─────────────────────────────────┘
        ↓
Patient shares referral code with friend
        ↓
Friend books appointment, mentions referral
        ↓
Both get incentive ($25 credit / whitening kit)
```

---

## Integration with DentalRank Workflow

### During Customer Onboarding (VA Tasks)

| # | Task | Time |
|---|------|------|
| 1 | Create Grade.us profile for the location | 10 min |
| 2 | Configure review sites (Google, Healthgrades, Facebook, Yelp) | 5 min |
| 3 | Enable negative feedback interception | 2 min |
| 4 | Set up 3-message email drip campaign | 10 min |
| 5 | Update QR card to point to Grade.us landing page (not direct Google link) | 5 min |
| 6 | Generate review widget embed code, add to Webflow site | 10 min |
| 7 | Configure review alerts (CC practice owner) | 2 min |
| 8 | Set up n8n referral trigger (Zapier webhook → n8n → email) | 15 min |
| 9 | Create referral email template with practice branding | 10 min |
| 10 | Test full flow: QR → review → referral email | 5 min |

**Total: ~75 min per location** (one-time setup)

### Monthly Maintenance

| Task | Who | Time |
|------|-----|------|
| Monitor Grade.us dashboard for new reviews | VA | 10 min/week |
| Post Claude-drafted review responses | VA | 15 min/week |
| Check referral redemptions with practice | VA | 5 min/month |
| Review Grade.us portfolio report | SALES | 5 min/month |
| Reorder review cards if needed | VA | 5 min/month |

### Updated Per-Customer Costs

| Item | Monthly Cost |
|------|-------------|
| Grade.us (Agency plan, $40/seat) | $40 |
| Claude + Voyage API | $2-4 |
| VA time (~4 hrs/mo) | $28 |
| BrightLocal (shared) | ~$4 (split across customers) |
| **Total** | **~$74-76/mo** |
| **Revenue** | **$3,000/mo** |
| **Gross margin** | **~97.5%** |

---

## Setup Checklist Summary

### One-Time (Agency Level)
- [ ] Sign up for Grade.us Agency plan ($400/mo for 10 seats)
- [ ] Set up CNAME: `reviews.dentalrank.ai` → Grade.us
- [ ] Configure white-label branding (logo, colors, email sender)
- [ ] Create email drip templates (3 messages)
- [ ] Create referral email template
- [ ] Set up Zapier → n8n webhook for referral trigger
- [ ] Configure portfolio reporting schedule

### Per-Location
- [ ] Create Grade.us location profile
- [ ] Set URL path on shared subdomain
- [ ] Configure review site priority (Google > Healthgrades > Facebook > Yelp)
- [ ] Enable negative feedback interception
- [ ] Activate email drip campaign
- [ ] Generate QR code pointing to Grade.us landing page
- [ ] Design and print review cards
- [ ] Add review widget to Webflow site
- [ ] Configure alerts (CC practice owner)
- [ ] Set up referral code for this location
- [ ] Test full flow end-to-end
