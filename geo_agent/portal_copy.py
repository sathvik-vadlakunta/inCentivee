"""Client Portal — plain-English copy module.

Single source of truth for every client-facing sentence used on the
Overview page and the 5 pillar-detail pages (Tickets 4-6). Nothing here is
scoring logic — it's labeling/glue on top of `practicerank_score.py`, kept
in one file so the portal's various templates can't drift out of sync with
each other's wording.

NOTE FOR REVIEWERS: this copy is a first draft written to match the tone of
the spec mockup (`specs/platform/client-portal.html`) and has NOT been
reviewed by Kody/marketing yet. Treat every string below as provisional
until that review happens.

See:
- `geo_agent/practicerank_score.py:33` (PILLAR_WEIGHTS, stable DB keys)
- `geo_agent/practicerank_score.py:42` (PILLAR_LABELS)
- `geo_agent/practicerank_score.py:52` (GRADES / grade_from_score labels)
- `geo_agent/practicerank_score.py:349` (_FOUNDATION_ITEMS)
- `specs/platform/client-portal.html` (rendered mockup this copy is drawn from)
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Pillar key <-> portal URL slug mapping
#
# The DB/scoring layer keys pillars by stable internal names (PILLAR_WEIGHTS
# in practicerank_score.py) that predate the portal and shouldn't be renamed
# (would require a migration). The portal instead uses human-readable URL
# slugs. This mapping is the only place that translates between the two so
# Overview (Ticket 4) can turn `score["pillars"]` (keyed by DB key) into
# portal links (keyed by slug).
# ---------------------------------------------------------------------------

PILLAR_KEY_TO_SLUG: dict[str, str] = {
    "ai_visibility": "ai-visibility",
    "technical_health": "geo-foundation",
    "content_velocity": "content-coverage",
    "reputation": "reputation",
    "search_growth": "search-performance",
}

PILLAR_SLUG_TO_KEY: dict[str, str] = {slug: key for key, slug in PILLAR_KEY_TO_SLUG.items()}


# ---------------------------------------------------------------------------
# Pillar copy — keyed by portal URL slug.
#
# - label: matches PILLAR_LABELS in practicerank_score.py (human name).
# - one_liner: the Overview breakdown sentence under each pillar bar
#   (spec lines ~297-330, class="why").
# - hero_description: the pillar-detail-page hero sentence, including the
#   "X% of your overall score" clause (spec lines ~366-674, the <p> under
#   each pillar-hero <h2>).
# ---------------------------------------------------------------------------

PILLAR_COPY: dict[str, dict] = {
    "ai-visibility": {
        "label": "AI Visibility",
        "one_liner": (
            "Out of 5 AI assistants we test (ChatGPT, Claude, Perplexity, "
            "Gemini, Grok), how many recommend you when a patient asks — "
            "and how you rank against nearby practices in those answers."
        ),
        "hero_description": (
            "How often ChatGPT, Claude, Perplexity, Gemini, and Grok "
            "recommend your practice when someone asks a question like "
            "\"best dentist near me\" — and how you rank against nearby "
            "practices in those answers. 30% of your overall score."
        ),
    },
    "geo-foundation": {
        "label": "GEO Foundation",
        "one_liner": (
            "7 technical deliverables that make your site machine-readable "
            "to AI search (structured business info, FAQ formatting, "
            "sitemap, etc.) — how many are done."
        ),
        "hero_description": (
            "The technical groundwork that makes your website readable and "
            "trustworthy to AI search tools — the deliverables we ship for "
            "every practice. 30% of your overall score."
        ),
    },
    "content-coverage": {
        "label": "Content & Coverage",
        "one_liner": (
            "Pages and articles we've published for you, and how many of "
            "your service areas/cities have their own page."
        ),
        "hero_description": (
            "New pages and articles we've written for your practice, and "
            "how completely they cover your services and service areas. "
            "20% of your overall score."
        ),
    },
    "reputation": {
        "label": "Reputation",
        "one_liner": (
            "Your Google rating and how quickly your review count is "
            "growing month over month."
        ),
        "hero_description": (
            "Your Google rating and how quickly your review count is "
            "growing. 10% of your overall score."
        ),
    },
    "search-performance": {
        "label": "Search Performance",
        "one_liner": (
            "Clicks and impressions from regular Google search, this "
            "period vs last — and which keywords are moving."
        ),
        "hero_description": (
            "How your website is trending in regular Google search — "
            "clicks and visibility over time. 10% of your overall score."
        ),
    },
}


# ---------------------------------------------------------------------------
# GEO Foundation checklist item copy — keyed by the first key of each tuple
# in _FOUNDATION_ITEMS (practicerank_score.py:349-358). Matches the style of
# the GEO Foundation checklist mock (spec lines ~458-465): a short label plus
# a plain-English "what this means for you" description.
# ---------------------------------------------------------------------------

FOUNDATION_ITEM_COPY: dict[str, dict] = {
    "seo_schema_localbusiness": {
        "label": "Business info schema",
        "description": (
            "Tells Google & AI assistants your name, address, hours, and "
            "services."
        ),
    },
    "seo_schema_faq": {
        "label": "FAQ formatting",
        "description": "Lets AI assistants pull direct answers from your site.",
    },
    "seo_llms_txt": {
        "label": "AI-readability file (llms.txt)",
        "description": "A file that tells AI assistants how to read your site.",
    },
    "seo_robots_txt": {
        "label": "AI crawling permissions",
        "description": "The rules that let AI bots access your site.",
    },
    "seo_llms_full": {
        "label": "Extended AI content file",
        "description": "More detail for AI assistants beyond the basics.",
    },
    "seo_xml_sitemap": {
        "label": "Sitemap",
        "description": "Tells search engines every page on your site.",
    },
    "seo_schema_review": {
        "label": "Additional structured data",
        "description": "Reviews, staff bios, service listings.",
    },
    "seo_structured_headings": {
        "label": "Organized page headings",
        "description": "Helps AI assistants understand your page structure.",
    },
}


# ---------------------------------------------------------------------------
# Score-hero takeaway, keyed by grade_from_score()'s "label" field
# (practicerank_score.py:52-58: Excellent / Strong / Good / Needs Work /
# Critical). Self-contained per grade — deliberately does NOT reference
# per-customer specifics ("your biggest opportunity" etc.); that's out of
# scope for a pure grade->text lookup (see Overview page ticket).
# ---------------------------------------------------------------------------

_GRADE_TAKEAWAYS: dict[str, str] = {
    "Excellent": "🌟 Excellent — you're leading the pack in AI and local search visibility.",
    "Strong": "✅ Strong — you're in the top range for AI search visibility.",
    "Good": "🙂 Good — solid footing, with clear room to grow.",
    "Needs Work": "⚠️ Needs Work — you're behind where you should be, but the gaps are fixable.",
    "Critical": "🚨 Critical — most patients searching for a dentist can't find you yet.",
}

_DEFAULT_TAKEAWAY = "Your PracticeRank Score is being calculated."


def grade_takeaway(grade_label: str) -> str:
    """Return a self-contained one-line takeaway sentence for a grade label.

    `grade_label` is one of `grade_from_score()`'s `"label"` values
    (practicerank_score.py:52-58): "Excellent", "Strong", "Good",
    "Needs Work", "Critical". Unrecognized labels return a safe generic
    default rather than raising, since this is display copy — a bad label
    should never crash a customer-facing page.
    """
    return _GRADE_TAKEAWAYS.get(grade_label, _DEFAULT_TAKEAWAY)
