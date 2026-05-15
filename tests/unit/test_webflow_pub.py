"""Tests for publishers/webflow.py — inject_schema, publish (respx).

The current Webflow publisher uses the Custom Code API v2 flow:
  inject_schema_to_site:
    1. GET /sites/{id}/registered_scripts  (get current version)
    2. DELETE /sites/{id}/custom_code      (clear existing)
    3. POST /sites/{id}/registered_scripts/inline  (register new JS)
    4. PUT /sites/{id}/custom_code         (apply script to site head)

  publish_site:
    1. GET /sites/{id}                     (get domain IDs)
    2. POST /sites/{id}/publish            (trigger publish)
"""

from __future__ import annotations

import httpx
import respx

from geo_agent.publishers.webflow import WebflowPublisher, SCRIPT_ID

BASE = "https://api.webflow.com/v2"


def _mock_inject_flow(site_id: str, *, existing_version: str | None = None):
    """Set up respx mocks for the full inject_schema_to_site flow."""
    # 1. GET registered_scripts
    scripts = []
    if existing_version:
        scripts = [{"id": SCRIPT_ID, "version": existing_version, "displayName": "PracticeRank Schema"}]
    respx.get(f"{BASE}/sites/{site_id}/registered_scripts").mock(
        return_value=httpx.Response(200, json={"registeredScripts": scripts})
    )
    # 2. DELETE custom_code (always succeeds)
    respx.delete(f"{BASE}/sites/{site_id}/custom_code").mock(
        return_value=httpx.Response(200, json={})
    )
    # 3. POST registered_scripts/inline
    respx.post(f"{BASE}/sites/{site_id}/registered_scripts/inline").mock(
        return_value=httpx.Response(200, json={"id": SCRIPT_ID})
    )
    # 4. PUT custom_code
    put_route = respx.put(f"{BASE}/sites/{site_id}/custom_code").mock(
        return_value=httpx.Response(200, json={})
    )
    return put_route


def _mock_publish_flow(site_id: str, *, domain_ids: list[str] | None = None):
    """Set up respx mocks for the full publish_site flow."""
    domains = [{"id": d} for d in (domain_ids or ["dom_1"])]
    respx.get(f"{BASE}/sites/{site_id}").mock(
        return_value=httpx.Response(200, json={"customDomains": domains})
    )
    post_route = respx.post(f"{BASE}/sites/{site_id}/publish").mock(
        return_value=httpx.Response(200, json={"queued": True})
    )
    return post_route


class TestInjectSchema:
    @respx.mock
    def test_inject_new_schema(self):
        site_id = "site_test"
        schema_html = '<script type="application/ld+json">{"@type":"Dentist"}</script>'

        put_route = _mock_inject_flow(site_id)

        pub = WebflowPublisher(api_key="key", site_id=site_id)
        result = pub.inject_schema_to_site(schema_html)
        pub.close()

        assert result is True
        body = put_route.calls[0].request.content.decode()
        assert SCRIPT_ID in body

    @respx.mock
    def test_bumps_version_when_existing(self):
        site_id = "site_test"
        schema_html = '<script type="application/ld+json">{"@type":"Dentist"}</script>'

        _mock_inject_flow(site_id, existing_version="1.0.2")

        pub = WebflowPublisher(api_key="key", site_id=site_id)
        result = pub.inject_schema_to_site(schema_html)
        pub.close()

        assert result is True
        # POST to registered_scripts/inline should have version 1.0.3
        post_call = respx.calls[-2]  # second-to-last call is POST inline
        body = post_call.request.content.decode()
        assert "1.0.3" in body

    @respx.mock
    def test_handles_missing_registered_scripts(self):
        """When no previous scripts exist, starts at version 1.0.0."""
        site_id = "site_test"

        _mock_inject_flow(site_id)

        pub = WebflowPublisher(api_key="key", site_id=site_id)
        result = pub.inject_schema_to_site("<script>SCHEMA</script>")
        pub.close()

        assert result is True

    @respx.mock
    def test_returns_false_on_put_error(self):
        site_id = "site_test"
        # Mock everything except PUT which returns 500
        respx.get(f"{BASE}/sites/{site_id}/registered_scripts").mock(
            return_value=httpx.Response(200, json={"registeredScripts": []})
        )
        respx.delete(f"{BASE}/sites/{site_id}/custom_code").mock(
            return_value=httpx.Response(200, json={})
        )
        respx.post(f"{BASE}/sites/{site_id}/registered_scripts/inline").mock(
            return_value=httpx.Response(200, json={"id": SCRIPT_ID})
        )
        respx.put(f"{BASE}/sites/{site_id}/custom_code").mock(
            return_value=httpx.Response(500)
        )

        pub = WebflowPublisher(api_key="key", site_id=site_id)
        result = pub.inject_schema_to_site("<script>X</script>")
        pub.close()

        assert result is False


class TestPublishSite:
    @respx.mock
    def test_publish_success(self):
        site_id = "site_test"
        _mock_publish_flow(site_id)

        pub = WebflowPublisher(api_key="key", site_id=site_id)
        assert pub.publish_site() is True
        pub.close()

    @respx.mock
    def test_publish_failure(self):
        site_id = "site_test"
        # GET site succeeds but POST publish fails
        respx.get(f"{BASE}/sites/{site_id}").mock(
            return_value=httpx.Response(200, json={"customDomains": []})
        )
        respx.post(f"{BASE}/sites/{site_id}/publish").mock(
            return_value=httpx.Response(500)
        )

        pub = WebflowPublisher(api_key="key", site_id=site_id)
        assert pub.publish_site() is False
        pub.close()
