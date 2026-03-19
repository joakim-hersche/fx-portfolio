from concurrent.futures import ThreadPoolExecutor, as_completed

import yfinance as yf
import pandas as pd
from cachetools import cached

from src.cache import short_cache, long_cache, lenient_key
from src.fx import get_ticker_currency, get_fx_rate


def compute_analytics(portfolio: dict, price_data: dict, spy_data: pd.DataFrame) -> pd.DataFrame:
    """
    Compute per-ticker risk analytics from 1-year price history.
    price_data: {ticker: DataFrame with 'Close' column}
    spy_data:   DataFrame with 'Close' column (SPY benchmark)
    Returns DataFrame with columns: Ticker, Volatility, Max Drawdown, Sharpe Ratio, Beta
    """
    RISK_FREE_RATE = 0.04  # assumed annual risk-free rate

    spy_returns = pd.Series(dtype=float)
    if not spy_data.empty and "Close" in spy_data.columns:
        spy_returns = spy_data["Close"].pct_change().dropna()

    rows = []
    for ticker in portfolio:
        hist = price_data.get(ticker)
        if hist is None or hist.empty or "Close" not in hist.columns:
            continue
        prices = hist["Close"].dropna()
        if len(prices) < 30:
            continue

        daily_returns = prices.pct_change().dropna()

        # Annualised volatility
        volatility = daily_returns.std() * (252 ** 0.5)

        # Max drawdown
        rolling_max = prices.cummax()
        drawdown = (prices - rolling_max) / rolling_max
        max_drawdown = float(drawdown.min())

        # Sharpe ratio (annualised, 4% risk-free rate)
        daily_rf = RISK_FREE_RATE / 252
        excess = daily_returns - daily_rf
        sharpe = float((excess.mean() / excess.std()) * (252 ** 0.5)) if excess.std() > 0 else None

        # Beta vs SPY
        beta = None
        if not spy_returns.empty:
            aligned = pd.concat([daily_returns, spy_returns], axis=1, join="inner").dropna()
            aligned.columns = ["stock", "spy"]
            if len(aligned) >= 30 and aligned["spy"].var() > 0:
                beta = float(aligned["stock"].cov(aligned["spy"]) / aligned["spy"].var())

        rows.append({
            "Ticker":       ticker,
            "Volatility":   round(volatility * 100, 1),
            "Max Drawdown": round(max_drawdown * 100, 1),
            "Sharpe Ratio": round(sharpe, 2) if sharpe is not None else None,
            "Beta":         round(beta, 2) if beta is not None else None,
        })

    return pd.DataFrame(rows) if rows else pd.DataFrame()

@cached(long_cache)
def _dividends_in_base_currency(
    ticker: str,
    purchase_date: str,
    from_currency: str,
    base_currency: str,
) -> float:
    """Sum dividends per share from purchase_date to today, converted at historical FX rates."""
    try:
        today = str(pd.Timestamp.today().date())
        ticker_obj = yf.Ticker(ticker)
        hist = ticker_obj.history(start=purchase_date, end=today)
        if hist.empty or "Dividends" not in hist.columns:
            return 0.0

        dividends = hist["Dividends"]
        dividends = dividends[dividends > 0]
        if dividends.empty:
            return 0.0

        if from_currency == base_currency:
            return float(dividends.sum())

        gbx = from_currency == "GBX"
        fx_from = "GBP" if gbx else from_currency
        fx_pair = f"{fx_from}{base_currency}=X"

        fx_hist = yf.Ticker(fx_pair).history(start=purchase_date, end=today)
        if fx_hist.empty:
            fallback, _ = get_fx_rate(from_currency, base_currency)
            return float(dividends.sum() * fallback)

        fx_series = fx_hist["Close"].reindex(dividends.index, method="ffill")
        # For dividends paid before FX history starts, use the earliest
        # available rate rather than bfill() which would pull a future rate.
        earliest_rate = fx_hist["Close"].iloc[0]
        fx_series = fx_series.fillna(earliest_rate)
        if gbx:
            fx_series = fx_series / 100

        return float((dividends * fx_series).sum())
    except Exception:
        return 0.0

@cached(short_cache, key=lenient_key)
def build_portfolio_df(portfolio: dict, base_currency: str) -> pd.DataFrame:
    """
    Convert raw portfolio session state into a display-ready DataFrame.
    All prices are converted to base_currency.
    """
    rows = []
    tickers = list(portfolio.keys())
    if not tickers:
        return pd.DataFrame()

    # Batch-fetch all ticker prices in a single HTTP request
    batch_data = yf.download(tickers, period="5d", group_by="ticker", progress=False, threads=True)

    # Fetch FX rates and dividends in parallel
    def _fetch_extras(ticker):
        ticker_ccy = get_ticker_currency(ticker)
        fx_rate, _ = get_fx_rate(ticker_ccy, base_currency)
        div_cache = {}
        for lot in portfolio[ticker]:
            pd_date = lot.get("purchase_date")
            if pd_date and pd_date != "Manual" and pd_date not in div_cache:
                div_cache[pd_date] = _dividends_in_base_currency(ticker, pd_date, ticker_ccy, base_currency)
        return ticker, fx_rate, div_cache

    extras = {}
    with ThreadPoolExecutor(max_workers=min(10, len(tickers))) as executor:
        futures = {executor.submit(_fetch_extras, t): t for t in tickers}
        for future in as_completed(futures):
            try:
                ticker, fx_rate, div_cache = future.result()
                extras[ticker] = (fx_rate, div_cache)
            except Exception:
                continue

    for ticker, lots in portfolio.items():
        # Extract this ticker's data from the batch result
        if len(tickers) == 1:
            data = batch_data
        else:
            try:
                data = batch_data[ticker]
            except (KeyError, TypeError):
                continue
        if data.empty or "Close" not in data.columns:
            continue
        close = data["Close"].dropna()
        if len(close) < 2:
            continue

        extra = extras.get(ticker)
        if extra is None:
            continue
        fx_rate, div_cache = extra

        current_price = float(close.iloc[-1]) * fx_rate
        prev_price = float(close.iloc[-2]) * fx_rate

        for i, lot in enumerate(lots):
            shares = lot["shares"]
            # Use purchase-date FX rate if stored; fall back to current rate for
            # legacy lots that pre-date this field.
            lot_fx = lot.get("buy_fx_rate", fx_rate)
            buy_price = lot["buy_price"] * lot_fx
            purchase_date = lot["purchase_date"]

            dividends_per_share = (
                div_cache.get(purchase_date, 0.0)
                if purchase_date and purchase_date != "Manual"
                else 0.0
            )
            total_dividends = round(dividends_per_share * shares, 2)
            cost_basis = buy_price * shares

            rows.append({
                "Ticker": ticker,
                "Purchase": i + 1,
                "Shares": shares,
                "Buy Price": round(buy_price, 2),
                "Purchase Date": purchase_date or "Manual",
                "Current Price": round(current_price, 2),
                "Total Value": round(current_price * shares, 2),
                "Dividends": total_dividends,
                "Daily P&L": round((current_price - prev_price) * shares, 2),
                "Return (%)": round(
                    (current_price * shares + total_dividends - cost_basis) / cost_basis * 100, 2
                ) if cost_basis else None,
            })

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["Weight (%)"] = (df["Total Value"] / df["Total Value"].sum() * 100).round(2)
    return df


def fetch_buy_price(ticker: str, purchase_date: str) -> tuple[float, str] | None:
    """
    Fetch closing price on or just after a given purchase date.

    Returns (price, actual_date_str) so callers can detect when the market
    was closed on the requested date and the next trading day was used instead.
    Returns None if no price data is found within 7 days.
    """
    try:
        end = str((pd.Timestamp(purchase_date) + pd.DateOffset(days=7)).date())
        hist = yf.Ticker(ticker).history(start=purchase_date, end=end)
        if hist.empty:
            return None
        actual_date = str(hist.index[0].date())
        return round(hist["Close"].iloc[0], 2), actual_date
    except Exception:
        return None