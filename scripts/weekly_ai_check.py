#!/usr/bin/env python3
"""Weekly AI mention check for all customers.

Run via cron: 0 9 * * 1  (every Monday at 9am)

Usage:
    python scripts/weekly_ai_check.py
    python scripts/weekly_ai_check.py --customer smileshape
"""

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from geo_agent.db import CustomerDB
from scripts.check_ai_mentions import (
    build_comprehensive_prompts, query_claude, query_openai, query_perplexity,
    query_gemini, query_grok, check_mention,
)

ENGINES = [
    ("Claude", query_claude),
    ("ChatGPT", query_openai),
    ("Perplexity", query_perplexity),
    ("Gemini", query_gemini),
    ("Grok", query_grok),
]


# Cost control: cap each run to the highest-value queries (surgical, not spammy).
# Categories are kept in this priority order; we take the top MAX_PROMPTS overall.
_CATEGORY_PRIORITY = {
    "recommendation": 0, "location": 1, "service": 2, "brand": 3,
    "general": 4, "reputation": 5, "comparison": 6,
}
MAX_PROMPTS = 16


def _prune_prompts(prompt_defs: list[dict]) -> list[dict]:
    """Keep only the highest-value prompts (cap the per-run cost)."""
    ranked = sorted(prompt_defs, key=lambda p: _CATEGORY_PRIORITY.get(p.get("category"), 9))
    return ranked[:MAX_PROMPTS]


def _recompute_and_save_run(db: CustomerDB, run_id: str, customer_id: str,
                            today: str, prompt_set: str = "comprehensive") -> None:
    """(Re)build the run summary FROM the persisted results — robust to a run that
    gets interrupted mid-loop (deploy/kill/timeout) instead of leaving it at 0/0."""
    rows = db.conn.execute(
        "SELECT engine, mentioned, position, samples, samples_mentioned "
        "FROM ai_mention_results WHERE run_id = ?",
        (run_id,),
    ).fetchall()
    engines: dict = {}
    mentions = 0
    positions = []
    total_samples = 0
    samples_mentioned = 0
    for engine, mentioned, position, samples, sm in rows:
        s = engines.setdefault(engine, {"status": "active", "mentions": 0, "total": 0})
        s["total"] += 1
        total_samples += (samples or 1)
        samples_mentioned += (sm if sm is not None else (1 if mentioned else 0))
        if mentioned:
            s["mentions"] += 1
            mentions += 1
            if position:
                positions.append(position)
    total = sum(s["total"] for s in engines.values())
    # Sample-averaged rate (benchmark runs sample each cell); falls back to the
    # binary cell rate when samples aren't recorded.
    rate = (samples_mentioned / total_samples) if total_samples else 0.0
    db.save_ai_mention_run({
        "id": run_id, "customer_id": customer_id, "run_date": today,
        "total_mentions": mentions, "total_queries": total,
        "mention_rate": rate,
        "avg_position": (sum(positions) / len(positions)) if positions else None,
        "engines": engines, "prompt_set": prompt_set,
    })


def run_check(db: CustomerDB, customer: dict) -> dict:
    """Run comprehensive AI mention check for a single customer."""
    customer_id = customer["id"]
    competitors = json.loads(customer.get("competitors_json", "[]")) if customer.get("competitors_json") else []

    prompt_defs = _prune_prompts(build_comprehensive_prompts(
        customer["name"], customer.get("city", ""), customer.get("state", ""),
        customer.get("specialties", []),
        business_type=customer.get("business_type", "practice"),
        competitors=competitors,
        service_areas=customer.get("service_areas", []),
    ))

    results = []
    mention_count = 0
    engine_stats = {}
    run_id = str(uuid.uuid4())
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Create run record first (FK constraint)
    db.save_ai_mention_run({
        "id": run_id,
        "customer_id": customer_id,
        "run_date": today,
        "total_mentions": 0,
        "total_queries": 0,
        "mention_rate": 0.0,
        "avg_position": None,
        "engines": {},
        "prompt_set": "comprehensive",
    })

    for prompt_idx, pdef in enumerate(prompt_defs):
        prompt = pdef["prompt"]
        category = pdef["category"]
        for ai_name, query_fn in ENGINES:
            er = query_fn(prompt)
            if er is None:
                engine_stats.setdefault(ai_name, {"status": "no_key", "mentions": 0, "total": 0})
                continue
            if er.error:
                engine_stats[ai_name] = {"status": "error", "mentions": engine_stats.get(ai_name, {}).get("mentions", 0), "total": engine_stats.get(ai_name, {}).get("total", 0)}
                continue
            response = er.text
            engine_stats.setdefault(ai_name, {"status": "active", "mentions": 0, "total": 0})
            engine_stats[ai_name]["total"] += 1

            result = check_mention(response, customer["name"])
            if result["mentioned"]:
                mention_count += 1
                engine_stats[ai_name]["mentions"] += 1

            # Save to DB (with the grounded model + web citations)
            db.save_ai_mention_result({
                "run_id": run_id,
                "customer_id": customer_id,
                "engine": ai_name,
                "prompt": prompt,
                "prompt_category": category,
                "mentioned": result["mentioned"],
                "position": result.get("position"),
                "quality_score": result.get("quality_score", 0),
                "context": result.get("context", "")[:500],
                "full_response": (response or "")[:2000],
                "is_disclaimer": result.get("disclaimer", False),
                "model": er.model,
                "citations": er.citations,
            })

            results.append({
                "prompt": prompt,
                "category": category,
                "ai": ai_name,
                "mentioned": result["mentioned"],
                "position": result["position"],
                "quality_score": result.get("quality_score", 0),
                "context": result["context"][:150] if result.get("context") else "",
            })

        # Persist the summary incrementally so an interruption (deploy/kill/timeout)
        # never leaves the run at 0/0 — it always reflects results saved so far.
        if (prompt_idx + 1) % 4 == 0:
            _recompute_and_save_run(db, run_id, customer_id, today)

    # Final summary — rebuilt from the persisted results (robust).
    _recompute_and_save_run(db, run_id, customer_id, today)
    total_queries = sum(s["total"] for s in engine_stats.values())
    mention_rate = mention_count / total_queries if total_queries > 0 else 0.0
    positions = [r["position"] for r in results if r["mentioned"] and r["position"]]
    avg_pos = sum(positions) / len(positions) if positions else None

    # Also save to KPI for backward compat
    db.record_kpi(customer_id, "ai_mentions", mention_count, today)
    if avg_pos:
        db.record_kpi(customer_id, "ai_avg_position", avg_pos, today)

    # Extract competitor entities from responses
    try:
        from geo_agent.entity_extractor import extract_and_store
        entity_count = extract_and_store(db, run_id, customer_id, customer["name"])
        print(f"  Extracted {entity_count} entities from responses")
        added = db.auto_discover_competitors_from_entities(customer_id, min_mentions=3)
        if added:
            print(f"  Auto-discovered {len(added)} new competitors: {', '.join(added)}")
    except Exception as e:
        print(f"  Entity extraction failed (non-fatal): {e}")

    return {
        "customer_id": customer_id,
        "customer_name": customer["name"],
        "date": today,
        "mention_count": mention_count,
        "total_queries": total_queries,
        "mention_rate": round(mention_rate * 100, 1),
        "engines": engine_stats,
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Weekly AI mention check")
    parser.add_argument("--customer", default=None, help="Run for specific customer only")
    parser.add_argument("--db", default=None, help="Database path")
    args = parser.parse_args()

    db = CustomerDB(db_path=args.db)
    try:
        if args.customer:
            customers = [db.get_customer(args.customer)]
            if not customers[0]:
                print(f"Customer not found: {args.customer}")
                sys.exit(1)
        else:
            customers = db.list_customers(status="active") + db.list_customers(status="live")
            # Deduplicate
            seen = set()
            customers = [c for c in customers if c["id"] not in seen and not seen.add(c["id"])]

        print(f"Running AI mention check for {len(customers)} customer(s)...")
        _engine_keys = {'Claude': 'ANTHROPIC_API_KEY', 'ChatGPT': 'OPENAI_API_KEY', 'Perplexity': 'PERPLEXITY_API_KEY', 'Gemini': 'GEMINI_API_KEY', 'Grok': 'XAI_API_KEY'}
        active_engines = [n for n, _ in ENGINES if os.environ.get(_engine_keys.get(n, ''))]
        print(f"Active engines: {', '.join(active_engines)}")
        print()

        all_results = []
        for customer in customers:
            print(f"Checking: {customer['name']}...")
            summary = run_check(db, customer)
            all_results.append(summary)

            active = {k: v for k, v in summary["engines"].items() if v["status"] == "active"}
            print(f"  Mentions: {summary['mention_count']}/{summary['total_queries']}")
            for eng, stats in active.items():
                print(f"    {eng}: {stats['mentions']}/{stats['total']}")
            print()

        # Save weekly report
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        reports_dir = Path(__file__).resolve().parent.parent / "data" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = reports_dir / f"ai-mentions-{today}.json"
        report_path.write_text(json.dumps(all_results, indent=2))
        print(f"Report saved: {report_path}")

        # Generate per-customer DOCX reports
        docx_paths = []
        try:
            from geo_agent.ai_report_docx import generate_ai_mention_report
            for summary in all_results:
                cust = db.get_customer(summary["customer_id"])
                if not cust:
                    continue
                # Get the full results for this run
                run_results = db.get_ai_mention_results(summary.get("run_id", "")) if summary.get("run_id") else summary.get("results", [])
                result_list = []
                if isinstance(run_results, list) and run_results:
                    for r in run_results:
                        result_list.append({
                            "prompt": r.get("prompt", ""),
                            "category": r.get("prompt_category", r.get("category", "general")),
                            "ai": r.get("engine", r.get("ai", "")),
                            "mentioned": bool(r.get("mentioned")),
                            "position": r.get("position"),
                            "quality_score": r.get("quality_score", 0),
                            "context": r.get("context", ""),
                        })

                run_data = {
                    "date": today,
                    "mention_count": summary["mention_count"],
                    "total_queries": summary["total_queries"],
                    "mention_rate": summary.get("mention_rate", 0),
                    "avg_position": None,
                    "engines": summary.get("engines", {}),
                }

                # Get history for trend
                hist_runs = db.get_ai_mention_runs(summary["customer_id"], limit=12)
                history = [{"date": r["run_date"], "mentions": r["total_mentions"], "total": r["total_queries"],
                            "rate": r["mention_rate"], "avg_position": r.get("avg_position"), "delta": None}
                           for r in hist_runs if r.get("total_queries", 0) > 0]
                for i, h in enumerate(history):
                    if i + 1 < len(history):
                        h["delta"] = h["mentions"] - history[i + 1]["mentions"]

                buf = generate_ai_mention_report(
                    customer=dict(cust),
                    run_data=run_data,
                    results=result_list or summary.get("results", []),
                    history=history if len(history) >= 2 else None,
                )
                name_slug = cust.get("name", "customer").replace(" ", "-")
                docx_path = reports_dir / f"AI-Report-{name_slug}-{today}.docx"
                docx_path.write_bytes(buf.read())
                docx_paths.append(docx_path)
                print(f"DOCX report saved: {docx_path}")
        except Exception as e:
            print(f"DOCX generation error: {e}")

        # Send email report
        send_weekly_email(db, all_results, today)
        db.record_job_run("weekly_ai_check", detail=f"{len(all_results)} customer(s)")

    finally:
        db.close()


def send_weekly_email(db: CustomerDB, all_results: list[dict], date: str):
    """Send an HTML email summary of the weekly AI mention check."""
    resend_key = os.environ.get("RESEND_API_KEY", "")
    notify_email = os.environ.get("NOTIFY_EMAIL", "jonlucas@lostrelic.com")
    if not resend_key:
        print("No RESEND_API_KEY — skipping email")
        return

    # Build HTML email
    html = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:700px;margin:0 auto;">
      <div style="background:#2563eb;color:white;padding:20px 24px;border-radius:12px 12px 0 0;">
        <h1 style="margin:0;font-size:20px;">PracticeRank — Weekly AI Mention Report</h1>
        <p style="margin:4px 0 0;opacity:0.85;font-size:14px;">Week of {date}</p>
      </div>
      <div style="padding:20px 24px;background:#f9fafb;border:1px solid #e5e7eb;border-top:none;border-radius:0 0 12px 12px;">
    """

    for summary in all_results:
        name = summary["customer_name"]
        mentions = summary["mention_count"]
        total = summary["total_queries"]
        pct = round(mentions / total * 100) if total > 0 else 0

        # Get previous week's data for comparison
        prev_kpis = db.get_kpis(summary["customer_id"], "ai_mentions", limit=2)
        prev_mentions = prev_kpis[1]["value"] if len(prev_kpis) >= 2 else None
        if prev_mentions is not None:
            delta = mentions - int(prev_mentions)
            trend = f'<span style="color:{"#22c55e" if delta > 0 else "#ef4444" if delta < 0 else "#6b7280"};">{"+" if delta > 0 else ""}{delta}</span>'
        else:
            trend = '<span style="color:#6b7280;">baseline</span>'

        html += f"""
        <div style="margin-bottom:20px;padding:16px;background:white;border-radius:8px;border:1px solid #e5e7eb;">
          <h2 style="margin:0 0 8px;font-size:16px;">{name}</h2>
          <div style="display:flex;gap:16px;margin-bottom:12px;">
            <div style="text-align:center;">
              <div style="font-size:28px;font-weight:bold;color:{"#22c55e" if pct > 30 else "#f59e0b" if pct > 0 else "#ef4444"};">{mentions}/{total}</div>
              <div style="font-size:12px;color:#6b7280;">mentions ({pct}%)</div>
            </div>
            <div style="text-align:center;">
              <div style="font-size:28px;font-weight:bold;">{trend}</div>
              <div style="font-size:12px;color:#6b7280;">vs last week</div>
            </div>
          </div>
          <table style="width:100%;font-size:13px;border-collapse:collapse;">
            <tr style="border-bottom:1px solid #e5e7eb;">
              <th style="text-align:left;padding:4px;">Engine</th>
              <th style="text-align:center;">Mentions</th>
              <th style="text-align:center;">Status</th>
            </tr>
        """
        for eng_name, stats in summary["engines"].items():
            if stats["status"] == "no_key":
                status_html = '<span style="color:#f59e0b;">No API key</span>'
                m = "-"
            else:
                m = f"{stats['mentions']}/{stats['total']}"
                status_html = '<span style="color:#22c55e;">Active</span>' if stats["mentions"] > 0 else '<span style="color:#ef4444;">Active</span>'
            html += f'<tr style="border-bottom:1px solid #f3f4f6;"><td style="padding:4px;">{eng_name}</td><td style="text-align:center;">{m}</td><td style="text-align:center;">{status_html}</td></tr>'

        # Top mentions with context
        mentioned = [r for r in summary["results"] if r["mentioned"]]
        if mentioned:
            html += '</table><div style="margin-top:10px;font-size:12px;color:#374151;"><b>Key mentions:</b><ul style="margin:4px 0;padding-left:20px;">'
            for r in mentioned[:5]:
                pos = f" (#{r['position']})" if r["position"] else ""
                ctx = r["context"][:100] + "..." if len(r.get("context", "")) > 100 else r.get("context", "")
                html += f'<li><b>{r["ai"]}</b> on "{r["prompt"]}"{pos}: <i>{ctx}</i></li>'
            html += '</ul></div>'
        else:
            html += '</table><p style="margin-top:8px;font-size:12px;color:#6b7280;">No genuine mentions found this week.</p>'

        html += '</div>'

    html += """
        <p style="font-size:12px;color:#9ca3af;text-align:center;margin-top:16px;">
          Auto-generated by PracticeRank AI Monitor · <a href="https://practicerank.ai">Dashboard</a>
        </p>
      </div>
    </div>
    """

    # Send via Resend
    try:
        import httpx
        resp = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
            json={
                "from": "PracticeRank <reports@practicerank.ai>",
                "to": [notify_email],
                "subject": f"AI Mention Report — {date} ({sum(s['mention_count'] for s in all_results)} total mentions)",
                "html": html,
            },
            timeout=15.0,
        )
        if resp.status_code in (200, 201):
            print(f"Email report sent to {notify_email}")
        else:
            print(f"Email send failed: {resp.status_code} {resp.text[:200]}")
    except Exception as e:
        print(f"Email send error: {e}")


if __name__ == "__main__":
    main()
