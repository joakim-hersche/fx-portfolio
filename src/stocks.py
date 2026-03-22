import io

import pandas as pd
import requests

HEADERS = {"User-Agent": "Mozilla/5.0"}

def fetch_wikipedia_table(url, ticker_col, name_col, suffix=""):
    try:
        response = requests.get(url, headers=HEADERS)
        tables = pd.read_html(io.StringIO(response.text))
        for table in tables:
            if ticker_col in table.columns and name_col in table.columns:
                stocks = {}
                for _, row in table.iterrows():
                    ticker = str(row[ticker_col]).strip()
                    name = str(row[name_col]).strip()
                    if ticker and name and ticker != "nan":
                        full_ticker = f"{ticker}{suffix}"
                        stocks[full_ticker] = f"{name} ({full_ticker})"
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
    )

def get_cac40_stocks():
    return fetch_wikipedia_table(
        url="https://en.wikipedia.org/wiki/CAC_40",
        ticker_col="Ticker",
        name_col="Company",
    )

def get_smi_stocks():
    return fetch_wikipedia_table(
        url="https://en.wikipedia.org/wiki/Swiss_Market_Index",
        ticker_col="Ticker",
        name_col="Name",
        suffix=""
    )

_SMIM_FALLBACK = {
    "BAER.SW": "Julius Baer (BAER.SW)",
    "SREN.SW": "Swiss Re (SREN.SW)",
    "SCMN.SW": "Swisscom (SCMN.SW)",
    "GEBN.SW": "Geberit (GEBN.SW)",
    "SGSN.SW": "SGS (SGSN.SW)",
    "TEMN.SW": "Temenos (TEMN.SW)",
    "PGHN.SW": "Partners Group (PGHN.SW)",
    "BARN.SW": "Barry Callebaut (BARN.SW)",
    "STMN.SW": "Straumann (STMN.SW)",
    "VACN.SW": "VAT Group (VACN.SW)",
    "SOON.SW": "Sonova (SOON.SW)",
    "SANN.SW": "Sandoz (SANN.SW)",
    "BEAN.SW": "Belimo (BEAN.SW)",
    "SIGN.SW": "SIG Group (SIGN.SW)",
    "KNIN.SW": "Kuehne+Nagel (KNIN.SW)",
    "DKSH.SW": "DKSH (DKSH.SW)",
    "SFZN.SW": "Siegfried (SFZN.SW)",
    "LISP.SW": "Chocoladefabriken Lindt (LISP.SW)",
    "BANB.SW": "Bachem (BANB.SW)",
}

def get_smim_stocks():
    result = fetch_wikipedia_table(
        url="https://en.wikipedia.org/wiki/Swiss_Market_Index_Mid",
        ticker_col="Ticker",
        name_col="Company",
        suffix=""
    )
    return result if result else _SMIM_FALLBACK

def get_aex_stocks():
    return fetch_wikipedia_table(
        url="https://en.wikipedia.org/wiki/AEX_index",
        ticker_col="Ticker",
        name_col="Company",
    )

def get_ibex_stocks():
    return fetch_wikipedia_table(
        url="https://en.wikipedia.org/wiki/IBEX_35",
        ticker_col="Ticker",
        name_col="Company",
    )

def get_omx30_stocks():
    return fetch_wikipedia_table(
        url="https://en.wikipedia.org/wiki/OMX_Stockholm_30",
        ticker_col="Ticker",
        name_col="Company",
    )

def get_crypto():
    return {
        "BTC-USD":  "Bitcoin (BTC-USD)",
        "ETH-USD":  "Ethereum (ETH-USD)",
        "SOL-USD":  "Solana (SOL-USD)",
        "XRP-USD":  "XRP (XRP-USD)",
        "BNB-USD":  "BNB (BNB-USD)",
    }

def get_commodities():
    return {
        "GC=F":  "Gold Futures (GC=F)",
        "SI=F":  "Silver Futures (SI=F)",
        "CL=F":  "Crude Oil WTI (CL=F)",
        "NG=F":  "Natural Gas (NG=F)",
        "GLD":   "Gold ETF (GLD)",
        "SLV":   "Silver ETF (SLV)",
    }

def get_etfs():
    return {
        "SPY":     "S&P 500 ETF (SPY)",
        "QQQ":     "Nasdaq 100 ETF (QQQ)",
        "VTI":     "Total Market ETF (VTI)",
        "VUG":     "Growth ETF (VUG)",
        "VYM":     "Dividend ETF (VYM)",
        "IMAE.AS": "iShares Core MSCI Europe (IMAE.AS)",
        "VGK":     "Vanguard FTSE Europe (VGK)",
        "EXSA.DE": "iShares STOXX Europe 600 (EXSA.DE)",
        "IWDA.AS": "iShares MSCI World (IWDA.AS)",
        "VT":      "Vanguard Total World (VT)",
    }


def get_reits():
    return {
        "VNQ":   "Vanguard Real Estate ETF (VNQ)",
        "XLRE":  "Real Estate Select Sector (XLRE)",
        "PLD":   "Prologis (PLD)",
        "AMT":   "American Tower (AMT)",
        "EQIX":  "Equinix (EQIX)",
        "SPG":   "Simon Property Group (SPG)",
        "O":     "Realty Income (O)",
        "WELL":  "Welltower (WELL)",
        "PSA":   "Public Storage (PSA)",
        "DLR":   "Digital Realty (DLR)",
        "CBRE":  "CBRE Group (CBRE)",
        "AVB":   "AvalonBay Communities (AVB)",
    }


def get_bonds():
    return {
        "AGG":   "iShares Core US Aggregate Bond (AGG)",
        "BND":   "Vanguard Total Bond Market (BND)",
        "TLT":   "iShares 20+ Year Treasury (TLT)",
        "SHY":   "iShares 1-3 Year Treasury (SHY)",
        "IEF":   "iShares 7-10 Year Treasury (IEF)",
        "LQD":   "iShares Invest. Grade Corp (LQD)",
        "HYG":   "iShares High Yield Corp (HYG)",
        "VGIT":  "Vanguard Interm. Treasury (VGIT)",
        "VGLT":  "Vanguard Long-Term Treasury (VGLT)",
        "TIP":   "iShares TIPS Bond (TIP)",
    }


def get_emerging_markets():
    return {
        "EEM":   "iShares MSCI Emerging Markets (EEM)",
        "VWO":   "Vanguard FTSE Emerging Markets (VWO)",
        "EWJ":   "iShares MSCI Japan (EWJ)",
        "EWZ":   "iShares MSCI Brazil (EWZ)",
        "FXI":   "iShares China Large-Cap (FXI)",
        "INDA":  "iShares MSCI India (INDA)",
        "MCHI":  "iShares MSCI China (MCHI)",
        "EWT":   "iShares MSCI Taiwan (EWT)",
        "EWY":   "iShares MSCI South Korea (EWY)",
        "VEA":   "Vanguard FTSE Developed ex-US (VEA)",
    }


# All colors are chosen to be legible on both light and dark backgrounds.
# Avoid luminance extremes: nothing too dark (<20% luminance) or too light (>80%).
TICKER_COLORS = {
    # US Tech
    "AAPL":   "#888888",  # Apple grey (lightened from brand #555 for dark-mode visibility)
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
    "V":      "#4a52e0",  # Visa (brightened from brand #1a1f71 for dark-mode visibility)
    "MA":     "#eb001b",  # Mastercard red
    # US Consumer / Other
    "WMT":    "#0071ce",  # Walmart blue
    "KO":     "#f40000",  # Coca-Cola red
    "PEP":    "#004b93",  # Pepsi blue
    "MCD":    "#c8960a",  # McDonald's (darkened from brand #ffbc0d for light-mode visibility)
    "NKE":    "#f85c00",  # Nike orange
    "DIS":    "#3b5ce6",  # Disney (brightened from brand #113ccf for dark-mode visibility)
    # ETFs
    "SPY":    "#c0392b",
    "QQQ":    "#2980b9",
    "VTI":    "#27ae60",
    "VUG":    "#16a085",
    "VYM":    "#8e44ad",
    "VT":     "#5d7a9e",  # (darkened from brand #2c3e50 for dark-mode visibility)
    "VGK":    "#2471a3",
    # UK
    "HSBA.L": "#db0011",  # HSBC red
    "BP.L":   "#009900",  # BP green
    "GSK.L":  "#f36633",  # GSK orange
    "AZN.L":  "#1a6ba0",  # AstraZeneca (brightened from brand #003865 for dark-mode visibility)
    "SHEL.L": "#c8a200",  # Shell (darkened from brand #fbce07 for light-mode visibility)
    "LLOY.L": "#1a7a50",  # Lloyds (brightened from brand #024731 for dark-mode visibility)
    "BARC.L": "#00aeef",  # Barclays blue
    # Switzerland
    "UBSG.SW":  "#e30613",  # UBS red
    # Europe
    "SAP.DE":   "#0faaff",  # SAP blue
    "VOW3.DE":  "#1a4fa0",  # VW (brightened from brand #001e50 for dark-mode visibility)
    "BMW.DE":   "#1c69d3",  # BMW blue
    "ASML.AS":  "#009ee2",  # ASML blue
    "NESN.SW":  "#e2001a",  # Nestlé red
    "NOVN.SW":  "#0460a9",  # Novartis blue
    "ROG.SW":   "#009fe3",  # Roche blue
    # Crypto
    "BTC-USD":  "#f7931a",  # Bitcoin orange
    "ETH-USD":  "#627eea",  # Ethereum purple
    "SOL-USD":  "#9945ff",  # Solana purple
    "XRP-USD":  "#346aa9",  # XRP blue
    "BNB-USD":  "#c8960a",  # BNB (darkened from brand #f3ba2f for light-mode visibility)
    # Commodities
    "GC=F":     "#c8a200",  # Gold (darkened from #ffd700 for light-mode visibility)
    "SI=F":     "#808080",  # Silver (mid-grey, visible on both themes)
    "GLD":      "#c8a200",  # Gold ETF
    "SLV":      "#808080",  # Silver ETF
    "CL=F":     "#6b7280",  # Crude Oil (lightened from near-black for dark-mode visibility)
    # REITs & Real Estate
    "VNQ":   "#c17d3c",  # Vanguard warm orange
    "XLRE":  "#b85c2c",  # dark copper
    "PLD":   "#0055a5",  # Prologis blue
    "AMT":   "#d4860b",  # American Tower amber
    "EQIX":  "#e31937",  # Equinix red
    "SPG":   "#5b4fcf",  # Simon Property purple
    "O":     "#2e7d32",  # Realty Income green
    "WELL":  "#0288d1",  # Welltower blue
    "PSA":   "#f57c00",  # Public Storage orange
    "DLR":   "#1565c0",  # Digital Realty blue
    "CBRE":  "#006747",  # CBRE green
    "AVB":   "#7b1fa2",  # AvalonBay purple
    # Bonds & Fixed Income
    "AGG":   "#546e7a",  # blue-grey
    "BND":   "#607d8b",  # steel blue
    "TLT":   "#78909c",  # slate
    "SHY":   "#4fc3f7",  # light blue
    "IEF":   "#039be5",  # medium blue
    "LQD":   "#1976d2",  # investment grade blue
    "HYG":   "#d84315",  # high yield orange-red (higher risk signal)
    "VGIT":  "#0288d1",  # Vanguard intermediate treasury
    "VGLT":  "#01579b",  # Vanguard long treasury deep blue
    "TIP":   "#00796b",  # TIPS teal
    # Emerging Markets
    "EEM":   "#e65100",  # iShares EM orange
    "VWO":   "#c8960a",  # Vanguard EM amber
    "EWJ":   "#bc002d",  # Japan red (flag)
    "EWZ":   "#009c3b",  # Brazil green (flag)
    "FXI":   "#de2910",  # China red (flag)
    "INDA":  "#ff9933",  # India saffron (flag)
    "MCHI":  "#c0392b",  # MSCI China red
    "EWT":   "#1c4da0",  # Taiwan blue
    "EWY":   "#003478",  # South Korea navy
    "VEA":   "#4e6b8c",  # Developed ex-US slate
}