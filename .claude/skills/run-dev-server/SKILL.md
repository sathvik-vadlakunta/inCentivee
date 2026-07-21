---
name: run-dev-server
description: >-
  Start the PracticeRank Flask dashboard locally against a synthetic demo
  customer, seeding it first if needed. Use when asked to run/start the dev
  server, test the client portal locally, or spin up a local dashboard
  instance. Never points at data/practicerank.db (the real production DB) —
  always the gitignored data/demo.db scratch database.
---

# Run Dev Server

Starts `dashboard/app.py` locally, pointed at a synthetic demo customer's
database — never at real customer data. Uses `scripts/seed_demo_data.py`
(see `specs/platform/client-portal-implementation.md` for what it seeds and
why: a real pipeline run against fake raw inputs, not a hand-typed fixture).

## Steps

1. **Ensure the demo DB exists and is actually seeded** (not just present as
   a file — a DB can exist but have empty tables, e.g. from a stale prior
   session):
   ```bash
   bash .claude/skills/run-dev-server/setup-demo-db.sh
   ```
   This creates/reseeds `data/demo.db` only if needed, and kills any stale
   process already bound to port 5199.

2. **Start the server in the background** (must use `run_in_background` —
   this is a long-running process):
   ```bash
   python3 dashboard/app.py --db data/demo.db --port 5199 --debug
   ```

3. **Smoke-test it's actually up**:
   ```bash
   sleep 2 && curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:5199/portal/login
   ```
   Expect `200`. If not, check the background task's output file for a
   traceback before reporting success.

4. **Report the login credentials** from `test-login.md` (read it — don't
   hardcode credentials here, they can drift). Give the user both URLs and
   both username/password pairs (client portal + staff admin).

## Notes

- `data/demo.db` is gitignored (matches the repo-wide `*.db` / `data/` PII
  rule) — never commit it, and never point this at `data/practicerank.db`
  (the real production DB) by mistake.
- Rerun `scripts/seed_demo_data.py --db data/demo.db --reset` any time to get
  a clean, fresh demo customer — safe and idempotent.
- The admin `/customer/demo-aspen-grove` detail page will 500 on a fresh
  checkout due to a pre-existing, unrelated gap (`geo_agent/secrets.py` is
  gitignored and was never committed) — `/` and `/content-queue` work fine.
  This is documented in `test-login.md`, not something this skill can fix.
