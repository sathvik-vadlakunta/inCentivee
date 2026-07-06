# Healing Hands PT — Round 2 client feedback (apply after in-flight agents land)

**Date:** 2026-06-29. Captured live from Kody while the imagery/locations agent + the 50-blog
workflow were running. Apply as ONE coordinated pass once those land (avoid concurrent edits on the
same pages), then run the performance pass + redeploy.

## ⭐⭐ BRAND POSITIONING & TARGET MARKET (north star — shapes everything)
- **Location/market:** richer **South Reno**, targeting a **higher-income** clientele who can pay cash.
- **Who she's for:** people for whom **standard (insurance) PT has NOT worked** — they're frustrated with
  rushed, exercise-handout PT that didn't fix them.
- **The core promise:** a **relaxing, elevated, spa-like experience that is BETTER THAN A MASSAGE — because
  it actually FIXES the real problem** (root cause), not just feels good for an hour. Massage = temporary
  relaxation; insurance PT = rushed & ineffective for this person; Healing Hands = **relaxing AND it works.**
- **Aesthetic implication:** lean MORE premium / luxe-wellness / boutique — calm, refined, upscale, serene
  (spa-meets-doctor). Not clinical-cheap, not high-volume-clinic. Think concierge med-spa quality.
- **Copy implication:** speak to the affluent buyer who values their time, wants a calm premium experience,
  has tried everything, and wants the ROOT problem fixed for good. Lead with experience + results, not price.
  "More relaxing than a massage. More effective than PT. The fix you've been looking for."
- **Add a "Massage vs. Real Bodywork" contrast element** (a band/table like the insurance-PT contrast):
  it is NOT just a massage — it's real therapeutic bodywork (manual therapy, myofascial release, dry
  needling, CranioSacral, StemWave) performed by a doctor. Make the distinction explicit and visual:
  **Massage = feels good, temporary relief, treats the surface. Her bodywork = as relaxing, but it finds
  and fixes the ROOT CAUSE for lasting results.** This is a primary homepage education point (pairs with
  the insurance-PT contrast). Tie to the "real fix + maintenance, not temporary" message (#6).

## Feedback items
1. **Kill the organic "blob" shapes** → clean modern framed imagery. *(in progress — imagery agent)*
2. **Real photos must load** — pull her real images from the HighLevel CDN. *(in progress — imagery agent)*
3. **Areas We Serve nav + location pages** — Reno, Sparks, Carson City, Incline Village, Truckee, Tahoe. *(in progress — imagery agent)*
4. **Feature StemWave + Dry Needling as her two SIGNATURE treatments.** StemWave = her acoustic/
   "sonic wave" (shockwave) therapy — confirmed from scrape (39+ "StemWave", "shockwave", "acoustic
   wave"; no separate SoftWave device). On the StemWave page + meta, explicitly name it "sonic /
   acoustic wave (shockwave) therapy" so people searching "sonic wave" find it. Give both a featured
   slot on the homepage (signature-treatments band) + stronger service pages.
5. **Add a lot more pictures throughout** — use ALL her real photos generously across home/about/
   service/area pages; where she has no real photo for a technique/condition, use clearly-generic
   licensed imagery (never present generic stock as her clinic/results). No fabricated image URLs.
6. **Positioning correction — NOT temporary relief, a REAL fix + long-term maintenance.** Core
   message everywhere (home hero/value section, service pages, blog editorial voice): her hands-on
   root-cause care *fixes the underlying problem* and sets up *long-term maintenance* — vs. a quick
   rub / pill / injection that only masks pain temporarily. Frame: "We don't chase the symptom — we
   find and fix the root cause, then keep you there." (Reinforces the cash-pay value: fewer visits,
   lasting result.)
7. **Performance: 90+ on PageSpeed Insights.** Final gate, after content+images settle — Astro
   `<Image>`/sharp (AVIF/WebP), explicit width/height, preload LCP, lazy-load below fold, minimal JS,
   Cloudflare edge. Measure on PSI, iterate to 90+ (very achievable on our stack).
8. **Monthly Maintenance Membership — feature it prominently (RETENTION play).** She offers monthly
   maintenance plans; the site barely sells them and her turnover/churn is too high — the explicit
   business goal is **retain more customers**. Add a dedicated membership section on the homepage +
   likely a `/membership` (or `/maintenance-plans`) page that sells the LONG-TERM value:
   - **Maintain your results** — ongoing tune-ups so the problem we fixed doesn't creep back.
   - **Prevent future injuries** — proactive maintenance vs. waiting until you're hurt again.
   - **Same-day access for new injuries** with the monthly package (a real, concrete member perk).
   - Priority booking / ongoing relationship with your doctor.
   - Framing: "Don't fix it and let it slide back. The body needs upkeep — stay ahead of pain with
     monthly maintenance." Position as the natural next step AFTER the initial fix (ties to #6).
   - Hook it into the homepage journey: Fix the root cause → **stay there with monthly maintenance**.
   - ⚠️ **Pricing gate:** do NOT invent membership prices/tiers. Sell the benefits + "ask about her
     monthly maintenance plan / book a call"; drop real pricing in once Kody/the client confirms it.

## Pricing & funnel (⚠️ UNCONFIRMED — Kody from memory 2026-06-29; CONFIRM with client before publishing)
Numbers are approximate ("I think…") — treat as provisional, verify before going live.
- **Intro session — $150**, 1 hour, hands-on. This is the CONVERSION ENTRY POINT: low-friction first
  visit where she treats you AND guides you into a package. **Lead the site CTA with this** ("Start
  with a $150 intro session"), not the package.
- **10-session package — ~$2,000.** ⛔ **DO NOT advertise this price** — causes sticker shock. Frame as
  "ask about her packages" / discussed at the intro. The intro de-risks the big number.
- **Monthly membership — ~$99/mo:** includes **10% off services** and **credit toward your first
  session**. Feature this as the long-term maintenance/retention offer (item #8).
- **One-off session — $220.** Don't lead with it (sticker shock); position the intro + package/membership
  as the smart path.
- **StemWave (sonic/acoustic wave) — a quick 10–15 MIN ADD-ON, ~$50.** NOT a standalone 1-hour service —
  it's a fast enhancement layered onto her hands-on sessions. Position it as "add StemWave to your visit
  (10–15 min, $50)" — a low-friction UPSELL and a "try it" lever. Good A/B test: "Add StemWave $50" /
  first StemWave free with an intro → convert to a series (it works best over a course of treatments).
  $50 IS advertisable (unlike the $2k package). On the StemWave page, frame it as an add-on/booster, not a
  primary modality, and clarify the "sonic/acoustic wave (shockwave)" naming for search.

## Upsell / trial-offer ideas (test list — refine with the referral-offers research)
- **"Try StemWave $50"** intro → upsell to a StemWave series or full package (it's only effective in a
  course of treatments, so the trial naturally leads to "you'll want a series").
- Bundle a StemWave add-on into the intro session as a taste of the signature tech.
- First-visit "add dry needling to your intro" trial.
- All trials are TOP-of-funnel hooks that feed the $150 intro → 10-pack / $99 membership path.
- **Funnel logic:** $150 intro (hands-on, builds trust) → convert to 10-pack (~$2k, price not shown) or
  $99/mo membership. Site should drive everyone to the intro session first.
- Anti-fabrication: publish ONLY the intro ($150) + membership ($99/mo) once confirmed; keep the package
  price OFF the site entirely. Mark all as pending client confirmation.

## ⭐ Conversion-efficiency principle (Kody — don't waste her time on non-buyers)
She doesn't want to burn hours on people who don't convert to real (package/membership) sales. Every
offer + funnel choice must respect this:
- **The paid $150 intro IS the qualifier** — a paid first visit (not free) filters tire-kickers, and its
  explicit job is to build a plan and convert to a package/membership. Frame it that way (a real working
  session + plan, not a free consult).
- **Reward referrals on REAL CONVERSION, not on showing up.** Favor offers where the reward unlocks only
  when the referred person actually buys a package/membership (Kody's 10-pack-gated seed offer fits this).
  Be cautious with "free session for just booking" double-sided offers — higher volume but can attract
  freebie-seekers who waste her hour. If using a reward, prefer a low-time-cost reward (a StemWave add-on
  or a maintenance/membership credit) over a full free hour.
- **Use low-time trials, not free hours** — the StemWave $50 / 10–15 min add-on is the ideal "try it"
  because it costs her almost no time vs. a free hour-long session.
- Net: optimize for QUALIFIED buyers and conversion-gated rewards over raw lead volume.

## Referral offers (research DONE — specs/customers/healing-hands-pt-referral-offers.md)
6 offers ranked; compliance: cash-pay removes federal teeth, but structure rewards as capped in-clinic
service credit ("patient appreciation," not a referral bounty) per NV PT-board NAC/NRS 640; NEVER reward
Google reviews. Per the conversion-efficiency principle above, lead the A/B with the **conversion-gated**
arm (reward only when the friend buys a package/membership), test the double-sided arm cautiously. Real
prices marked [NEEDS JAMIE'S NUMBERS]. Build the `/refer` page AFTER Kody picks the offer(s) to test.

## 50-blog content (workflow running)
Real research + VERBATIM-verified expert quotes (unverifiable quotes are auto-removed). Buckets:
technique explainers, condition→technique buying-intent guides (local), cash-pay decision content.
Editorial note to fold into the post-pass: weave the **"real fix + maintenance, not temporary relief"**
message and the **StemWave (sonic wave) + Dry Needling** emphasis into the relevant posts.
