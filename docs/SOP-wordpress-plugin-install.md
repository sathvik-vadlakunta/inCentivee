# SOP — Install PracticeRank SEO on a Client's WordPress (Backup First)

**Audience:** PracticeRank operator onboarding a WordPress client.
**Outcome:** the PracticeRank SEO plugin installed, the MCP endpoint live, and
Claude Code able to manage the site — with a tested rollback path.
**Time:** ~20–30 min (most of it the backup).
**Golden rule:** **Never touch the site until you have a verified backup you have
restored-tested at least once before.**

---

## Phase 0 — Pre-flight (record the starting state)

Do this before changing anything. Write the answers into the client's spec
(`specs/customers/<client>.md`).

1. Confirm you have **WP admin access** (or the client does, screen-share).
2. Record:
   - WordPress version (Dashboard → Updates, or Tools → Site Health → Info)
   - PHP version (Site Health → Info → Server)
   - Active theme + builder (Elementor/Divi/etc.)
   - **Existing SEO plugin?** (Yoast / RankMath / AIOSEO) — decides the sitemap toggle
   - Hosting provider + how to reach a backup (host panel, SFTP, plugin)
3. Capture the current public state (so you can prove nothing broke):
   - Save `https://SITE/robots.txt`, `https://SITE/sitemap.xml` (or `/wp-sitemap.xml`)
   - Screenshot the homepage and one key service page
   - `curl -s -o /dev/null -w '%{http_code}\n' https://SITE/` → expect `200`

> ⚠️ **Plugin requirements:** WP 5.6+ / PHP 7.4+. The plugin self-checks on
> activation and refuses to activate below that — it will not half-install.

---

## Phase 1 — BACKUP (do not skip)

Take **both** a file backup and a database backup. Use whichever you can verify.

**Option A — Host snapshot (preferred).** Most managed hosts (Kinsta, WP Engine,
SiteGround, GoDaddy) have one-click "create backup / restore point." Trigger it,
wait for completion, note the restore-point ID/time.

**Option B — Backup plugin (UpdraftPlus).**
1. Plugins → Add New → search **UpdraftPlus** → Install → Activate.
2. Settings → UpdraftPlus Backups → **Backup Now** → check *both* "database" and
   "files" → Backup Now.
3. Wait for "The backup apparently succeeded and is now complete." Download the
   5 archive files (db, plugins, themes, uploads, others) to your machine.

**Option C — Manual (technical hosts with SFTP + DB access).**
- Files: SFTP-download the WordPress root (at minimum `wp-content/`).
- DB: host panel → phpMyAdmin → Export, or WP-CLI: `wp db export backup.sql`.

**Verify the backup (mandatory):** confirm the DB dump is non-empty and the file
archive opens. If you can, restore it to a staging copy once so you *know* it works.
A backup you haven't validated is not a backup.

---

## Phase 2 — Install the plugin

1. Rebuild the zip if the plugin changed (see "Rebuild" at the bottom) — ship the
   freshest `wp-plugins/practicerank-seo.zip`.
2. WP Admin → **Plugins → Add New → Upload Plugin** → choose `practicerank-seo.zip`
   → **Install Now** → **Activate**.
3. The plugin is **purely additive** — it registers a REST namespace, a settings
   page, and `<head>`/`robots.txt` filters. It does **not** modify your theme,
   posts, or existing plugins. Content it creates is a **draft by default**.

---

## Phase 3 — Configure

1. **Settings → PracticeRank.**
2. Copy the **API Key** (read-only, 40 chars). This is the secret for both the
   REST API and the MCP endpoint.
3. **Schema Injection** — leave ON.
4. **AI Robots.txt** — leave ON.
5. **Managed Sitemap** — **leave OFF** if Yoast/RankMath/AIOSEO is present (it
   already owns the sitemap). Only turn ON if there is no SEO plugin and we want
   PracticeRank to control `/sitemap.xml`.
6. Confirm the **REST API** row shows a `…/practicerank/v1/health` URL.

---

## Phase 4 — Wire into PracticeRank

1. Customer must be `platform = wordpress` (set in the dashboard / DB).
2. Store the API key as the customer secret **`WP_API_KEY`** — dashboard customer
   page → WordPress section → paste → **Test Connection** (hits `/health`). Green =
   good. (Env fallback: `WP_API_KEY_<CUSTOMER_ID_UPPER_SNAKE>` in the droplet `.env`.)
3. The publish URL is derived from the customer's `domain` (`https://{domain}`), so
   `domain` **must be the WordPress host**. If WordPress lives on a different
   hostname than the public site, set `domain` to the WordPress host.

---

## Phase 5 — Connect Claude Code (the MCP endpoint)

The plugin ships its own MCP server (Streamable HTTP) — **no adapter plugin, no
Node proxy**. Connect with one command (API key as the bearer token):

```bash
claude mcp add <client> https://SITE/wp-json/practicerank/v1/mcp \
  --transport http \
  --header "Authorization: Bearer <API_KEY_FROM_SETTINGS>"
```

Then in Claude Code: `/mcp` should list the server and its tools
(`health`, `get_site_info`, `publish_content`, `update_content`, `push_schema`,
`push_files`). Try: *"call health on \<client\>"* — you should get site info back.

---

## Phase 6 — Verify (prove it works, safely)

1. `curl -s https://SITE/wp-json/practicerank/v1/health -H "Authorization: Bearer KEY"`
   → JSON with `status: ok`, `version: 2.1`, `mcp_endpoint: …`.
2. Via Claude Code, publish a **draft** test post (`publish_content`, leave
   `publish` false). Confirm it appears under Posts → Drafts. Delete it.
3. Re-check the items from Phase 0: homepage still `200`, robots.txt/sitemap as
   expected. Nothing public changed unless you intended it.

---

## Rollback (if anything looks wrong)

1. **First response:** Plugins → **Deactivate** "PracticeRank SEO." All its filters
   and routes stop instantly; the site returns to its pre-install behavior. Then
   **Delete** the plugin if needed.
2. If a deeper problem (unlikely — the plugin doesn't alter core data): restore the
   Phase 1 backup (host restore-point, or UpdraftPlus → Existing Backups → Restore).
3. Revoke access: Settings → PracticeRank can't rotate the key from the UI, so to
   kill API access, deactivate the plugin (or have a dev delete the
   `practicerank_api_key` option). Re-activating generates a fresh key.

---

## Why this is safe (and won't break the site)

- The MCP endpoint and REST routes are **isolated** — a bug there returns a JSON
  error, it cannot break page rendering.
- The whole MCP/REST surface is **behind the API-key check** (constant-time
  compare); there is no anonymous write access.
- Tools **reuse the existing handlers**, so all input sanitization (`wp_kses`,
  `sanitize_*`), draft-by-default, and duplicate-slug protection apply.
- The plugin exposes **no delete/destructive tool** — the most it does is create
  drafts, update content you point it at, and write files into
  `wp-content/uploads/practicerank/`.
- Errors are caught and never leak stack traces to the client.

---

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

Lint (no local PHP needed):
```bash
scp -i ~/.ssh/id_ed25519_do wp-plugins/practicerank-seo.php kody@129.212.138.145:/tmp/pr-seo.php
ssh -i ~/.ssh/id_ed25519_do kody@129.212.138.145 \
  "docker run --rm -v /tmp/pr-seo.php:/p.php:ro php:8.2-cli php -l /p.php"
```
