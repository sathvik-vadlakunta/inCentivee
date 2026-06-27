"""Search-intent classification for keyword-driven content.

Best practice: target keywords by what the searcher intends to DO, not just volume.
We rank intent into three buckets and weight content selection by them:

- **transactional** — ready to act: a transaction verb (buy/sell/trade/pawn/cash for),
  a place to transact (buyer/dealer/shop), local urgency (near me / in {city}),
  or money intent (price/cost/quote/"how much can I get"/"my X worth"). These convert.
- **commercial** — comparing before acting: best/top/cheapest/reviews/vs/compare, or a
  bare "{product} {city}" noun phrase. Close to action.
- **informational** — research/curiosity: what is / how does / history / "are X valuable".
  Rarely converts; useful only as top-of-funnel, never the primary target.

Pure + deterministic (regex heuristics) so it's free and testable. Used by
`keyword_content` (GSC → content recs) and `gbp_qa` (Q&A enrichment) to prefer
action keywords. For a buyer like a precious-metals shop, "sell gold near me" beats
"are antique tea sets valuable" every time.
"""

from __future__ import annotations

import re

# A transaction verb / money / local-urgency signal — the searcher wants to act.
# Modifiers per the 2025 buyer-intent playbook (buy/sell/price/quote/discount/near me…).
_TRANSACTIONAL = re.compile(
    r"\b(buy|buying|sell|sells|selling|purchase|trade|trade[\s-]?in|pawn|consign|"
    r"cash\s*for|hire|book|schedule|appointment|appointments|quote|order|financing|"
    r"for\s+sale|discount|deal|deals|coupon|open\s+now|"
    r"price|prices|pricing|cost|costs|how\s+much\s+(can\s+i\s+get|for|is|do|will)|"
    r"my\s+\w+(\s+\w+)?\s+worth)\b"
    r"|\bnear\s+me\b",
    re.I,
)
# A place to transact — buyer/dealer/shop nouns imply transactional intent.
_PLACE = re.compile(r"\b(buyer|buyers|dealer|dealers|shop|store|exchange|pawn\s*shop)\b", re.I)
# Comparing before acting — the "money tier": evaluation/validation modifiers.
_COMMERCIAL = re.compile(
    r"\b(best|top|cheapest|affordable|trusted|reputable|reviews?|rated|rating|"
    r"vs\.?|versus|compare|comparison|alternatives?|competitors?|recommended|"
    r"reliable|legit|worth\s+it)\b",
    re.I,
)
# Research / curiosity — NOT action. Only explicit research phrasing lands here; everything
# else defaults to commercial (the "money tier"), since most service/product queries are
# evaluation-stage, not pure curiosity.
_INFORMATIONAL = re.compile(
    r"\b(what\s+is|what\s+are|what'?s\s+a|how\s+(does|do|to)|why|when|history|meaning|"
    r"definition|facts?\s+about|types?\s+of|examples?\s+of|guide\s+to|ideas?|"
    r"can\s+i|symptoms?|causes?)\b"
    r"|\bare\s+.+\s+(valuable|worth\s+anything|real)\b",
    re.I,
)
# Local signal — "near me", "in {City}", "{City}, ST". Local + action = the premium target
# ("best dentist in austin", "where to sell gold near me").
_LOCAL = re.compile(
    r"\bnear\s+me\b|\bnearby\b|\bin\s+[A-Z][a-z]+|,\s*[A-Z]{2}\b|\blocal\b", re.I)


def classify_intent(keyword: str) -> str:
    """Return 'transactional', 'commercial', or 'informational' for a keyword.

    Transactional (ready to act) > informational (explicit research) > commercial (default
    money tier). Defaulting ambiguous product/service queries to commercial is intentional:
    bare "{service} {city}" searches are evaluation-stage buyers, not curiosity.
    """
    k = (keyword or "").strip()
    if not k:
        return "informational"
    # Transactional signals win — strongest, clearest action intent ("sell gold", "near me").
    if _TRANSACTIONAL.search(k) or _PLACE.search(k):
        return "transactional"
    # Explicit research phrasing → informational ("are tea sets valuable", "how does X work").
    if _INFORMATIONAL.search(k):
        return "informational"
    # Everything else — comparison modifiers OR a bare service/product query → commercial.
    return "commercial"


def has_local_intent(keyword: str) -> bool:
    """True when the search is geographically scoped (near me / in {city} / {City}, ST)."""
    return bool(_LOCAL.search(keyword or ""))


_WEIGHT = {"transactional": 2.0, "commercial": 1.5, "informational": 0.4}
_RANK = {"transactional": 3, "commercial": 2, "informational": 1}

# UI + generation metadata per intent tier.
INTENT_META = {
    "transactional": {"label": "Buy/Action", "tier": "transactional", "color": "#166534", "bg": "#dcfce7",
                      "format": "conversion-focused page (clear CTA, location, 'how it works', offer)"},
    "commercial": {"label": "Compare/Decide", "tier": "commercial", "color": "#92400e", "bg": "#fef3c7",
                   "format": "comparison/listicle ('best … in {city}', pros/cons, ratings, why-choose-us)"},
    "informational": {"label": "Research", "tier": "informational", "color": "#475569", "bg": "#e2e8f0",
                      "format": "concise answer / FAQ (top-of-funnel only)"},
}


def intent_weight(keyword: str) -> float:
    """Multiplier for ranking content opportunities — boosts action keywords."""
    return _WEIGHT[classify_intent(keyword)]


def intent_rank(keyword: str) -> int:
    """Ordinal (3 high → 1 low) for sorting; transactional first."""
    return _RANK[classify_intent(keyword)]


def target_priority(keyword: str) -> float:
    """Ranking score for 'what to target' — intent weight, boosted for local searches.

    A local action search ('sell gold near me', 'best dentist in austin') is the single
    highest-value target, so local adds a 40% boost on top of the intent weight.
    """
    return intent_weight(keyword) * (1.4 if has_local_intent(keyword) else 1.0)


def is_action(keyword: str) -> bool:
    """True for transactional/commercial (action / purchase-decision) keywords."""
    return classify_intent(keyword) != "informational"


def intent_meta(keyword: str) -> dict:
    """UI/generation metadata (label, color, recommended content format) for a keyword."""
    return INTENT_META[classify_intent(keyword)]


def content_format(keyword: str) -> str:
    """Recommended content format for a keyword's intent (match format to intent)."""
    return INTENT_META[classify_intent(keyword)]["format"]
