"""Tests for src.auth — registration, login, verification, rate limiting."""
import os
import pytest
import time

os.environ.pop("DATABASE_URL", None)

from src import db
from src import auth


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("SQLITE_PATH", db_path)
    monkeypatch.setenv("MASTER_KEY", "ab" * 32)  # 64 hex chars = 32 bytes
    monkeypatch.setenv("RESEND_API_KEY", "re_test_fake")
    monkeypatch.setenv("FROM_EMAIL", "test@example.com")
    db._init_connection(db_path)
    db.init_schema()
    auth._rate_limits.clear()
    yield
    db._close_connection()


# ── Registration ──


def test_register_creates_user():
    user_id, code = auth.register("new@example.com", "password123")
    assert user_id is not None
    assert len(code) == 6 and code.isdigit()
    user = db.get_user_by_email("new@example.com")
    assert user is not None
    assert user["email_verified"] is False


def test_register_duplicate_email():
    auth.register("dup@example.com", "password123")
    with pytest.raises(db.DuplicateEmailError):
        auth.register("dup@example.com", "otherpass")


def test_register_short_password():
    with pytest.raises(auth.ValidationError, match="8 characters"):
        auth.register("short@example.com", "1234567")


# ── Login ──


def test_login_success():
    user_id, _ = auth.register("login@example.com", "password123")
    db.mark_email_verified(user_id)
    result = auth.login("login@example.com", "password123")
    assert result["user_id"] == user_id
    assert result["verified"] is True
    assert "encryption_key" in result


def test_login_wrong_password():
    auth.register("wrong@example.com", "password123")
    with pytest.raises(auth.AuthError, match="Invalid"):
        auth.login("wrong@example.com", "wrongpass")


def test_login_unknown_email():
    with pytest.raises(auth.AuthError, match="Invalid"):
        auth.login("ghost@example.com", "anything")


def test_login_unverified_returns_unverified():
    auth.register("unv@example.com", "password123")
    result = auth.login("unv@example.com", "password123")
    assert result["verified"] is False


# ── Verification ──


def test_verify_correct_code():
    user_id, code = auth.register("ver@example.com", "password123")
    assert auth.verify_email(user_id, code) is True
    user = db.get_user_by_id(user_id)
    assert user["email_verified"] is True


def test_verify_wrong_code():
    user_id, _ = auth.register("ver2@example.com", "password123")
    assert auth.verify_email(user_id, "000000") is False


# ── Rate limiting ──


def test_login_rate_limit():
    auth.register("rate@example.com", "password123")
    for _ in range(5):
        try:
            auth.login("rate@example.com", "wrongpass")
        except auth.AuthError:
            pass
    with pytest.raises(auth.RateLimitError):
        auth.login("rate@example.com", "wrongpass")


# ── Password reset ──


def test_create_and_use_password_reset():
    user_id, _ = auth.register("reset@example.com", "oldpass123")
    token = auth.create_password_reset("reset@example.com")
    assert token is not None

    auth.complete_password_reset(token, "newpass123")
    result = auth.login("reset@example.com", "newpass123")
    assert result["user_id"] == user_id


def test_password_reset_unknown_email():
    # Should not raise — don't reveal whether email exists
    token = auth.create_password_reset("nobody@example.com")
    assert token is None


# ── Encryption key wrapping ──


def test_encryption_key_wrapped_at_rest():
    """The raw encryption key stored in DB should not match the unwrapped key."""
    user_id, _ = auth.register("wrap@example.com", "password123")
    user = db.get_user_by_id(user_id)
    stored_key = user["encryption_key"]
    # Login returns unwrapped key
    db.mark_email_verified(user_id)
    result = auth.login("wrap@example.com", "password123")
    unwrapped = result["encryption_key"]
    assert stored_key != unwrapped  # wrapped != raw
