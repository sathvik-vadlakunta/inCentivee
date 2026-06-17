"""Site auditor — technical SEO checks using PageSpeed Insights API + custom checks.

Uses free APIs (no keys needed for basic PageSpeed) and direct HTTP checks
to generate VA-friendly audit reports with fix instructions.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

_PSI_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"


def _run_pagespeed(domain: str, strategy: str = "mobile") -> dict | None:
    """Run PageSpeed Insights and return Lighthouse scores + audits."""
    # Try with and without www prefix
    urls = [f"https://{domain}", f"https://www.{domain}"]
    if domain.startswith("www."):
        urls = [f"https://{domain}", f"https://{domain.removeprefix('www.')}"]
    api_key = os.environ.get("PAGESPEED_API_KEY", "")
    data = None
    try:
        with httpx.Client(timeout=30.0) as client:
            for url in urls:
                # PSI returns only the performance category unless others are
                # requested explicitly — ask for all four so SEO/a11y scores populate.
                params = {
                    "url": url,
                    "strategy": strategy,
                    "category": ["PERFORMANCE", "ACCESSIBILITY", "SEO", "BEST_PRACTICES"],
                }
                if api_key:  # keyless quota is near-zero; a free key gives ~25k/day
                    params["key"] = api_key
                resp = client.get(_PSI_URL, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    break
                logger.debug(f"PageSpeed API returned {resp.status_code} for {url}")
            if data is None:
                logger.warning(f"PageSpeed API failed for all URLs: {urls}")
                return None
    except Exception as e:
        logger.warning(f"PageSpeed API error for {domain}: {e}")
        return None

    lh = data.get("lighthouseResult", {})
    categories = lh.get("categories", {})
    scores = {}
    for key in ("performance", "accessibility", "seo", "best-practices"):
        cat = categories.get(key, {})
        scores[key.replace("-", "_")] = round((cat.get("score") or 0) * 100)

    return {"scores": scores, "audits": lh.get("audits", {})}


def _check_schema_markup(domain: str) -> list[dict]:
    """Check for JSON-LD schema markup on the homepage."""
    issues = []
    try:
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            resp = client.get(f"https://{domain}")
            html = resp.text.lower()
    except Exception as e:
        issues.append({
            "category": "schema", "severity": "warning",
            "title": "Could not fetch homepage",
            "description": f"Failed to load https://{domain}: {e}",
            "fix_instruction": "Check that the website is online and accessible.",
        })
        return issues

    if "application/ld+json" not in html:
        issues.append({
            "category": "schema", "severity": "critical",
            "title": "No JSON-LD schema markup found",
            "description": "No structured data (JSON-LD) detected on the homepage.",
            "fix_instruction": "Go to the SEO & GEO tab and run the agent to generate schema markup, then publish it.",
        })
    else:
        if "faqpage" not in html:
            issues.append({
                "category": "schema", "severity": "warning",
                "title": "No FAQ schema markup",
                "description": "LocalBusiness schema found but no FAQPage schema detected.",
                "fix_instruction": "Run the agent to generate FAQ schema from the customer's services, then publish.",
            })

    return issues


def _check_security_headers(domain: str) -> list[dict]:
    """Check for basic security headers."""
    issues = []
    try:
        with httpx.Client(timeout=10.0, follow_redirects=False) as client:
            # Check HTTPS redirect
            try:
                http_resp = client.get(f"http://{domain}")
                if http_resp.status_code not in (301, 302, 307, 308):
                    issues.append({
                        "category": "security", "severity": "critical",
                        "title": "No HTTP to HTTPS redirect",
                        "description": f"http://{domain} does not redirect to HTTPS.",
                        "fix_instruction": "Enable 'Always Use HTTPS' in Cloudflare SSL/TLS settings, or configure a redirect in the hosting platform.",
                    })
            except Exception:
                pass  # HTTP might not resolve, that's fine

            # Check HTTPS headers
            https_resp = client.get(f"https://{domain}", follow_redirects=True)
            headers = {k.lower(): v for k, v in https_resp.headers.items()}

            if "strict-transport-security" not in headers:
                issues.append({
                    "category": "security", "severity": "info",
                    "title": "No HSTS header",
                    "description": "The site does not send a Strict-Transport-Security header.",
                    "fix_instruction": "Enable HSTS in Cloudflare: SSL/TLS > Edge Certificates > Enable HSTS.",
                })

    except Exception as e:
        logger.debug(f"Security header check failed for {domain}: {e}")

    return issues


def _check_llms_txt(domain: str) -> list[dict]:
    """Check if llms.txt exists and has content."""
    issues = []
    try:
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            resp = client.get(f"https://{domain}/llms.txt")
            if resp.status_code != 200 or len(resp.text.strip()) < 50:
                issues.append({
                    "category": "seo", "severity": "warning",
                    "title": "No llms.txt file",
                    "description": "No llms.txt found at the root of the site. AI search engines use this for discoverability.",
                    "fix_instruction": "Run the agent to generate llms.txt, then publish via Cloudflare Worker.",
                })
    except Exception:
        issues.append({
            "category": "seo", "severity": "warning",
            "title": "Could not check llms.txt",
            "description": f"Failed to fetch https://{domain}/llms.txt",
            "fix_instruction": "Check that the site is accessible and run the agent to generate llms.txt.",
        })
    return issues


def _check_sitemap(domain: str) -> list[dict]:
    """Check for sitemap.xml presence."""
    issues = []
    try:
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            resp = client.get(f"https://{domain}/sitemap.xml")
            if resp.status_code != 200:
                issues.append({
                    "category": "seo", "severity": "warning",
                    "title": "No sitemap.xml found",
                    "description": f"https://{domain}/sitemap.xml returned {resp.status_code}.",
                    "fix_instruction": "Most CMS platforms auto-generate sitemaps. For Webflow: Site Settings > SEO > Enable Sitemap. For Squarespace: it's at /sitemap.xml by default.",
                })
            elif "<urlset" not in resp.text and "<sitemapindex" not in resp.text:
                issues.append({
                    "category": "seo", "severity": "warning",
                    "title": "Invalid sitemap.xml",
                    "description": "sitemap.xml exists but doesn't appear to be valid XML.",
                    "fix_instruction": "Check the sitemap URL directly in a browser. It should show XML with <urlset> or <sitemapindex> tags.",
                })
    except Exception:
        pass
    return issues


def _check_robots_txt(domain: str) -> list[dict]:
    """Check robots.txt for issues."""
    issues = []
    try:
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            resp = client.get(f"https://{domain}/robots.txt")
            if resp.status_code != 200:
                issues.append({
                    "category": "seo", "severity": "info",
                    "title": "No robots.txt found",
                    "description": f"https://{domain}/robots.txt returned {resp.status_code}.",
                    "fix_instruction": "Run the agent to generate robots.txt, then publish via Cloudflare Worker.",
                })
            else:
                # Only flag "blocks all crawlers" when `Disallow: /` applies to the
                # wildcard agent (User-agent: *). A `Disallow: /` under a specific bot
                # (e.g. GPTBot, ClaudeBot, Google-Extended) is our INTENTIONAL
                # training-bot block, not a site-wide block — don't false-positive on it.
                current_agents: list[str] = []
                prev_was_agent = False
                blocks_all = False
                for raw in resp.text.split("\n"):
                    line = raw.split("#", 1)[0].strip()
                    if not line:
                        continue
                    low = line.lower()
                    if low.startswith("user-agent:"):
                        if not prev_was_agent:
                            current_agents = []
                        current_agents.append(line.split(":", 1)[1].strip())
                        prev_was_agent = True
                    elif low.startswith(("disallow:", "allow:")):
                        prev_was_agent = False
                        if low.startswith("disallow:"):
                            path = line.split(":", 1)[1].strip()
                            if path == "/" and "*" in current_agents:
                                blocks_all = True
                                break
                if blocks_all:
                    issues.append({
                        "category": "seo", "severity": "critical",
                        "title": "robots.txt blocks all crawlers",
                        "description": "robots.txt contains 'Disallow: /' under 'User-agent: *', which blocks search engines from indexing the site.",
                        "fix_instruction": "This usually means the site is still in development mode. Update robots.txt to allow crawling.",
                    })
    except Exception:
        pass
    return issues


def _extract_pagespeed_issues(audits: dict, platform: str = "") -> list[dict]:
    """Extract actionable issues from PageSpeed Insights audits."""
    issues = []
    priority_audits = {
        "meta-description": {
            "category": "seo", "severity": "critical",
            "title": "Missing or inadequate meta descriptions",
            "fix_instruction": f"In {'Webflow: Pages > select page > SEO Settings > Meta Description' if platform == 'webflow' else 'your CMS: edit each page SEO settings to add a meta description'} (150-160 characters).",
        },
        "document-title": {
            "category": "seo", "severity": "critical",
            "title": "Missing or inadequate page title",
            "fix_instruction": f"In {'Webflow: Pages > select page > SEO Settings > Title Tag' if platform == 'webflow' else 'your CMS: edit the page title'} (50-60 characters, include primary keyword).",
        },
        "image-alt": {
            "category": "accessibility", "severity": "warning",
            "title": "Images missing alt text",
            "fix_instruction": f"In {'Webflow: select each image > Settings > Alt Text' if platform == 'webflow' else 'your CMS: add descriptive alt text to each image'}.",
        },
        "link-text": {
            "category": "seo", "severity": "info",
            "title": "Links do not have descriptive text",
            "fix_instruction": "Replace generic link text like 'click here' or 'learn more' with descriptive text that tells users and search engines what the link leads to.",
        },
        "is-crawlable": {
            "category": "seo", "severity": "critical",
            "title": "Page is not crawlable",
            "fix_instruction": "Check for a 'noindex' meta tag or X-Robots-Tag header. Remove it to allow search engines to index the page.",
        },
        "render-blocking-resources": {
            "category": "performance", "severity": "info",
            "title": "Render-blocking resources detected",
            "fix_instruction": "This is usually handled by the CMS. For custom code, defer non-critical CSS/JS.",
        },
        "uses-optimized-images": {
            "category": "performance", "severity": "warning",
            "title": "Images not optimized",
            "fix_instruction": "Compress images using WebP format. In Webflow, images are auto-optimized. For other platforms, use tools like TinyPNG before uploading.",
        },
    }

    for audit_id, meta in priority_audits.items():
        audit = audits.get(audit_id, {})
        score = audit.get("score")
        if score is not None and score < 1.0:
            desc = audit.get("title", meta["title"])
            if audit.get("displayValue"):
                desc += f" ({audit['displayValue']})"
            issues.append({
                "category": meta["category"],
                "severity": meta["severity"],
                "title": meta["title"],
                "description": desc,
                "fix_instruction": meta["fix_instruction"],
            })

    return issues


def run_site_audit(domain: str, platform: str = "") -> dict:
    """Run a comprehensive site audit. Returns scores dict + issues list."""
    all_issues: list[dict] = []

    # PageSpeed Insights (main scores + audit-based issues)
    psi = _run_pagespeed(domain)
    scores = {"performance": 0, "accessibility": 0, "seo": 0, "best_practices": 0}
    if psi:
        scores = psi["scores"]
        all_issues.extend(_extract_pagespeed_issues(psi.get("audits", {}), platform))

    # Custom checks
    all_issues.extend(_check_schema_markup(domain))
    all_issues.extend(_check_security_headers(domain))
    all_issues.extend(_check_llms_txt(domain))
    all_issues.extend(_check_sitemap(domain))
    all_issues.extend(_check_robots_txt(domain))

    # Sort: critical first, then warning, then info
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    all_issues.sort(key=lambda x: severity_order.get(x["severity"], 3))

    return {
        "scores": scores,
        "issues": all_issues,
        "audit_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "raw_data": psi or {},
    }
