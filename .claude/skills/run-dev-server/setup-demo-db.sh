#!/usr/bin/env bash
# Ensures data/demo.db exists and has the seeded demo customer in it, killing
# any stale process already bound to port 5199 first. Run from the repo root.
# See .claude/skills/run-dev-server/SKILL.md.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$REPO_ROOT"

DB_PATH="data/demo.db"
PORT=5199

needs_seed=0
if [ ! -f "$DB_PATH" ]; then
  echo "$DB_PATH doesn't exist yet — will seed."
  needs_seed=1
else
  # The DB file existing isn't enough — it can be present but empty (e.g. a
  # stale scratch DB from a prior session whose tables got wiped). Check the
  # actual demo customer row, not just file presence.
  if ! python3 -c "
import sys
sys.path.insert(0, '.')
from geo_agent.db import CustomerDB
db = CustomerDB(db_path='$DB_PATH')
c = db.get_customer('demo-aspen-grove')
db.close()
sys.exit(0 if c else 1)
" 2>/dev/null; then
    echo "$DB_PATH exists but the demo customer is missing/stale — will reseed."
    needs_seed=1
  else
    echo "$DB_PATH already has the demo customer seeded — skipping reseed."
  fi
fi

if [ "$needs_seed" = "1" ]; then
  python3 scripts/seed_demo_data.py --db "$DB_PATH" --reset
fi

# Clear any stale server already bound to the dev port (a real issue hit
# during manual testing — a server can outlive the session that started it).
stale_pids="$(lsof -nP -iTCP:"$PORT" -sTCP:LISTEN -t 2>/dev/null || true)"
if [ -n "$stale_pids" ]; then
  echo "Killing stale process(es) on port $PORT: $stale_pids"
  kill $stale_pids 2>/dev/null || true
  sleep 1
fi

echo ""
echo "Ready. Next: start the dev server against $DB_PATH on port $PORT (see SKILL.md)."
