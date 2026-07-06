#!/usr/bin/env bash
#
# sync-worker-anthropic-key.sh — make the Cloudflare audit Worker's
# ANTHROPIC_API_KEY match the droplet's current key.
#
# The droplet .env is the source of truth (rotate-anthropic-key.sh sets it).
# This pushes that same value to the Worker so the free audit's AI step uses a
# valid key. Needed because a key rotation that only touched the droplet leaves
# the Worker on the old (revoked) key -> audits fail with "invalid x-api-key".
#
# The key streams droplet -> wrangler over stdin: it never prints, never hits
# your shell history, and never touches a local file.
#
# Usage:  ./scripts/sync-worker-anthropic-key.sh
#
set -euo pipefail

SSH_KEY="${SSH_KEY:-$HOME/.ssh/id_ed25519_do}"
DROPLET="${DROPLET:-kody@129.212.138.145}"
REMOTE_ENV="${REMOTE_ENV:-/home/kody/dental-marketing/.env}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKER_DIR="$(dirname "$SCRIPT_DIR")/worker"

echo "→ Pulling current ANTHROPIC_API_KEY from droplet and setting the Worker secret…"
ssh -i "$SSH_KEY" "$DROPLET" \
  "grep '^ANTHROPIC_API_KEY=' '$REMOTE_ENV' | head -1 | cut -d= -f2-" \
  | tr -d '\r\n' \
  | ( cd "$WORKER_DIR" && npx wrangler secret put ANTHROPIC_API_KEY )

echo "✓ Worker ANTHROPIC_API_KEY synced (secrets apply to the live Worker immediately — no redeploy needed)."
