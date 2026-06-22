#!/usr/bin/env python3
"""Fetch a curated, license-clean stock-image library from the Pexels API.

Pexels License: free for commercial use, no attribution required, usable on
client sites. https://www.pexels.com/license/

Usage:
    export PEXELS_API_KEY=xxxxx        # from https://www.pexels.com/api/
    python3 scripts/fetch_stock_images.py            # all verticals
    python3 scripts/fetch_stock_images.py dental     # one vertical

Output: stock-library/<vertical>/<label>.webp  (landscape, ~1600px, webp)
Each label maps to a customer-site service CATEGORY so we can wire one
distinct hero per category — fixing "all the service pages look the same".
"""
import os, sys, json, subprocess, urllib.request, urllib.parse, tempfile, time

API_KEY = os.environ.get("PEXELS_API_KEY", "").strip()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "stock-library")

# label -> Pexels search query. Labels match service categories where relevant.
LIBRARY = {
    "dental": {
        "general-dentistry":     "dentist examining patient teeth",
        "pediatric-dentistry":   "child smiling dentist visit",
        "technology":            "modern dental equipment technology",
        "restorative-dentistry": "dental implant crown model",
        "periodontics":          "dental hygienist cleaning teeth",
        "cosmetic-dentistry":    "woman bright white smile",
        "sedation-dentistry":    "relaxed patient dental chair",
        "holistic-dentistry":    "natural wellness calm spa",
        "orthodontics":          "clear aligners braces teeth",
        "oral-surgery":          "dental surgery operatory clinic",
        "endodontics":           "dental x-ray imaging",
        "hero-office":           "modern dental office interior",
        "hero-team":             "friendly dental team smiling",
        "hero-smile":            "happy patient smiling mirror",
    },
    "legal": {
        "personal-injury":   "car accident injury road",
        "family-law":        "family parents children outdoors",
        "criminal-defense":  "courthouse columns justice",
        "estate-planning":   "signing will estate documents",
        "business-law":      "business meeting contract handshake",
        "consultation":      "lawyer client consultation office",
        "courtroom":         "empty courtroom judge bench",
        "law-office":        "modern law office interior",
        "attorney":          "professional attorney portrait suit",
        "documents":         "legal documents gavel desk",
        "hero-justice":      "scales of justice law",
        "hero-team":         "law firm team professional",
    },
    "medical": {
        "family-medicine":   "doctor patient consultation clinic",
        "pediatrics":        "pediatrician examining child",
        "dermatology":       "dermatologist skin examination",
        "cardiology":        "heart health stethoscope doctor",
        "orthopedics":       "knee joint orthopedic physical therapy",
        "womens-health":     "pregnant woman doctor checkup",
        "med-spa":           "med spa facial treatment aesthetic",
        "telehealth":        "video call doctor laptop telehealth",
        "diagnostics":       "medical laboratory equipment",
        "medical-office":    "modern medical clinic waiting room",
        "hero-doctor":       "smiling doctor white coat portrait",
        "hero-team":         "medical team nurses doctors",
    },
}


def search(query, per_page=5):
    url = "https://api.pexels.com/v1/search?" + urllib.parse.urlencode({
        "query": query, "orientation": "landscape", "size": "large", "per_page": per_page,
    })
    req = urllib.request.Request(url, headers={"Authorization": API_KEY, "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    return data.get("photos", [])


def fetch_webp(src_url, dest):
    with urllib.request.urlopen(urllib.request.Request(src_url, headers={"User-Agent": "Mozilla/5.0"}), timeout=60) as r:
        raw = r.read()
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tf:
        tf.write(raw); tmp = tf.name
    subprocess.run(["cwebp", "-quiet", "-q", "82", "-resize", "1600", "0", tmp, "-o", dest], check=True)
    os.remove(tmp)


def download_variants(vertical, n):
    """Download N distinct variants per label into <vertical>-pool/<label>-<i>.webp
    so different customers can use different photos for the same category."""
    items = LIBRARY.get(vertical)
    if not items:
        print(f"unknown vertical: {vertical}"); return
    d = os.path.join(OUT, f"{vertical}-pool"); os.makedirs(d, exist_ok=True)
    print(f"\n== {vertical} variants pool ({len(items)} labels × {n}) ==")
    for label, query in items.items():
        try:
            photos = search(query, per_page=max(15, n * 4))
            seen, saved = set(), 0
            for p in photos:
                if saved >= n:
                    break
                # skip near-duplicate dominant colors for visual variety
                ac = p.get("avg_color", "")
                if ac in seen:
                    continue
                seen.add(ac)
                dest = os.path.join(d, f"{label}-{saved+1}.webp")
                if os.path.exists(dest):
                    saved += 1; continue
                src = p["src"].get("large2x") or p["src"].get("large")
                fetch_webp(src, dest)
                saved += 1
                time.sleep(0.3)
            print(f"  ✓ {label}: {saved} variants")
        except Exception as e:
            print(f"  ! {label}: {e}")
    print(f"\nDone → {d}")


def main():
    if not API_KEY:
        print("ERROR: set PEXELS_API_KEY (get one free at https://www.pexels.com/api/)")
        sys.exit(1)
    # variants mode:  fetch_stock_images.py variants dental 4
    if sys.argv[1:2] == ["variants"]:
        vert = sys.argv[2] if len(sys.argv) > 2 else "dental"
        n = int(sys.argv[3]) if len(sys.argv) > 3 else 4
        download_variants(vert, n)
        return
    verticals = sys.argv[1:] or list(LIBRARY.keys())
    for vert in verticals:
        items = LIBRARY.get(vert)
        if not items:
            print(f"  (skip unknown vertical: {vert})"); continue
        d = os.path.join(OUT, vert); os.makedirs(d, exist_ok=True)
        print(f"\n== {vert} ({len(items)} images) ==")
        for label, query in items.items():
            dest = os.path.join(d, f"{label}.webp")
            if os.path.exists(dest):
                print(f"  ✓ {label} (exists)"); continue
            try:
                photos = search(query)
                if not photos:
                    print(f"  ! {label}: no results for '{query}'"); continue
                src = photos[0]["src"].get("large2x") or photos[0]["src"].get("large")
                fetch_webp(src, dest)
                kb = os.path.getsize(dest) // 1024
                print(f"  ✓ {label}: {photos[0].get('photographer','?')} ({kb}kb) [pexels#{photos[0]['id']}]")
                time.sleep(0.4)  # be polite to the API
            except Exception as e:
                print(f"  ! {label}: {e}")
    print(f"\nDone → {OUT}")


if __name__ == "__main__":
    main()
