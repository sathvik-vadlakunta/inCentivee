#!/usr/bin/env python3
"""Download every asset the cloned pages + theme CSS reference but that isn't yet in
public/ — so nothing 404s after the DNS cutover (when westgalawyer.com becomes our
site). Pulls from the live origin (westgalawyer.com) and the old staging host.
Run from sites/parian-lawyers/:  python3 scripts/pull_missing_assets.py
"""
import os, re, time, pathlib, urllib.request, urllib.error

ROOT = pathlib.Path(__file__).resolve().parent.parent
PUB = ROOT / "public"
UA = "Mozilla/5.0 (compatible; PracticeRankMigrator/1.0)"
ORIGINS = ["https://westgalawyer.com", "https://mediatorworks.wpcomstaging.com"]
EXT = r"\.(?:jpg|jpeg|png|webp|gif|svg|ico|css|js|woff2?|ttf|eot|mp4)"

paths = set()

# 1) wp-content/wp-includes refs in cloned HTML (root-relative + staging-absolute)
for html in (ROOT / "clone-pages").rglob("index.html"):
    t = html.read_text(errors="replace")
    for m in re.findall(r'(/wp-(?:content|includes)/[^"\')\s]+?' + EXT + r')', t):
        paths.add(m.split("?")[0])
    for m in re.findall(r'https?://mediatorworks\.wpcomstaging\.com(/[^"\')\s]+?' + EXT + r')', t):
        paths.add(m.split("?")[0])

# 2) url(...) refs inside the theme + plugin CSS already in public/ (e.g. img/bg-lawyer.jpg)
for css in PUB.rglob("*.css"):
    base = "/" + str(css.parent.relative_to(PUB)).replace(os.sep, "/")
    for ref in re.findall(r'url\(\s*[\'"]?([^\'")]+?' + EXT + r')', css.read_text(errors="replace")):
        ref = ref.split("?")[0].split("#")[0]
        if ref.startswith("data:") or ref.startswith("http"):
            continue
        # resolve relative to the CSS file's dir
        p = ref if ref.startswith("/") else os.path.normpath(base + "/" + ref)
        if p.startswith("/wp-") or p.startswith("/"):
            paths.add(p)

missing = sorted(p for p in paths if not (PUB / p.lstrip("/")).exists())
print(f"referenced: {len(paths)} | missing locally: {len(missing)}")

ok = fail = 0
for p in missing:
    dest = PUB / p.lstrip("/")
    got = False
    for origin in ORIGINS:
        try:
            req = urllib.request.Request(origin + p, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                if r.status == 200:
                    data = r.read()
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(data)
                    got = True
                    break
        except Exception:
            continue
    if got:
        ok += 1
    else:
        fail += 1
        if fail <= 25:
            print("  ! could not fetch", p)
    if (ok + fail) % 50 == 0:
        print(f"  …{ok + fail}/{len(missing)}")
    time.sleep(0.05)

print(f"downloaded: {ok} | still missing: {fail}")
