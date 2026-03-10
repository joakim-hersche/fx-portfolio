import pandas as pd
import requests

HEADERS = {"User-Agent": "Mozilla/5.0"}

def fetch_wikipedia_table(url, ticker_col, name_col, suffix=""):
    try:
        response = requests.get(url, headers=HEADERS)
        tables = pd.read_html(response.text)
        for table in tables:
            if ticker_col in table.columns and name_col in table.columns:
                stocks = {}
                for _, row in table.iterrows():
                    ticker = str(row[ticker_col]).strip()
                    name = str(row[name_col]).strip()
                    if ticker and name and ticker != "nan":
                        full_ticker = f"{ticker}{suffix}"
                        stocks[f"{name} ({full_ticker})"] = full_ticker
                return stocks
    except Exception as e:
        print(f"Failed to fetch {url}: {e}")
    return {}

def get_sp500_stocks():
    return fetch_wikipedia_table(
        url="https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
        ticker_col="Symbol",
        name_col="Security"
    )

def get_ftse100_stocks():
    return fetch_wikipedia_table(
        url="https://en.wikipedia.org/wiki/FTSE_100_Index",
        ticker_col="Ticker",
        name_col="Company",
        suffix=".L"
    )

def get_dax_stocks():
    return fetch_wikipedia_table(
        url="https://en.wikipedia.org/wiki/DAX",
        ticker_col="Ticker",
        name_col="Company",
        suffix=".DE"
    )

def get_cac40_stocks():
    return fetch_wikipedia_table(
        url="https://en.wikipedia.org/wiki/CAC_40",
        ticker_col="Ticker",
        name_col="Company",
        suffix=".PA"
    )

def get_smi_stocks():
    return fetch_wikipedia_table(
        url="https://en.wikipedia.org/wiki/Swiss_Market_Index",
        ticker_col="Ticker",
        name_col="Name",
        suffix=""
    )

def get_aex_stocks():
    return fetch_wikipedia_table(
        url="https://en.wikipedia.org/wiki/AEX_index",
        ticker_col="Ticker",
        name_col="Company",
        suffix=".AS"
    )

def get_ibex_stocks():
    return fetch_wikipedia_table(
        url="https://en.wikipedia.org/wiki/IBEX_35",
        ticker_col="Ticker",
        name_col="Company",
        suffix=".MC"
    )

def get_etfs():
    return {
        "S&P 500 ETF (SPY)": "SPY",
        "Nasdaq 100 ETF (QQQ)": "QQQ",
        "Total Market ETF (VTI)": "VTI",
        "Growth ETF (VUG)": "VUG",
        "Dividend ETF (VYM)": "VYM",
        "iShares Core MSCI Europe (IMAE.AS)": "IMAE.AS",
        "Vanguard FTSE Europe (VGK)": "VGK",
        "iShares STOXX Europe 600 (EXSA.DE)": "EXSA.DE",
        "iShares MSCI World (IWDA.AS)": "IWDA.AS",
        "Vanguard Total World (VT)": "VT",
    }