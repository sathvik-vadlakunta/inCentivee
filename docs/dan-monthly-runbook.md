# Dan's Monthly Runbook — per customer

**Run once per customer, every month.** Do the steps in order. Every step has a **Confirm**
line — the work isn't "done" until the confirm check passes. Tag each `[LIVE]` (do it today)
or `[PLANNED]` (ships with `specs/active/gbp-monthly-management.md` — skip until built).

> Quick status to log at the end of each customer: **Billing ✓ · Off-site ✓ · Content ✓ ·
> GBP ✓ · Approval ✓ · Report ✓ · Checklist ✓** + date + your initials.

---

## 0. Billing is current `[LIVE]`
- **Do:** confirm this month's subscription **payment cleared** in Stripe before doing any work.
- **Where:** Stripe dashboard → customer → latest invoice `paid`.
- **Confirm:** invoice status = `paid` (not `past_due`/`open`). If unpaid → pause work, flag Kody. Do NOT do paid deliverables for an unpaid month.

## 1. Set the month's plan from their tier `[LIVE]`
- **Do:** read the customer's tier (Stripe plan → `optimize` / `grow` / `dominate`). The tier sets the month's off-site volume.
- **Where:** `/fatjoe` queue (it normalizes the Stripe plan to the tier and shows the plan).
- **Confirm:** the tier shown matches what they pay for. Monthly link target:
  - **Optimize** → 1 link (DR20–30) · **Grow** → 2 links (DR20–30) · **Dominate** → 4 links (DR30–40)
  - Quarterly brand mention: Grow (DR30–60) / Dominate (DR40–60) — only on quarter months.
  - Onboarding only (first month): 100 NAP citations.

## 2. Off-site work — FATJOE orders `[LIVE]`
- **Do:** place this month's FATJOE orders per the tier plan above. Rotate the target page (money/city pages), vary anchors (exact-match anchors ≤5%). Dominate: include a "best {service} in {area}" listicle placement.
- **Where:** `/fatjoe` queue → place orders; record order IDs against the customer.
- **Confirm done correctly:**
  - Order count + DR tier **matches the plan** for their tier (1/2/4 links; mention if a quarter month).
  - NAP on every citation **exactly matches** the canonical NAP (name/address/phone) — a mismatch hurts ranking.
  - Target page rotated vs last month (not hammering one URL); anchor mix not over-optimized.
  - Order IDs logged so next month you can verify delivery.

## 3. On-site content — generate → QA → approve → publish `[LIVE]`
- **Do (generate):** generate this month's content recommendations.
  - **Where:** customer → Content → **Generate** (`/api/content/generate`). Produces ~8–10 recs (blogs, FAQ updates, stat injections, freshness).
- **Do (QA — critical):** review every rec. **Reject anything with a blocking finding.**
  - **Where:** customer Content page — each rec shows its **NEEDS REVIEW** flags (credential / superlative / future-date / YMYL-absolute from `validate_html_claims`).
  - **Confirm:** **zero BLOCK findings** remain on anything you approve. Fabricated credentials (e.g. "Board Certified" when the provider is only "DDS, FACP"), "painless/guaranteed/lasts a lifetime", future "Last updated" dates, and superlatives ("best/#1") must be fixed or rejected. Spot-check that every stat has a real cited source.
- **Do (approve):** approve the clean recs (`/api/content/approve-all` or per-item).
- **Do (publish / hand off):**
  - Auto-publish customers → **Publish** (`/api/content/publish`) — note: publish runs the fact-check gate again and blocks unsupported claims.
  - Manual/dev customers → **Download all approved** docx (`/api/content/<id>/download-all-approved`) and hand to their dev.
- **Confirm done correctly:**
  - **Published:** open each new URL live and confirm the post renders (curl/open). Then **Sync published** (`/api/content/<id>/sync-published`) so status reflects reality.
  - **Docx handoff:** open the docx — **0 "NEEDS REVIEW" blocking banners**, every blog has a real Meta Description (≤155 chars, not a writer brief), no future dates, correct credentials.
  - At least 1 monthly blog post shipped + any FAQ/stat injections targeted to real pages.

## 4. Google Business Profile (GBP) — monthly `[PLANNED]`
Until the GBP build lands, do these **manually in the customer's GBP** (you must have Manager access — see the access step in the GBP spec). Once built, they appear as an auto-generated **"GBP — <month>"** card you approve.
- **Post:** publish 1 What's New / Offer post (keyword + city + CTA). **Confirm:** post is live on the profile; copy has no superlatives/absolutes/false credentials (same bar as on-site content).
- **Photos:** add 3–5 fresh photos. **Confirm:** they appear in the profile gallery.
- **Reviews:** reply to every new review (brand voice; never gate, no incentives, no PHI). **Confirm:** reply count = new-review count; nothing left unanswered.
- **Q&A (manual — API discontinued):** open the listing, answer/seed owner Q&A. **Confirm:** no unanswered questions; new questions emailed to the customer if only they can answer.
- **Info accuracy:** check hours (holiday/seasonal), services, categories, description. **Confirm:** matches the canonical NAP + their current services.
- **Performance:** pull the month's metrics (searches/calls/directions/views) for the report. **Confirm:** numbers captured and pasted into the monthly report.

## 5. Approval — Dan first, then client (if opted in) `[Dan QA LIVE · client portal PLANNED]`
- **Stage 1 — Dan QA:** you've already approved every item above (content + GBP). Nothing ships without this.
- **Stage 2 — Client portal:** check the customer's `client_approval_mode`.
  - `dan_only` → your approval ships it; no client step.
  - `client_review` → send the **`/approve/<token>`** link (blog + content + GBP in one page). **Confirm:** client approved (or the N-day auto-approve fired) before anything publishes; log who approved (Dan / client / auto).

## 6. Reporting — show the work `[LIVE]`
- **Do:** make sure the customer's report is current and the shareable link works.
- **Where:** `/report/<id>/weekly`; client link is `/r/<token>`.
- **Confirm:** the report reflects this month's links/citations/content/GBP + performance deltas; the `/r/<token>` link opens for a logged-out user and shows current data.

## 7. Checklist + account health `[LIVE]`
- **Do:** review the customer's SEO/GEO checklist for anything red that's now done (auto-detected items flip green automatically) and anything newly needed.
- **Where:** customer → checklist (`/api/checklist`).
- **Confirm:** no stale "todo" that's actually complete; no new gap left untracked (GBP access verified, schema live, citations consistent).

## 8. Sign-off `[LIVE]`
- **Do:** log the one-line status (top of this doc) with date + initials against the customer.
- **Confirm:** all seven check-lines are ✓ for this customer this month. If any is blocked, note why and the follow-up owner.

---

### "Confirm it was done correctly" — the fast verification pass
For a quick monthly audit that a customer's work actually shipped clean:
1. **Off-site:** order count/DR matches tier; NAP exact on citations.
2. **Content:** new URLs load live; `validate_html_claims` clean (no fabricated credentials / absolutes / future dates / unsourced stats); meta descriptions real.
3. **GBP:** post + photos visible on the live profile; every new review answered; Q&A clear; info accurate.
4. **Approval:** correct gate passed for their mode (Dan-only vs client-approved/auto), with an audit-trail entry.
5. **Report:** `/r/<token>` opens and reflects the month.

> The content/GBP correctness checks are the same guardrails the platform enforces in code
> (`geo_agent/content_validation.py` + the worker audit safety checks). If something passes
> those, it's clean; if Dan sees a flag, fix or reject before it reaches the customer.
