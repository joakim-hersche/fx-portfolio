"""Security Event Logging — structured audit trail for security-sensitive events.

JSON-formatted logs with rotation. All security events (auth, billing,
rate-limiting, admin actions) flow through log_security_event().
"""
from __future__ import annotations

import json
import logging
import logging.handlers
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Log directory ─────────────────────────────────────────
_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
_LOG_DIR.mkdir(exist_ok=True)

# ── JSON formatter ────────────────────────────────────────

class _JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
        }
        if hasattr(record, "event_data"):
            payload.update(record.event_data)
        else:
            payload["message"] = record.getMessage()
        return json.dumps(payload, default=str)


# ── Logger setup ──────────────────────────────────────────

def _build_logger() -> logging.Logger:
    logger = logging.getLogger("security_audit")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    handler = logging.handlers.RotatingFileHandler(
        _LOG_DIR / "security.log",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=10,
    )
    handler.setFormatter(_JSONFormatter())
    logger.addHandler(handler)
    return logger


_logger = _build_logger()

# ── Event types ───────────────────────────────────────────

LOGIN_SUCCESS          = "login_success"
LOGIN_FAILURE          = "login_failure"
PASSWORD_RESET_REQ     = "password_reset_requested"
PASSWORD_RESET_DONE    = "password_reset_completed"
SUBSCRIPTION_CHANGED   = "subscription_changed"
PAYMENT_FAILED         = "payment_failed"
ADMIN_ACTION           = "admin_action"
RATE_LIMIT_HIT         = "rate_limit_exceeded"
UNAUTHORIZED_ACCESS    = "unauthorized_access"
PROMO_CODE_ATTEMPT     = "promo_code_attempt"

# ── Public API ────────────────────────────────────────────

def log_security_event(
    event_type: str,
    severity: str = "MEDIUM",
    *,
    user_id: str | None = None,
    ip_address: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Emit a structured security log entry."""
    record = logging.LogRecord(
        name="security_audit",
        level=logging.WARNING if severity in ("CRITICAL", "HIGH") else logging.INFO,
        pathname="",
        lineno=0,
        msg="",
        args=(),
        exc_info=None,
    )
    record.event_data = {
        "event_type": event_type,
        "severity": severity,
        "user_id": user_id,
        "ip_address": ip_address,
        "details": details or {},
    }
    _logger.handle(record)
