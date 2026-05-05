"""Generate polished AI Mention Report DOCX for weekly client reviews.

Produces a branded, professional report showing:
- Executive summary with overall mention rate
- Per-engine performance breakdown
- Per-category analysis
- Detailed results grid
- Trend data (when multiple runs exist)
- Recommendations for improvement
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from io import BytesIO

from docx import Document
from docx.shared import Inches, Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn


# Brand colors
BLUE = RGBColor(0x25, 0x63, 0xEB)
GREEN = RGBColor(0x16, 0xA3, 0x4A)
RED = RGBColor(0xDC, 0x26, 0x26)
AMBER = RGBColor(0xD9, 0x77, 0x06)
GRAY = RGBColor(0x6B, 0x72, 0x80)
LIGHT_GRAY = RGBColor(0x9C, 0xA3, 0xAF)
DARK = RGBColor(0x1E, 0x29, 0x3B)

CAT_LABELS = {
    "brand": "Brand Awareness",
    "general": "General Discovery",
    "service": "Service-Specific",
    "location": "Location/Area",
    "comparison": "Competitor Comparison",
    "reputation": "Reputation",
    "recommendation": "Recommendations",
}


def _set_cell_shading(cell, color_hex: str):
    """Set cell background color."""
    shading = cell._element.get_or_add_tcPr()
    shading_elem = shading.makeelement(qn("w:shd"), {
        qn("w:fill"): color_hex,
        qn("w:val"): "clear",
    })
    shading.append(shading_elem)


def _add_run(paragraph, text: str, bold=False, italic=False, size=None, color=None):
    """Helper to add a formatted run."""
    run = paragraph.add_run(text)
    if bold:
        run.bold = True
    if italic:
        run.italic = True
    if size:
        run.font.size = Pt(size)
    if color:
        run.font.color.rgb = color
    return run


def generate_ai_mention_report(
    customer: dict,
    run_data: dict,
    results: list[dict],
    history: list[dict] | None = None,
    brand_name: str = "PracticeRank",
) -> BytesIO:
    """Generate a polished AI Mention Report DOCX.

    Args:
        customer: Customer dict with name, city, state, domain, etc.
        run_data: Run summary with mention_count, total_queries, mention_rate, engines, etc.
        results: List of result dicts with prompt, category, ai/engine, mentioned, position, quality_score, context
        history: Optional list of previous run summaries for trend section
        brand_name: Branding name for header
    """
    doc = Document()

    # Page margins
    for section in doc.sections:
        section.top_margin = Cm(2)
        section.bottom_margin = Cm(2)
        section.left_margin = Cm(2.5)
        section.right_margin = Cm(2.5)

    _add_cover(doc, customer, run_data, brand_name)
    _add_executive_summary(doc, customer, run_data, results)
    _add_engine_breakdown(doc, run_data)
    _add_category_analysis(doc, results)
    _add_results_detail(doc, results)

    if history and len(history) >= 2:
        doc.add_page_break()
        _add_trend_section(doc, history)

    _add_recommendations(doc, customer, run_data, results)
    _add_footer(doc, brand_name)

    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf


def _add_cover(doc: Document, customer: dict, run_data: dict, brand_name: str):
    """Cover header with branding and date."""
    # Brand name
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    _add_run(p, brand_name, bold=True, size=20, color=BLUE)

    # Report title
    p2 = doc.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.LEFT
    _add_run(p2, "AI Search Visibility Report", bold=True, size=16, color=DARK)

    # Customer info
    p3 = doc.add_paragraph()
    _add_run(p3, "Prepared for: ", size=11, color=GRAY)
    _add_run(p3, customer.get("name", "Unknown"), bold=True, size=12, color=DARK)

    location_parts = []
    if customer.get("city"):
        location_parts.append(customer["city"])
    if customer.get("state"):
        location_parts.append(customer["state"])
    if location_parts:
        p4 = doc.add_paragraph()
        _add_run(p4, "Location: ", size=10, color=GRAY)
        _add_run(p4, ", ".join(location_parts), size=10, color=DARK)

    if customer.get("domain"):
        p5 = doc.add_paragraph()
        _add_run(p5, "Website: ", size=10, color=GRAY)
        _add_run(p5, customer["domain"], size=10, color=BLUE)

    # Report date
    today = run_data.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    p6 = doc.add_paragraph()
    _add_run(p6, f"Report Date: {today}", size=10, color=GRAY)

    # Divider
    doc.add_paragraph("_" * 60).runs[0].font.color.rgb = RGBColor(0xE5, 0xE7, 0xEB)
    doc.add_paragraph()


def _add_executive_summary(doc: Document, customer: dict, run_data: dict, results: list[dict]):
    """Big numbers summary section."""
    doc.add_heading("Executive Summary", level=1)

    mention_count = run_data.get("mention_count", 0)
    total_queries = run_data.get("total_queries", 0)
    mention_rate = run_data.get("mention_rate", 0)
    if isinstance(mention_rate, float) and mention_rate <= 1:
        mention_rate = round(mention_rate * 100, 1)
    avg_pos = run_data.get("avg_position")

    name = customer.get("name", "your business")

    # Summary paragraph
    rate_color = GREEN if mention_rate > 30 else AMBER if mention_rate > 10 else RED
    p = doc.add_paragraph()
    _add_run(p, f"We queried {total_queries} searches across 5 major AI engines to evaluate how often ", size=11)
    _add_run(p, name, bold=True, size=11)
    _add_run(p, " appears in AI-generated recommendations.", size=11)

    doc.add_paragraph()

    # Metrics table
    table = doc.add_table(rows=1, cols=3)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    # Mention count
    cell0 = table.cell(0, 0)
    p0 = cell0.paragraphs[0]
    p0.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _add_run(p0, str(mention_count), bold=True, size=24, color=BLUE)
    p0a = cell0.add_paragraph()
    p0a.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _add_run(p0a, f"of {total_queries} Mentions", size=9, color=GRAY)

    # Mention rate
    cell1 = table.cell(0, 1)
    p1 = cell1.paragraphs[0]
    p1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _add_run(p1, f"{mention_rate}%", bold=True, size=24, color=rate_color)
    p1a = cell1.add_paragraph()
    p1a.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _add_run(p1a, "Mention Rate", size=9, color=GRAY)

    # Avg position
    cell2 = table.cell(0, 2)
    p2 = cell2.paragraphs[0]
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pos_text = f"#{avg_pos:.1f}" if avg_pos else "N/A"
    _add_run(p2, pos_text, bold=True, size=24, color=DARK)
    p2a = cell2.add_paragraph()
    p2a.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _add_run(p2a, "Avg Position", size=9, color=GRAY)

    doc.add_paragraph()

    # Context paragraph
    if mention_rate >= 30:
        summary = f"{name} has strong visibility across AI search engines. AI assistants are actively recommending the practice to users."
    elif mention_rate >= 10:
        summary = f"{name} has moderate visibility in AI search. There is significant room for improvement — most AI engines are not yet recommending the practice."
    else:
        summary = f"{name} has low visibility in AI search results. AI assistants are rarely recommending the practice. This represents a major growth opportunity as AI search adoption accelerates."

    p = doc.add_paragraph()
    _add_run(p, summary, size=10, italic=True, color=GRAY)
    doc.add_paragraph()


def _add_engine_breakdown(doc: Document, run_data: dict):
    """Per-engine performance table."""
    doc.add_heading("Performance by AI Engine", level=1)

    engines = run_data.get("engines", {})
    if not engines:
        doc.add_paragraph("No engine data available.")
        return

    table = doc.add_table(rows=1 + len(engines), cols=4)
    table.style = "Light Grid Accent 1"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    # Header
    for i, header in enumerate(["AI Engine", "Status", "Mentions", "Rate"]):
        cell = table.cell(0, i)
        cell.text = header
        for run in cell.paragraphs[0].runs:
            run.bold = True
            run.font.size = Pt(9)

    for row_idx, (eng_name, stats) in enumerate(engines.items(), start=1):
        table.cell(row_idx, 0).text = eng_name

        status = stats.get("status", "unknown")
        status_cell = table.cell(row_idx, 1)
        if status == "no_api_key":
            status_cell.text = "Not Connected"
            _set_cell_shading(status_cell, "FEF3C7")
        else:
            status_cell.text = "Active"
            _set_cell_shading(status_cell, "DCFCE7")

        mentions = stats.get("mentions", 0)
        total = stats.get("total", 0)
        table.cell(row_idx, 2).text = f"{mentions}/{total}" if status != "no_api_key" else "—"

        rate = round(mentions / total * 100) if total > 0 else 0
        rate_cell = table.cell(row_idx, 3)
        rate_cell.text = f"{rate}%" if status != "no_api_key" else "—"
        if rate > 30:
            _set_cell_shading(rate_cell, "DCFCE7")
        elif rate > 0:
            _set_cell_shading(rate_cell, "FEF9C3")
        elif status != "no_api_key":
            _set_cell_shading(rate_cell, "FECACA")

    # Set font size for all cells
    for row in table.rows:
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.font.size = Pt(9)

    doc.add_paragraph()


def _add_category_analysis(doc: Document, results: list[dict]):
    """Category breakdown with descriptions."""
    doc.add_heading("Performance by Search Category", level=1)

    p = doc.add_paragraph()
    _add_run(p, "We test different types of searches that real users make when looking for services like yours. "
             "Here's how you perform in each category:", size=10, color=GRAY)
    doc.add_paragraph()

    # Build category stats
    categories = {}
    for r in results:
        cat = r.get("category") or r.get("prompt_category", "general")
        categories.setdefault(cat, {"mentions": 0, "total": 0, "qualities": []})
        categories[cat]["total"] += 1
        if r.get("mentioned"):
            categories[cat]["mentions"] += 1
            categories[cat]["qualities"].append(r.get("quality_score", 0))

    cat_descriptions = {
        "brand": "Searches using your business name directly — do AI engines know who you are?",
        "general": "Generic discovery searches like 'best dentist in [city]' — top-of-funnel visibility.",
        "service": "Searches for specific services you offer — high-intent queries from potential patients.",
        "location": "Neighborhood and area-specific searches — local visibility.",
        "comparison": "Competitive searches comparing practices — how you stack up.",
        "reputation": "Reviews and trust queries — what AI says about your reputation.",
        "recommendation": "Direct recommendation requests — the most valuable mentions.",
    }

    table = doc.add_table(rows=1 + len(categories), cols=4)
    table.style = "Light Grid Accent 1"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    for i, header in enumerate(["Category", "Mentions", "Rate", "Avg Quality"]):
        cell = table.cell(0, i)
        cell.text = header
        for run in cell.paragraphs[0].runs:
            run.bold = True
            run.font.size = Pt(9)

    for row_idx, (cat, stats) in enumerate(categories.items(), start=1):
        label = CAT_LABELS.get(cat, cat.title())
        table.cell(row_idx, 0).text = label
        table.cell(row_idx, 1).text = f"{stats['mentions']}/{stats['total']}"

        rate = round(stats["mentions"] / stats["total"] * 100) if stats["total"] > 0 else 0
        rate_cell = table.cell(row_idx, 2)
        rate_cell.text = f"{rate}%"
        if rate > 50:
            _set_cell_shading(rate_cell, "DCFCE7")
        elif rate > 20:
            _set_cell_shading(rate_cell, "FEF9C3")
        else:
            _set_cell_shading(rate_cell, "FECACA")

        avg_q = round(sum(stats["qualities"]) / len(stats["qualities"])) if stats["qualities"] else 0
        table.cell(row_idx, 3).text = str(avg_q) if avg_q > 0 else "—"

    for row in table.rows:
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.font.size = Pt(9)

    # Category descriptions
    doc.add_paragraph()
    for cat, desc in cat_descriptions.items():
        if cat in categories:
            p = doc.add_paragraph()
            _add_run(p, f"{CAT_LABELS.get(cat, cat)}: ", bold=True, size=9, color=DARK)
            _add_run(p, desc, size=9, color=GRAY)

    doc.add_paragraph()


def _add_results_detail(doc: Document, results: list[dict]):
    """Detailed results — grouped by category showing prompt × engine grid."""
    doc.add_page_break()
    doc.add_heading("Detailed Results", level=1)

    # Group by category
    by_cat = {}
    for r in results:
        cat = r.get("category") or r.get("prompt_category", "general")
        by_cat.setdefault(cat, {})
        prompt = r.get("prompt", "")
        engine = r.get("ai") or r.get("engine", "")
        by_cat[cat].setdefault(prompt, {})[engine] = r

    engines = sorted(set(r.get("ai") or r.get("engine", "") for r in results))

    for cat, prompts in by_cat.items():
        label = CAT_LABELS.get(cat, cat.title())
        cat_mentions = sum(1 for p in prompts.values() for e in p.values() if e.get("mentioned"))
        cat_total = sum(len(p) for p in prompts.values())
        cat_rate = round(cat_mentions / cat_total * 100) if cat_total > 0 else 0

        doc.add_heading(f"{label} ({cat_rate}%)", level=2)

        # Build table: prompt × engines
        prompt_list = list(prompts.keys())
        table = doc.add_table(rows=1 + len(prompt_list), cols=1 + len(engines))
        table.alignment = WD_TABLE_ALIGNMENT.CENTER

        # Header row
        table.cell(0, 0).text = "Search Query"
        for run in table.cell(0, 0).paragraphs[0].runs:
            run.bold = True
            run.font.size = Pt(8)
        for ei, eng in enumerate(engines):
            cell = table.cell(0, ei + 1)
            cell.text = eng
            for run in cell.paragraphs[0].runs:
                run.bold = True
                run.font.size = Pt(8)
            cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

        # Data rows
        for pi, prompt in enumerate(prompt_list, start=1):
            table.cell(pi, 0).text = prompt
            for run in table.cell(pi, 0).paragraphs[0].runs:
                run.font.size = Pt(8)

            for ei, eng in enumerate(engines):
                cell = table.cell(pi, ei + 1)
                r = prompts[prompt].get(eng)
                if not r:
                    cell.text = "—"
                    _set_cell_shading(cell, "F3F4F6")
                elif r.get("mentioned"):
                    pos = r.get("position")
                    q = r.get("quality_score", 0)
                    cell.text = f"#{pos}" if pos else "Yes"
                    bg = "DCFCE7" if q >= 50 else "D9F99D" if q >= 25 else "FEF9C3"
                    _set_cell_shading(cell, bg)
                else:
                    cell.text = "No"
                    _set_cell_shading(cell, "FECACA")

                cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
                for run in cell.paragraphs[0].runs:
                    run.font.size = Pt(8)

        doc.add_paragraph()


def _add_trend_section(doc: Document, history: list[dict]):
    """Historical trend showing mention rate over time."""
    doc.add_heading("Trend Over Time", level=1)

    p = doc.add_paragraph()
    _add_run(p, "Your AI search visibility across recent weekly checks:", size=10, color=GRAY)
    doc.add_paragraph()

    # Only show runs with actual data
    valid = [h for h in history if h.get("total", 0) > 0 or h.get("total_queries", 0) > 0]
    if not valid:
        doc.add_paragraph("No historical data available yet.")
        return

    table = doc.add_table(rows=1 + len(valid), cols=5)
    table.style = "Light Grid Accent 1"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    for i, header in enumerate(["Date", "Mentions", "Rate", "Avg Position", "Change"]):
        cell = table.cell(0, i)
        cell.text = header
        for run in cell.paragraphs[0].runs:
            run.bold = True
            run.font.size = Pt(9)

    for ri, run_data in enumerate(valid, start=1):
        date = run_data.get("date") or run_data.get("run_date", "")
        mentions = run_data.get("mentions", run_data.get("total_mentions", 0))
        total = run_data.get("total", run_data.get("total_queries", 0))
        rate = run_data.get("rate", run_data.get("mention_rate", 0))
        if isinstance(rate, float) and rate <= 1:
            rate = round(rate * 100, 1)
        avg_pos = run_data.get("avg_position")
        delta = run_data.get("delta")

        table.cell(ri, 0).text = date
        table.cell(ri, 1).text = f"{mentions}/{total}"
        table.cell(ri, 2).text = f"{rate}%"
        table.cell(ri, 3).text = f"#{avg_pos:.1f}" if avg_pos else "—"

        delta_cell = table.cell(ri, 4)
        if delta is not None:
            sign = "+" if delta > 0 else ""
            delta_cell.text = f"{sign}{delta}"
        else:
            delta_cell.text = "baseline"

    for row in table.rows:
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.font.size = Pt(9)

    doc.add_paragraph()


def _add_recommendations(doc: Document, customer: dict, run_data: dict, results: list[dict]):
    """AI-powered recommendations based on the results."""
    doc.add_heading("Recommendations", level=1)

    mention_rate = run_data.get("mention_rate", 0)
    if isinstance(mention_rate, float) and mention_rate <= 1:
        mention_rate = mention_rate * 100

    engines = run_data.get("engines", {})
    name = customer.get("name", "your business")

    recs = []

    # Check brand awareness
    brand_results = [r for r in results if (r.get("category") or r.get("prompt_category")) == "brand"]
    brand_mentions = sum(1 for r in brand_results if r.get("mentioned"))
    if brand_results and brand_mentions / len(brand_results) < 0.5:
        recs.append(
            "Strengthen Brand Presence — AI engines are not consistently recognizing your business name. "
            "Ensure your website has comprehensive 'About' content, structured data (Schema.org), "
            "and that your business is referenced on authoritative third-party sites."
        )

    # Check service visibility
    svc_results = [r for r in results if (r.get("category") or r.get("prompt_category")) == "service"]
    svc_mentions = sum(1 for r in svc_results if r.get("mentioned"))
    if svc_results and svc_mentions / len(svc_results) < 0.3:
        recs.append(
            "Improve Service-Specific Content — Your services are not being surfaced in AI search. "
            "Create dedicated, detailed pages for each service with real patient outcomes, "
            "procedure descriptions, and FAQ sections that AI models can reference."
        )

    # Check location visibility
    loc_results = [r for r in results if (r.get("category") or r.get("prompt_category")) == "location"]
    loc_mentions = sum(1 for r in loc_results if r.get("mentioned"))
    if loc_results and loc_mentions / len(loc_results) < 0.3:
        recs.append(
            "Boost Local Visibility — AI engines are not connecting your business to local searches. "
            "Optimize your Google Business Profile, build local citations, and create "
            "neighborhood-specific landing pages with genuine local content."
        )

    # General AI optimization
    if mention_rate < 20:
        recs.append(
            "Implement llms.txt — Add an llms.txt file to your website to help AI models "
            "understand your business. This emerging standard (similar to robots.txt for AI) "
            "provides structured information that AI assistants can reference when making recommendations."
        )

    # Engine-specific
    active_engines = {k: v for k, v in engines.items() if v.get("status") != "no_api_key"}
    zero_engines = [k for k, v in active_engines.items() if v.get("mentions", 0) == 0]
    if zero_engines:
        recs.append(
            f"Zero Visibility on {', '.join(zero_engines)} — These AI engines returned zero mentions. "
            f"Each engine has different data sources and recency. Focus on building citations "
            f"and content that these specific engines are likely to crawl."
        )

    if not recs:
        recs.append(
            f"Strong Performance — {name} is performing well across AI search engines. "
            f"Continue publishing fresh, authoritative content and maintaining structured data "
            f"to sustain and improve these results."
        )

    for i, rec in enumerate(recs, 1):
        p = doc.add_paragraph()
        _add_run(p, f"{i}. ", bold=True, size=10, color=BLUE)
        # Split first sentence as bold
        parts = rec.split(" — ", 1)
        if len(parts) == 2:
            _add_run(p, parts[0], bold=True, size=10, color=DARK)
            _add_run(p, f" — {parts[1]}", size=10, color=GRAY)
        else:
            _add_run(p, rec, size=10, color=DARK)

    doc.add_paragraph()


def _add_footer(doc: Document, brand_name: str):
    """Add confidential footer."""
    doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _add_run(p, "_" * 50, color=RGBColor(0xE5, 0xE7, 0xEB))
    p2 = doc.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _add_run(p2, f"Generated by {brand_name}  |  practicerank.ai  |  Confidential", size=8, color=LIGHT_GRAY)
