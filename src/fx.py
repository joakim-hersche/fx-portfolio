import yfinance as yf
import streamlit as st

CURRENCY_SYMBOLS = {"USD": "$", "CHF": "CHF ", "EUR": "€", "GBP": "£"}

def get_ticker_currency(ticker: str) -> str:
    """Return the native currency code for a given ticker symbol."""
    if ticker.endswith(".L"):
        return "GBX"
    elif ticker.endswith((".DE", ".PA", ".AS", ".MC")):
        return "EUR"
    elif ticker.endswith(".SW"):
        return "CHF"
    elif ticker.endswith(".ST"):
        return "SEK"
    return "USD"

@st.cache_data(ttl=900)
def get_fx_rate(from_currency: str, to_currency: str) -> float:
    """Fetch live FX rate between two currencies. GBX (pence) handled automatically."""
    if from_currency == to_currency:
        return 1.0
    if from_currency == "GBX":
        return get_fx_rate("GBP", to_currency) / 100
    try:
        pair = f"{from_currency}{to_currency}=X"
        rate = yf.Ticker(pair).history(period="1d")["Close"].iloc[-1]
        return float(rate)
    except Exception:
        return 1.0