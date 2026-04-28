#!/bin/bash
# Monthly GEO Agent runner — call from cron
#
# Usage:
#   ./scripts/run-monthly.sh --stage              # Stage changes for all active customers
#   ./scripts/run-monthly.sh --publish-approved    # Publish approved, remind pending
#
# Cron setup:
#   0 6 1 * * /home/practicerank/dental-marketing/scripts/run-monthly.sh --stage
#   0 6 8 * * /home/practicerank/dental-marketing/scripts/run-monthly.sh --publish-approved

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# Load env vars
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

mkdir -p "$PROJECT_DIR/data/logs"

case "${1:-}" in
    --stage)
        echo "[$(date)] Running GEO Agent — stage mode for all active customers"
        python -m geo_agent.main --use-db --stage 2>&1 | tee -a data/logs/monthly-run.log
        ;;
    --publish-approved)
        echo "[$(date)] Publishing approved staged content"
        python -m geo_agent.main --use-db --publish 2>&1 | tee -a data/logs/monthly-run.log
        ;;
    *)
        echo "Usage: $0 [--stage|--publish-approved]"
        exit 1
        ;;
esac

echo "[$(date)] Done"
