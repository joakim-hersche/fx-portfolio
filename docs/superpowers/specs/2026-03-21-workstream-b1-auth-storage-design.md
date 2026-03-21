# Workstream B1 — Auth + Server Storage

**Date:** 2026-03-21
**Goal:** Add email/password authentication, email verification, and encrypted server-side portfolio storage to enable cross-device sync for paying users — while preserving the zero-friction anonymous experience for free users.

**Context:** The dashboard currently stores all data in the browser via NiceGUI's `app.storage.user` with Fernet encryption. This works for single-device use but blocks cross-device sync, email alerts, and any server-side feature gating. Workstream B1 adds the server infrastructure; Workstream B2 (separate spec) adds background alert jobs and email notifications on top.

---

## Scope

- Fly.io infrastructure: always-on machine, Postgres
- Database schema: users, portfolios, password resets
- Email/password registration with email verification (6-digit code via Resend)
- Login, logout, password reset flow
- Portfolio sync: anonymous users stay local-only, logged-in users read/write Postgres
- Local portfolio migration on first login
- SQLite fallback for local development

---

## Infrastructure

### Fly.io Changes

**`fly.toml` updates:**
- `min_machines_running = 1` (always-on, ~$5/month)
- Attach Fly Postgres (free tier: 1 shared CPU, 256MB RAM, 1GB storage)

**Environment variables to add:**
- `DATABASE_URL` — Postgres connection string (auto-set by Fly Postgres attachment)
- `MASTER_KEY` — 32-byte hex string used to wrap per-user encryption keys at rest (see Security section)
- `RESEND_API_KEY` — Resend email service API key
- `FROM_EMAIL` — sender address for verification/reset emails (e.g., noreply@yourdomain.com)

### Database Schema

Three tables. All IDs are UUIDs.

```sql
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           TEXT UNIQUE NOT NULL,
    password_hash   TEXT NOT NULL,
    encryption_key  BYTEA NOT NULL,
    email_verified  BOOLEAN DEFAULT FALSE,
    verify_code     TEXT,
    verify_expires  TIMESTAMP,
    created_at      TIMESTAMP DEFAULT now()
);

CREATE TABLE portfolios (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    data            BYTEA NOT NULL,
    updated_at      TIMESTAMP DEFAULT now(),
    UNIQUE(user_id)
);

CREATE TABLE password_resets (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    token_hash      TEXT NOT NULL,
    expires_at      TIMESTAMP NOT NULL
);
```

**Notes:**
- `users.encryption_key`: random 32-byte key, wrapped (encrypted) with the server-side `MASTER_KEY` before storage. On read, unwrap with `MASTER_KEY` to get the raw key for Fernet operations. A database dump alone cannot decrypt portfolio data without `MASTER_KEY`.
- `users.password_hash`: bcrypt hash.
- `portfolios.data`: encrypted JSON blob (Fernet, using the unwrapped per-user key). Same structure as current localStorage data. One row per user.
- `password_resets.token_hash`: bcrypt hash of the reset token (not stored plaintext).

### SQLite Compatibility

The Postgres schema above uses Postgres-specific syntax. For SQLite (local dev):
- UUIDs generated in Python (`uuid.uuid4()`) and stored as `TEXT`
- `BYTEA` becomes `BLOB`
- `gen_random_uuid()` and `now()` replaced by Python-side defaults
- `src/db.py` handles these differences internally

### Local Development

`DATABASE_URL` env var controls the database backend:
- **Set (Postgres URL):** connect to Postgres (production, Fly.io)
- **Unset:** use SQLite file at `data/dev.db`

**New file: `src/db.py`** — database connection and queries. Abstracts Postgres vs SQLite behind a common interface. Uses `psycopg` (sync mode, wrapped in `run.io_bound()` to avoid blocking the event loop — consistent with existing codebase pattern) for Postgres, `sqlite3` for SQLite.

### Schema Migrations

v1: `CREATE TABLE IF NOT EXISTS` on app startup in `src/db.py`. No migration tool. Sufficient until the schema changes, at which point Alembic or manual migration scripts can be added.

---

## Authentication

### New Files

- `src/auth.py` — registration, login, verification, password reset logic (no UI)
- `src/ui/auth.py` — login/register/verify/reset UI pages

### Registration Flow

1. User clicks "Sign in" button in the top bar
2. Shows login form with "Create account" link
3. User enters email + password (minimum 8 characters)
4. On submit:
   - Hash password with bcrypt
   - Generate random 32-byte encryption key
   - Generate 6-digit verification code (valid 15 minutes)
   - Create user row with `email_verified = FALSE`
   - Send verification email via Resend (code, not link — user stays in same tab)
5. Show "Enter the code we sent to your email" screen
6. On correct code: set `email_verified = TRUE`, migrate local portfolio to server, redirect to dashboard
7. On wrong code: allow retry. On expiry: "Resend code" button generates a new code.

### Login Flow

1. User enters email + password
2. Verify password against bcrypt hash
3. Check `email_verified = TRUE`. If not verified, show verification screen again (resend code option).
4. On success: set `user_id` in `app.storage.user`, load portfolio from Postgres, decrypt with user's encryption key, populate `app.storage.user` with portfolio data.
5. Session persists via NiceGUI's storage (browser session-scoped).

### Logout

Clear `user_id` from `app.storage.user`. Portfolio data stays in browser storage as a local cache (same as anonymous mode). Next page load behaves as anonymous.

### Password Reset Flow

1. "Forgot password" link on login form
2. User enters email
3. Generate reset token (random 32 bytes), hash with bcrypt, store in `password_resets` table (valid 1 hour)
4. Send reset email via Resend with a link containing the raw token
5. User clicks link, enters new password
6. Verify token against stored hash, update `password_hash` in users table
7. Delete used reset token
8. Portfolio data unaffected — encryption key doesn't change

### Unverified Users

Users with `email_verified = FALSE` can:
- Log in and use the dashboard in local-only mode (same as anonymous)
- See a banner: "Verify your email to enable sync"
- Cannot save to server until verified

This preserves the low-friction experience. No blocking.

### Rate Limiting

- **Login:** max 5 failed attempts per email per 15-minute window. After 5 failures, reject with "Too many attempts — try again in 15 minutes."
- **Verification code:** max 5 attempts per code. After 5 wrong entries, invalidate the code and require "Resend code."
- **Password reset requests:** max 3 per email per hour.

Rate limiting tracked in-memory (dict keyed by email + timestamp). No database table needed at this scale — resets on app restart, which is acceptable.

### Session Security

- Sessions are scoped to NiceGUI's `app.storage.user`, which is keyed by a browser cookie signed with `STORAGE_SECRET`. Cookie tampering (e.g., setting `user_id` manually) is prevented by the server-side signature.
- The user's unwrapped `encryption_key` is held in `app.storage.user` during the session (server-side, not browser-accessible — NiceGUI stores this server-side and only sends a session ID cookie to the browser).
- Sessions expire after 30 days of inactivity. On expiry, the user must log in again.
- On logout, `user_id` and `encryption_key` are cleared from server-side session. Local portfolio cache (encrypted with the existing local Fernet key) remains in the browser.

---

## Portfolio Sync

### Routing Logic

`load_portfolio()` and `save_portfolio()` in `src/ui/shared.py` are the only functions that touch portfolio data. All UI modules already call them. The change is internal routing:

**Anonymous user** (no `user_id` in `app.storage.user`):
- Current behavior unchanged. Read/write `app.storage.user[_LS_KEY]`. No server calls.

**Logged-in, verified user** (`user_id` present):
- `load_portfolio()`: query `portfolios` table for `user_id`, decrypt with user's `encryption_key`, return dict. Cache in `app.storage.user` for the session.
- `save_portfolio()`: encrypt dict with user's `encryption_key`, upsert into `portfolios` table. Also update `app.storage.user` cache.

### No Real-Time Sync

If the same user is logged in on two devices simultaneously, last-write-wins based on `updated_at` timestamp. No conflict resolution — overengineering at this scale. Each page load fetches the latest from Postgres.

### Local → Server Migration

On first login or registration, if:
- `app.storage.user` has a local portfolio (the `_LS_KEY` key exists and is non-empty), AND
- The server has no portfolio row for this user

Then: upload the local data to the server (encrypt with user's key, insert into `portfolios`).

If both local and server portfolios exist (edge case — user registered, then used a different browser):
- Show a one-time prompt: "Keep server version or replace with this browser's data?"
- User chooses. No automatic merge.

### Alert State

The `_alerts` key (from Workstream A) is nested inside the portfolio dict. It migrates to the server along with everything else. No separate handling needed.

### Non-Synced Data

`recent_searches` in `src/ui/research.py` writes directly to `app.storage.user` outside of `load_portfolio`/`save_portfolio`. This is intentionally local-only — search history is device-specific and not worth syncing.

---

## UI Changes

### Top Bar

Add a "Sign in" button (text, not icon) to the right side of the top bar, next to the currency selector. When logged in, replace with the user's email and a "Sign out" button.

### Auth Pages

Simple, dark-themed forms matching the dashboard aesthetic. Not full pages — render inside the main content area (same place tabs render). Four states:

1. **Login form:** email, password, "Sign in" button, "Create account" link, "Forgot password" link
2. **Register form:** email, password, "Create account" button, "Already have an account" link
3. **Verify form:** "Enter the 6-digit code" input, "Resend code" button
4. **Reset form:** email input (request step), then new password input (set step)

No separate routes except for password reset: a `/reset?token=xxx` route is needed so the email link has somewhere to land. This is the one URL-routed page in the app.

---

## Dependencies

**New Python packages:**
- `psycopg[binary]` — Postgres driver (sync mode, wrapped in `run.io_bound()`)
- No SQLite package needed — Python's built-in `sqlite3` module is sufficient
- `bcrypt` — password hashing
- `resend` — email API client

**External services:**
- Fly Postgres (free tier)
- Resend (free tier, 3,000 emails/month)

---

## What This Does NOT Include

- Feature gating / tier enforcement (Workstream C)
- Stripe billing (Workstream C)
- Background alert jobs / email notifications (Workstream B2)
- OAuth / social login (future, if needed)
- Multi-portfolio support (future)
- Email change flow (future — low priority at launch)

---

## File Changes Summary

| File | Change |
|------|--------|
| `src/db.py` | **New** — database connection, user/portfolio/reset queries |
| `src/auth.py` | **New** — registration, login, verification, reset logic |
| `src/ui/auth.py` | **New** — login/register/verify/reset UI components |
| `src/ui/shared.py` | Modify — route load/save through Postgres for logged-in users |
| `main.py` | Modify — add Sign in/out button to top bar, auth state handling |
| `fly.toml` | Modify — min_machines_running, Postgres attachment |
| `requirements.txt` | Modify — add psycopg, aiosqlite, bcrypt, resend |

**Unchanged:** All tab UI modules, `src/providers.py`, `src/data_fetch.py`, `src/alerts.py`, `src/fx.py`, `src/cache.py`, `src/theme.py`
