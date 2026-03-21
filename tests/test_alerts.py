"""Tests for in-app alert rules."""
import pytest
import numpy as np
import pandas as pd
from src.alerts import Alert, check_concentration, check_correlation, evaluate_all


def test_concentration_triggers_when_above_threshold():
    weights = {"AAPL": 0.45, "MSFT": 0.30, "GOOGL": 0.25}
    alerts = check_concentration(weights, threshold=0.30)
    assert len(alerts) >= 1
    assert alerts[0].severity == "critical"
    assert "AAPL" in alerts[0].message


def test_concentration_no_alert_when_below_threshold():
    weights = {"AAPL": 0.25, "MSFT": 0.25, "GOOGL": 0.25, "AMZN": 0.25}
    alerts = check_concentration(weights, threshold=0.30)
    assert len(alerts) == 0


def test_correlation_triggers_when_above_threshold():
    dates = pd.date_range("2025-01-01", periods=252, freq="B")
    np.random.seed(42)
    base = np.cumsum(np.random.randn(252)) + 100
    price_data = {
        "AAPL": pd.DataFrame({"Close": base}, index=dates),
        "MSFT": pd.DataFrame({"Close": base * 1.1 + np.random.randn(252) * 0.5}, index=dates),
    }
    alerts = check_correlation(price_data, threshold=0.80)
    assert len(alerts) >= 1
    assert alerts[0].severity == "warning"


def test_correlation_no_alert_when_below_threshold():
    dates = pd.date_range("2025-01-01", periods=252, freq="B")
    np.random.seed(42)
    price_data = {
        "AAPL": pd.DataFrame({"Close": np.cumsum(np.random.randn(252)) + 100}, index=dates),
        "GLD": pd.DataFrame({"Close": np.cumsum(np.random.randn(252)) + 50}, index=dates),
    }
    alerts = check_correlation(price_data, threshold=0.95)
    assert len(alerts) == 0


def test_correlation_skips_with_insufficient_data():
    alerts = check_correlation({}, threshold=0.85)
    assert len(alerts) == 0


def test_alert_dataclass_fields():
    a = Alert(severity="warning", title="Test", message="msg", rule_id="test_rule")
    assert a.severity == "warning"
    assert a.rule_id == "test_rule"


def test_evaluate_all_combines_rules():
    weights = {"AAPL": 0.50, "MSFT": 0.50}
    alerts = evaluate_all(weights, price_data=None)
    # Should get concentration alert for AAPL (50% > 30% default)
    assert any("AAPL" in a.message for a in alerts)
