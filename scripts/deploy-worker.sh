#!/usr/bin/env bash
# Deploy the PracticeRank audit API (Cloudflare Worker: practicerank-api).
#
# This is the worker that powers the free audit on practicerank.ai — it scrapes
# the site, calls Google Places + Claude, builds the report, stores leads in KV,
# and emails the report via Resend. Config: worker/wrangler.toml.
#
# Usage:
#   ./scripts/deploy-worker.sh           # deploy the worker
#   ./scripts/deploy-worker.sh --dry-run # build/validate only (wrangler deploy --dry-run)
#
# Requires: wrangler authenticated to the Cloudflare account.
# Secrets (ANTHROPIC_API_KEY, GOOGLE_PLACES_API_KEY, RESEND_API_KEY, etc.) are set once via:
#   cd worker && npx wrangler secret put <NAME>

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DRY_RUN=false
for arg in "$@"; do
    case $arg in --dry-run) DRY_RUN=true ;; esac
done

cd "$ROOT/worker"

echo "==> Running worker tests"
if [ -f package.json ] && npm run | grep -q '  test'; then
    npm test
else
    echo "    (no npm test script — skipping)"
fi

if [ "$DRY_RUN" = true ]; then
    echo "==> Dry run (no upload)"
    npx wrangler deploy --dry-run
    exit 0
fi

echo "==> Deploying worker 'practicerank-api'"
npx wrangler deploy

echo "==> Done. Audit endpoint: https://practicerank-api.practice-rank-ai-seo.workers.dev/audit"
