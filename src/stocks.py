import pandas as pd
import requests

def get_sp500_stocks():
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    table = pd.read_html(response.text)[0]
    
    stocks = {}
    for _, row in table.iterrows():
        ticker = row["Symbol"]
        name = row["Security"]
        stocks[f"{name} ({ticker})"] = ticker
    
    return stocks

def get_european_stocks():
    return {
        # UK
        "HSBC Holdings (HSBA.L)": "HSBA.L",
        "BP (BP.L)": "BP.L",
        "Shell (SHEL.L)": "SHEL.L",
        "AstraZeneca (AZN.L)": "AZN.L",
        "Unilever (ULVR.L)": "ULVR.L",
        "Barclays (BARC.L)": "BARC.L",
        "Rolls-Royce (RR.L)": "RR.L",
        "GSK (GSK.L)": "GSK.L",
        "Diageo (DGE.L)": "DGE.L",
        "Lloyds Banking Group (LLOY.L)": "LLOY.L",
        # Germany
        "SAP (SAP.DE)": "SAP.DE",
        "Siemens (SIE.DE)": "SIE.DE",
        "Volkswagen (VOW3.DE)": "VOW3.DE",
        "BMW (BMW.DE)": "BMW.DE",
        "Allianz (ALV.DE)": "ALV.DE",
        "Deutsche Bank (DBK.DE)": "DBK.DE",
        "Adidas (ADS.DE)": "ADS.DE",
        "BASF (BAS.DE)": "BAS.DE",
        "Mercedes-Benz (MBG.DE)": "MBG.DE",
        "Deutsche Telekom (DTE.DE)": "DTE.DE",
        # France
        "LVMH (MC.PA)": "MC.PA",
        "TotalEnergies (TTE.PA)": "TTE.PA",
        "Sanofi (SAN.PA)": "SAN.PA",
        "BNP Paribas (BNP.PA)": "BNP.PA",
        "Airbus (AIR.PA)": "AIR.PA",
        "L'Oreal (OR.PA)": "OR.PA",
        "Hermes (RMS.PA)": "RMS.PA",
        "AXA (CS.PA)": "CS.PA",
        "Schneider Electric (SU.PA)": "SU.PA",
        # Switzerland
        "Nestle (NESN.SW)": "NESN.SW",
        "Novartis (NOVN.SW)": "NOVN.SW",
        "Roche (ROG.SW)": "ROG.SW",
        "UBS (UBSG.SW)": "UBSG.SW",
        "ABB (ABBN.SW)": "ABBN.SW",
        # Netherlands
        "ASML (ASML.AS)": "ASML.AS",
        "ING Group (INGA.AS)": "INGA.AS",
        "Heineken (HEIA.AS)": "HEIA.AS",
        # Sweden
        "Spotify (SPOT)": "SPOT",
        "Volvo (VOLV-B.ST)": "VOLV-B.ST",
        "H&M (HM-B.ST)": "HM-B.ST",
        # Spain
        "Santander (SAN.MC)": "SAN.MC",
        "Inditex/Zara (ITX.MC)": "ITX.MC",
        "BBVA (BBVA.MC)": "BBVA.MC",
    }

def get_etfs():
    return {
        # US ETFs
        "S&P 500 ETF (SPY)": "SPY",
        "Nasdaq 100 ETF (QQQ)": "QQQ",
        "Total Market ETF (VTI)": "VTI",
        "Growth ETF (VUG)": "VUG",
        "Dividend ETF (VYM)": "VYM",
        # European ETFs
        "iShares Core MSCI Europe (IMAE.AS)": "IMAE.AS",
        "Vanguard FTSE Europe (VGK)": "VGK",
        "iShares STOXX Europe 600 (EXSA.DE)": "EXSA.DE",
        # Global ETFs
        "iShares MSCI World (IWDA.AS)": "IWDA.AS",
        "Vanguard Total World (VT)": "VT",
    }