"""Tests for publishers/cloudflare.py — KV namespace, upload, publish (respx)."""

from __future__ import annotations

import httpx
import respx

from geo_agent.publishers.cloudflare import CloudflarePublisher


ACCOUNT = "acct_test"
ZONE = "zone_test"
BASE = "https://api.cloudflare.com/client/v4"


class TestEnsureKvNamespace:
    @respx.mock
    def test_finds_existing(self):
        respx.get(f"{BASE}/accounts/{ACCOUNT}/storage/kv/namespaces").mock(
            return_value=httpx.Response(200, json={
                "result": [{"id": "ns-123", "title": "GEO_FILES"}]
            })
        )

        pub = CloudflarePublisher(api_token="tok", account_id=ACCOUNT, zone_id=ZONE)
        ns_id = pub.ensure_kv_namespace()
        pub.close()

        assert ns_id == "ns-123"

    @respx.mock
    def test_creates_new(self):
        respx.get(f"{BASE}/accounts/{ACCOUNT}/storage/kv/namespaces").mock(
            return_value=httpx.Response(200, json={"result": []})
        )
        respx.post(f"{BASE}/accounts/{ACCOUNT}/storage/kv/namespaces").mock(
            return_value=httpx.Response(200, json={"result": {"id": "ns-new"}})
        )

        pub = CloudflarePublisher(api_token="tok", account_id=ACCOUNT, zone_id=ZONE)
        ns_id = pub.ensure_kv_namespace()
        pub.close()

        assert ns_id == "ns-new"


class TestUploadFile:
    @respx.mock
    def test_upload_success(self):
        ns_id = "ns-123"
        respx.get(f"{BASE}/accounts/{ACCOUNT}/storage/kv/namespaces").mock(
            return_value=httpx.Response(200, json={
                "result": [{"id": ns_id, "title": "GEO_FILES"}]
            })
        )
        put_route = respx.put(
            f"{BASE}/accounts/{ACCOUNT}/storage/kv/namespaces/{ns_id}/values/llms.txt"
        ).mock(return_value=httpx.Response(200, json={"success": True}))

        pub = CloudflarePublisher(api_token="tok", account_id=ACCOUNT, zone_id=ZONE)
        result = pub.upload_file("llms.txt", "# Test content")
        pub.close()

        assert result is True
        assert put_route.called

    @respx.mock
    def test_upload_failure(self):
        ns_id = "ns-123"
        respx.get(f"{BASE}/accounts/{ACCOUNT}/storage/kv/namespaces").mock(
            return_value=httpx.Response(200, json={
                "result": [{"id": ns_id, "title": "GEO_FILES"}]
            })
        )
        respx.put(
            f"{BASE}/accounts/{ACCOUNT}/storage/kv/namespaces/{ns_id}/values/test.txt"
        ).mock(return_value=httpx.Response(500))

        pub = CloudflarePublisher(api_token="tok", account_id=ACCOUNT, zone_id=ZONE)
        result = pub.upload_file("test.txt", "content")
        pub.close()

        assert result is False


class TestPublishFiles:
    @respx.mock
    def test_publishes_all_three(self):
        ns_id = "ns-123"
        respx.get(f"{BASE}/accounts/{ACCOUNT}/storage/kv/namespaces").mock(
            return_value=httpx.Response(200, json={
                "result": [{"id": ns_id, "title": "GEO_FILES"}]
            })
        )

        for fname in ["llms.txt", "llms-full.txt", "robots.txt"]:
            respx.put(
                f"{BASE}/accounts/{ACCOUNT}/storage/kv/namespaces/{ns_id}/values/{fname}"
            ).mock(return_value=httpx.Response(200, json={"success": True}))

        pub = CloudflarePublisher(api_token="tok", account_id=ACCOUNT, zone_id=ZONE)
        result = pub.publish_files("llms content", "full content", "robots content")
        pub.close()

        assert result is True
