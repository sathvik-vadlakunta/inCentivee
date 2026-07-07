#!/usr/bin/env python3
"""Static generator for the SourceNow Supplier Marketplace SEO/AEO pages.

Builds the new pages (services, contact, blog) into dist/ with a design system
that matches the live Webflow site's tokens (white bg, Inter, brand blue
#2695ec / midnight purple #211056), a shared responsive header/footer, and
per-page SEO head + JSON-LD. Also rewrites the cloned homepage's nav links so
navigation is unified across the site.

Run:  python3 sites/supplier-marketplace/build.py
"""
import html
import os
import re
import shutil

DIST = os.path.join(os.path.dirname(__file__), "dist")
SITE = "https://supplier-marketplace.webflow.io"  # swap for production domain later

# Real brand assets + on-brand imagery (the site's own Webflow CDN files).
CDN = "https://cdn.prod.website-files.com/6942bb5373314df95a6fdae1/"
LOGO = CDN + "695d577b4c7fbfe169fd9719_logo.svg"
IMG = {
    "networking": CDN + "695d6cc54d381096ce1137c1_acogida-de-sesiones-de-redes-virtuales-ar-generativo-ai.jpg",
    "business": CDN + "695d6ce236be4186ed788955_business-work-concept%201.png",
    "office": CDN + "6942bb5473314df95a6fdc34_Office%20Image.webp",
    "users": CDN + "6942bb5473314df95a6fdc36_User%20Group%20(1).webp",
    "strategy": CDN + "6942bb5473314df95a6fde74_Strategy.webp",
    "discover": CDN + "6942bb5473314df95a6fde75_Discover.webp",
    "optimize": CDN + "6942bb5473314df95a6fde73_Optimize.webp",
}

NAV = [
    ("For Companies", "/for-companies"),
    ("For Suppliers", "/for-suppliers"),
    ("How It Works", "/how-it-works"),
    ("Verification", "/verification-compliance"),
    ("Pricing", "/pricing"),
    ("Blog", "/blog"),
    ("Contact", "/contact"),
]

CSS = """
:root{
  --ink:#111;--body:#474747;--muted:#6b7280;--brand:#2695c8;--brand-dark:#1f7ba7;
  --deep:#211056;--deep-2:#170939;--peach:#ffedcd;--lightblue:#e5f0fb;
  --line:#e6e6e6;--bg:#fff;--soft:#f7f9fc;--radius:16px;--max:1120px;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;font-family:Inter,system-ui,-apple-system,sans-serif;color:var(--body);
  background:var(--bg);line-height:1.6;font-size:17px;-webkit-font-smoothing:antialiased}
h1,h2,h3,h4{color:var(--ink);line-height:1.15;margin:0 0 .5em;font-weight:800;letter-spacing:-.02em;text-wrap:balance}
h1{font-size:clamp(2rem,5vw,3.25rem)}
h2{font-size:clamp(1.5rem,3.5vw,2.25rem)}
h3{font-size:1.25rem}
p{margin:0 0 1rem}
a{color:var(--brand);text-decoration:none}
a:hover{text-decoration:underline}
img{max-width:100%;height:auto}
.container{max-width:var(--max);margin:0 auto;padding:0 22px}
.section{padding:72px 0}
.section.soft{background:var(--soft)}
.eyebrow{color:var(--brand);font-weight:700;text-transform:uppercase;letter-spacing:.08em;font-size:.8rem;margin-bottom:.6rem}
.lead{font-size:1.2rem;color:var(--body);max-width:70ch}
.btn{display:inline-block;background:var(--brand);color:#fff;font-weight:700;padding:14px 26px;
  border-radius:999px;border:0;cursor:pointer;transition:background .15s;font-size:1rem}
.btn:hover{background:var(--brand-dark);text-decoration:none}
.btn.ghost{background:transparent;color:var(--ink);border:1.5px solid var(--line)}
.btn.ghost:hover{border-color:var(--brand);color:var(--brand);background:transparent}
.btn.light{background:#fff;color:var(--deep)}
.actions{display:flex;gap:14px;flex-wrap:wrap;margin-top:24px}
/* header — dark to match the primary site's hero nav + show the real logo */
.site-head{position:sticky;top:0;z-index:50;background:var(--deep-2);
  border-bottom:1px solid rgba(255,255,255,.08)}
.nav{display:flex;align-items:center;justify-content:space-between;height:74px}
.brand{display:flex;align-items:center;gap:9px}
.brand img{height:29px;width:auto;display:block}
.brand:hover{text-decoration:none}
.nav-links{display:flex;align-items:center;gap:26px;list-style:none;margin:0;padding:0}
.nav-links a{color:#e9e6f5;font-weight:600;font-size:.95rem}
.nav-links a:hover{color:#fff;text-decoration:none}
.nav-links a.on{color:#5cc8f0}
.nav-cta{display:flex;align-items:center;gap:14px}
.hamburger{display:none;background:none;border:0;cursor:pointer;padding:8px;font-size:1.5rem;color:#fff}
/* hero */
.hero{padding:84px 0 64px;background:radial-gradient(1200px 400px at 80% -10%,var(--lightblue),transparent)}
.hero .lead{margin-top:14px}
.badge{display:inline-block;background:var(--lightblue);color:var(--deep);font-weight:700;
  font-size:.8rem;padding:6px 14px;border-radius:999px;margin-bottom:18px}
/* grid + cards */
.grid{display:grid;gap:22px;grid-template-columns:repeat(auto-fit,minmax(250px,1fr))}
.card{background:#fff;border:1px solid var(--line);border-radius:var(--radius);padding:26px}
.card h3{margin-bottom:.4rem}
.card .ic{width:44px;height:44px;border-radius:12px;background:var(--lightblue);display:flex;
  align-items:center;justify-content:center;font-size:1.4rem;margin-bottom:14px}
.steps{counter-reset:s;display:grid;gap:20px;grid-template-columns:repeat(auto-fit,minmax(240px,1fr))}
.step{position:relative;padding:26px;border:1px solid var(--line);border-radius:var(--radius);background:#fff}
.step::before{counter-increment:s;content:counter(s);display:flex;align-items:center;justify-content:center;
  width:38px;height:38px;border-radius:50%;background:var(--deep);color:#fff;font-weight:800;margin-bottom:14px}
/* cta band */
.cta-band{background:linear-gradient(135deg,var(--deep),var(--deep-2));color:#fff;border-radius:24px;
  padding:48px;text-align:center}
.cta-band h2{color:#fff}
.cta-band p{color:#d7d3ea;max-width:60ch;margin:0 auto 8px}
/* faq */
.faq{max-width:820px}
.faq details{border:1px solid var(--line);border-radius:12px;padding:4px 20px;margin-bottom:12px;background:#fff}
.faq summary{cursor:pointer;font-weight:700;color:var(--ink);padding:14px 0;list-style:none}
.faq summary::-webkit-details-marker{display:none}
.faq summary::after{content:"+";float:right;color:var(--brand);font-size:1.3rem;line-height:1}
.faq details[open] summary::after{content:"–"}
.faq p{padding-bottom:14px;margin:0}
/* blog */
.post-grid{display:grid;gap:26px;grid-template-columns:repeat(auto-fit,minmax(300px,1fr))}
.post-card{border:1px solid var(--line);border-radius:var(--radius);padding:26px;background:#fff;display:flex;flex-direction:column}
.post-card .tag{color:var(--brand);font-weight:700;font-size:.78rem;text-transform:uppercase;letter-spacing:.06em}
.post-card h3{margin:.5rem 0}
.post-card a.more{margin-top:auto;font-weight:700}
.article{max-width:760px;margin:0 auto}
.article h2{margin-top:1.6em}
.article ul{padding-left:1.2em}
.article li{margin-bottom:.5em}
.meta{color:var(--muted);font-size:.9rem;margin-bottom:1.5rem}
/* contact */
.form{display:grid;gap:16px;max-width:560px}
.form label{font-weight:700;color:var(--ink);font-size:.9rem;display:block;margin-bottom:6px}
.form input,.form textarea{width:100%;padding:13px 15px;border:1px solid var(--line);border-radius:10px;
  font:inherit;font-size:1rem}
.form input:focus,.form textarea:focus{outline:2px solid var(--brand);border-color:var(--brand)}
/* footer */
.site-foot{background:var(--deep-2);color:#c9c4e0;padding:56px 0 30px}
.site-foot a{color:#c9c4e0}
.site-foot a:hover{color:#fff}
.foot-grid{display:grid;gap:32px;grid-template-columns:2fr 1fr 1fr;margin-bottom:32px}
.site-foot h4{color:#fff;font-size:.95rem;margin-bottom:12px}
.site-foot ul{list-style:none;padding:0;margin:0;display:grid;gap:8px}
.foot-bottom{border-top:1px solid rgba(255,255,255,.12);padding-top:20px;font-size:.85rem;color:#9a92bd}
/* slimmer header CTA (was too chunky) */
.nav-cta .btn{padding:9px 18px;font-size:.9rem}
/* split hero with image — kills the "wall of white" on service pages */
.hero-split{display:grid;grid-template-columns:1.06fr .94fr;gap:48px;align-items:center}
.hero-media img{width:100%;border-radius:22px;aspect-ratio:4/3;object-fit:cover;
  box-shadow:0 34px 70px -28px rgba(33,16,86,.45);display:block}
/* motion */
.card,.step,.post-card{transition:transform .2s ease,box-shadow .2s ease,border-color .2s ease}
.card:hover,.step:hover{transform:translateY(-4px);box-shadow:0 20px 44px -26px rgba(33,16,86,.4);border-color:#cfe3f4}
.post-card:hover{transform:translateY(-4px);box-shadow:0 20px 44px -26px rgba(33,16,86,.4)}
.btn{transition:background .15s ease,transform .15s ease,box-shadow .15s ease}
.btn:hover{transform:translateY(-1px);box-shadow:0 10px 24px -12px rgba(38,149,200,.6)}
.chip{transition:.15s ease}
@media (prefers-reduced-motion:no-preference){
  .reveal{opacity:0;transform:translateY(20px);transition:opacity .65s ease,transform .65s ease}
  .reveal.in{opacity:1;transform:none}
  .hero-copy>*,.blog-hero .container>*,.contact-hero .container>*{animation:heroIn .7s ease both}
  .hero-copy>*:nth-child(2),.blog-hero .container>*:nth-child(2){animation-delay:.07s}
  .hero-copy>*:nth-child(3),.blog-hero .container>*:nth-child(3){animation-delay:.14s}
  .hero-copy>*:nth-child(4){animation-delay:.21s}
  .hero-media img{animation:heroImg .8s ease both}
  @keyframes heroIn{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:none}}
  @keyframes heroImg{from{opacity:0;transform:translateY(24px) scale(.98)}to{opacity:1;transform:none}}
}
@media(max-width:860px){.hero-split{grid-template-columns:1fr;gap:30px}}
/* blog + service page hero (full-bleed dark image + overlay) */
.blog-hero,.page-hero{position:relative;color:#fff;padding:96px 0 84px;background:var(--deep-2);overflow:hidden}
.page-hero{padding:104px 0 96px}
.blog-hero .bg,.page-hero .bg{position:absolute;inset:0;background-size:cover;background-position:center;opacity:.35}
.blog-hero::after,.page-hero::after{content:"";position:absolute;inset:0;
  background:linear-gradient(180deg,rgba(23,9,57,.55),rgba(23,9,57,.9))}
.blog-hero .container,.page-hero .container{position:relative;z-index:2}
.blog-hero h1,.page-hero h1{color:#fff}
.blog-hero .lead,.page-hero .lead{color:#d7d3ea}
.blog-hero .badge,.page-hero .badge{background:rgba(255,255,255,.15);color:#fff}
.page-hero .lead{max-width:64ch}
/* buttons on the dark hero */
.page-hero .btn.ghost{background:transparent;color:#fff;border-color:rgba(255,255,255,.45)}
.page-hero .btn.ghost:hover{border-color:#fff;color:#fff;background:rgba(255,255,255,.08)}
/* search + chips */
.blsearch{position:relative;max-width:520px;margin:22px 0 8px}
.blsearch input{width:100%;padding:14px 18px 14px 44px;border-radius:999px;border:1px solid var(--line);
  font:inherit;font-size:1rem;background:#fff}
.blsearch input:focus{outline:2px solid var(--brand);border-color:var(--brand)}
.blsearch svg{position:absolute;left:16px;top:50%;transform:translateY(-50%);opacity:.5}
.chips{display:flex;flex-wrap:wrap;gap:10px;margin:14px 0 6px}
.chip{border:1px solid #cfe3f4;background:#fff;color:var(--deep);font-weight:600;font-size:13px;
  padding:8px 16px;border-radius:999px;cursor:pointer;transition:.15s;white-space:nowrap}
.chip:hover{border-color:var(--brand);color:var(--brand)}
.chip.on{background:var(--deep);color:#fff;border-color:var(--deep)}
/* blog cards w/ cover image */
.post-card{padding:0;overflow:hidden}
.post-card .cover{display:block;aspect-ratio:16/9;background-size:cover;background-position:center;background-color:var(--lightblue)}
.post-card .pc-body{padding:22px 24px;display:flex;flex-direction:column;flex:1}
.post-card h3{margin:.4rem 0}
.no-results{display:none;text-align:center;color:var(--muted);padding:40px 0}
/* article cover */
.article .cover{width:100%;aspect-ratio:16/8;object-fit:cover;border-radius:16px;margin-bottom:26px}
/* pricing */
.price-grid{display:grid;gap:24px;grid-template-columns:repeat(3,1fr);align-items:stretch;margin-top:28px}
.tier{border:1px solid var(--line);border-radius:20px;padding:32px 28px;background:#fff;
  display:flex;flex-direction:column;position:relative}
.tier.pop{border:2px solid var(--brand);box-shadow:0 26px 64px -30px rgba(38,149,200,.55)}
.tier .flag{position:absolute;top:-13px;left:50%;transform:translateX(-50%);background:var(--brand);
  color:#fff;font-size:.72rem;font-weight:700;letter-spacing:.05em;text-transform:uppercase;
  padding:6px 15px;border-radius:999px;white-space:nowrap}
.tier.trust .flag{background:var(--deep)}
.tier h3{margin:0;font-size:1.35rem}
.tier .price{font-size:2.2rem;font-weight:800;color:var(--ink);margin:12px 0 2px;letter-spacing:-.02em}
.tier .price span{font-size:.95rem;font-weight:600;color:var(--muted)}
.tier .annual{font-size:.85rem;color:var(--muted);margin:0}
.tier .tagline{color:var(--ink);font-weight:700;margin:16px 0 14px}
.tier ul{list-style:none;padding:0;margin:0;display:grid;gap:11px}
.tier li{position:relative;padding-left:26px;font-size:.94rem;line-height:1.5}
.tier li::before{content:"✓";position:absolute;left:0;top:0;color:var(--brand);font-weight:800}
.tier li.plus{font-weight:700;color:var(--ink);padding-left:0}.tier li.plus::before{content:""}
.tier .note{font-size:.85rem;color:var(--muted);margin-top:auto;padding-top:16px}
.tier .btn{width:100%;text-align:center;margin-top:18px}
@media(max-width:920px){.price-grid{grid-template-columns:1fr;max-width:440px;margin-left:auto;margin-right:auto}}
/* contact — colored hero + panel */
.contact-hero{position:relative;color:#fff;background:linear-gradient(135deg,var(--deep),#2b1a6b 60%,var(--brand));
  padding:88px 0 72px;overflow:hidden}
.contact-hero .bg{position:absolute;inset:0;background-size:cover;background-position:center;opacity:.18;mix-blend-mode:luminosity}
.contact-hero .container{position:relative;z-index:2}
.contact-hero h1{color:#fff}.contact-hero .lead{color:#e7e3f6}
.contact-hero .badge{background:rgba(255,255,255,.16);color:#fff}
.contact-grid{display:grid;gap:36px;grid-template-columns:1.25fr 1fr;align-items:start}
.contact-aside{background:var(--lightblue);border-radius:20px;padding:30px}
@media(max-width:860px){
  .nav-links{position:fixed;inset:74px 0 auto 0;background:var(--deep-2);flex-direction:column;
    gap:0;padding:10px 22px 20px;border-bottom:1px solid rgba(255,255,255,.1);display:none}
  .nav-links.open{display:flex}
  .nav-links li{width:100%;border-bottom:1px solid rgba(255,255,255,.08)}
  .nav-links a{display:block;padding:14px 0}
  .hamburger{display:block}
  .section{padding:52px 0}
  .cta-band{padding:36px 22px}
  .foot-grid{grid-template-columns:1fr}
  .contact-grid{grid-template-columns:1fr}
}
"""

MOBILE_JS = """<script>document.addEventListener('click',function(e){
  var b=e.target.closest('[data-nav-toggle]');
  if(b){document.getElementById('navlinks').classList.toggle('open');}
});</script>"""

BLOG_JS = """<script>(function(){
var grid=document.getElementById('blGrid');if(!grid)return;
var cards=[].slice.call(grid.querySelectorAll('.bfilter'));
var chips=[].slice.call(document.querySelectorAll('#blChips .chip'));
var search=document.getElementById('blSearch');var none=document.getElementById('blNone');
var tag='',q='';
function apply(){var n=0;cards.forEach(function(c){
  var okt=!tag||c.getAttribute('data-tag')===tag;
  var okq=!q||c.getAttribute('data-title').indexOf(q)>-1;
  var show=okt&&okq;c.style.display=show?'':'none';if(show)n++;});
  none.style.display=n?'none':'block';}
chips.forEach(function(ch){ch.addEventListener('click',function(){
  tag=ch.getAttribute('data-tag');chips.forEach(function(x){x.classList.toggle('on',x===ch);});apply();});});
var t;search.addEventListener('input',function(){clearTimeout(t);t=setTimeout(function(){q=search.value.trim().toLowerCase();apply();},120);});
var reset=document.getElementById('blReset');if(reset)reset.addEventListener('click',function(){tag='';q='';search.value='';chips.forEach(function(x){x.classList.toggle('on',x.getAttribute('data-tag')==='');});apply();});
document.addEventListener('keydown',function(e){if(e.key==='/'&&document.activeElement!==search){e.preventDefault();search.focus();}});
})();</script>"""

REVEAL_JS = """<script>(function(){
if(!('IntersectionObserver'in window)||matchMedia('(prefers-reduced-motion:reduce)').matches)return;
var io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){e.target.classList.add('in');io.unobserve(e.target);}});},{threshold:.12,rootMargin:'0px 0px -8% 0px'});
function mark(){[].forEach.call(document.querySelectorAll('.card,.step,.post-card,.section>.container>h2,.section>.container>.eyebrow,.cta-band,.faq details'),function(el){el.classList.add('reveal');io.observe(el);});}
if(document.readyState!=='loading')mark();else document.addEventListener('DOMContentLoaded',mark);
})();</script>"""


def head(title, desc, slug, schema_blocks=None, og_type="website"):
    url = SITE + slug
    ld = "".join(
        '<script type="application/ld+json">%s</script>' % b for b in (schema_blocks or []))
    return f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(desc)}"/>
<link rel="canonical" href="{url}"/>
<meta name="robots" content="index, follow, max-image-preview:large"/>
<meta property="og:type" content="{og_type}"/>
<meta property="og:site_name" content="SourceNow Supplier Marketplace"/>
<meta property="og:title" content="{html.escape(title)}"/>
<meta property="og:description" content="{html.escape(desc)}"/>
<meta property="og:url" content="{url}"/>
<meta name="twitter:card" content="summary_large_image"/>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet"/>
<style>{CSS}</style>{ld}
</head><body>"""


def header(active):
    links = "".join(
        f'<li><a href="{href}" class="{"on" if href==active else ""}">{html.escape(label)}</a></li>'
        for label, href in NAV)
    return f"""<header class="site-head"><div class="container nav">
<a href="/" class="brand" aria-label="SourceNow Supplier Marketplace"><img src="{LOGO}" alt="SourceNow Supplier Marketplace"/></a>
<ul class="nav-links" id="navlinks">{links}</ul>
<div class="nav-cta"><a href="/for-companies" class="btn">Find Suppliers</a>
<button class="hamburger" data-nav-toggle aria-label="Menu">☰</button></div>
</div></header>"""


FOOTER = f"""<footer class="site-foot"><div class="container">
<div class="foot-grid">
<div><a href="/" class="brand" style="margin-bottom:14px;display:inline-block"><img src="{LOGO}" alt="SourceNow Supplier Marketplace" style="height:28px"/></a>
<p style="color:#9a92bd;max-width:38ch">The global marketplace for verified temporary-staffing suppliers. Source with confidence, staff faster.</p></div>
<div><h4>Product</h4><ul>
<li><a href="/for-companies">For Companies</a></li>
<li><a href="/for-suppliers">For Suppliers</a></li>
<li><a href="/how-it-works">How It Works</a></li>
<li><a href="/verification-compliance">Verification</a></li></ul></div>
<div><h4>Company</h4><ul>
<li><a href="/blog">Blog</a></li>
<li><a href="/contact">Contact</a></li></ul></div>
</div>
<div class="foot-bottom">© 2026 SourceNow (Distinctive Workforce Solutions). All rights reserved. · Worldwide staffing supplier marketplace.</div>
</div></footer>{MOBILE_JS}{REVEAL_JS}</body></html>"""


def page(slug, title, desc, body, schema=None, active=None, og_type="website"):
    out = head(title, desc, slug, schema, og_type) + header(active or slug) + body + FOOTER
    d = os.path.join(DIST, slug.strip("/"))
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as f:
        f.write(out)
    return slug


def faq_html(items):
    rows = "".join(f"<details><summary>{html.escape(q)}</summary><p>{a}</p></details>" for q, a in items)
    return f'<div class="faq">{rows}</div>'


def faq_schema(items):
    import json
    return json.dumps({
        "@context": "https://schema.org", "@type": "FAQPage",
        "mainEntity": [{"@type": "Question", "name": q,
                        "acceptedAnswer": {"@type": "Answer", "text": re.sub("<[^>]+>", "", a)}}
                       for q, a in items]})


def service_schema(name, desc, slug):
    import json
    return json.dumps({
        "@context": "https://schema.org", "@type": "Service", "serviceType": name,
        "provider": {"@type": "Organization", "name": "SourceNow Supplier Marketplace",
                     "url": SITE + "/"},
        "areaServed": "Worldwide", "url": SITE + slug, "description": desc})


def split_hero(body, img, alt="Temporary staffing supplier marketplace"):
    """Turn a plain <section class="hero"> into a full-bleed dark hero with a
    background image + overlay (same treatment as the blog hero)."""
    m = re.search(r'<section class="hero"><div class="container">(.*?)</div></section>', body, re.S)
    if not m:
        return body
    new = (f'<section class="page-hero"><div class="bg" style="background-image:url(\'{img}\')"></div>'
           f'<div class="container">{m.group(1)}</div></section>')
    return body[:m.start()] + new + body[m.end():]


def cta_band(head, sub, btn="Find Suppliers", href="/for-companies"):
    return f"""<div class="section"><div class="container"><div class="cta-band">
<h2>{head}</h2><p>{sub}</p>
<div style="margin-top:20px"><a href="{href}" class="btn light">{btn}</a></div></div></div></div>"""


# ---------------------------------------------------------------------------
# PAGES
# ---------------------------------------------------------------------------

def build_for_companies():
    faqs = [
        ("How do I find staffing suppliers on the marketplace?",
         "Search the marketplace and filter verified suppliers by industry, location, capability, and performance, then connect directly — no cold outreach or scattered spreadsheets."),
        ("Are the staffing suppliers vetted?",
         "Yes. Every supplier is pre-vetted against SourceNow verification and compliance standards, so you source from a curated network you can trust."),
        ("How much does it cost to find suppliers?",
         "Companies can find and connect with staffing suppliers for free."),
        ("Does it work outside the US?",
         "Yes — the marketplace is worldwide and not limited to a single region."),
    ]
    body = f"""
<section class="hero"><div class="container">
<span class="badge">For companies &amp; staffing buyers</span>
<h1>Find &amp; Source Verified Temporary Staffing Suppliers</h1>
<p class="lead">Source pre-vetted staffing suppliers worldwide from one marketplace. Filter by industry, capability, and performance, cut risk with compliance-backed verification, and staff faster — without the manual outreach.</p>
<div class="actions"><a href="/contact" class="btn">Find Suppliers for Free</a><a href="/how-it-works" class="btn ghost">See how it works</a></div>
</div></section>

<section class="section"><div class="container">
<div class="eyebrow">Why source here</div>
<h2>Everything you need to source with confidence</h2>
<div class="grid" style="margin-top:32px">
<div class="card"><div class="ic">✅</div><h3>A curated, pre-vetted network</h3><p>Access staffing suppliers backed by SourceNow's verification and compliance standards — so you source with confidence, not guesswork.</p></div>
<div class="card"><div class="ic">🎯</div><h3>Filter to the right partner fast</h3><p>Find suppliers by industry, location, capabilities, and performance — no endless emails or manual outreach.</p></div>
<div class="card"><div class="ic">🛡️</div><h3>Less risk, more confidence</h3><p>A compliance-backed platform that helps ensure supplier credentials, documentation, and standards are consistently maintained.</p></div>
<div class="card"><div class="ic">👁️</div><h3>Full visibility &amp; control</h3><p>Manage supplier interactions, activity, and performance in one place — real-time insight across your entire sourcing process.</p></div>
</div></div></section>

<section class="section soft"><div class="container">
<div class="eyebrow">From search to supplier</div>
<h2>Sourcing staffing suppliers, simplified</h2>
<div class="steps" style="margin-top:32px">
<div class="step"><h3>Search &amp; filter</h3><p>Browse verified suppliers and narrow by industry, location, capability, and performance.</p></div>
<div class="step"><h3>Evaluate with confidence</h3><p>Review pre-vetted suppliers with compliance-backed credentials and documentation.</p></div>
<div class="step"><h3>Connect &amp; manage</h3><p>Reach out and manage every interaction, activity, and performance metric in one platform.</p></div>
</div></div></section>

<section class="section"><div class="container">
<div class="eyebrow">Questions</div><h2>Frequently asked</h2>
<div style="margin-top:26px">{faq_html(faqs)}</div>
</div></section>
{cta_band("Start sourcing verified staffing suppliers", "Find and connect with pre-vetted staffing suppliers worldwide — free for companies.", "Find Suppliers for Free", "/contact")}
"""
    return page("/for-companies",
                "Find Verified Temporary Staffing Suppliers — Source Faster, Cut Risk | SourceNow",
                "Source pre-vetted temporary-staffing suppliers worldwide. Filter by industry & capability, cut risk with compliance-backed verification, and staff faster — free for companies.",
                split_hero(body, IMG["business"]),
                schema=[service_schema("Staffing supplier sourcing",
                        "Find and source verified temporary-staffing suppliers worldwide.", "/for-companies"),
                        faq_schema(faqs)])


def build_for_suppliers():
    faqs = [
        ("How do staffing agencies get listed?",
         "Request a listing and, once verified against SourceNow's standards, your agency becomes discoverable to companies actively sourcing suppliers."),
        ("Who will see my listing?",
         "Companies searching the marketplace for staffing partners by industry, location, capability, and performance — buyers with real sourcing intent."),
        ("How is this better than cold outreach?",
         "Instead of manual outreach and referrals, you gain visibility to inbound demand — the buyers are already looking for suppliers like you."),
        ("Is the marketplace global?",
         "Yes. Suppliers and buyers connect worldwide, not just in one region."),
    ]
    body = f"""
<section class="hero"><div class="container">
<span class="badge">For staffing suppliers &amp; agencies</span>
<h1>List Your Staffing Agency &amp; Win New Clients</h1>
<p class="lead">Get discovered by companies actively sourcing staffing partners. Replace fragmented cold outreach and referrals with inbound demand — grow your staffing business on the world's largest supplier marketplace.</p>
<div class="actions"><a href="/contact" class="btn">Get Listed as a Supplier</a><a href="/verification-compliance" class="btn ghost">How verification works</a></div>
</div></section>

<section class="section"><div class="container">
<div class="eyebrow">The supplier growth challenge</div>
<h2>Traditional growth is fragmented and hard to scale</h2>
<p class="lead" style="margin-top:10px">Staffing agencies struggle to consistently connect with new clients, limited visibility reduces the chance of winning business, and growth still leans on manual outreach and referrals. The marketplace fixes that.</p>
<div class="grid" style="margin-top:32px">
<div class="card"><div class="ic">📣</div><h3>Get found by real buyers</h3><p>Be discovered by companies searching for staffing partners by industry, capability, and performance.</p></div>
<div class="card"><div class="ic">📈</div><h3>Grow without cold outreach</h3><p>Turn limited visibility into inbound demand — no more relying solely on referrals and manual prospecting.</p></div>
<div class="card"><div class="ic">🤝</div><h3>Build trust with verification</h3><p>A verified, compliance-backed listing signals credibility to buyers evaluating suppliers.</p></div>
</div></div></section>

<section class="section soft"><div class="container">
<div class="eyebrow">Getting listed</div><h2>Three steps to inbound demand</h2>
<div class="steps" style="margin-top:32px">
<div class="step"><h3>Request a listing</h3><p>Tell us about your agency, industries, and capabilities.</p></div>
<div class="step"><h3>Get verified</h3><p>We confirm credentials and documentation against SourceNow's compliance standards.</p></div>
<div class="step"><h3>Win new clients</h3><p>Appear in buyer searches and connect with companies ready to source.</p></div>
</div></div></section>

<section class="section"><div class="container">
<div class="eyebrow">Questions</div><h2>Frequently asked</h2>
<div style="margin-top:26px">{faq_html(faqs)}</div>
</div></section>
{cta_band("Grow your staffing business today", "List your agency and get discovered by companies sourcing staffing suppliers worldwide.", "Get Listed as a Supplier", "/contact")}
"""
    return page("/for-suppliers",
                "List Your Staffing Agency — Win New Clients on SourceNow's Marketplace",
                "Get your staffing agency listed on the world's largest supplier marketplace. Be discovered by companies sourcing suppliers, and grow without cold outreach.",
                split_hero(body, IMG["users"]),
                schema=[service_schema("Staffing supplier listing",
                        "List a staffing agency to win new clients on the SourceNow marketplace.", "/for-suppliers"),
                        faq_schema(faqs)])


def build_how_it_works():
    body = f"""
<section class="hero"><div class="container">
<span class="badge">How it works</span>
<h1>From Search to Supplier — Made Simple</h1>
<p class="lead">SourceNow Supplier Marketplace connects companies with verified staffing suppliers through one centralized platform built for speed, trust, and visibility.</p>
<div class="actions"><a href="/for-companies" class="btn">I'm sourcing suppliers</a><a href="/for-suppliers" class="btn ghost">I'm a supplier</a></div>
</div></section>

<section class="section"><div class="container">
<div class="eyebrow">The process</div><h2>One marketplace, three simple steps</h2>
<div class="steps" style="margin-top:32px">
<div class="step"><h3>Discover</h3><p>Search a curated network of pre-vetted staffing suppliers and filter by industry, location, capability, and performance.</p></div>
<div class="step"><h3>Verify &amp; evaluate</h3><p>Every supplier is backed by SourceNow verification and compliance standards, so you evaluate credible partners with confidence.</p></div>
<div class="step"><h3>Connect &amp; manage</h3><p>Connect directly and manage interactions, activity, and performance in one place — with full visibility across sourcing.</p></div>
</div></div></section>

<section class="section soft"><div class="container">
<h2>Built for both sides of the marketplace</h2>
<div class="grid" style="margin-top:28px">
<div class="card"><div class="ic">🏢</div><h3>For companies</h3><p>Source faster, cut risk, and gain full visibility — finding suppliers is free.</p><p><a href="/for-companies">Find suppliers →</a></p></div>
<div class="card"><div class="ic">🧩</div><h3>For suppliers</h3><p>Get listed, get discovered, and win new clients without manual outreach.</p><p><a href="/for-suppliers">Get listed →</a></p></div>
</div></div></section>
{cta_band("Turn staffing challenges into smarter connections", "Connect with verified staffing suppliers, reduce risk, and manage sourcing with full visibility — all in one platform.")}
"""
    return page("/how-it-works",
                "How the Staffing Supplier Marketplace Works — From Search to Supplier | SourceNow",
                "See how SourceNow connects companies with verified temporary-staffing suppliers: discover, verify, and connect in one centralized marketplace built for speed and trust.",
                split_hero(body, IMG["office"]))


def build_verification():
    faqs = [
        ("How are staffing suppliers verified?",
         "Suppliers are pre-vetted against SourceNow's verification and compliance standards, which help ensure credentials, documentation, and standards are consistently maintained."),
        ("What does 'compliance-backed' mean for buyers?",
         "It means you source from suppliers whose credentials and documentation are checked and maintained — reducing operational and compliance risk."),
        ("Does verification slow down sourcing?",
         "No — verification is what lets you move faster. Because suppliers are pre-vetted, you skip the manual due-diligence and connect with confidence."),
    ]
    body = f"""
<section class="hero"><div class="container">
<span class="badge">Verification &amp; compliance</span>
<h1>Staffing Supplier Verification &amp; Compliance</h1>
<p class="lead">Every supplier on the marketplace is pre-vetted against SourceNow's verification and compliance standards — so companies source from partners they can trust and agencies stand out as credible.</p>
<div class="actions"><a href="/for-companies" class="btn">Source verified suppliers</a></div>
</div></section>

<section class="section"><div class="container">
<div class="eyebrow">What verification covers</div>
<h2>Trust, built into the marketplace</h2>
<div class="grid" style="margin-top:32px">
<div class="card"><div class="ic">📄</div><h3>Credentials &amp; documentation</h3><p>Supplier credentials and documentation are checked and kept current, so buyers aren't chasing paperwork.</p></div>
<div class="card"><div class="ic">🛡️</div><h3>Consistent standards</h3><p>Suppliers are held to SourceNow's compliance standards, helping ensure reliable, repeatable partnerships.</p></div>
<div class="card"><div class="ic">⚖️</div><h3>Reduced operational risk</h3><p>Compliance-backed sourcing lowers the risk of partnering with unvetted or non-compliant suppliers.</p></div>
</div></div></section>

<section class="section soft"><div class="container">
<div class="eyebrow">Questions</div><h2>Frequently asked</h2>
<div style="margin-top:26px">{faq_html(faqs)}</div>
</div></section>
{cta_band("Source suppliers you can trust", "Work with pre-vetted, compliance-backed staffing suppliers and reduce risk across your sourcing.")}
"""
    return page("/verification-compliance",
                "Staffing Supplier Verification & Compliance — Vetted Partners You Can Trust | SourceNow",
                "Learn how SourceNow verifies staffing suppliers: credentials, documentation, and compliance standards that reduce risk and let you source with confidence.",
                split_hero(body, IMG["networking"]),
                schema=[faq_schema(faqs)])


def build_contact():
    import json
    schema = json.dumps({
        "@context": "https://schema.org", "@type": "ContactPage",
        "name": "Contact SourceNow Supplier Marketplace", "url": SITE + "/contact",
        "about": {"@type": "Organization", "name": "SourceNow Supplier Marketplace",
                  "legalName": "Distinctive Workforce Solutions", "areaServed": "Worldwide"}})
    body = f"""
<section class="contact-hero"><div class="bg" style="background-image:url('{IMG['office']}')"></div>
<div class="container"><span class="badge">Contact</span>
<h1>Let's Talk Staffing</h1>
<p class="lead">Sourcing suppliers, getting your agency listed, or want a demo of the marketplace? Send us a note and the SourceNow team will get back to you.</p>
</div></section>

<section class="section"><div class="container contact-grid">
<form class="form" action="https://formspree.io/f/REPLACE_WITH_FORM_ID" method="POST">
  <div><label for="name">Name</label><input id="name" name="name" required/></div>
  <div><label for="company">Company</label><input id="company" name="company"/></div>
  <div><label for="email">Work email</label><input id="email" name="email" type="email" required/></div>
  <div><label for="role">I am a…</label><input id="role" name="role" placeholder="Company sourcing suppliers / Staffing supplier"/></div>
  <div><label for="msg">How can we help?</label><textarea id="msg" name="message" rows="5"></textarea></div>
  <button class="btn" type="submit">Send message</button>
  <p style="font-size:.8rem;color:var(--muted)">By submitting you agree to be contacted about the SourceNow Supplier Marketplace.</p>
</form>
<div class="contact-aside">
  <h3>Prefer email?</h3>
  <p>Reach the team directly and we'll route you to the right place.</p>
  <p><a href="mailto:hello@sourcenow.com">hello@sourcenow.com</a></p>
  <h3 style="margin-top:26px">Two ways to start</h3>
  <p><strong>Companies:</strong> <a href="/for-companies">find verified suppliers for free →</a></p>
  <p><strong>Suppliers:</strong> <a href="/for-suppliers">get listed &amp; win clients →</a></p>
</div>
</div></section>
"""
    return page("/contact",
                "Contact SourceNow Supplier Marketplace — Get in Touch or Request a Demo",
                "Contact the SourceNow team to source verified staffing suppliers, list your staffing agency, or request a demo of the global supplier marketplace.",
                body, schema=[schema])


BLOG_POSTS = [
    ("how-to-find-and-vet-temporary-staffing-suppliers",
     "How to Find and Vet Temporary Staffing Suppliers (2026 Guide)",
     "A practical guide to finding and vetting temporary-staffing suppliers — where to look, what to verify, and how a marketplace cuts sourcing time and risk.",
     "Sourcing", """
<p>Finding the right temporary-staffing supplier is equal parts discovery and due diligence. Do it well and you fill roles faster with partners you trust; do it poorly and you inherit compliance risk and slow time-to-fill. Here's a practical framework.</p>
<h2>1. Define what "right" looks like</h2>
<p>Before you search, get specific: which industries and roles, what geographies, what volume, and what performance bar. The tighter your criteria, the faster you can filter suppliers that actually fit.</p>
<h2>2. Go where suppliers are already vetted</h2>
<p>Cold outreach and referrals are slow and inconsistent. A staffing supplier marketplace lets you filter a curated, pre-vetted network by industry, location, capability, and performance — so you start from qualified partners instead of a blank inbox.</p>
<h2>3. Vet credentials and documentation</h2>
<p>Before you commit, confirm the supplier's credentials, documentation, and compliance standing. On a compliance-backed marketplace this is maintained for you, which is what turns weeks of due diligence into minutes.</p>
<h2>4. Evaluate performance, not just promises</h2>
<p>Look for evidence of reliability — fill rates, responsiveness, and consistency — rather than sales claims. Visibility into supplier activity and performance helps you choose partners that deliver repeatedly.</p>
<h2>5. Keep everything in one place</h2>
<p>Managing suppliers across email threads and spreadsheets is where risk hides. Centralizing interactions, activity, and performance gives you full visibility and control over sourcing.</p>
<p><strong>The short version:</strong> define your criteria, source from a pre-vetted network, verify compliance, judge on performance, and centralize the relationship. That's how you cut both risk and time-to-staffing.</p>
"""),
    ("staffing-supplier-compliance-checklist",
     "Staffing Supplier Compliance Checklist: What to Verify Before You Partner",
     "The staffing supplier compliance checklist buyers should run before partnering — credentials, documentation, and standards that reduce risk.",
     "Compliance", """
<p>Compliance is the difference between a supplier partnership that scales and one that becomes a liability. Use this checklist before you sign.</p>
<h2>Credentials</h2>
<ul><li>Business registration and required licenses for each operating region</li><li>Insurance coverage appropriate to the work and volume</li><li>Any industry-specific certifications your roles require</li></ul>
<h2>Documentation</h2>
<ul><li>Worker eligibility and right-to-work documentation</li><li>Up-to-date contracts and terms</li><li>Records that are current — not expired or missing</li></ul>
<h2>Standards</h2>
<ul><li>Consistent screening and onboarding processes</li><li>Data handling and privacy practices</li><li>A track record of maintaining standards over time, not just at signup</li></ul>
<h2>Make it repeatable</h2>
<p>Running this manually for every supplier is slow. A compliance-backed marketplace pre-vets suppliers against these standards and helps keep credentials and documentation current — so you can source with confidence instead of chasing paperwork.</p>
"""),
    ("vendor-management-for-staffing",
     "Vendor Management for Staffing: Cutting Risk and Time-to-Fill",
     "How modern vendor management for staffing reduces risk and time-to-fill by centralizing supplier discovery, verification, and performance.",
     "Vendor management", """
<p>Staffing vendor management used to mean spreadsheets, email chains, and hope. Modern sourcing centralizes it — and the payoff is lower risk and faster fills.</p>
<h2>The problem with fragmented sourcing</h2>
<p>When supplier discovery, verification, and performance live in different places, visibility disappears. You can't compare partners, risk slips through, and every new role restarts the search.</p>
<h2>Centralize discovery</h2>
<p>Start from a curated network you can filter by industry, location, capability, and performance — instead of rebuilding a supplier list from scratch each time.</p>
<h2>Bake in verification</h2>
<p>Compliance-backed verification means credentials and documentation are maintained, so risk is managed continuously rather than rediscovered at the worst moment.</p>
<h2>Measure performance</h2>
<p>Real-time insight into supplier activity, engagement, and performance lets you double down on reliable partners and cut the ones that don't deliver.</p>
<p>Centralized vendor management is how staffing teams cut time-to-fill without taking on more risk.</p>
"""),
    ("win-staffing-clients-without-cold-outreach",
     "For Staffing Agencies: How to Win More Clients Without Cold Outreach",
     "Staffing agencies can grow without cold outreach by building visibility on a supplier marketplace where buyers are already sourcing.",
     "For suppliers", """
<p>Most staffing agencies grow through referrals and manual outreach — which is exactly why growth is inconsistent. Here's how to turn visibility into inbound demand.</p>
<h2>Why cold outreach caps your growth</h2>
<p>Manual prospecting is slow, competitive, and hard to scale. Agencies consistently cite limited visibility as the top reason they miss out on new business.</p>
<h2>Get in front of buyers with intent</h2>
<p>On a supplier marketplace, companies are already searching for staffing partners by industry, capability, and performance. A listing puts you in front of buyers when they're actively sourcing — not interrupting them when they're not.</p>
<h2>Let verification sell for you</h2>
<p>A verified, compliance-backed listing signals credibility. Buyers evaluating suppliers trust vetted partners, so verification does some of the selling before you ever talk.</p>
<h2>Show performance</h2>
<p>Visibility into your activity and performance helps buyers choose you with confidence. Consistency compounds — reliable delivery earns repeat sourcing.</p>
<p>Trade cold outreach for inbound demand: get listed where the buyers already are.</p>
"""),
    ("what-is-a-staffing-supplier-marketplace",
     "What Is a Staffing Supplier Marketplace (and Why It Beats Manual Sourcing)?",
     "A staffing supplier marketplace connects companies with verified staffing suppliers in one platform — cutting the risk and time of manual sourcing.",
     "Sourcing", """
<p>A staffing supplier marketplace is a platform that connects companies who need temporary staffing with verified staffing suppliers — replacing fragmented, manual sourcing with a single, searchable network.</p>
<h2>How it's different from manual sourcing</h2>
<p>Traditional sourcing means cold outreach, referrals, and scattered spreadsheets. A marketplace centralizes discovery, verification, and relationship management so both sides move faster with less risk.</p>
<h2>What buyers get</h2>
<ul><li>A curated network of pre-vetted, compliance-backed suppliers</li><li>Filtering by industry, location, capability, and performance</li><li>Full visibility into supplier activity and performance</li><li>Faster time-to-staffing with less operational risk</li></ul>
<h2>What suppliers get</h2>
<ul><li>Visibility to companies actively sourcing</li><li>Inbound demand instead of manual outreach</li><li>Credibility through verification</li></ul>
<h2>Why it wins</h2>
<p>Because it turns a slow, risky, fragmented process into a fast, trusted, centralized one. For companies that means confident sourcing; for suppliers it means scalable growth.</p>
"""),
]


POST_IMG = {
    "how-to-find-and-vet-temporary-staffing-suppliers": IMG["office"],
    "staffing-supplier-compliance-checklist": IMG["strategy"],
    "vendor-management-for-staffing": IMG["business"],
    "win-staffing-clients-without-cold-outreach": IMG["users"],
    "what-is-a-staffing-supplier-marketplace": IMG["networking"],
}


def build_blog():
    import json
    cta = cta_band("Ready to source smarter?",
                   "Find verified staffing suppliers — or list your agency — on the SourceNow marketplace.")
    cta_inner = cta[len('<div class="section">'):-len('</div>')]

    # --- posts (with cover image) ---
    for slug, title, desc, tag, content in BLOG_POSTS:
        img = POST_IMG.get(slug, IMG["business"])
        art_schema = json.dumps({
            "@context": "https://schema.org", "@type": "BlogPosting",
            "headline": title, "description": desc, "url": f"{SITE}/blog/{slug}",
            "articleSection": tag, "image": img, "datePublished": "2026-07-01",
            "publisher": {"@type": "Organization", "name": "SourceNow Supplier Marketplace"},
            "mainEntityOfPage": f"{SITE}/blog/{slug}"})
        body = f"""
<section class="section"><div class="container article">
<p class="meta"><a href="/blog">← Blog</a> · {tag}</p>
<h1>{html.escape(title)}</h1>
<img class="cover" src="{img}" alt="{html.escape(title)}" loading="lazy"/>
{content}
<div style="margin-top:40px">{cta_inner}</div>
</div></section>"""
        page(f"/blog/{slug}", f"{title} | SourceNow", desc, body,
             schema=[art_schema], active="/blog", og_type="article")

    # --- index: hero image + search + category chips + filterable cards ---
    tags = []
    for _, _, _, t, _ in BLOG_POSTS:
        if t not in tags:
            tags.append(t)
    chips = '<button class="chip on" data-tag="">All</button>' + "".join(
        f'<button class="chip" data-tag="{html.escape(t.lower())}">{html.escape(t)}</button>' for t in tags)
    cards = "".join(f"""<a class="post-card bfilter" href="/blog/{slug}" data-tag="{html.escape(tag.lower())}" data-title="{html.escape((title + ' ' + desc).lower())}">
<span class="cover" style="background-image:url('{POST_IMG.get(slug, IMG['business'])}')"></span>
<span class="pc-body"><span class="tag">{html.escape(tag)}</span>
<h3>{html.escape(title)}</h3><p>{html.escape(desc)}</p>
<span class="more" style="margin-top:auto;font-weight:700;color:var(--brand)">Read more →</span></span></a>""" for slug, title, desc, tag, _ in BLOG_POSTS)
    blog_schema = json.dumps({
        "@context": "https://schema.org", "@type": "Blog", "url": SITE + "/blog",
        "name": "SourceNow Supplier Marketplace Blog",
        "blogPost": [{"@type": "BlogPosting", "headline": t, "url": f"{SITE}/blog/{s}"}
                     for s, t, _, _, _ in BLOG_POSTS]})
    mag = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#211056" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>'
    body = f"""
<section class="blog-hero"><div class="bg" style="background-image:url('{IMG['networking']}')"></div>
<div class="container"><span class="badge">Blog</span>
<h1>Staffing Sourcing, Vendor Management &amp; Compliance</h1>
<p class="lead">Guides for companies sourcing staffing suppliers and for agencies growing on the marketplace.</p></div></section>
<section class="section"><div class="container">
<div class="blsearch">{mag}<input id="blSearch" type="search" placeholder="Search articles…  (press / )" autocomplete="off" aria-label="Search articles"/></div>
<div class="chips" id="blChips">{chips}</div>
<div class="post-grid" id="blGrid" style="margin-top:24px">{cards}</div>
<div class="no-results" id="blNone">No articles match your search. <button class="chip" id="blReset">Clear filters</button></div>
</div></section>
{BLOG_JS}"""
    page("/blog", "Staffing Sourcing & Vendor Management Blog | SourceNow Marketplace",
         "Guides on finding and vetting staffing suppliers, vendor management, compliance, and growing a staffing agency on the SourceNow marketplace.",
         body, schema=[blog_schema], active="/blog")


HOME_SEO_HEAD = """<!-- PracticeRank SEO/AEO -->
<meta name="robots" content="index, follow, max-image-preview:large"/>
<link rel="canonical" href="{site}/"/>
<meta name="twitter:card" content="summary_large_image"/>
<meta name="twitter:title" content="Temporary Staffing Supplier Marketplace | SourceNow"/>
<meta name="twitter:description" content="Source pre-vetted temporary-staffing suppliers worldwide. Less risk, more visibility, faster time-to-staffing."/>
{schema}"""

# In-place improvements to the original Webflow landing page (we keep its design,
# just fix what breaks on a static export).
HOME_FIXES = """<style id="pr-home-fixes">
/* Webflow hides every [data-w-id] element at opacity:0 until its IX2 engine adds
   .w-mod-ix and animates it in. That engine doesn't run on the static export, so
   the hero + sections were stuck invisible. Reveal them so nothing is ever hidden. */
html.w-mod-js:not(.w-mod-ix) [data-w-id]{opacity:1 !important}
.w-webflow-badge{display:none !important}
/* Our own tasteful scroll-reveal (progressive enhancement: only applied by JS, so
   content is always visible if JS/IO is unavailable). */
@media (prefers-reduced-motion:no-preference){
  .pr-rv{opacity:0 !important;transform:translateY(30px);will-change:opacity,transform;
    transition:opacity .8s cubic-bezier(.16,.84,.44,1),transform .8s cubic-bezier(.16,.84,.44,1)}
  .pr-rv.pr-in{opacity:1 !important;transform:none}
}
/* Hover micro-interactions on cards. */
.home-two-service-cards,.home-two-counter-card{transition:transform .25s ease,box-shadow .25s ease}
.home-two-service-cards:hover{transform:translateY(-6px)}
</style>
<script>(function(){
if(matchMedia('(prefers-reduced-motion:reduce)').matches||!('IntersectionObserver'in window))return;
function ready(fn){if(document.readyState!=='loading')fn();else document.addEventListener('DOMContentLoaded',fn);}
ready(function(){
  // 1) Staggered scroll-reveal on the real content blocks
  var sels=['.sticky-heading','.home-two-sticky-section .w-layout-vflex',
    '.home-two-counter-card','.counter-circle','.home-two-service-cards',
    '.home-two-markting .w-layout-vflex','.cta-two .w-layout-vflex'];
  sels.forEach(function(s){
    [].slice.call(document.querySelectorAll(s)).forEach(function(el,i){
      el.classList.add('pr-rv');el.style.transitionDelay=(Math.min(i,6)*0.09)+'s';});
  });
  var io=new IntersectionObserver(function(es){es.forEach(function(e){
    if(e.isIntersecting){e.target.classList.add('pr-in');io.unobserve(e.target);}});},
    {threshold:.15,rootMargin:'0px 0px -6% 0px'});
  document.querySelectorAll('.pr-rv').forEach(function(el){io.observe(el);});

  // 2) Count-up on the stat numbers (68 / 72 / 70) when the counter enters view
  var sec=document.querySelector('.service-v3-counter,.home-two-counter');
  if(sec){
    var stats=[].slice.call(sec.querySelectorAll('*')).filter(function(el){
      return el.children.length===0 && /^\\s*\\d{1,3}%?\\s*$/.test(el.textContent);});
    var run=false;
    var cio=new IntersectionObserver(function(es){es.forEach(function(e){
      if(e.isIntersecting&&!run){run=true;
        stats.forEach(function(el){
          var m=el.textContent.match(/(\\d{1,3})(%?)/);if(!m)return;
          var target=+m[1],suf=m[2],start=null,dur=1500;el.textContent='0'+suf;
          function step(ts){if(!start)start=ts;var p=Math.min((ts-start)/dur,1);
            el.textContent=Math.round((1-Math.pow(1-p,3))*target)+suf;
            if(p<1)requestAnimationFrame(step);}
          requestAnimationFrame(step);
        });
        cio.disconnect();
      }});},{threshold:.4});
    cio.observe(sec);
  }
});
})();</script>"""


def _replace_hflex_navmenu(h, new_inner):
    """Depth-match and replace the inner HTML of the VISIBLE navbar's
    <div class="w-layout-hflex nav-menu">…</div> (the one users actually see)."""
    key = '<div class="w-layout-hflex nav-menu">'
    i = h.find(key)
    if i < 0:
        return h, False
    j = i + len(key)
    depth = 1
    for m in re.finditer(r'<div\b|</div>', h[j:]):
        if m.group(0) == '</div>':
            depth -= 1
            if depth == 0:
                end = j + m.start()
                return h[:j] + new_inner + h[end:], True
        else:
            depth += 1
    return h, False


def patch_homepage():
    """Own the homepage transform on the fresh clone: inject SEO head + schema,
    then replace the VISIBLE navbar menu with the real page links (styled with
    the template's own visible nav classes)."""
    import json
    p = os.path.join(DIST, "index.html")
    h = open(p, encoding="utf-8").read()

    # --- SEO head ---
    NEW_TITLE = "Temporary Staffing Supplier Marketplace — Source Verified Suppliers | SourceNow"
    NEW_DESC = ("Find and source pre-vetted temporary-staffing suppliers worldwide. Filter by "
                "industry & capability, cut risk with compliance-backed verification, and staff "
                "faster — all in one marketplace.")
    h = re.sub(r"<title>.*?</title>", f"<title>{NEW_TITLE}</title>", h, count=1, flags=re.S)
    h = re.sub(r'(<meta[^>]*name="description"[^>]*content=")[^"]*(")',
               lambda m: m.group(1) + NEW_DESC + m.group(2), h, count=1, flags=re.I)
    hc = open(os.path.join(os.path.dirname(__file__), "seo", "head-code-home.html"),
              encoding="utf-8").read()
    schema = "".join('<script type="application/ld+json">%s</script>' % b
                     for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', hc, re.S))
    if "PracticeRank SEO/AEO" not in h:
        h = h.replace("</head>", HOME_SEO_HEAD.format(site=SITE, schema=schema) + "</head>", 1)

    # --- in-place fixes: reveal stuck IX2 elements + kill Webflow badge ---
    if "pr-home-fixes" not in h:
        h = h.replace("</head>", HOME_FIXES + "</head>", 1)

    # --- visible nav: real page links, styled like the template's own nav items ---
    items = [("Home", "/")] + NAV
    new_inner = "".join(
        f'<div class="dropdown w-dropdown"><div class="dropdown-toggle w-dropdown-toggle">'
        f'<a href="{href}" class="link-block w-inline-block"><div>{html.escape(label)}</div></a>'
        f'</div></div>' for label, href in items)
    h, nav_ok = _replace_hflex_navmenu(h, new_inner)
    h = h.replace('href="/old-home"', 'href="/"')  # brand → home

    open(p, "w", encoding="utf-8").write(h)
    return nav_ok


def pricing_grid():
    """Three supplier tiers — reused on /pricing and the homepage."""
    tiers = [
        dict(name="Free", sub="Basic Access", price="$0", per="/month", annual="",
             flag="", tagline="Get listed and start exploring.",
             feats=["Appear in the Marketplace with a basic profile + short company description",
                    "A limited number of direct client connections per month",
                    "A taste of the analytics dashboard"],
             note="Ideal for suppliers who want to show up and explore before upgrading. No payment method required.",
             cta=("Get Listed Free", "/for-suppliers")),
        dict(name="Premium", sub="", price="$699", per="/mo", annual="or $594/mo billed annually",
             flag="Most Popular", pop=True, plus="Everything in Free, plus:",
             tagline="Show up, stand out, get more connections.",
             feats=["Full company description + logo on your public profile",
                    "Unlimited direct client connections and messaging",
                    "Full analytics dashboard — profile views, engagement, opportunities"],
             note="For established suppliers ready to actively win business in the Marketplace.",
             cta=("Start Premium", "/contact")),
        dict(name="Verified Pro", sub="", price="$999", per="/mo", annual="or $849/mo billed annually",
             flag="Most Trusted", trust=True, plus="Everything in Premium, plus:",
             tagline="Maximum visibility and credibility.",
             feats=["Priority placement — top ranking and featured position in search",
                    "A SourceNow Verified trust badge that signals credibility to buyers"],
             note="For suppliers who want to be the first, most-trusted name buyers see.",
             cta=("Get Verified Pro", "/contact")),
    ]
    cards = []
    for t in tiers:
        cls = "tier" + (" pop" if t.get("pop") else "") + (" trust" if t.get("trust") else "")
        flag = f'<span class="flag">{t["flag"]}</span>' if t["flag"] else ""
        sub = f' <span style="font-weight:600;color:var(--muted);font-size:1rem">· {t["sub"]}</span>' if t["sub"] else ""
        annual = f'<p class="annual">{t["annual"]}</p>' if t["annual"] else ""
        plus = f'<li class="plus">{html.escape(t["plus"])}</li>' if t.get("plus") else ""
        feats = "".join(f"<li>{html.escape(f)}</li>" for f in t["feats"])
        label, href = t["cta"]
        btn_cls = "btn" if t.get("pop") else "btn ghost"
        cards.append(
            f'<div class="{cls}">{flag}<h3>{html.escape(t["name"])}{sub}</h3>'
            f'<div class="price">{t["price"]}<span>{t["per"]}</span></div>{annual}'
            f'<p class="tagline">{html.escape(t["tagline"])}</p>'
            f'<ul>{plus}{feats}</ul>'
            f'<p class="note">{html.escape(t["note"])}</p>'
            f'<a href="{href}" class="{btn_cls}">{html.escape(label)}</a></div>')
    return '<div class="price-grid">' + "".join(cards) + '</div>'


def build_pricing():
    import json
    offers = json.dumps({
        "@context": "https://schema.org", "@type": "Product",
        "name": "SourceNow Supplier Marketplace — Supplier Listing Plans",
        "description": "Supplier listing plans on the SourceNow Supplier Marketplace: Free, Premium, and Verified Pro. Companies source suppliers for free.",
        "brand": {"@type": "Brand", "name": "SourceNow"},
        "offers": [
            {"@type": "Offer", "name": "Free — Basic Access", "price": "0", "priceCurrency": "USD",
             "description": "Basic marketplace profile with a limited number of direct client connections per month."},
            {"@type": "Offer", "name": "Premium", "price": "699", "priceCurrency": "USD",
             "description": "Full public profile, unlimited client connections and messaging, and full analytics. $594/mo billed annually."},
            {"@type": "Offer", "name": "Verified Pro", "price": "999", "priceCurrency": "USD",
             "description": "Priority placement plus a SourceNow Verified trust badge. $849/mo billed annually."},
        ]})
    body = f"""
<section class="page-hero"><div class="bg" style="background-image:url('{IMG['office']}')"></div>
<div class="container"><span class="badge">Supplier plans</span>
<h1>Simple Pricing for Staffing Suppliers</h1>
<p class="lead">List your agency free, then upgrade when you're ready to win more business. Companies always source suppliers for free.</p></div></section>
<section class="section"><div class="container">
{pricing_grid()}
<p style="text-align:center;color:var(--muted);margin-top:24px;font-size:.9rem">Prices in USD. Annual billing saves ~15%. Companies sourcing suppliers pay nothing.</p>
</div></section>
{cta_band("Ready to grow your staffing business?", "Get listed free and start connecting with companies sourcing on the SourceNow marketplace.", btn="Get Listed as a Supplier", href="/for-suppliers")}
"""
    return page("/pricing",
                "Pricing — Supplier Plans | SourceNow Supplier Marketplace",
                "SourceNow supplier plans: Free ($0), Premium ($699/mo or $594 billed annually), and Verified Pro ($999/mo or $849 billed annually). Companies source staffing suppliers for free.",
                body, schema=[offers], active="/pricing")


if __name__ == "__main__":
    os.makedirs(DIST, exist_ok=True)
    build_for_companies()
    build_for_suppliers()
    build_how_it_works()
    build_verification()
    build_contact()
    build_pricing()
    build_blog()
    # copy SEO/AEO files (robots, sitemap, llms) from seo/ -> dist/ root
    seo_dir = os.path.join(os.path.dirname(__file__), "seo")
    for fn in ("robots.txt", "sitemap.xml", "llms.txt", "llms-full.txt"):
        src = os.path.join(seo_dir, fn)
        if os.path.exists(src):
            shutil.copyfile(src, os.path.join(DIST, fn))
    nav_ok = patch_homepage()  # keep the original Webflow landing page, improved in place
    built = ["/", "/for-companies", "/for-suppliers", "/how-it-works", "/verification-compliance",
             "/pricing", "/contact", "/blog"] + [f"/blog/{s}" for s, *_ in BLOG_POSTS]
    print(f"Built {len(built)} pages:")
    for b in built:
        print("  ", b)
    print("homepage nav rewritten:", nav_ok)
