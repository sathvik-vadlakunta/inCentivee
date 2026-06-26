# P5 — Tech-debt removal candidates (for review)

Conservative list from the data-integrity work. **Nothing here is blind-deleted** except the
zero-risk items already done. Each has a confidence + risk so you can approve before removal.

## ✅ Removed (zero references, zero risk)
- `DENTAL_RESEARCH_STATS` and `CONTENT_SYSTEM_PROMPT` backward-compat aliases in
  `geo_agent/content_recommender.py` — defined, never referenced anywhere (geo_agent/dashboard/
  scripts/tests). Removed.

## Recommended — low risk, your call
1. **Old SmileShape Webflow OAuth app** (`WEBFLOW_CLIENT_ID/SECRET` → "CJ's Workspace", SmileShape-era).
   It still works but is owned by a workspace we don't control, which is why per-client OAuth connects
   are awkward (empty authorize panel). **Action:** register a PracticeRank-owned Webflow app, swap the
   client id/secret. Needs a Webflow-account action (can't do from code). Until then, the per-site API
   token path (`WEBFLOW_KEY_<client>`) is the working alternative for CMS publishing.
2. **Legacy `customers.json` importer** (`db.import_customers_from_json`, `geo_agent/db.py:~3377`) —
   one-time migration from the pre-DB era. Verify no startup/CLI path still calls it, then remove.

## Keep — NOT debt (flagged but legitimate)
- **Two GSC tables** (`gsc_daily_metrics` = daily totals for the Overview/charts; `gsc_query_daily` =
  per-query for keywords). They are **complementary, not duplicate**. The real bug was that nothing
  populated both — now fixed: `geo_agent/refresh.py` is the single population path, and the Overview
  falls back to the cache. No removal needed.
- **`_legacy_steps` onboarding migration** (`db.py:~660`) — idempotent guard; harmless to keep, low value
  to remove. Remove only after confirming every customer has migrated off the legacy onboarding steps.
- **`proof.py` legacy 1.0 methodology branch** — intentionally kept for the long-arc "since we started"
  comparison. Keep.

## Needs a careful pass (don't rush)
- **Dead detection branches** in `_auto_detect_seo_status` / the Local-Listings scanner for verticals or
  platforms no longer used. These touch live checklist data — audit each branch against current verticals
  before removing, ideally behind the P3 integration tests.

## Recommendation
Do (1) when you can spin up the PracticeRank Webflow app; (2) is a quick verify-then-delete. Leave the
"keep" items. Tackle the dead-branch pass last, test-first.
