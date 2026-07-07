#!/usr/bin/env python3
"""Generate a branded PracticeRank SEO/AEO strategy + sales-pitch deck (PPTX)
for any prospect or client, from an external JSON config.

    python3 make_pitch_deck.py --config client.json [--out deck.pptx] [--assets-dir DIR] [--logo logo.png]

Evergreen slides (team, approach, what-we-fix, guarantee, close) are built in;
client-specific slides read from the config. Optional blocks — progress ("done"),
PracticeRank Score history, traffic trajectory, and pricing tiers — render ONLY
when their keys are present, so the same generator produces both a new-prospect
strategy deck and an existing-client results deck. See references/client-config.md.
"""
import argparse
import json
import os
import sys

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = SKILL_DIR

REQUIRED = ["name", "location", "industry", "competitor", "gap_rows",
            "da_self", "da_explainer", "da_insight", "da_source",
            "keyword_examples", "target"]
DEFAULTS = {
    "gap_intro": "", "gap_source": "", "comparison_placement": "",
    "service_areas": "", "da_rivals": [], "founding_note": "",
    "show_tiers": False, "popular_tier": 1, "tiers": [],
    "cover_image": None, "img_backlinks": None, "img_content": None, "img_done": None,
}


def load_client(path):
    if not os.path.exists(path):
        sys.exit("error: config not found: %s" % path)
    try:
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
    except json.JSONDecodeError as e:
        sys.exit("error: invalid JSON in %s: %s" % (path, e))
    missing = [k for k in REQUIRED if not cfg.get(k)]
    if missing:
        sys.exit("error: config is missing required fields: %s\n"
                 "See references/client-config.md for the full schema." % ", ".join(missing))
    if len(cfg.get("da_self") or []) != 2:
        sys.exit('error: "da_self" must be [name, score], e.g. ["Acme Co", 14]')
    for r in cfg["gap_rows"]:
        if len(r) != 4:
            sys.exit('error: each "gap_rows" row needs 4 items: [metric, you, competitor, multiplier]')
    if cfg.get("show_tiers") and not cfg.get("tiers"):
        sys.exit('error: "show_tiers" is true but "tiers" is empty')
    merged = dict(DEFAULTS)
    merged.update(cfg)
    return merged


_ap = argparse.ArgumentParser(description="Build a PracticeRank pitch deck (PPTX) from a JSON client config.")
_ap.add_argument("--config", required=True, help="path to the client JSON config")
_ap.add_argument("--out", help="output .pptx path (default: ./PracticeRank-SEO-Strategy-<Name>.pptx)")
_ap.add_argument("--assets-dir", help="base dir for relative image paths (default: the config file's folder)")
_ap.add_argument("--logo", help="path to a PracticeRank logo PNG (optional; default: bundled asset if present)")
_args = _ap.parse_args()

CLIENT = load_client(_args.config)
ASSETS_DIR = _args.assets_dir or os.path.dirname(os.path.abspath(_args.config))
LOGO = _args.logo or os.path.join(SKILL_DIR, "assets", "practicerank-logo-360.png")

from pptx.oxml.ns import qn

BG      = RGBColor(0x08, 0x08, 0x0D)   # site --bg (near-black)
CARD    = RGBColor(0x12, 0x18, 0x22)   # panel
CARD2   = RGBColor(0x16, 0x21, 0x3E)   # navy accent panel
NAVY    = RGBColor(0x16, 0x21, 0x3E)
GREEN   = RGBColor(0x4A, 0xDE, 0x80)   # --accent
GREEN_D = RGBColor(0x16, 0xA3, 0x4A)
WHITE   = RGBColor(0xFF, 0xFF, 0xFF)
TXT2    = RGBColor(0xDC, 0xE2, 0xE8)   # ~white 86%
GREY    = RGBColor(0x9A, 0xA6, 0xB4)   # muted
FAINT   = RGBColor(0x5E, 0x6A, 0x79)   # faint
BORDER  = RGBColor(0x23, 0x2C, 0x39)
DARKTXT = RGBColor(0x04, 0x21, 0x0F)   # text on green
# LOGO is provided by the header (bundled asset or --logo).

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
SW, SH = prs.slide_width, prs.slide_height
BLANK = prs.slide_layouts[6]


def _soft_edge(shape, rad_in):
    spPr = shape._element.spPr
    eff = spPr.find(qn('a:effectLst'))
    if eff is None:
        eff = spPr.makeelement(qn('a:effectLst'), {}); spPr.append(eff)
    eff.append(eff.makeelement(qn('a:softEdge'), {'rad': str(int(rad_in * 914400))}))


def _alpha(shape, pct):
    srgb = shape.fill.fore_color._xFill.find(qn('a:srgbClr'))
    srgb.append(srgb.makeelement(qn('a:alpha'), {'val': str(int(pct * 1000))}))


def glow(s, cx, cy, w, h, color, alpha=38, soft=1.3):
    """Soft radial-style glow ellipse — the site's signature lighting."""
    e = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(cx - w / 2), Inches(cy - h / 2), Inches(w), Inches(h))
    e.fill.solid(); e.fill.fore_color.rgb = color; e.line.fill.background(); e.shadow.inherit = False
    _alpha(e, alpha); _soft_edge(e, soft)
    return e


def slide(bg=BG, green_corner=False):
    s = prs.slides.add_slide(BLANK)
    r = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SW, SH)
    r.fill.solid(); r.fill.fore_color.rgb = bg; r.line.fill.background(); r.shadow.inherit = False
    glow(s, 6.67, -1.4, 15, 6.5, NAVY, alpha=46, soft=1.6)        # top navy glow
    if green_corner:
        glow(s, 12.8, 7.6, 7, 7, GREEN, alpha=12, soft=1.8)       # faint green corner
    return s


def text(s, l, t, w, h, runs, size=18, color=WHITE, bold=False, align=PP_ALIGN.LEFT,
         anchor=MSO_ANCHOR.TOP, font="Calibri", line_spacing=1.0):
    tb = s.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
    tf = tb.text_frame; tf.word_wrap = True; tf.vertical_anchor = anchor
    # A list => multiple INLINE runs on one paragraph; a string => one run.
    items = runs if isinstance(runs, list) else [(runs, color, bold, size)]
    p = tf.paragraphs[0]; p.alignment = align; p.line_spacing = line_spacing
    for item in items:
        txt, c, b, sz = (item + (color, bold, size))[:4] if isinstance(item, tuple) else (item, color, bold, size)
        run = p.add_run(); run.text = txt
        run.font.size = Pt(sz); run.font.bold = b; run.font.color.rgb = c; run.font.name = font
    return tb


def rect(s, l, t, w, h, fill=CARD, line=None, radius=True):
    shp = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE,
                             Inches(l), Inches(t), Inches(w), Inches(h))
    shp.fill.solid(); shp.fill.fore_color.rgb = fill
    if line is not None:
        shp.line.color.rgb = line; shp.line.width = Pt(1)
    elif radius and fill not in (GREEN, GREEN_D):
        shp.line.color.rgb = BORDER; shp.line.width = Pt(0.75)   # subtle card border
    else:
        shp.line.fill.background()
    shp.shadow.inherit = False
    return shp


def _footer(s):
    n = len(prs.slides._sldIdLst)
    if os.path.exists(LOGO):
        s.shapes.add_picture(LOGO, Inches(0.7), Inches(7.02), height=Inches(0.26))
    text(s, 1.05, 7.0, 4, 0.3, "practicerank.ai", size=9, color=FAINT, anchor=MSO_ANCHOR.MIDDLE)
    text(s, 11.55, 7.0, 1.1, 0.3, f"{n:02d}", size=9, color=FAINT, align=PP_ALIGN.RIGHT, anchor=MSO_ANCHOR.MIDDLE)


def _img_path(path):
    if not path:
        return None
    return path if os.path.isabs(path) else os.path.join(ASSETS_DIR, path)


def picture(s, path, l, t, w, h=None, border=True):
    p = _img_path(path)
    if not p or not os.path.exists(p):
        return None
    kw = {"width": Inches(w)} if h is None else {"width": Inches(w), "height": Inches(h)}
    pic = s.shapes.add_picture(p, Inches(l), Inches(t), **kw)
    if border:
        pic.line.color.rgb = BORDER; pic.line.width = Pt(1)
    return pic


def cover_image(s, path, darken=76):
    p = _img_path(path)
    if not p or not os.path.exists(p):
        return
    s.shapes.add_picture(p, 0, Inches(-0.85), width=SW)   # full-bleed, cover-crop
    ov = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SW, SH)
    ov.fill.solid(); ov.fill.fore_color.rgb = BG; ov.line.fill.background(); ov.shadow.inherit = False
    _alpha(ov, darken)


def column_chart(s, l, t, w, h, labels, values, target=None, accent_last=False):
    """On-brand rising column chart (shapes). values scaled to max*1.15."""
    n = len(values); vmax = max(values + ([target] if target else [])) * 1.12 or 1
    gap = 0.22; cw = (w - gap * (n - 1)) / n
    base = t + h
    rect(s, l - 0.05, base, w + 0.1, 0.02, fill=BORDER, radius=False)   # baseline
    if target:
        ty = base - h * target / vmax
        rect(s, l, ty, w, 0.025, fill=GREEN, radius=False)
        text(s, l, ty - 0.44, 3.0, 0.32, f"Goal: {target}+", size=11, color=GREEN, bold=True, align=PP_ALIGN.LEFT)
    for i, (lab, v) in enumerate(zip(labels, values)):
        x = l + i * (cw + gap); bh = max(0.06, h * v / vmax)
        mine = accent_last and i == n - 1
        col = GREEN if (mine or i == n - 1) else RGBColor(0x3A, 0x46, 0x55)
        rect(s, x, base - bh, cw, bh, fill=col, radius=False)
        text(s, x - 0.2, base - bh - 0.42, cw + 0.4, 0.35, str(v), size=12, bold=True,
             color=WHITE if not mine else GREEN, align=PP_ALIGN.CENTER)
        text(s, x - 0.2, base + 0.08, cw + 0.4, 0.3, lab, size=11, color=GREY, align=PP_ALIGN.CENTER)


def accent_bar(s, l=0.0, t=0.0, w=13.333, h=0.12):
    rect(s, l, t, w, h, fill=GREEN, radius=False)


def heading(s, kicker, title):
    rect(s, 0.72, 0.62, 0.22, 0.22, fill=GREEN, radius=False)   # green tick
    text(s, 1.05, 0.55, 11, 0.4, kicker, size=13, color=GREEN, bold=True)
    text(s, 0.68, 0.98, 12, 1.0, title, size=32, color=WHITE, bold=True)
    rect(s, 0.74, 1.78, 0.8, 0.055, fill=GREEN, radius=False)
    _footer(s)


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
s = slide(green_corner=True)
if CLIENT.get("cover_image"):
    cover_image(s, CLIENT.get("cover_image"))
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
    text(s, 0.72, 2.0, 11.9, 0.6, CLIENT.get("gap_intro", f"You're being out-ranked by {CLIENT['competitor']} — but the gap is closeable, and we've mapped exactly how."), size=16, color=GREY)
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
    s = slide(); accent_bar(s); heading(s, "AUTHORITY", "Domain Authority — and Why ~30 Is the Goal")
    text(s, 0.72, 1.95, 11.9, 0.7, CLIENT["da_explainer"], size=15, color=GREY, line_spacing=1.18)
    rows = [(CLIENT["da_self"][0], CLIENT["da_self"][1], True)] + [(n, d, False) for n, d in CLIENT["da_rivals"]]
    rows.sort(key=lambda r: -r[1])
    SCALE = 40.0
    bx, bw, lblw = 4.3, 6.4, 3.3
    rows_top, rh = 3.15, 0.6
    # target marker at ~30
    tx = bx + bw * 30 / SCALE
    rect(s, tx, rows_top - 0.05, 0.035, len(rows) * rh + 0.05, fill=GREEN, radius=False)
    text(s, tx - 0.85, rows_top - 0.5, 1.8, 0.35, "YOUR TARGET  ~30", size=11, color=GREEN, bold=True, align=PP_ALIGN.CENTER)
    for i, (nm, da, mine) in enumerate(rows):
        y = rows_top + i * rh
        text(s, 0.7, y, lblw, 0.45, nm, size=13.5, bold=mine, color=GREEN if mine else WHITE, anchor=MSO_ANCHOR.MIDDLE)
        rect(s, bx, y + 0.04, bw, 0.36, fill=CARD, radius=False)
        w = max(0.18, bw * da / SCALE)
        rect(s, bx, y + 0.04, w, 0.36, fill=GREEN if mine else RGBColor(0x5A, 0x67, 0x78), radius=False)
        text(s, bx + w + 0.1, y, 0.6, 0.45, str(int(da)), size=14, bold=True,
             color=GREEN if mine else GREY, anchor=MSO_ANCHOR.MIDDLE)
    text(s, 0.72, 5.55, 11.9, 1.1, CLIENT["da_insight"], size=14.5, color=TXT2, line_spacing=1.2)
    text(s, 0.72, 6.78, 8, 0.3, CLIENT["da_source"] + "   ·   Backlinks are the #1 lever for raising Domain Authority.", size=10.5, color=FAINT)

# ═══ 7. WHAT WE'VE DONE (only for existing clients with progress) ═══
if CLIENT.get("done"):
    s = slide(); accent_bar(s); heading(s, "PROGRESS", "What We've Done So Far")
    bullets(s, 0.9, 2.25, 7.5, CLIENT["done"], size=15)
    if CLIENT.get("img_done"):
        picture(s, CLIENT["img_done"], 8.55, 2.3, 4.1, 2.73)
    text(s, 0.9, 6.15, 11.4, 0.5, "Foundation set — now we scale visibility, authority, and content.", size=15, color=GREEN, bold=True)

# ═══ 7b. PRACTICERANK SCORE (proof of momentum) ═══
if CLIENT.get("score_now"):
    s = slide(); accent_bar(s); heading(s, "PROOF OF MOMENTUM", "Your PracticeRank Score — Already Climbing")
    text(s, 0.72, 1.95, 11.9, 0.7, "Your PracticeRank Score (0–100) is the one number we track and guarantee — your visibility across Google, Maps, reviews & AI search.", size=15, color=GREY, line_spacing=1.18)
    start, now = CLIENT["score_start"], CLIENT["score_now"]; delta = now - start
    # Starting card
    rect(s, 0.9, 2.7, 3.1, 1.95, fill=CARD)
    text(s, 0.9, 2.88, 3.1, 0.4, "WHERE YOU STARTED", size=11, color=GREY, bold=True, align=PP_ALIGN.CENTER)
    text(s, 0.9, 3.18, 3.1, 1.1, str(start), size=60, color=WHITE, bold=True, align=PP_ALIGN.CENTER)
    text(s, 0.9, 4.3, 3.1, 0.3, CLIENT.get("score_start_date", ""), size=11, color=FAINT, align=PP_ALIGN.CENTER)
    # Delta in the middle
    text(s, 4.1, 3.05, 1.3, 1.0, "→", size=40, color=GREEN, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    rect(s, 4.1, 3.95, 1.3, 0.5, fill=GREEN)
    text(s, 4.1, 3.97, 1.3, 0.46, f"+{delta} pts", size=15, color=DARKTXT, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    # Now card (highlighted)
    rect(s, 5.5, 2.7, 3.1, 1.95, fill=CARD, line=GREEN)
    text(s, 5.5, 2.88, 3.1, 0.4, "TODAY", size=11, color=GREEN, bold=True, align=PP_ALIGN.CENTER)
    text(s, 5.5, 3.18, 3.1, 1.1, str(now), size=60, color=GREEN, bold=True, align=PP_ALIGN.CENTER)
    text(s, 5.5, 4.3, 3.1, 0.3, CLIENT.get("score_now_date", "") + "  ·  and climbing", size=11, color=FAINT, align=PP_ALIGN.CENTER)
    # Guarantee tie-in
    rect(s, 9.0, 2.7, 3.6, 1.95, fill=CARD2)
    text(s, 9.25, 2.9, 3.1, 1.6, f"Already {delta} of the 20-point lift your guarantee is built on — in just a few weeks.", size=14.5, color=TXT2, line_spacing=1.2, anchor=MSO_ANCHOR.MIDDLE)
    # ── Why it climbed ──
    text(s, 0.9, 4.95, 8, 0.35, "WHAT MOVED IT", size=12, color=GREEN, bold=True)
    for i, (name, jump, why) in enumerate(CLIENT.get("score_drivers", [])):
        x = 0.9 + i * 3.95
        rect(s, x, 5.35, 3.7, 1.35, fill=CARD)
        text(s, x + 0.25, 5.5, 2.4, 0.4, name, size=14, bold=True)
        text(s, x + 2.55, 5.5, 1.0, 0.4, jump, size=14, bold=True, color=GREEN, align=PP_ALIGN.RIGHT)
        text(s, x + 0.25, 5.95, 3.25, 0.7, why, size=11.5, color=GREY, line_spacing=1.1)

# ═══ 8. NEXT: BACKLINKS ═══
s = slide(); accent_bar(s); heading(s, "NEXT STEPS · 1 OF 2", "Building Authority — Citations & Backlinks")
text(s, 0.72, 2.0, 11.9, 0.6, "Quality over volume: the work that raises your Domain Authority toward ~30 and gets you cited by AI.", size=16, color=GREY)
bullets(s, 0.9, 2.85, 7.2, [
    "Aggressive local citation building + NAP cleanup across the directories that matter",
    CLIENT.get("comparison_placement", "“Best [your service] in [your area]” comparison placements — rank for high-intent searches AND get cited by AI"),
    "High-authority backlinks from real, locally-relevant sites — no spam, no risky tactics",
    "Local press, partner & supplier links for authoritative mentions",
    "A steady monthly cadence — compounding authority that competitors can't shortcut",
], size=14.5)
if CLIENT.get("img_backlinks"):
    picture(s, CLIENT["img_backlinks"], 8.3, 2.95, 4.3, 2.87)

# ═══ 9. NEXT: CONTENT/BLOG ═══
s = slide(); accent_bar(s); heading(s, "NEXT STEPS · 2 OF 2", "Content & Blog — Capture Ready-to-Buy Searches")
text(s, 0.72, 2.0, 11.9, 0.6, "Shift from curiosity content to buyer-intent content that brings customers through the door.", size=16, color=GREY)
bullets(s, 0.9, 2.95, 7.2, [
    "Target real transactional searches from your Google data, like " + ", ".join(CLIENT["keyword_examples"][:2]),
    "Expand & refresh landing pages as we find new demand",
    "2–4 new posts per month on high-intent topics, refreshed to keep ranking",
    "FAQ content structured for Google snippets and AI answers",
], size=15)
if CLIENT.get("img_content"):
    picture(s, CLIENT["img_content"], 8.3, 2.95, 4.3, 2.87)

# ═══ 10. ROADMAP ═══
s = slide(); accent_bar(s); heading(s, "THE PLAN", "Your 90-Day Roadmap")
phases = [("Month 1  ✓", "Technical foundation, Google Business Profile, homepage rebuild, service & location landing pages"),
          ("Month 2", "Authority backlinks (raise Domain Authority), on-page depth, content cadence"),
          ("Month 3", "Authority push, review growth, measure & iterate")]
for i, (m, d) in enumerate(phases):
    x = 0.7 + i * 4.1
    rect(s, x, 2.4, 3.8, 2.7, fill=CARD)
    rect(s, x, 2.4, 3.8, 0.7, fill=GREEN)
    text(s, x, 2.45, 3.8, 0.6, m, size=18, bold=True, color=DARKTXT, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    text(s, x + 0.3, 3.4, 3.2, 1.5, d, size=15, color=GREY, line_spacing=1.2)
text(s, 0.72, 5.55, 11.9, 0.6, [("Goal:  ", GREY, False, 17), (CLIENT["target"], GREEN, True, 17),
     ("   — backed by our 90-day score guarantee.", GREY, False, 14)])

# ═══ 10b. PROJECTED GROWTH (chart) ═══
if CLIENT.get("current_visits") and CLIENT.get("target_visits"):
    s = slide(); accent_bar(s); heading(s, "THE TRAJECTORY", "Projected Organic Growth")
    cur, tgt = CLIENT["current_visits"], CLIENT["target_visits"]
    labels = ["Now", "Mo 1", "Mo 2", "Mo 3", "Mo 4", "Mo 5", "Mo 6"]
    vals = [round(cur + (tgt - cur) * (i / 6)) for i in range(7)]
    column_chart(s, 1.3, 2.85, 10.7, 2.95, labels, vals, target=tgt, accent_last=True)
    text(s, 0.72, 6.35, 11.9, 0.6, "Illustrative trajectory toward the 500+ monthly-visit goal as on-page, local, and authority work compound — not a guarantee. Backed by our 90-day score-improvement guarantee.", size=12.5, color=FAINT, line_spacing=1.15)

# ═══ 10c. YOUR OPTIONS (priced tiers) ═══
if CLIENT.get("show_tiers"):
    s = slide(); accent_bar(s); heading(s, "YOUR OPTIONS", "Three Ways to Grow")
    for i, (name, tagline, reg, found, feats) in enumerate(CLIENT["tiers"]):
        x = 0.7 + i * 4.1; pop = (i == CLIENT.get("popular_tier", 1))
        rect(s, x, 2.2, 3.8, 4.25, fill=CARD2 if pop else CARD, line=GREEN if pop else None)
        if pop:
            rect(s, x + 1.15, 2.02, 1.5, 0.4, fill=GREEN)
            text(s, x + 1.15, 2.03, 1.5, 0.38, "RECOMMENDED", size=9, color=DARKTXT, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        text(s, x + 0.3, 2.42, 3.2, 0.45, name, size=19, bold=True)
        text(s, x + 0.3, 2.87, 3.2, 0.32, tagline, size=12, color=GREEN, bold=True)
        if reg != found:   # show the discount ("was $X")
            text(s, x + 0.3, 3.24, 3.2, 0.28, f"reg. ${reg}/mo", size=11, color=FAINT)
        text(s, x + 0.3, 3.5, 3.2, 0.6, [(f"${found}", GREEN, True, 29), ("/mo", GREY, False, 14)])
        bullets(s, x + 0.3, 4.3, 3.3, feats, size=10.5, marker="✓")
    text(s, 0.72, 6.62, 11.9, 0.45, CLIENT.get("founding_note", ""), size=12, color=GREEN, bold=True, align=PP_ALIGN.CENTER)

# ═══ 11. GUARANTEE ═══
s = slide(green_corner=True); accent_bar(s)
text(s, 0.7, 2.1, 12, 0.5, "OUR PROMISE", size=15, color=GREEN, bold=True, align=PP_ALIGN.CENTER)
text(s, 1.0, 2.7, 11.3, 1.2, "The 90-Day Results-or-Refund Guarantee", size=34, bold=True, align=PP_ALIGN.CENTER)
text(s, 1.5, 4.1, 10.3, 1.4, "If your PracticeRank Score doesn't improve by 20+ points in 90 days, we refund your monthly fees — and you keep everything we built. Month-to-month. No long-term contracts.",
     size=18, color=GREY, align=PP_ALIGN.CENTER, line_spacing=1.25)

# ═══ 12. CLOSE ═══
s = slide(green_corner=True); accent_bar(s)
if os.path.exists(LOGO):
    s.shapes.add_picture(LOGO, Inches(6.17), Inches(0.9), height=Inches(1.0))
text(s, 1.0, 2.4, 11.3, 0.9, "Let's grow your visibility.", size=38, bold=True, align=PP_ALIGN.CENTER)
text(s, 1.0, 3.5, 11.3, 0.6, "Found everywhere your customers search — Google, Maps, and AI.", size=18, color=GREY, align=PP_ALIGN.CENTER)
text(s, 1.0, 4.7, 11.3, 0.5, [("Dan Toone", GREEN, True, 18), ("  ·  Client Relations Manager", GREY, False, 18)], align=PP_ALIGN.CENTER)
text(s, 1.0, 5.15, 11.3, 0.5, [("Kody Doherty", GREEN, True, 18), ("  ·  Chief Technology Officer", GREY, False, 18)], align=PP_ALIGN.CENTER)
text(s, 1.0, 6.2, 11.3, 0.4, "practicerank.ai  ·  kdoherty@practicerank.ai", size=14, color=GREY, align=PP_ALIGN.CENTER)

_safe = CLIENT["name"].replace(" ", "-").replace("/", "-")
_out = _args.out or os.path.join(os.getcwd(), "PracticeRank-SEO-Strategy-%s.pptx" % _safe)
_outdir = os.path.dirname(os.path.abspath(_out))
os.makedirs(_outdir, exist_ok=True)
prs.save(_out)
print("saved %s  (%d slides, %d kb)" % (_out, len(prs.slides._sldIdLst), os.path.getsize(_out) // 1024))
