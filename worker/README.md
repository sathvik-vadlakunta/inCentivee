# PracticeRank API Worker

Cloudflare Worker that powers the PracticeRank audit tool and lead capture.

## Endpoints

### `POST /audit` — Run an audit
Called by the practicerank.ai landing page when a user submits the form.

### `GET /leads` — View captured leads
Every audit automatically saves the lead (name, email, phone, website, score) to Cloudflare KV.

**To check leads**, use the Authorization header (preferred) or query param:

```bash
# Preferred — Authorization header (doesn't leak in logs)
curl -H "Authorization: Bearer pr-leads-2024" \
  https://practicerank-api.practice-rank-ai-seo.workers.dev/leads

# Filter by customer domain
curl -H "Authorization: Bearer pr-leads-2024" \
  "https://practicerank-api.practice-rank-ai-seo.workers.dev/leads?domain=downtowndentalsmile"

# Legacy — query param (still works but less secure)
curl "https://practicerank-api.practice-rank-ai-seo.workers.dev/leads?key=pr-leads-2024"
```

Returns JSON with all leads, newest first. Each lead includes:
- Name, email, phone
- Practice website URL and domain
- Audit score and grade
- Practice name, city, state
- Estimated revenue lost
- Executive summary

## Secrets

Managed via `wrangler secret put <NAME>`:

| Secret | Purpose |
|--------|---------|
| `ANTHROPIC_API_KEY` | Claude API key for generating audit reports |
| `LEADS_SECRET` | Auth key for the `/leads` endpoint (currently: `pr-leads-2024`) |

## Deploy

```bash
cd worker
CLOUDFLARE_ACCOUNT_ID="64057faec3376a9cd325386637e90127" npx wrangler deploy
```
