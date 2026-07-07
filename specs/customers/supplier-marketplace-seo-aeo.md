# SourceNow Supplier Marketplace — SEO & AEO Strategy

**Site:** https://supplier-marketplace.webflow.io/ (Webflow) · **Customer:** SourceNow (Distinctive Workforce Solutions)
**Vertical:** B2B SaaS — global temporary-staffing supplier marketplace
**Scope note:** WORLDWIDE product → **no local SEO / no service-area pages.** Framing is topical/buyer-intent, not geographic.

## What it is (for accurate framing)
A marketplace connecting two sides:
- **Buyers/companies** — source pre-vetted temporary-staffing suppliers ("Find Suppliers for Free"). Value: verified/compliant suppliers, filter by industry/capability/performance, full visibility, faster time-to-staffing, less risk.
- **Suppliers/staffing agencies** — get listed to win new clients ("Get Listed as a Supplier"). Value: visibility, inbound demand, growth without manual outreach.
Backed by SourceNow verification + compliance standards. Centralized platform for sourcing, activity, and performance.

## Current state (from raw scrape)
- ✅ Title + meta description present; viewport present; robots.txt 200
- ❌ **0 JSON-LD schema blocks** (biggest AEO gap)
- ❌ sitemap.xml 404 · llms.txt 404 · no canonical · only 3 OG tags · 1 H2 rendered
- ❌ 44 images, alt text mostly empty/"Arrow"
- ⚠️ Lingering Lorem-ipsum + empty stat numbers on the homepage
- ⚠️ Webflow template artifacts: duplicate variant pages (home/about/blog/contact/pricing/service `-one/-two/-three`, `old-home`) still published → sitemap/index bloat + duplicate content

## Keyword strategy (topical, buyer-intent — no geo)
**Primary:** temporary staffing supplier marketplace · find staffing suppliers · staffing vendor sourcing platform · verified staffing agencies
**Buyer-side:** source temp staffing suppliers · staffing vendor management · pre-vetted staffing agencies · staffing supplier directory · reduce staffing supplier risk / compliance
**Supplier-side:** list your staffing agency · get staffing clients · staffing agency lead generation · join a staffing marketplace
**AEO/question intent:** "how do I find vetted staffing suppliers", "best temp staffing marketplace", "how to vet a staffing agency", "staffing supplier compliance checklist"

## Page architecture (the build)
1. **Home** — consolidate to one canonical homepage (retire `-one/-two/-three`, `old-home`).
2. **Service/solution pages** (topical, not geo):
   - `/for-companies` — Find & source verified staffing suppliers
   - `/for-suppliers` — Get listed & win staffing clients
   - `/verification-compliance` — How suppliers are vetted (trust/risk)
   - `/how-it-works` — Marketplace platform / from search to supplier
3. **Contact** — `/contact` (real page, LocalBusiness-free; ContactPage + Organization schema).
4. **Blog** — `/blog` index + topical posts (SEO/AEO magnets, see below).
5. **Pricing** — keep one canonical `/pricing` if used; else noindex.

## "Better SEO framing" — before → after
| Page | Before | After (proposed) |
|---|---|---|
| Home `<title>` | Supplier Marketplace - Smarter Staffing Starts Here | **Temporary Staffing Supplier Marketplace — Source Verified Suppliers \| SourceNow** |
| Home meta | Connect with verified staffing suppliers through SourceNow's secure marketplace… | **Find and source pre-vetted temporary-staffing suppliers worldwide. Filter by industry & capability, cut risk with compliance-backed verification, and staff faster — all in one marketplace.** |
| Home H1 | The World's Largest Temporary Staffing Supplier Marketplace | keep (strong) — add keyworded H2s beneath |
| For companies | — | **Find Verified Temporary Staffing Suppliers — Source Faster, Cut Risk \| SourceNow** |
| For suppliers | — | **List Your Staffing Agency — Win New Clients on SourceNow's Marketplace** |
| Verification | — | **Staffing Supplier Verification & Compliance — Vetted Partners You Can Trust** |

## Technical SEO fixes (this deliverable)
- [ ] robots.txt → allow + reference sitemap (block template variant slugs)
- [ ] sitemap.xml → canonical pages only
- [ ] Canonical tag on every page (kills `-one/-two/-three` duplicate content)
- [ ] Per-page `<title>` + meta description + OG + Twitter card
- [ ] Alt text on all meaningful images
- [ ] Replace Lorem-ipsum + fill stat numbers (or remove the stat block)

## AEO fixes (this deliverable)
- [ ] `llms.txt` (concise) + `llms-full.txt` (detailed) at site root
- [ ] JSON-LD head code: **Organization**, **WebSite** (+SearchAction), **SoftwareApplication**/**Service**, **FAQPage** (home + service pages), **BreadcrumbList**
- [ ] Question-led FAQ sections feeding FAQPage schema (AI-overview bait)

## Blog — initial topical posts (buyer + supplier intent)
1. How to Find and Vet Temporary Staffing Suppliers (buyer, pillar)
2. Staffing Supplier Compliance Checklist: What to Verify Before You Partner
3. Vendor Management for Staffing: Cutting Risk and Time-to-Fill
4. For Staffing Agencies: How to Win More Clients Without Cold Outreach
5. What Is a Staffing Supplier Marketplace (and Why It Beats Manual Sourcing)?

## Delivery format (Webflow)
Artifacts under `sites/supplier-marketplace/`: `seo/` (llms, robots, sitemap, per-page head code w/ schema) to paste into Webflow page settings + host at root; `pages/` (markdown copy drafts w/ SEO-framed title/meta/H1/sections) to build in Webflow. No API push until SourceNow grants Webflow access.
