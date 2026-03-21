"""Cached yfinance data-fetching wrappers.

All functions use cachetools TTLCache so they are called once per ticker per
TTL window, with no framework dependency.
"""

import logging
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import yfinance as yf
from cachetools import cached

logger = logging.getLogger(__name__)

from src.cache import short_cache, long_cache, long_cache_history, long_cache_simulation, long_cache_analytics, long_cache_fundamentals, long_cache_names, lenient_key

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
    """Fetch 6-month price history. Cached for 5 minutes."""
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
    """Fetch P/E, dividend yield, and 1-year range. Cached for 24 hours.

    Price fields (``currentPrice``, ``1-Year Low/High``) are returned in
    the ticker's **trading currency** (i.e. what ``get_ticker_currency``
    returns — GBX for ``.L`` stocks, EUR for ``.AS``, etc.).

    ``Dividend Rate`` comes from yfinance in ``financialCurrency``
    which can differ from the trading currency (e.g. USD for many
    London-listed stocks).  We return it in ``financialCurrency`` and
    include a ``Financial Currency`` key so callers can apply the right
    FX conversion.  ``Target Price`` is in the trading currency.
    """
    try:
        info = yf.Ticker(ticker).info
        current      = info.get("currentPrice") or info.get("regularMarketPrice")
        low_1y       = info.get("fiftyTwoWeekLow")
        high_1y      = info.get("fiftyTwoWeekHigh")
        pe           = info.get("trailingPE")
        div_rate     = info.get("dividendRate")  # in financialCurrency
        sector       = info.get("sector", None)
        target_price = info.get("targetMeanPrice", None)  # in financialCurrency

        trading_ccy   = info.get("currency")           # e.g. "GBp", "EUR", "USD"
        financial_ccy = info.get("financialCurrency")   # e.g. "USD", "GBP", "EUR"
        # Normalise yfinance's "GBp" label to our canonical "GBX"
        if financial_ccy == "GBp":
            financial_ccy = "GBX"

        # ── Dividend yield (%) ──
        # Use dividendYield directly — it's already a ratio independent of
        # currency mismatches between trading and financial currencies.
        div_pct = None
        div = info.get("dividendYield")
        if div is not None:
            # dividendYield is normally a decimal fraction (0.0042 = 0.42%).
            # If result > 20% after multiplying it was already in percent form.
            candidate = div * 100
            div_pct = candidate if candidate <= 20.0 else div

        # ── 52-week position ──
        position = None
        if current and low_1y and high_1y and high_1y > low_1y:
            position = round((current - low_1y) / (high_1y - low_1y) * 100, 1)

        return {
            "P/E Ratio":          round(pe, 1)            if pe           else None,
            "Div Yield (%)":      round(div_pct, 2)       if div_pct      else None,
            "1-Year Low":         round(low_1y, 2)        if low_1y       else None,
            "1-Year High":        round(high_1y, 2)       if high_1y      else None,
            "1-Year Position":    position,
            "Current Price":      round(current, 2)       if current      else None,
            "Sector":             sector if sector else "Unknown",
            "Target Price":       round(target_price, 2)  if target_price else None,
            "Dividend Rate":      round(div_rate, 4)      if div_rate     else None,
            "Financial Currency": financial_ccy,
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


@cached(long_cache_simulation)
def fetch_simulation_history(ticker: str) -> pd.DataFrame:
    """Fetch up to 5-year price history for Monte Carlo simulation. Cached for 24 hours."""
    try:
        hist = yf.Ticker(ticker).history(period="5y")
        if hist.empty:
            logger.warning("fetch_simulation_history(%s): yfinance returned empty DataFrame", ticker)
            return pd.DataFrame()
        hist.index = hist.index.tz_localize(None)
        logger.info("fetch_simulation_history(%s): %d rows fetched", ticker, len(hist))
        return hist
    except Exception as e:
        logger.error("fetch_simulation_history(%s) failed: %s", ticker, e)
        return pd.DataFrame()


@cached(long_cache_analytics)
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
    """Fetch price history for a given period string (e.g. '3mo', '1y'). Cached for 5 minutes."""
    try:
        hist = yf.Ticker(ticker).history(period=period)
        hist.index = hist.index.tz_localize(None)
        return hist
    except Exception:
        return pd.DataFrame()


@cached(short_cache)
def fetch_ticker_news(ticker: str) -> list[dict]:
    """Fetch recent news for a ticker. Cached for 5 minutes."""
    try:
        news = yf.Ticker(ticker).news
        if not news:
            return []
        return [
            {
                "title": item.get("title", ""),
                "publisher": item.get("publisher", ""),
                "link": item.get("link", ""),
                "providerPublishTime": item.get("providerPublishTime", 0),
            }
            for item in news
        ]
    except Exception:
        return []


@cached(long_cache_fundamentals, key=lenient_key)
def fetch_sector_peers(sector, candidate_tickers, target_ticker, max_peers=4):
    """Find same-sector peers from candidate tickers. Cached for 24 hours."""
    peers = []
    for ticker in candidate_tickers:
        if len(peers) >= max_peers:
            break
        if ticker == target_ticker:
            continue
        try:
            info = yf.Ticker(ticker).info
            if info.get("sector", "") != sector:
                continue
            hist = yf.Ticker(ticker).history(period="1y")
            return_1y = None
            if not hist.empty and "Close" in hist.columns:
                close = hist["Close"].dropna()
                if len(close) >= 2:
                    return_1y = round((close.iloc[-1] / close.iloc[0] - 1) * 100, 1)
            peers.append({
                "ticker": ticker,
                "name": info.get("shortName", ticker),
                "pe": info.get("trailingPE"),
                "div_yield": round(info.get("dividendYield", 0) * 100, 2) if info.get("dividendYield") else None,
                "beta": info.get("beta"),
                "return_1y": return_1y,
            })
        except Exception:
            continue
    return peers


@cached(long_cache_fundamentals, key=lenient_key)
def fetch_sector_medians(sector, candidate_tickers, max_samples=10):
    """Compute median P/E and dividend yield for a sector. Cached for 24 hours."""
    import statistics

    pe_values, dy_values = [], []
    sampled = 0
    for ticker in candidate_tickers:
        if sampled >= max_samples:
            break
        try:
            info = yf.Ticker(ticker).info
            if info.get("sector") != sector:
                continue
            sampled += 1
            pe = info.get("trailingPE")
            if pe and pe > 0:
                pe_values.append(pe)
            dy = info.get("dividendYield")
            if dy and dy > 0:
                dy_values.append(dy * 100)
        except Exception:
            continue
    return {
        "median_pe": round(statistics.median(pe_values), 1) if pe_values else None,
        "median_div_yield": round(statistics.median(dy_values), 2) if dy_values else None,
    }


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
