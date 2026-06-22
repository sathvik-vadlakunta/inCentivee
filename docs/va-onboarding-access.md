# VA Instructions — Getting Client Access (Leadsie one-click)

When a new client signs, we need access to their Google accounts (Business
Profile, Analytics, Search Console, Tag Manager) plus their website/CMS and DNS.
**Use the Leadsie link first — it grants all the Google accounts in one step, no
passwords.**

## The link

```
https://app.leadsie.com/connect/practicerank/manage
```

This is our permanent PracticeRank connect link. It's safe to send to any
client. It is already built into the onboarding emails (see below) — you usually
don't need to paste it manually.

## Step by step

1. **Open the customer** in the dashboard → **Emails** tab. At the top there's a
   green **"One-click client access (Leadsie)"** box with a **Copy link** button.
2. **Send the access-request email** (template `01 — Initial Access Request`, the
   ⭐ recommended one during onboarding). The email now **leads with the Leadsie
   link** automatically — the client just clicks it, signs in with Google, and
   approves PracticeRank. That covers Business Profile, Analytics, Search Console
   & Tag Manager at once.
3. If the client prefers to do it themselves, the same email still lists the
   manual per-account steps underneath as a fallback — no extra work for you.
4. **Two things Leadsie does NOT cover** — handle these separately (also in the
   same email):
   - **Website / CMS access** (Webflow API token, WordPress plugin, Squarespace
     contributor, etc.) — platform-specific steps are in the email.
   - **DNS access** (Cloudflare / domain registrar).
5. **Follow up** after ~2 days if access hasn't come through: send template
   `02 — Access Follow-up`. It re-sends the Leadsie link for any Google items
   still outstanding.
6. **Confirm it landed:** check Leadsie (you'll get a notification when a client
   connects) and verify the account shows as granted in the customer's access
   list. Mark each access item complete in the dashboard.

## What to tell the client (plain-language script)

> "Easiest way to get us set up: click this link, sign in with your Google
> account, and approve PracticeRank. It connects your Google Business Profile,
> Analytics, Search Console, and Tag Manager in about two minutes — you stay the
> owner, and there are no passwords to share."

## Notes

- The Leadsie link never changes — bookmark it.
- It only grants the access we ask for; the client approves exactly what they see.
- If a client's Google Business Profile is owned by a previous marketer/agency,
  Leadsie can't force a transfer — fall back to the "Request access / Own this
  business?" flow described in the access email, or book a quick call.
