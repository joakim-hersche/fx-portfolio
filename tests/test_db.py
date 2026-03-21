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
