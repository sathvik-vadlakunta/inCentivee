# Gate recurring LLM work to cut-over customers only

**Goal (Kody, 2026-07-08/09):** Stop paying for LLM work — and polluting baselines —
on customers that haven't really started. Recurring per-customer work runs **only for
customers we've cut over** (site live with our changes / managed in Cloudflare). A new
customer gets a **one-time baseline** on add; recurring work waits until cut-over.

Why cut-over (not "paying"): payment is the business trigger, but the operational
truth is whether the site is live with our changes. Parian is cut over but not yet
paying; not-yet-started customers (even if marked `active`) shouldn't burn LLM spend.

## The flag (operator-controlled in the admin app)
`customers.cutover` (INTEGER 0/1) + `customers.cutover_at` (ISO date).
- Toggle: **customer detail page** → "Mark cut over / Clear cut-over" button + a
  green "🟢 Cut over" / grey "⚪ Not cut over" badge next to the status.
- Route: `POST /customer/<id>/cutover` (`toggle_cutover`), logs an activity entry.

## Source of truth (`geo_agent/db.py`)
- `db.is_cutover(customer_id)` → the gate (customer.cutover truthy).
- `db.set_cutover(customer_id, on)` → toggles + stamps `cutover_at`.
- `db.list_recurring_customers()` → customers where `cutover = 1`.
- `db._recurring_ids_sql()` → `SELECT id FROM customers WHERE cutover = 1` (badge COUNTs).
- `db.is_paying(customer_id)` → active/trialing subscription. **Billing signal only**
  (UI display), NOT the recurring-work gate.

## Surfaces gated (recurring = cut-over only)
1. **3×/week AI** — `scripts/scheduled_ai_check.py::get_active_customers` → `list_recurring_customers()`.
2. **Weekly AI** — `scripts/weekly_ai_check.py --all path` → `list_recurring_customers()`.
3. **Monthly content** — `geo_agent/main.py` bulk `--use-db` → `list_recurring_customers()`.
4. **Biweekly content** — `scripts/biweekly_content.py --all` → `cutover` filter.
5. **Daily alerts** — `geo_agent/status_checker.py::reconcile_all` skips non-cutover.
6. **Content Queue** — `content_queue` route iterates `list_recurring_customers()`;
   `count_all_pending_content()` (nav badge) counts cut-over customers only.
7. **Alerts view** — `get_active_alert_count()` (badge) + `/alerts` page filtered to
   cut-over customers (existing alerts hidden, not deleted).

## Baseline on add (unchanged, ungated)
`/customer/new` fires a one-time `_run_ai_check_background` for every new customer, so a
not-yet-cut-over customer gets exactly one baseline, then nothing recurring until cut-over.

## Rollout
- Mark **Paradigm** (`paradigm-experts`) and **Parian** (`parian-lawyers-carrolton-injury`)
  `cutover = 1` after deploy — the only two currently live with our changes.
- Everyone else stays `cutover = 0` (baseline only) until their site is cut over.

## Not changed
- No customer data deleted; not-started alerts are hidden, not purged.
- `--customer <id>` manual runs still work for any customer (baseline + one-offs).
