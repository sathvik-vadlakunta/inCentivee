"""Pre-publish fact-check: ground generated content against verified business data.

A cheap Haiku pass that compares HTML about to be published to a client's live
site against the verified business profile (services, providers + credentials,
address, reviews) and returns claims that aren't supported — invented services,
fabricated credentials/stats, fake reviews/testimonials, definitive YMYL claims.
Publish is blocked on any finding. This is the backstop for medical/legal content.

Fails OPEN on infrastructure errors (logs a warning, returns no findings) so a
transient API hiccup can't block all publishing — content has already passed the
human approval gate before this runs.
"""

from __future__ import annotations

import json
import logging
import os

import anthropic

from geo_agent.config import Customer
from geo_agent.llm import MODEL_FACTCHECK, complete

logger = logging.getLogger(__name__)

FACTCHECK_SYSTEM = """You are a strict fact-checker for content about to be published to a business's live website. You receive (1) a VERIFIED PROFILE of the business and (2) an HTML snippet. Identify ONLY claims in the HTML that are NOT supported by the verified profile and that a reader would take as a specific factual assertion about THIS business. Flag:
- Services, procedures, or specialties claimed that are not in the profile's services/specialties.
- Provider names, credentials (DDS, MD, JD, "board-certified"), or years of experience not in the profile.
- Specific statistics presented as fact without a cited source (percentages, "X% of patients...", counts).
- Star ratings, review counts, or testimonials/quotes attributed to people, unless they match the profile's verified data.
- Definitive medical or legal outcome claims ("cures", "guaranteed", "pain-free", "you will win your case").
Do NOT flag generic educational content, clearly industry-wide statements, or marketing tone. Only flag specific factual assertions about this business or uncited statistics.
Return ONLY a JSON array: [{"claim": "<exact text>", "reason": "<why unsupported>"}]. Return [] if everything checks out."""


def build_profile(customer: Customer) -> str:
    """Render the verified business profile the fact-checker grounds against."""
    lines = [
        f"Business: {customer.name}",
        f"Type: {customer.business_type}",
        f"Location: {customer.city}, {customer.state}",
    ]
    if customer.address:
        lines.append(f"Address: {customer.address}")
    if customer.phone:
        lines.append(f"Phone: {customer.phone}")
    if customer.services:
        lines.append("Services offered: " + ", ".join(customer.services))
    if customer.specialties:
        lines.append("Specialties: " + ", ".join(customer.specialties))
    if customer.providers:
        provs = "; ".join(
            f"{p.name} ({p.credentials})"
            + (f", {p.years_experience} yrs" if p.years_experience else "")
            for p in customer.providers
        )
        lines.append("Providers (only these names/credentials may appear): " + provs)
    if customer.insurance_accepted:
        lines.append("Insurance accepted: " + ", ".join(customer.insurance_accepted))
    if customer.verified_quotes:
        qs = "; ".join(q.get("quote", "")[:140] for q in customer.verified_quotes)
        lines.append("Verified quotes (ONLY these may be attributed to a person): " + qs)
    else:
        lines.append(
            "Verified quotes: NONE — no testimonials or quotes may be attributed to any person."
        )
    return "\n".join(lines)


def fact_check_html(
    customer: Customer,
    html: str,
    client: anthropic.Anthropic | None = None,
) -> list[dict]:
    """Return unsupported claims found in `html`. Empty list = clean (publishable)."""
    if not html or "<" not in html:
        return []
    if client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            logger.warning("fact_check: ANTHROPIC_API_KEY unset; skipping (allowing publish)")
            return []
        client = anthropic.Anthropic(api_key=api_key)

    user = f"VERIFIED PROFILE:\n{build_profile(customer)}\n\nHTML TO CHECK:\n{html}"
    try:
        text = complete(
            client,
            model=MODEL_FACTCHECK,
            system=FACTCHECK_SYSTEM,
            user=user,
            max_tokens=2000,
            label="factcheck",
        )
    except Exception as e:  # fail open — human approval already happened
        logger.warning(f"fact_check call failed (allowing publish): {e}")
        return []

    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    try:
        findings = json.loads(text)
    except json.JSONDecodeError:
        logger.warning(f"fact_check: unparseable output (allowing publish): {text[:120]}")
        return []
    return findings if isinstance(findings, list) else []
