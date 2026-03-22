"""Authentication logic — registration, login, verification, password reset.

No UI concerns. All blocking; callers wrap in run.io_bound().
"""
from __future__ import annotations

import base64
import datetime
import os
import secrets
import time
from typing import Any

import bcrypt
from cryptography.fernet import Fernet

from src import db


class ValidationError(Exception):
    pass


class AuthError(Exception):
    pass


class RateLimitError(Exception):
    pass


# ── Rate limiting (in-memory) ────────────────────────────

# In-memory only — resets on restart, not shared across processes.
# Sufficient for single-process NiceGUI; would need Redis for multi-instance.
_rate_limits: dict[str, list[float]] = {}

_RATE_WINDOWS = {
    "login": (5, 900),       # 5 attempts per 15 min
    "verify": (5, 900),      # 5 attempts per 15 min
    "reset": (3, 3600),      # 3 per hour
}


def _check_rate(action: str, key: str) -> None:
    """Raise RateLimitError if too many attempts."""
    max_attempts, window = _RATE_WINDOWS[action]
    rate_key = f"{action}:{key}"
    now = time.monotonic()
    attempts = _rate_limits.get(rate_key, [])
    # Prune old attempts
    attempts = [t for t in attempts if now - t < window]
    if len(attempts) >= max_attempts:
        raise RateLimitError("Too many attempts — try again later.")
    attempts.append(now)
    _rate_limits[rate_key] = attempts


# ── Key wrapping ──────────────────────────────────────────


def _get_master_key() -> bytes:
    """Return the 32-byte master key from env."""
    hex_key = os.environ.get("MASTER_KEY", "")
    if len(hex_key) != 64:
        raise RuntimeError("MASTER_KEY must be a 64-char hex string (32 bytes)")
    return bytes.fromhex(hex_key)


def _wrap_key(raw_key: bytes) -> bytes:
    """Encrypt a raw 32-byte key with the master key using Fernet."""
    master = _get_master_key()
    f = Fernet(base64.urlsafe_b64encode(master))
    return f.encrypt(raw_key)


def _unwrap_key(wrapped: bytes) -> bytes:
    """Decrypt a wrapped key back to the raw 32-byte key."""
    master = _get_master_key()
    f = Fernet(base64.urlsafe_b64encode(master))
    return f.decrypt(wrapped)


# ── Registration ──────────────────────────────────────────


def register(email: str, password: str) -> tuple[str, str]:
    """Register a new user. Returns (user_id, verify_code).

    Raises ValidationError for invalid input, DuplicateEmailError if taken.
    """
    email = email.strip().lower()
    if len(password) < 8:
        raise ValidationError("Password must be at least 8 characters.")

    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    raw_key = secrets.token_bytes(32)
    wrapped_key = _wrap_key(raw_key)

    user_id = db.create_user(email, pw_hash, wrapped_key)

    code = f"{secrets.randbelow(1_000_000):06d}"
    db.set_verify_code(user_id, code, minutes=15)

    return user_id, code


# ── Login ─────────────────────────────────────────────────


def login(email: str, password: str) -> dict[str, Any]:
    """Authenticate a user. Returns dict with user_id, verified, encryption_key.

    Raises AuthError on bad credentials, RateLimitError on too many attempts.
    """
    email = email.strip().lower()
    _check_rate("login", email)

    user = db.get_user_by_email(email)
    if not user:
        raise AuthError("Invalid email or password.")

    if not bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
        raise AuthError("Invalid email or password.")

    # Clear rate limit on successful login
    _rate_limits.pop(f"login:{email}", None)

    encryption_key = _unwrap_key(
        user["encryption_key"]
        if isinstance(user["encryption_key"], bytes)
        else user["encryption_key"].encode()
    )

    return {
        "user_id": user["id"],
        "email": user["email"],
        "verified": user["email_verified"],
        "encryption_key": encryption_key,
    }


# ── Email verification ───────────────────────────────────


def verify_email(user_id: str, code: str) -> bool:
    """Check the verification code. Returns True on success."""
    _check_rate("verify", user_id)

    user = db.get_user_by_id(user_id)
    if not user or user["verify_code"] != code:
        return False

    # Check expiry
    if user["verify_expires"]:
        expires = datetime.datetime.fromisoformat(str(user["verify_expires"]))
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=datetime.timezone.utc)
        if datetime.datetime.now(datetime.timezone.utc) > expires:
            return False

    db.mark_email_verified(user_id)
    _rate_limits.pop(f"verify:{user_id}", None)
    return True


def generate_new_verify_code(user_id: str) -> str:
    """Generate and store a fresh 6-digit code. Returns the code."""
    code = f"{secrets.randbelow(1_000_000):06d}"
    db.set_verify_code(user_id, code, minutes=15)
    _rate_limits.pop(f"verify:{user_id}", None)
    return code


# ── Password reset ────────────────────────────────────────


def create_password_reset(email: str) -> str | None:
    """Create a password reset token. Returns raw token, or None if email unknown.

    Callers should not reveal whether the email exists — always show
    "If that email is registered, we sent a reset link."
    """
    email = email.strip().lower()
    _check_rate("reset", email)

    user = db.get_user_by_email(email)
    if not user:
        return None

    raw_token = secrets.token_urlsafe(32)
    token_hash = bcrypt.hashpw(raw_token.encode(), bcrypt.gensalt()).decode()
    db.create_password_reset(user["id"], token_hash, minutes=60)
    return raw_token


def complete_password_reset(token: str, new_password: str) -> None:
    """Validate a reset token and update the password.

    Raises AuthError if token invalid/expired, ValidationError if password too short.
    """
    if len(new_password) < 8:
        raise ValidationError("Password must be at least 8 characters.")

    # Scan all non-expired resets (brute-force safe: bcrypt comparison is slow)
    # This is fine at low scale; at high scale you'd index by a token prefix.
    now = datetime.datetime.now(datetime.timezone.utc)
    for table_row in _all_active_resets():
        expires = datetime.datetime.fromisoformat(str(table_row["expires_at"]))
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=datetime.timezone.utc)
        if now > expires:
            continue
        if bcrypt.checkpw(token.encode(), table_row["token_hash"].encode()):
            new_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
            db.update_password_hash(table_row["user_id"], new_hash)
            db.delete_password_reset(table_row["id"])
            return

    raise AuthError("Invalid or expired reset link.")


def _all_active_resets() -> list[dict]:
    """Return all non-expired password_reset rows."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    ph = db._p(1)[0]
    return db._fetchall(
        f"SELECT * FROM password_resets WHERE expires_at > {ph}", (now,)
    )


# ── Persistent auth tokens ──────────────────────────────

import hashlib


def _hash_token(raw_token: str) -> str:
    """SHA-256 hash a high-entropy token (no need for bcrypt here)."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


def create_auth_token(user_id: str) -> str:
    """Generate a persistent auth token, store its hash in the DB.

    Returns the raw token (to be set as a browser cookie).
    """
    raw_token = secrets.token_urlsafe(32)
    db.create_auth_token(user_id, _hash_token(raw_token))
    return raw_token


def validate_auth_token(raw_token: str) -> dict | None:
    """Validate a raw auth token. Returns user dict if valid, else None."""
    token_row = db.find_auth_token_by_hash(_hash_token(raw_token))
    if not token_row:
        return None
    user = db.get_user_by_id(token_row["user_id"])
    if not user:
        db.delete_auth_token(token_row["id"])
        return None
    return user


def delete_user_auth_tokens(user_id: str) -> None:
    """Delete all auth tokens for a user (logout)."""
    db.delete_auth_tokens(user_id)
