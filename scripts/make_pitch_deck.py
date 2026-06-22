#!/usr/bin/env python3
"""Generate a branded PracticeRank SEO strategy / sales-pitch deck (PPTX).

Doubles as a reusable TEMPLATE: edit the CLIENT block below for any prospect or
client. The evergreen slides (team, approach, what-we-fix, guarantee) stay the
same; the client-specific slides (standing, what-we've-done, roadmap) read from
CLIENT. Run:  python3 scripts/make_pitch_deck.py
"""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ─────────────────────────── CLIENT CONFIG (swap per deal) ───────────────────────────
CLIENT = {
    "name": "Paradigm Experts",
    "location": "Springfield, Virginia",
    "industry": "Gold, Silver & Estate Jewelry Buyer",
    "competitor": "Alexandria Gold & Silver",
    # real, sourced numbers (Semrush, May 2026) — leave blank for a generic pitch
    "gap_rows": [
        ("Monthly organic visits", "131", "1,281", "9.8x"),
        ("“Near me” keywords (top 10)", "2", "49", "24x"),
        ("Top-10 ranking keywords", "14", "69", "4.9x"),
    ],
    "gap_source": "Source: Semrush organic research, May 2026",
    # Real Domain Authority (Moz). da_self first, then rivals.
    "da_self": ("Paradigm Experts", 14),
    "da_rivals": [("CASH FOR GOLD", 18), ("Alexandria Gold & Silver", 11), ("Cash for Gold NOVA", 10)],
    "da_source": "Domain Authority — Moz, June 2026",
    "da_insight": "You already out-rank Alexandria on Domain Authority (14 vs 11) — yet they pull ~10x your traffic. That proves the gap is on-page & local, not authority. We close that gap AND push your DA past the market leader to lock in the lead.",
    "service_areas": "Springfield · Arlington · McLean · Fairfax · Alexandria · Lorton · DC",
    "keyword_examples": ['"sell gold in Springfield VA"', '"estate jewelry buyer near me"',
                         '"where to sell silver Northern Virginia"'],
    "target": "500+ monthly organic visits within 6 months",
    "done": [
        "Deep competitive & keyword-gap analysis vs your top local rival (Semrush)",
        "Full SEO / AI-search audit + a phased action plan",
        "Technical foundation: schema markup, llms.txt / llms-full.txt, HTTPS-canonical fixes",
        "Google Business Profile access secured — category, services & service-area optimization underway",
    ],
}

# ─────────────────────────── brand ───────────────────────────
BG      = RGBColor(0x0F, 0x16, 0x20)
CARD    = RGBColor(0x1B, 0x24, 0x30)
CARD2   = RGBColor(0x16, 0x21, 0x3E)
GREEN   = RGBColor(0x4A, 0xDE, 0x80)
WHITE   = RGBColor(0xFF, 0xFF, 0xFF)
GREY    = RGBColor(0xA8, 0xB3, 0xC2)
DARKTXT = RGBColor(0x0F, 0x16, 0x20)
LOGO    = os.path.join(ROOT, "brand", "practicerank-logo-360.png")

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
SW, SH = prs.slide_width, prs.slide_height
BLANK = prs.slide_layouts[6]


def slide(bg=BG):
    s = prs.slides.add_slide(BLANK)
    r = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SW, SH)
    r.fill.solid(); r.fill.fore_color.rgb = bg; r.line.fill.background()
    r.shadow.inherit = False
    return s


def text(s, l, t, w, h, runs, size=18, color=WHITE, bold=False, align=PP_ALIGN.LEFT,
         anchor=MSO_ANCHOR.TOP, font="Calibri", line_spacing=1.0):
    tb = s.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
    tf = tb.text_frame; tf.word_wrap = True; tf.vertical_anchor = anchor
    items = runs if isinstance(runs, list) else [(runs, color, bold, size)]
    for i, item in enumerate(items):
        txt, c, b, sz = (item + (color, bold, size))[:4] if isinstance(item, tuple) else (item, color, bold, size)
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align; p.line_spacing = line_spacing
        run = p.add_run(); run.text = txt
        run.font.size = Pt(sz); run.font.bold = b; run.font.color.rgb = c; run.font.name = font
    return tb


def rect(s, l, t, w, h, fill=CARD, line=None, radius=True):
    shp = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE,
                             Inches(l), Inches(t), Inches(w), Inches(h))
    shp.fill.solid(); shp.fill.fore_color.rgb = fill
    if line: shp.line.color.rgb = line; shp.line.width = Pt(1)
    else: shp.line.fill.background()
    shp.shadow.inherit = False
    return shp


def accent_bar(s, l=0.0, t=0.0, w=13.333, h=0.12):
    rect(s, l, t, w, h, fill=GREEN, radius=False)


def heading(s, kicker, title):
    text(s, 0.7, 0.55, 11, 0.4, kicker, size=14, color=GREEN, bold=True)
    text(s, 0.7, 0.95, 12, 1.0, title, size=33, color=WHITE, bold=True)
    rect(s, 0.72, 1.75, 0.9, 0.06, fill=GREEN, radius=False)


def bullets(s, l, t, w, items, size=16, gap=True, color=WHITE, marker="—"):
    tb = s.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(5))
    tf = tb.text_frame; tf.word_wrap = True
    for i, it in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(10 if gap else 4); p.line_spacing = 1.1
        m = p.add_run(); m.text = marker + "  "; m.font.color.rgb = GREEN; m.font.bold = True; m.font.size = Pt(size)
        r = p.add_run(); r.text = it; r.font.color.rgb = color; r.font.size = Pt(size); r.font.name = "Calibri"
    return tb


# ═══ 1. TITLE ═══
s = slide(CARD2)
accent_bar(s)
if os.path.exists(LOGO):
    s.shapes.add_picture(LOGO, Inches(0.7), Inches(0.7), height=Inches(1.0))
text(s, 0.7, 2.3, 12, 1.6, "SEO & AI-Search\nGrowth Strategy", size=46, bold=True)
text(s, 0.72, 4.25, 12, 0.6, [("Prepared for ", GREY, False, 22), (CLIENT["name"], GREEN, True, 22),
     ("   ·   " + CLIENT["location"], GREY, False, 22)])
text(s, 0.72, 5.0, 12, 0.5, CLIENT["industry"], size=16, color=GREY)
text(s, 0.7, 6.7, 12, 0.4, "PracticeRank  ·  practicerank.ai", size=14, color=GREY)

# ═══ 2. MEET YOUR TEAM ═══
s = slide(); accent_bar(s); heading(s, "WHO YOU'RE WORKING WITH", "Meet Your Team")
team = [
    ("Dan Toone", "Client Relations Manager",
     "Your dedicated day-to-day point of contact. Dan keeps you informed, coordinates approvals, and makes sure every deliverable ships on time — so you always know exactly what's happening and what's next."),
    ("Kody Doherty", "Chief Technology Officer",
     "Leads the technical SEO, automation, and AI-search engineering behind your growth — the systems that get you found across Google, Maps, and AI assistants."),
]
for i, (nm, role, bio) in enumerate(team):
    x = 0.7 + i * 6.25
    rect(s, x, 2.2, 5.85, 3.7, fill=CARD)
    rect(s, x + 0.45, 2.65, 0.9, 0.9, fill=GREEN)  # avatar placeholder circle-ish
    text(s, x + 0.45, 2.7, 0.9, 0.8, nm[0], size=34, color=DARKTXT, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    text(s, x + 1.6, 2.6, 4.0, 0.5, nm, size=22, bold=True)
    text(s, x + 1.6, 3.1, 4.0, 0.4, role, size=14, color=GREEN, bold=True)
    text(s, x + 0.45, 3.8, 5.0, 1.9, bio, size=14, color=GREY, line_spacing=1.15)

# ═══ 3. SEARCH HAS CHANGED ═══
s = slide(); accent_bar(s); heading(s, "WHY THIS MATTERS", "How Customers Find You Has Changed")
text(s, 0.72, 2.0, 11.9, 0.9, "People don't just “Google it” anymore. They search Google, tap the Maps 3-pack, and increasingly ask AI assistants for a recommendation. Winning today means showing up in all of them.", size=18, color=GREY, line_spacing=1.2)
chans = [("Google Search", "Organic rankings for the searches that bring you customers"),
         ("Google & Apple Maps", "The local 3-pack — where most “near me” clicks go"),
         ("AI Assistants", "ChatGPT, Gemini, Perplexity & Google AI recommending you")]
for i, (t_, d) in enumerate(chans):
    x = 0.7 + i * 4.1
    rect(s, x, 3.4, 3.8, 2.6, fill=CARD)
    text(s, x + 0.35, 3.7, 3.2, 0.6, t_, size=19, bold=True, color=GREEN)
    text(s, x + 0.35, 4.45, 3.2, 1.4, d, size=14, color=GREY, line_spacing=1.15)

# ═══ 4. WELL-ROUNDED APPROACH ═══
s = slide(); accent_bar(s); heading(s, "OUR METHOD", "A Well-Rounded Approach — Every Signal Covered")
pillars = ["Technical SEO", "On-Page SEO", "Schema / Structured Data", "Local SEO & Google Profile",
           "Content & Authority", "AI-Search (AEO)", "Reviews & Reputation", "Conversion & UX"]
for i, p in enumerate(pillars):
    col, row = i % 4, i // 4
    x = 0.7 + col * 3.05; y = 2.3 + row * 1.7
    rect(s, x, y, 2.85, 1.45, fill=CARD)
    text(s, x + 0.25, y + 0.2, 2.4, 1.1, p, size=15, bold=True, anchor=MSO_ANCHOR.MIDDLE)
text(s, 0.72, 5.95, 11.9, 0.6, "We don't do one thing well — we cover every signal Google and AI engines use to find, trust, and recommend you.", size=15, color=GREY)

# ═══ 5. WHAT WE FIX ═══
s = slide(); accent_bar(s); heading(s, "THE PROBLEMS WE SOLVE", "What We Fix")
fixes = [
    ("Invisible in “near me” searches", "Local SEO + Google Business Profile + city/neighborhood pages"),
    ("Site doesn't tell Google what you do", "Keyword-rich service pages + complete schema markup"),
    ("Not showing up in AI answers", "llms.txt, structured data & AI-readable content (AEO)"),
    ("Thin or off-target content", "Buyer-intent content + a focused blog strategy"),
    ("Low domain authority", "A few HIGH-value local backlinks + citation cleanup"),
    ("Few or aging reviews", "Automated review engine + reputation management"),
]
for i, (prob, fix) in enumerate(fixes):
    col, row = i % 2, i // 2
    x = 0.7 + col * 6.25; y = 2.2 + row * 1.55
    rect(s, x, y, 5.85, 1.35, fill=CARD)
    text(s, x + 0.3, y + 0.18, 5.3, 0.5, "✗  " + prob, size=15, bold=True, color=WHITE)
    text(s, x + 0.3, y + 0.72, 5.3, 0.5, "→  " + fix, size=13.5, color=GREEN)

# ═══ 6. WHERE YOU STAND ═══
if CLIENT.get("gap_rows"):
    s = slide(); accent_bar(s); heading(s, "THE OPPORTUNITY", f"Where {CLIENT['name']} Stands Today")
    text(s, 0.72, 2.0, 11.9, 0.6, f"You're being out-ranked by {CLIENT['competitor']} — but the gap is closeable, and we've mapped exactly how.", size=16, color=GREY)
    # table header
    cols = [("", 4.6), (CLIENT["name"], 2.7), (CLIENT["competitor"], 2.7), ("Gap", 1.6)]
    x = 0.7; y = 2.85
    rect(s, x, y, 11.6, 0.55, fill=CARD2)
    cx = x
    for label, w in cols:
        text(s, cx + 0.2, y + 0.05, w, 0.45, label, size=14, bold=True, color=GREEN if label != "" else WHITE)
        cx += w
    for ri, row in enumerate(CLIENT["gap_rows"]):
        ry = y + 0.55 + ri * 0.72
        rect(s, x, ry, 11.6, 0.72, fill=CARD if ri % 2 == 0 else BG)
        cx = x
        for ci, (val, w) in enumerate(zip(row, [c[1] for c in cols])):
            c = WHITE; sz = 15; b = False
            if ci == 2: c = GREEN
            if ci == 3: c = GREEN; b = True; sz = 17
            if ci == 0: c = GREY
            text(s, cx + 0.2, ry + 0.12, w, 0.5, val, size=sz, bold=b, color=c, anchor=MSO_ANCHOR.MIDDLE)
            cx += w
    text(s, 0.72, 6.55, 11.9, 0.4, CLIENT.get("gap_source", ""), size=11, color=GREY)

# ═══ 6b. DOMAIN AUTHORITY ═══
if CLIENT.get("da_self"):
    s = slide(); accent_bar(s); heading(s, "AUTHORITY", "Your Domain Authority vs. The Competition")
    rows = [(CLIENT["da_self"][0], CLIENT["da_self"][1], True)] + [(n, d, False) for n, d in CLIENT["da_rivals"]]
    rows.sort(key=lambda r: -r[1])
    maxda = max(r[1] for r in rows) or 1
    bx, bw_max = 5.2, 5.7
    for i, (nm, da, mine) in enumerate(rows):
        y = 2.25 + i * 0.78
        text(s, 0.7, y, 4.3, 0.55, nm, size=15, bold=mine, color=GREEN if mine else WHITE, anchor=MSO_ANCHOR.MIDDLE)
        rect(s, bx, y + 0.06, bw_max, 0.42, fill=CARD, radius=False)
        w = max(0.25, bw_max * da / 20.0)
        rect(s, bx, y + 0.06, w, 0.42, fill=GREEN if mine else RGBColor(0x5A, 0x67, 0x78), radius=False)
        text(s, bx + w + 0.12, y, 1.0, 0.55, str(int(da)), size=16, bold=True,
             color=GREEN if mine else GREY, anchor=MSO_ANCHOR.MIDDLE)
    text(s, 0.7, 5.55, 11.9, 1.0, CLIENT["da_insight"], size=15, color=GREY, line_spacing=1.2)
    text(s, 0.7, 6.95, 8, 0.3, CLIENT["da_source"], size=10.5, color=GREY)
    # how-we-grow chips
    text(s, 9.0, 2.2, 3.6, 0.4, "HOW WE GROW IT", size=12, color=GREEN, bold=True)
    for j, chip in enumerate(["High-value local links", "Citation building + cleanup", "Local press & sponsorships", "Partner / supplier links"]):
        rect(s, 9.0, 2.65 + j * 0.62, 3.6, 0.5, fill=CARD)
        text(s, 9.2, 2.68 + j * 0.62, 3.3, 0.45, chip, size=12.5, anchor=MSO_ANCHOR.MIDDLE)

# ═══ 7. WHAT WE'VE DONE ═══
s = slide(); accent_bar(s); heading(s, "PROGRESS", "What We've Done So Far")
bullets(s, 0.9, 2.3, 11.4, CLIENT["done"], size=18)
text(s, 0.9, 5.9, 11.4, 0.5, "Foundation set — now we scale visibility, authority, and content.", size=15, color=GREEN, bold=True)

# ═══ 8. NEXT: BACKLINKS ═══
s = slide(); accent_bar(s); heading(s, "NEXT STEPS · 1 OF 2", "Building Authority — High-Value Backlinks")
text(s, 0.72, 2.0, 11.9, 0.6, "Quality over volume: a few strong, locally-relevant links that lift rankings AND AI recommendations.", size=16, color=GREY)
bullets(s, 0.9, 2.9, 11.4, [
    "Local citations + NAP consistency across the directories that matter (industry + general)",
    "Local press, community sponsorships & events for authoritative local mentions",
    "Partner, supplier & association links relevant to your business",
    "“Best in {city}” roundups and local guides that AI assistants cite",
    "Steady cadence of high-authority links each month — no spam, no risky tactics",
], size=16)

# ═══ 9. NEXT: CONTENT/BLOG ═══
s = slide(); accent_bar(s); heading(s, "NEXT STEPS · 2 OF 2", "Content & Blog — Capture Ready-to-Buy Searches")
text(s, 0.72, 2.0, 11.9, 0.6, "Shift from curiosity content to buyer-intent content that brings customers through the door.", size=16, color=GREY)
bullets(s, 0.9, 2.85, 11.4, [
    "Target transactional searches like " + ", ".join(CLIENT["keyword_examples"]),
    "City & service landing pages for every area you serve (" + CLIENT["service_areas"] + ")",
    "2–4 new posts per month on high-intent topics, refreshed so they stay ranking",
    "FAQ content structured for Google snippets and AI answers",
], size=16)

# ═══ 10. ROADMAP ═══
s = slide(); accent_bar(s); heading(s, "THE PLAN", "Your 90-Day Roadmap")
phases = [("Month 1", "Technical foundation, Google Business Profile, homepage rebuild"),
          ("Month 2", "City / service landing pages, first authority links, content cadence"),
          ("Month 3", "Authority push, review growth, measure & iterate")]
for i, (m, d) in enumerate(phases):
    x = 0.7 + i * 4.1
    rect(s, x, 2.4, 3.8, 2.7, fill=CARD)
    rect(s, x, 2.4, 3.8, 0.7, fill=GREEN)
    text(s, x, 2.45, 3.8, 0.6, m, size=18, bold=True, color=DARKTXT, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    text(s, x + 0.3, 3.4, 3.2, 1.5, d, size=15, color=GREY, line_spacing=1.2)
text(s, 0.72, 5.5, 11.9, 0.6, [("Target:  ", GREY, False, 18), (CLIENT["target"], GREEN, True, 18)])

# ═══ 11. GUARANTEE ═══
s = slide(CARD2); accent_bar(s)
text(s, 0.7, 2.1, 12, 0.5, "OUR PROMISE", size=15, color=GREEN, bold=True, align=PP_ALIGN.CENTER)
text(s, 1.0, 2.7, 11.3, 1.2, "The 90-Day Results-or-Refund Guarantee", size=34, bold=True, align=PP_ALIGN.CENTER)
text(s, 1.5, 4.1, 10.3, 1.4, "If your PracticeRank Score doesn't improve by 20+ points in 90 days, we refund your monthly fees — and you keep everything we built. Month-to-month. No long-term contracts.",
     size=18, color=GREY, align=PP_ALIGN.CENTER, line_spacing=1.25)

# ═══ 12. CLOSE ═══
s = slide(); accent_bar(s)
if os.path.exists(LOGO):
    s.shapes.add_picture(LOGO, Inches(6.17), Inches(0.9), height=Inches(1.0))
text(s, 1.0, 2.4, 11.3, 0.9, "Let's grow your visibility.", size=38, bold=True, align=PP_ALIGN.CENTER)
text(s, 1.0, 3.5, 11.3, 0.6, "Found everywhere your customers search — Google, Maps, and AI.", size=18, color=GREY, align=PP_ALIGN.CENTER)
text(s, 1.0, 4.7, 11.3, 0.5, [("Dan Toone", GREEN, True, 18), ("  ·  Client Relations Manager", GREY, False, 18)], align=PP_ALIGN.CENTER)
text(s, 1.0, 5.15, 11.3, 0.5, [("Kody Doherty", GREEN, True, 18), ("  ·  Chief Technology Officer", GREY, False, 18)], align=PP_ALIGN.CENTER)
text(s, 1.0, 6.2, 11.3, 0.4, "practicerank.ai  ·  kdoherty@practicerank.ai", size=14, color=GREY, align=PP_ALIGN.CENTER)

os.makedirs(os.path.join(ROOT, "deliverables"), exist_ok=True)
safe = CLIENT["name"].replace(" ", "-")
out = os.path.join(ROOT, "deliverables", f"PracticeRank-SEO-Strategy-{safe}.pptx")
prs.save(out)
print(f"saved {out}  ({len(prs.slides.__iter__.__self__._sldIdLst)} slides, {os.path.getsize(out)//1024} kb)")
