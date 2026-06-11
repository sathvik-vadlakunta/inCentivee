"""Extract business entities mentioned in AI engine responses.

Parses full_response text from ai_mention_results to find all businesses
mentioned (not just our customer). Used for competitive share-of-voice
analysis and auto-discovery of competitors.
"""

from __future__ import annotations

import re


# Words that are NOT business names (common filler in AI responses)
_STOP_NAMES = frozenset({
    "here are", "here is", "the following", "some options", "you might",
    "consider the following", "top choices", "best options", "here's a list",
    "in conclusion", "note that", "keep in mind", "important to",
    "for example", "such as", "according to", "based on", "please note",
    "i recommend", "i would suggest", "it depends", "disclaimer",
    "however", "additionally", "furthermore", "overall",
})

# Platform/directory names that should NOT be treated as competitors
_PLATFORM_NAMES = frozenset({
    # Review/directory platforms
    "yelp", "google", "google maps", "google my business", "google business",
    "google reviews", "facebook", "instagram", "twitter", "tiktok",
    "linkedin", "reddit", "healthgrades", "zocdoc", "zocdoc.com",
    "vitals", "ratemds", "webmd", "bbb", "better business bureau",
    "angi", "angie's list", "thumbtack", "homeadvisor", "nextdoor",
    "yellowpages", "amazon", "walmart", "costco", "ebay", "etsy",
    # Consulting/unrelated
    "accenture", "deloitte", "mckinsey", "mckinsey & company",
    "peptide sciences",
    # Medical institutions
    "mayo clinic", "cleveland clinic", "johns hopkins",
    "american dental association", "ada",
    # Generic terms that aren't businesses (industry-agnostic)
    "location", "overview", "summary", "note", "disclaimer",
    "website", "address", "phone", "email", "hours", "pricing",
    "cost", "reviews", "ratings", "insurance", "payment",
    "specialty", "services", "treatment", "procedure", "experience",
    "quality", "care", "staff", "team", "office", "practice",
    "services offered", "what industry", "factors to consider",
    "key features", "things to consider", "important factors",
    "top picks", "our top", "editor's pick", "best overall",
    "pros and cons", "final thoughts", "bottom line",
    # Dental-specific generic terms
    "general dentistry", "family dentistry", "cosmetic dentistry",
    "dental implants", "dental services", "dental care",
    # Legal-specific generic terms
    "personal injury", "family law", "criminal defense",
    "estate planning", "business law",
    # Medical-specific generic terms
    "primary care", "urgent care", "family medicine",
    # Retail/service generic terms
    "customer service", "free shipping", "money back guarantee",
    "free consultation", "free estimate",
    # Review/aggregator platforms (these get cited a LOT and otherwise pollute
    # share-of-voice as fake "competitors")
    "trustpilot", "bbb accredited", "sitejabber", "consumeraffairs",
    "glassdoor", "indeed", "birdeye", "trustindex", "shopper approved",
    "resellerratings", "pissedconsumer", "g2", "capterra", "clutch", "yotpo",
    "trustindex.io", "bbb.org",
})

# Standalone tokens that mark a name as a review/directory/aggregator platform
# rather than a competitor — catches variants the exact set misses
# ('BBB Accredited', 'Trustpilot Reviews', 'Yelp listing').
_PLATFORM_TOKENS = frozenset({
    "yelp", "trustpilot", "bbb", "google", "facebook", "instagram", "reddit",
    "healthgrades", "zocdoc", "vitals", "ratemds", "webmd", "angi", "thumbtack",
    "homeadvisor", "nextdoor", "yellowpages", "sitejabber", "consumeraffairs",
    "glassdoor", "indeed", "birdeye", "trustindex", "resellerratings",
    "pissedconsumer", "capterra", "yotpo",
})


def is_platform_or_directory(normalized_name: str) -> bool:
    """True if a name is a review/directory/aggregator platform, not a competitor.

    Used both at extraction time and at share-of-voice read time, so already-stored
    junk entities are filtered without needing a backfill.
    """
    n = (normalized_name or "").lower().strip()
    if not n:
        return True
    if n in _PLATFORM_NAMES:
        return True
    words = set(re.split(r"[^a-z0-9]+", n))
    return bool(words & _PLATFORM_TOKENS)

# Common suffixes to strip from extracted names
_STRIP_SUFFIXES = re.compile(
    r'\s*[-–—]\s*$|'         # trailing dashes
    r'\s*\(.*$|'             # trailing parenthetical
    r'\s*,\s*(LLC|Inc|Ltd|PC|DDS|DMD|MD|PA|PLLC)\.?\s*$',  # business suffixes
    re.IGNORECASE,
)


def extract_entities_from_response(
    response_text: str,
    customer_name: str,
) -> list[dict]:
    """Extract all business/practice names mentioned in an AI response.

    Returns list of dicts:
        {name, normalized_name, position, is_customer}
    """
    if not response_text or len(response_text) < 20:
        return []

    entities: list[dict] = []
    seen: set[str] = set()

    def _add(name: str, position: int) -> None:
        name = _STRIP_SUFFIXES.sub("", name).strip().rstrip(".")
        if len(name) < 3 or len(name) > 60:
            return
        norm = name.lower().strip()
        if norm in seen:
            return
        # Skip generic phrases and platform names
        if norm in _STOP_NAMES or any(s in norm for s in _STOP_NAMES):
            return
        if is_platform_or_directory(norm):
            return
        # Must start with uppercase or digit (real business names)
        if not name[0].isupper() and not name[0].isdigit():
            return
        seen.add(norm)
        entities.append({
            "name": name,
            "normalized_name": norm,
            "position": position,
            "is_customer": _is_same_business(norm, customer_name),
        })

    # Pattern 1: Numbered list — "1. **Business Name** — description"
    #   or "1. Business Name: description" or "1) Business Name -"
    for m in re.finditer(
        r'(?:^|\n)\s*(\d+)[.)]\s*\*{0,2}\s*'  # number + optional bold markers
        r'([A-Z0-9][A-Za-z0-9\s&\'\-\.\/]{2,55}?)'  # business name
        r'\s*\*{0,2}\s*(?:[-–—:,\n]|$)',  # delimiter
        response_text,
    ):
        _add(m.group(2).strip(), int(m.group(1)))

    # Pattern 2: Bold names — "**Business Name**"
    pos = len(entities) + 1
    for m in re.finditer(r'\*\*([A-Z0-9][A-Za-z0-9\s&\'\-\.\/]{2,55}?)\*\*', response_text):
        _add(m.group(1).strip(), pos)
        pos += 1

    # Pattern 3: Bullet points — "- Business Name: description"
    for m in re.finditer(
        r'(?:^|\n)\s*[-*•]\s*\*{0,2}\s*'
        r'([A-Z0-9][A-Za-z0-9\s&\'\-\.\/]{2,55}?)'
        r'\s*\*{0,2}\s*(?:[-–—:,\n]|$)',
        response_text,
    ):
        _add(m.group(1).strip(), pos)
        pos += 1

    return entities


def _is_same_business(normalized_entity: str, customer_name: str) -> bool:
    """Check if an extracted entity matches the customer's business name."""
    cust_lower = customer_name.lower().strip()

    # Exact match
    if normalized_entity == cust_lower:
        return True

    # Significant word overlap (ignore common words)
    noise = {"the", "of", "and", "in", "at", "for", "a", "an", "dr", "dr.",
             "dental", "dentistry", "family", "care", "group", "center",
             "clinic", "practice", "associates", "llc", "inc", "pc"}
    entity_words = set(normalized_entity.split()) - noise
    cust_words = set(cust_lower.split()) - noise

    if not entity_words or not cust_words:
        return False

    # Both directions: entity subset of customer or vice versa
    if entity_words.issubset(cust_words):
        return True
    if cust_words.issubset(entity_words):
        return True

    return False


def extract_and_store(db, run_id: str, customer_id: str, customer_name: str) -> int:
    """Extract entities from all results in a run and store them.

    Returns count of entities extracted.
    """
    results = db.get_ai_mention_results(run_id)
    total = 0
    run_date = None

    for r in results:
        if not run_date:
            # Get run_date from the run record
            runs = db.conn.execute(
                "SELECT run_date FROM ai_mention_runs WHERE id = ?", (run_id,)
            ).fetchone()
            run_date = runs["run_date"] if runs else ""

        response = r.get("full_response", "")
        if not response:
            continue

        entities = extract_entities_from_response(response, customer_name)
        for ent in entities:
            db.save_ai_response_entity({
                "result_id": r["id"],
                "run_id": run_id,
                "customer_id": customer_id,
                "entity_name": ent["name"],
                "entity_name_normalized": ent["normalized_name"],
                "is_customer": ent["is_customer"],
                "position": ent["position"],
                "engine": r["engine"],
                "prompt": r["prompt"],
                "prompt_category": r.get("prompt_category", "general"),
                "run_date": run_date,
            })
            total += 1

    return total
