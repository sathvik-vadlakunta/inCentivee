"""Tests for the customer database."""

from __future__ import annotations

import json
import pytest
from pathlib import Path

from geo_agent.db import CustomerDB


@pytest.fixture
def db(tmp_path):
    """Create a fresh test database."""
    db_path = str(tmp_path / "test.db")
    database = CustomerDB(db_path=db_path)
    yield database
    database.close()


@pytest.fixture
def populated_db(db):
    """DB with a sample customer."""
    db.add_customer(
        id="hilltop-dental",
        name="Hilltop Family Dental",
        domain="hilltopdental.com",
        platform="webflow",
        city="Austin",
        state="TX",
        zip="78756",
        address="4500 Medical Pkwy",
        phone="(512) 555-0199",
        specialties=["General Dentistry", "Implants"],
        hours="Mon-Fri 8am-5pm",
        emergency_available=True,
    )
    db.add_provider(
        customer_id="hilltop-dental",
        name="Dr. David Gallup",
        credentials="DDS",
        specialties=["Implants", "Cosmetic"],
        years_experience=27,
        bio="Board-certified implant specialist.",
        is_primary=True,
    )
    db.add_contact(
        customer_id="hilltop-dental",
        name="Dr. David Gallup",
        email="gallup@hilltopdental.com",
        role="owner",
    )
    return db


class TestCustomerCRUD:
    def test_add_and_get_customer(self, db):
        db.add_customer(
            id="test-practice",
            name="Test Practice",
            domain="testpractice.com",
            platform="squarespace",
            city="Reno",
            state="NV",
        )
        customer = db.get_customer("test-practice")
        assert customer is not None
        assert customer["name"] == "Test Practice"
        assert customer["domain"] == "testpractice.com"
        assert customer["platform"] == "squarespace"
        assert customer["city"] == "Reno"
        assert customer["status"] == "onboarding"

    def test_list_customers(self, populated_db):
        customers = populated_db.list_customers()
        assert len(customers) == 1
        assert customers[0]["name"] == "Hilltop Family Dental"

    def test_list_customers_by_status(self, populated_db):
        assert len(populated_db.list_customers(status="onboarding")) == 1
        assert len(populated_db.list_customers(status="active")) == 0

    def test_update_customer(self, populated_db):
        populated_db.update_customer("hilltop-dental", city="Dallas", phone="(214) 555-1234")
        customer = populated_db.get_customer("hilltop-dental")
        assert customer["city"] == "Dallas"
        assert customer["phone"] == "(214) 555-1234"

    def test_set_customer_status(self, populated_db):
        populated_db.set_customer_status("hilltop-dental", "active")
        customer = populated_db.get_customer("hilltop-dental")
        assert customer["status"] == "active"
        assert customer["onboarded_at"] is not None

    def test_status_note_and_activity_timeline(self, populated_db):
        # Pinned status note is distinct from the lifecycle status field.
        populated_db.set_customer_status_note(
            "hilltop-dental", status_note="Awaiting Webflow token", next_action="Ping Adam Fri")
        c = populated_db.get_customer("hilltop-dental")
        assert c["status_note"] == "Awaiting Webflow token"
        assert c["next_action"] == "Ping Adam Fri"
        assert c["status"] != "Awaiting Webflow token"  # didn't clobber lifecycle status

        # Activity timeline: note + email, with gmail de-dupe.
        populated_db.add_customer_activity("hilltop-dental", "note", body="Called owner")
        populated_db.add_customer_activity(
            "hilltop-dental", "email", subject="Re: access", body="ok",
            meta={"gmail_id": "m1", "from": "owner@x.com"})
        dup = populated_db.add_customer_activity(
            "hilltop-dental", "email", subject="Re: access", body="ok", meta={"gmail_id": "m1"})
        assert dup == 0  # duplicate gmail_id skipped
        acts = populated_db.get_customer_activities("hilltop-dental")
        assert len(acts) == 2
        assert acts[0]["meta"].get("gmail_id") == "m1"  # newest first, meta parsed

    def test_get_nonexistent_customer(self, db):
        assert db.get_customer("nonexistent") is None

    def test_specialties_stored_as_json(self, populated_db):
        customer = populated_db.get_customer("hilltop-dental")
        assert isinstance(customer["specialties"], list)
        assert "General Dentistry" in customer["specialties"]

    def test_emergency_available_bool(self, populated_db):
        customer = populated_db.get_customer("hilltop-dental")
        assert customer["emergency_available"] is True


class TestProviders:
    def test_add_and_get_providers(self, populated_db):
        providers = populated_db.get_providers("hilltop-dental")
        assert len(providers) == 1
        assert providers[0]["name"] == "Dr. David Gallup"
        assert providers[0]["credentials"] == "DDS"
        assert isinstance(providers[0]["specialties"], list)
        assert "Implants" in providers[0]["specialties"]

    def test_multiple_providers(self, populated_db):
        populated_db.add_provider(
            customer_id="hilltop-dental",
            name="Dr. Sarah Chen",
            credentials="DMD",
        )
        providers = populated_db.get_providers("hilltop-dental")
        assert len(providers) == 2


class TestContacts:
    def test_add_and_get_contacts(self, populated_db):
        contacts = populated_db.get_contacts("hilltop-dental")
        assert len(contacts) == 1
        assert contacts[0]["name"] == "Dr. David Gallup"
        assert contacts[0]["role"] == "owner"


class TestPlatformAccess:
    def test_add_and_track_access(self, populated_db):
        populated_db.add_platform_access("hilltop-dental", "gsc")
        populated_db.add_platform_access("hilltop-dental", "ga")
        populated_db.add_platform_access("hilltop-dental", "webflow")

        access = populated_db.get_platform_access("hilltop-dental")
        assert len(access) == 3
        assert all(a["status"] == "pending" for a in access)

    def test_update_access_status(self, populated_db):
        populated_db.add_platform_access("hilltop-dental", "gsc")
        populated_db.update_access_status("hilltop-dental", "gsc", "granted")

        access = populated_db.get_platform_access("hilltop-dental")
        assert access[0]["status"] == "granted"
        assert access[0]["granted_at"] is not None

    def test_pending_access(self, populated_db):
        populated_db.add_platform_access("hilltop-dental", "gsc")
        populated_db.add_platform_access("hilltop-dental", "ga")
        populated_db.update_access_status("hilltop-dental", "gsc", "granted")

        pending = populated_db.get_pending_access("hilltop-dental")
        assert len(pending) == 1
        assert pending[0]["platform"] == "ga"


class TestGooglePlaces:
    def test_upsert_and_get(self, populated_db):
        populated_db.upsert_google_places(
            customer_id="hilltop-dental",
            place_id="ChIJ123",
            rating=4.7,
            review_count=156,
            match_confidence="high",
            lat=30.31,
            lng=-97.74,
        )
        places = populated_db.get_google_places("hilltop-dental")
        assert places is not None
        assert places["rating"] == 4.7
        assert places["review_count"] == 156

    def test_upsert_updates_existing(self, populated_db):
        populated_db.upsert_google_places("hilltop-dental", "ChIJ123", 4.7, 156, "high")
        populated_db.upsert_google_places("hilltop-dental", "ChIJ123", 4.8, 170, "high")
        places = populated_db.get_google_places("hilltop-dental")
        assert places["rating"] == 4.8
        assert places["review_count"] == 170


class TestCompetitors:
    def test_add_and_get_competitors(self, populated_db):
        populated_db.add_competitor("hilltop-dental", "Walden Dental", 4.5, 200, "Austin TX")
        populated_db.add_competitor("hilltop-dental", "River Rock", 4.2, 89, "Austin TX")

        comps = populated_db.get_competitors("hilltop-dental")
        assert len(comps) == 2
        assert comps[0]["name"] == "Walden Dental"  # sorted by review_count desc

    def test_replace_competitors(self, populated_db):
        populated_db.add_competitor("hilltop-dental", "Old Competitor", 3.0, 10)
        populated_db.replace_competitors("hilltop-dental", [
            {"name": "New Comp 1", "rating": 4.5, "review_count": 100},
            {"name": "New Comp 2", "rating": 4.0, "review_count": 50},
        ])
        comps = populated_db.get_competitors("hilltop-dental")
        assert len(comps) == 2
        assert comps[0]["name"] == "New Comp 1"


class TestRuns:
    def test_create_and_get_run(self, populated_db):
        run_id = populated_db.create_run("hilltop-dental")
        assert run_id > 0

        run = populated_db.get_latest_run("hilltop-dental")
        assert run is not None
        assert run["status"] == "running"
        assert run["customer_id"] == "hilltop-dental"

    def test_update_run(self, populated_db):
        run_id = populated_db.create_run("hilltop-dental")
        populated_db.update_run(
            run_id,
            status="staged",
            pages_crawled=15,
            changes=["Generated llms.txt", "Generated schema"],
            errors=[],
        )
        run = populated_db.get_latest_run("hilltop-dental")
        assert run["status"] == "staged"
        assert run["pages_crawled"] == 15
        assert len(run["changes"]) == 2

    def test_approve_and_publish_run(self, populated_db):
        run_id = populated_db.create_run("hilltop-dental")
        populated_db.update_run(run_id, status="staged")
        populated_db.approve_run(run_id)

        run = populated_db.get_latest_run("hilltop-dental")
        assert run["approved"] == 1
        assert run["status"] == "approved"

        populated_db.mark_run_published(run_id)
        run = populated_db.get_latest_run("hilltop-dental")
        assert run["status"] == "published"
        assert run["published_at"] is not None

    def test_staged_runs(self, populated_db):
        run_id = populated_db.create_run("hilltop-dental")
        populated_db.update_run(run_id, status="staged")

        staged = populated_db.get_staged_runs()
        assert len(staged) == 1


class TestKPIs:
    def test_record_and_get_kpi(self, populated_db):
        populated_db.record_kpi("hilltop-dental", "review_count", 156, "2024-01-15")
        populated_db.record_kpi("hilltop-dental", "review_count", 162, "2024-02-15")

        kpis = populated_db.get_kpis("hilltop-dental", "review_count")
        assert len(kpis) == 2
        assert kpis[0]["value"] == 162  # most recent first

    def test_get_latest_kpi(self, populated_db):
        populated_db.record_kpi("hilltop-dental", "rating", 4.7, "2024-01-15")
        populated_db.record_kpi("hilltop-dental", "rating", 4.8, "2024-02-15")

        latest = populated_db.get_latest_kpi("hilltop-dental", "rating")
        assert latest["value"] == 4.8

    def test_no_kpi_returns_none(self, populated_db):
        assert populated_db.get_latest_kpi("hilltop-dental", "ai_mentions") is None


class TestToConfigCustomer:
    def test_converts_to_customer_object(self, populated_db, monkeypatch):
        # Mock secrets manager
        monkeypatch.setenv("WEBFLOW_KEY_HILLTOP_DENTAL", "test-key")
        customer = populated_db.to_config_customer("hilltop-dental")
        assert customer is not None
        assert customer.name == "Hilltop Family Dental"
        assert customer.city == "Austin"
        assert len(customer.providers) == 1
        assert customer.providers[0].name == "Dr. David Gallup"


class TestImportFromJson:
    def test_import_from_json(self, db, tmp_path):
        json_data = {
            "customers": [{
                "id": "test-practice",
                "name": "Test Practice",
                "domain": "test.com",
                "city": "Austin",
                "state": "TX",
                "providers": [
                    {"name": "Dr. Test", "credentials": "DDS", "specialties": ["General"]}
                ],
            }]
        }
        json_path = tmp_path / "customers.json"
        json_path.write_text(json.dumps(json_data))

        db.import_from_json(str(json_path))

        customer = db.get_customer("test-practice")
        assert customer is not None
        assert customer["name"] == "Test Practice"

        providers = db.get_providers("test-practice")
        assert len(providers) == 1

    def test_import_skips_existing(self, db, tmp_path):
        db.add_customer(id="existing", name="Existing", domain="existing.com")

        json_data = {
            "customers": [
                {"id": "existing", "name": "Updated Name", "domain": "existing.com", "city": "", "state": ""},
                {"id": "new-one", "name": "New Practice", "domain": "new.com", "city": "", "state": ""},
            ]
        }
        json_path = tmp_path / "customers.json"
        json_path.write_text(json.dumps(json_data))

        db.import_from_json(str(json_path))

        # Existing customer should NOT be updated
        customer = db.get_customer("existing")
        assert customer["name"] == "Existing"

        # New customer should be added
        assert db.get_customer("new-one") is not None


# --- Off-site authority ledger (FATJOE orders + assets) ---

def test_offsite_order_lifecycle(populated_db):
    db = populated_db
    cid = "hilltop-dental"
    oid = db.add_offsite_order(
        cid, "link", target_url="https://hilltopdental.com/implants-austin",
        anchor_text="dental implants in Austin", anchor_type="partial",
        dr_tier=30, cost_usd=120.0, vendor_order_id="FJ-42",
    )
    assert oid > 0
    order = db.get_offsite_order(oid)
    assert order["status"] == "ordered"
    assert order["dr_tier"] == 30
    assert order["customer_id"] == cid

    # Adding an asset advances nothing automatically here, but delivered sets stamp.
    db.update_offsite_order(oid, status="delivered")
    assert db.get_offsite_order(oid)["delivered_at"]


def test_offsite_assets_dedup_and_summary(populated_db):
    db = populated_db
    cid = "hilltop-dental"
    oid = db.add_offsite_order(cid, "link", cost_usd=120.0)
    db.add_offsite_asset(oid, cid, "https://blog.example.com/post",
                         asset_type="link", domain="blog.example.com", da=27)
    # Duplicate live_url is ignored (UNIQUE constraint).
    db.add_offsite_asset(oid, cid, "https://blog.example.com/post",
                         asset_type="link", domain="blog.example.com", da=99)
    assets = db.get_offsite_assets(cid)
    assert len(assets) == 1
    assert assets[0]["da"] == 27

    cit = db.add_offsite_order(cid, "citation", quantity=100, cost_usd=120.0)
    db.add_offsite_asset(cit, cid, "https://yelp.com/biz/x", asset_type="citation", domain="yelp.com")

    s = db.offsite_summary(cid)
    assert s["links"] == 1
    assert s["citations"] == 1
    assert s["ref_domains"] == 1          # only link/mention domains count
    assert s["avg_link_da"] == 27
    assert s["spend_usd"] == 240.0


def test_offsite_delete_cascades_assets(populated_db):
    db = populated_db
    cid = "hilltop-dental"
    oid = db.add_offsite_order(cid, "link")
    db.add_offsite_asset(oid, cid, "https://x.com/a", asset_type="link", domain="x.com")
    assert db.delete_offsite_order(oid) is True
    assert db.get_offsite_assets(cid) == []
    assert db.get_offsite_order(oid) is None


class TestClientPortalUsers:
    def test_create_client_user_issues_signup_token(self, populated_db):
        db = populated_db
        result = db.create_client_user("hilltop-dental", "davidg", "Dr. David Gallup")
        assert result["id"] is not None
        assert result["signup_token"]

        users = db.list_client_users("hilltop-dental")
        assert len(users) == 1
        assert users[0]["username"] == "davidg"
        assert users[0]["password_hash"] is None

    def test_duplicate_username_raises_clean_error(self, populated_db):
        db = populated_db
        db.create_client_user("hilltop-dental", "davidg")
        with pytest.raises(ValueError):
            db.create_client_user("hilltop-dental", "davidg")

    def test_get_client_user_by_signup_token_hit_and_miss(self, populated_db):
        db = populated_db
        result = db.create_client_user("hilltop-dental", "davidg")
        token = result["signup_token"]

        found = db.get_client_user_by_signup_token(token)
        assert found is not None
        assert found["username"] == "davidg"

        assert db.get_client_user_by_signup_token("not-a-real-token") is None

    def test_complete_client_signup_then_token_fails_second_time(self, populated_db):
        db = populated_db
        result = db.create_client_user("hilltop-dental", "davidg")
        token = result["signup_token"]

        assert db.complete_client_signup(token, "correct horse battery staple") is True
        # Token is consumed: same token doesn't work again.
        assert db.complete_client_signup(token, "another password") is False
        # And no longer resolves via lookup either.
        assert db.get_client_user_by_signup_token(token) is None

    def test_authenticate_client_user_before_and_after_signup(self, populated_db):
        db = populated_db
        result = db.create_client_user("hilltop-dental", "davidg")
        token = result["signup_token"]

        # Not yet signed up: authentication must fail even with the eventual password.
        assert db.authenticate_client_user("davidg", "correct horse battery staple") is None

        db.complete_client_signup(token, "correct horse battery staple")

        user = db.authenticate_client_user("davidg", "correct horse battery staple")
        assert user is not None
        assert user["username"] == "davidg"
        # last_login is stamped by this call (mirrors authenticate_user's precedent of
        # returning the pre-update row), so re-fetch to confirm it was actually set.
        assert db.list_client_users("hilltop-dental")[0]["last_login"] is not None

    def test_authenticate_client_user_wrong_password(self, populated_db):
        db = populated_db
        result = db.create_client_user("hilltop-dental", "davidg")
        db.complete_client_signup(result["signup_token"], "correct horse battery staple")
        assert db.authenticate_client_user("davidg", "wrong password") is None

    def test_authenticate_client_user_inactive(self, populated_db):
        db = populated_db
        result = db.create_client_user("hilltop-dental", "davidg")
        db.complete_client_signup(result["signup_token"], "correct horse battery staple")
        user = db.list_client_users("hilltop-dental")[0]
        db.set_client_user_active(user["id"], False)
        assert db.authenticate_client_user("davidg", "correct horse battery staple") is None

    def test_regenerate_client_signup_token_invalidates_old_issues_new(self, populated_db):
        db = populated_db
        result = db.create_client_user("hilltop-dental", "davidg")
        old_token = result["signup_token"]
        db.complete_client_signup(old_token, "correct horse battery staple")

        user = db.list_client_users("hilltop-dental")[0]
        new_token = db.regenerate_client_signup_token(user["id"])

        assert new_token != old_token
        assert db.get_client_user_by_signup_token(old_token) is None
        assert db.get_client_user_by_signup_token(new_token) is not None
        # Password was cleared, so the old password no longer authenticates.
        assert db.authenticate_client_user("davidg", "correct horse battery staple") is None
        # And the new token completes signup normally.
        assert db.complete_client_signup(new_token, "a new password") is True
        assert db.authenticate_client_user("davidg", "a new password") is not None

    def test_delete_client_user(self, populated_db):
        db = populated_db
        result = db.create_client_user("hilltop-dental", "davidg")
        user = db.list_client_users("hilltop-dental")[0]
        db.delete_client_user(user["id"])
        assert db.list_client_users("hilltop-dental") == []


class TestReportSnapshotByID:
    def test_get_report_snapshot_hit(self, populated_db):
        db = populated_db
        db.save_report_snapshot(
            "hilltop-dental", "weekly", "2026-07-01", "2026-07-07",
            score=72, payload_json=json.dumps({"score": 72}), html="<html>report</html>",
        )
        row = db.conn.execute(
            "SELECT id FROM report_snapshots WHERE customer_id = ?", ("hilltop-dental",)
        ).fetchone()
        snap = db.get_report_snapshot(row["id"])
        assert snap is not None
        assert snap["score"] == 72
        assert snap["html"] == "<html>report</html>"
        assert json.loads(snap["payload_json"]) == {"score": 72}

    def test_get_report_snapshot_miss(self, populated_db):
        assert populated_db.get_report_snapshot(999999) is None
