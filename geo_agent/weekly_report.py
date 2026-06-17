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

    # --- AI visibility (REAL) ---
    rolling = db.get_rolling_mention_stats(customer_id)
    llms = db.get_latest_kpi(customer_id, "llms_txt_hits")
    llms_hist = db.get_kpis(customer_id, "llms_txt_hits", limit=2)
    if rolling or llms:
        data["sections"]["ai"] = {
            "rolling": rolling,
            "llms": llms,
            "llms_prev": llms_hist[1]["value"] if len(llms_hist) > 1 else None,
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
        data["sections"]["reviews"] = {
            "places": places,
            "new_count": len(new_reviews),
            "new_five_star": sum(1 for r in new_reviews if r.get("rating") == 5),
            "gap": db.get_competitor_review_gap(customer_id, own_reviews),
        }

    # --- Local listings / NAP (R4; renders only when citations audited) ---
    citations = db.get_citations(customer_id)
    if citations:
        tracked = [c for c in citations if c.get("listed")]
        consistent = sum(1 for c in tracked if c.get("nap_match"))
        issues = [c for c in tracked if not c.get("nap_match")]
        denom = len(tracked) or 1
        data["sections"]["listings"] = {
            "score": round(consistent / denom * 100),
            "consistent": consistent, "total": len(tracked),
            "issues": issues[:5],
        }

    # --- Wins (REAL) ---
    published = [r for r in db.get_content_recommendations(customer_id, status="published", limit=50)
                 if (r.get("published_at") or "")[:10] >= ds(cur_start)]
    data["sections"]["wins"] = {"published": published}

    # --- Alerts (REAL) → inform "what's next" ---
    data["alerts"] = db.get_alerts(customer_id, active_only=True, limit=10)

    data["exec_summary"] = _exec_summary(data)
    return data


def _exec_summary(data: dict) -> str:
    """Rule-based headline from the biggest positive movement. (Claude hook: future.)"""
    name = data["practice_name"]
    bits = []
    s = data["sections"]
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
        names = {"ai_visibility": "AI Visibility", "search_growth": "Search Growth",
                 "technical_health": "Technical Health", "content_velocity": "Content Velocity",
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

    # 5. AI visibility
    if "ai" in s:
        kpis = ""
        roll = s["ai"].get("rolling")
        if roll:
            rate = roll["current_rate"] * 100
            d = ("from %.0f%%" % (roll["prev_rate"] * 100), roll["trend"]) if roll.get("prev_rate") else ("", "flat")
            kpis += _kpi("AI mention rate", f"{rate:.0f}%", _delta_span(*d) if d[0] else "")
        if s["ai"].get("llms"):
            cur = s["ai"]["llms"]["value"]
            prev = s["ai"].get("llms_prev")
            kpis += _kpi("llms.txt bot hits", f"{int(cur)}",
                         _delta_span(*_abs_delta(cur, prev)) if prev is not None else "")
        if kpis:
            parts.append(f'<div class="r-sec"><h3>AI search visibility</h3>'
                         f'<div class="kpis" style="grid-template-columns:repeat(2,1fr)">{kpis}</div></div>')

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
            <div class="pillars"><p style="margin:0 0 6px">{ls['consistent']} of {ls['total']} key directories consistent.</p><ul style="margin:4px 0">{issues}</ul></div>
          </div></div>""")

    # 9. Wins
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
  .summary{{background:{b['accent']}12;border:1px solid {b['accent']}33;border-radius:12px;padding:16px 18px}}
  .summary p{{margin:0;font-size:15.5px;color:#14532d}}
  .score-row{{display:flex;gap:22px;align-items:center;flex-wrap:wrap}}
  .score-badge{{width:104px;height:104px;border-radius:50%;display:flex;flex-direction:column;align-items:center;justify-content:center;color:#fff;flex:0 0 auto}}
  .score-badge b{{font-size:34px;line-height:1}} .score-badge span{{font-size:12px;opacity:.9}}
  .pillars{{flex:1;min-width:240px}}
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
