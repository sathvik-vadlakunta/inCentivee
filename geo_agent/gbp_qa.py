"""Monthly, keyword-driven Google Business Profile Q&A generation.

GBP "Questions & answers" is a strong local + AI-citation surface, but Google has no
reliable Q&A API — the owner seeds questions and answers them from the managing account.
So this engine *generates* a fresh set of 10–15 Q&A pairs each month, targeted at the
keywords the business actually wants to rank for, and files them as ONE `gbp_qa` content
recommendation that flows into the normal approval queue. Dan approves, then copy-pastes
the pairs into the GBP listing (asking + answering as the owner).

Targeting comes from real signals — tracked keywords + question/striking-distance GSC
queries — so the Q&A drifts with demand month to month. Answers are grounded in the
business's real services/city; the prompt forbids invented stats, prices, or claims
(same anti-fabrication stance as the rest of the content pipeline).

See specs/active/local-seo-and-gbp-qa.md.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone

from geo_agent import keyword_intent
from geo_agent.business_profiles import get_profile
from geo_agent.directory_profiles import default_service_terms
from geo_agent.keyword_content import _classify
from geo_agent.llm import MODEL_CONTENT, complete

logger = logging.getLogger(__name__)

_QA_SCHEMA = {
    "type": "object",
    "properties": {
        "qa": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "A natural question a real customer would type/ask, targeting one of the keywords."},
                    "answer": {"type": "string", "description": "Owner-voice answer, 2–4 sentences, grounded only in the business's real services/location. No invented stats, prices, or guarantees."},
                },
                "required": ["question", "answer"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["qa"],
    "additionalProperties": False,
}


def _target_keywords(db, customer_id: str, limit: int = 30) -> list[str]:
    """Tracked keywords + question/striking-distance GSC queries, de-duped."""
    out: list[str] = []
    seen: set[str] = set()

    def _add(kw: str):
        k = (kw or "").strip()
        # Guard against corrupted CSV-imported keywords (embedded commas/numbers).
        if not k or "," in k or len(k) > 80:
            return
        low = k.lower()
        if low not in seen:
            seen.add(low)
            out.append(k)

    for k in db.get_tracked_keywords(customer_id):
        _add(k.get("keyword", ""))

    try:
        end = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        start = (datetime.now(timezone.utc) - timedelta(days=28)).strftime("%Y-%m-%d")
        for q in db.get_query_aggregates(customer_id, start, end, min_impressions=10, limit=200):
            if _classify(q) in ("question", "striking_distance"):
                _add(q.get("query", ""))
    except Exception as exc:  # noqa: BLE001
        logger.info("gbp_qa: query aggregates unavailable for %s: %s", customer_id, exc)

    return out[:limit]


def _relevant_enrichment(keywords: list[str], relevance_terms: list[str], limit: int = 6) -> list[str]:
    """Keep only keywords that mention a CORE service term — so a skewed tracked-keyword
    table (e.g. lots of 'antique tea set') can't pull the Q&A off the main business — then
    rank what's left by PURCHASE INTENT so action searches ('where to sell gold near me')
    are chosen over research ('are tea sets valuable'). Capped so enrichment never dominates."""
    terms = [t.lower() for t in relevance_terms if t]
    relevant = [k for k in keywords if any(t in k.lower() for t in terms)]
    relevant.sort(key=keyword_intent.target_priority, reverse=True)
    return relevant[:limit]


def _render_html(qa: list[dict]) -> str:
    """Copy-paste-friendly block: each Q as a heading, A below — what Dan posts to GBP."""
    parts = ['<div class="gbp-qa">']
    for i, pair in enumerate(qa, 1):
        q = (pair.get("question") or "").strip()
        a = (pair.get("answer") or "").strip()
        if not q or not a:
            continue
        parts.append(f"<h3>Q{i}. {q}</h3>\n<p>{a}</p>")
    parts.append("</div>")
    return "\n".join(parts)


def generate_gbp_qa(db, customer_id: str, *, max_questions: int = 12,
                    today: str | None = None) -> dict | None:
    """Generate one month's GBP Q&A rec for a customer (idempotent per month).

    Returns the created rec dict, or None if one already exists this month or there's
    nothing to target / no API key.
    """
    customer = db.get_customer(customer_id)
    if not customer:
        raise ValueError(f"Unknown customer: {customer_id}")

    month = (today or datetime.now(timezone.utc).strftime("%Y-%m-%d"))[:7]
    rec_id = f"gbpqa_{customer_id}_{month}"

    # Idempotent: one gbp_qa rec per month, regardless of status.
    for r in db.get_content_recommendations(customer_id, limit=200):
        if r.get("id") == rec_id or (
            r.get("rec_type") == "gbp_qa" and (r.get("created_at") or "")[:7] == month
        ):
            logger.info("gbp_qa: already have a rec for %s %s", customer_id, month)
            return None

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    name = customer.get("name", "the business")
    btype_raw = customer.get("business_type") or "local_business"
    btype = btype_raw.replace("_", " ")
    city = customer.get("city", "")
    areas = customer.get("service_areas") or []
    area_block = ", ".join(areas[:12]) if isinstance(areas, list) else ""

    # ----- Anchor on the business's CORE FOCUS, not noisy tracked keywords -----
    # Primary: the customer's own services; fallback to the vertical's canonical core
    # services. The business profile supplies the seller-process FAQs + relevance terms.
    services = customer.get("services") or []
    if isinstance(services, str):
        try:
            services = json.loads(services)
        except Exception:
            services = []
    core_services = services[:12] if services else default_service_terms(btype_raw)
    profile = get_profile(btype_raw)
    seller_faqs = list(getattr(profile, "faq_seeds", []) or [])
    relevance_terms = list(getattr(profile, "service_keywords", []) or []) + [
        s.lower() for s in core_services
    ]
    industry = getattr(profile, "industry_label", btype)

    # Keywords are SECONDARY: relevance-filtered to the core focus + capped so a skewed
    # keyword table can't take over the Q&A set.
    enrich = _relevant_enrichment(_target_keywords(db, customer_id), relevance_terms, limit=6)

    core_block = ", ".join(core_services)
    faq_block = "\n".join(f"- {q}" for q in seller_faqs) if seller_faqs else "- How does the process work?\n- How do you determine value?"
    enrich_block = ("\n".join(f"- {k}" for k in enrich)
                    if enrich else "(none relevant — rely on the core services above)")

    import anthropic

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    user = (
        f"Write {max_questions} Google Business Profile Q&A pairs for '{name}', a {industry} "
        f"in {city}.\n\n"
        f"THE BUSINESS'S CORE FOCUS (anchor every Q&A here): {name} primarily helps people with "
        f"these services: {core_block}.\n"
        f"Service areas: {area_block or city}.\n\n"
        f"COVERAGE RULE (most important): distribute the questions ACROSS the core services above — "
        f"include at least one question for each major category (e.g. for a precious-metals buyer: "
        f"selling gold, selling silver, selling coins, selling gold/silver jewelry, selling diamonds). "
        f"Do NOT cluster many questions on one narrow niche. Write the questions a real SELLER/CUSTOMER "
        f"would ask with INTENT: 'how much can I get for…', 'where can I sell… near me / in {city}', "
        f"'do you buy… (broken, scrap, estate, inherited)', plus the process questions below.\n\n"
        f"ALSO INCLUDE these process/trust questions (reword naturally):\n{faq_block}\n\n"
        f"Supplemental keywords — use ONLY if they fit the core focus, and never let them dominate; "
        f"ignore anything off-topic:\n{enrich_block}\n\n"
        f"RULES:\n"
        f"- Every Q&A must be about the CORE business above. If a keyword is off-focus (not about the "
        f"core services), ignore it.\n"
        f"- NO near-duplicate questions — each must cover a distinct category or intent. Do not ask the "
        f"same thing reworded.\n"
        f"- Each QUESTION is phrased the way a real customer would ask it (natural, specific).\n"
        f"- Each ANSWER is 2–4 sentences in the owner's voice, specific to {name}; mention the city/area "
        f"and the relevant service where natural.\n"
        f"- Do NOT invent statistics, prices, dollar amounts, or guarantees. Speak generally (e.g. 'free "
        f"evaluation') without fabricated numbers. No superlatives like 'best' or 'guaranteed'."
    )
    out = complete(client, model=MODEL_CONTENT, user=user, max_tokens=4000,
                   output_schema=_QA_SCHEMA, label="gbp-qa")
    qa = [p for p in json.loads(out).get("qa", []) if p.get("question") and p.get("answer")]
    if not qa:
        logger.info("gbp_qa: model returned no usable pairs for %s", customer_id)
        return None

    rec = {
        "id": rec_id,
        "customer_id": customer_id,
        "rec_type": "gbp_qa",
        "target_page": "Google Business Profile — Q&A",
        "title": f"GBP Q&A — {datetime.strptime(month, '%Y-%m').strftime('%B %Y')} ({len(qa)} questions)",
        "description": ("Post these Q&A pairs on the Google Business Profile listing — ask each "
                        "question and answer it from the practice's managing Google account so it's "
                        "marked as Owner-verified. Refreshed monthly against current keyword demand."),
        "html_snippet": _render_html(qa),
        "priority": 2,
        "category": "local_seo",
        "status": "pending",
        "ai_impact_reason": ("GBP Q&A is a high-visibility local surface that AI assistants and the "
                             "local pack draw from; keyword-targeted, owner-answered Q&A captures "
                             "long-tail 'near me' intent."),
    }
    db.add_content_recommendation(rec)
    logger.info("gbp_qa: created %d-question rec for %s (%s)", len(qa), customer_id, month)
    return rec
