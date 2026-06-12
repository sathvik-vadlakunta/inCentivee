# Incident + Fix: `admin.practicerank.ai` "database is locked" outage (2026-06-12)

## Symptom
Dashboard homepage (`/`) returned HTTP 500. Logs showed:

```
File "/app/geo_agent/db.py", line 626, in _init_schema
    self.conn.execute("UPDATE customers SET onboarding_step = 'outreach' ...")
sqlite3.OperationalError: database is locked
```

The `-wal` file was frozen at ~4 MB (the autocheckpoint high-water mark) and a
concurrent writer (an SEO/AI audit) held the write lock momentarily.

## Root cause
Two independent issues in `geo_agent/db.py` `CustomerDB`:

1. **No `busy_timeout`.** The connection set `journal_mode=WAL` but not
   `busy_timeout`, so any connection that hit the write lock failed *instantly*
   instead of waiting. SQLite's default is fail-fast.
2. **A write on every page load.** `_init_schema()` runs on every `CustomerDB()`
   instantiation (i.e. every request), and it executed three unconditional
   `UPDATE customers SET onboarding_step = ...` data-migrations. So the
   read-only homepage took a write lock it didn't need — and died when a
   background audit held it.

Note on what was NOT the cause: an Explore audit of `main.py`, `dashboard/app.py`
and the audit modules confirmed every write method commits promptly and
atomically, and the long-lived background AI-audit connection commits between
network calls (no transaction held across network I/O). The write path was sound.

## Fix (deployed 2026-06-12)
`geo_agent/db.py`:
- `sqlite3.connect(..., timeout=15)` + `PRAGMA busy_timeout=15000` — callers now
  wait up to 15s for the lock instead of 500ing.
- Guarded the three migration `UPDATE`s behind a `SELECT ... LIMIT 1` existence
  check, so the steady state (every page load re-runs `_init_schema`) stays
  **read-only** and never contends for the write lock.
- Added `CustomerDB.checkpoint()` — best-effort `PRAGMA wal_checkpoint(TRUNCATE)`,
  no-op if the lock is held.

`dashboard/app.py` (`_run_ai_check_background`) and `geo_agent/main.py`
(end of pipeline run): call `db.checkpoint()` before `db.close()` so the `-wal`
file is trimmed back to zero after heavy write bursts.

## Verification
- 638 non-docker tests pass.
- After deploy: `/login` 200, `/` 200, `-wal` checkpointed to empty.

## Should we move to Postgres?
Decided **no** for now. Concurrency is tiny (single gunicorn worker, handful of
customers) and the GEO agent is deeply tied to SQLite (`sqlite-vec` + FTS5, one
`.db` per customer for hybrid RAG). Revisit only if we go multi-process /
multi-container writers, or customer count grows into the hundreds with
overlapping pipeline runs — target would be Postgres + pgvector.
