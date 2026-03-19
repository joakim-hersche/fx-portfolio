"""Tests for data_fetch.fetch_fundamentals()."""
import pytest
from unittest.mock import patch, MagicMock
from src.cache import long_cache_fundamentals
from src.data_fetch import fetch_fundamentals


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear the fundamentals cache before each test."""
    long_cache_fundamentals.clear()


def _mock_info(overrides=None):
    """Return a realistic yfinance .info dict."""
    base = {
        "trailingPE": 28.5,
        "dividendRate": 0.96,
        "dividendYield": 0.005,
        "fiftyTwoWeekLow": 142.0,
        "fiftyTwoWeekHigh": 198.5,
        "currentPrice": 176.0,
        "sector": "Technology",
        "targetMeanPrice": 195.0,
    }
    if overrides:
        base.update(overrides)
    return base


@patch("src.data_fetch.yf.Ticker")
def test_fundamentals_returns_sector(mock_ticker):
    mock_ticker.return_value.info = _mock_info()
    result = fetch_fundamentals("AAPL")
    assert result["Sector"] == "Technology"


@patch("src.data_fetch.yf.Ticker")
def test_fundamentals_returns_target_price(mock_ticker):
    mock_ticker.return_value.info = _mock_info()
    result = fetch_fundamentals("AAPL")
    assert result["Target Price"] == 195.0


@patch("src.data_fetch.yf.Ticker")
def test_fundamentals_returns_dividend_rate(mock_ticker):
    mock_ticker.return_value.info = _mock_info()
    result = fetch_fundamentals("AAPL")
    assert result["Dividend Rate"] == 0.96


@patch("src.data_fetch.yf.Ticker")
def test_fundamentals_missing_sector_defaults_to_unknown(mock_ticker):
    mock_ticker.return_value.info = _mock_info({"sector": None})
    result = fetch_fundamentals("SPY")
    assert result["Sector"] == "Unknown"


@patch("src.data_fetch.yf.Ticker")
def test_fundamentals_missing_target_price_returns_none(mock_ticker):
    mock_ticker.return_value.info = _mock_info({"targetMeanPrice": None})
    result = fetch_fundamentals("BTC-USD")
    assert result["Target Price"] is None


@patch("src.data_fetch.yf.Ticker")
def test_fundamentals_gbx_target_price_divided_by_100(mock_ticker):
    mock_ticker.return_value.info = _mock_info({"targetMeanPrice": 15000.0})
    result = fetch_fundamentals("SHEL.L")
    assert result["Target Price"] == 150.0  # 15000 / 100
