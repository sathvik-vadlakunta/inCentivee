"""Stripe billing integration — normalize subscriptions into our DB shape.

The dashboard tracks, per customer: which plan they're on and whether they've
paid. Stripe is the source of truth; we mirror the minimum we need.

Webhook pattern: a webhook event is treated as a *notification*. We then read the
authoritative current state back from Stripe (`fetch_subscription`) and upsert it,
rather than trusting the (possibly out-of-order) event payload. This keeps all
parsing in one place and is naturally idempotent.

Requires STRIPE_SECRET_KEY in the environment. STRIPE_WEBHOOK_SECRET is used to
verify webhook signatures.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Stripe subscription statuses that mean "currently paying us".
ACTIVE_STATUSES = frozenset({"active", "trialing"})

_product_name_cache: dict[str, str] = {}


def _stripe():
    """Return the configured stripe module, or None if no secret key / not installed."""
    key = os.environ.get("STRIPE_SECRET_KEY")
    if not key:
        return None
    try:
        import stripe
    except ImportError:
        logger.warning("stripe package not installed — billing disabled")
        return None
    stripe.api_key = key
    return stripe


def billing_enabled() -> bool:
    return _stripe() is not None


def _g(obj, key, default=None):
    """Read a key from a Stripe object or plain dict."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _ts_to_iso(ts) -> str | None:
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
    except (ValueError, TypeError, OSError):
        return None


def _product_name(price) -> str:
    """Friendly plan name from a price's product (expanded object or bare id)."""
    product = _g(price, "product")
    if product is None:
        return ""
    if isinstance(product, str):
        if product in _product_name_cache:
            return _product_name_cache[product]
        stripe = _stripe()
        if not stripe:
            return ""
        try:
            name = _g(stripe.Product.retrieve(product), "name", "") or ""
        except Exception:  # noqa: BLE001 — never let a name lookup break billing
            name = ""
        _product_name_cache[product] = name
        return name
    return _g(product, "name", "") or ""


def parse_subscription(sub) -> dict:
    """Normalize a Stripe Subscription (ideally expanded with items.data.price.product,
    latest_invoice, customer) into the dict CustomerDB.upsert_subscription expects."""
    items = _g(_g(sub, "items"), "data") or []
    price = _g(items[0], "price") if items else None

    # Customer email: expanded customer object preferred; fall back to invoice.
    customer = _g(sub, "customer")
    email = ""
    stripe_customer_id = ""
    if isinstance(customer, str):
        stripe_customer_id = customer
    elif customer is not None:
        stripe_customer_id = _g(customer, "id", "") or ""
        email = _g(customer, "email", "") or ""

    invoice = _g(sub, "latest_invoice")
    latest_invoice_status = ""
    last_payment_at = None
    if invoice and not isinstance(invoice, str):
        latest_invoice_status = _g(invoice, "status", "") or ""
        if not email:
            email = _g(invoice, "customer_email", "") or ""
        if latest_invoice_status == "paid":
            paid_at = _g(_g(invoice, "status_transitions"), "paid_at")
            last_payment_at = _ts_to_iso(paid_at) or _ts_to_iso(_g(invoice, "created"))

    recurring = _g(price, "recurring")
    return {
        "stripe_subscription_id": _g(sub, "id", "") or "",
        "stripe_customer_id": stripe_customer_id,
        "stripe_customer_email": email,
        "plan_name": _product_name(price),
        "price_id": _g(price, "id", "") or "",
        "amount_cents": _g(price, "unit_amount", 0) or 0,
        "currency": _g(price, "currency", "usd") or "usd",
        "billing_interval": _g(recurring, "interval", "month") or "month",
        "status": _g(sub, "status", "incomplete") or "incomplete",
        "latest_invoice_status": latest_invoice_status,
        "last_payment_at": last_payment_at,
        "current_period_end": _ts_to_iso(_g(sub, "current_period_end")),
        "cancel_at_period_end": bool(_g(sub, "cancel_at_period_end")),
        "raw": {
            "id": _g(sub, "id"),
            "status": _g(sub, "status"),
            "plan_name": _product_name(price),
        },
    }


_EXPAND = ["items.data.price.product", "latest_invoice", "customer"]


def fetch_subscription(sub_id: str) -> dict | None:
    """Retrieve a subscription from Stripe (fully expanded) and parse it."""
    stripe = _stripe()
    if not stripe or not sub_id:
        return None
    try:
        sub = stripe.Subscription.retrieve(sub_id, expand=_EXPAND)
    except Exception as e:  # noqa: BLE001
        logger.warning("Stripe subscription fetch failed for %s: %s", sub_id, e)
        return None
    return parse_subscription(sub)


def sync_all(db) -> int:
    """Backfill: pull every subscription from Stripe and upsert. Returns count.
    Used for the initial population and the manual 'Sync from Stripe' button —
    webhooks keep it live thereafter."""
    stripe = _stripe()
    if not stripe:
        return 0
    n = 0
    try:
        for sub in stripe.Subscription.list(status="all", expand=["data." + e for e in _EXPAND], limit=100).auto_paging_iter():
            parsed = parse_subscription(sub)
            if db.upsert_subscription(parsed):
                n += 1
    except Exception as e:  # noqa: BLE001
        logger.warning("Stripe sync_all failed after %d: %s", n, e)
    return n


def verify_event(payload: bytes, sig_header: str):
    """Verify a webhook signature and return the Stripe event, or None on failure."""
    stripe = _stripe()
    secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
    if not stripe or not secret:
        return None
    try:
        return stripe.Webhook.construct_event(payload, sig_header, secret)
    except Exception as e:  # noqa: BLE001 — bad signature / malformed
        logger.warning("Stripe webhook verification failed: %s", e)
        return None


def subscription_id_from_event(event) -> str | None:
    """Extract the subscription id from any billing-relevant event object."""
    obj = _g(_g(event, "data"), "object") or {}
    obj_type = _g(obj, "object")
    if obj_type == "subscription":
        return _g(obj, "id")
    # invoice / checkout.session carry the subscription as a field
    sub = _g(obj, "subscription")
    if isinstance(sub, str):
        return sub
    if sub is not None:
        return _g(sub, "id")
    return None
