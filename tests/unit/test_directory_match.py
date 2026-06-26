"""P2 #2: directory-listing scanner must match per-result (name + the directory's own
domain in the SAME DuckDuckGo result), not page-wide substring — otherwise a competitor
result writes a false-positive checklist checkmark.
"""

from __future__ import annotations

from dashboard.app import _directory_listing_found


def _result(href, title):
    # minimal DuckDuckGo html result anchor shape
    return f'<a rel="nofollow" class="result__a" href="{href}">{title}</a>'


def _ddg(*results):
    return "<div>" + "".join(results) + "</div>"


def test_real_listing_matches():
    html = _ddg(_result(
        "//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.yelp.com%2Fbiz%2Fsmith-dental-reno",
        "Smith Dental - Reno, NV - Yelp",
    ))
    found, url = _directory_listing_found(html, "Smith Dental", "yelp.com")
    assert found is True
    assert "yelp.com/biz/smith-dental" in url


def test_competitor_result_is_not_a_false_positive():
    # A different business on yelp.com — name tokens don't match → must NOT count.
    html = _ddg(_result(
        "//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.yelp.com%2Fbiz%2Fjones-orthodontics",
        "Jones Orthodontics - Yelp",
    ))
    found, url = _directory_listing_found(html, "Smith Dental", "yelp.com")
    assert found is False
    assert url == ""


def test_name_present_but_not_on_directory_domain_is_not_found():
    # Practice name appears, but the result links to the practice's own site, not yelp.
    html = _ddg(_result(
        "//duckduckgo.com/l/?uddg=https%3A%2F%2Fsmithdental.com%2Fabout",
        "About Smith Dental — yelp reviews mentioned",
    ))
    found, _url = _directory_listing_found(html, "Smith Dental", "yelp.com")
    assert found is False


def test_allows_one_missing_token():
    # "Smith Family Dental" listed as "Smith Dental" on the directory — 2/3 tokens is enough.
    html = _ddg(_result(
        "//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.healthgrades.com%2Fsmith-dental",
        "Smith Dental | Healthgrades",
    ))
    found, _url = _directory_listing_found(html, "Smith Family Dental", "healthgrades.com")
    assert found is True


def test_empty_html_no_match():
    assert _directory_listing_found("", "Smith Dental", "yelp.com") == (False, "")
