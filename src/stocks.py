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


TICKER_COLORS = {
    # US Tech
    "AAPL":   "#555555",  # Apple space grey
    "MSFT":   "#00a4ef",  # Microsoft blue
    "GOOGL":  "#4285f4",  # Google blue
    "GOOG":   "#4285f4",
    "AMZN":   "#ff9900",  # Amazon orange
    "META":   "#0866ff",  # Meta blue
    "NVDA":   "#76b900",  # NVIDIA green
    "TSLA":   "#e31937",  # Tesla red
    "NFLX":   "#e50914",  # Netflix red
    "AMD":    "#ed1c24",  # AMD red
    "INTC":   "#0071c5",  # Intel blue
    "ORCL":   "#f80000",  # Oracle red
    "CRM":    "#00a1e0",  # Salesforce blue
    "ADBE":   "#ff0000",  # Adobe red
    # US Finance
    "JPM":    "#005eb8",  # JPMorgan blue
    "GS":     "#7399c6",  # Goldman blue
    "BAC":    "#e31837",  # BofA red
    "V":      "#1a1f71",  # Visa navy
    "MA":     "#eb001b",  # Mastercard red
    # US Consumer / Other
    "WMT":    "#0071ce",  # Walmart blue
    "KO":     "#f40000",  # Coca-Cola red
    "PEP":    "#004b93",  # Pepsi blue
    "MCD":    "#ffbc0d",  # McDonald's yellow
    "NKE":    "#f85c00",  # Nike orange
    "DIS":    "#113ccf",  # Disney blue
    # ETFs
    "SPY":    "#c0392b",
    "QQQ":    "#2980b9",
    "VTI":    "#27ae60",
    "VUG":    "#16a085",
    "VYM":    "#8e44ad",
    "VT":     "#2c3e50",
    "VGK":    "#2471a3",
    # UK
    "HSBA.L": "#db0011",  # HSBC red
    "BP.L":   "#009900",  # BP green
    "GSK.L":  "#f36633",  # GSK orange
    "AZN.L":  "#003865",  # AstraZeneca navy
    "SHEL.L": "#fbce07",  # Shell yellow
    "LLOY.L": "#024731",  # Lloyds green
    "BARC.L": "#00aeef",  # Barclays blue
    # Switzerland
    "UBSG.SW":  "#e30613",  # UBS red
    # Europe
    "SAP.DE":   "#0faaff",  # SAP blue
    "VOW3.DE":  "#001e50",  # VW navy
    "BMW.DE":   "#1c69d3",  # BMW blue
    "ASML.AS":  "#009ee2",  # ASML blue
    "NESN.SW":  "#e2001a",  # Nestlé red
    "NOVN.SW":  "#0460a9",  # Novartis blue
    "ROG.SW":   "#009fe3",  # Roche blue
}