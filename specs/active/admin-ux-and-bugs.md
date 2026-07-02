# Admin App: Bug Fixes + Operator Self-Service (Dan)

**Goal:** Fix confirmed bugs and remove the friction that forces Kody into the loop, so Dan can onboard + run monthly delivery unaided. Skip WordPress (may not support).

## Batch 1 — Confirmed bugs
- [x] #1 SEO "vs ~30d" delta grabs oldest record, not ~30d ago — `app.py:472-479`
- [x] #2 FATJOE margin conflates subscription COGS w/ ad-hoc revenue — scope spend to ad-hoc (`sell_usd>0`) — `app.py:802-812`, `db.py:offsite_spend`
- [x] #3 `rerender_snapshots` no-ops — `get_report_snapshots` doesn't SELECT payload_json — `db.py:3845`, `weekly_report.py:879`
- [x] #4 Catalog "verified" checkbox dead (`1 if..else 1`) — `app.py:902`
- [x] #5 FATJOE double-pay: `quick_order` has no idempotency guard — `app.py:912`

## Batch 2 — Unblock Dan (backend/ops)
- [x] Integration/config health page (green/red per env+integration)
- [x] Job-health tracking: record last-run per scheduled job + stale banner
- [x] GBP/GTM/Cloudflare surfaced as "not verified" warnings (onboarding finish line)
- [x] "Publish all approved" (bulk staged schema) button

## Batch 3 — UI friction
- [x] Sidebar badge counts (Content Queue, Alerts, pending approvals, FATJOE due)
- [x] Status-change mis-click guard (confirm on onchange select)
- [x] Progress trend (score delta) on dashboard/customer list
- [x] Reduce reload+alert() pattern → toast + preserve tab (scoped to hottest actions)

## Skipped
- WordPress key handling / WP publish hardening (may deprecate WP support)
- customer_detail.html full JS extraction (large refactor — separate effort if desired)

## Decisions
- #2 margin = ad-hoc only: `offsite_spend(adhoc_only=True)` = COGS of orders w/ sell_usd>0.
- #5 guard: block a duplicate quick-order (same customer+type+dr within current period) unless `confirm=true` override.
