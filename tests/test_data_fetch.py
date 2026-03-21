"""Tests for data_fetch functions."""
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from src.cache import short_cache, long_cache_fundamentals
from src.data_fetch import fetch_fundamentals, fetch_ticker_news, fetch_sector_peers


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear caches before each test."""
    long_cache_fundamentals.clear()
    short_cache.clear()


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
def test_fundamentals_gbx_target_price_returned_in_trading_currency(mock_ticker):
    """Target price is returned in trading currency (pence for GBX).
    Callers handle GBX->GBP conversion via get_fx_rate('GBX', ...) which divides by 100.
    """
    mock_ticker.return_value.info = _mock_info({"targetMeanPrice": 15000.0})
    result = fetch_fundamentals("SHEL.L")
    assert result["Target Price"] == 15000.0  # raw pence, caller converts


# ── fetch_ticker_news tests ──


@patch("src.data_fetch.yf.Ticker")
def test_fetch_ticker_news_returns_list(mock_ticker):
    mock_ticker.return_value.news = [
        {"title": "Stock rises", "publisher": "Reuters", "link": "https://example.com", "providerPublishTime": 1700000000},
        {"title": "Earnings beat", "publisher": "Bloomberg", "link": "https://example.com/2", "providerPublishTime": 1700001000},
    ]
    result = fetch_ticker_news("AAPL")
    assert len(result) == 2
    assert result[0]["title"] == "Stock rises"
    assert result[0]["publisher"] == "Reuters"
    assert "link" in result[0]
    assert "providerPublishTime" in result[0]


@patch("src.data_fetch.yf.Ticker")
def test_fetch_ticker_news_handles_failure(mock_ticker):
    mock_ticker.return_value.news = property(lambda self: (_ for _ in ()).throw(Exception("fail")))
    mock_ticker.side_effect = Exception("network error")
    result = fetch_ticker_news("BAD")
    assert result == []


# ── fetch_sector_peers tests ──


@patch("src.data_fetch.yf.Ticker")
def test_fetch_sector_peers_returns_peer_data(mock_ticker):
    mock_info = {
        "sector": "Technology",
        "shortName": "Microsoft Corp",
        "trailingPE": 35.0,
        "dividendYield": 0.008,
        "beta": 0.9,
    }
    hist_df = pd.DataFrame({"Close": [100.0, 110.0]})
    mock_instance = MagicMock()
    mock_instance.info = mock_info
    mock_instance.history.return_value = hist_df
    mock_ticker.return_value = mock_instance

    result = fetch_sector_peers("Technology", ("MSFT", "GOOGL"), "AAPL")
    assert len(result) >= 1
    peer = result[0]
    assert peer["ticker"] == "MSFT"
    assert peer["name"] == "Microsoft Corp"
    assert peer["pe"] == 35.0
    assert peer["div_yield"] == 0.80
    assert peer["beta"] == 0.9
    assert peer["return_1y"] == 10.0
