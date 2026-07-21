# Client Portal — Local Test Logins

Dummy credentials seeded by `scripts/seed_demo_data.py` for local dev/testing of the
client portal. **Not real accounts** — synthetic demo data only, generated fresh each
time the script runs. See `specs/platform/client-portal-implementation.md` for the
full feature writeup.

## Setup

Fastest path: ask Claude Code to run the `run-dev-server` skill (`.claude/skills/run-dev-server/`)
— it checks whether `data/demo.db` exists and is actually seeded (not just present as a
file), creates/reseeds it if needed, clears any stale process on port 5199, and starts
the server.

Manual equivalent:
```
python scripts/seed_demo_data.py --db data/demo.db [--reset]
python dashboard/app.py --db data/demo.db --port 5199 --debug
```

`--reset` wipes the demo customer's existing rows first — safe to rerun any time.
Without it, rerunning skips raw-data seeding if the demo customer already exists and
just regenerates fresh report snapshots. `data/demo.db` is gitignored, same as the
real `data/practicerank.db` — never commit it.

## Logins

| | URL | Username | Password |
|---|---|---|---|
| **Client portal** | `http://127.0.0.1:5199/portal/login` | `demo` | `demo-password-123` |
| **Staff admin** | `http://127.0.0.1:5199/login` | `demo-admin` | `demo-admin-password-123` |

Demo customer: `demo-aspen-grove` ("Aspen Grove Dental") — admin customer page at
`/customer/demo-aspen-grove` (note: this specific admin page currently 500s on a
fresh checkout due to a pre-existing, unrelated gap — `geo_agent/secrets.py` is
gitignored and was never committed to this repo; `/` and `/content-queue` work fine).

## What's seeded

Realistic raw data across every table the report pipeline reads — GSC daily metrics,
AI mention runs/results + share-of-voice entities, Google Places, reviews, the GEO
Foundation checklist, content recommendations, competitors — then the actual
`weekly_report.generate_and_store()` pipeline is run against it, so the resulting
snapshot is exactly what a real customer's looks like, not a hand-typed fixture.

Do not commit the resulting `.db` file — `*.db` is gitignored repo-wide (PII
protection) and unnecessary anyway, since this script reproduces an equivalent
environment from a plain checkout.
