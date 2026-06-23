#!/usr/bin/env python3
"""Fast parallel static-site cloner for an authorized website migration.

Produces a pixel-accurate, self-contained static copy of a site: fetches every
page in parallel, downloads every same-domain asset (css/js/img/fonts) it
references, and rewrites all absolute domain URLs to root-relative so the copy
runs standalone. Output dir is ready to deploy to Cloudflare Pages.

Usage (run where there's network, e.g. the droplet):
    python3 clone_site.py https://example.com /tmp/clonedoc
"""
import os
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlsplit

UA = "Mozilla/5.0 (compatible; PracticeRankMigrator/1.0)"
ASSET_EXT = (".css", ".js", ".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg",
             ".woff", ".woff2", ".ttf", ".eot", ".ico", ".mp4", ".webm", ".avif")


def get(url, binary=False, timeout=30, retries=5):
    for a in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read()
            return data if binary else data.decode("utf-8", "replace")
        except Exception:
            if a == retries - 1:
                raise
            time.sleep(2 * (a + 1))  # back off — the origin rate-limits under load
    return None


def sitemap_urls(base):
    urls = set()
    try:
        subs = re.findall(r"<loc>([^<]+)</loc>", get(base.rstrip("/") + "/sitemap.xml"))
    except Exception:
        subs = []
    for sm in [s for s in subs if s.endswith(".xml")] or [base]:
        try:
            for loc in re.findall(r"<loc>([^<]+)</loc>", get(sm)):
                if not loc.endswith(".xml") and "?" not in loc:
                    urls.add(loc.split("#")[0])
        except Exception:
            pass
    urls.add(base.rstrip("/") + "/")
    return sorted(urls)


def page_path(url, host):
    p = urlsplit(url).path
    if p.endswith("/") or p == "":
        return (p.strip("/") + "/index.html").lstrip("/") or "index.html"
    if not os.path.splitext(p)[1]:
        return p.strip("/") + "/index.html"
    return p.lstrip("/")


def save(docroot, relpath, data, binary=False):
    fp = os.path.join(docroot, relpath)
    os.makedirs(os.path.dirname(fp) or docroot, exist_ok=True)
    with open(fp, "wb") as f:
        f.write(data if binary else data.encode("utf-8"))


def main():
    base = sys.argv[1].rstrip("/")
    docroot = sys.argv[2]
    host = urlsplit(base).netloc
    os.makedirs(docroot, exist_ok=True)

    pages = sitemap_urls(base)
    print(f"Fetching {len(pages)} pages...", file=sys.stderr)
    html_by_path, assets = {}, set()

    def fetch_page(url):
        try:
            html = get(url)
        except Exception as e:
            return url, None, str(e)
        return url, html, None

    with ThreadPoolExecutor(max_workers=5) as ex:
        for i, fut in enumerate(as_completed([ex.submit(fetch_page, u) for u in pages]), 1):
            url, html, err = fut.result()
            if err or not html:
                continue
            rel = page_path(url, host)
            html_by_path[rel] = html
            # collect same-domain assets referenced by this page
            for m in re.findall(r'(?:src|href)=["\']([^"\']+)["\']', html):
                if m.lower().endswith(ASSET_EXT):
                    full = m if m.startswith("http") else (base + m if m.startswith("/") else None)
                    if full and host in full:
                        assets.add(full.split("?")[0].split("#")[0])
            for m in re.findall(r'srcset=["\']([^"\']+)["\']', html):
                for part in m.split(","):
                    u = part.strip().split(" ")[0]
                    if u.lower().split("?")[0].endswith(ASSET_EXT) and host in (u if u.startswith("http") else base):
                        full = u if u.startswith("http") else base + u
                        assets.add(full.split("?")[0])
            if i % 100 == 0:
                print(f"  pages {i}/{len(pages)}", file=sys.stderr)

    print(f"Fetched {len(html_by_path)} pages; downloading {len(assets)} assets...", file=sys.stderr)

    def fetch_asset(url):
        try:
            return url, get(url, binary=True), None
        except Exception as e:
            return url, None, str(e)

    with ThreadPoolExecutor(max_workers=8) as ex:
        for i, fut in enumerate(as_completed([ex.submit(fetch_asset, a) for a in assets]), 1):
            url, data, err = fut.result()
            if err or not data:
                continue
            save(docroot, urlsplit(url).path.lstrip("/"), data, binary=True)

    # also pull CSS-referenced url(...) assets one level deep
    print("Resolving CSS url() assets...", file=sys.stderr)
    css_assets = set()
    for root, _, files in os.walk(docroot):
        for fn in files:
            if fn.endswith(".css"):
                try:
                    txt = open(os.path.join(root, fn), encoding="utf-8", errors="replace").read()
                except Exception:
                    continue
                for u in re.findall(r'url\(["\']?([^"\')]+)["\']?\)', txt):
                    if u.lower().split("?")[0].endswith(ASSET_EXT):
                        full = u if u.startswith("http") else (base + u if u.startswith("/") else None)
                        if full and host in full:
                            css_assets.add(full.split("?")[0])
    with ThreadPoolExecutor(max_workers=8) as ex:
        for fut in as_completed([ex.submit(fetch_asset, a) for a in css_assets]):
            url, data, err = fut.result()
            if not err and data:
                save(docroot, urlsplit(url).path.lstrip("/"), data, binary=True)

    # rewrite absolute domain URLs -> root-relative so the clone is self-contained
    print("Rewriting URLs...", file=sys.stderr)
    pat = re.compile(r'https?:\\?/\\?/' + re.escape(host) + r'|//' + re.escape(host))
    for relpath, html in html_by_path.items():
        html = pat.sub("", html)
        save(docroot, relpath, html)

    print(f"Done. {len(html_by_path)} pages + {len(assets) + len(css_assets)} assets -> {docroot}", file=sys.stderr)


if __name__ == "__main__":
    main()
