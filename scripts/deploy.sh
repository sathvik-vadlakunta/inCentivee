#!/usr/bin/env bash
# Deploy PracticeRank dashboard to the droplet.
#
# Usage:
#   ./scripts/deploy.sh          # rsync + rebuild dashboard
#   ./scripts/deploy.sh --sync   # rsync only (no rebuild)
#   ./scripts/deploy.sh --logs   # show dashboard logs after deploy

set -euo pipefail

DROPLET_USER="kody"
DROPLET_HOST="129.212.138.145"
SSH_KEY="$HOME/.ssh/id_ed25519_do"
REMOTE_DIR="/home/kody/dental-marketing"
LOCAL_DIR="$(cd "$(dirname "$0")/.." && pwd)"

SSH_CMD="ssh -i $SSH_KEY $DROPLET_USER@$DROPLET_HOST"

SYNC_ONLY=false
SHOW_LOGS=false

for arg in "$@"; do
    case $arg in
        --sync) SYNC_ONLY=true ;;
        --logs) SHOW_LOGS=true ;;
    esac
done

echo "==> Syncing $LOCAL_DIR -> $DROPLET_USER@$DROPLET_HOST:$REMOTE_DIR"
rsync -avz --delete \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='.venv' \
    --exclude='node_modules' \
    --exclude='.wrangler' \
    --exclude='data/' \
    --exclude='*.pyc' \
    --exclude='.env' \
    --exclude='.DS_Store' \
    -e "ssh -i $SSH_KEY" \
    "$LOCAL_DIR/" "$DROPLET_USER@$DROPLET_HOST:$REMOTE_DIR/"

echo "==> Files synced"

if [ "$SYNC_ONLY" = true ]; then
    echo "==> Sync only — skipping rebuild"
    exit 0
fi

echo "==> Rebuilding dashboard container"
$SSH_CMD "cd $REMOTE_DIR/dashboard && docker compose up -d --build dashboard"

echo "==> Deploy complete"

if [ "$SHOW_LOGS" = true ]; then
    echo "==> Tailing logs..."
    $SSH_CMD "docker logs practicerank-dashboard --tail 20 -f"
fi
