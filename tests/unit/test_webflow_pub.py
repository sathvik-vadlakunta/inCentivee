"""Tests for publishers/webflow.py — inject_schema, publish (respx)."""

from __future__ import annotations

import httpx
import respx

from geo_agent.publishers.webflow import WebflowPublisher


class TestInjectSchema:
    @respx.mock
    def test_inject_new_schema(self):
        site_id = "site_test"
        schema_html = '<script type="application/ld+json">{"@type":"Dentist"}</script>'

        # Mock GET existing custom code (empty)
        respx.get(f"https://api.webflow.com/v2/sites/{site_id}/custom_code").mock(
            return_value=httpx.Response(200, json={"headCode": ""})
        )

        # Mock PUT update
        put_route = respx.put(f"https://api.webflow.com/v2/sites/{site_id}/custom_code").mock(
            return_value=httpx.Response(200, json={"headCode": "updated"})
        )

        pub = WebflowPublisher(api_key="key", site_id=site_id)
        result = pub.inject_schema_to_site(schema_html)
        pub.close()

        assert result is True
        body = put_route.calls[0].request.content.decode()
        assert "DentalRank Schema Start" in body
        assert "DentalRank Schema End" in body
        assert "Dentist" in body

    @respx.mock
    def test_replaces_existing_schema(self):
        site_id = "site_test"
        existing = (
            '<meta name="test">\n'
            "<!-- DentalRank Schema Start -->\n"
            "<script>OLD</script>\n"
            "<!-- DentalRank Schema End -->\n"
            '<meta name="other">'
        )

        respx.get(f"https://api.webflow.com/v2/sites/{site_id}/custom_code").mock(
            return_value=httpx.Response(200, json={"headCode": existing})
        )

        put_route = respx.put(f"https://api.webflow.com/v2/sites/{site_id}/custom_code").mock(
            return_value=httpx.Response(200, json={})
        )

        pub = WebflowPublisher(api_key="key", site_id=site_id)
        result = pub.inject_schema_to_site("<script>NEW</script>")
        pub.close()

        assert result is True
        body = put_route.calls[0].request.content.decode()
        assert "OLD" not in body
        assert "NEW" in body
        assert "test" in body  # preserved non-DentalRank code

    @respx.mock
    def test_handles_404_custom_code(self):
        site_id = "site_test"
        respx.get(f"https://api.webflow.com/v2/sites/{site_id}/custom_code").mock(
            return_value=httpx.Response(404)
        )
        respx.put(f"https://api.webflow.com/v2/sites/{site_id}/custom_code").mock(
            return_value=httpx.Response(200, json={})
        )

        pub = WebflowPublisher(api_key="key", site_id=site_id)
        result = pub.inject_schema_to_site("<script>SCHEMA</script>")
        pub.close()

        assert result is True

    @respx.mock
    def test_returns_false_on_put_error(self):
        site_id = "site_test"
        respx.get(f"https://api.webflow.com/v2/sites/{site_id}/custom_code").mock(
            return_value=httpx.Response(200, json={"headCode": ""})
        )
        respx.put(f"https://api.webflow.com/v2/sites/{site_id}/custom_code").mock(
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
        respx.post(f"https://api.webflow.com/v2/sites/{site_id}/publish").mock(
            return_value=httpx.Response(200, json={"queued": True})
        )

        pub = WebflowPublisher(api_key="key", site_id=site_id)
        assert pub.publish_site() is True
        pub.close()

    @respx.mock
    def test_publish_failure(self):
        site_id = "site_test"
        respx.post(f"https://api.webflow.com/v2/sites/{site_id}/publish").mock(
            return_value=httpx.Response(500)
        )

        pub = WebflowPublisher(api_key="key", site_id=site_id)
        assert pub.publish_site() is False
        pub.close()
