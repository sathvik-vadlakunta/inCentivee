"""Quick Wins Engine — surfaces highest-impact, lowest-effort actions.

Each quick win has: id, title, description, pillar, impact, effort,
estimated score boost, action URL, and whether it's auto-actionable.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geo_agent.db import CustomerDB

logger = logging.getLogger(__name__)

IMPACT_RANK = {"high": 3, "medium": 2, "low": 1}
EFFORT_RANK = {"low": 3, "medium": 2, "high": 1}  # inverted: low effort = high priority


@dataclass
class QuickWin:
    id: str
    title: str
    description: str
    pillar: str  # ai_visibility, search_growth, technical, content, reputation
    impact: str  # high, medium, low
    effort: str  # low, medium, high
    est_score_boost: int
    action_url: str
    action_label: str
    auto_actionable: bool = False
    details: dict | None = None

    @property
    def priority(self) -> int:
        """Higher = more urgent. Range: 1-9."""
        return IMPACT_RANK.get(self.impact, 1) * EFFORT_RANK.get(self.effort, 1)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["priority"] = self.priority
        return d


def detect_quick_wins(db: CustomerDB, customer_id: str) -> list[QuickWin]:
    """Detect all applicable quick wins for a customer."""
    wins: list[QuickWin] = []
    base_url = f"/customer/{customer_id}"

    _check_ai_visibility(db, customer_id, base_url, wins)
    _check_search_health(db, customer_id, base_url, wins)
    _check_technical(db, customer_id, base_url, wins)
    _check_content(db, customer_id, base_url, wins)
    _check_reputation(db, customer_id, base_url, wins)

    return prioritize(wins)


def prioritize(wins: list[QuickWin]) -> list[QuickWin]:
    """Sort quick wins by priority (highest first), then by score boost."""
    return sorted(wins, key=lambda w: (-w.priority, -w.est_score_boost))


def format_for_email(wins: list[QuickWin], max_items: int = 3) -> str:
    """Format top quick wins as markdown for email templates."""
    if not wins:
        return "No immediate actions needed — keep up the great work!"

    lines = ["**Your Top Actions This Week:**", ""]
    for i, w in enumerate(wins[:max_items], 1):
        lines.append(f"{i}. **{w.title}** — {w.description}")
        lines.append(f"   Est. impact: +{w.est_score_boost} to your PracticeRank Score.")
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# AI Visibility checks
# ---------------------------------------------------------------------------

def _check_ai_visibility(
    db: CustomerDB, customer_id: str, base_url: str, wins: list[QuickWin]
) -> None:
    runs = db.get_ai_mention_runs(customer_id, limit=10)

    # No AI check run recently
    if not runs:
        wins.append(QuickWin(
            id="ai_no_run",
            title="Run your first AI visibility check",
            description="See how AI search engines like ChatGPT and Claude recommend your business.",
            pillar="ai_visibility",
            impact="high",
            effort="low",
            est_score_boost=5,
            action_url=f"{base_url}?tab=ai",
            action_label="Run AI Check",
            auto_actionable=True,
        ))
        return

    latest = runs[0]
    run_date = latest.get("run_date", "")
    try:
        last_run = datetime.fromisoformat(run_date.replace("Z", "+00:00"))
        if last_run.tzinfo is None:
            last_run = last_run.replace(tzinfo=timezone.utc)
        days_since = (datetime.now(timezone.utc) - last_run).days
    except (ValueError, TypeError):
        days_since = 999

    if days_since > 30:
        wins.append(QuickWin(
            id="ai_stale_run",
            title="Run an AI visibility check",
            description=f"It's been {days_since} days since your last scan. Check if optimizations are working.",
            pillar="ai_visibility",
            impact="high",
            effort="low",
            est_score_boost=5,
            action_url=f"{base_url}?tab=ai",
            action_label="Run AI Check",
            auto_actionable=True,
        ))

    mention_rate = latest.get("mention_rate", 0) or 0
    if mention_rate < 0.20:
        wins.append(QuickWin(
            id="ai_low_rate",
            title="Improve AI search visibility",
            description=f"You're only mentioned in {mention_rate:.0%} of AI queries. Target: 40%+.",
            pillar="ai_visibility",
            impact="high",
            effort="medium",
            est_score_boost=10,
            action_url=f"{base_url}?tab=ai",
            action_label="View AI Report",
        ))

    # Check engine breadth
    engines_json = latest.get("engines_json", "{}")
    if isinstance(engines_json, str):
        try:
            engines_data = json.loads(engines_json)
        except (json.JSONDecodeError, TypeError):
            engines_data = {}
    else:
        engines_data = engines_json or {}

    engines_with_mentions = sum(
        1 for e in engines_data.values()
        if isinstance(e, dict) and e.get("mentions", 0) > 0
    )
    if engines_with_mentions <= 1 and mention_rate > 0:
        wins.append(QuickWin(
            id="ai_single_engine",
            title="Expand AI presence to more engines",
            description="You're only appearing on 1 AI engine. Diversify with schema markup and structured content.",
            pillar="ai_visibility",
            impact="medium",
            effort="medium",
            est_score_boost=4,
            action_url=f"{base_url}?tab=ai-mentions",
            action_label="View AI Mentions",
        ))

    # Check for declining trend
    if len(runs) >= 4:
        recent_avg = sum(r.get("mention_rate", 0) or 0 for r in runs[:4]) / 4
        older_avg = sum(r.get("mention_rate", 0) or 0 for r in runs[4:8]) / max(len(runs[4:8]), 1)
        if older_avg > 0 and recent_avg < older_avg - 0.10:
            wins.append(QuickWin(
                id="ai_declining",
                title="AI visibility is declining",
                description=f"Mention rate dropped from {older_avg:.0%} to {recent_avg:.0%}. Investigate content freshness and competitor moves.",
                pillar="ai_visibility",
                impact="high",
                effort="medium",
                est_score_boost=5,
                action_url=f"{base_url}?tab=ai",
                action_label="Investigate",
            ))


# ---------------------------------------------------------------------------
# Search Health checks
# ---------------------------------------------------------------------------

def _check_search_health(
    db: CustomerDB, customer_id: str, base_url: str, wins: list[QuickWin]
) -> None:
    daily = db.get_gsc_daily(customer_id, limit=7)

    if not daily:
        # Check if GSC is connected
        try:
            integrations = db.get_integrations(customer_id)
            gsc_connected = any(
                i.get("integration") == "gsc" and i.get("status") == "active"
                for i in integrations
            )
        except Exception:
            gsc_connected = False

        if not gsc_connected:
            wins.append(QuickWin(
                id="seo_no_gsc",
                title="Connect Google Search Console",
                description="GSC is the #1 source of search performance data. Connect it to track clicks, impressions, and keywords.",
                pillar="search_growth",
                impact="high",
                effort="low",
                est_score_boost=10,
                action_url=f"{base_url}?tab=seo&sub=integrations",
                action_label="Connect GSC",
            ))
        return

    # Check for declining keywords
    kw_summary = db.get_keyword_summary(customer_id)
    if kw_summary:
        declining = []
        for kw in kw_summary:
            curr = kw.get("current_position") or kw.get("position")
            prev = kw.get("prev_position")
            if curr and prev and curr > prev + 3:
                declining.append(kw.get("keyword", ""))

        if len(declining) >= 3:
            wins.append(QuickWin(
                id="seo_declining_kw",
                title=f"Optimize {len(declining)} declining keywords",
                description=f"Keywords like '{declining[0]}' dropped 3+ positions. Update content targeting these terms.",
                pillar="search_growth",
                impact="high",
                effort="medium",
                est_score_boost=5,
                action_url=f"{base_url}?tab=seo&sub=rankings",
                action_label="View Rankings",
                details={"keywords": declining[:5]},
            ))


# ---------------------------------------------------------------------------
# Technical checks
# ---------------------------------------------------------------------------

def _check_technical(
    db: CustomerDB, customer_id: str, base_url: str, wins: list[QuickWin]
) -> None:
    audit = db.get_latest_audit(customer_id)

    if not audit:
        wins.append(QuickWin(
            id="tech_no_audit",
            title="Run a site audit",
            description="No site audit on record. Run one to identify technical SEO issues.",
            pillar="technical",
            impact="medium",
            effort="low",
            est_score_boost=3,
            action_url=f"{base_url}?tab=seo&sub=audit",
            action_label="Run Audit",
            auto_actionable=True,
        ))
        return

    # Check for critical issues
    issues = db.get_audit_issues(customer_id, status="open")
    critical = [i for i in issues if i.get("severity") == "critical"]
    if critical:
        wins.append(QuickWin(
            id="tech_critical_issues",
            title=f"Fix {len(critical)} critical site issue{'s' if len(critical) != 1 else ''}",
            description=f"Critical: {critical[0].get('title', 'Unknown issue')}. These directly hurt rankings.",
            pillar="technical",
            impact="high",
            effort="medium",
            est_score_boost=5,
            action_url=f"{base_url}?tab=seo&sub=audit",
            action_label="View Issues",
            details={"issues": [i.get("title") for i in critical[:3]]},
        ))


# ---------------------------------------------------------------------------
# Content checks
# ---------------------------------------------------------------------------

def _check_content(
    db: CustomerDB, customer_id: str, base_url: str, wins: list[QuickWin]
) -> None:
    recs = db.get_content_recommendations(customer_id, limit=100)

    if not recs:
        wins.append(QuickWin(
            id="content_no_recs",
            title="Generate content recommendations",
            description="Run the content analyzer to identify blog posts, FAQs, and pages that will boost your visibility.",
            pillar="content",
            impact="medium",
            effort="low",
            est_score_boost=3,
            action_url=f"{base_url}?tab=content",
            action_label="Generate Content",
            auto_actionable=True,
        ))
        return

    # Approved but not published
    approved = [r for r in recs if r.get("status") == "approved"]
    if approved:
        wins.append(QuickWin(
            id="content_unpublished",
            title=f"Publish {len(approved)} approved content piece{'s' if len(approved) != 1 else ''}",
            description=f"'{approved[0].get('title', 'Content')}' is approved and ready to go. Publishing boosts your content score.",
            pillar="content",
            impact="high",
            effort="low",
            est_score_boost=5,
            action_url=f"{base_url}?tab=content",
            action_label="Publish Content",
            auto_actionable=True,
            details={"count": len(approved), "titles": [r.get("title") for r in approved[:3]]},
        ))

    # Check content freshness
    published = [r for r in recs if r.get("status") == "published"]
    if published:
        dates = []
        for r in published:
            pub_date = r.get("published_at")
            if pub_date:
                try:
                    dates.append(datetime.fromisoformat(pub_date.replace("Z", "+00:00")))
                except (ValueError, TypeError):
                    pass
        if dates:
            latest = max(dates)
            days_since = (datetime.now(timezone.utc) - latest).days
            if days_since > 30:
                wins.append(QuickWin(
                    id="content_stale",
                    title="Content is getting stale",
                    description=f"No new content published in {days_since} days. Fresh content signals relevance to AI and search engines.",
                    pillar="content",
                    impact="medium",
                    effort="medium",
                    est_score_boost=4,
                    action_url=f"{base_url}?tab=content",
                    action_label="Review Content",
                ))


# ---------------------------------------------------------------------------
# Reputation checks
# ---------------------------------------------------------------------------

def _check_reputation(
    db: CustomerDB, customer_id: str, base_url: str, wins: list[QuickWin]
) -> None:
    places = db.get_google_places(customer_id)

    if not places:
        wins.append(QuickWin(
            id="rep_no_gbp",
            title="Set up Google Business Profile",
            description="A Google Business Profile is essential for local visibility and AI search recommendations.",
            pillar="reputation",
            impact="high",
            effort="medium",
            est_score_boost=8,
            action_url=f"{base_url}?tab=seo&sub=overview",
            action_label="Set Up GBP",
        ))
        return

    rating = places.get("rating") or 0
    review_count = places.get("review_count") or 0

    if rating > 0 and rating < 4.0:
        wins.append(QuickWin(
            id="rep_low_rating",
            title=f"Rating is {rating} — address negative feedback",
            description="A rating below 4.0 hurts both search rankings and AI recommendations. Focus on service quality and responding to reviews.",
            pillar="reputation",
            impact="high",
            effort="high",
            est_score_boost=5,
            action_url=f"{base_url}?tab=seo&sub=reviews",
            action_label="View Reviews",
        ))

    if review_count < 20:
        wins.append(QuickWin(
            id="rep_low_reviews",
            title=f"Build review volume ({review_count} reviews)",
            description="More reviews = stronger signal to both Google and AI engines. Request reviews from recent clients.",
            pillar="reputation",
            impact="high",
            effort="medium",
            est_score_boost=5,
            action_url=f"{base_url}?tab=seo&sub=reviews",
            action_label="Review Strategy",
        ))

    # Competitor surge detection
    competitors = db.get_competitors(customer_id)
    for comp in competitors[:5]:
        comp_reviews = comp.get("review_count", 0)
        if comp_reviews > review_count * 1.5 and comp_reviews > 20:
            wins.append(QuickWin(
                id=f"rep_competitor_surge_{comp.get('id', '')}",
                title=f"{comp.get('name', 'Competitor')} has {comp_reviews} reviews vs your {review_count}",
                description="A competitor is outpacing you on reviews. Consider a review generation campaign.",
                pillar="reputation",
                impact="medium",
                effort="medium",
                est_score_boost=3,
                action_url=f"{base_url}?tab=competitors",
                action_label="View Competitors",
            ))
            break  # only show one competitor surge
