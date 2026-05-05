#!/usr/bin/env python3
"""Check if AI assistants mention a dental practice.

Queries ChatGPT, Claude, and Perplexity with practice-relevant prompts
and checks if the practice is mentioned in the response.

Usage:
    python scripts/check_ai_mentions.py --customer hilltop-family-dental
    python scripts/check_ai_mentions.py --customer hilltop-family-dental --save

Requires:
    ANTHROPIC_API_KEY — for Claude queries
    OPENAI_API_KEY — for ChatGPT queries (optional)
    PERPLEXITY_API_KEY — for Perplexity queries (optional)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from geo_agent.db import CustomerDB

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def build_prompts(practice_name: str, city: str, state: str, specialties: list[str], business_type: str = "practice") -> list[str]:
    """Build basic search prompts (backward compat). Use build_comprehensive_prompts for full checks."""
    return [p["prompt"] for p in build_comprehensive_prompts(practice_name, city, state, specialties, business_type)]


def build_comprehensive_prompts(
    practice_name: str, city: str, state: str, specialties: list[str],
    business_type: str = "practice", competitors: list[str] | None = None,
    neighborhoods: list[str] | None = None,
    services: list[str] | None = None,
) -> list[dict]:
    """Build comprehensive categorized prompts for AI mention tracking.

    Returns list of {"prompt": str, "category": str} dicts.
    Categories: brand, general, service, location, comparison, reputation, recommendation
    """
    prompts = []

    def add(prompt: str, category: str):
        prompts.append({"prompt": prompt, "category": category})

    # --- Brand queries (do they know us?) ---
    add(f"{practice_name} reviews", "brand")
    add(f"tell me about {practice_name}", "brand")
    add(f"is {practice_name} good", "brand")

    if business_type in ("practice", "dental_practice"):
        # --- General discovery (top of funnel) ---
        add(f"best dentist in {city} {state}", "general")
        add(f"top rated dental practice in {city}", "general")
        add(f"dentist near me {city} {state}", "general")
        add(f"find a dentist in {city}", "general")
        add(f"who is the best dentist in {city}", "general")
        add(f"recommend a dentist in {city} {state}", "recommendation")

        # --- Service-specific (high intent) ---
        # Use granular services first, then broad specialties
        # Deduplicate: don't repeat if a service name matches a specialty
        service_queries = set()
        if services:
            for svc in services[:15]:
                svc_lower = svc.lower()
                if svc_lower not in service_queries:
                    service_queries.add(svc_lower)
                    add(f"best {svc_lower} in {city} {state}", "service")
                    add(f"who is an expert in {svc_lower} near {city}", "service")
        if specialties:
            for spec in specialties[:10]:
                spec_lower = spec.lower()
                if spec_lower not in service_queries:
                    service_queries.add(spec_lower)
                    add(f"best {spec_lower} in {city} {state}", "service")
                    add(f"who is an expert in {spec_lower} near {city}", "service")
        if not service_queries:
            # Minimal fallback for practices with no specialties configured
            for s in ["dentist", "dental care"]:
                add(f"best {s} in {city} {state}", "service")

        # --- Expert/recommendation queries (natural language) ---
        if service_queries:
            top_services = list(service_queries)[:5]
            for svc in top_services:
                add(f"who do you recommend for {svc} in {city}", "recommendation")
            add(f"dentist who specializes in {top_services[0]} {city} {state}", "recommendation")

        # --- Location-specific (neighborhood level) ---
        if neighborhoods:
            for hood in neighborhoods[:3]:
                add(f"dentist in {hood} {city}", "location")
                add(f"best dental practice near {hood}", "location")
        # County/region level
        add(f"best dentist near {city} {state}", "location")

        # --- Comparison/competitor queries ---
        if competitors:
            for comp in competitors[:3]:
                add(f"{practice_name} vs {comp}", "comparison")
        add(f"best dentist in {city} compared", "comparison")

        # --- Reputation/trust queries ---
        add(f"{practice_name} patient reviews", "reputation")
        add(f"is {practice_name} in {city} good", "reputation")

        # --- Cost/insurance queries (high intent) ---
        add(f"affordable dentist in {city} {state}", "service")
        add(f"dentist that accepts medicaid in {city}", "service")

    elif business_type == "technology":
        # --- B2B tech/SaaS company ---
        # Infer industry from specialties or name
        industry_keywords = []
        for s in specialties[:5]:
            sl = s.lower()
            if any(w in sl for w in ("dental", "denture", "scan", "cad")):
                industry_keywords.append("dental")
                break
        industry = industry_keywords[0] if industry_keywords else "technology"

        add(f"best {industry} technology companies", "general")
        add(f"top {industry} software companies", "general")
        add(f"{practice_name} {industry} technology", "brand")
        add(f"best AI companies in {industry}", "general")
        add(f"{industry} technology startups to watch", "general")
        add(f"{industry} software comparison", "comparison")

        for specialty in specialties[:8]:
            add(f"best {specialty.lower()} software", "service")
            add(f"{specialty.lower()} companies", "service")

        if competitors:
            for comp in competitors[:3]:
                add(f"{practice_name} vs {comp}", "comparison")
            add(f"best alternatives to {competitors[0]}", "comparison")

        add(f"recommend {industry} software", "recommendation")

    else:
        # --- Generic business (consulting, services, etc.) ---
        add(f"best {business_type} companies", "general")
        add(f"top {business_type} firms", "general")
        add(f"{practice_name} {business_type}", "brand")

        if city and state:
            add(f"best {business_type} in {city} {state}", "location")
            add(f"{business_type} near {city}", "location")
            add(f"top rated {business_type} {city}", "general")
            add(f"recommend a {business_type} in {city} {state}", "recommendation")

        for specialty in specialties[:8]:
            add(f"best {specialty.lower()}", "service")
            add(f"{specialty.lower()} experts", "service")

        if competitors:
            for comp in competitors[:3]:
                add(f"{practice_name} vs {comp}", "comparison")

        add(f"{practice_name} reviews", "reputation")

    return prompts


def query_claude(prompt: str) -> str | None:
    """Query Claude and return the response text."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return None

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text
    except Exception as e:
        logger.warning(f"Claude query failed: {e}")
        return None


def query_openai(prompt: str) -> str | None:
    """Query ChatGPT and return the response text."""
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return None

    try:
        import httpx
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 1000,
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logger.warning(f"OpenAI query failed: {e}")
        return None


def query_perplexity(prompt: str) -> str | None:
    """Query Perplexity Sonar (searches live web, respects llms.txt)."""
    api_key = os.environ.get("PERPLEXITY_API_KEY", "")
    if not api_key:
        return None

    try:
        import httpx
        with httpx.Client(timeout=45.0) as client:
            resp = client.post(
                "https://api.perplexity.ai/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": "sonar",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 1000,
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logger.warning(f"Perplexity query failed: {e}")
        return None


def query_gemini(prompt: str) -> str | None:
    """Query Google Gemini (free tier, 15 RPM)."""
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return None

    try:
        import httpx
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={api_key}",
                headers={"Content-Type": "application/json"},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                },
            )
            resp.raise_for_status()
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        logger.warning(f"Gemini query failed: {e}")
        return None


def query_grok(prompt: str) -> str | None:
    """Query xAI Grok (OpenAI-compatible API)."""
    api_key = os.environ.get("XAI_API_KEY", "")
    if not api_key:
        return None

    try:
        import httpx
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                "https://api.x.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": "grok-3-mini",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 1000,
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logger.warning(f"Grok query failed: {e}")
        return None


def check_mention(text: str, practice_name: str) -> dict:
    """Check if the practice is mentioned and track its position.

    Returns a dict with:
    - mentioned: bool
    - position: int or None (1st, 2nd, 3rd mention in the response)
    - context: str (the sentence containing the mention)
    """
    if not text:
        return {"mentioned": False, "position": None, "context": ""}

    text_lower = text.lower()
    name_lower = practice_name.lower()

    # Check full name
    found = name_lower in text_lower

    # Check significant words from the name
    if not found:
        words = [w for w in name_lower.split() if len(w) > 3 and w not in ("dental", "dentistry", "family", "care")]
        if words and all(w in text_lower for w in words):
            found = True

    if not found:
        return {"mentioned": False, "position": None, "context": ""}

    # Filter out false positives — AI just echoing the name in a disclaimer
    disclaimer_phrases = [
        "i don't have specific information",
        "i can't access real-time",
        "i don't have access to",
        "i cannot verify",
        "i'm not able to",
        "i do not have",
        "i cannot provide specific",
        "i'm unable to",
        "i don't have real-time",
        "not have current data",
        "cannot confirm",
        "no specific information",
    ]
    # Check if the mention is just in a disclaimer context
    for phrase in disclaimer_phrases:
        if phrase in text_lower:
            # Find which sentence has the name
            import re as _re
            sentences = _re.split(r'[.!?]\s+', text)
            for sent in sentences:
                if name_lower in sent.lower() and any(p in sent.lower() for p in disclaimer_phrases):
                    return {"mentioned": False, "position": None, "context": sent.strip()[:150], "disclaimer": True}
            break

    # Find position — split response into numbered items or paragraphs
    position = _find_position(text, practice_name)

    # Extract context sentence
    context = _extract_context(text, practice_name)

    # Quality score: how good is this mention?
    quality = _score_mention_quality(text, practice_name, position, context)

    return {"mentioned": True, "position": position, "context": context, "quality_score": quality}


def _score_mention_quality(text: str, practice_name: str, position: int | None, context: str) -> int:
    """Score the quality of a mention from 0-100.

    Factors:
    - Position in list (1st = 100, 2nd = 80, etc.)
    - Sentiment (recommendation vs neutral mention)
    - Detail level (address, phone, services mentioned)
    - Context (listed as recommendation vs just mentioned)
    """
    score = 0
    text_lower = text.lower()
    ctx_lower = context.lower() if context else ""

    # Position score (0-40 points)
    if position is not None:
        if position == 1:
            score += 40
        elif position == 2:
            score += 32
        elif position == 3:
            score += 25
        elif position <= 5:
            score += 15
        else:
            score += 5
    else:
        score += 10  # Mentioned but not in a ranked list

    # Recommendation language (0-25 points)
    rec_phrases = ["recommend", "top pick", "excellent", "highly rated", "great choice",
                   "best", "outstanding", "leading", "top-rated", "well-known", "renowned"]
    for phrase in rec_phrases:
        if phrase in ctx_lower:
            score += 25
            break

    # Detail level (0-20 points) — AI knows real info about the practice
    detail_signals = [
        (r'\d{3}[-.)\s]\d{3}[-.]\d{4}', 5),  # phone number
        (r'\d+\s+\w+\s+(st|ave|blvd|rd|dr|way|ln)', 5),  # address
        (r'\d\.\d\s*(star|rating|out of)', 5),  # rating
        (r'(specializ|known for|offer)', 5),  # services detail
    ]
    import re as _re
    for pattern, pts in detail_signals:
        if _re.search(pattern, text_lower):
            score += pts

    # Negative signals (deductions)
    if "i'm not sure" in ctx_lower or "may not be" in ctx_lower:
        score -= 10
    if "verify" in ctx_lower or "check" in ctx_lower:
        score -= 5

    return max(0, min(100, score))


def _find_position(text: str, practice_name: str) -> int | None:
    """Determine what position the practice appears in a list of recommendations.

    Looks for numbered lists (1., 2., 3.) or bullet points and determines
    which item contains the practice name.
    """
    import re
    name_lower = practice_name.lower()

    # Try numbered list pattern: "1." or "1)" or "**1."
    numbered = re.split(r'\n\s*(?:\*\*)?(\d+)[.)]\s*', text)
    if len(numbered) > 2:
        for i in range(1, len(numbered), 2):
            num = int(numbered[i])
            content = numbered[i + 1] if i + 1 < len(numbered) else ""
            if name_lower in content.lower():
                return num

    # Try bullet points
    bullets = re.split(r'\n\s*[-*•]\s+', text)
    for i, bullet in enumerate(bullets):
        if name_lower in bullet.lower():
            return i  # 0-indexed but first bullet is position 1 effectively

    # Fallback: paragraph position
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    for i, para in enumerate(paragraphs):
        if name_lower in para.lower():
            return i + 1

    return None


def _extract_context(text: str, practice_name: str) -> str:
    """Extract the sentence or segment containing the practice name."""
    import re
    name_lower = practice_name.lower()

    # Split into sentences
    sentences = re.split(r'[.!?]\s+', text)
    for sent in sentences:
        if name_lower in sent.lower():
            return sent.strip()[:200]

    # Fallback: find a window around the mention
    idx = text.lower().find(name_lower)
    if idx >= 0:
        start = max(0, idx - 50)
        end = min(len(text), idx + len(practice_name) + 100)
        return text[start:end].strip()

    return ""


def main():
    parser = argparse.ArgumentParser(description="Check AI mentions of a practice")
    parser.add_argument("--customer", required=True, help="Customer ID")
    parser.add_argument("--save", action="store_true", help="Save results to DB as KPI")
    parser.add_argument("--db", default=None, help="Database file path")
    args = parser.parse_args()

    db = CustomerDB(db_path=args.db)
    try:
        customer = db.get_customer(args.customer)
        if not customer:
            print(f"Customer not found: {args.customer}")
            sys.exit(1)

        prompts = build_prompts(
            customer["name"], customer["city"], customer["state"],
            customer.get("specialties", []),
            business_type=customer.get("business_type", "practice"),
        )

        results = []
        mention_count = 0

        for prompt in prompts:
            print(f"\nQuery: \"{prompt}\"")

            # Query each AI engine
            for ai_name, query_fn in [("Claude", query_claude), ("ChatGPT", query_openai), ("Perplexity", query_perplexity), ("Gemini", query_gemini), ("Grok", query_grok)]:
                response = query_fn(prompt)
                if response is None:
                    print(f"  {ai_name}: (no API key)")
                    continue

                result = check_mention(response, customer["name"])
                if result["mentioned"]:
                    mention_count += 1
                    pos_str = f" (position #{result['position']})" if result["position"] else ""
                    print(f"  {ai_name}: MENTIONED{pos_str}")
                    if result["context"]:
                        print(f"    Context: \"{result['context'][:120]}...\"")
                else:
                    print(f"  {ai_name}: not mentioned")

                results.append({
                    "prompt": prompt,
                    "ai": ai_name,
                    "mentioned": result["mentioned"],
                    "position": result["position"],
                    "context": result["context"],
                    "response_preview": response[:300],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

        # Summary with position tracking
        mentioned_results = [r for r in results if r["mentioned"]]
        positions = [r["position"] for r in mentioned_results if r["position"] is not None]
        avg_position = sum(positions) / len(positions) if positions else None

        print(f"\n{'='*50}")
        print(f"Total mentions: {mention_count}/{len(results)}")
        if avg_position:
            print(f"Average position: #{avg_position:.1f}")
        if mentioned_results:
            print(f"\nMention details:")
            for r in mentioned_results:
                pos = f" #{r['position']}" if r['position'] else ""
                print(f"  [{r['ai']}] \"{r['prompt']}\" → position{pos}")

        if args.save:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            db.record_kpi(args.customer, "ai_mentions", mention_count, today)
            if avg_position:
                db.record_kpi(args.customer, "ai_avg_position", avg_position, today)
            print(f"Saved to KPI database.")

            # Save detailed results
            customer_dir = Path(__file__).resolve().parent.parent / "data" / "customers" / args.customer
            customer_dir.mkdir(parents=True, exist_ok=True)
            results_path = customer_dir / f"ai-mentions-{today}.json"
            results_path.write_text(json.dumps(results, indent=2))
            print(f"Detailed results saved to: {results_path}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
