# Daily Status Reconciliation — Plan of Action

**Goal:** A daily per-customer job that checks each customer's *live site* against what
we have on file, marks fixed audit issues + published content as complete, ticks off
the SEO/GEO todos that are now satisfied, and **auto-advances the customer's status**
(e.g. paradigmexperts.com → `active` / `monitoring`) — with every change logged.

**Owner:** Kody · **Status:** Plan (awaiting go-ahead) · 2026-06-17

---

## Why this is mostly assembly, not new invention

The hard part — detecting what's true on the live site — already exists, it's just not
persisted or acted on:

| Capability | Already exists | Today it… |
|---|---|---|
| Detect schema / llms.txt / robots / sitemap / analytics on a live domain | `geo_agent/site_auditor.py` (`_check_*`), `_auto_detect_seo_status()` in `dashboard/app.py` | runs only on dashboard page-load; result is **thrown away** |
| Re-run a full audit + scores | `site_auditor.run_site_audit()`, `daily_gsc_pull.py` (Mondays) | saves a new audit but **doesn't reconcile old open issues** |
| Per-task todos | `SEO_GEO_TASKS` + `va_checklist` + `set_checklist_item()` | auto-detection overrides display but is **never saved** to the checklist |
| Issue / content status | `audit_issues.status`, `update_audit_issue_status()`, `content_recommendations.status`, `update_content_recommendation_status()` | only changed by hand |
| Status + step | `customers.status` (onboarding/active/paused/churned), `onboarding_step`, `set_customer_status()`, `set_onboarding_step()` | changed only manually on the board |

**So the work is:** (1) extract the detection into one shared module, (2) **persist** what it
finds, (3) reconcile issues/content/todos, (4) apply an auto-advance rule, (5) wrap it in a
daily cron. Nothing here needs new external APIs.

---

## The four reconciliation checks (per customer, per day)

**1. Audit issues → resolve fixed ones.**
Re-run `run_site_audit(domain)`. For each currently-`open` row in `audit_issues`, if the
audit no longer reports that issue (matched by `category`+`title`), set
`status='resolved'`, `fixed_date=today`. New issues found are inserted as `open` (existing
behavior). Net effect: the open-issue count tracks reality.

**2. Content recommendations → mark live ones published.**
For each rec in `draft`/`pending`/`approved`, verify it's actually on the site:
- **Webflow customers:** check the CMS item's published state via the Webflow API (we
  already store `webflow_item_id`), else crawl `target_page`.
- **Other platforms / no item id:** crawl the live page and match by title/slug/heading.
If found live → `status='published'`, set `published_at`. (Conservative: only promote, never
demote.)

**3. Todos → persist auto-detected completions.**
Run the shared detector and write its results into `va_checklist` via `set_checklist_item()`
for every verifiable `SEO_GEO_TASKS` key (schema types, llms.txt, robots AI rules, sitemap,
FAQ schema, etc.). Now the checklist is correct everywhere, not just on page-load.

**4. Status / onboarding_step → auto-advance.** See the state machine below.

---

## Auto-advance state machine (proposed rules)

Forward-only and conservative — it promotes when a customer is clearly "done & live," raises
an **alert** if something it had marked done later breaks, and **never** auto-pauses/churns.

```
"Fully live" = ALL of:
  • 0 open CRITICAL audit issues  (warnings allowed)
  • schema (LocalBusiness/Dentist) + llms.txt + robots AI rules detected live
  • ≥ 80% of this customer's content recs are 'published'
  • we have recent data flowing (a GSC pull OR an AI-mention run in last ~14d)

Transitions (only forward):
  review/setup  ─fully live─▶  onboarding_step = 'monitoring', status = 'active'
  live/content  ─fully live─▶  onboarding_step = 'monitoring', status = 'active'
  monitoring (active)         ─stays─ (steady state)

Regression guard (no silent downgrade):
  if a 'monitoring' customer loses schema/llms.txt OR a critical issue reappears
     → raise a 'critical' alert + set onboarding_step = 'attention'
       (status stays 'active'); never auto-pause/churn.
```

Every transition writes a `customer_activities` row ("Auto-advanced to active — all content
live, 0 critical issues") and an `alert` so it's visible on the board.

---

## How paradigmexperts.com flows through it

Current DB state: `status=onboarding`, `onboarding_step=review`, **6 open audit issues**,
content recs `14 draft / 18 pending / 0 published`, checklist empty. You say it's actually
all live. First run would:
1. Re-audit → finds the 6 issues fixed → mark them `resolved`.
2. Crawl/Webflow-verify the 32 recs → mark the live ones `published`.
3. Detect schema/llms.txt/robots → tick the matching checklist todos.
4. All green → set `onboarding_step='monitoring'`, `status='active'`, log
   "Auto-advanced to active." ✅

We'll **dry-run paradigm first** and print exactly what it *would* change before any writes.

---

## Code layout

- **`geo_agent/status_checker.py`** (new) — the brains:
  - `detect_live_status(domain, customer_id) -> dict[task_key,bool]` — extracted from the
    dashboard's `_auto_detect_seo_status` so both share one source of truth.
  - `reconcile_customer(db, customer_id, *, dry_run=False) -> ReconcileResult` — runs all 4
    checks, returns a structured diff (issues resolved, content published, todos ticked,
    transition). Writes only when `dry_run=False`.
- **`dashboard/app.py`** — repoint `_auto_detect_seo_status` to call the shared function
  (no behavior change for the page).
- **`scripts/daily_status_check.py`** (new) — cron entrypoint; loops customers in
  `status IN ('onboarding','active')`, calls `reconcile_customer`, prints a summary.
  Supports `--dry-run` and `--customer <id>`.
- Reuses existing: `run_site_audit`, `schema_validator`, `crawler`, Webflow publisher,
  and all the `db` setters above.

## Cron

```
# Daily 06:30 (after the 06:00 GSC pull, before the day starts)
30 6 * * * docker exec practicerank-dashboard python3 /app/scripts/daily_status_check.py
```
Runs sequentially; ~10–30s/customer (PageSpeed + a few fetches), so ~5 min for 12 customers —
fine. "However long it takes" is bounded by PageSpeed; we add per-call timeouts.

## Safety / robustness

- **Idempotent** — re-running the same day changes nothing new.
- **Forward-only** promotions; never auto-pause/churn.
- **Dry-run first** on paradigm, then enable.
- Every write is logged to `customer_activities` + surfaced as an `alert`.
- Each customer wrapped in try/except so one failure can't block the rest.
- Per-request timeouts on all live fetches.

## Build order

1. Extract `detect_live_status` into `status_checker.py`; repoint the dashboard. (no-op refactor, covered by existing page)
2. `reconcile_customer` checks 1+3 (audit-issue resolve + todo persist) — pure, testable.
3. Check 2 (content-live verification).
4. Auto-advance state machine + activity/alert logging.
5. `scripts/daily_status_check.py` + unit tests (mock auditor/crawler).
6. Dry-run on paradigm → review diff → enable cron.

## Decisions needed before build

- **D1 — "active" definition:** is `status='active'` + `onboarding_step='monitoring'` the
  right "done" state? (proposed yes)
- **D2 — regression behavior:** if a live customer breaks, alert + flip to `attention`
  (proposed) vs. alert-only vs. do nothing?
- **D3 — content "live" check:** Webflow API where we have it, crawl-and-match otherwise
  (proposed) — acceptable, or trust rec status only?
- **D4 — frequency:** daily 06:30 ok, or different cadence?
