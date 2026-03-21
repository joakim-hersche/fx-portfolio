# Workstream C — Monetisation

**Date:** 2026-03-21
**Goal:** Add Stripe billing, feature gating, and an admin dashboard — with a testing mode that keeps everything unlocked until ready to charge.

**Context:** Workstreams A (product quality), B1 (auth + server storage), and B2 (background alerts) are shipped and deployed. The dashboard has user accounts, encrypted portfolio storage, and email notifications. This workstream adds the revenue layer: a Pro tier with feature gates, Stripe checkout, and an admin dashboard for user management.

---

## Scope

- Two tiers: Free (default) and Pro
- Feature gates on Forecast, Income, Excel export, email alerts, and position count
- Stripe Checkout for Pro subscriptions (monthly, yearly, lifetime)
- Multi-currency pricing: EUR, CHF, SEK, GBP
- Locked tab overlay with upgrade CTA (blurred preview)
- Standalone pricing page (`/pricing`)
- Stripe webhook for subscription lifecycle events
- Admin dashboard (`/admin`) with user list, tier override, subscription summary
- Testing mode: `TESTING_MODE=true` env var bypasses all gates

---

## Tiers and Pricing

### Feature Matrix

| Feature | Free | Pro |
|---------|------|-----|
| Positions | 10 max | Unlimited |
| Overview tab | Yes | Yes |
| Positions tab | Yes | Yes |
| Portfolio Health tab | Yes | Yes |
| Research tab | Yes | Yes |
| Guide tab | Yes | Yes |
| Forecast (Monte Carlo) | Locked | Yes |
| Income tab | Locked | Yes |
| Excel export | Locked | Yes |
| Email alerts (B2) | Locked | Yes |

### Pricing

| Plan | EUR | CHF | SEK | GBP |
|------|-----|-----|-----|-----|
| Monthly | 8 | 8 | 89 | 7 |
| Yearly | 79 | 79 | 879 | 69 |
| Lifetime | 149 | 149 | 1649 | 129 |

- Monthly and yearly are recurring Stripe subscriptions.
- Lifetime is a one-time Stripe payment. User gets permanent Pro access.
- Currency is determined by the user's selected dashboard currency. If their currency isn't in the table (e.g., USD), default to EUR.

---

## Feature Gates

### Gate Check Logic

A single function `is_pro(user_id) -> bool` determines access:

1. If `TESTING_MODE=true` env var is set: return `True` for all users (bypass all gates).
2. If user is not logged in: return `False`.
3. If user's `tier` column is `"pro"`: return `True`.
4. Otherwise: return `False`.

All gate checks go through this one function. No scattered tier checks.

### Position Limit

In `src/ui/sidebar.py`, when adding a new position:
- Count existing tickers in portfolio.
- If `>= 10` and `not is_pro(user_id)`: show notification "Free plan allows up to 10 positions. Upgrade to Pro for unlimited." and block the add.

### Locked Tabs

Forecast and Income tabs remain visible in the tab bar. When a free user clicks them:
- The tab panel renders a blurred overlay instead of the actual content.
- Overlay contains: lock icon, "Upgrade to Pro" heading, 1-line feature description, price, and a "View plans" button linking to `/pricing`.
- No computation runs behind the blur — the tab builder is not called.

### Excel Export

In the export dropdown, the Excel option shows a lock icon for free users. Clicking it shows a notification: "Excel export is a Pro feature" with a link to `/pricing`.

### Email Alerts

In the account dropdown, the email alerts toggle is visible but disabled for free users, with a label "Pro feature" next to it. The opt-in prompt (from B2) only shows for Pro users.

In the background job (`src/alert_job.py`), `get_alerted_users()` already filters by `email_alerts = TRUE`. Free users can't enable alerts, so they're naturally excluded.

---

## Stripe Integration

### Setup

**Stripe products to create (via Stripe Dashboard or API):**
- One product: "Market Dashboard Pro"
- Six prices: monthly and yearly for each of EUR, CHF, SEK, GBP (recurring)
- Four prices: lifetime for each currency (one-time)
- Total: 10 Stripe prices

**Environment variables:**
- `STRIPE_SECRET_KEY` — Stripe secret key
- `STRIPE_WEBHOOK_SECRET` — webhook signing secret
- `STRIPE_PRICE_IDS` — JSON mapping of `{currency}_{interval}` to Stripe price ID, e.g.:
  ```json
  {
    "eur_monthly": "price_xxx",
    "eur_yearly": "price_yyy",
    "eur_lifetime": "price_zzz",
    "chf_monthly": "price_aaa",
    ...
  }
  ```

### Checkout Flow

1. User clicks "View plans" on locked overlay or visits `/pricing`.
2. User selects monthly / yearly / lifetime.
3. App creates a Stripe Checkout Session:
   - `customer_email` = user's email
   - `client_reference_id` = user's ID
   - `price` = price ID for user's currency + selected interval
   - `mode` = `"subscription"` for monthly/yearly, `"payment"` for lifetime
   - `success_url` = `{APP_URL}/?upgraded=1`
   - `cancel_url` = `{APP_URL}/pricing`
4. User is redirected to Stripe Checkout.
5. On success: Stripe sends webhook, app updates user tier.

### Webhook Handler

**Route:** `POST /stripe/webhook`

**Events to handle:**

- `checkout.session.completed`:
  - Extract `client_reference_id` (user ID) and `customer` (Stripe customer ID).
  - Set `tier = "pro"` and `stripe_customer_id` on user row.
  - For subscriptions: also store `stripe_subscription_id`.

- `customer.subscription.deleted`:
  - Look up user by `stripe_customer_id`.
  - Set `tier = "free"`.
  - Clear `stripe_subscription_id`.

- `invoice.payment_failed`:
  - Log warning. Don't downgrade immediately — Stripe retries.

**Webhook verification:** Verify signature using `STRIPE_WEBHOOK_SECRET` via `stripe.Webhook.construct_event()`.

### New Dependencies

- `stripe` Python package

---

## Database Changes

Three new columns on the `users` table:

```sql
ALTER TABLE users ADD COLUMN tier TEXT DEFAULT 'free';
ALTER TABLE users ADD COLUMN stripe_customer_id TEXT;
ALTER TABLE users ADD COLUMN stripe_subscription_id TEXT;
```

- `tier`: `"free"` or `"pro"`. Default `"free"`.
- `stripe_customer_id`: Stripe customer ID, set on first checkout.
- `stripe_subscription_id`: Stripe subscription ID for monthly/yearly. `NULL` for lifetime.

**New DB functions:**
- `db.set_tier(user_id, tier)` — update tier
- `db.get_user_by_stripe_customer(customer_id) -> dict | None` — lookup for webhooks
- `db.set_stripe_ids(user_id, customer_id, subscription_id)` — store Stripe references

---

## UI

### Locked Tab Overlay (`src/ui/paywall.py`)

Reusable component rendered inside the tab panel for gated tabs:

```
┌─────────────────────────────────────┐
│                                     │
│     (blurred placeholder area)      │
│                                     │
│          🔒 Upgrade to Pro          │
│                                     │
│   Run Monte Carlo simulations to    │
│   project future portfolio value    │
│                                     │
│        From €8/month                │
│                                     │
│        [ View plans ]               │
│                                     │
└─────────────────────────────────────┘
```

Each locked tab has its own description:
- Forecast: "Run Monte Carlo simulations to project future portfolio value"
- Income: "Track dividend income and yield across your portfolio"

### Pricing Page (`/pricing`)

Standalone page at `/pricing` route. Dark-themed, matching dashboard aesthetic.

**Layout:**
- Hero: "Market Dashboard Pro" heading
- Toggle: Monthly / Yearly / Lifetime selector
- Two cards side by side: Free vs Pro
- Free card: feature list with checkmarks and crosses
- Pro card: feature list with all checkmarks, price, "Get started" button
- Price updates based on user's dashboard currency and selected interval

**"Get started" button:** Creates Stripe Checkout session and redirects.

**For logged-in Pro users:** Show "You're on Pro" instead of checkout button.

**For anonymous users:** "Sign in to upgrade" button, links to sign-in flow.

### Account Dropdown Changes

Add tier badge next to email in the dropdown trigger button:
- Free users: small "Free" label
- Pro users: small "Pro" label (styled in accent color)

### Success State

When user returns from Stripe checkout to `/?upgraded=1`:
- Show a one-time notification: "Welcome to Pro! All features are now unlocked."
- Query param consumed on load, not persisted.

---

## Admin Dashboard

### Access Control

Protected by `ADMIN_EMAILS` env var (comma-separated list of email addresses). Any logged-in user whose email matches gets access. Others get a 403.

### Route: `/admin`

No link in the main navigation — admins access by URL directly.

### User List

Table with columns:
- Email
- Tier (free/pro)
- Signup date
- Last active (from `updated_at` on portfolios table, or "Never" if no portfolio)
- Stripe customer ID (linked to Stripe dashboard if present)
- Actions: tier override dropdown (free/pro)

**Tier override:** Dropdown in each row. Changing it calls `db.set_tier()` directly, bypassing Stripe. For manual upgrades (e.g., comp accounts) or emergency downgrades.

### Subscription Summary

Top of the admin page:
- Total users
- Pro users (count)
- Free users (count)
- Active subscriptions (count of users with non-null `stripe_subscription_id`)

No revenue numbers — use Stripe Dashboard for that.

---

## Testing Mode

`TESTING_MODE=true` env var (set as a Fly secret).

**Effect:** `is_pro()` always returns `True`. Every user behaves as Pro:
- All tabs accessible
- No position limit
- Excel export works
- Email alerts available
- Pricing page still visible (for testing the checkout flow)
- Stripe checkout still works (for testing the payment flow)

**When ready to charge:** Remove `TESTING_MODE` secret from Fly. Gates enforce immediately.

---

## File Changes Summary

| File | Change |
|------|--------|
| `src/billing.py` | **New** — `is_pro()`, Stripe checkout session creation, webhook handler, tier management |
| `src/ui/paywall.py` | **New** — locked tab overlay component, pricing page |
| `src/db.py` | Modify — tier/stripe columns migration, new query functions |
| `main.py` | Modify — gate checks in tab builder, pricing route, webhook route, admin route, position limit, export gate |
| `src/alert_job.py` | Modify — skip free users in `_run_all_checks` (or rely on existing email_alerts gate) |
| `src/ui/sidebar.py` | Modify — position limit check on add |
| `requirements.txt` | Modify — add `stripe` |
| `tests/test_billing.py` | **New** — is_pro, tier management, webhook handling tests |
| `tests/test_db.py` | Modify — tests for new columns |

**Unchanged:** `src/alerts.py`, `src/auth.py`, `src/ui/auth.py`, `src/ui/shared.py`, `src/ui/overview.py`, `src/ui/positions.py`, `src/ui/health.py`, `src/ui/research.py`, `src/ui/guide.py`

---

## What This Does NOT Include

- Payment refund handling (use Stripe Dashboard)
- Promo codes / coupons (add via Stripe Dashboard directly — Checkout supports them natively)
- Usage-based billing
- Team/org accounts
- Free trial period (not needed — free tier is the trial)
- In-app billing management (plan changes, cancellation — use Stripe Customer Portal)
