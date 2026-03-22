import os
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock

from src.risk_free import fetch_risk_free_yields, _fetch_fred, _fetch_riksbank
from src.cache import long_cache_risk_free


@pytest.fixture(autouse=True)
def clear_risk_free_cache():
    """Clear the risk-free cache before each test to prevent cross-test interference."""
    long_cache_risk_free.clear()
    yield
    long_cache_risk_free.clear()


class TestFetchFred:
    """FRED API fetcher for USD 10Y Treasury yield."""

    def test_returns_series_on_success(self):
        mock_json = {
            "observations": [
                {"date": "2025-01-02", "value": "4.25"},
                {"date": "2025-01-03", "value": "4.30"},
                {"date": "2025-01-06", "value": "."},
                {"date": "2025-01-07", "value": "4.28"},
            ]
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_json
        mock_resp.raise_for_status = MagicMock()

        with patch("src.risk_free.requests.get", return_value=mock_resp):
            with patch.dict(os.environ, {"FRED_API_KEY": "test_key"}):
                result = _fetch_fred("2025-01-02", "2025-01-07")

        assert isinstance(result, pd.Series)
        assert len(result) == 3
        assert result.iloc[0] == pytest.approx(4.25)

    def test_returns_empty_without_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("FRED_API_KEY", None)
            result = _fetch_fred("2025-01-02", "2025-01-07")
        assert result.empty


class TestFetchRiksbank:
    """Riksbank API fetcher for EUR/GBP/SEK 10Y yields."""

    def test_returns_series_on_success(self):
        mock_json = [
            {"date": "2025-01-02", "value": 2.35},
            {"date": "2025-01-03", "value": 2.40},
        ]
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_json
        mock_resp.raise_for_status = MagicMock()

        with patch("src.risk_free.requests.get", return_value=mock_resp):
            result = _fetch_riksbank("EUR", "2025-01-02", "2025-01-03")

        assert isinstance(result, pd.Series)
        assert len(result) == 2
        assert result.iloc[0] == pytest.approx(2.35)

    def test_returns_empty_on_error(self):
        with patch("src.risk_free.requests.get", side_effect=Exception("timeout")):
            result = _fetch_riksbank("EUR", "2025-01-02", "2025-01-03")
        assert result.empty


class TestFetchRiskFreeYields:
    """Public dispatch function."""

    def test_usd_dispatches_to_fred(self):
        fake = pd.Series([4.0, 4.1], index=pd.to_datetime(["2025-01-02", "2025-01-03"]))
        with patch("src.risk_free._fetch_fred", return_value=fake):
            result = fetch_risk_free_yields("USD", "2025-01-02", "2025-01-03")
        assert len(result) == 2

    def test_unsupported_currency_returns_empty(self):
        result = fetch_risk_free_yields("JPY", "2025-01-02", "2025-01-03")
        assert result.empty
