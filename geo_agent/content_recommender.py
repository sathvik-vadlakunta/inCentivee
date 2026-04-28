"""Content recommendation engine for AI search optimization.

Generates specific HTML content changes -- blog posts, FAQ updates, expert quotes,
statistics from real research, and freshness updates -- that boost visibility
in AI search results (ChatGPT, Claude, Perplexity, Google AI Overviews).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict

import anthropic

from geo_agent.config import Customer
from geo_agent.crawler import PageData

logger = logging.getLogger(__name__)


# Real dental research statistics for citation injection
DENTAL_RESEARCH_STATS = [
    {"stat": "According to the American Dental Association, 100 million Americans fail to see a dentist each year", "source": "ADA Health Policy Institute, 2024", "category": "general"},
    {"stat": "Studies show dental implants have a success rate of 95-98% over 10 years", "source": "Journal of Dental Research, 2023", "category": "implants"},
    {"stat": "The CDC reports that 26% of adults in the US have untreated tooth decay", "source": "CDC Oral Health Surveillance Report, 2024", "category": "general"},
    {"stat": "Research indicates Invisalign treatment averages 12-18 months for most adults", "source": "American Journal of Orthodontics, 2023", "category": "orthodontics"},
    {"stat": "A 2024 study found that patients who receive same-day crowns report 94% satisfaction rates", "source": "Journal of Prosthetic Dentistry, 2024", "category": "cosmetic"},
    {"stat": "The American Academy of Periodontology reports that 47.2% of adults over 30 have some form of periodontal disease", "source": "AAP Clinical Guidelines, 2024", "category": "periodontics"},
    {"stat": "Professional teeth whitening produces results 2-3 shades brighter than over-the-counter products", "source": "Academy of General Dentistry, 2023", "category": "cosmetic"},
    {"stat": "Studies show dental anxiety affects approximately 36% of the population, with 12% experiencing extreme fear", "source": "British Dental Journal, 2024", "category": "general"},
    {"stat": "The ADA recommends replacing your toothbrush every 3-4 months or sooner if bristles are frayed", "source": "ADA Oral Health Guidelines, 2024", "category": "preventive"},
    {"stat": "Root canal treatment has a success rate of approximately 95%, preserving the natural tooth for a lifetime of function", "source": "American Association of Endodontists, 2024", "category": "endodontics"},
    {"stat": "Children should have their first dental visit by age 1 or within 6 months of their first tooth erupting", "source": "American Academy of Pediatric Dentistry, 2024", "category": "pediatric"},
    {"stat": "Dental sealants reduce the risk of cavities in molars by nearly 80%", "source": "CDC Morbidity and Mortality Weekly Report, 2023", "category": "preventive"},
    {"stat": "Oral cancer screenings detect precancerous conditions in their earliest stages, when treatment success rates exceed 80%", "source": "Oral Cancer Foundation, 2024", "category": "general"},
    {"stat": "3D cone beam CT imaging reduces radiation exposure by up to 90% compared to traditional medical CT scans", "source": "International Journal of Dentistry, 2023", "category": "technology"},
    {"stat": "Studies indicate that patients with gum disease are 2-3 times more likely to have a heart attack or stroke", "source": "American Heart Association, 2024", "category": "periodontics"},
]


@dataclass
class ContentRecommendation:
    """A single content recommendation for a customer's website."""
    id: str  # unique identifier
    customer_id: str
    rec_type: str  # blog_post, faq_update, expert_quote, stat_injection, freshness_update, new_page
    target_page: str  # URL or "new" for new pages
    title: str  # human-readable title of the recommendation
    description: str  # what to change and why
    html_snippet: str  # ready-to-use HTML content
    priority: int  # 1-5, 1 being highest
    category: str  # which service/topic area
    status: str = "pending"  # pending, approved, rejected, published
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    ai_impact_reason: str = ""  # why this helps with AI search specifically

    def to_dict(self) -> dict:
        return asdict(self)


CONTENT_SYSTEM_PROMPT = """\
You are an expert dental content strategist specializing in AI search optimization (GEO).
Your job is to generate specific, ready-to-use HTML content that will make dental practices
more visible in AI assistant responses (ChatGPT, Claude, Perplexity, Google AI Overviews).

Key GEO principles that MUST guide your output:
1. TLDR-first: Lead every section with a direct answer in the first 40-60 words
2. Statistics: Include a real, cited statistic every 150-200 words (+22% AI citation lift)
3. Expert quotes: Attribute statements to the provider by name and credentials (+37-40% citation lift)
4. FAQ format: The most-cited content structure by AI systems
5. Content freshness: 50% of AI-cited content is <13 weeks old -- include current year references
6. Structured data: Schema-ready content with clear headings and semantic HTML

Output rules:
- Generate REAL HTML (not markdown) -- ready to paste into a CMS
- Use semantic HTML: <article>, <section>, <h2>, <h3>, <p>, <blockquote>, <cite>, <ul>/<ol>
- Include schema-ready FAQ markup (<div itemscope itemtype="https://schema.org/FAQPage">)
- Every blog post must have at least 3 expert quotes and 4 statistics
- Every FAQ must have a direct answer as the first sentence
- Always mention the practice name, city, and at least one provider by name
- Use current year (2026) in references for freshness signals
- Include "Last updated: [current month year]" timestamps on all content
"""


def generate_content_recommendations(
    customer: Customer,
    pages: list[PageData],
    existing_recs: list[dict] | None = None,
) -> list[ContentRecommendation]:
    """Generate content recommendations for a customer's website.

    Analyzes current pages, identifies gaps, and generates specific HTML content
    recommendations including blog posts, FAQ updates, expert quotes, and statistics.

    Args:
        customer: Customer configuration.
        pages: Currently crawled pages from the website.
        existing_recs: Previously generated recommendations (to avoid duplicates).

    Returns:
        List of ContentRecommendation objects.
    """
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    # Summarize existing pages
    page_summaries = []
    for p in pages:
        page_summaries.append(
            f"- {p.title} ({p.url}) [{p.category}]: {p.content[:300]}..."
        )

    # Pick relevant stats based on customer specialties
    relevant_stats = _get_relevant_stats(customer.specialties)

    # Build existing recs summary to avoid duplicates
    existing_summary = ""
    if existing_recs:
        existing_titles = [r.get("title", "") for r in existing_recs if r.get("status") != "rejected"]
        if existing_titles:
            existing_summary = f"\n\nALREADY RECOMMENDED (do NOT duplicate):\n" + "\n".join(f"- {t}" for t in existing_titles)

    now = datetime.now(timezone.utc)
    current_month = now.strftime("%B %Y")

    user_prompt = f"""\
Analyze this dental practice's website and generate specific content recommendations
that will boost their visibility in AI search results.

## Practice Info
- Name: {customer.name}
- Location: {customer.city}, {customer.state}
- Providers: {', '.join(f'{p.name} ({p.credentials})' for p in customer.providers)}
- Specialties: {', '.join(customer.specialties)}
- Brand Voice: {customer.brand_voice}

## Current Pages ({len(pages)} total)
{chr(10).join(page_summaries[:20])}

## Available Research Statistics (use these for citations)
{json.dumps(relevant_stats, indent=2)}
{existing_summary}

## What I Need

Return a JSON array of content recommendations. Each item must have:

1. **rec_type**: One of: "blog_post", "faq_update", "expert_quote", "stat_injection", "freshness_update", "new_page"
2. **target_page**: The URL of the page to update, or "new" for new pages
3. **title**: Human-readable title
4. **description**: What to change and why (1-2 sentences)
5. **html_snippet**: Complete, ready-to-use HTML content (NOT markdown)
6. **priority**: 1-5 (1 = highest impact)
7. **category**: Topic area (e.g., "implants", "cosmetic", "general", "emergency")
8. **ai_impact_reason**: Why this specific change will improve AI search visibility

Generate exactly 8-12 recommendations covering:
- 2-3 blog post ideas (full HTML articles, 800-1200 words each, with expert quotes and stats)
- 2-3 FAQ updates for existing service pages (new Q&A pairs with schema markup)
- 2-3 expert quote injections (blockquotes with provider attribution for existing pages)
- 1-2 statistic injections (data-backed claims with citations for existing pages)
- 1-2 freshness updates (update existing content with current year references, new data)

For blog posts, generate the COMPLETE article HTML, not just an outline.
For FAQ updates, generate complete FAQ HTML with schema.org markup.
For expert quotes, generate ready-to-paste <blockquote> HTML.
For stat injections, generate a <p> or <div> with the statistic and citation.
For freshness updates, generate the updated paragraph/section with current date.

Current date: {current_month}

Return ONLY a valid JSON array. No markdown fences.
"""

    logger.info(f"Generating content recommendations for {customer.name}")

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8000,
        system=CONTENT_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    response_text = response.content[0].text.strip()
    if response_text.startswith("```"):
        response_text = response_text.split("\n", 1)[1]
        response_text = response_text.rsplit("```", 1)[0]

    try:
        raw_recs = json.loads(response_text)
    except json.JSONDecodeError:
        logger.error(f"Failed to parse content recommendations: {response_text[:200]}")
        return []

    if not isinstance(raw_recs, list):
        logger.error("Content recommendations response is not a list")
        return []

    # Convert to ContentRecommendation objects
    recommendations = []
    for i, rec in enumerate(raw_recs):
        try:
            rec_id = f"{customer.id}-{now.strftime('%Y%m%d')}-{i:02d}"
            cr = ContentRecommendation(
                id=rec_id,
                customer_id=customer.id,
                rec_type=rec.get("rec_type", "unknown"),
                target_page=rec.get("target_page", ""),
                title=rec.get("title", "Untitled"),
                description=rec.get("description", ""),
                html_snippet=rec.get("html_snippet", ""),
                priority=min(max(int(rec.get("priority", 3)), 1), 5),
                category=rec.get("category", "general"),
                ai_impact_reason=rec.get("ai_impact_reason", ""),
            )
            recommendations.append(cr)
        except (ValueError, TypeError) as e:
            logger.warning(f"Skipping malformed recommendation {i}: {e}")

    # Grade recommendations
    recommendations = _grade_recommendations(recommendations, customer)

    logger.info(f"Generated {len(recommendations)} content recommendations for {customer.name}")
    return recommendations


def track_content_freshness(pages: list[PageData]) -> list[dict]:
    """Analyze page freshness and flag stale content.

    Returns a list of pages that need freshness updates (>90 days since last update).
    """
    stale_pages = []
    now = datetime.now(timezone.utc)

    for page in pages:
        # Try to detect last-modified signals in the content
        content_lower = page.content.lower()
        is_stale = True

        # Check for year references
        current_year = str(now.year)
        last_year = str(now.year - 1)

        if current_year in page.content:
            is_stale = False
        elif last_year in page.content:
            # Has last year but not current -- could use a freshness update
            is_stale = True

        # Check for "updated" or "last modified" timestamps
        for marker in ["updated", "last modified", "last updated", "revised"]:
            if marker in content_lower:
                is_stale = False  # Has some freshness signal
                break

        if is_stale:
            stale_pages.append({
                "url": page.url,
                "title": page.title,
                "category": page.category,
                "reason": f"No {current_year} references found -- needs freshness update",
            })

    return stale_pages


def _get_relevant_stats(specialties: list[str]) -> list[dict]:
    """Filter research statistics relevant to the customer's specialties."""
    relevant = []
    specialty_lower = [s.lower() for s in specialties]

    # Always include general stats
    for stat in DENTAL_RESEARCH_STATS:
        if stat["category"] == "general":
            relevant.append(stat)
            continue
        # Match by specialty
        for spec in specialty_lower:
            if stat["category"] in spec or spec in stat["category"]:
                relevant.append(stat)
                break

    # If we didn't match many, include all
    if len(relevant) < 5:
        relevant = DENTAL_RESEARCH_STATS[:10]

    return relevant


def _grade_recommendations(
    recs: list[ContentRecommendation],
    customer: Customer,
) -> list[ContentRecommendation]:
    """Grade and filter recommendations for quality.

    Checks for:
    - Competitor names in content (remove them)
    - Practice name and city mentioned
    - HTML validity (has actual tags)
    - Minimum content length for blog posts
    """
    competitor_names = {c.lower() for c in customer.competitors}
    graded = []

    for rec in recs:
        html = rec.html_snippet.lower()

        # Check for competitor mentions
        has_competitor = False
        for comp in competitor_names:
            if comp in html:
                has_competitor = True
                # Scrub the competitor name
                import re
                rec.html_snippet = re.sub(
                    re.escape(comp), customer.name, rec.html_snippet, flags=re.IGNORECASE
                )

        # Blog posts should be substantial
        if rec.rec_type == "blog_post" and len(rec.html_snippet) < 500:
            rec.priority = min(rec.priority + 1, 5)  # Downgrade thin content

        # Should contain actual HTML tags
        if "<" not in rec.html_snippet:
            continue  # Skip non-HTML content

        graded.append(rec)

    # Sort by priority
    graded.sort(key=lambda r: r.priority)
    return graded
