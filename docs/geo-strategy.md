# Generative Engine Optimization (GEO) Strategy

## Why GEO Matters

- AI-referred website sessions grew **527% YoY** in early 2025
- Patients increasingly ask ChatGPT/Claude "who is the best dentist near me for implants" instead of Googling
- ~25% of health searches already influenced by AI Overviews (projected 40% by 2027)
- Virtually zero dental offices are optimized for this — massive first-mover advantage

## AEO Readiness Checklist

From the DentalRank report scoring system:

- [ ] FAQ Schema Markup
- [ ] LocalBusiness Schema
- [ ] Review/Rating Schema
- [ ] MedicalProcedure Schema
- [ ] Structured Headings (H1/H2/H3)
- [ ] Sufficient Content Depth (300+ words per page)
- [ ] XML Sitemap Present
- [ ] NAP Data Consistent (Name, Address, Phone across all directories)

## Implementation

### Schema Markup (Priority 1 — do within 72 hours of onboarding)

```json
// LocalBusiness schema example
{
  "@context": "https://schema.org",
  "@type": "Dentist",
  "name": "Practice Name",
  "address": { ... },
  "telephone": "...",
  "openingHours": "...",
  "aggregateRating": { ... },
  "medicalSpecialty": ["Cosmetic Dentistry", "Dental Implants"]
}
```

### Content Optimization for AI Extraction

- Service pages must be 2,000+ words with clear structure
- FAQ sections with direct, quotable answers
- Provider bios with credentials, specialties, years of experience
- Procedure pages covering: candidacy, process, timeline, cost, recovery

### Third-Party Authority Building

- Healthgrades, Zocdoc, WebMD profiles fully completed
- Consistent NAP across 50+ directories
- Health directory backlinks

### LLM Monitoring

Weekly automated queries to track how practice appears in:
- ChatGPT ("best dentist for implants in [city]")
- Claude
- Google AI Overviews
- Perplexity
- Microsoft Copilot

Track: mentioned? ranked? what context? what competitors mentioned?

## Impact Projections

- Schema markup alone: **+300% AI visibility within 90 days**
- Full GEO implementation: positions practice among first in market to capture AI-driven referrals
- Combined with traditional SEO: **300-400% increase in organic patient inquiries within 12 months**
