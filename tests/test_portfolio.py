"""Tests for src.portfolio.build_portfolio_df()."""
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture(autouse=True)
def clear_caches():
    """Clear relevant caches before each test."""
    from src.cache import short_cache
    short_cache.clear()


@patch("src.portfolio.yf.download")
@patch("src.portfolio.get_fx_rate", return_value=(1.0, True))
@patch("src.portfolio._dividends_in_base_currency", return_value=0.0)
def test_empty_portfolio_returns_empty_df(mock_divs, mock_fx, mock_download):
    from src.portfolio import build_portfolio_df
    result = build_portfolio_df({}, "USD")
    assert isinstance(result, pd.DataFrame)
    assert result.empty


@patch("src.portfolio.yf.download")
@patch("src.portfolio.get_fx_rate", return_value=(1.0, True))
@patch("src.portfolio._dividends_in_base_currency", return_value=0.0)
def test_basic_portfolio_returns_expected_columns(mock_divs, mock_fx, mock_download):
    from src.portfolio import build_portfolio_df

    # Mock yfinance download: 5 days of prices for a single ticker
    dates = pd.date_range("2024-01-10", periods=5, freq="B")
    mock_download.return_value = pd.DataFrame(
        {"Close": [148.0, 149.0, 150.0, 151.0, 152.0]},
        index=dates,
    )

    portfolio = {
        "AAPL": [
            {"shares": 10, "buy_price": 145.0, "buy_fx_rate": 1.0, "purchase_date": "2024-01-08"},
        ],
    }

    result = build_portfolio_df(portfolio, "USD")
    assert not result.empty

    expected_cols = {"Ticker", "Total Value", "Current Price", "Buy Price",
                     "Shares", "Daily P&L", "Return (%)", "Weight (%)"}
    assert expected_cols.issubset(set(result.columns))

    assert result.iloc[0]["Ticker"] == "AAPL"
    assert result.iloc[0]["Shares"] == 10
    assert result.iloc[0]["Current Price"] == 152.0
    assert result.iloc[0]["Total Value"] == 1520.0
