# GA4 Conversion Tracking Setup (R3)

How to wire a customer's Google Analytics 4 property so the weekly report's
**Leads** section (phone calls + form submits) shows real data.

Code: `geo_agent/ga4_client.py` · Cron: `scripts/weekly_reports.py` · Table: `conversions_daily`.

There are two ways to authenticate. **Recommended: OAuth "add my email"** — it
matches what onboarding already does (clients add `kdoherty@practicerank.ai` to
their GA4). The service-account method is the alternative.

## Option 1 (recommended) — authenticate as your account

Clients already add `kdoherty@practicerank.ai` as a user on their GA4 property
during onboarding, so there's **nothing new to ask them**. The platform just
authenticates *as* that account.

One-time server setup:

1. **Enable the API.** Google Cloud Console → enable **Google Analytics Data API**.
2. **Create an OAuth client ID** (type: **Desktop app**) and download its JSON.
   On the **consent screen**, add scope `…/auth/analytics.readonly`.
   - If practicerank.ai is a Google **Workspace** org, set the consent screen to
     **Internal** → no verification, and the refresh token **never expires**. ✅
   - If External, refresh tokens for this (sensitive) scope expire after 7 days
     in test mode — publish/verify the app, or use Internal.
3. **Mint the refresh token** (local, opens a browser — log in as
   `kdoherty@practicerank.ai`):
   ```
   pip install google-auth-oauthlib
   python3 scripts/ga4_authorize.py /path/to/oauth_client.json
   ```
4. Paste the three printed values into the droplet `.env`
   (`GA4_OAUTH_CLIENT_ID`, `GA4_OAUTH_CLIENT_SECRET`, `GA4_OAUTH_REFRESH_TOKEN`),
   then `docker compose up -d` (not `restart` — env vars won't reload).

Per customer: just confirm `kdoherty@practicerank.ai` has at least **Viewer** on
the property (Editor, which onboarding collects, already covers it), then enter
the **Property ID** in the dashboard (below).

## Option 2 — service account

1. Enable the API; create a **service account** + JSON key.
2. Credentials on the droplet: `GA4_SERVICE_ACCOUNT_JSON='{...}'`
   (or `GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json`).
3. Per customer: add the **service-account email** as a **Viewer** in the
   property's **Admin → Property Access Management**. ⚠️ This requires
   **Administrator** on the property — Editor (what onboarding collects) can't add
   users, which is why Option 1 is usually easier for existing clients.

Lib is already in `requirements.txt` (`google-analytics-data>=0.18.0`). Either
mode degrades gracefully if unset.

## Enter the Property ID (both options)

GA4 Admin → Property Settings → numeric **Property ID** (e.g. `123456789`, *not*
the `G-XXXX` measurement ID). In the dashboard: customer → **SEO → Integrations
→ Google Analytics 4** → paste the ID → **Save** → **Test** (runs a live 7-day
query and flips the integration to `active`).

## Conversion events (the important part)

The client recognizes these GA4 event names out of the box and normalizes them:

| GA4 event(s) | Report bucket |
|---|---|
| `phone_click`, `click_to_call`, `tel_click`, `call_button_click` | **phone_click** |
| `form_submit`, `generate_lead`, `contact_form`, `contact_form_submit` | **form_submit** |
| `appointment_request`, `book_appointment`, `schedule_appointment` | **appointment_request** |

Most dental sites don't emit these automatically — set them up once per site
(best practice: **Google Tag Manager**):

- **Phone calls:** a GTM trigger on clicks to `tel:` links → GA4 event
  `phone_click`.
- **Form submits:** a GTM form-submit trigger (or the platform's native submit
  event) → GA4 event `form_submit`.
- Mark both as **Key events** in GA4 (Admin → Key events) so they're treated as
  conversions in GA4's own UI too.

Custom event names? Add them to the integration config:
`{"property_id": "...", "conversion_events": ["chat_started"]}`. Unknown names
are tracked under their own label.

## How it behaves

- Pulls a trailing window ending **yesterday** (GA4 intraday data is incomplete).
- Channel is bucketed from `sessionDefaultChannelGroup`; the report's Leads
  section shows **organic** leads.
- Writes are **idempotent** (upsert per day/event/channel) — safe to re-run.
- **Resilient:** RunReport is retried with exponential backoff on transient gRPC
  errors and **paginated** so busy properties aren't truncated.
- **Fails safe:** if the lib, credentials, or property aren't configured the job
  logs and skips; the report simply omits the Leads section. No crash, no zeros.
