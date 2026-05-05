"""Publish content recommendations to Webflow CMS collections.

Maps approved content (blog posts, FAQs) to Webflow CMS items and pushes them live.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone

from geo_agent.db import CustomerDB
from geo_agent.publishers.webflow import WebflowPublisher

logger = logging.getLogger(__name__)

# Rec types that can be published to CMS collections
CMS_PUBLISHABLE_TYPES = {"blog_post", "new_page", "faq_update"}

# Collection type mapping with field definitions
COLLECTION_SCHEMAS = {
    "blog_posts": {
        "display_name": "Blog Posts",
        "slug": "blog-posts",
        "fields": [
            {"displayName": "Post Body", "slug": "post-body", "type": "RichText"},
            {"displayName": "Author", "slug": "author", "type": "PlainText"},
            {"displayName": "Category", "slug": "category", "type": "PlainText"},
            {"displayName": "Published On", "slug": "published-on", "type": "Date"},
            {"displayName": "Meta Description", "slug": "meta-description", "type": "PlainText"},
        ],
    },
    "faqs": {
        "display_name": "FAQs",
        "slug": "faqs",
        "fields": [
            {"displayName": "Answer", "slug": "answer", "type": "RichText"},
            {"displayName": "Page Category", "slug": "page-category", "type": "PlainText"},
            {"displayName": "Sort Order", "slug": "sort-order", "type": "Number"},
        ],
    },
}

REC_TYPE_TO_COLLECTION = {
    "blog_post": "blog_posts",
    "new_page": "blog_posts",
    "faq_update": "faqs",
}


# Auto-template scripts injected into CMS template pages via Custom Code API.
# These render blog posts / FAQs in a styled layout that inherits the site's
# existing Webflow CSS (nav, footer, fonts, colors come from the site stylesheet).
BLOG_TEMPLATE_SCRIPT = """\
(function() {{
  var CUSTOMER_ID = '{customer_id}';
  var API_BASE = 'https://admin.practicerank.ai';

  var LOCALE_LABELS = {{
    en:'English',es:'Espa\\u00f1ol',fr:'Fran\\u00e7ais',de:'Deutsch',
    pt:'Portugu\\u00eas',sv:'Svenska',ja:'\\u65e5\\u672c\\u8a9e',
    ko:'\\ud55c\\uad6d\\uc5b4',zh:'\\u4e2d\\u6587',ar:'\\u0627\\u0644\\u0639\\u0631\\u0628\\u064a\\u0629'
  }};

  var css = document.createElement('style');
  css.textContent = '.pr-blog-article{{max-width:780px;margin:80px auto 100px;padding:0 32px;font-family:Host Grotesk,Geist,-apple-system,sans-serif}}.pr-blog-header{{margin-bottom:48px;padding-bottom:32px;border-bottom:1px solid rgba(255,255,255,.1)}}.pr-blog-title{{font-family:Geist,sans-serif;font-size:clamp(2rem,5vw,3rem);font-weight:600;line-height:1.15;margin-bottom:20px;color:inherit}}.pr-blog-meta{{display:flex;gap:16px;font-size:.9rem;opacity:.6;flex-wrap:wrap;align-items:center}}.pr-blog-meta span{{white-space:nowrap}}.pr-blog-category{{display:inline-block;padding:4px 14px;border-radius:100px;background:rgba(109,40,217,.15);color:#B38BFF;font-size:.8rem;font-weight:500;text-transform:uppercase;letter-spacing:.5px}}.pr-blog-body{{font-size:1.1rem;line-height:1.8}}.pr-blog-body h2{{font-family:Geist,sans-serif;font-size:1.6rem;font-weight:600;margin:2.5rem 0 1rem}}.pr-blog-body h3{{font-family:Geist,sans-serif;font-size:1.25rem;font-weight:600;margin:2rem 0 .75rem}}.pr-blog-body p{{margin:1rem 0}}.pr-blog-body ul,.pr-blog-body ol{{margin:1rem 0;padding-left:1.75rem}}.pr-blog-body li{{margin:.4rem 0}}.pr-blog-body blockquote{{border-left:3px solid #6D28D9;margin:2rem 0;padding:1.25rem 1.5rem;background:rgba(109,40,217,.06);border-radius:0 8px 8px 0;font-style:italic}}.pr-blog-body blockquote cite{{display:block;margin-top:.75rem;font-style:normal;font-weight:600;font-size:.9rem;opacity:.7}}.pr-blog-body a{{color:#B38BFF}}.pr-blog-body strong{{font-weight:600}}.pr-blog-body img{{max-width:100%;border-radius:12px;margin:1.5rem 0}}.pr-blog-loading{{text-align:center;padding:100px 32px;font-size:1.1rem;opacity:.5}}.pr-lang-switcher{{position:relative;display:inline-block}}.pr-lang-btn{{background:rgba(109,40,217,.12);color:#B38BFF;border:1px solid rgba(109,40,217,.25);border-radius:8px;padding:4px 12px;font-size:.8rem;cursor:pointer;font-family:inherit;white-space:nowrap}}.pr-lang-btn:hover{{background:rgba(109,40,217,.2)}}.pr-lang-menu{{display:none;position:absolute;top:100%;left:0;margin-top:4px;background:#1a1a2e;border:1px solid rgba(255,255,255,.1);border-radius:8px;min-width:140px;z-index:100;box-shadow:0 8px 24px rgba(0,0,0,.3);overflow:hidden}}.pr-lang-menu.open{{display:block}}.pr-lang-option{{display:block;width:100%;padding:8px 14px;font-size:.85rem;color:#ccc;background:none;border:none;text-align:left;cursor:pointer;font-family:inherit}}.pr-lang-option:hover{{background:rgba(109,40,217,.15);color:#fff}}.pr-lang-option.active{{color:#B38BFF;font-weight:600}}@media(max-width:767px){{.pr-blog-article{{margin:40px auto 60px;padding:0 20px}}.pr-blog-body{{font-size:1rem}}}}';
  document.head.appendChild(css);

  var pathParts = window.location.pathname.split('/');
  var itemSlug = pathParts[pathParts.length - 1];
  if (!itemSlug) return;

  // Get saved locale or detect from browser
  var currentLocale = localStorage.getItem('pr-locale') || 'en';

  function fetchArticle(locale) {{
    var localeParam = locale && locale !== 'en' ? '?locale=' + locale : '';
    return fetch(API_BASE + '/api/content/' + CUSTOMER_ID + '/by-slug/' + itemSlug + localeParam)
      .then(function(r) {{ return r.json(); }});
  }}

  function buildLangSwitcher(locales, active) {{
    if (!locales || locales.length <= 1) return '';
    var label = LOCALE_LABELS[active] || active;
    var html = '<div class="pr-lang-switcher">' +
      '<button class="pr-lang-btn" onclick="this.nextElementSibling.classList.toggle(\'open\')">' +
      '\\ud83c\\udf10 ' + label + '</button>' +
      '<div class="pr-lang-menu">';
    locales.forEach(function(loc) {{
      var cls = loc === active ? ' active' : '';
      var name = LOCALE_LABELS[loc] || loc;
      html += '<button class="pr-lang-option' + cls + '" data-locale="' + loc + '">' + name + '</button>';
    }});
    html += '</div></div>';
    return html;
  }}

  function wireUpLangSwitcher() {{
    document.querySelectorAll('.pr-lang-option').forEach(function(btn) {{
      btn.addEventListener('click', function() {{
        var loc = btn.getAttribute('data-locale');
        currentLocale = loc;
        localStorage.setItem('pr-locale', loc);
        // Re-fetch article in new locale and update content in-place
        fetchArticle(loc).then(function(data) {{
          if (data && !data.error) {{
            var titleEl = document.querySelector('.pr-blog-title');
            var bodyEl = document.querySelector('.pr-blog-body');
            if (titleEl) titleEl.innerHTML = data.title || '';
            if (bodyEl) bodyEl.innerHTML = data.html_snippet || '';
            document.title = (data.title || 'Blog') + ' \\u2014 SmileShape';
            // Update switcher active state
            document.querySelectorAll('.pr-lang-option').forEach(function(o) {{
              o.classList.toggle('active', o.getAttribute('data-locale') === loc);
            }});
            var langBtn = document.querySelector('.pr-lang-btn');
            if (langBtn) langBtn.innerHTML = '\\ud83c\\udf10 ' + (LOCALE_LABELS[loc] || loc);
          }}
          // Close menu
          document.querySelectorAll('.pr-lang-menu').forEach(function(m) {{ m.classList.remove('open'); }});
        }});
      }});
    }});
    // Close menu on outside click
    document.addEventListener('click', function(e) {{
      if (!e.target.closest('.pr-lang-switcher')) {{
        document.querySelectorAll('.pr-lang-menu').forEach(function(m) {{ m.classList.remove('open'); }});
      }}
    }});
  }}

  function render() {{
    document.body.innerHTML = '<div class="pr-blog-loading">Loading...</div>';

    var localeParam = currentLocale && currentLocale !== 'en' ? '?locale=' + currentLocale : '';

    // Fetch the About Us page (simpler than homepage — has nav + footer, no hero animations)
    Promise.all([
      fetch('/about-us').then(function(r) {{ return r.text(); }}),
      fetch(API_BASE + '/api/content/' + CUSTOMER_ID + '/by-slug/' + itemSlug + localeParam).then(function(r) {{ return r.json(); }})
    ]).then(function(results) {{
      var siteHtml = results[0];
      var data = results[1];

      // Parse the site page to steal its full body
      var parser = new DOMParser();
      var doc = parser.parseFromString(siteHtml, 'text/html');

      // Copy all head stylesheets we might be missing
      var links = doc.querySelectorAll('link[rel="stylesheet"]');
      links.forEach(function(link) {{
        if (!document.querySelector('link[href="' + link.href + '"]')) {{
          document.head.appendChild(link.cloneNode());
        }}
      }});

      // Get everything from the site page body
      var siteBody = doc.body;

      // Strategy: keep first section (has nav), remove middle sections, keep footer
      var keepElements = [];
      var foundFirst = false;
      var children = Array.from(siteBody.children);

      for (var i = 0; i < children.length; i++) {{
        var el = children[i];
        if (!foundFirst && el.tagName === 'SECTION') {{
          var containers = el.querySelectorAll('.w-container');
          var navContainer = containers[0];
          if (navContainer) {{
            el.innerHTML = '';
            el.appendChild(navContainer);
            el.style.paddingBottom = '0';
            el.style.minHeight = 'auto';
          }}
          keepElements.push(el.outerHTML);
          foundFirst = true;
          continue;
        }}
        if (el.classList && (el.classList.contains('footer') || el.classList.contains('backtotop'))) {{
          keepElements.push(el.outerHTML);
          continue;
        }}
        if (el.classList && el.classList.contains('fs_modal-2_wrapper')) {{
          keepElements.push(el.outerHTML);
          continue;
        }}
        if (keepElements.length > 1) {{
          keepElements.push(el.outerHTML);
        }}
      }}

      // Build blog article HTML
      var articleHtml = '';
      if (!data || data.error) {{
        articleHtml = '<div class="pr-blog-loading">Article not found.</div>';
      }} else {{
        var activeLocale = data.locale || currentLocale || 'en';
        var langSwitcherHtml = buildLangSwitcher(data.available_locales, activeLocale);

        var metaParts = [];
        if (data.author) metaParts.push('<span>' + data.author + '</span>');
        if (data.published_on) {{
          var d = new Date(data.published_on);
          metaParts.push('<span>' + d.toLocaleDateString('en-US', {{year:'numeric',month:'long',day:'numeric'}}) + '</span>');
        }}
        if (langSwitcherHtml) metaParts.push(langSwitcherHtml);

        articleHtml =
          '<article class="pr-blog-article">' +
            '<div class="pr-blog-header">' +
              (data.category ? '<span class="pr-blog-category">' + data.category + '</span>' : '') +
              '<h1 class="pr-blog-title">' + (data.title || '') + '</h1>' +
              '<div class="pr-blog-meta">' + metaParts.join('<span>\\u00b7</span>') + '</div>' +
            '</div>' +
            '<div class="pr-blog-body">' + (data.html_snippet || '') + '</div>' +
          '</article>';
        document.title = (data.title || 'Blog') + ' \\u2014 SmileShape';
      }}

      // Assemble: nav + blog + footer
      var navHtml = keepElements.length > 0 ? keepElements[0] : '';
      var footerHtml = keepElements.slice(1).join('');
      document.body.innerHTML = navHtml + articleHtml + footerHtml;

      // Wire up language switcher
      wireUpLangSwitcher();

      // Re-wire mobile nav toggle
      var menuBtn = document.querySelector('.menu-lines.open');
      var mobileNavEl = document.querySelector('.mobile-nav');
      if (menuBtn && mobileNavEl) {{
        menuBtn.addEventListener('click', function() {{
          mobileNavEl.style.display = mobileNavEl.style.display === 'flex' ? 'none' : 'flex';
        }});
        document.querySelectorAll('.closes').forEach(function(btn) {{
          btn.addEventListener('click', function() {{
            mobileNavEl.style.display = 'none';
          }});
        }});
      }}

    }}).catch(function(err) {{
      document.body.innerHTML = '<div class="pr-blog-loading">Failed to load article.</div>';
      console.error('PracticeRank blog error:', err);
    }});
  }}

  if (document.readyState === 'loading') {{
    document.addEventListener('DOMContentLoaded', render);
  }} else {{
    render();
  }}
}})();
"""

FAQ_TEMPLATE_SCRIPT = """
<style>
  .pr-faq-page {
    max-width: 780px;
    margin: 80px auto 100px;
    padding: 0 32px;
    font-family: 'Host Grotesk', 'Geist', -apple-system, sans-serif;
  }
  .pr-faq-title {
    font-family: 'Geist', sans-serif;
    font-size: clamp(1.75rem, 4vw, 2.5rem);
    font-weight: 600;
    margin-bottom: 12px;
  }
  .pr-faq-category {
    display: inline-block;
    padding: 4px 14px;
    border-radius: 100px;
    background: rgba(109, 40, 217, 0.15);
    color: #B38BFF;
    font-size: 0.8rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 32px;
  }
  .pr-faq-body {
    font-size: 1.1rem;
    line-height: 1.8;
  }
  .pr-faq-body p { margin: 1rem 0; }
  .pr-faq-body a { color: #B38BFF; }
  @media (max-width: 767px) {
    .pr-faq-page { margin: 40px auto 60px; padding: 0 20px; }
  }
</style>
<script>
document.addEventListener('DOMContentLoaded', function() {
  var body = document.querySelector('.w-richtext');
  if (!body) return;
  var name = document.querySelector('[data-wf-bindings*="name"]');
  var cat = document.querySelector('[data-wf-bindings*="page-category"]');
  var section = body.closest('section') || body.parentElement;
  var page = document.createElement('div');
  page.className = 'pr-faq-page';
  var titleText = name ? name.textContent : document.title;
  var catText = cat ? cat.textContent : '';
  page.innerHTML =
    (catText ? '<span class="pr-faq-category">' + catText + '</span>' : '') +
    '<h1 class="pr-faq-title">' + titleText + '</h1>' +
    '<div class="pr-faq-body">' + body.innerHTML + '</div>';
  section.innerHTML = '';
  section.appendChild(page);
});
</script>
"""


def slugify(text: str) -> str:
    """Convert a title to a URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")[:80]


class WebflowContentPublisher:
    """Publish content recommendations to Webflow CMS."""

    def __init__(self, publisher: WebflowPublisher, db: CustomerDB, customer_id: str):
        self.publisher = publisher
        self.db = db
        self.customer_id = customer_id

    def ensure_collection(self, collection_type: str) -> str | None:
        """Ensure the CMS collection exists, return its ID.

        Checks DB cache first, then Webflow API, creates if missing.
        """
        # Check DB cache
        cached = self.db.get_webflow_collection(self.customer_id, collection_type)
        if cached:
            return cached["webflow_collection_id"]

        schema = COLLECTION_SCHEMAS.get(collection_type)
        if not schema:
            logger.error(f"Unknown collection type: {collection_type}")
            return None

        # Check if collection exists on Webflow
        existing = self.publisher.find_collection(schema["display_name"])
        if existing:
            col_id = existing["id"]
            # Ensure custom fields exist on the collection
            self._ensure_fields(col_id, schema)
            self.db.save_webflow_collection(
                self.customer_id, collection_type, col_id, schema["display_name"]
            )
            return col_id

        # Create collection
        created = self.publisher.create_collection(schema["display_name"], schema["slug"])
        if not created:
            return None

        col_id = created["id"]

        # Create custom fields on the new collection
        for field_def in schema.get("fields", []):
            self.publisher.create_collection_field(col_id, field_def)
            time.sleep(0.5)  # Rate limit

        self.db.save_webflow_collection(
            self.customer_id, collection_type, col_id, schema["display_name"]
        )
        return col_id

    def _ensure_fields(self, collection_id: str, schema: dict):
        """Create any missing custom fields on an existing collection."""
        col_detail = self.publisher.get_collection(collection_id)
        if not col_detail:
            return
        existing_slugs = {f["slug"] for f in col_detail.get("fields", [])}
        for field_def in schema.get("fields", []):
            if field_def["slug"] not in existing_slugs:
                logger.info(f"Creating missing field '{field_def['displayName']}' on collection {collection_id}")
                self.publisher.create_collection_field(collection_id, field_def)
                time.sleep(0.5)

    def map_recommendation_to_fields(self, rec: dict) -> tuple[str | None, dict]:
        """Map a recommendation to (collection_type, webflow_field_data).

        Returns (None, {}) for unsupported types.
        """
        rec_type = rec.get("rec_type", "")
        collection_type = REC_TYPE_TO_COLLECTION.get(rec_type)

        if not collection_type:
            return None, {}

        if collection_type == "blog_posts":
            return collection_type, {
                "name": rec["title"],
                "slug": slugify(rec["title"]),
                "post-body": rec.get("html_snippet", ""),
                "author": "PracticeRank",
                "category": rec.get("category", "general"),
                "published-on": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "meta-description": rec.get("description", "")[:160],
            }
        elif collection_type == "faqs":
            return collection_type, {
                "name": rec["title"],
                "slug": slugify(rec["title"]),
                "answer": rec.get("html_snippet", ""),
                "page-category": rec.get("category", "general"),
                "sort-order": rec.get("priority", 3),
            }

        return None, {}

    def publish_recommendation(self, rec_id: str) -> dict:
        """Publish a single recommendation to Webflow CMS.

        Returns dict with keys: ok, error, webflow_item_id
        """
        rec = self.db.get_content_recommendation(rec_id)
        if not rec:
            return {"ok": False, "error": "Recommendation not found"}

        if rec["status"] not in ("approved", "published"):
            return {"ok": False, "error": f"Cannot publish rec with status '{rec['status']}'. Must be approved first."}

        if rec["rec_type"] not in CMS_PUBLISHABLE_TYPES:
            return {"ok": False, "error": f"Type '{rec['rec_type']}' is not CMS-publishable. Use manual publish."}

        collection_type, fields = self.map_recommendation_to_fields(rec)
        if not collection_type:
            return {"ok": False, "error": "Failed to map recommendation to CMS fields"}

        # Ensure collection exists
        collection_id = self.ensure_collection(collection_type)
        if not collection_id:
            error = "Failed to find or create Webflow collection"
            self.db.set_recommendation_publish_error(rec_id, error)
            return {"ok": False, "error": error}

        try:
            # Update existing item or create new
            if rec.get("webflow_item_id"):
                success = self.publisher.update_collection_item(
                    collection_id, rec["webflow_item_id"], fields, publish=True
                )
                if not success:
                    error = "Failed to update existing Webflow item"
                    self.db.set_recommendation_publish_error(rec_id, error)
                    return {"ok": False, "error": error}
                item_id = rec["webflow_item_id"]
            else:
                item = self.publisher.create_collection_item(
                    collection_id, fields, publish=True
                )
                if not item:
                    error = "Failed to create Webflow CMS item"
                    self.db.set_recommendation_publish_error(rec_id, error)
                    return {"ok": False, "error": error}
                item_id = item.get("id", item.get("_id", ""))

            # Update DB with success
            self.db.update_recommendation_webflow_ids(rec_id, item_id, collection_id)
            return {"ok": True, "webflow_item_id": item_id}

        except Exception as e:
            error = str(e)
            self.db.set_recommendation_publish_error(rec_id, error)
            return {"ok": False, "error": error}

    def setup_cms_template(self, collection_type: str) -> bool:
        """Auto-setup a CMS template page via Custom Code injection.

        Injects CSS + JS that renders CMS fields in a styled blog/FAQ layout,
        matching a clean modern design. Works on the CMS template page so every
        item in the collection gets the same layout automatically.
        """
        schema = COLLECTION_SCHEMAS.get(collection_type)
        if not schema:
            return False

        collection_id = self.ensure_collection(collection_type)
        if not collection_id:
            return False

        # Find the CMS template page
        template_page = self.publisher.find_cms_template_page(collection_id)
        if not template_page:
            logger.error(f"No CMS template page found for collection {collection_id}")
            return False

        page_id = template_page["id"]

        if collection_type == "blog_posts":
            source_code = BLOG_TEMPLATE_SCRIPT.format(
                customer_id=self.customer_id,
            )
            display_name = "PracticeRank Blog Template"
        elif collection_type == "faqs":
            source_code = FAQ_TEMPLATE_SCRIPT.format(
                customer_id=self.customer_id,
            )
            display_name = "PracticeRank FAQ Template"
        else:
            return False

        # Find current version of this script and bump it
        current_version = None
        try:
            resp = self.publisher.client.get(f"/sites/{self.publisher.site_id}/registered_scripts")
            if resp.status_code == 200:
                for s in resp.json().get("registeredScripts", []):
                    if s.get("displayName") == display_name:
                        current_version = s.get("version")
        except Exception:
            pass
        version = self.publisher._bump_version(current_version)
        logger.info(f"Registering {display_name} v{version} (previous: {current_version})")

        # Register the script (returns the actual Webflow-assigned ID)
        registered_id = self.publisher.register_inline_script(display_name, source_code, version)
        if not registered_id:
            return False

        # Apply to the CMS template page header
        if not self.publisher.apply_custom_code_to_page(page_id, registered_id, version, location="header"):
            return False

        logger.info(f"Auto-setup CMS template for {collection_type} on page {page_id}")
        return True

    def publish_batch(self, rec_ids: list[str]) -> list[dict]:
        """Publish multiple recommendations, then publish the site once.

        Auto-sets up CMS template pages on first publish for each collection type.
        Returns list of result dicts (one per rec_id).
        """
        results = []
        any_success = False
        templates_setup = set()  # Track which collection types we've set up templates for

        for rec_id in rec_ids:
            result = self.publish_recommendation(rec_id)
            result["rec_id"] = rec_id
            results.append(result)
            if result["ok"]:
                any_success = True
                # Auto-setup template for this collection type (once per type per batch)
                rec = self.db.get_content_recommendation(rec_id)
                if rec:
                    col_type = REC_TYPE_TO_COLLECTION.get(rec["rec_type"])
                    if col_type and col_type not in templates_setup:
                        self.setup_cms_template(col_type)
                        templates_setup.add(col_type)
            # Rate limit: 1s between API calls
            time.sleep(1)

        # Publish site once if any items were pushed
        if any_success:
            published = self.publisher.publish_site()
            if not published:
                for r in results:
                    if r["ok"]:
                        r["warning"] = "Item created but site publish failed"

        return results
