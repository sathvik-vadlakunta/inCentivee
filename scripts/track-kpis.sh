#!/bin/bash
# Track KPIs for all active customers — call from cron
#
# Cron: 0 6 15 * * /home/practicerank/dental-marketing/scripts/track-kpis.sh

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

echo "[$(date)] Tracking KPIs for all customers"
python scripts/kpi_report.py --all --track 2>&1 | tee -a data/logs/kpi-tracking.log
echo "[$(date)] Done"
