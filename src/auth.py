"""Authentication logic — registration, login, verification, password reset.

No UI concerns. All blocking; callers wrap in run.io_bound().
"""
from __future__ import annotations

import base64
import datetime
import logging
import os
import secrets
import time
from typing import Any

import bcrypt
from cryptography.fernet import Fernet

from src import db
from src.security_logger import (
    log_security_event, LOGIN_SUCCESS, LOGIN_FAILURE,
    PASSWORD_RESET_REQ, PASSWORD_RESET_DONE, RATE_LIMIT_HIT,
)

_log = logging.getLogger(__name__)


class ValidationError(Exception):
    pass


class AuthError(Exception):
    pass


class RateLimitError(Exception):
    pass


# ── Rate limiting (Redis with in-memory fallback) ────────

_redis_client = None

def _get_redis():
    """Lazy-init Redis. Falls back to in-memory if unavailable."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    redis_url = os.environ.get("REDIS_URL")
    if redis_url:
        try:
            import redis
            _redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
            _redis_client.ping()
            _log.info("Rate limiter using Redis")
            return _redis_client
        except Exception:
            _log.warning("Redis unavailable — falling back to in-memory rate limiter")
    _redis_client = False  # sentinel: don't retry
    return None

# In-memory fallback (used when Redis is not available)
_rate_limits: dict[str, list[float]] = {}

_RATE_WINDOWS = {
    "login": (5, 900),       # 5 attempts per 15 min
    "verify": (5, 900),      # 5 attempts per 15 min
    "reset": (3, 3600),      # 3 per hour
    "promo": (5, 3600),      # 5 promo attempts per hour
}


def _check_rate(action: str, key: str) -> None:
    """Raise RateLimitError if too many attempts. Uses Redis when available."""
    max_attempts, window = _RATE_WINDOWS[action]
    rate_key = f"rl:{action}:{key}"

    r = _get_redis()
    if r:
        # Redis sliding window: INCR + EXPIRE
        count = r.incr(rate_key)
        if count == 1:
            r.expire(rate_key, window)
        if count > max_attempts:
            log_security_event(RATE_LIMIT_HIT, "HIGH", details={"action": action, "key": key})
            raise RateLimitError("Too many attempts — try again later.")
        return

    # In-memory fallback
    now = time.monotonic()
    attempts = _rate_limits.get(rate_key, [])
    attempts = [t for t in attempts if now - t < window]
    if len(attempts) >= max_attempts:
        log_security_event(RATE_LIMIT_HIT, "HIGH", details={"action": action, "key": key})
        raise RateLimitError("Too many attempts — try again later.")
    attempts.append(now)
    _rate_limits[rate_key] = attempts


def _clear_rate(action: str, key: str) -> None:
    """Clear rate-limit counter on successful action."""
    rate_key = f"rl:{action}:{key}"
    r = _get_redis()
    if r:
        r.delete(rate_key)
    else:
        _rate_limits.pop(rate_key, None)


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
        log_security_event(LOGIN_FAILURE, "MEDIUM", details={"email": email, "reason": "unknown_email"})
        raise AuthError("Invalid email or password.")

    if not bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
        log_security_event(LOGIN_FAILURE, "HIGH", user_id=user["id"], details={"email": email, "reason": "bad_password"})
        raise AuthError("Invalid email or password.")

    # Clear rate limit on successful login
    _clear_rate("login", email)

    log_security_event(LOGIN_SUCCESS, "LOW", user_id=user["id"], details={"email": email})

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
    _clear_rate("verify", user_id)
    return True


def generate_new_verify_code(user_id: str) -> str:
    """Generate and store a fresh 6-digit code. Returns the code."""
    code = f"{secrets.randbelow(1_000_000):06d}"
    db.set_verify_code(user_id, code, minutes=15)
    _clear_rate("verify", user_id)
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

    # Invalidate any existing reset tokens for this user
    db.delete_password_resets_for_user(user["id"])

    raw_token = secrets.token_urlsafe(32)
    token_hash = bcrypt.hashpw(raw_token.encode(), bcrypt.gensalt()).decode()
    # Store a fast-lookup prefix (first 8 chars of raw token) to avoid O(n) scan
    token_prefix = raw_token[:8]
    db.create_password_reset(user["id"], token_hash, minutes=60, token_prefix=token_prefix)

    log_security_event(PASSWORD_RESET_REQ, "MEDIUM", user_id=user["id"], details={"email": email})
    return raw_token


def complete_password_reset(token: str, new_password: str) -> None:
    """Validate a reset token and update the password.

    Raises AuthError if token invalid/expired, ValidationError if password too short.
    """
    if len(new_password) < 8:
        raise ValidationError("Password must be at least 8 characters.")

    # Use token prefix for fast lookup, then bcrypt verify for security
    token_prefix = token[:8]
    now = datetime.datetime.now(datetime.timezone.utc)

    candidates = db.find_resets_by_prefix(token_prefix)
    for table_row in candidates:
        expires = datetime.datetime.fromisoformat(str(table_row["expires_at"]))
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=datetime.timezone.utc)
        if now > expires:
            continue
        if bcrypt.checkpw(token.encode(), table_row["token_hash"].encode()):
            new_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
            db.update_password_hash(table_row["user_id"], new_hash)
            db.delete_password_reset(table_row["id"])
            log_security_event(PASSWORD_RESET_DONE, "MEDIUM", user_id=table_row["user_id"])
            return

    raise AuthError("Invalid or expired reset link.")


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
