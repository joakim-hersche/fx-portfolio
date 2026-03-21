# Workstream B2 — Background Alert Emails

**Date:** 2026-03-21
**Goal:** Run daily server-side alert checks and email users when new portfolio warnings are detected — so users don't have to open the dashboard to stay informed.

**Context:** Workstream A added an alert rule engine (`src/alerts.py`) that checks concentration risk and high correlation. Currently, alerts only evaluate when a user opens the Overview tab. Workstream B1 added user accounts, server-side portfolio storage, and Resend email integration. B2 connects these: a background scheduler evaluates alerts for all opted-in users and sends a digest email when something new triggers.

---

## Scope

- Daily background job (07:00 CET) checking alert rules for all opted-in users
- Digest email with new alerts only (skip if nothing changed since last email)
- Opt-in prompt on first login after feature ships (not surprising — user explicitly chooses)
- Account dropdown in top bar with email alert toggle
- Database changes: email_alerts preference and last-sent alert state per user

---

## Background Job

### Scheduler

An asyncio background task started in `_preload()` on app startup. Runs inside the NiceGUI process — no new infrastructure.

**Logic:**
1. Compute seconds until next 07:00 CET, sleep until then
2. On wake: query all users with `email_verified = TRUE` and `email_alerts = TRUE`
3. For each user:
   a. Load and decrypt their portfolio from the database
   b. Compute portfolio weights from current cached prices (use `build_portfolio_df`)
   c. Run `evaluate_all(weights, price_data, settings)` from `src/alerts.py`
   d. Compare resulting `rule_id` set against `last_alert_ids` stored on the user
   e. If new alerts exist (rule_ids not in last set): send digest email, update `last_alert_ids`
   f. If no new alerts: skip, no email
4. After processing all users, sleep until the next 07:00 CET

**Edge cases:**
- App restart: recalculate sleep time from current clock. If 07:00 already passed today, sleep until tomorrow's 07:00.
- User with empty portfolio: skip (no weights to evaluate).
- Price data not cached: call `build_portfolio_df` which fetches prices as needed. This runs on a background thread via `run.io_bound()`, not blocking the UI event loop.
- Resend failure: log the error, don't crash. The user will get the email on the next cycle if the alerts persist.

### New File: `src/alert_job.py`

Responsible for:
- `start_alert_scheduler()` — called from `_preload()`, launches the asyncio task
- `_run_daily_check()` — the loop: sleep until 07:00, process users, repeat
- `_check_user(user_id, encryption_key)` — load portfolio, evaluate alerts, diff, send email if needed
- `_build_alert_email(alerts, email)` — construct the HTML email body

All database and portfolio operations wrapped in `run.io_bound()` to avoid blocking the event loop.

---

## Database Changes

Two new columns on the `users` table:

```sql
ALTER TABLE users ADD COLUMN email_alerts BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN last_alert_ids TEXT DEFAULT '[]';
```

- `email_alerts`: whether the user has opted in to daily alert emails
- `last_alert_ids`: JSON array of `rule_id` strings from the last email sent (e.g., `["concentration_AAPL", "correlation_MSFT_GOOGL"]`). Used to diff against current alerts — only new ones trigger an email.

**SQLite equivalent:** `email_alerts INTEGER DEFAULT 0`, `last_alert_ids TEXT DEFAULT '[]'`.

**Migration:** Add columns via `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` in `init_schema()`. Safe to run repeatedly.

### New DB Functions

- `db.get_alerted_users() -> list[dict]` — returns all users with `email_verified = TRUE` and `email_alerts = TRUE`
- `db.set_email_alerts(user_id, enabled: bool)` — toggle the preference
- `db.get_email_alerts(user_id) -> bool` — read the preference
- `db.update_last_alert_ids(user_id, rule_ids: list[str])` — persist the last-sent set

---

## Email Format

### Subject Line

- Multiple alerts: `"Portfolio Alert: 2 new warnings"`
- Single alert: `"Portfolio Alert: AAPL concentration at 47%"` (use the alert title directly)

### HTML Body

```
Market Dashboard — Portfolio Alerts

{count} new alert(s) detected for your portfolio:

[CRITICAL — Concentration Risk]
AAPL is 47% of your portfolio (threshold: 30%)

[WARNING — High Correlation]
MSFT and GOOGL have 91% correlation (threshold: 85%)

---
Manage alert settings in your dashboard: {APP_URL}
You're receiving this because you enabled email alerts.
```

- Alert cards colored by severity: critical = red (#EF4444), warning = amber (#F59E0B)
- Simple HTML — no images, no complex layout. Must render in all email clients.
- Footer with dashboard link and explanation of why they're receiving the email.

### Sending

Via Resend, same pattern as `_send_verify_email` in `src/ui/auth.py`. The `FROM_EMAIL` and `RESEND_API_KEY` env vars are already configured.

---

## UI Changes

### Account Dropdown (Top Bar)

Replace the current email label + "Sign out" button (added in B1) with a dropdown menu:

```
[user@email.com ▾]
  ├── Email alerts: [toggle]
  └── Sign out
```

- Toggle is a switch/checkbox showing current `email_alerts` state
- Toggling calls `db.set_email_alerts(user_id, value)` via `run.io_bound()`
- Styled consistently with the existing export dropdown in the top bar

### Opt-In Prompt

On page load, if:
- User is logged in AND verified
- User's `email_alerts` is `NULL` (never been asked — distinguish from explicitly set to `FALSE`)

Show a one-time dialog:

```
Stay on top of your portfolio

We can email you when we detect concentration risk or high
correlation in your holdings. One email per day, only when
something changes.

[Enable alerts]  [No thanks]
```

- "Enable alerts" → `set_email_alerts(user_id, True)`
- "No thanks" → `set_email_alerts(user_id, False)`
- Either choice dismisses the dialog permanently (the column is no longer `NULL`)

**Implementation note:** To distinguish "never asked" from "explicitly disabled", use `NULL` as the default for `email_alerts` instead of `FALSE`. The schema becomes `email_alerts BOOLEAN DEFAULT NULL` (Postgres) / `email_alerts INTEGER DEFAULT NULL` (SQLite). The background job queries `WHERE email_alerts = TRUE`, so `NULL` users are excluded.

---

## File Changes Summary

| File | Change |
|------|--------|
| `src/alert_job.py` | **New** — scheduler, per-user check, email builder |
| `src/db.py` | Modify — add email_alerts/last_alert_ids columns, new query functions |
| `main.py` | Modify — start scheduler in _preload(), account dropdown, opt-in prompt |
| `tests/test_alert_job.py` | **New** — scheduler logic, diff logic, email construction tests |
| `tests/test_db.py` | Modify — tests for new columns and query functions |

**Unchanged:** `src/alerts.py`, `src/ui/alerts.py`, `src/auth.py`, `src/ui/auth.py`, `src/ui/shared.py`, all tab UI modules.

---

## What This Does NOT Include

- No new alert rule types (uses existing concentration + correlation from Workstream A)
- No per-rule email opt-in (all or nothing toggle)
- No real-time/intraday alerts (daily at 07:00 CET only)
- No in-app notification center (alerts still show on Overview tab as before)
- No email frequency configuration (daily is fixed)
