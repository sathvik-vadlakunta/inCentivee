# Client Portal — Implementation

**Status:** implemented on `client-portal-branch` (commit `6860478`), all tests green, not yet deployed. Ticket 2a (CSRF + secure cookies, below) is still pending review before it gets built.

Source spec/mockup: `specs/platform/client-portal.html`. This doc replaces the working `tickets.md` ticket tracker (deleted) now that the feature is done — it records what actually shipped, the decisions made along the way, and what was found while testing.

## What this is

A logged-in, read-mostly portal at `/portal/*` where a dental-practice client can see their own PracticeRank score, drill into each of the 5 scoring pillars, approve/reject the content we've drafted for them, and pull up any past report — without any access to the admin dashboard. Entirely new and additive: nothing here touches `/r/<token>`, `/gap/<token>`, or any existing admin route.

## Key decisions

Three things were originally open questions; here's how they were resolved and why.

**Session exclusivity.** A browser is either logged into the admin dashboard or the client portal, never both. Both login routes share one Flask app and one secret key, so `_reset_session_kind(keep: str)` (`dashboard/app.py:158`) pops the *other* mode's session keys before establishing a new one — `/portal/login` clears `logged_in`/`username`/`display_name` first, `/login` clears the four `client_*` keys first. No code path can leave both `session.get("logged_in")` and `session.get("client_logged_in")` truthy at once.

**Account creation is password-less on the staff side.** Staff never choose or see a client's password. The admin "Client Portal Access" panel (on `customer_detail.html`) lets staff create a **username only**, which mints a one-time signup link (`/portal/signup/<token>`); the client visits it and sets their own password. `client_users.password_hash` starts `NULL` and stays that way until signup completes — `get_client_user_by_signup_token()` only resolves tokens where `password_hash IS NULL`, so a completed signup naturally invalidates its own link (no separate revocation step needed), and staff have a "Reset access" action that clears the password back to `NULL` and mints a fresh token for lost-link or forgotten-password cases.

**Every pillar page — including AI Visibility — reads the same frozen snapshot, never a live re-query.** `report_snapshots.payload_json` is a point-in-time capture of everything `weekly_report.build_report_data()` computed when that snapshot was generated. The Overview page's 5 pillar bars and each pillar's own detail page both read that same payload, so a client can never see the Overview bar disagree with the pillar page for the same report — a live re-query could easily drift (score changes between page loads, a new AI-check run lands mid-session, etc.). The one narrow, deliberate exception is Ticket 6's "Questions we test" sample list, which does run a live query — but it's scoped to the *exact historical `run_id`* recorded in that snapshot, not "whatever's latest right now," so it still describes the same historical moment as the rest of the page.

## What shipped

**Auth & session** (`dashboard/app.py`, `portal_login.html`, `portal_base.html`)
`client_login_required` decorator (mirrors the admin `login_required`). `GET/POST /portal/login` and `GET /portal/logout`. `portal_base.html` is a standalone shell — does not extend the admin `base.html`, contains no admin-session-gated content anywhere.

**Overview** (`GET /portal/`, `portal_home.html`)
Loads the latest snapshot (weekly → monthly → quarterly fallback), renders the score hero (score/grade/delta/one-line takeaway), the 5-pillar breakdown (each bar linking to its pillar page, colored by that pillar's own score band — never by rank among the 5), and 4 supporting cards (search clicks, AI hit-rate summary, reviews, "what we did for you"). Friendly empty state if no snapshot exists at all. Copy for all of this lives in one module, `geo_agent/portal_copy.py` (`PILLAR_COPY`, `FOUNDATION_ITEM_COPY`, `grade_takeaway()`, plus a `PILLAR_KEY_TO_SLUG`/`PILLAR_SLUG_TO_KEY` mapping between the DB's stable pillar keys and the portal's URL slugs) — not yet reviewed by marketing.

**Pillar detail pages** (`GET /portal/pillar/<key>`, `portal_pillar.html` shared by 4 pillars; `GET /portal/pillar/ai-visibility`, its own `portal_pillar_ai.html`)
- *GEO Foundation*: 8-item checklist from the snapshot's stored `technical_health` detail.
- *Content & Coverage*: by-type publish breakdown (grouped via `_CONTENT_CATEGORIES`) and service-area coverage chips — `compute_content_velocity()` was extended to also return `covered_areas`/`uncovered_areas` (not just the aggregate count) so this doesn't need a live re-query; older snapshots predating that change just show the aggregate with no chips.
- *Reputation*: 3 KPI cards plus a rating-trend chart. This is the one pillar page with a deliberate, narrow live-query exception: it reads `db.get_kpis(customer_id, "rating", limit=6)` directly rather than from the payload, because a *trend* needs to keep accumulating regardless of which snapshot is "latest" — the same `"rating"` KPI `kpi_tracker.track_google_reviews()` already records on its own schedule and the admin panel already reads.
- *Search Performance*: 3 KPI cards, two 8-week SVG line charts (clicks, AI mention rate) with hover/focus tooltips, and a keyword-movers table. `weekly_report.build_report_data()` was extended to stash `ctr` onto each `traffic_series` week and add a new `sections.ai_mention_series` (via `get_rolling_mention_stats(window=8, prompt_set="benchmark")`), both wrapped in try/except so missing history can't break report generation.
- *AI Visibility*: one `engine-row` per engine (Claude/ChatGPT/Perplexity/Gemini/Grok — always all 5, an untested engine renders as 0%/"not yet tested"), a share-of-voice breakdown, and a "Questions we test" sample scoped to the snapshot's exact historical `run_id`.

**Action Items** (`GET /portal/actions`, `portal_actions.html`; approve/reject/preview routes)
Pending content recommendations ("Needs your approval") shown first, then recently published (re-sorted by `created_at` since the underlying query's primary sort is `priority`, not recency), then "Other things we need from you" (live-queried checklist-style needs, with the redundant "approve pending content" line item filtered out since content now has its own section). `POST /portal/actions/<rec_id>/approve|reject` write through the exact same `db.update_content_recommendation_status()` the admin content queue uses, with an ownership check (404 on another customer's `rec_id`). `GET /portal/actions/<rec_id>` reuses `content_preview.html` (its one admin-coupled element, a hardcoded back-link, was parameterized into `back_url` so both the admin and portal routes can use it unchanged otherwise).

**Full Reports** (`GET /portal/reports`, `portal_reports.html`; `GET /portal/reports/<int:snapshot_id>`)
Lists snapshots per cadence (empty tab, not an error, when a cadence has none). Opening one returns the stored `html` directly via the identical rendering path `/r/<token>`'s `public_report()` uses — byte-identical output, just gated by portal login instead of an unguessable token. 404s on a missing or cross-customer snapshot id.

**Admin invite panel** (`customer_detail.html`, `POST /customer/<id>/client-users` + reset/deactivate routes)
Lists existing `client_users` for the customer (status derived from `password_hash IS NULL`), a username-only create form, and reset/deactivate actions. The generated signup link is a one-time server-side reveal (`session["client_portal_new_link"]`, popped on next GET) rather than routed through the flash-message system, specifically to avoid needing `|safe` on a block that's user-data-bearing elsewhere in that template.

**Client signup** (`GET/POST /portal/signup/<token>`, `portal_signup.html`)
Invalid/unknown/already-used tokens get a friendly dead-end message, never a raw 404 or stack trace. Password confirmation + 8-character minimum, re-shown inline on validation failure without touching the token. Success auto-logs the client in (session-exclusivity applied) and redirects to `/portal/`. The same token used twice is rejected the second time — proven by both an automated test and a manual `curl` round-trip (complete signup → re-GET the same link → rejected; second POST with a different password → rejected, first password still works).

## Bugs found during testing

Three real issues surfaced — two while building, one during a later pass with real pipeline-generated data (see below):

1. **Duplicate rating-history metric.** An early pass at the Reputation pillar page believed no rating history was tracked anywhere and added a new `google_rating` KPI capture in `weekly_report.generate_and_store()`. It wasn't true — `kpi_tracker.track_google_reviews()` (`geo_agent/kpi_tracker.py:49`) already records a `"rating"` KPI on its own schedule, which the admin panel already reads. Fixed by removing the redundant write and repointing the pillar route at the pre-existing metric.
2. **Colliding AI-engine logo badges.** The AI Visibility page used `engine_name[0]` for the logo initial — Claude/ChatGPT both start with "C", Gemini/Grok both start with "G". The spec mock uses distinct abbreviations (C/G/P/Ge/X); fixed with an explicit lookup dict. Cosmetic only, but invisible to every hand-typed test fixture (which happened to never render this collision) — only surfaced once real pipeline output was driven through the actual template.
3. **`published_at` never written by the seed script.** `add_content_recommendation()` doesn't write `published_at` at all — only `update_content_recommendation_status()` does, and only to "now." The demo-data script (below) was setting a `published_at` key that was silently ignored, so every "published" item had `published_at = NULL`, and `weekly_report.py`'s period filter (`published_at >= cur_start`) excluded all of them at every cadence — the Content & Coverage page's by-type breakdown showed all zeros. Fixed in the seed script (direct SQL `UPDATE` after insert); not a portal bug, but a good example of why testing against a real pipeline run catches things a hand-typed fixture wouldn't.

## Testing & demo data

`scripts/seed_demo_data.py` seeds a synthetic demo customer ("Aspen Grove Dental") with realistic **raw** data — 60 days of GSC daily metrics, 8 weekly AI-mention runs with full per-prompt results for the latest one, Google Places + reviews + rating history, the GEO Foundation checklist, content recommendations, competitors — across every table the report pipeline actually reads, then runs the real `weekly_report.generate_and_store()` pipeline against it. This produces a genuine `report_snapshots` row via the real code path, rather than a hand-typed `payload_json` fixture that can silently drift from what the pipeline actually emits (see bug #2 and #3 above — both were only caught this way). Idempotent via `--reset`; also seeds a portal login (`demo` / `demo-password-123`) and marks the customer cut-over so it shows up in admin `/content-queue` too.

```
python scripts/seed_demo_data.py --db /tmp/demo.db [--reset]
python dashboard/app.py --db /tmp/demo.db --port 5199 --debug
```

Do not commit the resulting `.db` file — `*.db` is gitignored repo-wide (PII protection), and it's unnecessary anyway since the seed script reproduces an equivalent environment from a plain checkout.

Automated coverage: `tests/integration/test_portal_*.py` (72 tests) — auth/session exclusivity, Overview, all 5 pillar pages, Action Items + approve/reject/preview, Reports, the admin invite panel, signup, and a consolidated `test_portal_e2e.py` closing pass (score/pillar parity against the real snapshot payload including the AI Visibility cross-page check, content-queue parity — proven against both a cut-over and a non-cut-over customer, byte-identical report viewing, the full signup round-trip, and cross-customer isolation including a direct proof of the `login_required`/`client_login_required` decorator logic plus spot-checks across ~9 concrete admin routes).

## Deferred: CSRF + secure session cookies

Flagged during auth research, not part of the original spec — this app currently has neither CSRF protection nor `SESSION_COOKIE_SECURE`/`SAMESITE` flags, and the portal introduces a second login surface sharing the same Flask secret key as admin. **Not yet approved for build.** If/when it is: `Flask-WTF`'s `CSRFProtect(app)` applied globally means every existing admin form (currently plain POSTs) needs `{{ csrf_token() }}` added or it starts rejecting with 400 — that cleanup would need to happen in the same pass, not just the new portal forms.

## Known gap (pre-existing, unrelated)

`geo_agent/secrets.py` is gitignored and was never committed to this repo at all. `customer_detail`'s WordPress-connection check imports it unconditionally, so a full `GET /customer/<id>` — including the new Client Portal Access panel — 500s on a fresh checkout with no workaround other than stubbing the module. Several pre-existing tests already fail the same way independent of this feature; this feature's own tests stub it out. Worth fixing at some point but out of scope here.

## Notable assumptions

- `rec_id` is untyped (`<rec_id>`) in portal routes since `content_recommendations.id` is `TEXT`; `snapshot_id` is `<int:snapshot_id>`.
- Approve/reject are plain form POSTs (full page reload), not fetch/JS calls like the admin equivalent — sufficient for an action taken a few times a month.
- No rejected-item list is surfaced to the client beyond removing it from "Needs your approval," matching the spec mock.
- Dark mode is out of scope; the portal ships light-only.
- No rate limiting / lockout on `/portal/login` or `/portal/signup/<token>` — parity with the existing admin login, not a new control.
- Username format is staff's free choice (doesn't have to be an email — there's no password-reset email to send to it).
- Signup links don't expire on a timer; staff's "Reset access" is the sole revocation/renewal mechanism.
- Successful signup auto-logs the client in rather than bouncing to `/portal/login` with a "your account is ready" message — lower friction, easy to flip later if preferred.
- Minimum password length is 8 characters, no other complexity rules (no existing precedent to match in `dashboard_users`).
