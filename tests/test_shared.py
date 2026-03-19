"""Tests for encryption round-trip in src.ui.shared."""
import json
import pytest
from src.ui.shared import _fernet


def encrypt_portfolio(data: dict) -> str:
    """Encrypt portfolio data the same way save_portfolio does."""
    plaintext = json.dumps(data, default=str).encode()
    return _fernet.encrypt(plaintext).decode()


def decrypt_portfolio(raw) -> dict:
    """Decrypt portfolio data the same way load_portfolio does."""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        from cryptography.fernet import InvalidToken
        try:
            decrypted = _fernet.decrypt(raw.encode())
            parsed = json.loads(decrypted)
            return parsed if isinstance(parsed, dict) else {}
        except InvalidToken:
            pass
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def test_encrypt_decrypt_round_trip():
    original = {
        "portfolio": {
            "AAPL": [{"shares": 10, "buy_price": 150.0, "purchase_date": "2024-01-15"}],
        },
        "currency": "USD",
    }
    encrypted = encrypt_portfolio(original)
    assert isinstance(encrypted, str)
    assert encrypted != json.dumps(original)

    decrypted = decrypt_portfolio(encrypted)
    assert decrypted == original


def test_unencrypted_dict_passes_through():
    raw = {"portfolio": {"MSFT": [{"shares": 5, "buy_price": 300.0, "purchase_date": "2024-06-01"}]}}
    result = decrypt_portfolio(raw)
    assert result == raw


def test_unencrypted_json_string_passes_through():
    raw_dict = {"portfolio": {"TSLA": [{"shares": 2, "buy_price": 200.0, "purchase_date": "2024-03-01"}]}}
    raw_str = json.dumps(raw_dict)
    result = decrypt_portfolio(raw_str)
    assert result == raw_dict


def test_empty_portfolio_round_trip():
    original = {}
    encrypted = encrypt_portfolio(original)
    decrypted = decrypt_portfolio(encrypted)
    assert decrypted == original
