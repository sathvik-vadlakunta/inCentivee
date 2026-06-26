# Content Pipeline Guardrails — close the docx fact-check bypass + harden generation

**Status:** active
**Started:** 2026-06-26
**Trigger:** Review of `Downtown Dental-all-content (6).docx` surfaced six classes of issue
that shipped to a live YMYL client. Root-cause analysis traced every one to the content
generator + the fact that the **DOCX deliverable bypasses all validation**.

## Root cause

`geo_agent/fact_check.py` (the YMYL backstop that flags unsupported credentials, uncited
stats, fabricated quotes) is wired **only** into the auto-publish endpoint
(`dashboard/app.py` `/api/content/<id>/publish`, ~line 6793). The three DOCX export
endpoints (`/api/content/download-docx`, `/download-all-approved`, `/download-all`) render
stored recommendations straight to Word with **zero** validation. Manual clients (review +
publish from the docx, e.g. Downtown Dental) therefore never hit the gate.

Three data/spec defects fed bad input even before any gate:
- The `description` field is an **internal rationale** by spec (prompt: "What to change and
  why") but the docx labels it **"Meta Description:"** → briefs shipped as meta tags.
- `RESEARCH_STATS["practice"]` row for dental anxiety was **internally contradictory**: stat
  text said "2021 Adult Oral Health Survey", source field said "British Dental Journal, 2024".
- The "≥4 statistics per blog" rule + no cross-rec dedup → the same stat repeated 14×.

## Fixes (all six)

1. **Close the bypass.** New deterministic validator `geo_agent/content_validation.py`
   (`validate_html_claims(html, customer)`) — no LLM, fast, testable. Runs at BOTH
   generation time (`_grade_recommendations`) and docx render time (so existing stored recs
   are checked too). The docx renders an unmissable **"⚠ NEEDS REVIEW BEFORE PUBLISHING"**
   block listing findings. Endpoints additionally run the existing LLM `fact_check_html`
   best-effort and fold its findings in.
2. **Real `meta_description` field** added to the rec schema (required), dataclass, prompt,
   and DB round-trip. Docx renders `meta_description` (≤155 char patient-facing copy) — never
   the internal `description`. Falls back to no meta line when empty (old recs).
3. **Future-date guard** (in the validator): any visible date or `<time datetime>` after today
   is flagged; obvious "Last updated: <future>" strings are rewritten to the current month.
4. **Stat-row fix**: replace the contradictory anxiety row with the verifiable
   *Journal of Dentistry, 2021 systematic review & meta-analysis* figure (15.3% dental fear;
   12.4% high, 3.3% severe — Silveira et al.). Add a CI test asserting no stat row's text names
   a publication/year that conflicts with its `source`.
5. **Batch stat-dedup**: `_grade_recommendations` counts stat usage (by citation URL) across
   the batch and flags any stat used more than `STAT_REUSE_CAP` (3) times. Prompt softened:
   "2–3 distinct stats per blog; do not reuse the same stat across pieces."
6. **Superlative + credential grounding** (in the validator): flags marketing superlatives
   (best/#1/premier/world-class/top-rated) and dangerous YMYL absolutes
   (painless/pain-free/guaranteed → also auto-softened); flags any credential claim
   (board-certified/diplomate/specialist/fellow/DDS/DMD/MD) **not present verbatim in the
   provider credentials list**. This is the deterministic backstop that would have caught the
   "Board Certified Prosthodontist" claim (profile lists only "Fellow, ACP" + Prosthodontics).

Defense in depth: prompt rules (prevent) → deterministic validator (catch, no API) →
LLM fact-check (catch semantic) at publish AND docx.

## Tests (`tests/unit/test_content_validation.py`, `test_stat_library.py`)
- credential grounding flags unlisted "board certified"; passes when listed.
- superlative + YMYL-absolute detection + auto-soften.
- future-date detection + "Last updated" rewrite.
- batch stat-dedup over cap.
- stat-library internal consistency (source ⇄ stat text).
- docx renders a Needs-Review block when findings are passed; renders meta_description not description.

## Results (2026-06-26, deployed)

- All 6 fixes shipped; 792 tests green (760 existing + 32 new). Deployed to droplet; DB
  migrated to v3 (`meta_description` column live on `practicerank.db`).
- **Validator on the EXISTING Downtown batch (before regen):** 20 of 26 recs flagged —
  9 credential ("Board Certified" not in `DDS, FACP`), 8 future-date, 13 superlative,
  1 YMYL-absolute. Proves the fix catches the real production defects.
- **Regenerated** a fresh batch via the hardened pipeline: 10 recs, **10/10 with a real
  meta_description, 0 flagged**. Sample blog meta = 153 chars, credits "Dr. Paul Zhivago,
  DDS, FACP" (the real credential) with zero "board certified" mentions.
- **Superseded** the bad content: rejected the 14 old recs with BLOCK findings; kept 12 clean
  old + 10 new. Publishable set is now 22 recs with **0 blocking findings**. Nothing was ever
  published live, so no on-site cleanup was needed.

## Follow-up
- Other clients (Sojo, Oak Ridge, Hilltop, Parian) ran through the same buggy generator —
  re-validate/regenerate as needed (same `validate_html_claims` audit).
- Audit report has the SAME unverified-claim disease (Ethan: false "absent from CFP Board
  directory" negative) — apply the ground-or-soften principle to the audit/report generator.
