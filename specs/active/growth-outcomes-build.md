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

## Phase 2/3 (NEXT): #02 AI Share-of-Voice, #05 Day-1 quick win, #06 churn radar
- BIG FIND: #02 already has real infra — `weekly_report` renders an "AI search visibility"
  block with `s["ai"]["sov"]` (customer_share, competitors[], customer_rank). Need to verify the
  SoV computation source (ai_mention_runs) and productize the 0–100 score + dashboard tile + trend.
- #05 quick_wins.detect_quick_wins exists → standardize Day-1 pass + gate onboarding + first-result.
- #06 churn_risk.py new: combine seo_score_and_delta + review_velocity + engagement + recency.
