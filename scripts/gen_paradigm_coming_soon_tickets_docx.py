#!/usr/bin/env python3
"""Generate the 'Tysons expansion + Areas-We-Serve fix' dev-ticket handoff DOCX
for Paradigm Experts (Webflow). Mirrors the style of gen_paradigm_perf_docx.py.

    python scripts/gen_paradigm_coming_soon_tickets_docx.py [out.docx]
"""
import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor

GOLD = RGBColor(0xC1, 0x8D, 0x15)
DARK = RGBColor(0x1A, 0x1E, 0x2E)
GREY = RGBColor(0x55, 0x5B, 0x66)
RED = RGBColor(0xC0, 0x39, 0x2B)

CARD_IMG = Path(__file__).resolve().parent.parent.parent / (
    "../private/tmp"  # placeholder; overwritten below via --card
)


def ticket(doc, tid, title, prio, problem, tasks, acceptance):
    h = doc.add_heading(level=2)
    r = h.add_run(f"{tid} — {title}")
    r.font.color.rgb = DARK
    meta = doc.add_paragraph()
    mr = meta.add_run(f"Priority: {prio}   ·   Site: paradigmexperts.com (Webflow)   ·   Owner: Dev")
    mr.font.size = Pt(9.5)
    mr.font.color.rgb = GREY
    pp = doc.add_paragraph()
    pp.add_run("Problem / Goal — ").bold = True
    pp.add_run(problem)
    doc.add_paragraph("Tasks", style="Heading 4")
    for t in tasks:
        doc.add_paragraph(t, style="List Bullet")
    ap = doc.add_paragraph()
    ar = ap.add_run("Acceptance criteria — ")
    ar.bold = True
    ar.font.color.rgb = GOLD
    ap.add_run(acceptance)
    doc.add_paragraph()


def build(path, card_path=None):
    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10.5)

    title = doc.add_heading(level=0)
    tr = title.add_run("Paradigm Experts — Website Tickets: Tysons Expansion + Areas-We-Serve Fix")
    tr.font.color.rgb = DARK
    sub = doc.add_paragraph()
    sr = sub.add_run("Prepared by PracticeRank for the Paradigm Experts web developer. "
                     "Three tickets: (1) fix the Areas-We-Serve headline contrast bug, "
                     "(2) add the new Vienna/Tysons location as “Coming Soon,” and "
                     "(3) a homepage “Opening Soon” banner + a dedicated Tysons landing page.")
    sr.font.color.rgb = GREY
    sr.font.size = Pt(10)
    doc.add_paragraph()

    # Canonical NAP box
    doc.add_heading("Business details (use exactly)", level=2)
    for line in [
        "Existing (primary): 6310-A Springfield Plaza, Springfield, VA 22150",
        "NEW (Coming Soon): 8381 Old Courthouse Road, Suite 211, Vienna, VA 22181  (Tysons area)",
        "Contact: Danny Gouterman · Danny@ParadigmExperts.com · (703) 650-5034 (main) / 703-585-1964 (Danny)",
        "Buys: gold, precious metals, diamonds, jewelry, timepieces (watches), and coins.",
    ]:
        p = doc.add_paragraph(style="List Bullet")
        p.add_run(line)
    if card_path and Path(card_path).exists():
        cap = doc.add_paragraph()
        cr = cap.add_run("Source — new business card (new Vienna/Tysons address):")
        cr.italic = True
        cr.font.color.rgb = GREY
        cr.font.size = Pt(9)
        doc.add_picture(str(card_path), width=Inches(4.2))
    doc.add_paragraph()

    ticket(
        doc, "PE-1", "Fix “Areas We Serve” headline — unreadable over hero image", "High – client-reported",
        "On the “Areas We Serve” city landing pages, the headline/H1 color blends into the background "
        "hero image (low contrast), so it’s hard to read. These pages share one template/CMS collection, "
        "so fix it once at the template level.",
        [
            "Add a dark overlay/scrim between the hero image and the text (e.g. a linear-gradient or "
            "rgba(0,0,0,0.45–0.6) layer) so text is legible over any photo.",
            "Set the headline to a high-contrast color (white) with a subtle text-shadow for safety.",
            "Verify WCAG AA contrast (≥ 4.5:1) against the LIGHTEST hero image in the set, not just a dark one.",
            "Apply on the shared hero component/symbol so every area page inherits the fix (don’t patch pages one by one).",
        ],
        "Headline is clearly legible and passes AA contrast on every Areas-We-Serve page, desktop and mobile, "
        "including the lightest hero image.",
    )

    ticket(
        doc, "PE-2", "Add new Vienna/Tysons location (Coming Soon)", "High",
        "Paradigm is opening a second location and wants it announced now (good for growth + credibility). "
        "Add it site-wide as “Coming Soon” without implying it’s open for walk-ins yet.",
        [
            "Add the Vienna location to the Locations section/CMS: 8381 Old Courthouse Road, Suite 211, "
            "Vienna, VA 22181, with a visible “Coming Soon” badge/label.",
            "Add second-office details to the footer and Contact page, clearly marked Coming Soon (no live "
            "hours; use the main phone for now).",
            "Add a second PostalAddress to the Organization/LocalBusiness JSON-LD (or a second location entity) "
            "so search engines learn about the new address; keep Springfield as the primary location.",
            "Do NOT set up or link a Google Business Profile as “open” yet — coming-soon only until Danny confirms the open date.",
        ],
        "The Vienna location appears with a “Coming Soon” treatment in Locations, footer, and Contact; "
        "JSON-LD validates in Google’s Rich Results test; the Springfield location is unchanged.",
    )

    ticket(
        doc, "PE-3", "Homepage “Opening Soon” banner + dedicated Tysons landing page", "High",
        "Announce the Tysons expansion on the homepage with a CTA that drives visitors to a dedicated Tysons "
        "landing page (captures the expansion news + local Tysons/Vienna search intent).",
        [
            "Build a dedicated Tysons landing page (suggested URL /tysons or /locations/tysons): hero with "
            "“Opening Soon in Tysons / Vienna”, the new address, what Paradigm buys, and copy targeting "
            "Tysons, Vienna, McLean, and Falls Church sellers.",
            "Add a “Notify me / Get a free evaluation” lead form + phone CTA on the Tysons page.",
            "Set the Tysons page’s SEO: title/meta + LocalBusiness schema for the Vienna address; make it indexable.",
            "Add a dismissible announcement banner on the HOMEPAGE (top strip or hero ribbon): "
            "“Opening Soon in Tysons” + a CTA button linking to the Tysons page.",
            "Ensure the banner is mobile-friendly, doesn’t cover key content, and the Tysons page inherits the "
            "PE-1 hero contrast fix.",
        ],
        "Homepage shows the Opening-Soon banner on desktop + mobile linking to a live, indexable Tysons landing "
        "page with correct NAP, schema, working form, and legible hero.",
    )

    doc.save(path)
    print(f"wrote {path}")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "docs/Paradigm-Experts-Coming-Soon-Tickets.docx"
    card = sys.argv[2] if len(sys.argv) > 2 else None
    build(out, card)
