"""Quick test to verify a Webflow API key works.

Usage:
    python scripts/test_webflow.py <api_key>
    python scripts/test_webflow.py  # reads from WEBFLOW_API_KEY env var
"""

import os
import sys
import json

import httpx


def test_webflow_key(api_key: str):
    """Test that the Webflow API key is valid and list available sites."""
    client = httpx.Client(
        base_url="https://api.webflow.com/v2",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        },
        timeout=15.0,
    )

    # Test 1: List sites
    print("Testing Webflow API key...")
    print("-" * 40)

    try:
        resp = client.get("/sites")
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        print(f"FAILED: {e.response.status_code} — {e.response.text}")
        if e.response.status_code == 401:
            print("The API key is invalid or expired.")
        elif e.response.status_code == 403:
            print("The API key doesn't have permission to list sites.")
        sys.exit(1)
    except httpx.RequestError as e:
        print(f"FAILED: Network error — {e}")
        sys.exit(1)

    data = resp.json()
    sites = data.get("sites", [])

    if not sites:
        print("API key is valid but no sites are accessible.")
        print("Make sure the token was generated at the site level, not workspace level.")
        sys.exit(1)

    print(f"API key is VALID. Found {len(sites)} site(s):\n")

    for site in sites:
        site_id = site.get("id", "?")
        name = site.get("displayName", site.get("name", "?"))
        short_name = site.get("shortName", "?")
        custom_domains = site.get("customDomains", [])
        domains_str = ", ".join(d.get("url", "") for d in custom_domains) if custom_domains else "none"

        print(f"  Site: {name}")
        print(f"  ID:   {site_id}  <-- use this as webflow_site_id")
        print(f"  Slug: {short_name}")
        print(f"  Domains: {domains_str}")
        print()

        # Test 2: List pages for each site
        try:
            pages_resp = client.get(f"/sites/{site_id}/pages", params={"limit": 5})
            pages_resp.raise_for_status()
            pages = pages_resp.json().get("pages", [])
            print(f"  Pages (first {len(pages)}):")
            for page in pages:
                print(f"    - {page.get('title', '?')} (/{page.get('slug', '')})")
            print()
        except Exception as e:
            print(f"  Could not list pages: {e}")
            print()

    client.close()
    print("All tests passed. You're ready to go.")
    print("\nNext step: Add the site ID and API key to data/customers.json")


if __name__ == "__main__":
    api_key = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("WEBFLOW_API_KEY")
    if not api_key:
        print("Usage: python scripts/test_webflow.py <api_key>")
        print("   or: WEBFLOW_API_KEY=xxx python scripts/test_webflow.py")
        sys.exit(1)
    test_webflow_key(api_key)
