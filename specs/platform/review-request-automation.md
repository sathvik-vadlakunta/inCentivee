# Review-Request Automation (email/SMS drip + pluggable feed)

**Status:** 📋 Planned — **HOLD until a pilot customer is selected** (need real PMS/CRM + place_id + consent to build against).
**Owner:** Kody · **Created:** 2026-06-24
**Category:** platform / feature

---

## Goal
Systematically generate more **first-party Google reviews** for each client and protect
their reputation — automatically, with **zero daily effort from the practice**. Review
volume/velocity is the #1 local-pack lever after proximity/relevance (e.g. the Sunrise
audit: competitor's 1,748 reviews vs 806 was *the* reason it owned the map pack).

This is **not** review syndication. You cannot legitimately post one review to many
third-party sites (Google/Yelp/FB require first-party reviews; duplicating = fraud). The
value is **generating new genuine reviews**, not copying one everywhere.

## Build vs. buy — decision
- **Don't pay per-location review SaaS** (Grade.us/GatherUp/Podium/Birdeye ~$40–150/loc/mo).
  Their value is the integration + funnel UI; the marginal cost of a request is ~$0.
- **Build on cheap infra we already have:** n8n (droplet, free) + **Resend** (email, wired) +
  **Twilio** (SMS, ~$0.008/text). Fully white-label, lives in our dashboard, ~$0/location.
- **Defer Sikka** (the dental PMS connector) until we have enough legacy on-prem dental
  clients to justify its cost.

## The hard part: getting the contact feed (NOT the sending)
Manual daily spreadsheet upload is a **dealbreaker** — practices won't do it. The feed must
be **set up once, runs forever**. Build a **pluggable feed layer** → one normalized
`completed_visits` queue → identical drip regardless of source:

| Source | Systems | Effort | Notes |
|---|---|---|---|
| **Native API / webhook** | Open Dental, Curve, Dentrix Ascend, Denticon (dental); Clio, Lawmatics, MyCase, PracticePanther (legal) | one OAuth/API-key setup | Default for cloud systems — automated, ~$0 |
| **Scheduled-export parser** | any PMS that can auto-email/SFTP a daily "completed appointments" report → `feed+<practiceID>@practicerank.ai` → auto-parse attachment | configure once at onboarding | Bridge for on-prem without paying Sikka |
| **PMS connector (Sikka)** | legacy on-prem **Dentrix, Eaglesoft** (no cloud API) | install agent on practice server; $ | Deferred — only at scale |
| **CSV upload** | universal | manual | **Fallback / one-time backfill only — never the daily mechanism** |

## The drip (stops the instant they click the review link)
| Touch | Timing | Message |
|---|---|---|
| 1 | Day 1–2 after visit | "Thanks for seeing us, {first}! How was your visit with {provider}? → **Leave a Google review**" |
| 2 | Day 5 (if no click) | soft reminder |
| 3 | Day 12 (optional) | final gentle nudge, then suppress |

- **Review link:** Google deep link `https://search.google.com/local/writereview?placeid={PLACE_ID}`
  (we already capture `place_id` in the audit worker → automatic per customer).
- **Channels:** email first (Resend, free); SMS optional (Twilio; higher response but needs
  10DLC carrier registration — the one genuinely annoying piece).

## Compliance guardrails (blocking)
- **No gating.** Everyone gets the Google CTA — do NOT filter by sentiment to hide the public
  option (violates Google ToS + FTC 2024 review rule). Add a *secondary* "had a problem? tell
  us privately →" link that routes 1–3★ feedback to the owner's inbox — without suppressing
  the public path.
- **HIPAA (dental):** patient data is PHI. Review request is generally OK under "healthcare
  operations," but keep PHI out of the message body, honor opt-outs, confirm practice consent.
- **Legal:** ask **past clients only**, **no incentives**, no drafting reviews for them.
- **CAN-SPAM:** unsubscribe link + practice physical address; global suppression list; never
  re-ask someone who already reviewed or recently received the sequence.

## Architecture (when built)
```
[feed source: API | scheduled-export | CSV]
        → normalize → completed_visits queue (dedupe + suppression)
        → n8n drip (Resend email / Twilio SMS, cadence + stop-on-click)
        → Google review deep link (place_id)
        → tracking: sent/opened/clicked  (+ BrightLocal watches review velocity)
        → dashboard: per-practice config (place_id, from-name, cadence, source) + reporting
```

## MVP scope (first pilot)
1. One feed source matched to the pilot's actual system (API if cloud; scheduled-export if not).
2. 3-touch **email** drip (defer SMS/10DLC).
3. Google review deep link + click tracking + stop-on-click.
4. Suppression list + unsubscribe.
5. Minimal dashboard config + sent/clicked reporting.

## Out of scope (v1)
SMS/10DLC, Sikka, multi-site review-site rotation, AI-drafted review *responses* (later),
display widgets on the practice site.

## Blocked on / next step
**Pick a pilot customer**, then capture: their PMS/CRM (→ which feed source), place_id,
from-name/domain for sending (SPF/DKIM), and written consent to email their patients/clients.
Then move this spec to `specs/active/` and build the MVP.
