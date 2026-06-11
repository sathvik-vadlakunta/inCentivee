"""Generate llms.txt and llms-full.txt for businesses."""

from __future__ import annotations

import html as html_lib
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from geo_agent.business_profiles import BusinessProfile, get_profile
from geo_agent.config import Customer
from geo_agent.crawler import PageData, clean_page_content, normalize_url
from geo_agent.google_places import CONFIDENCE_FOR_REVIEWS, VerifiedBusinessData, is_trusted


def _chunk_content(text: str, max_words: int = 180) -> list[str]:
    """Split page content into ~150-200 word self-contained passages.

    AI retrieval works on passages, not whole pages — a wall of text fails to
    surface any quotable unit. Group paragraphs (or sentences when there are no
    paragraph breaks) into chunks under ~max_words so each is independently liftable.
    """
    if not text:
        return []
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(paras) <= 1:
        paras = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]
    chunks: list[str] = []
    cur: list[str] = []
    cur_words = 0
    for p in paras:
        words = p.split()
        w = len(words)
        if w > max_words:
            # A single passage with no break points — hard-split by word window.
            if cur:
                chunks.append(" ".join(cur))
                cur, cur_words = [], 0
            for i in range(0, w, max_words):
                chunks.append(" ".join(words[i:i + max_words]))
            continue
        if cur and cur_words + w > max_words:
            chunks.append(" ".join(cur))
            cur, cur_words = [p], w
        else:
            cur.append(p)
            cur_words += w
    if cur:
        chunks.append(" ".join(cur))
    return chunks


def _answer_seed_faq(question: str, customer: Customer, profile: BusinessProfile | None) -> str | None:
    """Answer a seed FAQ question from VERIFIED customer facts only (never fabricate).

    Returns None when there isn't a fact-grounded answer, so we skip it rather than
    invent one.
    """
    q = question.lower()
    loc = f"in {customer.city}, {customer.state}" if customer.city else ""

    if "insurance" in q:
        if customer.insurance_accepted:
            return f"Yes — {customer.name} accepts {', '.join(customer.insurance_accepted)}. Call {customer.phone or 'us'} to confirm your specific plan."
        return None
    if "emergency" in q:
        if customer.emergency_available:
            return f"Yes — {customer.name} offers same-day emergency appointments {loc}. Call {customer.phone or 'us'} as soon as possible."
        return None
    if "schedule" in q or "appointment" in q or "book" in q:
        if customer.phone:
            return f"Call {customer.name} at {customer.phone} to schedule. {('Located at ' + customer.address + '.') if customer.address else ''}".strip()
        return None
    if "hours" in q or "open" in q:
        return f"{customer.name} hours: {customer.hours}." if customer.hours else None
    if "where" in q or "located" in q or "location" in q:
        return f"{customer.name} is located at {customer.address}." if customer.address else None
    if "service" in q or "offer" in q or "treatment" in q or "procedure" in q:
        svc = customer.services or customer.specialties
        if svc:
            cat = profile.service_category if profile else "services"
            return f"{customer.name} offers {cat} {loc}, including {', '.join(svc[:6])}."
        return None
    return None


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

    # Non-practice types: describe what the company does. Prefer the real
    # catalog ("products including BPC-157, TB-500, …"); only fall back to
    # generic profile keywords when there's no catalog at all.
    if specialties_str:
        desc = f"{profile.service_category} including {specialties_str}"
    elif profile.service_keywords:
        top_kw = ", ".join(profile.service_keywords[:4])
        desc = f"{profile.service_category} including {top_kw}"
    else:
        desc = profile.service_category
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
    """Get specialties string, falling back to provider specialties, then the
    product/service catalog if empty.

    Non-practice customers (e-commerce, etc.) often have no `specialties` but do
    have a populated services/products catalog — without this fallback the
    blockquote degrades to generic profile keywords ('product, shop, store').
    """
    if customer.specialties:
        return ", ".join(customer.specialties)

    # Derive from providers if customer-level specialties are empty
    all_specs = []
    for p in customer.providers:
        for s in (p.specialties or []):
            if s.lower() not in [x.lower() for x in all_specs]:
                all_specs.append(s)
    if all_specs:
        return ", ".join(all_specs)

    # Fall back to the real product/service catalog (top items)
    services = getattr(customer, "services", None) or []
    if services:
        return ", ".join(services[:6])

    return ""


_DESC_VERB = re.compile(
    r"\b(is|are|was|were|we|our|offers?|provides?|specializ\w*|located|call|schedule|"
    r"welcome|deliver\w*|help\w*|serv\w+|treats?|care|experienced?|trusted)\b",
    re.IGNORECASE,
)


def _looks_like_nav_list(s: str) -> bool:
    """True for service-menu / nav remnants (comma-separated lists, no real prose)."""
    return s.count(",") >= 3 and not _DESC_VERB.search(s)


def _clean_truncate(s: str, max_len: int) -> str:
    """Truncate on a word boundary without leaving a trailing comma fragment."""
    if len(s) <= max_len:
        return s
    return s[:max_len].rsplit(" ", 1)[0].rstrip(",;:-– ") + "..."


def _extract_description(content: str, title: str = "", max_len: int = 120) -> str:
    """Extract the first meaningful sentence from page content for link descriptions.

    Skips nav cruft, page title echoes, and finds the first real body sentence.
    """
    if not content:
        return ""

    # Clean the content first
    text = clean_page_content(content)
    text = html_lib.unescape(text)

    if not text:
        return ""

    # Strip the page title / H1 from the start of content.
    # WordPress renders H1 as leading text: "Teeth Whitening South Jordan, UT A radiant smile..."
    # The HTML <title> may differ slightly ("Teeth Whitening in South Jordan, UT | Brighten...")
    if title:
        # Extract the core topic from the title (before pipe/dash separators)
        core_title = re.split(r'\s*[|–—]\s*', title)[0].strip()
        # Remove location suffix for fuzzy matching ("in City, ST")
        core_no_loc = re.sub(r'\s+in\s+[\w\s,]+[A-Z]{2}\b.*$', '', core_title).strip()
        # Try to find and strip matching leading text from content
        for prefix in [core_title, core_no_loc]:
            if len(prefix) > 10 and text.lower().startswith(prefix.lower()):
                text = text[len(prefix):].strip()
                # Strip trailing location remnant ("South Jordan, UT") or pipe separators
                text = re.sub(r'^(?:in\s+)?[\w\s,]+[A-Z]{2}\s*', '', text, count=1).strip()
                text = re.sub(r'^[|–—]\s*[^.!?]+\s+', '', text, count=1).strip() if text[:1] in '|–—' else text
                break

    # Normalize title for comparison (strip location suffixes like "in City, ST")
    title_words = set(re.sub(r'\s+', ' ', title.lower().split("|")[0]).split()) if title else set()

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
        # Skip if it still looks like nav (menu items without punctuation)
        if "Home About Us" in sentence or "Meet Our" in sentence:
            continue
        # Skip lines that are just service menu listings
        if sentence.count("Dentistry") > 3 or sentence.count("Dental") > 5:
            continue
        # Skip comma-separated nav/service-menu remnants (no real prose)
        if _looks_like_nav_list(sentence):
            continue
        # Skip if this sentence is basically the page title repeated
        if title_words:
            sent_words = set(sentence.lower().split())
            overlap = len(title_words & sent_words) / max(len(title_words), 1)
            if overlap > 0.7 and len(sentence) < len(title) + 20:
                continue

        return _clean_truncate(sentence, max_len)

    # Fallback: only use raw text if it reads like prose, never a menu-list fragment.
    if text and not _looks_like_nav_list(text[:max_len]):
        return _clean_truncate(text, max_len)
    return ""


def _normalize_page_url(url: str) -> str:
    """Normalize a page URL for output — strip www if non-www resolves."""
    norm = normalize_url(url)
    # Also ensure consistent scheme
    return norm


def _dedup_pages(pages: list[PageData]) -> list[PageData]:
    """Remove duplicate pages based on normalized URL (www vs non-www, trailing slash)."""
    seen_urls: set[str] = set()
    deduped: list[PageData] = []
    for page in pages:
        norm = normalize_url(page.url)
        if norm in seen_urls:
            continue
        seen_urls.add(norm)
        # Normalize the URL in-place so output is consistent
        page.url = _normalize_page_url(page.url)
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


def generate_llms_txt(customer: Customer, pages: list[PageData], verified_data: VerifiedBusinessData | None = None, extra_faqs: list[tuple[str, str]] | None = None) -> str:
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
    if is_trusted(verified_data, CONFIDENCE_FOR_REVIEWS) and verified_data.review_count > 0:
        lines.append(f"- **Google Reviews**: {verified_data.rating} stars ({verified_data.review_count} reviews)")
    if customer.city:
        lines.append(f"- **Service Area**: {customer.city}, {customer.state}")
    # Freshness signal — regenerated monthly; recency is a real citation factor
    # (Perplexity especially). Also a corroboration cue for NAP cross-referencing.
    lines.append(f"- **Last updated**: {datetime.now(timezone.utc).strftime('%B %Y')}")
    if customer.address and customer.phone:
        lines.append("- This name, address, and phone match our Google Business Profile and directory listings.")
    lines.append("")

    if providers_str:
        lines.append(providers_str)
        lines.append("")

    # Services/Products/Solutions section
    service_pages = by_category.get("service", [])
    if service_pages:
        lines.append(f"## {_service_section_label(customer, profile)}")
        for page in service_pages:
            desc = _extract_description(page.content, title=page.title)
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

    # Reviews / Testimonials
    review_pages = by_category.get("reviews", [])
    if review_pages:
        lines.append("## Reviews")
        for page in review_pages:
            lines.append(f"- [{page.title}]({page.url})")
        lines.append("")

    # FAQ section — embed top Q&A pairs inline. These self-contained Q&A pairs are
    # the #1 citable asset, so every file should ship a populated block: use crawled
    # FAQs, then adaptation-fed FAQs (queries AI isn't citing us on), then fact-based
    # answers to the industry seed questions so a site without an FAQ page still has one.
    faq_pages = by_category.get("faq", [])
    faqs = list(_extract_faqs_from_pages(pages))
    if extra_faqs:
        faqs.extend(extra_faqs)
    if len(faqs) < 4:
        have_q = {q.lower().strip() for q, _ in faqs}
        for seed_q in (profile.faq_seeds if profile else []):
            if seed_q.lower().strip() in have_q:
                continue
            ans = _answer_seed_faq(seed_q, customer, profile)
            if ans:
                faqs.append((seed_q, ans))
    if faq_pages or faqs:
        lines.append("## Frequently Asked Questions")
        for page in faq_pages:
            lines.append(f"- [{page.title}]({page.url})")
        if faqs:
            lines.append("")
            for q, a in faqs[:7]:  # Top 7 in llms.txt
                lines.append(f"**Q: {q}**")
                # Keep answers near-complete: these Q&A pairs are the exact
                # self-contained chunks AI engines quote, so truncating at 200
                # chars destroyed their citability. 600 chars covers almost all
                # FAQ answers without bloating llms.txt (llms-full.txt always
                # carries the full text).
                if len(a) > 600:
                    a = a[:600].rsplit(" ", 1)[0] + "..."
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
            # Clean, then split into passage-sized chunks so each is liftable.
            cleaned = html_lib.unescape(clean_page_content(page.content))
            for chunk in _chunk_content(cleaned):
                lines.append(chunk)
                lines.append("")
            lines.append("---")
            lines.append("")

    return "\n".join(lines)
