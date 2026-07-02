"""GEO Agent — Monthly SEO & AEO optimizer for any business type.

Crawls customer websites, analyzes content with Claude 4.6,
generates llms.txt + schema markup, and publishes updates.

Usage:
    # Run for all customers (stage only — default)
    python -m geo_agent.main

    # Run for a single customer
    python -m geo_agent.main --customer hilltop-dental

    # Dry run (analyze but don't stage or publish)
    python -m geo_agent.main --dry-run

    # Stage changes for approval (default behavior)
    python -m geo_agent.main --stage

    # Publish approved staged changes
    python -m geo_agent.main --publish

    # Force-publish without approval (emergencies only)
    python -m geo_agent.main --force-publish

    # Use DB instead of customers.json
    python -m geo_agent.main --use-db --customer downtown-dental
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from geo_agent.business_profiles import get_profile
from geo_agent.config import Customer, load_customers
from geo_agent.crawler import get_crawler
from geo_agent.validators.business_type_check import validate_output, validate_schema_type
from geo_agent.embeddings import embed_texts
from geo_agent.google_places import verify_customer, VerifiedBusinessData, CompetitorData
from geo_agent.rag_store import CustomerRAG
from geo_agent.analyzer import analyze_and_recommend
from geo_agent.generators.llms_txt import generate_llms_txt, generate_llms_full_txt
from geo_agent.generators.schema_markup import (
    generate_all_schemas,
    generate_faq_schema,
    schema_to_js_injection,
    schema_to_script_tag,
)
from geo_agent.generators.robots_txt import generate_robots_txt
from geo_agent.publishers.webflow import WebflowPublisher
from geo_agent.privacy import minimize_for_embedding
from geo_agent.staging import StagingManager
from geo_agent.content_recommender import generate_content_recommendations, track_content_freshness
from geo_agent.competitive_intel import check_competitor_reviews
from geo_agent.schema_validator import validate_site_schema

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("geo_agent")


class AuditLogger:
    """Write structured audit logs for every customer operation.

    Logs WHO accessed WHAT customer data, WHEN, and WHAT changed.
    Never logs secrets or raw API keys — only hashed fingerprints.
    """

    def __init__(self, log_dir: str = "/app/data/audit_logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def log(self, customer_id: str, action: str, details: dict | None = None):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "customer_id": customer_id,
            "action": action,
            "details": details or {},
        }
        # Append to per-day audit log
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_file = self.log_dir / f"audit_{date_str}.jsonl"
        with open(log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
        logger.debug(f"AUDIT: [{customer_id}] {action}")

    def log_credential_access(self, customer_id: str, credential_type: str, key_value: str):
        """Log credential access with a fingerprint (NOT the raw key)."""
        fingerprint = hashlib.sha256(key_value.encode()).hexdigest()[:12] if key_value else "empty"
        self.log(customer_id, "credential_access", {
            "credential_type": credential_type,
            "key_fingerprint": fingerprint,
        })


def _get_platform(customer: Customer) -> str:
    """Determine the customer's platform."""
    # Check if customer has a platform attribute (from DB-backed customers)
    if hasattr(customer, "platform"):
        return customer.platform
    # Default: if they have a webflow site ID, it's webflow
    if customer.webflow_site_id:
        return "webflow"
    return "generic"


def process_customer(
    customer: Customer,
    dry_run: bool = False,
    stage_only: bool = False,
    output_base: str | None = None,
    data_dir: str | None = None,
    db=None,
    run_id: int | None = None,
    resume_from: str | None = None,
) -> dict:
    """Run the full GEO optimization pipeline for one customer.

    Args:
        customer: Customer configuration.
        dry_run: If True, analyze but don't stage or publish.
        stage_only: If True, stage changes but don't publish (default flow).
        output_base: Base directory for output files.
        data_dir: Base data directory.
        db: Optional CustomerDB instance for recording runs.

    Returns a summary dict of what was done.
    """
    data_dir = data_dir or "/app/data"
    audit = AuditLogger(log_dir=str(Path(data_dir) / ".." / "audit_logs"))
    staging = StagingManager(data_dir=data_dir)

    # Resolve business profile early — used throughout the pipeline
    profile = get_profile(customer)

    mode_label = "[DRY RUN] " if dry_run else "[STAGE] " if stage_only else ""
    logger.info(f"{mode_label}Processing: {customer.name} ({customer.domain}) [{profile.industry_label}]")
    audit.log(customer.id, "pipeline_start", {
        "dry_run": dry_run, "stage_only": stage_only,
        "domain": customer.domain, "business_type": profile.industry,
    })

    # Create a run record in DB if available
    if run_id is None and db:
        run_id = db.create_run(customer.id)
        db.init_run_steps(run_id)

    # Step tracking helpers
    def _should_run(step_name: str) -> bool:
        """Check if this step should run (for resume-from support)."""
        if not resume_from:
            return True
        step_names = [s[0] for s in db.PIPELINE_STEPS] if db else []
        if step_name not in step_names or resume_from not in step_names:
            return True
        return step_names.index(step_name) >= step_names.index(resume_from)

    def _start(step_name: str):
        if db and run_id:
            db.start_step(run_id, step_name)

    def _finish(step_name: str, status="success", log_text="", result=None, error_message=""):
        if db and run_id:
            db.finish_step(run_id, step_name, status=status, log_text=log_text, result=result, error_message=error_message)

    def _skip(step_name: str, reason=""):
        if db and run_id:
            db.skip_step(run_id, step_name, reason=reason)

    summary = {
        "customer": customer.name,
        "domain": customer.domain,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pages_crawled": 0,
        "changes": [],
        "errors": [],
    }

    # --- Step 1: Crawl website ---
    platform = _get_platform(customer)
    logger.info(f"Step 1: Crawling {platform} site")

    if platform == "webflow" and customer.webflow_api_key:
        audit.log_credential_access(customer.id, "webflow_api_key", customer.webflow_api_key)

    crawler = None
    if not _should_run("crawl"):
        _skip("crawl", "Skipped (resuming from later step)")
        # Still need pages for later steps — load from last output
        output_dir = Path(output_base or (data_dir + "/output")) / customer.id
        pages = []
        logger.info("  Crawl skipped — will use cached data")
    else:
        _start("crawl")
        try:
            crawler = get_crawler(
                platform=platform,
                domain=customer.domain,
                api_key=customer.webflow_api_key,
                site_id=customer.webflow_site_id,
                business_type=profile.industry,
                service_keywords=profile.service_keywords,
            )
            pages = crawler.get_pages()
            summary["pages_crawled"] = len(pages)
            logger.info(f"  Crawled {len(pages)} pages")
            audit.log(customer.id, "crawl_complete", {"pages_found": len(pages), "platform": platform})
            _finish("crawl", result={"pages_found": len(pages), "platform": platform})
        except Exception as e:
            if crawler:
                crawler.close()
                crawler = None
            # Fall back to generic crawler if platform-specific one fails
            if platform != "generic":
                logger.warning(f"  {platform} crawler failed ({type(e).__name__}), falling back to generic")
                try:
                    crawler = get_crawler(
                        platform="generic",
                        domain=customer.domain,
                    )
                    pages = crawler.get_pages()
                    summary["pages_crawled"] = len(pages)
                    logger.info(f"  Crawled {len(pages)} pages (generic fallback)")
                    audit.log(customer.id, "crawl_complete", {"pages_found": len(pages), "platform": "generic"})
                    _finish("crawl", result={"pages_found": len(pages), "platform": "generic"})
                except Exception as e2:
                    logger.error(f"  Crawl failed for {customer.id}: {type(e2).__name__}")
                    summary["errors"].append(f"Crawl failed: {type(e2).__name__}")
                    audit.log(customer.id, "crawl_failed", {"error": type(e2).__name__})
                    _finish("crawl", status="failed", error_message=str(e2))
                    if db and run_id:
                        db.update_run(run_id, status="failed", errors=summary["errors"])
                    return summary
            else:
                logger.error(f"  Crawl failed for {customer.id}: {type(e).__name__}")
                summary["errors"].append(f"Crawl failed: {type(e).__name__}")
                audit.log(customer.id, "crawl_failed", {"error": type(e).__name__})
                _finish("crawl", status="failed", error_message=str(e))
                if db and run_id:
                    db.update_run(run_id, status="failed", errors=summary["errors"])
                return summary
        finally:
            if crawler:
                crawler.close()

        if not pages:
            logger.warning("  No pages found — skipping")
            summary["errors"].append("No pages found on site")
            if db and run_id:
                db.update_run(run_id, status="failed", errors=summary["errors"])
            return summary

    # --- Step 1.5: Verify business data via Google Places ---
    logger.info("Step 1.5: Verifying business data via Google Places")
    verified_data: VerifiedBusinessData | None = None
    competitors: list[CompetitorData] = []
    if not _should_run("places"):
        _skip("places", "Skipped (resuming from later step)")
    else:
        _start("places")
        try:
            verified_data, competitors = verify_customer(customer)
            if verified_data:
                audit.log(customer.id, "places_verified", {
                    "match_confidence": verified_data.match_confidence,
                    "rating": verified_data.rating,
                    "review_count": verified_data.review_count,
                    "competitors_found": len(competitors),
                })
                logger.info(
                    f"  Verified: {verified_data.name} — "
                    f"{verified_data.rating} stars ({verified_data.review_count} reviews), "
                    f"{len(competitors)} competitors found"
                )

                # Update DB with Places data
                if db:
                    db.upsert_google_places(
                        customer_id=customer.id,
                        place_id=verified_data.place_id,
                        rating=verified_data.rating,
                        review_count=verified_data.review_count,
                        match_confidence=verified_data.match_confidence,
                        lat=verified_data.lat,
                        lng=verified_data.lng,
                    )
                    db.replace_competitors(customer.id, [
                        {"name": c.name, "rating": c.rating, "review_count": c.review_count,
                         "address": c.address, "place_id": c.place_id}
                        for c in competitors
                    ])
                _finish("places", result={
                    "rating": verified_data.rating,
                    "review_count": verified_data.review_count,
                    "competitors": len(competitors),
                })
            else:
                logger.info("  Google Places verification not available — continuing without")
                _finish("places", log_text="Google Places verification not available")
        except Exception as e:
            logger.warning(f"  Google Places verification failed: {type(e).__name__} — continuing without")
            audit.log(customer.id, "places_verification_failed", {"error": type(e).__name__})
            _finish("places", status="failed", error_message=str(e))

    # --- Step 2: Update RAG store ---
    logger.info("Step 2: Updating RAG store")
    rag = None
    if not _should_run("rag"):
        _skip("rag", "Skipped (resuming from later step)")
    else:
        _start("rag")
        try:
            rag = CustomerRAG(customer.id, data_dir=data_dir + "/customers" if not data_dir.endswith("/customers") else data_dir)
            # Minimize PII before sending to external embedding service
            page_texts = [minimize_for_embedding(p.content) for p in pages]
            embeddings = embed_texts(page_texts)

            for page, embedding in zip(pages, embeddings):
                rag.upsert_page(
                    page_id=page.id,
                    url=page.url,
                    title=page.title,
                    content=page.content,
                    embedding=embedding,
                    category=page.category,
                )
            logger.info(f"  Stored {len(pages)} pages with embeddings")
            _finish("rag", result={"pages_stored": len(pages)})
        except Exception as e:
            logger.error(f"  RAG update failed for {customer.id}: {type(e).__name__}")
            summary["errors"].append(f"RAG update failed: {type(e).__name__}")
            _finish("rag", status="failed", error_message=str(e))
            # Continue without RAG — we still have the crawled pages
            rag = None

    # --- Step 3: Analyze with Claude ---
    logger.info("Step 3: Analyzing with Claude 4.6")
    audit.log(customer.id, "claude_analysis_start", {"page_count": len(pages)})
    if not _should_run("analysis"):
        _skip("analysis", "Skipped (resuming from later step)")
        analysis = {}
    else:
        _start("analysis")
        try:
            analysis = analyze_and_recommend(customer, pages, verified_data=verified_data, competitors=competitors)
            summary["content_gaps"] = len(analysis.get("content_gaps", []))
            summary["faq_sets"] = len(analysis.get("faq_entries", {}))
            summary["priority_actions"] = analysis.get("priority_actions", [])

            # Check for grading issues — block publish if any are critical
            grading_issues = analysis.get("_grading_issues", [])
            blocked_issues = [i for i in grading_issues if i.startswith("BLOCKED:")]
            if blocked_issues:
                for issue in blocked_issues:
                    summary["errors"].append(f"Grading: {issue}")
                audit.log(customer.id, "analysis_blocked", {"issues": blocked_issues})
                logger.error(f"  Analysis blocked by grading: {len(blocked_issues)} critical issue(s)")
            if grading_issues:
                summary["grading_warnings"] = len(grading_issues) - len(blocked_issues)

            logger.info(f"  Analysis complete: {summary['content_gaps']} gaps, {summary['faq_sets']} FAQ sets")
            audit.log(customer.id, "claude_analysis_complete", {
                "gaps": summary["content_gaps"], "faq_sets": summary["faq_sets"],
                "grading_issues": len(grading_issues),
            })
            _finish("analysis", result={
                "content_gaps": summary["content_gaps"],
                "faq_sets": summary["faq_sets"],
                "grading_issues": len(grading_issues),
            })
        except Exception as e:
            import traceback
            logger.error(f"  Analysis failed for {customer.id}: {type(e).__name__}: {e}")
            logger.error(traceback.format_exc())
            summary["errors"].append(f"Analysis failed: {type(e).__name__}: {e}")
            audit.log(customer.id, "claude_analysis_failed", {"error": f"{type(e).__name__}: {e}"})
            _finish("analysis", status="failed", error_message=str(e))
            analysis = {}

    # --- Step 3.5: Generate content recommendations ---
    logger.info("Step 3.5: Generating content recommendations")
    if not _should_run("content_recs"):
        _skip("content_recs", "Skipped (resuming from later step)")
    else:
        _start("content_recs")
        try:
            existing_recs = []
            if db:
                existing_recs = db.get_content_recommendations(customer.id)

            content_recs = generate_content_recommendations(customer, pages, existing_recs=existing_recs)

            # Track content freshness
            stale_pages = track_content_freshness(pages)
            if stale_pages:
                summary["stale_pages"] = len(stale_pages)
                logger.info(f"  Found {len(stale_pages)} stale page(s) needing freshness updates")

            # Save recommendations to DB
            if db and content_recs:
                for rec in content_recs:
                    db.add_content_recommendation(rec.to_dict())
                summary["content_recommendations"] = len(content_recs)
                logger.info(f"  Generated {len(content_recs)} content recommendations")
                audit.log(customer.id, "content_recs_generated", {
                    "count": len(content_recs),
                    "types": list({r.rec_type for r in content_recs}),
                    "stale_pages": len(stale_pages),
                })
            elif content_recs:
                # Save to file if no DB
                recs_file = Path(output_base or (data_dir + "/output")) / customer.id / "content_recommendations.json"
                recs_file.parent.mkdir(parents=True, exist_ok=True)
                recs_file.write_text(json.dumps([r.to_dict() for r in content_recs], indent=2))
                summary["content_recommendations"] = len(content_recs)
                logger.info(f"  Generated {len(content_recs)} content recommendations (saved to file)")
            _finish("content_recs", result={
                "recommendations": len(content_recs) if content_recs else 0,
                "stale_pages": len(stale_pages) if stale_pages else 0,
            })
        except Exception as e:
            logger.warning(f"  Content recommendations failed: {type(e).__name__} — continuing")
            audit.log(customer.id, "content_recs_failed", {"error": type(e).__name__})
            _finish("content_recs", status="failed", error_message=str(e))

    # --- Step 3.6: Competitor intelligence ---
    logger.info("Step 3.6: Checking competitor activity")
    if not _should_run("competitor"):
        _skip("competitor", "Skipped (resuming from later step)")
    else:
        _start("competitor")
        try:
            comp_alerts = check_competitor_reviews(db, customer.id) if db else []
            if comp_alerts and db:
                for alert in comp_alerts:
                    db.add_alert(
                        customer_id=customer.id,
                        alert_type=alert.alert_type,
                        severity=alert.severity,
                        source=alert.competitor_name,
                        message=alert.message,
                        details=alert.details,
                    )
                summary["competitor_alerts"] = len(comp_alerts)
                logger.info(f"  {len(comp_alerts)} competitor alert(s) generated")
                audit.log(customer.id, "competitor_check_complete", {"alerts": len(comp_alerts)})
            _finish("competitor", result={"alerts": len(comp_alerts) if comp_alerts else 0})
        except Exception as e:
            logger.warning(f"  Competitor check failed: {type(e).__name__} — continuing")
            _finish("competitor", status="failed", error_message=str(e))

    # --- Step 3.7: Schema validation ---
    logger.info("Step 3.7: Validating live schema markup")
    if not _should_run("schema_validation"):
        _skip("schema_validation", "Skipped (resuming from later step)")
    else:
        _start("schema_validation")
        try:
            schema_results = validate_site_schema(customer.domain)
            issues_count = sum(len(r.issues) for r in schema_results)
            error_results = [r for r in schema_results if r.status in ("error", "missing")]

            if error_results and db:
                for r in error_results:
                    db.add_alert(
                        customer_id=customer.id,
                        alert_type="schema_invalid",
                        severity="warning" if r.status == "missing" else "critical",
                        source=r.url,
                        message=f"Schema {r.status} on {r.url}: {'; '.join(r.issues[:3])}",
                        details=r.to_dict(),
                    )

            summary["schema_valid"] = sum(1 for r in schema_results if r.status == "valid")
            summary["schema_issues"] = issues_count
            logger.info(
                f"  Schema: {summary['schema_valid']}/{len(schema_results)} pages valid, "
                f"{issues_count} issue(s)"
            )
            audit.log(customer.id, "schema_validation_complete", {
                "pages_checked": len(schema_results),
                "valid": summary["schema_valid"],
                "issues": issues_count,
            })
            _finish("schema_validation", result={
                "pages_checked": len(schema_results),
                "valid": summary.get("schema_valid", 0),
                "issues": issues_count,
            })
        except Exception as e:
            logger.warning(f"  Schema validation failed: {type(e).__name__} — continuing")
            _finish("schema_validation", status="failed", error_message=str(e))

    # --- Step 4: Generate files ---
    logger.info("Step 4: Generating llms.txt, schema, robots.txt")
    llms_txt = llms_full_txt = schema_html = robots_txt = ""
    if not _should_run("generate"):
        _skip("generate", "Skipped (resuming from later step)")
    else:
        _start("generate")
        try:
            # Adapt over time: feed queries AI isn't citing us on into llms.txt as
            # FAQ entries, answered from verified facts where possible.
            extra_faqs = []
            if db:
                try:
                    from geo_agent.generators.llms_txt import _answer_seed_faq
                    prof = get_profile(customer)
                    for gap in db.get_uncited_prompts(customer.id)[:6]:
                        ans = _answer_seed_faq(gap["prompt"], customer, prof)
                        if ans:
                            extra_faqs.append((gap["prompt"].rstrip("?").strip() + "?", ans))
                    if extra_faqs:
                        logger.info(f"  Adaptation: added {len(extra_faqs)} FAQ(s) for uncited queries")
                except Exception as e:
                    logger.warning(f"  Adaptation feed skipped: {e}")

            llms_txt = generate_llms_txt(customer, pages, verified_data=verified_data, extra_faqs=extra_faqs)
            llms_full_txt = generate_llms_full_txt(customer, pages)
            is_webflow = customer.platform == "webflow"

            # On-page FAQPage schema from the same Q&A used in llms.txt (corroboration).
            analysis_faqs = []
            for _url, fqs in analysis.get("faq_entries", {}).items():
                for f in (fqs or []):
                    if isinstance(f, dict) and f.get("question") and f.get("answer"):
                        analysis_faqs.append((f["question"], f["answer"]))
            schema_faqs = analysis_faqs + extra_faqs
            schema_html = generate_all_schemas(
                customer, verified_data=verified_data, webflow_safe=is_webflow,
                faqs=schema_faqs or None,
            )
            robots_txt = generate_robots_txt(customer)

            summary["changes"].append(f"Generated llms.txt ({len(llms_txt)} bytes)")
            summary["changes"].append(f"Generated llms-full.txt ({len(llms_full_txt)} bytes)")
            summary["changes"].append(f"Generated schema markup ({schema_html.count('application/ld+json')} blocks)")
            summary["changes"].append(f"Generated robots.txt ({len(robots_txt)} bytes)")

            # --- Post-generation validation: check for business-type contamination ---
            generated_files = {
                "llms.txt": llms_txt,
                "llms-full.txt": llms_full_txt,
                "schema.html": schema_html,
                "robots.txt": robots_txt,
            }
            bt_warnings = validate_output(profile, generated_files, business_type=getattr(customer, "business_type", ""))
            bt_warnings += validate_schema_type(profile, schema_html)
            if bt_warnings:
                logger.warning(f"  Business-type validation: {len(bt_warnings)} warning(s)")
                for w in bt_warnings:
                    logger.warning(f"    {w}")
                summary["business_type_warnings"] = bt_warnings
                audit.log(customer.id, "business_type_validation", {
                    "warnings": len(bt_warnings),
                    "details": bt_warnings[:10],
                })

            # Save generated files locally
            output_dir = Path(output_base or (data_dir + "/output")) / customer.id
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "llms.txt").write_text(llms_txt)
            (output_dir / "llms-full.txt").write_text(llms_full_txt)
            (output_dir / "schema.html").write_text(schema_html)
            (output_dir / "robots.txt").write_text(robots_txt)
            (output_dir / "analysis.json").write_text(json.dumps(analysis, indent=2))
            logger.info(f"  Files saved to {output_dir}")
            _finish("generate", result={
                "llms_txt_bytes": len(llms_txt),
                "schema_blocks": schema_html.count("application/ld+json"),
            })
        except Exception as e:
            logger.error(f"  File generation failed for {customer.id}: {type(e).__name__}")
            summary["errors"].append(f"File generation failed: {type(e).__name__}")
            _finish("generate", status="failed", error_message=str(e))
            if db and run_id:
                db.update_run(run_id, status="failed", errors=summary["errors"])
            return summary

    if dry_run:
        logger.info("  DRY RUN — skipping stage/publish")
        summary["changes"].append("DRY RUN — nothing staged or published")
        audit.log(customer.id, "pipeline_complete", {"dry_run": True, "changes": len(summary["changes"])})
        _skip("stage", "Dry run")
        _skip("publish", "Dry run")
        if rag:
            rag.log_run(
                changes=json.dumps(summary["changes"]),
                llms_txt=llms_txt,
                schema_updates=schema_html[:500],
            )
            rag.close()
        if db and run_id:
            db.update_run(run_id, status="dry_run", pages_crawled=len(pages),
                          changes=summary["changes"], errors=summary["errors"])
        return summary

    # --- Step 5: Stage changes ---
    logger.info("Step 5: Staging changes for approval")
    if not _should_run("stage"):
        _skip("stage", "Skipped (resuming from later step)")
    else:
        _start("stage")
        try:
            staged_files = {
                "llms.txt": llms_txt,
                "llms-full.txt": llms_full_txt,
                "schema.html": schema_html,
                "robots.txt": robots_txt,
            }
            staging.stage_changes(customer.id, staged_files)
            diff_report = staging.generate_diff_report(customer.id)
            summary["changes"].append("Changes staged for approval")
            audit.log(customer.id, "changes_staged", {"files": list(staged_files.keys())})
            _finish("stage", result={"files_staged": len(staged_files)})
        except Exception as e:
            logger.error(f"  Staging failed for {customer.id}: {type(e).__name__}")
            summary["errors"].append(f"Staging failed: {type(e).__name__}")
            _finish("stage", status="failed", error_message=str(e))

    if db and run_id:
        db.update_run(run_id, status="staged", pages_crawled=len(pages),
                      changes=summary["changes"], errors=summary["errors"])

    if stage_only:
        logger.info("  STAGE ONLY — awaiting approval before publish")
        _skip("publish", "Stage only — awaiting approval")
        if rag:
            rag.log_run(
                changes=json.dumps(summary["changes"]),
                llms_txt=llms_txt,
                schema_updates=schema_html[:500],
            )
            rag.close()
        return summary

    # --- Step 6: Publish (only if not stage_only) ---
    logger.info("Step 6: Publishing")
    _start("publish")
    try:
        _publish_for_platform(customer, platform, schema_html, summary, audit)

        # Mark as published
        staging.approve_changes(customer.id)
        staging.publish_staged(customer.id)
        if db and run_id:
            db.approve_run(run_id)
            db.mark_run_published(run_id)
        _finish("publish", result={"platform": platform})
    except Exception as e:
        logger.error(f"  Publish failed for {customer.id}: {type(e).__name__}")
        summary["errors"].append(f"Publish failed: {type(e).__name__}")
        _finish("publish", status="failed", error_message=str(e))

    # Log the run
    if rag:
        rag.log_run(
            changes=json.dumps(summary["changes"]),
            llms_txt=llms_txt,
            schema_updates=schema_html[:500],
        )
        rag.close()

    audit.log(customer.id, "pipeline_complete", {
        "changes": len(summary["changes"]),
        "errors": len(summary["errors"]),
    })
    logger.info(f"Done: {customer.name} — {len(summary['changes'])} changes, {len(summary['errors'])} errors")
    return summary


def _publish_for_platform(customer: Customer, platform: str, schema_html: str, summary: dict, audit: AuditLogger):
    """Handle publishing based on the customer's platform."""
    if platform == "webflow":
        audit.log_credential_access(customer.id, "webflow_api_key", customer.webflow_api_key)
        audit.log(customer.id, "publish_start", {"site_id": customer.webflow_site_id, "platform": "webflow"})
        publisher = None
        try:
            publisher = WebflowPublisher(
                api_key=customer.webflow_api_key,
                site_id=customer.webflow_site_id,
            )

            if publisher.inject_schema_to_site(schema_html):
                summary["changes"].append("Schema markup published to Webflow")
                audit.log(customer.id, "schema_injected", {"schema_blocks": schema_html.count("application/ld+json")})
            else:
                summary["errors"].append("Failed to inject schema to Webflow")

            if publisher.publish_site():
                summary["changes"].append("Webflow site published")
            else:
                summary["errors"].append("Failed to publish Webflow site")
        except Exception as e:
            logger.error(f"  Publish failed for {customer.id}: {type(e).__name__}")
            summary["errors"].append(f"Publish failed: {type(e).__name__}")
            audit.log(customer.id, "publish_failed", {"error": type(e).__name__})
        finally:
            if publisher:
                publisher.close()

    elif platform == "squarespace":
        # Squarespace: schema via API if available, llms.txt via Cloudflare
        audit.log(customer.id, "publish_start", {"platform": "squarespace"})
        try:
            from geo_agent.publishers.squarespace import SquarespacePublisher
            from geo_agent.secrets import get_secrets
            secrets = get_secrets()
            sq_api_key = secrets.get_customer_secret(customer.id, "SQUARESPACE_KEY")
            if sq_api_key:
                publisher = SquarespacePublisher(api_key=sq_api_key)
                if publisher.inject_schema_to_site(schema_html):
                    summary["changes"].append("Schema markup published to Squarespace")
                else:
                    summary["errors"].append("Failed to inject schema to Squarespace")
                publisher.close()
            else:
                summary["changes"].append("Squarespace schema: manual injection needed (no API key)")
                logger.info("  No Squarespace API key — schema needs manual injection")
        except Exception as e:
            logger.error(f"  Squarespace publish failed: {type(e).__name__}")
            summary["errors"].append(f"Squarespace publish failed: {type(e).__name__}")

    elif platform == "wordpress":
        # WordPress: schema + files via PracticeRank plugin REST API
        audit.log(customer.id, "publish_start", {"platform": "wordpress"})
        try:
            from geo_agent.publishers.wordpress import WordPressPublisher
            from geo_agent.secrets import get_secrets
            secrets = get_secrets()
            wp_api_key = secrets.get_customer_secret(customer.id, "WP_API_KEY")
            if wp_api_key:
                publisher = WordPressPublisher(
                    site_url=f"https://{customer.domain}",
                    api_key=wp_api_key,
                )
                health = publisher.health_check()
                if health:
                    # Parse schema HTML back into JSON-LD dicts for the WP API
                    import re
                    import json as _json
                    schema_blocks = re.findall(
                        r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>',
                        schema_html, re.DOTALL,
                    )
                    global_schemas = []
                    for block in schema_blocks:
                        try:
                            global_schemas.append(_json.loads(block.strip()))
                        except _json.JSONDecodeError:
                            pass

                    if global_schemas:
                        result = publisher.push_schema(global_schemas=global_schemas)
                        if result:
                            summary["changes"].append("Schema markup published to WordPress")
                            audit.log(customer.id, "schema_injected", {"schema_blocks": len(global_schemas)})
                        else:
                            summary["errors"].append("Failed to push schema to WordPress")
                    else:
                        summary["changes"].append("No schema blocks to push")
                else:
                    summary["errors"].append("WordPress PracticeRank plugin unreachable")
                publisher.close()
            else:
                summary["changes"].append("WordPress: no WP_API_KEY configured — manual publish needed")
                logger.info("  No WP_API_KEY — schema needs manual injection")
        except Exception as e:
            logger.error(f"  WordPress publish failed: {type(e).__name__}: {e}")
            summary["errors"].append(f"WordPress publish failed: {type(e).__name__}")

    else:
        # Generic platform: just stage files, manual publish needed
        summary["changes"].append(f"Files generated for {platform} — manual publish needed")
        logger.info(f"  Platform '{platform}': manual publishing required")


def publish_approved(data_dir: str | None = None, db=None):
    """Publish all approved staged content."""
    data_dir = data_dir or "/app/data"
    staging = StagingManager(data_dir=data_dir)

    staging_base = Path(data_dir) / "staging"
    if not staging_base.exists():
        logger.info("No staging directory found")
        return

    for customer_dir in staging_base.iterdir():
        if not customer_dir.is_dir():
            continue
        customer_id = customer_dir.name

        if staging.is_approved(customer_id):
            logger.info(f"Publishing approved changes for {customer_id}")
            published = staging.publish_staged(customer_id)
            if published and db:
                latest_run = db.get_latest_run(customer_id)
                if latest_run and latest_run["status"] == "approved":
                    db.mark_run_published(latest_run["id"])
            logger.info(f"  Published {len(published)} files")
        else:
            logger.info(f"  {customer_id}: not yet approved — skipping")


def _validate() -> int:
    """Lightweight health check: verify imports and sqlite-vec load."""
    import sqlite3 as _sql
    import sqlite_vec as _sv

    db = _sql.connect(":memory:")
    db.enable_load_extension(True)
    _sv.load(db)
    db.enable_load_extension(False)
    ver = db.execute("SELECT vec_version()").fetchone()[0]
    db.close()
    logger.info(f"Validate OK — sqlite-vec {ver}")
    return 0


def main():
    parser = argparse.ArgumentParser(description="PracticeRank GEO Agent")
    parser.add_argument("--customer", help="Process only this customer ID")
    parser.add_argument("--dry-run", action="store_true", help="Analyze but don't stage or publish")
    parser.add_argument("--stage", action="store_true", help="Stage changes for approval (default behavior)")
    parser.add_argument("--publish", action="store_true", help="Publish approved staged changes")
    parser.add_argument("--force-publish", action="store_true", help="Skip approval and publish immediately")
    parser.add_argument("--config", help="Path to customers.json")
    parser.add_argument("--use-db", action="store_true", help="Load customers from SQLite DB instead of JSON")
    parser.add_argument("--db-path", help="Path to SQLite database file")
    parser.add_argument("--data-dir", help="Base data directory")
    parser.add_argument("--validate", action="store_true", help="Health check: verify imports and exit")
    parser.add_argument("--run-id", type=int, help="Existing run ID (for retry)")
    parser.add_argument("--resume-from", help="Resume pipeline from this step (for retry)")
    args = parser.parse_args()

    if args.validate:
        sys.exit(_validate())

    data_dir = args.data_dir or str(Path(__file__).resolve().parent.parent / "data")

    # Load customer DB if requested
    customer_db = None
    if args.use_db or args.db_path:
        from geo_agent.db import CustomerDB
        customer_db = CustomerDB(db_path=args.db_path)

    # Handle --publish mode: publish already-approved staged content
    if args.publish:
        publish_approved(data_dir=data_dir, db=customer_db)
        if customer_db:
            if not args.customer:  # bulk (cron) publish, not a single manual customer
                customer_db.record_job_run("monthly_publish")
            customer_db.close()
        return

    # Load customers
    if customer_db:
        if args.customer:
            config_customer = customer_db.to_config_customer(args.customer)
            if not config_customer:
                logger.error(f"Customer not found in DB: {args.customer}")
                sys.exit(1)
            customers = [config_customer]
        else:
            all_customers = customer_db.list_customers(status="active")
            customers = []
            for c in all_customers:
                cc = customer_db.to_config_customer(c["id"])
                if cc:
                    customers.append(cc)
    else:
        customers = load_customers(args.config)
        if args.customer:
            customers = [c for c in customers if c.id == args.customer]
            if not customers:
                logger.error(f"Customer not found: {args.customer}")
                sys.exit(1)

    logger.info(f"GEO Agent starting — {len(customers)} customer(s) to process")

    # Determine mode
    stage_only = not args.force_publish  # Default is stage-only

    results = []
    for customer in customers:
        try:
            result = process_customer(
                customer,
                dry_run=args.dry_run,
                stage_only=stage_only,
                data_dir=data_dir,
                db=customer_db,
                run_id=args.run_id,
                resume_from=args.resume_from,
            )
            results.append(result)
        except Exception as e:
            # Log only customer ID and error type — never PII in log messages
            logger.error(f"Unhandled error processing {customer.id}: {type(e).__name__}")
            logger.debug(f"Details for {customer.id}: {e}", exc_info=True)
            results.append({
                "customer": customer.name,
                "errors": [f"Unhandled error: {type(e).__name__}"],
            })

    if customer_db:
        if not args.customer:  # bulk (cron) stage run over all active customers
            _ok = sum(1 for r in results if not r.get("errors"))
            customer_db.record_job_run(
                "monthly_stage",
                status="ok" if _ok == len(results) else "partial",
                detail=f"{_ok}/{len(results)} ok",
            )
        customer_db.checkpoint()
        customer_db.close()

    # Print summary
    print("\n" + "=" * 60)
    print("GEO Agent Run Summary")
    print("=" * 60)
    for r in results:
        status = "OK" if not r.get("errors") else "ERRORS"
        print(f"\n[{status}] {r.get('customer', 'Unknown')}")
        for change in r.get("changes", []):
            print(f"  + {change}")
        for error in r.get("errors", []):
            print(f"  ! {error}")
        for action in r.get("priority_actions", [])[:3]:
            if isinstance(action, str):
                print(f"  >> {action}")
    print()


if __name__ == "__main__":
    main()
