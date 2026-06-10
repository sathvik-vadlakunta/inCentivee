"""Fix Downtown Dental content recommendations.

Fixes:
1. Incorrect/unverifiable source citations → real sources with URLs
2. Missing <a href> linked citations
3. Missing Sources sections on blog posts
4. Stale dental anxiety stat (36% → 42%)
5. Fluff freshness updates → rewritten with real content
6. De-duplicated stats (same 3 stats were in 5+ recs)
"""

import sqlite3
import sys

DB_PATH = sys.argv[1] if len(sys.argv) > 1 else "/app/data/practicerank.db"

# ── Corrected, sourced stats with real URLs ──────────────────────────
# Each post gets DIFFERENT stats to avoid repetition

UPDATES = {}

# ── Blog 1: Prosthodontic Treatment Guide ────────────────────────────
UPDATES["downtown-dental-20260505-00"] = {
    "html_snippet": """<article itemscope itemtype="https://schema.org/Article">
<header>
<h1 itemprop="headline">The Complete Guide to Prosthodontic Treatment: Restoring Function and Beauty</h1>
<p><time datetime="2026-05-15" itemprop="datePublished">Last updated: May 2026</time></p>
</header>

<section>
<p><strong>TLDR:</strong> Prosthodontic treatment at Downtown Dental in Westfield, NJ combines advanced digital technology with specialty-trained precision to restore both function and aesthetics — from single crowns to full mouth reconstructions.</p>

<h2>What is Prosthodontic Treatment?</h2>
<p>Prosthodontics is the dental specialty focused on the restoration and replacement of teeth. The <a href="https://www.ada.org/resources/practice/dental-specialties/prosthodontics" target="_blank" rel="noopener">American Dental Association recognizes prosthodontics</a> as one of only 12 dental specialties, requiring 3 additional years of residency training beyond dental school.</p>

<p>There are only about <a href="https://www.prosthodontics.org/about-acp/" target="_blank" rel="noopener">3,600 board-certified prosthodontists in the United States</a> compared to over 200,000 general dentists — making prosthodontists among the most specialized dental providers available.</p>

<h2>Common Prosthodontic Procedures</h2>

<h3>Crowns and Bridges</h3>
<p>Dental crowns and bridges restore damaged or missing teeth while maintaining natural appearance and function. Modern all-ceramic materials now offer both strength and aesthetics that closely match natural teeth.</p>

<h3>Dentures and Partial Dentures</h3>
<p>According to the <a href="https://www.nidcr.nih.gov/research/data-statistics/tooth-loss" target="_blank" rel="noopener">National Institute of Dental and Craniofacial Research</a>, approximately 26% of adults aged 65-74 have lost all their teeth. Modern dentures offer improved comfort and functionality through digital design and precision manufacturing.</p>

<h3>Dental Implant Restorations</h3>
<p>A <a href="https://www.sciencedirect.com/science/article/abs/pii/S0300571219300491" target="_blank" rel="noopener">systematic review published in the Journal of Dentistry</a> found that dental implants have a cumulative survival rate of approximately 96.4% at 10 years. At Downtown Dental, we combine implant placement with expertly crafted restorations for comprehensive tooth replacement.</p>

<h3>Full Mouth Reconstruction</h3>
<p>For patients with extensive dental damage or wear, full mouth reconstruction addresses all aspects of oral health and function. This comprehensive approach may combine multiple treatments to achieve optimal results.</p>

<h2>Advanced Technology in Prosthodontic Care</h2>
<p>Our Westfield practice uses CAD/CAM (Computer-Aided Design/Manufacturing) technology for precise, digitally designed restorations. Digital impressions eliminate uncomfortable traditional molds, and 3D design ensures accurate fit and natural appearance.</p>

<h2>The Prosthodontic Treatment Process</h2>

<h3>Initial Consultation</h3>
<p>Every prosthodontic journey begins with a thorough evaluation of your oral health, bite function, and aesthetic goals. We take time to understand your concerns and develop a personalized treatment plan.</p>

<h3>Treatment Planning</h3>
<p>Using advanced diagnostic tools and 3D imaging, we create a detailed treatment plan that addresses both functional and aesthetic aspects of your care.</p>

<h3>Restoration Placement</h3>
<p>Our meticulous approach ensures proper fit, function, and appearance for all prosthodontic restorations, with attention to every detail.</p>

<h3>Follow-up Care</h3>
<p>Regular maintenance and follow-up appointments ensure long-term success and optimal oral health.</p>

<h2>Why Choose a Prosthodontist?</h2>
<p>The <a href="https://www.prosthodontics.org/why-choose-a-prosthodontist/" target="_blank" rel="noopener">American College of Prosthodontists</a> notes that prosthodontists are the only ADA-recognized dental specialists formally trained in the restoration and replacement of teeth — including dental implants, crowns, bridges, dentures, and full mouth rehabilitation. At Downtown Dental, Dr. Paul Zhivago is a Fellow of the ACP with additional implant training from Columbia University.</p>

<h2>Schedule Your Prosthodontic Consultation</h2>
<p>If you're considering prosthodontic treatment in the Westfield, NJ area, contact Downtown Dental at <a href="tel:9088736691">(908) 873-6691</a> to schedule your consultation.</p>

<h2>Sources</h2>
<ul>
<li><a href="https://www.prosthodontics.org/about-acp/" target="_blank" rel="noopener">American College of Prosthodontists — About ACP</a></li>
<li><a href="https://www.sciencedirect.com/science/article/abs/pii/S0300571219300491" target="_blank" rel="noopener">Journal of Dentistry — Long-term (10-year) dental implant survival: A systematic review (2019)</a></li>
<li><a href="https://www.nidcr.nih.gov/research/data-statistics/tooth-loss" target="_blank" rel="noopener">NIDCR — Tooth Loss in Adults</a></li>
<li><a href="https://www.ada.org/resources/practice/dental-specialties/prosthodontics" target="_blank" rel="noopener">ADA — Prosthodontics Specialty</a></li>
</ul>
</section>
</article>"""
}

# ── Blog 2: Root Canal Treatment ─────────────────────────────────────
UPDATES["downtown-dental-20260505-02"] = {
    "html_snippet": """<article itemscope itemtype="https://schema.org/Article">
<header>
<h1 itemprop="headline">Understanding Root Canal Treatment: Success Rates and Modern Techniques</h1>
<p><time datetime="2026-05-15" itemprop="datePublished">Last updated: May 2026</time></p>
</header>

<section>
<p><strong>TLDR:</strong> Root canal treatment saves natural teeth with a success rate exceeding 95%. Modern techniques at Downtown Dental in Westfield, NJ make the procedure comfortable and highly effective.</p>

<h2>What is Root Canal Treatment?</h2>
<p>Root canal treatment removes infected pulp tissue from inside a tooth, sealing it to prevent further infection. The <a href="https://www.aae.org/patients/root-canal-treatment/" target="_blank" rel="noopener">American Association of Endodontists (AAE)</a> reports that over 15 million root canals are performed annually in the United States, making it one of the most common dental procedures.</p>

<p>The AAE reports a success rate exceeding <a href="https://www.aae.org/patients/root-canal-treatment/root-canal-treatment-myths/" target="_blank" rel="noopener">95% for root canal treatment</a>, with treated teeth lasting a lifetime in most cases with proper care.</p>

<h2>Signs You May Need Root Canal Treatment</h2>

<h3>Severe Tooth Pain</h3>
<p>Persistent, throbbing pain when biting down or applying pressure often indicates infected or inflamed pulp tissue.</p>

<h3>Prolonged Sensitivity</h3>
<p>Extended sensitivity to hot or cold that lingers after the stimulus is removed may signal the need for endodontic treatment.</p>

<h3>Discoloration</h3>
<p>Darkening of a tooth can indicate internal damage to the pulp tissue.</p>

<h3>Swelling and Tenderness</h3>
<p>Swelling in nearby gums or facial areas may indicate an infected tooth requiring immediate attention.</p>

<h2>Modern Root Canal Techniques</h2>

<h3>Digital Imaging</h3>
<p>Advanced digital X-rays and 3D imaging allow for precise diagnosis and treatment planning.</p>

<h3>Rotary Instrumentation</h3>
<p>Modern rotary instruments clean and shape root canals more efficiently and comfortably than traditional hand files.</p>

<h3>Advanced Irrigation</h3>
<p>Sophisticated irrigation systems thoroughly disinfect the root canal system, reducing the risk of reinfection.</p>

<h2>The Root Canal Process at Downtown Dental</h2>

<h3>Diagnosis and Treatment Planning</h3>
<p>Our thorough examination includes digital imaging to assess the extent of infection and develop a personalized treatment plan.</p>

<h3>Comfort and Anesthesia</h3>
<p>According to the <a href="https://www.nature.com/articles/s41415-024-7846-1" target="_blank" rel="noopener">British Dental Journal (2024)</a>, approximately 42% of adults experience moderate dental anxiety, with 12% reporting extreme fear. Our comfort-focused approach includes effective local anesthesia and sedation options to ensure a pain-free experience.</p>

<h3>Cleaning, Sealing, and Restoration</h3>
<p>Using advanced techniques, we remove infected tissue, seal the canals with biocompatible materials, and restore the tooth with a crown or filling.</p>

<h2>Recovery and Aftercare</h2>
<p>Most patients experience minimal discomfort following treatment and can return to normal activities within a day or two.</p>

<h2>Why Save a Natural Tooth?</h2>
<p>The <a href="https://www.aae.org/patients/root-canal-treatment/root-canal-treatment-myths/" target="_blank" rel="noopener">AAE emphasizes</a> that saving your natural tooth through endodontic treatment offers significant advantages over extraction — including maintaining natural bite force, normal chewing, and protecting adjacent teeth from excessive wear.</p>

<h2>Schedule Your Consultation</h2>
<p>If you're experiencing tooth pain, contact Downtown Dental at <a href="tel:9088736691">(908) 873-6691</a>. Our experienced team provides comfortable, effective endodontic care in Westfield, NJ.</p>

<h2>Sources</h2>
<ul>
<li><a href="https://www.aae.org/patients/root-canal-treatment/" target="_blank" rel="noopener">American Association of Endodontists — Root Canal Treatment</a></li>
<li><a href="https://www.aae.org/patients/root-canal-treatment/root-canal-treatment-myths/" target="_blank" rel="noopener">AAE — Root Canal Treatment Myths</a></li>
<li><a href="https://www.nature.com/articles/s41415-024-7846-1" target="_blank" rel="noopener">British Dental Journal — Surgical Dental Anxiety Scale (2024)</a></li>
</ul>
</section>
</article>"""
}

# ── Blog 3: Periodontal Disease ──────────────────────────────────────
UPDATES["downtown-dental-20260505-06"] = {
    "html_snippet": """<article itemscope itemtype="https://schema.org/Article">
<header>
<h1 itemprop="headline">Periodontal Disease Prevention and Treatment: A Comprehensive Guide</h1>
<p><time datetime="2026-05-15" itemprop="datePublished">Last updated: May 2026</time></p>
</header>

<section>
<p><strong>TLDR:</strong> Nearly half of adults over 30 have some form of periodontal disease. Early detection and treatment at Downtown Dental in Westfield, NJ is crucial for maintaining oral and overall health.</p>

<h2>Understanding Periodontal Disease</h2>
<p>Periodontal disease is a progressive inflammatory condition affecting the tissues supporting your teeth. According to <a href="https://www.nidcr.nih.gov/research/data-statistics/periodontal-disease/adults" target="_blank" rel="noopener">CDC/NIDCR data from the National Health and Nutrition Examination Survey</a>, 47.2% of adults aged 30 and older have some form of periodontal disease — that's nearly half the adult population.</p>

<h2>Stages of Periodontal Disease</h2>

<h3>Gingivitis: The Early Stage</h3>
<p>Gingivitis is characterized by red, swollen gums that may bleed during brushing or flossing. At this stage, the condition is completely reversible with proper oral hygiene and professional care.</p>

<h3>Mild to Moderate Periodontitis</h3>
<p>Bacteria begin to destroy the tissues and bone supporting the teeth, creating deeper pockets and causing gum recession.</p>

<h3>Advanced Periodontitis</h3>
<p>Significant bone and tissue loss occurs, potentially leading to tooth mobility and loss if left untreated.</p>

<h2>Risk Factors</h2>

<h3>Smoking and Tobacco Use</h3>
<p>The <a href="https://www.cdc.gov/oral-health/risk-factors/tobacco.html" target="_blank" rel="noopener">CDC reports</a> that smokers are about twice as likely to develop periodontal disease compared to non-smokers, and smoking impairs healing after treatment.</p>

<h3>Systemic Health Conditions</h3>
<p>The <a href="https://www.perio.org/for-patients/gum-disease-information/gum-disease-and-other-diseases/" target="_blank" rel="noopener">American Academy of Periodontology</a> notes strong bidirectional links between periodontal disease and diabetes, cardiovascular disease, and respiratory conditions.</p>

<h3>Genetic Predisposition</h3>
<p>Some individuals may be genetically predisposed to developing periodontal disease despite good oral hygiene habits.</p>

<h2>Prevention Strategies</h2>

<h3>Professional Cleanings</h3>
<p>Regular professional cleanings and examinations are essential for early detection. Our team at Downtown Dental provides thorough cleanings in a comfortable, spa-like environment.</p>

<h3>Effective Home Care</h3>
<p>Proper brushing technique, daily flossing, and antimicrobial rinses form the foundation of prevention.</p>

<h2>Modern Treatment Options</h2>

<h3>Scaling and Root Planing</h3>
<p>This deep cleaning removes bacteria and toxins from below the gum line and smooths root surfaces to promote healing.</p>

<h3>Laser Therapy</h3>
<p>Advanced laser treatments can effectively eliminate bacteria and infected tissue while promoting faster healing.</p>

<h3>Regenerative Procedures</h3>
<p>When appropriate, regenerative treatments can help restore lost bone and tissue around affected teeth.</p>

<h2>The Connection Between Periodontal and Overall Health</h2>
<p>The <a href="https://www.who.int/news-room/fact-sheets/detail/oral-health" target="_blank" rel="noopener">World Health Organization</a> reports that severe periodontal disease affects approximately 19% of the global adult population, representing more than 1 billion cases worldwide. Research continues to reveal connections between periodontal disease and systemic conditions including cardiovascular disease and diabetes.</p>

<h2>Schedule Your Periodontal Evaluation</h2>
<p>Early detection is key. Contact Downtown Dental at <a href="tel:9088736691">(908) 873-6691</a> to schedule your comprehensive periodontal evaluation in Westfield, NJ.</p>

<h2>Sources</h2>
<ul>
<li><a href="https://www.nidcr.nih.gov/research/data-statistics/periodontal-disease/adults" target="_blank" rel="noopener">NIDCR — Periodontal Disease in Adults (CDC/NHANES data)</a></li>
<li><a href="https://www.cdc.gov/oral-health/risk-factors/tobacco.html" target="_blank" rel="noopener">CDC — Tobacco Use and Periodontal Disease</a></li>
<li><a href="https://www.perio.org/for-patients/gum-disease-information/gum-disease-and-other-diseases/" target="_blank" rel="noopener">AAP — Gum Disease and Other Diseases</a></li>
<li><a href="https://www.who.int/news-room/fact-sheets/detail/oral-health" target="_blank" rel="noopener">WHO — Oral Health Fact Sheet</a></li>
</ul>
</section>
</article>"""
}

# ── FAQ: Whitening ───────────────────────────────────────────────────
UPDATES["downtown-dental-20260505-01"] = {
    "html_snippet": """<div itemscope itemtype="https://schema.org/FAQPage">
<h2>Frequently Asked Questions About Professional Teeth Whitening</h2>

<div itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
<h3 itemprop="name">How effective is professional teeth whitening compared to over-the-counter products?</h3>
<div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
<div itemprop="text">
<p>Professional teeth whitening can brighten teeth by 3 to 8 shades in a single visit, compared to 1-2 shades with over-the-counter strips, according to the <a href="https://www.ada.org/resources/ada-library/oral-health-topics/whitening" target="_blank" rel="noopener">American Dental Association</a>. At Downtown Dental in Westfield, NJ, our professional whitening uses higher-concentration agents and custom-fitted trays that aren't available in retail products, delivering superior and more consistent results.</p>
</div>
</div>
</div>

<div itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
<h3 itemprop="name">Is professional teeth whitening safe for my enamel?</h3>
<div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
<div itemprop="text">
<p>Yes, professional teeth whitening is safe when performed under dental supervision. The <a href="https://www.ada.org/resources/ada-library/oral-health-topics/whitening" target="_blank" rel="noopener">ADA notes</a> that hydrogen peroxide and carbamide peroxide-based whitening products, when used as directed, do not damage tooth enamel. Our team conducts thorough evaluations before treatment to ensure candidacy and safety.</p>
</div>
</div>
</div>

<div itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
<h3 itemprop="name">How long do professional whitening results last?</h3>
<div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
<div itemprop="text">
<p>Professional whitening results typically last 1-3 years with proper maintenance and lifestyle choices. Avoiding staining foods and beverages (coffee, red wine, tea) and using take-home maintenance kits can extend the results significantly.</p>
</div>
</div>
</div>

<div itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
<h3 itemprop="name">Can I get my teeth whitened if I have sensitive teeth?</h3>
<div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
<div itemprop="text">
<p>Yes. We offer specialized whitening protocols for patients with sensitive teeth, including desensitizing treatments and customized whitening schedules. Professional supervision allows us to adjust concentration and timing to minimize sensitivity while achieving excellent results.</p>
</div>
</div>
</div>
</div>"""
}

# ── FAQ: Implant Success Rate ────────────────────────────────────────
UPDATES["downtown-dental-20260505-04"] = {
    "html_snippet": """<div itemscope itemtype="https://schema.org/FAQPage">
<h2>Dental Implant Success Rate and Longevity FAQ</h2>

<div itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
<h3 itemprop="name">What is the success rate of dental implants?</h3>
<div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
<div itemprop="text">
<p>Dental implants have a cumulative survival rate of approximately 96.4% at 10 years, according to a <a href="https://www.sciencedirect.com/science/article/abs/pii/S0300571219300491" target="_blank" rel="noopener">systematic review and meta-analysis published in the Journal of Dentistry</a>. At Downtown Dental in Westfield, NJ, our meticulous surgical techniques and comprehensive follow-up care contribute to consistently excellent implant outcomes.</p>
</div>
</div>
</div>

<div itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
<h3 itemprop="name">How long do dental implants last?</h3>
<div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
<div itemprop="text">
<p>With proper care, the titanium implant itself can last a lifetime — it integrates permanently with your jawbone through a process called osseointegration. The crown restoration on top may need replacement after 15-20 years of normal use. Our team provides comprehensive care instructions to maximize implant longevity.</p>
</div>
</div>
</div>

<div itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
<h3 itemprop="name">Am I a good candidate for dental implants?</h3>
<div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
<div itemprop="text">
<p>Most healthy adults with sufficient bone density are excellent candidates. During your consultation at Downtown Dental, we use digital imaging including 3D scans to evaluate bone structure and develop a personalized treatment plan. Even patients with some bone loss may be candidates with bone grafting procedures.</p>
</div>
</div>
</div>

<div itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
<h3 itemprop="name">What makes Downtown Dental different for implant treatment?</h3>
<div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
<div itemprop="text">
<p>Dr. Paul Zhivago is a <a href="https://www.prosthodontics.org/why-choose-a-prosthodontist/" target="_blank" rel="noopener">Fellow of the American College of Prosthodontists</a> with implant training from Columbia University College of Dental Medicine. As a prosthodontist, he has 3 additional years of specialty training beyond dental school focused specifically on restoring and replacing teeth — including implant planning, placement, and restoration.</p>
</div>
</div>
</div>
</div>"""
}

# ── FAQ: Dental Anxiety ──────────────────────────────────────────────
UPDATES["downtown-dental-20260505-08"] = {
    "html_snippet": """<div itemscope itemtype="https://schema.org/FAQPage">
<h2>Frequently Asked Questions About Comfort and Anxiety</h2>

<div itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
<h3 itemprop="name">Do you help patients with dental anxiety?</h3>
<div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
<div itemprop="text">
<p>Absolutely. According to the <a href="https://www.nature.com/articles/s41415-024-7846-1" target="_blank" rel="noopener">British Dental Journal (2024)</a>, approximately 42% of adults experience moderate dental anxiety, with 12% reporting extreme fear. At Downtown Dental in Westfield, NJ, our spa-like environment and comfort-focused approach are specifically designed to help anxious patients feel relaxed and welcome.</p>
</div>
</div>
</div>

<div itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
<h3 itemprop="name">What comfort options do you offer for nervous patients?</h3>
<div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
<div itemprop="text">
<p>We offer sedation options, take time to explain every procedure before starting, and prioritize communication throughout your visit. Our spa-like atmosphere and gentle team approach help create a calming experience. We also allow patients to set the pace and take breaks during treatment.</p>
</div>
</div>
</div>

<div itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
<h3 itemprop="name">Can I discuss my anxiety before my appointment?</h3>
<div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
<div itemprop="text">
<p>We encourage it. Call us at <a href="tel:9088736691">(908) 873-6691</a> to discuss your concerns and learn about our comfort options before your visit. Knowing what to expect helps many patients feel more at ease.</p>
</div>
</div>
</div>
</div>"""
}

# ── Freshness: Services → REWRITTEN with real digital dentistry content
UPDATES["downtown-dental-20260505-05"] = {
    "rec_type": "stat_injection",
    "title": "Add Digital Dentistry Technology Section to Services Page",
    "description": "Add specific details about CAD/CAM and digital dentistry capabilities that differentiate Downtown Dental, with verifiable technology references.",
    "html_snippet": """<section class="digital-dentistry-highlight">
<h2>Digital Dentistry at Downtown Dental</h2>
<p>Downtown Dental uses CAD/CAM (Computer-Aided Design and Manufacturing) technology for designing and fabricating dental restorations in-house. Digital impressions replace traditional putty molds, and 3D design software allows Dr. Zhivago to plan each restoration with sub-millimeter precision.</p>

<p>As a <a href="https://www.prosthodontics.org/why-choose-a-prosthodontist/" target="_blank" rel="noopener">Fellow of the American College of Prosthodontists</a>, Dr. Zhivago also serves as Course Director of Digital Dentistry for the Post Graduate Prosthodontics Department at <a href="https://dental.nyu.edu/" target="_blank" rel="noopener">NYU College of Dentistry</a> — bringing academic-level digital expertise directly to patient care in Westfield, NJ.</p>

<p>Our digital workflow includes:</p>
<ul>
<li><strong>Digital impressions</strong> — no uncomfortable putty trays</li>
<li><strong>3D treatment planning</strong> — precise implant placement and restoration design</li>
<li><strong>CAD/CAM restorations</strong> — custom crowns, veneers, and bridges designed digitally</li>
<li><strong>Guided surgery</strong> — computer-guided implant placement for accuracy and faster healing</li>
</ul>
</section>"""
}

# ── Freshness: Doctors → REWRITTEN with verifiable credential details
UPDATES["downtown-dental-20260505-09"] = {
    "rec_type": "expert_quote",
    "title": "Add Dr. Zhivago Credential Highlights to Doctor Page",
    "description": "Add verifiable credential details and academic role information to strengthen Dr. Zhivago's authority signals for AI search.",
    "html_snippet": """<section class="doctor-credentials-highlight">
<h2>Dr. Paul Zhivago's Qualifications</h2>
<p>Dr. Zhivago holds a Doctor of Dental Surgery (DDS) degree and completed advanced prosthodontic residency training and an implant fellowship at <a href="https://www.dental.columbia.edu/" target="_blank" rel="noopener">Columbia University College of Dental Medicine</a>. He is a Fellow of the <a href="https://www.prosthodontics.org/" target="_blank" rel="noopener">American College of Prosthodontists (FACP)</a>, the premier professional organization for prosthodontists.</p>

<p>In addition to private practice, Dr. Zhivago serves as Clinical Associate Professor in the Department of Prosthodontics at <a href="https://dental.nyu.edu/" target="_blank" rel="noopener">NYU College of Dentistry</a>, where he directs the Digital Dentistry course for postgraduate prosthodontics residents. He lectures nationally and internationally on digital dentistry.</p>

<p><strong>Professional Memberships:</strong></p>
<ul>
<li><a href="https://www.prosthodontics.org/" target="_blank" rel="noopener">American College of Prosthodontists</a> (Fellow)</li>
<li><a href="https://www.ada.org/" target="_blank" rel="noopener">American Dental Association</a></li>
<li>Greater New York Academy of Prosthodontics</li>
</ul>
</section>"""
}

# ── Stat injection: About page ───────────────────────────────────────
UPDATES["downtown-dental-20260505-03"] = {
    "html_snippet": """<div class="practice-mission-stats">
<p>At Downtown Dental in Westfield, NJ, we recognize that <a href="https://www.ada.org/resources/community-initiatives/action-for-dental-health" target="_blank" rel="noopener">100 million Americans fail to see a dentist each year</a> according to the American Dental Association. This drives our commitment to creating a welcoming environment where every patient feels comfortable seeking care.</p>

<p>We also understand that dental anxiety is common — the <a href="https://www.nature.com/articles/s41415-024-7846-1" target="_blank" rel="noopener">British Dental Journal (2024)</a> reports that approximately 42% of adults experience moderate dental anxiety, with 12% experiencing extreme fear. Our spa-like atmosphere and comfort-focused approach are designed to help anxious patients receive the care they need.</p>
</div>"""
}

# ── Stat injection: Blog landing ─────────────────────────────────────
UPDATES["downtown-dental-20260505-07"] = {
    "html_snippet": """<div class="blog-stats-highlight">
<h2>Evidence-Based Dental Care Insights</h2>
<p>Our blog provides dental care insights backed by clinical research. For example, the <a href="https://www.cdc.gov/mmwr/volumes/65/wr/mm6541e1.htm" target="_blank" rel="noopener">CDC's Vital Signs report</a> found that <strong>dental sealants reduce the risk of cavities in molars by nearly 80%</strong> in the first two years after placement — highlighting the importance of preventive treatments for children and adults.</p>

<p>We're committed to sharing accurate, sourced information to help our Westfield, NJ community make informed decisions about oral health.</p>
</div>"""
}


def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    for rec_id, fields in UPDATES.items():
        # Build SET clause dynamically from provided fields
        set_parts = []
        values = []
        for key, value in fields.items():
            set_parts.append(f"{key} = ?")
            values.append(value)

        values.append(rec_id)
        sql = f"UPDATE content_recommendations SET {', '.join(set_parts)} WHERE id = ?"
        cursor.execute(sql, values)
        print(f"Updated {rec_id}: {cursor.rowcount} row(s)")

    conn.commit()
    total = cursor.execute(
        "SELECT COUNT(*) FROM content_recommendations WHERE customer_id = 'downtown-dental'"
    ).fetchone()[0]
    print(f"\nDone. {total} total Downtown Dental recs in DB.")
    conn.close()


if __name__ == "__main__":
    main()
