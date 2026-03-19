import yfinance as yf
import pandas as pd
import logging
from cachetools import cached, TTLCache

from src.cache import short_cache, long_cache

_log = logging.getLogger(__name__)

CURRENCY_SYMBOLS = {"USD": "$", "EUR": "€", "GBP": "£", "CHF": "CHF ", "SEK": "kr "}

# Dedicated cache for ticker currency lookups (24h, same as fundamentals)
_currency_cache = TTLCache(maxsize=512, ttl=86400)


def normalize_gbx(value, currency: str):
    """Convert GBX (pence) to GBP by dividing by 100. Pass-through for other currencies."""
    if currency == "GBX":
        return value / 100
    return value


def _suffix_heuristic(ticker: str) -> str:
    """Infer currency from ticker suffix. Used as fallback when API lookup fails."""
    if ticker.endswith(".L"):
        return "GBX"
    elif ticker.endswith((".DE", ".PA", ".AS", ".MC")):
        return "EUR"
    elif ticker.endswith(".SW"):
        return "CHF"
    elif ticker.endswith(".ST"):
        return "SEK"
    return "USD"


@cached(_currency_cache)
def get_ticker_currency(ticker: str) -> str:
    """Return the native trading currency for a ticker.

    Tries yfinance metadata first, falls back to suffix heuristic.
    Results are cached for 24 hours.
    """
    try:
        ccy = yf.Ticker(ticker).info.get("currency")
        if ccy:
            # Normalize yfinance quirks: "GBp" -> "GBX"
            if ccy in ("GBp", "GBX"):
                return "GBX"
            return ccy
    except Exception:
        _log.debug("Currency lookup failed for %s, using suffix heuristic", ticker)
    return _suffix_heuristic(ticker)

@cached(short_cache)
def get_fx_rate(from_currency: str, to_currency: str) -> tuple[float, bool]:
    """Fetch live FX rate between two currencies. GBX (pence) handled automatically.

    Returns ``(rate, success)`` — when the lookup fails the rate is 1.0 and
    *success* is False so callers can surface a warning to the user.
    """
    if from_currency == to_currency:
        return 1.0, True
    if from_currency == "GBX":
        gbp_rate, ok = get_fx_rate("GBP", to_currency)
        return gbp_rate / 100, ok
    try:
        pair = f"{from_currency}{to_currency}=X"
        rate = yf.Ticker(pair).history(period="1d")["Close"].iloc[-1]
        return float(rate), True
    except Exception as exc:
        _log.warning("FX rate fetch failed for %s→%s: %s — using 1.0 fallback", from_currency, to_currency, exc)
        return 1.0, False


@cached(long_cache)
def get_historical_fx_rate(from_currency: str, to_currency: str, date_str: str) -> float:
    """
    Fetch the FX rate on or just after a given date (YYYY-MM-DD).
    Falls back to the current live rate if historical data is unavailable.
    GBX (pence) handled automatically.
    """
    if from_currency == to_currency:
        return 1.0
    if from_currency == "GBX":
        return get_historical_fx_rate("GBP", to_currency, date_str) / 100
    try:
        end = str((pd.Timestamp(date_str) + pd.DateOffset(days=7)).date())
        pair = f"{from_currency}{to_currency}=X"
        hist = yf.Ticker(pair).history(start=date_str, end=end)
        if not hist.empty:
            return float(hist["Close"].iloc[0])
    except Exception:
        _log.warning("Historical FX lookup failed for %s→%s on %s; falling back to live rate", from_currency, to_currency, date_str)
    rate, _ = get_fx_rate(from_currency, to_currency)
    return rate