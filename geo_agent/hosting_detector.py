"""Auto-detect DNS, hosting, and infrastructure details for a domain.

Returns a dict with: registrar, nameservers, hosting, web_server, cdn,
cms, a_record, cname, domain_expiry, and any detected details.
"""

from __future__ import annotations

import logging
import re
import subprocess
from datetime import datetime

import httpx

logger = logging.getLogger("practicerank.hosting")

# Known hosting/CDN signatures from HTTP headers
HOSTING_SIGNATURES = {
    "cloudfront": "Amazon CloudFront CDN",
    "amazons3": "Amazon S3",
    "netlify": "Netlify",
    "vercel": "Vercel",
    "fly.io": "Fly.io",
    "heroku": "Heroku",
    "squarespace": "Squarespace",
    "wpengine": "WP Engine",
    "pantheon": "Pantheon",
    "godaddy": "GoDaddy Hosting",
    "bluehost": "Bluehost",
    "siteground": "SiteGround",
    "cloudflare": "Cloudflare",
    "fastly": "Fastly CDN",
    "akamai": "Akamai CDN",
    "sucuri": "Sucuri WAF/CDN",
    "nginx": "Nginx",
    "apache": "Apache",
    "litespeed": "LiteSpeed",
    "microsoft-iis": "Microsoft IIS",
}

CMS_SIGNATURES = {
    "wp-content": "WordPress",
    "wp-includes": "WordPress",
    "wordpress": "WordPress",
    "squarespace": "Squarespace",
    "webflow": "Webflow",
    "wix.com": "Wix",
    "shopify": "Shopify",
    "drupal": "Drupal",
    "joomla": "Joomla",
    "ghost": "Ghost",
    "weebly": "Weebly",
    "duda": "Duda",
}

NAMESERVER_OWNERS = {
    "cloudflare": "Cloudflare",
    "godaddy": "GoDaddy",
    "domaincontrol": "GoDaddy",
    "awsdns": "Amazon Route 53",
    "google": "Google Cloud DNS",
    "digitalocean": "DigitalOcean",
    "netlify": "Netlify DNS",
    "vercel": "Vercel DNS",
    "namecheap": "Namecheap",
    "hostgator": "HostGator",
    "bluehost": "Bluehost",
    "hover": "Hover",
    "name.com": "Name.com",
    "squarespace": "Squarespace",
    "wix": "Wix",
    "dnsimple": "DNSimple",
}


def _run_cmd(cmd: list[str], timeout: int = 10) -> str:
    """Run a shell command and return stdout."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.stdout
    except Exception:
        return ""


def _detect_nameservers(domain: str) -> list[str]:
    """Get nameservers for a domain via dig."""
    out = _run_cmd(["dig", domain, "NS", "+short"])
    return [ns.strip().rstrip('.') for ns in out.strip().split('\n') if ns.strip()]


def _detect_a_record(domain: str) -> str:
    """Get A record for a domain."""
    out = _run_cmd(["dig", domain, "A", "+short"])
    lines = [l.strip() for l in out.strip().split('\n') if l.strip()]
    return lines[0] if lines else ""


def _detect_cname(domain: str) -> str:
    """Get CNAME for www subdomain."""
    out = _run_cmd(["dig", f"www.{domain}", "CNAME", "+short"])
    lines = [l.strip().rstrip('.') for l in out.strip().split('\n') if l.strip()]
    return lines[0] if lines else ""


def _detect_registrar(domain: str) -> dict:
    """Get registrar and expiry from whois."""
    out = _run_cmd(["whois", domain], timeout=15)
    info = {"registrar": "", "domain_expiry": "", "creation_date": ""}

    for line in out.split('\n'):
        line_lower = line.lower().strip()
        if 'registrar:' in line_lower and not info["registrar"]:
            info["registrar"] = line.split(':', 1)[1].strip()
        elif 'registrar url:' in line_lower:
            pass  # skip URL line
        elif 'expir' in line_lower and 'date' in line_lower and not info["domain_expiry"]:
            val = line.split(':', 1)[1].strip() if ':' in line else ""
            if val:
                info["domain_expiry"] = val[:10]  # Just the date part
        elif 'creation date' in line_lower and not info["creation_date"]:
            val = line.split(':', 1)[1].strip() if ':' in line else ""
            if val:
                info["creation_date"] = val[:10]

    return info


def _detect_hosting_from_headers(domain: str) -> dict:
    """Detect hosting/CDN/CMS from HTTP response headers and HTML."""
    info = {"web_server": "", "cdn": "", "hosting": "", "cms": ""}

    try:
        r = httpx.get(f"https://{domain}", timeout=15, follow_redirects=True,
                      headers={"User-Agent": "PracticeRank-Auditor/1.0"})
    except Exception:
        try:
            r = httpx.get(f"https://www.{domain}", timeout=15, follow_redirects=True,
                          headers={"User-Agent": "PracticeRank-Auditor/1.0"})
        except Exception:
            return info

    headers = {k.lower(): v.lower() for k, v in r.headers.items()}
    html_lower = r.text[:10000].lower() if r.text else ""

    # Server header
    server = headers.get("server", "")
    if server:
        info["web_server"] = server

    # CDN detection
    if "cf-ray" in headers:
        info["cdn"] = "Cloudflare"
    elif "x-cache" in headers and "cloudfront" in headers.get("x-cache", ""):
        info["cdn"] = "Amazon CloudFront"
    elif "x-served-by" in headers and "cache" in headers.get("x-served-by", ""):
        info["cdn"] = "Fastly"
    elif "via" in headers:
        via = headers["via"]
        if "cloudfront" in via:
            info["cdn"] = "Amazon CloudFront"
        elif "varnish" in via:
            info["cdn"] = "Varnish/Fastly"

    # Hosting from server/headers
    for sig, name in HOSTING_SIGNATURES.items():
        if sig in server or sig in headers.get("x-powered-by", "") or sig in headers.get("via", ""):
            if not info["hosting"]:
                info["hosting"] = name

    # CMS from HTML
    for sig, name in CMS_SIGNATURES.items():
        if sig in html_lower:
            info["cms"] = name
            break

    # Detect CMS theme if WordPress
    if info["cms"] == "WordPress":
        theme_match = re.search(r'wp-content/themes/([a-zA-Z0-9_-]+)', r.text or "")
        if theme_match:
            info["cms"] = f"WordPress ({theme_match.group(1)} theme)"

    # Platform-specific detection
    if "x-wix-request-id" in headers:
        info["hosting"] = "Wix"
        info["cms"] = "Wix"
    elif "x-shopify" in str(headers):
        info["hosting"] = "Shopify"
        info["cms"] = "Shopify"

    return info


def _identify_ns_owner(nameservers: list[str]) -> str:
    """Try to identify who owns the nameservers."""
    for ns in nameservers:
        ns_lower = ns.lower()
        for sig, owner in NAMESERVER_OWNERS.items():
            if sig in ns_lower:
                return owner
    # If unknown, return the NS domain
    if nameservers:
        ns_domain = '.'.join(nameservers[0].split('.')[-2:])
        return ns_domain
    return "Unknown"


def detect_hosting(domain: str) -> dict:
    """Run full DNS/hosting detection for a domain.

    Returns a dict with all discovered infrastructure details.
    """
    logger.info(f"Detecting hosting for {domain}")

    # Clean domain
    domain = domain.removeprefix("https://").removeprefix("http://").removeprefix("www.").rstrip("/")

    result = {
        "domain": domain,
        "registrar": "",
        "nameservers": [],
        "nameserver_owner": "",
        "a_record": "",
        "cname": "",
        "web_server": "",
        "cdn": "",
        "hosting": "",
        "cms": "",
        "domain_expiry": "",
        "creation_date": "",
        "detected_at": datetime.utcnow().isoformat() + "Z",
    }

    # DNS lookups
    result["nameservers"] = _detect_nameservers(domain)
    result["nameserver_owner"] = _identify_ns_owner(result["nameservers"])
    result["a_record"] = _detect_a_record(domain)
    result["cname"] = _detect_cname(domain)

    # WHOIS
    whois_info = _detect_registrar(domain)
    result["registrar"] = whois_info["registrar"]
    result["domain_expiry"] = whois_info["domain_expiry"]
    result["creation_date"] = whois_info["creation_date"]

    # HTTP headers
    http_info = _detect_hosting_from_headers(domain)
    result["web_server"] = http_info["web_server"]
    result["cdn"] = http_info["cdn"]
    result["hosting"] = http_info["hosting"]
    result["cms"] = http_info["cms"]

    # Build a human-readable summary
    parts = []
    if result["cms"]:
        parts.append(f"CMS: {result['cms']}")
    if result["hosting"]:
        parts.append(f"Hosting: {result['hosting']}")
    if result["cdn"]:
        parts.append(f"CDN: {result['cdn']}")
    if result["registrar"]:
        parts.append(f"Registrar: {result['registrar']}")
    result["summary"] = " | ".join(parts) if parts else "Could not detect"

    logger.info(f"Hosting detection complete for {domain}: {result['summary']}")
    return result
