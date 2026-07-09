# Weekly report: score consistency + dated chart + Zhivago FAQ finding

Raised 2026-07-09 from a Downtown Dental report where the headline said "PracticeRank
Score climbed to 42 (+6)" but the trend graph + progress table showed 36.

## (a) Score self-inconsistency — FIXED
Root cause: the report drew "current score" from two places:
- Headline + score circle: `compute_practicerank_score()` recomputed **live** at run time (42).
- Trend graph + "progress since" row: the **persisted** `practicerank_scores` history, whose
  latest saved point was 36 — because the fresh score is persisted only *after* the report
  data (incl. the chart series) is built. So the chart lagged one save behind the headline.

Fix: `build_report_data` now passes the live score as `live_point` into
`_progress_since_start`, which appends it as the current point of the score series (for live
renders only; skipped when `live_state=False` so historical rebuilds aren't rewritten). Now the
headline, circle, chart endpoint, and table "current" all show the same number.

## (b) Dated points on the trend chart — DONE
`_trend_chart_svg` now labels the **start date** (left), the **report-run date** (right, "· run"),
annotates the **peak** with a marker + its date/value, and prints the end value at the endpoint.

## (c) Dr. Zhivago Qualifications FAQ — our content is CORRECT; dev flattened it
The generated rec (`downtown-dental-20260604-08`) is already **5 separate `<details>/<summary>`
Q&A items** with full FAQPage schema (mainEntity → Question → acceptedAnswer). The live page shows
one block of paragraphs → the customer's dev collapsed our accordion on publish, dropping the
per-question `<summary>` + schema. Downtown Dental self-publishes (we provide content, they apply
it), so the fix is a dev handoff: `docs/downtown-dental-zhivago-faq-handoff.html` (publish as-is).

## Verify
Regenerate a live report for `downtown-dental` after deploy; headline score == chart endpoint ==
progress-row "current".
