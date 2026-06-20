#!/usr/bin/env bash
# Deploy the PracticeRank marketing site (practicerank.ai) to Cloudflare Pages.
#
# Canonical source dir: deploy/   (NOT public/, NOT the root practicerank-*.html — those are legacy/diverged)
# Cloudflare Pages project: practicerank   ->   practicerank.ai
#
# What it does:
#   1. Rebuilds the blog HTML from content/blog/*.md into deploy/blog/  (scripts/build_blog.py)
#   2. Sanity-checks the bundle (index.html, llms.txt, sitemap.xml, robots.txt all present)
#   3. Uploads deploy/ to Cloudflare Pages with Wrangler
#
# Usage:
#   ./scripts/deploy-site.sh              # build blog + deploy to production
#   ./scripts/deploy-site.sh --no-build   # skip the blog rebuild, just deploy deploy/ as-is
#   ./scripts/deploy-site.sh --dry-run    # build + sanity-check only, no upload
#
# Requires: wrangler (npx wrangler) authenticated to the Cloudflare account, python3.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC_DIR="$ROOT/deploy"
PROJECT="practicerank"

# Cloudflare account id (same account as the worker — see worker/wrangler.toml).
# `wrangler pages deploy` needs this explicitly or the API path comes back empty (code 7003).
export CLOUDFLARE_ACCOUNT_ID="${CLOUDFLARE_ACCOUNT_ID:-64057faec3376a9cd325386637e90127}"

DO_BUILD=true
DRY_RUN=false
for arg in "$@"; do
    case $arg in
        --no-build) DO_BUILD=false ;;
        --dry-run)  DRY_RUN=true ;;
    esac
done

if [ "$DO_BUILD" = true ]; then
    echo "==> Building blog HTML from content/blog -> deploy/blog"
    python3 "$ROOT/scripts/build_blog.py"
else
    echo "==> Skipping blog build (--no-build)"
fi

echo "==> Sanity-checking $SRC_DIR"
missing=false
for f in index.html law-firms/index.html medical-practices/index.html llms.txt llms-full.txt robots.txt sitemap.xml _redirects; do
    if [ ! -f "$SRC_DIR/$f" ]; then
        echo "    MISSING: deploy/$f"
        missing=true
    fi
done
if [ "$missing" = true ]; then
    echo "!! Bundle is missing required files — aborting." >&2
    exit 1
fi
# sitemap must be valid XML
python3 -c "import xml.dom.minidom,sys; xml.dom.minidom.parse('$SRC_DIR/sitemap.xml')" \
    && echo "    sitemap.xml: valid XML"
echo "    OK — $(find "$SRC_DIR" -type f | wc -l | tr -d ' ') files staged"

if [ "$DRY_RUN" = true ]; then
    echo "==> Dry run — not uploading. Run without --dry-run to deploy."
    exit 0
fi

echo "==> Deploying deploy/ to Cloudflare Pages project '$PROJECT' (production)"
cd "$ROOT"
# Force the PRODUCTION branch — without --branch, wrangler deploys to a preview
# alias named after the current git branch when you're not on main, which
# silently does NOT update practicerank.ai. (Bit us 2026-06-19.)
npx wrangler pages deploy "$SRC_DIR" --project-name="$PROJECT" --branch main --commit-dirty=true

echo "==> Done. Verify: https://practicerank.ai  (and /legal /medical /blog /llms.txt /sitemap.xml)"
