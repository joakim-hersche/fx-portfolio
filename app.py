import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from src.stocks import get_sp500_stocks, get_european_stocks, get_etfs

# --- Stock List ---
stock_options = {
    **get_sp500_stocks(),
    **get_european_stocks(),
    **get_etfs()
}

# --- Page Config ---
st.set_page_config(page_title="Market Dashboard", layout="wide")
st.title("Market Dashboard")
st.markdown("Build and track your stock portfolio in real time.")

# --- Session State ---
if "portfolio" not in st.session_state:
    st.session_state.portfolio = {}

# --- Stock List ---
stock_options = get_sp500_stocks()

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
        purchase_date = st.date_input("Purchase Date", value=None)
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

        if manual_price:
            buy_price = buy_price_input
        else:
            hist = yf.Ticker(ticker).history(start=str(purchase_date), period="5d")
            if hist.empty:
                st.error("No price data found for that date. Try a different date.")
            else:
                buy_price = round(hist["Close"].iloc[0], 2)

        st.session_state.portfolio[ticker] = {
            "shares": shares,
            "buy_price": buy_price,
            "purchase_date": str(purchase_date) if purchase_date else None
        }
        st.success(f"Added {shares} shares of {ticker} at ${buy_price}")

# --- Display Portfolio ---
if st.session_state.portfolio:
    st.subheader("Portfolio Overview")

    rows = []
    for t, position in st.session_state.portfolio.items():
        data = yf.Ticker(t).history(period="5d")

        if len(data) < 2:
            continue

        s = position["shares"]
        buy_price = position["buy_price"]
        current_price = data["Close"].iloc[-1]
        prev_price = data["Close"].iloc[-2]
        daily_pnl = (current_price - prev_price) * s
        total_value = current_price * s
        total_return = ((current_price - buy_price) / buy_price * 100)

        rows.append({
            "Ticker": t,
            "Shares": s,
            "Buy Price": round(buy_price, 2),
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
    metric3.metric("Number of Positions", len(df))

    # --- Manage Positions ---
    st.subheader("Manage Positions")
    for t in list(st.session_state.portfolio.keys()):
        col_name, col_btn, col_spacer = st.columns([2, 1, 8])
        col_name.write(t)
        if col_btn.button("Remove", key=f"remove_{t}"):
            del st.session_state.portfolio[t]
            st.rerun()

    st.dataframe(df.set_index("Ticker"), use_container_width=True)

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

    col_from, col_to = st.columns(2)
    with col_from:
        date_from = st.date_input("From", value=pd.Timestamp.today() - pd.DateOffset(months=6))
    with col_to:
        date_to = st.date_input("To", value=pd.Timestamp.today())

    for t in st.session_state.portfolio:
        hist = yf.Ticker(t).history(period="max")
        hist.index = hist.index.tz_localize(None)

        position = st.session_state.portfolio[t]
        buy_price = position["buy_price"]

        fig = px.line(hist, x=hist.index, y="Close", title=f"{t} — Price History")
        fig.update_layout(
            xaxis_title="Date",
            yaxis_title="Price (USD)",
            xaxis_range=[str(date_from), str(date_to)]
        )

        fig.add_hline(
            y=buy_price,
            line_dash="dash",
            line_color="yellow",
            annotation_text=f"Buy Price ${buy_price}",
            annotation_position="top left"
        )

        purchase_date = position.get("purchase_date")
        if purchase_date:
            fig.add_vline(
                x=str(pd.Timestamp(purchase_date).date()),
                line_dash="dash",
                line_color="gray"
            )

        st.plotly_chart(fig, use_container_width=True)