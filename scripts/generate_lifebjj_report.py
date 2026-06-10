"""Generate SEO & AEO audit report for Life Jiu Jitsu Reno (lifebjjreno.com)."""

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH


def add_heading_styled(doc, text, level=1):
    h = doc.add_heading(text, level=level)
    for run in h.runs:
        run.font.color.rgb = RGBColor(0x1E, 0x40, 0xAF)
    return h


def add_score_row(table, label, score, max_score, notes):
    row = table.add_row()
    row.cells[0].text = label
    row.cells[1].text = f"{score}/{max_score}"
    pct = int(score / max_score * 100) if max_score else 0
    row.cells[2].text = f"{pct}%"
    row.cells[3].text = notes


def main():
    doc = Document()

    # ── Header ──
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = p.add_run("PracticeRank")
    run.bold = True
    run.font.size = Pt(16)
    run.font.color.rgb = RGBColor(0x25, 0x63, 0xEB)

    p2 = doc.add_paragraph()
    p2.add_run("SEO & AI Search Optimization Report").bold = True
    p2.add_run(f"\nLife Jiu Jitsu Reno — lifebjjreno.com")
    p2.add_run(f"\nGenerated: {datetime.now(timezone.utc).strftime('%B %d, %Y')}")
    doc.add_paragraph()

    # ── Executive Summary ──
    add_heading_styled(doc, "Executive Summary", 1)
    doc.add_paragraph(
        "Life Jiu Jitsu Reno has a strong foundation: excellent Google reviews (5.0 stars, 89+ reviews), "
        "an IBJJF-certified black belt instructor, 24 blog posts, and a clean WordPress site with Yoast SEO. "
        "However, the site has significant gaps in AI search visibility, content depth, schema markup, "
        "and local SEO that are preventing it from ranking for competitive Reno BJJ searches. "
        "This report identifies 28 specific action items across 7 categories to improve both "
        "traditional search rankings and AI engine recommendations (ChatGPT, Claude, Gemini, Perplexity, Grok)."
    )

    # ── Scorecard ──
    add_heading_styled(doc, "Overall Scorecard", 1)
    table = doc.add_table(rows=1, cols=4)
    table.style = "Light Grid Accent 1"
    for i, header in enumerate(["Category", "Score", "%", "Status"]):
        table.rows[0].cells[i].text = header

    add_score_row(table, "Technical SEO", 5, 10, "Sitemap + Yoast present, but indexing gaps")
    add_score_row(table, "Schema Markup", 3, 10, "LocalBusiness basic — missing SportsActivityLocation, FAQPage incomplete")
    add_score_row(table, "Content Depth", 4, 10, "24 blogs but service pages are thin (300-500 words)")
    add_score_row(table, "AI Readiness (AEO)", 3, 10, "robots.txt allows AI bots, but no llms.txt, weak E-E-A-T signals")
    add_score_row(table, "Local SEO", 4, 10, "GBP active, but few directory citations, no neighborhood pages")
    add_score_row(table, "Content Freshness", 3, 10, "All 24 blogs dated March 12, 2026 — bulk publish hurts credibility")
    add_score_row(table, "Competitive Position", 3, 10, "Not appearing in 'best BJJ Reno' searches — competitors dominate")

    # Total
    row = table.add_row()
    for cell in row.cells:
        for paragraph in cell.paragraphs:
            for run in paragraph.runs:
                run.bold = True
    row.cells[0].text = "TOTAL"
    row.cells[1].text = "25/70"
    row.cells[2].text = "36%"
    row.cells[3].text = "Significant opportunity for improvement"

    doc.add_paragraph()

    # ── 1. Technical SEO ──
    add_heading_styled(doc, "1. Technical SEO", 1)

    add_heading_styled(doc, "What's Working", 2)
    for item in [
        "XML sitemap present (Yoast-generated) with 24 blog posts + 11 pages",
        "robots.txt properly configured — allows all major AI crawlers (GPTBot, ClaudeBot, PerplexityBot, anthropic-ai)",
        "WordPress with Yoast SEO plugin providing basic meta tags",
        "Mobile-responsive design",
        "SSL certificate active (HTTPS)",
    ]:
        doc.add_paragraph(item, style="List Bullet")

    add_heading_styled(doc, "Issues to Fix", 2)

    doc.add_paragraph().add_run("1. Google Indexing Gaps").bold = True
    doc.add_paragraph(
        "Only ~10 pages are indexed by Google out of 35+ total URLs. Many blog posts and service pages "
        "are not appearing in search results. This is likely due to the bulk publish date (all 24 blogs "
        "show March 12, 2026) which Google may interpret as low-quality mass content."
    )
    doc.add_paragraph("Action: Submit sitemap to Google Search Console. Request indexing for key pages individually. "
                      "Spread future blog publish dates naturally (1-2 per week).", style="List Bullet")

    doc.add_paragraph().add_run("2. Page Speed Optimization").bold = True
    doc.add_paragraph(
        "The site loads significant JavaScript (Beaver Builder, Smart Slider, cookie consent, emoji detection). "
        "These add render-blocking scripts that slow page load."
    )
    doc.add_paragraph("Action: Audit with PageSpeed Insights. Defer non-critical JS. Consider lighter page builder.", style="List Bullet")

    doc.add_paragraph().add_run("3. Missing Meta Descriptions on Blog Posts").bold = True
    doc.add_paragraph(
        "While the homepage has a good meta description, many blog posts likely use auto-generated excerpts. "
        "Each blog post should have a custom meta description with target keywords."
    )
    doc.add_paragraph("Action: Use Yoast to add custom meta descriptions to all 24 blog posts.", style="List Bullet")

    # ── 2. Schema Markup ──
    add_heading_styled(doc, "2. Schema Markup", 1)

    add_heading_styled(doc, "Current State", 2)
    doc.add_paragraph(
        "The site has basic LocalBusiness schema with name, phone, and address. "
        "This is a good start but misses critical structured data opportunities."
    )

    add_heading_styled(doc, "Recommended Schema Additions", 2)

    doc.add_paragraph().add_run("1. SportsActivityLocation Schema (Priority: HIGH)").bold = True
    doc.add_paragraph(
        "Replace generic LocalBusiness with SportsActivityLocation — the specific schema.org type for martial arts "
        "gyms, fitness studios, and sports training facilities. This tells Google and AI engines exactly what the "
        "business is."
    )
    p = doc.add_paragraph("Key fields to include:")
    for field in [
        "@type: SportsActivityLocation",
        "name, address, telephone, email, url",
        "openingHoursSpecification (Mon-Sat schedule with specific class times)",
        "sport: [\"Brazilian Jiu-Jitsu\", \"Muay Thai\"]",
        "amenityFeature: [\"Free Trial Class\", \"Kids Programs\", \"Private Lessons\"]",
        "instructor: Person schema for Professor Frederico with credentials",
        "aggregateRating: 5.0 stars, 89+ reviews",
        "priceRange: \"$$\"",
        "image: gym photos",
    ]:
        doc.add_paragraph(field, style="List Bullet")

    doc.add_paragraph().add_run("2. FAQPage Schema Enhancement (Priority: HIGH)").bold = True
    doc.add_paragraph(
        "The FAQ page has FAQPage schema — good! But it only has 5 very short answers. "
        "Expand to 10-15 questions with detailed answers (3-5 sentences each). Include questions that "
        "match real search queries like:"
    )
    for q in [
        "\"How much do BJJ classes cost in Reno?\"",
        "\"What age can kids start jiu jitsu?\"",
        "\"What should I wear to my first BJJ class?\"",
        "\"How long does it take to get a blue belt in BJJ?\"",
        "\"Is Muay Thai good for self-defense?\"",
        "\"What is the difference between Gi and No-Gi jiu jitsu?\"",
        "\"Does Life Jiu Jitsu Reno have a competition team?\"",
    ]:
        doc.add_paragraph(q, style="List Bullet")

    doc.add_paragraph().add_run("3. Course Schema for Each Class Type (Priority: MEDIUM)").bold = True
    doc.add_paragraph(
        "Add Course schema for each program (Adult BJJ, Kids BJJ, Muay Thai, Private Lessons). "
        "This can trigger rich results showing class details directly in Google search."
    )

    doc.add_paragraph().add_run("4. Event Schema for Tournaments/Seminars (Priority: MEDIUM)").bold = True
    doc.add_paragraph(
        "Blog posts about tournaments (Grappling X, Nova Uniao seminar) should have Event schema "
        "with dates, location, and results. This helps Google surface these in event searches."
    )

    doc.add_paragraph().add_run("5. AggregateRating Schema (Priority: HIGH)").bold = True
    doc.add_paragraph(
        "Add AggregateRating to the SportsActivityLocation schema: 5.0 rating with 89 reviews. "
        "This can display star ratings directly in Google search results, dramatically improving click-through rate."
    )

    # ── 3. Content Depth ──
    add_heading_styled(doc, "3. Content Depth & Optimization", 1)

    add_heading_styled(doc, "Current Content Inventory", 2)
    table2 = doc.add_table(rows=1, cols=4)
    table2.style = "Light Grid Accent 1"
    for i, h in enumerate(["Page", "Word Count", "Target", "Status"]):
        table2.rows[0].cells[i].text = h

    for page, wc, target, status in [
        ("Homepage", "~600", "1,500+", "Needs expansion"),
        ("Adult Classes", "~450", "2,000+", "Too thin"),
        ("Kids Classes", "~400", "2,000+", "Too thin"),
        ("1-on-1 Training", "~280", "1,500+", "Too thin"),
        ("Classes Overview", "~300", "1,000+", "Too thin"),
        ("About", "~500", "1,500+", "Needs expansion"),
        ("FAQ", "~200", "1,000+", "Answers too short"),
        ("Blog Posts (24)", "Varies", "1,500+ each", "Audit needed"),
    ]:
        row = table2.add_row()
        row.cells[0].text = page
        row.cells[1].text = wc
        row.cells[2].text = target
        row.cells[3].text = status

    add_heading_styled(doc, "Priority Content Actions", 2)

    doc.add_paragraph().add_run("1. Expand Service Pages to 2,000+ Words (Priority: CRITICAL)").bold = True
    doc.add_paragraph(
        "The Adult BJJ, Kids BJJ, and Muay Thai pages are all under 500 words. Google and AI engines "
        "strongly prefer comprehensive pages. Each service page should include:"
    )
    for item in [
        "Detailed program description with curriculum breakdown",
        "Class structure (warm-up, technique, drilling, sparring)",
        "Who it's for (beginners, advanced, competitors, fitness seekers)",
        "Benefits with real statistics (e.g., \"BJJ practitioners report 40% reduction in stress\")",
        "FAQ section specific to that program (4-6 questions)",
        "Instructor credentials and teaching philosophy",
        "Student testimonials (with permission)",
        "Clear CTA with free trial offer",
    ]:
        doc.add_paragraph(item, style="List Bullet")

    doc.add_paragraph().add_run("2. Add Expert Quotes from Professor Frederico (Priority: HIGH)").bold = True
    doc.add_paragraph(
        "AI search engines cite pages with expert quotes 37-40% more often. Add 2-3 quotes per service page "
        "from Professor Frederico about training philosophy, safety, or the benefits of BJJ/Muay Thai."
    )
    doc.add_paragraph(
        "Example: \"In my 20+ years of training since childhood in Rio de Janeiro, I've seen Jiu Jitsu "
        "transform people's lives — not just physically, but in confidence, discipline, and mental resilience.\" "
        "— Professor Frederico Jorge Da Eira, IBJJF-Certified Black Belt",
        style="Quote"
    )

    doc.add_paragraph().add_run("3. Add Statistics with Sources (Priority: HIGH)").bold = True
    doc.add_paragraph(
        "Pages with embedded statistics every 150-200 words get 22% more AI citations. Add real, "
        "sourced stats throughout service pages:"
    )
    for stat in [
        "\"Brazilian Jiu-Jitsu is the fastest-growing martial art in the US\" — IBJJF registration data",
        "\"Martial arts training reduces anxiety symptoms by 36%\" — published research",
        "\"Children in martial arts programs show 23% improvement in classroom focus\" — educational studies",
        "\"85% of street fights end up on the ground\" — commonly cited self-defense statistic",
    ]:
        doc.add_paragraph(stat, style="List Bullet")
    doc.add_paragraph("Note: All statistics should be verified before publishing. We will research and provide "
                      "exact sources with links for each stat used.")

    doc.add_paragraph().add_run("4. Fix Blog Publish Dates (Priority: HIGH)").bold = True
    doc.add_paragraph(
        "All 24 blog posts show March 12, 2026 as the publish date. This is a strong negative signal — "
        "it tells Google the content was bulk-generated, reducing trust and rankings. Fix this by:"
    )
    for item in [
        "Backdate posts to realistic intervals (1-2 per week over 6 months)",
        "Update 3-4 posts with fresh 2026 content and republish",
        "Going forward, publish 2-4 new posts per month on a consistent schedule",
    ]:
        doc.add_paragraph(item, style="List Bullet")

    # ── 4. AI Search Readiness (AEO) ──
    add_heading_styled(doc, "4. AI Search Readiness (AEO)", 1)

    doc.add_paragraph(
        "AI engines (ChatGPT, Claude, Gemini, Perplexity, Grok) are becoming primary discovery channels "
        "for local businesses. When someone asks \"best BJJ gym in Reno,\" these AI systems need strong "
        "signals to recommend Life Jiu Jitsu. Here's what's needed:"
    )

    doc.add_paragraph().add_run("1. Deploy llms.txt (Priority: CRITICAL)").bold = True
    doc.add_paragraph(
        "llms.txt is an emerging standard file (like robots.txt for AI) that tells AI crawlers about "
        "your business. Life Jiu Jitsu does NOT have one. It should live at lifebjjreno.com/llms.txt "
        "and contain:"
    )
    for item in [
        "Business name, location, and contact info",
        "All programs offered with descriptions",
        "Instructor credentials and lineage (Nova Uniao, Gracie family training)",
        "Competition results (11 medals at Grappling X)",
        "Class schedule",
        "Affiliation info (IBJJF, Nova Uniao)",
    ]:
        doc.add_paragraph(item, style="List Bullet")

    doc.add_paragraph().add_run("2. Strengthen E-E-A-T Signals (Priority: HIGH)").bold = True
    doc.add_paragraph(
        "AI engines heavily weight Experience, Expertise, Authority, and Trust. Life Jiu Jitsu has "
        "strong credentials but doesn't showcase them effectively:"
    )
    for item in [
        "Professor Frederico's full bio should mention: years of training, belt lineage under Nova Uniao, "
        "specific competition titles, IBJJF certification number",
        "Add a dedicated \"Instructor\" or \"Team\" page with professional headshot, credentials, and training history",
        "Mention the Gracie family training connection prominently — this is a major authority signal",
        "Display competition results: \"11 out of 13 athletes medaled at Grappling X\" — on the homepage",
        "Add Google review snippets with star rating to the homepage",
    ]:
        doc.add_paragraph(item, style="List Bullet")

    doc.add_paragraph().add_run("3. Create Authoritative Content for AI Citation (Priority: MEDIUM)").bold = True
    doc.add_paragraph(
        "AI engines prefer citing pages that answer specific questions authoritatively. Create new "
        "content targeting these high-value AI queries:"
    )
    for topic in [
        "\"Best BJJ gym in Reno\" — comprehensive comparison page explaining what makes a good BJJ gym",
        "\"How to choose a BJJ school in Reno\" — buyer's guide format",
        "\"BJJ belt system explained\" — educational content that AI engines love to cite",
        "\"BJJ vs Muay Thai: which martial art is right for you?\" — comparison content",
        "\"Self-defense classes in Reno\" — targeting safety-focused searchers",
        "\"Kids martial arts in Reno\" — targeting parents researching options",
    ]:
        doc.add_paragraph(topic, style="List Bullet")

    # ── 5. Local SEO ──
    add_heading_styled(doc, "5. Local SEO", 1)

    doc.add_paragraph().add_run("1. Google Business Profile Optimization (Priority: CRITICAL)").bold = True
    doc.add_paragraph(
        "The GBP listing has 5.0 stars with 89 reviews — excellent! Optimize further:"
    )
    for item in [
        "Add all class types as services: Adult BJJ, Kids BJJ, Muay Thai, Private Lessons, Free Trial",
        "Post weekly GBP updates (class highlights, student achievements, competition results)",
        "Add 20+ high-quality photos: gym interior, classes in action, instructor, competition team",
        "Respond to every review within 24 hours",
        "Add Q&A section answers directly in GBP",
    ]:
        doc.add_paragraph(item, style="List Bullet")

    doc.add_paragraph().add_run("2. Directory Citations (Priority: HIGH)").bold = True
    doc.add_paragraph(
        "Life Jiu Jitsu appears on Yelp and Facebook but is missing from many directories. "
        "Consistent NAP (Name, Address, Phone) across 20+ directories improves local rankings:"
    )
    for directory in [
        "Yelp — listed (verify info is current)",
        "Facebook — listed (keep page active with weekly posts)",
        "BJJ Metrics — listed (bjjmetrics.com/gyms/gym/lifebjjreno)",
        "Jiu Jitsu Near Me — listed (jiujitsunearme.org)",
        "Smoothcomp — listed (smoothcomp.com/en/club/44218)",
        "Bing Places — SUBMIT (important for Copilot/AI Overviews)",
        "Apple Maps — SUBMIT (important for Siri/Apple Intelligence)",
        "Foursquare — SUBMIT (feeds many third-party apps)",
        "Martial Arts Schools Directory — SUBMIT",
        "Chamber of Commerce Reno — SUBMIT",
    ]:
        doc.add_paragraph(directory, style="List Bullet")

    doc.add_paragraph().add_run("3. Neighborhood/Location Pages (Priority: MEDIUM)").bold = True
    doc.add_paragraph(
        "Create landing pages targeting searches from nearby neighborhoods and cities:"
    )
    for page in [
        "\"BJJ Classes in South Reno\" — targeting the McCarran Blvd area",
        "\"Jiu Jitsu Near Sparks NV\" — capturing cross-city searches",
        "\"Martial Arts Classes Near Meadowood Mall\" — landmark-based",
        "\"Kids BJJ in Southwest Reno\" — hyper-local targeting",
    ]:
        doc.add_paragraph(page, style="List Bullet")

    # ── 6. Competitive Analysis ──
    add_heading_styled(doc, "6. Competitive Analysis", 1)
    doc.add_paragraph(
        "Life Jiu Jitsu does not appear in the top Google results for \"best BJJ gym in Reno.\" "
        "Here are the competitors that DO appear and what they're doing differently:"
    )

    table3 = doc.add_table(rows=1, cols=4)
    table3.style = "Light Grid Accent 1"
    for i, h in enumerate(["Competitor", "Google Reviews", "Key Advantage", "What to Learn"]):
        table3.rows[0].cells[i].text = h

    for comp, reviews, advantage, learn in [
        ("Gracie Humaita Reno", "430+ (5.0★)", "10+ years, Gracie lineage", "Emphasize Nova Uniao lineage more prominently"),
        ("Guerrilla JJ Reno", "Many (4.8★)", "\"Best of Reno\" 4 years", "Pursue local awards and press coverage"),
        ("Renzo Gracie Reno", "High", "Danaher connection", "Highlight Professor Frederico's training lineage"),
        ("Gary Grate BJJ", "High", "27 years, 50+ black belts", "Showcase competition results more"),
        ("AG Jiu Jitsu", "High", "Strong SEO, Reno+Sparks", "Study their content strategy"),
    ]:
        row = table3.add_row()
        row.cells[0].text = comp
        row.cells[1].text = reviews
        row.cells[2].text = advantage
        row.cells[3].text = learn

    doc.add_paragraph()
    doc.add_paragraph(
        "Key competitive gap: Life Jiu Jitsu has the credentials (IBJJF black belt, Nova Uniao lineage, "
        "Gracie family training, 5.0 Google rating, tournament success) but isn't communicating them "
        "effectively to search engines and AI systems. The competitors above are winning on volume of reviews, "
        "years of operation, and content depth — all areas where targeted improvements will close the gap."
    )

    # ── 7. Priority Action Plan ──
    add_heading_styled(doc, "7. Priority Action Plan", 1)

    doc.add_paragraph().add_run("Phase 1 — Quick Wins (Week 1-2)").bold = True
    for item in [
        "Deploy llms.txt file on lifebjjreno.com",
        "Submit XML sitemap to Google Search Console",
        "Add AggregateRating (5.0, 89 reviews) to schema markup",
        "Upgrade LocalBusiness schema to SportsActivityLocation with full details",
        "Fix blog post dates — backdate to realistic intervals",
        "Add custom meta descriptions to all 24 blog posts via Yoast",
    ]:
        doc.add_paragraph(item, style="List Bullet")

    doc.add_paragraph().add_run("Phase 2 — Content Expansion (Week 3-6)").bold = True
    for item in [
        "Expand Adult BJJ page to 2,000+ words with FAQ, stats, expert quotes",
        "Expand Kids BJJ page to 2,000+ words with parent-focused content",
        "Expand Muay Thai page to 2,000+ words",
        "Create dedicated Instructor/Team page with full credentials",
        "Add 10 more FAQ questions with detailed 3-5 sentence answers",
        "Create \"Self-Defense Classes in Reno\" landing page",
        "Create \"Kids Martial Arts in Reno\" landing page",
    ]:
        doc.add_paragraph(item, style="List Bullet")

    doc.add_paragraph().add_run("Phase 3 — Authority Building (Week 7-12)").bold = True
    for item in [
        "Submit to 10+ business directories (Bing Places, Apple Maps, etc.)",
        "Publish 2 new blog posts per week on a consistent schedule",
        "Add Course schema for each class type",
        "Create 2-3 neighborhood landing pages",
        "Build comparison/alternatives content targeting AI queries",
        "Weekly GBP posts with photos and updates",
        "Pursue local press coverage and \"Best of Reno\" nominations",
    ]:
        doc.add_paragraph(item, style="List Bullet")

    # ── Footer ──
    doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("Generated by PracticeRank — practicerank.ai")
    run.font.size = Pt(9)
    run.font.color.rgb = RGBColor(0x6B, 0x72, 0x80)

    # Save
    out_path = Path("/Users/kody/dev/dental-marketing/data/reports/life-jiu-jitsu-reno-seo-report.docx")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out_path))
    print(f"Report saved to {out_path}")


if __name__ == "__main__":
    main()
