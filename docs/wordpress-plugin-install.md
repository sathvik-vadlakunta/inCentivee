# PracticeRank SEO — WordPress Plugin Install & Wiring

The **PracticeRank SEO** plugin lets the GEO agent manage a client's WordPress
site over a REST API: publish blog posts/pages, inject JSON-LD schema, and serve
`llms.txt`, `llms-full.txt`, `robots.txt`, and (optionally) `sitemap.xml`.

- Plugin source: `wp-plugins/practicerank-seo.php`
- Upload artifact: `wp-plugins/practicerank-seo.zip` (rebuild with the snippet at
  the bottom whenever the `.php` changes — the zip does **not** auto-update)

## What it does

| Capability | Endpoint / mechanism | Notes |
|---|---|---|
| Blog posts & pages | `POST /wp-json/practicerank/v1/content` | `wp_insert_post`; drafts by default; dup-slug → update |
| Update content | `PUT /wp-json/practicerank/v1/content/{id}` | |
| JSON-LD schema | `POST .../schema` → injected into `<head>` | global + per-page + FAQ |
| llms.txt / llms-full.txt | `POST .../files` → served at `/llms.txt` | real root paths via rewrite rules |
| robots.txt | `POST .../files` + `robots_txt` filter | full override, or append AI-crawler rules |
| sitemap.xml | `POST .../files` → served at `/sitemap.xml` | **opt-in** (see below) |
| Health / discovery | `GET .../health`, `.../site-info` | |

Auth: every write requires the `X-PracticeRank-Key` header. The key is
auto-generated on activation.

## Install (manual, ~5 min per site)

1. **Rebuild the zip** if the plugin changed (snippet at bottom).
2. WordPress Admin → **Plugins → Add New → Upload Plugin** → choose
   `practicerank-seo.zip` → **Install Now** → **Activate**.
3. Go to **Settings → PracticeRank**.
4. Copy the **API Key** (read-only, 40 chars).
5. (Optional) Toggle **Managed Sitemap** — see the warning below.
6. Send the API key + the site's base URL back to the PracticeRank operator.

## Wire it into PracticeRank

The agent resolves WordPress credentials per customer:

- `platform` must be `wordpress` (Hilltop is already set).
- The API key is stored as the customer secret **`WP_API_KEY`**.
- The site URL is derived from the customer's `domain` field
  (`https://{domain}`) — so `domain` must be the **WordPress** host.

Two ways to store the key:

- **Dashboard (preferred):** customer detail page → WordPress section →
  paste key → **Test Connection** (`POST /api/wordpress/test-connection`,
  hits the plugin's `/health`). On success it flips WordPress access to
  `granted`.
- **Env fallback:** `WP_API_KEY_<CUSTOMER_ID_UPPER_SNAKE>` in the droplet `.env`
  (e.g. `WP_API_KEY_HILLTOP_FAMILY_DENTAL=...`).

## ⚠️ Sitemap toggle — leave OFF if an SEO plugin is present

WordPress core serves `/wp-sitemap.xml`, and Yoast / RankMath serve their own
sitemap and will fight a second one. **Managed Sitemap is OFF by default.** Only
enable it if the site has **no** SEO plugin and you want PracticeRank to own the
sitemap. Content we publish via `/content` becomes a real WP post, so it lands in
the native/Yoast sitemap automatically either way — enabling our sitemap is only
for full manual control.

When enabled: the plugin serves the pushed `sitemap.xml` at `/sitemap.xml`,
adds a `Sitemap:` line to robots.txt, and flushes rewrite rules.

## ⚠️ Hilltop-specific blocker

Hilltop's stored `domain` is `www.hilltopfamilydentalwy.com`, which currently
resolves to **Webflow** (apex + www → `proxy-ssl.webflow.com`). The WordPress
site they log into is on a **different host** we haven't identified yet. Before
wiring Hilltop:

1. Get the actual WordPress URL (staging/temp/old domain or GoDaddy address).
2. Install + activate the plugin there.
3. Either point the customer `domain` at the WP host, or confirm the publish URL
   matches the WordPress site (the publisher uses `https://{customer.domain}`).

## Rebuild the zip after editing the plugin

```bash
python3 - <<'PY'
import zipfile
data = open('wp-plugins/practicerank-seo.php','rb').read()
with zipfile.ZipFile('wp-plugins/practicerank-seo.zip','w',zipfile.ZIP_DEFLATED) as z:
    z.writestr('practicerank-seo/practicerank-seo.php', data)
print('rebuilt', len(data), 'bytes')
PY
```

Lint before shipping (no local PHP needed):

```bash
scp -i ~/.ssh/id_ed25519_do wp-plugins/practicerank-seo.php kody@129.212.138.145:/tmp/pr-seo.php
ssh -i ~/.ssh/id_ed25519_do kody@129.212.138.145 \
  "docker run --rm -v /tmp/pr-seo.php:/p.php:ro php:8.2-cli php -l /p.php"
```
