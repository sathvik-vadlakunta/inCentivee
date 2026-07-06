# Admin app UX/navigation review + cleanup

**Status:** quick wins + consolidation done (2026-06-29) · **Trigger:** "lots of pages per client, navigation
is confusing — full review of where we can improve layout/UX."

## Audit findings (the why)
- A single client page exposed **~34 navigation points**: 9 top tabs → "SEO & GEO" fanned into 9 sub-tabs
  → 16-item Actions menu. Plus 13 global nav items and **5 different nav patterns** (sidebar links, tabs,
  sub-tabs, collapsible cards, toggles).
- Same concept in 3–4 places under different names: Reports (×4), Backlinks/FATJOE (×4), Content (×3).
- Label collisions: "Overview" top tab AND a "SEO Overview" sub-tab AND a global "Dashboard".
- Overview tab = 12-card mega-scroll mixing health + actions + reference.

## Shipped — quick wins
- Renamed jargon/collisions: nav "SEO & GEO" → **Search & AI**; its "Overview" sub-tab → **Summary**;
  global "Reports" → **Audit Reports** (it's the prospect lead-magnet audits).
- **Dashboard vs Analytics** disambiguated: page-header subtitles + descriptive sidebar tooltips
  (Dashboard = action items & health; Analytics = performance metrics & leaderboard).
- **De-orphaned FATJOE Catalog**: the `/fatjoe/catalog` endpoint now highlights the FATJOE nav active
  (reachable from the queue header link added in the FATJOE overhaul).

## Shipped — per-client consolidation (9 → 6 top tabs)
Regrouped the nav (all content divs left in place — zero content risk) into collapsible groups driven by
`data-tabs` on each `.detail-nav-group`; `switchTab` generalized to open the owning group + highlight it:
1. **Overview** (slimmed — KPI History + Recent Runs now collapsed in a "History & recent runs" `<details>`)
2. **Search & AI** — Checklist, Summary, Rankings, Traffic, Audit, Backlinks, Competitors, **AI Mentions**, Reviews, Integrations
3. **Content** — Recommendations + **Emails**
4. **Local SEO** (conditional)
5. **Reports**
6. **Account** — Details & Access + **Notes**

`switchSeoSubtab` targets the SEO group specifically; hash-restore handles grouped sub-items. Verified:
all pages + customer_detail render 200 authenticated.

## Not yet done (remaining recommendations)
- Cross-link the client Backlinks sub-tab ↔ FATJOE queue ("Order links for this client →").
- Unify on one nav pattern app-wide (tabs everywhere; collapsible cards only for lists).
- Further Overview slim: move Platform Access fully into Account (currently still on Overview too).
- Terminology pass across remaining headers (proof vs progress reports).
