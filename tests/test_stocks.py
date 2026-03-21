"""Tests for stock list scraping functions."""
import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
from src.stocks import get_smim_stocks


@patch("src.stocks.requests.get")
def test_get_smim_stocks_returns_dict(mock_get):
    html = '''
    <table class="wikitable">
    <tr><th>Ticker</th><th>Company</th></tr>
    <tr><td>BAER.SW</td><td>Julius Baer</td></tr>
    <tr><td>SREN.SW</td><td>Swiss Re</td></tr>
    </table>
    '''
    mock_response = MagicMock()
    mock_response.text = html
    mock_get.return_value = mock_response
    result = get_smim_stocks()
    assert isinstance(result, dict)
    assert len(result) >= 1
    for ticker in result:
        assert ticker.endswith(".SW"), f"SMIM ticker {ticker} missing .SW suffix"


@patch("src.stocks.requests.get")
def test_get_smim_stocks_fallback_on_failure(mock_get):
    mock_get.side_effect = Exception("network error")
    result = get_smim_stocks()
    assert isinstance(result, dict)
    assert len(result) > 0  # fallback should have entries
