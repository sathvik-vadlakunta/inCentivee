# GBP API setup — one-time, to turn manual GBP into automation

**Status:** access is proven (the `practicerank` Google account is a verified **Manager** on
Paradigm + Hilltop via Leadsie — confirmed in Business Profile Manager). Manual GBP work is
possible **today**. This checklist is the remaining **our-side** work to let `geo_agent/gbp_client.py`
do it via API instead of by hand.

**Identity:** the agency ops Google account (the Leadsie-connected `…@practicerank.ai`). One token
from it sees every client Leadsie connects (Paradigm, Hilltop, and future ones).

## 1. Enable the Business Profile APIs (GCP Console → APIs & Services → Library)
On our existing GCP project (the one already holding the GA4 OAuth app + Places key), enable:
- **Google My Business API** (legacy v4 — posts, reviews, media)
- **My Business Account Management API**
- **My Business Business Information API**
- **Business Profile Performance API**

> These show **0 quota until access is approved** (step 2). Enabling them is fine before approval.

## 2. Apply for Business Profile API access (the gate) — ✅ SUBMITTED 2026-06-26
- Submitted via the Business Profile API Support form → "Application For Basic API Access",
  anchored on Paradigm Experts, project = **Practice Rank**.
- **Support case ID: `0-1827000040711`** · review ETA **7–10 business days (~July 7–10, 2026)**.
- Until approved, API calls return 403 / quota-0 — but Steps 1, 3, 4 below can all be done now.

## 3. OAuth client + consent (reuse what we have if possible)
- We already have `GA4_OAUTH_CLIENT_ID/_SECRET` in this project. **Reuse that OAuth client** if it's
  a Web/Desktop client — just add the GBP scope below. Otherwise create a new OAuth 2.0 Client ID.
- **Scope:** `https://www.googleapis.com/auth/business.manage` (single scope covers all GBP ops).
- On the OAuth consent screen, add the ops `…@practicerank.ai` account as a **test user** (or publish).

## 4. Mint the refresh token (as the ops account)
Easiest path — **OAuth 2.0 Playground** (oauth2.googleapis.com playground):
1. Gear icon → "Use your own OAuth credentials" → paste our client ID + secret.
2. Authorize scope `https://www.googleapis.com/auth/business.manage` → sign in as the ops `…@practicerank.ai`.
3. "Exchange authorization code for tokens" → copy the **refresh_token** (long-lived).

(Or run a tiny local `google-auth-oauthlib` InstalledAppFlow with the same scope — same result.)

## 5. Set secrets on the droplet + verify
```bash
# in /home/kody/dental-marketing/.env on the droplet
GBP_OAUTH_CLIENT_ID=...
GBP_OAUTH_CLIENT_SECRET=...
GBP_OAUTH_REFRESH_TOKEN=...
```
Then redeploy/restart the dashboard container and run the built-in check:
```bash
docker exec practicerank-dashboard python -m geo_agent.gbp_client
```
Expected: `OK — N account(s) accessible.` then a list including **Paradigm Experts** and
**Hilltop Family Dental** with their `locations/…` IDs. That confirms M1 end-to-end.

## After this works
- M1 done → build **M2** (generate post + photos → `validate_html_claims` gate → Dan approval card →
  `localPosts.create` / `media.create`). See `specs/active/gbp-monthly-management.md`.
- Capture each location's `locations/{id}` (from the CLI output) alongside the `place_id` we already
  store, so posts/reviews/performance calls have the right resource name.

## Notes / gotchas
- **Service accounts don't work for GBP** — must be the OAuth user (Manager). That's why this is an
  OAuth-token setup, unlike GSC/GA4.
- **Q&A has no API** (discontinued 2025-11-03) → stays a manual Dan checklist item.
- Refresh token is long-lived but revocable; if the ops account password/2FA changes or access is
  pulled in Leadsie, re-mint (step 4). `gbp_client` fails safe (logs + returns empty) until then.
