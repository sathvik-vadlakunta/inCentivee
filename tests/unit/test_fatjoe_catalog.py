"""FATJOE catalog: seed, price/buy-link resolution, real-COGS into Expenses."""

from geo_agent import fatjoe_plan as fp
from geo_agent.db import CustomerDB
from geo_agent.expenses import compute_expenses


def _db():
    return CustomerDB(":memory:")


class TestCatalogSeedAndResolve:
    def test_seed_populates_all_families(self):
        db = _db()
        cat = db.get_fatjoe_catalog()
        fams = {c["family"] for c in cat}
        assert fams == {"citation", "blogger_outreach", "niche_edit", "mention"}
        db.close()

    def test_find_exact_dr(self):
        db = _db()
        assert db.find_catalog_item("blogger_outreach", 40)["product_key"] == "blogger_outreach_dr40"
        db.close()

    def test_find_falls_up_to_next_band(self):
        db = _db()
        # No DR35 row → resolves to the next band ≥35 (DR40).
        item = db.find_catalog_item("niche_edit", 35)
        assert item["dr_tier"] == 40
        db.close()

    def test_update_marks_verified(self):
        db = _db()
        db.update_catalog_item("mention_brand", price_usd=210.0, buy_url="https://x", verified=1)
        it = db.get_catalog_item("mention_brand")
        assert it["price_usd"] == 210.0 and it["verified"] == 1 and it["buy_url"] == "https://x"
        db.close()


class TestCostResolution:
    def test_resolve_product_uses_catalog_price_and_url(self):
        db = _db()
        spec = {"type": "link", "qty": 4, "dr_tier": 40}
        prod = fp.resolve_product(db, spec)
        # 4 × DR40 blogger outreach @ real $243 = $972, with the real buy link.
        assert prod["cost_each_period"] == 972
        assert prod["unit_price"] == 243.0
        assert "fatjoe.com" in prod["buy_url"]
        db.close()

    def test_citation_is_pack_price_not_times_qty(self):
        db = _db()
        spec = {"type": "citation", "qty": 100, "dr_tier": None}
        prod = fp.resolve_product(db, spec)
        assert prod["cost_each_period"] == 135  # one campaign price, not ×100
        db.close()

    def test_due_orders_attach_buy_links(self):
        db = _db()
        due = fp.due_orders(db, "cust1", "Dominate plan")
        assert due["tier"] == "dominate"
        for i in due["items"]:
            assert i["buy_url"].startswith("https://fatjoe.com")
            assert i["cost_each_period"] > 0
        db.close()

    def test_dominate_has_two_link_rows_2x40_2x30(self):
        db = _db()
        due = fp.due_orders(db, "cust1", "Dominate plan")
        links = sorted([i for i in due["items"] if i["type"] == "link"], key=lambda x: -x["dr_tier"])
        assert [(l["dr_tier"], l["qty_target"]) for l in links] == [(40, 2), (30, 2)]
        # real prices: DR40 $243 ×2 = $486, DR30 $135 ×2 = $270
        assert links[0]["cost_each_period"] == 486
        assert links[1]["cost_each_period"] == 270
        db.close()

    def test_higher_dr_satisfies_lower_rows(self):
        # Dominate needs 2×DR40 + 2×DR30. Ordering 4×DR40 should auto-complete BOTH.
        db = _db()
        db.add_customer("c1", "C", "c.com")
        for _ in range(4):
            db.add_offsite_order("c1", "link", quantity=1, dr_tier=40, status="ordered")
        due = fp.due_orders(db, "c1", "Dominate")
        links = [i for i in due["items"] if i["type"] == "link"]
        assert all(l["qty_due"] == 0 for l in links)  # both rows satisfied by the DR40s
        db.close()

    def test_lower_dr_does_not_satisfy_higher_and_no_overcount(self):
        db = _db()
        db.add_customer("c1", "C", "c.com")
        # Only 2×DR40 ordered: DR40 row clears, DR30 row still owed (no over-credit).
        for _ in range(2):
            db.add_offsite_order("c1", "link", quantity=1, dr_tier=40, status="ordered")
        due = fp.due_orders(db, "c1", "Dominate")
        by = {i["dr_tier"]: i for i in due["items"] if i["type"] == "link"}
        assert by[40]["qty_due"] == 0 and by[30]["qty_due"] == 2
        db.close()

    def test_count_respects_dr_tier(self):
        db = _db()
        db.add_customer("c1", "C One", "c1.com")
        db.add_offsite_order("c1", "link", quantity=1, dr_tier=40, status="ordered")
        db.add_offsite_order("c1", "link", quantity=1, dr_tier=30, status="ordered")
        assert db.count_offsite_orders_in_period("c1", "link") == 2          # all links
        assert db.count_offsite_orders_in_period("c1", "link", dr_tier=40) == 1  # only DR40
        assert db.count_offsite_orders_in_period("c1", "link", dr_tier=30) == 1
        db.close()


class TestExpensesCogs:
    def test_real_fatjoe_spend_flows_into_expenses(self):
        d = compute_expenses(5, fatjoe_mtd=2280.0, fatjoe_total=9500.0)
        assert d["totals"]["variable_cogs"] == 2280.0          # only the FATJOE line, not doubled
        assert d["totals"]["all_in_monthly"] == round(d["totals"]["recurring"] + 2280.0, 2)
        fj = [r for r in d["groups"]["Link Building (variable COGS)"] if r["vendor"] == "FATJOE"][0]
        assert fj["monthly_effective"] == 2280.0

    def test_no_spend_keeps_variable_placeholder(self):
        d = compute_expenses(5)  # fatjoe_mtd=None
        assert d["totals"]["variable_cogs"] == 0.0
        fj = [r for r in d["groups"]["Link Building (variable COGS)"] if r["vendor"] == "FATJOE"][0]
        assert fj["monthly_effective"] is None

    def test_offsite_spend_sums_logged_orders(self):
        db = _db()
        db.add_customer("c1", "C One", "c1.com")
        db.add_offsite_order("c1", "link", quantity=1, cost_usd=285.0, status="ordered")
        db.add_offsite_order("c1", "citation", quantity=1, cost_usd=120.0, status="ordered")
        db.add_offsite_order("c1", "link", quantity=1, cost_usd=99.0, status="cancelled")  # excluded
        assert db.offsite_spend() == 405.0
        assert db.offsite_spend(customer_id="c1") == 405.0
        db.close()
