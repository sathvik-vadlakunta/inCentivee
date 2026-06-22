#!/usr/bin/env python3
"""Scored SEO/AEO/UX audit for a customer site — turns the dental-SEO benchmark
checklist (docs/dental-seo-benchmark-and-checklist.md) into an automatic gap list.

Usage:
    python3 scripts/site_audit.py sojo-dental.pages.dev
    python3 scripts/site_audit.py https://paradigmexperts.com --json
    python3 scripts/site_audit.py oak-ridge-dental.pages.dev --pages 8

Fetches the homepage, robots/sitemap/llms, and a sample of service pages, then
scores 7 dimensions and prints what's PASSING vs the prioritized GAPS to fix.
No external dependencies (stdlib only).
"""
import sys, re, json, urllib.request, urllib.parse, gzip, io

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"


def fetch(url, timeout=15):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
            return r.status, raw.decode("utf-8", "ignore"), r.geturl()
    except Exception:
        return None, "", url


def norm_base(target):
    if not target.startswith("http"):
        target = "https://" + target
    return target.rstrip("/")


def jsonld_types(html):
    types = set()
    for m in re.finditer(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.S | re.I):
        block = m.group(1)
        for t in re.findall(r'"@type"\s*:\s*"([^"]+)"', block):
            types.add(t.lower())
        for t in re.findall(r'"@type"\s*:\s*\[([^\]]+)\]', block):
            for x in re.findall(r'"([^"]+)"', t):
                types.add(x.lower())
    return types


def discover_pages(base, limit):
    """Pull URLs from sitemap(s); fall back to homepage links."""
    urls = []
    for sm in ("/sitemap-index.xml", "/sitemap.xml", "/sitemap-0.xml"):
        st, body, _ = fetch(base + sm)
        if st == 200 and "<loc>" in body:
            locs = re.findall(r"<loc>\s*([^<]+?)\s*</loc>", body)
            # if this was an index, fetch child sitemaps
            child = [l for l in locs if l.endswith(".xml")]
            for c in child[:3]:
                _, cb, _ = fetch(c)
                urls += re.findall(r"<loc>\s*([^<]+?)\s*</loc>", cb)
            urls += [l for l in locs if not l.endswith(".xml")]
            if urls:
                break
    return list(dict.fromkeys(urls))


def chk(passed, label, fix):
    return {"pass": bool(passed), "label": label, "fix": fix}


def audit(target, max_pages=6):
    base = norm_base(target)
    st, home, final = fetch(base)
    if st != 200 or not home:
        return {"error": f"could not fetch {base} (status {st})"}

    robots_st, robots, _ = fetch(base + "/robots.txt")
    llms_st, llms, _ = fetch(base + "/llms.txt")
    llmsf_st, _, _ = fetch(base + "/llms-full.txt")
    pages = discover_pages(base, max_pages)
    service_urls = [u for u in pages if "/service" in u][:max_pages]
    blog_urls = [u for u in pages if "/blog" in u]
    location_urls = [u for u in pages if re.search(r"/(location|areas|service-area|cities)/", u)]

    # sample a service page for deep checks
    svc_html = ""
    if service_urls:
        _, svc_html, _ = fetch(service_urls[0])

    home_types = jsonld_types(home)
    svc_types = jsonld_types(svc_html)
    all_types = home_types | svc_types

    dims = {}

    # ── 1. Technical ──
    dims["Technical SEO"] = [
        chk(final.startswith("https"), "HTTPS", "Force HTTPS on the whole site"),
        chk(robots_st == 200 and "sitemap" in robots.lower(), "robots.txt references a sitemap", "Add a robots.txt that points to the sitemap"),
        chk(bool(pages), "XML sitemap with pages", "Generate & submit an XML sitemap covering every service/location page"),
        chk(re.search(r'<meta[^>]+name=["\']viewport["\']', home, re.I), "Mobile viewport tag", "Add a responsive viewport meta tag"),
        chk(re.search(r'\.(webp|avif)', home, re.I), "Next-gen images (WebP/AVIF)", "Serve hero/section images as WebP/AVIF and lazy-load below the fold"),
    ]

    # ── 2. On-page ──
    title = (re.search(r"<title[^>]*>([^<]*)</title>", home, re.I) or [None, ""])[1].strip()
    h1s = re.findall(r"<h1[^>]*>(.*?)</h1>", svc_html or home, re.S | re.I)
    dims["On-page SEO"] = [
        chk(bool(re.search(r'<meta[^>]+name=["\']description["\']', home, re.I)), "Meta description on homepage", "Add a benefit + CTA meta description to every page"),
        chk("|" in title or "-" in title, "Title uses a [Brand | benefit] pattern", "Use titles like '[Service] in [City], [ST] | [Practice]'"),
        chk(len(h1s) == 1, "Exactly one H1 per page", "Ensure a single, descriptive H1 per page"),
        chk(len(service_urls) >= 5, f"Dedicated per-service pages ({len(service_urls)}+ found)", "Split a single 'Services' page into one page per service"),
        chk(_alt_coverage(svc_html or home) >= 0.7, "Most images have alt text", "Add keyword-aware alt text to images"),
        chk(len(re.sub(r"<[^>]+>", " ", svc_html or "")) > 1800, "Service pages have real depth (600+ words)", "Deepen thin service pages to 600–1,000 words (cost/procedure/recovery/financing)"),
    ]

    # ── 3. Schema ──
    dims["Schema / structured data"] = [
        chk(bool(all_types & {"dentist", "localbusiness", "medicalbusiness", "professionalservice"}), "LocalBusiness/Dentist schema", "Add Dentist/LocalBusiness JSON-LD to home + each location"),
        chk("faqpage" in all_types, "FAQPage schema", "Add FAQPage JSON-LD to service pages (biggest untapped win)"),
        chk(bool(all_types & {"medicalprocedure", "dental", "service"}), "Service/MedicalProcedure schema", "Add MedicalProcedure schema to each service page"),
        chk(bool(all_types & {"review", "aggregaterating"}), "Review/AggregateRating schema", "Add Review/AggregateRating so star ratings render in SERPs"),
        chk("breadcrumblist" in all_types, "BreadcrumbList schema", "Add BreadcrumbList matching the service hierarchy"),
        chk("person" in all_types, "Person schema for providers", "Add Person schema linked to each dentist's bio"),
    ]

    # ── 4. Local ──
    has_phone = bool(re.search(r'tel:\+?[\d\-\(\) ]{7,}', home, re.I))
    has_map = bool(re.search(r'google\.com/maps|maps\.google|/embed', home, re.I))
    dims["Local SEO"] = [
        chk(has_phone, "Phone (tel:) present", "Add a click-to-call phone number"),
        chk(bool(re.search(r'\d{1,5}\s+\w+.*(?:st|street|ave|blvd|rd|dr|way|ln|suite|ste)\b', home, re.I)), "Street address on page (NAP)", "Show a complete, consistent NAP"),
        chk(has_map, "Embedded map / directions", "Embed a Google Map + directions link on contact/location pages"),
        chk(len(location_urls) >= 1, f"City/neighborhood landing pages ({len(location_urls)})", "Build city/neighborhood landing pages with unique local content"),
        chk(bool(re.search(r'(\d[\d,]*)\s*(?:\+?\s*)?(?:5[- ]star|reviews?)', home, re.I)), "Review count/rating shown on site", "Surface your Google review count + rating prominently"),
    ]

    # ── 5. Content / E-E-A-T ──
    dims["Content & E-E-A-T"] = [
        chk(len(blog_urls) >= 3, f"Blog with articles ({len(blog_urls)})", "Stand up a clustered blog tied to top revenue services"),
        chk(bool(re.search(r'(frequently asked|faq)', svc_html or home, re.I)), "FAQ content on service pages", "Add a FAQ block to every service page"),
        chk(any("/team" in u or "/about" in u or "/doctor" in u for u in pages) or "person" in all_types, "Provider/author bios", "Add author bios with credentials + Person schema"),
    ]

    # ── 6. AEO / AI-search ──
    dims["AEO / AI-search"] = [
        chk(llms_st == 200 and len(llms) > 200, "llms.txt present", "Publish llms.txt summarizing the practice for AI engines"),
        chk(llmsf_st == 200, "llms-full.txt present", "Publish llms-full.txt with full service/location detail"),
        chk(robots_st != 200 or not _blocks_ai(robots), "robots.txt does NOT block AI crawlers", "Stop blocking GPTBot/ClaudeBot/PerplexityBot/Google-Extended"),
        chk("faqpage" in all_types, "Machine-readable Q&A (FAQ schema)", "Structure FAQ content as FAQPage for AI extraction"),
    ]

    # ── 7. Conversion / UX ──
    booking = bool(re.search(r'nexhealth|modento|flexbook|localmed|zocdoc|book.{0,15}(appointment|online|now)|request.{0,10}appointment', home, re.I))
    dims["Conversion / UX"] = [
        chk(has_phone, "Click-to-call", "Add tel: links + a sticky call bar on mobile"),
        chk(booking, "Online booking / appointment request", "Integrate online booking (NexHealth/Modento) or a prominent request form"),
        chk(bool(re.search(r'(book|schedule|appointment|call|contact)', home[:4000], re.I)), "Primary CTA above the fold", "Repeat a clear primary CTA above the fold"),
        chk(bool(re.search(r'\.(webp|jpg|jpeg|png)', svc_html or home, re.I)), "Real imagery in content", "Use real photos/video in the body, not just the hero"),
    ]

    # score
    out_dims = {}
    total_p = total_m = 0
    for name, checks in dims.items():
        p = sum(1 for c in checks if c["pass"]); m = len(checks)
        total_p += p; total_m += m
        out_dims[name] = {
            "score": round(100 * p / m),
            "passed": [c["label"] for c in checks if c["pass"]],
            "gaps": [{"item": c["label"], "fix": c["fix"]} for c in checks if not c["pass"]],
        }
    return {
        "site": base, "overall_score": round(100 * total_p / total_m),
        "pages_sampled": len(pages), "service_pages": len(service_urls),
        "dimensions": out_dims,
    }


def _alt_coverage(html):
    imgs = re.findall(r"<img\b[^>]*>", html, re.I)
    if not imgs:
        return 1.0
    with_alt = sum(1 for i in imgs if re.search(r'alt=["\'][^"\']+["\']', i, re.I))
    return with_alt / len(imgs)


def _blocks_ai(robots):
    for bot in ("gptbot", "claudebot", "perplexitybot", "google-extended", "oai-searchbot"):
        if re.search(r'user-agent:\s*' + bot + r'\s*\n\s*disallow:\s*/\s*$', robots, re.I | re.M):
            return True
    return False


def render(rep):
    if rep.get("error"):
        return "✗ " + rep["error"]
    L = []
    L.append(f"\n═══ Site Audit — {rep['site']} ═══")
    L.append(f"OVERALL: {rep['overall_score']}/100   ({rep['service_pages']} service pages, {rep['pages_sampled']} pages sampled)\n")
    for name, d in rep["dimensions"].items():
        L.append(f"  {name}: {d['score']}/100")
        for g in d["gaps"]:
            L.append(f"     ✗ {g['item']}  →  {g['fix']}")
    # prioritized gap list
    gaps = [g for d in rep["dimensions"].values() for g in d["gaps"]]
    if gaps:
        L.append(f"\n  ── {len(gaps)} GAPS TO FIX ──")
        for g in gaps:
            L.append(f"   • {g['fix']}")
    else:
        L.append("\n  ✓ No gaps — clean across all dimensions.")
    return "\n".join(L)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print("usage: python3 scripts/site_audit.py <url-or-domain> [--json] [--pages N]")
        sys.exit(1)
    npages = 6
    if "--pages" in sys.argv:
        npages = int(sys.argv[sys.argv.index("--pages") + 1])
    rep = audit(args[0], npages)
    if "--json" in sys.argv:
        print(json.dumps(rep, indent=2))
    else:
        print(render(rep))
