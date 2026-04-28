#!/usr/bin/env python3
"""Render email templates with customer data and save or send.

Usage:
    # Preview an email
    python scripts/send_email.py --template 01-initial-access-request --customer hilltop-family-dental --preview

    # Save rendered email to file
    python scripts/send_email.py --template 02-access-followup --customer hilltop-family-dental
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from geo_agent.db import CustomerDB

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "emails"


def render_template(template_name: str, variables: dict[str, str]) -> str:
    """Load and render an email template with variable substitution."""
    # Ensure .md extension
    if not template_name.endswith(".md"):
        template_name += ".md"

    template_path = TEMPLATES_DIR / template_name
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    text = template_path.read_text()
    for key, value in variables.items():
        text = text.replace(f"{{{key}}}", str(value))
    return text


def get_template_variables(db: CustomerDB, customer_id: str, template_name: str) -> dict[str, str]:
    """Build template variables from customer database."""
    customer = db.get_customer(customer_id)
    if not customer:
        raise ValueError(f"Customer not found: {customer_id}")

    contacts = db.get_contacts(customer_id)
    primary_contact = contacts[0] if contacts else {"name": "", "email": ""}

    variables = {
        "contact_name": primary_contact.get("name", ""),
        "practice_name": customer["name"],
        "platform": customer.get("platform", "unknown").title(),
        "domain": customer["domain"],
    }

    # Template-specific variables
    if "access-followup" in template_name or "02" in template_name:
        pending = db.get_pending_access(customer_id)
        if pending:
            lines = []
            for p in pending:
                lines.append(f"- {p['platform'].upper()}")
            variables["pending_access_list"] = "\n".join(lines)
        else:
            variables["pending_access_list"] = "All access has been granted!"

    if "initial-access" in template_name or "01" in template_name:
        platform = customer.get("platform", "unknown")
        from scripts.onboard import _get_platform_access_steps
        variables["platform_access_steps"] = _get_platform_access_steps(platform)

    if "monthly-report" in template_name or "04" in template_name:
        from datetime import datetime
        variables["report_month"] = datetime.now().strftime("%B %Y")

        for metric, key in [
            ("review_count", "review_count"), ("rating", "rating"),
            ("ai_mentions", "ai_mentions"), ("llms_txt_hits", "llms_hits"),
        ]:
            kpis = db.get_kpis(customer_id, metric, limit=2)
            if kpis:
                variables[key] = str(kpis[0]["value"])
                if len(kpis) >= 2:
                    prev = kpis[1]["value"]
                    variables[f"prev_{key}"] = str(prev)
                    delta = kpis[0]["value"] - prev
                    variables[f"{key}_delta"] = f"{delta:+.1f}" if delta != 0 else "0"
                else:
                    variables[f"prev_{key}"] = "N/A"
                    variables[f"{key}_delta"] = "--"
            else:
                variables[key] = "N/A"
                variables[f"prev_{key}"] = "N/A"
                variables[f"{key}_delta"] = "--"

        # Pull changes from latest run
        latest_run = db.get_latest_run(customer_id)
        if latest_run and latest_run.get("changes"):
            variables["changes_list"] = "\n".join(f"- {c}" for c in latest_run["changes"])
        else:
            variables["changes_list"] = "- (No changes recorded yet)"
        variables["next_month_plans"] = "- Continue monitoring and optimization"

    if "staging-approval" in template_name or "05" in template_name:
        from geo_agent.staging import StagingManager
        data_dir = str(Path(__file__).resolve().parent.parent / "data")
        staging = StagingManager(data_dir=data_dir)
        if staging.is_staged(customer_id):
            diff = staging.generate_diff_report(customer_id)
            staged_files = staging.get_staged_files(customer_id)
            variables["changes_summary"] = "\n".join(f"- {f}" for f in staged_files.keys())
            variables["diff_summary"] = diff
        else:
            variables["changes_summary"] = "(No staged changes)"
            variables["diff_summary"] = "(No diff available)"

    return variables


def main():
    parser = argparse.ArgumentParser(description="Render and send email templates")
    parser.add_argument("--template", required=True, help="Template name (e.g. 01-initial-access-request)")
    parser.add_argument("--customer", required=True, help="Customer ID")
    parser.add_argument("--preview", action="store_true", help="Print to stdout instead of saving")
    parser.add_argument("--db", default=None, help="Database file path")
    args = parser.parse_args()

    db = CustomerDB(db_path=args.db)
    try:
        variables = get_template_variables(db, args.customer, args.template)
        rendered = render_template(args.template, variables)

        if args.preview:
            print(rendered)
        else:
            # Save to customer directory
            customer_dir = (
                Path(__file__).resolve().parent.parent
                / "data" / "customers" / args.customer
            )
            customer_dir.mkdir(parents=True, exist_ok=True)
            output_path = customer_dir / f"{args.template}.txt"
            output_path.write_text(rendered)
            print(f"Email saved to: {output_path}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
