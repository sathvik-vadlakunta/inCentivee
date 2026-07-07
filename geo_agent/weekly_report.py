"""Weekly customer progress report (R0).

Assembles the weekly report payload from data we already collect, renders a
branded HTML report (PracticeRank look-and-feel), and persists a snapshot.

Spec:  specs/platform/weekly-customer-report.html
Reqs:  docs/requirements.md → Reporting & Data-Completeness Requirements (R0-R4)

Every section degrades gracefully: if its data source isn't connected for a
customer, the section is omitted rather than rendered empty/zero.

Usage:
    from geo_agent.db import CustomerDB
    from geo_agent import weekly_report
    with CustomerDB() as db:
        weekly_report.generate_all(db)            # all active customers
        weekly_report.generate_and_store(db, id)  # one customer
"""

from __future__ import annotations

import html
import json
import logging
from datetime import datetime, timedelta, timezone

from geo_agent.db import CustomerDB
from geo_agent.practicerank_score import compute_practicerank_score, grade_from_score

logger = logging.getLogger(__name__)

# Customers in these onboarding steps receive weekly reports.
ACTIVE_STEPS = ("live", "content", "monitoring")

# Brand tokens — mirrors practicerank.ai (deploy/index.html light theme + dark hero).
BRAND = {
    "ink": "#1a1a2e", "bg": "#f8faf9", "card": "#ffffff",
    "line": "rgba(26,26,46,0.1)", "muted": "rgba(26,26,46,0.55)",
    "hero": "#08080d", "accent": "#16a34a", "accent2": "#4ade80",
    "good": "#16a34a", "warn": "#d97706", "bad": "#dc2626",
}


# ---------------------------------------------------------------------------
# Small formatting helpers
# ---------------------------------------------------------------------------

def _pct_delta(cur: float, prev: float) -> tuple[str, str]:
    """Return (label, direction) for a percentage change. direction in up/down/flat."""
    if prev in (None, 0):
        return ("—", "flat")
    change = (cur - prev) / prev * 100
    if abs(change) < 0.5:
        return ("flat", "flat")
    sign = "+" if change > 0 else ""
    return (f"{sign}{change:.0f}%", "up" if change > 0 else "down")


def _abs_delta(cur: float, prev: float, fmt: str = "{:+.0f}") -> tuple[str, str]:
    if prev is None:
        return ("—", "flat")
    diff = cur - prev
    if abs(diff) < 1e-9:
        return ("no change", "flat")
    return (fmt.format(diff), "up" if diff > 0 else "down")


def _pos_delta(cur: float, prev: float) -> tuple[str, str]:
    """Position: lower is better, so an improvement is a *decrease*."""
    if prev is None or cur is None:
        return ("—", "flat")
    diff = prev - cur
    if abs(diff) < 0.1:
        return ("no change", "flat")
    return (f"from {prev:.1f}", "up" if diff > 0 else "down")


def _arrow(direction: str) -> str:
    return {"up": "▲", "down": "▼"}.get(direction, "–")


# ---------------------------------------------------------------------------
# Data assembly
# ---------------------------------------------------------------------------

def build_report_data(db: CustomerDB, customer_id: str, period_end: str | None = None,
                      period_days: int = 7, live_state: bool = True) -> dict:
    """Gather every available field for the report. Missing data → None/empty.

    period_days sets the comparison window: 7 = weekly, 30 = monthly, 90 = quarterly,
    180 = half-year. The current window is compared against the immediately-prior window
    of the same length, so the report shows progress over the chosen period vs the last.
    """
    customer = db.get_customer(customer_id)
    if not customer:
        raise ValueError(f"Unknown customer: {customer_id}")
    changes_live_at = customer.get("changes_live_at")

    pd = max(1, int(period_days))
    end = datetime.strptime(period_end, "%Y-%m-%d") if period_end \
        else datetime.now(timezone.utc).replace(tzinfo=None)
    cur_start = end - timedelta(days=pd - 1)
    prev_end = cur_start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=pd - 1)
    ds = lambda d: d.strftime("%Y-%m-%d")  # noqa: E731
    period_human = {7: "last 7 days", 30: "last 30 days", 90: "last 90 days",
                    180: "last 6 months", 365: "last year"}.get(pd, f"last {pd} days")
    cadence = {7: "Weekly", 30: "Monthly", 90: "Quarterly", 180: "Half-Year",
               365: "Annual"}.get(pd, f"{pd}-Day")

    data: dict = {
        "customer": customer,
        "practice_name": customer.get("name", "Your Practice"),
        "contact_name": (db.get_contacts(customer_id) or [{}])[0].get("name", "there")
        if hasattr(db, "get_contacts") else "there",
        "period_days": pd,
        "period_human": period_human,
        "cadence": cadence,
        "period_start": ds(cur_start),
        "period_end": ds(end),
        "period_label": f"{cur_start.strftime('%b %-d')}–{end.strftime('%-d, %Y')}",
        "sections": {},
    }

    # --- Score (REAL) ---
    score = compute_practicerank_score(db, customer_id)
    prev_rows = db.get_practicerank_scores(customer_id, limit=8)
    prev_overall = next((r["overall_score"] for r in prev_rows if r.get("date") < ds(end)), None)
    data["score"] = score
    data["score_prev"] = prev_overall

    # --- Search performance (REAL) — totals over the chosen window vs the prior window ---
    daily = db.get_gsc_daily(customer_id, limit=pd * 2 + 10)
    def _sum_window(start_d: str, end_d: str):
        rows = [r for r in (daily or []) if start_d <= (r.get("date") or "")[:10] <= end_d]
        if not rows:
            return None
        clicks = sum(int(r.get("clicks", 0) or 0) for r in rows)
        impr = sum(int(r.get("impressions", 0) or 0) for r in rows)
        pos = [r.get("position") for r in rows if r.get("position")]
        return {"clicks": clicks, "impressions": impr,
                "ctr": (clicks / impr) if impr else 0.0,
                "position": (sum(pos) / len(pos)) if pos else 0.0}
    cur_search = _sum_window(ds(cur_start), ds(end))
    if cur_search:
        data["sections"]["search"] = {"cur": cur_search, "prev": _sum_window(ds(prev_start), ds(prev_end))}

    # --- Keywords (R1; renders only once gsc_query_daily has data) ---
    top = db.get_top_queries(customer_id, ds(cur_start), ds(end), limit=8)
    if top:
        data["sections"]["keywords"] = {
            "top": top,
            "movers": db.get_query_movers(customer_id, ds(cur_start), ds(end),
                                          ds(prev_start), ds(prev_end)),
        }

    # --- AI visibility (REAL — our differentiator) ---
    rolling = db.get_rolling_mention_stats(customer_id)
    llms = db.get_latest_kpi(customer_id, "llms_txt_hits")
    llms_hist = db.get_kpis(customer_id, "llms_txt_hits", limit=2)
    ai_runs = db.get_ai_mention_runs(customer_id, limit=1)
    latest_ai = ai_runs[0] if ai_runs else None
    engines = {}
    if latest_ai and latest_ai.get("engines_json"):
        try:
            engines = json.loads(latest_ai["engines_json"])
        except Exception:
            engines = {}
    try:
        sov = db.get_share_of_voice(customer_id)
    except Exception:
        sov = None
    try:
        from geo_agent import share_of_voice as _sovmod
        sov_flag = _sovmod.sov_summary(db, customer_id)  # flagship score + trend
    except Exception:
        sov_flag = None
    if rolling or llms or latest_ai:
        data["sections"]["ai"] = {
            "rolling": rolling,
            "llms": llms,
            "llms_prev": llms_hist[1]["value"] if len(llms_hist) > 1 else None,
            "latest": latest_ai,
            "engines": engines,
            "sov": sov,
            "sov_flag": sov_flag,
        }

    # --- Leads / conversions (R3; renders only when GA4 conversions configured) ---
    conv = db.get_conversions(customer_id, ds(cur_start), ds(end), channel="organic")
    if conv:
        prev_conv = db.get_conversions(customer_id, ds(prev_start), ds(prev_end), channel="organic")
        data["sections"]["leads"] = {"cur": conv, "prev": prev_conv}

    # --- Patient outcomes (the headline clients renew for) ---
    from geo_agent import outcomes as _oc
    _out = _oc.patient_outcomes(db, customer_id, ds(cur_start), ds(end),
                                ds(prev_start), ds(prev_end))
    if _out:
        data["sections"]["outcomes"] = _out

    # --- Reviews & reputation (REAL) ---
    places = db.get_google_places(customer_id)
    if places:
        own_reviews = int(places.get("review_count", 0))
        # new reviews in window
        new_reviews = [r for r in db.get_reviews(customer_id, limit=100)
                       if (r.get("review_date") or "")[:10] >= ds(cur_start)]
        gap = db.get_competitor_review_gap(customer_id, own_reviews)
        # Suppress an absurd/mismatched competitor (wrong-industry seed data) —
        # don't show "−1970 vs an orthodontist" on a metals buyer's report.
        if gap and gap.get("competitor_reviews", 0) > max(50, own_reviews * 5):
            gap = None
        data["sections"]["reviews"] = {
            "places": places,
            "new_count": len(new_reviews),
            "new_five_star": sum(1 for r in new_reviews if r.get("rating") == 5),
            "gap": gap,
            "velocity": db.review_velocity(customer_id),
        }

    # --- Local listings / NAP (R4; renders only when citations audited) ---
    citations = db.get_citations(customer_id)
    if citations:
        tracked = [c for c in citations if c.get("listed")]
        consistent = sum(1 for c in tracked if c.get("nap_match"))
        issues = [c for c in tracked if not c.get("nap_match")]
        denom = len(tracked) or 1
        from geo_agent.directory_profiles import profile_target_count
        target = profile_target_count(customer.get("business_type"))
        data["sections"]["listings"] = {
            "score": round(consistent / denom * 100),
            "consistent": consistent, "total": len(tracked),
            "target": target,  # per-vertical directory profile size (breadth denominator)
            "issues": issues[:5],
        }

    # --- Wins (REAL) ---
    published = [r for r in db.get_content_recommendations(customer_id, status="published", limit=50)
                 if (r.get("published_at") or "")[:10] >= ds(cur_start)]
    # --- Domain Authority + competitor gap (Moz; renders only when tracked) ---
    da_latest = db.get_latest_kpi(customer_id, "domain_authority")
    if da_latest:
        da_hist = list(reversed(db.get_kpis(customer_id, "domain_authority", limit=60)))
        comp_das = sorted(
            (c.get("domain_authority") or 0 for c in (db.get_competitor_domains(customer_id) or [])),
            reverse=True)

        def _da_at_or_before(target_date: str):
            """Latest DA value recorded on/before target_date (None if none old enough)."""
            prior = [h for h in da_hist if (h.get("date") or "")[:10] <= target_date]
            return prior[-1]["value"] if prior else None

        # Last ~10 DA readings as a labelled series for the over-time chart.
        da_series = [{"label": (h.get("date") or "")[5:10].replace("-", "/"), "value": h["value"]}
                     for h in da_hist[-10:]]
        # Named competitor DAs for the comparison bars (real competitors only).
        competitors = sorted(
            [{"name": (c.get("competitor_name") or c.get("competitor_domain") or "Competitor"),
              "da": c.get("domain_authority") or 0}
             for c in (db.get_competitor_domains(customer_id) or [])
             if (c.get("domain_authority") or 0) > 0],
            key=lambda x: x["da"], reverse=True)[:4]

        data["sections"]["authority"] = {
            "da": da_latest["value"],
            "first": da_hist[0]["value"] if da_hist else da_latest["value"],
            "week_prev": _da_at_or_before(ds(end - timedelta(days=7))),
            "month_prev": _da_at_or_before(ds(end - timedelta(days=28))),
            "top_competitor": comp_das[0] if comp_das and comp_das[0] > 0 else None,
            "series": da_series if len(da_series) > 1 else [],
            "competitors": competitors,
        }


    # --- Visitors / clicks over time (last 8 weeks) for the trend chart ---
    try:
        wk = db.get_gsc_weekly_summary(customer_id, weeks=8)
        if wk and len(wk) > 1:
            data["sections"]["traffic_series"] = [
                {"label": (w.get("week_start") or "")[5:10].replace("-", "/"),
                 "clicks": int(w.get("clicks") or 0)}
                for w in reversed(wk)
            ]
    except Exception:
        pass

    # --- Authority work this period (FATJOE off-site, last 30 days) ---
    try:
        since30 = ds(end - timedelta(days=30))
        osum = db.offsite_summary(customer_id, since=since30)
        # In-progress orders = ordered/in_progress/redo (placed, not yet live). Shows
        # the client the work that's underway, so a light-delivery month still reads
        # as active. Grouped into friendly line items, never cost.
        wip_items = []
        try:
            wip_states = {"ordered", "in_progress", "redo_requested"}
            links_wip = cites_wip = mentions_wip = 0
            link_tiers = set()
            for o in (db.get_offsite_orders(customer_id) or []):
                if (o.get("status") or "") not in wip_states:
                    continue
                typ = o.get("order_type") or "link"
                qty = int(o.get("quantity") or 1)
                if typ == "link":
                    links_wip += qty
                    if o.get("dr_tier"):
                        link_tiers.add(int(o["dr_tier"]))
                elif typ == "citation":
                    cites_wip += 1  # a package (yields many directory listings)
                elif typ == "mention":
                    mentions_wip += qty
            if links_wip:
                tier = f" (DR{min(link_tiers)}+)" if link_tiers else ""
                wip_items.append(f"{links_wip} backlink{'s' if links_wip != 1 else ''}{tier} being built")
            if cites_wip:
                wip_items.append(f"{cites_wip} local citation package{'s' if cites_wip != 1 else ''} in progress")
            if mentions_wip:
                wip_items.append(f"{mentions_wip} brand mention{'s' if mentions_wip != 1 else ''} in progress")
        except Exception:
            wip_items = []
        if osum["links"] or osum["citations"] or osum["mentions"] or wip_items:
            assets = [a for a in db.get_offsite_assets(customer_id)
                      if (a.get("live_at") or "")[:10] >= since30]
            link_da = [a for a in assets if a["asset_type"] == "link" and a.get("da") is not None]
            top_link = max(link_da, key=lambda a: a["da"]) if link_da else None
            mention = next((a for a in assets if a["asset_type"] == "mention"), None)
            data["sections"]["offsite"] = {
                "links": osum["links"],
                "avg_link_da": osum["avg_link_da"],
                "citations": osum["citations"],
                "mentions": osum["mentions"],
                "new_ref_domains": osum["ref_domains"],
                "total_ref_domains": db.offsite_summary(customer_id)["ref_domains"],
                "top_link": {"domain": top_link["domain"], "da": top_link["da"]} if top_link else None,
                "mention_domain": mention["domain"] if mention else None,
                "wip_items": wip_items,
            }
    except Exception:
        pass

    # Intent mix of what we shipped — proof we target money queries, not just traffic.
    intent_mix = None
    tiers = [(r.get("intent_tier") or "") for r in published]
    tiers = [t for t in tiers if t]
    if tiers:
        buyer = sum(1 for t in tiers if t in ("transactional", "commercial"))
        intent_mix = {"buyer": buyer, "research": len(tiers) - buyer, "total": len(tiers),
                      "buyer_pct": round(buyer / len(tiers) * 100)}
    data["sections"]["wins"] = {"published": published, "intent_mix": intent_mix}

    # --- Sources now citing you (from grounded AI answers) ---
    try:
        srcs = db.get_citation_domains(customer_id, last_n_runs=4)
        if srcs:
            data["sections"]["sources"] = srcs[:12]
    except Exception:
        pass

    # --- What we shipped (all-time summary, not just this week) ---
    try:
        events = db.get_published_content_events(customer_id, limit=200)
        if events:
            data["sections"]["shipped"] = _summarize_published(events)
    except Exception:
        pass

    # --- High-value buyer-intent keywords to focus on (intent engine) ---
    try:
        from geo_agent import keyword_intent as _ki
        focus = []
        for kw in (db.get_keyword_summary(customer_id) or []):
            text = (kw.get("keyword") or "").strip()
            if not text or not _ki.is_action(text):
                continue  # only action/purchase-decision keywords, not research
            meta = _ki.intent_meta(text)
            focus.append({
                "keyword": text, "label": meta["label"], "color": meta["color"], "bg": meta["bg"],
                "local": _ki.has_local_intent(text),
                "position": round(kw["current_position"], 1) if kw.get("current_position") else None,
                "impressions": int(kw.get("current_impressions", 0) or 0),
                "_p": _ki.target_priority(text),
            })
        focus.sort(key=lambda x: (x["_p"], x["impressions"]), reverse=True)
        if live_state and focus:  # current-state section — omit when re-creating point-in-time history
            data["sections"]["focus_keywords"] = focus[:8]
    except Exception:
        pass

    # --- What we need from you (customer action items / best-practice to-dos) ---
    try:
        needs = []
        cl = db.get_checklist(customer_id)
        if not cl.get("seo_gbp_photos"):
            needs.append({"icon": "📸", "title": "Send us 10+ photos for your Google Business Profile",
                          "why": "Profiles with fresh, real photos get far more views, calls, and direction requests."})
        if not cl.get("seo_gbp_qa"):
            needs.append({"icon": "❓", "title": "Approve this month's Google Business Q&A",
                          "why": "Pre-answered questions help you surface for more 'near me' searches."})
        # Precise: reviews in this period that don't yet have an owner reply.
        unanswered = db.count_unanswered_reviews(customer_id, since=ds(cur_start)) if places else 0
        if unanswered:
            needs.append({"icon": "💬", "title": f"Reply to {unanswered} Google review(s) without a response yet",
                          "why": "Replying to reviews builds trust and is a Google local-ranking signal."})
        elif places:
            needs.append({"icon": "💬", "title": "Reply to your recent Google reviews",
                          "why": "Responding to every review builds trust and helps your local ranking."})
        # Content waiting on approval (ties to the content queue).
        pending_recs = db.get_content_recommendations(customer_id, status="pending", limit=50)
        if pending_recs:
            needs.append({"icon": "📝", "title": f"Approve {len(pending_recs)} piece(s) of content we've prepared for you",
                          "why": "Approving the content we've drafted lets us publish it and grow your visibility."})
        for p in (db.get_pending_access(customer_id) or []):
            label = p.get("platform") or p.get("access_type") or "platform access"
            needs.append({"icon": "🔑", "title": f"Grant access: {label}",
                          "why": "We need this connected to keep optimizing your campaign."})
        if live_state and needs:  # "what we need from you" is current-state — omit on historical rebuilds
            data["sections"]["needs"] = needs[:6]
    except Exception:
        pass

    # --- Alerts (REAL) → inform "what's next" ---
    data["alerts"] = db.get_alerts(customer_id, active_only=True, limit=10)

    data["progress"] = _progress_since_start(db, customer_id)
    data["changes_live_at"] = changes_live_at
    data["exec_summary"] = _exec_summary(data)
    return data


_REC_TYPE_LABELS = {
    "new_page": "Location & service pages", "blog_post": "Blog posts",
    "faq_update": "FAQ enhancements", "freshness_update": "Content refreshes",
    "expert_quote": "Expert quotes added", "stat_injection": "Statistics added",
}


def _summarize_published(events: list[dict]) -> dict:
    """Roll published content into total + counts by type + recent highlights."""
    from collections import Counter
    counts = Counter((e.get("rec_type") or "other") for e in events)
    groups = [{"label": _REC_TYPE_LABELS.get(t, t.replace("_", " ").title()), "count": c}
              for t, c in counts.most_common()]
    return {"total": len(events), "groups": groups,
            "recent": [e.get("title", "") for e in events[:5] if e.get("title")]}


def _exec_summary(data: dict) -> str:
    """Rule-based headline from the biggest positive movement. (Claude hook: future.)"""
    name = data["practice_name"]
    bits = []
    s = data["sections"]
    # Lead with the outcome that matters most — new patients + production.
    if "outcomes" in s and s["outcomes"].get("inquiries"):
        o = s["outcomes"]
        if o.get("estimated_value"):
            bits.append(f"you drew {o['inquiries']} new patient inquiries "
                        f"(~${o['estimated_value']:,} in potential production)")
        else:
            bits.append(f"you drew {o['inquiries']} new patient inquiries")
    # Lead with AI rank when strong — it's our differentiator.
    if "ai" in s and s["ai"].get("sov"):
        sov = s["ai"]["sov"]
        rank = sov.get("customer_rank")
        if rank == 1:
            bits.append("you're ranked #1 in AI search vs your competitors")
        elif rank and rank <= 3:
            bits.append(f"you're a top-{rank} result in AI search")
    if "ai" in s and (s["ai"].get("latest") or {}).get("total_queries"):
        lr = s["ai"]["latest"]
        bits.append(f"AI engines mention you {round(lr['mention_rate']*100)}% of the time")
    if "search" in s and s["search"].get("prev"):
        label, direction = _pct_delta(s["search"]["cur"]["clicks"], s["search"]["prev"]["clicks"])
        if direction == "up":
            bits.append(f"organic clicks rose {label}")
    score = data["score"].get("score")
    if score is not None and data.get("score_prev") is not None:
        d = score - data["score_prev"]
        if d > 0:
            bits.append(f"your PracticeRank Score climbed to {score} (+{d})")
        elif d == 0:
            bits.append(f"your PracticeRank Score held at {score}")
    if "reviews" in s and s["reviews"]["new_count"]:
        bits.append(f"{s['reviews']['new_count']} new review(s) came in")
    if not bits:
        return f"Here's this week's progress for {name}."
    return f"Strong week for {name} — " + ", ".join(bits) + "."


# ---------------------------------------------------------------------------
# Rendering (branded HTML)
# ---------------------------------------------------------------------------

def _delta_span(label: str, direction: str) -> str:
    cls = {"up": "up", "down": "down"}.get(direction, "flat")
    return f'<div class="delta {cls}">{_arrow(direction)} {html.escape(label)}</div>'


def _kpi(k: str, v: str, delta_html: str = "") -> str:
    return (f'<div class="kpi"><div class="k">{html.escape(k)}</div>'
            f'<div class="v">{html.escape(v)}</div>{delta_html}</div>')


def _vbars(points: list[dict], value_key: str, *, color: str = "#16a34a", height: int = 48) -> str:
    """Email-safe vertical bar chart (table-based) from [{label, <value_key>}]."""
    if not points:
        return ""
    vals = [max(p.get(value_key) or 0, 0) for p in points]
    mx = max(vals) or 1
    cells = ""
    for p in points:
        v = max(p.get(value_key) or 0, 0)
        bh = max(int(round(v / mx * height)), 2)
        cells += (
            f'<td style="vertical-align:bottom;text-align:center;padding:0 3px;">'
            f'<div style="font-size:9px;color:#64748b;margin-bottom:2px;">{int(v)}</div>'
            f'<div style="width:16px;height:{bh}px;background:{color};border-radius:3px 3px 0 0;margin:0 auto;"></div>'
            f'<div style="font-size:8.5px;color:#9aa6b2;margin-top:3px;">{html.escape(str(p.get("label","")))}</div>'
            f'</td>')
    return f'<table style="border-collapse:collapse;margin-top:6px;"><tr>{cells}</tr></table>'


def _hbars(rows: list[tuple], *, you_color: str = "#16a34a", other: str = "#cbd5e1") -> str:
    """Email-safe horizontal comparison bars. rows = [(name, value, is_you)]."""
    rows = [r for r in rows if r[1] is not None]
    if not rows:
        return ""
    mx = max((r[1] for r in rows), default=1) or 1
    out = '<table style="border-collapse:collapse;width:100%;margin-top:6px;font-size:12px;">'
    for name, val, is_you in rows:
        w = int(round(val / mx * 100))
        col = you_color if is_you else other
        nm = f"<b>{html.escape(str(name))}</b>" if is_you else html.escape(str(name))
        out += (
            f'<tr><td style="width:42%;padding:3px 8px 3px 0;white-space:nowrap;overflow:hidden;'
            f'text-overflow:ellipsis;max-width:0;">{nm}</td>'
            f'<td style="padding:3px 0;"><div style="background:{col};height:13px;width:{w}%;'
            f'border-radius:3px;display:inline-block;vertical-align:middle;"></div>'
            f'<span style="font-weight:700;margin-left:6px;">{int(val)}</span></td></tr>')
    return out + "</table>"


# ---------------------------------------------------------------------------
# Progress since inception (full-history trends, not just one window back)
# ---------------------------------------------------------------------------

# (kpi metric, label, format kind, higher_is_better)
_PROGRESS_METRICS = [
    ("domain_authority", "Domain authority", "int", True),
    ("ai_mentions", "AI mentions", "int", True),
    ("organic_clicks", "Organic clicks / mo", "int", True),
    ("organic_impressions", "Organic impressions / mo", "int", True),
    ("avg_search_position", "Avg search position", "pos", False),
    ("rating", "Google rating", "rating", True),
    ("review_count", "Total reviews", "int", True),
]


def _fmt_metric(kind: str, v) -> str:
    if v is None:
        return "—"
    if kind == "rating":
        return f"{v:.1f}"
    if kind == "pos":
        return f"{v:.1f}"
    return f"{int(round(v)):,}"


def _short_num(v) -> str:
    v = float(v)
    if abs(v) >= 1000:
        return f"{v/1000:.1f}k".replace(".0k", "k")
    return str(int(v)) if v == int(v) else f"{v:.1f}"


def _progress_since_start(db, customer_id: str) -> dict | None:
    """Full-history trend for every tracked metric since the customer started —
    each metric's first value → latest value + the whole series (for sparklines),
    plus score & traffic series for the headline charts."""
    metrics: list[dict] = []
    all_start_dates: list[str] = []

    def _add(label, kind, higher, series):
        # series: list of (date, value) ascending; need >=2 real points
        series = [(d, v) for d, v in series if v is not None]
        if len(series) < 2:
            return
        start_v, cur_v = series[0][1], series[-1][1]
        metrics.append({
            "label": label, "kind": kind, "higher_better": higher,
            "start": start_v, "current": cur_v, "delta": round(cur_v - start_v, 2),
            "series": [v for _, v in series], "start_date": series[0][0],
            "start_str": _fmt_metric(kind, start_v), "cur_str": _fmt_metric(kind, cur_v),
        })
        all_start_dates.append(series[0][0])

    score_rows = list(reversed(db.get_practicerank_scores(customer_id, limit=60)))
    score_series = [(r["date"], r.get("overall_score")) for r in score_rows]
    _add("PracticeRank score", "int", True, score_series)

    for metric, label, kind, higher in _PROGRESS_METRICS:
        rows = list(reversed(db.get_kpis(customer_id, metric, limit=60)))
        _add(label, kind, higher, [(r["date"], r.get("value")) for r in rows])

    if not metrics:
        return None
    traffic_rows = list(reversed(db.get_kpis(customer_id, "organic_clicks", limit=60)))
    return {
        "start_date": min(all_start_dates) if all_start_dates else None,
        "metrics": metrics,
        "score_chart": [(d, v) for d, v in score_series if v is not None],
        "traffic_chart": [(r["date"], r.get("value")) for r in traffic_rows if r.get("value") is not None],
    }


def _sparkline_svg(values: list[float], *, w: int = 96, h: int = 26, color: str = "#16a34a") -> str:
    if not values or len(values) < 2:
        return ""
    lo, hi = min(values), max(values)
    rng = (hi - lo) or 1
    n = len(values)
    pts = []
    for i, v in enumerate(values):
        x = round(i / (n - 1) * (w - 4) + 2, 1)
        y = round(h - 3 - (v - lo) / rng * (h - 6), 1)
        pts.append(f"{x},{y}")
    lx, ly = pts[-1].split(",")
    return (f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
            f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" '
            f'stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round"/>'
            f'<circle cx="{lx}" cy="{ly}" r="2.2" fill="{color}"/></svg>')


def _trend_chart_svg(points: list[tuple], *, title: str, color: str = "#16a34a",
                     w: int = 640, h: int = 180) -> str:
    pts = [(d, v) for d, v in points if v is not None]
    if len(pts) < 2:
        return ""
    vals = [v for _, v in pts]
    lo, hi = min(vals), max(vals)
    if lo == hi:
        lo, hi = lo - 1, hi + 1
    rng = hi - lo
    n = len(pts)
    padL, padR, padT, padB = 42, 10, 14, 24
    pw, ph = w - padL - padR, h - padT - padB

    def X(i):
        return round(padL + i / (n - 1) * pw, 1)

    def Y(v):
        return round(padT + (1 - (v - lo) / rng) * ph, 1)

    line = " ".join(f"{X(i)},{Y(v)}" for i, (_, v) in enumerate(pts))
    area = f"{X(0)},{Y(lo)} {line} {X(n-1)},{Y(lo)}"
    grid = ""
    for gv in (lo, (lo + hi) / 2, hi):
        gy = Y(gv)
        grid += (f'<line x1="{padL}" y1="{gy}" x2="{w-padR}" y2="{gy}" stroke="#eef1f4" stroke-width="1"/>'
                 f'<text x="{padL-6}" y="{gy+3}" text-anchor="end" font-size="10" fill="#9aa6b2">{_short_num(gv)}</text>')
    xl = (f'<text x="{padL}" y="{h-5}" font-size="10" fill="#9aa6b2">{html.escape(pts[0][0][:7])}</text>'
          f'<text x="{w-padR}" y="{h-5}" text-anchor="end" font-size="10" fill="#9aa6b2">{html.escape(pts[-1][0][:7])}</text>')
    lx, ly = X(n - 1), Y(pts[-1][1])
    return (f'<div class="trend"><div class="trend-t">{html.escape(title)}</div>'
            f'<svg viewBox="0 0 {w} {h}" role="img">{grid}'
            f'<polygon points="{area}" fill="{color}" opacity="0.09"/>'
            f'<polyline points="{line}" fill="none" stroke="{color}" stroke-width="2.2" stroke-linejoin="round"/>'
            f'<circle cx="{lx}" cy="{ly}" r="3.2" fill="{color}"/>{xl}</svg></div>')


def _maturation_note(data: dict) -> str:
    """Set expectations: SEO/AEO changes take time to surface, so short windows
    under-report real progress. Anchored on when the on-site optimizations went
    LIVE (data['changes_live_at']), not on customer signup — effects only start
    once the changes ship. Falls back to neutral copy when no go-live date is set."""
    live = (data.get("changes_live_at") or "").strip()
    weeks = None
    if live:
        try:
            when = datetime.strptime(live[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            weeks = max(0, (datetime.now(timezone.utc) - when).days // 7)
        except ValueError:
            weeks = None
    if weeks is None:
        # No go-live date recorded — don't assert a timeline; keep it general.
        return ("SEO and AEO compound over time — AI-search (AEO) changes typically take "
                "6+ weeks to surface in results after they go live, and traditional SEO/ranking "
                "gains build over 3–6 months. Recent work is always maturing behind these numbers.")
    if weeks < 1:
        return ("Your on-site optimizations just went live. AI engines typically take 6+ weeks "
                "to reflect changes, and SEO/ranking gains build over 3–6 months — so almost all "
                "of the impact is still ahead. This report sets the baseline to measure against.")
    if weeks < 6:
        return (f"Your on-site optimizations went live about {weeks} week{'s' if weeks != 1 else ''} "
                f"ago — so most of the impact is still ahead of us. AI engines typically take 6+ weeks "
                f"to reflect changes, and SEO/ranking gains build over 3–6 months. Early signals come "
                f"first; the larger movement follows.")
    if weeks < 16:
        return (f"Your optimizations went live about {weeks} weeks ago — AEO effects are starting to "
                f"compound (they usually take 6+ weeks to appear), while SEO/ranking gains keep building "
                f"for 3–6 months. So the numbers here are still catching up to the work behind them.")
    months = weeks // 4
    return (f"Your optimizations have been live about {months} months — past the initial ramp, so "
            f"changes should be materializing steadily. Any newer work still takes ~6+ weeks (AEO) to "
            f"surface and months for SEO, so the most recent changes always trail the numbers.")


def render_html(data: dict) -> str:
    b = BRAND
    s = data["sections"]
    e = html.escape
    parts: list[str] = []

    # Header
    parts.append(f"""<div class="r-head">
      <div class="brand">PracticeRank · {e(data.get('cadence', 'Weekly'))} Report</div>
      <h2>{e(data['practice_name'])}</h2>
      <div class="sub">Week of {e(data['period_label'])} · prepared for {e(data['contact_name'])}</div>
    </div>
    <div class="r-body">""")

    # 1. Exec summary
    parts.append(f"""<div class="r-sec"><h3>The headline</h3>
      <div class="summary"><p>📈 {e(data['exec_summary'])}</p></div></div>""")

    # 1b. Progress since you started — full-history trends (hybrid: strip + charts)
    prog = data.get("progress")
    if prog and prog.get("metrics"):
        rows_html = ""
        for m in prog["metrics"]:
            improved = (m["delta"] > 0) if m["higher_better"] else (m["delta"] < 0)
            worse = (m["delta"] < 0) if m["higher_better"] else (m["delta"] > 0)
            cls = "up" if improved else ("down" if worse else "flat")
            col = b["good"] if improved else (b["bad"] if worse else b["muted"])
            sign = "+" if m["delta"] > 0 else ("−" if m["delta"] < 0 else "±")
            gain = _fmt_metric(m["kind"], abs(m["delta"]))
            spark = _sparkline_svg(m["series"], color=col)
            rows_html += (
                f'<tr><td class="pm-l">{e(m["label"])}</td>'
                f'<td class="pm-v">{e(m["start_str"])} <span class="pm-ar">→</span> <b>{e(m["cur_str"])}</b></td>'
                f'<td class="pm-s">{spark}</td>'
                f'<td class="pm-d {cls}">{sign}{e(gain)}</td></tr>')
        sc = _trend_chart_svg(prog.get("score_chart") or [], title="PracticeRank Score", color=b["accent"])
        tc = _trend_chart_svg(prog.get("traffic_chart") or [], title="Organic Traffic (clicks)", color="#2563eb")
        charts = f'<div class="trends">{sc}{tc}</div>' if (sc or tc) else ""
        sd = prog.get("start_date")
        since = f" since {e(sd[:10])}" if sd else ""
        has_pos = any(m["label"] == "Avg search position" for m in prog["metrics"])
        pos_note = (
            '<p class="pm-note">📌 <b>About average position:</b> it can <b>rise (look worse)</b> '
            'precisely when things are going well — as you start ranking for <b>more</b> queries, '
            'new keywords enter at lower positions and pull the <i>average</i> down even while your '
            'total visibility (impressions) grows and your best pages hold. Read it alongside '
            'impressions and query count, never on its own.</p>') if has_pos else ""
        parts.append(
            f'<div class="r-sec"><h3>Your progress{since}</h3>'
            f'<table class="pm">{rows_html}</table>{pos_note}{charts}</div>')

    # 1c. What to expect — maturation timeline (AEO 6+ weeks, SEO longer)
    parts.append(
        f'<div class="r-sec"><div class="expect">'
        f'<div class="expect-t">⏳ What to expect</div>'
        f'<p>{e(_maturation_note(data))} Week-to-week swings are normal noise — judge progress '
        f'by the trend since you started, not any single week.</p></div></div>')

    # 1·outcome — the number clients renew for: new-patient inquiries + production
    if s.get("outcomes"):
        o = s["outcomes"]
        delta_html = ""
        if o.get("prev_inquiries") is not None:
            label, direction = _pct_delta(o["inquiries"], o["prev_inquiries"])
            delta_html = _delta_span(f"{label} vs prior period", direction)
        bd = o["breakdown"]
        chips = " &nbsp;·&nbsp; ".join(
            f"{ic} {n} {lbl}" for ic, n, lbl in (
                ("📞", bd["calls"], "calls"), ("✍️", bd["forms"], "forms"),
                ("📅", bd["bookings"], "bookings")) if n)
        if o.get("estimated_value"):
            money = (f'<div style="font-size:20px;font-weight:800;color:#0f766e;margin-top:2px;">'
                     f'~${o["estimated_value"]:,} <span style="font-size:13px;font-weight:600;color:#475569;">'
                     f'in potential new-patient production</span></div>'
                     f'<div style="font-size:11px;color:#94a3b8;margin-top:4px;">'
                     f'{o["inquiries"]} inquiries × {round(o["close_rate"]*100)}% est. close × '
                     f'${o["avg_case_value"]:,} avg case value</div>')
        else:
            money = ('<div style="font-size:11px;color:#94a3b8;margin-top:6px;">'
                     'Set this practice’s average case value to show estimated production.</div>')
        parts.append(f"""<div class="r-sec"><h3>New patients this period</h3>
          <div style="background:#f0fdfa;border:1px solid #99f6e4;border-radius:12px;padding:18px 20px;">
            <div style="font-size:34px;font-weight:800;color:#0f766e;line-height:1;">{o['inquiries']}
              <span style="font-size:15px;font-weight:600;color:#334155;">new patient inquiries</span></div>
            {money}
            <div style="margin-top:10px;font-size:12px;color:#475569;">{chips}</div>
            {delta_html}
          </div></div>""")

    # 1a. What we need from you (customer action items)
    if s.get("needs"):
        items = "".join(
            f'<li style="display:flex;gap:10px;align-items:flex-start;margin-bottom:11px">'
            f'<span style="font-size:18px;line-height:1.3">{n["icon"]}</span>'
            f'<div><b>{e(n["title"])}</b><div class="mini" style="color:#64748b">{e(n["why"])}</div></div></li>'
            for n in s["needs"])
        parts.append(f"""<div class="r-sec" style="background:#fff7ed;border:1px solid #fed7aa;border-radius:12px;">
          <h3>✅ What we need from you</h3>
          <p class="mini" style="margin:0 0 10px;color:#9a3412">A few quick things on your end will boost your results this month:</p>
          <ul style="list-style:none;padding:0;margin:0">{items}</ul></div>""")

    # 1b. High-value buyer-intent keywords to focus on
    if s.get("focus_keywords"):
        rows = ""
        for f in s["focus_keywords"]:
            pos = f'#{f["position"]}' if f["position"] else "—"
            loc = ' <span title="local search">📍</span>' if f["local"] else ''
            rows += (f'<tr style="border-bottom:1px solid #f1f5f9"><td style="padding:7px 6px;font-weight:500">{e(f["keyword"])}{loc}</td>'
                     f'<td style="padding:7px 6px"><span style="font-size:10.5px;font-weight:700;background:{f["bg"]};color:{f["color"]};padding:2px 8px;border-radius:99px;white-space:nowrap">{e(f["label"])}</span></td>'
                     f'<td style="padding:7px 6px;text-align:right;color:#64748b;white-space:nowrap">{pos}</td></tr>')
        parts.append(f"""<div class="r-sec"><h3>🎯 Your high-value keywords to win</h3>
          <p class="mini" style="margin:0 0 8px;color:#64748b">The buyer-intent searches that bring real customers your way — ranked by intent. These are what we're focused on winning for you.</p>
          <table style="width:100%;border-collapse:collapse;font-size:14px"><tbody>{rows}</tbody></table></div>""")

    # 2. Score
    score = data["score"]
    if score.get("score") is not None:
        g = score["grade"]
        delta = ""
        if data.get("score_prev") is not None:
            d = score["score"] - data["score_prev"]
            arr = "▲" if d > 0 else ("▼" if d < 0 else "–")
            delta = f' <span class="mini">{arr} {d:+d} vs last</span>' if d else ""
        pillars_html = ""
        names = {"ai_visibility": "AI Visibility", "search_growth": "Search Performance",
                 "technical_health": "GEO Foundation", "content_velocity": "Content & Coverage",
                 "reputation": "Reputation"}
        for key, label in names.items():
            p = score["pillars"].get(key, {})
            if not p.get("available"):
                continue
            val = p["score"]
            color = grade_from_score(val)["color"]
            pillars_html += (f'<div class="pillar"><div class="lbl"><span>{label}</span>'
                             f'<span>{val}</span></div><div class="bar">'
                             f'<i style="width:{val}%;background:{color}"></i></div></div>')
        parts.append(f"""<div class="r-sec"><h3>PracticeRank Score{delta}</h3>
          <div class="score-row">
            <div class="score-badge" style="background:{g['color']}"><b>{score['score']}</b><span>Grade {g['letter']}</span></div>
            <div class="pillars">{pillars_html}</div>
          </div></div>""")

    # 3. Search performance
    if "search" in s:
        cur, prev = s["search"]["cur"], s["search"].get("prev")
        def sd(field, fmt="{:+.0f}"):
            return _delta_span(*_abs_delta(cur[field], prev[field] if prev else None, fmt)) if prev else ""
        clicks_d = _delta_span(*_pct_delta(cur["clicks"], prev["clicks"])) if prev else ""
        impr_d = _delta_span(*_pct_delta(cur["impressions"], prev["impressions"])) if prev else ""
        pos_d = _delta_span(*_pos_delta(cur["position"], prev["position"] if prev else None)) if prev else ""
        ctr_d = sd("ctr", "{:+.1f}pt")
        kpis = (_kpi("Clicks", f"{int(cur['clicks'])}", clicks_d)
                + _kpi("Impressions", f"{int(cur['impressions'])}", impr_d)
                + _kpi("Avg position", f"{cur['position']:.1f}", pos_d)
                + _kpi("CTR", f"{cur['ctr']*100:.1f}%" if cur['ctr'] < 1 else f"{cur['ctr']:.1f}%", ctr_d))
        parts.append(f'<div class="r-sec"><h3>Search performance · {e(data.get("period_human", "last 7 days"))}</h3><div class="kpis">{kpis}</div></div>')

    # 4. Keywords (R1)
    if "keywords" in s:
        rows = ""
        for q in s["keywords"]["top"]:
            rows += (f'<tr><td>{e(q["query"])}</td><td>{int(q["clicks"])}</td>'
                     f'<td>{q["position"]:.1f}</td></tr>')
        parts.append(f"""<div class="r-sec"><h3>Top keywords</h3>
          <table><tr><th>Query</th><th>Clicks</th><th>Avg position</th></tr>{rows}</table></div>""")

    # 5. AI visibility (the differentiator — lead with Share of Voice)
    if "ai" in s:
        ai = s["ai"]
        latest = ai.get("latest") or {}
        roll = ai.get("rolling")
        # Headline KPIs
        kpis = ""
        rate = None
        if latest and latest.get("total_queries"):
            rate = latest["mention_rate"] * 100
        elif roll:
            rate = roll["current_rate"] * 100
        if rate is not None:
            d = ("from %.0f%%" % (roll["prev_rate"] * 100), roll["trend"]) if roll and roll.get("prev_rate") else ("", "flat")
            kpis += _kpi("AI mention rate", f"{rate:.0f}%", _delta_span(*d) if d[0] else "")
        if latest.get("avg_position"):
            kpis += _kpi("Avg position in answers", f"#{latest['avg_position']:.1f}")
        if ai.get("llms"):
            cur = ai["llms"]["value"]; prev = ai.get("llms_prev")
            kpis += _kpi("llms.txt bot hits", f"{int(cur)}",
                         _delta_span(*_abs_delta(cur, prev)) if prev is not None else "")
        # Per-engine chips
        engine_chips = ""
        for name, info in (ai.get("engines") or {}).items():
            if not isinstance(info, dict):
                continue
            m, t = info.get("mentions", 0), info.get("total", 0)
            if info.get("status") == "active" and t:
                engine_chips += f'<span class="chip">✓ {e(name)} {m}/{t}</span>'
            else:
                engine_chips += f'<span class="chip miss">{e(name)} — pending</span>'
        # Share of Voice leaderboard
        sov_html = ""
        sov = ai.get("sov")
        if sov and sov.get("competitors"):
            rank = sov.get("customer_rank")
            n = len(sov["competitors"]) + 1
            you = round((sov.get("customer_share", 0) or 0) * 100)
            rows = f'<tr style="font-weight:700;color:{BRAND["accent"]}"><td>★ You</td><td>{you}%</td></tr>'
            for c in sov["competitors"][:5]:
                rows += f'<tr><td>{e(c.get("name",""))}</td><td>{round((c.get("share",0) or 0)*100)}%</td></tr>'
            rank_txt = f'<b>#{rank} of {n}</b> in AI search share of voice' if rank else 'AI search share of voice'
            sov_html = (f'<p class="mini" style="margin:14px 0 6px">{rank_txt} — who AI engines name for your queries:</p>'
                        f'<table><tr><th>Business</th><th>Share</th></tr>{rows}</table>')
        # Flagship AI Share-of-Voice score — the moat metric, led with.
        flag_html = ""
        flag = ai.get("sov_flag")
        if flag and flag.get("score") is not None:
            delta = flag.get("delta")
            dtxt = ""
            if delta:
                dcol = "#0f766e" if delta > 0 else "#b45309"
                dtxt = (f'<span style="font-size:13px;font-weight:700;color:{dcol};margin-left:8px;">'
                        f'{"▲" if delta > 0 else "▼"} {abs(delta)} pts</span>')
            rank = flag.get("rank")
            sub = ("You’re the <b>#1</b> business AI engines name for your buyer queries."
                   if flag.get("leads") else
                   (f'Ranked <b>#{rank}</b> of {flag.get("total_named", 0)} businesses AI engines name for your queries.'
                    if rank else "Share of AI answers that name your practice."))
            flag_html = (
                f'<div style="background:#faf5ff;border:1px solid #e9d5ff;border-radius:12px;padding:16px 20px;margin-bottom:14px;">'
                f'<div style="font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#7c3aed;">AI Share-of-Voice</div>'
                f'<div style="font-size:34px;font-weight:800;color:#7c3aed;line-height:1.1;">{flag["score"]}%{dtxt}</div>'
                f'<div style="font-size:12.5px;color:#475569;margin-top:2px;">{sub}</div></div>')
        if kpis or engine_chips or sov_html or flag_html:
            block = '<div class="r-sec"><h3>AI search visibility</h3>'
            block += flag_html
            if kpis:
                block += f'<div class="kpis" style="grid-template-columns:repeat(3,1fr)">{kpis}</div>'
            if engine_chips:
                block += f'<div class="engines" style="margin-top:12px">{engine_chips}</div>'
            block += sov_html + '</div>'
            parts.append(block)

    # 6. Leads (R3)
    if "leads" in s:
        cur, prev = s["leads"]["cur"], s["leads"].get("prev", {})
        labels = {"phone_click": "Phone calls", "form_submit": "Form submits",
                  "appointment_request": "Appt requests"}
        kpis = ""
        total_cur = total_prev = 0
        for ev, lab in labels.items():
            c = cur.get(ev, 0); p = prev.get(ev, 0)
            total_cur += c; total_prev += p
            if c or p:
                kpis += _kpi(lab, str(c), _delta_span(*_abs_delta(c, p)))
        kpis += _kpi("Total leads", str(total_cur), _delta_span(*_pct_delta(total_cur, total_prev)))
        parts.append(f'<div class="r-sec"><h3>Leads this week · from organic search</h3>'
                     f'<div class="kpis">{kpis}</div></div>')

    # 7. Reviews
    if "reviews" in s:
        rv = s["reviews"]; pl = rv["places"]
        kpis = (_kpi("Google rating", f"{pl.get('rating', 0):.1f}★")
                + _kpi("Total reviews", str(int(pl.get("review_count", 0))))
                + _kpi("New this week", str(rv["new_count"]),
                       f'<div class="delta up">{rv["new_five_star"]} × 5★</div>' if rv["new_five_star"] else ""))
        vel = rv.get("velocity")
        if vel:
            vcls = "up" if vel["on_track"] else "down"
            vlbl = "on pace" if vel["on_track"] else f"target {vel['target']}/mo"
            vdelta = f'<div class="delta {vcls}">{vlbl}</div>'
            kpis += _kpi("Reviews / month", str(vel["current"]), vdelta)
        gap_note = ""
        if rv.get("gap"):
            g = rv["gap"]
            trend = ""
            if g.get("gap_delta") is not None and g["gap_delta"]:
                trend = f' (gap {"narrowed" if g["gap_delta"] > 0 else "widened"} by {abs(g["gap_delta"])} this week)'
            kpis += _kpi(f"vs {e(g['competitor'])[:18]}", f"{g['gap']:+d}",
                         '<div class="delta flat">review volume</div>')
            gap_note = f'<p class="mini" style="margin-top:12px">Nearest competitor has {g["competitor_reviews"]} reviews{trend}.</p>'
        if vel and not vel["on_track"]:
            gap_note += (f'<p class="mini" style="margin-top:8px;color:#b45309">'
                         f'Review pace is below target ({vel["current"]} vs {vel["target"]}/mo) — '
                         f'the review-request campaign needs a nudge.</p>')
        parts.append(f'<div class="r-sec"><h3>Reviews &amp; reputation</h3>'
                     f'<div class="kpis">{kpis}</div>{gap_note}</div>')

    # 8. Local listings (R4)
    if "listings" in s:
        ls = s["listings"]
        color = grade_from_score(ls["score"])["color"]
        issues = "".join(f'<li><b>{e(c["directory"])}</b> — NAP mismatch</li>' for c in ls["issues"]) \
            or "<li>All tracked directories consistent. ✅</li>"
        parts.append(f"""<div class="r-sec"><h3>Local listings health</h3>
          <div class="score-row">
            <div class="score-badge" style="background:{color};width:88px;height:88px"><b style="font-size:26px">{ls['score']}%</b><span>NAP consistent</span></div>
            <div class="pillars"><p style="margin:0 0 6px">{ls['consistent']} of {ls['total']} tracked directories consistent{f" — building toward {ls['target']} key local directories for your industry" if ls.get('target') else ''}.</p><ul style="margin:4px 0">{issues}</ul></div>
          </div></div>""")

    # 8b. Domain Authority + competitor gap
    if "authority" in s:
        a = s["authority"]
        da = round(a["da"])

        def _da_pill(prev, label):
            """A '+N vs <label>' chip; None/no-change → ''."""
            if prev is None:
                return ""
            d = da - round(prev)
            if d > 0:
                return (f'<span class="da-pill" style="background:#dcfce7;color:#166534">'
                        f'▲ +{d} vs {label}</span>')
            if d < 0:
                return (f'<span class="da-pill" style="background:#fee2e2;color:#991b1b">'
                        f'▼ {d} vs {label}</span>')
            return f'<span class="da-pill" style="background:#f1f5f9;color:#475569">flat vs {label}</span>'

        pills = "".join(p for p in (
            _da_pill(a.get("week_prev"), "last week"),
            _da_pill(a.get("month_prev"), "last month"),
        ) if p)
        started = da - round(a["first"])
        started_html = (f'<span class="da-pill" style="background:#eff6ff;color:#1e40af">'
                        f'▲ +{started} since we started</span>') if started > 0 else ""
        pills = f'<div class="da-pills">{pills}{started_html}</div>' if (pills or started_html) else ""
        gap_html = ""
        if a.get("top_competitor"):
            top = round(a["top_competitor"])
            gap = max(0, top - da)
            gap_html = (f'<p style="margin:8px 0 0">Your top competitor sits at <b>{top}</b> — '
                        f'a <b>{gap}-point</b> authority gap. Closing it is exactly what our off-site '
                        f'link &amp; citation work targets.</p>')
        # Over-time chart + competitor comparison bars.
        trend_html = ""
        if a.get("series"):
            trend_html = (f'<div style="margin-top:14px"><div class="mini" style="margin-bottom:2px">'
                          f'Domain Authority over time</div>{_vbars(a["series"], "value", color="#16a34a")}</div>')
        comp_html = ""
        if a.get("competitors"):
            rows = [(f"You", da, True)] + [(c["name"], round(c["da"]), False) for c in a["competitors"]]
            rows.sort(key=lambda r: r[1], reverse=True)
            comp_html = (f'<div style="margin-top:14px"><div class="mini" style="margin-bottom:2px">'
                         f'You vs your competitors (DA)</div>{_hbars(rows)}</div>')
        parts.append(
            f'<div class="r-sec"><h3>Domain Authority</h3>'
            f'<div class="score-row"><div class="score-badge" style="background:#16a34a;width:88px;height:88px">'
            f'<b style="font-size:26px">{da}</b><span>of 100</span></div>'
            f'<div class="pillars"><p style="margin:0">Your site\'s link authority — a 0–100 measure of how '
            f'much Google trusts your domain.</p>{pills}{gap_html}</div>'
            f'</div>{trend_html}{comp_html}</div>')

    # 8b-2. Visitors over time (organic clicks trend)
    if s.get("traffic_series"):
        parts.append(
            f'<div class="r-sec"><h3>Visitors over time</h3>'
            f'<p class="mini" style="margin:0 0 2px">Organic visitors per week (Google Search)</p>'
            f'{_vbars(s["traffic_series"], "clicks", color="#2563eb", height=54)}</div>')

    # 8c. Authority work this period (off-site / FATJOE)
    if "offsite" in s:
        o = s["offsite"]
        items = []
        if o["links"]:
            top = ""
            if o.get("top_link"):
                top = f' — avg DA {o["avg_link_da"]}, highest <b>{e(o["top_link"]["domain"])}</b> DA {o["top_link"]["da"]}'
            items.append(f'{o["links"]} new editorial link{"s" if o["links"] != 1 else ""} live{top}')
        if o["citations"]:
            items.append(f'{o["citations"]} local citations submitted &amp; NAP-consistent')
        if o.get("mention_domain"):
            items.append(f'Brand mention live at <b>{e(o["mention_domain"])}</b> — now eligible to be cited by AI')
        elif o["mentions"]:
            items.append(f'{o["mentions"]} brand mention{"s" if o["mentions"] != 1 else ""} live')
        if o.get("new_ref_domains"):
            items.append(f'Referring domains: <b>+{o["new_ref_domains"]}</b> this period ({o["total_ref_domains"]} total)')
        completed_html = ""
        if items:
            lis = "".join(f'<li>✅ {it}</li>' for it in items)
            completed_html = (f'<p class="mini" style="margin:6px 0 2px;font-weight:600;color:#16a34a">Completed</p>'
                              f'<ul style="margin:0;padding-left:18px">{lis}</ul>')
        wip_html = ""
        if o.get("wip_items"):
            wlis = "".join(f'<li>⏳ {e(it)}</li>' for it in o["wip_items"])
            wip_html = (f'<p class="mini" style="margin:10px 0 2px;font-weight:600;color:#b45309">In progress</p>'
                        f'<ul style="margin:0;padding-left:18px;color:#475569">{wlis}</ul>')
        parts.append(
            f'<div class="r-sec"><h3>Authority work · last 30 days</h3>'
            f'{completed_html}{wip_html}</div>')

    # 9. Sources now citing you (from grounded AI answers)
    if "sources" in s and s["sources"]:
        chips = "".join(
            f'<span class="chip">{e(src.get("domain",""))} · {src.get("count",0)}</span>'
            for src in s["sources"])
        parts.append(f'<div class="r-sec"><h3>Sources now citing you</h3>'
                     f'<p class="mini" style="margin:0 0 10px">When AI assistants answer questions about your area, '
                     f'these are the sources they pull from that reference you:</p>'
                     f'<div class="engines">{chips}</div></div>')

    # 10. What we've shipped (all-time summary)
    if "shipped" in s and s["shipped"].get("total"):
        sh = s["shipped"]
        cards = "".join(
            f'<div class="kpi"><div class="v">{g["count"]}</div><div class="k">{e(g["label"])}</div></div>'
            for g in sh["groups"])
        recent = "".join(f'<li>{e(t)}</li>' for t in sh.get("recent", []))
        recent_html = (f'<p class="mini" style="margin:12px 0 4px">Recent highlights:</p>'
                       f'<ul style="margin:0">{recent}</ul>') if recent else ""
        parts.append(f'<div class="r-sec"><h3>What we\'ve shipped — {sh["total"]} improvements</h3>'
                     f'<div class="kpis">{cards}</div>{recent_html}</div>')

    # 11. Wins (this week)
    wins = s.get("wins", {}).get("published", [])
    if wins:
        items = "".join(f'<li>✅ Published <b>{e(w["title"])}</b></li>' for w in wins[:8])
        mix = s.get("wins", {}).get("intent_mix")
        mix_html = ""
        if mix and mix["total"]:
            bp = mix["buyer_pct"]
            mix_html = (
                f'<div style="margin-top:12px">'
                f'<div style="display:flex;height:10px;border-radius:5px;overflow:hidden;background:#e2e8f0">'
                f'<div style="width:{bp}%;background:#0f766e"></div><div style="width:{100-bp}%;background:#cbd5e1"></div></div>'
                f'<p class="mini" style="margin:6px 0 0">Content focus: <b>{bp}% buyer-intent</b> '
                f'({mix["buyer"]} buyer · {mix["research"]} research) — we prioritize the searches that book patients.</p>'
                f'</div>')
        parts.append(f'<div class="r-sec"><h3>What we did this week</h3><ul class="wins">{items}</ul>{mix_html}</div>')

    # 10. What's next (from alerts)
    next_items = ""
    for a in data.get("alerts", [])[:4]:
        next_items += f'<li>→ {e(a.get("message", ""))}</li>'
    if not next_items:
        next_items = "<li>→ Continue content publishing and AI-visibility optimization.</li>"
    parts.append(f'<div class="r-sec"><h3>What\'s next</h3><ul>{next_items}</ul></div>')

    parts.append("""</div>
    <div class="r-foot">Questions about any of these metrics? Just reply to this email.<br>
    <b>Kody Doherty · PracticeRank</b> · practicerank.ai</div>""")

    body = "\n".join(parts)
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Weekly Report — {e(data['practice_name'])}</title>
<style>
  body{{margin:0;background:{b['bg']};font:15px/1.55 -apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,Roboto,Helvetica,Arial,sans-serif;color:{b['ink']};-webkit-font-smoothing:antialiased}}
  .report{{max-width:720px;margin:24px auto;background:{b['card']};border:1px solid {b['line']};border-radius:16px;overflow:hidden;box-shadow:0 8px 30px rgba(0,0,0,.06)}}
  .r-head{{background:{b['hero']};color:#fff;padding:26px 30px}}
  .r-head .brand{{font-size:12px;letter-spacing:.18em;text-transform:uppercase;color:{b['accent2']}}}
  .r-head h2{{margin:6px 0 2px;font-size:24px;color:#fff}}
  .r-head .sub{{opacity:.7;font-size:14px}}
  .r-body{{padding:6px 30px 24px}}
  .r-sec{{padding:20px 0;border-bottom:1px solid {b['line']}}}
  .r-sec:last-child{{border-bottom:0}}
  h3{{color:{b['ink']};font-size:13px;text-transform:uppercase;letter-spacing:.05em;margin:0 0 12px;font-weight:700}}
  .mini{{font-size:12px;color:{b['muted']}}}
  .engines{{display:flex;gap:8px;flex-wrap:wrap}}
  .chip{{font-size:12px;background:#eef4f8;border:1px solid #d7e6ef;color:#0f3d5c;padding:4px 10px;border-radius:99px}}
  .chip.miss{{background:{b['bg']};color:{b['muted']};border-color:{b['line']}}}
  .summary{{background:{b['accent']}12;border:1px solid {b['accent']}33;border-radius:12px;padding:16px 18px}}
  .summary p{{margin:0;font-size:15.5px;color:#14532d}}
  .score-row{{display:flex;gap:22px;align-items:center;flex-wrap:wrap}}
  .score-badge{{width:104px;height:104px;border-radius:50%;display:flex;flex-direction:column;align-items:center;justify-content:center;color:#fff;flex:0 0 auto}}
  .score-badge b{{font-size:34px;line-height:1}} .score-badge span{{font-size:12px;opacity:.9}}
  .pillars{{flex:1;min-width:240px}}
  .da-pills{{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}}
  .da-pill{{font-size:12px;font-weight:700;padding:3px 10px;border-radius:99px;white-space:nowrap}}
  .pillar{{margin:7px 0}} .pillar .lbl{{display:flex;justify-content:space-between;font-size:13px;margin-bottom:3px}}
  .bar{{height:8px;background:#eef1f4;border-radius:99px;overflow:hidden}} .bar i{{display:block;height:100%;border-radius:99px}}
  .kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}
  @media(max-width:560px){{.kpis{{grid-template-columns:repeat(2,1fr)}}}}
  .kpi{{background:{b['bg']};border:1px solid {b['line']};border-radius:10px;padding:12px 14px}}
  .kpi .v{{font-size:22px;font-weight:700}} .kpi .k{{font-size:12px;color:{b['muted']};text-transform:uppercase;letter-spacing:.04em}}
  .delta{{font-size:12.5px;font-weight:600;margin-top:3px}}
  .up{{color:{b['good']}}} .down{{color:{b['bad']}}} .flat{{color:{b['muted']}}}
  .pm{{width:100%;font-size:14px}}
  .pm td{{border-bottom:1px solid {b['line']};padding:9px 6px;vertical-align:middle}}
  .pm tr:last-child td{{border-bottom:0}}
  .pm-l{{color:{b['muted']};font-weight:600;white-space:nowrap}}
  .pm-v{{white-space:nowrap}} .pm-ar{{color:{b['muted']}}}
  .pm-s{{width:104px}} .pm-s svg{{display:block}}
  .pm-d{{text-align:right;font-weight:700;white-space:nowrap;font-variant-numeric:tabular-nums}}
  .trends{{display:grid;grid-template-columns:1fr;gap:14px;margin-top:16px}}
  .trend{{border:1px solid {b['line']};border-radius:12px;padding:12px 14px;background:{b['bg']}}}
  .trend-t{{font-size:11px;font-weight:700;color:{b['muted']};text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px}}
  .trend svg{{width:100%;height:auto;display:block}}
  .expect{{background:#fff7ed;border:1px solid #fed7aa;border-radius:12px;padding:14px 16px}}
  .expect-t{{font-size:12px;font-weight:800;color:#9a3412;text-transform:uppercase;letter-spacing:.04em;margin-bottom:4px}}
  .expect p{{margin:0;font-size:13.5px;color:#7c2d12;line-height:1.5}}
  .pm-note{{margin:10px 0 0;font-size:12.5px;color:{b['muted']};line-height:1.5;background:{b['bg']};border-left:3px solid {b['accent']};padding:9px 12px;border-radius:0 8px 8px 0}}
  table{{border-collapse:collapse;width:100%;font-size:14px}}
  th,td{{text-align:left;padding:8px 10px;border-bottom:1px solid {b['line']}}}
  th{{font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:{b['muted']}}}
  ul{{margin:6px 0;padding-left:20px}} li{{margin:5px 0}}
  .r-foot{{background:{b['bg']};padding:18px 30px;font-size:13px;color:{b['muted']};text-align:center}}
</style></head><body><div class="report">{body}</div></body></html>"""


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

_REPORT_TYPE_BY_DAYS = {7: "weekly", 30: "monthly", 90: "quarterly", 180: "half-year", 365: "annual"}


def generate_and_store(db: CustomerDB, customer_id: str, period_end: str | None = None,
                       period_days: int = 7, report_type: str | None = None) -> dict:
    """Build + render + persist one report. Returns {customer_id, score, html, ...}.
    period_days: 7 weekly · 30 monthly · 90 quarterly · 180 half-year. The snapshot is
    stored under its report_type so weekly/monthly/quarterly reports coexist."""
    rt = report_type or _REPORT_TYPE_BY_DAYS.get(period_days, "custom")
    data = build_report_data(db, customer_id, period_end, period_days=period_days)
    html_doc = render_html(data)
    score_val = data["score"].get("score") or 0

    # Snapshot the score history (so deltas work week over week)
    today = data["period_end"]
    sc = data["score"]
    if sc.get("score") is not None:
        pil = sc["pillars"]
        db.save_practicerank_score(
            customer_id, today, sc["score"],
            pil.get("ai_visibility", {}).get("score"),
            pil.get("search_growth", {}).get("score"),
            pil.get("technical_health", {}).get("score"),
            pil.get("content_velocity", {}).get("score"),
            pil.get("reputation", {}).get("score"),
            sc.get("breakdown_json", "{}"),
        )

    payload = {k: v for k, v in data.items() if k not in ("customer",)}
    token = db.save_report_snapshot(
        customer_id, rt, data["period_start"], data["period_end"],
        int(score_val), json.dumps(payload, default=str), html_doc,
    )
    logger.info("%s report generated for %s (score=%s)", rt, customer_id, score_val)
    return {"customer_id": customer_id, "score": score_val, "report_type": rt,
            "period_end": data["period_end"], "html": html_doc, "share_token": token}


def rerender_snapshots(db: CustomerDB, customer_id: str | None = None,
                       report_type: str = "weekly", limit: int = 200) -> dict:
    """Apply the CURRENT report template to already-stored snapshots, re-using each
    snapshot's captured point-in-time payload (no recompute — the historical data stays
    exactly as it was). Preserves period_start/end, score, and share_token (so existing
    links don't break). Skips empty placeholder snapshots. Returns {rerendered, skipped, errors}."""
    cust = [customer_id] if customer_id else [c["id"] for c in db.list_customers()]
    done = skipped = errors = 0
    for cid in cust:
        for snap in db.get_report_snapshots(cid, report_type, limit=limit, include_payload=True):
            raw = snap.get("payload_json") or "{}"
            try:
                payload = json.loads(raw)
            except Exception:
                payload = {}
            if not payload.get("sections"):
                skipped += 1
                continue
            try:
                html = render_html(payload)
                db.save_report_snapshot(cid, report_type, snap["period_start"],
                                        snap["period_end"], int(snap.get("score") or 0), raw, html)
                done += 1
            except Exception:
                logger.exception("re-render failed for %s %s", cid, snap.get("period_end"))
                errors += 1
    return {"rerendered": done, "skipped_empty": skipped, "errors": errors}


def generate_all(db: CustomerDB, period_end: str | None = None, period_days: int = 7) -> list[dict]:
    """Generate reports for every active customer (period_days: 7 weekly / 30 monthly / 90 quarterly)."""
    results = []
    for c in db.list_customers():
        if c.get("onboarding_step") not in ACTIVE_STEPS:
            continue
        try:
            results.append(generate_and_store(db, c["id"], period_end, period_days=period_days))
        except Exception:
            logger.exception("Report (%dd) failed for %s", period_days, c.get("id"))
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import sys
    with CustomerDB() as _db:
        if len(sys.argv) > 1:
            res = generate_and_store(_db, sys.argv[1])
            print(f"Generated weekly report for {res['customer_id']} (score {res['score']})")
        else:
            for r in generate_all(_db):
                print(f"  {r['customer_id']}: score {r['score']}")
