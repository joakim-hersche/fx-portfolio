import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px

from src.stocks import (
    get_sp500_stocks, get_ftse100_stocks, get_dax_stocks,
    get_cac40_stocks, get_smi_stocks, get_aex_stocks,
    get_ibex_stocks, get_etfs
)
from src.fx import get_ticker_currency, get_fx_rate, CURRENCY_SYMBOLS
from src.portfolio import build_portfolio_df, fetch_buy_price

# ──────────────────────────────────────────────
# Page Config
# ──────────────────────────────────────────────
st.set_page_config(page_title="Market Dashboard", layout="wide")

# ──────────────────────────────────────────────
# Header
# ──────────────────────────────────────────────
col_title, col_currency = st.columns([4, 1])

with col_title:
    st.title("Market Dashboard")
    st.markdown("Build and track your stock portfolio in real time.")

with col_currency:
    st.write(" ")
    st.write(" ")
    base_currency = st.selectbox(
        "Display Currency",
        options=list(CURRENCY_SYMBOLS.keys()),
        index=0,
        label_visibility="collapsed"
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
    st.session_state.portfolio = pd.read_json(uploaded_file, typ="series").to_dict()
    st.session_state.imported = True
    st.success("Portfolio imported successfully.")
    st.rerun()

if uploaded_file is None:
    st.session_state.imported = False

# ──────────────────────────────────────────────
# Stock List
# ──────────────────────────────────────────────
@st.cache_data(ttl=86400)
def load_stock_options() -> dict:
    return {
        **get_sp500_stocks(),
        **get_ftse100_stocks(),
        **get_dax_stocks(),
        **get_cac40_stocks(),
        **get_smi_stocks(),
        **get_aex_stocks(),
        **get_ibex_stocks(),
        **get_etfs()
    }

stock_options = load_stock_options()

# ──────────────────────────────────────────────
# Portfolio Input
# ──────────────────────────────────────────────
st.subheader("Add Position")
manual_price = st.session_state.get("manual_price_toggle", False)

col1, col2, col3, col4 = st.columns(4)

with col1:
    selected = st.selectbox(
        "Select a Stock",
        options=list(stock_options.keys()),
        index=None,
        placeholder="e.g. Apple Inc. (AAPL)"
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
            st.success(f"Added {shares} shares of {ticker} at {currency_symbol}{buy_price}")

# ──────────────────────────────────────────────
# Portfolio Display
# ──────────────────────────────────────────────
if not st.session_state.portfolio:
    st.stop()

st.subheader("Portfolio Overview")
df = build_portfolio_df(st.session_state.portfolio, base_currency)

if df.empty:
    st.warning("Could not retrieve price data for any positions.")
    st.stop()

# --- Summary Metrics ---
col_m1, col_m2, col_m3 = st.columns(3)
col_m1.metric("Total Portfolio Value", f"{currency_symbol}{df['Total Value'].sum():,.2f}")
col_m2.metric("Daily P&L", f"{currency_symbol}{df['Daily P&L'].sum():,.2f}")
col_m3.metric("Number of Positions", len(st.session_state.portfolio))

# --- Manage Positions ---
st.subheader("Manage Positions")
for t, lots in list(st.session_state.portfolio.items()):
    for i, lot in enumerate(lots):
        col_name, col_date, col_btn, col_spacer = st.columns([2, 2, 1, 6])
        col_name.write(f"{t} (Lot {i + 1})")
        col_date.write(lot["purchase_date"] or "Manual")
        if col_btn.button("Remove", key=f"remove_{t}_{i}"):
            st.session_state.portfolio[t].pop(i)
            if not st.session_state.portfolio[t]:
                del st.session_state.portfolio[t]
            st.rerun()

# --- Format columns for display ---
display_df = df.copy()
for col in ["Buy Price", "Current Price", "Total Value", "Daily P&L"]:
    display_df[col] = display_df[col].apply(lambda x: f"{currency_symbol}{x:,.2f}")
display_df["Return (%)"] = display_df["Return (%)"].apply(lambda x: f"{x:,.2f}%")
display_df["Weight (%)"] = display_df["Weight (%)"].apply(lambda x: f"{x:,.2f}%")
display_df = display_df.rename(columns={"Return (%)": "Return", "Weight (%)": "Weight"})

st.dataframe(display_df.set_index("Ticker"), use_container_width=True)

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

# --- Portfolio Allocation ---
fig = px.pie(df, values="Total Value", names="Ticker", title="Portfolio Allocation")
fig.update_traces(textposition="inside", textinfo="percent+label")
st.plotly_chart(fig, use_container_width=True)

# --- Normalised Performance Comparison ---
st.subheader("Normalised Performance Comparison")
fx_adjust_comparison = st.toggle("Currency-adjusted", key="fx_toggle_comparison")

comparison_data = {}
for t in st.session_state.portfolio:
    hist = yf.Ticker(t).history(period="6mo")
    hist.index = hist.index.tz_localize(None)

    ticker_currency = get_ticker_currency(t)

    if fx_adjust_comparison and ticker_currency != base_currency:
        fx_pair = "GBP" if ticker_currency == "GBX" else ticker_currency
        fx_hist = yf.Ticker(f"{fx_pair}{base_currency}=X").history(period="6mo")
        fx_hist.index = fx_hist.index.tz_localize(None)
        fx_series = fx_hist["Close"].reindex(hist.index, method="ffill")
        if ticker_currency == "GBX":
            fx_series = fx_series / 100
        comparison_data[t] = hist["Close"] * fx_series
    else:
        comparison_data[t] = hist["Close"]

comparison_df = pd.DataFrame(comparison_data).dropna()
comparison_df = comparison_df / comparison_df.iloc[0] * 100

title_suffix = f"({base_currency}-adjusted)" if fx_adjust_comparison else "(native currencies)"
fig = px.line(
    comparison_df, x=comparison_df.index, y=comparison_df.columns,
    title=f"Normalised Performance over 6 months — {title_suffix}"
)
fig.update_layout(xaxis_title="Date", yaxis_title="Normalised Price (Base 100)")
fig.add_hline(y=100, line_dash="dash", line_color="gray")
st.plotly_chart(fig, use_container_width=True)

# --- Price History ---
st.subheader("Price History")

col_to, col_fx, _ = st.columns([2, 2, 7])
with col_to:
    date_to = st.date_input("To", value=pd.Timestamp.today())
with col_fx:
    st.write(" ")
    st.write(" ")
    fx_adjust_history = st.toggle("Currency-adjusted", key="fx_toggle_history")

for t, lots in st.session_state.portfolio.items():
    hist = yf.Ticker(t).history(period="max")
    hist.index = hist.index.tz_localize(None)

    ticker_currency = get_ticker_currency(t)

    if fx_adjust_history and ticker_currency != base_currency:
        fx_pair = "GBP" if ticker_currency == "GBX" else ticker_currency
        fx_hist = yf.Ticker(f"{fx_pair}{base_currency}=X").history(period="max")
        fx_hist.index = fx_hist.index.tz_localize(None)
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

    title_suffix = f"({base_currency}-adjusted)" if fx_adjust_history else f"({ticker_currency})"
    fig = px.line(
        hist_converted, x=hist_converted.index, y="Close",
        title=f"{t} — Price History {title_suffix}"
    )
    fig.update_layout(
        xaxis_title="Date",
        yaxis_title=y_label,
        xaxis_range=[str(default_from.date()), str(date_to)]
    )

    for i, lot in enumerate(lots):
        if fx_adjust_history:
            fx_rate = get_fx_rate(ticker_currency, base_currency)
            buy_price_display = round(lot["buy_price"] * fx_rate, 2)
            buy_label = f"Lot {i + 1} Buy {currency_symbol}{buy_price_display}"
        else:
            buy_price_display = lot["buy_price"]
            buy_label = f"Lot {i + 1} Buy {buy_price_display}"

        fig.add_hline(
            y=buy_price_display,
            line_dash="dash",
            line_color="yellow",
            annotation_text=buy_label,
            annotation_position="top left"
        )
        if lot["purchase_date"]:
            fig.add_vline(
                x=str(pd.Timestamp(lot["purchase_date"]).date()),
                line_dash="dash",
                line_color="gray"
            )

    st.plotly_chart(fig, use_container_width=True)