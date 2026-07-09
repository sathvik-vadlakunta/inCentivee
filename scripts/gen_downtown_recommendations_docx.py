#!/usr/bin/env python3
"""Downtown Dental — Recommended Changes DOCX.

Grounded in a FRESH scrape of downtowndentalsmile.com + recomputed scorecard
(2026-07-09): overall 88 (A). Corrected from an earlier stale 42/D reading after
the practice's developer (Jared) shipped the technical foundation, all 8
service-area pages, and the content. All figures verified from the live site.

    python scripts/gen_downtown_recommendations_docx.py [out.docx]
"""
import sys

from docx import Document
from docx.shared import Pt, RGBColor

DARK = RGBColor(0x14, 0x2A, 0x3D)
GREY = RGBColor(0x55, 0x5B, 0x66)
GREEN = RGBColor(0x1E, 0x7A, 0x3D)
AMBER = RGBColor(0xB4, 0x6A, 0x00)
RED = RGBColor(0xB4, 0x2A, 0x1F)
ACCENT = RGBColor(0x1F, 0x6F, 0xB2)

PILLARS = [
    ("GEO Foundation (technical)", 100, "done", "8 of 8 deliverables live — llms.txt, sitemap, robots, FAQ + Review + LocalBusiness schema"),
    ("Reputation", 81, "strong", "5.0★ · 219 reviews · AggregateRating schema live"),
    ("AI Visibility", 71, "strong", "41% AI mention rate · avg position 2.51 · all 5 engines"),
    ("Content & Coverage", 100, "done", "21 content pieces live · 8 of 8 service areas covered"),
]

# Verified live on the fresh scrape (2026-07-09) — acknowledge what's already done.
SHIPPED = [
    "llms.txt + llms-full.txt, robots.txt, and an XML sitemap (181 URLs) — all live.",
    "FAQPage schema across home/implantology/cosmetic/prosthodontics (20 Q&A entities).",
    "Review + AggregateRating schema (the 5.0★ / 219 reviews are now marked up).",
    "LocalBusiness + Dentist schema, single-H1 structure, and BlogPosting schema (blog live).",
    "8 content pieces published (FAQs, stat callouts, blog posts).",
]

# (priority, title, why[grounded], change[what to do], lifts) — only NEW, verified dev tasks.
RECS = [
    ("P1", "Improve site performance",
     "A fresh audit (2026-07-09) puts mobile Lighthouse performance in the low 30s — slow pages suppress "
     "rankings and conversions even though the SEO/AEO foundation is complete.",
     "Target 90+: serve images as WebP, compress/lazy-load media, defer non-critical JS, and fix Core Web "
     "Vitals (LCP/CLS).",
     "Rankings, conversions"),
    ("P2", "Render the FAQs as collapsible accordions",
     "The FAQ schema is correct (multiple Q&A entities), but the live pages have no <details>/<summary> "
     "elements — the questions display as a flat block instead of an expand/collapse accordion. UX only; the "
     "AEO/schema side is already done.",
     "Wrap each existing Q&A in <details>/<summary> so visitors can expand/collapse. Keep the schema as-is.",
     "UX / on-page engagement"),
]

TAG = {"P1": ("DO FIRST", RED), "P2": ("NEXT", AMBER), "P3": ("THEN", ACCENT)}


def build(path):
    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10.5)

    h = doc.add_heading(level=0)
    h.add_run("Downtown Dental — Recommended Changes").font.color.rgb = DARK
    sub = doc.add_paragraph()
    s = sub.add_run("Prepared by PracticeRank · based on a fresh scrape of the live site (2026-07-09). "
                    "The SEO/AEO foundation, schema, content, and all 8 service-area pages are already live — "
                    "so this is only the NEW work still outstanding.")
    s.font.color.rgb = GREY
    s.font.size = Pt(10)
    doc.add_paragraph()

    doc.add_heading("What's left to do", level=2)
    for prio, title, why, change, lifts in RECS:
        p = doc.add_heading(level=3)
        label, color = TAG[prio]
        tag = p.add_run(f"[{label}]  ")
        tag.font.color.rgb = color
        p.add_run(title).font.color.rgb = DARK
        for lbl, val, col in (("Why", why, GREY), ("Change", change, DARK), ("Lifts", lifts, ACCENT)):
            bp = doc.add_paragraph()
            r = bp.add_run(lbl + " — ")
            r.bold = True
            r.font.color.rgb = col
            bp.add_run(val)
        doc.add_paragraph()

    note = doc.add_paragraph()
    nr = note.add_run("Note: Downtown Dental self-publishes (PracticeRank provides content; the practice's "
                      "developer applies it). The location pages above can be drafted by PracticeRank next.")
    nr.italic = True
    nr.font.size = Pt(9)
    nr.font.color.rgb = GREY

    doc.save(path)
    print(f"wrote {path}")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "docs/Downtown-Dental-Recommended-Changes-2026-07.docx")
