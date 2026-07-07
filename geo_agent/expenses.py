"""PracticeRank operating-cost ledger — every AI/LLM API, data service, and
subscription the platform pays for, with monthly cost and when it's charged.

Powers the **Expenses** dashboard page. This is the single source of truth — edit
the line items here to keep the breakdown accurate. Costs are grouped as:

- ``fixed``       : flat monthly subscription / infra (exact, charged on a date)
- ``per_customer``: metered usage that scales with active customers (estimate)
- ``annual``      : billed yearly; shown monthlyized
- ``variable``    : pass-through COGS billed per order (e.g. FATJOE) — not totalled
- ``free``        : on a free tier today (shown at $0 with the paid trigger noted)

`monthly` is the USD monthly figure (for per_customer items it's the per-customer
rate; for annual it's the yearly amount). Keep estimates honest — flag guesses in
`note`. See specs/pricing for the unit economics these feed.
"""

from __future__ import annotations

# category, name, vendor, purpose, billing, monthly, charged, note
EXPENSE_ITEMS: list[dict] = [
    # ---- AI / LLM APIs (metered, scale per active customer) ----
    {"category": "AI / LLM APIs", "name": "Anthropic Claude API", "vendor": "Anthropic",
     "purpose": "Content generation, GEO/AEO, service scraping, free-audit worker",
     "billing": "per_customer", "monthly": 15.0, "charged": "Metered — billed monthly in arrears",
     "note": "~$15/customer/mo (Sonnet 4.6 + Opus). Biggest LLM line."},
    {"category": "AI / LLM APIs", "name": "Voyage AI (embeddings)", "vendor": "Voyage AI",
     "purpose": "Hybrid-RAG embeddings for the per-customer knowledge base",
     "billing": "per_customer", "monthly": 1.0, "charged": "Metered — billed monthly in arrears",
     "note": "Cheap — mostly one-time indexing then incremental."},
    {"category": "AI / LLM APIs", "name": "OpenAI (ChatGPT checks)", "vendor": "OpenAI",
     "purpose": "AI-visibility checks — is the client recommended in ChatGPT?",
     "billing": "per_customer", "monthly": 2.0, "charged": "Metered — billed monthly in arrears",
     "note": "Part of the multi-LLM AI-mention scan (3×/week)."},
    {"category": "AI / LLM APIs", "name": "Google Gemini API", "vendor": "Google",
     "purpose": "AI-visibility checks — Google AI / Gemini recommendations",
     "billing": "per_customer", "monthly": 1.0, "charged": "Metered — billed monthly in arrears",
     "note": "Low cost / generous free tier."},
    {"category": "AI / LLM APIs", "name": "Perplexity API", "vendor": "Perplexity",
     "purpose": "AI-visibility checks — Perplexity answer citations",
     "billing": "per_customer", "monthly": 2.0, "charged": "Metered — billed monthly in arrears",
     "note": "Part of the AI-mention scan."},
    {"category": "AI / LLM APIs", "name": "xAI Grok API", "vendor": "xAI",
     "purpose": "AI-visibility checks — Grok recommendations",
     "billing": "per_customer", "monthly": 2.0, "charged": "Metered — billed monthly in arrears",
     "note": "Part of the AI-mention scan."},

    # ---- SEO & Data APIs ----
    {"category": "SEO & Data APIs", "name": "Moz Links API", "vendor": "Moz",
     "purpose": "Domain Authority + competitor DA tracking",
     "billing": "fixed", "monthly": 20.0, "charged": "Monthly subscription (API Starter)",
     "note": "Flat — covers all customers."},
    {"category": "SEO & Data APIs", "name": "BrightLocal API", "vendor": "BrightLocal",
     "purpose": "Citation tracking / NAP audit / listings management",
     "billing": "free", "monthly": 0.0, "charged": "Not yet activated",
     "note": "Pending — no charge until the account is opened. Budget ~$40–80/mo when live."},
    {"category": "SEO & Data APIs", "name": "Google Places API", "vendor": "Google",
     "purpose": "Business lookup — address, phone, rating, reviews",
     "billing": "fixed", "monthly": 5.0, "charged": "Metered — monthly (mostly inside $200 free credit)",
     "note": "Usually $0 thanks to Google's monthly credit; budgeted small."},
    {"category": "SEO & Data APIs", "name": "Google PageSpeed API", "vendor": "Google",
     "purpose": "PageSpeed / Core Web Vitals scoring",
     "billing": "free", "monthly": 0.0, "charged": "Free tier", "note": "No cost."},
    {"category": "SEO & Data APIs", "name": "Search Console + GA4 APIs", "vendor": "Google",
     "purpose": "Search performance + conversions/leads reporting",
     "billing": "free", "monthly": 0.0, "charged": "Free", "note": "Free Google APIs."},
    {"category": "SEO & Data APIs", "name": "Nominatim + Overpass (OSM)", "vendor": "OpenStreetMap",
     "purpose": "Geocoding + nearby-city discovery for service areas",
     "billing": "free", "monthly": 0.0, "charged": "Free (keyless)", "note": "No account needed."},

    # ---- Reviews & funnel ----
    {"category": "Reviews & Funnel", "name": "In-house review funnel", "vendor": "PracticeRank (Cloudflare/Astro)",
     "purpose": "Self-hosted star-gate page + free Google review link + QR / email templates",
     "billing": "free", "monthly": 0.0, "charged": "Free — runs on our existing infra",
     "note": "Built on the Cloudflare Workers / Astro stack we already use — $0 marginal cost. "
             "Grade.us (~$40/location) is available as an OPTIONAL billable upsell for clients who want "
             "multi-platform review management + a reporting dashboard."},

    # ---- Publishing & comms ----
    {"category": "Publishing & Comms", "name": "Resend (email)", "vendor": "Resend",
     "purpose": "Transactional email — contact-form leads, reports, onboarding, alerts",
     "billing": "fixed", "monthly": 20.0, "charged": "Monthly subscription (Transactional Pro)",
     "note": "Paid plan unlocks multiple verified sending domains, so each customer site "
             "can send branded email from its own domain (noreply@<customer>). Automated via "
             "scripts/verify_customer_email_domain.py."},
    {"category": "Publishing & Comms", "name": "Webflow API", "vendor": "Webflow",
     "purpose": "Push content/schema to client Webflow sites",
     "billing": "variable", "monthly": 0.0, "charged": "Per client (their plan)",
     "note": "Client's Webflow plan covers API — not our cost."},
    {"category": "Publishing & Comms", "name": "Cloudflare (Pages/Workers/DNS)", "vendor": "Cloudflare",
     "purpose": "Marketing site hosting, audit Worker, DNS/CDN",
     "billing": "free", "monthly": 0.0, "charged": "Free tier",
     "note": "Free today; Workers Paid is $5/mo if we exceed 100k req/day."},

    # ---- Infrastructure ----
    {"category": "Infrastructure", "name": "DigitalOcean droplet (shared)", "vendor": "DigitalOcean",
     "purpose": "Dashboard + GEO-agent pipeline host (shared with OptionsOwl)",
     "billing": "fixed", "monthly": 24.0, "charged": "Monthly on billing-cycle date",
     "note": "~Half of a shared droplet allocated to PracticeRank — adjust to your real plan."},
    {"category": "Infrastructure", "name": "practicerank.ai domain", "vendor": "Registrar",
     "purpose": "Primary domain",
     "billing": "annual", "monthly": 18.0, "charged": "Annual renewal",
     "note": "~$18/yr → $1.50/mo amortized."},

    # ---- Link building (variable COGS — billed per order, not a subscription) ----
    {"category": "Link Building (variable COGS)", "name": "FATJOE — links / citations / listicles",
     "vendor": "FATJOE", "purpose": "Backlinks, local citations, brand listicles per client tier",
     "billing": "variable", "monthly": 0.0, "charged": "Per order (drip / one-time)",
     "note": "Pass-through COGS that scales with client tier — tracked live in each "
             "customer's Backlinks & Authority ledger, not a fixed monthly bill."},

    # ---- Setup / one-time costs we incur to onboard a NEW customer ----
    # `monthly` here = the one-time amount (charged once at onboarding, not recurring).
    {"category": "Setup / one-time (per customer)", "name": "Onboarding citation build (100)",
     "vendor": "FATJOE", "purpose": "Initial 100 local citations + NAP foundation",
     "billing": "onetime", "monthly": 135.0, "charged": "Once at onboarding",
     "note": "FATJOE 100-citation pack ($135)."},
    {"category": "Setup / one-time (per customer)", "name": "Initial audit + content scrape",
     "vendor": "Anthropic / Voyage", "purpose": "Full SEO/AEO audit, services scrape, RAG index build",
     "billing": "onetime", "monthly": 10.0, "charged": "Once at onboarding",
     "note": "Claude + Voyage tokens for the first deep crawl/index."},
    {"category": "Setup / one-time (per customer)", "name": "Cloudflare migration + setup",
     "vendor": "Internal / VA", "purpose": "Move site to managed platform, DNS, SSL, perf tuning",
     "billing": "onetime", "monthly": 60.0, "charged": "Once at onboarding (Grow & Dominate)",
     "note": "~6–8 VA/dev hours. Optimize tier has no migration."},
    {"category": "Setup / one-time (per customer)", "name": "Professional website redesign",
     "vendor": "Contract designer", "purpose": "Full UI/UX redesign — Dominate tier only",
     "billing": "onetime", "monthly": 5000.0, "charged": "Once at onboarding (Dominate only)",
     "note": "$4,000–6,000 pass-through; recovered by Dominate's $7.5–10k setup fee."},
]


# ---------------------------------------------------------------------------
# REAL recurring subscriptions we actually pay each month (for the reimbursement
# ledger — expense_entries table). These are seeded into a month on demand and
# then edited to the exact charged amount. Metered lines seed at $0 as a reminder
# to paste in the real invoice figure. This is the source of truth for what the
# monthly "Add recurring" button drops in — keep amounts close to reality.
# ---------------------------------------------------------------------------
RECURRING_TEMPLATES: list[dict] = [
    {"key": "digitalocean", "category": "Infrastructure", "vendor": "DigitalOcean",
     "name": "DigitalOcean droplet (shared)", "amount": 24.0,
     "note": "~Half of the shared droplet allocated to PracticeRank — set to your real split."},
    {"key": "google_workspace", "category": "Google", "vendor": "Google",
     "name": "Google Workspace (Business Standard)", "amount": 0.0,
     "note": "Business Standard, ~6–7 seats — metered, varies with seat count "
             "(~$20–50/mo). Auto-paid ~1st for the prior month (Visa …8695). Enter the real charge."},
    {"key": "google_voice", "category": "Google", "vendor": "Google",
     "name": "Google Voice (Telecom)", "amount": 0.0,
     "note": "Voice Starter for practicerank.ai + telecom taxes/surcharges (~$10–14/mo). "
             "Auto-paid ~1st for the prior month (Visa …8695). Enter the real charge."},
    {"key": "moz", "category": "SEO & Data APIs", "vendor": "Moz",
     "name": "Moz Links API (API Starter)", "amount": 20.0,
     "note": "Flat monthly — covers all customers."},

    # ---- AI / LLM APIs (all metered; pulled live via usage_sync where the
    #      provider exposes a cost API, otherwise paste the invoice amount) ----
    {"key": "anthropic", "category": "AI / LLM APIs", "vendor": "Anthropic",
     "name": "Anthropic (Claude API)", "amount": 0.0,
     "note": "Metered — Claude content/GEO. Auto-syncs from the Anthropic Cost API (or paste the invoice)."},
    {"key": "openai", "category": "AI / LLM APIs", "vendor": "OpenAI",
     "name": "OpenAI (ChatGPT API)", "amount": 0.0,
     "note": "Metered — ChatGPT AI-visibility checks. Auto-syncs from the OpenAI Costs API (or paste the invoice)."},
    {"key": "gemini", "category": "AI / LLM APIs", "vendor": "Google",
     "name": "Google Gemini API", "amount": 0.0,
     "note": "Metered — Gemini AI-visibility checks. Paste the invoice (Cloud Billing export)."},
    {"key": "perplexity", "category": "AI / LLM APIs", "vendor": "Perplexity",
     "name": "Perplexity API", "amount": 0.0,
     "note": "Metered — Perplexity answer-citation checks. Paste the invoice."},
    {"key": "xai", "category": "AI / LLM APIs", "vendor": "xAI",
     "name": "xAI (Grok API)", "amount": 0.0,
     "note": "Metered — Grok AI-visibility checks. Paste the invoice."},

    {"key": "google_apis", "category": "Google", "vendor": "Google",
     "name": "Google Maps / Places API", "amount": 0.0,
     "note": "Usually within the $200 monthly credit — enter any overage."},
]


def compute_expenses(active_customers: int = 1, fatjoe_mtd: float | None = None,
                     fatjoe_total: float | None = None) -> dict:
    """Group line items by category and total them for `active_customers`.

    Per-customer items are multiplied by the customer count; annual items are
    monthlyized. Variable COGS (FATJOE) is now wired to the REAL month-to-date
    spend from logged offsite_orders (`fatjoe_mtd`) — surfaced as its own
    variable-COGS total and folded into an all-in monthly figure, instead of the
    old placeholder that excluded it entirely.
    """
    n = max(active_customers, 0)
    groups: dict[str, list[dict]] = {}
    fixed_total = usage_total = annual_total = 0.0
    setup_total = setup_min = 0.0  # one-time onboarding cost per customer
    variable_cogs = 0.0

    for item in EXPENSE_ITEMS:
        row = dict(item)
        b = item["billing"]
        if b == "per_customer":
            row["monthly_effective"] = round(item["monthly"] * n, 2)
            row["display_rate"] = f"${item['monthly']:.2f}/customer"
            usage_total += row["monthly_effective"]
        elif b == "annual":
            row["monthly_effective"] = round(item["monthly"] / 12.0, 2)
            row["display_rate"] = f"${item['monthly']:.0f}/yr"
            annual_total += row["monthly_effective"]
        elif b in ("fixed", "free"):
            row["monthly_effective"] = round(item["monthly"], 2)
            row["display_rate"] = "free" if b == "free" else f"${item['monthly']:.2f}/mo"
            fixed_total += row["monthly_effective"]
        elif b == "onetime":
            # One-time per-customer onboarding cost — kept out of the recurring total.
            row["monthly_effective"] = round(item["monthly"], 2)  # the one-time amount
            row["display_rate"] = "one-time"
            setup_total += item["monthly"]
            # "min" setup = exclude the Dominate-only designer (a tier-specific add).
            if "redesign" not in item["name"].lower():
                setup_min += item["monthly"]
        else:  # variable — only the FATJOE line carries real logged COGS
            is_fatjoe = item.get("vendor") == "FATJOE"
            if is_fatjoe and fatjoe_mtd is not None:
                row["monthly_effective"] = round(fatjoe_mtd, 2)
                row["display_rate"] = f"${fatjoe_mtd:,.0f} this month"
                if fatjoe_total is not None:
                    row["note"] = (f"Real logged COGS — ${fatjoe_mtd:,.0f} month-to-date, "
                                   f"${fatjoe_total:,.0f} all-time. Logged on the FATJOE queue "
                                   f"per order; priced from the FATJOE catalog.")
                variable_cogs += round(fatjoe_mtd, 2)
            else:
                row["monthly_effective"] = None
                row["display_rate"] = "variable"
        groups.setdefault(item["category"], []).append(row)

    recurring = round(fixed_total + usage_total + annual_total, 2)
    return {
        "groups": groups,
        "active_customers": n,
        "totals": {
            "fixed": round(fixed_total, 2),
            "usage": round(usage_total, 2),
            "annual": round(annual_total, 2),
            "recurring": recurring,
            "variable_cogs": round(variable_cogs, 2),
            "all_in_monthly": round(recurring + variable_cogs, 2),
            "per_customer_usage": round(usage_total / n, 2) if n else 0.0,
            "setup_per_customer": round(setup_total, 2),
            "setup_per_customer_base": round(setup_min, 2),
        },
        "category_totals": {
            cat: round(sum(r["monthly_effective"] for r in rows if r["monthly_effective"] is not None), 2)
            for cat, rows in groups.items()
        },
    }
