"""Tests for src.portfolio.build_portfolio_df()."""
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture(autouse=True)
def clear_caches():
    """Clear relevant caches before each test."""
    from src.cache import short_cache, long_cache_splits
    short_cache.clear()
    long_cache_splits.clear()


@patch("src.portfolio.get_split_factor", return_value=1.0)
@patch("src.portfolio.yf.download")
@patch("src.portfolio.get_fx_rate", return_value=(1.0, True))
@patch("src.portfolio._dividends_in_base_currency", return_value=0.0)
def test_empty_portfolio_returns_empty_df(mock_divs, mock_fx, mock_download, mock_split):
    from src.portfolio import build_portfolio_df
    result = build_portfolio_df({}, "USD")
    assert isinstance(result, pd.DataFrame)
    assert result.empty


@patch("src.portfolio.get_split_factor", return_value=1.0)
@patch("src.portfolio.yf.download")
@patch("src.portfolio.get_fx_rate", return_value=(1.0, True))
@patch("src.portfolio._dividends_in_base_currency", return_value=0.0)
def test_basic_portfolio_returns_expected_columns(mock_divs, mock_fx, mock_download, mock_split):
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


def test_dividend_timeline_respects_purchase_dates():
    """Dividends should only count shares owned at the time of the dividend."""
    from unittest.mock import patch
    import pandas as pd
    from src.portfolio import build_dividend_timeline

    portfolio = {
        "AAPL": [
            {"shares": 10, "purchase_date": "2024-01-01", "buy_price": 150},
            {"shares": 10, "purchase_date": "2025-06-01", "buy_price": 200},
        ]
    }

    div_dates = pd.DatetimeIndex(["2024-06-15", "2025-08-15"])
    mock_hist = pd.DataFrame({
        "Close": [150.0, 200.0],
        "Dividends": [0.50, 0.60],
    }, index=div_dates)

    with patch("src.portfolio.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.history.return_value = mock_hist
        with patch("src.portfolio.get_ticker_currency", return_value="USD"):
            with patch("src.portfolio.get_historical_fx_rate", return_value=1.0):
                result = build_dividend_timeline(portfolio, "USD", months_back=24)

    amounts = {r["month"]: r["amount"] for r in result}
    assert amounts.get("2024-06") == 5.00, f"Expected 5.00 for 2024-06, got {amounts.get('2024-06')}"
    assert amounts.get("2025-08") == 12.00, f"Expected 12.00 for 2025-08, got {amounts.get('2025-08')}"


@patch("src.portfolio.yf.Ticker")
def test_get_split_factor_cumulative(mock_ticker_cls):
    """Cumulative product of splits after purchase date."""
    from src.portfolio import get_split_factor
    from src.cache import long_cache_splits
    long_cache_splits.clear()

    # Simulate a 4:1 split on 2024-06-01 and a 2:1 split on 2024-09-01
    splits = pd.Series(
        [4.0, 2.0],
        index=pd.DatetimeIndex(["2024-06-01", "2024-09-01"]),
    )
    mock_ticker_cls.return_value.splits = splits

    # Purchased before both splits -> factor = 4 * 2 = 8
    assert get_split_factor("AAPL", "2024-01-10") == 8.0


@patch("src.portfolio.yf.Ticker")
def test_get_split_factor_no_splits(mock_ticker_cls):
    """Returns 1.0 when no splits exist."""
    from src.portfolio import get_split_factor
    from src.cache import long_cache_splits
    long_cache_splits.clear()

    mock_ticker_cls.return_value.splits = pd.Series(dtype=float)

    assert get_split_factor("AAPL", "2024-01-10") == 1.0


def test_get_split_factor_manual_date():
    """Returns 1.0 for 'Manual' purchase date without calling yfinance."""
    from src.portfolio import get_split_factor
    assert get_split_factor("AAPL", "Manual") == 1.0
    assert get_split_factor("AAPL", None) == 1.0
