import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px

from src.stocks import (
    get_sp500_stocks, get_ftse100_stocks, get_dax_stocks,
    get_cac40_stocks, get_smi_stocks, get_aex_stocks,
    get_ibex_stocks, get_etfs, get_crypto, get_commodities, TICKER_COLORS
)
from src.fx import get_ticker_currency, get_fx_rate, CURRENCY_SYMBOLS
from src.portfolio import build_portfolio_df, fetch_buy_price, compute_analytics

@st.cache_data(ttl=900)   # 15 minutes — current price data
def fetch_price_history_short(ticker: str) -> pd.DataFrame:
    """Fetch 6-month price history. Cached for 15 minutes."""
    try:
        hist = yf.Ticker(ticker).history(period="6mo")
        hist.index = hist.index.tz_localize(None)
        return hist
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=86400)  # 24 hours — historical chart data
def fetch_price_history_long(ticker: str) -> pd.DataFrame:
    """Fetch full price history. Cached for 24 hours."""
    try:
        hist = yf.Ticker(ticker).history(period="max")
        hist.index = hist.index.tz_localize(None)
        return hist
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=86400)  # 24 hours — fundamental data
def fetch_fundamentals(ticker: str) -> dict:
    """Fetch P/E, dividend yield, and 52-week range. Cached for 24 hours."""
    try:
        info = yf.Ticker(ticker).info
        current  = info.get("currentPrice") or info.get("regularMarketPrice")
        low_52w  = info.get("fiftyTwoWeekLow")
        high_52w = info.get("fiftyTwoWeekHigh")
        pe       = info.get("trailingPE")
        div      = info.get("dividendYield")

        position = None
        if current and low_52w and high_52w and high_52w > low_52w:
            position = round((current - low_52w) / (high_52w - low_52w) * 100, 1)

        return {
            "P/E Ratio":     round(pe, 1)        if pe       else None,
            "Div Yield (%)": round(div * 100, 2)  if div      else None,
            "52W Low":       round(low_52w, 2)    if low_52w  else None,
            "52W High":      round(high_52w, 2)   if high_52w else None,
            "52W Position":  position,
        }
    except Exception:
        return {}


@st.cache_data(ttl=86400)  # 24 hours — analytics price data
def fetch_analytics_history(ticker: str) -> pd.DataFrame:
    """Fetch 1-year price history for analytics. Cached for 24 hours."""
    try:
        hist = yf.Ticker(ticker).history(period="1y")
        hist.index = hist.index.tz_localize(None)
        return hist
    except Exception:
        return pd.DataFrame()

CHART_COLORS = px.colors.qualitative.Plotly

# ──────────────────────────────────────────────
# Page Config
# ──────────────────────────────────────────────
st.set_page_config(page_title="Market Dashboard", layout="wide")

# ──────────────────────────────────────────────
# Global CSS
# ──────────────────────────────────────────────
st.markdown("""
<style>
/* Section headers */
h3 {
    margin-top: 1.8rem !important;
    margin-bottom: 0.8rem !important;
}

/* Metric cards — base style */
[data-testid="metric-container"] {
    background-color: #1a1a1a;
    border: 1px solid #2d2d2d;
    border-radius: 8px;
    padding: 16px 20px;
}

/* Section card containers */
.section-card {
    background-color: #1a1a1a;
    border: 1px solid #2d2d2d;
    border-radius: 8px;
    padding: 20px;
    margin-bottom: 16px;
}

/* KPI metric cards */
.kpi-card {
    background-color: #1a1a1a;
    border-radius: 8px;
    padding: 18px 24px;
    text-align: center;
}
.kpi-label {
    font-size: 13px;
    color: #888;
    margin-bottom: 6px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.kpi-value {
    font-size: 26px;
    font-weight: 600;
    line-height: 1.2;
}
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# Header
# ──────────────────────────────────────────────
col_title, col_currency = st.columns([4, 1])

with col_title:
    st.markdown("""
    <div style="display:flex; align-items:center; gap:12px; margin-bottom:4px;">
        <div style="width:4px; height:40px; background:#4f8ef7; border-radius:2px; flex-shrink:0;"></div>
        <h1 style="margin:0; padding:0;">Market Dashboard</h1>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("Build and track your stock portfolio in real time.")

with col_currency:
    base_currency = st.selectbox(
        "Currency",
        options=list(CURRENCY_SYMBOLS.keys()),
        index=0,
    )

currency_symbol = CURRENCY_SYMBOLS[base_currency]

# ──────────────────────────────────────────────
# Session State
# ──────────────────────────────────────────────
if "portfolio" not in st.session_state:
    st.session_state.portfolio = {}

if "imported" not in st.session_state:
    st.session_state.imported = False

# ──────────────────────────────────────────────
# Import Portfolio
# ──────────────────────────────────────────────
st.caption("Build your own portfolio using the form below, import a saved JSON file, or load the sample portfolio to explore the dashboard.")
col_import, col_sample = st.columns([3, 1], vertical_alignment="bottom")
uploaded_file = col_import.file_uploader("Import Portfolio", type="json")
if col_sample.button("Load Sample Portfolio", use_container_width=True):
    import json, os
    sample_path = os.path.join(os.path.dirname(__file__), "data", "sample_portfolio.json")
    with open(sample_path) as f:
        st.session_state.portfolio = json.load(f)
    st.session_state.imported = False
    st.rerun()

if uploaded_file is not None and not st.session_state.imported:
    try:
        data = pd.read_json(uploaded_file, typ="series").to_dict()
        valid = (
            isinstance(data, dict)
            and all(
                isinstance(ticker, str)
                and isinstance(lots, list)
                and all(
                    isinstance(lot, dict) and {"shares", "buy_price", "purchase_date"}.issubset(lot.keys())
                    for lot in lots
                )
                for ticker, lots in data.items()
            )
        )
        if not valid:
            st.error("Invalid portfolio file. Expected format: {ticker: [{shares, buy_price, purchase_date, ...}]}.")
        else:
            st.session_state.portfolio = data
            st.session_state.imported = True
            st.success("Portfolio imported successfully.")
            st.rerun()
    except Exception:
        st.error("Could not read the file. Make sure it is a valid portfolio JSON export.")

if uploaded_file is None:
    st.session_state.imported = False

# ──────────────────────────────────────────────
# Stock List
# ──────────────────────────────────────────────
@st.cache_data(ttl=86400)
def load_stock_options() -> dict:
    return {
        "S&P 500":  get_sp500_stocks(),
        "FTSE 100": get_ftse100_stocks(),
        "DAX":      get_dax_stocks(),
        "CAC 40":   get_cac40_stocks(),
        "SMI":      get_smi_stocks(),
        "AEX":      get_aex_stocks(),
        "IBEX 35":  get_ibex_stocks(),
        "ETFs":        get_etfs(),
        "Crypto":      get_crypto(),
        "Commodities": get_commodities(),
    }

all_stock_options = load_stock_options()

# ──────────────────────────────────────────────
# Add Position
# ──────────────────────────────────────────────
st.subheader("Add Position")
manual_price = st.session_state.get("manual_price_toggle", False)

# Index selector first so we can adapt the rest of the form to it
col1, col2, col3, col4 = st.columns([2, 2, 2, 1])

with col1:
    index_choice = st.selectbox(
        "Index",
        options=list(all_stock_options.keys()),
        index=0,
    )
    stock_options = all_stock_options[index_choice]
    selected = st.selectbox(
        "Stock",
        options=list(stock_options.keys()),
        index=None,
        placeholder="Search by name or ticker…"
    )

alt_asset = index_choice in ("Crypto", "Commodities")

with col2:
    if alt_asset:
        amount_input = st.number_input(
            f"Amount ({base_currency})",
            min_value=0.0, value=None, step=1.0,
            placeholder="e.g. 5000"
        )
        shares_input = None
    else:
        shares_input = st.number_input(
            "Number of Shares",
            min_value=0.0, value=None, step=1.0,
            placeholder="e.g. 5"
        )
        amount_input = None

with col3:
    if not alt_asset and manual_price:
        buy_price_input = st.number_input(
            f"Average Buy Price ({base_currency})",
            min_value=0.0, value=None, step=0.01,
            placeholder="e.g. 180.00"
        )
        purchase_date = None
    else:
        purchase_date = st.date_input(
            "Purchase Date" + (" (optional)" if alt_asset else ""),
            value=None,
            min_value=pd.Timestamp("1980-01-01").date(),
            max_value=pd.Timestamp.today().date()
        )
        buy_price_input = None

with col4:
    if not alt_asset:
        st.markdown("<div style='margin-top: 36px;'>", unsafe_allow_html=True)
        manual_price = st.checkbox("Enter price manually", key="manual_price_toggle")
        st.markdown("</div>", unsafe_allow_html=True)

if st.button("Add to Portfolio"):
    if selected is None:
        st.warning("Please select a stock.")
    elif not alt_asset and (shares_input is None or shares_input == 0):
        st.warning("Please enter the number of shares.")
    elif alt_asset and (amount_input is None or amount_input == 0):
        st.warning("Please enter the amount.")
    elif not alt_asset and not manual_price and purchase_date is None:
        st.warning("Please select a purchase date or enter a price manually.")
    elif not alt_asset and manual_price and (buy_price_input is None or buy_price_input == 0):
        st.warning("Please enter a valid buy price.")
    else:
        ticker = stock_options[selected]

        if not alt_asset and manual_price:
            buy_price = buy_price_input
        elif purchase_date is not None:
            buy_price = fetch_buy_price(ticker, str(purchase_date))
            if buy_price is None:
                st.error("No price data found for that date. Try a different date.")
        else:
            buy_price = fetch_buy_price(ticker, str(pd.Timestamp.today().date()))
            purchase_date = pd.Timestamp.today().date()

        if buy_price is not None:
            if alt_asset:
                shares = round(amount_input / buy_price, 6)
            else:
                shares = shares_input

            lot = {
                "shares": shares,
                "buy_price": buy_price,
                "purchase_date": str(purchase_date) if purchase_date else None,
                "manual_price": manual_price
            }
            st.session_state.portfolio.setdefault(ticker, []).append(lot)
            st.success(f"Added {shares:g} units of {ticker} at {currency_symbol}{buy_price:,.2f}")

# ──────────────────────────────────────────────
# Portfolio Display
# ──────────────────────────────────────────────
if not st.session_state.portfolio:
    st.stop()

st.divider()
st.subheader("Portfolio Overview")
df = build_portfolio_df(st.session_state.portfolio, base_currency)

if df.empty:
    st.warning("Could not retrieve price data for any positions.")
    st.stop()

# --- KPI Cards ---
total_value  = df["Total Value"].sum()
daily_pnl    = df["Daily P&L"].sum()
n_positions  = len(st.session_state.portfolio)
cost_basis   = (df["Buy Price"] * df["Shares"]).sum()
total_divs   = df["Dividends"].sum()
total_return = total_value + total_divs - cost_basis
total_ret_pct = (total_return / cost_basis * 100) if cost_basis else 0.0

pnl_color    = "#00c853" if daily_pnl    >= 0 else "#ff5252"
pnl_border   = "#00c853" if daily_pnl    >= 0 else "#ff5252"
ret_color    = "#00c853" if total_return >= 0 else "#ff5252"
ret_border   = "#00c853" if total_return >= 0 else "#ff5252"

col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)

with col_m1:
    st.markdown(f"""
    <div class="kpi-card" style="border: 1px solid #2d2d2d;">
        <div class="kpi-label">Total Portfolio Value</div>
        <div class="kpi-value" style="color: white;">{currency_symbol}{total_value:,.2f}</div>
    </div>
    """, unsafe_allow_html=True)

with col_m2:
    st.markdown(f"""
    <div class="kpi-card" style="border: 1px solid {pnl_border};">
        <div class="kpi-label">Daily P&amp;L</div>
        <div class="kpi-value" style="color: {pnl_color};">
            {"+" if daily_pnl >= 0 else ""}{currency_symbol}{daily_pnl:,.2f}
        </div>
    </div>
    """, unsafe_allow_html=True)

with col_m3:
    st.markdown(f"""
    <div class="kpi-card" style="border: 1px solid {ret_border};">
        <div class="kpi-label">Total Return</div>
        <div class="kpi-value" style="color: {ret_color};">
            {"+" if total_return >= 0 else ""}{currency_symbol}{total_return:,.2f}
        </div>
    </div>
    """, unsafe_allow_html=True)

with col_m4:
    st.markdown(f"""
    <div class="kpi-card" style="border: 1px solid {ret_border};">
        <div class="kpi-label">Total Return %</div>
        <div class="kpi-value" style="color: {ret_color};">
            {"+" if total_ret_pct >= 0 else ""}{total_ret_pct:,.2f}%
        </div>
    </div>
    """, unsafe_allow_html=True)

with col_m5:
    st.markdown(f"""
    <div class="kpi-card" style="border: 1px solid #2d2d2d;">
        <div class="kpi-label">Positions</div>
        <div class="kpi-value" style="color: white;">{n_positions}</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<div style='margin-bottom: 16px;'></div>", unsafe_allow_html=True)

# --- Manage Positions ---
col_manage_title, col_clear, col_spacer = st.columns([3, 1, 6], vertical_alignment="bottom")
col_manage_title.subheader("Manage Positions")
if col_clear.button("Clear All", key="clear_portfolio"):
    st.session_state.portfolio = {}
    st.rerun()

for t, lots in list(st.session_state.portfolio.items()):
    for i, lot in enumerate(lots):
        col_name, col_date, col_btn, col_spacer = st.columns([2, 2, 1, 6])
        col_name.write(f"{t} (Lot {i + 1})")
        col_date.write(lot["purchase_date"] or "Manual")
        if col_btn.button("×", key=f"remove_{t}_{i}"):
            st.session_state.portfolio[t].pop(i)
            if not st.session_state.portfolio[t]:
                del st.session_state.portfolio[t]
            st.rerun()

# --- Positions Table with conditional formatting ---
styled_df = df.copy().rename(columns={"Return (%)": "Return", "Weight (%)": "Weight"})

def _color_pnl(val):
    if val > 0:
        return "color: #00c853; font-weight: 500"
    elif val < 0:
        return "color: #ff5252; font-weight: 500"
    return "color: white"

def _fmt_shares(x):
    if x == int(x):
        return f"{int(x):,}"
    return f"{x:g}"

styled = (
    styled_df.set_index(["Ticker", "Lot"])
    .style
    .format({
        "Shares":        _fmt_shares,
        "Buy Price":     lambda x: f"{currency_symbol}{x:,.2f}",
        "Current Price": lambda x: f"{currency_symbol}{x:,.2f}",
        "Total Value":   lambda x: f"{currency_symbol}{x:,.2f}",
        "Dividends":     lambda x: f"{currency_symbol}{x:,.2f}",
        "Daily P&L":     lambda x: f"{currency_symbol}{x:,.2f}",
        "Return":        "{:,.2f}%",
        "Weight":        "{:,.2f}%",
    })
    .map(_color_pnl, subset=["Daily P&L", "Return"])
)

st.dataframe(styled, use_container_width=True, column_config={
    "Shares": st.column_config.TextColumn("Shares", width="small"),
})

# --- Export Portfolio ---
st.download_button(
    label="Export Portfolio",
    data=pd.Series(st.session_state.portfolio).to_json(),
    file_name="portfolio.json",
    mime="application/json"
)

# ──────────────────────────────────────────────
# Risk & Analytics
# ──────────────────────────────────────────────
st.divider()
st.subheader("Risk & Analytics")
st.caption("Based on 12 months of daily closing prices. Sharpe Ratio assumes a 4% annual risk-free rate.")

_tickers = list(st.session_state.portfolio.keys())
_price_data_1y = {t: fetch_analytics_history(t) for t in _tickers}
_spy_data = fetch_analytics_history("SPY")

analytics_df = compute_analytics(st.session_state.portfolio, _price_data_1y, _spy_data)

if not analytics_df.empty:
    st.dataframe(
        analytics_df.set_index("Ticker"),
        use_container_width=True,
        column_config={
            "Volatility":   st.column_config.NumberColumn("Volatility",   format="%.1f%%"),
            "Max Drawdown": st.column_config.NumberColumn("Max Drawdown", format="%.1f%%"),
            "Sharpe Ratio": st.column_config.NumberColumn("Sharpe Ratio", format="%.2f"),
            "Beta":         st.column_config.NumberColumn("Beta",         format="%.2f"),
        },
    )

    col_leg1, col_leg2 = st.columns(2)
    with col_leg1:
        st.caption("📊 **Volatility** — how much the stock price swings in a year. 25% means it typically moves ±25% over 12 months. Higher = more unpredictable.")
        st.caption("📉 **Max Drawdown** — the biggest drop from a peak over the past year. −35% means the price fell 35% from its highest point before recovering.")
    with col_leg2:
        st.caption("⚖️ **Sharpe Ratio** — how much return you earned per unit of risk. Above 1 is good; above 2 is excellent; below 0 means the risk wasn't rewarded.")
        st.caption("📈 **Beta** — how sensitive the stock is to S&P 500 moves. 1.5 = moves 50% more than the market; 0.5 = half as much; below 0 = tends to move opposite.")

    if len(_tickers) >= 2:
        with st.expander("Correlation Matrix"):
            st.caption("How much your positions move together. 1.0 = always move in the same direction; −1.0 = always move opposite; 0 = no relationship. Low correlation between positions helps reduce overall portfolio risk.")
            _returns = {
                t: _price_data_1y[t]["Close"].pct_change().dropna()
                for t in _tickers
                if not _price_data_1y.get(t, pd.DataFrame()).empty
            }
            if len(_returns) >= 2:
                corr_df = pd.DataFrame(_returns).dropna().corr()
                fig_corr = px.imshow(
                    corr_df,
                    color_continuous_scale="RdBu_r",
                    zmin=-1, zmax=1,
                    text_auto=".2f",
                )
                fig_corr.update_layout(template="plotly_dark", margin=dict(t=20))
                st.plotly_chart(fig_corr, use_container_width=True)

    # --- Fundamentals ---
    st.markdown("#### Fundamentals")
    st.caption("Valuation and price range data from the latest available figures.")

    fund_rows = []
    for t in _tickers:
        f = fetch_fundamentals(t)
        if f:
            fund_rows.append({"Ticker": t, **f})

    if fund_rows:
        fund_df = pd.DataFrame(fund_rows).set_index("Ticker")
        st.dataframe(
            fund_df,
            use_container_width=True,
            column_config={
                "P/E Ratio":     st.column_config.NumberColumn("P/E Ratio",    format="%.1f"),
                "Div Yield (%)": st.column_config.NumberColumn("Div Yield (%)", format="%.2f"),
                "52W Low":       st.column_config.NumberColumn("52W Low",      format="%.2f"),
                "52W High":      st.column_config.NumberColumn("52W High",     format="%.2f"),
                "52W Position":  st.column_config.ProgressColumn(
                    "52W Position",
                    min_value=0,
                    max_value=100,
                    format="%.0f%%",
                ),
            },
        )

        col_f1, col_f2 = st.columns(2)
        with col_f1:
            st.caption("💰 **P/E Ratio** — how much investors pay relative to earnings. A P/E of 20 means the stock costs 20× what the company earns per share. Lower can mean better value, but varies by sector.")
            st.caption("💵 **Div Yield** — the annual dividend as a % of the current price. 3% means every $100 invested pays $3/year in dividends.")
        with col_f2:
            st.caption("📏 **52W Low / High** — the lowest and highest price the stock reached over the past year.")
            st.caption("📍 **52W Position** — where the current price sits in the yearly range. 100% = at the yearly high; 0% = at the yearly low.")

# ──────────────────────────────────────────────
# Charts
# ──────────────────────────────────────────────
st.divider()

# --- Portfolio Allocation ---
st.subheader("Portfolio Allocation")

alloc_df = (
    df.groupby("Ticker")["Total Value"]
    .sum()
    .reset_index()
    .assign(**{"Weight (%)": lambda x: (x["Total Value"] / x["Total Value"].sum() * 100).round(2)})
    .sort_values("Weight (%)", ascending=True)
)
bar_colors = [
    TICKER_COLORS.get(t, CHART_COLORS[i % len(CHART_COLORS)])
    for i, t in enumerate(alloc_df["Ticker"])
]
fig_alloc = px.bar(
    alloc_df,
    x="Weight (%)",
    y="Ticker",
    orientation="h",
    color="Ticker",
    color_discrete_sequence=bar_colors,
    text=alloc_df["Weight (%)"].map(lambda v: f"{v:.1f}%"),
)
fig_alloc.update_traces(textposition="outside")
fig_alloc.update_layout(
    xaxis_title="Portfolio Weight (%)",
    yaxis_title=None,
    showlegend=False,
    template="plotly_dark",
    xaxis=dict(range=[0, alloc_df["Weight (%)"].max() * 1.15]),
)
st.plotly_chart(fig_alloc, use_container_width=True)

st.divider()

# --- Normalised Performance Comparison ---
st.subheader("Normalised Performance")
fx_adjust_comparison = st.toggle("Currency-adjusted", key="fx_toggle_comparison")

comparison_data = {}
for t in st.session_state.portfolio:
    hist = fetch_price_history_short(t)
    if hist.empty:
        st.warning(f"Could not load data for {t} — skipping.")
        continue
    ticker_currency = get_ticker_currency(t)
    if fx_adjust_comparison and ticker_currency != base_currency:
        fx_pair = "GBP" if ticker_currency == "GBX" else ticker_currency
        fx_hist = fetch_price_history_short(f"{fx_pair}{base_currency}=X")
        if fx_hist.empty:
            comparison_data[t] = hist["Close"]
            continue
        fx_series = fx_hist["Close"].reindex(hist.index, method="ffill")
        if ticker_currency == "GBX":
            fx_series = fx_series / 100
        comparison_data[t] = hist["Close"] * fx_series
    else:
        comparison_data[t] = hist["Close"]

comparison_df = pd.DataFrame(comparison_data).dropna()
comparison_df = comparison_df / comparison_df.iloc[0] * 100

color_map = {
    t: TICKER_COLORS.get(t, CHART_COLORS[i % len(CHART_COLORS)])
    for i, t in enumerate(comparison_df.columns)
}
title_suffix = f"({base_currency}-adjusted)" if fx_adjust_comparison else "(native currencies)"
fig_comp = px.line(
    comparison_df,
    x=comparison_df.index,
    y=comparison_df.columns,
    color_discrete_map=color_map,
)
fig_comp.update_layout(
    xaxis_title="Date",
    yaxis_title=f"Normalised Price (Base 100)  —  6 months  {title_suffix}",
    legend_title="Ticker",
    template="plotly_dark",
)
fig_comp.add_hline(y=100, line_dash="dash", line_color="gray")
st.plotly_chart(fig_comp, use_container_width=True)

st.divider()

# --- Price History ---
st.subheader("Price History")

col_to, col_fx, _ = st.columns([2, 2, 7])
with col_to:
    date_to = st.date_input("To", value=pd.Timestamp.today())
with col_fx:
    st.write(" ")
    st.write(" ")
    fx_adjust_history = st.toggle("Currency-adjusted", key="fx_toggle_history")

for idx, (t, lots) in enumerate(st.session_state.portfolio.items()):
    hist = fetch_price_history_long(t)
    if hist.empty:
        st.warning(f"No price history available for {t}.")
        continue

    ticker_currency = get_ticker_currency(t)

    if fx_adjust_history and ticker_currency != base_currency:
        fx_pair = "GBP" if ticker_currency == "GBX" else ticker_currency
        fx_hist = fetch_price_history_long(f"{fx_pair}{base_currency}=X")
        if fx_hist.empty:
            hist_converted = hist.copy()
            y_label = f"Price ({ticker_currency})"
        else:
            fx_series = fx_hist["Close"].reindex(hist.index, method="ffill")
            if ticker_currency == "GBX":
                fx_series = fx_series / 100
            hist_converted = hist.copy()
            hist_converted["Close"] = hist["Close"] * fx_series
            y_label = f"Price ({base_currency})"
    else:
        hist_converted = hist.copy()
        y_label = f"Price ({ticker_currency})"

    dates = [lot["purchase_date"] for lot in lots if lot["purchase_date"]]
    default_from = (
        min(pd.Timestamp(d) for d in dates) - pd.DateOffset(months=2)
        if dates else pd.Timestamp.today() - pd.DateOffset(months=6)
    )

    line_color = TICKER_COLORS.get(t, CHART_COLORS[idx % len(CHART_COLORS)])
    title_suffix = f"({base_currency}-adjusted)" if fx_adjust_history else f"({ticker_currency})"
    with st.expander(f"{t} — Price History {title_suffix}", expanded=False):
        fig_hist = px.line(
            hist_converted,
            x=hist_converted.index,
            y="Close",
            color_discrete_sequence=[line_color],
        )
        fig_hist.update_layout(
            xaxis_title="Date",
            yaxis_title=y_label,
            xaxis_range=[str(default_from.date()), str(date_to)],
            showlegend=False,
            template="plotly_dark",
        )

        for i, lot in enumerate(lots):
            if fx_adjust_history:
                fx_rate = get_fx_rate(ticker_currency, base_currency)
                buy_price_display = round(lot["buy_price"] * fx_rate, 2)
                buy_label = f"Lot {i + 1} Buy {currency_symbol}{buy_price_display}"
            else:
                buy_price_display = lot["buy_price"]
                buy_label = f"Lot {i + 1} Buy {buy_price_display}"

            fig_hist.add_hline(
                y=buy_price_display,
                line_dash="dash",
                line_color="yellow",
                annotation_text=buy_label,
                annotation_position="top left"
            )
            if lot["purchase_date"]:
                fig_hist.add_vline(
                    x=str(pd.Timestamp(lot["purchase_date"]).date()),
                    line_dash="dash",
                    line_color="gray"
                )

        st.plotly_chart(fig_hist, use_container_width=True)
