"""Tests for content-pipeline guardrails: stat-library integrity, batch stat-dedup, and the
DOCX deliverable (real meta_description rendering + the Needs-Review block).
"""

from __future__ import annotations

import re

from docx import Document

from geo_agent import content_recommender as cr
from geo_agent.docx_generator import ContentDocxGenerator


def _docx_text(buf) -> str:
    return "\n".join(p.text for p in Document(buf).paragraphs)


class TestStatLibraryIntegrity:
    def test_no_named_publication_in_text_conflicts_with_source(self):
        """A stat must not name a Survey/Journal/Report/Study/Review in its text that is absent
        from its `source` field — that's the exact contradiction that produced the double-sourced
        42% dental-anxiety stat ("2021 Adult Oral Health Survey" text vs "British Dental Journal"
        source).
        """
        named = re.compile(
            r"\b([A-Z][a-z]+(?:\s+(?:of\s+)?[A-Z][a-z]+){0,4}\s+"
            r"(?:Survey|Journal|Report|Study|Review))\b"
        )
        offenders = []
        for bt, stats in cr.RESEARCH_STATS.items():
            for s in stats:
                src = s["source"].lower()
                for m in named.finditer(s["stat"]):
                    phrase = m.group(1)
                    # ignore generic phrases like "systematic review" / "meta-analysis"
                    if phrase.lower().startswith(("systematic", "meta")):
                        continue
                    head = phrase.split()[0].lower()
                    if head not in src and phrase.lower() not in src:
                        offenders.append((bt, phrase, s["source"]))
        assert not offenders, f"stat text names a source absent from `source`: {offenders}"

    def test_every_stat_has_source_and_url(self):
        for bt, stats in cr.RESEARCH_STATS.items():
            for s in stats:
                assert s.get("stat") and s.get("source"), f"{bt}: incomplete stat row {s}"
                assert s["url"].startswith("http"), f"{bt}: bad url {s['url']}"

    def test_anxiety_stat_is_internally_consistent(self):
        row = next(s for s in cr.RESEARCH_STATS["practice"] if "dental fear" in s["stat"])
        assert "Journal of Dentistry" in row["source"]
        # No longer claims a separate "Adult Oral Health Survey".
        assert "Adult Oral Health Survey" not in row["stat"]


class TestBatchStatDedup:
    def test_overused_stat_downgraded(self):
        url = cr.RESEARCH_STATS["practice"][1]["url"]  # the implant survival stat
        recs = [
            cr.ContentRecommendation(
                id=f"r{i}", customer_id="c", rec_type="blog_post", target_page="/blog/",
                title=f"Post {i}", description="", html_snippet=f'<p><a href="{url}">src</a></p>',
                priority=1, category="implants",
            )
            for i in range(6)
        ]
        cr._flag_overused_stats(recs, "practice")
        downgraded = [r for r in recs if r.priority > 1]
        # 6 uses, cap 3 → the excess (uses 4,5,6) get downgraded.
        assert len(downgraded) == 6 - cr.STAT_REUSE_CAP

    def test_under_cap_not_downgraded(self):
        url = cr.RESEARCH_STATS["practice"][1]["url"]
        recs = [
            cr.ContentRecommendation(
                id=f"r{i}", customer_id="c", rec_type="blog_post", target_page="/blog/",
                title=f"Post {i}", description="", html_snippet=f'<p><a href="{url}">src</a></p>',
                priority=2, category="implants",
            )
            for i in range(cr.STAT_REUSE_CAP)
        ]
        cr._flag_overused_stats(recs, "practice")
        assert all(r.priority == 2 for r in recs)


class TestDocxDeliverable:
    BASE = {
        "id": "r1", "rec_type": "blog_post", "title": "Implants in Westfield",
        "description": "INTERNAL BRIEF: Cover consultation, position Dr. Zhivago.",
        "meta_description": "Dental implants in Westfield, NJ — book your consult with Downtown Dental.",
        "html_snippet": "<p>Body copy here.</p>",
    }

    def test_renders_meta_description_not_internal_brief(self):
        buf = ContentDocxGenerator({"name": "Downtown Dental"}).generate_single(self.BASE)
        text = _docx_text(buf)
        assert "Dental implants in Westfield" in text
        assert "INTERNAL BRIEF" not in text  # the brief must never ship as the meta tag

    def test_omits_meta_line_when_no_meta_description(self):
        rec = {**self.BASE, "meta_description": ""}
        text = _docx_text(ContentDocxGenerator({"name": "X"}).generate_single(rec))
        assert "Meta Description:" not in text  # no fallback to the internal brief

    def test_needs_review_block_rendered_when_findings(self):
        vals = {"r1": [
            {"severity": "block", "category": "credential", "message": "unverified board cert"},
            {"severity": "warn", "category": "superlative", "message": "'best'"},
        ]}
        text = _docx_text(ContentDocxGenerator({"name": "X"}).generate_batch([self.BASE], vals))
        assert "NEEDS REVIEW BEFORE PUBLISHING" in text
        assert "unverified board cert" in text

    def test_no_review_block_when_clean(self):
        text = _docx_text(ContentDocxGenerator({"name": "X"}).generate_batch([self.BASE], {}))
        assert "NEEDS REVIEW" not in text
