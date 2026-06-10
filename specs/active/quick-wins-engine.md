# Quick Wins Engine — Actionable Recommendations System

## Problem

Customers want to know "what should I do next?" and our team needs to prioritize work across 10+ customers. Currently, insights are buried in raw data tables. We need a system that automatically surfaces the highest-impact, lowest-effort actions.

Industry context:
- Best agency dashboards open with executive summaries: biggest wins, concerns, next focus
- Quick wins in SEO are high-impact actions requiring minimal resources — nearly half work within a week
- Effective reports combine automated data with strategic recommendations

## Architecture

```
quick_wins.py
├── detect_quick_wins(customer_id) → List[QuickWin]
│   ├── _check_ai_visibility(customer_id)
│   ├── _check_search_health(customer_id)
│   ├── _check_technical(customer_id)
│   ├── _check_content(customer_id)
│   ├── _check_reputation(customer_id)
│   └── _check_competitive(customer_id)
├── prioritize(wins) → sorted by impact/effort matrix
└── format_for_email(wins) → markdown summary
```

## Quick Win Detection Rules

### AI Visibility Wins

| ID | Condition | Title | Impact | Effort | Est. Score Boost |
|----|-----------|-------|--------|--------|-----------------|
| `ai_no_run` | No AI check in 30+ days | "Run an AI visibility check" | High | Low | +5 |
| `ai_no_faq_schema` | FAQPage schema missing | "Add FAQ schema to service pages" | High | Low | +8 |
| `ai_no_llms_txt` | llms.txt missing or < 500 bytes | "Create/expand llms.txt file" | High | Low | +6 |
| `ai_low_rate` | Mention rate < 20% | "Optimize content for AI citations" | High | Medium | +10 |
| `ai_single_engine` | Only mentioned on 1 engine | "Diversify AI presence across engines" | Medium | Medium | +4 |
| `ai_declining` | Mention rate dropped 10%+ | "AI visibility declining — investigate" | High | Medium | +5 |
| `ai_no_person_schema` | No Person/author schema | "Add author credentials to content" | Medium | Low | +3 |

### Search Growth Wins

| ID | Condition | Title | Impact | Effort | Est. Score Boost |
|----|-----------|-------|--------|--------|-----------------|
| `seo_title_issues` | Duplicate/missing title tags | "Fix {N} title tag issues" | Medium | Low | +3 |
| `seo_declining_kw` | 3+ keywords dropped 5+ positions | "Optimize {N} declining keyword pages" | High | Medium | +5 |
| `seo_low_ctr` | Pages with pos < 10 but CTR < 2% | "Improve meta descriptions for {N} pages" | Medium | Low | +3 |
| `seo_no_gsc` | GSC not connected | "Connect Google Search Console" | High | Low | +10 |
| `seo_thin_pages` | Pages with < 300 words ranking | "Expand thin content on {N} pages" | Medium | Medium | +4 |

### Technical Wins

| ID | Condition | Title | Impact | Effort | Est. Score Boost |
|----|-----------|-------|--------|--------|-----------------|
| `tech_critical_issues` | Open critical audit issues | "Fix {N} critical site issues" | High | Varies | +5 |
| `tech_no_https` | HTTP not redirecting to HTTPS | "Enable HTTPS redirect" | High | Low | +5 |
| `tech_slow_lcp` | LCP > 2.5s | "Improve page load speed" | Medium | Medium | +3 |
| `tech_no_sitemap` | Sitemap missing/empty | "Create XML sitemap" | Medium | Low | +3 |
| `tech_no_audit` | No audit run in 30+ days | "Run a site audit" | Medium | Low | +2 |

### Content Wins

| ID | Condition | Title | Impact | Effort | Est. Score Boost |
|----|-----------|-------|--------|--------|-----------------|
| `content_unpublished` | Approved recs not published | "Publish {N} approved content pieces" | High | Low | +5 |
| `content_stale` | No publish in 30+ days | "Content is getting stale — refresh or publish" | Medium | Medium | +4 |
| `content_no_recs` | No content recommendations generated | "Generate content recommendations" | Medium | Low | +3 |
| `content_low_quality` | Avg page score < 50 | "Improve content quality on key pages" | Medium | High | +4 |

### Reputation Wins

| ID | Condition | Title | Impact | Effort | Est. Score Boost |
|----|-----------|-------|--------|--------|-----------------|
| `rep_low_reviews` | < 20 Google reviews | "Build review volume — request from recent clients" | High | Medium | +5 |
| `rep_no_responses` | Reviews without owner responses | "Respond to {N} unanswered reviews" | Medium | Low | +2 |
| `rep_competitor_surge` | Competitor gained 10+ reviews | "{Competitor} surging — respond with review push" | Medium | Medium | +3 |
| `rep_low_rating` | Rating < 4.0 | "Rating below 4.0 — address negative feedback" | High | High | +5 |
| `rep_no_gbp` | No Google Places data | "Set up Google Business Profile" | High | Medium | +8 |

## Quick Win Data Model

```python
@dataclass
class QuickWin:
    id: str                    # unique identifier (e.g., "ai_no_faq_schema")
    title: str                 # human-readable title
    description: str           # 1-2 sentence explanation
    pillar: str                # ai_visibility, search_growth, technical, content, reputation
    impact: str                # high, medium, low
    effort: str                # low, medium, high
    est_score_boost: int       # estimated points added to overall score
    action_url: str            # relative URL to take action
    action_label: str          # button text ("View Audit", "Publish", "Run Check")
    auto_actionable: bool      # can the system do this automatically?
    details: dict              # context-specific data (e.g., {"count": 3, "pages": [...]})
```

## Priority Matrix

```
                    LOW EFFORT    MEDIUM EFFORT    HIGH EFFORT
HIGH IMPACT    │  ★★★ Do First │  ★★ Do Next   │  ★ Plan     │
MEDIUM IMPACT  │  ★★ Do Next   │  ★ Consider   │  ○ Backlog  │
LOW IMPACT     │  ★ Consider   │  ○ Backlog    │  ○ Skip     │
```

Sort order:
1. impact_rank (high=3, medium=2, low=1) * inverse_effort_rank (low=3, medium=2, high=1)
2. Higher product = higher priority
3. Tie-break: est_score_boost descending

## Display Rules

- Show max **5 quick wins** on customer overview
- Show max **3 quick wins** in weekly email reports
- Aggregate across all customers on Analytics page (grouped by type, count affected)
- Don't show the same quick win if customer dismissed it (add `dismissed_wins` JSON field or table)
- Re-surface dismissed wins if condition worsens (e.g., dismissed "low reviews" but reviews dropped further)

## Customer-Facing Report Format

For weekly emails:

```markdown
**Your Top Actions This Week:**

1. **Publish 2 approved blog posts** — Your content score is dropping.
   These are already written and approved. Est. +5 to your PracticeRank Score.

2. **Respond to 3 unanswered Google reviews** — Shows engagement to both
   customers and AI engines. Takes ~15 minutes.

3. **Run an AI visibility check** — It's been 35 days since your last scan.
   Let's see if recent optimizations are working.
```

Short, specific, actionable. Each has a clear time estimate and expected impact.

## Files to Create/Modify

| File | Action |
|------|--------|
| `geo_agent/quick_wins.py` | **NEW** — Quick win detection engine |
| `dashboard/app.py` | Add `/api/quick-wins/<cid>` endpoint, inject into overview |
| `dashboard/templates/customer_detail.html` | Quick wins panel on overview tab |
| `dashboard/templates/analytics.html` | Aggregate quick wins section |
| `templates/emails/07-weekly-seo-update.md` | Add quick wins to weekly report |

## Testing

Test with each customer to verify:
1. Customer with no data → shows "Connect GSC", "Set up GBP", "Run AI check"
2. Customer with all data healthy → shows 0-1 low-priority wins
3. Customer with declining metrics → shows high-priority wins related to the decline
4. Verify sort order matches priority matrix
5. Verify dismissed wins don't re-appear (unless condition worsens)
