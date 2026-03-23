"""Billing and tier management — Stripe integration, feature gating.

All tier checks go through is_pro(). Gate logic is centralised here.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from src import db
from src.security_logger import (
    log_security_event, SUBSCRIPTION_CHANGED, PROMO_CODE_ATTEMPT,
)

_log = logging.getLogger(__name__)


# ── Pricing table ─────────────────────────────────────────

_PRICES = {
    "EUR": {"monthly": 8, "yearly": 79, "lifetime": 149, "symbol": "\u20ac"},
    "CHF": {"monthly": 8, "yearly": 79, "lifetime": 149, "symbol": "CHF"},
    "SEK": {"monthly": 89, "yearly": 879, "lifetime": 1649, "symbol": "kr"},
    "GBP": {"monthly": 7, "yearly": 69, "lifetime": 129, "symbol": "\u00a3"},
}

_LOCKED_TABS = {"Forecast", "Income"}

_LOCKED_TAB_DESCRIPTIONS = {
    "Forecast": "Run Monte Carlo simulations to project future portfolio value",
    "Income": "Track dividend income and yield across your portfolio",
}

FREE_POSITION_LIMIT = 10


# ── Tier check ────────────────────────────────────────────


def is_pro(user_id: str | None) -> bool:
    """Check if a user has Pro access. Lazy-downgrades expired promos."""
    if os.environ.get("TESTING_MODE", "").lower() == "true":
        return True
    if not user_id:
        return False
    user = db.get_user_by_id(user_id)
    if not user:
        return False
    if user.get("tier") != "pro":
        return False
    expires = user.get("pro_expires_at")
    if expires is None:
        return True  # Stripe Pro — no expiry
    if isinstance(expires, str):
        expires = datetime.fromisoformat(expires)
    # Ensure timezone-aware comparison (Postgres may return naive timestamps)
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) < expires:
        return True  # Promo still active
    # Promo expired — lazy downgrade (keep pro_expires_at as re-use evidence)
    db.set_tier(user_id, "free")
    return False


def is_tab_locked(tab_name: str) -> bool:
    """Check if a tab is in the locked set (requires Pro)."""
    return tab_name in _LOCKED_TABS


# ── Promo codes ──────────────────────────────────────────


def apply_promo_code(user_id: str, code: str) -> str:
    """Apply a promo code. Returns 'ok', 'invalid', 'already_used', or 'rate_limited'."""
    from src.auth import _check_rate, RateLimitError
    try:
        _check_rate("promo", user_id)
    except RateLimitError:
        log_security_event(PROMO_CODE_ATTEMPT, "HIGH", user_id=user_id, details={"result": "rate_limited"})
        return "rate_limited"
    expected = os.environ.get("PROMO_CODE", "")
    if not expected or code.strip().upper() != expected.strip().upper():
        log_security_event(PROMO_CODE_ATTEMPT, "MEDIUM", user_id=user_id, details={"result": "invalid"})
        return "invalid"
    user = db.get_user_by_id(user_id)
    if not user:
        return "invalid"
    if user.get("pro_expires_at") is not None:
        log_security_event(PROMO_CODE_ATTEMPT, "LOW", user_id=user_id, details={"result": "already_used"})
        return "already_used"
    db.set_tier(user_id, "pro")
    db.set_pro_expires(user_id, datetime.now(timezone.utc) + timedelta(days=30))
    log_security_event(PROMO_CODE_ATTEMPT, "LOW", user_id=user_id, details={"result": "ok"})
    return "ok"


# ── Display prices ────────────────────────────────────────


def get_display_prices(currency: str) -> dict:
    """Return display prices for a currency with a Stripe price. Falls back to EUR."""
    price_ids = json.loads(os.environ.get("STRIPE_PRICE_IDS", "{}"))
    key = f"{currency.lower()}_monthly"
    if key in price_ids:
        return _PRICES.get(currency, _PRICES["EUR"])
    return _PRICES["EUR"]


# ── Stripe price IDs ──────────────────────────────────────


def get_price_id(currency: str, interval: str) -> str:
    """Look up the Stripe price ID for a currency+interval combo."""
    price_ids = json.loads(os.environ.get("STRIPE_PRICE_IDS", "{}"))
    key = f"{currency.lower()}_{interval}"
    if key in price_ids:
        return price_ids[key]
    # Fallback: try each currency until we find one that exists
    for fallback in ("eur", "chf", "gbp", "sek"):
        fallback_key = f"{fallback}_{interval}"
        if fallback_key in price_ids:
            return price_ids[fallback_key]
    return ""


# ── Stripe checkout ───────────────────────────────────────


def create_checkout_session(user_id: str, email: str, currency: str, interval: str) -> str:
    """Create a Stripe Checkout Session. Returns the checkout URL."""
    import stripe
    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
    app_url = os.environ.get("APP_URL", "http://localhost:8080")

    price_id = get_price_id(currency, interval)
    mode = "payment" if interval == "lifetime" else "subscription"

    session = stripe.checkout.Session.create(
        customer_email=email,
        client_reference_id=user_id,
        line_items=[{"price": price_id, "quantity": 1}],
        mode=mode,
        success_url=f"{app_url}/?upgraded=1",
        cancel_url=f"{app_url}/pricing",
        allow_promotion_codes=True,
    )
    return session.url


def create_portal_session(stripe_customer_id: str) -> str:
    """Create a Stripe Customer Portal session. Returns the portal URL."""
    import stripe
    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
    app_url = os.environ.get("APP_URL", "http://localhost:8080")

    session = stripe.billing_portal.Session.create(
        customer=stripe_customer_id,
        return_url=app_url,
    )
    return session.url


# ── Webhook handlers ──────────────────────────────────────


def handle_checkout_completed(user_id: str, customer_id: str, subscription_id: str | None) -> None:
    """Handle successful checkout — upgrade user to Pro."""
    db.set_tier(user_id, "pro")
    db.set_stripe_ids(user_id, customer_id, subscription_id)
    db.set_pro_expires(user_id, None)  # Clear any promo expiry
    log_security_event(SUBSCRIPTION_CHANGED, "LOW", user_id=user_id, details={"action": "upgrade_to_pro", "customer_id": customer_id})


def handle_subscription_deleted(customer_id: str) -> None:
    """Handle subscription cancellation — downgrade to Free."""
    user = db.get_user_by_stripe_customer(customer_id)
    if not user:
        _log.warning("Subscription deleted for unknown customer %s", customer_id)
        return
    db.set_tier(user["id"], "free")
    db.set_stripe_ids(user["id"], customer_id, None)
    log_security_event(SUBSCRIPTION_CHANGED, "MEDIUM", user_id=user["id"], details={"action": "downgrade_to_free", "customer_id": customer_id})


# ── Admin helpers ─────────────────────────────────────────


def is_admin(email: str | None) -> bool:
    """Check if an email is in the ADMIN_EMAILS list."""
    if not email:
        return False
    admin_emails = os.environ.get("ADMIN_EMAILS", "").split(",")
    return email.strip().lower() in [e.strip().lower() for e in admin_emails]
