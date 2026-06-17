"""Tests for site_auditor robots.txt analysis.

Regression guard: a `Disallow: /` scoped to a specific training bot (GPTBot,
ClaudeBot, Google-Extended) is our INTENTIONAL block and must NOT be flagged as
"blocks all crawlers" — otherwise every optimized customer trips a false critical
and can never auto-advance to active.
"""

from __future__ import annotations

import geo_agent.site_auditor as sa


class _FakeResp:
    def __init__(self, text, status=200):
        self.text = text
        self.status_code = status


class _FakeClient:
    def __init__(self, text):
        self._text = text

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get(self, url):
        return _FakeResp(self._text)


def _robots(text, monkeypatch):
    monkeypatch.setattr(sa.httpx, "Client", lambda *a, **k: _FakeClient(text))
    return sa._check_robots_txt("example.com")


# Our standard generated robots.txt: training bots blocked, retrieval bots + * allowed.
PRACTICERANK_ROBOTS = """\
User-agent: GPTBot
Disallow: /

User-agent: ClaudeBot
Disallow: /

User-agent: Google-Extended
Disallow: /

User-agent: ChatGPT-User
Allow: /

User-agent: PerplexityBot
Allow: /

User-agent: *
Allow: /

Sitemap: https://example.com/sitemap.xml
"""

DEV_MODE_ROBOTS = """\
User-agent: *
Disallow: /
"""


def test_training_bot_block_is_not_flagged(monkeypatch):
    issues = _robots(PRACTICERANK_ROBOTS, monkeypatch)
    assert not any(i["title"] == "robots.txt blocks all crawlers" for i in issues)


def test_wildcard_block_is_flagged_critical(monkeypatch):
    issues = _robots(DEV_MODE_ROBOTS, monkeypatch)
    blockers = [i for i in issues if i["title"] == "robots.txt blocks all crawlers"]
    assert blockers and blockers[0]["severity"] == "critical"


def test_grouped_agents_block_flagged(monkeypatch):
    # consecutive User-agent lines share the following rules
    grouped = "User-agent: SomeBot\nUser-agent: *\nDisallow: /\n"
    issues = _robots(grouped, monkeypatch)
    assert any(i["title"] == "robots.txt blocks all crawlers" for i in issues)
