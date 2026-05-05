#!/usr/bin/env python3
"""Translate published blog posts into all supported locales using Claude API.

Usage:
    python scripts/translate_blog_posts.py [--customer smileshape] [--locale es] [--force]

Flags:
    --customer  Customer ID (default: smileshape)
    --locale    Only translate to this locale (default: all)
    --force     Re-translate even if translation already exists
"""

import argparse
import os
import sys
import uuid
from datetime import datetime, timezone

import anthropic

# Add parent dir to path so we can import geo_agent
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from geo_agent.db import CustomerDB

SUPPORTED_LOCALES = ["es", "fr", "de", "pt", "sv", "ja", "ko", "zh", "ar"]

LOCALE_NAMES = {
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "pt": "Brazilian Portuguese",
    "sv": "Swedish",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Simplified Chinese",
    "ar": "Arabic",
}

DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"))


def get_db() -> CustomerDB:
    """Connect to the main practicerank DB."""
    db_path = os.path.join(DATA_DIR, "practicerank.db")
    if not os.path.exists(db_path):
        print(f"ERROR: Database not found at {db_path}")
        sys.exit(1)
    return CustomerDB(db_path)


def translate_post(client: anthropic.Anthropic, title: str, description: str, html_snippet: str, locale: str) -> dict:
    """Translate a blog post's title, description, and HTML content.

    Uses XML-style output to avoid JSON parsing issues with HTML content.
    """
    lang_name = LOCALE_NAMES[locale]

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8000,
        messages=[{
            "role": "user",
            "content": f"""Translate this blog post into {lang_name}. Return the translation using these XML tags:

<translated_title>translated title here</translated_title>
<translated_description>translated description here</translated_description>
<translated_html>translated HTML here</translated_html>

IMPORTANT:
- Keep product names untranslated: SmileShape, SmartScan, SmartCAD, SmartRX
- Keep technical terms as-is: CAD, CAD/CAM, AI, 3D
- Preserve ALL HTML structure, tags, classes, and attributes exactly
- Only translate the visible text content inside HTML elements
- Keep URLs unchanged

Title: {title}

Description: {description}

HTML:
{html_snippet}"""
        }],
    )

    import re
    text = response.content[0].text.strip()

    def extract_tag(tag_name: str) -> str:
        match = re.search(f'<{tag_name}>(.*?)</{tag_name}>', text, re.DOTALL)
        return match.group(1).strip() if match else ""

    translated_title = extract_tag("translated_title")
    translated_desc = extract_tag("translated_description")
    translated_html = extract_tag("translated_html")

    if not translated_title:
        raise ValueError(f"No translated_title found in response")

    return {
        "title": translated_title,
        "description": translated_desc,
        "html_snippet": translated_html,
    }


def main():
    parser = argparse.ArgumentParser(description="Translate blog posts into multiple locales")
    parser.add_argument("--customer", default="smileshape", help="Customer ID")
    parser.add_argument("--locale", default=None, help="Only translate to this locale")
    parser.add_argument("--force", action="store_true", help="Re-translate existing translations")
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable required")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    db = get_db()

    locales = [args.locale] if args.locale else SUPPORTED_LOCALES

    try:
        # Get all published posts
        recs = db.get_content_recommendations(args.customer, status="published")
        blog_posts = [r for r in recs if r["rec_type"] in ("blog_post", "new_page")]

        if not blog_posts:
            print(f"No published blog posts found for customer '{args.customer}'")
            return

        print(f"Found {len(blog_posts)} published posts. Translating to {len(locales)} locale(s)...")

        total = 0
        skipped = 0

        for post in blog_posts:
            for locale in locales:
                # Check if translation already exists
                existing = db.get_content_translation(post["id"], locale)
                if existing and not args.force:
                    skipped += 1
                    continue

                print(f"  Translating '{post['title'][:60]}...' -> {LOCALE_NAMES[locale]}...")

                try:
                    translated = translate_post(
                        client,
                        post["title"],
                        post.get("description", ""),
                        post.get("html_snippet", ""),
                        locale,
                    )

                    db.add_content_translation({
                        "id": existing["id"] if existing else str(uuid.uuid4()),
                        "recommendation_id": post["id"],
                        "locale": locale,
                        "title": translated["title"],
                        "description": translated.get("description", ""),
                        "html_snippet": translated.get("html_snippet", ""),
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    })
                    total += 1
                    print(f"    Done.")

                except Exception as e:
                    print(f"    ERROR: {e}")

        print(f"\nComplete. Translated {total} posts, skipped {skipped} existing.")

    finally:
        db.close()


if __name__ == "__main__":
    main()
