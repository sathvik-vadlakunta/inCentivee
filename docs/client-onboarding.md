# Client Onboarding Process

## Access Requirements

All of these are blockers — implementation cannot start without them.

### 1. Google Search Console
- Add jonlucas@lostrelic.com as **Full user**
- Path: Settings > Users and permissions > Add user

### 2. Google Analytics
- Add jonlucas@lostrelic.com as **Editor**
- Path: Admin > Property Access Management > Add user

### 3. Google Tag Manager
- Add jonlucas@lostrelic.com as **User with Publish access**
- Path: Admin > User Management > Add user

### 4. Webflow (or other CMS)
- Invite as site collaborator
- Path: Project settings > Members > Invite
- **Also need**: Site-level API token for automated content publishing
- Path: Project settings > Integrations > Generate API token
- API token must be sent securely (not over email)

### 5. Google Business Profile
- Add as **Manager**
- Path: People and access > Add user

### 6. DNS / Domain Access
- Need access to domain registrar (GoDaddy, Namecheap, etc.)
- Purpose: Point DNS to Cloudflare (free plan) for speed + security
- Options: delegate access or temporary login for nameserver update

### 7. Brand Voice
- How should the practice come across in writing?
- Friendly/casual? Professional/warm? Clinical/authoritative?
- Even 1-2 sentences is enough

## 7-Day Launch Timeline

| Day | Action | Who |
|-----|--------|-----|
| 1 | 30-min kickoff call. Collect logins, brand assets, specialties. | Ops |
| 1-2 | Connect PMS via middleware API. Sync patient data. | Automated |
| 2-3 | CRM sub-account from dental template. Review sequences activated. | Automated |
| 3-4 | GBP audit and optimization. Citations submitted. Schema deployed. | Semi-auto + ops |
| 4-5 | GEO content generated and published. AI monitoring activated. | AI + ops approval |
| 5-6 | Google Ads campaigns from templates. Tracking configured. | Template + ops |
| 7 | Everything live. Dashboard access. First review requests sent. | Automated |

**Total ops time per onboarding: ~4-6 hours**

## Current Clients

### Hilltop Dental (Dr. David Gallup)
- **Status**: Onboarding in progress
- Google Search Console: LINKED (as of March 24, 2026)
- Webflow API token: PENDING
- Website platform: Webflow
- Contacts: Adam Milmont (amilmont@gmail.com) handles tech access
