import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px

from src.stocks import (
    get_sp500_stocks, get_ftse100_stocks, get_dax_stocks,
    get_cac40_stocks, get_smi_stocks, get_aex_stocks,
    get_ibex_stocks, get_etfs, TICKER_COLORS
)
from src.fx import get_ticker_currency, get_fx_rate, CURRENCY_SYMBOLS
from src.portfolio import build_portfolio_df, fetch_buy_price

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
uploaded_file = st.file_uploader("Import Portfolio", type="json")

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
        "ETFs":     get_etfs(),
    }

all_stock_options = load_stock_options()

# ──────────────────────────────────────────────
# Add Position
# ──────────────────────────────────────────────
st.subheader("Add Position")
manual_price = st.session_state.get("manual_price_toggle", False)

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
with col2:
    shares = st.number_input(
        "Number of Shares",
        min_value=0.0, value=None, step=1.0,
        placeholder="e.g. 5"
    )
with col3:
    if manual_price:
        buy_price_input = st.number_input(
            f"Average Buy Price ({base_currency})",
            min_value=0.0, value=None, step=0.01,
            placeholder="e.g. 180.00"
        )
        purchase_date = None
    else:
        purchase_date = st.date_input(
            "Purchase Date",
            value=None,
            min_value=pd.Timestamp("1980-01-01").date(),
            max_value=pd.Timestamp.today().date()
        )
        buy_price_input = None
with col4:
    st.markdown("<div style='margin-top: 36px;'>", unsafe_allow_html=True)
    manual_price = st.checkbox("Enter price manually", key="manual_price_toggle")
    st.markdown("</div>", unsafe_allow_html=True)

if st.button("Add to Portfolio"):
    if selected is None or shares is None or shares == 0:
        st.warning("Please fill in all fields.")
    elif not manual_price and purchase_date is None:
        st.warning("Please select a purchase date or enter a price manually.")
    elif manual_price and (buy_price_input is None or buy_price_input == 0):
        st.warning("Please enter a valid buy price.")
    else:
        ticker = stock_options[selected]

        if manual_price:
            buy_price = buy_price_input
        else:
            buy_price = fetch_buy_price(ticker, str(purchase_date))
            if buy_price is None:
                st.error("No price data found for that date. Try a different date.")

        if buy_price is not None:
            lot = {
                "shares": shares,
                "buy_price": buy_price,
                "purchase_date": str(purchase_date) if purchase_date else None,
                "manual_price": manual_price
            }
            st.session_state.portfolio.setdefault(ticker, []).append(lot)
            st.success(f"Added {shares:g} shares of {ticker} at {currency_symbol}{buy_price:,.2f}")

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
total_value = df["Total Value"].sum()
daily_pnl   = df["Daily P&L"].sum()
n_positions = len(st.session_state.portfolio)

pnl_color  = "#00c853" if daily_pnl >= 0 else "#ff5252"
pnl_border = "#00c853" if daily_pnl >= 0 else "#ff5252"

col_m1, col_m2, col_m3 = st.columns(3)

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

styled = (
    styled_df.set_index(["Ticker", "Lot"])
    .style
    .format({
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

st.dataframe(styled, use_container_width=True)

# --- Export Portfolio ---
st.download_button(
    label="Export Portfolio",
    data=pd.Series(st.session_state.portfolio).to_json(),
    file_name="portfolio.json",
    mime="application/json"
)

# ──────────────────────────────────────────────
# Charts
# ──────────────────────────────────────────────
st.divider()

# --- Portfolio Allocation ---
st.subheader("Portfolio Allocation")
unique_tickers = list(dict.fromkeys(df["Ticker"]))
pie_colors = [
    TICKER_COLORS.get(t, CHART_COLORS[i % len(CHART_COLORS)])
    for i, t in enumerate(unique_tickers)
]
fig_pie = px.pie(
    df,
    values="Total Value",
    names="Ticker",
    color_discrete_sequence=pie_colors,
)
fig_pie.update_traces(textposition="inside", textinfo="percent+label")
fig_pie.update_layout(showlegend=True)
st.plotly_chart(fig_pie, use_container_width=True)

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
