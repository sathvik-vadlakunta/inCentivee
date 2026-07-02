# Growth & Outcomes — build (from specs/platform/growth-outcomes-review-engine-spec.html)

Building the 6 initiatives. Phase 1 = #01, #03, #04.

## #01 Outcome-led reporting — ✅ DONE (tested)
- `customers.avg_case_value` (INT $) + `close_rate` (REAL, def 0.35) columns.
- `geo_agent/outcomes.py`: `patient_outcomes()` (inquiries=calls+forms+bookings organic → est patients → est production) + `inquiries_in_window()`.
- `weekly_report`: outcomes section + hero band + exec-summary now leads with "N new patient inquiries (~$X production)".
- Dashboard: editable "Avg case value" card + `/customer/<id>/case-value` route; index shows "New patients (30d)" column.
- Tests: `tests/unit/test_outcomes.py`.

## #04 Review velocity + white-label engine — ✅ TRACKING LAYER DONE (tested)
- Recommendation (spec): white-label Grade.us; we build the tracking layer.
- `customers.review_target_pm` (INT, def 4) column.
- `db.review_velocity()`: trailing-30d vs prior-30d review counts + target + on_track.
- `action_items`: "Reviews behind pace" warning (guarded on total>0 so un-synced clients don't flag).
- `weekly_report`: "Reviews / month" KPI + below-target note in reviews section.
- Dashboard: editable "Review target /mo" card; setter route extended.
- Tests: `tests/unit/test_review_velocity.py`.
- REMAINING (external / ops, not code): Grade.us white-label account setup, contact intake (CSV/Zapier), review-sync so velocity has data. Onboarding "Connect review requests" step.

## #03 Money-query weighting — ✅ DONE (tested)
- content_recommender prompt already prioritizes transactional/commercial.
- `content_recommendations.intent_tier` column + persisted in add_content_recommendation.
- `ContentRecommendation.intent_tier` field; grading tags via `classify_intent(title+category)` and
  downgrades informational (non-FAQ) so buyer-intent sorts first.
- Report: intent-mix bar in "What we did this week" (buyer% vs research, from published recs).
- Content queue: Buyer/Compare/Research chip per rec.

## #02 AI Share-of-Voice — ✅ DONE (tested)
- `db._sov_from_run_ids()` refactor + `db.get_share_of_voice_history()` (per-run trend).
- `geo_agent/share_of_voice.py`: `sov_summary()` (score 0–100 = pooled share, rank, delta vs
  baseline, per-run history, top competitors) + `sov_score()`.
- Report: flagship SoV score band (purple) leading the AI section, with delta + rank sub-line.
- Dashboard: "AI share" column (score% + #rank).
- Tests appended to `tests/unit/test_share_of_voice.py`.

## #06 Churn-risk radar — ✅ DONE (tested)
- `geo_agent/churn_risk.py`: additive 0–100 risk from payment health, results trend
  (seo delta), SoV delta, review velocity, no-inquiries-30d, report recency, pending access.
  Returns {score, level, reasons, top_reason}; inert for non-active.
- Dashboard: "Renewal risk" column (chip + top reason), "At Renewal Risk" stat, `?sort=risk` toggle.
- Tests: `tests/unit/test_churn_risk.py`.

## #05 Day-1 quick win — ✅ DONE (tested)
- `customers.quick_win_shipped_at` column; `quick_wins.first_quick_win()` (auto-actionable top pick).
- action_items onboarding gate ("Ship the Day-1 quick win") clears when shipped.
- `/customer/<id>/quick-win-shipped` route locks baseline_score for the first-report "first result".
- Customer page: Day-1 quick-win banner (recommend + mark-shipped) → shipped confirmation.
- Tests: `tests/unit/test_quick_win_pass.py`.

## STATUS: all 6 built + tested (878 unit tests green). Remaining = ops/external:
- #04: stand up Grade.us white-label + contact intake + review-sync (so velocity/churn have data).
- #02: cost-manage the query panels (weekly runs, ~10 queries) when live.
- Nice-to-haves: churn → daily digest feed; SoV sparkline in report; first-report "first result" callout.
