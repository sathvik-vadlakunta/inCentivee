#!/usr/bin/env python3
"""Re-pull EVERY blog post from westgalawyer.com via the WordPress REST API and
rebuild blog-index.json (listing, newest-first) + the /blog/ entries in mirror.json
(full post content). The WP API gives authoritative publish dates, titles,
excerpts, categories and content — far more reliable than scraping HTML.

The site changed permalinks over time (older posts at /blog/<slug>, newer ones at
/<slug>); we normalize ALL posts to /blog/<slug> and emit 301s from any original
non-/blog/ permalink so inbound links/SEO survive the cutover.

Run from sites/parian-lawyers/:  python3 scripts/repull_blog.py
"""
import json, re, html, time, urllib.request, pathlib
import html2text

ROOT = pathlib.Path(__file__).resolve().parent.parent
BASE = "https://westgalawyer.com"
UA = "Mozilla/5.0 (compatible; PracticeRankMigrator/1.0)"

h2t = html2text.HTML2Text()
h2t.body_width = 0          # don't hard-wrap
h2t.ignore_images = False
h2t.ignore_links = False


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    last = None
    for a in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except Exception as e:  # retry transient errors
            last = e
            time.sleep(1.5 * (a + 1))
    raise last


def fetch_all(endpoint, fields):
    out, page = [], 1
    while True:
        arr = get_json(f"{BASE}/wp-json/wp/v2/{endpoint}?per_page=100&page={page}&_fields={fields}")
        if not arr:
            break
        out += arr
        if len(arr) < 100:
            break
        page += 1
    return out


def clean_text(h):
    h = re.sub(r"<[^>]+>", " ", h or "")
    h = html.unescape(h)
    h = re.sub(r"\s+", " ", h).strip()
    h = re.sub(r"\s*Continue Reading\.*\s*$", "", h, flags=re.I).strip()
    return h


def fix_domain(s):
    return re.sub(r"https?://mediatorworks\.wpcomstaging\.com", "https://westgalawyer.com", s or "")


# 1) categories id -> name
cats = {c["id"]: html.unescape(c["name"]) for c in fetch_all("categories", "id,name")}

# 2) every post (with content)
posts = fetch_all("posts", "id,slug,date,link,title,excerpt,content,categories,featured_media")
print(f"fetched {len(posts)} posts")

# category -> stock image key (parian has /images/stock/<key>-1|2.jpg)
CATKEY = {
    "car accident": "car-accident", "truck accidents": "truck-accident",
    "pedestrian accidents": "pedestrian", "slip and fall": "slip-and-fall",
    "nursing home abuse": "nursing-home", "workers compensation": "workers-compensation",
    "wrongful death": "wrongful-death", "dangerous drugs & products": "mass-torts",
    "medical malpractice": "injury", "child accidents": "pedestrian", "dui": "courthouse",
    "personal injury": "injury", "faq": "courthouse", "general": "courthouse", "safety tips": "consult",
}
GENERIC = {"general", "faq", "personal injury", "safety tips"}


def pick_cat(ids):
    names = [cats.get(i, "") for i in ids if cats.get(i)]
    for n in names:                       # prefer a specific category
        if n.lower() not in GENERIC:
            return n
    return names[0] if names else "General"


def stock_for(cat, slug):
    key = CATKEY.get(cat.lower(), "courthouse")
    return f"/images/stock/{key}-{(sum(ord(c) for c in slug) % 2) + 1}.jpg"


index, blog_pages, redirects, seen = [], [], [], {}
for po in posts:
    # Derive the slug from the REAL permalink (po['link']), NOT po['slug'] — the WP
    # slug field is unreliable here (older posts carry a spurious 'blog-' prefix).
    linkpath = re.sub(r"^https?://[^/]+", "", po["link"]).strip("/")   # 'blog/foo' or 'foo'
    seg = linkpath.split("/")[-1]
    if not seg or seg == "blog":          # skip the blog index / root-permalink edge cases
        continue
    path = f"/blog/{seg}"
    if path in seen:                       # rare slug collision → keep both, suffix
        seen[path] += 1
        path = f"/blog/{seg}-{seen[path]}"
    else:
        seen[path] = 1
    title = html.unescape(po["title"]["rendered"]).strip()
    date = po["date"][:10]
    excerpt = clean_text(po["excerpt"]["rendered"])
    cat = pick_cat(po.get("categories", []))
    content_md = fix_domain(h2t.handle(po["content"]["rendered"])).strip()
    index.append({"url": path, "title": title, "date": date,
                  "excerpt": excerpt, "image": stock_for(cat, seg), "cat": cat})
    blog_pages.append({"path": path, "url": BASE + path, "title": title,
                       "description": excerpt[:160], "h1": title, "section": "blog",
                       "content_md": content_md, "words": len(content_md.split())})
    orig = "/" + linkpath
    if orig.rstrip("/") != path:
        redirects.append((orig + "/", path + "/"))

# newest-first
index.sort(key=lambda x: x["date"], reverse=True)

json.dump(index, open(ROOT / "src/data/blog-index.json", "w"), ensure_ascii=False, indent=0)

mirror = json.load(open(ROOT / "src/data/mirror.json"))
mirror["pages"] = [p for p in mirror["pages"] if not p.get("path", "").startswith("/blog/")] + blog_pages
mirror["count"] = len(mirror["pages"])
json.dump(mirror, open(ROOT / "src/data/mirror.json", "w"), ensure_ascii=False)

# redirects fragment for _redirects (original non-/blog/ permalinks -> /blog/<slug>)
frag = ROOT / "scripts" / "_blog_redirects.generated.txt"
with open(frag, "w") as f:
    f.write("# blog permalink redirects (generated by repull_blog.py)\n")
    for o, n in sorted(redirects):
        f.write(f"{o:70} {n}  301\n")

print(f"blog-index: {len(index)} posts | newest {index[0]['date']} | oldest {index[-1]['date']}")
print(f"redirects (original permalink -> /blog/): {len(redirects)} -> {frag}")
