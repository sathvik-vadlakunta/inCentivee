#!/usr/bin/env python3
"""Generate a branded PracticeRank PDF report from audit JSON."""

import json
import sys
from weasyprint import HTML

def status_color(status):
    return {
        "critical": "#ef4444",
        "needs_work": "#f59e0b",
        "good": "#22c55e",
        "excellent": "#06b6d4",
    }.get(status, "#888")

def status_label(status):
    return {
        "critical": "Critical",
        "needs_work": "Needs Work",
        "good": "Good",
        "excellent": "Excellent",
    }.get(status, status)

def visibility_icon(v):
    if v == "yes":
        return '<span style="color:#22c55e;font-weight:700;">✓ Visible</span>'
    elif v == "partial":
        return '<span style="color:#f59e0b;font-weight:700;">◐ Partial</span>'
    else:
        return '<span style="color:#ef4444;font-weight:700;">✗ Not Visible</span>'

def grade_color(grade):
    return {
        "A": "#22c55e", "B": "#06b6d4", "C": "#f59e0b", "D": "#f97316", "F": "#ef4444"
    }.get(grade, "#888")

def score_color(score):
    if score >= 81: return "#22c55e"
    if score >= 61: return "#06b6d4"
    if score >= 31: return "#f59e0b"
    return "#ef4444"

CAT_NAMES = {
    "gbp": "Google Business Profile",
    "ai_readiness": "AI Search Readiness",
    "reviews": "Review Strength",
    "local_seo": "Local SEO",
    "content": "Content & On-Page SEO",
    "technical": "Technical SEO",
}

def build_html(r):
    cats_html = ""
    for key, label in CAT_NAMES.items():
        cat = r["categories"].get(key, {})
        sc = cat.get("score", 0)
        st = cat.get("status", "")
        findings_html = "".join(f'<li style="margin-bottom:6px;color:#334155;font-size:13px;line-height:1.5;">{f}</li>' for f in cat.get("findings", []))

        extra = ""
        if key == "reviews":
            extra = f'''
            <div style="display:flex;gap:24px;margin-top:8px;">
                <div style="background:#f1f5f9;padding:8px 14px;border-radius:8px;text-align:center;">
                    <div style="font-size:22px;font-weight:700;color:#0f172a;">{cat.get("count","?")}</div>
                    <div style="font-size:11px;color:#64748b;">Your Reviews</div>
                </div>
                <div style="background:#f1f5f9;padding:8px 14px;border-radius:8px;text-align:center;">
                    <div style="font-size:22px;font-weight:700;color:#ef4444;">{cat.get("competitor_reviews","?")}</div>
                    <div style="font-size:11px;color:#64748b;">{cat.get("competitor_name","Competitor")}</div>
                </div>
                <div style="background:#f1f5f9;padding:8px 14px;border-radius:8px;text-align:center;">
                    <div style="font-size:22px;font-weight:700;color:#0f172a;">{cat.get("rating","?")}</div>
                    <div style="font-size:11px;color:#64748b;">Your Rating</div>
                </div>
            </div>'''

        cats_html += f'''
        <div style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:20px;margin-bottom:16px;page-break-inside:avoid;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
                <h3 style="margin:0;font-size:16px;color:#0f172a;">{label}</h3>
                <div style="display:flex;align-items:center;gap:10px;">
                    <span style="background:{status_color(st)};color:#fff;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:600;">{status_label(st)}</span>
                    <span style="font-size:24px;font-weight:800;color:{score_color(sc)};">{sc}</span>
                </div>
            </div>
            <ul style="padding-left:18px;margin:0;">{findings_html}</ul>
            {extra}
        </div>'''

    # AI Visibility
    ai_rows = ""
    for platform, data in r.get("ai_visibility", {}).items():
        ai_rows += f'''
        <tr>
            <td style="padding:10px 14px;font-weight:600;text-transform:capitalize;border-bottom:1px solid #e2e8f0;">{platform}</td>
            <td style="padding:10px 14px;border-bottom:1px solid #e2e8f0;">{visibility_icon(data.get("visible","no"))}</td>
            <td style="padding:10px 14px;color:#475569;font-size:13px;border-bottom:1px solid #e2e8f0;">{data.get("reason","")}</td>
        </tr>'''

    # Priority Actions
    actions_html = ""
    for i, a in enumerate(r.get("priority_actions", []), 1):
        impact_color = "#ef4444" if a.get("impact") == "high" else "#f59e0b"
        actions_html += f'''
        <div style="display:flex;gap:14px;align-items:flex-start;margin-bottom:14px;page-break-inside:avoid;">
            <div style="min-width:36px;height:36px;background:#6366f1;color:#fff;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:16px;">{i}</div>
            <div style="flex:1;">
                <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
                    <strong style="font-size:14px;color:#0f172a;">{a.get("title","")}</strong>
                    <span style="background:{impact_color};color:#fff;padding:2px 8px;border-radius:12px;font-size:10px;font-weight:600;">{a.get("impact","").upper()}</span>
                    <span style="color:#6366f1;font-weight:700;font-size:13px;">{a.get("est_patients_mo","")} patients/mo</span>
                </div>
                <p style="margin:0;color:#475569;font-size:13px;line-height:1.5;">{a.get("description","")}</p>
            </div>
        </div>'''

    # Projections
    proj = r.get("projections", {})

    return f'''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
    @page {{ size: A4; margin: 40px 50px; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; color: #0f172a; line-height: 1.6; }}
</style>
</head>
<body>

<!-- Header -->
<div style="display:flex;justify-content:space-between;align-items:center;padding-bottom:20px;border-bottom:3px solid #6366f1;margin-bottom:30px;">
    <div>
        <div style="font-size:28px;font-weight:800;color:#6366f1;">PracticeRank</div>
        <div style="font-size:12px;color:#64748b;margin-top:2px;">AI-Powered Dental Marketing Intelligence</div>
    </div>
    <div style="text-align:right;">
        <div style="font-size:11px;color:#64748b;">Audit Report</div>
        <div style="font-size:13px;font-weight:600;color:#0f172a;">{r.get("practice_name","")}</div>
        <div style="font-size:12px;color:#64748b;">{r.get("city","")}, {r.get("state","")}</div>
    </div>
</div>

<!-- Score Hero -->
<div style="background:linear-gradient(135deg,#6366f1,#8b5cf6);border-radius:16px;padding:30px;color:#fff;text-align:center;margin-bottom:24px;">
    <div style="font-size:64px;font-weight:900;line-height:1;">{r.get("overall_score","")}</div>
    <div style="font-size:14px;opacity:0.8;margin-top:4px;">out of 100</div>
    <div style="display:inline-block;margin-top:10px;background:rgba(255,255,255,0.2);padding:6px 20px;border-radius:20px;font-size:18px;font-weight:700;">Grade: {r.get("grade","")}</div>
    <p style="margin:16px auto 0;max-width:560px;font-size:14px;line-height:1.6;opacity:0.9;">{r.get("executive_summary","")}</p>
</div>

<!-- Revenue Lost -->
<div style="background:#fef2f2;border:2px solid #fca5a5;border-radius:12px;padding:18px;text-align:center;margin-bottom:28px;">
    <div style="font-size:12px;color:#ef4444;font-weight:600;text-transform:uppercase;letter-spacing:1px;">Estimated Revenue Lost Annually</div>
    <div style="font-size:32px;font-weight:900;color:#ef4444;margin-top:4px;">{r.get("revenue_lost_annually","")}</div>
    <div style="font-size:12px;color:#64748b;margin-top:4px;">Based on patient lifetime value of {r.get("patient_lifetime_value","")}</div>
</div>

<!-- Category Scores -->
<h2 style="font-size:18px;color:#0f172a;margin-bottom:16px;">Category Breakdown</h2>
{cats_html}

<!-- AI Visibility -->
<div style="page-break-before:always;"></div>
<h2 style="font-size:18px;color:#0f172a;margin-bottom:16px;">AI Platform Visibility</h2>
<p style="font-size:13px;color:#64748b;margin-top:-8px;margin-bottom:14px;">40%+ of patients now use AI assistants to find dentists. Here's whether they'd find you.</p>
<table style="width:100%;border-collapse:collapse;background:#fff;border:1px solid #e2e8f0;border-radius:12px;margin-bottom:28px;">
    <thead>
        <tr style="background:#f8fafc;">
            <th style="padding:10px 14px;text-align:left;font-size:12px;color:#64748b;border-bottom:2px solid #e2e8f0;">Platform</th>
            <th style="padding:10px 14px;text-align:left;font-size:12px;color:#64748b;border-bottom:2px solid #e2e8f0;">Status</th>
            <th style="padding:10px 14px;text-align:left;font-size:12px;color:#64748b;border-bottom:2px solid #e2e8f0;">Details</th>
        </tr>
    </thead>
    <tbody>{ai_rows}</tbody>
</table>

<!-- CTA -->
<div style="background:linear-gradient(135deg,#6366f1,#8b5cf6);border-radius:12px;padding:24px;color:#fff;text-align:center;margin-bottom:28px;">
    <div style="font-size:18px;font-weight:700;">Your practice is invisible to AI search.</div>
    <div style="font-size:14px;opacity:0.85;margin-top:6px;">40%+ of patients now ask ChatGPT, Gemini, and other AI assistants for dentist recommendations — and they'll never hear about you.</div>
    <div style="margin-top:14px;display:inline-block;background:#fff;color:#6366f1;padding:10px 28px;border-radius:8px;font-weight:700;font-size:14px;">Book a Free Strategy Call → practicerank.ai</div>
</div>

<!-- Priority Actions -->
<h2 style="font-size:18px;color:#0f172a;margin-bottom:16px;">Top 5 Priority Actions</h2>
{actions_html}

<!-- Growth Projections -->
<h2 style="font-size:18px;color:#0f172a;margin-top:28px;margin-bottom:16px;">Growth Projections</h2>
<div style="display:flex;gap:12px;margin-bottom:28px;">
    <div style="flex:1;background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:16px;text-align:center;">
        <div style="font-size:11px;color:#64748b;font-weight:600;">TODAY</div>
        <div style="font-size:28px;font-weight:800;color:#ef4444;margin-top:6px;">{proj.get("current_inquiries_mo","")}</div>
        <div style="font-size:11px;color:#64748b;">inquiries/mo</div>
    </div>
    <div style="flex:1;background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:16px;text-align:center;">
        <div style="font-size:11px;color:#64748b;font-weight:600;">3 MONTHS</div>
        <div style="font-size:28px;font-weight:800;color:#f59e0b;margin-top:6px;">{proj.get("month_3","")}</div>
        <div style="font-size:11px;color:#64748b;">inquiries/mo</div>
    </div>
    <div style="flex:1;background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:16px;text-align:center;">
        <div style="font-size:11px;color:#64748b;font-weight:600;">6 MONTHS</div>
        <div style="font-size:28px;font-weight:800;color:#22c55e;margin-top:6px;">{proj.get("month_6","")}</div>
        <div style="font-size:11px;color:#64748b;">inquiries/mo</div>
    </div>
    <div style="flex:1;background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:16px;text-align:center;">
        <div style="font-size:11px;color:#64748b;font-weight:600;">12 MONTHS</div>
        <div style="font-size:28px;font-weight:800;color:#6366f1;margin-top:6px;">{proj.get("month_12","")}</div>
        <div style="font-size:11px;color:#64748b;">inquiries/mo</div>
    </div>
</div>

<!-- Final CTA -->
<div style="background:#0f172a;border-radius:12px;padding:28px;color:#fff;text-align:center;margin-top:20px;">
    <div style="font-size:14px;color:#f59e0b;font-weight:600;">You're leaving {r.get("revenue_lost_annually","")} on the table every year.</div>
    <div style="font-size:22px;font-weight:800;margin-top:8px;">Ready to start getting the patients you deserve?</div>
    <div style="margin-top:14px;font-size:13px;color:#94a3b8;">Schedule a free 30-minute strategy call. We'll walk through your report and show you exactly how to fix it.</div>
    <div style="margin-top:16px;display:inline-block;background:#6366f1;color:#fff;padding:12px 32px;border-radius:8px;font-weight:700;font-size:15px;">Book Your Strategy Call → practicerank.ai</div>
</div>

<div style="text-align:center;margin-top:24px;padding-top:16px;border-top:1px solid #e2e8f0;">
    <span style="font-size:11px;color:#94a3b8;">PracticeRank — AI-Powered Dental Marketing | practicerank.ai | kdoherty@practicerank.ai</span>
</div>

</body>
</html>'''


if __name__ == "__main__":
    input_file = sys.argv[1] if len(sys.argv) > 1 else "hilltop-report.json"
    with open(input_file) as f:
        report = json.load(f)

    name_slug = report.get("practice_name", "practice").lower().replace(" ", "-")
    output_file = f"/Users/kody/dev/dental-marketing/practicerank-report-{name_slug}.pdf"

    html_str = build_html(report)
    HTML(string=html_str).write_pdf(output_file)
    print(f"PDF saved: {output_file}")
