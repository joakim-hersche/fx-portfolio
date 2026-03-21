"""Tests for src.db — uses SQLite backend (no DATABASE_URL set)."""
import os
import pytest
import uuid

# Ensure SQLite backend
os.environ.pop("DATABASE_URL", None)

from src import db


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    """Point db at a temporary SQLite file for each test."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("SQLITE_PATH", db_path)
    monkeypatch.setenv("MASTER_KEY", "a" * 64)  # 32-byte hex
    db._init_connection(db_path)
    db.init_schema()
    yield
    db._close_connection()


def test_init_schema_creates_tables():
    """Tables exist after init_schema."""
    tables = db._table_names()
    assert "users" in tables
    assert "portfolios" in tables
    assert "password_resets" in tables


def test_create_user_and_get_by_email():
    user_id = db.create_user("test@example.com", "hashed_pw", b"enc_key_bytes")
    assert user_id is not None
    user = db.get_user_by_email("test@example.com")
    assert user is not None
    assert user["email"] == "test@example.com"
    assert user["email_verified"] is False


def test_get_user_by_email_not_found():
    assert db.get_user_by_email("nobody@example.com") is None


def test_duplicate_email_raises():
    db.create_user("dup@example.com", "hash1", b"key1")
    with pytest.raises(db.DuplicateEmailError):
        db.create_user("dup@example.com", "hash2", b"key2")


def test_set_verify_code_and_verify_email():
    user_id = db.create_user("v@example.com", "hash", b"key")
    db.set_verify_code(user_id, "123456", minutes=15)
    user = db.get_user_by_id(user_id)
    assert user["verify_code"] == "123456"
    assert user["email_verified"] is False

    db.mark_email_verified(user_id)
    user = db.get_user_by_id(user_id)
    assert user["email_verified"] is True
    assert user["verify_code"] is None


def test_upsert_and_get_portfolio():
    user_id = db.create_user("p@example.com", "hash", b"key")
    assert db.get_portfolio(user_id) is None

    db.upsert_portfolio(user_id, b"encrypted_blob_1")
    row = db.get_portfolio(user_id)
    assert row["data"] == b"encrypted_blob_1"

    db.upsert_portfolio(user_id, b"encrypted_blob_2")
    row = db.get_portfolio(user_id)
    assert row["data"] == b"encrypted_blob_2"


def test_create_and_get_password_reset():
    user_id = db.create_user("r@example.com", "hash", b"key")
    db.create_password_reset(user_id, "token_hash_abc", minutes=60)
    resets = db.get_password_resets(user_id)
    assert len(resets) >= 1
    assert resets[0]["token_hash"] == "token_hash_abc"


def test_delete_password_reset():
    user_id = db.create_user("d@example.com", "hash", b"key")
    db.create_password_reset(user_id, "tok_hash", minutes=60)
    resets = db.get_password_resets(user_id)
    db.delete_password_reset(resets[0]["id"])
    assert db.get_password_resets(user_id) == []


def test_update_password_hash():
    user_id = db.create_user("pw@example.com", "old_hash", b"key")
    db.update_password_hash(user_id, "new_hash")
    user = db.get_user_by_id(user_id)
    assert user["password_hash"] == "new_hash"


# ── Email alert preference queries ──


def test_email_alerts_default_is_none():
    """New users have email_alerts = None (never asked)."""
    user_id = db.create_user("alerts@example.com", "hash", b"key")
    user = db.get_user_by_id(user_id)
    assert user["email_alerts"] is None


def test_set_and_get_email_alerts():
    user_id = db.create_user("toggle@example.com", "hash", b"key")
    db.set_email_alerts(user_id, True)
    assert db.get_email_alerts(user_id) is True
    db.set_email_alerts(user_id, False)
    assert db.get_email_alerts(user_id) is False


def test_get_alerted_users():
    """Only verified users with email_alerts=True are returned."""
    u1 = db.create_user("on@example.com", "hash", b"key")
    db.mark_email_verified(u1)
    db.set_email_alerts(u1, True)

    u2 = db.create_user("off@example.com", "hash", b"key")
    db.mark_email_verified(u2)
    db.set_email_alerts(u2, False)

    u3 = db.create_user("unverified@example.com", "hash", b"key")
    db.set_email_alerts(u3, True)  # verified=False, should be excluded

    u4 = db.create_user("null@example.com", "hash", b"key")
    db.mark_email_verified(u4)
    # email_alerts is None — should be excluded

    users = db.get_alerted_users()
    ids = [u["id"] for u in users]
    assert u1 in ids
    assert u2 not in ids
    assert u3 not in ids
    assert u4 not in ids


def test_update_last_alert_ids():
    user_id = db.create_user("last@example.com", "hash", b"key")
    db.update_last_alert_ids(user_id, ["concentration_AAPL", "correlation_MSFT_GOOGL"])
    user = db.get_user_by_id(user_id)
    import json
    assert json.loads(user["last_alert_ids"]) == ["concentration_AAPL", "correlation_MSFT_GOOGL"]


def test_last_alert_ids_default_empty():
    user_id = db.create_user("empty_alerts@example.com", "hash", b"key")
    user = db.get_user_by_id(user_id)
    import json
    assert json.loads(user["last_alert_ids"]) == []
