"""Tests for the FATJOE CSV report importer."""

from __future__ import annotations

import pytest

from geo_agent.db import CustomerDB
from geo_agent.fatjoe_import import domain_of, import_report, parse_report


def test_domain_of():
    assert domain_of("https://www.Example.com/path?x=1") == "example.com"
    assert domain_of("http://blog.site.org") == "blog.site.org"
    assert domain_of("Example.COM") == "example.com"


def test_parse_links_report_fuzzy_headers():
    csv = ("Live URL,Anchor Text,DR,Dofollow\n"
           "https://www.healthblog.com/p,dental implants,32,Yes\n"
           "https://care.example.org/x,read more,18,No\n"
           ",blank-row,5,Yes\n")
    rows = parse_report(csv, "link")
    assert len(rows) == 2
    assert rows[0]["domain"] == "healthblog.com"
    assert rows[0]["_da"] == 32
    assert rows[0]["is_dofollow"] == 1
    assert rows[1]["is_dofollow"] == 0


def test_parse_citation_report_derives_domain_from_url():
    csv = "Directory,Directory URL\nYelp,https://yelp.com/biz/x\nFoursquare,https://foursquare.com/v/y\n"
    rows = parse_report(csv, "citation")
    # The "Directory" name column must NOT become the domain.
    assert {r["domain"] for r in rows} == {"yelp.com", "foursquare.com"}


@pytest.fixture
def db(tmp_path):
    database = CustomerDB(db_path=str(tmp_path / "t.db"))
    database.add_customer(id="c1", name="C", domain="c.com")
    yield database
    database.close()


def test_import_report_dedupes_and_advances_status(db):
    oid = db.add_offsite_order("c1", "link", cost_usd=120.0)
    csv = ("Live URL,Anchor Text,DR\n"
           "https://a.com/1,x,30\n"
           "https://a.com/1,x,30\n"   # dup within file
           "https://b.com/2,y,25\n")
    res = import_report(db, oid, csv.encode())
    assert res["added"] == 2
    assert res["skipped_dupes"] == 1
    assert db.get_offsite_order(oid)["status"] == "delivered"
    # DA came straight from the CSV (no Moz needed)
    assets = {a["domain"]: a for a in db.get_offsite_assets("c1")}
    assert assets["a.com"]["da"] == 30

    # Re-importing the same file adds nothing (cross-run dedupe).
    res2 = import_report(db, oid, csv.encode())
    assert res2["added"] == 0
