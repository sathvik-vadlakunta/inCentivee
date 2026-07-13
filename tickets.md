# Client Portal — Implementation Tickets

Source spec: `specs/platform/client-portal.html`. Plan: `~/.claude/plans/in-this-project-we-twinkly-wave.md`.
All routes are new and additive — none of this touches `/r/<token>`, `/gap/<token>`, or any existing admin route.

**Revision note:** three decisions that were originally open (D1–D3) have been resolved and folded into the tickets below — see "Decisions (resolved)" after the summary table.

## Summary

| # | Title | Est. | Depends on |
|---|---|---|---|
| 1 | Add client-portal data-layer methods to `geo_agent/db.py` | M | None |
| 2 | Build client auth/session (mutually exclusive with admin) + login/logout routes + portal shell | M | 1 |
| 2a | Add CSRF protection and secure session cookie flags *(to be reviewed later)* | S | 2 |
| 3 | Write plain-English portal copy module | S | None |
| 4 | Build Overview page (score hero, pillar breakdown, supporting cards) | M | 1, 2, 3 |
| 5 | Build Pillar Detail page for GEO Foundation, Content & Coverage, Reputation, Search Performance | L | 1, 2, 3, 4 |
| 6 | Build Pillar Detail page for AI Visibility (frozen snapshot, same as Overview) | M | 1, 2, 3, 4 |
| 7 | Build Action Items list page (recommendations + secondary needs) | M | 1, 2 |
| 8 | Add approve/reject actions to Action Items | S | 7 |
| 9 | Add recommendation preview route (reuse `content_preview.html`) | S | 1, 2, 7 |
| 10 | Build Full Reports history + snapshot viewer | S | 1, 2 |
| 11 | Add "Client Portal Access" admin panel — staff creates a username, no password | M | 1 |
| 12 | Build client sign-up page (client sets their own password) | S | 1, 2, 11 |
| 13 | End-to-end verification pass: isolation, regressions, data parity | M | 2–12 |

## Decisions (resolved)

- **Session exclusivity (was D1):** a browser session is either an admin session or a client session, never both. Logging into `/portal/login` clears any existing `logged_in`/`username`/`display_name` admin keys first, and logging into `/login` clears any existing `client_*` keys first. Implemented in Ticket 2.
- **Account creation flow (was D2):** staff no longer choose or see a client's password. Staff create a **username** only (Ticket 11); this mints a one-time signup link the client uses to set their own password (Ticket 12). Replaces the earlier "staff types a password" / "system generates and reveals a password" options entirely.
- **Pillar-page data source (was D3):** every pillar detail page — including AI Visibility — reads the *same frozen snapshot* `payload_json` that the Overview page reads, never a live re-query. Confirmed by reading `weekly_report.py:163-185`: the snapshot's `sections.ai` already captures `engines` (per-engine hit rate) and `sov` (share of voice) at generation time, so no live `db.get_ai_mention_runs()`/`db.get_share_of_voice()` call is needed on the pillar page at all. Implemented in Ticket 6.

---

## Ticket 1 — Add client-portal data-layer methods to `geo_agent/db.py`

**Status:** ✅ Complete.

**Context:** Spec §3 "Data mapping" marks client login as the only genuinely new table; everything else is a read against existing tables. Per the resolved account-creation decision, `client_users` must support a **password-less invite state**: staff create a row with a username and no password, and a one-time signup token; the client sets the password themselves later (Ticket 12). Also, no existing method fetches a `report_snapshots` row by primary key — `/portal/reports/<id>` needs that.

**Acceptance criteria:**
- [x] New table `client_users` created via a migration block alongside the existing `dashboard_users` migration (`geo_agent/db.py:572`):
  ```sql
  CREATE TABLE IF NOT EXISTS client_users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      customer_id TEXT NOT NULL REFERENCES customers(id),
      username TEXT NOT NULL UNIQUE,
      password_hash TEXT,                 -- NULL until the client completes signup
      display_name TEXT NOT NULL DEFAULT '',
      active INTEGER NOT NULL DEFAULT 1,
      signup_token TEXT UNIQUE,           -- NULL once consumed
      signup_token_created_at TEXT,
      last_login TEXT,
      created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
  );
  CREATE INDEX IF NOT EXISTS idx_client_users_customer ON client_users(customer_id);
  ```
  Running the app against an existing (pre-migration) DB file does not error, and the table exists after startup.
- [x] `create_client_user(customer_id, username, display_name="") -> dict` inserts a row with `password_hash = NULL` and a freshly minted `signup_token` (`secrets.token_urlsafe(24)`, same pattern `save_report_snapshot` already uses at `db.py:4111`), returns `{"id": ..., "signup_token": ...}`. Duplicate `username` returns/raises a clean, catchable error (not a bare `sqlite3.IntegrityError` bubbling to the route) — mirrors how `create_user` (`db.py:2931`) is called from `app.py`.
- [x] `get_client_user_by_signup_token(token) -> dict | None` — matches only rows where `signup_token = ?` **and** `password_hash IS NULL` (a token whose account already completed signup must not resolve, even if the token string is still technically present in the row at query time — the completion step below always clears it, so this is a defense-in-depth condition, not the primary guard).
- [x] `complete_client_signup(token, password) -> bool` — looks up by token (same guard as above), hashes the password with the existing `_hash_password` (`db.py:2915`, same scrypt helper `create_user` uses — no new crypto), sets `password_hash`, clears `signup_token` and `signup_token_created_at` to `NULL`. Returns `False` on an invalid/already-used/unknown token, `True` on success.
- [x] `regenerate_client_signup_token(id) -> str` — for staff-driven "resend invite" / "reset access": clears `password_hash` back to `NULL` and mints a new `signup_token`, returns the new token. (A client who never completed signup, or who needs a forced reset, goes through the exact same signup page again.)
- [x] `authenticate_client_user(username, password) -> dict | None` matches only rows with `active = 1` **and** `password_hash IS NOT NULL`, verifies via `_verify_password` (`db.py:2922`), and on success updates `last_login` to now. Returns `None` (never an exception) on no match, wrong password, inactive, or not-yet-signed-up.
- [x] `list_client_users(customer_id) -> list[dict]` returns all rows for that customer ordered by `created_at`, including enough to distinguish "invited, awaiting signup" (`password_hash IS NULL`) from "active" in the UI.
- [x] `set_client_user_active(id, active: bool)` and `delete_client_user(id)` implemented as single-row UPDATE/DELETE by primary key, committing before return.
- [x] `get_report_snapshot(snapshot_id: int) -> dict | None` — `SELECT * FROM report_snapshots WHERE id = ?`, returns the full row (including `payload_json` and `html`) or `None`.
- [x] Unit tests cover: create + signup-token issued; `get_client_user_by_signup_token` hit/miss; `complete_client_signup` success, then the same token failing a second time; `authenticate_client_user` failing before signup completes and succeeding after; wrong password; `active=0`; `regenerate_client_signup_token` invalidates the old token and issues a working new one; `get_report_snapshot` hit and miss. (`tests/unit/test_db.py::TestClientPortalUsers`, `::TestReportSnapshotByID`)

**Out of scope:** Any Flask route, session handling, or admin UI — this ticket is `geo_agent/db.py` only.

**Dependencies:** None.

**Estimate:** M

---

## Ticket 2 — Build client auth/session (mutually exclusive with admin) + login/logout routes + portal shell

**Status:** ✅ Complete.

**Context:** Spec principle "Real accounts, not links" and "Zero admin surface" (§1), plus the resolved session-exclusivity decision: a browser can be logged into the admin dashboard *or* the client portal, never both at once, to avoid the confusing/messy dual-session state the original plan left ambiguous.

**Acceptance criteria:**
- [x] `client_login_required` decorator added to `dashboard/app.py`, checking `session.get("client_logged_in")` only, redirecting to `url_for("portal_login")` — modeled on `login_required` (`app.py:158-164`).
- [x] A small shared helper (e.g. `_reset_session_kind(keep: str)`) pops the *other* mode's session keys before establishing a new session: `/portal/login` on success pops `logged_in`, `username`, `display_name` before setting the client keys; `/login` on success pops `client_logged_in`, `client_user_id`, `client_customer_id`, `client_display_name` before setting the admin keys. Both existing and new login routes call this helper — no path exists where both `logged_in` and `client_logged_in` are simultaneously truthy in the same session.
- [x] `GET/POST /portal/login` mirrors `/login` (`app.py:167-195`): on POST, calls `db.authenticate_client_user(username, password)` (field labeled "Username," matching the new invite-based signup flow rather than "Email"); on success clears any admin keys (above), sets `session["client_logged_in"]=True`, `session["client_user_id"]`, `session["client_customer_id"]`, `session["client_display_name"]`, calls `audit_log("client_login", customer_id=..., details=...)`, redirects to `/portal/`. On failure — including a not-yet-signed-up account, since `authenticate_client_user` returns `None` for those too — one generic flashed error ("Invalid username or password") with no user-enumeration, plus `audit_log("client_login_failed", ...)`.
- [x] `GET /portal/logout` pops only the four `client_*` session keys and redirects to `/portal/login`.
- [x] `portal_login.html` built per spec's Login mockup (`client-portal.html` lines 258-271, field relabeled Username), using the `BRAND` tokens from `geo_agent/weekly_report.py:36`.
- [x] `portal_base.html` built per spec's shared shell (topbar, nav, log-out) — does **not** `{% extends %}` the admin `base.html`, and contains no admin-session-gated content anywhere.
- [x] `GET /portal/` exists as a stub behind `client_login_required` rendering `portal_base.html` with a placeholder body (real content lands in Ticket 4).
- [x] Manual verification: (a) log into `/login` as staff, then in the same browser open `/portal/login` and log in as a client — confirm the admin session's `logged_in`/`username` keys are gone and hitting `/` now redirects to `/login`, not admin content; (b) reverse the order (client first, then staff) and confirm the same exclusivity holds; (c) confirm `/portal/` with no session redirects to `/portal/login`, and any `@login_required` admin route with only `client_logged_in` set redirects to `/login`. (`tests/integration/test_portal_auth.py`, plus a live local run against a scratch DB.)

**Out of scope:** Overview page content, pillar pages, action items, reports list, the sign-up page itself (Ticket 12), CSRF protection and secure cookie flags (Ticket 2a).

**Dependencies:** Ticket 1 (`authenticate_client_user`).

**Estimate:** M

---

## Ticket 2a — Add CSRF protection and secure session cookie flags

**Context:** Flagged during research into auth best practices — the app currently has neither. Not part of the original spec; this is hardening that piggybacks on Ticket 2 introducing a second login surface (`/portal/login`) sharing the same Flask app/secret key as admin. **Status: to be reviewed later**, not yet approved for build.

**Acceptance criteria:**
- [ ] **CSRF protection:** `Flask-WTF` added to `dashboard/requirements.txt` (not currently a dependency) and `CSRFProtect(app)` initialized in `app.py` alongside the `Flask(__name__)` app object (`app.py:55`). Applies globally, so every existing admin form (currently plain POSTs, no tokens) needs `{{ csrf_token() }}` added or it will start rejecting with 400 once this is enabled — that cleanup is in scope here. `portal_login.html`, `portal_base.html`'s logout, and all new portal POST forms include the token from the start.
- [ ] **Secure session cookie flags:** `app.config` gets `SESSION_COOKIE_SECURE=True`, `SESSION_COOKIE_SAMESITE="Lax"`, and an explicit `PERMANENT_SESSION_LIFETIME` (e.g. `timedelta(hours=12)`) added near the existing `app.config["PREFERRED_URL_SCHEME"] = "https"` line (`app.py:63`). `SESSION_COOKIE_HTTPONLY` is already Flask's default (True) — no change needed there. Applies to both admin and portal sessions since they share one Flask app/secret key.
- [ ] Manual verification: (a) confirm a POST to `/login`, `/portal/login`, or any admin form missing a CSRF token is rejected (400); (b) inspect the `Set-Cookie` header in dev tools and confirm `Secure` and `SameSite=Lax` are present on both admin and client sessions; (c) spot-check a handful of existing admin forms still submit successfully post-change.

**Out of scope:** Rate limiting / brute-force lockout on login routes (deferred per Ticket 13 assumption #7, no existing precedent to match); MFA.

**Dependencies:** Ticket 2 (both login surfaces need to exist to verify cookie/CSRF behavior on each).

**Estimate:** S

---

## Ticket 3 — Write plain-English portal copy module

**Context:** Spec principle "The customer is a dental practice owner, not a marketer" (§1) and the data-mapping table's explicit `NEW COPY` row for "Plain-English sentence per pillar" (§3). Verified while reading the code: neither `PILLAR_LABELS` (`practicerank_score.py:42`) nor `_FOUNDATION_ITEMS` (`practicerank_score.py:349-358`, plain tuples of internal checklist keys like `seo_schema_localbusiness`, `seo_llms_txt`) carry any client-facing wording today — all of this copy is new and needs a single source of truth so Overview and the pillar detail pages don't drift out of sync.

**Acceptance criteria:**
- [ ] A new module (e.g. `geo_agent/portal_copy.py`) defines:
  - `PILLAR_COPY: dict[str, dict]` keyed by the 5 pillar slugs (`ai-visibility`, `geo-foundation`, `content-coverage`, `reputation`, `search-performance`), each with `label`, `one_liner` (Overview breakdown sentence, e.g. spec line 300), and `hero_description` (pillar-detail-page sentence, e.g. spec line 381).
  - `FOUNDATION_ITEM_COPY: dict[str, dict]` keyed by each of the 8 `_FOUNDATION_ITEMS` first-keys (`seo_schema_localbusiness`, `seo_schema_faq`, `seo_llms_txt`, `seo_robots_txt`, `seo_llms_full`, `seo_xml_sitemap`, `seo_schema_review`, `seo_structured_headings`), each with `label` and `description` matching spec lines 458-465.
  - A `grade_takeaway(grade_label) -> str` helper producing the Overview score-hero one-liner (spec line 289 style), keyed off `grade_from_score()`'s existing grade labels (`practicerank_score.py:61`).
- [ ] Every string lives in this one file — no copy embedded inline in Jinja templates for these three surfaces.
- [ ] A comment notes this copy should be reviewed by Kody/marketing before shipping.

**Out of scope:** Wiring this module into any template (Tickets 4–6); `_FOUNDATION_ITEMS` ordering/weights themselves (unchanged).

**Dependencies:** None.

**Estimate:** S

---

## Ticket 4 — Build Overview page (score hero, pillar breakdown, supporting cards)

**Context:** Spec §1 "Score first, breakdown second" and the fully mocked Overview page (`client-portal.html` lines 273-364). This page's data-loading pattern — read the latest `report_snapshots` row, parse `payload_json`, never recompute — is reused as-is by every pillar detail page per the resolved D3 decision.

**Acceptance criteria:**
- [ ] `GET /portal/` (replacing the Ticket 2 stub) loads the customer's latest snapshot via `db.get_latest_report_snapshot(session["client_customer_id"], "weekly")`, falling back to `"monthly"` then `"quarterly"` if no weekly snapshot exists, and parses `payload_json`.
- [ ] `portal_home.html` renders, in order: (1) score hero — score, grade, delta vs. `score_prev`, one-line takeaway from `grade_takeaway()` (Ticket 3); (2) pillar breakdown — 5 bars from `data["score"]["pillars"]`, each showing `PILLAR_COPY[slug]["one_liner"]` and weight as "N% of your score," each linking to `/portal/pillar/<slug>`; (3) supporting cards — search clicks, AI hit-rate summary + per-engine chips, reviews, "what we did for you" — matching spec lines 334-361.
- [ ] Bar fill color is a function of that pillar's own score band (green/yellow-green/amber/red thresholds), never colored by rank/position among the 5 bars.
- [ ] "No report yet" state: if no snapshot exists in any of the three cadences, render a friendly empty state instead of erroring.
- [ ] Domain-authority/competitor-gap detail, FATJOE line items, and system alerts are **not** rendered anywhere on this page.
- [ ] Manual verification: load `/portal/` for a customer with a real snapshot and confirm every number matches that customer's admin-panel report for the same period.

**Out of scope:** Pillar detail pages (Tickets 5–6), Action Items, Full Reports.

**Dependencies:** Ticket 1, Ticket 2, Ticket 3.

**Estimate:** M

---

## Ticket 5 — Build Pillar Detail page for GEO Foundation, Content & Coverage, Reputation, Search Performance

**Context:** Spec principle "Every category is a door, not a dead end" (§1) and the 4 fully mocked pillar pages other than AI Visibility (`client-portal.html` lines 436-674). All four read exclusively from the same already-loaded snapshot `payload_json` as Overview — no new queries.

**Acceptance criteria:**
- [ ] `GET /portal/pillar/<key>` route added for `key` in `{geo-foundation, content-coverage, reputation, search-performance}`, loading the same latest-snapshot payload Ticket 4 loads, reusing one shared `portal_pillar.html` template keyed by `key`. Unknown `key` returns 404.
- [ ] Each page has a `pillar-hero` (score, delta, `PILLAR_COPY[key]["hero_description"]`) and a breadcrumb back to `/portal/`.
- [ ] **GEO Foundation**: 8-item checklist from the snapshot's stored technical-health detail (`items` dict, `compute_technical_health`, `practicerank_score.py:395-405`), each row's label/description from `FOUNDATION_ITEM_COPY` (Ticket 3), done/pending dot per spec lines 456-466.
- [ ] **Content & Coverage**: by-type breakdown bars (`_CONTENT_CATEGORIES` groupings, spec lines 489-495) and service-area coverage chips (spec lines 497-506), all from the snapshot payload.
- [ ] **Reputation**: 3 KPI cards (current rating, total reviews, new this period) and a rating-trend bar list (spec lines 529-542), from `sections.reviews`/`compute_reputation()` detail already in the payload.
- [ ] **Search Performance**: 3 KPI cards (clicks, impressions, CTR — CTR read directly off the `ctr` field already present in `sections.search.cur`/`.prev`), the two 8-week SVG line/area charts (clicks, AI mention rate) per the dataviz-skill-compliant markup already built in the spec (lines 574-661: solid hairline gridlines, single flat color per chart, only the endpoint direct-labeled, each with a collapsible `<details class="table-toggle">` full-data table), and the keyword-movers table (spec lines 663-672). Chart series come from the snapshot's `sections.traffic_series`/stored weekly figures (same "frozen, not live" rule as every other pillar — if the payload doesn't already carry 8 weeks of clicks/CTR/mention-rate at the granularity the chart needs, extend what gets written into `payload_json` at snapshot-generation time rather than querying `db.get_gsc_weekly_summary()`/`db.get_rolling_mention_stats()` live at render time).
- [ ] Real implementation adds a hover/focus tooltip on both line charts per the dataviz skill's `interaction.md`. Tooltip is additive only — every value must already be reachable via the endpoint label or the collapsible table.
- [ ] Manual verification: for each of the 4 keys, confirm the pillar-hero score matches the corresponding bar on `/portal/` for the same customer/snapshot, and confirm the Search Performance chart's 8 weekly numbers in the collapsible table match what's actually stored in that snapshot's `payload_json` (not a fresh live query).

**Out of scope:** AI Visibility pillar page (Ticket 6).

**Dependencies:** Ticket 1, Ticket 2, Ticket 3, Ticket 4.

**Estimate:** L

---

## Ticket 6 — Build Pillar Detail page for AI Visibility (frozen snapshot, same as Overview)

**Context:** Spec's flagship example (§1) — "your hit rate on each individual AI assistant, not just one blended percentage" — mocked at `client-portal.html` lines 366-434. Per the resolved D3 decision, this page must **not** issue any live query; it reads the exact same snapshot payload as Overview and every other pillar page, so the AI Visibility number on Overview's pillar bar can never disagree with this page's detail for the same report.

**Acceptance criteria:**
- [ ] `GET /portal/pillar/ai-visibility` uses the identical snapshot-loading call as Ticket 4/5 (no separate `db.get_ai_mention_runs()` or `db.get_share_of_voice()` call) — confirmed via `weekly_report.py:163-185` that `sections.ai.engines` (per-engine hit rate, sourced from `latest_ai["engines_json"]` at snapshot time) and `sections.ai.sov` (share of voice, from `db.get_share_of_voice()` at snapshot time) are already captured into `payload_json` when the snapshot was generated.
- [ ] "Your hit rate by AI assistant" renders one `engine-row` per engine in `ENGINES` (`scripts/scheduled_ai_check.py`: Claude, ChatGPT, Perplexity, Gemini, Grok) from `sections.ai.engines`, per spec lines 385-414. An engine absent from that dict (never run as of this snapshot) renders as 0% / "not yet tested" — every engine in `ENGINES` always has a row.
- [ ] "Share of voice" renders the practice + named competitors + "everyone else" from `sections.ai.sov`, per spec lines 425-432.
- [ ] "Questions we test" (sample prompts + hit/miss, spec lines 416-423) is the one sub-section with no aggregate figure already in `payload_json` — it is scoped to the **specific historical run** referenced by `sections.ai.latest`'s run id (i.e. `ai_mention_results` filtered to that exact `run_id`, not "whatever `ai_mention_runs` row is latest right now"). This keeps the sample-question list describing the same historical moment as the rest of the page even though it's technically a DB query rather than a payload field.
- [ ] Bar/chip colors assigned by each row's own value band (or a fixed "you" vs. "competitor" 2-color distinction for share-of-voice), not by rank position.
- [ ] Manual verification: confirm the per-engine numbers on this page exactly match `sections.ai.engines` inside that snapshot's stored `payload_json` (not the current live `ai_mention_runs` row, which may have since changed), and confirm the AI Visibility score shown here matches the AI Visibility bar on `/portal/` for the same snapshot byte-for-byte.

**Out of scope:** The other 4 pillar pages (Ticket 5).

**Dependencies:** Ticket 1, Ticket 2, Ticket 3, Ticket 4.

**Estimate:** M

---

## Ticket 7 — Build Action Items list page (recommendations + secondary needs)

**Context:** User's explicit correction mid-session: "make the actionable items page actually contain the content recommendations we generate for each client." Spec §"Action Items" mockup, `client-portal.html` lines 676-748.

**Acceptance criteria:**
- [ ] `GET /portal/actions` (`client_login_required`) calls `db.get_content_recommendations(session["client_customer_id"], limit=100)` (`db.py:2574`), splits into `status == "pending"` (shown first) and `status == "published"` (most recent ~8).
- [ ] `portal_actions.html` renders, in order: "Needs your approval · N" — one `rec-card` per pending item with title, friendly type label (reuse `_REC_TYPE_LABELS`, `weekly_report.py:431-435`), the `ai_impact_reason` field as the "why" copy, and Approve/Not for us/Preview affordances (wired in Tickets 8/9); then "Recently added to your site" — read-only rows per spec lines 728-730.
- [ ] Below that, "Other things we need from you" sourced from `build_report_data(db, customer_id, live_state=True)["sections"].get("needs", [])` (`weekly_report.py:390-420`), with its own "approve pending content" line item (if produced) dropped since content now has its own full section above.
- [ ] Empty state: when pending/published recs and `needs` are all empty, render "✅ You're all caught up" (spec lines 742-746) instead of empty section headers.
- [ ] Manual verification: for a test customer with a pending, a published, and a `needs` item, confirm this page's grouping matches what admin `/content-queue` shows for that customer's pending items.

**Out of scope:** Approve/reject write actions (Ticket 8), full-piece preview (Ticket 9).

**Dependencies:** Ticket 1, Ticket 2.

**Estimate:** M

---

## Ticket 8 — Add approve/reject actions to Action Items

**Context:** Spec's rec-card Approve/"Not for us" buttons must write status changes through the exact same DB write the admin content queue already uses.

**Acceptance criteria:**
- [ ] `POST /portal/actions/<rec_id>/approve` and `POST /portal/actions/<rec_id>/reject` (`client_login_required`) each: load via `db.get_content_recommendation(rec_id)` (`db.py:2649`), **404 if missing or `rec["customer_id"] != session["client_customer_id"]`** (matches the existing `content_preview` route's ownership-check pattern, `app.py:7314`), call `db.update_content_recommendation_status(rec_id, "approved" | "rejected")` (`db.py:2594`, same method `api_content_status` at `app.py:7334` uses), call `audit_log("client_content_status_changed", ...)`, redirect to `/portal/actions`.
- [ ] `content_recommendations.id` is `TEXT` (confirmed `db.py:165`), so the route uses `<rec_id>` with no `int:` converter.
- [ ] Approving/rejecting removes the item from "Needs your approval" on next load; approving doesn't move it into "Recently added" (still gated on `status == "published"`).
- [ ] Cross-check: approving from the portal is reflected in admin `/content-queue` for the same customer.
- [ ] Approving/rejecting a `rec_id` belonging to a different customer returns 404 and does not change that row.

**Out of scope:** Preview page (Ticket 9).

**Dependencies:** Ticket 7.

**Estimate:** S

---

## Ticket 9 — Add recommendation preview route (reuse `content_preview.html`)

**Context:** `dashboard/templates/content_preview.html` is confirmed standalone (no admin `base.html` extension) with no admin-only data — its only admin-coupled element is a hardcoded back-link (`content_preview.html:169`).

**Acceptance criteria:**
- [ ] `content_preview.html`'s back-link is parameterized (`back_url` passed in by the caller); the existing admin `content_preview` route (`app.py:7306-7318`) passes its current admin URL as `back_url`, unchanged behavior.
- [ ] `GET /portal/actions/<rec_id>` (`client_login_required`) loads via `db.get_content_recommendation(rec_id)`, same ownership check as Ticket 8, renders `content_preview.html` with `back_url` = `/portal/actions`.
- [ ] Confirmed no admin-only fields (webflow ids, publish errors) render anywhere in this template — only title/type/status/body, all already visible to the client on the Action Items list.
- [ ] Manual verification: "Preview full piece →" from `/portal/actions` renders the same body a staff member sees via the admin queue, with "← Back" returning to `/portal/actions`.

**Out of scope:** Editing recommendation content (no such feature exists anywhere today).

**Dependencies:** Ticket 1, Ticket 2, Ticket 7.

**Estimate:** S

---

## Ticket 10 — Build Full Reports history + snapshot viewer

**Context:** Spec §"Full Reports" (`client-portal.html` lines 750-775) — reuses the exact stored HTML `/r/<token>` already serves.

**Acceptance criteria:**
- [ ] `GET /portal/reports` (`client_login_required`) lists snapshots across weekly/monthly/quarterly (`report_periods`, `app.py:794-798`) via `db.get_report_snapshots(customer_id, rt, limit=26)`, per spec lines 759-772.
- [ ] `portal_reports.html` handles a cadence with zero snapshots as an empty tab, not an error.
- [ ] `GET /portal/reports/<int:snapshot_id>` (`client_login_required`) loads via `db.get_report_snapshot(snapshot_id)` (Ticket 1), **404s if missing or `snap["customer_id"] != session["client_customer_id"]`**, otherwise returns `snap["html"]` directly — identical rendering path to `/r/<token>`'s `public_report()` (`app.py:1644-1663`).
- [ ] Manual verification: confirm `/portal/reports/<id>` output is byte-identical to that snapshot's existing `/r/<token>` link; confirm guessing another customer's snapshot id returns 404.

**Out of scope:** Any change to `/r/<token>` itself or snapshot generation.

**Dependencies:** Ticket 1, Ticket 2.

**Estimate:** S

---

## Ticket 11 — Add "Client Portal Access" admin panel — staff creates a username, no password

**Context:** Plan §5, revised per the resolved account-creation decision: staff no longer set or see a client's password at all. Staff assign a username; the system mints a one-time signup link for the client to set their own password (Ticket 12). Panel sits near the existing "Secure customer share link" section (`customer_detail.html:2865-2878`).

**Acceptance criteria:**
- [ ] "Client Portal Access" panel lists existing `client_users` for this customer via `db.list_client_users(customer_id)`, showing username, status (**Invited — awaiting signup** vs **Active**, derived from `password_hash IS NULL`), active/inactive, last login.
- [ ] A form (username + optional display name — no password field anywhere in this UI) posts to `POST /customer/<customer_id>/client-users` (`@login_required`), calls `db.create_client_user(...)`, `audit_log("client_user_created", ...)`, and on success **displays the generated signup link** (`/portal/signup/<signup_token>`, absolute URL) in a copy-to-clipboard field so staff can hand it to the client via whatever channel they use — no new email-sending infrastructure required.
- [ ] "Reset access" action (for a lost invite link or a forgotten password) calls `db.regenerate_client_signup_token(id)` (Ticket 1), `audit_log("client_user_reset", ...)`, and re-displays the new signup link. This works for both "still invited, never signed up" and "was active, needs a fresh password" cases — both end up back at the signup page.
- [ ] "Deactivate" toggles `active` via `db.set_client_user_active`, `audit_log(...)`, independent of signup state.
- [ ] Duplicate-username creation shows a flashed error instead of a 500.
- [ ] Manual verification: create a username for a test customer, copy the generated link, confirm it matches the format Ticket 12's route expects; deactivate the account and confirm a since-completed login now fails at `/portal/login`.

**Out of scope:** Any client-facing self-service password reset (staff-driven "Reset access" is the only recovery path, matching the no-new-infra constraint).

**Dependencies:** Ticket 1.

**Estimate:** M

---

## Ticket 12 — Build client sign-up page (client sets their own password)

**Context:** Direct user request: staff should create a username only; the client visits a link and creates their own password. This is the missing half of Ticket 11's invite flow and the reason `client_users.password_hash` starts `NULL`.

**Acceptance criteria:**
- [ ] `GET /portal/signup/<token>` looks up via `db.get_client_user_by_signup_token(token)` (Ticket 1). An invalid, unknown, or already-consumed token shows a friendly "This invite link is invalid or has already been used — ask your account manager for a new one" message (not a raw 404 or stack trace).
- [ ] On a valid token, the page shows the practice name and the assigned username (read-only) plus a "Create a password" field and a "Confirm password" field, styled with the same `BRAND` tokens as `portal_login.html`.
- [ ] `POST /portal/signup/<token>` validates the two password fields match and meet a minimum length (8 characters), re-showing the form with an inline error otherwise (no data loss — token stays valid on a validation failure).
- [ ] On success, calls `db.complete_client_signup(token, password)` (Ticket 1). If it returns `False` (token already consumed by a concurrent request), show the same "invalid or already used" message rather than silently failing.
- [ ] On success, the client is signed in immediately: applies the same session-exclusivity clearing as `/portal/login` (Ticket 2's helper), sets the four `client_*` session keys, `audit_log("client_signup_completed", ...)`, redirects to `/portal/`.
- [ ] The same token, used a second time (e.g. the client re-opens the original invite email/link after already finishing signup), shows the "invalid or already used" message — never lets a second password overwrite the first silently.
- [ ] Manual verification: create a username via Ticket 11, open the generated link in a private window, set a password, confirm landing on `/portal/` already logged in; reopen the same original link and confirm it's rejected; log out and confirm `/portal/login` with the new username/password works.

**Out of scope:** Self-service "forgot password" (covered by staff-driven "Reset access" in Ticket 11, which routes back through this same page).

**Dependencies:** Ticket 1 (signup token methods), Ticket 2 (session-exclusivity helper + client session keys), Ticket 11 (this is where the invite link is generated).

**Estimate:** S

---

## Ticket 13 — End-to-end verification pass: isolation, regressions, data parity

**Context:** Closing checklist run once Tickets 2–12 are merged, not new feature work.

**Acceptance criteria:**
- [ ] For one real (or realistic test) customer: `/portal/` score hero and pillar breakdown match that customer's latest `report_snapshots` row exactly, **including the AI Visibility pillar page**, which must match Overview's AI Visibility bar exactly for the same snapshot (regression check for the resolved D3 decision).
- [ ] `/portal/actions` pending list matches the admin `/content-queue` group for that customer; approving/rejecting via the portal is reflected there too.
- [ ] `/portal/reports` lists only that customer's snapshots; opening one matches its `/r/<token>` output byte-for-byte.
- [ ] Session exclusivity: logging into `/portal/login` while an admin session is active clears the admin session (and vice versa) — no browser state ever satisfies both `login_required` and `client_login_required` at once.
- [ ] Sign-up flow end-to-end: staff creates a username (Ticket 11) → invite link → client sets password (Ticket 12) → auto-logged-in → logs out → logs back in with the new credentials → the same original invite link is rejected on reuse.
- [ ] From a client session for customer A: requests to `/` and every `@login_required` admin route redirect to `/login` and render no data; guessing another customer's `snapshot_id` at `/portal/reports/<id>` or `rec_id` at `/portal/actions/<rec_id>` (including the approve/reject POSTs) all return 404.
- [ ] `/r/<token>` and every existing admin route behave exactly as before this work started (spot-check a handful of admin pages + one existing `/r/<token>` link).

**Out of scope:** New feature work — a real bug found here becomes a new ticket unless trivial.

**Dependencies:** Tickets 2 through 12.

**Estimate:** M

---

## Assumptions

Flag any of these you want to veto — build proceeds on these defaults otherwise:

1. **Route param typing:** `rec_id` is untyped (`<rec_id>`) not `<int:rec_id>` in portal routes, matching the existing admin `content_preview` route, since `content_recommendations.id` is `TEXT`. `snapshot_id` **is** `<int:snapshot_id>`, matching `report_snapshots.id` being an integer primary key.
2. **Approve/reject are plain form POSTs** (full page reload back to `/portal/actions`), not JS/fetch calls like the admin's `/api/content/status` — simpler and sufficient for an action taken a few times a month.
3. **No rejected-item list is surfaced to the client** beyond removing it from "Needs your approval" — matches the spec mockup, which only shows pending + published sections.
4. **GEO Foundation `items` dict keys** used for the checklist (Ticket 5) are the first key of each `_FOUNDATION_ITEMS` tuple, as already built by `compute_technical_health()` (`practicerank_score.py:370`) — confirmed by reading the source.
5. **`ENGINES` list** (Claude, ChatGPT, Perplexity, Gemini, Grok) for Ticket 6 is read from `scripts/scheduled_ai_check.py` — worth a quick re-check before starting Ticket 6 in case it's changed since this review.
6. **Dark mode is out of scope** — the portal ships light-only, consistent with the rest of the product.
7. **No rate limiting / lockout on `/portal/login` or `/portal/signup/<token>`** beyond whatever (if anything) `/login` already has — parity with the existing admin login, not a new security control.
8. **Username format is staff's free choice** (could be an email address, could be a plain handle) — no email-format validation is enforced, since the field is no longer necessarily an email now that there's no password-reset email to send to it.
9. **Signup links do not expire on a timer.** Staff's "Reset access" action (Ticket 11) is the sole revocation/renewal mechanism if a link is stale or was sent to the wrong person — no background expiry job.
10. **Successful signup auto-logs the client in** rather than redirecting to `/portal/login` with a "your account is ready" message — chosen for lower friction; easy to flip if preferred.
11. **Minimum password length is 8 characters**, no other complexity rules — matches typical baseline; no existing password-policy precedent found in `dashboard_users` to match against.

## Spec sections that produced no tickets

- **Spec §1, bullet "Zero admin surface"** — enforced structurally across every ticket (separate session keys + exclusivity in Ticket 2, standalone templates in every UI ticket, ownership checks in Tickets 8/9/10) rather than being one discrete unit of work. Verified holistically in Ticket 13.
- **Spec §1, bullet "Reuse, don't recompute"** — same treatment; a constraint applied inside Tickets 4–10, reinforced further by the resolved D3 decision (Ticket 6), not a ticket of its own.
- **Spec's "Precedent: weekly-customer-report.html" reference** (line 204) — documentation/provenance only.
- **The closing spec line** ("End of spec. Next step: `client_users` table + auth...", line 777) — superseded by this ticket breakdown.
