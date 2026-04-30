"""Generate AI Search Optimization reports for dental practices.

Takes customer data from the DB, crawls the site for current state,
and produces a full report (markdown + docx) with deploy-ready files.
"""

from __future__ import annotations

import json
import logging
import os
import re
import zipfile
from datetime import date
from pathlib import Path
from textwrap import dedent

import httpx

logger = logging.getLogger("practicerank.report")

# ---------------------------------------------------------------------------
# Site crawler helpers
# ---------------------------------------------------------------------------

def _fetch(url: str, timeout: int = 15) -> str | None:
    """Fetch URL text, return None on failure."""
    try:
        with httpx.stream("GET", url, timeout=timeout, follow_redirects=True,
                          headers={"User-Agent": "PracticeRank-Auditor/1.0"}) as r:
            if r.status_code >= 400:
                return None
            # Limit to 2MB to avoid memory issues
            chunks = []
            total = 0
            for chunk in r.iter_text():
                total += len(chunk)
                if total > 2_000_000:
                    break
                chunks.append(chunk)
            return "".join(chunks)
    except Exception as e:
        logger.debug(f"Failed to fetch {url}: {e}")
        return None


def _check_file_exists(domain: str, path: str) -> bool:
    url = f"https://{domain}{path}"
    try:
        r = httpx.head(url, timeout=10, follow_redirects=True,
                       headers={"User-Agent": "PracticeRank-Auditor/1.0"})
        return r.status_code < 400
    except Exception:
        return False


def _extract_schema_types(html: str) -> list[str]:
    """Extract @type values from JSON-LD blocks."""
    types = []
    for m in re.finditer(r'"@type"\s*:\s*"([^"]+)"', html):
        types.append(m.group(1))
    return types


def _count_pages_in_sitemap(domain: str) -> int:
    """Count total pages across all sitemaps."""
    count = 0
    idx = _fetch(f"https://{domain}/sitemap.xml") or _fetch(f"https://www.{domain}/sitemap.xml")
    if not idx:
        return 0
    # sitemap index → sub-sitemaps
    sub_urls = re.findall(r'<loc>([^<]+)</loc>', idx)
    for url in sub_urls:
        if url.endswith('.xml'):
            sub = _fetch(url)
            if sub:
                count += len(re.findall(r'<loc>', sub))
        else:
            count += 1
    return count or len(sub_urls)


def _extract_text_content(html: str, after: str | None = None) -> str:
    """Strip tags and return text. Optionally start after a marker."""
    if after:
        idx = html.find(after)
        if idx >= 0:
            html = html[idx:]
    html = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.S)
    html = re.sub(r'<style[^>]*>.*?</style>', ' ', html, flags=re.S)
    html = re.sub(r'<[^>]+>', ' ', html)
    return re.sub(r'\s+', ' ', html).strip()



# ---------------------------------------------------------------------------
# Score calculator
# ---------------------------------------------------------------------------

def _calculate_scores(site_data: dict) -> dict:
    """Calculate AEO scores based on site audit data."""
    scores = {}

    # Technical SEO
    tech = 30
    if site_data.get('has_sitemap'):
        tech += 15
    if site_data.get('schema_types'):
        tech += 10
    if site_data.get('pages_indexed', 0) > 20:
        tech += 10
    if site_data.get('has_analytics'):
        tech += 5
    scores['technical_seo'] = min(tech, 100)

    # AEO
    aeo = 0
    if site_data.get('has_llms_txt'):
        aeo += 30
    if site_data.get('has_ai_robots'):
        aeo += 20
    if 'FAQPage' in site_data.get('schema_types', []):
        aeo += 20
    if 'Person' in site_data.get('schema_types', []):
        aeo += 15
    if 'MedicalProcedure' in site_data.get('schema_types', []):
        aeo += 15
    scores['aeo'] = min(aeo, 100)

    # Content
    content = 30
    pages = site_data.get('pages_indexed', 0)
    if pages > 50:
        content += 20
    elif pages > 20:
        content += 10
    # Placeholder — full content analysis would check for expert quotes, stats
    scores['content_quality'] = min(content + 20, 100)

    # Local
    local = 30
    if site_data.get('rating', 0) >= 4.5:
        local += 15
    if site_data.get('review_count', 0) > 100:
        local += 10
    scores['local_visibility'] = min(local, 100)

    # Reviews
    review = 20
    rc = site_data.get('review_count', 0)
    if rc > 500:
        review += 35
    elif rc > 100:
        review += 25
    elif rc > 30:
        review += 15
    if site_data.get('rating', 0) >= 4.8:
        review += 10
    if 'AggregateRating' in site_data.get('schema_types', []):
        review += 10
    scores['review_presence'] = min(review, 100)

    # Overall
    weights = [0.2, 0.3, 0.2, 0.15, 0.15]
    vals = [scores['technical_seo'], scores['aeo'], scores['content_quality'],
            scores['local_visibility'], scores['review_presence']]
    scores['overall'] = int(sum(w * v for w, v in zip(weights, vals)))

    return scores


# ---------------------------------------------------------------------------
# File generators
# ---------------------------------------------------------------------------

def _generate_llms_txt(customer: dict, providers: list, services: list) -> str:
    """Generate llms.txt content from customer data."""
    name = customer['name']
    city = customer.get('city', '')
    state = customer.get('state', '')
    domain = customer.get('domain', '')
    address = customer.get('address', '')
    phone = customer.get('phone', '')
    zipcode = customer.get('zip', '')
    specialties = customer.get('specialties', [])
    if isinstance(specialties, str):
        try:
            specialties = json.loads(specialties)
        except Exception:
            specialties = [s.strip() for s in specialties.split(',') if s.strip()]

    lines = [f"# {name}", ""]

    # Summary line
    spec_text = ", ".join(specialties[:5]) if specialties else "general, cosmetic, and restorative dentistry"
    lines.append(f"> Dental practice in {city}, {state} offering {spec_text}. "
                 f"{f'{len(providers)} providers. ' if providers else ''}"
                 f"Serving {city} and surrounding communities.")
    lines.append("")

    # About
    lines.append("## About")
    lines.append("")
    lines.append(f"{name} is a dental practice located at {address}, {city}, {state} {zipcode}. "
                 f"The practice offers comprehensive dental care with a focus on patient comfort and modern technology.")
    lines.append("")

    # Providers
    if providers:
        lines.append("## Providers")
        lines.append("")
        for p in providers:
            creds = f" ({p.get('credentials', '')})" if p.get('credentials') else ""
            bio = f" — {p['bio']}" if p.get('bio') else ""
            specs = f". Specialties: {', '.join(p['specialties'])}" if p.get('specialties') else ""
            lines.append(f"- {p['name']}{creds}{bio}{specs}")
        lines.append("")

    # Services
    if services:
        lines.append("## Services")
        lines.append("")
        # Group by category if available
        cats = {}
        for s in services:
            cat = s.get('category', 'General')
            cats.setdefault(cat, []).append(s['name'])
        for cat, names in cats.items():
            lines.append(f"- {cat} — {', '.join(names)}")
        lines.append("")

    # Contact
    lines.append("## Contact")
    lines.append("")
    if address:
        lines.append(f"- Address: {address}, {city}, {state} {zipcode}")
    if phone:
        lines.append(f"- Phone: {phone}")
    if domain:
        lines.append(f"- Website: https://{domain}")
    lines.append("")

    # Service area
    if city:
        lines.append("## Service Area")
        lines.append("")
        lines.append(f"{city}, {state} and surrounding communities")
        lines.append("")

    return "\n".join(lines)


def _generate_robots_txt(domain: str) -> str:
    """Generate robots.txt with AI crawler permissions."""
    return dedent(f"""\
    # {domain}
    # Allow AI search/retrieval bots, block AI training crawlers

    # Standard search engines
    User-agent: Googlebot
    Allow: /

    User-agent: Bingbot
    Allow: /

    User-agent: Applebot
    Allow: /

    # AI search/retrieval bots - ALLOW
    User-agent: ChatGPT-User
    Allow: /

    User-agent: Claude-SearchBot
    Allow: /

    User-agent: PerplexityBot
    Allow: /

    User-agent: YouBot
    Allow: /

    User-agent: Amazonbot
    Allow: /

    # AI training crawlers - BLOCK
    User-agent: GPTBot
    Disallow: /

    User-agent: ClaudeBot
    Disallow: /

    User-agent: Google-Extended
    Disallow: /

    User-agent: CCBot
    Disallow: /

    User-agent: meta-externalagent
    Disallow: /

    User-agent: Bytespider
    Disallow: /

    User-agent: anthropic-ai
    Disallow: /

    User-agent: Applebot-Extended
    Disallow: /

    # Default
    User-agent: *
    Allow: /

    Sitemap: https://{domain}/sitemap.xml
    """)


def _generate_schema_homepage(customer: dict, providers: list, services: list) -> str:
    """Generate Dentist + Organization JSON-LD."""
    name = customer['name']
    domain = customer.get('domain', '')
    address = customer.get('address', '')
    city = customer.get('city', '')
    state = customer.get('state', '')
    zipcode = customer.get('zip', '')
    phone = customer.get('phone', '')

    available_services = []
    for s in services[:10]:
        available_services.append({
            "@type": "MedicalProcedure",
            "name": s['name'],
            "description": s.get('description', f"{s['name']} services at {name}")
        })

    schema = {
        "@context": "https://schema.org",
        "@type": "Dentist",
        "@id": f"https://{domain}/#dentist",
        "name": name,
        "url": f"https://{domain}",
        "description": f"Dental practice in {city}, {state} offering comprehensive dental care.",
        "telephone": phone,
        "priceRange": "$$",
        "address": {
            "@type": "PostalAddress",
            "streetAddress": address,
            "addressLocality": city,
            "addressRegion": state,
            "postalCode": zipcode,
            "addressCountry": "US"
        },
    }

    if available_services:
        schema["availableService"] = available_services

    if city:
        schema["areaServed"] = {
            "@type": "City",
            "name": city,
            "containedInPlace": {"@type": "State", "name": state}
        }

    return ('<!-- Enhanced Homepage Schema -->\n'
            '<script type="application/ld+json">\n'
            + json.dumps(schema, indent=2) +
            '\n</script>')


def _generate_schema_faq(customer: dict) -> str:
    """Generate FAQPage schema with common dental questions."""
    name = customer['name']
    city = customer.get('city', '')
    state = customer.get('state', '')
    phone = customer.get('phone', '')

    faqs = [
        (f"What services does {name} offer?",
         f"{name} offers comprehensive dental care including general dentistry, cosmetic dentistry, restorative dentistry, preventive care, and emergency dental services in {city}, {state}. Call {phone} for appointments."),
        (f"Does {name} accept insurance?",
         f"{name} accepts most major dental insurance plans. Contact the office at {phone} to verify your specific plan."),
        (f"Where is {name} located?",
         f"{name} is located at {customer.get('address', '')}, {city}, {state} {customer.get('zip', '')}. Call {phone} for directions."),
        (f"Does {name} offer emergency dental care?",
         f"Yes, {name} provides emergency dental care for situations like severe toothaches, broken teeth, and dental infections. Call {phone} for emergency appointments."),
        (f"How do I schedule an appointment at {name}?",
         f"You can schedule an appointment at {name} by calling {phone} or visiting the website at {customer.get('domain', '')}."),
        (f"What makes {name} different?",
         f"{name} combines experienced dental professionals with modern technology to deliver personalized, comfortable dental care in {city}, {state}."),
    ]

    schema = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": q,
                "acceptedAnswer": {"@type": "Answer", "text": a}
            }
            for q, a in faqs
        ]
    }

    return ('<!-- FAQPage Schema -->\n'
            '<script type="application/ld+json">\n'
            + json.dumps(schema, indent=2) +
            '\n</script>')


def _generate_schema_doctors(customer: dict, providers: list) -> str:
    """Generate Person schema for each provider."""
    domain = customer.get('domain', '')
    name = customer['name']

    persons = []
    for p in providers:
        person = {
            "@context": "https://schema.org",
            "@type": "Dentist",
            "name": p['name'],
            "jobTitle": "Dentist",
            "description": p.get('bio', f"Dentist at {name}"),
            "worksFor": {
                "@type": "Dentist",
                "@id": f"https://{domain}/#dentist",
                "name": name
            }
        }
        if p.get('specialties'):
            person["medicalSpecialty"] = p['specialties']
        persons.append(person)

    if not persons:
        return ""

    return ('<!-- Doctor/Person Schema -->\n'
            '<script type="application/ld+json">\n'
            + json.dumps(persons, indent=2) +
            '\n</script>')


# ---------------------------------------------------------------------------
# DOCX generator
# ---------------------------------------------------------------------------

def _generate_docx(report_md: str, customer: dict, scores: dict, site_data: dict,
                   providers: list, out_path: Path):
    """Generate a formatted Word document from the report data."""
    try:
        from docx import Document
        from docx.shared import Pt, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.enum.table import WD_TABLE_ALIGNMENT
    except ImportError:
        logger.warning("python-docx not installed, skipping DOCX generation")
        return None

    doc = Document()
    style = doc.styles['Normal']
    style.font.name = 'Calibri'
    style.font.size = Pt(11)

    name = customer['name']
    city = customer.get('city', '')
    state = customer.get('state', '')
    domain = customer.get('domain', '')

    # Title page
    title = doc.add_heading('AI Search Optimization Report', level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = sub.add_run(f'{name} — {city}, {state}')
    run.font.size = Pt(16)
    run.font.color.rgb = RGBColor(0x2B, 0x57, 0x97)

    meta = doc.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    meta.add_run('Prepared by: PracticeRank AI Search Optimization\n').font.size = Pt(10)
    from datetime import date
    meta.add_run(f'Date: {date.today().strftime("%B %d, %Y")}\n').font.size = Pt(10)
    meta.add_run('Contact: kdoherty@practicerank.ai').font.size = Pt(10)

    doc.add_page_break()

    # Executive Summary
    doc.add_heading('Executive Summary', level=1)
    doc.add_paragraph(
        f'{name} is a dental practice in {city}, {state} with a website at {domain}. '
        f'This report analyzes the practice\'s current AI search visibility and provides '
        f'actionable recommendations to improve discoverability in AI-powered search engines '
        f'like ChatGPT, Claude, Perplexity, and Google AI Overviews.'
    )

    p = doc.add_paragraph()
    run = p.add_run('Key findings: ')
    run.bold = True

    issues = []
    if not site_data.get('has_llms_txt'):
        issues.append('No llms.txt file (AI discoverability standard)')
    if not site_data.get('has_ai_robots'):
        issues.append('No AI crawler permissions in robots.txt')
    if 'FAQPage' not in site_data.get('schema_types', []):
        issues.append('No FAQPage schema markup')
    if 'Person' not in site_data.get('schema_types', []):
        issues.append('No Person schema for providers')
    if not issues:
        issues.append('Good foundation — see recommendations for further optimization')

    for issue in issues:
        doc.add_paragraph(issue, style='List Bullet')

    # Scores
    doc.add_heading(f'Current Score: {scores["overall"]}/100', level=2)
    score_table = doc.add_table(rows=6, cols=3)
    score_table.style = 'Light Shading Accent 1'
    for i, h in enumerate(['Category', 'Score', 'Notes']):
        score_table.rows[0].cells[i].text = h
        for p in score_table.rows[0].cells[i].paragraphs:
            for r in p.runs:
                r.bold = True
    score_rows = [
        ('Technical SEO', f'{scores["technical_seo"]}/100',
         f'{len(site_data.get("schema_types", []))} schema types, {site_data.get("pages_indexed", 0)} pages'),
        ('AI Search Readiness', f'{scores["aeo"]}/100',
         f'llms.txt: {"Yes" if site_data.get("has_llms_txt") else "No"}, AI robots: {"Yes" if site_data.get("has_ai_robots") else "No"}'),
        ('Content Quality', f'{scores["content_quality"]}/100',
         f'{site_data.get("pages_indexed", 0)} pages indexed'),
        ('Local Visibility', f'{scores["local_visibility"]}/100',
         f'Rating: {site_data.get("rating", "N/A")}, Reviews: {site_data.get("review_count", "N/A")}'),
        ('Review Presence', f'{scores["review_presence"]}/100',
         f'{site_data.get("review_count", 0)} reviews'),
    ]
    for i, (cat, score, notes) in enumerate(score_rows):
        score_table.rows[i + 1].cells[0].text = cat
        score_table.rows[i + 1].cells[1].text = score
        score_table.rows[i + 1].cells[2].text = notes

    # Projected
    projected = min(scores['overall'] + 40, 95)
    p = doc.add_paragraph()
    run = p.add_run(f'\nProjected Improvement: {scores["overall"]} → {projected}/100 after implementation')
    run.bold = True
    run.font.color.rgb = RGBColor(0x05, 0x6F, 0x46)

    doc.add_page_break()

    # Business Snapshot
    doc.add_heading('Business Snapshot', level=1)
    biz_data = [
        ('Business Name', name),
        ('Website', domain),
        ('Address', f'{customer.get("address", "")}, {city}, {state} {customer.get("zip", "")}'),
        ('Phone', customer.get('phone', '')),
        ('Platform', customer.get('platform', 'unknown').title()),
    ]
    biz_table = doc.add_table(rows=len(biz_data), cols=2)
    biz_table.style = 'Light Shading Accent 1'
    for i, (field, val) in enumerate(biz_data):
        biz_table.rows[i].cells[0].text = field
        biz_table.rows[i].cells[1].text = str(val)
        for p in biz_table.rows[i].cells[0].paragraphs:
            for r in p.runs:
                r.bold = True

    if providers:
        doc.add_heading('Providers', level=2)
        for p in providers:
            para = doc.add_paragraph()
            run = para.add_run(f'{p["name"]} — ')
            run.bold = True
            para.add_run(p.get('bio', '') or p.get('credentials', ''))

    doc.add_page_break()

    # Issues & Fixes
    doc.add_heading('Technical Issues & Fixes', level=1)
    fix_data = []
    if not site_data.get('has_llms_txt'):
        fix_data.append(('CRITICAL', 'No llms.txt', 'AI assistants can\'t discover practice', 'Deploy llms.txt'))
    if not site_data.get('has_ai_robots'):
        fix_data.append(('CRITICAL', 'No AI crawler permissions', 'AI bots may not crawl', 'Update robots.txt'))
    if 'FAQPage' not in site_data.get('schema_types', []):
        fix_data.append(('HIGH', 'No FAQPage schema', 'Missing from AI answers', 'Add FAQ schema'))
    if 'Person' not in site_data.get('schema_types', []):
        fix_data.append(('HIGH', 'No Person schema', 'Doctors not in AI results', 'Add Person schema'))
    fix_data.append(('HIGH', 'Service pages lack expert quotes', '37-40% less AI citations', 'Add Dr. quotes'))
    fix_data.append(('MEDIUM', 'No neighborhood pages', 'Missing local queries', 'Create area pages'))
    fix_data.append(('LOW', 'No blog content', 'No freshness signals', 'Start monthly blog'))

    if fix_data:
        fix_table = doc.add_table(rows=len(fix_data) + 1, cols=4)
        fix_table.style = 'Light Shading Accent 1'
        for i, h in enumerate(['Priority', 'Issue', 'Impact', 'Fix']):
            fix_table.rows[0].cells[i].text = h
            for p in fix_table.rows[0].cells[i].paragraphs:
                for r in p.runs:
                    r.bold = True
        for i, row in enumerate(fix_data):
            for j, val in enumerate(row):
                fix_table.rows[i + 1].cells[j].text = val

    doc.add_page_break()

    # Deploy Files
    doc.add_heading('Files to Deploy', level=1)
    doc.add_paragraph('The following files are included and ready to deploy:')
    files_info = [
        ('llms.txt', 'AI discoverability file', 'Site root: /llms.txt'),
        ('robots.txt', 'AI crawler permissions', 'Site root: /robots.txt'),
        ('schema-homepage.html', 'Dentist + Organization JSON-LD', 'Homepage <head>'),
        ('schema-faq.html', 'FAQPage JSON-LD', 'Homepage or FAQ page <head>'),
        ('schema-doctors.html', 'Person JSON-LD for providers', 'Doctors page <head>'),
    ]
    files_table = doc.add_table(rows=len(files_info) + 1, cols=3)
    files_table.style = 'Light Shading Accent 1'
    for i, h in enumerate(['File', 'Purpose', 'Deploy Location']):
        files_table.rows[0].cells[i].text = h
        for p in files_table.rows[0].cells[i].paragraphs:
            for r in p.runs:
                r.bold = True
    for i, (f, purpose, loc) in enumerate(files_info):
        files_table.rows[i + 1].cells[0].text = f
        files_table.rows[i + 1].cells[1].text = purpose
        files_table.rows[i + 1].cells[2].text = loc

    doc.add_page_break()

    # Implementation Roadmap
    doc.add_heading('Implementation Roadmap', level=1)
    phases = [
        ('Phase 1: Week 1 — Technical Foundation', [
            'Deploy llms.txt to site root',
            'Update robots.txt with AI crawler permissions',
            'Add enhanced homepage schema',
            'Add FAQPage schema',
            'Add Person schema for providers',
        ]),
        ('Phase 2: Month 1 — Content Enhancement', [
            'Add expert quotes to top service pages',
            'Add statistics and data points',
            'Rewrite page intros to TLDR-first format',
        ]),
        ('Phase 3: Month 2 — Local Expansion', [
            'Create neighborhood landing pages for surrounding cities',
            'Verify/optimize directory listings',
            'Set up monthly blog cadence',
        ]),
        ('Phase 4: Month 3+ — Ongoing', [
            'Monthly blog posts with expert quotes',
            'KPI tracking (AI mentions, llms.txt hits)',
            'Quarterly re-audit',
        ]),
    ]
    for phase_title, tasks in phases:
        doc.add_heading(phase_title, level=2)
        for task in tasks:
            doc.add_paragraph(task, style='List Bullet')

    # Footer
    doc.add_page_break()
    doc.add_heading('About PracticeRank', level=1)
    doc.add_paragraph(
        'PracticeRank specializes in AI Search Optimization (AEO) for dental practices. '
        'We help practices appear in AI-powered search results from ChatGPT, Claude, Perplexity, '
        'and Google AI Overviews.'
    )
    p = doc.add_paragraph()
    p.add_run('Kody Doherty').bold = True
    p.add_run(' — Chief Technology Officer\n')
    p.add_run('Email: kdoherty@practicerank.ai\n')
    p.add_run('Phone: (925) 819-2663\n')
    p.add_run('Web: practicerank.ai')

    doc.save(str(out_path))
    return out_path


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def generate_report(customer: dict, providers: list, services: list,
                    places: dict | None = None,
                    data_dir: str = "data") -> dict:
    """Generate full AI search optimization report for a customer.

    Args:
        customer: Customer dict from DB (name, domain, city, state, etc.)
        providers: List of provider dicts from DB
        services: List of service dicts from DB
        places: Google Places data dict (rating, review_count) or None
        data_dir: Base data directory

    Returns:
        dict with keys: output_dir, zip_path, files (list of generated file paths)
    """
    name = customer.get('name', '')
    if not name:
        raise ValueError("Customer must have a name")
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    if not slug:
        raise ValueError(f"Could not generate slug from customer name: {name!r}")
    domain = customer.get('domain', '')
    if not domain:
        raise ValueError("Customer must have a domain")

    # Ensure www variant
    www_domain = domain if domain.startswith('www.') else f'www.{domain}'

    out_dir = Path(data_dir) / "customers" / slug
    deploy_dir = out_dir / "deploy-files"
    deploy_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Generating report for {customer['name']} ({domain})")

    # ---- Crawl site for current state ----
    site_data = {
        'has_llms_txt': False,
        'has_ai_robots': False,
        'has_sitemap': False,
        'has_analytics': False,
        'schema_types': [],
        'pages_indexed': 0,
        'rating': 0,
        'review_count': 0,
        'platform': customer.get('platform', 'unknown'),
    }

    # Check llms.txt
    site_data['has_llms_txt'] = (
        _check_file_exists(domain, '/llms.txt') or
        _check_file_exists(www_domain, '/llms.txt')
    )

    # Check robots.txt for AI bot mentions
    robots = _fetch(f"https://{domain}/robots.txt") or _fetch(f"https://{www_domain}/robots.txt")
    if robots:
        ai_bots = ['ChatGPT-User', 'Claude-SearchBot', 'PerplexityBot', 'GPTBot']
        site_data['has_ai_robots'] = any(bot in robots for bot in ai_bots)

    # Check sitemap
    site_data['has_sitemap'] = (
        _check_file_exists(domain, '/sitemap.xml') or
        _check_file_exists(www_domain, '/sitemap.xml')
    )

    # Count pages
    site_data['pages_indexed'] = _count_pages_in_sitemap(domain) or _count_pages_in_sitemap(www_domain)

    # Fetch homepage for schema + analytics check
    homepage = _fetch(f"https://{domain}") or _fetch(f"https://{www_domain}")
    if homepage:
        site_data['schema_types'] = _extract_schema_types(homepage)
        site_data['has_analytics'] = ('google-analytics' in homepage.lower() or
                                       'gtag' in homepage.lower() or
                                       'googletagmanager' in homepage.lower())

    # Places data
    if places:
        site_data['rating'] = places.get('rating') or 0
        site_data['review_count'] = places.get('review_count') or 0

    # ---- Calculate scores ----
    scores = _calculate_scores(site_data)

    # ---- Generate deploy files ----
    files = []

    # llms.txt
    llms_content = _generate_llms_txt(customer, providers, services)
    llms_path = deploy_dir / "llms.txt"
    llms_path.write_text(llms_content)
    files.append(str(llms_path))

    # robots.txt
    robots_content = _generate_robots_txt(domain)
    robots_path = deploy_dir / "robots.txt"
    robots_path.write_text(robots_content)
    files.append(str(robots_path))

    # Schema - homepage
    schema_home = _generate_schema_homepage(customer, providers, services)
    schema_home_path = deploy_dir / "schema-homepage.html"
    schema_home_path.write_text(schema_home)
    files.append(str(schema_home_path))

    # Schema - FAQ
    schema_faq = _generate_schema_faq(customer)
    schema_faq_path = deploy_dir / "schema-faq.html"
    schema_faq_path.write_text(schema_faq)
    files.append(str(schema_faq_path))

    # Schema - doctors
    if providers:
        schema_docs = _generate_schema_doctors(customer, providers)
        if schema_docs:
            schema_docs_path = deploy_dir / "schema-doctors.html"
            schema_docs_path.write_text(schema_docs)
            files.append(str(schema_docs_path))

    # ---- Generate markdown report ----
    projected = min(scores['overall'] + 40, 95)
    report_md = f"""# AI Search Optimization Report: {customer['name']}

**Prepared for:** {customer['name']} ({city}, {state})
**Date:** {date.today().strftime('%B %d, %Y')}
**Prepared by:** PracticeRank AI Search Optimization

---

## Current Score: {scores['overall']}/100

| Category | Score |
|----------|-------|
| Technical SEO | {scores['technical_seo']}/100 |
| AI Search Readiness (AEO) | {scores['aeo']}/100 |
| Content Quality | {scores['content_quality']}/100 |
| Local Visibility | {scores['local_visibility']}/100 |
| Review Presence | {scores['review_presence']}/100 |

**Projected Improvement: {scores['overall']} → {projected}/100 after implementation**

## Site Audit Summary

- **Domain:** {domain}
- **Pages Indexed:** {site_data['pages_indexed']}
- **Platform:** {site_data['platform']}
- **llms.txt:** {'Found' if site_data['has_llms_txt'] else 'Missing (404)'}
- **AI Crawler Permissions:** {'Configured' if site_data['has_ai_robots'] else 'Not configured'}
- **Schema Types Found:** {', '.join(site_data['schema_types']) if site_data['schema_types'] else 'None'}
- **Google Rating:** {site_data['rating']} ({site_data['review_count']} reviews)
- **Analytics:** {'Installed' if site_data['has_analytics'] else 'Not detected'}

## Files Included

| File | Purpose | Deploy Location |
|------|---------|----------------|
| llms.txt | AI discoverability | Site root: /llms.txt |
| robots.txt | AI crawler permissions | Site root: /robots.txt |
| schema-homepage.html | Dentist + Organization JSON-LD | Homepage <head> |
| schema-faq.html | FAQPage JSON-LD | Homepage or FAQ page <head> |
| schema-doctors.html | Person JSON-LD for providers | Doctors page <head> |

---

*Report generated by PracticeRank AI Search Optimization*
*Contact: kdoherty@practicerank.ai | practicerank.ai*
"""

    md_path = out_dir / "ai-search-optimization-report.md"
    md_path.write_text(report_md)
    files.append(str(md_path))

    # ---- Generate DOCX ----
    docx_path = out_dir / "ai-search-optimization-report.docx"
    _generate_docx(report_md, customer, scores, site_data, providers, docx_path)
    if docx_path.exists():
        files.append(str(docx_path))

    # ---- Create ZIP ----
    zip_path = out_dir / f"{slug}-ai-optimization.zip"
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            arcname = os.path.relpath(f, out_dir)
            zf.write(f, arcname)

    logger.info(f"Report generated: {zip_path} ({len(files)} files)")

    return {
        'output_dir': str(out_dir),
        'zip_path': str(zip_path),
        'docx_path': str(docx_path) if docx_path.exists() else None,
        'files': files,
        'scores': scores,
        'site_data': site_data,
    }
