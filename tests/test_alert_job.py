"""Tests for src.alert_job — per-user check logic and email construction."""
import json
import os
import pytest
from unittest.mock import patch, MagicMock

os.environ.pop("DATABASE_URL", None)

from src import db, auth
from src.alert_job import check_user_alerts, build_alert_email, compute_new_alerts


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("SQLITE_PATH", db_path)
    monkeypatch.setenv("MASTER_KEY", "ab" * 32)
    db._init_connection(db_path)
    db.init_schema()
    auth._rate_limits.clear()
    yield
    db._close_connection()


def _create_opted_in_user(email="test@example.com"):
    """Helper: register, verify, opt in, return (user_id, encryption_key)."""
    user_id, _ = auth.register(email, "password123")
    db.mark_email_verified(user_id)
    db.set_email_alerts(user_id, True)
    result = auth.login(email, "password123")
    return user_id, result["encryption_key"]


# ── compute_new_alerts ──


def test_compute_new_alerts_all_new():
    current = ["concentration_AAPL", "correlation_MSFT_GOOGL"]
    last_sent = []
    new = compute_new_alerts(current, last_sent)
    assert set(new) == {"concentration_AAPL", "correlation_MSFT_GOOGL"}


def test_compute_new_alerts_some_new():
    current = ["concentration_AAPL", "correlation_MSFT_GOOGL"]
    last_sent = ["concentration_AAPL"]
    new = compute_new_alerts(current, last_sent)
    assert new == ["correlation_MSFT_GOOGL"]


def test_compute_new_alerts_none_new():
    current = ["concentration_AAPL"]
    last_sent = ["concentration_AAPL", "correlation_MSFT_GOOGL"]
    new = compute_new_alerts(current, last_sent)
    assert new == []


# ── build_alert_email ──


def test_build_alert_email_single():
    from src.alerts import Alert
    alerts = [Alert("critical", "Concentration risk", "AAPL is 47%", "concentration_AAPL")]
    subject, html = build_alert_email(alerts)
    assert "AAPL" in subject
    assert "47%" in html
    assert "critical" in html.lower() or "EF4444" in html


def test_build_alert_email_multiple():
    from src.alerts import Alert
    alerts = [
        Alert("critical", "Concentration risk", "AAPL is 47%", "concentration_AAPL"),
        Alert("warning", "High correlation", "MSFT and GOOGL 91%", "correlation_MSFT_GOOGL"),
    ]
    subject, html = build_alert_email(alerts)
    assert "2" in subject
    assert "AAPL" in html
    assert "MSFT" in html


# ── check_user_alerts (integration) ──


@patch("src.alert_job.build_portfolio_df")
@patch("src.alert_job._send_alert_email")
def test_check_user_alerts_sends_on_new(mock_send, mock_build_df):
    """When new alerts are detected, email is sent and last_alert_ids updated."""
    import pandas as pd
    user_id, enc_key = _create_opted_in_user()

    from src.ui.shared import _server_save
    portfolio_data = {"portfolio": {"AAPL": [{"shares": 100, "buy_price": 150.0, "purchase_date": "2024-01-01"}]}}
    _server_save(portfolio_data, enc_key, user_id)

    mock_df = pd.DataFrame({"Ticker": ["AAPL"], "Total Value": [15000.0]})
    mock_build_df.return_value = mock_df

    check_user_alerts(user_id, enc_key)

    mock_send.assert_called_once()
    user = db.get_user_by_id(user_id)
    stored_ids = json.loads(user["last_alert_ids"])
    assert "concentration_AAPL" in stored_ids


@patch("src.alert_job.build_portfolio_df")
@patch("src.alert_job._send_alert_email")
def test_check_user_alerts_skips_when_no_new(mock_send, mock_build_df):
    """When all alerts were already sent, no email is sent."""
    import pandas as pd
    user_id, enc_key = _create_opted_in_user("skip@example.com")

    from src.ui.shared import _server_save
    portfolio_data = {"portfolio": {"AAPL": [{"shares": 100, "buy_price": 150.0, "purchase_date": "2024-01-01"}]}}
    _server_save(portfolio_data, enc_key, user_id)

    db.update_last_alert_ids(user_id, ["concentration_AAPL"])

    mock_df = pd.DataFrame({"Ticker": ["AAPL"], "Total Value": [15000.0]})
    mock_build_df.return_value = mock_df

    check_user_alerts(user_id, enc_key)

    mock_send.assert_not_called()


@patch("src.alert_job.build_portfolio_df")
@patch("src.alert_job._send_alert_email")
def test_check_user_alerts_skips_empty_portfolio(mock_send, mock_build_df):
    """Users with empty portfolios get no email."""
    user_id, enc_key = _create_opted_in_user("empty@example.com")

    from src.ui.shared import _server_save
    _server_save({"portfolio": {}}, enc_key, user_id)

    import pandas as pd
    mock_build_df.return_value = pd.DataFrame()

    check_user_alerts(user_id, enc_key)

    mock_send.assert_not_called()
