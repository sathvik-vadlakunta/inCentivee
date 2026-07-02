"""Weekly-report authority section: backlinks/citations in-progress vs completed."""

from datetime import datetime, timezone

from geo_agent.db import CustomerDB
from geo_agent import weekly_report as wr


def _today():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _report(db):
    return wr.build_report_data(db, "c1", period_end=_today(), period_days=30)


def test_in_progress_orders_render_without_any_completed():
    db = CustomerDB(":memory:")
    db.add_customer("c1", "C1", "c1.com")
    db.add_offsite_order("c1", "link", status="in_progress", quantity=2, dr_tier=40)
    db.add_offsite_order("c1", "citation", status="ordered", quantity=1)
    sec = _report(db)["sections"].get("offsite")
    assert sec is not None  # renders on WIP alone, not only on completed work
    assert "2 backlinks (DR40+) being built" in sec["wip_items"]
    assert any("citation package" in w for w in sec["wip_items"])
    html = wr.render_html(_report(db))
    assert "In progress" in html
    db.close()


def test_completed_assets_counted_and_labeled():
    db = CustomerDB(":memory:")
    db.add_customer("c1", "C1", "c1.com")
    oid = db.add_offsite_order("c1", "link", status="live", quantity=1, dr_tier=30)
    db.add_offsite_asset(oid, "c1", "https://blog.example.com/p",
                         asset_type="link", domain="blog.example.com", da=45)
    sec = _report(db)["sections"]["offsite"]
    assert sec["links"] == 1
    html = wr.render_html(_report(db))
    assert "Completed" in html
    db.close()


def test_delivered_orders_not_counted_as_wip():
    db = CustomerDB(":memory:")
    db.add_customer("c1", "C1", "c1.com")
    db.add_offsite_order("c1", "link", status="live", quantity=1, dr_tier=30)
    db.add_offsite_order("c1", "link", status="cancelled", quantity=1)
    sec = _report(db)["sections"].get("offsite")
    # No live assets and no active WIP → section may be absent; if present, WIP empty.
    assert sec is None or sec.get("wip_items") == []
    db.close()
