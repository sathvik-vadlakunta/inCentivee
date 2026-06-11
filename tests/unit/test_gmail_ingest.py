"""Email-routing logic for Gmail ingestion (no live IMAP)."""

from __future__ import annotations

import email

import pytest

from geo_agent.db import CustomerDB
from geo_agent.gmail_ingest import _route, _plain_body, _self_address


@pytest.fixture
def db(tmp_path):
    d = CustomerDB(db_path=str(tmp_path / "g.db"))
    d.add_customer(id="hilltop", name="Hilltop Dental", domain="hilltopdental.com", city="Reno", state="NV")
    d.add_customer(id="sojo", name="SoJo Dental", domain="www.sojodental.com", city="Austin", state="TX")
    d.add_contact("hilltop", "Dr. Gallup", email="gallupster@gmail.com", role="owner")
    d.add_contact("sojo", "Office", email="front@sojodental.com", role="office_manager")
    yield d
    d.close()


def test_index_emails_and_domains(db):
    idx = db.get_email_customer_index()
    # exact contact emails (incl. personal gmail)
    assert idx["emails"]["gallupster@gmail.com"] == "hilltop"
    # business domain, www-stripped
    assert idx["domains"]["sojodental.com"] == "sojo"
    # generic host (gmail.com) must NOT become a routing domain
    assert "gmail.com" not in idx["domains"]


def test_route_prefers_exact_email(db):
    idx = db.get_email_customer_index()
    assert _route(["gallupster@gmail.com"], idx) == "hilltop"


def test_route_by_business_domain(db):
    idx = db.get_email_customer_index()
    assert _route(["someoneelse@sojodental.com"], idx) == "sojo"


def test_route_no_match(db):
    idx = db.get_email_customer_index()
    assert _route(["random@stranger.com"], idx) is None


def test_self_address():
    assert _self_address("kdoherty@practicerank.ai") is True
    assert _self_address("jon@lostrelic.com") is True
    assert _self_address("client@gmail.com") is False


def test_plain_body_strips_html_and_quotes():
    msg = email.message_from_string(
        "Content-Type: text/html\n\n<p>Hi <b>there</b></p>\nOn Mon wrote:\nold quoted text"
    )
    body = _plain_body(msg)
    assert "Hi" in body and "there" in body
    assert "<b>" not in body
    assert "old quoted text" not in body  # quoted chain trimmed
