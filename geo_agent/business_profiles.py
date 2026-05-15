"""Business profile resolution for multi-industry support.

Maps customer business_type to industry-specific configuration used by
generators, analyzers, and content recommenders. This is the single source
of truth for how the agent adapts its output to different business types.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BusinessProfile:
    """Industry-specific configuration for a customer."""

    # Schema.org type for the primary entity
    schema_type: str = "LocalBusiness"
    schema_id_suffix: str = "business"
    # Only set for medical/dental businesses
    schema_specialty: str | None = None
    # Additional schema.org type (e.g. SoftwareApplication)
    additional_schema_type: str | None = None

    # Human-readable labels
    industry: str = "business"
    industry_label: str = "Business"
    customer_term: str = "customers"  # "patients" for dental
    provider_term: str = "team members"  # "doctors" for dental

    # Content generation
    service_category: str = "services"
    content_expert_label: str = "content strategist"

    # Crawler: page category keywords for service pages
    service_keywords: list[str] = field(default_factory=lambda: [
        "service", "product", "solution", "platform", "feature",
        "integration", "api", "pricing", "demo", "case-study", "partner",
    ])

    # Whether to include practice-specific sections (insurance, patient resources, etc.)
    is_practice: bool = False
    # Whether to include dental-specific crawler slugs
    use_dental_slugs: bool = False

    # FAQ topic seeds for schema generation
    faq_seeds: list[str] = field(default_factory=list)


# Pre-built profiles for known business types
PROFILES: dict[str, BusinessProfile] = {
    "practice": BusinessProfile(
        schema_type="Dentist",
        schema_id_suffix="dentist",
        schema_specialty="Dentistry",
        industry="dental",
        industry_label="Dental Practice",
        customer_term="patients",
        provider_term="doctors",
        service_category="dental services",
        content_expert_label="dental content strategist",
        service_keywords=[
            "service", "implant", "cosmetic", "whitening",
            "crown", "veneer", "invisalign", "orthodont",
            "cleaning", "filling", "root canal", "extraction",
            "denture", "bridge", "sedation", "emergency",
        ],
        is_practice=True,
        use_dental_slugs=True,
        faq_seeds=[
            "What services do you offer?",
            "Do you accept insurance?",
            "Do you offer emergency dental care?",
            "How do I schedule an appointment?",
        ],
    ),
    "technology": BusinessProfile(
        schema_type="Organization",
        schema_id_suffix="organization",
        additional_schema_type="https://schema.org/SoftwareApplication",
        industry="technology",
        industry_label="Technology Company",
        customer_term="clients",
        provider_term="team members",
        service_category="solutions",
        content_expert_label="B2B technology content strategist",
        service_keywords=[
            "product", "solution", "platform", "feature",
            "integration", "api", "pricing", "demo",
            "case-study", "partner", "enterprise",
        ],
        faq_seeds=[
            "What does your platform do?",
            "How does your product work?",
            "What integrations do you offer?",
        ],
    ),
    "product": BusinessProfile(
        schema_type="Organization",
        schema_id_suffix="organization",
        industry="product",
        industry_label="Product Company",
        customer_term="customers",
        provider_term="team members",
        service_category="products",
        content_expert_label="product content strategist",
        service_keywords=[
            "product", "solution", "feature", "pricing",
            "shop", "store", "catalog", "collection",
        ],
        faq_seeds=[
            "What products do you offer?",
            "How do I place an order?",
            "What is your return policy?",
        ],
    ),
    "ecommerce": BusinessProfile(
        schema_type="Organization",
        schema_id_suffix="organization",
        industry="ecommerce",
        industry_label="E-Commerce Brand",
        customer_term="customers",
        provider_term="team",
        service_category="products",
        content_expert_label="e-commerce content strategist",
        service_keywords=[
            "product", "shop", "store", "catalog", "collection",
            "category", "sale", "deal", "bundle",
        ],
        faq_seeds=[
            "How do I place an order?",
            "What is your shipping policy?",
            "What is your return policy?",
        ],
    ),
    "service": BusinessProfile(
        schema_type="LocalBusiness",
        schema_id_suffix="business",
        industry="service",
        industry_label="Service Business",
        customer_term="customers",
        provider_term="team members",
        service_category="services",
        content_expert_label="service business content strategist",
        service_keywords=[
            "service", "solution", "consultation", "assessment",
            "pricing", "booking", "appointment",
        ],
        faq_seeds=[
            "What services do you offer?",
            "How do I book an appointment?",
            "What areas do you serve?",
        ],
    ),
    "precious_metals_buyer": BusinessProfile(
        schema_type="LocalBusiness",
        schema_id_suffix="business",
        industry="precious metals & jewelry buying",
        industry_label="Precious Metals & Jewelry Buyer",
        customer_term="customers",
        provider_term="appraisers",
        service_category="buying services",
        content_expert_label="precious metals and jewelry buying content strategist",
        service_keywords=[
            "gold", "silver", "diamond", "estate", "coin", "watch",
            "sterling", "platinum", "jewelry", "bullion", "sell",
            "buy", "appraisal", "evaluation",
        ],
        faq_seeds=[
            "How does the selling process work?",
            "How do you determine the value of my items?",
            "Do I need an appointment?",
            "How quickly will I get paid?",
        ],
    ),
}


def get_profile(customer_or_type) -> BusinessProfile:
    """Resolve the business profile for a customer or business_type string.

    Args:
        customer_or_type: Either a Customer object (with .business_type attr)
            or a string business_type value.

    Returns:
        BusinessProfile for the resolved type, falling back to a generic profile.
    """
    if isinstance(customer_or_type, str):
        btype = customer_or_type
    else:
        btype = getattr(customer_or_type, "business_type", "practice")

    if btype in PROFILES:
        return PROFILES[btype]

    # Fallback: return a generic LocalBusiness profile
    return BusinessProfile(
        industry=btype or "business",
        industry_label=(btype or "business").replace("_", " ").title(),
    )
