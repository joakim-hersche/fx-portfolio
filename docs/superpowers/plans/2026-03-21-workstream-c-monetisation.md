# Workstream C — Monetisation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Stripe billing with Free/Pro tiers, feature gates (bypassed in testing mode), locked tab overlays, a pricing page, and an admin dashboard.

**Architecture:** `src/billing.py` centralises all tier logic behind a single `is_pro()` function that checks `TESTING_MODE` env var first, then the user's `tier` column. Feature gates in `main.py` short-circuit the tab builder for locked tabs, rendering a paywall overlay from `src/ui/paywall.py` instead. Stripe Checkout handles payments; a webhook endpoint updates the user's tier. The admin dashboard is a separate `/admin` route with user management.

**Tech Stack:** Python 3.12, NiceGUI 3.8, Stripe (stripe Python SDK), pytest

**Spec:** `docs/superpowers/specs/2026-03-21-workstream-c-monetisation-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `src/billing.py` | Create | `is_pro()`, Stripe checkout session, webhook handling, customer portal |
| `src/ui/paywall.py` | Create | Locked tab overlay, pricing page builder |
| `src/db.py` | Modify | tier/stripe columns migration, new query functions |
| `main.py` | Modify | Gate checks in tab builder, export gate, position limit, account dropdown changes, webhook route, pricing route, admin route, success notification |
| `src/ui/sidebar.py` | Modify | Position limit check on add |
| `requirements.txt` | Modify | Add stripe |
| `tests/test_billing.py` | Create | is_pro, tier management tests |
| `tests/test_db.py` | Modify | Tests for new columns |

---

## Task 1: Database Schema — Tier + Stripe Columns

**Files:**
- Modify: `src/db.py`
- Modify: `tests/test_db.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_db.py`:

```python
# ── Tier and Stripe queries ──


def test_tier_defaults_to_free():
    user_id = db.create_user("tier@example.com", "hash", b"key")
    user = db.get_user_by_id(user_id)
    assert user["tier"] == "free"


def test_set_tier():
    user_id = db.create_user("pro@example.com", "hash", b"key")
    db.set_tier(user_id, "pro")
    user = db.get_user_by_id(user_id)
    assert user["tier"] == "pro"


def test_set_stripe_ids():
    user_id = db.create_user("stripe@example.com", "hash", b"key")
    db.set_stripe_ids(user_id, "cus_abc123", "sub_xyz789")
    user = db.get_user_by_id(user_id)
    assert user["stripe_customer_id"] == "cus_abc123"
    assert user["stripe_subscription_id"] == "sub_xyz789"


def test_get_user_by_stripe_customer():
    user_id = db.create_user("lookup@example.com", "hash", b"key")
    db.set_stripe_ids(user_id, "cus_lookup", None)
    user = db.get_user_by_stripe_customer("cus_lookup")
    assert user is not None
    assert user["id"] == user_id


def test_get_user_by_stripe_customer_not_found():
    assert db.get_user_by_stripe_customer("cus_nonexistent") is None


def test_get_all_users():
    db.create_user("all1@example.com", "hash", b"key")
    db.create_user("all2@example.com", "hash", b"key")
    users = db.get_all_users()
    emails = [u["email"] for u in users]
    assert "all1@example.com" in emails
    assert "all2@example.com" in emails
```

- [ ] **Step 2: Run tests — confirm they fail**

Run: `pytest tests/test_db.py -v -k "tier or stripe or get_all_users"`

- [ ] **Step 3: Add migration and query functions to `src/db.py`**

Add to end of `init_schema()` (after existing B2 migrations):

```python
    # C: tier and Stripe billing
    try:
        _execute("ALTER TABLE users ADD COLUMN tier TEXT DEFAULT 'free'")
    except Exception:
        pass
    try:
        _execute("ALTER TABLE users ADD COLUMN stripe_customer_id TEXT")
    except Exception:
        pass
    try:
        _execute("ALTER TABLE users ADD COLUMN stripe_subscription_id TEXT")
    except Exception:
        pass
```

Add new functions after the email alert queries section:

```python
# ── Tier and Stripe queries ───────────────────────────


def set_tier(user_id: str, tier: str) -> None:
    """Set user tier ('free' or 'pro')."""
    ph = _p(2)
    _execute(f"UPDATE users SET tier = {ph[0]} WHERE id = {ph[1]}", (tier, user_id))


def get_user_by_stripe_customer(customer_id: str) -> dict | None:
    """Look up a user by their Stripe customer ID."""
    ph = _p(1)[0]
    row = _fetchone(f"SELECT * FROM users WHERE stripe_customer_id = {ph}", (customer_id,))
    if row and _backend == "sqlite":
        row["email_verified"] = bool(row["email_verified"])
    return row


def set_stripe_ids(user_id: str, customer_id: str | None, subscription_id: str | None) -> None:
    """Store Stripe customer and subscription IDs."""
    ph = _p(3)
    _execute(
        f"UPDATE users SET stripe_customer_id = {ph[0]}, stripe_subscription_id = {ph[1]} WHERE id = {ph[2]}",
        (customer_id, subscription_id, user_id),
    )


def get_all_users() -> list[dict]:
    """Return all users (for admin dashboard)."""
    rows = _fetchall("SELECT * FROM users ORDER BY created_at DESC")
    if _backend == "sqlite":
        for r in rows:
            r["email_verified"] = bool(r["email_verified"])
    return rows
```

- [ ] **Step 4: Run tests — confirm they pass**

Run: `pytest tests/test_db.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/db.py tests/test_db.py
git commit -m "feat: add tier, stripe_customer_id, stripe_subscription_id columns"
```

---

## Task 2: Billing Logic (`src/billing.py`)

**Files:**
- Create: `src/billing.py`
- Create: `tests/test_billing.py`
- Modify: `requirements.txt`

- [ ] **Step 1: Add stripe dependency**

Append to `requirements.txt`:
```
stripe==12.2.0
```

Run: `pip install -r requirements.txt`

- [ ] **Step 2: Write failing tests**

```python
# tests/test_billing.py
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
```

- [ ] **Step 3: Run tests — confirm they fail**

Run: `pytest tests/test_billing.py -v`

- [ ] **Step 4: Implement `src/billing.py`**

```python
# src/billing.py
"""Billing and tier management — Stripe integration, feature gating.

All tier checks go through is_pro(). Gate logic is centralised here.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

from src import db

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
    """Check if a user has Pro access.

    Returns True if:
    - TESTING_MODE=true (bypasses all gates)
    - User's tier is 'pro'
    """
    if os.environ.get("TESTING_MODE", "").lower() == "true":
        return True
    if not user_id:
        return False
    user = db.get_user_by_id(user_id)
    if not user:
        return False
    return user.get("tier") == "pro"


def is_tab_locked(tab_name: str) -> bool:
    """Check if a tab is in the locked set (requires Pro)."""
    return tab_name in _LOCKED_TABS


# ── Display prices ────────────────────────────────────────


def get_display_prices(currency: str) -> dict:
    """Return display prices for a currency. Falls back to EUR."""
    return _PRICES.get(currency, _PRICES["EUR"])


# ── Stripe price IDs ──────────────────────────────────────


def get_price_id(currency: str, interval: str) -> str:
    """Look up the Stripe price ID for a currency+interval combo.

    Falls back to EUR if currency not found.
    """
    price_ids = json.loads(os.environ.get("STRIPE_PRICE_IDS", "{}"))
    key = f"{currency.lower()}_{interval}"
    if key in price_ids:
        return price_ids[key]
    # Fallback to EUR
    fallback_key = f"eur_{interval}"
    return price_ids.get(fallback_key, "")


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


def handle_subscription_deleted(customer_id: str) -> None:
    """Handle subscription cancellation — downgrade to Free."""
    user = db.get_user_by_stripe_customer(customer_id)
    if not user:
        _log.warning("Subscription deleted for unknown customer %s", customer_id)
        return
    db.set_tier(user["id"], "free")
    db.set_stripe_ids(user["id"], customer_id, None)


# ── Admin helpers ─────────────────────────────────────────


def is_admin(email: str | None) -> bool:
    """Check if an email is in the ADMIN_EMAILS list."""
    if not email:
        return False
    admin_emails = os.environ.get("ADMIN_EMAILS", "").split(",")
    return email.strip().lower() in [e.strip().lower() for e in admin_emails]
```

- [ ] **Step 5: Run tests — confirm they pass**

Run: `pytest tests/test_billing.py -v`

- [ ] **Step 6: Commit**

```bash
git add src/billing.py tests/test_billing.py requirements.txt
git commit -m "feat: add billing logic with is_pro, Stripe checkout, webhook handlers"
```

---

## Task 3: Paywall UI (`src/ui/paywall.py`)

**Files:**
- Create: `src/ui/paywall.py`

No unit tests — pure NiceGUI UI code.

- [ ] **Step 1: Create `src/ui/paywall.py`**

```python
# src/ui/paywall.py
"""Paywall UI — locked tab overlay and pricing page."""
from __future__ import annotations

from nicegui import app, run, ui

from src.billing import (
    get_display_prices, create_checkout_session, is_pro,
    _LOCKED_TAB_DESCRIPTIONS,
)
from src.theme import (
    ACCENT, BG_CARD, BG_MAIN, BORDER_SUBTLE,
    TEXT_DIM, TEXT_MUTED, TEXT_PRIMARY,
)


def render_locked_overlay(tab_name: str, currency: str) -> None:
    """Render a locked tab overlay with upgrade CTA."""
    description = _LOCKED_TAB_DESCRIPTIONS.get(tab_name, "This feature requires Pro")
    prices = get_display_prices(currency)
    symbol = prices["symbol"]
    monthly = prices["monthly"]

    with ui.column().classes("w-full items-center justify-center").style(
        "min-height:400px; padding:40px 20px;"
    ):
        # Blurred placeholder
        ui.html(
            '<div style="width:100%; max-width:600px; height:200px; border-radius:12px;'
            ' background:linear-gradient(135deg, rgba(59,130,246,0.08), rgba(139,92,246,0.08));'
            ' filter:blur(2px); margin-bottom:32px;"></div>'
        )

        ui.icon("lock").style("font-size:32px; color:rgba(255,255,255,0.3); margin-bottom:12px;")
        ui.label("Upgrade to Pro").style(
            f"font-size:22px; font-weight:700; color:{TEXT_PRIMARY}; margin-bottom:8px;"
        )
        ui.label(description).style(
            f"font-size:14px; color:{TEXT_MUTED}; margin-bottom:20px; text-align:center; max-width:400px;"
        )
        ui.label(f"From {symbol}{monthly}/month").style(
            f"font-size:13px; color:{TEXT_DIM}; margin-bottom:16px;"
        )
        ui.button("View plans", on_click=lambda: ui.navigate.to("/pricing")).props(
            "no-caps unelevated"
        ).style(f"background:{ACCENT}; border-radius:8px; font-size:14px; padding:8px 24px;")


def build_pricing_page(user_id: str | None, currency: str) -> None:
    """Build the /pricing page content."""
    prices = get_display_prices(currency)
    symbol = prices["symbol"]
    user_is_pro = is_pro(user_id)
    email = app.storage.user.get("auth_email")

    with ui.column().classes("w-full items-center").style(
        f"background:{BG_MAIN}; min-height:100vh; padding:40px 20px;"
    ):
        ui.label("Market Dashboard Pro").style(
            f"font-size:28px; font-weight:700; color:{TEXT_PRIMARY}; margin-bottom:8px;"
        )
        ui.label("Unlock the full power of your portfolio tracker").style(
            f"font-size:14px; color:{TEXT_MUTED}; margin-bottom:32px;"
        )

        # Interval selector
        selected_interval = {"value": "yearly"}

        interval_row = ui.row().classes("items-center gap-2").style("margin-bottom:32px;")

        def _update_interval(interval: str):
            selected_interval["value"] = interval
            _refresh_cards()

        with interval_row:
            for iv in ["monthly", "yearly", "lifetime"]:
                ui.button(
                    iv.capitalize(),
                    on_click=lambda i=iv: _update_interval(i),
                ).props("flat no-caps").style(
                    f"border:1px solid {BORDER_SUBTLE}; border-radius:6px; padding:4px 16px;"
                    f" font-size:13px; color:{TEXT_MUTED};"
                )

        # Cards container
        @ui.refreshable
        def _refresh_cards():
            iv = selected_interval["value"]
            price = prices[iv]
            period = {"monthly": "/month", "yearly": "/year", "lifetime": " one-time"}[iv]

            with ui.row().classes("items-start gap-6 justify-center flex-wrap"):
                # Free card
                with ui.card().style(
                    f"width:280px; background:{BG_CARD}; border:1px solid rgba(255,255,255,0.08);"
                    f" border-radius:12px; padding:28px;"
                ):
                    ui.label("Free").style(f"font-size:20px; font-weight:700; color:{TEXT_PRIMARY}; margin-bottom:4px;")
                    ui.label(f"{symbol}0").style(f"font-size:28px; font-weight:700; color:{TEXT_PRIMARY}; margin-bottom:16px;")
                    _feature_list([
                        ("Up to 10 positions", True),
                        ("Overview & Positions", True),
                        ("Portfolio Health", True),
                        ("Research & Guide", True),
                        ("Monte Carlo Forecast", False),
                        ("Income tracking", False),
                        ("Excel export", False),
                        ("Email alerts", False),
                    ])

                # Pro card
                with ui.card().style(
                    f"width:280px; background:{BG_CARD}; border:2px solid {ACCENT};"
                    f" border-radius:12px; padding:28px;"
                ):
                    ui.label("Pro").style(f"font-size:20px; font-weight:700; color:{ACCENT}; margin-bottom:4px;")
                    ui.label(f"{symbol}{price}{period}").style(
                        f"font-size:28px; font-weight:700; color:{TEXT_PRIMARY}; margin-bottom:16px;"
                    )
                    _feature_list([
                        ("Unlimited positions", True),
                        ("Overview & Positions", True),
                        ("Portfolio Health", True),
                        ("Research & Guide", True),
                        ("Monte Carlo Forecast", True),
                        ("Income tracking", True),
                        ("Excel export", True),
                        ("Email alerts", True),
                    ])
                    ui.html('<div style="height:12px;"></div>')

                    if user_is_pro:
                        ui.label("You're on Pro").style(
                            f"font-size:13px; color:{ACCENT}; font-weight:600; text-align:center; width:100%;"
                        )
                    elif not user_id:
                        ui.button("Sign in to upgrade", on_click=lambda: ui.navigate.to("/")).props(
                            "no-caps unelevated"
                        ).style(f"width:100%; background:{ACCENT}; border-radius:8px;")
                    else:
                        async def _checkout(interval=iv):
                            url = await run.io_bound(
                                create_checkout_session, user_id, email, currency, interval
                            )
                            ui.navigate.to(url, new_tab=False)

                        ui.button("Get started", on_click=_checkout).props(
                            "no-caps unelevated"
                        ).style(f"width:100%; background:{ACCENT}; border-radius:8px;")

        _refresh_cards()


def _feature_list(features: list[tuple[str, bool]]) -> None:
    """Render a feature checklist."""
    for label, included in features:
        icon = "check_circle" if included else "cancel"
        color = "#22C55E" if included else "rgba(255,255,255,0.2)"
        with ui.row().classes("items-center gap-2").style("margin-bottom:6px;"):
            ui.icon(icon).style(f"font-size:16px; color:{color};")
            ui.label(label).style(f"font-size:13px; color:{TEXT_MUTED};")
```

- [ ] **Step 2: Verify import works**

Run: `python3 -c "from src.ui.paywall import render_locked_overlay, build_pricing_page; print('OK')"`

- [ ] **Step 3: Commit**

```bash
git add src/ui/paywall.py
git commit -m "feat: add paywall overlay and pricing page UI"
```

---

## Task 4: Main App Integration — Feature Gates + Routes

**Files:**
- Modify: `main.py`

This is the largest integration task. Six edits.

- [ ] **Step 1: Add imports**

After line 54 (`from src.alert_job import start_alert_scheduler`), add:

```python
from src.billing import is_pro, is_tab_locked, create_portal_session, is_admin, FREE_POSITION_LIMIT
from src.ui.paywall import render_locked_overlay, build_pricing_page
```

- [ ] **Step 2: Add feature gate in `_build_tab`**

In the `_build_tab` function (around line 708), add a gate check at the start, before the spinner. Insert after `container.clear()` and before `with container:`:

Find:
```python
        async def _build_tab(name: str) -> None:
            """Build (or rebuild) a single tab's content."""
            container = _tab_containers[name]
            container.clear()
            with container:
                spinner = ui.spinner('dots', size='xl').classes('self-center')
```

Add a gate check **before** the existing code. Insert these lines at the start of the function body, before `container.clear()`:

```python
            # Feature gate — show paywall for locked tabs
            auth_uid = app.storage.user.get("user_id")
            if is_tab_locked(name) and not is_pro(auth_uid):
                container.clear()
                with container:
                    render_locked_overlay(name, currency)
                _tab_built[name] = True
                return
```

The rest of the function (container.clear(), spinner, try/finally) stays unchanged below this block.

- [ ] **Step 3: Add Excel export gate**

In the export dropdown section (around line 491), wrap the Excel menu item with a gate. Find the Excel export menu item and add a lock for free users:

Find:
```python
                    with ui.menu_item(on_click=lambda: export_excel(portfolio, currency)).style("padding:10px 14px;"):
```

Replace with:
```python
                    async def _export_excel_gated():
                        if not is_pro(app.storage.user.get("user_id")):
                            ui.notify("Excel export is a Pro feature.", type="warning")
                            return
                        export_excel(portfolio, currency)

                    with ui.menu_item(on_click=_export_excel_gated).style("padding:10px 14px;"):
```

- [ ] **Step 4: Update account dropdown — tier badge, alert gate, manage subscription**

Replace the account dropdown block (from `# ── Auth / account` through the Sign out menu item closing) with the updated version that includes:
- Tier badge on the button
- Email alerts toggle gated for Pro only
- "Manage subscription" link for Pro users with Stripe subscription
- Sign out

Find the line `# ── Auth / account ────────────────────────────────` and replace the entire `if auth_user_id:` branch (up to and including the Sign out menu_item) with:

```python
            if auth_user_id:
                _user_tier = "Pro" if is_pro(auth_user_id) else "Free"
                _tier_color = ACCENT if _user_tier == "Pro" else TEXT_DIM

                with ui.button(f"{auth_email or ''}", icon="expand_more").props(
                    "flat dense no-caps size=sm color=none"
                ).style(
                    f"border:1px solid {BORDER_INPUT}; border-radius:6px; padding:0 10px;"
                    f" height:28px; color:{TEXT_MUTED} !important; font-size:11px;"
                    f" max-width:200px; overflow:hidden; text-overflow:ellipsis;"
                ):
                    with ui.menu().style(
                        f"background:{BG_CARD}; border:1px solid rgba(255,255,255,0.12);"
                        f" border-radius:10px; min-width:220px;"
                    ):
                        # Tier badge
                        with ui.menu_item().style("padding:6px 14px;"):
                            ui.label(_user_tier).style(
                                f"font-size:11px; font-weight:600; color:{_tier_color};"
                                f" background:rgba(59,130,246,0.1); border-radius:4px; padding:2px 8px;"
                            )

                        ui.separator().style("margin:4px 14px; opacity:0.15;")

                        # Email alerts toggle (Pro only)
                        with ui.menu_item().style("padding:10px 14px;"):
                            with ui.row().classes("items-center gap-3 no-wrap w-full"):
                                ui.label("Email alerts").style(
                                    f"font-size:13px; color:{TEXT_PRIMARY}; font-weight:500;"
                                )
                                if is_pro(auth_user_id):
                                    alert_pref = app.storage.user.get("_email_alerts_cached")
                                    alert_switch = ui.switch(value=bool(alert_pref)).props("dense")

                                    async def _toggle_alerts(e):
                                        await run.io_bound(db.set_email_alerts, auth_user_id, e.value)
                                        app.storage.user["_email_alerts_cached"] = e.value

                                    alert_switch.on_value_change(_toggle_alerts)
                                else:
                                    ui.label("Pro").style(
                                        f"font-size:10px; color:{TEXT_DIM}; background:rgba(255,255,255,0.06);"
                                        f" border-radius:3px; padding:1px 6px;"
                                    )

                        # Manage subscription (Pro with Stripe only)
                        _fresh_user = db.get_user_by_id(auth_user_id) or {}
                        _stripe_cust = _fresh_user.get("stripe_customer_id")
                        if is_pro(auth_user_id) and _stripe_cust:
                            async def _manage_sub():
                                url = await run.io_bound(create_portal_session, _stripe_cust)
                                ui.navigate.to(url, new_tab=False)

                            with ui.menu_item(on_click=_manage_sub).style("padding:10px 14px;"):
                                ui.label("Manage subscription").style(
                                    f"font-size:13px; color:{TEXT_PRIMARY};"
                                )

                        ui.separator().style("margin:4px 14px; opacity:0.15;")

                        # Sign out
                        def _logout():
                            app.storage.user.pop("user_id", None)
                            app.storage.user.pop("encryption_key", None)
                            app.storage.user.pop("auth_email", None)
                            app.storage.user.pop("_email_alerts_cached", None)
                            ui.navigate.to("/")

                        with ui.menu_item(on_click=_logout).style("padding:10px 14px;"):
                            ui.label("Sign out").style(
                                f"font-size:13px; color:{TEXT_PRIMARY};"
                            )
```

- [ ] **Step 5: Add success notification**

Near the top of the index function (after loading portfolio state, around line 300), add a client-side script that detects the `?upgraded=1` query param from Stripe's redirect, cleans the URL, and shows a Quasar notification:

```python
    # Stripe checkout return — detect via URL param, show toast, clean URL
    ui.run_javascript('''
        const params = new URLSearchParams(window.location.search);
        if (params.get("upgraded") === "1") {
            window.history.replaceState({}, "", "/");
            setTimeout(() => {
                Quasar.Notify.create({
                    message: "Welcome to Pro! All features are now unlocked.",
                    color: "positive",
                    timeout: 5000,
                    position: "top"
                });
            }, 1000);
        }
    ''', respond=False)
```

- [ ] **Step 6: Add `/pricing` route**

After the `/reset` route, add:

```python
@ui.page("/pricing")
async def pricing_page():
    """Pricing page — Free vs Pro comparison."""
    user_id = app.storage.user.get("user_id")
    currency = "EUR"
    if user_id:
        stored = load_portfolio()
        currency = stored.get("currency", "EUR")
    build_pricing_page(user_id, currency)
```

- [ ] **Step 7: Add Stripe webhook route**

After the pricing route, add:

```python
@app.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events."""
    import stripe
    from starlette.responses import JSONResponse
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig, webhook_secret)
    except (ValueError, stripe.SignatureVerificationError):
        return JSONResponse({"error": "Invalid signature"}, status_code=400)

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = session.get("client_reference_id")
        customer_id = session.get("customer")
        subscription_id = session.get("subscription")
        if user_id:
            from src.billing import handle_checkout_completed
            await run.io_bound(handle_checkout_completed, user_id, customer_id, subscription_id)

    elif event["type"] == "customer.subscription.deleted":
        customer_id = event["data"]["object"].get("customer")
        if customer_id:
            from src.billing import handle_subscription_deleted
            await run.io_bound(handle_subscription_deleted, customer_id)

    return JSONResponse({"status": "ok"})
```

- [ ] **Step 8: Add `/admin` route**

After the webhook route, add:

```python
@ui.page("/admin")
async def admin_page():
    """Admin dashboard — user management and subscription summary."""
    auth_email = app.storage.user.get("auth_email")
    if not is_admin(auth_email):
        ui.label("Access denied.").style(f"color:{TEXT_MUTED}; padding:40px;")
        return

    users = await run.io_bound(db.get_all_users)

    with ui.column().classes("w-full").style(f"background:{BG_MAIN}; min-height:100vh; padding:24px;"):
        ui.label("Admin Dashboard").style(
            f"font-size:22px; font-weight:700; color:{TEXT_PRIMARY}; margin-bottom:20px;"
        )

        # Summary cards
        total = len(users)
        pro_count = sum(1 for u in users if u.get("tier") == "pro")
        free_count = total - pro_count
        sub_count = sum(1 for u in users if u.get("stripe_subscription_id"))

        with ui.row().classes("gap-4 flex-wrap").style("margin-bottom:24px;"):
            for label, value in [("Total users", total), ("Pro", pro_count), ("Free", free_count), ("Subscriptions", sub_count)]:
                with ui.card().style(
                    f"background:{BG_CARD}; border:1px solid rgba(255,255,255,0.08);"
                    f" border-radius:10px; padding:16px 24px; min-width:120px;"
                ):
                    ui.label(str(value)).style(f"font-size:28px; font-weight:700; color:{TEXT_PRIMARY};")
                    ui.label(label).style(f"font-size:12px; color:{TEXT_DIM};")

        # User table
        columns = [
            {"name": "email", "label": "Email", "field": "email", "align": "left"},
            {"name": "tier", "label": "Tier", "field": "tier", "align": "left"},
            {"name": "created_at", "label": "Signed up", "field": "created_at", "align": "left"},
            {"name": "stripe_customer_id", "label": "Stripe", "field": "stripe_customer_id", "align": "left"},
        ]
        rows = [
            {
                "id": u["id"],
                "email": u["email"],
                "tier": u.get("tier", "free"),
                "created_at": (u.get("created_at") or "")[:10],
                "stripe_customer_id": u.get("stripe_customer_id") or "",
            }
            for u in users
        ]

        table = ui.table(columns=columns, rows=rows, row_key="id").style(
            f"background:{BG_CARD}; border-radius:10px; width:100%;"
        ).props("flat bordered")

        # Tier override
        ui.label("Tier Override").style(
            f"font-size:16px; font-weight:600; color:{TEXT_PRIMARY}; margin-top:24px; margin-bottom:8px;"
        )
        with ui.row().classes("items-end gap-3"):
            email_input = ui.input("User email").props("outlined dense").style("width:250px;")
            tier_select = ui.select(["free", "pro"], value="pro").props("outlined dense").style("width:100px;")

            async def _override_tier():
                target = await run.io_bound(db.get_user_by_email, email_input.value.strip().lower())
                if not target:
                    ui.notify("User not found.", type="warning")
                    return
                await run.io_bound(db.set_tier, target["id"], tier_select.value)
                ui.notify(f"Set {email_input.value} to {tier_select.value}.", type="positive")
                ui.navigate.to("/admin")

            ui.button("Apply", on_click=_override_tier).props("no-caps unelevated").style(
                f"background:{ACCENT}; border-radius:6px;"
            )
```

- [ ] **Step 9: Verify syntax and run tests**

Run: `python3 -c "import ast; ast.parse(open('main.py').read()); print('OK')"`
Run: `pytest -v`

- [ ] **Step 10: Commit**

```bash
git add main.py
git commit -m "feat: feature gates, pricing page, Stripe webhook, admin dashboard"
```

---

## Task 5: Position Limit in Sidebar

**Files:**
- Modify: `src/ui/sidebar.py`

- [ ] **Step 1: Add position limit check**

At the top of `src/ui/sidebar.py`, add import:

```python
from src.billing import is_pro, FREE_POSITION_LIMIT
```

Find the function where a new position is added to the portfolio (the "add" button handler). Before the position is added, insert:

```python
        # Position limit for free users
        user_id = app.storage.user.get("user_id")
        if not is_pro(user_id) and len(portfolio) >= FREE_POSITION_LIMIT:
            ui.notify(
                f"Free plan allows up to {FREE_POSITION_LIMIT} positions. Upgrade to Pro for unlimited.",
                type="warning",
            )
            return
```

This needs to go inside the add-position callback, before the portfolio mutation happens. Read the sidebar code to find the exact insertion point.

- [ ] **Step 2: Run full test suite**

Run: `pytest -v`

- [ ] **Step 3: Commit**

```bash
git add src/ui/sidebar.py
git commit -m "feat: enforce position limit for free users"
```

---

## Task 6: Set TESTING_MODE and Deploy

- [ ] **Step 1: Set testing mode and admin email on Fly**

```bash
fly secrets set TESTING_MODE=true ADMIN_EMAILS=joakim.hersche@gmail.com --app market-dashboard-currency-adjusted
```

- [ ] **Step 2: Run full test suite**

Run: `pytest -v`
Expected: all tests PASS

- [ ] **Step 3: Commit any remaining changes and push**

```bash
git push
```

- [ ] **Step 4: Deploy**

```bash
fly deploy
```

---

## Post-Implementation: Stripe Setup

Before flipping `TESTING_MODE` off, you need to:

1. Create the "Market Dashboard Pro" product in Stripe Dashboard
2. Create 10 prices (monthly + yearly for EUR/CHF/SEK/GBP, lifetime for each)
3. Set `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, and `STRIPE_PRICE_IDS` as Fly secrets
4. Configure the Stripe webhook endpoint URL: `https://market-dashboard-currency-adjusted.fly.dev/stripe/webhook` (or `https://portfoliotracker.app/stripe/webhook` once domain is pointed)
5. Remove `TESTING_MODE` secret to enforce gates
