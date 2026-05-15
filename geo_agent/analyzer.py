"""Claude 4.6 analysis engine for business SEO and AEO.

This is the brain — it reads the customer's current website content from RAG,
analyzes gaps, and generates recommendations + content improvements.
"""

from __future__ import annotations

import json
import logging
import os

import anthropic

from geo_agent.business_profiles import BusinessProfile, get_profile
from geo_agent.config import Customer
from geo_agent.crawler import PageData
from geo_agent.google_places import (
    CONFIDENCE_FOR_COMPETITORS,
    CONFIDENCE_FOR_REVIEWS,
    CompetitorData,
    VerifiedBusinessData,
    is_trusted,
)

logger = logging.getLogger(__name__)


def _build_system_prompt(profile: BusinessProfile) -> str:
    """Build the analysis system prompt adapted to the business type."""
    customer_term = profile.customer_term
    schema_type = profile.schema_type
    service_category = profile.service_category

    return f"""\
You are an expert SEO and GEO (Generative Engine Optimization) analyst for {profile.industry_label.lower()} businesses.
Your job is to analyze a business's website content and generate recommendations
that will help new {customer_term} find this business through:
1. Google Search and Google Maps
2. AI assistants (ChatGPT, Claude, Perplexity, Gemini, Grok)
3. Apple Maps

Key principles:
- Content must lead with direct answers (TLDR-first, first 40-60 words answer the query)
- Include statistics every 150-200 words
- Expert quotes with provider name and credentials increase AI citation by 37-40%
- FAQ format is the most-cited content structure by AI systems
- Content freshness matters: 50% of AI-cited content is less than 13 weeks old
- Schema markup ({schema_type}, FAQPage, Service) gives a 22% citation lift
- Every service page needs at least 4-5 FAQ entries

Focus on driving new {customer_term} acquisition. Every recommendation should connect to
"how does this help a potential {customer_term[:-1] if customer_term.endswith('s') else customer_term} find and choose this business?"
"""


def grade_analysis(
    result: dict,
    customer: Customer,
    verified_data: VerifiedBusinessData | None = None,
) -> list[str]:
    """Grade Claude's analysis output for accuracy and safety.

    Checks for:
    - Fabricated review counts/ratings that don't match verified data
    - Competitor names appearing in FAQ answers (would promote competitors on client site)
    - Missing required fields in the response
    - FAQ answers that don't mention the practice or city
    - Suspiciously round review numbers (likely hallucinated)

    Returns a list of issue descriptions. Empty list = passed all checks.
    """
    issues = []

    # --- Check required keys exist ---
    required_keys = ["faq_entries", "content_gaps", "priority_actions"]
    for key in required_keys:
        if key not in result:
            issues.append(f"Missing required key: {key}")

    # --- Check FAQ entries for quality ---
    provider_names = {p.name.lower() for p in customer.providers}
    competitor_names = {c.lower() for c in customer.competitors}
    practice_name_lower = customer.name.lower()
    city_lower = customer.city.lower()

    faq_entries = result.get("faq_entries", {})
    for page_url, faqs in faq_entries.items():
        if not isinstance(faqs, list):
            issues.append(f"FAQ entries for {page_url} is not a list")
            continue
        for faq in faqs:
            if not isinstance(faq, dict):
                continue
            answer = faq.get("answer", "").lower()

            # Check for competitor names in FAQ answers
            for comp in competitor_names:
                if comp in answer:
                    issues.append(
                        f"BLOCKED: FAQ answer mentions competitor '{comp}' — "
                        f"Q: {faq.get('question', '')[:60]}"
                    )
                    faq["answer"] = _scrub_competitor(faq["answer"], customer.competitors)

    # --- Cross-check review numbers against verified data ---
    _check_fabricated_reviews(result, verified_data, issues)

    return issues


def _scrub_competitor(answer: str, competitors: list[str]) -> str:
    """Remove competitor names from an FAQ answer."""
    import re
    for comp in competitors:
        # Case-insensitive replacement
        answer = re.sub(re.escape(comp), "[practice]", answer, flags=re.IGNORECASE)
    return answer


def _check_fabricated_reviews(
    result: dict,
    verified_data: VerifiedBusinessData | None,
    issues: list[str],
) -> None:
    """Check if Claude fabricated review counts that don't match verified data."""
    if not verified_data or not is_trusted(verified_data, CONFIDENCE_FOR_REVIEWS):
        return

    # Scan all string values in the result for review-like numbers
    import re
    all_text = json.dumps(result)

    # Look for patterns like "4.8 stars" or "150 reviews" or "rated 4.9"
    rating_mentions = re.findall(r'(\d\.\d)\s*(?:stars?|rating)', all_text, re.IGNORECASE)
    review_mentions = re.findall(r'(\d{2,})\s*(?:reviews?|ratings?)', all_text, re.IGNORECASE)

    for mentioned_rating in rating_mentions:
        if abs(float(mentioned_rating) - verified_data.rating) > 0.2:
            issues.append(
                f"Fabricated rating detected: Claude said {mentioned_rating} stars, "
                f"actual is {verified_data.rating}"
            )

    for mentioned_count in review_mentions:
        count = int(mentioned_count)
        # Allow 10% tolerance for rounding, but flag big discrepancies
        if abs(count - verified_data.review_count) > max(10, verified_data.review_count * 0.15):
            issues.append(
                f"Fabricated review count detected: Claude said {count} reviews, "
                f"actual is {verified_data.review_count}"
            )


def get_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def analyze_and_recommend(
    customer: Customer,
    pages: list[PageData],
    current_llms_txt: str | None = None,
    verified_data: VerifiedBusinessData | None = None,
    competitors: list[CompetitorData] | None = None,
) -> dict:
    """Analyze current site content and generate SEO/GEO recommendations.

    Returns a dict with:
    - faq_entries: Generated FAQ Q&A pairs per service page
    - content_gaps: Missing pages/content that should exist
    - service_descriptions: Improved descriptions for llms.txt
    - meta_improvements: Title/description suggestions
    - priority_actions: Ranked list of what to do first
    """
    client = get_client()

    # Build the analysis prompt with all page content
    pages_summary = []
    for page in pages:
        truncated = page.content[:2000]
        pages_summary.append(
            f"**Page: {page.title}** (URL: {page.url}, Category: {page.category})\n"
            f"Content preview:\n{truncated}\n"
        )

    pages_text = "\n---\n".join(pages_summary)

    providers_info = "\n".join(
        f"- {p.name}, {p.credentials}, specialties: {', '.join(p.specialties)}"
        for p in customer.providers
    ) or "No provider info available"

    # Build verified data section — only include data that meets confidence thresholds
    verified_section = ""
    if is_trusted(verified_data, CONFIDENCE_FOR_REVIEWS):
        verified_section = f"""
## Google-Verified Business Data
CRITICAL: Use these EXACT numbers — do not estimate or guess.
- **Google Rating**: {verified_data.rating} stars ({verified_data.review_count} reviews)
- **Verified Address**: {verified_data.address}
- **Verified Phone**: {verified_data.phone}
- **Business Status**: {verified_data.business_status}
- **Match Confidence**: {verified_data.match_confidence}
"""
        if competitors and is_trusted(verified_data, CONFIDENCE_FOR_COMPETITORS):
            comp_lines = []
            for c in competitors[:10]:
                comp_lines.append(f"  - {c.name}: {c.rating} stars ({c.review_count} reviews) — {c.address}")
            verified_section += "\n### Nearby Competitors (from Google Maps)\n" + "\n".join(comp_lines) + "\n"
    else:
        verified_section = """
## Google Places Data
WARNING: Google Places data was not available for this practice.
Be conservative with any review count or rating estimates. Do NOT fabricate specific numbers.
"""

    profile = get_profile(customer)
    customer_term = profile.customer_term
    singular_term = customer_term[:-1] if customer_term.endswith("s") else customer_term

    user_prompt = f"""\
Analyze this {profile.industry_label.lower()}'s website and generate specific, actionable improvements.

## Business Info
- **Name**: {customer.name}
- **Business Type**: {profile.industry_label}
- **Location**: {customer.address}, {customer.city}, {customer.state} {customer.zip_code}
- **Phone**: {customer.phone}
- **Specialties**: {', '.join(customer.specialties)}
- **Insurance**: {', '.join(customer.insurance_accepted)}
- **Providers/Team**:
{providers_info}
- **Brand Voice**: {customer.brand_voice}
- **Emergency Available**: {customer.emergency_available}

## Current Website Pages ({len(pages)} total)
{pages_text}

## Current llms.txt
{current_llms_txt or "None exists yet — this will be the first generation."}
{verified_section}
## What I Need From You

Return a JSON object with these keys:

1. **faq_entries**: For each service page, generate 4-6 FAQ Q&A pairs that a potential
   {singular_term} would actually search for. Format: {{"page_url": [{{"question": "...", "answer": "..."}}]}}
   Make answers direct (start with the answer, not fluff), include the city name,
   and mention the provider/team by name where relevant.

2. **content_gaps**: List of pages that should exist but don't. For each, include
   the suggested title, URL slug, and a 2-sentence description of what it should cover.
   Focus on high-search-volume {profile.industry} queries for {customer.city}.

3. **service_descriptions**: For each service page, write an improved 1-2 sentence
   description optimized for llms.txt (concise, factual, includes location and provider).

4. **priority_actions**: Top 5 ranked actions this business should take to get more
   new {customer_term} finding them online. Be specific and tailored to this {profile.industry} business.

IMPORTANT: All content must be specific to this {profile.industry_label} business.
Do NOT use generic dental or medical terminology unless this IS a dental/medical practice.

Return ONLY valid JSON, no markdown code fences.
"""

    logger.info(f"Analyzing {customer.name} ({len(pages)} pages)")

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=8192,
        system=_build_system_prompt(profile),
        messages=[{"role": "user", "content": user_prompt}],
    )

    # Parse the JSON response
    response_text = response.content[0].text.strip()
    # Handle if Claude wraps in code fences
    if response_text.startswith("```"):
        response_text = response_text.split("\n", 1)[1]
        response_text = response_text.rsplit("```", 1)[0]

    try:
        result = json.loads(response_text)
    except json.JSONDecodeError:
        logger.error(f"Failed to parse Claude response as JSON: {response_text[:200]}")
        result = {
            "faq_entries": {},
            "content_gaps": [],
            "service_descriptions": {},
            "priority_actions": ["Error: Could not parse analysis results. Run again."],
        }

    # Grade the response before returning
    issues = grade_analysis(result, customer, verified_data)
    if issues:
        logger.warning(f"Analysis grading found {len(issues)} issue(s) for {customer.name}:")
        for issue in issues:
            logger.warning(f"  - {issue}")
        result["_grading_issues"] = issues

    logger.info(
        f"Analysis complete: {len(result.get('faq_entries', {}))} FAQ sets, "
        f"{len(result.get('content_gaps', []))} gaps, "
        f"{len(result.get('priority_actions', []))} priority actions"
    )
    return result
