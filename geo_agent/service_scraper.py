"""Scrape a customer's services from their website with Claude.

Shared by the manual "Scrape from site" button, the Local Relevancy Engine
(auto-populates missing services), and new-customer onboarding.
"""

from __future__ import annotations

import json
import logging
import os
import re

logger = logging.getLogger(__name__)


def scrape_services(domain: str, name: str = "", business_type: str = "local business") -> list[str]:
    """Fetch the homepage and extract the services it offers. [] on any failure."""
    domain = (domain or "").strip()
    if not domain:
        return []
    url = domain if domain.startswith("http") else f"https://{domain}"
    try:
        import httpx
        with httpx.Client(timeout=20.0, follow_redirects=True,
                          headers={"User-Agent": "Mozilla/5.0 (compatible; PracticeRankBot/1.0)"}) as cl:
            html = cl.get(url).text
    except Exception as exc:  # noqa: BLE001
        logger.info("service scrape fetch failed for %s: %s", url, exc)
        return []

    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()[:6000]
    if not os.environ.get("ANTHROPIC_API_KEY") or not text:
        return []

    prompt = (
        f"This is the website text for a {business_type} named '{name}'. List the specific "
        f"services or products it offers, as short noun phrases a customer would search "
        f"(e.g. \"Sell Gold\", \"Teeth Whitening\", \"Personal Injury\"). "
        f"Return ONLY a JSON array of 4-10 strings — no prose, no code fences.\n\n{text}"
    )
    try:
        import anthropic

        from geo_agent.llm import MODEL_AUX
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        msg = client.messages.create(model=MODEL_AUX, max_tokens=400,
                                     messages=[{"role": "user", "content": prompt}])
        raw = "".join(b.text for b in msg.content if b.type == "text").strip()
        raw = re.sub(r"^```(?:json)?|```$", "", raw).strip()
        s, e = raw.find("["), raw.rfind("]")
        arr = json.loads(raw[s:e + 1]) if s != -1 and e > s else []
    except Exception as exc:  # noqa: BLE001
        logger.info("service scrape extract failed for %s: %s", domain, exc)
        return []
    return [str(x).strip() for x in arr if str(x).strip()][:12]


def ensure_services(db, customer_id: str) -> list[str]:
    """Scrape + save services only if the customer has none. Returns the services."""
    customer = db.get_customer(customer_id)
    if not customer:
        return []
    existing = db.get_services(customer_id) or []
    if existing:
        return [s.get("name", "") for s in existing]
    found = scrape_services(
        customer.get("domain", ""), customer.get("name", ""),
        customer.get("business_type", "local business"))
    for nm in found:
        db.add_service(customer_id, nm)
    if found:
        logger.info("auto-populated %d services for %s", len(found), customer_id)
    return found
