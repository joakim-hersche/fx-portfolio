import yfinance as yf
import pandas as pd
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

def _dividends_in_base_currency(
    ticker_obj: yf.Ticker,
    purchase_date: str,
    from_currency: str,
    base_currency: str,
) -> float:
    """Sum dividends per share from purchase_date to today, converted at historical FX rates."""
    try:
        today = str(pd.Timestamp.today().date())
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
            fallback = get_fx_rate(from_currency, base_currency)
            return float(dividends.sum() * fallback)

        fx_series = fx_hist["Close"].reindex(dividends.index, method="ffill").bfill()
        if gbx:
            fx_series = fx_series / 100

        return float((dividends * fx_series).sum())
    except Exception:
        return 0.0

def build_portfolio_df(portfolio: dict, base_currency: str) -> pd.DataFrame:
    """
    Convert raw portfolio session state into a display-ready DataFrame.
    All prices are converted to base_currency.
    """
    rows = []

    for ticker, lots in portfolio.items():
        t = yf.Ticker(ticker)
        data = t.history(period="5d")
        if len(data) < 2:
            continue

        fx_rate = get_fx_rate(get_ticker_currency(ticker), base_currency)
        current_price = data["Close"].iloc[-1] * fx_rate
        prev_price = data["Close"].iloc[-2] * fx_rate

        for i, lot in enumerate(lots):
            shares = lot["shares"]
            buy_price = lot["buy_price"] * fx_rate
            purchase_date = lot["purchase_date"]

            dividends_per_share = (
                _dividends_in_base_currency(t, purchase_date, get_ticker_currency(ticker), base_currency)
                if purchase_date and purchase_date != "Manual"
                else 0.0
            )
            total_dividends = round(dividends_per_share * shares, 2)
            cost_basis = buy_price * shares

            rows.append({
                "Ticker": ticker,
                "Lot": i + 1,
                "Shares": shares,
                "Buy Price": round(buy_price, 2),
                "Purchase Date": purchase_date or "Manual",
                "Current Price": round(current_price, 2),
                "Total Value": round(current_price * shares, 2),
                "Dividends": total_dividends,
                "Daily P&L": round((current_price - prev_price) * shares, 2),
                "Return (%)": round(
                    (current_price * shares + total_dividends - cost_basis) / cost_basis * 100, 2
                ),
            })

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["Weight (%)"] = (df["Total Value"] / df["Total Value"].sum() * 100).round(2)
    return df


def fetch_buy_price(ticker: str, purchase_date: str) -> float | None:
    """Fetch closing price on or just after a given purchase date."""
    try:
        end = str((pd.Timestamp(purchase_date) + pd.DateOffset(days=7)).date())
        hist = yf.Ticker(ticker).history(start=purchase_date, end=end)
        if hist.empty:
            return None
        return round(hist["Close"].iloc[0], 2)
    except Exception:
        return None