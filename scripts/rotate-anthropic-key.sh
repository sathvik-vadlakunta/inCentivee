#!/usr/bin/env bash
#
# Rotate the PracticeRank Anthropic API key on the droplet.
#
#   ./scripts/rotate-anthropic-key.sh
#
# Prompts for the new key with hidden input, backs up the current .env, swaps
# ANTHROPIC_API_KEY in the droplet's root .env (which dashboard/docker-compose.yml
# reads via `env_file: ../.env`), restarts the dashboard container from the right
# directory, and verifies. The key is streamed over the SSH stdin channel — it
# never lands in your shell history, process args, or any local file.
#
# NOTE: never paste a key into a chat/ticket first. If you have, revoke it in the
# Anthropic console and rotate a FRESH one with this script.
set -euo pipefail

SSH_KEY="${SSH_KEY:-$HOME/.ssh/id_ed25519_do}"
DROPLET="${DROPLET:-kody@129.212.138.145}"
REMOTE_DIR="${REMOTE_DIR:-/home/kody/dental-marketing}"

read -r -s -p "Paste the NEW Anthropic key (hidden): " NEW_KEY
echo
if [[ "$NEW_KEY" != sk-ant-* ]]; then
  echo "✗ That doesn't look like an Anthropic key (expected sk-ant-…). Aborting." >&2
  exit 1
fi

echo "→ Rotating ANTHROPIC_API_KEY + restarting dashboard on $DROPLET …"

# Heredoc is UNquoted so $NEW_KEY interpolates locally into the script body that
# is piped over ssh stdin; \$… / \$(…) are escaped so they run remotely.
ssh -i "$SSH_KEY" "$DROPLET" "REMOTE_DIR='$REMOTE_DIR' bash -s" <<EOF
set -e
cd "\$REMOTE_DIR"
cp .env ".env.bak.\$(date +%Y%m%d-%H%M%S)"
if grep -q '^ANTHROPIC_API_KEY=' .env; then
  sed -i "s|^ANTHROPIC_API_KEY=.*|ANTHROPIC_API_KEY=$NEW_KEY|" .env
else
  echo "ANTHROPIC_API_KEY=$NEW_KEY" >> .env
fi
cd dashboard && docker compose up -d dashboard >/dev/null
sleep 3
printf 'live key prefix : '
docker exec practicerank-dashboard sh -lc 'printf %s "\$ANTHROPIC_API_KEY" | cut -c1-20'
printf 'login check     : '
curl -s -o /dev/null -w '%{http_code}\n' localhost:5099/login
EOF

# Also update the Cloudflare audit Worker — it reads ANTHROPIC_API_KEY as its
# own wrangler secret, NOT from the droplet .env. Skipping this leaves the free
# audit's AI step on the revoked key ("invalid x-api-key"). Streamed over stdin,
# so the key never lands in shell history or a file.
if command -v npx >/dev/null 2>&1; then
  echo "→ Updating Cloudflare Worker ANTHROPIC_API_KEY secret …"
  printf '%s' "$NEW_KEY" | ( cd "$(dirname "$0")/../worker" && npx wrangler secret put ANTHROPIC_API_KEY )
  echo "✓ Worker secret updated."
else
  echo "⚠ npx not found — run ./scripts/sync-worker-anthropic-key.sh separately to update the Worker." >&2
fi

unset NEW_KEY
echo "✓ Done. New Claude calls now isolate to this key — the Cost console will show PracticeRank-only spend."
