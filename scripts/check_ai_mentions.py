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


def build_prompts(practice_name: str, city: str, state: str, specialties: list[str]) -> list[str]:
    """Build search prompts to test AI mention of the practice."""
    prompts = [
        f"best dentist in {city} {state}",
        f"top rated dental practice in {city}",
        f"{practice_name} reviews",
    ]
    for specialty in specialties[:2]:
        prompts.append(f"best {specialty.lower()} in {city} {state}")
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
            model="claude-sonnet-4-20250514",
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

    # Find position — split response into numbered items or paragraphs
    position = _find_position(text, practice_name)

    # Extract context sentence
    context = _extract_context(text, practice_name)

    return {"mentioned": True, "position": position, "context": context}


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
        )

        results = []
        mention_count = 0

        for prompt in prompts:
            print(f"\nQuery: \"{prompt}\"")

            # Query each AI
            for ai_name, query_fn in [("Claude", query_claude), ("ChatGPT", query_openai)]:
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
