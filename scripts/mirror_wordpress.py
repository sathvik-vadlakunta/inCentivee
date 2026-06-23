#!/usr/bin/env python3
"""Mirror a WordPress/Elementor site 1:1 for conversion to our Astro platform.

Crawls every URL in the site's sitemaps, extracts each page's real main content
(title, meta description, body as Markdown) with trafilatura, and writes a single
manifest JSON keyed by the page's URL path. A downstream Astro catch-all route
renders each entry at its ORIGINAL path, so the new site has every page at the
same URL (1:1 parity) with our schema/disclaimers/brand layered on.

Usage (run where there's outbound network, e.g. the droplet):
    pip install trafilatura requests
    python3 mirror_wordpress.py https://example.com out/mirror.json [--limit N] [--only substr]
"""
import json
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

import trafilatura

UA = "Mozilla/5.0 (compatible; PracticeRankMigrator/1.0)"


def fetch(url, timeout=25, retries=3):
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001 — retry transient 500s/timeouts
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise last


def all_sitemap_urls(base):
    """Collect page + post URLs from the WP sitemap index."""
    urls = set()
    try:
        idx = fetch(base.rstrip("/") + "/sitemap.xml")
        subs = re.findall(r"<loc>([^<]+)</loc>", idx)
    except Exception:
        subs = []
    # prefer page/post sitemaps; fall back to any *-sitemap.xml
    targets = [s for s in subs if re.search(r"(page|post|product)-sitemap", s)] or subs
    for sm in targets:
        try:
            xml = fetch(sm)
            for loc in re.findall(r"<loc>([^<]+)</loc>", xml):
                if loc.endswith(".xml"):
                    continue
                urls.add(loc.split("#")[0].split("?")[0])
        except Exception as e:
            print(f"  ! sitemap {sm}: {e}", file=sys.stderr)
    return sorted(urls)


def path_of(url, base):
    p = url[len(base.rstrip("/")):] if url.startswith(base.rstrip("/")) else url
    p = "/" + p.strip("/")
    return "/" if p == "/" else p


def section_of(path):
    seg = path.strip("/").split("/")[0] if path != "/" else "home"
    if re.search(r"-injury$", seg): return "location"
    if "mass-torts" in seg or "mass-torts" in path: return "mass-torts"
    if re.search(r"-lawyer$|-attorney", seg): return "practice"
    if seg.startswith("about"): return "about"
    if any(k in path for k in ("/20", "blog")): return "blog"
    return "page"


def extract(url, base):
    try:
        html = fetch(url)
    except Exception as e:
        return {"url": url, "error": str(e)}
    title = (re.search(r"<title>([^<]+)</title>", html) or [None, ""])[1].strip()
    desc = (re.search(r'<meta name="description" content="([^"]*)"', html) or [None, ""])[1].strip()
    h1 = re.sub(r"<[^>]+>", "", (re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S) or [None, ""])[1]).strip()
    md = trafilatura.extract(html, output_format="markdown", include_comments=False,
                             include_tables=True, favor_recall=True) or ""
    path = path_of(url, base)
    return {
        "path": path, "url": url, "title": title, "description": desc,
        "h1": h1, "section": section_of(path), "content_md": md.strip(),
        "words": len(md.split()),
    }


def main():
    base = sys.argv[1]
    out = sys.argv[2]
    limit = None
    only = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
    if "--only" in sys.argv:
        only = sys.argv[sys.argv.index("--only") + 1]

    urls = all_sitemap_urls(base)
    if only:
        urls = [u for u in urls if only in u]
    if limit:
        urls = urls[:limit]
    print(f"Mirroring {len(urls)} URLs from {base}", file=sys.stderr)

    pages, errors = [], []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(extract, u, base): u for u in urls}
        for i, f in enumerate(as_completed(futs), 1):
            r = f.result()
            if r.get("error") or not r.get("content_md"):
                errors.append(r.get("url"))
            else:
                pages.append(r)
            if i % 25 == 0:
                print(f"  {i}/{len(urls)} ({len(errors)} empty/err)", file=sys.stderr)

    pages.sort(key=lambda p: p["path"])
    import os
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    json.dump({"base": base, "count": len(pages), "errors": errors, "pages": pages},
              open(out, "w"), ensure_ascii=False)
    print(f"Wrote {len(pages)} pages ({len(errors)} empty/errors) -> {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
