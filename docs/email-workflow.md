# Email Workflow & Config

How customer emails work in PracticeRank: which email to send at each stage, how
to send it, and where the templates live.

## Where the templates live
- Source: `templates/emails/*.md` (one file per email; `Subject:` on the first line).
- Variables like `{practice_name}`, `{contact_name}`, `{ai_mentions}` are filled
  with the customer's real data at render time.
- Stage metadata (category + which onboarding steps each email is for) is defined
  in `dashboard/app.py` → `EMAIL_TEMPLATE_META`. Edit there to re-map an email to a
  different stage or category.

## Using the dashboard (the normal way)
Customer page → **Emails** tab. It now:
- **Renders** every template with that customer's live data.
- **Orders** them so the emails relevant to the customer's *current* onboarding
  step come first, each flagged ⭐ "recommended for current stage."
- **Search box** — filter by name/subject/category as you type.
- **Category chips** — Sales / Access / Onboarding / Approvals / Reporting.
- **Copy for Email / Copy Subject** — copies formatted text; paste into Gmail,
  Outlook, or any client. (Sending itself is manual — see below.)

## Which email at which stage

| Order | Email | Category | Send when (onboarding step) |
|---|---|---|---|
| 1 | Pricing Quote (`08`) | Sales | `new`, `outreach` — prospect deciding |
| 2 | Initial Access Request (`01`) | Access | `outreach`, `setup` — signed, need platform access |
| 3 | Access Follow-Up (`02`) | Access | `setup` — access still pending |
| 4 | Onboarding Complete (`03`) | Onboarding | `review`, `live` — everything connected |
| 5 | Staging Approval (`05`) | Approvals | `review`, `live` — changes staged, need sign-off |
| 6 | Content Review (`06`) | Approvals | `content`, `live`, `monitoring` — new content to approve |
| 7 | Weekly SEO Update (`07`) | Reporting | `live`, `content`, `monitoring` — weekly progress |
| 8 | Monthly Report (`04`) | Reporting | `monitoring` — monthly deep-dive |

The board's onboarding steps: `new → outreach → setup → review → live → content →
monitoring` (plus `attention`, `paused`). The daily status check auto-advances
customers toward `monitoring` (see `specs/active/daily-status-reconciliation.md`).

## Sending
Today, **sending is manual**: copy the rendered email from the dashboard and paste
it into your email client. There is **no automated SMTP/ESP configured** — the
platform renders, it does not deliver. `scripts/send_email.py` renders/previews a
template from the CLI but also does not deliver:

```
python scripts/send_email.py --template 01-initial-access-request \
    --customer paradigm-experts --preview
```

If/when we want automated delivery, wire an ESP (e.g. SendGrid/Postmark) behind a
small `send()` in `send_email.py` and add the API key to `.env` — the weekly-report
job (`scripts/weekly_reports.py`) already has an `EMAIL_CUSTOMERS = False` switch
that would flip on customer delivery.

## Adding or re-staging an email
1. Add `templates/emails/NN-name.md` (start with `Subject: …`).
2. Add an entry to `EMAIL_TEMPLATE_META` in `dashboard/app.py` with its
   `category`, relevant `steps`, and `order`. Done — it appears in the tab,
   filtered and ordered correctly.
