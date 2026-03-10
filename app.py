import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from src.stocks import (
    get_sp500_stocks, get_ftse100_stocks, get_dax_stocks,
    get_cac40_stocks, get_smi_stocks, get_aex_stocks,
    get_ibex_stocks, get_etfs
)

# --- Page Config ---
st.set_page_config(page_title="Market Dashboard", layout="wide")
st.title("Market Dashboard")
st.markdown("Build and track your stock portfolio in real time.")

# --- Session State ---
if "portfolio" not in st.session_state:
    st.session_state.portfolio = {}

if "imported" not in st.session_state:
    st.session_state.imported = False

# --- Import Portfolio ---
uploaded_file = st.file_uploader("Import Portfolio", type="json")
if uploaded_file is not None and not st.session_state.imported:
    imported = pd.read_json(uploaded_file, typ="series").to_dict()
    st.session_state.portfolio = imported
    st.session_state.imported = True
    st.success("Portfolio imported successfully.")
    st.rerun()

if uploaded_file is None:
    st.session_state.imported = False

# --- Stock List ---
stock_options = {
    **get_sp500_stocks(),
    **get_ftse100_stocks(),
    **get_dax_stocks(),
    **get_cac40_stocks(),
    **get_smi_stocks(),
    **get_aex_stocks(),
    **get_ibex_stocks(),
    **get_etfs()
}

# --- Portfolio Input ---
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
    shares = st.number_input("Number of Shares", min_value=0.0, value=None, step=1.0, placeholder="e.g. 5")
with col3:
    if manual_price:
        buy_price_input = st.number_input("Average Buy Price (USD)", min_value=0.0, value=None, step=0.01, placeholder="e.g. 180.00")
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

add = st.button("Add to Portfolio")

if add:
    if selected is None or shares is None or shares == 0:
        st.warning("Please fill in all fields.")
    elif not manual_price and purchase_date is None:
        st.warning("Please select a purchase date or enter a price manually.")
    elif manual_price and (buy_price_input is None or buy_price_input == 0):
        st.warning("Please enter a valid buy price.")
    else:
        ticker = stock_options[selected]
        buy_price = None

        if manual_price:
            buy_price = buy_price_input
        else:
            hist = yf.Ticker(ticker).history(
                start=str(purchase_date),
                end=str((pd.Timestamp(str(purchase_date)) + pd.DateOffset(days=7)).date())
            )
            if hist.empty:
                st.error("No price data found for that date. Try a different date.")
            else:
                buy_price = round(hist["Close"].iloc[0], 2)

        if buy_price is not None:
            lot = {
                "shares": shares,
                "buy_price": buy_price,
                "purchase_date": str(purchase_date) if purchase_date else None,
                "manual_price": manual_price
            }
            if ticker not in st.session_state.portfolio:
                st.session_state.portfolio[ticker] = []
            st.session_state.portfolio[ticker].append(lot)
            st.success(f"Added {shares} shares of {ticker} at ${buy_price}")

# --- Display Portfolio ---
if st.session_state.portfolio:
    st.subheader("Portfolio Overview")

    rows = []
    for t, lots in st.session_state.portfolio.items():
        data = yf.Ticker(t).history(period="5d")

        if len(data) < 2:
            continue

        current_price = data["Close"].iloc[-1]
        prev_price = data["Close"].iloc[-2]

        for i, lot in enumerate(lots):
            s = lot["shares"]
            buy_price = lot["buy_price"]
            daily_pnl = (current_price - prev_price) * s
            total_value = current_price * s
            total_return = ((current_price - buy_price) / buy_price * 100)

            rows.append({
                "Ticker": t,
                "Lot": i + 1,
                "Shares": s,
                "Buy Price": round(buy_price, 2),
                "Purchase Date": lot["purchase_date"] if lot["purchase_date"] else "Manual",
                "Current Price": round(current_price, 2),
                "Total Value": round(total_value, 2),
                "Daily P&L": round(daily_pnl, 2),
                "Return (%)": round(total_return, 2)
            })

    df = pd.DataFrame(rows)
    df["Weight (%)"] = (df["Total Value"] / df["Total Value"].sum() * 100).round(2)

    # --- Summary Metrics ---
    total_portfolio_value = df["Total Value"].sum()
    total_daily_pnl = df["Daily P&L"].sum()

    metric1, metric2, metric3 = st.columns(3)
    metric1.metric("Total Portfolio Value", f"${total_portfolio_value:,.2f}")
    metric2.metric("Daily P&L", f"${total_daily_pnl:,.2f}")
    metric3.metric("Number of Positions", len(st.session_state.portfolio))

    # --- Manage Positions ---
    st.subheader("Manage Positions")
    for t, lots in list(st.session_state.portfolio.items()):
        for i, lot in enumerate(lots):
            col_name, col_date, col_btn, col_spacer = st.columns([2, 2, 1, 6])
            col_name.write(f"{t} (Lot {i + 1})")
            col_date.write(lot["purchase_date"] if lot["purchase_date"] else "Manual")
            if col_btn.button("Remove", key=f"remove_{t}_{i}"):
                st.session_state.portfolio[t].pop(i)
                if not st.session_state.portfolio[t]:
                    del st.session_state.portfolio[t]
                st.rerun()

    st.dataframe(df.set_index("Ticker"), use_container_width=True)

    # --- Export Portfolio ---
    portfolio_json = pd.Series(st.session_state.portfolio).to_json()
    st.download_button(
        label="Export Portfolio",
        data=portfolio_json,
        file_name="portfolio.json",
        mime="application/json"
    )

    # --- Portfolio Weights Pie Chart ---
    fig = px.pie(df, values="Total Value", names="Ticker", title="Portfolio Allocation")
    fig.update_traces(textposition="inside", textinfo="percent+label")
    st.plotly_chart(fig, use_container_width=True)

    # --- Normalised Comparison Chart ---
    st.subheader("Normalised Performance Comparison")

    comparison_data = {}
    for t in st.session_state.portfolio:
        hist = yf.Ticker(t).history(period="6mo")
        hist.index = hist.index.tz_localize(None)
        comparison_data[t] = hist["Close"]

    comparison_df = pd.DataFrame(comparison_data)
    comparison_df = comparison_df / comparison_df.iloc[0] * 100

    fig = px.line(comparison_df, x=comparison_df.index, y=comparison_df.columns,
                  title="Normalised Performance over 6 months (Base 100)")
    fig.update_layout(xaxis_title="Date", yaxis_title="Normalised Price (Base 100)")
    fig.add_hline(y=100, line_dash="dash", line_color="gray")
    st.plotly_chart(fig, use_container_width=True)

    # --- Price History Charts ---
    st.subheader("Price History")

    col_to, _ = st.columns(2)
    with col_to:
        date_to = st.date_input("To", value=pd.Timestamp.today())

    for t, lots in st.session_state.portfolio.items():
        hist = yf.Ticker(t).history(period="max")
        hist.index = hist.index.tz_localize(None)

        dates = [lot["purchase_date"] for lot in lots if lot["purchase_date"]]
        if dates:
            earliest = min(pd.Timestamp(d) for d in dates)
            default_from = earliest - pd.DateOffset(months=2)
        else:
            default_from = pd.Timestamp.today() - pd.DateOffset(months=6)

        fig = px.line(hist, x=hist.index, y="Close", title=f"{t} — Price History")
        fig.update_layout(
            xaxis_title="Date",
            yaxis_title="Price (USD)",
            xaxis_range=[str(default_from.date()), str(date_to)]
        )

        for i, lot in enumerate(lots):
            fig.add_hline(
                y=lot["buy_price"],
                line_dash="dash",
                line_color="yellow",
                annotation_text=f"Lot {i + 1} Buy ${lot['buy_price']}",
                annotation_position="top left"
            )
            if lot["purchase_date"]:
                fig.add_vline(
                    x=str(pd.Timestamp(lot["purchase_date"]).date()),
                    line_dash="dash",
                    line_color="gray"
                )

        st.plotly_chart(fig, use_container_width=True)
