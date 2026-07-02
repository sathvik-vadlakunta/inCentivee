"""Retail (client-facing) pricing layer on top of FATJOE COGS:
sell_usd on the catalog + orders, offsite_revenue, and the ad-hoc order route."""

from geo_agent.db import CustomerDB


def _db():
    return CustomerDB(":memory:")


class TestCatalogSellPrice:
    def test_seed_populates_sell_usd(self):
        db = _db()
        cat = {c["product_key"]: c for c in db.get_fatjoe_catalog()}
        assert cat["citation_100"]["sell_usd"] == 299.0
        assert cat["blogger_outreach_dr40"]["sell_usd"] == 499.0
        assert cat["mention_brand"]["sell_usd"] == 749.0
        # niche edits ~ 2× COGS (seeded defaults)
        assert cat["niche_edit_dr40"]["sell_usd"] == 399.0
        # every row carries a positive retail price
        assert all(c["sell_usd"] > 0 for c in cat.values())
        db.close()

    def test_sell_usd_column_present(self):
        db = _db()
        cols = [r[1] for r in db.conn.execute("PRAGMA table_info(fatjoe_catalog)").fetchall()]
        assert "sell_usd" in cols
        db.close()

    def test_update_catalog_item_saves_sell_usd(self):
        db = _db()
        db.update_catalog_item("mention_brand", price_usd=210.0, buy_url="https://x",
                               verified=1, sell_usd=899.0)
        it = db.get_catalog_item("mention_brand")
        assert it["price_usd"] == 210.0
        assert it["sell_usd"] == 899.0
        assert it["buy_url"] == "https://x"
        db.close()

    def test_update_without_sell_preserves_existing(self):
        db = _db()
        before = db.get_catalog_item("blogger_outreach_dr40")["sell_usd"]
        db.update_catalog_item("blogger_outreach_dr40", price_usd=250.0,
                               buy_url="https://y", verified=1)
        assert db.get_catalog_item("blogger_outreach_dr40")["sell_usd"] == before
        db.close()


class TestOrderSellPriceAndRevenue:
    def test_add_offsite_order_stores_sell_usd(self):
        db = _db()
        db.add_customer("c1", "C One", "c1.com")
        oid = db.add_offsite_order("c1", "link", quantity=1, cost_usd=243.0,
                                   sell_usd=499.0, status="ordered")
        row = db.get_offsite_order(oid)
        assert row["cost_usd"] == 243.0
        assert row["sell_usd"] == 499.0
        db.close()

    def test_offsite_revenue_sums_excluding_cancelled(self):
        db = _db()
        db.add_customer("c1", "C One", "c1.com")
        db.add_offsite_order("c1", "link", quantity=1, cost_usd=243.0, sell_usd=499.0, status="ordered")
        db.add_offsite_order("c1", "citation", quantity=1, cost_usd=135.0, sell_usd=299.0, status="ordered")
        db.add_offsite_order("c1", "link", quantity=1, cost_usd=99.0, sell_usd=199.0, status="cancelled")
        assert db.offsite_revenue() == 798.0
        assert db.offsite_revenue(customer_id="c1") == 798.0
        # COGS still excludes cancelled too — margin is consistent
        assert db.offsite_spend() == 378.0
        db.close()

    def test_revenue_zero_when_no_orders(self):
        db = _db()
        assert db.offsite_revenue() == 0.0
        db.close()

    def test_adhoc_only_spend_excludes_subscription_cogs(self):
        """Margin must scope COGS to ad-hoc orders (sell_usd>0). A tier/subscription
        link logs sell_usd=0 and would otherwise drag margin negative."""
        db = _db()
        db.add_customer("c1", "C One", "c1.com")
        # subscription/tier link: real COGS, no client sell price
        db.add_offsite_order("c1", "link", quantity=1, cost_usd=200.0, status="ordered")
        # ad-hoc upsell: COGS + client sell price
        db.add_offsite_order("c1", "link", quantity=1, cost_usd=99.0, sell_usd=249.0, status="ordered")
        assert db.offsite_spend("c1") == 299.0          # all COGS
        assert db.offsite_spend("c1", adhoc_only=True) == 99.0  # ad-hoc COGS only
        revenue = db.offsite_revenue("c1")              # 249.0
        assert revenue - db.offsite_spend("c1", adhoc_only=True) == 150.0  # true ad-hoc margin
        db.close()


class TestDoublePayGuard:
    def test_recent_offsite_order_detects_duplicate(self):
        db = _db()
        db.add_customer("c1", "C One", "c1.com")
        db.add_offsite_order("c1", "link", quantity=1, dr_tier=40, cost_usd=243.0, status="ordered")
        # A matching order exists at/after epoch -> duplicate detected
        assert db.recent_offsite_order("c1", "link", 40, "1970-01-01T00:00:00Z") is not None
        # Different DR band is not a duplicate
        assert db.recent_offsite_order("c1", "link", 30, "1970-01-01T00:00:00Z") is None
        # Cutoff in the far future -> nothing recent
        assert db.recent_offsite_order("c1", "link", 40, "2999-01-01T00:00:00Z") is None
        db.close()

    def test_recent_offsite_order_ignores_cancelled(self):
        db = _db()
        db.add_customer("c1", "C One", "c1.com")
        db.add_offsite_order("c1", "citation", quantity=1, cost_usd=135.0, status="cancelled")
        assert db.recent_offsite_order("c1", "citation", None, "1970-01-01T00:00:00Z") is None
        db.close()
