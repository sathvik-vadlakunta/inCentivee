"""Security tests for the /internal/fetch-relay endpoint (audit blocked-site
fallback). The relay is a server-side fetch proxy, so the SSRF guard + shared
secret are the safety-critical parts."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("RELAY_SECRET", "unit-test-secret")
import dashboard.app as A  # noqa: E402

SECRET = os.environ["RELAY_SECRET"]


@pytest.mark.parametrize("host", [
    "localhost", "127.0.0.1", "10.0.0.5", "192.168.1.1",
    "172.16.0.1", "169.254.169.254", "0.0.0.0", "::1",
])
def test_ssrf_guard_blocks_private(host):
    assert A._relay_host_is_public(host) is False


@pytest.mark.parametrize("host", ["1.1.1.1", "8.8.8.8"])
def test_ssrf_guard_allows_public(host):
    assert A._relay_host_is_public(host) is True


@pytest.fixture
def client():
    return A.app.test_client()


def test_requires_secret(client):
    assert client.get("/internal/fetch-relay?url=https://example.com").status_code == 403
    r = client.get("/internal/fetch-relay?url=https://example.com",
                   headers={"X-Relay-Secret": "wrong"})
    assert r.status_code == 403


def test_rejects_non_http_scheme(client):
    r = client.get("/internal/fetch-relay?url=ftp://example.com",
                   headers={"X-Relay-Secret": SECRET})
    assert r.status_code == 400


def test_rejects_private_and_metadata_targets(client):
    h = {"X-Relay-Secret": SECRET}
    assert client.get("/internal/fetch-relay?url=http://127.0.0.1/x", headers=h).status_code == 400
    assert client.get("/internal/fetch-relay?url=http://169.254.169.254/latest/meta-data",
                      headers=h).status_code == 400
    assert client.get("/internal/fetch-relay?url=http://10.0.0.1/", headers=h).status_code == 400
