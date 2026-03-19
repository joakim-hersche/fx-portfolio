"""Cached yfinance data-fetching wrappers.

All functions use cachetools TTLCache so they are called once per ticker per
TTL window, with no framework dependency.
"""

from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import yfinance as yf
from cachetools import cached

from src.cache import short_cache, long_cache, long_cache_history, long_cache_fundamentals, long_cache_names, lenient_key

from src.fx import get_ticker_currency, CURRENCY_SYMBOLS
from src.monte_carlo import run_monte_carlo_backtest, run_monte_carlo_portfolio, run_monte_carlo_ticker
from src.stocks import (
    get_sp500_stocks, get_ftse100_stocks, get_dax_stocks,
    get_cac40_stocks, get_smi_stocks, get_aex_stocks,
    get_ibex_stocks, get_omx30_stocks, get_etfs, get_crypto,
    get_commodities, get_reits, get_bonds, get_emerging_markets,
)


@cached(short_cache)
def fetch_price_history_short(ticker: str) -> pd.DataFrame:
    """Fetch 6-month price history. Cached for 15 minutes."""
    try:
        hist = yf.Ticker(ticker).history(period="6mo")
        hist.index = hist.index.tz_localize(None)
        return hist
    except Exception:
        return pd.DataFrame()


@cached(long_cache_history)
def fetch_price_history_long(ticker: str) -> pd.DataFrame:
    """Fetch full price history. Cached for 24 hours."""
    try:
        hist = yf.Ticker(ticker).history(period="max")
        hist.index = hist.index.tz_localize(None)
        return hist
    except Exception:
        return pd.DataFrame()


@cached(long_cache_fundamentals)
def fetch_fundamentals(ticker: str) -> dict:
    """Fetch P/E, dividend yield, and 1-year range. Cached for 24 hours."""
    try:
        info = yf.Ticker(ticker).info
        current  = info.get("currentPrice") or info.get("regularMarketPrice")
        low_1y   = info.get("fiftyTwoWeekLow")
        high_1y  = info.get("fiftyTwoWeekHigh")
        pe       = info.get("trailingPE")
        div_rate = info.get("dividendRate")  # annual dividend per share, native currency

        # Prefer computing yield from dividendRate/price — more reliable than dividendYield
        # which yfinance returns inconsistently (sometimes decimal fraction, sometimes percent).
        if div_rate and current and current > 0:
            candidate = round(div_rate / current * 100, 4)
            # Guard: yields above 20% almost certainly indicate a unit mismatch
            # (e.g. dividendRate returned in cents instead of dollars). Fall through
            # to the dividendYield fallback in that case.
            div_pct = candidate if candidate <= 20.0 else None
        else:
            div_pct = None

        if div_pct is None:
            div = info.get("dividendYield")
            if div is not None:
                # dividendYield is normally a decimal fraction (0.0042 = 0.42%).
                # If result > 20% after multiplying it was already in percent form.
                candidate = div * 100
                div_pct = candidate if candidate <= 20.0 else div

        # For London-listed tickers yfinance returns fiftyTwoWeekLow/High in GBX
        # (pence) but currentPrice in GBP, so divide by 100 to make units consistent.
        ticker_ccy = get_ticker_currency(ticker)
        if ticker_ccy == "GBX":
            low_1y  = low_1y  / 100 if low_1y  else None
            high_1y = high_1y / 100 if high_1y else None

        position = None
        if current and low_1y and high_1y and high_1y > low_1y:
            position = round((current - low_1y) / (high_1y - low_1y) * 100, 1)

        return {
            "P/E Ratio":      round(pe, 1)        if pe      else None,
            "Div Yield (%)":  round(div_pct, 2)   if div_pct else None,
            "1-Year Low":     round(low_1y, 2)     if low_1y  else None,
            "1-Year High":    round(high_1y, 2)    if high_1y else None,
            "1-Year Position": position,
            "Current Price":  round(current, 2)    if current else None,
        }
    except Exception:
        return {}


@cached(long_cache_names)
def fetch_company_name(ticker: str) -> str:
    """Fetch short company name. Falls back to ticker on failure."""
    try:
        info = yf.Ticker(ticker).info
        return info.get("shortName") or info.get("longName") or ticker
    except Exception:
        return ticker


@cached(long_cache)
def fetch_simulation_history(ticker: str) -> pd.DataFrame:
    """Fetch up to 5-year price history for Monte Carlo simulation. Cached for 24 hours."""
    try:
        hist = yf.Ticker(ticker).history(period="5y")
        hist.index = hist.index.tz_localize(None)
        return hist
    except Exception:
        return pd.DataFrame()


@cached(long_cache)
def fetch_analytics_history(ticker: str) -> pd.DataFrame:
    """Fetch 1-year price history for analytics. Cached for 24 hours."""
    try:
        hist = yf.Ticker(ticker).history(period="1y")
        hist.index = hist.index.tz_localize(None)
        return hist
    except Exception:
        return pd.DataFrame()


@cached(short_cache)
def fetch_price_history_range(ticker: str, period: str) -> pd.DataFrame:
    """Fetch price history for a given period string (e.g. '3mo', '1y'). Cached for 15 minutes."""
    try:
        hist = yf.Ticker(ticker).history(period=period)
        hist.index = hist.index.tz_localize(None)
        return hist
    except Exception:
        return pd.DataFrame()


@cached(long_cache, key=lenient_key)
def cached_run_monte_carlo_backtest(portfolio: dict, price_data: dict) -> dict:
    """Cached wrapper for run_monte_carlo_backtest. Recomputes when portfolio or price data changes."""
    return run_monte_carlo_backtest(portfolio, price_data)


@cached(long_cache, key=lenient_key)
def cached_run_monte_carlo_portfolio(
    portfolio: dict,
    price_data: dict,
    start_prices_base: dict,
    horizon_days: int = 252,
    lookback_days: int | None = None,
) -> dict:
    """Cached wrapper for run_monte_carlo_portfolio."""
    return run_monte_carlo_portfolio(
        portfolio=portfolio,
        price_data=price_data,
        start_prices_base=start_prices_base,
        horizon_days=horizon_days,
        lookback_days=lookback_days,
    )


@cached(long_cache, key=lenient_key)
def cached_run_monte_carlo_ticker(
    ticker: str,
    hist: pd.DataFrame,
    current_price: float,
    horizon_days: int = 252,
    lookback_days: int | None = None,
) -> dict:
    """Cached wrapper for run_monte_carlo_ticker."""
    return run_monte_carlo_ticker(
        hist=hist,
        current_price=current_price,
        horizon_days=horizon_days,
        lookback_days=lookback_days,
    )


@cached(long_cache)
def load_stock_options() -> dict:
    """Load all available stock lists from Wikipedia scrapers. Cached for 24 hours."""
    sources = [
        ("US — S&P 500",       get_sp500_stocks),
        ("UK — FTSE 100",      get_ftse100_stocks),
        ("Germany — DAX",      get_dax_stocks),
        ("France — CAC 40",    get_cac40_stocks),
        ("Switzerland — SMI",  get_smi_stocks),
        ("Netherlands — AEX",  get_aex_stocks),
        ("Spain — IBEX 35",    get_ibex_stocks),
        ("Sweden — OMX 30",    get_omx30_stocks),
        ("ETFs",               get_etfs),
        ("REITs",              get_reits),
        ("Bonds",              get_bonds),
        ("Emerging Markets",   get_emerging_markets),
        ("Crypto",             get_crypto),
        ("Commodities",        get_commodities),
    ]

    def _call(pair):
        label, fn = pair
        return label, fn()

    with ThreadPoolExecutor(max_workers=len(sources)) as executor:
        results = executor.map(_call, sources)

    return dict(results)
