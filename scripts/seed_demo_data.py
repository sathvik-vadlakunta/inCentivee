#!/usr/bin/env python3
"""Seed a fully realistic demo customer for local dev/testing.

Unlike the hand-typed `payload_json` fixtures scattered across
`tests/integration/test_portal_*.py`, this script seeds the RAW tables the
report pipeline actually reads (GSC daily metrics, AI mention runs/results,
Google Places, reviews, the GEO Foundation checklist, content
recommendations, KPI history) and then runs the real
`weekly_report.generate_and_store()` pipeline against them. The resulting
`report_snapshots` row is exactly what a real customer's snapshot looks
like — same code path, same schema — not a JSON blob someone typed by hand
that can silently drift from what the pipeline actually produces.

Usage:
    python scripts/seed_demo_data.py --db /path/to/scratch.db [--reset]

    --reset   Wipe this demo customer's existing rows first (safe to rerun;
              without --reset, rerunning skips seeding if the customer
              already exists and just regenerates fresh snapshots).

Prints the demo customer id, portal login credentials, and the score each
generated snapshot actually came out to, so you can eyeball whether the
pipeline produced something sane before pointing a dev server at it.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

from geo_agent.db import CustomerDB  # noqa: E402
from geo_agent import weekly_report  # noqa: E402

CUSTOMER_ID = "demo-aspen-grove"
CUSTOMER_NAME = "Aspen Grove Dental"
PORTAL_USERNAME = "demo"
PORTAL_PASSWORD = "demo-password-123"
ADMIN_USERNAME = "demo-admin"
ADMIN_PASSWORD = "demo-admin-password-123"
ADMIN_DISPLAY_NAME = "Demo Staff"

SERVICE_AREAS = ["Bellingham, WA", "Ferndale, WA", "Lynden, WA", "Blaine, WA"]
LIVE_AREA_PAGES = ["Bellingham, WA", "Ferndale, WA", "Lynden, WA"]  # 3 of 4 — matches spec mock

# 7 of 8 done — matches the spec mock's "7 of 8 deliverables complete."
FOUNDATION_CHECKLIST = {
    "seo_schema_localbusiness": True,
    "seo_schema_faq": True,
    "seo_llms_txt": True,
    "seo_robots_txt": True,
    "seo_llms_full": False,  # "in progress", per spec mock
    "seo_xml_sitemap": True,
    "seo_schema_review": True,
    "seo_structured_headings": True,
}

ENGINES = ["Claude", "ChatGPT", "Perplexity", "Gemini", "Grok"]
BENCHMARK_PROMPTS = [
    "Best emergency dentist in Bellingham WA",
    "Family dentist near me that takes new patients",
    "Dentist in Bellingham that does same-day crowns",
    "Cheapest teeth whitening in Bellingham Washington",
    "Pediatric dentist Bellingham WA",
    "Dentist that accepts Medicaid Bellingham",
    "Cosmetic dentist near Ferndale WA",
    "Weekend emergency dentist Whatcom County",
]
# Per-engine hit rate for the LATEST run, matching the spec mock's numbers
# (Claude 100%, ChatGPT 75%, Perplexity 63%, Gemini 38%, Grok 13%).
LATEST_ENGINE_HITS = {"Claude": 8, "ChatGPT": 6, "Perplexity": 5, "Gemini": 3, "Grok": 1}

RESET_TABLES = [
    ("content_recommendations", "customer_id"),
    ("reviews", "customer_id"),
    ("competitors", "customer_id"),
    ("competitor_domains", "customer_id"),
    ("gsc_daily_metrics", "customer_id"),
    ("gsc_query_daily", "customer_id"),
    ("ai_response_entities", "customer_id"),
    ("ai_mention_results", "customer_id"),
    ("ai_mention_runs", "customer_id"),
    ("google_places", "customer_id"),
    ("kpis", "customer_id"),
    ("va_checklist", "customer_id"),
    ("client_users", "customer_id"),
    ("report_snapshots", "customer_id"),
    ("practicerank_scores", "customer_id"),
]


def _today() -> datetime:
    return datetime.now(timezone.utc)


def reset_demo_customer(db: CustomerDB) -> None:
    for table, col in RESET_TABLES:
        try:
            db.conn.execute(f"DELETE FROM {table} WHERE {col} = ?", (CUSTOMER_ID,))
        except Exception as e:
            print(f"  (skip {table}: {e})")
    db.conn.execute("DELETE FROM customers WHERE id = ?", (CUSTOMER_ID,))
    db.conn.execute("DELETE FROM dashboard_users WHERE username = ?", (ADMIN_USERNAME,))
    db.conn.commit()
    print(f"Reset: cleared all existing rows for {CUSTOMER_ID} (+ the demo admin login)")


def seed_customer(db: CustomerDB) -> None:
    db.conn.execute(
        """INSERT OR IGNORE INTO customers
           (id, name, domain, platform, business_type, city, state, zip, phone, status)
           VALUES (?, ?, ?, 'webflow', 'practice', ?, ?, ?, ?, 'active')""",
        (CUSTOMER_ID, CUSTOMER_NAME, "aspengrovedental.com", "Bellingham", "WA",
         "98225", "(360) 555-0142"),
    )
    db.conn.commit()
    # service_areas isn't auto-JSON-encoded by update_customer() — pass it pre-encoded.
    db.update_customer(CUSTOMER_ID, service_areas=json.dumps(SERVICE_AREAS))
    db.set_live_area_pages(CUSTOMER_ID, LIVE_AREA_PAGES)
    db.set_cutover(CUSTOMER_ID, True)  # so it shows up in admin /content-queue too
    print(f"Seeded customer: {CUSTOMER_ID} ({CUSTOMER_NAME})")


def seed_checklist(db: CustomerDB) -> None:
    for key, done in FOUNDATION_CHECKLIST.items():
        db.set_checklist_item(CUSTOMER_ID, key, done)
    done_n = sum(FOUNDATION_CHECKLIST.values())
    print(f"Seeded GEO Foundation checklist: {done_n}/{len(FOUNDATION_CHECKLIST)} done")


def seed_gsc(db: CustomerDB) -> None:
    today = _today()
    # 60 days of daily metrics, rising trend, so 8-week aggregation shows growth.
    for i in range(60, 0, -1):
        d = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        progress = (60 - i) / 60  # 0 -> 1 as we approach today
        clicks = round(5 + progress * 8 + (i % 3))  # noisy upward trend
        impressions = round(clicks * (13 + progress * 4))
        position = round(14 - progress * 6, 1)
        ctr = round(clicks / impressions, 4) if impressions else 0.0
        db.save_gsc_daily(CUSTOMER_ID, d, clicks, impressions, ctr, position)

    # Query-level data for the last 14 days (covers current + previous 7-day
    # windows) so top-queries and query-movers both have real data.
    queries = [
        ("emergency dentist bellingham", 6.8, 3.3),
        ("dentist bellingham wa", 4.1, 1.2),
        ("teeth whitening bellingham", 5.2, 0.9),
        ("family dentist near me", 11.4, -0.6),
        ("pediatric dentist bellingham", 8.0, 2.1),
        ("same day crowns bellingham", 9.5, 1.5),
        ("dentist accepts medicaid bellingham", 15.2, 0.4),
        ("cosmetic dentist ferndale wa", 12.8, 0.8),
    ]
    for i in range(14, 0, -1):
        d = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        in_current_window = i <= 7
        rows = []
        for query, end_pos, total_move in queries:
            # Position improves linearly from (end_pos + total_move) toward end_pos.
            frac = (14 - i) / 13
            pos = round(end_pos + total_move * (1 - frac), 1)
            clicks = max(1, round(20 * (1 - pos / 20)))
            impressions = clicks * 12
            rows.append({"query": query, "clicks": clicks, "impressions": impressions,
                         "ctr": round(clicks / impressions, 4), "position": pos})
        db.save_gsc_query_daily(CUSTOMER_ID, d, rows)
    print("Seeded 60 days of GSC daily metrics + 14 days of query-level data")


def seed_ai_mentions(db: CustomerDB) -> None:
    today = _today()
    # 8 weekly benchmark runs, mention rate rising ~34% -> 58% (matches spec mock).
    rates = [0.34, 0.37, 0.39, 0.42, 0.46, 0.49, 0.53, 0.58]
    run_ids = []
    for week_i, rate in enumerate(rates):
        run_date = (today - timedelta(days=(7 - week_i) * 7)).strftime("%Y-%m-%d")
        run_id = f"{CUSTOMER_ID}-run-{week_i}"
        run_ids.append(run_id)
        is_latest = week_i == len(rates) - 1
        if is_latest:
            engines_summary = {
                name: {"mentions": hits, "total": 8, "status": "active"}
                for name, hits in LATEST_ENGINE_HITS.items()
            }
        else:
            # Earlier runs: same relative engine ordering, scaled to that week's rate.
            engines_summary = {
                name: {"mentions": round(hits * rate / rates[-1]), "total": 8, "status": "active"}
                for name, hits in LATEST_ENGINE_HITS.items()
            }
        db.save_ai_mention_run({
            "id": run_id, "customer_id": CUSTOMER_ID, "run_date": run_date,
            "total_mentions": round(rate * 8 * len(ENGINES)),
            "total_queries": 8 * len(ENGINES), "mention_rate": rate,
            "avg_position": round(3.5 - rate * 2, 1),
            "engines": engines_summary, "prompt_set": "benchmark", "methodology": "2.0",
        })
        # Full per-prompt results for the last 3 runs — "Questions we test"
        # (Ticket 6) only ever needs the single latest run, but share-of-voice
        # (db.get_share_of_voice, default last_n_runs=3) pools entities across
        # the last 3, so those need real ai_mention_results rows to attach
        # ai_response_entities to (FOREIGN KEY result_id -> ai_mention_results.id).
        is_sov_run = week_i >= len(rates) - 3
        if is_sov_run:
            run_hits = (LATEST_ENGINE_HITS if is_latest else
                       {n: round(h * rate / rates[-1]) for n, h in LATEST_ENGINE_HITS.items()})
            claude_result_ids = {}  # prompt -> id, used as the SOV entity anchor below
            for engine in ENGINES:
                hits = run_hits[engine]
                for p_i, prompt in enumerate(BENCHMARK_PROMPTS):
                    mentioned = p_i < hits
                    db.save_ai_mention_result({
                        "run_id": run_id, "customer_id": CUSTOMER_ID, "engine": engine,
                        "prompt": prompt, "prompt_category": "local_intent",
                        "mentioned": mentioned, "position": (p_i + 1) if mentioned else None,
                        "quality_score": 8 if mentioned else 0,
                        "context": f"Mentioned {CUSTOMER_NAME}" if mentioned else "",
                        "full_response": "", "is_disclaimer": False, "model": "",
                    })
                    if engine == "Claude":
                        row = db.conn.execute(
                            "SELECT id FROM ai_mention_results WHERE run_id=? AND engine=? AND prompt=?",
                            (run_id, engine, prompt),
                        ).fetchone()
                        claude_result_ids[p_i] = row["id"]

            # Share of voice: which businesses AI answers name, not just whether
            # ours got mentioned. Anchored on Claude's result row per prompt (one
            # AI answer often names several practices in one response, e.g. a
            # "top 3 dentists near you" — so multiple entities per result_id is
            # realistic, not a bug). Deterministic per-prompt pattern rather than
            # random so reruns without --reset produce identical entity counts.
            for p_i, prompt in enumerate(BENCHMARK_PROMPTS):
                result_id = claude_result_ids[p_i]
                run_date_iso = f"{run_date}T00:00:00Z"

                def _entity(name: str, is_customer: bool, position: int):
                    db.save_ai_response_entity({
                        "result_id": result_id, "run_id": run_id, "customer_id": CUSTOMER_ID,
                        "entity_name": name, "entity_name_normalized": name.lower().strip(),
                        "is_customer": is_customer, "position": position,
                        "engine": "Claude", "prompt": prompt,
                        "prompt_category": "local_intent", "run_date": run_date_iso,
                    })

                if p_i < LATEST_ENGINE_HITS["Claude"]:  # matches Claude's own hit/miss above
                    _entity(CUSTOMER_NAME, True, 1)
                if p_i % 2 == 0:
                    _entity("Bellingham Family Dental", False, 2)
                if p_i % 3 == 0:
                    _entity("Whatcom Smiles", False, 3)
                if p_i % 4 == 0:
                    _entity("Cascade Family Dentistry", False, 4)
    print(f"Seeded {len(rates)} weekly AI mention runs (rate {rates[0]:.0%} -> {rates[-1]:.0%}), "
          f"full per-prompt results + share-of-voice entities for the last 3 runs "
          f"({len(BENCHMARK_PROMPTS)} prompts x {len(ENGINES)} engines each)")


def seed_reviews_and_places(db: CustomerDB) -> None:
    today = _today()
    db.upsert_google_places(CUSTOMER_ID, place_id="demo-place-id", rating=4.7,
                            review_count=128, match_confidence="high",
                            lat=48.7519, lng=-122.4787)
    review_dates = [1, 3, 5, 12, 20, 35, 50, 70, 90, 110]
    for i, days_ago in enumerate(review_dates):
        rating = 5 if i % 3 != 0 else 4
        d = (today - timedelta(days=days_ago)).strftime("%Y-%m-%d")
        db.add_review(CUSTOMER_ID, rating=rating,
                      review_text="Great experience, friendly staff!" if rating == 5
                                  else "Good visit overall.",
                      reviewer_name=f"Patient {i + 1}", review_date=d,
                      source="google", sentiment="positive" if rating >= 4 else "neutral")
    # Rating history (Mar->Jun climb, matches spec mock's rating-trend chart)
    # and review_count history (for the growth sub-score).
    for months_ago, rating, count in [(3, 4.4, 118), (2, 4.5, 121), (1, 4.6, 124), (0, 4.7, 128)]:
        d = (today - timedelta(days=months_ago * 30)).strftime("%Y-%m-%d")
        db.record_kpi(CUSTOMER_ID, "rating", rating, date=d)
        db.record_kpi(CUSTOMER_ID, "review_count", count, date=d)
    db.add_competitor(CUSTOMER_ID, "Bellingham Family Dental", rating=4.5, review_count=94,
                      location="Bellingham, WA")
    db.add_competitor(CUSTOMER_ID, "Whatcom Smiles", rating=4.3, review_count=61,
                      location="Ferndale, WA")
    print("Seeded Google Places, 10 reviews, rating/review_count KPI history, 2 competitors")


def seed_domain_authority(db: CustomerDB) -> None:
    """Moz Domain Authority history + one competitor domain's DA, for the
    Overview page's "Domain rank" card (weekly_report.py's `sections.authority`,
    gated on db.get_latest_kpi(customer_id, "domain_authority") existing)."""
    today = _today()
    for months_ago, da in [(3, 24), (2, 27), (1, 29), (0, 31)]:
        d = (today - timedelta(days=months_ago * 30)).strftime("%Y-%m-%d")
        db.record_kpi(CUSTOMER_ID, "domain_authority", da, date=d)
    db.add_competitor_domain(CUSTOMER_ID, "bellinghamfamilydental.com",
                             name="Bellingham Family Dental")
    db.update_competitor_da(CUSTOMER_ID, "bellinghamfamilydental.com", 38)
    print("Seeded Domain Authority history (24 -> 31) + 1 competitor domain (DA 38)")


def seed_content(db: CustomerDB) -> None:
    today = _today()

    def rec(i, rec_type, title, status, days_ago, impact=""):
        db.add_content_recommendation({
            "id": f"{CUSTOMER_ID}-rec-{i}", "customer_id": CUSTOMER_ID, "rec_type": rec_type,
            "target_page": "", "title": title, "description": title,
            "html_snippet": f"<p>Demo content body for {title}.</p>",
            "priority": 2, "category": "general", "status": status,
            "ai_impact_reason": impact or f"Improves AI/search visibility for {title.lower()}.",
            "created_at": (today - timedelta(days=days_ago + 2)).isoformat(),
        })
        if status == "published":
            # add_content_recommendation() does NOT write published_at (only
            # update_content_recommendation_status() does, and only to "now") —
            # set it directly so `sections.wins.published`'s period filter
            # (weekly_report.py: `published_at >= cur_start`) actually includes
            # these rows instead of silently excluding all of them.
            published_at = (today - timedelta(days=days_ago)).isoformat()
            db.conn.execute(
                "UPDATE content_recommendations SET published_at = ? WHERE id = ?",
                (published_at, f"{CUSTOMER_ID}-rec-{i}"),
            )
            db.conn.commit()

    # Recent (within the last week) so these show up in the weekly, monthly,
    # AND quarterly report windows alike — sections.wins.published is
    # period-scoped to `published_at >= cur_start` of whichever cadence
    # generated that snapshot, so an old publish date would silently vanish
    # from the shorter-window snapshots (this bit me during manual testing).
    rec(1, "new_page", "Emergency Dental Care in Bellingham", "published", 6)
    rec(2, "blog_post", "What to Do If You Chip a Tooth", "published", 5)
    rec(3, "blog_post", "5 Signs You Need a Root Canal", "published", 4)
    rec(4, "faq_update", "Updated Insurance & Payment FAQ", "published", 3)
    rec(5, "freshness_update", "Refreshed Homepage Service Descriptions", "published", 2)
    rec(6, "new_page", "Pediatric Dentistry in Ferndale", "pending", 0,
        impact="A dedicated Ferndale page closes your one uncovered service area and "
               "targets 'pediatric dentist ferndale wa', a query with rising impressions.")
    rec(7, "blog_post", "Same-Day Crowns: What to Expect", "pending", 0,
        impact="Directly answers a benchmark question AI assistants are currently asked "
               "about your practice — closing an AI-visibility gap.")
    print("Seeded 5 published (all within the last week, visible at every cadence) + 2 pending content recommendations")


def generate_snapshots(db: CustomerDB) -> None:
    for period_days, label in [(7, "weekly"), (30, "monthly"), (90, "quarterly")]:
        result = weekly_report.generate_and_store(db, CUSTOMER_ID, period_days=period_days)
        print(f"Generated {label} snapshot via the REAL pipeline: "
              f"score={result['score']}, report_type={result['report_type']}")


def seed_portal_login(db: CustomerDB) -> None:
    existing = db.list_client_users(CUSTOMER_ID)
    if existing:
        print(f"Portal login already exists for {CUSTOMER_ID} (username: {existing[0]['username']})")
        return
    result = db.create_client_user(CUSTOMER_ID, PORTAL_USERNAME, "Demo Client")
    db.complete_client_signup(result["signup_token"], PORTAL_PASSWORD)
    print(f"Seeded portal login: username={PORTAL_USERNAME!r} password={PORTAL_PASSWORD!r}")


def seed_admin_login(db: CustomerDB) -> None:
    """Staff/admin login (dashboard_users) — separate table and session from the
    client-portal login above; create_user() is idempotent (returns False on a
    duplicate username rather than raising), so this is safe to call every run."""
    created = db.create_user(ADMIN_USERNAME, ADMIN_PASSWORD, ADMIN_DISPLAY_NAME, role="admin")
    if created:
        print(f"Seeded admin login: username={ADMIN_USERNAME!r} password={ADMIN_PASSWORD!r}")
    else:
        print(f"Admin login already exists: username={ADMIN_USERNAME!r}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="Path to the SQLite DB file to seed")
    parser.add_argument("--reset", action="store_true",
                        help="Wipe this demo customer's existing rows before reseeding")
    args = parser.parse_args()

    db = CustomerDB(db_path=args.db)
    try:
        if args.reset:
            reset_demo_customer(db)
        existing = db.get_customer(CUSTOMER_ID)
        if existing and not args.reset:
            print(f"{CUSTOMER_ID} already exists — skipping raw-data seeding "
                  f"(use --reset to wipe and reseed). Regenerating snapshots only.\n")
        else:
            seed_customer(db)
            seed_checklist(db)
            seed_gsc(db)
            seed_ai_mentions(db)
            seed_reviews_and_places(db)
            seed_domain_authority(db)
            seed_content(db)
            seed_portal_login(db)
            print()

        seed_admin_login(db)  # idempotent — ensures the demo admin exists even on a re-run
        generate_snapshots(db)
        print(f"\nDone. DB: {args.db}")
        print(f"Portal login:  http://127.0.0.1:5199/portal/login  "
              f"(username={PORTAL_USERNAME!r}, password={PORTAL_PASSWORD!r})")
        print(f"Admin login:   http://127.0.0.1:5199/login  "
              f"(username={ADMIN_USERNAME!r}, password={ADMIN_PASSWORD!r})")
        print(f"Admin customer page: /customer/{CUSTOMER_ID}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
