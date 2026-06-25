#!/usr/bin/env python3
"""Fetch a UNIQUE, service-relevant Pexels photo for every service on a site, so no
two service pages share an image. Saves public/images/stock/svc-<slug>.webp.

Usage: PEXELS_API_KEY=... python3 scripts/fetch_service_images.py <site-slug> [site-index]
  site-index (0/1/…) offsets the pick so different sites get different photos for the
  same query (anti-cookie-cutter). Services with a hand-set frontmatter `image:` are skipped.
"""
import os, re, sys, glob, json, time, subprocess, tempfile, urllib.request, urllib.parse

API_KEY = os.environ.get("PEXELS_API_KEY", "").strip()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = "Mozilla/5.0 (compatible; PracticeRankImager/1.0)"

# Exact slug -> hand-tuned query (for services whose name returns off-topic stock).
SLUG_OVERRIDE = {
    "retainers": "clear orthodontic retainer teeth",
    "pulpotomy": "child at dentist pediatric chair",
    "night-guards": "dental night guard occlusal splint",
    "sports-mouth-guards": "sports mouthguard athlete",
    "dental-sealants": "dentist examining patient teeth",
    "cone-beam-cbct-imaging": "dental panoramic x-ray machine",
    "botox": "botox cosmetic injection face",
    "pediatric-tooth-extractions": "child patient dentist chair",
    "amalgam-removal": "dentist drilling tooth treatment",
    "mercury-free-dentistry": "dentist composite tooth filling",
    "tooth-extractions": "dental tooth extraction forceps",
    "baby-tooth-crowns": "child teeth dentist pediatric",
    "braces": "orthodontic metal braces teeth",
}

# title/slug keyword -> a better Pexels query than the raw title
REFINE = [
    (r"whitening", "teeth whitening dentist"),
    (r"x-ray|xray|radiograph", "dental x-ray radiograph"),
    (r"root canal", "endodontist root canal"),
    (r"wisdom", "wisdom tooth extraction dental surgery"),
    (r"implant", "dental implant"),
    (r"denture", "dentures dental"),
    (r"crown", "dental crown"),
    (r"bridge", "dental bridge"),
    (r"veneer", "dental veneers smile"),
    (r"filling", "dental filling treatment"),
    (r"cleaning|hygiene|exam", "dental cleaning hygienist"),
    (r"sedation|anesthesia", "dental sedation patient relaxed"),
    (r"aligner|invisalign|ortho|braces", "clear aligners orthodontics"),
    (r"pediatric|child|kid", "child at dentist pediatric"),
    (r"gum|periodont|scaling", "gum periodontal dental treatment"),
    (r"extraction|removal|oral surg", "oral surgery dental"),
    (r"emergency", "emergency dentist patient"),
    (r"bonding", "cosmetic dental bonding"),
    (r"sealant", "dental sealant child teeth"),
    (r"mouthguard|night guard|tmj", "dental mouthguard"),
    (r"scan|cad|cam|digital|3d|cbct|intraoral", "modern dental technology scanner"),
]


def search(query, per_page=40):
    url = "https://api.pexels.com/v1/search?" + urllib.parse.urlencode(
        {"query": query, "orientation": "landscape", "size": "large", "per_page": per_page})
    req = urllib.request.Request(url, headers={"Authorization": API_KEY, "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read()).get("photos", [])


def fetch_webp(src_url, dest):
    req = urllib.request.Request(src_url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read()
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tf:
        tf.write(raw); tmp = tf.name
    subprocess.run(["cwebp", "-quiet", "-q", "82", "-resize", "1200", "0", tmp, "-o", dest], check=True)
    os.unlink(tmp)


def query_for(title, slug=""):
    if slug in SLUG_OVERRIDE:
        return SLUG_OVERRIDE[slug]
    low = title.lower()
    for pat, q in REFINE:
        if re.search(pat, low):
            return q
    t = re.sub(r"[^a-zA-Z ]", " ", title).strip()
    t = re.sub(r"\s+", " ", t)
    if not re.search(r"dental|tooth|teeth|denture|smile", t.lower()):
        t += " dentistry"
    return t


def main():
    if not API_KEY:
        print("ERROR: set PEXELS_API_KEY"); sys.exit(1)
    site = sys.argv[1]
    site_idx = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    sdir = os.path.join(ROOT, "sites", site)
    out = os.path.join(sdir, "public/images/stock")
    os.makedirs(out, exist_ok=True)
    used: set[int] = set()
    files = sorted(glob.glob(os.path.join(sdir, "src/content/services/*.md")))
    print(f"== {site}: {len(files)} services ==")
    got = 0
    for f in files:
        slug = os.path.basename(f)[:-3]
        s = open(f).read()
        if re.search(r"^image:", s, re.M):
            print("  · skip (frontmatter image):", slug); continue
        title = (re.search(r"^title:\s*(.+)$", s, re.M) or [None, slug])[1].strip()
        q = query_for(title, slug)
        dest = os.path.join(out, f"svc-{slug}.webp")
        try:
            photos = search(q)
            order = photos[site_idx:] + photos[:site_idx]
            chosen = next((p for p in order if p["id"] not in used), photos[0] if photos else None)
            if not chosen:
                print(f"  ! no results: {slug} ('{q}')"); continue
            used.add(chosen["id"])
            fetch_webp(chosen["src"]["large"], dest)
            got += 1
            print(f"  ✓ {slug}: '{q}' -> pexels#{chosen['id']}")
            time.sleep(0.15)
        except Exception as e:
            print(f"  ! {slug}: {e}")
    print(f"done → {got} unique service images for {site}")


if __name__ == "__main__":
    main()
