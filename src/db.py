"""Database abstraction — Postgres (production) or SQLite (local dev).

Uses psycopg (sync) for Postgres, sqlite3 for SQLite.
All blocking calls should be wrapped in run.io_bound() by callers.
"""
from __future__ import annotations

import datetime
import os
import sqlite3
import threading
import uuid
from typing import Any

_conn: sqlite3.Connection | Any = None
_backend: str = "sqlite"  # "sqlite" or "postgres"
_lock = threading.Lock()


class DuplicateEmailError(Exception):
    pass


# ── Connection management ────────────────────────────────


def _init_connection(path: str | None = None) -> None:
    """Initialise the database connection. Called once at app startup."""
    global _conn, _backend
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        import psycopg
        _conn = psycopg.connect(database_url)
        _backend = "postgres"
    else:
        db_path = path or os.environ.get("SQLITE_PATH", "data/dev.db")
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        _conn = sqlite3.connect(db_path, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _backend = "sqlite"


def _close_connection() -> None:
    global _conn
    if _conn:
        _conn.close()
        _conn = None


def _execute(sql: str, params: tuple = ()) -> Any:
    """Execute a query and return the cursor."""
    with _lock:
        cur = _conn.cursor()
        cur.execute(sql, params)
        _conn.commit()
        return cur


def _fetchone(sql: str, params: tuple = ()) -> dict | None:
    with _lock:
        cur = _conn.cursor()
        cur.execute(sql, params)
        row = cur.fetchone()
        if row is None:
            return None
        if _backend == "sqlite":
            return dict(row)
        # psycopg returns tuples; use description for column names
        cols = [d.name for d in cur.description]
        return dict(zip(cols, row))


def _fetchall(sql: str, params: tuple = ()) -> list[dict]:
    with _lock:
        cur = _conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        if _backend == "sqlite":
            return [dict(r) for r in rows]
        cols = [d.name for d in cur.description]
        return [dict(zip(cols, row)) for row in rows]


def _table_names() -> list[str]:
    if _backend == "sqlite":
        rows = _fetchall("SELECT name FROM sqlite_master WHERE type='table'")
        return [r["name"] for r in rows]
    rows = _fetchall(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
    )
    return [r["tablename"] for r in rows]


def _p(n: int) -> tuple[str, ...]:
    """Return n placeholders for the current backend."""
    ph = "%s" if _backend == "postgres" else "?"
    return tuple(ph for _ in range(n))


# ── Schema ────────────────────────────────────────────────


def init_schema() -> None:
    """Create tables if they don't exist."""
    if _backend == "postgres":
        _execute("""
            CREATE TABLE IF NOT EXISTS users (
                id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                email           TEXT UNIQUE NOT NULL,
                password_hash   TEXT NOT NULL,
                encryption_key  BYTEA NOT NULL,
                email_verified  BOOLEAN DEFAULT FALSE,
                verify_code     TEXT,
                verify_expires  TIMESTAMP,
                created_at      TIMESTAMP DEFAULT now()
            )
        """)
        _execute("""
            CREATE TABLE IF NOT EXISTS portfolios (
                id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id     UUID REFERENCES users(id) ON DELETE CASCADE,
                data        BYTEA NOT NULL,
                updated_at  TIMESTAMP DEFAULT now(),
                UNIQUE(user_id)
            )
        """)
        _execute("""
            CREATE TABLE IF NOT EXISTS password_resets (
                id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id     UUID REFERENCES users(id) ON DELETE CASCADE,
                token_hash  TEXT NOT NULL,
                expires_at  TIMESTAMP NOT NULL
            )
        """)
    else:
        _execute("""
            CREATE TABLE IF NOT EXISTS users (
                id              TEXT PRIMARY KEY,
                email           TEXT UNIQUE NOT NULL,
                password_hash   TEXT NOT NULL,
                encryption_key  BLOB NOT NULL,
                email_verified  INTEGER DEFAULT 0,
                verify_code     TEXT,
                verify_expires  TEXT,
                created_at      TEXT
            )
        """)
        _execute("""
            CREATE TABLE IF NOT EXISTS portfolios (
                id          TEXT PRIMARY KEY,
                user_id     TEXT REFERENCES users(id) ON DELETE CASCADE,
                data        BLOB NOT NULL,
                updated_at  TEXT,
                UNIQUE(user_id)
            )
        """)
        _execute("""
            CREATE TABLE IF NOT EXISTS password_resets (
                id          TEXT PRIMARY KEY,
                user_id     TEXT REFERENCES users(id) ON DELETE CASCADE,
                token_hash  TEXT NOT NULL,
                expires_at  TEXT NOT NULL
            )
        """)

    # ── Migrations (safe to re-run) ───────────────────────
    # B2: email alert preferences
    try:
        _execute("ALTER TABLE users ADD COLUMN email_alerts %s DEFAULT NULL" %
                 ("BOOLEAN" if _backend == "postgres" else "INTEGER"))
    except Exception:
        pass  # Column already exists
    try:
        _execute("ALTER TABLE users ADD COLUMN last_alert_ids TEXT DEFAULT '[]'")
    except Exception:
        pass  # Column already exists


# ── User queries ──────────────────────────────────────────


def create_user(email: str, password_hash: str, encryption_key: bytes) -> str:
    """Insert a new user. Returns user ID. Raises DuplicateEmailError."""
    user_id = str(uuid.uuid4())
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    ph = _p(5)
    try:
        _execute(
            f"INSERT INTO users (id, email, password_hash, encryption_key, created_at)"
            f" VALUES ({', '.join(ph)})",
            (user_id, email, password_hash, encryption_key, now),
        )
    except Exception as e:
        err = str(e).lower()
        if "unique" in err or "duplicate" in err:
            raise DuplicateEmailError(f"Email already registered: {email}")
        raise
    return user_id


def get_user_by_email(email: str) -> dict | None:
    ph = _p(1)[0]
    row = _fetchone(f"SELECT * FROM users WHERE email = {ph}", (email,))
    if row and _backend == "sqlite":
        row["email_verified"] = bool(row["email_verified"])
    return row


def get_user_by_id(user_id: str) -> dict | None:
    ph = _p(1)[0]
    row = _fetchone(f"SELECT * FROM users WHERE id = {ph}", (user_id,))
    if row and _backend == "sqlite":
        row["email_verified"] = bool(row["email_verified"])
    return row


def set_verify_code(user_id: str, code: str, minutes: int) -> None:
    expires = (
        datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(minutes=minutes)
    ).isoformat()
    ph = _p(3)
    _execute(
        f"UPDATE users SET verify_code = {ph[0]}, verify_expires = {ph[1]} WHERE id = {ph[2]}",
        (code, expires, user_id),
    )


def mark_email_verified(user_id: str) -> None:
    ph = _p(2)
    verified_val = True if _backend == "postgres" else 1
    _execute(
        f"UPDATE users SET email_verified = {ph[0]}, verify_code = NULL WHERE id = {ph[1]}",
        (verified_val, user_id),
    )


def update_password_hash(user_id: str, new_hash: str) -> None:
    ph = _p(2)
    _execute(
        f"UPDATE users SET password_hash = {ph[0]} WHERE id = {ph[1]}",
        (new_hash, user_id),
    )


# ── Email alert queries ───────────────────────────────────


def get_email_alerts(user_id: str) -> bool | None:
    """Return the user's email_alerts preference (True/False/None)."""
    ph = _p(1)[0]
    row = _fetchone(f"SELECT email_alerts FROM users WHERE id = {ph}", (user_id,))
    if not row:
        return None
    val = row["email_alerts"]
    if val is None:
        return None
    if _backend == "sqlite":
        return bool(val)
    return val


def set_email_alerts(user_id: str, enabled: bool) -> None:
    """Set the user's email alert preference."""
    ph = _p(2)
    val = enabled if _backend == "postgres" else int(enabled)
    _execute(
        f"UPDATE users SET email_alerts = {ph[0]} WHERE id = {ph[1]}",
        (val, user_id),
    )


def get_alerted_users() -> list[dict]:
    """Return all verified users who have opted in to email alerts."""
    if _backend == "postgres":
        return _fetchall(
            "SELECT * FROM users WHERE email_verified = TRUE AND email_alerts = TRUE"
        )
    return _fetchall(
        "SELECT * FROM users WHERE email_verified = 1 AND email_alerts = 1"
    )


def update_last_alert_ids(user_id: str, rule_ids: list[str]) -> None:
    """Persist the rule_id list from the last alert email sent."""
    import json
    ph = _p(2)
    _execute(
        f"UPDATE users SET last_alert_ids = {ph[0]} WHERE id = {ph[1]}",
        (json.dumps(rule_ids), user_id),
    )


# ── Portfolio queries ─────────────────────────────────────


def get_portfolio(user_id: str) -> dict | None:
    ph = _p(1)[0]
    return _fetchone(f"SELECT * FROM portfolios WHERE user_id = {ph}", (user_id,))


def upsert_portfolio(user_id: str, data: bytes) -> None:
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    port_id = str(uuid.uuid4())
    ph = _p(4)
    if _backend == "sqlite":
        _execute(
            f"INSERT OR REPLACE INTO portfolios (id, user_id, data, updated_at) VALUES ({', '.join(ph)})",
            (port_id, user_id, data, now),
        )
    else:
        _execute(
            f"INSERT INTO portfolios (id, user_id, data, updated_at) VALUES ({', '.join(ph)})"
            " ON CONFLICT (user_id) DO UPDATE SET data = EXCLUDED.data, updated_at = EXCLUDED.updated_at",
            (port_id, user_id, data, now),
        )


# ── Password reset queries ───────────────────────────────


def create_password_reset(user_id: str, token_hash: str, minutes: int) -> None:
    reset_id = str(uuid.uuid4())
    expires = (
        datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(minutes=minutes)
    ).isoformat()
    ph = _p(4)
    _execute(
        f"INSERT INTO password_resets (id, user_id, token_hash, expires_at) VALUES ({', '.join(ph)})",
        (reset_id, user_id, token_hash, expires),
    )


def get_password_resets(user_id: str) -> list[dict]:
    ph = _p(1)[0]
    return _fetchall(
        f"SELECT * FROM password_resets WHERE user_id = {ph}", (user_id,)
    )


def delete_password_reset(reset_id: str) -> None:
    ph = _p(1)[0]
    _execute(f"DELETE FROM password_resets WHERE id = {ph}", (reset_id,))
