import json
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import os

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
    """Fetch P/E, dividend yield, and 1-year range. Cached for 24 hours."""
    try:
        info = yf.Ticker(ticker).info
        current  = info.get("currentPrice") or info.get("regularMarketPrice")
        low_1y   = info.get("fiftyTwoWeekLow")
        high_1y  = info.get("fiftyTwoWeekHigh")
        pe       = info.get("trailingPE")
        div      = info.get("dividendYield")

        position = None
        if current and low_1y and high_1y and high_1y > low_1y:
            position = round((current - low_1y) / (high_1y - low_1y) * 100, 1)

        return {
            "P/E Ratio":      round(pe, 1)       if pe      else None,
            "Div Yield (%)":  round(div * 100, 2) if div and div < 1 else (round(div, 2) if div else None),
            "1-Year Low":     round(low_1y, 2)    if low_1y  else None,
            "1-Year High":    round(high_1y, 2)   if high_1y else None,
            "1-Year Position": position,
        }
    except Exception:
        return {}


@st.cache_data(ttl=86400)  # 24 hours — company name
def fetch_company_name(ticker: str) -> str:
    """Fetch short company name. Falls back to ticker on failure."""
    try:
        info = yf.Ticker(ticker).info
        return info.get("shortName") or info.get("longName") or ticker
    except Exception:
        return ticker


@st.cache_data(ttl=86400)  # 24 hours — analytics price data
def fetch_analytics_history(ticker: str) -> pd.DataFrame:
    """Fetch 1-year price history for analytics. Cached for 24 hours."""
    try:
        hist = yf.Ticker(ticker).history(period="1y")
        hist.index = hist.index.tz_localize(None)
        return hist
    except Exception:
        return pd.DataFrame()


# Fallback colors for tickers without a brand color.
# Deliberately avoids red and green so bars can't be misread as gain/loss signals.
CHART_COLORS = [
    "#4a90d9",  # steel blue
    "#7b5ea7",  # purple
    "#17becf",  # teal
    "#f0a500",  # amber
    "#5c7cfa",  # indigo
    "#00b4d8",  # sky blue
    "#e6a817",  # golden
    "#9467bd",  # medium purple
    "#74c0fc",  # light blue
    "#da77f2",  # lavender
]

# ──────────────────────────────────────────────
# Page Config
# ──────────────────────────────────────────────
st.set_page_config(page_title="Market Dashboard", layout="wide")

# ──────────────────────────────────────────────
# Global CSS
# ──────────────────────────────────────────────
st.markdown("""
<style>
h3 {
    margin-top: 1.8rem !important;
    margin-bottom: 0.8rem !important;
}
[data-testid="metric-container"] {
    background-color: var(--secondary-background-color);
    border: 1px solid rgba(128,128,128,0.3);
    border-radius: 8px;
    padding: 16px 20px;
}
.kpi-card {
    background-color: var(--secondary-background-color);
    border-radius: 8px;
    padding: 18px 24px;
    text-align: center;
}
.kpi-label {
    font-size: 13px;
    color: var(--text-color);
    opacity: 0.6;
    margin-bottom: 6px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.kpi-value {
    font-size: 26px;
    font-weight: 600;
    line-height: 1.2;
}
.section-intro {
    color: var(--text-color);
    opacity: 0.7;
    font-size: 14px;
    margin-bottom: 12px;
}
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# Session State  (must run before any widgets)
# ──────────────────────────────────────────────

if "portfolio" not in st.session_state:
    st.session_state.portfolio = {}

if "currency" not in st.session_state:
    st.session_state.currency = list(CURRENCY_SYMBOLS.keys())[0]

if "imported" not in st.session_state:
    st.session_state.imported = False

if "confirm_clear" not in st.session_state:
    st.session_state.confirm_clear = False

if "pending_remove" not in st.session_state:
    st.session_state.pending_remove = False

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
    st.markdown("Track your stock portfolio in real time.")

with col_currency:
    base_currency = st.selectbox(
        "Currency",
        options=list(CURRENCY_SYMBOLS.keys()),
        key="currency",
    )

currency_symbol = CURRENCY_SYMBOLS[base_currency]

# ──────────────────────────────────────────────
# Stock List
# ──────────────────────────────────────────────
@st.cache_data(ttl=86400)
def load_stock_options() -> dict:
    return {
        "S&P 500":     get_sp500_stocks(),
        "FTSE 100":    get_ftse100_stocks(),
        "DAX":         get_dax_stocks(),
        "CAC 40":      get_cac40_stocks(),
        "SMI":         get_smi_stocks(),
        "AEX":         get_aex_stocks(),
        "IBEX 35":     get_ibex_stocks(),
        "ETFs":        get_etfs(),
        "Crypto":      get_crypto(),
        "Commodities": get_commodities(),
    }

all_stock_options = load_stock_options()

# ──────────────────────────────────────────────
# Add / Manage Positions
# ──────────────────────────────────────────────
is_new_user = not bool(st.session_state.portfolio)

with st.expander("➕ Add / Manage Positions", expanded=is_new_user):
    if is_new_user:
        st.markdown(
            '<p class="section-intro">'
            'Welcome! Start by adding your first stock below. '
            'Select which market it\'s listed on, search for it by name, enter how many shares you bought and when — '
            'the app looks up the price automatically. '
            'Already have a saved portfolio? Import it or load the sample to explore.</p>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            '<p class="section-intro">'
            'Add a new position or remove an existing one. '
            'Each time you bought the same stock counts as a separate purchase.</p>',
            unsafe_allow_html=True
        )

    # Import / Load Sample
    col_import, col_sample = st.columns([3, 1], vertical_alignment="bottom")
    uploaded_file = col_import.file_uploader("Import saved portfolio (.json file)", type="json")
    st.caption("Use the file you previously exported with the 'Export Portfolio' button.")
    if col_sample.button("Load Sample Portfolio", use_container_width=True):
        import os
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

    st.markdown("---")

    # Add Position form
    manual_price = st.session_state.get("manual_price_toggle", False)
    col1, col2, col3, col4 = st.columns([2, 2, 2, 1])

    with col1:
        index_choice = st.selectbox(
            "Stock Market",
            options=list(all_stock_options.keys()),
            index=0,
        )
        st.caption("US → S&P 500 · UK → FTSE 100 · Switzerland → SMI · Germany → DAX")
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
            st.caption("Leave unchecked to use the actual market price on that date (recommended).")
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
                shares = round(amount_input / buy_price, 6) if alt_asset else shares_input
                lot = {
                    "shares": shares,
                    "buy_price": buy_price,
                    "purchase_date": str(purchase_date) if purchase_date else None,
                    "manual_price": manual_price
                }
                st.session_state.portfolio.setdefault(ticker, []).append(lot)
                st.success(f"Added {shares:g} units of {ticker} at {currency_symbol}{buy_price:,.2f}")

    # Manage existing positions
    if st.session_state.portfolio:
        st.markdown("---")
        col_manage_title, col_clear, col_spacer = st.columns([3, 1, 6], vertical_alignment="bottom")
        col_manage_title.markdown("**Your purchases**")
        if col_clear.button("Clear All", key="clear_portfolio"):
            st.session_state.confirm_clear = True

        if st.session_state.confirm_clear:
            st.warning("This will delete all your positions. Are you sure?")
            col_yes, col_no, _ = st.columns([1, 1, 8])
            if col_yes.button("Yes, clear all", key="confirm_clear_yes"):
                st.session_state.portfolio = {}
                st.session_state.confirm_clear = False
                st.rerun()
            if col_no.button("Cancel", key="confirm_clear_no"):
                st.session_state.confirm_clear = False
                st.rerun()

        for t, lots in list(st.session_state.portfolio.items()):
            for i, lot in enumerate(lots):
                col_name, col_detail, col_date, col_btn, col_spacer = st.columns([2, 3, 2, 1, 3])
                col_name.write(f"{t} — Buy {i + 1}")
                tc = get_ticker_currency(t)
                display_tc = "GBP" if tc == "GBX" else tc
                col_detail.caption(f"{lot['shares']:g} shares · {display_tc} {lot['buy_price']:,.2f}")
                col_date.write(lot["purchase_date"] or "Manual")
                if col_btn.button("×", key=f"remove_{t}_{i}"):
                    st.session_state.pending_remove = (t, i)
                    st.rerun()

        if st.session_state.pending_remove:
            pt, pi = st.session_state.pending_remove
            st.warning(f"Remove {pt} (Buy {pi + 1})? This cannot be undone.")
            col_yes, col_no, _ = st.columns([1, 1, 8])
            if col_yes.button("Remove", key="confirm_remove_yes"):
                st.session_state.portfolio[pt].pop(pi)
                if not st.session_state.portfolio[pt]:
                    del st.session_state.portfolio[pt]
                st.session_state.pending_remove = None
                st.rerun()
            if col_no.button("Cancel", key="confirm_remove_no"):
                st.session_state.pending_remove = None
                st.rerun()

# ──────────────────────────────────────────────
# Portfolio Display
# ──────────────────────────────────────────────
if not st.session_state.portfolio:
    st.stop()

st.divider()

df = build_portfolio_df(st.session_state.portfolio, base_currency)

if df.empty:
    st.warning("Could not retrieve price data for any positions.")
    st.stop()

# ── Shared display helpers ─────────────────
# Single color map keyed by portfolio insertion order — used consistently across all charts.
portfolio_color_map = {
    t: TICKER_COLORS.get(t, CHART_COLORS[i % len(CHART_COLORS)])
    for i, t in enumerate(st.session_state.portfolio.keys())
}
# Company names — falls back to ticker if fetch fails.
name_map = {t: fetch_company_name(t) for t in st.session_state.portfolio}

# ── KPI Cards ────────────────────────────────
total_value   = df["Total Value"].sum()
daily_pnl     = df["Daily P&L"].sum()
n_positions   = len(st.session_state.portfolio)
cost_basis    = (df["Buy Price"] * df["Shares"]).sum()
total_divs    = df["Dividends"].sum()
total_return  = total_value + total_divs - cost_basis
total_ret_pct = (total_return / cost_basis * 100) if cost_basis else 0.0

pnl_color  = "#2e7d32" if daily_pnl    >= 0 else "#c0392b"
ret_color  = "#2e7d32" if total_return >= 0 else "#c0392b"

n_purchases = sum(len(lots) for lots in st.session_state.portfolio.values())
positions_sub = f'<div style="color: var(--text-color); opacity: 0.55; font-size:12px; margin-top:4px;">{n_purchases} purchases</div>' if n_purchases != n_positions else ""

_all_dates = [lot["purchase_date"] for lots in st.session_state.portfolio.values() for lot in lots if lot.get("purchase_date")]
_first_purchase = min(_all_dates) if _all_dates else None
return_sub = f'<div style="color: var(--text-color); opacity: 0.55; font-size:12px; margin-top:4px;">Since {_first_purchase}</div>' if _first_purchase else ""

col_m1, col_m2, col_m3, col_m4 = st.columns(4)

_spacer_line_md  = '<div style="font-size:14px; margin-top:4px; visibility:hidden;">.</div>'
_spacer_line_sm  = '<div style="font-size:12px; margin-top:4px; visibility:hidden;">.</div>'

with col_m1:
    st.markdown(f"""
    <div class="kpi-card" style="border: 1px solid rgba(128,128,128,0.3);">
        <div class="kpi-label">Total Portfolio Value</div>
        <div class="kpi-value" style="color: var(--text-color);">{currency_symbol}{total_value:,.2f}</div>
        {_spacer_line_md}
        {_spacer_line_sm}
    </div>
    """, unsafe_allow_html=True)

with col_m2:
    st.markdown(f"""
    <div class="kpi-card" style="border: 1px solid {pnl_color};">
        <div class="kpi-label">Today's Change</div>
        <div class="kpi-value" style="color: {pnl_color};">
            {"+" if daily_pnl >= 0 else ""}{currency_symbol}{daily_pnl:,.2f}
        </div>
        <div style="color: var(--text-color); opacity: 0.55; font-size:14px; margin-top:4px;">Since yesterday's close</div>
        {_spacer_line_sm}
    </div>
    """, unsafe_allow_html=True)

with col_m3:
    st.markdown(f"""
    <div class="kpi-card" style="border: 1px solid {ret_color};">
        <div class="kpi-label">Total Return</div>
        <div class="kpi-value" style="color: {ret_color};">
            {"+" if total_return >= 0 else ""}{currency_symbol}{total_return:,.2f}
        </div>
        <div style="color: {ret_color}; font-size: 14px; margin-top: 4px;">
            {"+" if total_ret_pct >= 0 else ""}{total_ret_pct:,.2f}%
        </div>
        {return_sub if return_sub else _spacer_line_sm}
    </div>
    """, unsafe_allow_html=True)

with col_m4:
    st.markdown(f"""
    <div class="kpi-card" style="border: 1px solid rgba(128,128,128,0.3);">
        <div class="kpi-label">Positions</div>
        <div class="kpi-value" style="color: var(--text-color);">{n_positions}</div>
        {positions_sub if positions_sub else _spacer_line_md}
        {_spacer_line_sm}
    </div>
    """, unsafe_allow_html=True)

from datetime import datetime
_last_updated = datetime.now().strftime("%H:%M")
st.markdown(
    f'<p style="text-align:right; color: var(--text-color); opacity: 0.55; font-size:12px; margin-top:4px;">Prices last fetched at {_last_updated} (cached up to 15 min)</p>',
    unsafe_allow_html=True
)
st.markdown("<div style='margin-bottom: 16px;'></div>", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# Positions Table
# ──────────────────────────────────────────────
st.divider()
with st.expander("📋 Your Positions", expanded=True):
    st.markdown(
        '<p class="section-intro">Every stock you own, how much you paid, what it\'s worth now, '
        'and how much you\'ve gained or lost. <b>Today\'s Change</b> is how much your value moved since yesterday\'s market close. '
        '<b>Total Return</b> includes any dividends received. <b>Portfolio Share</b> is what percentage of your total investment this position represents.</p>',
        unsafe_allow_html=True
    )

    styled_df = df.copy().rename(columns={
        "Return (%)": "Total Return (%)",
        "Weight (%)": "Portfolio Share (%)",
        "Daily P&L":  "Today's Change",
        "Purchase":   "Buy #",
    })
    styled_df.insert(1, "Company", styled_df["Ticker"].map(name_map))

    def _color_pnl(val):
        if val > 0:   return "color: #2e7d32; font-weight: 500"
        elif val < 0: return "color: #c0392b; font-weight: 500"
        return "color: var(--text-color)"

    def _fmt_shares(x):
        return f"{int(x):,}" if x == int(x) else f"{x:g}"

    styled = (
        styled_df.set_index(["Ticker", "Company", "Buy #"])
        .style
        .format({
            "Shares":           _fmt_shares,
            "Buy Price":        lambda x: f"{currency_symbol}{x:,.2f}",
            "Current Price":    lambda x: f"{currency_symbol}{x:,.2f}",
            "Total Value":      lambda x: f"{currency_symbol}{x:,.2f}",
            "Dividends":        lambda x: f"{currency_symbol}{x:,.2f}",
            "Today's Change":   lambda x: f"{currency_symbol}{x:,.2f}",
            "Total Return (%)": "{:,.2f}%",
            "Portfolio Share (%)": "{:,.2f}%",
        })
        .map(_color_pnl, subset=["Today's Change", "Total Return (%)"])
    )

    st.dataframe(styled, use_container_width=True, column_config={
        "Shares":    st.column_config.TextColumn("Shares", width="small"),
        "Dividends": st.column_config.NumberColumn("Dividends", help="Total dividends received since purchase. Already included in Total Return."),
    })

    st.download_button(
        label="Export Portfolio",
        data=pd.Series(st.session_state.portfolio).to_json(),
        file_name="portfolio.json",
        mime="application/json"
    )

# ──────────────────────────────────────────────
# Portfolio Allocation
# ──────────────────────────────────────────────
st.divider()
with st.expander("📊 Portfolio Allocation", expanded=True):
    st.markdown(
        '<p class="section-intro">How your money is spread across your positions. '
        'Larger bars mean a bigger share of your total investment in that stock.</p>',
        unsafe_allow_html=True
    )

    alloc_df = (
        df.groupby("Ticker")["Total Value"]
        .sum()
        .reset_index()
        .assign(**{"Portfolio Share (%)": lambda x: (x["Total Value"] / x["Total Value"].sum() * 100).round(2)})
        .sort_values("Portfolio Share (%)", ascending=True)
    )
    alloc_df["Company"] = alloc_df["Ticker"].map(name_map)
    alloc_color_map = {name_map[t]: portfolio_color_map[t] for t in alloc_df["Ticker"]}
    fig_alloc = px.bar(
        alloc_df,
        x="Portfolio Share (%)",
        y="Company",
        orientation="h",
        color="Company",
        color_discrete_map=alloc_color_map,
        text=alloc_df["Portfolio Share (%)"].map(lambda v: f"{v:.1f}%"),
    )
    fig_alloc.update_traces(textposition="outside")
    fig_alloc.update_layout(
        xaxis_title="Portfolio Share (%)",
        yaxis_title=None,
        showlegend=False,
        template="plotly",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(range=[0, alloc_df["Portfolio Share (%)"].max() * 1.15]),
    )
    st.plotly_chart(fig_alloc, use_container_width=True)

# ──────────────────────────────────────────────
# Side-by-Side Comparison
# ──────────────────────────────────────────────
st.divider()
with st.expander("📈 How My Stocks Compare", expanded=True):
    st.markdown(
        '<p class="section-intro">All your stocks shown on the same scale. '
        'Every stock starts at 100 on the left so you can fairly compare their growth — '
        'a stock at 120 has grown 20%, a stock at 85 has fallen 15%. '
        'Click a ticker in the legend to hide or show it. '
        'Enable <b>Currency-adjusted</b> to account for exchange rate changes if you hold stocks in different currencies.</p>',
        unsafe_allow_html=True
    )

    col_range, col_fx_comp = st.columns([3, 2], vertical_alignment="bottom")
    with col_range:
        range_options = {"3 months": "3mo", "6 months": "6mo", "1 year": "1y", "All time": "max"}
        range_label = st.radio("Time range", list(range_options.keys()), index=1, horizontal=True)
        selected_range = range_options[range_label]
    with col_fx_comp:
        fx_adjust_comparison = st.toggle("Currency-adjusted", key="fx_toggle_comparison")

    @st.cache_data(ttl=900)
    def fetch_price_history_range(ticker: str, period: str) -> pd.DataFrame:
        try:
            hist = yf.Ticker(ticker).history(period=period)
            hist.index = hist.index.tz_localize(None)
            return hist
        except Exception:
            return pd.DataFrame()

    comparison_data = {}
    for t in st.session_state.portfolio:
        hist = fetch_price_history_range(t, selected_range)
        if hist.empty:
            st.warning(f"Could not load data for {t} — skipping.")
            continue
        ticker_currency = get_ticker_currency(t)
        if fx_adjust_comparison and ticker_currency != base_currency:
            fx_pair = "GBP" if ticker_currency == "GBX" else ticker_currency
            fx_hist = fetch_price_history_range(f"{fx_pair}{base_currency}=X", selected_range)
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

    comp_name_map = {t: name_map.get(t, t) for t in comparison_df.columns}
    comp_color_map = {comp_name_map[t]: portfolio_color_map[t] for t in comparison_df.columns if t in portfolio_color_map}
    comparison_df_display = comparison_df.rename(columns=comp_name_map)
    title_suffix = f"({base_currency}-adjusted)" if fx_adjust_comparison else "(native currencies)"
    fig_comp = px.line(
        comparison_df_display,
        x=comparison_df_display.index,
        y=comparison_df_display.columns,
        color_discrete_map=comp_color_map,
    )
    fig_comp.update_layout(
        xaxis_title="Date",
        yaxis_title=f"Indexed growth (100 = start)  —  {range_label}  {title_suffix}",
        legend_title="Stock",
        template="plotly",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    fig_comp.add_hline(y=100, line_dash="dash", line_color="gray")
    st.plotly_chart(fig_comp, use_container_width=True)

# ──────────────────────────────────────────────
# Price History
# ──────────────────────────────────────────────
st.divider()
st.markdown("### 🕐 Price History")
st.markdown(
    '<p class="section-intro">The full price history for each stock you own. '
    'The dashed line shows what you paid. The grey line marks when you bought it. '
    'Prices are shown in each stock\'s native trading currency — enable <b>Currency-adjusted</b> to convert to your base currency. '
    'Click any stock below to expand its chart.</p>',
    unsafe_allow_html=True
)

col_range_hist, col_to, col_fx, _ = st.columns([4, 2, 2, 3])
with col_range_hist:
    hist_range_options = ["3 months", "6 months", "1 year", "2 years", "Since purchase", "Custom"]
    hist_range_label = st.radio("Time range", hist_range_options, index=4, horizontal=True, key="hist_range")
with col_to:
    date_to = st.date_input("To", value=pd.Timestamp.today())
with col_fx:
    st.write(" ")
    st.write(" ")
    fx_adjust_history = st.toggle("Currency-adjusted", key="fx_toggle_history")

date_from = None
if hist_range_label == "Custom":
    date_from = st.date_input("From date", value=None, min_value=pd.Timestamp("1980-01-01").date(), key="hist_custom_from")

_hist_range_months = {"3 months": 3, "6 months": 6, "1 year": 12, "2 years": 24}

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
    auto_from = (
        min(pd.Timestamp(d) for d in dates) - pd.DateOffset(months=2)
        if dates else pd.Timestamp.today() - pd.DateOffset(months=6)
    )
    if hist_range_label == "Since purchase":
        effective_from = auto_from
    elif hist_range_label == "Custom":
        effective_from = pd.Timestamp(date_from) if date_from else auto_from
    else:
        effective_from = pd.Timestamp.today() - pd.DateOffset(months=_hist_range_months[hist_range_label])

    line_color = portfolio_color_map.get(t, CHART_COLORS[idx % len(CHART_COLORS)])
    title_suffix = f"({base_currency}-adjusted)" if fx_adjust_history else f"({ticker_currency})"
    company = name_map.get(t, t)
    with st.expander(f"{company} ({t}) — Price History {title_suffix}", expanded=False):
        if ticker_currency == "GBX" and not fx_adjust_history:
            st.caption("Prices shown in GBX (British pence). 100 GBX = 1 GBP. Enable Currency-adjusted above to convert to your base currency.")
        fig_hist = px.line(
            hist_converted,
            x=hist_converted.index,
            y="Close",
            color_discrete_sequence=[line_color],
        )
        fig_hist.update_layout(
            xaxis_title="Date",
            yaxis_title=y_label,
            xaxis_range=[str(pd.Timestamp(effective_from).date()), str(date_to)],
            showlegend=False,
            template="plotly",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )

        for i, lot in enumerate(lots):
            if fx_adjust_history:
                fx_rate = get_fx_rate(ticker_currency, base_currency)
                buy_price_display = round(lot["buy_price"] * fx_rate, 2)
                buy_label = f"Buy {i + 1}  {currency_symbol}{buy_price_display}"
            else:
                buy_price_display = lot["buy_price"]
                buy_label = f"Buy {i + 1}  {buy_price_display}"

            fig_hist.add_hline(
                y=buy_price_display,
                line_dash="dash",
                line_color="#e6a817",  # amber — visible on both light and dark backgrounds
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

# ──────────────────────────────────────────────
# Risk & Analytics
# ──────────────────────────────────────────────
st.divider()
with st.expander("🔬 Risk & Analytics", expanded=False):
    st.markdown(
        '<p class="section-intro">A deeper look at how risky your positions are and how efficiently they\'ve rewarded that risk. '
        'All figures are based on the past 12 months of daily price data. '
        'This section uses financial industry-standard metrics — each one is explained below its table.</p>',
        unsafe_allow_html=True
    )

    _tickers = list(st.session_state.portfolio.keys())
    _price_data_1y = {t: fetch_analytics_history(t) for t in _tickers}
    _spy_data = fetch_analytics_history("SPY")

    analytics_df = compute_analytics(st.session_state.portfolio, _price_data_1y, _spy_data)

    if not analytics_df.empty:
        # ── Risk Metrics ──
        st.markdown("##### Risk Metrics")
        st.markdown(
            '<p class="section-intro">'
            '📊 <b>Volatility</b> — how much the price typically swings in a year. 25% means it moves roughly ±25% over 12 months. Higher = more unpredictable.<br>'
            '📉 <b>Worst Drop</b> — the biggest fall from a peak in the past year. −35% means it dropped 35% from its highest point before recovering.<br>'
            '⚖️ <b>Return/Risk Score</b> — how much return you earned per unit of risk. Above 1 is good; above 2 is excellent; below 0 means the risk was not rewarded.<br>'
            '📈 <b>Market Sensitivity</b> — how much this stock moves when the S&P 500 moves. 1.0 = moves exactly with the market; 1.5 = moves 50% more; 0.5 = half as much.'
            '</p>',
            unsafe_allow_html=True
        )

        def _color_sharpe(val):
            if not isinstance(val, (int, float)): return ""
            if val >= 1:   return "color: #2e7d32"
            if val >= 0:   return "color: #b8860b"
            return "color: #c0392b"

        def _color_volatility(val):
            if not isinstance(val, (int, float)): return ""
            if val <= 20:  return "color: #2e7d32"
            if val <= 35:  return "color: #b8860b"
            return "color: #c0392b"

        def _color_drawdown(val):
            if not isinstance(val, (int, float)): return ""
            if val >= -20: return "color: #2e7d32"
            if val >= -40: return "color: #b8860b"
            return "color: #c0392b"

        risk_display = analytics_df.set_index("Ticker").rename(columns={
            "Volatility":   "Volatility (%)",
            "Max Drawdown": "Worst Drop (%)",
            "Sharpe Ratio": "Return/Risk Score",
            "Beta":         "Market Sensitivity",
        })

        styled_risk = (
            risk_display.style
            .format({
                "Volatility (%)":     "{:.1f}%",
                "Worst Drop (%)":     "{:.1f}%",
                "Return/Risk Score":  "{:.2f}",
                "Market Sensitivity": "{:.2f}",
            }, na_rep="—")
            .map(_color_volatility, subset=["Volatility (%)"])
            .map(_color_drawdown,   subset=["Worst Drop (%)"])
            .map(_color_sharpe,     subset=["Return/Risk Score"])
        )
        st.dataframe(styled_risk, use_container_width=True)

        # ── Correlation Matrix ──
        if len(_tickers) >= 2:
            st.markdown("##### How Your Stocks Move Together")
            st.markdown(
                '<p class="section-intro">'
                'Shows how closely your positions move in sync. '
                '<b>1.0</b> = always move in the same direction at the same time. '
                '<b>−1.0</b> = always move in opposite directions. '
                '<b>0</b> = no relationship at all. '
                'Holding stocks that don\'t all move together reduces your overall risk — if one falls, the others may not. '
                'If you see no blue cells, it means none of your stocks tend to move in opposite directions — this is normal for a typical portfolio.'
                '</p>',
                unsafe_allow_html=True
            )
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
                fig_corr.update_layout(
                    template="plotly",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    margin=dict(t=20),
                    coloraxis_colorbar=dict(title="Correlation"),
                )
                st.plotly_chart(fig_corr, use_container_width=True)

        # ── Fundamentals ──
        st.markdown("##### Valuation & Price Range")
        st.markdown(
            '<p class="section-intro">'
            '💰 <b>P/E Ratio</b> — how much investors pay relative to what the company earns. A P/E of 20 means you pay 20× the company\'s annual earnings per share. Lower can mean better value, but varies widely by industry.<br>'
            '💵 <b>Dividend Yield</b> — the annual cash payment as a % of the current price. 3% means every $100 invested pays $3/year directly to you, regardless of whether the stock price moves.<br>'
            '📏 <b>1-Year Low / High</b> — the cheapest and most expensive the stock has been over the past 12 months.<br>'
            '📍 <b>1-Year Position</b> — where the current price sits in that range. 100% = at the yearly high; 0% = at the yearly low.'
            '</p>',
            unsafe_allow_html=True
        )

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
                    "P/E Ratio":       st.column_config.NumberColumn("P/E Ratio",      format="%.1f"),
                    "Div Yield (%)":   st.column_config.NumberColumn("Div Yield (%)",  format="%.2f"),
                    "1-Year Low":      st.column_config.NumberColumn("1-Year Low",     format="%.2f"),
                    "1-Year High":     st.column_config.NumberColumn("1-Year High",    format="%.2f"),
                    "1-Year Position": st.column_config.ProgressColumn(
                        "1-Year Position",
                        min_value=0,
                        max_value=100,
                        format="%.0f%%",
                    ),
                },
            )

