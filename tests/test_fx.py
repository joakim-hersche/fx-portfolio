"""Tests for src.fx.get_ticker_currency()."""
import pytest
from src.fx import get_ticker_currency


@pytest.mark.parametrize(
    "ticker, expected",
    [
        ("AAPL", "USD"),
        ("SHEL.L", "GBX"),
        ("ASML.AS", "EUR"),
        ("MC.PA", "EUR"),
        ("NESN.SW", "CHF"),
        ("VOLV-B.ST", "SEK"),
        ("BTC-USD", "USD"),
        ("GC=F", "USD"),
    ],
)
def test_get_ticker_currency(ticker, expected):
    assert get_ticker_currency(ticker) == expected
