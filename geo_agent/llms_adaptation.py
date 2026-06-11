"""Adapt llms.txt / content over time using the product's own citation data.

Closes the measurement -> action loop: the AI-mention checks tell us exactly which
real queries the practice is NOT cited on, which engines cite competitors instead,
and which source domains AI pulls from. This turns that data into a concrete plan —
the queries to answer (as new FAQ entries), the engines to strengthen for, and the
citation gaps to chase — which then feeds llms.txt + content regeneration.

Read-only and defensive; every signal is optional.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# Query phrasings -> a natural FAQ question. Best-effort; the content generator
# writes the actual answer from verified facts.
_LEADERS = ("what", "who", "where", "when", "why", "how", "is", "are", "do", "does", "can", "should")


def prompt_to_question(prompt: str, practice_name: str = "") -> str:
    """Turn a benchmark query into an FAQ question the practice should answer."""
    q = prompt.strip().rstrip("?").strip()
    if practice_name:
        q = re.sub(re.escape(practice_name), "we", q, flags=re.IGNORECASE)
    if not q.lower().startswith(_LEADERS):
        q = f"What should patients know about {q}"
    return q[0].upper() + q[1:] + "?"


def build_adaptation_plan(db, customer_id: str, limit: int = 10) -> dict:
    """Assemble the 'how we adjust over time' plan from citation data."""
    customer = db.get_customer(customer_id) or {}
    name = customer.get("name", "")
    plan: dict = {"customer_id": customer_id, "customer_name": name}

    # 1. Queries we're not cited on -> candidate FAQ additions (highest leverage)
    try:
        uncited = db.get_uncited_prompts(customer_id)[:limit]
    except Exception as e:
        logger.warning(f"adaptation: uncited failed: {e}")
        uncited = []
    plan["uncited_queries"] = uncited
    plan["suggested_faqs"] = [
        {
            "question": prompt_to_question(u["prompt"], name),
            "source_query": u["prompt"],
            "category": u.get("category", "general"),
            "reason": f"AI engines answered this {u['checks']}x without citing the practice.",
        }
        for u in uncited
    ]

    # 2. Where competitors win the share of voice
    try:
        sov = db.get_share_of_voice(customer_id, last_n_runs=4)
        comps = (sov.get("competitors") or [])[:5]
        plan["competitors_ahead"] = [
            c for c in comps
            if (c.get("mentions") or c.get("share") or 0) > (sov.get("customer_mentions") or 0)
        ]
        plan["customer_share"] = round((sov.get("customer_share", 0) or 0) * 100, 1)
    except Exception as e:
        logger.warning(f"adaptation: sov failed: {e}")

    # 3. Domains AI cites (NAP-alignment / off-site targets)
    try:
        plan["cited_domains"] = db.get_citation_domains(customer_id, last_n_runs=4)[:10]
    except Exception as e:
        logger.warning(f"adaptation: citations failed: {e}")
        plan["cited_domains"] = []

    # 4. The headline action summary
    plan["actions"] = []
    if plan["suggested_faqs"]:
        plan["actions"].append(
            f"Add {len(plan['suggested_faqs'])} FAQ answer(s) (with FAQPage schema) for the "
            f"queries you're not cited on, then re-check next run to confirm lift."
        )
    if plan.get("competitors_ahead"):
        plan["actions"].append(
            "Strengthen service/FAQ sections where competitors out-cite you "
            "(add credentials/entities for ChatGPT, fresh dated content for Perplexity)."
        )
    if plan.get("cited_domains"):
        plan["actions"].append(
            "Ensure your NAP exactly matches the directories AI already cites; "
            "pursue listings on the cited domains where you're absent."
        )
    return plan
