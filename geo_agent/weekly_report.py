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

def build_report_data(db: CustomerDB, customer_id: str, period_end: str | None = None) -> dict:
    """Gather every available field for the weekly report. Missing data → None/empty."""
    customer = db.get_customer(customer_id)
    if not customer:
        raise ValueError(f"Unknown customer: {customer_id}")

    end = datetime.strptime(period_end, "%Y-%m-%d") if period_end \
        else datetime.now(timezone.utc).replace(tzinfo=None)
    cur_start = end - timedelta(days=6)
    prev_end = cur_start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=6)
    ds = lambda d: d.strftime("%Y-%m-%d")  # noqa: E731

    data: dict = {
        "customer": customer,
        "practice_name": customer.get("name", "Your Practice"),
        "contact_name": (db.get_contacts(customer_id) or [{}])[0].get("name", "there")
        if hasattr(db, "get_contacts") else "there",
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

    # --- Search performance (REAL) ---
    weekly = db.get_gsc_weekly_summary(customer_id, weeks=3)
    if weekly:
        data["sections"]["search"] = {
            "cur": weekly[0],
            "prev": weekly[1] if len(weekly) > 1 else None,
        }

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
    if rolling or llms or latest_ai:
        data["sections"]["ai"] = {
            "rolling": rolling,
            "llms": llms,
            "llms_prev": llms_hist[1]["value"] if len(llms_hist) > 1 else None,
            "latest": latest_ai,
            "engines": engines,
            "sov": sov,
        }

    # --- Leads / conversions (R3; renders only when GA4 conversions configured) ---
    conv = db.get_conversions(customer_id, ds(cur_start), ds(end), channel="organic")
    if conv:
        prev_conv = db.get_conversions(customer_id, ds(prev_start), ds(prev_end), channel="organic")
        data["sections"]["leads"] = {"cur": conv, "prev": prev_conv}

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

        data["sections"]["authority"] = {
            "da": da_latest["value"],
            "first": da_hist[0]["value"] if da_hist else da_latest["value"],
            "week_prev": _da_at_or_before(ds(end - timedelta(days=7))),
            "month_prev": _da_at_or_before(ds(end - timedelta(days=28))),
            "top_competitor": comp_das[0] if comp_das and comp_das[0] > 0 else None,
        }

    # --- Authority work this period (FATJOE off-site, last 30 days) ---
    try:
        since30 = ds(end - timedelta(days=30))
        osum = db.offsite_summary(customer_id, since=since30)
        if osum["links"] or osum["citations"] or osum["mentions"]:
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
            }
    except Exception:
        pass

    data["sections"]["wins"] = {"published": published}

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

    # --- Alerts (REAL) → inform "what's next" ---
    data["alerts"] = db.get_alerts(customer_id, active_only=True, limit=10)

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


def render_html(data: dict) -> str:
    b = BRAND
    s = data["sections"]
    e = html.escape
    parts: list[str] = []

    # Header
    parts.append(f"""<div class="r-head">
      <div class="brand">PracticeRank · Weekly Report</div>
      <h2>{e(data['practice_name'])}</h2>
      <div class="sub">Week of {e(data['period_label'])} · prepared for {e(data['contact_name'])}</div>
    </div>
    <div class="r-body">""")

    # 1. Exec summary
    parts.append(f"""<div class="r-sec"><h3>The headline</h3>
      <div class="summary"><p>📈 {e(data['exec_summary'])}</p></div></div>""")

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
        parts.append(f'<div class="r-sec"><h3>Search performance · last 7 days</h3><div class="kpis">{kpis}</div></div>')

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
        if kpis or engine_chips or sov_html:
            block = '<div class="r-sec"><h3>AI search visibility</h3>'
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
        gap_note = ""
        if rv.get("gap"):
            g = rv["gap"]
            trend = ""
            if g.get("gap_delta") is not None and g["gap_delta"]:
                trend = f' (gap {"narrowed" if g["gap_delta"] > 0 else "widened"} by {abs(g["gap_delta"])} this week)'
            kpis += _kpi(f"vs {e(g['competitor'])[:18]}", f"{g['gap']:+d}",
                         '<div class="delta flat">review volume</div>')
            gap_note = f'<p class="mini" style="margin-top:12px">Nearest competitor has {g["competitor_reviews"]} reviews{trend}.</p>'
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
        parts.append(
            f'<div class="r-sec"><h3>Domain Authority</h3>'
            f'<div class="score-row"><div class="score-badge" style="background:#16a34a;width:88px;height:88px">'
            f'<b style="font-size:26px">{da}</b><span>of 100</span></div>'
            f'<div class="pillars"><p style="margin:0">Your site\'s link authority — a 0–100 measure of how '
            f'much Google trusts your domain.</p>{pills}{gap_html}</div>'
            f'</div></div>')

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
        lis = "".join(f'<li>{it}</li>' for it in items)
        parts.append(
            f'<div class="r-sec"><h3>Authority work · last 30 days</h3>'
            f'<ul style="margin:6px 0 0;padding-left:18px">{lis}</ul></div>')

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
        parts.append(f'<div class="r-sec"><h3>What we did this week</h3><ul class="wins">{items}</ul></div>')

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
  table{{border-collapse:collapse;width:100%;font-size:14px}}
  th,td{{text-align:left;padding:8px 10px;border-bottom:1px solid {b['line']}}}
  th{{font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:{b['muted']}}}
  ul{{margin:6px 0;padding-left:20px}} li{{margin:5px 0}}
  .r-foot{{background:{b['bg']};padding:18px 30px;font-size:13px;color:{b['muted']};text-align:center}}
</style></head><body><div class="report">{body}</div></body></html>"""


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def generate_and_store(db: CustomerDB, customer_id: str, period_end: str | None = None) -> dict:
    """Build + render + persist one weekly report. Returns {customer_id, score, html, ...}."""
    data = build_report_data(db, customer_id, period_end)
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
        customer_id, "weekly", data["period_start"], data["period_end"],
        int(score_val), json.dumps(payload, default=str), html_doc,
    )
    logger.info("Weekly report generated for %s (score=%s)", customer_id, score_val)
    return {"customer_id": customer_id, "score": score_val,
            "period_end": data["period_end"], "html": html_doc, "share_token": token}


def generate_all(db: CustomerDB, period_end: str | None = None) -> list[dict]:
    """Generate weekly reports for every active customer."""
    results = []
    for c in db.list_customers():
        if c.get("onboarding_step") not in ACTIVE_STEPS:
            continue
        try:
            results.append(generate_and_store(db, c["id"], period_end))
        except Exception:
            logger.exception("Weekly report failed for %s", c.get("id"))
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
