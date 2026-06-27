"""Web-grounded expert-quote sourcing with verbatim verification.

Populates ``customers.verified_quotes`` with REAL quotes pulled from authoritative
sources. Every candidate quote is checked to appear **verbatim** in the live source
page before it is accepted — anything we cannot confirm against the source is
rejected. This is the anti-fabrication gate that lets the content pipeline cite
expert quotes without ever inventing one.

Flow: pick sources (per-vertical seeds + operator URLs) → fetch + de-tag → Claude
extracts contiguous verbatim quotes from NAMED experts → verify each appears in the
source → store the survivors as {quote, attribution, source, url}.

See specs/active/web-grounded-quote-sourcing.md.
"""

from __future__ import annotations

import html
import logging
import os
import re

import httpx

from geo_agent.llm import MODEL_CONTENT, complete

logger = logging.getLogger(__name__)

# Reputable starting points per vertical. Operator-supplied article URLs (the most
# reliable source of attributable quotes) are merged on top of these at call time.
AUTHORITATIVE_SOURCES: dict[str, list[dict[str, str]]] = {
    "precious_metals": [
        {"label": "World Gold Council", "url": "https://www.gold.org/goldhub/gold-focus"},
        {"label": "Kitco News", "url": "https://www.kitco.com/news/"},
        {"label": "Reuters Commodities", "url": "https://www.reuters.com/markets/commodities/"},
    ],
    "practice": [
        {"label": "American Dental Association", "url": "https://www.ada.org/publications/ada-news"},
    ],
    "legal": [
        {"label": "American Bar Association", "url": "https://www.americanbar.org/news/"},
    ],
}

# business_type → source-bucket key (mirrors directory_profiles' grouping).
_BUSINESS_TYPE_SOURCES = {
    "precious_metals_buyer": "precious_metals",
    "jeweler": "precious_metals",
    "practice": "practice",
    "dentist": "practice",
    "legal": "legal",
    "law_firm": "legal",
    "attorney": "legal",
}

_MIN_QUOTE_CHARS = 40
_MIN_QUOTE_WORDS = 6

_EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "quotes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "quote": {"type": "string", "description": "The exact, contiguous verbatim sentence as it appears in the source — copied character-for-character, no paraphrase, no ellipses, no edits."},
                    "speaker": {"type": "string", "description": "The named person or organization the source attributes the quote to."},
                    "role": {"type": "string", "description": "That speaker's title/affiliation as stated in the source (or empty)."},
                },
                "required": ["quote", "speaker", "role"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["quotes"],
    "additionalProperties": False,
}


def _normalize(s: str) -> str:
    """Lowercase, unify quotes/dashes, collapse whitespace — for verbatim matching."""
    s = html.unescape(s or "")
    s = (s.replace("“", '"').replace("”", '"')
           .replace("‘", "'").replace("’", "'")
           .replace("–", "-").replace("—", "-").replace("…", "..."))
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


def _significant_word_count(quote: str) -> int:
    return len([w for w in re.findall(r"[a-zA-Z]{3,}", quote)])


def _verify(quote: str, normalized_source: str) -> bool:
    """True only if the quote appears verbatim (normalized) in the source text.

    Strict on purpose: we would rather drop a real quote than store a fabricated
    one. The normalized quote (stripped of surrounding quote marks) must be a
    substring of the normalized source, and be substantial enough to be a real
    quotation rather than an incidental phrase match.
    """
    q = _normalize(quote).strip('"\'' + " .,")
    if len(q) < _MIN_QUOTE_CHARS or _significant_word_count(q) < _MIN_QUOTE_WORDS:
        return False
    return q in normalized_source


def _fetch(url: str) -> tuple[str, str]:
    """Return (plaintext_for_extraction, normalized_full_text_for_verification)."""
    try:
        with httpx.Client(timeout=20.0, follow_redirects=True,
                          headers={"User-Agent": "Mozilla/5.0 (compatible; PracticeRankBot/1.0)"}) as cl:
            raw = cl.get(url).text
    except Exception as exc:  # noqa: BLE001
        logger.info("quote source fetch failed for %s: %s", url, exc)
        return "", ""
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", raw, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:14000], _normalize(text)


def _extract_candidates(client, plaintext: str, source_label: str, topics: str) -> list[dict]:
    """Ask Claude for contiguous verbatim quotes from named experts in the text."""
    if not plaintext:
        return []
    import json
    user = (
        f"Below is text from a page published by '{source_label}'. Extract up to 5 direct "
        f"quotations that are attributed in the text to a NAMED person or a named organization "
        f"and that are relevant to: {topics}.\n\n"
        f"STRICT RULES:\n"
        f"- Copy each quote EXACTLY as it appears — character for character. Do NOT paraphrase, "
        f"summarize, fix grammar, join sentences, or use ellipses.\n"
        f"- Each quote must be a single contiguous span of text actually present below.\n"
        f"- Only include a quote if the text clearly attributes it to a named speaker.\n"
        f"- If there are no real attributed quotes, return an empty list. Never invent one.\n\n"
        f"TEXT:\n{plaintext}"
    )
    try:
        out = complete(client, model=MODEL_CONTENT, user=user, max_tokens=2000,
                       output_schema=_EXTRACT_SCHEMA, label="quote-extract")
        return json.loads(out).get("quotes", [])
    except Exception as exc:  # noqa: BLE001
        logger.info("quote extraction failed for %s: %s", source_label, exc)
        return []


def _sources_for(business_type: str) -> list[dict[str, str]]:
    bucket = _BUSINESS_TYPE_SOURCES.get((business_type or "").lower())
    return list(AUTHORITATIVE_SOURCES.get(bucket, [])) if bucket else []


def source_quotes_for_customer(db, customer_id: str, *, max_quotes: int = 6,
                               extra_urls: list[str] | None = None,
                               replace: bool = False) -> dict:
    """Source, verify, and store verified quotes for a customer.

    Returns a report dict: sources_checked, candidates, accepted, rejected, stored.
    Only quotes that pass verbatim verification are persisted.
    """
    customer = db.get_customer(customer_id)
    if not customer:
        raise ValueError(f"Unknown customer: {customer_id}")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    topics = ", ".join(filter(None, [
        customer.get("business_type", "").replace("_", " "),
        customer.get("name", ""),
        ", ".join((customer.get("services") or [])[:5]) if isinstance(customer.get("services"), list) else "",
    ])) or "this business's industry"

    sources = _sources_for(customer.get("business_type", ""))
    for u in (extra_urls or []):
        sources.append({"label": u.split("//")[-1].split("/")[0], "url": u})

    existing = customer.get("verified_quotes") or []
    seen = {_normalize(q.get("quote", "")) for q in existing}
    report = {"sources_checked": 0, "candidates": 0, "accepted": 0, "rejected": 0,
              "stored": [], "rejected_samples": []}
    accepted: list[dict] = []

    for src in sources:
        if len(accepted) >= max_quotes:
            break
        plaintext, norm_source = _fetch(src["url"])
        report["sources_checked"] += 1
        if not plaintext:
            continue
        for cand in _extract_candidates(client, plaintext, src["label"], topics):
            report["candidates"] += 1
            quote = (cand.get("quote") or "").strip()
            if not _verify(quote, norm_source):
                report["rejected"] += 1
                if len(report["rejected_samples"]) < 5:
                    report["rejected_samples"].append(quote[:80])
                continue
            key = _normalize(quote)
            if key in seen:
                continue
            seen.add(key)
            speaker = (cand.get("speaker") or "").strip()
            role = (cand.get("role") or "").strip()
            attribution = ", ".join(filter(None, [speaker, role])) or src["label"]
            entry = {"quote": quote, "attribution": attribution,
                     "source": src["label"], "url": src["url"]}
            accepted.append(entry)
            report["accepted"] += 1
            report["stored"].append(entry)
            if len(accepted) >= max_quotes:
                break

    final = accepted if replace else (existing + accepted)
    db.update_customer(customer_id, verified_quotes=final)
    report["total_on_file"] = len(final)
    return report
