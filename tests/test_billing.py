"""Tests for src.billing — tier checks, Stripe session creation."""
import os
import pytest
from unittest.mock import patch, MagicMock

os.environ.pop("DATABASE_URL", None)

from src import db
from src import billing


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("SQLITE_PATH", db_path)
    monkeypatch.setenv("MASTER_KEY", "ab" * 32)
    db._init_connection(db_path)
    db.init_schema()
    yield
    db._close_connection()


# ── is_pro ──


def test_is_pro_testing_mode(monkeypatch):
    """TESTING_MODE=true makes everyone Pro."""
    monkeypatch.setenv("TESTING_MODE", "true")
    assert billing.is_pro(None) is True
    assert billing.is_pro("any_user_id") is True


def test_is_pro_no_user():
    assert billing.is_pro(None) is False


def test_is_pro_free_user():
    user_id = db.create_user("free@example.com", "hash", b"key")
    assert billing.is_pro(user_id) is False


def test_is_pro_pro_user():
    user_id = db.create_user("pro@example.com", "hash", b"key")
    db.set_tier(user_id, "pro")
    assert billing.is_pro(user_id) is True


# ── get_price_for_currency ──


def test_get_price_for_currency_eur(monkeypatch):
    monkeypatch.setenv("STRIPE_PRICE_IDS", '{"eur_monthly":"price_eur_m","eur_yearly":"price_eur_y","eur_lifetime":"price_eur_l"}')
    assert billing.get_price_id("EUR", "monthly") == "price_eur_m"


def test_get_price_for_currency_fallback(monkeypatch):
    """Unknown currency falls back to EUR."""
    monkeypatch.setenv("STRIPE_PRICE_IDS", '{"eur_monthly":"price_eur_m"}')
    assert billing.get_price_id("USD", "monthly") == "price_eur_m"


# ── handle_checkout_completed ──


def test_handle_checkout_completed():
    user_id = db.create_user("checkout@example.com", "hash", b"key")
    billing.handle_checkout_completed(user_id, "cus_123", "sub_456")
    user = db.get_user_by_id(user_id)
    assert user["tier"] == "pro"
    assert user["stripe_customer_id"] == "cus_123"
    assert user["stripe_subscription_id"] == "sub_456"


def test_handle_checkout_completed_lifetime():
    """Lifetime purchases have no subscription ID."""
    user_id = db.create_user("lifetime@example.com", "hash", b"key")
    billing.handle_checkout_completed(user_id, "cus_789", None)
    user = db.get_user_by_id(user_id)
    assert user["tier"] == "pro"
    assert user["stripe_subscription_id"] is None


# ── handle_subscription_deleted ──


def test_handle_subscription_deleted():
    user_id = db.create_user("cancel@example.com", "hash", b"key")
    db.set_tier(user_id, "pro")
    db.set_stripe_ids(user_id, "cus_cancel", "sub_cancel")
    billing.handle_subscription_deleted("cus_cancel")
    user = db.get_user_by_id(user_id)
    assert user["tier"] == "free"
    assert user["stripe_subscription_id"] is None


# ── display prices ──


def test_display_prices():
    prices = billing.get_display_prices("EUR")
    assert prices["monthly"] == 8
    assert prices["yearly"] == 79
    assert prices["lifetime"] == 149
    assert prices["symbol"] == "\u20ac"


def test_display_prices_chf():
    prices = billing.get_display_prices("CHF")
    assert prices["monthly"] == 8
    assert prices["symbol"] == "CHF"
