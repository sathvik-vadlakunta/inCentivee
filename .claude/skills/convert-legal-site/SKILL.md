# Convert Legal Site (state-agnostic law-firm conversion)

## Description
Convert a **law firm's** website into a modern, AEO-optimized site on the PracticeRank
Astro + Cloudflare Pages platform — for **any practice type, in any US state**. This is the
legal-vertical wrapper around `convert-site`: same build machinery, plus the legal schema,
content, directories, review constraints, and the part that makes legal hard — a
**state-agnostic compliance engine** (bar advertising rules vary by state and a mistake can
get the *client* sanctioned). Use when the user says "convert this law firm / attorney site",
"port <firm> to our platform", or runs `/convert-legal-site <url>`.

**Canonical references — read first:**
- `docs/legal-site-conversion-playbook.html` — the legal swaps, the **compliance engine
  (§2)**, the **per-state research process (§3)**, the disclaimer library (§4), review-engine
  constraints (§5), and the phase plan with compliance gates (§6).
- `docs/site-conversion-playbook.md` + `.claude/skills/convert-site/SKILL.md` — the underlying
  build process, gotcha library, and QA checklist (all reused unchanged). **Read §13 "Lessons
  from the Parian Lawyers build"** — the clone-then-clean port playbook this skill assumes
  (Elementor rebuild, build-time enrichment to avoid FOUC, GTM/phone-swap strip, staging-domain
  rewrite, dead-asset strip, WP REST blog pull, cached-301/302, mobile QA sweep).
- First reference build: `specs/customers/parian-lawyers-conversion.html` (Parian Lawyers, PI, GA+AL),
  live at parian-lawyers.pages.dev — the canonical example of every §13 technique.

## User-invocable
`/convert-legal-site <firm-url> [slug]` — convert the law firm at `<firm-url>` into
`sites/<slug>/`. Derive the slug from the firm name if omitted.

## ⚖️ Hard guardrails (legal-specific — never skip)
1. **We are not lawyers.** The output is a compliant-by-default draft + checklist. A
   **licensed attorney in every state the firm practices in or advertises into must sign off
   before cutover.** This is a blocking human gate.
2. **Run the compliance engine before writing content** — jurisdictions → per-state rules →
   compliance matrix (playbook §2–§3). Disclaimers are injected from the matrix.
3. **Re-research the rules every build** — never reuse a cached ruleset (rules change; e.g.
   AL overhauled its ad rules 1/1/2026). Pull from the state bar's official rules page; use
   the **exact mandated disclaimer wording** — don't paraphrase.
4. **Multi-state = strictest rule wins.** A firm is bound by every state it advertises into,
   not just where it's licensed. Add "not licensed in <state>" + referral disclosures as needed.
5. **Banned language:** no "best / expert / specialist / certified" in titles, meta, schema,
   or copy unless actually board-certified.
6. **Schema swap:** `LegalService`+`LocalBusiness` (entity), `Service` (practice areas),
   `Attorney`/`Person` with `memberOf` state bar + `sameAs` Justia/Avvo/bar (entity authority).
   No `Dentist`/`MedicalProcedure` leftovers.
7. **Review engine constrained (playbook §5):** ask past clients only; no incentives/drafting/
   quotas; confidential responses; keep the no-gating private-feedback path.
8. **All inherited dental guardrails still apply** (real data only, `404.astro`,
   `@tailwindcss/typography`, brand colors in `global.css :root`, allow AI crawlers,
   curl-verify live, purge template tokens).

## Process
Run in order; stop at the 🚦 human gates.

1. **`/scrape-site <url>`** → ground-truth: firm + attorneys (with **bar admissions/numbers**),
   practice areas, case results, testimonials, **all office NAPs**, old URL inventory.
   🚦 **GATE:** confirm the practice-area list + business facts (fabrication risk).
2. **Compliance research (playbook §2–§3)** → identify jurisdictions (licensure + advertised
   service area); web-research each state's Rules 7.1–7.5; fill the 12-dimension matrix with
   exact disclaimer wording; produce a per-firm compliance matrix.
3. **`/scaffold-site <slug>`** → fork `_template`; all offices in NAP; attorneys →
   `providers[]` with credentials + admissions; brand in `global.css`.
4. **`/generate-content <slug>`** → practice-area pages (subtypes), bar-verified bios,
   question-first cited blogs ("how much is my case worth in <state>", statute of
   limitations). **Inject the disclaimer matrix into footer + relevant pages; strip banned terms.**
5. **`/seo-aeo <slug>`** → legal schema + entity-authority `sameAs`; llms.txt; robots allow AI;
   redirects; `404.astro`. Use `VERTICAL_DIRECTORIES["legal"]` for citations.
6. **`/local-seo <slug>`** → per-office location pages; GBP primary = the **specific** practice
   category (e.g. "Personal Injury Attorney"), never generic "Lawyer".
7. **`/build-deploy-verify <slug>`** → build, deploy, QA as curl assertions **+ assert every
   required disclaimer renders**.
8. 🚦 **GATE — counsel sign-off:** send the firm's licensed attorney(s) the compliance matrix
   + rendered disclaimers; get written approval before domain cutover.
9. **Handoff** → per-firm results doc + open items (bar numbers, AL/other-state licensure,
   case-result permissions, GA4/GSC IDs, domain cutover). Start retention snapshots.

## Output
A deployed `sites/<slug>/` on Cloudflare Pages with all QA + disclaimer assertions passing, a
per-firm compliance matrix, and a handoff doc — pending licensed-counsel sign-off before cutover.
