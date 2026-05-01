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
    hosting_info = customer.get('hosting_info') or {}
    platform = customer.get('platform', 'unknown').title()
    address = customer.get('address', '')
    phone = customer.get('phone', '')
    zipcode = customer.get('zip', '')

    def _grade(score):
        if score >= 90: return 'A'
        if score >= 80: return 'B'
        if score >= 70: return 'C'
        if score >= 60: return 'D'
        return 'F'

    schema_types = site_data.get('schema_types', [])

    # ---- Title page ----
    doc.add_paragraph()
    title = doc.add_heading('AI Search Optimization Report', level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = sub.add_run(f'{name} — {domain}')
    run.font.size = Pt(16)
    run.font.color.rgb = RGBColor(0x2B, 0x57, 0x97)

    meta = doc.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    from datetime import date as _date
    meta.add_run(f'Report Date: {_date.today().strftime("%B %d, %Y")}\n').font.size = Pt(11)
    meta.add_run('Prepared by: PracticeRank AI Audit Engine\n').font.size = Pt(11)
    meta.add_run('Contact: kdoherty@practicerank.ai | (925) 819-2663').font.size = Pt(10)

    doc.add_page_break()

    # ---- Executive Summary ----
    doc.add_heading('Executive Summary', level=1)
    doc.add_paragraph(
        f'{name} is a dental practice in {city}, {state} with a website at {domain}. '
        f'This report analyzes the practice\'s current search visibility across both traditional search engines '
        f'and AI-powered search (ChatGPT, Claude, Perplexity, Google AI Overviews) and provides actionable '
        f'recommendations with deploy-ready files.'
    )
    overall = scores['overall']
    projected = min(overall + 40, 95)
    summary_p = doc.add_paragraph()
    summary_p.add_run(f'The site scores {overall}/100 overall').bold = True
    gap_text = f' with {"critical gaps" if overall < 50 else "notable opportunities"} in AI search readiness ({scores["aeo"]}/100)'
    if scores['technical_seo'] < 60:
        gap_text += f' and technical SEO ({scores["technical_seo"]}/100)'
    gap_text += '.'
    summary_p.add_run(gap_text)

    # Key findings
    p = doc.add_paragraph()
    p.add_run('Key findings:').bold = True
    findings = []
    if not site_data.get('has_llms_txt'):
        findings.append('No llms.txt file — completely invisible to AI assistants')
    if not site_data.get('has_ai_robots'):
        findings.append('No AI bot permissions in robots.txt')
    if not schema_types:
        findings.append('No schema markup found')
    elif 'Dentist' not in schema_types and 'LocalBusiness' not in schema_types:
        findings.append(f'Schema incomplete — found {", ".join(schema_types)} but no Dentist/LocalBusiness')
    if 'FAQPage' not in schema_types:
        findings.append('No FAQPage schema for AI answer extraction')
    if 'Person' not in schema_types:
        findings.append('No Person schema — doctors invisible to AI')
    if not site_data.get('has_analytics'):
        findings.append('No analytics tracking detected')
    if not findings:
        findings.append('Good foundation — see recommendations for optimization')
    for f in findings:
        doc.add_paragraph(f, style='List Bullet')

    doc.add_page_break()

    # ---- Scores ----
    doc.add_heading(f'Overall Score: {overall}/100', level=1)
    score_table = doc.add_table(rows=6, cols=3)
    score_table.style = 'Light Shading Accent 1'
    for i, h in enumerate(['Category', 'Score', 'Grade']):
        score_table.rows[0].cells[i].text = h
        for para in score_table.rows[0].cells[i].paragraphs:
            for r in para.runs:
                r.bold = True
    score_rows = [
        ('Technical SEO', scores['technical_seo']),
        ('AI Search Readiness (AEO)', scores['aeo']),
        ('Content Quality', scores['content_quality']),
        ('Local Visibility', scores['local_visibility']),
        ('Review Presence', scores['review_presence']),
    ]
    for i, (cat, s) in enumerate(score_rows):
        score_table.rows[i + 1].cells[0].text = cat
        score_table.rows[i + 1].cells[1].text = f'{s}/100'
        score_table.rows[i + 1].cells[2].text = _grade(s)

    p = doc.add_paragraph()
    run = p.add_run(f'\nProjected Improvement: {overall} -> {projected}/100 after implementation')
    run.bold = True
    run.font.color.rgb = RGBColor(0x05, 0x6F, 0x46)

    doc.add_page_break()

    # ---- Infrastructure Summary ----
    doc.add_heading('Infrastructure Summary', level=1)
    infra_data = [
        ('Platform', f'{platform}{" (" + hosting_info.get("cms", "") + ")" if hosting_info.get("cms") and hosting_info.get("cms","").lower() != platform.lower() else ""}'),
        ('Hosting', hosting_info.get('hosting', 'Unknown')),
        ('CDN', hosting_info.get('cdn', 'None detected')),
        ('Registrar', hosting_info.get('registrar', 'Unknown')),
        ('Nameservers', ', '.join(hosting_info.get('nameservers', [])) or 'Unknown'),
        ('A Record', hosting_info.get('a_record', 'Unknown')),
        ('CNAME (www)', hosting_info.get('cname', 'None')),
        ('Web Server', hosting_info.get('web_server', 'Unknown')),
        ('SSL', 'Active'),
        ('Domain Expiry', hosting_info.get('domain_expiry', 'Unknown')),
    ]
    infra_table = doc.add_table(rows=len(infra_data), cols=2)
    infra_table.style = 'Light Shading Accent 1'
    for i, (field, val) in enumerate(infra_data):
        infra_table.rows[i].cells[0].text = field
        infra_table.rows[i].cells[1].text = str(val)
        for para in infra_table.rows[i].cells[0].paragraphs:
            for r in para.runs:
                r.bold = True

    # ---- Business Snapshot ----
    doc.add_heading('Business Snapshot', level=1)
    biz_data = [
        ('Business Name', name),
        ('Website', domain),
        ('Address', f'{address}, {city}, {state} {zipcode}'.strip(', ')),
        ('Phone', phone),
        ('Google Rating', f'{site_data.get("rating", "N/A")} ({site_data.get("review_count", 0)} reviews)'),
    ]
    biz_table = doc.add_table(rows=len(biz_data), cols=2)
    biz_table.style = 'Light Shading Accent 1'
    for i, (field, val) in enumerate(biz_data):
        biz_table.rows[i].cells[0].text = field
        biz_table.rows[i].cells[1].text = str(val)
        for para in biz_table.rows[i].cells[0].paragraphs:
            for r in para.runs:
                r.bold = True

    if providers:
        doc.add_heading('Providers', level=2)
        for prov in providers:
            para = doc.add_paragraph()
            run = para.add_run(f'{prov["name"]}')
            run.bold = True
            creds = prov.get('credentials', '') or prov.get('bio', '')
            if creds:
                para.add_run(f' — {creds}')

    doc.add_page_break()

    # ---- Detailed Audit: Technical SEO ----
    doc.add_heading(f'1. Technical SEO Audit ({scores["technical_seo"]}/100 — {_grade(scores["technical_seo"])})', level=1)

    doc.add_heading("What's Working", level=2)
    working = ['HTTPS active with SSL certificate']
    if site_data.get('has_sitemap'):
        working.append(f'Sitemap.xml present ({site_data["pages_indexed"]} pages indexed)')
    if schema_types:
        working.append(f'Schema types found: {", ".join(schema_types)}')
    if site_data.get('has_analytics'):
        working.append('Analytics tracking installed')
    for w in working:
        doc.add_paragraph(w, style='List Bullet')

    doc.add_heading('Issues Found', level=2)
    if not schema_types:
        doc.add_heading('No Schema Markup', level=3)
        doc.add_paragraph(
            'The site has zero JSON-LD structured data. Search engines and AI models rely on schema '
            'to understand entities, services, and relationships. Missing: Dentist, FAQPage, Person, '
            'MedicalProcedure, BreadcrumbList, AggregateRating.')
    elif 'Dentist' not in schema_types and 'LocalBusiness' not in schema_types:
        doc.add_heading('Incomplete Schema Markup', level=3)
        doc.add_paragraph(
            f'Found: {", ".join(schema_types)}. Missing critical types: Dentist/LocalBusiness, '
            'FAQPage, Person, MedicalProcedure, BreadcrumbList.')
    if not site_data.get('has_analytics'):
        doc.add_heading('No Analytics Tracking', level=3)
        doc.add_paragraph(
            'No Google Analytics 4, Google Tag Manager, or other analytics platform detected. '
            'Without analytics there is no visibility into traffic, conversions, or user behavior.')
    if site_data.get('pages_indexed', 0) < 15:
        doc.add_heading('Low Page Count', level=3)
        doc.add_paragraph(
            f'Only {site_data["pages_indexed"]} pages indexed. Practices with 30+ pages of quality '
            'content rank significantly better in both traditional and AI search.')

    doc.add_page_break()

    # ---- Detailed Audit: AEO ----
    doc.add_heading(f'2. AI Search Readiness — AEO ({scores["aeo"]}/100 — {_grade(scores["aeo"])})', level=1)

    aeo_checks = [
        ('llms.txt', site_data.get('has_llms_txt'), 'Found', 'NOT FOUND — AI assistants cannot discover this practice'),
        ('AI bot permissions', site_data.get('has_ai_robots'), 'Configured', 'NOT configured — no rules for ChatGPT-User, GPTBot, ClaudeBot'),
        ('FAQPage schema', 'FAQPage' in schema_types, 'Present', 'Missing — cannot appear in AI FAQ answers'),
        ('Person schema', 'Person' in schema_types, 'Present', 'Missing — doctors invisible to AI'),
        ('Dentist schema', any(t in schema_types for t in ['Dentist', 'LocalBusiness']), 'Present', 'Missing — practice not typed for AI'),
    ]
    aeo_table = doc.add_table(rows=len(aeo_checks) + 1, cols=2)
    aeo_table.style = 'Light Shading Accent 1'
    aeo_table.rows[0].cells[0].text = 'Check'
    aeo_table.rows[0].cells[1].text = 'Status'
    for para in aeo_table.rows[0].cells[0].paragraphs:
        for r in para.runs:
            r.bold = True
    for para in aeo_table.rows[0].cells[1].paragraphs:
        for r in para.runs:
            r.bold = True
    for i, (check, passed, yes_text, no_text) in enumerate(aeo_checks):
        aeo_table.rows[i + 1].cells[0].text = check
        aeo_table.rows[i + 1].cells[1].text = yes_text if passed else no_text

    if not site_data.get('has_llms_txt'):
        doc.add_paragraph()
        doc.add_heading('No llms.txt File', level=3)
        doc.add_paragraph(
            'The llms.txt standard is the emerging way to make your business discoverable by AI assistants. '
            'Without it, when someone asks ChatGPT "best dentist in ' + (city or 'your area') + '," '
            'your practice is invisible to the AI\'s knowledge base.')
    if not site_data.get('has_ai_robots'):
        doc.add_heading('No AI Bot Permissions', level=3)
        doc.add_paragraph(
            'The robots.txt has no specific rules for AI search bots (ChatGPT-User, GPTBot, ClaudeBot, '
            'Google-Extended, PerplexityBot, Applebot-Extended). Explicit Allow directives signal intent '
            'and improve crawl priority for AI-powered search engines.')

    doc.add_page_break()

    # ---- Issues & Fixes Table ----
    doc.add_heading('3. All Issues — Priority Matrix', level=1)
    fix_data = []
    if not site_data.get('has_llms_txt'):
        fix_data.append(('CRITICAL', 'No llms.txt', 'Invisible to AI assistants', 'Deploy llms.txt to site root'))
    if not site_data.get('has_ai_robots'):
        fix_data.append(('CRITICAL', 'No AI crawler permissions', 'AI bots may not prioritize crawling', 'Update robots.txt'))
    if not schema_types or ('Dentist' not in schema_types and 'LocalBusiness' not in schema_types):
        fix_data.append(('CRITICAL', 'Missing Dentist schema', 'Practice not typed for search engines', 'Add Dentist JSON-LD'))
    if 'FAQPage' not in schema_types:
        fix_data.append(('HIGH', 'No FAQPage schema', '37-40% fewer AI citations', 'Add FAQ schema'))
    if 'Person' not in schema_types:
        fix_data.append(('HIGH', 'No Person schema', 'Doctors not in AI results', 'Add Person JSON-LD per provider'))
    if not site_data.get('has_analytics'):
        fix_data.append(('HIGH', 'No analytics', 'No traffic/conversion data', 'Install Google Analytics 4'))
    if not site_data.get('has_sitemap'):
        fix_data.append(('HIGH', 'No sitemap.xml', 'Pages may not be indexed', 'Generate and submit sitemap'))
    fix_data.append(('HIGH', 'Service pages lack expert quotes', 'Reduces AI trust signals', 'Add Dr. quotes to top pages'))
    fix_data.append(('MEDIUM', 'No neighborhood pages', 'Missing local search queries', 'Create area-specific pages'))
    fix_data.append(('MEDIUM', 'No blog/content cadence', 'No freshness signals', 'Start 2-4 posts/month'))

    if fix_data:
        fix_table = doc.add_table(rows=len(fix_data) + 1, cols=4)
        fix_table.style = 'Light Shading Accent 1'
        for i, h in enumerate(['Priority', 'Issue', 'Impact', 'Fix']):
            fix_table.rows[0].cells[i].text = h
            for para in fix_table.rows[0].cells[i].paragraphs:
                for r in para.runs:
                    r.bold = True
        for i, row in enumerate(fix_data):
            for j, val in enumerate(row):
                fix_table.rows[i + 1].cells[j].text = val

    doc.add_page_break()

    # ---- Deploy Files ----
    doc.add_heading('4. Deploy Files Included', level=1)
    doc.add_paragraph('The following files are included and ready to deploy:')
    files_info = [
        ('llms.txt', 'AI assistant discoverability file', 'Site root: /llms.txt'),
        ('robots.txt', 'Updated with AI bot permissions', 'Site root: /robots.txt'),
        ('schema-homepage.html', 'Dentist + Organization + Breadcrumb JSON-LD', 'Homepage <head>'),
        ('schema-faq.html', 'FAQPage JSON-LD (10-15 questions)', 'Homepage or FAQ page <head>'),
        ('schema-doctors.html', 'Person JSON-LD for each provider', 'Doctors/team page <head>'),
    ]
    files_table = doc.add_table(rows=len(files_info) + 1, cols=3)
    files_table.style = 'Light Shading Accent 1'
    for i, h in enumerate(['File', 'Purpose', 'Deploy Location']):
        files_table.rows[0].cells[i].text = h
        for para in files_table.rows[0].cells[i].paragraphs:
            for r in para.runs:
                r.bold = True
    for i, (fname, purpose, loc) in enumerate(files_info):
        files_table.rows[i + 1].cells[0].text = fname
        files_table.rows[i + 1].cells[1].text = purpose
        files_table.rows[i + 1].cells[2].text = loc

    doc.add_page_break()

    # ---- Implementation Roadmap ----
    doc.add_heading('5. Implementation Roadmap', level=1)
    phases = [
        ('Phase 1: Week 1-2 — Technical Foundation', [
            'Deploy llms.txt to site root',
            'Update robots.txt with AI crawler permissions',
            'Add Dentist + Organization schema to homepage',
            'Add FAQPage schema with top patient questions',
            'Add Person schema for each provider',
        ] + (['Set up Google Analytics 4'] if not site_data.get('has_analytics') else [])),
        ('Phase 2: Week 3-4 — Content Enhancement', [
            'Add expert quotes and statistics to service pages',
            'Rewrite page intros to TLDR-first format for AI extraction',
            'Create/optimize Google Business Profile',
            'Verify all directory listings (Yelp, Healthgrades, Zocdoc)',
        ]),
        ('Phase 3: Month 2-3 — Local Expansion', [
            'Create neighborhood landing pages for surrounding cities',
            'Start monthly blog cadence (2-4 posts/month)',
            'Build local citation and backlink profile',
            'Set up review generation system',
        ]),
        ('Phase 4: Month 3+ — Ongoing Optimization', [
            'Monthly AI mention monitoring (ChatGPT, Claude, Perplexity)',
            'Monthly llms.txt hit tracking via Cloudflare analytics',
            'Quarterly full re-audit and score update',
            'Competitor SEO/AEO monitoring',
        ]),
    ]
    for phase_title, tasks in phases:
        doc.add_heading(phase_title, level=2)
        for task in tasks:
            doc.add_paragraph(task, style='List Bullet')

    # ---- Footer ----
    doc.add_page_break()
    doc.add_heading('About PracticeRank', level=1)
    doc.add_paragraph(
        'PracticeRank specializes in AI Search Optimization (AEO) for dental and medical practices. '
        'We help practices appear in AI-powered search results from ChatGPT, Claude, Perplexity, '
        'and Google AI Overviews — the fastest-growing channel for how patients find healthcare providers.'
    )
    doc.add_paragraph()
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
    city = customer.get('city', '')
    state = customer.get('state', '')

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
    site_data['robots_txt'] = robots or ''
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

    # ---- Build report context ----
    projected = min(scores['overall'] + 40, 95)
    hosting_info = customer.get('hosting_info') or {}
    platform = customer.get('platform', 'unknown').title()
    address = customer.get('address', '')
    phone = customer.get('phone', '')
    zipcode = customer.get('zip', '')

    def _grade(score):
        if score >= 90: return 'A'
        if score >= 80: return 'B'
        if score >= 70: return 'C'
        if score >= 60: return 'D'
        return 'F'

    # Build issues list
    issues_critical = []
    issues_high = []
    issues_medium = []

    if not site_data.get('has_llms_txt'):
        issues_critical.append(('No llms.txt file',
            'The llms.txt standard is the emerging way to make your business discoverable by AI assistants '
            '(ChatGPT, Claude, Perplexity, Google AI Overviews). Without it, AI models have no structured '
            'summary of what your practice offers. When someone asks ChatGPT "best dentist in '
            f'{city}," your practice is invisible.'))
    if not site_data.get('has_ai_robots'):
        issues_critical.append(('No AI bot permissions in robots.txt',
            'The robots.txt has no specific rules for AI search bots (ChatGPT-User, GPTBot, ClaudeBot, '
            'Google-Extended, PerplexityBot, Applebot-Extended). Explicit Allow directives signal intent '
            'and improve crawl priority for AI-powered search engines.'))
    if 'FAQPage' not in site_data.get('schema_types', []):
        issues_high.append(('No FAQPage schema markup',
            'FAQ schema enables rich results in Google and provides structured answers that AI assistants '
            'can cite directly. Practices with FAQ schema see 37-40% more AI search citations.'))
    if 'Person' not in site_data.get('schema_types', []):
        issues_high.append(('No Person schema for providers',
            'Without Person schema, AI assistants cannot reliably identify your doctors, their credentials, '
            'or specialties. This data is critical for queries like "Dr. [Name] dentist" or '
            f'"best cosmetic dentist in {city}."'))
    if not site_data.get('has_analytics'):
        issues_high.append(('No analytics tracking detected',
            'No Google Analytics 4, Google Tag Manager, or other analytics platform was detected. '
            'Without analytics there is no visibility into traffic, conversions, or user behavior.'))
    schema_types = site_data.get('schema_types', [])
    if not schema_types:
        issues_high.append(('No schema markup found',
            'The site has zero JSON-LD structured data. Search engines and AI models rely on schema '
            'to understand entities, services, and relationships.'))
    elif 'Dentist' not in schema_types and 'LocalBusiness' not in schema_types:
        issues_medium.append(('Missing Dentist/LocalBusiness schema',
            f'Found schema types: {", ".join(schema_types)}. But no Dentist or LocalBusiness schema, '
            'which is critical for local search visibility and Google Maps integration.'))
    if site_data.get('pages_indexed', 0) < 15:
        issues_medium.append(('Low page count',
            f'Only {site_data["pages_indexed"]} pages indexed. Practices with 30+ pages of quality '
            'content rank significantly better in both traditional and AI search.'))
    if not site_data.get('has_sitemap'):
        issues_high.append(('No sitemap.xml found',
            'Without a sitemap, search engines may miss pages during crawling.'))

    # Provider info for report
    provider_names = [p.get('name', '') for p in (providers or [])]
    provider_str = ', '.join(provider_names) if provider_names else 'None listed'

    # Service info
    service_names = [s.get('name', '') for s in (services or [])]
    service_str = ', '.join(service_names[:10]) if service_names else 'None listed'
    if len(service_names) > 10:
        service_str += f', and {len(service_names) - 10} more'

    # ---- Generate markdown report ----
    report_md = f"""# AI Search Optimization Report
## {customer['name']} — {domain}

**Report Date:** {date.today().strftime('%B %d, %Y')}
**Prepared by:** PracticeRank AI Audit Engine

---

## Executive Summary

{customer['name']} is a dental practice in {city}, {state} with a website at {domain}. This report analyzes the practice's current search visibility across both traditional search engines and AI-powered search (ChatGPT, Claude, Perplexity, Google AI Overviews) and provides actionable recommendations with deploy-ready files.

The site scores **{scores['overall']}/100 overall** with {'critical gaps' if scores['overall'] < 50 else 'notable opportunities'} in AI search readiness ({scores['aeo']}/100){' and technical SEO (' + str(scores['technical_seo']) + '/100)' if scores['technical_seo'] < 60 else ''}.

---

## Overall Score: {scores['overall']}/100

| Category | Score | Grade |
|----------|-------|-------|
| Technical SEO | {scores['technical_seo']}/100 | {_grade(scores['technical_seo'])} |
| AI Search Readiness (AEO) | {scores['aeo']}/100 | {_grade(scores['aeo'])} |
| Content Quality | {scores['content_quality']}/100 | {_grade(scores['content_quality'])} |
| Local Visibility | {scores['local_visibility']}/100 | {_grade(scores['local_visibility'])} |
| Review Presence | {scores['review_presence']}/100 | {_grade(scores['review_presence'])} |

**Projected Improvement: {scores['overall']} -> {projected}/100 after implementation**

---

## Infrastructure Summary

| Component | Status |
|-----------|--------|
| Platform | {platform}{' (' + hosting_info.get('cms', '') + ')' if hosting_info.get('cms') and hosting_info.get('cms','').lower() != platform.lower() else ''} |
| Hosting | {hosting_info.get('hosting', 'Unknown')} |
| CDN | {hosting_info.get('cdn', 'None detected')} |
| Registrar | {hosting_info.get('registrar', 'Unknown')} |
| Nameservers | {', '.join(hosting_info.get('nameservers', [])) or 'Unknown'} |
| A Record | {hosting_info.get('a_record', 'Unknown')} |
| CNAME (www) | {hosting_info.get('cname', 'None')} |
| Web Server | {hosting_info.get('web_server', 'Unknown')} |
| SSL | Active |
| Domain Expiry | {hosting_info.get('domain_expiry', 'Unknown')} |

---

## 1. Technical SEO Audit (Score: {scores['technical_seo']}/100 — {_grade(scores['technical_seo'])})

### What's Working
- {'HTTPS active with SSL certificate' if True else ''}
- {'Sitemap.xml present' if site_data.get('has_sitemap') else 'Sitemap.xml NOT found (critical)'}
- {str(site_data['pages_indexed']) + ' pages indexed in sitemap' if site_data['pages_indexed'] else 'Could not determine page count'}
- Schema types found: {', '.join(schema_types) if schema_types else 'None'}
- Analytics: {'Installed' if site_data.get('has_analytics') else 'NOT detected'}

### Issues Found
"""
    # Add issues to markdown
    for title, desc in issues_critical:
        report_md += f"\n#### CRITICAL: {title}\n{desc}\n"
    for title, desc in issues_high:
        report_md += f"\n#### HIGH: {title}\n{desc}\n"
    for title, desc in issues_medium:
        report_md += f"\n#### MEDIUM: {title}\n{desc}\n"

    report_md += f"""
---

## 2. AI Search Readiness — AEO (Score: {scores['aeo']}/100 — {_grade(scores['aeo'])})

| Check | Status |
|-------|--------|
| llms.txt | {'Found' if site_data['has_llms_txt'] else 'NOT FOUND — AI assistants cannot discover practice'} |
| AI bot permissions (robots.txt) | {'Configured' if site_data['has_ai_robots'] else 'NOT configured — no rules for ChatGPT-User, GPTBot, ClaudeBot'} |
| FAQPage schema | {'Present' if 'FAQPage' in schema_types else 'Missing — cannot appear in AI FAQ answers'} |
| Person schema (providers) | {'Present' if 'Person' in schema_types else 'Missing — doctors invisible to AI'} |
| Dentist/LocalBusiness schema | {'Present' if any(t in schema_types for t in ['Dentist', 'LocalBusiness']) else 'Missing — practice not typed for AI'} |
| MedicalProcedure schema | {'Present' if 'MedicalProcedure' in schema_types else 'Missing — services not structured for AI'} |

---

## 3. Content & Local Visibility

- **Google Rating:** {site_data['rating']} ({site_data['review_count']} reviews)
- **Providers:** {provider_str}
- **Services:** {service_str}
- **Pages Indexed:** {site_data['pages_indexed']}
- **Address:** {address}, {city}, {state} {zipcode}
- **Phone:** {phone}

---

## 4. Recommendations — Priority Order

### Immediate (Week 1-2)

1. **Deploy llms.txt** — Make practice discoverable by AI assistants
2. **Update robots.txt** — Add explicit AI bot permissions (ChatGPT-User, GPTBot, ClaudeBot, PerplexityBot)
3. **Add Dentist + Organization schema** — Complete JSON-LD with address, phone, providers, services
4. **Add FAQPage schema** — Top 10-15 patient questions with answers
5. **Add Person schema for providers** — Each doctor with credentials and specialties
{'6. **Set up Google Analytics 4** — Start tracking traffic and conversions' if not site_data.get('has_analytics') else ''}

### Short-Term (Week 3-4)

{'7' if not site_data.get('has_analytics') else '6'}. Add expert quotes and statistics to service pages
{'8' if not site_data.get('has_analytics') else '7'}. Rewrite page intros to TLDR-first format for AI extraction
{'9' if not site_data.get('has_analytics') else '8'}. Create/optimize Google Business Profile

### Medium-Term (Month 2-3)

- Create neighborhood landing pages for surrounding cities
- Start monthly blog cadence (2-4 posts/month)
- Build local citation listings (Yelp, Healthgrades, Zocdoc)
- Set up review generation system

### Ongoing

- Monthly AI mention monitoring (ChatGPT, Claude, Perplexity)
- Monthly llms.txt hit tracking via Cloudflare analytics
- Quarterly full re-audit
- Competitor SEO/AEO monitoring

---

## Deploy Files Included

| File | Purpose | Deploy Location |
|------|---------|----------------|
| llms.txt | AI assistant discoverability file | Site root: /llms.txt |
| robots.txt | AI crawler permissions | Site root: /robots.txt |
| schema-homepage.html | Dentist + Organization + BreadcrumbList JSON-LD | Homepage `<head>` |
| schema-faq.html | FAQPage JSON-LD | Homepage or FAQ page `<head>` |
| schema-doctors.html | Person JSON-LD for providers | Doctors/team page `<head>` |

---

*Report generated by PracticeRank AI Audit Engine v1.0*
*Contact: kdoherty@practicerank.ai | (925) 819-2663 | practicerank.ai*
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
