#!/usr/bin/env bash
#
# setup-relay-secret.sh — provision the shared RELAY_SECRET used by the audit
# Worker's blocked-site fallback (Worker -> droplet /internal/fetch-relay).
#
# Sets the SAME secret in both places it must match:
#   1) the droplet dashboard env  (/home/kody/dental-marketing/.env)
#   2) the Cloudflare Worker       (wrangler secret RELAY_SECRET)
#
# Idempotent: if the droplet already has a RELAY_SECRET, it is reused so the two
# sides stay in sync instead of drifting. Safe to re-run.
#
# Usage:  ./scripts/setup-relay-secret.sh
#
set -euo pipefail

DROPLET="kody@129.212.138.145"
SSH_KEY="$HOME/.ssh/id_ed25519_do"
ENV_PATH="/home/kody/dental-marketing/.env"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
WORKER_DIR="$REPO_DIR/worker"

echo "==> Checking droplet for an existing RELAY_SECRET..."
EXISTING="$(ssh -i "$SSH_KEY" "$DROPLET" \
  "grep '^RELAY_SECRET=' '$ENV_PATH' 2>/dev/null | head -1 | cut -d= -f2-" || true)"

if [ -n "$EXISTING" ]; then
  SECRET="$EXISTING"
  echo "    Reusing the RELAY_SECRET already in the droplet .env."
else
  SECRET="$(openssl rand -hex 32)"
  echo "==> Generating a new RELAY_SECRET and appending to droplet .env..."
  printf 'RELAY_SECRET=%s\n' "$SECRET" | \
    ssh -i "$SSH_KEY" "$DROPLET" "cat >> '$ENV_PATH'"
fi

echo "==> Verifying droplet .env..."
if ssh -i "$SSH_KEY" "$DROPLET" "grep -q '^RELAY_SECRET=' '$ENV_PATH'"; then
  echo "    droplet .env: RELAY_SECRET present."
else
  echo "    ERROR: RELAY_SECRET did not land in droplet .env" >&2
  exit 1
fi

echo "==> Setting the Cloudflare Worker secret (wrangler)..."
( cd "$WORKER_DIR" && printf '%s' "$SECRET" | npx wrangler secret put RELAY_SECRET )

echo ""
echo "==> Done. RELAY_SECRET is set on the droplet and the Worker."
echo "    Next (once the AI catch-up finishes so the container restart is safe):"
echo "      ./scripts/deploy.sh          # dashboard: picks up RELAY_SECRET from .env"
echo "      ./scripts/deploy-worker.sh   # worker: relay fallback goes live"
