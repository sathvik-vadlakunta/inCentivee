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

## When the client doesn't have the Google accounts yet

This is common (Paradigm had no Analytics / Search Console / Tag Manager). **Do
not block onboarding waiting for them to create accounts.** Split it like this:

**We create and own these — no client action needed:**

- **Google Analytics (GA4), Tag Manager, Search Console.** Because we control the
  site and DNS, we create all three under our agency account
  (`kdoherty@practicerank.ai`) and install them ourselves. This is *better* than
  using the client's — consistent across every client, and we never lose access.
  - **Default — we port the site to our managed platform:** we rebuild it on our
    side, so all we need is **DNS access** to point the domain. No Webflow / CMS
    login required. We add GTM + GA and verify Search Console ourselves.
  - **Exception — client keeps their existing site** (e.g. Paradigm staying on
    Webflow): then we also need **Webflow editor access** so we can install the
    tags on their site. Still create/own GA4, GTM, and GSC under our account.

**Only the client can own this one:**

- **Google Business Profile.** Tied to their real address and verified by Google
  (postcard / phone / video), so it must be theirs. Three cases:
  1. *They have it* → they grant us **Manager** via the Leadsie link.
  2. *It exists but unclaimed* → they claim it (link below), then grant Manager.
  3. *No profile at all* → they create one (link below); we help optimize it.

### Self-serve setup links (send only if they want to DIY)

Most clients should just use the Leadsie link and let us handle the rest. But if
a client prefers to set things up themselves, these are the official Google
how-to pages — safe to paste into an email:

- **Google Business Profile** (create / claim / verify):
  https://support.google.com/business/answer/6300717
- **Google Analytics (GA4)** — create account & property:
  https://support.google.com/analytics/answer/9304153
- **Google Search Console** — add your site:
  https://support.google.com/webmasters/answer/34592
- **Google Tag Manager** — create account & container:
  https://support.google.com/tagmanager/answer/6103696

After they create any of these, they grant us access via the **same Leadsie
link** — no need to share passwords.

## Notes

- The Leadsie link never changes — bookmark it.
- It only grants the access we ask for; the client approves exactly what they see.
- If a client's Google Business Profile is owned by a previous marketer/agency,
  Leadsie can't force a transfer — fall back to the "Request access / Own this
  business?" flow described in the access email, or book a quick call.
