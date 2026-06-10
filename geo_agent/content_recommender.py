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

import re

import anthropic

from geo_agent.config import Customer
from geo_agent.crawler import PageData
from geo_agent.llm import MODEL_CONTENT, complete

logger = logging.getLogger(__name__)

# Structured-output schema for content recommendations. The model is constrained
# to emit JSON matching this (output_config.format), so the response is
# guaranteed-valid JSON — no fence stripping or repair needed. JSON Schema strict
# mode: no min/max (use enum for priority), additionalProperties must be false.
_REC_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "rec_type": {
            "type": "string",
            "enum": [
                "blog_post", "faq_update", "stat_injection",
                "freshness_update", "new_page", "expert_quote",
            ],
        },
        "target_page": {"type": "string"},
        "title": {"type": "string"},
        "description": {"type": "string"},
        "html_snippet": {"type": "string"},
        "priority": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
        "category": {"type": "string"},
        "ai_impact_reason": {"type": "string"},
    },
    "required": [
        "rec_type", "target_page", "title", "description",
        "html_snippet", "priority", "category", "ai_impact_reason",
    ],
}
CONTENT_OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "recommendations": {"type": "array", "items": _REC_SCHEMA},
    },
    "required": ["recommendations"],
}


# Research statistics organized by business type
RESEARCH_STATS = {
    "practice": [
        {"stat": "According to the American Dental Association, 100 million Americans fail to see a dentist each year", "source": "ADA Health Policy Institute, 2024", "url": "https://www.ada.org/resources/research/health-policy-institute", "category": "general"},
        {"stat": "A systematic review found dental implants have a cumulative survival rate of approximately 96.4% at 10 years", "source": "Journal of Dentistry, Systematic Review and Meta-Analysis, 2019", "url": "https://www.sciencedirect.com/science/article/abs/pii/S0300571219300491", "category": "implants"},
        {"stat": "The CDC reports that approximately 1 in 4 adults in the US have untreated tooth decay", "source": "CDC Oral Health Surveillance Report, 2024", "url": "https://www.cdc.gov/oral-health/php/2024-oral-health-surveillance-report/selected-findings.html", "category": "general"},
        {"stat": "A 2024 peer-reviewed study found adult clear-aligner treatment averaged about 14.5 months (within the typical 12-18 month range for mild-to-moderate cases)", "source": "Alam et al., Cureus, 2024 (peer-reviewed)", "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC11805330/", "category": "orthodontics"},
        {"stat": "CDC/NHANES data shows that 47.2% of adults aged 30 and older have some form of periodontal disease", "source": "CDC/NIDCR National Health and Nutrition Examination Survey", "url": "https://www.nidcr.nih.gov/research/data-statistics/periodontal-disease/adults", "category": "periodontics"},
        {"stat": "Professional teeth whitening can brighten teeth by 3 to 8 shades in a single visit, compared to 1-2 shades with over-the-counter products", "source": "American Dental Association, Whitening", "url": "https://www.ada.org/resources/ada-library/oral-health-topics/whitening", "category": "cosmetic"},
        {"stat": "The 2021 Adult Oral Health Survey found that approximately 42% of adults experience moderate dental anxiety, with 12% experiencing extreme fear", "source": "British Dental Journal, 2024", "url": "https://www.nature.com/articles/s41415-024-7846-1", "category": "general"},
        {"stat": "Root canal treatment has a success rate of approximately 95%, preserving the natural tooth for decades of function with proper care", "source": "American Association of Endodontists, 2024", "url": "https://www.aae.org/patients/root-canal-treatment/", "category": "endodontics"},
        {"stat": "Children should have their first dental visit by age 1 or within 6 months of their first tooth erupting", "source": "American Academy of Pediatric Dentistry, 2024", "url": "https://www.aapd.org/resources/parent/faq/", "category": "pediatric"},
        {"stat": "Dental sealants reduce the risk of cavities in molars by nearly 80% in the first two years", "source": "CDC Vital Signs, MMWR, 2016", "url": "https://www.cdc.gov/mmwr/volumes/65/wr/mm6541e1.htm", "category": "preventive"},
        {"stat": "Oral cancer screenings detect precancerous conditions in their earliest stages, when treatment success rates exceed 80%", "source": "Oral Cancer Foundation, 2024", "url": "https://oralcancerfoundation.org/facts/", "category": "general"},
        {"stat": "3D cone beam CT imaging reduces radiation exposure by up to 90% compared to traditional medical CT scans", "source": "International Journal of Dentistry, 2023", "url": "https://www.hindawi.com/journals/ijd/", "category": "technology"},
        {"stat": "Studies indicate that patients with gum disease are 2-3 times more likely to have a heart attack or stroke", "source": "American Heart Association, 2024", "url": "https://www.heart.org/en/health-topics/gum-disease-and-heart-disease", "category": "periodontics"},
    ],
    "technology": [
        {"stat": "The global dental CAD/CAM market is projected to reach $4.2B by 2032, growing at a 6.1% CAGR", "source": "Grand View Research, Dental CAD/CAM Market Report, 2024", "url": "https://www.grandviewresearch.com/industry-analysis/dental-cad-cam-market", "category": "market"},
        {"stat": "The U.S. dental laboratory market is projected to exceed $10B by 2032, growing at approximately 10% CAGR", "source": "Fortune Business Insights, U.S. Dental Laboratory Market, 2024", "url": "https://www.fortunebusinessinsights.com/dental-laboratory-market-109498", "category": "market"},
        {"stat": "An audit of dental prescriptions found about 66% were non-compliant with ethical and legal guidelines, driving costly back-and-forth between clinics and labs", "source": "Berry, Nesbit et al., British Dental Journal, 2011 (prescription audit)", "url": "https://www.nature.com/articles/sj.bdj.2011.623", "category": "workflow"},
        {"stat": "The U.S. dental prosthetics market is expected to surpass $8B by 2032, driven by an aging population and rising implant adoption", "source": "Markets and Markets, Dental Prosthetics Report, 2024", "url": "https://www.marketsandmarkets.com/Market-Reports/dental-prosthetics-market-702.html", "category": "market"},
        {"stat": "Digital impression systems have been adopted by over 50% of U.S. dental offices as of 2024", "source": "ADA Health Policy Institute, Dental Technology Survey, 2024", "url": "https://www.ada.org/resources/research/health-policy-institute", "category": "digital"},
        {"stat": "Intraoral scanner adoption in U.S. dental practices has grown from 14% in 2017 to over 50% in 2024", "source": "ADA Health Policy Institute, Technology Adoption Report, 2024", "url": "https://www.ada.org/resources/research/health-policy-institute", "category": "digital"},
    ],
    "legal": [
        {"stat": "There are over 1.3 million active attorneys in the United States (1,322,649 as of January 2024)", "source": "ABA Profile of the Legal Profession / National Lawyer Population Survey, 2024", "url": "https://www.americanbar.org/news/profile-legal-profession/demographics/", "category": "general"},
        {"stat": "Nearly 40% of people who need legal help never reach out to a lawyer, often due to not knowing where to start", "source": "Legal Services Corporation Justice Gap Study, 2022", "url": "https://www.lsc.gov/our-impact/publications/other-publications-and-reports/justice-gap-report", "category": "general"},
        {"stat": "Online reviews influence 84% of consumers as much as a personal recommendation when choosing a lawyer", "source": "BrightLocal Consumer Review Survey, 2024", "url": "https://www.brightlocal.com/research/local-consumer-review-survey/", "category": "marketing"},
        {"stat": "The average cost of hiring a divorce lawyer in the US is $11,300, though this varies significantly by state and complexity", "source": "Martindale-Nolo Legal Fee Survey, 2024", "url": "https://www.nolo.com/legal-encyclopedia/ctp/cost-of-divorce.html", "category": "family_law"},
        {"stat": "Over 50% of potential clients expect a response from a law firm within 1 hour of their inquiry", "source": "Clio Legal Trends Report, 2024", "url": "https://www.clio.com/resources/legal-trends/", "category": "intake"},
        {"stat": "Workers compensation claims account for approximately $100 billion in annual costs to US employers", "source": "National Academy of Social Insurance, 2024", "url": "https://www.nasi.org/research/workers-compensation/", "category": "workers_comp"},
        {"stat": "Tort/personal injury cases take a median of roughly 16 months from filing to disposition, with complex cases taking significantly longer", "source": "BJS Civil Justice Survey of State Courts / NCSC civil caseload data", "url": "https://bjs.ojp.gov/content/pub/ascii/TCILC.TXT", "category": "personal_injury"},
    ],
    "medical": [
        {"stat": "The CDC reports that 83.4% of adults aged 18-64 had contact with a health care professional in the past year", "source": "CDC National Health Interview Survey, 2024", "url": "https://www.cdc.gov/nchs/nhis/index.htm", "category": "general"},
        {"stat": "Telehealth utilization has stabilized at 38x pre-pandemic levels, with 40% of consumers preferring virtual visits for follow-ups", "source": "McKinsey Digital Health Survey, 2024", "url": "https://www.mckinsey.com/industries/healthcare/our-insights/telehealth", "category": "telehealth"},
        {"stat": "Patients who book appointments online are 2.6x more likely to keep their appointment compared to phone bookings", "source": "Accenture Digital Health Consumer Survey, 2024", "url": "https://www.accenture.com/us-en/insights/health", "category": "scheduling"},
        {"stat": "78% of patients use online reviews as their first step in finding a new doctor", "source": "Software Advice Patient Survey, 2024", "url": "https://www.softwareadvice.com/resources/how-patients-use-online-reviews/", "category": "marketing"},
        {"stat": "Dermatology is the most searched medical specialty online, with skin cancer screening searches increasing 45% year-over-year", "source": "Google Health Trends, 2024", "url": "https://trends.google.com/trends/", "category": "dermatology"},
        {"stat": "The average patient lifetime value for primary care is $2,000-$4,000 per year, while specialists range from $5,000-$10,000+", "source": "Medical Group Management Association, 2024", "url": "https://www.mgma.com/data", "category": "general"},
        {"stat": "Expanded access to primary care reduced patient-initiated emergency department visits for minor problems by about 26%", "source": "Dolton & Pathania, difference-in-differences analysis (peer-reviewed)", "url": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5012704/", "category": "preventive"},
    ],
    "ecommerce": [
        {"stat": "The global peptide therapeutics market is projected to reach $49.5B by 2027, growing at 9.7% CAGR", "source": "Grand View Research, Peptide Therapeutics Market Report, 2024", "url": "https://www.grandviewresearch.com/industry-analysis/peptide-therapeutics-market", "category": "market"},
        {"stat": "E-commerce accounts for over 20% of global retail sales as of 2024", "source": "Statista, Global E-Commerce Report, 2024", "url": "https://www.statista.com/topics/871/online-shopping/", "category": "market"},
        {"stat": "93% of online buyers say product reviews influence their purchasing decisions", "source": "Podium Consumer Survey, 2024", "url": "https://www.podium.com/resources/podium-state-of-reviews/", "category": "trust"},
        {"stat": "Third-party lab testing certificates increase customer trust by 71% for supplement and research chemical purchases", "source": "NSF International Consumer Trust Survey, 2024", "url": "https://www.nsf.org/consumer-resources", "category": "trust"},
        {"stat": "The global research chemicals market is expected to reach $65B by 2030", "source": "Allied Market Research, Research Chemicals Report, 2024", "url": "https://www.alliedmarketresearch.com/research-chemicals-market", "category": "market"},
        {"stat": "Free shipping is the top purchase driver for 73% of online shoppers", "source": "National Retail Federation Consumer Survey, 2024", "url": "https://nrf.com/research/consumer-research", "category": "conversion"},
    ],
}

# Backward compat alias
DENTAL_RESEARCH_STATS = RESEARCH_STATS["practice"]


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


SYSTEM_PROMPTS = {
    "practice": """\
You are an expert content strategist for dental practices, specializing in AI search optimization (GEO).
Your job is to generate specific, ready-to-use HTML content that will make dental practices
more visible in AI assistant responses (ChatGPT, Claude, Perplexity, Google AI Overviews).

Key GEO principles that MUST guide your output:
1. TLDR-first: Lead every section with a direct answer in the first 40-60 words
2. Statistics: ONLY use statistics from the "Available Research Statistics" list provided — do NOT invent numbers
3. Authoritative voice: Write in the practice's voice ("Our team...", "At [Practice Name]...") WITHOUT fabricating quotes
4. FAQ format: The most-cited content structure by AI systems
5. Content freshness: 50% of AI-cited content is <13 weeks old -- include current year references
6. Structured data: Schema-ready content with clear headings and semantic HTML

CRITICAL — NEVER FABRICATE:
- Do NOT generate fake quotes attributed to real people (providers, staff, anyone)
- Do NOT invent statistics, percentages, patient counts, success rates, or satisfaction scores
- Do NOT attribute statements to providers unless the exact quote is provided in "Verified Quotes" below
- ONLY use statistics from the provided research list with their exact citations
- If no verified quotes are provided, do NOT use <blockquote> with personal attribution at all
- You MAY write content in the practice's authoritative voice WITHOUT quoting specific individuals

Output rules:
- Generate REAL HTML (not markdown) -- ready to paste into a CMS
- Use semantic HTML: <article>, <section>, <h2>, <h3>, <p>, <blockquote>, <cite>, <ul>/<ol>
- Include schema-ready FAQ markup (<div itemscope itemtype="https://schema.org/FAQPage">)
- Every blog post must have at least 4 statistics from the provided research list
- Every FAQ must have a direct answer as the first sentence
- Always mention the practice name and city
- Use current year (2026) in references for freshness signals
- Include "Last updated: [current month year]" timestamps on all content

BLOG FORMATTING RULES (mandatory — blogs must NOT be walls of text):
- Use clear <h2> and <h3> subheadings every 2-3 paragraphs to break up content
- Keep paragraphs SHORT — 2-4 sentences max, never more than 5 lines
- Use <ul> or <ol> lists for any enumerable points (benefits, steps, tips)
- Include at least one FAQ section with 3-5 questions using <details>/<summary> accordion markup
- Add visual breaks: use <hr> between major sections
- Bold key phrases with <strong> for scannability
- Structure: intro paragraph → problem/context → solution with subheadings → FAQ → sources

BLOG UNIQUENESS RULES (mandatory — every blog must be unique to THIS practice):
- Blog topics MUST be directly tied to the specific services this practice offers (listed in Practice Info)
- NEVER write generic dental content that could apply to any practice — always reference specific services, providers, location, and differentiators
- Each blog must mention at least 2 specific services from this practice's offerings
- Reference the practice's city and surrounding areas for local relevance
- If the practice has unique differentiators (languages spoken, technology, specialties), weave them in
- Do NOT reuse or adapt blog topics from other practices — every topic must originate from THIS practice's service list and local market

CITATION RULES (mandatory):
- Every statistic MUST include a linked citation using the URL from the provided stats
- Format: <a href="URL" target="_blank" rel="noopener">Source Name</a>
- Example: According to the <a href="https://www.cdc.gov/oral-health/data-research/index.html" target="_blank" rel="noopener">CDC Oral Health Surveillance Report (2024)</a>, 26% of adults have untreated decay.
- Place citations inline near the statistic, not in a footnote
- If a stat has no URL, still include the source name in a <cite> tag
- Blog posts MUST have a "Sources" section at the bottom listing all referenced sources with links
""",
    "technology": """\
You are an expert B2B content strategist specializing in AI search optimization (GEO) for
technology companies. Your job is to generate specific, ready-to-use HTML content that
will make technology platforms more visible in AI assistant responses (ChatGPT, Claude,
Perplexity, Google AI Overviews).

This is B2B content targeting industry professionals, businesses, and enterprise clients -- NOT consumers.

Key GEO principles that MUST guide your output:
1. TLDR-first: Lead every section with a direct answer in the first 40-60 words
2. Statistics: ONLY use statistics from the "Available Industry Statistics" list provided — do NOT invent numbers
3. Thought leadership: Write in the company's authoritative voice WITHOUT fabricating quotes from individuals
4. FAQ format: The most-cited content structure by AI systems
5. Content freshness: 50% of AI-cited content is <13 weeks old -- include current year references
6. Industry authority: Position the company as an expert without revealing proprietary technology details

CRITICAL — NEVER FABRICATE:
- Do NOT generate fake quotes attributed to real people (CEO, CTO, any team member)
- Do NOT invent statistics, percentages, performance metrics, or satisfaction scores
- Do NOT attribute statements to leadership unless the exact quote is provided in "Verified Quotes" below
- ONLY use statistics from the provided industry statistics list with their exact citations
- If no verified quotes are provided, do NOT use <blockquote> with personal attribution at all
- You MAY write content in the company's authoritative voice WITHOUT quoting specific individuals

CRITICAL rules for tech companies:
- NEVER describe internal AI architecture, training data, model details, or pipeline specifics
- NEVER reveal pricing unless explicitly provided
- Focus on PROBLEMS the industry faces and the OUTCOMES the product delivers, not HOW it works internally
- Use industry pain points (bad scans, designer shortage, remake costs, incomplete prescriptions) as hooks
- Reference market growth and digital adoption trends

Output rules:
- Generate REAL HTML (not markdown) -- ready to paste into a CMS
- Use semantic HTML: <article>, <section>, <h2>, <h3>, <p>, <blockquote>, <cite>, <ul>/<ol>
- Include schema-ready FAQ markup (<div itemscope itemtype="https://schema.org/FAQPage">)
- Always mention the company name
- Use current year (2026) in references for freshness signals
- Include "Last updated: [current month year]" timestamps on all content

BLOG FORMATTING RULES (mandatory — blogs must NOT be walls of text):
- Use clear <h2> and <h3> subheadings every 2-3 paragraphs to break up content
- Keep paragraphs SHORT — 2-4 sentences max, never more than 5 lines
- Use <ul> or <ol> lists for any enumerable points (benefits, steps, tips)
- Include at least one FAQ section with 3-5 questions using <details>/<summary> accordion markup
- Add visual breaks: use <hr> between major sections
- Bold key phrases with <strong> for scannability
- Structure: intro paragraph → problem/context → solution with subheadings → FAQ → sources

BLOG UNIQUENESS RULES (mandatory — every blog must be unique to THIS company):
- Blog topics MUST be directly tied to the specific products/solutions this company offers (listed in Company Info)
- NEVER write generic industry content that could apply to any company — always reference specific products, team, and differentiators
- Each blog must mention at least 2 specific products/solutions from this company's offerings
- Do NOT reuse or adapt blog topics from other customers — every topic must originate from THIS company's product list and market position

CITATION RULES (mandatory):
- Every statistic MUST include a linked citation using the URL from the provided stats
- Format: <a href="URL" target="_blank" rel="noopener">Source Name</a>
- Place citations inline near the statistic, not in a footnote
- If a stat has no URL, still include the source name in a <cite> tag
- Blog posts MUST have a "Sources" section at the bottom listing all referenced sources with links
""",
    "ecommerce": """\
You are an expert e-commerce content strategist specializing in AI search optimization (GEO).
Your job is to generate specific, ready-to-use HTML content that will make online stores
more visible in AI assistant responses (ChatGPT, Claude, Perplexity, Google AI Overviews).

Key GEO principles that MUST guide your output:
1. TLDR-first: Lead every section with a direct answer in the first 40-60 words
2. Statistics: ONLY use statistics from the "Available Research Statistics" list provided — do NOT invent numbers
3. Authoritative voice: Write in the brand's voice WITHOUT fabricating quotes
4. FAQ format: The most-cited content structure by AI systems
5. Content freshness: 50% of AI-cited content is <13 weeks old -- include current year references
6. Product education: Help buyers understand products, use cases, and quality differentiators

CRITICAL — NEVER FABRICATE:
- Do NOT generate fake quotes attributed to real people
- Do NOT invent statistics, percentages, or satisfaction scores
- Do NOT make health claims or medical promises about products
- ONLY use statistics from the provided research list with their exact citations
- If no verified quotes are provided, do NOT use <blockquote> with personal attribution at all
- You MAY write content in the brand's authoritative voice WITHOUT quoting specific individuals

Output rules:
- Generate REAL HTML (not markdown) -- ready to paste into a CMS
- Use semantic HTML: <article>, <section>, <h2>, <h3>, <p>, <blockquote>, <cite>, <ul>/<ol>
- Include schema-ready FAQ markup (<div itemscope itemtype="https://schema.org/FAQPage">)
- Always mention the brand name
- Use current year (2026) in references for freshness signals
- Include "Last updated: [current month year]" timestamps on all content

BLOG FORMATTING RULES (mandatory — blogs must NOT be walls of text):
- Use clear <h2> and <h3> subheadings every 2-3 paragraphs to break up content
- Keep paragraphs SHORT — 2-4 sentences max, never more than 5 lines
- Use <ul> or <ol> lists for any enumerable points (benefits, steps, tips)
- Include at least one FAQ section with 3-5 questions using <details>/<summary> accordion markup
- Add visual breaks: use <hr> between major sections
- Bold key phrases with <strong> for scannability
- Structure: intro paragraph → problem/context → solution with subheadings → FAQ → sources

BLOG UNIQUENESS RULES (mandatory — every blog must be unique to THIS brand):
- Blog topics MUST be directly tied to the specific products this brand sells (listed in Brand Info)
- NEVER write generic e-commerce content that could apply to any store — always reference specific products, categories, and brand differentiators
- Each blog must mention at least 2 specific products/categories from this brand's offerings
- Do NOT reuse or adapt blog topics from other customers — every topic must originate from THIS brand's product catalog

CITATION RULES (mandatory):
- Every statistic MUST include a linked citation using the URL from the provided stats
- Format: <a href="URL" target="_blank" rel="noopener">Source Name</a>
- Place citations inline near the statistic, not in a footnote
- If a stat has no URL, still include the source name in a <cite> tag
- Blog posts MUST have a "Sources" section at the bottom listing all referenced sources with links
""",
    "legal": """\
You are an expert legal marketing content strategist specializing in AI search optimization (GEO)
for law firms. Your job is to generate specific, ready-to-use HTML content that will make
law firms more visible in AI assistant responses (ChatGPT, Claude, Perplexity, Google AI Overviews).

Key GEO principles that MUST guide your output:
1. TLDR-first: Lead every section with a direct answer in the first 40-60 words
2. Statistics: ONLY use statistics from the "Available Research Statistics" list provided — do NOT invent numbers
3. Authoritative voice: Write in the firm's voice ("Our attorneys...", "At [Firm Name]...") WITHOUT fabricating quotes
4. FAQ format: The most-cited content structure by AI systems
5. Content freshness: 50% of AI-cited content is <13 weeks old -- include current year references
6. E-E-A-T signals: Demonstrate attorney expertise, experience, authoritativeness, and trustworthiness

LEGAL-SPECIFIC RULES:
- Use "clients" NOT "patients" — this is a law firm, not a medical practice
- Reference practice areas, case types, and legal processes specific to THIS firm
- Include attorney credentials, bar admissions, and notable case experience where available
- Reference relevant legal directories (Avvo, Martindale-Hubbell, Super Lawyers, FindLaw)
- Mention consultation/intake process and what clients should expect
- DO NOT give specific legal advice — content should educate and build authority
- DO NOT promise specific case outcomes or settlement amounts
- Reference the firm's jurisdiction and courts they practice in

CRITICAL — NEVER FABRICATE:
- Do NOT generate fake quotes attributed to real attorneys or staff
- Do NOT invent statistics, case results, settlement amounts, or success rates
- Do NOT attribute statements to attorneys unless the exact quote is provided in "Verified Quotes" below
- ONLY use statistics from the provided research list with their exact citations
- If no verified quotes are provided, do NOT use <blockquote> with personal attribution at all
- You MAY write content in the firm's authoritative voice WITHOUT quoting specific individuals

Output rules:
- Generate REAL HTML (not markdown) -- ready to paste into a CMS
- Use semantic HTML: <article>, <section>, <h2>, <h3>, <p>, <blockquote>, <cite>, <ul>/<ol>
- Include schema-ready FAQ markup (<div itemscope itemtype="https://schema.org/FAQPage">)
- Every blog post must have at least 4 statistics from the provided research list
- Every FAQ must have a direct answer as the first sentence
- Always mention the firm name and location
- Use current year (2026) in references for freshness signals
- Include "Last updated: [current month year]" timestamps on all content

BLOG FORMATTING RULES (mandatory — blogs must NOT be walls of text):
- Use clear <h2> and <h3> subheadings every 2-3 paragraphs to break up content
- Keep paragraphs SHORT — 2-4 sentences max, never more than 5 lines
- Use <ul> or <ol> lists for any enumerable points (benefits, steps, tips)
- Include at least one FAQ section with 3-5 questions using <details>/<summary> accordion markup
- Add visual breaks: use <hr> between major sections
- Bold key phrases with <strong> for scannability
- Structure: intro paragraph → problem/context → solution with subheadings → FAQ → sources

BLOG UNIQUENESS RULES (mandatory — every blog must be unique to THIS firm):
- Blog topics MUST be directly tied to the specific practice areas this firm handles (listed in Firm Info)
- NEVER write generic legal content that could apply to any firm — always reference specific practice areas, attorneys, location, and differentiators
- Each blog must mention at least 2 specific practice areas from this firm's offerings
- Reference the firm's city, state, and surrounding areas for local relevance
- Do NOT reuse or adapt blog topics from other clients — every topic must originate from THIS firm's practice areas and local market

CITATION RULES (mandatory):
- Every statistic MUST include a linked citation using the URL from the provided stats
- Format: <a href="URL" target="_blank" rel="noopener">Source Name</a>
- Place citations inline near the statistic, not in a footnote
- If a stat has no URL, still include the source name in a <cite> tag
- Blog posts MUST have a "Sources" section at the bottom listing all referenced sources with links
""",
    "medical": """\
You are an expert medical practice content strategist specializing in AI search optimization (GEO)
for medical practices. Your job is to generate specific, ready-to-use HTML content that will make
medical practices more visible in AI assistant responses (ChatGPT, Claude, Perplexity, Google AI Overviews).

Key GEO principles that MUST guide your output:
1. TLDR-first: Lead every section with a direct answer in the first 40-60 words
2. Statistics: ONLY use statistics from the "Available Research Statistics" list provided — do NOT invent numbers
3. Authoritative voice: Write in the practice's voice ("Our providers...", "At [Practice Name]...") WITHOUT fabricating quotes
4. FAQ format: The most-cited content structure by AI systems
5. Content freshness: 50% of AI-cited content is <13 weeks old -- include current year references
6. E-E-A-T signals: Demonstrate provider expertise, credentials, and medical authority

MEDICAL-SPECIFIC RULES:
- Reference specialties, conditions treated, and procedures specific to THIS practice
- Include provider credentials (MD, DO, board certifications) where available
- Reference relevant medical directories (Healthgrades, Vitals, ZocDoc, WebMD, RateMDs)
- Mention insurance accepted, online scheduling, and telehealth availability
- Feature individual provider pages and specialty-specific condition pages
- DO NOT provide specific medical advice — content should educate and build authority
- DO NOT make treatment outcome guarantees or promise specific results
- Reference the practice's service area and hospital affiliations if available
- Address common patient concerns: wait times, appointment availability, new patient process

CRITICAL — NEVER FABRICATE:
- Do NOT generate fake quotes attributed to real providers or staff
- Do NOT invent statistics, success rates, patient counts, or satisfaction scores
- Do NOT attribute statements to providers unless the exact quote is provided in "Verified Quotes" below
- ONLY use statistics from the provided research list with their exact citations
- If no verified quotes are provided, do NOT use <blockquote> with personal attribution at all
- You MAY write content in the practice's authoritative voice WITHOUT quoting specific individuals

Output rules:
- Generate REAL HTML (not markdown) -- ready to paste into a CMS
- Use semantic HTML: <article>, <section>, <h2>, <h3>, <p>, <blockquote>, <cite>, <ul>/<ol>
- Include schema-ready FAQ markup (<div itemscope itemtype="https://schema.org/FAQPage">)
- Every blog post must have at least 4 statistics from the provided research list
- Every FAQ must have a direct answer as the first sentence
- Always mention the practice name and city
- Use current year (2026) in references for freshness signals
- Include "Last updated: [current month year]" timestamps on all content

BLOG FORMATTING RULES (mandatory — blogs must NOT be walls of text):
- Use clear <h2> and <h3> subheadings every 2-3 paragraphs to break up content
- Keep paragraphs SHORT — 2-4 sentences max, never more than 5 lines
- Use <ul> or <ol> lists for any enumerable points (benefits, steps, tips)
- Include at least one FAQ section with 3-5 questions using <details>/<summary> accordion markup
- Add visual breaks: use <hr> between major sections
- Bold key phrases with <strong> for scannability
- Structure: intro paragraph → problem/context → solution with subheadings → FAQ → sources

BLOG UNIQUENESS RULES (mandatory — every blog must be unique to THIS practice):
- Blog topics MUST be directly tied to the specific specialties and services this practice offers (listed in Practice Info)
- NEVER write generic medical content that could apply to any practice — always reference specific specialties, providers, location, and differentiators
- Each blog must mention at least 2 specific services/specialties from this practice's offerings
- Reference the practice's city and surrounding areas for local relevance
- If the practice has unique differentiators (languages, extended hours, technology), weave them in
- Do NOT reuse or adapt blog topics from other clients — every topic must originate from THIS practice's service list and local market

CITATION RULES (mandatory):
- Every statistic MUST include a linked citation using the URL from the provided stats
- Format: <a href="URL" target="_blank" rel="noopener">Source Name</a>
- Place citations inline near the statistic, not in a footnote
- If a stat has no URL, still include the source name in a <cite> tag
- Blog posts MUST have a "Sources" section at the bottom listing all referenced sources with links
""",
    "service": """\
You are an expert content strategist specializing in AI search optimization (GEO) for
service businesses. Your job is to generate specific, ready-to-use HTML content that will make
service companies more visible in AI assistant responses (ChatGPT, Claude, Perplexity, Google AI Overviews).

Key GEO principles that MUST guide your output:
1. TLDR-first: Lead every section with a direct answer in the first 40-60 words
2. Statistics: ONLY use statistics from the "Available Research Statistics" list provided — do NOT invent numbers
3. Authoritative voice: Write in the company's voice WITHOUT fabricating quotes
4. FAQ format: The most-cited content structure by AI systems
5. Content freshness: 50% of AI-cited content is <13 weeks old -- include current year references
6. Local authority: Establish the business as the go-to provider in their area

CRITICAL — NEVER FABRICATE:
- Do NOT generate fake quotes attributed to real people
- Do NOT invent statistics, percentages, or satisfaction scores
- ONLY use statistics from the provided research list with their exact citations
- If no verified quotes are provided, do NOT use <blockquote> with personal attribution at all

Output rules:
- Generate REAL HTML (not markdown) -- ready to paste into a CMS
- Use semantic HTML: <article>, <section>, <h2>, <h3>, <p>, <blockquote>, <cite>, <ul>/<ol>
- Include schema-ready FAQ markup (<div itemscope itemtype="https://schema.org/FAQPage">)
- Always mention the company name and location
- Use current year (2026) in references for freshness signals
- Include "Last updated: [current month year]" timestamps on all content

BLOG FORMATTING RULES (mandatory — blogs must NOT be walls of text):
- Use clear <h2> and <h3> subheadings every 2-3 paragraphs to break up content
- Keep paragraphs SHORT — 2-4 sentences max, never more than 5 lines
- Use <ul> or <ol> lists for any enumerable points (benefits, steps, tips)
- Include at least one FAQ section with 3-5 questions using <details>/<summary> accordion markup
- Add visual breaks: use <hr> between major sections
- Bold key phrases with <strong> for scannability
- Structure: intro paragraph → problem/context → solution with subheadings → FAQ → sources

BLOG UNIQUENESS RULES (mandatory — every blog must be unique to THIS business):
- Blog topics MUST be directly tied to the specific services/products this business offers (listed in Business Info)
- NEVER write generic content that could apply to any business — always reference specific services, location, and differentiators
- Each blog must mention at least 2 specific services from this business's offerings
- Reference the business's city and surrounding service area for local relevance
- Do NOT reuse or adapt blog topics from other customers — every topic must originate from THIS business's service list and local market

CITATION RULES (mandatory):
- Every statistic MUST include a linked citation using the URL from the provided stats
- Format: <a href="URL" target="_blank" rel="noopener">Source Name</a>
- Place citations inline near the statistic, not in a footnote
- If a stat has no URL, still include the source name in a <cite> tag
- Blog posts MUST have a "Sources" section at the bottom listing all referenced sources with links
""",
}

# Backward compat alias
CONTENT_SYSTEM_PROMPT = SYSTEM_PROMPTS["practice"]


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
    business_type = getattr(customer, "business_type", "practice")

    # Summarize existing pages
    page_summaries = []
    for p in pages:
        page_summaries.append(
            f"- {p.title} ({p.url}) [{p.category}]: {p.content[:300]}..."
        )

    # Pick relevant stats based on business type and specialties
    relevant_stats = _get_relevant_stats(customer.specialties, business_type)

    # Build existing recs summary to avoid duplicates
    existing_summary = ""
    if existing_recs:
        existing_titles = [r.get("title", "") for r in existing_recs if r.get("status") != "rejected"]
        if existing_titles:
            existing_summary = f"\n\nALREADY RECOMMENDED (do NOT duplicate):\n" + "\n".join(f"- {t}" for t in existing_titles)

    now = datetime.now(timezone.utc)
    current_month = now.strftime("%B %Y")

    user_prompt = _build_user_prompt(
        customer=customer,
        business_type=business_type,
        page_summaries=page_summaries,
        relevant_stats=relevant_stats,
        existing_summary=existing_summary,
        current_month=current_month,
    )

    system_prompt = SYSTEM_PROMPTS.get(business_type, SYSTEM_PROMPTS.get("service", SYSTEM_PROMPTS["practice"]))
    logger.info(f"Generating content recommendations for {customer.name} (type={business_type})")

    # Structured outputs: the schema is enforced server-side, so the response is
    # guaranteed-valid JSON (no fences, no repair). Streams with a generous cap and
    # FAILS LOUDLY on truncation — never silently returns [] and loses a month of content.
    response_text = complete(
        client,
        model=MODEL_CONTENT,
        system=system_prompt,
        user=user_prompt,
        max_tokens=64000,
        output_schema=CONTENT_OUTPUT_SCHEMA,
        label=f"content:{customer.name}",
    )
    try:
        data = json.loads(response_text)
    except json.JSONDecodeError as e:
        logger.error(
            f"Unparseable content JSON for {customer.name}: {e}; head={response_text[:200]}"
        )
        raise RuntimeError(
            f"Content generation returned unparseable JSON for {customer.name}"
        ) from e
    raw_recs = data.get("recommendations", []) if isinstance(data, dict) else data

    if not isinstance(raw_recs, list):
        logger.error("Content recommendations response is not a list")
        return []

    # Convert to ContentRecommendation objects
    recommendations = []
    for i, rec in enumerate(raw_recs):
        try:
            rec_id = f"{customer.id}-{now.strftime('%Y%m%d')}-{i:02d}"
            html = _fix_link_spacing(rec.get("html_snippet", ""))
            cr = ContentRecommendation(
                id=rec_id,
                customer_id=customer.id,
                rec_type=rec.get("rec_type", "unknown"),
                target_page=rec.get("target_page", ""),
                title=rec.get("title", "Untitled"),
                description=rec.get("description", ""),
                html_snippet=html,
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


def _fix_link_spacing(html: str) -> str:
    """Ensure proper whitespace around <a> tags in generated HTML.

    LLMs sometimes generate 'The<a href=...' or '</a>notes' without spaces.
    """
    # Add space before <a if preceded by a word character
    html = re.sub(r'(\w)(<a\s)', r'\1 \2', html)
    # Add space after </a> if followed by a word character
    html = re.sub(r'(</a>)(\w)', r'\1 \2', html)
    return html


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


def _build_user_prompt(
    customer: Customer,
    business_type: str,
    page_summaries: list[str],
    relevant_stats: list[dict],
    existing_summary: str,
    current_month: str,
) -> str:
    """Build the user prompt based on business type."""
    providers_str = ', '.join(f'{p.name} ({p.credentials})' for p in customer.providers) if customer.providers else "N/A"
    specialties_str = ', '.join(customer.specialties) if customer.specialties else "N/A"

    # Get verified quotes if available
    verified_quotes = getattr(customer, "verified_quotes", None) or []
    verified_quotes_str = ""
    if verified_quotes:
        verified_quotes_str = "\n## Verified Quotes (ONLY use these exact quotes — do NOT invent others)\n"
        for q in verified_quotes:
            verified_quotes_str += f'- "{q["quote"]}" — {q["attribution"]}\n'
    else:
        verified_quotes_str = "\n## Verified Quotes\nNONE PROVIDED. Do NOT generate any quotes attributed to specific people.\n"

    if business_type == "technology":
        return f"""\
Analyze this technology company's website and generate specific content recommendations
that will boost their visibility in AI search results. This is a B2B company — content targets
industry professionals and enterprise clients, NOT consumers.

## Company Info
- Name: {customer.name}
- Location: {customer.city}, {customer.state}
- Team/Leadership: {providers_str}
- Products/Solutions: {specialties_str}
- Brand Voice: {customer.brand_voice}

## Current Pages ({len(page_summaries)} total)
{chr(10).join(page_summaries[:20])}

## Available Industry Statistics (ONLY use these — do NOT fabricate any numbers or metrics)
{json.dumps(relevant_stats, indent=2)}
{verified_quotes_str}
{existing_summary}

## What I Need

Each recommendation object must have these fields:

1. **rec_type**: One of: "blog_post", "faq_update", "stat_injection", "freshness_update", "new_page"
2. **target_page**: The URL of the page to update, or "new" for new pages
3. **title**: Human-readable title
4. **description**: What to change and why (1-2 sentences)
5. **html_snippet**: Complete, ready-to-use HTML content (NOT markdown)
6. **priority**: 1-5 (1 = highest impact)
7. **category**: Topic area (e.g., "scan-quality", "cad-design", "workflow", "digital-dentistry", "lab-efficiency")
8. **ai_impact_reason**: Why this specific change will improve AI search visibility

CRITICAL: Do NOT reveal proprietary technology details, AI model architecture, training data, \
or internal system design. Focus on industry problems and product outcomes.

CRITICAL: Do NOT fabricate quotes, statistics, performance metrics, or satisfaction rates. \
Only use statistics from the "Available Industry Statistics" section above. \
Only use quotes from the "Verified Quotes" section above. If none are provided, do NOT quote anyone.

Generate exactly 8-10 recommendations covering:
- 2-3 blog posts (full HTML articles, 800-1200 words each, thought leadership with industry stats)
- 2-3 FAQ updates (product/company FAQs targeting what labs and clinics ask)
- 2-3 statistic injections (data-backed market/industry claims using ONLY the provided statistics)
- 1-2 freshness updates (update existing content with current year references)

For blog posts, generate the COMPLETE article HTML, not just an outline. Include inline linked citations for every stat and a "Sources" section at the bottom with linked references.
For FAQ updates, generate complete FAQ HTML with schema.org markup.
For stat injections, generate a <p> or <div> with the statistic and a linked citation (<a href="url">Source Name</a>).
For freshness updates, generate the updated paragraph/section with current date.

Current date: {current_month}

Return a JSON object of the form {{"recommendations": [ ...one object per recommendation... ]}}.
"""
    elif business_type == "ecommerce":
        services_str = ', '.join(customer.services[:20]) if customer.services else specialties_str
        return f"""\
Analyze this e-commerce brand's website and generate specific content recommendations
that will boost their visibility in AI search results. This brand sells products online —
content should help buyers find, trust, and choose this brand.

## Brand Info
- Name: {customer.name}
- Location: {customer.city}, {customer.state} (if applicable)
- Products/Services: {services_str}
- Specialties: {specialties_str}
- Brand Voice: {customer.brand_voice}

## Current Pages ({len(page_summaries)} total)
{chr(10).join(page_summaries[:20])}

## Available Research Statistics (ONLY use these — do NOT fabricate any numbers or metrics)
{json.dumps(relevant_stats, indent=2)}
{verified_quotes_str}
{existing_summary}

## What I Need

Each recommendation object must have these fields:

1. **rec_type**: One of: "blog_post", "faq_update", "stat_injection", "freshness_update", "new_page"
2. **target_page**: The URL of the page to update, or "new" for new pages
3. **title**: Human-readable title
4. **description**: What to change and why (1-2 sentences)
5. **html_snippet**: Complete, ready-to-use HTML content (NOT markdown)
6. **priority**: 1-5 (1 = highest impact)
7. **category**: Topic area relevant to the brand's products (e.g., product names, use cases, buying guides)
8. **ai_impact_reason**: Why this specific change will improve AI search visibility

CRITICAL: Do NOT fabricate quotes, statistics, or satisfaction scores. \
Only use statistics from the "Available Research Statistics" section above. \
Only use quotes from the "Verified Quotes" section above. If none are provided, do NOT quote anyone. \
Do NOT make health claims or medical promises about products.

Generate exactly 8-10 recommendations covering:
- 2-3 blog posts (full HTML articles, 800-1200 words each — buyer's guides, product comparisons, educational content about the products)
- 2-3 FAQ updates (product FAQs targeting what buyers commonly ask — shipping, quality, usage, comparisons)
- 2-3 statistic injections (data-backed industry/market claims using ONLY the provided statistics)
- 1-2 freshness updates (update existing content with current year references)

For blog posts, generate the COMPLETE article HTML, not just an outline. Include inline linked citations for every stat and a "Sources" section at the bottom with linked references.
For FAQ updates, generate complete FAQ HTML with schema.org markup.
For stat injections, generate a <p> or <div> with the statistic and a linked citation (<a href="url">Source Name</a>).
For freshness updates, generate the updated paragraph/section with current date.

Current date: {current_month}

Return a JSON object of the form {{"recommendations": [ ...one object per recommendation... ]}}.
"""
    elif business_type == "practice":
        return f"""\
Analyze this dental practice's website and generate specific content recommendations
that will boost their visibility in AI search results.

## Practice Info
- Name: {customer.name}
- Location: {customer.city}, {customer.state}
- Providers: {providers_str}
- Specialties: {specialties_str}
- Services: {', '.join(customer.services[:15]) if customer.services else 'N/A'}
- Brand Voice: {customer.brand_voice}

## Current Pages ({len(page_summaries)} total)
{chr(10).join(page_summaries[:20])}

## Available Research Statistics (ONLY use these — do NOT fabricate any numbers or metrics)
{json.dumps(relevant_stats, indent=2)}
{verified_quotes_str}
{existing_summary}

## What I Need

Each recommendation object must have these fields:

1. **rec_type**: One of: "blog_post", "faq_update", "stat_injection", "freshness_update", "new_page"
2. **target_page**: The URL of the page to update, or "new" for new pages
3. **title**: Human-readable title
4. **description**: What to change and why (1-2 sentences)
5. **html_snippet**: Complete, ready-to-use HTML content (NOT markdown)
6. **priority**: 1-5 (1 = highest impact)
7. **category**: Topic area (e.g., "implants", "cosmetic", "general", "emergency")
8. **ai_impact_reason**: Why this specific change will improve AI search visibility

CRITICAL: Do NOT fabricate quotes, statistics, patient counts, success rates, or satisfaction scores. \
Only use statistics from the "Available Research Statistics" section above. \
Only use quotes from the "Verified Quotes" section above. If none are provided, do NOT quote anyone. \
Write in the practice's authoritative voice instead.

Generate exactly 8-10 recommendations covering:
- 2-3 blog posts (full HTML articles, 800-1200 words each, using provided stats)
- 2-3 FAQ updates for existing service pages (new Q&A pairs with schema markup)
- 2-3 statistic injections (data-backed claims using ONLY the provided statistics with their citations)
- 1-2 freshness updates (update existing content with current year references)

CONTENT ACCURACY — CRITICAL (violations will mislead patients and damage trust):
- ONLY reference services that appear in the "Services" and "Specialties" lists above — do NOT invent or assume services the practice offers
- ONLY use provider credentials EXACTLY as stated in "Providers" above — do NOT embellish titles, add fellowships, or assume board certifications that aren't listed
- NEVER claim any dental treatment "lasts a lifetime" — use evidence-based language like "decades of reliable function with proper maintenance" or cite specific survival rate statistics
- The "Brand Voice" field may contain CONTENT RULES (e.g., "do NOT create root canal content"). These are direct instructions from the practice owner — follow them exactly.
- target_page must be a real URL from the "Current Pages" list above or "/blog/" for new posts — do NOT target pages that don't exist on the site

BLOG TOPIC SELECTION — CRITICAL:
- Each blog MUST focus on 1-2 specific services from this practice's "Services" and "Specialties" lists above
- Do NOT write generic dental topics like "importance of oral health" — tie every blog to a specific service this practice offers
- Example: if the practice offers "IV Sedation" and "Dental Implants", write "How IV Sedation Makes Dental Implant Surgery Comfortable in [City]" — NOT "Why You Should Visit the Dentist"
- Blog titles must include the practice's city or region for local SEO
- Do NOT write content about services the practice refers out or doesn't offer — check the Brand Voice field for restrictions

BLOG FORMATTING — CRITICAL (blogs must NOT be walls of text):
- Use <h2> and <h3> subheadings every 2-3 paragraphs
- Keep paragraphs to 2-4 sentences max
- Use <ul>/<ol> lists for enumerable points
- Include a FAQ section with 3-5 <details>/<summary> accordion items
- Bold key phrases with <strong>
- Add a "Sources" section at the bottom with linked references

For blog posts, generate the COMPLETE article HTML, not just an outline. Include inline linked citations for every stat and a "Sources" section at the bottom with linked references.
For FAQ updates, generate complete FAQ HTML with schema.org markup.
For stat injections, generate a <p> or <div> with the statistic and a linked citation (<a href="url">Source Name</a>).
For freshness updates, generate the updated paragraph/section with current date.

Current date: {current_month}

Return a JSON object of the form {{"recommendations": [ ...one object per recommendation... ]}}.
"""
    else:
        # Generic fallback — adapts to any business type using services
        services_str = ', '.join(customer.services[:20]) if customer.services else specialties_str
        biz_label = business_type.replace("_", " ").title() if business_type else "Business"
        return f"""\
Analyze this {biz_label.lower()}'s website and generate specific content recommendations
that will boost their visibility in AI search results. Tailor all content to THIS specific
business and its actual offerings — do NOT use generic or dental-focused content.

## Business Info
- Name: {customer.name}
- Type: {biz_label}
- Location: {customer.city}, {customer.state}
- Team: {providers_str}
- Services/Products: {services_str}
- Brand Voice: {customer.brand_voice}

## Current Pages ({len(page_summaries)} total)
{chr(10).join(page_summaries[:20])}

## Available Research Statistics (ONLY use these — do NOT fabricate any numbers or metrics)
{json.dumps(relevant_stats, indent=2)}
{verified_quotes_str}
{existing_summary}

## What I Need

Each recommendation object must have these fields:

1. **rec_type**: One of: "blog_post", "faq_update", "stat_injection", "freshness_update", "new_page"
2. **target_page**: The URL of the page to update, or "new" for new pages
3. **title**: Human-readable title
4. **description**: What to change and why (1-2 sentences)
5. **html_snippet**: Complete, ready-to-use HTML content (NOT markdown)
6. **priority**: 1-5 (1 = highest impact)
7. **category**: Topic area relevant to this business's services/products
8. **ai_impact_reason**: Why this specific change will improve AI search visibility

CRITICAL: Do NOT fabricate quotes, statistics, or satisfaction scores. \
Only use statistics from the "Available Research Statistics" section above. \
Only use quotes from the "Verified Quotes" section above. If none are provided, do NOT quote anyone.

Generate exactly 8-10 recommendations covering:
- 2-3 blog posts (full HTML articles, 800-1200 words each, relevant to this business's industry)
- 2-3 FAQ updates (targeting what customers commonly ask about these services/products)
- 2-3 statistic injections (data-backed claims using ONLY the provided statistics)
- 1-2 freshness updates (update existing content with current year references)

For blog posts, generate the COMPLETE article HTML, not just an outline. Include inline linked citations for every stat and a "Sources" section at the bottom with linked references.
For FAQ updates, generate complete FAQ HTML with schema.org markup.
For stat injections, generate a <p> or <div> with the statistic and a linked citation (<a href="url">Source Name</a>).
For freshness updates, generate the updated paragraph/section with current date.

Current date: {current_month}

Return a JSON object of the form {{"recommendations": [ ...one object per recommendation... ]}}.
"""


def _get_relevant_stats(specialties: list[str], business_type: str = "practice") -> list[dict]:
    """Filter research statistics relevant to the customer's business type and specialties."""
    stats_pool = RESEARCH_STATS.get(business_type, [])

    # For non-practice types with their own curated pool, return all
    if business_type in ("technology", "ecommerce") and stats_pool:
        return stats_pool

    # If no stats pool for this business type, return empty (Claude will work without stats)
    if not stats_pool:
        return []

    relevant = []
    specialty_lower = [s.lower() for s in specialties]

    # Always include general stats
    for stat in stats_pool:
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
        relevant = stats_pool[:10]

    return relevant


def _grade_recommendations(
    recs: list[ContentRecommendation],
    customer: Customer,
) -> list[ContentRecommendation]:
    """Grade and filter recommendations for quality.

    Checks for:
    - Competitor names in content (remove them)
    - Fabricated quotes (blockquotes attributing to people without verified quotes)
    - HTML validity (has actual tags)
    - Minimum content length for blog posts
    """
    import re

    competitor_names = {c.lower() for c in customer.competitors}
    verified_quotes = getattr(customer, "verified_quotes", None) or []
    verified_texts = {q["quote"].lower().strip()[:50] for q in verified_quotes}
    graded = []

    for rec in recs:
        html = rec.html_snippet.lower()

        # Check for competitor mentions. Replace with a NEUTRAL term — never the
        # client's own name (that turns a competitor claim into a false claim about
        # the client on the client's own site).
        for comp in competitor_names:
            if comp in html:
                rec.html_snippet = re.sub(
                    re.escape(comp), "another local practice", rec.html_snippet,
                    flags=re.IGNORECASE,
                )
                logger.warning(
                    f"Neutralized competitor mention '{comp}' in rec '{rec.title}'"
                )

        # Strip fabricated quotes if no verified quotes are provided
        if not verified_quotes and "<blockquote" in html:
            # Remove blockquotes that attribute to specific people
            rec.html_snippet = re.sub(
                r'<blockquote[^>]*>.*?</blockquote>',
                '',
                rec.html_snippet,
                flags=re.IGNORECASE | re.DOTALL,
            )
            logger.warning(f"Stripped unverified blockquotes from rec '{rec.title}'")

        # Skip expert_quote rec type entirely if no verified quotes
        if rec.rec_type == "expert_quote" and not verified_quotes:
            logger.warning(f"Skipping expert_quote rec '{rec.title}' — no verified quotes available")
            continue

        # Flag misleading longevity claims — "last a lifetime" / "lifetime of function"
        lifetime_patterns = [
            r'last\s+a\s+lifetime', r'lifetime\s+of\s+function',
            r'lasts?\s+forever', r'permanent\s+solution\s+for\s+life',
        ]
        for pat in lifetime_patterns:
            if re.search(pat, html):
                rec.html_snippet = re.sub(
                    pat,
                    'decades of reliable function with proper maintenance',
                    rec.html_snippet,
                    flags=re.IGNORECASE,
                )
                logger.warning(f"Replaced lifetime claim in rec '{rec.title}'")

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
