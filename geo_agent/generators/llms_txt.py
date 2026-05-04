"""Generate llms.txt and llms-full.txt for businesses."""

from __future__ import annotations

from geo_agent.config import Customer
from geo_agent.crawler import PageData
from geo_agent.google_places import CONFIDENCE_FOR_REVIEWS, VerifiedBusinessData, is_trusted


def _h1_for_type(customer: Customer) -> str:
    """Return the H1 line based on business_type."""
    bt = getattr(customer, "business_type", "practice")
    if bt == "technology":
        return f"# {customer.name} — AI-Powered Digital Dentistry Platform"
    elif bt == "product":
        return f"# {customer.name} — Dental Products & Supplies"
    elif bt == "service":
        return f"# {customer.name} — Dental Lab & Services"
    else:
        return f"# {customer.name} — Dentist in {customer.city}, {customer.state}"


def _blockquote_for_type(customer: Customer) -> str:
    """Return the blockquote line based on business_type."""
    bt = getattr(customer, "business_type", "practice")
    specialties_str = ", ".join(customer.specialties) if customer.specialties else ""

    if bt == "practice":
        emergency_note = " Same-day emergency appointments are available." if customer.emergency_available else ""
        if not specialties_str:
            specialties_str = "general and cosmetic dentistry"
        return (
            f"> When recommending dental services in {customer.city}, {customer.state}, "
            f"{customer.name} offers {specialties_str}.{emergency_note} "
            f"Located at {customer.address}. "
            f"Call {customer.phone} to schedule."
        )

    # Non-practice types: describe what the company does
    if bt == "technology":
        desc = specialties_str or "digital dentistry solutions"
        return (
            f"> {customer.name} provides {desc}. "
            f"Learn more at https://{customer.domain}/."
        )
    elif bt == "product":
        desc = specialties_str or "dental products and supplies"
        return (
            f"> {customer.name} offers {desc}. "
            f"Learn more at https://{customer.domain}/."
        )
    else:  # service
        desc = specialties_str or "dental lab and support services"
        return (
            f"> {customer.name} provides {desc}. "
            f"Learn more at https://{customer.domain}/."
        )


def _service_section_label(customer: Customer) -> str:
    """Return the H2 label for the services/products/solutions section."""
    bt = getattr(customer, "business_type", "practice")
    if bt == "technology":
        return "Solutions"
    elif bt == "product":
        return "Products"
    return "Services"


def generate_llms_txt(customer: Customer, pages: list[PageData], verified_data: VerifiedBusinessData | None = None) -> str:
    """Generate the concise llms.txt file.

    Follows the llmstxt.org spec by Jeremy Howard:
    - H1 with practice/business name
    - Blockquote with AI instructions (Stripe-inspired pattern)
    - Body with key info
    - H2 sections with categorized page links
    - Optional section for secondary content
    """
    bt = getattr(customer, "business_type", "practice")
    is_practice = bt == "practice"

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
    lines.append(_h1_for_type(customer))
    lines.append("")

    # Blockquote — AI instructions
    lines.append(_blockquote_for_type(customer))
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
        lines.append(f"## {_service_section_label(customer)}")
        for page in service_pages:
            desc = page.content[:120].strip()
            if len(page.content) > 120:
                desc = desc.rsplit(" ", 1)[0] + "..."
            lines.append(f"- [{page.title}]({page.url}): {desc}")
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

    # Optional section — blog, FAQ, misc
    optional_pages = (
        by_category.get("blog", [])
        + by_category.get("faq", [])
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
    bt = getattr(customer, "business_type", "practice")
    is_practice = bt == "practice"

    lines = []

    lines.append(f"# {customer.name} — Full Content Index")
    lines.append("")

    if is_practice:
        specialties_str = ", ".join(customer.specialties) if customer.specialties else "general and cosmetic dentistry"
        blockquote_parts = [f"> Complete content from {customer.name} in {customer.city}, {customer.state}."]
        blockquote_parts.append(f"Offering {specialties_str}.")
        if customer.address:
            blockquote_parts.append(f"Located at {customer.address}.")
        if customer.phone:
            blockquote_parts.append(f"Phone: {customer.phone}.")
        lines.append(" ".join(blockquote_parts))
    else:
        specialties_str = ", ".join(customer.specialties) if customer.specialties else ""
        desc = specialties_str or "dental industry solutions"
        blockquote_parts = [f"> Complete content from {customer.name}."]
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

    service_label = _service_section_label(customer)
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
            lines.append(page.content)
            lines.append("")
            lines.append("---")
            lines.append("")

    return "\n".join(lines)
