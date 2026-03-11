import yfinance as yf
import pandas as pd
from src.fx import get_ticker_currency, get_fx_rate

def build_portfolio_df(portfolio: dict, base_currency: str) -> pd.DataFrame:
    """
    Convert raw portfolio session state into a display-ready DataFrame.
    All prices are converted to base_currency.
    """
    rows = []

    for ticker, lots in portfolio.items():
        data = yf.Ticker(ticker).history(period="5d")
        if len(data) < 2:
            continue

        fx_rate = get_fx_rate(get_ticker_currency(ticker), base_currency)
        current_price = data["Close"].iloc[-1] * fx_rate
        prev_price = data["Close"].iloc[-2] * fx_rate

        for i, lot in enumerate(lots):
            shares = lot["shares"]
            buy_price = lot["buy_price"] * fx_rate
            rows.append({
                "Ticker": ticker,
                "Lot": i + 1,
                "Shares": shares,
                "Buy Price": round(buy_price, 2),
                "Purchase Date": lot["purchase_date"] or "Manual",
                "Current Price": round(current_price, 2),
                "Total Value": round(current_price * shares, 2),
                "Daily P&L": round((current_price - prev_price) * shares, 2),
                "Return (%)": round((current_price - buy_price) / buy_price * 100, 2),
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