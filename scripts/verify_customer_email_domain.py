#!/usr/bin/env python3
"""Register a customer domain in Resend and auto-add its verification DNS records
to Cloudflare, then trigger + poll verification.

This automates branded transactional email (e.g. noreply@<customer-domain>) for any
customer whose DNS we manage in Cloudflare. Run it once per customer site.

Prereqs:
  - Resend API key  -> env RESEND_API_KEY  or  ~/.resend_key
  - Cloudflare token -> env CLOUDFLARE_API_TOKEN or ~/.cf_pages_token
      (needs Zone:Read + DNS:Edit on the customer zone)
  - Resend plan must allow an additional domain (free tier = 1 domain only).

Usage:
  python3 scripts/verify_customer_email_domain.py westgalawyer.com
  python3 scripts/verify_customer_email_domain.py westgalawyer.com --zone <cf_zone_id>
  python3 scripts/verify_customer_email_domain.py westgalawyer.com --region us-east-1

It is idempotent: re-running re-uses the existing Resend domain and skips DNS
records that already match. Resend's send records live on the `send.<domain>`
subdomain + a DKIM key, so they do NOT touch an existing apex MX (Google, etc.).
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

RESEND = "https://api.resend.com"
CF = "https://api.cloudflare.com/client/v4"


def _read_secret(env_name, path):
    if os.environ.get(env_name):
        return os.environ[env_name].strip()
    p = os.path.expanduser(path)
    if os.path.exists(p):
        with open(p) as f:
            return f.read().strip()
    sys.exit(f"Missing credential: set ${env_name} or write {path}")


def _req(method, url, token, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    # Resend's API sits behind Cloudflare, which 1010-blocks urllib's default UA.
    req.add_header("User-Agent", "practicerank-domain-verify/1.0")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read() or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or "{}")
        except Exception:
            return e.code, {}


def fqdn(name, domain):
    """Normalize a Resend record name to a Cloudflare FQDN."""
    if not name or name in ("@", domain):
        return domain
    name = name.rstrip(".")
    if name == domain or name.endswith("." + domain):
        return name
    return f"{name}.{domain}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("domain")
    ap.add_argument("--zone", help="Cloudflare zone id (looked up by name if omitted)")
    ap.add_argument("--region", default="us-east-1")
    ap.add_argument("--poll", type=int, default=300, help="max seconds to wait for verification")
    args = ap.parse_args()
    domain = args.domain.strip().lower()

    resend_key = _read_secret("RESEND_API_KEY", "~/.resend_key")
    cf_token = _read_secret("CLOUDFLARE_API_TOKEN", "~/.cf_pages_token")

    # --- 1) find or create the domain in Resend ---------------------------------
    _, listing = _req("GET", f"{RESEND}/domains", resend_key)
    existing = next((d for d in listing.get("data", []) if d.get("name") == domain), None)
    if existing:
        dom_id = existing["id"]
        print(f"• Resend domain already exists: {domain} ({dom_id}) status={existing.get('status')}")
        _, dom = _req("GET", f"{RESEND}/domains/{dom_id}", resend_key)
        records = dom.get("records", [])
    else:
        status, dom = _req("POST", f"{RESEND}/domains", resend_key,
                           {"name": domain, "region": args.region})
        if status >= 400 or not dom.get("id"):
            sys.exit(f"✗ Resend register failed: {dom.get('message') or dom}")
        dom_id = dom["id"]
        records = dom.get("records", [])
        print(f"• Registered {domain} in Resend ({dom_id}); {len(records)} DNS records to add")

    if not records:
        sys.exit("✗ No DNS records returned by Resend — cannot continue.")

    # --- 2) resolve the Cloudflare zone -----------------------------------------
    zone = args.zone
    if not zone:
        _, z = _req("GET", f"{CF}/zones?name={domain}", cf_token)
        res = z.get("result") or []
        if not res:
            sys.exit(f"✗ Cloudflare zone for {domain} not found (pass --zone).")
        zone = res[0]["id"]
    print(f"• Cloudflare zone: {zone}")

    # --- 3) push each Resend record into Cloudflare (idempotent) -----------------
    _, cur = _req("GET", f"{CF}/zones/{zone}/dns_records?per_page=500", cf_token)
    existing_recs = cur.get("result", [])

    def already_present(rtype, name, content):
        for r in existing_recs:
            if (r["type"] == rtype and r["name"].rstrip(".") == name.rstrip(".")
                    and content.split()[0] in r.get("content", "")):
                return True
        return False

    for rec in records:
        rtype = rec["type"].upper()
        name = fqdn(rec.get("name", ""), domain)
        content = rec["value"]
        payload = {"type": rtype, "name": name, "content": content,
                   "ttl": 1, "proxied": False}
        if rtype == "MX":
            payload["priority"] = int(rec.get("priority", 10))
        label = f"[{rec.get('record','?')}] {rtype} {name}"
        if already_present(rtype, name, content):
            print(f"  = exists, skip  {label}")
            continue
        status, out = _req("POST", f"{CF}/zones/{zone}/dns_records", cf_token, payload)
        if out.get("success"):
            print(f"  + added        {label}")
        else:
            errs = out.get("errors")
            # 81057 = record already exists
            if errs and errs[0].get("code") == 81057:
                print(f"  = exists, skip  {label}")
            else:
                print(f"  ✗ FAILED       {label}: {errs}")

    # --- 4) trigger verification + poll -----------------------------------------
    _req("POST", f"{RESEND}/domains/{dom_id}/verify", resend_key)
    print("• Verification triggered; polling Resend (DNS can take a few minutes)…")
    deadline = time.time() + args.poll
    last = None
    while time.time() < deadline:
        _, d = _req("GET", f"{RESEND}/domains/{dom_id}", resend_key)
        st = d.get("status")
        if st != last:
            print(f"  status: {st}")
            last = st
        if st == "verified":
            print(f"\n✓ {domain} verified. You can now send from noreply@{domain}.")
            print(f"  Next: set CONTACT_FROM='<Business> <noreply@{domain}>' on the Pages project + redeploy.")
            return
        time.sleep(15)
    print(f"\n… still '{last}' after {args.poll}s. DNS may need more time; re-run to re-poll.")


if __name__ == "__main__":
    main()
