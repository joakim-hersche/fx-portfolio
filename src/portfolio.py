import yfinance as yf
import pandas as pd
from src.fx import get_ticker_currency, get_fx_rate

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