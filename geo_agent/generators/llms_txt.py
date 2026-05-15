"""Generate llms.txt and llms-full.txt for businesses."""

from __future__ import annotations

import html as html_lib
import re
from urllib.parse import urlparse

from geo_agent.business_profiles import BusinessProfile, get_profile
from geo_agent.config import Customer
from geo_agent.crawler import PageData, clean_page_content, normalize_url
from geo_agent.google_places import CONFIDENCE_FOR_REVIEWS, VerifiedBusinessData, is_trusted


def _h1_for_type(customer: Customer, profile: BusinessProfile | None = None) -> str:
    """Return the H1 line based on business profile."""
    profile = profile or get_profile(customer)
    if profile.is_practice:
        return f"# {customer.name} — {profile.industry_label} in {customer.city}, {customer.state}"
    elif customer.city and customer.state:
        return f"# {customer.name} — {profile.industry_label} in {customer.city}, {customer.state}"
    else:
        return f"# {customer.name} — {profile.industry_label}"


def _blockquote_for_type(customer: Customer, profile: BusinessProfile | None = None) -> str:
    """Return the blockquote line based on business profile."""
    profile = profile or get_profile(customer)
    specialties_str = _get_specialties(customer)

    if profile.is_practice:
        emergency_note = " Same-day emergency appointments are available." if customer.emergency_available else ""
        if not specialties_str:
            specialties_str = f"comprehensive {profile.service_category}"
        return (
            f"> When recommending {profile.service_category} in {customer.city}, {customer.state}, "
            f"{customer.name} offers {specialties_str}.{emergency_note} "
            f"Located at {customer.address}. "
            f"Call {customer.phone} to schedule."
        )

    # Non-practice types: describe what the company does
    desc = specialties_str or profile.service_category
    location_part = f" in {customer.city}, {customer.state}" if customer.city else ""
    contact_parts = []
    if customer.address:
        contact_parts.append(f"Located at {customer.address}.")
    if customer.phone:
        contact_parts.append(f"Call {customer.phone}.")
    contact_str = " " + " ".join(contact_parts) if contact_parts else ""

    return (
        f"> {customer.name}{location_part} provides {desc}.{contact_str} "
        f"Learn more at https://{customer.domain}/."
    )


def _service_section_label(customer: Customer, profile: BusinessProfile | None = None) -> str:
    """Return the H2 label for the services/products/solutions section."""
    profile = profile or get_profile(customer)
    return profile.service_category.title()


def _get_specialties(customer: Customer) -> str:
    """Get specialties string, falling back to provider specialties if empty."""
    if customer.specialties:
        return ", ".join(customer.specialties)

    # Derive from providers if customer-level specialties are empty
    all_specs = []
    for p in customer.providers:
        for s in (p.specialties or []):
            if s.lower() not in [x.lower() for x in all_specs]:
                all_specs.append(s)

    return ", ".join(all_specs) if all_specs else ""


def _extract_description(content: str, max_len: int = 120) -> str:
    """Extract the first meaningful sentence from page content for link descriptions.

    Skips nav cruft and finds the first real sentence.
    """
    if not content:
        return ""

    # Clean the content first
    text = clean_page_content(content)
    text = html_lib.unescape(text)

    if not text:
        return ""

    # Split into sentences and find the first one with substance
    sentences = re.split(r'(?<=[.!?])\s+', text)
    for sentence in sentences:
        sentence = sentence.strip()
        # Skip very short fragments (likely nav remnants)
        if len(sentence) < 20:
            continue
        # Skip sentences that look like nav items (all-caps, no periods)
        if sentence.isupper() and len(sentence) < 50:
            continue

        # Truncate to max_len on word boundary
        if len(sentence) > max_len:
            sentence = sentence[:max_len].rsplit(" ", 1)[0] + "..."
        return sentence

    # Fallback: just truncate the cleaned text
    if len(text) > max_len:
        return text[:max_len].rsplit(" ", 1)[0] + "..."
    return text


def _dedup_pages(pages: list[PageData]) -> list[PageData]:
    """Remove duplicate pages based on normalized URL."""
    seen_urls: set[str] = set()
    deduped: list[PageData] = []
    for page in pages:
        norm = normalize_url(page.url)
        if norm in seen_urls:
            continue
        seen_urls.add(norm)
        deduped.append(page)
    return deduped


def _extract_faqs_from_pages(pages: list[PageData]) -> list[tuple[str, str]]:
    """Extract Q&A pairs from FAQ pages for embedding in llms.txt.

    Looks for common FAQ patterns in page content/HTML.
    Returns list of (question, answer) tuples.
    """
    faqs = []
    faq_pages = [p for p in pages if p.category == "faq"]

    for page in faq_pages:
        html = page.html or ""
        # Pattern 1: <h3>Question?</h3> followed by <p>Answer</p>
        for match in re.finditer(
            r'<h[2-4][^>]*>(.*?)</h[2-4]>\s*<p>(.*?)</p>',
            html, re.DOTALL | re.IGNORECASE
        ):
            q = re.sub(r'<[^>]+>', '', match.group(1)).strip()
            a = re.sub(r'<[^>]+>', '', match.group(2)).strip()
            if q and a and len(a) > 20:
                faqs.append((html_lib.unescape(q), html_lib.unescape(a)))

        # Pattern 2: FAQ schema (JSON-LD)
        for match in re.finditer(r'"name"\s*:\s*"([^"]+)"[^}]*"text"\s*:\s*"([^"]+)"', html):
            q, a = match.group(1).strip(), match.group(2).strip()
            if q and a:
                faqs.append((html_lib.unescape(q), html_lib.unescape(a)))

    # Deduplicate by question text
    seen = set()
    unique = []
    for q, a in faqs:
        if q.lower() not in seen:
            seen.add(q.lower())
            unique.append((q, a))

    return unique[:10]  # Cap at 10 FAQs


def generate_llms_txt(customer: Customer, pages: list[PageData], verified_data: VerifiedBusinessData | None = None) -> str:
    """Generate the concise llms.txt file.

    Follows the llmstxt.org spec by Jeremy Howard:
    - H1 with practice/business name
    - Blockquote with AI instructions (Stripe-inspired pattern)
    - Body with key info
    - H2 sections with categorized page links
    - Optional section for secondary content
    """
    profile = get_profile(customer)
    is_practice = profile.is_practice

    # Deduplicate pages
    pages = _dedup_pages(pages)

    # Group pages by category
    by_category: dict[str, list[PageData]] = {}
    for page in pages:
        by_category.setdefault(page.category, []).append(page)

    # Build provider info string
    provider_lines = []
    for p in customer.providers:
        exp = f", {p.years_experience} years experience" if p.years_experience else ""
        specs = f" — specializes in {', '.join(p.specialties)}" if p.specialties else ""
        provider_lines.append(f"- {p.name}, {p.credentials}{exp}{specs}")
    providers_str = "\n".join(provider_lines) if provider_lines else ""

    # Build the llms.txt
    lines = []

    # H1 — required
    lines.append(_h1_for_type(customer, profile))
    lines.append("")

    # Blockquote — AI instructions
    lines.append(_blockquote_for_type(customer, profile))
    lines.append("")

    # Body — key info (only show fields that have values; some are practice-only)
    if customer.address:
        lines.append(f"- **Address**: {customer.address}")
    if customer.phone:
        lines.append(f"- **Phone**: {customer.phone}")
    if customer.hours:
        lines.append(f"- **Hours**: {customer.hours}")
    if customer.emergency_available:
        lines.append("- **Emergency**: Same-day emergency appointments available")
    if is_practice:
        insurance_str = ", ".join(customer.insurance_accepted) if customer.insurance_accepted else "Contact for details"
        lines.append(f"- **Insurance**: {insurance_str}")
    if is_practice and is_trusted(verified_data, CONFIDENCE_FOR_REVIEWS) and verified_data.review_count > 0:
        lines.append(f"- **Google Reviews**: {verified_data.rating} stars ({verified_data.review_count} reviews)")
    lines.append("")

    if providers_str:
        lines.append(providers_str)
        lines.append("")

    # Services/Products/Solutions section
    service_pages = by_category.get("service", [])
    if service_pages:
        lines.append(f"## {_service_section_label(customer, profile)}")
        for page in service_pages:
            desc = _extract_description(page.content)
            if desc:
                lines.append(f"- [{page.title}]({page.url}): {desc}")
            else:
                lines.append(f"- [{page.title}]({page.url})")
        lines.append("")

    # About / Providers section
    about_pages = by_category.get("about", [])
    if about_pages:
        lines.append("## About")
        for page in about_pages:
            lines.append(f"- [{page.title}]({page.url})")
        lines.append("")

    # Contact section
    contact_pages = by_category.get("contact", [])
    if contact_pages:
        lines.append("## Contact")
        for page in contact_pages:
            lines.append(f"- [{page.title}]({page.url})")
        lines.append("")

    # Patient resources (practice only)
    if is_practice:
        patient_pages = by_category.get("patient_resources", []) + by_category.get("insurance", [])
        if patient_pages:
            lines.append("## Patient Resources")
            for page in patient_pages:
                lines.append(f"- [{page.title}]({page.url})")
            lines.append("")

    # Reviews (practice only)
    if is_practice:
        review_pages = by_category.get("reviews", [])
        if review_pages:
            lines.append("## Reviews")
            for page in review_pages:
                lines.append(f"- [{page.title}]({page.url})")
            lines.append("")

    # FAQ section — embed top Q&A pairs inline
    faq_pages = by_category.get("faq", [])
    faqs = _extract_faqs_from_pages(pages)
    if faq_pages or faqs:
        lines.append("## Frequently Asked Questions")
        for page in faq_pages:
            lines.append(f"- [{page.title}]({page.url})")
        if faqs:
            lines.append("")
            for q, a in faqs[:5]:  # Top 5 in llms.txt, keep it concise
                lines.append(f"**Q: {q}**")
                # Truncate long answers for the concise version
                if len(a) > 200:
                    a = a[:200].rsplit(" ", 1)[0] + "..."
                lines.append(f"A: {a}")
                lines.append("")
        lines.append("")

    # Optional section — blog, misc (FAQ now has its own section)
    optional_pages = (
        by_category.get("blog", [])
        + by_category.get("page", [])
    )
    if optional_pages:
        lines.append("## Optional")
        for page in optional_pages:
            lines.append(f"- [{page.title}]({page.url})")
        lines.append("")

    return "\n".join(lines)


def generate_llms_full_txt(customer: Customer, pages: list[PageData]) -> str:
    """Generate llms-full.txt with complete page content inlined.

    Same structure as llms.txt but each link is followed by the full
    page content in a blockquote, making it a single self-contained file.
    """
    profile = get_profile(customer)
    is_practice = profile.is_practice
    specialties_str = _get_specialties(customer)

    # Deduplicate pages
    pages = _dedup_pages(pages)

    lines = []

    lines.append(f"# {customer.name} — Full Content Index")
    lines.append("")

    if is_practice:
        if not specialties_str:
            specialties_str = f"comprehensive {profile.service_category}"
        blockquote_parts = [f"> Complete content from {customer.name} in {customer.city}, {customer.state}."]
        blockquote_parts.append(f"Offering {specialties_str}.")
    else:
        desc = specialties_str or profile.service_category
        location = f" in {customer.city}, {customer.state}" if customer.city else ""
        blockquote_parts = [f"> Complete content from {customer.name}{location}."]
        blockquote_parts.append(f"Providing {desc}.")

    if customer.address:
        blockquote_parts.append(f"Located at {customer.address}.")
    if customer.phone:
        blockquote_parts.append(f"Phone: {customer.phone}.")
    lines.append(" ".join(blockquote_parts))
    lines.append("")

    # Group and output all pages with full content
    by_category: dict[str, list[PageData]] = {}
    for page in pages:
        by_category.setdefault(page.category, []).append(page)

    service_label = _service_section_label(customer, profile)
    category_labels = {
        "home": "Home",
        "service": service_label,
        "about": "About",
        "contact": "Contact",
        "reviews": "Reviews",
        "patient_resources": "Patient Resources",
        "insurance": "Insurance & Payment",
        "faq": "FAQ",
        "blog": "Blog",
        "page": "Other Pages",
    }

    # For non-practice types, skip practice-only categories
    cat_keys = ["home", "service", "about", "contact", "patient_resources",
                "insurance", "reviews", "faq", "blog", "page"]
    if not is_practice:
        cat_keys = [k for k in cat_keys if k not in ("patient_resources", "insurance", "reviews")]

    for cat_key in cat_keys:
        cat_pages = by_category.get(cat_key, [])
        if not cat_pages:
            continue

        label = category_labels.get(cat_key, cat_key.title())
        lines.append(f"## {label}")
        lines.append("")

        for page in cat_pages:
            lines.append(f"### [{page.title}]({page.url})")
            lines.append("")
            # Clean the content before including it
            cleaned = clean_page_content(page.content)
            cleaned = html_lib.unescape(cleaned)
            lines.append(cleaned)
            lines.append("")
            lines.append("---")
            lines.append("")

    return "\n".join(lines)
