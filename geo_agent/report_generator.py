"""Generate AI Search Optimization reports for businesses.

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

from geo_agent.schema_validator import extract_jsonld

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
    """Extract @type values from <script type="application/ld+json"> blocks only.

    Uses schema_validator.extract_jsonld so @type strings inside inline JS or
    other page content are never counted as structured data.
    """
    types: list[str] = []

    def _collect(node):
        if isinstance(node, dict):
            t = node.get('@type')
            if isinstance(t, str):
                types.append(t)
            elif isinstance(t, list):
                types.extend(x for x in t if isinstance(x, str))
            for v in node.values():
                _collect(v)
        elif isinstance(node, list):
            for item in node:
                _collect(item)

    for schema in extract_jsonld(html):
        _collect(schema)
    return types


def _parse_ai_robots(robots: str) -> tuple[list[str], list[str]]:
    """Determine which AI bots robots.txt explicitly ALLOWS vs DISALLOWS.

    A bot mentioned only with 'Disallow: /' is blocked — mere presence of the
    bot name in the file is NOT permission. Returns (allowed, blocked).
    """
    ai_bots = ['ChatGPT-User', 'Claude-SearchBot', 'PerplexityBot', 'GPTBot',
               'ClaudeBot', 'Google-Extended']
    # Parse into user-agent groups: ([agents], [(directive, value), ...])
    groups: list[tuple[list[str], list[tuple[str, str]]]] = []
    agents: list[str] = []
    rules: list[tuple[str, str]] = []
    for raw in robots.splitlines():
        line = raw.split('#', 1)[0].strip()
        if not line or ':' not in line:
            continue
        field, _, value = line.partition(':')
        field = field.strip().lower()
        value = value.strip()
        if field == 'user-agent':
            if rules:
                groups.append((agents, rules))
                agents, rules = [], []
            agents.append(value.lower())
        elif field in ('allow', 'disallow') and agents:
            rules.append((field, value))
    if agents:
        groups.append((agents, rules))

    def _group_blocks_all(group_rules: list[tuple[str, str]]) -> bool:
        return any(f == 'disallow' and v == '/' for f, v in group_rules)

    allowed: list[str] = []
    blocked: list[str] = []
    for bot in ai_bots:
        bot_l = bot.lower()
        verdict = None
        for grp_agents, grp_rules in groups:
            if bot_l in grp_agents:
                verdict = 'blocked' if _group_blocks_all(grp_rules) else 'allowed'
                break
        if verdict is None:
            # Not explicitly mentioned — blocked only if wildcard disallows all
            for grp_agents, grp_rules in groups:
                if '*' in grp_agents and _group_blocks_all(grp_rules):
                    verdict = 'blocked'
                    break
        if verdict == 'allowed':
            allowed.append(bot)
        elif verdict == 'blocked':
            blocked.append(bot)
    return allowed, blocked


def _extract_page_locs(xml: str) -> list[str]:
    """Extract <loc> values from <url> entries only.

    Skips <sitemap> index locs and namespaced image:/video: locs so the
    page count is not inflated by media entries or nested sitemaps.
    """
    locs: list[str] = []
    for block in re.findall(r'<url\b[^>]*>(.*?)</url>', xml, re.S | re.I):
        m = re.search(r'<loc>\s*([^<]+?)\s*</loc>', block)
        if m:
            locs.append(m.group(1))
    return locs


def _get_sitemap_page_urls(domain: str) -> list[str]:
    """Collect page URLs across all sitemaps."""
    idx = _fetch(f"https://{domain}/sitemap.xml") or _fetch(f"https://www.{domain}/sitemap.xml")
    if not idx:
        return []
    urls = _extract_page_locs(idx)
    # sitemap index → sub-sitemaps (<sitemap> entries only)
    sub_sitemaps = re.findall(
        r'<sitemap\b[^>]*>.*?<loc>\s*([^<]+?)\s*</loc>.*?</sitemap>', idx, re.S | re.I)
    for sm_url in sub_sitemaps:
        sub = _fetch(sm_url)
        if sub:
            urls.extend(_extract_page_locs(sub))
    if not urls and not sub_sitemaps:
        # Malformed sitemap without <url> wrappers — fall back to bare <loc>
        # values, excluding anything that looks like a nested sitemap
        urls = [u for u in re.findall(r'<loc>([^<]+)</loc>', idx)
                if not u.strip().endswith('.xml')]
    return urls


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
    if any(t in site_data.get('schema_types', []) for t in ['MedicalProcedure', 'Service', 'OfferCatalog']):
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
    from geo_agent.business_profiles import get_profile
    profile = get_profile(customer.get('business_type', 'practice'))

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
    spec_text = ", ".join(specialties[:5]) if specialties else profile.service_category
    location_str = f" in {city}, {state}" if city else ""
    lines.append(f"> {profile.industry_label}{location_str} offering {spec_text}. "
                 f"{f'{len(providers)} {profile.provider_term}. ' if providers else ''}"
                 f"{'Serving ' + city + ' and surrounding communities.' if city else ''}")
    lines.append("")

    # About
    lines.append("## About")
    lines.append("")
    location_detail = f" located at {address}, {city}, {state} {zipcode}" if address else f" in {city}, {state}" if city else ""
    lines.append(f"{name} is a {profile.industry_label.lower()}{location_detail}. "
                 f"The business offers {spec_text}.")
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
    """Generate primary business schema JSON-LD."""
    from geo_agent.business_profiles import get_profile
    profile = get_profile(customer.get('business_type', 'practice'))

    name = customer['name']
    domain = customer.get('domain', '')
    address = customer.get('address', '')
    city = customer.get('city', '')
    state = customer.get('state', '')
    zipcode = customer.get('zip', '')
    phone = customer.get('phone', '')

    # Use Service for non-medical businesses, MedicalProcedure for dental
    svc_type = "MedicalProcedure" if profile.is_practice else "Service"
    available_services = []
    for s in services[:10]:
        available_services.append({
            "@type": svc_type,
            "name": s['name'],
            "description": s.get('description', f"{s['name']} at {name}")
        })

    location_desc = f" in {city}, {state}" if city else ""
    schema = {
        "@context": "https://schema.org",
        "@type": profile.schema_type,
        "@id": f"https://{domain}/#{profile.schema_id_suffix}",
        "name": name,
        "url": f"https://{domain}",
        "description": f"{profile.industry_label}{location_desc}.",
        "telephone": phone,
        "address": {
            "@type": "PostalAddress",
            "streetAddress": address,
            "addressLocality": city,
            "addressRegion": state,
            "postalCode": zipcode,
            "addressCountry": "US"
        },
    }

    if profile.is_practice:
        schema["priceRange"] = "$$"

    if profile.schema_specialty:
        schema["medicalSpecialty"] = profile.schema_specialty

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
    """Generate FAQPage schema with common business questions."""
    from geo_agent.business_profiles import get_profile
    profile = get_profile(customer.get('business_type', 'practice'))

    name = customer['name']
    city = customer.get('city', '')
    state = customer.get('state', '')
    phone = customer.get('phone', '')
    location_str = f" in {city}, {state}" if city else ""

    if profile.is_practice:
        faqs = [
            (f"What services does {name} offer?",
             f"{name} offers comprehensive dental care including general dentistry, cosmetic dentistry, restorative dentistry, preventive care, and emergency dental services{location_str}. Call {phone} for appointments."),
            (f"Does {name} accept insurance?",
             f"{name} accepts most major dental insurance plans. Contact the office at {phone} to verify your specific plan."),
            (f"Where is {name} located?",
             f"{name} is located at {customer.get('address', '')}, {city}, {state} {customer.get('zip', '')}. Call {phone} for directions."),
            (f"Does {name} offer emergency dental care?",
             f"Yes, {name} provides emergency dental care for situations like severe toothaches, broken teeth, and dental infections. Call {phone} for emergency appointments."),
            (f"How do I schedule an appointment at {name}?",
             f"You can schedule an appointment at {name} by calling {phone} or visiting the website at {customer.get('domain', '')}."),
            (f"What makes {name} different?",
             f"{name} combines experienced dental professionals with modern technology to deliver personalized, comfortable dental care{location_str}."),
        ]
    else:
        faqs = [
            (f"What {profile.service_category} does {name} offer?",
             f"{name} provides {profile.service_category}{location_str}. Contact us at {phone} for more information."),
            (f"Where is {name} located?",
             f"{name} is located at {customer.get('address', '')}, {city}, {state} {customer.get('zip', '')}. Call {phone} for directions."),
            (f"How do I contact {name}?",
             f"You can reach {name} by calling {phone} or visiting the website at {customer.get('domain', '')}."),
            (f"What areas does {name} serve?",
             f"{name} serves {profile.customer_term}{location_str} and surrounding areas." if city else f"{name} serves {profile.customer_term} nationwide."),
            (f"What makes {name} different?",
             f"{name} provides professional {profile.service_category} with a focus on quality and {profile.customer_term} satisfaction."),
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
    """Generate Person schema for each provider/team member."""
    from geo_agent.business_profiles import get_profile
    profile = get_profile(customer.get('business_type', 'practice'))

    domain = customer.get('domain', '')
    name = customer['name']

    persons = []
    for p in providers:
        job_title = p.get('credentials', '') or profile.provider_term.rstrip('s').title()
        person = {
            "@context": "https://schema.org",
            "@type": "Person",
            "name": p['name'],
            "jobTitle": job_title,
            "description": p.get('bio', f"{job_title} at {name}"),
            "worksFor": {
                "@type": profile.schema_type,
                "@id": f"https://{domain}/#{profile.schema_id_suffix}",
                "name": name
            }
        }
        if p.get('specialties'):
            if profile.schema_specialty:
                person["medicalSpecialty"] = p['specialties']
            else:
                person["knowsAbout"] = p['specialties']
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
    from geo_agent.business_profiles import get_profile
    profile = get_profile(customer.get('business_type', 'practice'))
    location_str = f" in {city}, {state}" if city else ""
    doc.add_paragraph(
        f'{name} is a {profile.industry_label.lower()}{location_str} with a website at {domain}. '
        f'This report analyzes the business\'s current search visibility across both traditional search engines '
        f'and AI-powered search (ChatGPT, Claude, Perplexity, Google AI Overviews) and provides actionable '
        f'recommendations with deploy-ready files.'
    )
    overall = scores['overall']
    # Recomputed by generate_report using the same scoring model with the
    # deployed fixes applied — not an invented delta.
    projected = scores.get('projected', overall)
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
        if site_data.get('ai_bots_blocked'):
            findings.append(f'robots.txt blocks AI bots ({", ".join(site_data["ai_bots_blocked"])})')
        else:
            findings.append('No AI bot permissions in robots.txt')
    if not schema_types:
        findings.append('No schema markup detected on crawled pages')
    elif 'Dentist' not in schema_types and 'LocalBusiness' not in schema_types and 'Organization' not in schema_types:
        findings.append(f'Schema incomplete — found {", ".join(schema_types)} but no {profile.schema_type}')
    if 'FAQPage' not in schema_types:
        findings.append('No FAQPage schema for AI answer extraction')
    if 'Person' not in schema_types:
        findings.append(f'No Person schema — {profile.provider_term} invisible to AI')
    if not site_data.get('has_analytics'):
        findings.append('Analytics tracking not detected on crawled pages')
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
    run = p.add_run(f'\nProjected Score: {overall} -> {projected}/100 after deploying the included fixes (same scoring model, fixes applied)')
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
        ('SSL', 'Active (HTTPS verified)' if site_data.get('https_ok') else 'Not verified'),
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
    working = []
    if site_data.get('https_ok'):
        working.append('HTTPS active with SSL certificate')
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
        doc.add_heading('No Schema Markup Detected', level=3)
        doc.add_paragraph(
            'No JSON-LD structured data was detected on the homepage or key interior pages crawled. '
            'Search engines and AI models rely on schema '
            f'to understand entities, services, and relationships. Missing: {profile.schema_type}, FAQPage, Person, '
            'BreadcrumbList, AggregateRating.')
    elif profile.schema_type not in schema_types and 'LocalBusiness' not in schema_types and 'Organization' not in schema_types:
        doc.add_heading('Incomplete Schema Markup', level=3)
        doc.add_paragraph(
            f'Found: {", ".join(schema_types)}. Missing critical types: {profile.schema_type}, '
            'FAQPage, Person, BreadcrumbList.')
    if not site_data.get('has_analytics'):
        doc.add_heading('Analytics Tracking Not Detected', level=3)
        doc.add_paragraph(
            'No Google Analytics 4 or Google Tag Manager tags were detected on the crawled pages. '
            'Note: analytics loaded via a consent manager or server-side tagging may not be visible '
            'in page HTML — verify in your tag configuration. Without working analytics there is no '
            'visibility into traffic, conversions, or user behavior.')
    if site_data.get('pages_indexed', 0) < 15:
        doc.add_heading('Low Page Count', level=3)
        doc.add_paragraph(
            f'Only {site_data["pages_indexed"]} pages indexed. Businesses with 30+ pages of quality '
            'content rank significantly better in both traditional and AI search.')

    doc.add_page_break()

    # ---- Detailed Audit: AEO ----
    doc.add_heading(f'2. AI Search Readiness — AEO ({scores["aeo"]}/100 — {_grade(scores["aeo"])})', level=1)

    aeo_checks = [
        ('llms.txt', site_data.get('has_llms_txt'), 'Found', 'NOT FOUND — AI assistants cannot discover this business'),
        ('AI bot permissions', site_data.get('has_ai_robots'),
         site_data.get('ai_robots_status', 'Configured'),
         site_data.get('ai_robots_status', 'NOT configured — no rules for ChatGPT-User, GPTBot, ClaudeBot')),
        ('FAQPage schema', 'FAQPage' in schema_types, 'Present', 'Missing — cannot appear in AI FAQ answers'),
        ('Person schema', 'Person' in schema_types, 'Present', f'Missing — {profile.provider_term} invisible to AI'),
        (f'{profile.schema_type} schema', any(t in schema_types for t in [profile.schema_type, 'LocalBusiness', 'Organization']), 'Present', 'Missing — business not typed for AI'),
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
            'Without it, when someone asks ChatGPT about your ' + profile.service_category + ' in ' + (city or 'your area') + ', '
            'your business is invisible to the AI\'s knowledge base.')
    if not site_data.get('has_ai_robots'):
        if site_data.get('ai_bots_blocked'):
            doc.add_heading('robots.txt Blocks AI Bots', level=3)
            doc.add_paragraph(
                f'The robots.txt explicitly disallows {", ".join(site_data["ai_bots_blocked"])}. '
                'Blocked AI search bots cannot crawl the site, which keeps the business out of '
                'AI-powered search results.')
        else:
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
        if site_data.get('ai_bots_blocked'):
            fix_data.append(('CRITICAL', 'robots.txt blocks AI bots', 'AI search engines cannot crawl the site', 'Update robots.txt'))
        else:
            fix_data.append(('CRITICAL', 'No AI crawler permissions', 'AI bots may not prioritize crawling', 'Update robots.txt'))
    if not schema_types or (profile.schema_type not in schema_types and 'LocalBusiness' not in schema_types and 'Organization' not in schema_types):
        fix_data.append(('CRITICAL', f'Missing {profile.schema_type} schema', 'Business not typed for search engines', f'Add {profile.schema_type} JSON-LD'))
    if 'FAQPage' not in schema_types:
        fix_data.append(('HIGH', 'No FAQPage schema', 'Missing a schema type AI engines cite most often', 'Add FAQ schema'))
    if 'Person' not in schema_types:
        fix_data.append(('HIGH', 'No Person schema', f'{profile.provider_term.title()} not in AI results', f'Add Person JSON-LD per {profile.provider_term[:-1] if profile.provider_term.endswith("s") else profile.provider_term}'))
    if not site_data.get('has_analytics'):
        fix_data.append(('HIGH', 'Analytics not detected on crawled pages', 'No traffic/conversion data', 'Install/verify Google Analytics 4'))
    if not site_data.get('has_sitemap'):
        fix_data.append(('HIGH', 'No sitemap.xml', 'Pages may not be indexed', 'Generate and submit sitemap'))
    # Content findings — only asserted when the crawl data actually supports them
    page_paths = []
    for u in site_data.get('sitemap_urls', []):
        rest = u.split('//', 1)[-1]
        page_paths.append('/' + rest.split('/', 1)[1].lower() if '/' in rest else '/')
    if not site_data.get('has_blockquote'):
        fix_data.append(('HIGH', 'Expert quotes not detected on crawled pages', 'Reduces AI trust signals', 'Add expert quotes to top pages'))
    city_slug = re.sub(r'[^a-z0-9]+', '-', city.lower()).strip('-') if city else ''
    area_markers = ('neighborhood', 'service-area', '/areas', '/locations', '/communities', 'serving-')
    if not any(any(m in p for m in area_markers) or (city_slug and city_slug in p) for p in page_paths):
        fix_data.append(('MEDIUM', 'No neighborhood/area pages detected in sitemap', 'Missing local search queries', 'Create area-specific pages'))
    blog_markers = ('/blog', '/post', '/news', '/article')
    if not any(m in p for p in page_paths for m in blog_markers):
        fix_data.append(('MEDIUM', 'No blog/content cadence detected', 'No freshness signals', 'Start 2-4 posts/month'))

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
        ('schema-homepage.html', f'{profile.schema_type} + Organization JSON-LD', 'Homepage <head>'),
        ('schema-faq.html', 'FAQPage JSON-LD (10-15 questions)', 'Homepage or FAQ page <head>'),
        ('schema-doctors.html', f'Person JSON-LD for each {profile.provider_term[:-1] if profile.provider_term.endswith("s") else profile.provider_term}', 'Team page <head>'),
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
            f'Add {profile.schema_type} + Organization schema to homepage',
            f'Add FAQPage schema with top {profile.customer_term} questions',
            f'Add Person schema for each {profile.provider_term[:-1] if profile.provider_term.endswith("s") else profile.provider_term}',
        ] + (['Set up Google Analytics 4'] if not site_data.get('has_analytics') else [])),
        ('Phase 2: Week 3-4 — Content Enhancement', [
            'Add expert quotes and statistics to service pages',
            'Rewrite page intros to TLDR-first format for AI extraction',
            'Create/optimize Google Business Profile',
            'Verify all directory listings',
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
        'PracticeRank specializes in AI Search Optimization (AEO) for businesses of all types. '
        'We help businesses appear in AI-powered search results from ChatGPT, Claude, Perplexity, '
        'and Google AI Overviews — the fastest-growing channel for how customers find service providers.'
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
    from geo_agent.business_profiles import get_profile
    profile = get_profile(customer.get('business_type', 'practice'))

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

    # Check robots.txt AI bot POLICY (allowed vs disallowed — presence of a
    # bot name is not permission; a Disallow rule is the opposite)
    robots = _fetch(f"https://{domain}/robots.txt") or _fetch(f"https://{www_domain}/robots.txt")
    site_data['robots_txt'] = robots or ''
    site_data['ai_bots_allowed'] = []
    site_data['ai_bots_blocked'] = []
    if robots:
        ai_allowed, ai_blocked = _parse_ai_robots(robots)
        site_data['ai_bots_allowed'] = ai_allowed
        site_data['ai_bots_blocked'] = ai_blocked
        site_data['has_ai_robots'] = bool(ai_allowed)
        if ai_allowed:
            site_data['ai_robots_status'] = ('Configured — allows ' + ', '.join(ai_allowed)
                                             + (f"; blocks {', '.join(ai_blocked)}" if ai_blocked else ''))
        elif ai_blocked:
            site_data['ai_robots_status'] = f"BLOCKED — robots.txt disallows {', '.join(ai_blocked)}"
        else:
            site_data['ai_robots_status'] = 'NOT configured — no rules for ChatGPT-User, GPTBot, ClaudeBot'
    else:
        site_data['ai_robots_status'] = 'NOT configured — no robots.txt found'

    # Check sitemap
    site_data['has_sitemap'] = (
        _check_file_exists(domain, '/sitemap.xml') or
        _check_file_exists(www_domain, '/sitemap.xml')
    )

    # Count pages (keep URLs so content findings can be verified, not assumed)
    sitemap_urls = _get_sitemap_page_urls(domain) or _get_sitemap_page_urls(www_domain)
    site_data['sitemap_urls'] = sitemap_urls
    site_data['pages_indexed'] = len(sitemap_urls)

    # Fetch homepage for schema + analytics check
    homepage = _fetch(f"https://{domain}") or _fetch(f"https://{www_domain}")
    # HTTPS verified iff the homepage actually loaded over https
    site_data['https_ok'] = bool(homepage)
    site_data['has_blockquote'] = bool(homepage) and '<blockquote' in homepage.lower()

    def _has_analytics_tags(html: str) -> bool:
        lower = html.lower()
        return ('google-analytics' in lower or 'gtag' in lower or
                'googletagmanager' in lower)

    # Schema and analytics often live on interior pages (WP SEO plugins,
    # consent managers) — check key crawled pages, not just the homepage.
    schema_types_found: set[str] = set()
    analytics_found = False
    pages_checked = 0
    if homepage:
        pages_checked += 1
        schema_types_found.update(_extract_schema_types(homepage))
        analytics_found = _has_analytics_tags(homepage)
    interior_markers = ('service', 'about', 'contact', 'team', 'faq',
                        'doctor', 'location')
    interior_urls = [u for u in sitemap_urls
                     if any(m in u.lower() for m in interior_markers)][:6]
    for page_url in interior_urls:
        page_html = _fetch(page_url)
        if not page_html:
            continue
        pages_checked += 1
        schema_types_found.update(_extract_schema_types(page_html))
        if not analytics_found:
            analytics_found = _has_analytics_tags(page_html)
    site_data['schema_types'] = sorted(schema_types_found)
    site_data['has_analytics'] = analytics_found
    site_data['pages_checked'] = pages_checked

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
    # Projected score: re-run the same scoring model with the fixes this report
    # actually deploys applied (llms.txt, AI robots rules, AEO schema types).
    projected_site = dict(site_data)
    projected_site['has_llms_txt'] = True
    projected_site['has_ai_robots'] = True
    installed_schema = {profile.schema_type, 'FAQPage'}
    if providers:
        installed_schema.add('Person')
    if services:
        installed_schema.add('MedicalProcedure' if profile.is_practice else 'Service')
    projected_site['schema_types'] = sorted(set(site_data.get('schema_types', [])) | installed_schema)
    projected = _calculate_scores(projected_site)['overall']
    scores['projected'] = projected
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

    from geo_agent.business_profiles import get_profile as _gp
    profile = _gp(customer.get('business_type', 'practice'))

    if not site_data.get('has_llms_txt'):
        issues_critical.append(('No llms.txt file',
            'The llms.txt standard is the emerging way to make your business discoverable by AI assistants '
            '(ChatGPT, Claude, Perplexity, Google AI Overviews). Without it, AI models have no structured '
            f'summary of what your business offers. When someone asks AI about {profile.service_category} in '
            f'{city}, your business is invisible.'))
    if not site_data.get('has_ai_robots'):
        if site_data.get('ai_bots_blocked'):
            issues_critical.append(('robots.txt blocks AI bots',
                f'The robots.txt explicitly disallows {", ".join(site_data["ai_bots_blocked"])}. '
                'Blocked AI search bots cannot crawl the site, which keeps the business out of '
                'AI-powered search results.'))
        else:
            issues_critical.append(('No AI bot permissions in robots.txt',
                'The robots.txt has no specific rules for AI search bots (ChatGPT-User, GPTBot, ClaudeBot, '
                'Google-Extended, PerplexityBot, Applebot-Extended). Explicit Allow directives signal intent '
                'and improve crawl priority for AI-powered search engines.'))
    if 'FAQPage' not in site_data.get('schema_types', []):
        issues_high.append(('No FAQPage schema markup',
            'FAQ schema enables rich results in Google and provides structured answers that AI assistants '
            'can cite directly. FAQ schema is among the structured data types AI engines cite most often.'))
    if 'Person' not in site_data.get('schema_types', []):
        issues_high.append((f'No Person schema for {profile.provider_term}',
            f'Without Person schema, AI assistants cannot reliably identify your {profile.provider_term}, their credentials, '
            f'or specialties. This data is critical for queries about your {profile.provider_term}.'))
    if not site_data.get('has_analytics'):
        issues_high.append(('Analytics tracking not detected on crawled pages',
            'No Google Analytics 4 or Google Tag Manager tags were detected on the crawled pages. '
            'Analytics loaded via a consent manager or server-side tagging may not be visible in '
            'page HTML — verify in your tag configuration. Without working analytics there is no '
            'visibility into traffic, conversions, or user behavior.'))
    schema_types = site_data.get('schema_types', [])
    if not schema_types:
        issues_high.append(('No schema markup detected',
            'No JSON-LD structured data was detected on the homepage or key interior pages crawled. '
            'Search engines and AI models rely on schema '
            'to understand entities, services, and relationships.'))
    elif profile.schema_type not in schema_types and 'LocalBusiness' not in schema_types and 'Organization' not in schema_types:
        issues_medium.append((f'Missing {profile.schema_type}/LocalBusiness schema',
            f'Found schema types: {", ".join(schema_types)}. But no {profile.schema_type} or LocalBusiness schema, '
            'which is critical for search visibility and Google Maps integration.'))
    if site_data.get('pages_indexed', 0) < 15:
        issues_medium.append(('Low page count',
            f'Only {site_data["pages_indexed"]} pages indexed. Businesses with 30+ pages of quality '
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

{customer['name']} is a {profile.industry_label.lower()}{' in ' + city + ', ' + state if city else ''} with a website at {domain}. This report analyzes the business's current search visibility across both traditional search engines and AI-powered search (ChatGPT, Claude, Perplexity, Google AI Overviews) and provides actionable recommendations with deploy-ready files.

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

**Projected Score: {scores['overall']} -> {projected}/100 after deploying the included fixes (same scoring model, fixes applied)**

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
| SSL | {'Active (HTTPS verified)' if site_data.get('https_ok') else 'Not verified'} |
| Domain Expiry | {hosting_info.get('domain_expiry', 'Unknown')} |

---

## 1. Technical SEO Audit (Score: {scores['technical_seo']}/100 — {_grade(scores['technical_seo'])})

### What's Working
- {'HTTPS active with SSL certificate' if site_data.get('https_ok') else 'HTTPS could not be verified during crawl'}
- {'Sitemap.xml present' if site_data.get('has_sitemap') else 'Sitemap.xml NOT found (critical)'}
- {str(site_data['pages_indexed']) + ' pages indexed in sitemap' if site_data['pages_indexed'] else 'Could not determine page count'}
- Schema types found: {', '.join(schema_types) if schema_types else 'None detected on crawled pages'}
- Analytics: {'Installed' if site_data.get('has_analytics') else 'Not detected on crawled pages'}

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
| llms.txt | {'Found' if site_data['has_llms_txt'] else 'NOT FOUND — AI assistants cannot discover this business'} |
| AI bot permissions (robots.txt) | {site_data.get('ai_robots_status', 'Configured' if site_data['has_ai_robots'] else 'NOT configured — no rules for ChatGPT-User, GPTBot, ClaudeBot')} |
| FAQPage schema | {'Present' if 'FAQPage' in schema_types else 'Missing — cannot appear in AI FAQ answers'} |
| Person schema ({profile.provider_term}) | {'Present' if 'Person' in schema_types else 'Missing — ' + profile.provider_term + ' invisible to AI'} |
| {profile.schema_type}/LocalBusiness schema | {'Present' if any(t in schema_types for t in [profile.schema_type, 'LocalBusiness', 'Organization']) else 'Missing — business not typed for AI'} |
| Service schema | {'Present' if any(t in schema_types for t in ['Service', 'MedicalProcedure']) else 'Missing — services not structured for AI'} |

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

1. **Deploy llms.txt** — Make business discoverable by AI assistants
2. **Update robots.txt** — Add explicit AI bot permissions (ChatGPT-User, GPTBot, ClaudeBot, PerplexityBot)
3. **Add {profile.schema_type} + Organization schema** — Complete JSON-LD with address, phone, {profile.provider_term}, services
4. **Add FAQPage schema** — Top 10-15 {profile.customer_term} questions with answers
5. **Add Person schema for {profile.provider_term}** — Each {profile.provider_term[:-1] if profile.provider_term.endswith('s') else profile.provider_term} with credentials and specialties
{'6. **Set up Google Analytics 4** — Start tracking traffic and conversions' if not site_data.get('has_analytics') else ''}

### Short-Term (Week 3-4)

{'7' if not site_data.get('has_analytics') else '6'}. Add expert quotes and statistics to service pages
{'8' if not site_data.get('has_analytics') else '7'}. Rewrite page intros to TLDR-first format for AI extraction
{'9' if not site_data.get('has_analytics') else '8'}. Create/optimize Google Business Profile

### Medium-Term (Month 2-3)

- Create neighborhood landing pages for surrounding cities
- Start monthly blog cadence (2-4 posts/month)
- Build local citation listings
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
| schema-homepage.html | {profile.schema_type} + Organization JSON-LD | Homepage `<head>` |
| schema-faq.html | FAQPage JSON-LD | Homepage or FAQ page `<head>` |
| schema-doctors.html | Person JSON-LD for {profile.provider_term} | Team page `<head>` |

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
