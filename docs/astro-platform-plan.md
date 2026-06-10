# PracticeRank Website Platform — Full Automation Plan

## Test Case: Sojo Dental (sojodental.com)

**Goal**: Port Sojo Dental from DentalQore WordPress to an Astro site on Cloudflare Pages that PracticeRank fully owns and automates — then replicate for every customer.

---

## 1. Architecture Overview

```
dental-marketing/                    # Existing repo (Python agent + dashboard)
├── geo_agent/                       # Existing — SEO/AEO agent
├── dashboard/                       # Existing — Flask admin
├── worker/                          # Existing — Cloudflare Worker (audit tool)
├── sites/                           # NEW — All customer Astro sites
│   ├── _template/                   # Base template (forked per customer)
│   └── sojo-dental/                 # First customer site
└── packages/
    └── practicerank-ui/             # Shared Astro component library
```

Each customer site is an **independent Astro project** inside `sites/`, deployed to its own Cloudflare Pages project. The monorepo approach means Claude can work across all sites from one repo, and shared components update everywhere.

---

## 2. Tech Stack (Final)

| Layer | Tool | Why |
|-------|------|-----|
| Framework | **Astro 5.x** | Zero JS by default, built-in i18n, content collections, Cloudflare-owned |
| Styling | **Tailwind CSS 4** | Utility-first, consistent across sites, Claude writes it fluently |
| Hosting | **Cloudflare Pages** | Free unlimited bandwidth, preview deploys per branch, 300+ edge locations |
| Content | **Markdown/MDX in git** | Claude edits .md files directly — no CMS API needed |
| Admin CMS | **Keystatic** | Git-backed visual editor, stores as markdown, works with Astro |
| Auth | **Cloudflare Access** | Zero-trust login (email OTP or Google SSO) for /keystatic admin |
| Staging | **Cloudflare Pages Preview Deployments** | Every branch auto-gets a unique URL |
| Forms | **Cloudflare Workers** | Contact form → email/CRM, no 3rd party |
| Analytics | **Cloudflare Web Analytics** | Free, privacy-respecting, no cookie banner needed |
| Images | **Cloudflare Images** or local `/public/images/` | CDN-optimized delivery |
| DNS | **Cloudflare** | Already managing DNS for most clients |

**Cost per customer site: $0/month** (all free tiers)

---

## 3. Monorepo Structure

```
dental-marketing/
├── sites/
│   ├── _template/                          # Base template (copy for new clients)
│   │   ├── astro.config.mjs
│   │   ├── keystatic.config.tsx
│   │   ├── tailwind.config.mjs
│   │   ├── package.json
│   │   ├── tsconfig.json
│   │   ├── src/
│   │   │   ├── content/
│   │   │   │   ├── config.ts               # Content collection schemas
│   │   │   │   ├── blog/                    # Blog posts (markdown)
│   │   │   │   │   └── .gitkeep
│   │   │   │   ├── services/                # Service pages (markdown)
│   │   │   │   │   └── .gitkeep
│   │   │   │   └── team/                    # Doctor/team bios (markdown)
│   │   │   │       └── .gitkeep
│   │   │   ├── data/
│   │   │   │   └── practice.json            # Practice info (name, address, phone, hours, etc.)
│   │   │   ├── layouts/
│   │   │   │   └── Base.astro               # HTML shell, nav, footer, schema injection
│   │   │   ├── pages/
│   │   │   │   ├── index.astro              # Homepage (fully custom per client)
│   │   │   │   ├── about.astro              # About page
│   │   │   │   ├── contact.astro            # Contact page
│   │   │   │   ├── services/
│   │   │   │   │   ├── index.astro          # Services listing
│   │   │   │   │   └── [...slug].astro      # Dynamic service page from content collection
│   │   │   │   ├── blog/
│   │   │   │   │   ├── index.astro          # Blog listing
│   │   │   │   │   └── [...slug].astro      # Blog post from content collection
│   │   │   │   ├── team/
│   │   │   │   │   └── [...slug].astro      # Team member page
│   │   │   │   └── keystatic/
│   │   │   │       └── [...params].astro    # Keystatic admin UI
│   │   │   ├── components/
│   │   │   │   ├── Nav.astro                # Navigation (reads practice.json)
│   │   │   │   ├── Footer.astro             # Footer (reads practice.json)
│   │   │   │   ├── ContactForm.astro        # Form → Cloudflare Worker
│   │   │   │   ├── SchemaMarkup.astro       # JSON-LD auto-generated from practice.json
│   │   │   │   ├── ReviewStars.astro        # Google review widget
│   │   │   │   ├── MapEmbed.astro           # Google Maps embed
│   │   │   │   ├── ServiceCard.astro        # Service listing card
│   │   │   │   ├── BlogCard.astro           # Blog post card
│   │   │   │   ├── TeamCard.astro           # Team member card
│   │   │   │   ├── Hero.astro               # Reusable hero (props: title, subtitle, bg, cta)
│   │   │   │   └── CTABanner.astro          # Call-to-action banner
│   │   │   └── styles/
│   │   │       └── global.css               # Tailwind base + CSS custom properties
│   │   └── public/
│   │       ├── llms.txt                     # Auto-generated by geo_agent
│   │       ├── llms-full.txt                # Auto-generated by geo_agent
│   │       ├── robots.txt                   # Auto-generated by geo_agent
│   │       ├── favicon.svg
│   │       └── images/                      # Client photos, logos
│   │           └── .gitkeep
│   │
│   └── sojo-dental/                         # Sojo Dental (first real site)
│       ├── (same structure as _template, but customized)
│       ├── src/
│       │   ├── data/
│       │   │   └── practice.json            # Sojo-specific practice data
│       │   ├── content/
│       │   │   ├── services/
│       │   │   │   ├── dental-implant-placement.md
│       │   │   │   ├── dental-veneers.md
│       │   │   │   ├── teeth-whitening.md
│       │   │   │   ├── root-canal-therapy.md
│       │   │   │   ├── dental-cleanings-exams.md
│       │   │   │   ├── wisdom-teeth-removal.md
│       │   │   │   ├── iv-sedation.md
│       │   │   │   ├── same-day-dental-crowns.md
│       │   │   │   ├── dental-bridges.md
│       │   │   │   ├── dentures.md
│       │   │   │   ├── dental-fillings.md
│       │   │   │   ├── pediatric-dentistry.md
│       │   │   │   └── mini-dental-implants.md
│       │   │   ├── team/
│       │   │   │   ├── dr-brian-call.md
│       │   │   │   └── dr-conner-ogden.md
│       │   │   └── blog/
│       │   │       └── .gitkeep
│       │   ├── pages/
│       │   │   ├── index.astro              # Custom Sojo homepage
│       │   │   ├── about.astro              # Custom about page
│       │   │   └── contact.astro            # Custom contact page
│       │   └── styles/
│       │       └── global.css               # Sojo brand: sage green #90C969, forest green #3C8043
│       └── public/
│           └── images/
│               ├── logo.svg
│               ├── hero.jpg
│               ├── dr-call.jpg
│               └── dr-ogden.jpg
```

---

## 4. practice.json — Single Source of Truth

Every site has one `practice.json` that drives nav, footer, schema markup, llms.txt, and contact info:

```json
{
  "name": "SoJo Dental",
  "domain": "sojodental.com",
  "tagline": "Comprehensive Family & Implant Dentistry in South Jordan, Utah",
  "phone": "(801) 260-9150",
  "email": "info@sojodental.com",
  "address": {
    "street": "3473 W South Jordan Parkway, Ste. #2",
    "city": "South Jordan",
    "state": "UT",
    "zip": "84095"
  },
  "geo": {
    "lat": 40.561636,
    "lng": -111.973761
  },
  "hours": [
    { "days": "Monday-Thursday", "open": "8:00 AM", "close": "5:00 PM" },
    { "days": "Friday", "open": "8:00 AM", "close": "2:00 PM" },
    { "days": "Saturday-Sunday", "note": "Closed" }
  ],
  "providers": [
    {
      "name": "Dr. Brian Call",
      "slug": "dr-brian-call",
      "credentials": "DMD",
      "title": "General Dentist",
      "specialties": ["Implant Dentistry", "Cosmetic Dentistry", "Restorative Dentistry"],
      "photo": "/images/dr-call.jpg"
    },
    {
      "name": "Dr. Conner Ogden",
      "slug": "dr-conner-ogden",
      "credentials": "DMD",
      "title": "General Dentist",
      "specialties": ["General Dentistry", "Pediatric Dentistry", "Endodontics"],
      "photo": "/images/dr-ogden.jpg"
    }
  ],
  "serviceCategories": [
    "Cosmetic Dentistry",
    "Endodontics",
    "General & Family Dentistry",
    "Implant Dentistry",
    "Pediatric Dentistry",
    "Restorative Dentistry"
  ],
  "insurance": "Most major dental insurance plans accepted",
  "financing": "Cherry Financing available",
  "social": {
    "google": "https://g.page/sojo-dental",
    "facebook": "",
    "yelp": ""
  },
  "colors": {
    "primary": "#90C969",
    "secondary": "#3C8043",
    "dark": "#1B1C1D",
    "light": "#FAF8F6"
  },
  "fonts": {
    "heading": "Gotu",
    "body": "Outfit"
  },
  "patientPortal": "https://patientportal-mw.carestack.com/?dn=sojo",
  "maps": "https://www.google.com/maps/place/SoJo+Dental"
}
```

---

## 5. Content Collection Schemas

`src/content/config.ts`:

```typescript
import { defineCollection, z } from 'astro:content'

const services = defineCollection({
  type: 'content',
  schema: z.object({
    title: z.string(),
    description: z.string(),
    category: z.string(),
    icon: z.string().optional(),
    image: z.string().optional(),
    order: z.number().default(0),
    faqs: z.array(z.object({
      question: z.string(),
      answer: z.string(),
    })).optional(),
  }),
})

const team = defineCollection({
  type: 'content',
  schema: z.object({
    name: z.string(),
    credentials: z.string(),
    title: z.string(),
    photo: z.string().optional(),
    specialties: z.array(z.string()).default([]),
    education: z.array(z.string()).default([]),
    order: z.number().default(0),
  }),
})

const blog = defineCollection({
  type: 'content',
  schema: z.object({
    title: z.string(),
    description: z.string(),
    pubDate: z.date(),
    updatedDate: z.date().optional(),
    author: z.string().default('SoJo Dental'),
    image: z.string().optional(),
    tags: z.array(z.string()).default([]),
    draft: z.boolean().default(false),
  }),
})

export const collections = { services, team, blog }
```

---

## 6. Automation Pipelines

### 6A. Content Publishing Pipeline (Claude → Branch → Preview → Approve → Live)

```
┌──────────────────────────────────────────────────────────────┐
│                    CONTENT PIPELINE                            │
│                                                                │
│  1. GEO Agent generates content recommendation                │
│     → "Blog post: 5 Signs You Need a Root Canal"             │
│     → Approved in PracticeRank dashboard                      │
│                                                                │
│  2. Claude creates branch:                                     │
│     git checkout -b content/sojo/root-canal-signs             │
│                                                                │
│  3. Claude writes the markdown file:                           │
│     sites/sojo-dental/src/content/blog/                       │
│       5-signs-you-need-a-root-canal.md                        │
│                                                                │
│  4. Claude commits + pushes:                                   │
│     git add sites/sojo-dental/                                │
│     git commit -m "Add blog: 5 Signs You Need a Root Canal"  │
│     git push origin content/sojo/root-canal-signs             │
│                                                                │
│  5. Cloudflare Pages auto-builds preview:                     │
│     → https://content-sojo-root-canal-signs.sojodental.pages.dev │
│                                                                │
│  6. Client notified (email/dashboard):                         │
│     "New blog post ready for review — click to preview"       │
│                                                                │
│  7. Client approves:                                           │
│     Option A: Clicks "Approve" in Keystatic admin             │
│     Option B: Jon merges PR in dashboard                      │
│     Option C: API call from PracticeRank dashboard            │
│                                                                │
│  8. Branch merges to main → auto-deploys to production        │
│     → https://sojodental.com/blog/5-signs-you-need-root-canal │
│                                                                │
│  9. GEO Agent regenerates llms.txt (includes new blog post)   │
│     → Commits to main directly (no approval needed for SEO)   │
└──────────────────────────────────────────────────────────────┘
```

### 6B. SEO/AEO Auto-Update Pipeline (No Approval Needed)

These files are technical — clients don't need to approve them:

```
GEO Agent monthly run
  → Regenerates public/llms.txt
  → Regenerates public/llms-full.txt
  → Regenerates public/robots.txt
  → Updates SchemaMarkup component data (practice.json)
  → Updates sitemap.xml
  → Commits directly to main
  → Auto-deploys in ~30 seconds
```

### 6C. Site Update Pipeline (Design Changes — Needs Approval)

```
Claude edits .astro pages or components
  → Branch: update/sojo/new-hero-section
  → Preview URL generated
  → Client reviews at preview URL
  → Approval → merge → live
```

---

## 7. Git Strategy

### Branch Naming Convention

```
main                                    # Production (auto-deploys)
content/{customer}/{slug}              # Blog/content additions
update/{customer}/{description}        # Design/layout changes
seo/{customer}/{description}           # SEO file updates (auto-merge)
fix/{customer}/{description}           # Bug fixes
```

### Commit Convention

```
[sojo] Add blog: 5 Signs You Need a Root Canal
[sojo] Update hero section with new photos
[sojo] Regenerate llms.txt (monthly run)
[oakridge] Add service page: dental-implants
[template] Add testimonial carousel component
```

### Monorepo Build Isolation

Each site builds independently. Cloudflare Pages is configured per-site:

```
# Cloudflare Pages project: sojo-dental
Build command: cd sites/sojo-dental && npm run build
Build output: sites/sojo-dental/dist
Root directory: /

# Cloudflare Pages project: oakridge-dental
Build command: cd sites/oakridge-dental && npm run build
Build output: sites/oakridge-dental/dist
Root directory: /
```

**Important**: Cloudflare Pages only rebuilds when files in the site's directory change (configurable via `[build.watch_paths]` in `wrangler.toml` or Pages settings).

---

## 8. Keystatic Admin Setup

`keystatic.config.tsx`:

```tsx
import { config, fields, collection } from '@keystatic/core'

export default config({
  storage: { kind: 'github', repo: 'practicerank/dental-marketing' },
  collections: {
    blog: collection({
      label: 'Blog Posts',
      slugField: 'title',
      path: 'sites/sojo-dental/src/content/blog/*',
      format: { contentField: 'content' },
      schema: {
        title: fields.slug({ name: { label: 'Title' } }),
        description: fields.text({ label: 'Description', multiline: true }),
        pubDate: fields.date({ label: 'Publish Date' }),
        author: fields.text({ label: 'Author', defaultValue: 'SoJo Dental' }),
        image: fields.image({ label: 'Cover Image', directory: 'public/images/blog' }),
        tags: fields.array(fields.text({ label: 'Tag' }), { label: 'Tags' }),
        draft: fields.checkbox({ label: 'Draft', defaultValue: true }),
        content: fields.markdoc({ label: 'Content' }),
      },
    }),
    services: collection({
      label: 'Services',
      slugField: 'title',
      path: 'sites/sojo-dental/src/content/services/*',
      format: { contentField: 'content' },
      schema: {
        title: fields.slug({ name: { label: 'Title' } }),
        description: fields.text({ label: 'Description', multiline: true }),
        category: fields.text({ label: 'Category' }),
        order: fields.integer({ label: 'Sort Order', defaultValue: 0 }),
        content: fields.markdoc({ label: 'Content' }),
      },
    }),
    team: collection({
      label: 'Team Members',
      slugField: 'name',
      path: 'sites/sojo-dental/src/content/team/*',
      format: { contentField: 'content' },
      schema: {
        name: fields.slug({ name: { label: 'Name' } }),
        credentials: fields.text({ label: 'Credentials (e.g. DMD, DDS)' }),
        title: fields.text({ label: 'Title' }),
        photo: fields.image({ label: 'Photo', directory: 'public/images/team' }),
        specialties: fields.array(fields.text({ label: 'Specialty' }), { label: 'Specialties' }),
        order: fields.integer({ label: 'Sort Order', defaultValue: 0 }),
        content: fields.markdoc({ label: 'Bio' }),
      },
    }),
  },
})
```

**Access control**: Keystatic admin at `/keystatic` is protected by Cloudflare Access. Only whitelisted emails (Jon + client) can log in.

---

## 9. Cloudflare Pages Deployment Setup

### Per-Customer Cloudflare Pages Project

```bash
# One-time setup per customer
# Option A: Cloudflare dashboard (manual)
# Option B: Wrangler CLI (automatable)

# Create Pages project linked to GitHub repo
npx wrangler pages project create sojo-dental \
  --production-branch main \
  --build-command "cd sites/sojo-dental && npm install && npm run build" \
  --build-output-dir "sites/sojo-dental/dist"

# Set custom domain
npx wrangler pages project set sojo-dental \
  --custom-domain sojodental.com \
  --custom-domain www.sojodental.com

# Set environment variables
npx wrangler pages secret put KEYSTATIC_GITHUB_TOKEN --project-name sojo-dental
```

### wrangler.toml (per site)

```toml
# sites/sojo-dental/wrangler.toml
name = "sojo-dental"
compatibility_date = "2026-05-01"

[build]
command = "npm run build"
watch_paths = ["sites/sojo-dental/"]

[env.production]
routes = [
  { pattern = "sojodental.com/*", zone_name = "sojodental.com" },
  { pattern = "www.sojodental.com/*", zone_name = "sojodental.com" }
]
```

### DNS Migration Plan (Sojo Dental)

Sojo's DNS is currently managed by DentalQore. Migration:

1. **Add Cloudflare nameservers** — request DentalQore to update NS records at registrar
2. **Import existing DNS records** — Cloudflare auto-imports when NS is pointed
3. **Point A/CNAME to Cloudflare Pages** — `sojodental.com` CNAME → `sojo-dental.pages.dev`
4. **Keep email records** (MX, SPF, DKIM) untouched
5. **SSL auto-provisioned** by Cloudflare (free)

**Fallback if DentalQore won't change NS**: Add a CNAME for `new.sojodental.com` → Pages, run in parallel, then flip when ready.

---

## 10. Contact Form Handler (Cloudflare Worker)

```javascript
// worker/contact-form/src/index.js
export default {
  async fetch(request, env) {
    if (request.method !== 'POST') {
      return new Response('Method not allowed', { status: 405 })
    }

    const data = await request.json()
    const { name, email, phone, message, site } = data

    // Send via email (Cloudflare Email Workers or external SMTP)
    await fetch('https://api.mailchannels.net/tx/v1/send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        personalizations: [{
          to: [{ email: env.PRACTICE_EMAIL }],
        }],
        from: { email: 'noreply@practicerank.ai', name: 'PracticeRank' },
        subject: `New appointment request from ${name}`,
        content: [{
          type: 'text/plain',
          value: `Name: ${name}\nEmail: ${email}\nPhone: ${phone}\nMessage: ${message}`,
        }],
      }),
    })

    return Response.json({ success: true })
  },
}
```

---

## 11. GEO Agent Integration

### Updated Publisher: Astro Sites

Add a new publisher to `geo_agent/publishers/` that writes directly to the monorepo:

```python
# geo_agent/publishers/astro_site.py

class AstroSitePublisher:
    """Publishes GEO artifacts directly to Astro site files in the monorepo."""

    def __init__(self, customer_id: str, repo_root: str = "."):
        self.site_dir = Path(repo_root) / "sites" / customer_id

    def publish_llms_txt(self, content: str):
        (self.site_dir / "public" / "llms.txt").write_text(content)

    def publish_llms_full_txt(self, content: str):
        (self.site_dir / "public" / "llms-full.txt").write_text(content)

    def publish_robots_txt(self, content: str):
        (self.site_dir / "public" / "robots.txt").write_text(content)

    def publish_schema(self, schema_json: dict):
        """Write schema to practice.json — SchemaMarkup.astro reads it."""
        practice_json = self.site_dir / "src" / "data" / "practice.json"
        data = json.loads(practice_json.read_text())
        data["schema"] = schema_json
        practice_json.write_text(json.dumps(data, indent=2))

    def publish_blog_post(self, slug: str, frontmatter: dict, content: str):
        """Write a blog post markdown file."""
        post_dir = self.site_dir / "src" / "content" / "blog"
        post_dir.mkdir(parents=True, exist_ok=True)
        md = "---\n"
        md += yaml.dump(frontmatter, default_flow_style=False)
        md += "---\n\n"
        md += content
        (post_dir / f"{slug}.md").write_text(md)

    def publish_sitemap_data(self, pages: list[dict]):
        """Write sitemap data that Astro's sitemap integration reads."""
        # Astro generates sitemap.xml automatically from pages
        # No manual action needed — just ensure pages exist
        pass

    def git_commit_and_push(self, message: str, branch: str = "main"):
        """Commit changes and push. For content, use a feature branch."""
        subprocess.run(["git", "add", str(self.site_dir)], check=True)
        subprocess.run(["git", "commit", "-m", message], check=True)
        subprocess.run(["git", "push", "origin", branch], check=True)
```

### Updated main.py Flow

```python
# In geo_agent/main.py, after generating artifacts:

if customer.platform == "astro":
    publisher = AstroSitePublisher(customer.id)

    # SEO files — commit directly to main (no approval needed)
    publisher.publish_llms_txt(llms_txt_content)
    publisher.publish_llms_full_txt(llms_full_content)
    publisher.publish_robots_txt(robots_txt_content)
    publisher.publish_schema(schema_data)
    publisher.git_commit_and_push(
        f"[{customer.id}] Regenerate SEO files (monthly run)",
        branch="main"
    )

    # Blog posts — create branch for approval
    for post in approved_content_recs:
        branch = f"content/{customer.id}/{post.slug}"
        subprocess.run(["git", "checkout", "-b", branch, "main"])
        publisher.publish_blog_post(post.slug, post.frontmatter, post.content)
        publisher.git_commit_and_push(
            f"[{customer.id}] Add blog: {post.title}",
            branch=branch
        )
        # Cloudflare Pages auto-builds preview URL
        notify_client(customer, post, preview_url=f"https://{branch}.sojodental.pages.dev")
        subprocess.run(["git", "checkout", "main"])
```

---

## 12. Image Strategy

### Current Images (Scrape from DentalQore)

Before taking the WordPress site down, scrape all images:

```bash
# Download all images from current site
wget -r -l1 -A jpg,jpeg,png,svg,webp https://www.sojodental.com/ -P sites/sojo-dental/public/images/
```

### Ongoing Image Management

- **Doctor photos**: Provided by client, stored in `public/images/team/`
- **Service images**: Stock + AI-generated, stored in `public/images/services/`
- **Blog images**: Generated per post, stored in `public/images/blog/`
- **Optimization**: Astro's built-in `<Image>` component auto-generates WebP/AVIF + responsive sizes

---

## 13. Sojo Dental — Site Porting Checklist

### Phase 1: Setup (Day 1)

- [ ] Create `sites/sojo-dental/` from `sites/_template/`
- [ ] Populate `practice.json` with Sojo's data (address, phone, hours, providers, colors, fonts)
- [ ] Download logo + all images from current WordPress site
- [ ] Install Astro + Tailwind + Keystatic dependencies
- [ ] Verify `npm run dev` works locally

### Phase 2: Content Migration (Day 1-2)

- [ ] Create all service page markdown files (22 services across 6 categories)
- [ ] Create team member markdown files (Dr. Brian Call, Dr. Conner Ogden)
- [ ] Write `practice.json` with complete business data
- [ ] Set up CSS custom properties matching Sojo's brand colors/fonts
- [ ] Verify content renders correctly in dev

### Phase 3: Custom Pages (Day 2-3)

- [ ] Build homepage (`index.astro`) — custom hero, service grid, testimonials, CTA
- [ ] Build about page (`about.astro`) — practice story, provider cards
- [ ] Build contact page (`contact.astro`) — form, map, hours, directions
- [ ] Build service listing page (`services/index.astro`)
- [ ] Build dynamic service page template (`services/[...slug].astro`)
- [ ] Build blog listing + post templates
- [ ] Ensure mobile responsiveness

### Phase 4: SEO & Schema (Day 3)

- [ ] Generate `llms.txt` and `llms-full.txt` via GEO agent
- [ ] Generate `robots.txt`
- [ ] Implement `SchemaMarkup.astro` (Dentist, FAQPage, MedicalProcedure, LocalBusiness)
- [ ] Auto-generate `sitemap.xml` via Astro integration
- [ ] Set up meta tags (title, description, og:image) per page
- [ ] Verify with Google Rich Results Test

### Phase 5: Keystatic Admin (Day 3-4)

- [ ] Configure Keystatic collections (blog, services, team)
- [ ] Set up GitHub repo connection for Keystatic
- [ ] Test creating/editing blog posts via admin UI
- [ ] Set up Cloudflare Access for `/keystatic` route

### Phase 6: Deployment (Day 4)

- [ ] Create Cloudflare Pages project for `sojo-dental`
- [ ] Connect to GitHub repo
- [ ] Configure build command and output directory
- [ ] Deploy to `sojo-dental.pages.dev` (staging)
- [ ] Test all pages, forms, schema, performance
- [ ] Run Lighthouse audit (target: 95+ performance, 100 SEO, 100 accessibility)

### Phase 7: DNS Migration (Day 5)

- [ ] Request DentalQore to update nameservers to Cloudflare
- [ ] Import all existing DNS records into Cloudflare
- [ ] Add custom domain `sojodental.com` to Cloudflare Pages
- [ ] Verify SSL certificate provisioned
- [ ] Test live site at sojodental.com
- [ ] Set up 301 redirects for any URL changes
- [ ] Verify Google Search Console still works
- [ ] Submit updated sitemap to GSC

### Phase 8: Automation Verification (Day 5-6)

- [ ] Run GEO agent against new Astro site — verify llms.txt generation
- [ ] Test content pipeline: create blog branch → preview URL → merge → live
- [ ] Test Keystatic: client login → edit post → save → preview → publish
- [ ] Verify Cloudflare Analytics tracking
- [ ] Decommission old WordPress site (keep backup)

---

## 14. New Customer Onboarding Script

Once the template is proven with Sojo, onboarding a new customer is scripted:

```bash
#!/bin/bash
# scripts/new-site.sh — Create a new customer site from template

CUSTOMER_ID=$1  # e.g., "oakridge-dental"

if [ -z "$CUSTOMER_ID" ]; then
  echo "Usage: ./scripts/new-site.sh <customer-id>"
  exit 1
fi

SITE_DIR="sites/$CUSTOMER_ID"

# 1. Copy template
cp -r sites/_template "$SITE_DIR"

# 2. Replace template placeholders
# (Claude fills in practice.json, custom pages, content)

# 3. Install deps
cd "$SITE_DIR" && npm install

# 4. Create Cloudflare Pages project
npx wrangler pages project create "$CUSTOMER_ID" \
  --production-branch main \
  --build-command "cd sites/$CUSTOMER_ID && npm run build" \
  --build-output-dir "sites/$CUSTOMER_ID/dist"

echo "Site created at $SITE_DIR"
echo "Next steps:"
echo "  1. Fill in src/data/practice.json"
echo "  2. Add service content to src/content/services/"
echo "  3. Add team bios to src/content/team/"
echo "  4. Customize pages in src/pages/"
echo "  5. Run: cd $SITE_DIR && npm run dev"
echo "  6. Push to deploy preview"
```

---

## 15. Dashboard Integration

Add to the PracticeRank dashboard (`dashboard/app.py`):

### New Routes

```python
@app.route('/customers/<customer_id>/site')
def customer_site(customer_id):
    """View customer site status, preview URLs, pending content."""
    # Show: production URL, latest preview URLs, pending branches,
    # last deploy time, Lighthouse scores, content pipeline status
    pass

@app.route('/api/customers/<customer_id>/content/approve', methods=['POST'])
def approve_content(customer_id):
    """Merge a content branch to main (triggers deploy)."""
    branch = request.json['branch']
    # git merge branch → main → push → Cloudflare auto-deploys
    pass

@app.route('/api/customers/<customer_id>/content/reject', methods=['POST'])
def reject_content(customer_id):
    """Close/delete a content branch."""
    branch = request.json['branch']
    # git branch -D branch → git push origin --delete branch
    pass
```

### New Dashboard Tab: "Website"

Shows per customer:
- Production URL + status (green/red)
- Latest Cloudflare Pages deploy timestamp
- Pending content branches with preview URLs
- Approve/Reject buttons
- Lighthouse performance score (cached, run weekly)
- Link to Keystatic admin

---

## 16. Performance Targets

| Metric | Target | How |
|--------|--------|-----|
| Lighthouse Performance | 95+ | Zero JS by default (Astro), optimized images, Cloudflare CDN |
| Lighthouse SEO | 100 | Auto-generated meta, schema, sitemap, semantic HTML |
| Lighthouse Accessibility | 95+ | Semantic HTML, alt text, contrast ratios in template |
| First Contentful Paint | < 1.0s | Static HTML, edge-cached, no JS blocking |
| Largest Contentful Paint | < 1.5s | Optimized hero images, preloaded fonts |
| CLS | 0 | No layout shifts (no dynamic content loading) |
| Time to Interactive | < 1.0s | Zero JS (unless interactive component island) |
| Build time | < 30s | Astro is fast, small site |
| Deploy time | < 60s | Cloudflare Pages builds are fast |

---

## 17. Risk Mitigation

| Risk | Mitigation |
|------|------------|
| DentalQore won't transfer DNS | Run on subdomain first (`new.sojodental.com`), prove value, then migrate |
| Client doesn't like new design | Preview URL for approval before any DNS changes; keep old site as fallback |
| SEO ranking drop during migration | 301 redirects for all old URLs; keep same URL structure; submit sitemap immediately |
| Google Search Console disruption | Re-verify GSC after DNS change; site stays on same domain, so history preserved |
| Keystatic too complex for clients | Simplify to just blog post editing; Jon handles everything else |
| Cloudflare Pages build failures | Each site is independent; one failure doesn't affect others |
| Image quality loss | Download originals before migration; use Astro's image optimization |

---

## 18. Timeline

| Day | Task | Deliverable |
|-----|------|------------|
| 1 | Scaffold template + Sojo site, populate practice.json, migrate content | Working dev server with all content |
| 2 | Build custom homepage, about, contact pages | Pixel-comparable to current site |
| 3 | Service pages, blog templates, schema markup, SEO files | Full site with all pages |
| 4 | Keystatic admin, Cloudflare Access, form handler | Admin panel working |
| 5 | Deploy to Cloudflare Pages, DNS migration | Live at sojodental.com |
| 6 | Test automation pipelines, verify GEO agent integration | End-to-end content pipeline working |

---

## 19. Success Criteria

1. **sojodental.com serves from Cloudflare Pages** — fast, reliable, PracticeRank-controlled
2. **Lighthouse 95+ across all metrics** — faster than DentalQore WordPress
3. **Claude can publish a blog post** by writing a markdown file and pushing a branch
4. **Client can preview changes** at a staging URL before they go live
5. **Client can log into /keystatic** and edit blog posts themselves
6. **GEO agent writes llms.txt/robots.txt** directly to `public/` and auto-deploys
7. **Onboarding a second customer** (Oakridge) takes < 1 day using the template
8. **Zero ongoing hosting cost** — entirely on Cloudflare free tier

---

## 20. After Sojo: Rollout Order

1. **Sojo Dental** — test case (this plan)
2. **Oakridge Dental** — same ownership as Sojo, same DentalQore setup, near-identical template
3. **Downtown Dental** — currently Squarespace, easy to port
4. **Hilltop Dental** — currently Webflow, waiting on access
5. **Paradigm Experts** — different industry (gold/jewelry), proves template works beyond dental
6. **New customers** — onboard directly to Astro (skip WordPress/Webflow entirely)
