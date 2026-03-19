"""Shared UI utilities used across tab modules."""

from __future__ import annotations

import base64
import json
import logging as _logging
import os
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from nicegui import app, ui

_log = _logging.getLogger(__name__)

# Type alias for the shared state dict passed to all tab builders
SharedState = dict[str, Any]

# ── Storage key (matches the Streamlit version's localStorage key) ──
_LS_KEY = "market_dashboard_portfolio"

# ── Encryption for at-rest portfolio data ─────────────────
_STORAGE_SECRET = os.environ.get("STORAGE_SECRET", "market-dashboard-dev-fallback")
if _STORAGE_SECRET == "market-dashboard-dev-fallback":
    _log.warning("Using deterministic fallback encryption secret. Set STORAGE_SECRET env var for production.")
    if os.environ.get("HOST", "127.0.0.1") == "0.0.0.0":
        raise RuntimeError("STORAGE_SECRET must be set in production")
_kdf = PBKDF2HMAC(
    algorithm=hashes.SHA256(),
    length=32,
    salt=b"market-dashboard-portfolio-salt",
    iterations=480_000,
)
_fernet = Fernet(base64.urlsafe_b64encode(_kdf.derive(_STORAGE_SECRET.encode())))


def get_storage_secret() -> str:
    """Return the storage secret for NiceGUI's storage_secret parameter."""
    return _STORAGE_SECRET


def load_portfolio() -> dict:
    """Load and decrypt portfolio from user storage."""
    raw = app.storage.user.get(_LS_KEY, {})
    # Already a dict — unencrypted legacy data; will be encrypted on next save
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        # Try decrypting first (encrypted data is a Fernet token string)
        try:
            decrypted = _fernet.decrypt(raw.encode())
            parsed = json.loads(decrypted)
            return parsed if isinstance(parsed, dict) else {}
        except InvalidToken:
            pass
        # Fallback: legacy unencrypted JSON string
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def save_portfolio(data: dict) -> None:
    """Encrypt and persist portfolio to user storage."""
    plaintext = json.dumps(data, default=str).encode()
    app.storage.user[_LS_KEY] = _fernet.encrypt(plaintext).decode()
