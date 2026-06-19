#!/usr/bin/env bash
# Build → validate AEO files → run tests → deploy a customer Astro site.
#
# Every customer site must ship a correct robots.txt, sitemap, llms.txt, and
# llms-full.txt (the AEO/GEO contract). This script enforces that on every
# deploy so we never ship a site that blocks AI crawlers or has a stale sitemap.
#
# Usage:
#   scripts/deploy-customer-site.sh <site>           # build + validate + deploy
#   scripts/deploy-customer-site.sh <site> --check   # build + validate only (no deploy)
#
# <site> is the directory name under sites/ (== the customer id), e.g. sojo-dental.
set -euo pipefail

SITE="${1:-}"
MODE="${2:-deploy}"
if [ -z "$SITE" ]; then
  echo "usage: scripts/deploy-customer-site.sh <site> [--check]"
  echo "  sites: $(ls -1 "$(cd "$(dirname "$0")/.." && pwd)/sites" | grep -vE '^_' | tr '\n' ' ')"
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SITE_DIR="$ROOT/sites/$SITE"
[ -d "$SITE_DIR" ] || { echo "✗ no site at sites/$SITE"; exit 1; }
cd "$SITE_DIR"

echo "▶ [$SITE] Building…"
if ! npm run build >/tmp/build-"$SITE".log 2>&1; then
  echo "✗ build failed:"; tail -25 /tmp/build-"$SITE".log; exit 1
fi
echo "✓ build ok"

# Run site tests if the package defines a real test script (not the placeholder).
if node -e "const t=(require('./package.json').scripts||{}).test||''; process.exit(t && !/no test specified/.test(t) ? 0 : 1)" 2>/dev/null; then
  echo "▶ [$SITE] Running site tests…"
  npm test || { echo "✗ tests failed"; exit 1; }
  echo "✓ tests ok"
fi

echo "▶ [$SITE] Validating AEO files (robots / sitemap / llms / llms-full)…"
python3 - "$SITE_DIR/dist" <<'PY'
import sys, os, re, glob, xml.etree.ElementTree as ET
dist = sys.argv[1]
fails, warns = [], []

pages = glob.glob(os.path.join(dist, '**', 'index.html'), recursive=True)
npages = len(pages)

# 1) robots.txt — must exist, reference the sitemap, and NOT block AI crawlers.
rp = os.path.join(dist, 'robots.txt')
if not os.path.exists(rp):
    fails.append('robots.txt missing')
else:
    r = open(rp, encoding='utf-8').read()
    if 'Sitemap:' not in r:
        fails.append('robots.txt: no "Sitemap:" directive')
    for bot in ('GPTBot', 'ClaudeBot', 'Google-Extended', 'PerplexityBot',
                'OAI-SearchBot', 'ChatGPT-User', 'Claude-User'):
        if re.search(r'User-agent:\s*' + re.escape(bot) + r'\s*\n\s*Disallow:\s*/\s*$', r, re.I | re.M):
            fails.append(f'robots.txt: {bot} is Disallowed (blocks AI — backwards for GEO)')

# 2) sitemap — index + sitemap-0 present, valid XML, covers the built pages.
locs = 0
if not os.path.exists(os.path.join(dist, 'sitemap-index.xml')):
    fails.append('sitemap-index.xml missing')
s0 = os.path.join(dist, 'sitemap-0.xml')
if not os.path.exists(s0):
    fails.append('sitemap-0.xml missing')
else:
    try:
        locs = sum(1 for e in ET.parse(s0).iter() if e.tag.endswith('loc'))
    except Exception as e:
        fails.append(f'sitemap-0.xml invalid XML: {e}')
    if locs and npages and locs < npages * 0.8:
        fails.append(f'sitemap has {locs} URLs but {npages} pages were built — pages missing from sitemap')

# 3) llms.txt — present, H1 title, blockquote summary.
lp = os.path.join(dist, 'llms.txt')
if not os.path.exists(lp):
    fails.append('llms.txt missing')
else:
    l = open(lp, encoding='utf-8').read()
    if not l.lstrip().startswith('# '):
        fails.append('llms.txt: missing H1 ("# Title")')
    if not re.search(r'^>\s+', l, re.M):
        warns.append('llms.txt: no blockquote summary ("> …")')
    if len(l) < 300:
        warns.append('llms.txt looks thin (<300 chars)')

# 4) llms-full.txt — present.
if not os.path.exists(os.path.join(dist, 'llms-full.txt')):
    warns.append('llms-full.txt missing')

print(f'  pages built: {npages} · sitemap URLs: {locs}')
for w in warns:
    print(f'  ⚠ {w}')
for f in fails:
    print(f'  ✗ {f}')
sys.exit(1 if fails else 0)
PY
echo "✓ AEO files valid"

if [ "$MODE" = "--check" ]; then
  echo "✓ [$SITE] check-only — not deploying"
  exit 0
fi

echo "▶ [$SITE] Deploying to Cloudflare Pages (project: $SITE)…"
npx wrangler pages deploy dist --project-name="$SITE" --branch main --commit-dirty=true
echo "✓ [$SITE] deployed"
